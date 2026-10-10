"""Checks for out/run_long_basis_release_20261010.py (synthetic data, LCR feature_state golden count, run outputs)."""
import importlib.util, json
from pathlib import Path
import numpy as np, pandas as pd, pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("lbr", ROOT / "out/run_long_basis_release_20261010.py")
lbr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lbr)
L, b5, MIN = lbr.L, lbr.b5, lbr.MIN
LCR_FS = ROOT / "out/long_cap_recovery_20261010/LCR-20261010T092956Z-4d28b82a/feature_state.parquet"
_t = importlib.util.spec_from_file_location("t_lcr", ROOT / "tests/test_long_cap_recovery_20261010.py")
tl = importlib.util.module_from_spec(_t)
_t.loader.exec_module(tl)


@pytest.fixture(scope="module")
def syn():
    m = tl.synth_market()
    dec4 = np.arange(239, m.N, 240)
    st = b5.build_state(m, dec4)
    met, prem = tl.synth_inputs(m)
    return m, dec4, st, met, prem, L.features(m, dec4, st, met, prem)


def test_grid_counts():
    ids = [lbr.cid(g) for g in lbr.GRID]
    sims = [lbr.sid(c, o, p) for c in ids for o, p in lbr.CELLS]
    assert len(ids) == len(set(ids)) == 48 and len(sims) == len(set(sims)) == 288
    assert lbr.cid(lbr.GOLDEN) == "LBR-EITHER-b-1.0-d0.25-a2-h2"


@pytest.mark.skipif(not LCR_FS.exists(), reason="LCR feature_state missing")
def test_golden_count():
    fs = pd.read_parquet(LCR_FS)
    f = {k: fs[k].to_numpy(float) for k in ("zr4", "ztaker", "zfund", "zprem", "w")}
    a = lbr.activation_counts(pd.DatetimeIndex(fs.bar_time), lbr.lbr_signal(f, lbr.GOLDEN)["side"])
    assert a["DEV"] == 283 and [a[str(y)] for y in range(2020, 2026)] == [0, 59, 34, 64, 51, 75]
    assert a["2026JanJul"] == 65
    dev = [lbr.activation_counts(pd.DatetimeIndex(fs.bar_time), lbr.lbr_signal(f, g)["side"])["DEV"]
           for g in lbr.GRID]
    assert (min(dev), np.median(dev), max(dev)) == (98, 244, 590)


def test_feature_causality_and_robust_z(syn):
    m, dec4, st, met, prem, f = syn
    T = f["T"]
    assert np.all(T == m.t[dec4] + MIN) and np.all(f["fund_time"] < T)
    ok = np.isfinite(f["taker"])
    assert np.all(f["taker_avail"][ok] <= T[ok]) and np.all(T[ok] - f["taker_avail"][ok] <= 10 * MIN)
    ok = f["prem_n"] > 0
    assert np.all(f["prem_last_avail"][ok] <= T[ok]) and np.all(np.isnan(f["prem4"][f["prem_n"] < 216]))
    rng = np.random.default_rng(0)
    for x, z in (("r4", "zr4"), ("taker", "ztaker"), ("prem4", "zprem")):
        v, zz = f[x], f[z]
        for k in rng.choice(np.flatnonzero(np.isfinite(zz)), 20, replace=False):
            s = v[max(0, k - 1080):k]
            s = s[np.isfinite(s)]
            med = np.median(s)
            assert len(s) >= 540 and np.isclose(zz[k], (v[k] - med) / (1.4826 * np.median(np.abs(s - med))))
    assert np.all(np.isnan(L.rz(np.ones(2000))))                                   # MAD 0 -> NaN


