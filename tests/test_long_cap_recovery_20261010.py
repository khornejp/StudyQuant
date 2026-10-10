"""Checks for out/run_long_cap_recovery_20261010.py (synthetic data + the latest LCR run outputs)."""
import importlib.util, json
from pathlib import Path
import numpy as np, pandas as pd, pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("lcr", ROOT / "out/run_long_cap_recovery_20261010.py")
lcr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lcr)
b2, b5, MIN, DAY = lcr.b2, lcr.b5, lcr.b2.MIN, lcr.b2.DAY


def synth_market(days=400, seed=3, vol=6e-4):
    rng = np.random.default_rng(seed)
    n = 1440 * days
    reg = np.repeat(rng.choice([-1, 1], n // (1440 * 20) + 1), 1440 * 20)[:n]
    c = 100 * np.exp(np.cumsum(rng.normal(reg * 2e-5, vol, n)))
    o = np.concatenate([[c[0]], c[:-1]])
    t = b2.START.value + np.arange(n) * MIN
    ft = b2.START.value + np.arange(0, n, 480) * MIN + 8_000_000
    return b2.Market(t, o, np.maximum(o, c) * 1.002, np.minimum(o, c) * 0.998, c, np.ones(n), np.full(n, 0.5),
                     ft, rng.normal(1e-4, 1e-4, len(ft)))


def synth_inputs(m, seed=5):
    rng = np.random.default_rng(seed)
    av = np.arange(m.t[0] + 5 * MIN, m.t[-1], 5 * MIN)
    met = pd.DataFrame({"available_time": pd.to_datetime(av, utc=True),
                        "oi": 1e4 * np.exp(np.cumsum(rng.normal(0, 3e-3, len(av)))),
                        "taker_lsr": np.exp(rng.normal(0, 0.2, len(av)))})
    met = met.drop(index=range(3000, 3400)).reset_index(drop=True)          # gap -> stale OI/taker
    pa = m.t + MIN
    prem = pd.DataFrame({"available_time": pd.to_datetime(pa, utc=True), "premium": rng.normal(0, 1e-4, m.N)})
    prem = prem.drop(index=range(20000, 20100)).reset_index(drop=True)      # 100 missing minutes -> < 216 rows
    return met, prem


@pytest.fixture(scope="module")
def syn():
    m = synth_market()
    dec4 = np.arange(239, m.N, 240)
    st = b5.build_state(m, dec4)
    met, prem = synth_inputs(m)
    return m, dec4, st, met, prem, lcr.features(m, dec4, st, met, prem)


def test_grid_counts():
    ids = [lcr.cid(g) for g in lcr.GRID]
    sims = [lcr.sid(c, o, p) for c in ids for o, p in lcr.CELLS]
    assert len(ids) == len(set(ids)) == 48 and len(sims) == len(set(sims)) == 288


def test_feature_causality(syn):
    m, dec4, st, met, prem, f = syn
    T = f["T"]
    assert np.all(T == m.t[dec4] + MIN)
    for k in ("oi_T", "taker"):
        a = f[k + "_avail" if k == "oi_T" else "taker_avail"]
        ok = np.isfinite(f[k])
        assert np.all(a[ok] <= T[ok]) and np.all(T[ok] - a[ok] <= 10 * MIN) and (~ok).any()
    ok = np.isfinite(f["oi_24"])
    assert np.all(f["oi_24_avail"][ok] <= T[ok] - DAY)
    assert np.all(f["fund_time"] < T)
    ok = f["prem_n"] > 0
    assert np.all(f["prem_last_avail"][ok] <= T[ok])
    assert np.all(np.isnan(f["prem4"][f["prem_n"] < 216])) and (f["prem_n"] < 216).any()
    pa, pv = prem.available_time.array.asi8, prem.premium.to_numpy()
    for k in np.flatnonzero(np.isfinite(f["prem4"]))[::97]:
        s = pv[(pa > T[k] - 4 * 60 * MIN) & (pa <= T[k])]
        assert np.isclose(f["prem4"][k], s.mean())


def test_robust_baselines_exclude_current(syn):
    *_, f = syn
    rng = np.random.default_rng(0)
    for x, z in (("r4", "zr4"), ("dOI24", "zOI24"), ("taker", "ztaker"), ("prem4", "zprem"), ("dSVI", "zdSVI")):
        v, zz = f[x], f[z]
        for k in rng.choice(np.flatnonzero(np.isfinite(zz)), 20, replace=False):
            s = v[max(0, k - 1080):k]
            s = s[np.isfinite(s)]
            med = np.median(s)
            assert len(s) >= 540 and np.isclose(zz[k], (v[k] - med) / (1.4826 * np.median(np.abs(s - med))))
    lc = np.log(syn[0].c[syn[1]])
    r4 = f["r4"]
    for k in rng.choice(np.flatnonzero(np.isfinite(f["gap"])), 20, replace=False):
        w = r4[k - 180:k]
        mad = np.median(np.abs(w - np.median(w)))
        assert np.isclose(f["gap"][k], (lc[k] - np.median(lc[k - 42:k])) / (1.4826 * mad * np.sqrt(42)))


def test_mad_zero_and_missing_fail_closed():
    assert np.all(np.isnan(lcr.rz(np.ones(2000))))
    lc = np.log(100 * np.exp(np.arange(400) * 1e-3))                       # constant r4 -> MAD 0
    assert np.all(np.isnan(lcr.gap_feature(lc, np.diff(lc, prepend=np.nan))))


def test_future_tamper_prefix(syn):
    m, dec4, st, met, prem, f = syn
    cut = pd.Timestamp(m.t[dec4[len(dec4) // 2]] + MIN, tz="UTC").floor("D")
    mt, met2, prem2 = lcr.tamper_inputs(m, met, prem, cut)
    f2 = lcr.features(mt, dec4, b5.build_state(mt, dec4), met2, prem2)
    k = int(np.sum(m.t[dec4] + MIN <= cut.value))
    for x in lcr.FEAT + ("w",):
        assert np.array_equal(f[x][:k], f2[x][:k], equal_nan=True), x
    assert not np.array_equal(f["zr4"][k:], f2["zr4"][k:], equal_nan=True)


def hand_features(n=30):
    z = lambda v: np.full(n, float(v))  # noqa: E731
    f = {"gap": z(0.5), "zOI24": z(0), "ztaker": z(0), "zfund": z(-1), "zprem": z(-2), "zr4": z(1), "zdSVI": z(1),
         "w": z(0.8)}
    return f


def test_state_machine_rules():
    f = hand_features()
    g = (-1.5, "NONE", 2, -0.5, 3)
    f["gap"][2], f["zOI24"][2], f["ztaker"][2] = -2.0, -1.0, -1.5                # shock at 2
    f["gap"][3], f["ztaker"][3] = -1.0, -0.9                                     # recovery at 3
    f["gap"][4] = -1.0                                                           # hold
    f["gap"][5] = -1.0
    f["gap"][6], f["zOI24"][6], f["ztaker"][6] = -2.0, -1.0, -1.5                # max hold exit at 6 (shock ignored)
    s = lcr.lcr_signal(f, g)
    assert list(s["side"][:8]) == [0, 0, 0, 1, 1, 1, 0, 0]
    assert s["events"][0]["arm_idx"] == 2 and s["events"][0]["end_idx"] == 3 and s["events"][0]["exit_idx"] == 6
    assert len(s["events"]) == 1                                                 # exit decision never re-arms
    lcr.check_signal(f, s, g)
    assert np.all(s["w"][3:6] == 0.8)
    # re-arm, expiry, gap exit, fail-closed shock
    f = hand_features()
    f["gap"][2], f["zOI24"][2], f["ztaker"][2] = -2.0, -1.0, -1.5
    f["gap"][3], f["zOI24"][3], f["ztaker"][3] = -2.5, -1.0, -2.0                # later shock: re-arm at 3
    f["gap"][4], f["ztaker"][4] = -2.2, -1.9                                     # gap delta 0.3 < 0.5 -> no rec
    f["gap"][5], f["ztaker"][5] = -2.2, -1.9                                     # arm+2 -> expired
    f["gap"][7], f["zOI24"][7], f["ztaker"][7] = np.nan, -1.0, -1.5              # NaN gap -> no shock
    f["gap"][9], f["zOI24"][9], f["ztaker"][9] = -2.0, -1.0, -1.5                # shock 9
    f["gap"][10], f["ztaker"][10] = -1.4, -1.0                                   # recovery 10
    f["gap"][11] = -0.4                                                          # gap >= -0.5 -> exit 11
    s = lcr.lcr_signal(f, g)
    out = [(e["arm_idx"], e["outcome"], e["end_idx"]) for e in s["events"]]
    assert out == [(2, "REARMED", 3), (3, "EXPIRED", 5), (9, "RECOVERY", 10)]
    assert s["events"][1]["rearm"] and not s["events"][0]["rearm"]
    assert list(s["side"][9:13]) == [0, 1, 0, 0]
    lcr.check_signal(f, s, g)
    # discount gates and NaN recovery inputs
    f = hand_features()
    f["gap"][2], f["zOI24"][2], f["ztaker"][2] = -2.0, -1.0, -1.5
    f["zfund"][2] = np.nan
    assert lcr.lcr_signal(f, (-1.5, "FUND", 2, -0.5, 3))["events"] == []
    assert len(lcr.lcr_signal(f, (-1.5, "PREM", 2, -0.5, 3))["events"]) == 1
    f["gap"][3], f["ztaker"][3], f["zdSVI"][3] = -1.0, -0.9, np.nan
    assert lcr.lcr_signal(f, g)["side"].sum() == 0


def test_selection_dev_only_and_tamper():
    rows = []
    for i, c in enumerate("abcd"):
        rows.append({"config_id": c, "dev_eligible": c != "a", "dev_pos_delta": [9, 2, 2, 1][i],
                     "dev_score": [9, 0.1, 0.1, 5][i], "dev_cell_floor_pd": [0, 1, 1, 1][i],
                     "dev_abs_pearson": [0, 0.2, 0.1, 0][i], "DEV-FULL_comb_mdd": [0, 1, 1, 1][i],
                     "TEST_net4": [0, -5, 9, 0][i], "TEST_worst_cell": 0.0})
    cm = pd.DataFrame(rows)
    pick, elig, _ = lcr.select(lcr.dev_view(cm))
    assert (pick, elig) == ("c", True)
    assert lcr.tamper_invariance(cm, pick)["pick_unchanged"]
    p2, e2, _ = lcr.select(lcr.dev_view(cm.assign(dev_eligible=False)))
    assert (p2, e2) == ("a", False)
    with pytest.raises(AssertionError):
        lcr.select(cm)


def test_run_outputs():
    runs = sorted(r for r in lcr.OUT_BASE.glob("LCR-*") if (r / "manifest.json").exists()) \
        if lcr.OUT_BASE.exists() else []
    if not runs:
        pytest.skip("no LCR run output")
    d = runs[-1]
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert man["counts"]["logical"] == 48 and man["counts"]["sims"] == 288
    p = man["parity_s180"]
    assert p["trades_equal"] and p["cells_max_abs_diff"] == 0 and p["daily_max_abs_diff"] == 0 \
        and p["boot_max_abs_diff"] == 0
    assert man["selection_tamper"]["pick_unchanged"] and man["gross_max"] <= 2
    fold = pd.read_parquet(d / "fold_metrics.parquet")
    assert fold.sim_id.nunique() == 288 and len(pd.read_parquet(d / "config_metrics.parquet")) == 48
    fs = pd.read_parquet(d / "feature_state.parquet")
    assert ((fs["T"] - fs.bar_time) == pd.Timedelta(minutes=1)).all()
    for c in ("oi_T_available_time", "taker_available_time", "prem_last_available_time", "funding_time"):
        ok = fs[c].notna()
        assert (fs[c][ok] <= fs["T"][ok]).all(), c
    assert (fs.funding_time[fs.funding_time.notna()] < fs["T"][fs.funding_time.notna()]).all()
    ok = fs.oi_24_available_time.notna()
    assert (fs.oi_24_available_time[ok] <= fs["T"][ok] - pd.Timedelta(days=1)).all()
    for f in (d / "daily").glob("SELECTED_*.parquet"):
        x = pd.read_parquet(f)
        assert np.allclose(x.combined_net4, x.new_net4 + x.s180_net4, rtol=0, atol=0)
    for f in (d / "trades").glob("SELECTED_*.parquet"):
        t = pd.read_parquet(f)
        assert (t.entry_idx > t.decision_idx).all()
        c = ~t.open_at_end
        assert (t.exit_idx[c] > t.exit_decision_idx[c]).all()
        assert np.allclose(t.net4_full - t.gross_full - t.funding_full, -4 * t.entry_weight_frozen)
    dec = json.loads((d / "decision.json").read_text(encoding="utf-8"))
    assert {"PASS", "COMPLEMENT_PASS"} <= set(dec)
