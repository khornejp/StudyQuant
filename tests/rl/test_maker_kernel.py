"""Signed-size maker kernel: parity with the Batch-2 sleeve path (state kind, one position) and order/risk properties."""
import importlib.util, sys
from pathlib import Path
import numpy as np, pandas as pd, pytest
from btcusdt_quant.rl import maker_kernel as MK

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("nm_b2_mk_t", ROOT / "out/run_new_model_batch2_20261010.py")
b2 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = b2
spec.loader.exec_module(b2)


def market(n=40 * 1440, seed=0, vol=6e-4):
    rng = np.random.default_rng(seed)
    c = 40_000 * np.exp(np.cumsum(rng.normal(0, vol, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + rng.uniform(0, 5e-4, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, 5e-4, n))
    t = (pd.Timestamp("2024-01-01", tz="UTC").value + np.arange(n) * 60_000_000_000).astype(np.int64)
    ft = t[::480].copy()
    fr = rng.normal(1e-4, 2e-4, len(ft))
    return b2.Market(t, o, h, l, c, np.ones(n), np.ones(n), ft, fr)


def kernel(m, off, pen):
    return MK.Kernel(m.o, m.h, m.l, m.c, m.t, m.ft, m.fr, off, pen)


@pytest.mark.parametrize("seed,side,off,pen", [(1, 1, 2, 0.5), (2, -1, 5, 2.0), (3, 1, 5, 1.0)])
def test_parity_with_batch2_state_sleeve(seed, side, off, pen):
    m = market(seed=seed)
    rng = np.random.default_rng(seed + 10)
    dec = np.arange(239, m.N - 2000, 240)
    tgt = side * (rng.random(len(dec)) < 0.5).astype(int)
    tr, od = b2.simulate(m, "state", dec, tgt, np.ones(len(dec)), off, 60, pen, 0, m.N)
    bk = b2.Book(m, tr, od, 0, m.N)
    k = kernel(m, off, pen)
    k.reset(int(dec[0]))
    for q in range(len(dec)):
        k.step(float(tgt[q]), 240 if q + 1 < len(dec) else 1440)
    hi = int(dec[-1]) + 1440
    end = int(dec[0]) + 1200                                # legacy sleeve parity before A8's 24 h lease can fire
    assert np.allclose(k.pnl[:end], bk.pnl[:end], rtol=0, atol=1e-9)
    assert hi <= m.N


def test_properties_reselect_cancel_reversal_funding():
    m = market(seed=5, vol=1e-5)                            # near-flat prices: entry orders rarely fill
    k = kernel(m, 5, 2.0)
    i = k.reset(1000)
    k.step(1.0, 5)
    exp0 = k.st[MK.S_PEXP]
    k.step(1.0, 5)                                          # same target re-selected: TTL not reset
    assert k.st[MK.S_PEND] == 0 or k.st[MK.S_PEXP] == exp0
    k.step(0.5, 5)                                          # changed target: replacement rests from i + 2
    if k.st[MK.S_PEND]:
        assert k.st[MK.S_PSTART] == i + 10 + 2 and k.st[MK.S_PTGT] == 0.5
    m = market(seed=6)
    k = kernel(m, 2, 0.5)
    k.reset(500)
    sides = []
    for q in range(400):
        tg = [1.0, -1.0, 0.25, -0.75, 0.0][q % 5]
        k.step(tg, 60)
        sides.append(k.st[MK.S_U])
    u = k.upath[501:k.i + 1]
    assert np.abs(u).max() <= 1.0 + 1e-12
    du = np.diff(np.r_[0.0, u])
    assert not np.any((np.r_[0.0, u[:-1]] * u) < -1e-12)     # never long and short across one minute (flat between)
    assert np.isclose(k.pnl.sum(), k.st[MK.S_EQ]) and k.st[MK.S_FILLS] > 50
    assert np.all(np.isin(np.round(np.abs(du[np.abs(du) > 0]) * 4, 9), [1, 2, 3, 4, 5, 6, 7, 8]))


def test_funding_pess_and_manual_kill_aborts():
    m = market(seed=7)
    k = kernel(m, 2, 0.5)
    k.reset(100, kill=True)
    r = k.step(1.0, 60)
    assert r["fault"] and r["kill_reason"] == "manual_kill" and r["episode_aborted"] and k.pnl.sum() == 0.0
    assert r["minutes_valid"] == 0 and k.st[MK.S_U] == 0                        # no flatten simulated
    k = kernel(m, 2, 0.5)
    k.reset(100)
    for _ in range(200):
        k.step(1.0, 60)
    s = np.flatnonzero(np.isfinite(k.frate))
    s = s[(s > 200) & (s < k.i)]
    held = s[(k.upath[s - 1] == 1.0) & (k.upath[s] == 1.0)]
    assert len(held) > 3


def _faulty(kind):
    m = market(seed=11)
    k0 = 3000
    if kind == "gap":
        m.t[k0:] += 60_000_000_000                                               # 1-minute hole
    elif kind == "nan":
        m.c[k0] = np.nan
    else:
        m.h[k0] = min(m.o[k0], m.c[k0]) - 1.0                                    # high below open/close
    return m, k0


def test_fault_kill_records_prefix_without_flatten():
    for kind, reason in (("gap", "data_gap_or_timestamp_discontinuity"), ("nan", "nonfinite_ohlc"),
                         ("ohlc", "ohlc_invariant")):
        m, k0 = _faulty(kind)
        k = kernel(m, 2, 0.5)
        k.reset(1000)
        r = None
        for _ in range(100):
            r = k.step(1.0, 60)
            if r["fault"]:
                break
        assert r["fault"] and r["kill_reason"] == reason and r["kill_count"] == 1
        assert r["valid_prefix_minutes"] == k0 - 1001 and r["fault_time"] == int(m.t[k0])
        u_before = k.upath[k0 - 1]
        assert k.st[MK.S_U] == u_before                                          # position left as is (no fake flatten)
        n = k.step(0.0, 60)
        assert n["fault"] and n["minutes_valid"] == 0


def test_no_unselected_stop_but_renewable_cap_applies():
    m = market(seed=8)
    m.c[5000:] = m.c[5000:] * np.linspace(1.0, 0.9, m.N - 5000)                  # -10 % slide: no stop in A6
    m.o[5000:] = np.r_[m.c[4999], m.c[5000:-1]]
    m.h[:] = np.maximum(m.h, np.maximum(m.o, m.c))
    m.l[:] = np.minimum(m.l, np.minimum(m.o, m.c))
    k = kernel(m, 2, 0.5)
    k.reset(4000)
    for _ in range(300):
        k.step(1.0, 60)
    u = k.upath[4001:k.i + 1]
    first = int(np.argmax(u == 1.0))
    assert u[first] == 1.0 and k.st[MK.S_SLCOUNT] == 0 and k.st[MK.S_TPCOUNT] == 0
    assert k.st[MK.S_CAPCOUNT] > 0 and k.st[MK.S_MAXHOLD] <= 1440               # only lease renewals flatten
    d = MK.diagnostics(k.st)
    assert d["kill_count"] == 0 and not d["episode_aborted"]


def flat_market(n=5000):
    from types import SimpleNamespace
    c = np.full(n, 100.0)
    o = c.copy(); h = np.full(n, 101.0); l = np.full(n, 99.0)
    t = (pd.Timestamp("2024-01-01", tz="UTC").value + np.arange(n) * MK.MIN_NS).astype(np.int64)
    return SimpleNamespace(o=o, h=h, l=l, c=c, t=t, ft=np.array([], np.int64), fr=np.array([]), N=n)


def test_a8_cap_boundary_clock_and_no_automatic_reentry():
    m = flat_market()
    k = kernel(m, 2, 0.5)
    i = k.reset(100)
    r = k.step(1.0, 1440)
    assert r["j"] == i + 1440 and r["step_exit_reason"] == "cap"
    assert k.st[MK.S_MAXHOLD] == 1440 and k.st[MK.S_U] == 0 and not k.st[MK.S_PEND]
    assert k.upath[r["j"] - 1] == 1.0 and k.upath[r["j"]] == 0.0                # 1439 / 1440 boundary
    assert r["fault"] is False and r["renewal_count"] == 1
    before = k.i
    assert k.st[MK.S_REENTRYFILL] == 0                                          # cap never auto re-enters
    k.step(1.0, 5)
    assert k.i - before == 5 and k.st[MK.S_REENTRYREQ] == 1 and k.st[MK.S_REENTRYFILL] == 1
    assert k.st[MK.S_RENEWCOST] == 4.0 and k.st[MK.S_FLATGAP] == 0


def test_a8_increase_reduction_do_not_reset_clock_flat_and_reversal_do():
    m = flat_market()
    k = kernel(m, 2, 0.5)
    k.reset(100)
    k.step(0.5, 5); opened = k.st[MK.S_OPENK]
    k.step(1.0, 5)
    assert k.st[MK.S_OPENK] == opened
    k.step(0.25, 5)
    assert k.st[MK.S_OPENK] == opened
    k.step(0.0, 5)
    assert k.st[MK.S_U] == 0 and k.st[MK.S_OPENK] == -1
    k.step(-1.0, 5)
    assert k.st[MK.S_U] == -1 and k.st[MK.S_OPENK] > opened


def test_a8_passive_exit_and_leg2_are_cancelled_by_cap():
    m = flat_market()
    m.h[:] = 100.0                                                        # buy entry fills; sell reduction never does
    k = kernel(m, 2, 0.5)
    k.reset(100)
    k.step(1.0, 5)
    assert k.st[MK.S_U] == 1
    r = k.step(-1.0, 1440)
    assert r["step_exit_reason"] == "cap" and k.st[MK.S_U] == 0
    assert k.st[MK.S_PEND] == 0 and k.st[MK.S_LEG2] == 0 and k.st[MK.S_REQ] > 0


def test_a8_same_bar_sl_wins_gap_price_and_tp_is_trigger_price():
    m = flat_market()
    k = kernel(m, 2, 0.5)
    k.reset(100)
    k.step(1.0, 5)
    basis = k.st[MK.S_BASIS]
    i = k.i
    rv = 1000.0
    sigma = rv * np.sqrt(5 / 1440)
    trigger = basis * (1 - sigma / 1e4)
    m.o[i + 1] = trigger - 5.0
    m.l[i + 1] = m.o[i + 1]
    m.h[i + 1] = basis * (1 + sigma / 1e4) + 1.0                            # both barriers touch
    r = k.step(1.0, 5, sl_mult=1, tp_mult=1, rv_bps=rv)
    assert r["step_exit_reason"] == "SL" and r["j"] == i + 1 and k.st[MK.S_SLCOUNT] == 1
    expected = (m.o[i + 1] / basis - 1) * 1e4 - 2 * MK.FEE_SIDE
    assert np.isclose(k.st[MK.S_SLPNL], expected, atol=1e-9)                  # gap open, full RT fees

    m = flat_market(); k = kernel(m, 2, 0.5); k.reset(100); k.step(1.0, 5)
    basis, i = k.st[MK.S_BASIS], k.i
    trigger = basis * (1 + sigma / 1e4)
    m.h[i + 1], m.l[i + 1], m.o[i + 1] = trigger + 5, basis, trigger + 3
    r = k.step(1.0, 5, tp_mult=1, rv_bps=rv)
    assert r["step_exit_reason"] == "TP" and r["j"] == i + 1 and k.st[MK.S_TPCOUNT] == 1
    expected = (trigger / basis - 1) * 1e4 - 2 * MK.FEE_SIDE
    assert np.isclose(k.st[MK.S_TPPNL], expected, atol=1e-9)                  # trigger price, full RT fees


def test_flat_diagnostics_and_k_reset():
    m = market(seed=12)
    k = kernel(m, 2, 0.5)
    k.reset(2000)
    for _ in range(10):
        k.step(0.0, 240)
    assert k.kpath[k.i] == k.i - 2000 and MK.diagnostics(k.st)["flat_hours"] == (k.i - 2000) / 60.0
    for _ in range(30):
        k.step(1.0, 15)
    first = int(np.flatnonzero(k.upath[2001:k.i + 1] != 0)[0]) + 2001
    assert k.kpath[first + 58] > 0 and k.kpath[first + 59] == 0                  # reset after 60 non-flat minutes
    assert MK.diagnostics(k.st)["flat_to_fill_h"] > 0


def test_reward_decomposition():
    from btcusdt_quant.rl import smdp_reward as RW
    m = market(seed=9)
    k = kernel(m, 2, 0.5)
    i = k.reset(2000)
    r = k.step(1.0, 60)
    rv = MK.rv24h(m.c)
    mp = RW.m_of_t(rv, np.full(m.N, float(np.median(rv[1440:]))), RW.RewardConfig())
    cfg = RW.RewardConfig(idle_bps_per_h=0.3, inventory_bps_per_h=0.1, turnover_bps=0.05, f_kind="linear", f_param=0.1)
    d = RW.step_reward(k.pnl, k.upath, k.kpath, mp, i, r["j"], r["d_target"], cfg)
    assert np.isclose(d["net4"], r["net4"]) and d["blocks"] == 12 and np.isclose(d["turnover"], 0.05)
    assert np.isclose(d["reward"], d["net4"] - d["idle"] - d["inventory"] - d["turnover"])
    import pytest
    with pytest.raises(ValueError):
        RW.step_reward(k.pnl, k.upath, k.kpath, mp, i, r["j"], r["d_target"], RW.RewardConfig())
    assert np.isclose(MK.gamma(30 * 1440), 0.5)
