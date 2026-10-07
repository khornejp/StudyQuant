"""Baselines (plan 3 Task 7): C17 baseline 2 picks, C15 trade relocation, C16 shuffled state, C14 supervised."""
import json, math
from pathlib import Path
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import costs
from btcusdt_quant.sim.rolling import TRAIN_START, WINDOWS, Window
from btcusdt_quant.rl import baselines as B
from btcusdt_quant.rl.state import fit_normalizer
from tests.rl.test_vec_env import MIN, T0, make_store, market

ROOT = Path(__file__).resolve().parents[2] / "out/k45_rl_r2_48_20261007"
PATHS = [ROOT / "strategies", ROOT / "levels_r2_49", ROOT / "levels_r2_50"]
DAY = pd.Timedelta(days=1)


@pytest.mark.skipif(not all((p / "windows.parquet").exists() for p in PATHS), reason="frozen catalog output absent")
def test_baseline2_all_matches_codex_check():
    combos = pd.concat([pd.read_parquet(p / "combos.parquet") for p in PATHS])
    assert len(combos) == 152 and combos.combo.is_unique
    picks = B.baseline2_all(PATHS)
    assert list(picks.window) == [w.name for w in WINDOWS]
    got = dict(zip(picks.window, picks.combo))
    assert got["W04"] == "K25__NONE__NATIVE" and got["W07"] == "K26__NONE__NATIVE"      # Codex's check
    assert not picks.combo.str.match(r"B[123]__").any()
    assert (picks.n_candidates == 144).all()        # 152 - 6 composites - 2 skipped K10 DETEXIT (no rows)
    assert got == {"W01": "K14__GATED__NATIVE", "W02": "K15__NONE__NATIVE", "W03": "K01__NONE__NATIVE",
                   "W04": "K25__NONE__NATIVE", "W05": "K11_15m__GATED__NATIVE", "W06": "K01__NONE__NATIVE",
                   "W07": "K26__NONE__NATIVE", "W08": "K09__NONE__NATIVE", "W09": "K11_1h__GATED__NATIVE",
                   "W10": "K01__NONE__NATIVE"}


def test_relocation_placements_preserve_length_and_never_overlap():
    rng = np.random.default_rng(0)
    lengths = np.array([30, 120, 15, 400, 1])
    starts = B.relocate(lengths, 1440, 500, rng)
    assert starts.shape == (500, 5) and (starts >= 0).all() and (starts + lengths <= 1440).all()
    for row in starts:
        order = np.argsort(row)
        assert (row[order][1:] >= (row + lengths)[order][:-1]).all()      # next entry at or after previous exit
    assert len({tuple(r) for r in starts}) > 450                            # actually random
    np.testing.assert_array_equal(B.relocate(np.array([1440]), 1440, 3, rng), 0)


def test_relocation_mc_preserves_count_side_hold():
    m = market(2, gaps=0)
    win = Window("WX", T0, T0, T0, T0, T0 + DAY, T0 + 2 * DAY)
    a, last = win.test_start, win.test_end - MIN
    # one long over the whole window (forced close): relocation has no freedom, so it reproduces the replay net
    full = pd.DataFrame({"entry_time": [a], "exit_time": [last], "side": [1], "units": [1.0],
                         "exit_reason": ["data_end"]})
    nets = B.relocation_mc(full, win, reps=7, seed=0, minutes=m)
    o, c = m.set_index("open_time").open, m.set_index("open_time").close
    fund = sum(v for _, v in costs.funding_events(1, a, last + pd.Timedelta(1, "ns")))
    assert nets.shape == (7,) and np.allclose(nets, math.log(c[last] / o[a]) * 1e4 - 4 + fund, atol=1e-9)
    # three trades: count, sides and holds survive; nets differ between reps; zero trades -> zeros
    trades = pd.DataFrame({"entry_time": [a + 16 * MIN, a + 301 * MIN, a + 601 * MIN],
                           "exit_time": [a + 76 * MIN, a + 541 * MIN, a + 631 * MIN], "side": [1, -1, 1],
                           "units": 1.0, "exit_reason": "signal"})
    k, lens, sides, starts, nets = B.relocation_mc(trades, win, reps=200, seed=1, minutes=m, detail=True)
    assert k == 3 and list(lens) == [60, 240, 30] and list(sides) == [1, -1, 1] and starts.shape == (200, 3)
    assert np.isfinite(nets).all() and nets.std() > 0
    assert (B.relocation_mc(trades.iloc[:0], win, reps=5, minutes=m) == 0).all()


