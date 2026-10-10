"""Checks for out/run_new_model_batch4_20261010.py (synthetic data + the latest NM-B4 run outputs)."""
import importlib.util, json
from pathlib import Path
import numpy as np, pandas as pd, pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("nm_b4", ROOT / "out/run_new_model_batch4_20261010.py")
nm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nm)
b2, b3, MIN, DAY = nm.b2, nm.b3, nm.MIN, nm.DAY


def market(c, ft=(), fr=(), wick=0.002):
    c = np.asarray(c, float)
    o = np.concatenate([[c[0]], c[:-1]])
    h, l = np.maximum(o, c) * (1 + wick), np.minimum(o, c) * (1 - wick)
    t = b2.START.value + np.arange(len(c)) * MIN
    return b2.Market(t, o, h, l, c, np.ones(len(c)), np.full(len(c), 0.5), np.asarray(ft, np.int64), np.asarray(fr, float))


def synth(days, seed=0, vol=6e-4):
    rng = np.random.default_rng(seed)
    n = 1440 * days
    reg = np.repeat(rng.choice([-1, 1], n // (1440 * 20) + 1), 1440 * 20)[:n]        # 20-day drift regimes
    c = 100 * np.exp(np.cumsum(rng.normal(reg * 2e-5, vol, n)))
    ft = b2.START.value + np.arange(0, n, 480) * MIN + 8_000_000                         # 8h events, +8ms publish
    fr = rng.normal(1e-4, 1e-4, len(ft))
    return c, ft, fr


def latest_run():
    runs = sorted(nm.OUT_BASE.glob("NM-B4-*")) if nm.OUT_BASE.exists() else []
    runs = [r for r in runs if (r / "manifest.json").exists()]
    if not runs:
        pytest.skip("no NM-B4 run output")
    return runs[-1]


# 1, 2
def test_counts():
    assert len(nm.QCFG) + len(nm.WFCFG) == 8 and len(nm.CONTROLS) == 2
    assert (len(nm.QCFG) + len(nm.WFCFG) + len(nm.CONTROLS)) * len(nm.OFFSETS) * len(nm.PENS) == 60
    assert len({nm.cid(p) for p in nm.QCFG + nm.WFCFG}) == 8


def test_styles_q4_wf4():
    assert [nm.cid(p) for p in nm.QCFG] == ["Q-W180-P50", "Q-W180-P65", "Q-W365-P50", "Q-W365-P65"]
    assert [nm.cid(p) for p in nm.WFCFG] == ["WF-H365-C3", "WF-H365-C6", "WF-H730-C3", "WF-H730-C6"]


# 3
def test_threshold_rows():
    n4 = (b2.END - b2.START).days * 6
    assert n4 == 14832 and 4 * n4 == 59328
    run = latest_run()
    tt = pd.read_parquet(run / "adaptive_thresholds.parquet")
    assert len(tt) == 59328 and tt.groupby("config_id").size().eq(14832).all()


# 4, 5
def test_refits():
    n = [len(nm.anchors(p["H"], p["C"])) for p in nm.WFCFG]
    assert n == [20, 10, 16, 8] and sum(n) == 54
    assert nm.anchors(365, 3)[-1] == pd.Timestamp("2026-10-01", tz="UTC")


def test_wf_score_rows():
    run = latest_run()
    ws = pd.read_parquet(run / "walkforward_scores.parquet")
    wc = pd.read_parquet(run / "walkforward_choices.parquet")
    assert len(ws) == 216 and len(wc) == 54 and ws.chosen.sum() == 54
    assert wc.groupby("config_id").size().to_dict() == {"WF-H365-C3": 20, "WF-H365-C6": 10, "WF-H730-C3": 16,
                                                        "WF-H730-C6": 8}


# 6, 7
def test_toy_linear_quantile():
    x = np.array([5.0, 1.0, 4.0, 2.0, 3.0, 10.0, 0.0])
    q = nm.trailing_q(x, 4, 0.65)
    assert np.isnan(q[:4]).all()
    for i in range(4, 7):
        assert q[i] == pytest.approx(np.quantile(x[i - 4:i], 0.65), abs=1e-12)
    s, pos = np.sort(x[0:4]), 0.65 * 3          # sorted [1,2,4,5], pos 1.95 -> 3.9
    assert q[4] == pytest.approx(s[int(pos)] + (pos - int(pos)) * (s[int(pos) + 1] - s[int(pos)])) == 3.9


def test_current_row_excluded():
    x = np.arange(20, dtype=float)
    y = x.copy(); y[10] = 1e9
    a, b = nm.trailing_q(x, 5, 1.0), nm.trailing_q(y, 5, 1.0)     # max of the sample: spike at i only seen from i+1
    assert a[10] == b[10] == 9.0 and a[11] == 10.0 and b[11] == 1e9
    z = x.copy(); z[3] = np.nan
    assert np.isnan(nm.trailing_q(z, 5, 0.5)[4:9]).all() and np.isfinite(nm.trailing_q(z, 5, 0.5)[9])


# 8
def test_latest_funding_excluded():
    ft = b2.START.value + np.arange(0, 20) * 480 * MIN
    fr = np.zeros(20); fr[10] = 1.0
    m = market(np.full(20 * 480, 100.0), ft, fr)
    q, lo, hi = nm.funding_thr(m, 1, (0.5, 1.0))
    assert np.all(hi <= np.arange(20)) and q[10, 1] == 0.0 and q[11, 1] == 1.0     # own event never in sample
    assert np.isnan(q[:3]).all() and np.isfinite(q[3]).all()                    # W=1d history needs ft_j-1d >= ft_0


def test_funding_publish_equal_T_excluded():
    n = 240 * 12
    T0 = b2.START.value + 240 * MIN                                 # first 4h decision time
    ft = np.array([T0 - 480 * MIN, T0 - 1, T0, T0 + 1])             # one event exactly at T
    m = market(np.full(n, 100.0), ft, np.array([0.1, 0.2, 0.3, 0.4]))
    dec4 = np.arange(239, n, 240)
    inp = nm.adaptive_inputs(m, dec4)
    assert inp["T"][0] == T0 and inp["j"][0] == 1 and m.ft[inp["j"][0]] < T0
    fz, fr, _ = nm.gate_inputs_strict(m, dec4, np.arange(1439, n, 1440))
    assert fr[0] == 0.2
    _, fr_orig, _ = b3.gate_inputs(m, dec4, np.arange(1439, n, 1440))
    assert fr_orig[0] == 0.3                                        # original Batch-3 semantics included it


# 9
def test_tamper_future_unchanged():
    c, ft, fr = synth(420, 1)
    m = market(c, ft, fr)
    dec4 = np.arange(239, m.N, 240)
    _, th = nm.all_thresholds(m, dec4)
    cut = len(dec4) - 200
    tcut = m.t[dec4[cut]] + MIN
    c2, fr2 = c.copy(), fr.copy()
    c2[dec4[cut] + 1:] *= 1.7
    fr2[ft > tcut] = -0.05
    _, th2 = nm.all_thresholds(market(c2, ft, fr2), dec4)
    for a in nm.INNER:
        for k in ("db", "g", "tv", "fthr", "side", "w"):
            assert np.array_equal(th[a][k][:cut + 1], th2[a][k][:cut + 1], equal_nan=True), (a, k)
    assert (th[(180, 0.5)]["side"] != 0).any()


# 10
def test_prefix_equals_full():
    c, ft, fr = synth(915, 2)
    m = market(c, ft, fr)
    end = pd.Timestamp(m.t[-1] + MIN, tz="UTC")
    dec4 = np.arange(239, m.N, 240)
    _, th = nm.all_thresholds(m, dec4)
    books = nm.inner_books(m, dec4, th)
    Rs = nm.anchors(365, 3, end=end)
    assert len(Rs) == 3
    for R in Rs:
        rows = nm.wf_rows(books, m, R, 365)
        nm.prefix_check(m, dec4, th, {365: rows}, R)          # raises on any threshold / P&L / choice mismatch


# 11
def test_warmup_fail_closed():
    c, ft, fr = synth(420, 3)
    m = market(c, ft, fr)
    dec4 = np.arange(239, m.N, 240)
    _, th = nm.all_thresholds(m, dec4)
    x = th[(180, 0.5)]
    first = np.flatnonzero(x["ready_4h"])[0]
    assert first >= 6 * 180 + 180 and (x["side"][:first] == 0).all() and (x["w"][:first] == 0).all()
    assert not x["ready_f"][m.t[dec4] + MIN < ft[0] + 180 * DAY].any()
    f365 = np.flatnonzero(th[(365, 0.5)]["ready_4h"])[0]
    assert f365 >= 6 * 365 + 180 and (th[(365, 0.5)]["side"][:f365] == 0).all()
    assert not th[(365, 0.5)]["ready_f"][m.t[dec4] + MIN < ft[0] + 365 * DAY].any()


# 12
def test_state_flat_held_short_exits_passively():
    n4 = 30
    c = 100 * np.exp(np.cumsum(np.random.default_rng(4).normal(0, 5e-4, 240 * n4)))
    ft = b2.START.value + np.arange(0, 240 * n4, 480) * MIN + 1000
    fr = np.full(len(ft), 1e-4)
    m = market(c, ft, fr)
    dec4 = np.arange(239, m.N, 240)
    T = m.t[dec4] + MIN
    inp = dict(T=T, score=np.full(n4, -2.0), svi=np.full(n4, -0.5), sig=np.full(n4, 0.5),
               j=np.searchsorted(ft, T, "right") - 1)
    inp["score"][:7] = np.linspace(-1, 1, 7)
    fthr = np.zeros(len(ft)); fthr[ft > T[15]] = 1.0          # funding condition fails from decision 16+
    x = nm.thresholds(inp, m, 1, 0.5, fthr)
    assert (x["side"][7:16] == -1).all() and (x["side"][17:] == 0).all() and (x["des"][17:] == -1).all()
    tr, _ = b2.simulate(m, "state", dec4, x["side"], x["w"], 2, 60, 0.5, 0, m.N)
    s = tr[tr.side < 0]
    assert len(s) >= 1 and not s.open_at_end.iloc[-1] and s.exit_decision_idx.iloc[-1] in set(dec4[16:18])


# 13
def test_wf_first_trade_after_first_refit():
    assert nm.anchors(365, 3)[0] == pd.Timestamp("2022-01-01", tz="UTC")
    assert nm.anchors(730, 6)[0] == pd.Timestamp("2023-01-01", tz="UTC")
    T = np.arange(b2.START.value, b2.END.value, 4 * 3600 * 10**9)
    th = {a: dict(side=np.ones(len(T), int), w=np.ones(len(T)), des=np.ones(len(T), int), gate=np.ones(len(T), bool))
          for a in nm.INNER}
    for H, C in ((365, 3), (730, 6)):
        Rs = nm.anchors(H, C)
        side, w, _, _ = nm.wf_signal(th, T, Rs, [nm.INNER[0]] * len(Rs))
        assert T[np.flatnonzero(side)[0]] == Rs[0].value and (side[T < Rs[0].value] == 0).all()
    run = latest_run()
    for f in (run / "trades").glob("WF_*.parquet"):
        t = pd.read_parquet(f)
        cfg = json.loads((run / "selected_walkforward.json").read_text())
        H = next(iter(cfg.values()))["params"]["H"]
        assert (t.decision_time + pd.Timedelta(minutes=1) >= nm.anchors(H, 3)[0]).all()


class FakeBook:
    def __init__(self, v):
        self.v = v

    def window(self, a, b):
        return {**{f"{s}_{k}": self.v[s] for s in nm.SIDES for k in ("net4",)},
                **{f"{s}_{k}": 0 for s in nm.SIDES for k in ("gross", "funding", "entries", "closed")},
                "mdd_1m": self.v.get("mdd", 1.0), "turnover": 1.0}


class FakeM:
    def __init__(self, days=2000):
        self.t = b2.START.value + np.arange(days * 1440) * MIN

    def idx(self, ts):
        return int(np.searchsorted(self.t, pd.Timestamp(ts).value))


# 14
def test_refit_score_manual():
    vals = {(180, 0.5): (365.0, 730.0, -365.0, 0.0), (180, 0.65): (730.0, 730.0, 730.0, 730.0),
            (365, 0.5): (0.0, 0.0, 0.0, 0.0), (365, 0.65): (1095.0, 365.0, 365.0, 365.0)}
    books = {}
    for a, (l2, s2, l5, s5) in vals.items():
        books[(a, 2)] = FakeBook({"long": l2, "short": s2})
        books[(a, 5)] = FakeBook({"long": l5, "short": s5})
    R = pd.Timestamp("2023-01-01", tz="UTC")
    rows = nm.wf_rows(books, FakeM(), R, 365)
    sc = {(r["W"], r["q"]): r["score"] for r in rows}
    assert sc == {(180, 0.5): -1.0, (180, 0.65): 2.0, (365, 0.5): 0.0, (365, 0.65): 1.0}
    assert [r["chosen"] for r in rows] == [False, True, False, False]
    with pytest.raises(AssertionError):
        nm.wf_rows(books, FakeM(300), R, 365)                     # train window truncated -> not H days


# 15
def test_tie_break_order():
    base = dict(score=1.0, all_mean_per_day=1.0, mdd_1m=5.0, turnover=3.0)
    rows = [dict(base, W=365, q=0.65), dict(base, W=365, q=0.5), dict(base, W=180, q=0.65), dict(base, W=180, q=0.5)]
    assert (nm.wf_rank(rows)[0]["W"], nm.wf_rank(rows)[0]["q"]) == (180, 0.5)
    rows[3]["turnover"] = 4.0
    assert (nm.wf_rank(rows)[0]["W"], nm.wf_rank(rows)[0]["q"]) == (180, 0.65)
    rows[1]["mdd_1m"] = 1.0
    assert nm.wf_rank(rows)[0] is rows[1]
    rows[0]["all_mean_per_day"] = 2.0
    assert nm.wf_rank(rows)[0] is rows[0]
    rows[3]["score"] = 1.5
    assert nm.wf_rank(rows)[0] is rows[3]


# 16
def test_window_days():
    n = (b2.END - b2.START).value // MIN
    m = FakeM((b2.END - b2.START).days)
    assert len(m.t) == n
    wb = b3.window_bounds(m)
    assert {k: (b - a) // 1440 for k, (a, b) in wb.items()} == {"DEV-FULL": 2192, "DEV-A": 1461, "DEV-B": 731, "TEST": 280}


def _book(days=6, seed=5):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 8e-4, 1440 * days)))
    ft = b2.START.value + np.arange(0, len(c), 480) * MIN
    m = market(c, ft, rng.normal(0, 1e-4, len(ft)))
    dec = np.arange(239, m.N, 240)
    side = np.tile([1, 1, -1, -1, 0], len(dec))[:len(dec)]
    tr, od = b2.simulate(m, "state", dec, side, np.full(len(dec), 0.7), 2, 60, 0.5, 0, m.N)
    return m, tr, od, b2.Book(m, tr, od, 0, m.N)


