"""Unit checks for out/run_new_model_batch2_20261010.py (synthetic data only)."""
import importlib.util
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("nm_b2", ROOT / "out/run_new_model_batch2_20261010.py")
nm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nm)
MIN = nm.MIN


def market(c, ft=(), fr=(), wick=0.002):
    c = np.asarray(c, float)
    o = np.concatenate([[c[0]], c[:-1]])
    h, l = np.maximum(o, c) * (1 + wick), np.minimum(o, c) * (1 - wick)
    t = nm.START.value + np.arange(len(c)) * MIN
    return nm.Market(t, o, h, l, c, np.ones(len(c)), np.full(len(c), 0.5), np.asarray(ft, np.int64), np.asarray(fr, float))


def test_grid_counts():
    g = nm.grid()
    assert len(g) == 354 and len({nm.vid(p) for p in g}) == 354
    assert {f: sum(p["family"] == f for p in g) for f in nm.FAMILIES} == dict(V=96, E=18, F=48, G=64, H=36, I=24, J=36, K=32)


def test_fill_gap_through_and_penetration():
    o, h, l = np.array([100.0, 99.0]), np.array([100.5, 99.5]), np.array([99.0, 98.0])
    assert nm.first_fill(o, h, l, 0, 2, 99.5, True) == 0               # open above, low trades through
    assert nm.first_fill(o, h, l, 1, 2, 99.5, True) == -1              # gap-through (open below limit) rejected
    assert nm.first_fill(o, h, l, 0, 1, 99.0 / (1 - 0.4e-4), True, pen=0.5) == -1   # only 0.4bp through
    assert nm.first_fill(o, h, l, 0, 1, 99.0 / (1 - 0.4e-4), True, pen=0.3) == 0


def test_no_stale_reentry_and_flip_waits_for_next_decision():
    rng = np.random.default_rng(0)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 5e-4, 1440 * 3)))
    m = market(c)
    dec = np.arange(59, m.N, 60)
    side = np.where(np.arange(len(dec)) < 10, 1, -1)
    side[10] = -1
    side[11:13] = 0                    # target flat right after the flip decision
    tr, od = nm.simulate(m, "state", dec, side, np.ones(len(dec)), 2, 60, 0.5, 0, m.N)
    first = tr.iloc[0]
    assert first.side == 1 and first.exit_decision_idx == dec[10]
    nxt = tr.iloc[1]
    assert nxt.side == -1 and nxt.decision_idx >= first.exit_idx and nxt.decision_idx >= dec[13]


def test_open_not_closed_and_windows_partition_without_split_cost():
    c = np.linspace(100, 110, 1440 * 4)
    ft = [nm.START.value + 8 * 60 * MIN, nm.START.value + 2 * 1440 * MIN]
    m = market(c, ft, [1e-4, -1e-4])
    dec = np.array([59])
    tr, od = nm.simulate(m, "state", dec, np.array([1]), np.array([0.5]), 2, 60, 0.5, 0, m.N)
    assert len(tr) == 1 and tr.open_at_end.iloc[0]
    b = nm.Book(m, tr, od, 0, m.N)
    w1, w2 = b.window(0, 2 * 1440), b.window(2 * 1440, m.N)
    assert w1["closed"] == 0 and w2["closed"] == 0 and np.isnan(w2["win"])
    assert w1["open_n"] == 1 and w2["open_n"] == 1 and w2["entries"] == 0
    assert abs(w1["net4"] + w2["net4"] - b.net4_full.sum()) < 1e-9          # cut = MTM only, no split cost
    assert abs(w1["turnover"] - 0.5) < 1e-12 and abs(w2["turnover"] - 0.5) < 1e-12   # entry leg / reserved exit leg
    # funding: long pays +1e-4 (adverse) and receives on the -1e-4 event
    assert abs(b.fund_full[0] - (-1 + 1) * 0.5) < 1e-9


def test_trailing_stats_exclude_current():
    x = np.arange(10.0)
    z = nm.z_prev(x, 3)
    assert np.isnan(z[2]) and abs(z[3] - (3 - 1) / 1.0) < 1e-12
    x[5] = 1e6                                 # a spike cannot move its own threshold
    q = nm.b1.trailing_quantile(pd.Series(x), 0.5, 3, 3).to_numpy()
    assert q[5] == 3.0
    rz = nm.b1.trailing_robust_z(np.r_[np.arange(40.0), 500.0], 90, 30)
    assert np.isfinite(rz[-1]) and rz[-1] > 10


def test_stationary_bootstrap_constant_and_seeded():
    assert abs(nm.stationary_boot_p05(np.full(50, 3.0), 10, 200) - 3.0) < 1e-12
    x = np.random.default_rng(1).normal(size=100)
    assert nm.stationary_boot_p05(x, 20, 300) == nm.stationary_boot_p05(x, 20, 300)


def test_asof_values_causal():
    avail = np.array([10, 20, 30], np.int64)
    out = nm.asof_values(avail, np.array([1.0, 2.0, 3.0]), np.array([9, 20, 29, 45], np.int64), ttl_ns=10)
    assert np.isnan(out[0]) and out[1] == 2.0 and out[2] == 2.0 and np.isnan(out[3])