def test_shuffled_store_permutes_train_day_blocks_only():
    start, end = TRAIN_START - 2 * DAY, TRAIN_START + 10 * DAY
    store = make_store(start, end, missing=np.random.default_rng(3).random(12 * 96) < 0.2)
    store = type(store)(store.times, store.seq, np.column_stack([store.static, np.arange(len(store.times))]),
                        store.mask_missing, store.feature_names + ["hour_sin"], "S1")   # calendar column stays
    train_end = TRAIN_START + 6 * DAY
    s = B.shuffled_store(store, train_end, seed=0)
    t = store.times
    inside = (t >= TRAIN_START.value) & (t < train_end.value)               # 6 whole days; train_end's row stays
    assert inside.sum() == 6 * 96
    np.testing.assert_array_equal(s.times, t)
    np.testing.assert_array_equal(s.static[:, -1], store.static[:, -1])
    for x, y in ((s.static[:, :3], store.static[:, :3]), (s.seq, store.seq), (s.mask_missing, store.mask_missing)):
        np.testing.assert_array_equal(x[~inside], y[~inside])
    src = s.static[inside, 0].reshape(6, 96)
    orig = store.static[inside, 0].reshape(6, 96)
    perm = [int(np.flatnonzero((orig == row).all(1))[0]) for row in src]
    assert sorted(perm) == list(range(6)) and perm != list(range(6))
    for d, p in enumerate(perm):         # seq and the missing mask move with their day's static block
        np.testing.assert_array_equal(s.seq[inside].reshape(6, 96, 32, 4)[d], store.seq[inside].reshape(6, 96, 32, 4)[p])
        np.testing.assert_array_equal(s.mask_missing[inside].reshape(6, 96)[d],
                                      store.mask_missing[inside].reshape(6, 96)[p])
    a, b = fit_normalizer(store, train_end), fit_normalizer(s, train_end)
    np.testing.assert_allclose(a.static_mean, b.static_mean, rtol=1e-12)
    part = B.shuffled_store(store, train_end + pd.Timedelta(hours=6), seed=0)    # partial last day never moves
    tail = (t >= train_end.value) & (t < (train_end + pd.Timedelta(hours=6)).value)
    np.testing.assert_array_equal(part.static[tail], store.static[tail])


def test_supervised_labels_and_switch_rule():
    n = 600
    o = 100 * np.exp(np.arange(n) * 1e-4)                                   # +1 bps per minute
    m = pd.DataFrame({"open_time": T0 + MIN * np.arange(n), "open": o, "high": o, "low": o, "close": o})
    times = pd.date_range(T0, periods=25, freq="15min").as_unit("ns").asi8
    y = B.supervised_labels(times, m)
    ok = np.arange(25) * 15 + 241 < n
    np.testing.assert_allclose(y[ok], np.tile([240 - 4, -240 - 4], (ok.sum(), 1)), atol=1e-9)
    assert np.isnan(y[~ok]).all()
    pred = np.array([[3, -9], [10, -9], [9, 12], [9, 14], [-1, 1], [-1, 30], [-1, 30]], float)
    missing = np.array([0, 0, 0, 0, 0, 1, 0], bool)
    # gain < 4 stays flat; long; short 12 vs 9 is +3 -> hold long; +5 -> reverse; short 1 vs flat 0 -> hold;
    # missing detector: no new entry or reversal (here only hold); then free again
    np.testing.assert_array_equal(B.supervised_policy(pred, missing), [0, 1, 1, -1, -1, -1, -1])
    pred2 = np.array([[10, 0], [0, 20], [-10, -10]], float)
    np.testing.assert_array_equal(B.supervised_policy(pred2, np.array([0, 1, 1], bool)), [1, 1, 0])


def test_fit_supervised_smoke(tmp_path):
    store = make_store(T0, T0 + 3 * DAY)
    m = market(0, gaps=0)
    win = Window("WS", T0, T0 + DAY, T0 + 1.5 * DAY, T0 + 3 * DAY, T0 + 3 * DAY, T0 + 3 * DAY)
    res = B.fit_supervised(store, m, win, tmp_path, seed=0, device="cpu", max_samples=4 * 64 * 2, eval_every=2,
                           minibatch=64)
    assert math.isfinite(res["val_net_bps"]) and (tmp_path / "best.pt").exists()
    assert res["train_rows"] == 97 and len(res["selection_trace"]) == 4       # T0..train_end, labels inside data
    acts = B.supervised_actions(B.load_supervised(tmp_path / "best.pt"), store, win.val_start, win.val_end)
    assert len(acts) == 144 and set(acts.unique()) <= {-1, 0, 1}