# 17
def test_split_no_extra_cost():
    m, tr, od, bk = _book()
    span = tr[(tr.entry_idx < 3 * 1440) & ((tr.exit_idx >= 3 * 1440) | tr.open_at_end)]
    a, b = bk.window(0, 3 * 1440), bk.window(3 * 1440, m.N)
    assert abs(a["net4"] + b["net4"] - bk.net4_full.sum()) < 1e-6
    assert a["closed"] + b["closed"] == int((~tr.open_at_end).sum()) and a["entries"] + b["entries"] == len(tr)
    nm.window_checks(bk, {"DEV-FULL": (0, 4 * 1440), "DEV-A": (0, 2 * 1440), "DEV-B": (2 * 1440, 4 * 1440),
                          "TEST": (4 * 1440, m.N)}, m)
    assert len(span) <= 1


# 18
def test_1m_pnl_partition():
    m, tr, od, bk = _book(seed=6)
    cuts = [0, 1440, 2 * 1440 + 0, 5 * 1440, m.N]
    tot = sum(bk.window(a, b)["net4"] for a, b in zip(cuts[:-1], cuts[1:]))
    assert abs(tot - bk.pnl.sum()) < 1e-6 and abs(bk.daily(0, m.N).sum() - bk.pnl.sum()) < 1e-6


