"""RL allocator sleeve precompute (btcusdt_quant/rl/sleeve_precompute.py): TEST guard, ledger decomposition vs the
Batch-2 Book, log-ledger identity, counterfactual replay vs direct recompute. Synthetic data only."""
import importlib.util
from pathlib import Path
import numpy as np, pandas as pd, pytest
from btcusdt_quant.rl import sleeve_precompute as sp

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("nm_b2_rl_test", ROOT / "out/run_new_model_batch2_20261010.py")
b2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b2)
T0 = pd.Timestamp("2025-12-20", tz="UTC")


# ---------------------------------------------------------------- TEST guard
def test_guard_refuses_test_rows_until_unlock(tmp_path):
    t = pd.date_range("2025-12-31 23:58", periods=4, freq="1min", tz="UTC").as_unit("ns").asi8
    with pytest.raises(sp.TestAccessError):
        sp.guard_times(t)
    assert len(sp.guard_times(t, allow_test=True)) == 4
    assert len(sp.guard_times(t[:2])) == 2
    for y, ts in ((2025, t[:2]), (2026, t[2:])):
        pd.DataFrame({"minute_time": ts, "x": 1.0}).to_parquet(tmp_path / f"grid_{y}.parquet")
    with pytest.raises(sp.TestAccessError):
        sp.read_partitioned(tmp_path, "grid")
    assert len(sp.read_partitioned(tmp_path, "grid", years={2025})) == 2
    assert len(sp.read_partitioned(tmp_path, "grid", allow_test=True)) == 4
    # a mislabeled partition holding TEST rows is still refused by the row check
    pd.DataFrame({"minute_time": t[2:], "x": 1.0}).to_parquet(tmp_path / "grid_2025.parquet")
    with pytest.raises(sp.TestAccessError):
        sp.read_partitioned(tmp_path, "grid", years={2025})


