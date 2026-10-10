"""Unit checks for out/run_new_model_batch3_20261010.py (synthetic data only)."""
import importlib.util
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("nm_b3", ROOT / "out/run_new_model_batch3_20261010.py")
nm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nm)
b2, MIN = nm.b2, nm.b2.MIN


def market(c, ft=(), fr=(), wick=0.002):
    c = np.asarray(c, float)
    o = np.concatenate([[c[0]], c[:-1]])
    h, l = np.maximum(o, c) * (1 + wick), np.minimum(o, c) * (1 - wick)
    t = b2.START.value + np.arange(len(c)) * MIN
    return b2.Market(t, o, h, l, c, np.ones(len(c)), np.full(len(c), 0.5), np.asarray(ft, np.int64), np.asarray(fr, float))


def test_grid_120_logical_720_sims():
    g = nm.grid()
    sims = {nm.sid(p, o, q) for p in g for o in nm.OFFSETS for q in nm.PENS}
    assert len(g) == 120 and len(sims) == 720
    assert sum(p["gate"] == "none" for p in g) == 8 and all(p["action"] == "none" for p in g if p["gate"] == "none")
    assert nm.BASES[0] == dict(base=1, svi_w=42, trend="(42, 168, 504)", tv=0.20)
    assert nm.BASES[7] == dict(base=8, svi_w=180, trend="(6, 18, 42)", tv=0.40)


def test_zero_weight_nan_not_propagated():
    a, b, nan = np.array([1.0, 2.0]), np.array([3.0, 4.0]), np.full(2, np.nan)
    assert np.allclose(nm.blend((a, b, nan), (0.5, 0.5, 0)), [2.0, 3.0])
    assert np.isnan(nm.blend((a, nan), (0.5, 0.5))).all()          # positive-weight NaN still NaN


def test_fixed_window_days():
    n = (b2.END - b2.START).value // MIN
    m = SimpleMarket(b2.START.value + np.arange(n) * MIN)
    wb = nm.window_bounds(m)
    assert {k: (b - a) // 1440 for k, (a, b) in wb.items()} == {"DEV-FULL": 2192, "DEV-A": 1461, "DEV-B": 731, "TEST": 280}
    assert wb["DEV-FULL"][0] == 0                                   # no 2021 truncation


class SimpleMarket:
    def __init__(self, t):
        self.t = t

    def idx(self, ts):
        return int(np.searchsorted(self.t, pd.Timestamp(ts).value))


def test_gate_causal_and_fail_closed():
    rng = np.random.default_rng(0)
    n = 1440 * 400
    c = 100 * np.exp(np.cumsum(rng.normal(0, 2e-4, n)))
    ft = b2.START.value + np.arange(0, n, 480) * MIN               # 8h events
    fr = rng.normal(1e-4, 5e-5, len(ft))
    m = market(c, ft, fr)
    dec4, d1 = np.arange(239, n, 240), np.arange(1439, n, 1440)
    fz, frr, daily = nm.gate_inputs(m, dec4, d1)
    cut = len(dec4) // 2
    fr2 = fr.copy()
    fr2[m.ft > m.t[dec4[cut]] + MIN] = -1.0                         # perturb only the future
    c2 = c.copy()
    c2[dec4[cut] + 1:] *= 0.5
    fz2, frr2, daily2 = nm.gate_inputs(market(c2, ft, fr2), dec4, d1)
    for x, y in ((fz, fz2), (frr, frr2), (daily, daily2)):
        assert np.array_equal(x[:cut + 1], y[:cut + 1], equal_nan=True)
    assert np.isnan(fz[:10]).all() and np.isnan(daily[:300]).all()   # warm-up -> missing
    g = nm.gate_masks(fz, frr, daily)
    assert not g["fz>=0"][:10].any() and not g["fz>=0&daily_ready"][:300].any() and g["none"].all()
    assert not g["fr>=0&daily_ready"][np.isnan(daily)].any()


def test_state_flat_exits_veto_holds():
    rng = np.random.default_rng(3)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 5e-4, 1440 * 3)))
    m = market(c)
    dec = np.arange(239, m.N, 240)
    des = np.full(len(dec), -1)
    gate = np.ones(len(dec), bool)
    gate[4:] = False
    sf, ok_sf = nm.g3_signal(des, gate, "state_flat")
    sv, ok_v = nm.g3_signal(des, gate, "entry_veto")
    assert ok_sf is None and (sf[4:] == 0).all() and (sv == -1).all() and not ok_v[4:].any()
    t1, _ = b2.simulate(m, "state", dec, sf, np.ones(len(dec)), 2, 60, 0.5, 0, m.N, entry_ok=ok_sf)
    t2, _ = b2.simulate(m, "state", dec, sv, np.ones(len(dec)), 2, 60, 0.5, 0, m.N, entry_ok=ok_v)
    assert len(t1) == 1 and not t1.open_at_end.iloc[0] and t1.exit_decision_idx.iloc[0] == dec[4]
    assert len(t2) == 1 and t2.open_at_end.iloc[0]
    d = nm.diagnostics(t1, dec, des, gate, {"all": (0, m.N)})["all"]
    assert d["forced_exit"] == 1 and d["gate_fail"] == len(dec) - 4 and d["blocked_flat"] < d["gate_fail"]
    with np.testing.assert_raises(AssertionError):
        nm.g3_signal(des, gate, "none")