# 19
def test_long_short_sum():
    m, tr, od, bk = _book(seed=7)
    sb = b3.side_books(m, bk)
    assert np.allclose(sb["all"].daily(0, m.N), sb["long"].daily(0, m.N) + sb["short"].daily(0, m.N))
    w = bk.window(0, m.N)
    assert abs(w["long_net4"] + w["short_net4"] - w["net4"]) < 1e-9


# 20
def test_bootstrap_seeded():
    x = np.random.default_rng(1).normal(size=120)
    assert b2.stationary_boot_p05(x, 20, 300) == b2.stationary_boot_p05(x, 20, 300)
    assert nm.SEED == 20261010 and nm.NBOOT == 10_000 and nm.BLOCKS == (20, 60, 120)


def _R(v=1.0, closed=30, fill=0.5):
    w = {f"{s}_{k}": v for s in nm.SIDES for k in ("net4", "per_day")}
    w.update({f"{s}_closed": closed for s in nm.SIDES} | {f"{s}_exp_days": 0 for s in nm.SIDES})
    w["fill_notional_rate"] = fill
    return {(o, p): {k: dict(w) for k in nm.WINDOWS} for o in nm.OFFSETS for p in nm.PENS}


# 21
def test_selection_verdict_regression():
    R = _R()
    assert b3.eligible(R) and b3.dev_score(R) == 1.0 and b3.adapt_score(R) == 1.0
    assert not b3.eligible(_R(fill=0.05)) and not b3.eligible(_R(closed=5))
    R2 = _R()
    R2[(5, 1.0)]["DEV-B"]["short_net4"] = -1
    assert b3.eligible(R2)
    pos = {"all": 1, "long": 1, "short": 1}
    v = b3.verdict(R, True, pos)
    assert v["PROFIT_PASS"] and v["STRONG"] and v["ROBUST_PASS"] and v["SIDE_STRONG"] and not v["LOW_N"]
    assert not b3.verdict(R2, True, pos)["ROBUST_PASS"]
    assert b3.verdict(_R(closed=5), True, pos)["LOW_N"]
    R4 = _R()
    R4[(2, 0.5)]["TEST"]["long_net4"] = -1
    assert b3.verdict(R4, True, pos)["verdict"] == "FAIL"
    run = latest_run()
    cm = pd.read_parquet(run / "config_metrics.parquet").set_index("config_id")
    for c, r in cm.iterrows():
        assert r.verdict == ("+".join(k for k in ("PROFIT_PASS", "LOW_N", "STRONG", "ROBUST_PASS", "SIDE_STRONG")
                                      if r[k]) or "FAIL")