def test_future_tamper_prefix(syn):
    m, dec4, st, met, prem, f = syn
    cut = pd.Timestamp(m.t[dec4[len(dec4) // 2]] + MIN, tz="UTC").floor("D")
    mt, met2, prem2 = L.tamper_inputs(m, met, prem, cut)
    f2 = L.features(mt, dec4, b5.build_state(mt, dec4), met2, prem2)
    k = int(np.sum(m.t[dec4] + MIN <= cut.value))
    for x in lbr.FEAT + ("w",):
        assert np.array_equal(f[x][:k], f2[x][:k], equal_nan=True), x
    for g in lbr.GRID:
        assert np.array_equal(lbr.lbr_signal(f, g)["side"][:k], lbr.lbr_signal(f2, g)["side"][:k])


def hand(n=30):
    z = lambda v: np.full(n, float(v))  # noqa: E731
    return {"zr4": z(1), "ztaker": z(0.5), "zfund": z(0), "zprem": z(0), "w": z(0.8)}


def test_state_machine_rules():
    g = ("FUND", -1.0, 0.5, 2, 2)
    f = hand()
    f["zfund"][2], f["ztaker"][2] = -1.5, -1.0                                     # setup at 2
    f["zfund"][3], f["ztaker"][3] = -1.5, -0.4                                     # rebound 0.6, still setup -> re-arm
    f["zfund"][4:7] = -1.5                                                         # basis stays, taker > 0 -> no setup
    f["ztaker"][4] = 0.2                                                           # rebound 0.6 vs re-arm value -> rec 4
    f["zfund"][5], f["ztaker"][5] = -1.5, -2.0                                     # setup during HOLD ignored
    f["ztaker"][6] = -2.0                                                          # exit decision 6: no re-arm
    s = lbr.lbr_signal(f, g)
    assert list(s["side"][:9]) == [0, 0, 0, 0, 1, 1, 0, 0, 0]
    assert [(e["arm_idx"], e["outcome"], e["end_idx"], e["exit_idx"]) for e in s["events"]] == \
        [(2, "REARMED", 3, -1), (3, "RECOVERY", 4, 6)]
    assert np.all(s["w"][4:6] == 0.8)
    lbr.check_signal(f, s, g)
    # expiry, NaN fail-closed, zr4 < 0, w <= 0, PREM / EITHER modes
    f = hand()
    f["zfund"][2], f["ztaker"][2] = -1.5, -1.0
    f["zr4"][3], f["ztaker"][3] = -0.1, 0.0                                       # zr4 < 0
    f["ztaker"][4] = 0.0                                                          # zr4 ok but d=2 > arm 1 -> expired
    s = lbr.lbr_signal(f, ("FUND", -1.0, 0.5, 1, 2))
    assert s["side"].sum() == 0 and s["events"][0]["outcome"] == "EXPIRED" and s["events"][0]["end_idx"] == 3
    assert lbr.lbr_signal(f, ("FUND", -1.0, 0.5, 2, 2))["side"][4] == 1
    f["w"][4] = 0.0
    assert lbr.lbr_signal(f, ("FUND", -1.0, 0.5, 2, 2))["side"].sum() == 0
    f = hand()
    f["zfund"][2], f["ztaker"][2] = np.nan, -1.0
    assert lbr.lbr_signal(f, ("FUND", -0.5, 0.25, 2, 2))["events"] == []
    f["zprem"][2] = -0.6
    assert lbr.lbr_signal(f, ("PREM", -0.5, 0.25, 2, 2))["events"]
    assert lbr.lbr_signal(f, ("EITHER", -0.5, 0.25, 2, 2))["events"]
    assert not lbr.lbr_signal(f, ("PREM", -1.0, 0.25, 2, 2))["events"]
    f["ztaker"][2] = np.nan
    assert not lbr.lbr_signal(f, ("EITHER", -0.5, 0.25, 2, 2))["setup"].any()
    # hold 4 cap
    f = hand()
    f["zfund"][2], f["ztaker"][2] = -1.5, -1.0
    s = lbr.lbr_signal(f, ("FUND", -1.0, 0.5, 2, 4))
    assert list(s["side"][2:9]) == [0, 1, 1, 1, 1, 0, 0]
    lbr.check_signal(f, s, ("FUND", -1.0, 0.5, 2, 4))


def test_registry_idempotent(tmp_path):
    fold = pd.DataFrame([{"sim_id": "x|o|p", "window": w, "net4": 1.0, "net8": 0.5, "closed": 3, "fill": 0.5}
                         for w in lbr.WINDOWS])
    p = tmp_path / "reg.jsonl"
    assert lbr.write_registry(fold, {"pick": "x"}, {"code": "h"}, "LBR-test", p) == {"added": 2, "skipped": 0}
    assert lbr.write_registry(fold, {"pick": "x"}, {"code": "h"}, "LBR-test2", p) == {"added": 0, "skipped": 2}


def test_run_outputs():
    runs = sorted(r for r in lbr.OUT_BASE.glob("LBR-*") if (r / "manifest.json").exists()) \
        if lbr.OUT_BASE.exists() else []
    if not runs:
        pytest.skip("no LBR run output")
    d = runs[-1]
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert man["counts"]["logical"] == 48 and man["counts"]["sims"] == 288
    gc = man["golden_count"]
    assert gc["DEV"] == 283 and gc["2026JanJul"] == 65
    p = man["parity_s180"]
    assert p["trades_equal"] and p["cells_max_abs_diff"] == 0 and p["daily_max_abs_diff"] == 0 \
        and p["boot_max_abs_diff"] == 0 and p["trades_net4_max_abs_diff"] == 0
    assert man["selection_tamper"]["pick_unchanged"] and man["gross_max"] <= 2
    assert man["prefix_check"]["configs_checked"] == 48
    fold = pd.read_parquet(d / "fold_metrics.parquet")
    assert fold.sim_id.nunique() == 288 and len(pd.read_parquet(d / "config_metrics.parquet")) == 48
    fs = pd.read_parquet(d / "feature_state.parquet")
    assert ((fs["T"] - fs.bar_time) == pd.Timedelta(minutes=1)).all()
    for c in ("taker_available_time", "prem_last_available_time", "funding_time"):
        ok = fs[c].notna()
        assert (fs[c][ok] <= fs["T"][ok]).all(), c
    assert (fs.funding_time[fs.funding_time.notna()] < fs["T"][fs.funding_time.notna()]).all()
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