# ---------------------------------------------------------------- synthetic market
def market(n=20 * 1440, seed=0):
    rng = np.random.default_rng(seed)
    c = 40_000 * np.exp(np.cumsum(rng.normal(0, 6e-4, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + rng.uniform(0, 5e-4, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, 5e-4, n))
    t = (T0.value + np.arange(n) * sp.MIN).astype(np.int64)
    ft = t[::480] + np.int64(7)                              # off-minute by 7 ns: Book assigns by bar
    fr = rng.normal(0, 2e-4, len(ft))
    return b2.Market(t, o, h, l, c, np.ones(n), np.ones(n), ft, fr)


def lin_case(seed=0):
    m = market(seed=seed)
    rng = np.random.default_rng(seed + 1)
    dec = np.arange(239, m.N, 240)
    side = rng.choice([-1, 0, 1], len(dec), p=[.3, .3, .4])
    w = np.where(side != 0, rng.uniform(.2, 1, len(dec)), 0.0)
    tr, od = b2.simulate(m, "state", dec, side, w, 2, 60, 0.5, 0, m.N)
    tr = tr.reset_index(drop=True).assign(tid=np.arange(len(tr)))
    return m, tr, od


def test_lin_rows_equal_book_per_minute():
    for seed in range(3):
        m, tr, od = lin_case(seed)
        assert len(tr) > 10 and tr.open_at_end.iloc[-1] in (True, False)
        rows = sp.lin_rows(m.t, m.c, tr, m.N, m.ft, m.fr)
        bk = b2.Book(m, tr.drop(columns="tid"), od, 0, m.N)
        assert np.abs(sp.minute_sum(rows, m.N) - bk.pnl).max() <= 1e-9
        tot = np.bincount(rows["tid"], rows["gross"] + rows["fee"] + rows["funding"], minlength=len(tr))
        assert np.allclose(tot, bk.net4_full, rtol=0, atol=1e-9)


def test_lin_exit_fill_matches_source():
    m, tr, _ = lin_case(0)
    for dec in range(100, m.N - 2000, 997):
        for s in (1, -1):
            for pen in (0.5, 2.0):
                a = sp.exit_fill(m.o, m.h, m.l, m.c, dec, s, m.N, pen)
                b = b2.exit_fill(m, dec, s, m.N, pen)
                assert a[0] == b[0] and (a[0] < 0 or a[1] == b[1])


def lin_direct(m, tr, od, mult, ex, pen):
    t2 = tr.copy()
    t2["entry_weight_frozen"] = t2.entry_weight_frozen * mult
    for q in np.flatnonzero((ex >= 0) & (mult > 0)):
        r = t2.iloc[q]
        xd = int(ex[q]) - 1
        xc = int(r.exit_decision_idx) if not r.open_at_end else m.N
        if not int(r.entry_idx) <= xd < xc:
            continue
        j, px = b2.exit_fill(m, xd, int(r.side), m.N, pen)
        if j < 0 or (not r.open_at_end and j > int(r.exit_idx)):
            continue
        t2.loc[q, ["exit_decision_idx", "exit_idx", "exit_px", "open_at_end"]] = [xd, j, px, False]
    t2 = t2[mult > 0].drop(columns="tid").reset_index(drop=True)
    for c in ("exit_decision_idx", "exit_idx"):
        t2[c] = t2[c].astype(np.int64)
    t2["open_at_end"] = t2.open_at_end.astype(bool)
    return b2.Book(m, t2, od, 0, m.N).pnl


def test_lin_counterfactual_replay_equals_direct_book():
    m, tr, od = lin_case(1)
    rows = sp.lin_rows(m.t, m.c, tr, m.N, m.ft, m.fr)
    mk = {"t": m.t, "o": m.o, "h": m.h, "l": m.l, "c": m.c}
    rng = np.random.default_rng(5)
    n_applied = 0
    for _ in range(20):
        mult = rng.choice(sp.LEVELS, len(tr))
        ex = np.full(len(tr), -1)
        for q in range(len(tr)):
            if rng.random() < .5:
                hi = int(tr.exit_decision_idx.iloc[q]) if not tr.open_at_end.iloc[q] else m.N - 1
                if hi > tr.entry_idx.iloc[q] + 1:
                    ex[q] = rng.integers(tr.entry_idx.iloc[q] + 1, hi + 1)
                    n_applied += 1
        fast = sp.replay("lin", rows, tr, mk, m.ft, m.fr, mult, ex, pen=0.5)
        slow = lin_direct(m, tr, od, mult, ex, 0.5)
        assert np.abs(fast - slow).max() <= 1e-9 and abs(fast.sum() - slow.sum()) <= 1e-6
    assert n_applied > 50
    zero = sp.replay("lin", rows, tr, mk, m.ft, m.fr, np.zeros(len(tr)), np.full(len(tr), -1))
    assert not zero.any()


# ---------------------------------------------------------------- log ledger
def log_case(seed=0):
    m = market(seed=seed)
    t = m.t
    ft = t[::480].copy()                                     # on-minute settlements
    rng = np.random.default_rng(seed + 7)
    e = np.sort(rng.choice(np.arange(10, m.N - 3000, 37), 40, replace=False))
    rows = []
    prev = -1
    for a in e:
        if a <= prev:
            continue
        x = a + int(rng.integers(0, 1500))
        rows.append((a, x))
        prev = x
    e, x = np.array(rows, dtype=np.int64).T
    side = rng.choice([-1, 1], len(e))
    tr = pd.DataFrame({"tid": np.arange(len(e)), "side": side, "units": 1.0, "e": e, "x": x,
                       "px_in": m.o[e], "px_out": m.o[x], "entry_ns": t[e], "exit_ns": t[x]})
    return m, ft, tr


def test_log_rows_trade_identity_and_pess_boundary():
    m, ft, tr = log_case(0)
    fr = np.random.default_rng(3).normal(0, 3e-4, len(ft))
    rows = sp.log_rows(m.t, m.c, tr, 2.0, ft, fr)
    tot = np.bincount(rows["tid"], rows["gross"] + rows["fee"] + rows["funding"], minlength=len(tr))
    for r in tr.itertuples():
        g = r.side * np.log(r.px_out / r.px_in) * 1e4
        v = -r.side * fr * 1e4
        inner = (ft > r.entry_ns) & (ft < r.exit_ns)
        edge = ((ft == r.entry_ns) | (ft == r.exit_ns)) & (v < 0)
        want = g - 4.0 + v[inner | edge].sum()
        assert abs(tot[r.tid] - want) <= 1e-9


def test_log_counterfactual_replay_equals_rebuilt_rows():
    m, ft, tr = log_case(1)
    fr = np.random.default_rng(4).normal(0, 3e-4, len(ft))
    rows = sp.log_rows(m.t, m.c, tr, 2.0, ft, fr)
    mk = {"t": m.t, "o": m.o, "h": m.h, "l": m.l, "c": m.c}
    rng = np.random.default_rng(9)
    for _ in range(20):
        mult = rng.choice(sp.LEVELS, len(tr))
        ex = np.where(rng.random(len(tr)) < .5, tr.e + rng.integers(1, 1600, len(tr)), -1)
        fast = sp.replay("log", rows, tr, mk, ft, fr, mult, ex)
        t2 = tr.copy()
        ok = (ex >= 0) & (ex > tr.e) & (ex <= tr.x)
        t2.loc[ok, "x"] = ex[ok]
        t2.loc[ok, "px_out"] = m.o[ex[ok]]
        t2.loc[ok, "exit_ns"] = m.t[ex[ok]]
        t2["units"] = mult
        t2 = t2[mult > 0]
        slow = sp.minute_sum(sp.log_rows(m.t, m.c, t2, 2.0, ft, fr), m.N)
        assert np.abs(fast - slow).max() <= 1e-9
    assert not sp.replay("log", rows, tr, mk, ft, fr, np.zeros(len(tr)), np.full(len(tr), -1)).any()


def test_intervals():
    assert sp.interval_mask(10, [1, 5], [2, 4]).tolist() == [0, 1, 1, 0, 0, 0, 0, 0, 0, 0]
    assert sp.interval_fill(6, [0, 2], [2, 3], [7, 8], -1, int).tolist() == [7, 7, 8, 8, -1, -1]