def test_side_books_sum_and_split_no_cost():
    rng = np.random.default_rng(5)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 8e-4, 1440 * 6)))
    ft = b2.START.value + np.arange(0, len(c), 480) * MIN
    m = market(c, ft, rng.normal(0, 1e-4, len(ft)))
    dec = np.arange(239, m.N, 240)
    side = np.tile([1, 1, -1, -1, 0], len(dec))[:len(dec)]
    tr, od = b2.simulate(m, "state", dec, side, np.full(len(dec), 0.7), 2, 60, 0.5, 0, m.N)
    assert (tr.side > 0).any() and (tr.side < 0).any()
    bk = nm.side_books(m, b2.Book(m, tr, od, 0, m.N))
    assert np.allclose(bk["all"].daily(0, m.N), bk["long"].daily(0, m.N) + bk["short"].daily(0, m.N))
    a, b = bk["all"].window(0, 3 * 1440), bk["all"].window(3 * 1440, m.N)
    assert abs(a["net4"] + b["net4"] - bk["all"].net4_full.sum()) < 1e-6
    assert abs(a["long_net4"] + a["short_net4"] - a["net4"]) < 1e-9


def test_bootstrap_seeded():
    x = np.random.default_rng(1).normal(size=120)
    assert b2.stationary_boot_p05(x, 20, 300) == b2.stationary_boot_p05(x, 20, 300)


def _R(v=1.0, closed=30, fill=0.5):
    w = {f"{s}_{k}": v for s in nm.SIDES for k in ("net4", "per_day")}
    w.update({f"{s}_closed": closed for s in nm.SIDES} | {f"{s}_exp_days": 0 for s in nm.SIDES})
    w["fill_notional_rate"] = fill
    return {(o, p): {k: dict(w) for k in nm.WINDOWS} for o in nm.OFFSETS for p in nm.PENS}


def test_selection_and_verdict_rules():
    R = _R()
    assert nm.eligible(R) and nm.dev_score(R) == 1.0 and nm.adapt_score(R) == 1.0
    assert not nm.eligible(_R(fill=0.05)) and not nm.eligible(_R(closed=5))
    R2 = _R()
    R2[(5, 0.5)]["DEV-B"]["short_net4"] = -1
    assert not nm.eligible(R2)
    R2 = _R()
    R2[(5, 1.0)]["DEV-B"]["short_net4"] = -1                        # pen 1.0 not in eligibility
    assert nm.eligible(R2)
    pos = {"all": 1, "long": 1, "short": 1}
    v = nm.verdict(R, True, pos)
    assert v["PROFIT_PASS"] and v["STRONG"] and v["ROBUST_PASS"] and v["SIDE_STRONG"] and not v["LOW_N"]
    v = nm.verdict(R2, True, pos)
    assert v["PROFIT_PASS"] and not v["ROBUST_PASS"] and not v["SIDE_STRONG"]
    v = nm.verdict(R, True, {"all": 1, "long": 1, "short": -1})
    assert v["STRONG"] and not v["SIDE_STRONG"]
    R3 = _R(closed=5)
    v = nm.verdict(R3, True, pos)
    assert v["LOW_N"] and v["PROFIT_PASS"] and not v["STRONG"]
    assert not nm.verdict(R, False, pos)["PROFIT_PASS"]
    R4 = _R()
    R4[(2, 0.5)]["TEST"]["long_net4"] = -1
    assert nm.verdict(R4, True, pos)["verdict"] == "FAIL"