# 22, 23
def test_control_parity_vs_batch3():
    run = latest_run()
    g = pd.read_parquet(run / "grid.parquet").set_index("sim_id")
    old = pd.read_parquet(nm.PARENT_DIR / "grid.parquet").set_index("sim_id")
    cols = [c for c in g.columns if c.split("_")[0] in nm.WINDOWS and c in old.columns and not c.endswith("_worst")]
    n = 0
    for lab, p in nm.CONTROLS.items():
        for o in nm.OFFSETS:
            for q in nm.PENS:
                a, b = g.loc[nm.sid(lab, o, q), cols].astype(float), old.loc[b3.sid(p, o, q), cols].astype(float)
                assert np.allclose(a, b, atol=1e-9, rtol=0, equal_nan=True), (lab, o, q)
                n += 1
    assert n == 12 and len(cols) > 4 * 40


def test_control_primary_net4():
    run = latest_run()
    g = pd.read_parquet(run / "grid.parquet").set_index("sim_id")
    for lab, vals in nm.CONTROL_NET4.items():
        r = g.loc[nm.sid(lab, 2, 0.5)]
        assert [round(r[f"{w}_net4"], 4) for w in ("DEV-FULL", "DEV-B", "TEST")] == list(vals)


# 24
def test_registry_counts_idempotent(tmp_path):
    run = latest_run()
    g = pd.read_parquet(run / "grid.parquet")
    reg = tmp_path / "reg.jsonl"
    sel = {"X": {"config_id": "Q-W180-P50"}}
    assert nm.write_registry(g, sel, {"h": "1"}, "run", reg) == {"added": 61, "skipped": 0}
    rows = [json.loads(x) for x in reg.read_text().splitlines()]
    sims = [r for r in rows if r["role"] != "selection"]
    assert len(sims) == 60 and sum(r["n_trials"] for r in sims) == 48
    assert sum(r["role"] == "control" and r["n_trials"] == 0 for r in sims) == 12
    s = next(r for r in rows if r["role"] == "selection")
    assert s["n_trials"] == 0 and s["result_summary"]["batch_trials"] == 48 and s["result_summary"]["batch_simulations"] == 60
    assert nm.write_registry(g, sel, {"h": "1"}, "run", reg) == {"added": 0, "skipped": 61}
    gs = pd.read_parquet(run / "controls_strict.parquet")
    assert len(gs) == 12
    assert nm.write_registry(g, sel, {"h": "1"}, "run", reg, g_strict=gs) == {"added": 12, "skipped": 61}
    rows = [json.loads(x) for x in reg.read_text().splitlines()]
    assert sum(r["role"] == "control_strict" and r["n_trials"] == 0 for r in rows) == 12
    assert sum(r["n_trials"] for r in rows) == 48


