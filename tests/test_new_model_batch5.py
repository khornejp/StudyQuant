"""Checks for out/run_new_model_batch5_20261010.py (synthetic data + the latest NM-B5 run outputs)."""
import importlib.util, json
from pathlib import Path
import numpy as np, pandas as pd, pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("nm_b5", ROOT / "out/run_new_model_batch5_20261010.py")
nm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nm)
b2, b3, b4, MIN, DAY = nm.b2, nm.b3, nm.b4, nm.MIN, nm.DAY


def market(c, ft=(), fr=(), wick=0.002):
    c = np.asarray(c, float)
    o = np.concatenate([[c[0]], c[:-1]])
    h, l = np.maximum(o, c) * (1 + wick), np.minimum(o, c) * (1 - wick)
    t = b2.START.value + np.arange(len(c)) * MIN
    return b2.Market(t, o, h, l, c, np.ones(len(c)), np.full(len(c), 0.5), np.asarray(ft, np.int64), np.asarray(fr, float))


def synth(days, seed=0, vol=6e-4):
    rng = np.random.default_rng(seed)
    n = 1440 * days
    reg = np.repeat(rng.choice([-1, 1], n // (1440 * 20) + 1), 1440 * 20)[:n]
    c = 100 * np.exp(np.cumsum(rng.normal(reg * 2e-5, vol, n)))
    ft = b2.START.value + np.arange(0, n, 480) * MIN + 8_000_000
    fr = rng.normal(1e-4, 1e-4, len(ft))
    return c, ft, fr


@pytest.fixture(scope="module")
def syn():
    c, ft, fr = synth(800, 3)
    m = market(c, ft, fr)
    dec4 = np.arange(239, m.N, 240)
    return m, dec4, nm.build_state(m, dec4)


def latest_run():
    runs = sorted(nm.OUT_BASE.glob("NM-B5-*")) if nm.OUT_BASE.exists() else []
    runs = [r for r in runs if (r / "manifest.json").exists()]
    if not runs:
        pytest.skip("no NM-B5 run output")
    return runs[-1]


def test_grid_counts():
    assert len(nm.CORE) == 40 and len({nm.cid(p) for p in nm.CORE}) == 40 and len(nm.CONTROLS) == 2
    assert (len(nm.CORE) + len(nm.CONTROLS)) * len(nm.OFFSETS) * len(nm.PENS) == 252
    assert nm.VPOL == ("W180-P50", "W180-P65", "W365-P50", "W365-P65", "V-ENS") and len(nm.ENS) == 5


# 1, 4, 12
def test_T_and_equal_T_funding_excluded():
    n = 240 * 12
    T0 = b2.START.value + 240 * MIN
    ft = np.array([T0 - 480 * MIN, T0 - 1, T0, T0 + 1])
    m = market(np.full(n, 100.0), ft, np.array([0.1, 0.2, 0.3, 0.4]))
    dec4 = np.arange(239, n, 240)
    T = m.t[dec4] + MIN
    assert T[0] == T0 and m.t[dec4[0] + 1] == T0
    j = nm.fund_idx(m, T)
    assert j[0] == 1 and m.fr[j[0]] == 0.2 and np.all(m.ft[j[j >= 0]] < T[j >= 0])


# 3, 4, 6
def test_funding_stats_exclude_current_and_formula():
    fr = np.arange(100, dtype=float)
    med, mad = nm.funding_stats(fr, 90, 30)
    assert np.isnan(med[:30]).all() and med[30] == np.median(fr[:30])
    assert med[95] == np.median(fr[5:95]) and mad[95] == np.median(np.abs(fr[5:95] - np.median(fr[5:95])))
    y = fr.copy(); y[95] = -1e9
    m2, _ = nm.funding_stats(y, 90, 30)
    assert m2[95] == med[95] and m2[96] != med[96]              # spike enters only the next event's sample
    assert nm.raw_thr(med, mad, -0.5)[95] == pytest.approx(med[95] - 0.5 * 1.4826 * mad[95], abs=1e-15)
    assert nm.raw_thr(med, mad, 0.0)[95] == med[95]


# 5
def test_vol_quantile_window_and_vens():
    sig = np.linspace(0.3, 0.9, 6 * 365 + 50)
    tv, w = nm.vol_weights(sig)
    n = 6 * 180
    assert np.isnan(tv["W180-P50"][:n]).all() and tv["W180-P50"][n] == pytest.approx(np.quantile(sig[:n], 0.5))
    assert np.isnan(w["V-ENS"][:6 * 365]).all() and np.isfinite(w["V-ENS"][6 * 365])   # needs all four
    k = 6 * 365 + 10
    assert w["V-ENS"][k] == pytest.approx(np.mean([w[v][k] for v in nm.VPOL[:4]]))
    s2 = sig.copy(); s2[k] = 99.0
    assert nm.vol_weights(s2)[0]["W365-P65"][k] == tv["W365-P65"][k]          # current sigma excluded


# 2, 3, 5, 6, 7 (identities on synthetic data)
def test_identities(syn):
    m, dec4, st = syn
    out = nm.check_identities(m, dec4, st, check=100)
    assert out["assert7_unclipped_rows"] > 0


# 8, 9, 10
def test_signal_not_ready_flat_no_raw_cutoff(syn):
    m, dec4, st = syn
    for p in nm.CORE:
        assert set(p) == {"struct", "c", "vol"}
        s = nm.core_signal(st, p)
        trend, sw = nm.STRUCTS[p["struct"]]
        nr = ~(np.isfinite(st["score"][trend]) & np.isfinite(st["svi"][sw]) & np.isfinite(st["w"][p["vol"]]))
        assert nr.any() and np.all(s["side"][nr] == 0) and np.all(s["w"][nr] == 0)
        assert np.all(s["side"][~np.isfinite(s["thr"])] >= 0)
        assert np.all(s["w"] <= 1) and (s["side"] != 0).any()


# 11
def test_control_uses_strict_accessor(syn):
    m, dec4, st = syn
    masks = b3.gate_masks(*b4.gate_inputs_strict(m, dec4, np.arange(1439, m.N, 1440)))
    for p in nm.CONTROLS.values():
        assert np.array_equal(nm.control_signal(st, p)["gate"], masks[p["b3_gate"]])


# 13, 14
def test_tamper_and_prefix(syn):
    m, dec4, st = syn
    cut = pd.Timestamp(m.t[0] + 700 * DAY, tz="UTC")
    p = dict(struct="F42", c=0.0, vol="W180-P50")
    out = nm.prefix_checks(m, dec4, st, {"x": (nm.core_signal, p),
                                          "ctl": (nm.control_signal, nm.CONTROLS["CONTROL_B3_DEV_PICK_STRICT"])}, cut)
    assert out["configs"]["x"]["prefix_closed_trades_equal"] > 0


# 17, 18
def test_ensemble_arith():
    mk = lambda v: {(o, q): {w: {"days": 10, **{f"long_{x}": v for x in ("net4", "net8", "gross", "funding",
                                                                           "exp_days", "per_day", "open_mtm")},
                                 **{f"long_{x}": 3 for x in ("closed", "entries", "open_n")}}
                             for w in nm.WINDOWS} for o in nm.OFFSETS for q in nm.PENS}
    e = nm.ensemble_R(mk(10.0), mk(-4.0))
    assert e[(2, 0.5)]["TEST"]["long_net4"] == 3.0 and e[(5, 2.0)]["DEV-A"]["long_closed"] == 6


# 20
def test_selection_tie_and_verdicts():
    df = pd.DataFrame({"config_id": ["b", "a", "c"], "k": [1.0, 1.0, 1.0], "mdd": [5.0, 5.0, 4.0],
                       "turn": [1.0, 1.0, 9.0]})
    assert list(nm.rank(df, "k", "mdd", "turn").config_id) == ["c", "a", "b"]
    cell = lambda v, cl=30: {w: {"long_net4": v, "short_net4": v, "long_per_day": v, "short_per_day": v,
                                 "long_closed": cl, "short_closed": cl} for w in nm.WINDOWS}
    R = {(o, q): cell(1.0) for o in nm.OFFSETS for q in nm.PENS}
    assert nm.side_verdict(R, "long", True, 0.1)["side_verdict"] == "S_PROFIT_PASS+S_STRONG+S_ROBUST_PASS+S_ROBUST_STRONG"
    R[(5, 2.0)]["TEST"]["long_net4"] = -1
    assert nm.side_verdict(R, "long", True, -0.1)["side_verdict"] == "S_PROFIT_PASS"
    R2 = {(o, q): cell(1.0, 5) for o in nm.OFFSETS for q in nm.PENS}
    assert nm.side_verdict(R2, "short", False, 1.0)["side_verdict"] == "S_LOW_N+S_ROBUST_PASS+S_ROBUST_STRONG"
    vd = b3.verdict(R2, True, {"all": 1, "long": 1, "short": 1})
    assert vd["verdict"] == "PROFIT_PASS+LOW_N+ROBUST_PASS+SIDE_STRONG"
    sw = {"DEV-FULL": {"long_closed": 19, "long_exp_days": 179.0}}
    assert not nm.side_eligible(R2, "long", sw, 0.5)
    assert nm.side_eligible(R2, "long", {"DEV-FULL": {"long_closed": 20, "long_exp_days": 0}}, 0.10)
    assert not nm.side_eligible(R2, "long", {"DEV-FULL": {"long_closed": 20, "long_exp_days": 0}}, 0.09)


# 15, 16, 19, 21, 22, 23, 24 (run outputs)
def test_run_outputs():
    run = latest_run()
    rows = {"grid.parquet": 252, "fold_metrics.parquet": 1008, "config_metrics.parquet": 42,
            "adaptive_state.parquet": 14832, "signal_diagnostics.parquet": 1008, "bootstrap.parquet": 1512,
            "long_ensemble_metrics.parquet": 20, "long_ensemble_bootstrap.parquet": 60}
    for f, n in rows.items():
        assert len(pd.read_parquet(run / f)) == n, f
    assert sum(1 for _ in (run / "runs.jsonl").open(encoding="utf-8")) == 252
    g = pd.read_parquet(run / "grid.parquet")
    for w, d in nm.WIN_DAYS.items():
        assert (g[f"{w}_days"] == d).all()                                                   # 19
        assert np.allclose(g[f"{w}_net4"], g[f"{w}_long_net4"] + g[f"{w}_short_net4"])     # 16
    assert np.allclose(g["DEV-A_net4"] + g["DEV-B_net4"], g["DEV-FULL_net4"])               # 15
    ctl = json.loads((run / "controls.json").read_text(encoding="utf-8"))
    for k, ref in nm.CONTROL_REF.items():                                                    # 21
        assert ctl[k]["parity"]["n_diff_atol_1e-6"] == 0
        assert np.allclose(ctl[k]["parity"]["net4_DEV-FULL/DEV-B/TEST"], ref, atol=5e-5)
    for f in ("reselected_overall.json", "reselected_long.json", "reselected_short.json"):  # 23
        assert json.loads((run / f).read_text(encoding="utf-8"))["selection_flag"] == nm.TEST_FLAG
    man = json.loads((run / "manifest.json").read_text(encoding="utf-8"))                   # 24
    for k in ("sources", "input_sha256", "created_utc", "data_cutoff", "frozen_hypothesis", "test_selection_flags"):
        assert man[k]
    assert man["counts"]["n_trials"] == 245 and man["counts"]["sims"] == 252
    reg = [json.loads(x) for x in nm.REGISTRY.read_text(encoding="utf-8").splitlines() if '"NM-B5' in x]
    reg = [r for r in reg if r.get("config", {}).get("run_id") == run.name]
    if reg:                                                                                  # 22
        assert sum(r["n_trials"] for r in reg) == 245 and sum(r.get("n_simulations", 0) for r in reg) == 252
        assert len({r["idempotency_key"] for r in reg}) == len(reg)