# 25
def test_output_row_counts():
    run = latest_run()
    n = {f: len(pd.read_parquet(run / f)) for f in ("grid.parquet", "fold_metrics.parquet", "config_metrics.parquet",
                                                     "adaptive_thresholds.parquet", "walkforward_scores.parquet",
                                                     "walkforward_choices.parquet", "signal_diagnostics.parquet",
                                                     "bootstrap.parquet")}
    assert n == {"grid.parquet": 60, "fold_metrics.parquet": 240, "config_metrics.parquet": 10,
                 "adaptive_thresholds.parquet": 59328, "walkforward_scores.parquet": 216,
                 "walkforward_choices.parquet": 54, "signal_diagnostics.parquet": 240, "bootstrap.parquet": 360}
    assert len((run / "runs.jsonl").read_text().splitlines()) == 60
    sc = pd.read_parquet(run / "style_comparison.parquet")
    assert {"CONTROL_B3_DEV_PICK", "CONTROL_B3_RESELECTED"} <= set(sc.label) and len(sc) == 4 * sc.label.nunique()
    for f in ("selected_quantile.json", "selected_walkforward.json", "selected_adaptive.json", "reselected_adaptive.json",
              "controls.json", "manifest.json"):
        assert (run / f).exists()
    man = json.loads((run / "manifest.json").read_text())
    assert man["counts"]["sims"] == 60 and man["data_cutoff"].startswith("2026-10-08")
    labs = {p.stem for p in (run / "trades").glob("*.parquet")}
    assert labs == {p.stem for p in (run / "daily").glob("*.parquet")} and len(labs) == sc.label.nunique()
