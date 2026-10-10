"""Batch-3 (2026-10-10): family G3 = Batch-2 G long kept + funding-based short gate.

Spec: scratchpad codex_batch3.md section 2 (Codex Batch-2 review + Batch-3 spec). Parent run NM-B2-20261010T065219Z-97244bea.
Frozen hypothesis: G short losses in DEV-B come from negative-funding / crowded-short regimes; restricting only the short
side with the latest funding state keeps G long and makes short net4 > 0 in both DEV-B and TEST.

Engine: imported unchanged from out/run_new_model_batch2_20261010.py (simulate, Book, fill model, PESS funding,
stationary bootstrap, data loading, G features); its file hash is an input hash. Batch-2 fixes applied here:
  * evaluation windows fixed for every config: DEV-FULL 2192d, DEV-A 1461d, DEV-B 731d, TEST 280d (asserted);
  * zero-weight NaN: blend() sums only positive-weight components (G3 itself has no blended score; kept for parity
    of the engine contract and unit-tested).
Grid: 8 G bases (SVI g=0.10, db=0.50) x (gate none + 7 short gates x {state_flat, entry_veto}) = 120 logical configs;
each simulated at offset {2,5} bps x penetration {0.5,1,2} bp = 720 continuous simulations 2020-01-01..2026-10-08.
Interpretations (spec silent; recorded in the manifest):
  * decisions on closed 4h bars (minute index 239 + 240k), T = bar open + 1m; gate inputs as-of T (available <= T);
  * funding_z = robust z of the latest published funding event vs the previous 90 events (current excluded, min 30),
    i.e. Batch-2 fz90; latest_funding_rate = rate of that same event; funding time = Market.ft (as in Batch-2 K);
  * daily_score = Batch-2 1d tsmom (30,90,180,360), sigma = std of the previous 30 daily log returns (current excluded),
    taken from the latest completed 1d bar whose close minute <= decision minute;
  * gate input missing (NaN) -> comparison False -> short fail-closed; long never gated;
  * state_flat: short target -> 0 when the gate is false (held short exits passively, no entry);
    entry_veto: only new short entries blocked; a held short keeps following the G base target;
  * eligibility 'primary each side closed>=20 OR exposure>=180d' read on DEV-FULL (as Batch-2);
  * signal diagnostics 'blocked_flat' = base-short decisions with gate false while no position is held
    (pending unfilled entry orders not tracked); 'forced_exit' = closed shorts whose exit decision still had base short.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.sim import provenance, registry  # noqa: E402
from btcusdt_quant.sim.store import canonical  # noqa: E402

B2_PATH = ROOT / "out/run_new_model_batch2_20261010.py"
_spec = importlib.util.spec_from_file_location("nm_b2", B2_PATH)
b2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b2)

OUT_BASE = ROOT / "out/new_model_batch3_20261010"
PARENT = "NM-B2-20261010T065219Z-97244bea"
PARENT_DIR = ROOT / "out/new_model_batch2_20261010" / PARENT
REGISTRY = b2.REGISTRY
WINDOWS, SIDES, SEED, NBOOT, BLOCKS = b2.WINDOWS, b2.SIDES, b2.SEED, b2.NBOOT, b2.BLOCKS
WIN_DAYS = {"DEV-FULL": 2192, "DEV-A": 1461, "DEV-B": 731, "TEST": 280}
OFFSETS, PENS, PRIMARY = (2, 5), (0.5, 1.0, 2.0), (2, 0.5)
DB, G_SVI = 0.50, 0.10
BASES = [dict(base=i + 1, svi_w=w, trend=str(ts), tv=tv) for i, (ts, w, tv) in enumerate(
    (ts, w, tv) for ts in ((42, 168, 504), (6, 18, 42)) for w in (42, 180) for tv in (0.20, 0.40))]
GATES = ("none", "fz>=-0.5", "fz>=0", "fz>=0.5", "fz>=0&daily_ready", "fz>=0&daily<=0", "fz>=0&daily<=-0.25",
         "fr>=0&daily_ready")
ACTIONS = ("state_flat", "entry_veto")
B2_SANITY_ID = "family=G|svi_w=42|g=0.1|trend=(42, 168, 504)|db=0.5|tv=0.2|offset=2"


def blend(parts, weights):
    """Weighted sum over positive-weight parts only (0 * NaN must not poison the score)."""
    return sum(w * x for w, x in zip(weights, parts) if w > 0)


def grid():
    out = [dict(**b, gate="none", action="none") for b in BASES]
    out += [dict(**b, gate=g, action=a) for b in BASES for g in GATES[1:] for a in ACTIONS]
    assert len(out) == 120 and len({cid(p) for p in out}) == 120
    return out


def cid(p: dict) -> str:
    return "|".join(f"{k}={v}" for k, v in p.items())


def sid(p: dict, off, pen) -> str:
    return f"{cid(p)}|offset={off}|pen={pen}"


def window_bounds(m) -> dict:
    wb = {k: (m.idx(a), m.idx(b)) for k, (a, b) in WINDOWS.items()}
    assert {k: (b - a) // 1440 for k, (a, b) in wb.items()} == WIN_DAYS, wb
    return wb


# ---------------- gates / signal ----------------
def gate_inputs(m, dec4, d1):
    """funding_z, latest funding rate, daily score as-of each 4h decision (T = t[dec] + 1m)."""
    T = m.t[dec4] + b2.MIN
    fz90 = b2.b1.trailing_robust_z(m.fr, 90, 30)
    fz = b2.asof_values(m.ft, fz90, T, None)
    fr = b2.asof_values(m.ft, m.fr, T, None)
    ds, _ = b2.tsmom_score(m.c[d1], (30, 90, 180, 360), 30)
    p = b2.asof_bars(d1, dec4)
    assert np.all(d1[p[p >= 0]] <= dec4[p >= 0]), "daily bar closes after decision"
    return fz, fr, b2.take(ds, p)


def gate_masks(fz, fr, daily) -> dict:
    """True = short allowed. NaN inputs compare False -> fail-closed."""
    with np.errstate(invalid="ignore"):
        ready = np.isfinite(daily)
        return {"none": np.ones(len(fz), bool), "fz>=-0.5": fz >= -0.5, "fz>=0": fz >= 0, "fz>=0.5": fz >= 0.5,
                "fz>=0&daily_ready": (fz >= 0) & ready, "fz>=0&daily<=0": (fz >= 0) & (daily <= 0),
                "fz>=0&daily<=-0.25": (fz >= 0) & (daily <= -0.25), "fr>=0&daily_ready": (fr >= 0) & ready}


def base_side(sc, svi):
    with np.errstate(invalid="ignore"):
        return np.where((sc >= DB) & (svi >= G_SVI), 1, np.where((sc <= -DB) & (svi <= -G_SVI), -1, 0))


def g3_signal(des, gate, action):
    """-> (side, entry_ok). Gate only touches shorts."""
    blocked = (des < 0) & ~gate
    if action == "state_flat":
        return np.where(blocked, 0, des), None
    if action == "entry_veto":
        return des, ~blocked
    assert action == "none" and not blocked.any()
    return des, None


# ---------------- selection / verdicts ----------------
def eligible(R) -> bool:
    p = R[PRIMARY]["DEV-FULL"]
    ok = all(R[(o, 0.5)][w][f"{s}_net4"] > 0 for o in OFFSETS for w in ("DEV-FULL", "DEV-A", "DEV-B") for s in SIDES)
    ok &= all(p[f"{s}_closed"] >= 20 or p[f"{s}_exp_days"] >= 180 for s in SIDES)
    ok &= bool(p["fill_notional_rate"] >= 0.10)
    return bool(ok)


def dev_score(R) -> float:
    return min(R[(o, 0.5)][w][f"{s}_per_day"] for o in OFFSETS for w in ("DEV-A", "DEV-B") for s in SIDES)


def adapt_score(R) -> float:
    return min(R[(o, p)]["TEST"][f"{s}_per_day"] for o in OFFSETS for p in PENS for s in SIDES)


def verdict(R, elig: bool, boot60: dict) -> dict:
    profit = elig and all(R[(o, 0.5)]["TEST"][f"{s}_net4"] > 0 for o in OFFSETS for s in SIDES)
    low_n = any(R[PRIMARY]["TEST"][f"{s}_closed"] < 10 for s in SIDES)
    strong = profit and not low_n and boot60["all"] > 0
    robust = all(R[(o, p)][w][f"{s}_net4"] > 0 for o in OFFSETS for p in PENS for w in WINDOWS for s in SIDES)
    side_strong = robust and boot60["long"] > 0 and boot60["short"] > 0
    flags = {"PROFIT_PASS": profit, "LOW_N": low_n, "STRONG": strong, "ROBUST_PASS": robust, "SIDE_STRONG": side_strong}
    return {**flags, "verdict": "+".join(k for k, v in flags.items() if v) or "FAIL"}


# ---------------- run ----------------
def side_books(m, book):
    tr = book.tr
    return {"all": book, **{s: b2.Book(m, tr[mk].reset_index(drop=True), book.orders, book.lo, book.hi)
                            for s, mk in (("long", tr.side > 0), ("short", tr.side < 0))}}


def diagnostics(tr, dec4, des, gate, wb) -> dict:
    """Per window: base-short decisions, gate pass/fail, blocked while flat, gate-forced short exits."""
    ds, ex = tr.decision_idx.to_numpy(), np.where(tr.open_at_end, np.iinfo(np.int64).max, tr.exit_idx).astype(np.int64)
    k = np.searchsorted(ds, dec4, "right") - 1
    held = (k >= 0) & (dec4 < ex[np.maximum(k, 0)]) if len(ds) else np.zeros(len(dec4), bool)
    short = des < 0
    pos = {d: i for i, d in enumerate(dec4)}
    forced = np.zeros(len(dec4), bool)
    for x in tr.exit_decision_idx[(tr.side < 0) & ~tr.open_at_end]:
        i = pos.get(int(x))
        if i is not None:
            forced[i] = des[i] < 0
    out = {}
    for w, (a, b) in wb.items():
        mk = (dec4 >= a) & (dec4 < b)
        out[w] = {"base_short_dec": int((short & mk).sum()), "gate_pass": int((short & gate & mk).sum()),
                  "gate_fail": int((short & ~gate & mk).sum()), "blocked_flat": int((short & ~gate & ~held & mk).sum()),
                  "forced_exit": int((forced & mk).sum())}
    return out


def input_hashes() -> dict:
    h = b2.input_hashes()
    h["batch2_code"] = h.pop("code")
    h["code"] = provenance.file_sha256(Path(__file__))
    h["parent_manifest"] = provenance.file_sha256(PARENT_DIR / "manifest.json")
    return h


def registry_keys(path: Path) -> set:
    return b2.registry_keys(path)


def write_registry(g: pd.DataFrame, sel: dict, hashes: dict, run_id: str) -> dict:
    have = registry_keys(REGISTRY)
    ih = hashlib.sha256(canonical(hashes).encode()).hexdigest()
    added = skipped = 0
    for r in g.to_dict("records"):
        key = hashlib.sha256(canonical({"batch": "NM-B3", "sim_id": r["sim_id"], "inputs": ih}).encode()).hexdigest()
        if key in have:
            skipped += 1
            continue
        registry.record(REGISTRY, {
            "experiment": f"NM-B3 G3 {r['sim_id']}", "idempotency_key": key,
            "config": {"sim_id": r["sim_id"], "run_id": run_id, "parent_run_id": PARENT,
                       "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()},
                       "costs": "4 bps rt maker flat, 0 slip, PESS funding; 8 bps report-only"},
            "input_hashes": hashes, "n_trials": 1,
            "result_summary": {f"{w}_{k}": r[f"{w}_{k}"] for w in WINDOWS
                               for k in ("net4", "net8", "long_net4", "short_net4", "closed", "fill_notional_rate")}})
        added += 1
    key = hashlib.sha256(canonical({"batch": "NM-B3", "selection": True, "inputs": ih}).encode()).hexdigest()
    if key in have:
        skipped += 1
    else:
        registry.record(REGISTRY, {"experiment": "NM-B3 G3 selection (DEV_PICK/DEV_BEST_INELIGIBLE + RESELECTED_ADAPTIVE)",
                                   "idempotency_key": key, "config": {"run_id": run_id, "parent_run_id": PARENT},
                                   "input_hashes": hashes, "n_trials": 0,
                                   "result_summary": {"batch_trials": 720,
                                                      "picks": {k: v["config_id"] for k, v in sel.items()}}})
        added += 1
    return {"added": added, "skipped": skipped}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-registry", action="store_true")
    args = ap.parse_args(argv)
    t0 = time.time()
    code_hash = provenance.file_sha256(Path(__file__))
    run_id = f"NM-B3-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{code_hash[:8]}"
    run_dir = OUT_BASE / run_id
    run_dir.mkdir(parents=True, exist_ok=False)          # write-once
    minutes, met, prem, funding = b2.load_all()
    m = b2.Market.from_frames(minutes, funding)
    del minutes, met, prem
    wb = window_bounds(m)
    dec4, d1 = np.arange(239, m.N, 240), np.arange(1439, m.N, 1440)
    fe = SimpleNamespace(m=m, h4=dec4)
    b2.Features.g_prep(fe)                                # Batch-2 G features, unchanged code
    fz, fr, daily = gate_inputs(m, dec4, d1)
    masks = gate_masks(fz, fr, daily)
    print(f"[load] N={m.N} funding={len(m.ft)} {time.time()-t0:.0f}s", flush=True)

    params = grid()
    rows, fold, diag, R_all, sigs = [], [], [], {}, {}
    for n_, p in enumerate(params):
        G = fe.G
        des = base_side(G["score"][eval(p["trend"])], G["svi"][p["svi_w"]])
        w = np.nan_to_num(np.minimum(1.0, p["tv"] / G["sig_ann"]))
        side, ok = g3_signal(des, masks[p["gate"]], p["action"])
        sigs[cid(p)] = (des, side, w, ok)
        R = {}
        for off in OFFSETS:
            for pen in PENS:
                tr, od = b2.simulate(m, "state", dec4, side, w, off, b2.TTL_TREND, pen, 0, m.N, entry_ok=ok)
                book = b2.Book(m, tr, od, 0, m.N)
                ev = {k: book.window(a, b) for k, (a, b) in wb.items()}
                R[(off, pen)] = ev
                s_id = sid(p, off, pen)
                row = {"sim_id": s_id, "config_id": cid(p), **p, "offset": off, "pen_bps": pen}
                for k, d in ev.items():
                    row.update({f"{k}_{x}": v for x, v in d.items()})
                    fold.append({"sim_id": s_id, "config_id": cid(p), "offset": off, "pen_bps": pen, "window": k, **d})
                for k, d in diagnostics(tr, dec4, des, masks[p["gate"]], wb).items():
                    diag.append({"sim_id": s_id, "config_id": cid(p), "gate": p["gate"], "action": p["action"],
                                 "offset": off, "pen_bps": pen, "window": k, **d,
                                 "short_entries": ev[k]["short_entries"], "short_closed": ev[k]["short_closed"],
                                 "long_entries": ev[k]["long_entries"], "long_closed": ev[k]["long_closed"]})
                rows.append(row)
        R_all[cid(p)] = R
        print(f"[grid] {n_+1}/120 {time.time()-t0:.0f}s", flush=True)
    g = pd.DataFrame(rows)
    for k in WINDOWS:
        g[f"{k}_worst"] = g[[f"{k}_long_net4", f"{k}_short_net4"]].min(axis=1)
    cfg = pd.DataFrame([{"config_id": c, "DEV_eligible": eligible(R), "DEV_score": dev_score(R),
                         "ADAPT_score": adapt_score(R)} for c, R in R_all.items()])
    g = g.merge(cfg, on="config_id")
    assert len(g) == 720 and g.sim_id.is_unique

    # sanity: gate none, base 1, offset 2, pen 0.5 == Batch-2 G DEV_PICK
    old = pd.read_parquet(PARENT_DIR / "grid.parquet").set_index("variant_id").loc[B2_SANITY_ID]
    new = g.set_index("sim_id").loc[sid(params[0], 2, 0.5)]
    cols = [f"{k}_{x}" for k in WINDOWS for x in R_all[cid(params[0])][PRIMARY]["TEST"] if f"{k}_{x}" in old.index]
    diffs = {c: float(new[c]) - float(old[c]) for c in cols
             if not (pd.isna(new[c]) and pd.isna(old[c])) and float(new[c]) != float(old[c])}
    sanity = {"b2_variant": B2_SANITY_ID, "b3_sim": new.name, "n_compared": len(cols), "n_diff": len(diffs),
              "diffs": diffs, **{f"{k}_{x}": float(new[f"{k}_{x}"]) for k in WINDOWS for x in ("net4", "short_net4")}}
    print(f"[sanity] compared {len(cols)} diff {len(diffs)}", flush=True)

    # selection
    primary = g[(g.offset == 2) & (g.pen_bps == 0.5)].set_index("config_id")
    el = cfg[cfg.DEV_eligible].merge(primary[["DEV-FULL_mdd_1m", "DEV-FULL_turnover"]], left_on="config_id", right_index=True)
    allc = cfg.merge(primary[["DEV-FULL_mdd_1m", "DEV-FULL_turnover"]], left_on="config_id", right_index=True)
    order = dict(by=["DEV_score", "DEV-FULL_mdd_1m", "DEV-FULL_turnover"], ascending=[False, True, True])
    picks = {("DEV_PICK" if len(el) else "DEV_BEST_INELIGIBLE"): (el if len(el) else allc).sort_values(**order).iloc[0]}
    if len(el):
        picks["RESELECTED_ADAPTIVE"] = el.sort_values(["ADAPT_score", "DEV_score"], ascending=False).iloc[0]
    sel, boot_rows = {}, []
    (run_dir / "trades").mkdir()
    (run_dir / "daily").mkdir()
    for lab, best in picks.items():
        c = best.config_id
        p = next(q for q in params if cid(q) == c)
        R = R_all[c]
        des, side, w, ok = sigs[c]
        tr, od = b2.simulate(m, "state", dec4, side, w, 2, b2.TTL_TREND, 0.5, 0, m.N, entry_ok=ok)
        books = side_books(m, b2.Book(m, tr, od, 0, m.N))
        boots = {}
        for k, (a, b) in wb.items():
            for sc_, bk in books.items():
                dly = bk.daily(a, b)
                for bl in BLOCKS:
                    v = b2.stationary_boot_p05(dly, bl)
                    boots[(k, sc_, bl)] = v
                    boot_rows.append({"pick": lab, "config_id": c, "window": k, "scope": sc_, "block_days": bl,
                                      "p05_mean_day": v, "n_days": len(dly), "n_boot": NBOOT, "seed": SEED})
        vd = verdict(R, bool(best.DEV_eligible), {s: boots[("TEST", s, 60)] for s in ("all", "long", "short")})
        sel[lab] = {"config_id": c, "params": p, "dev_eligible": bool(best.DEV_eligible), "n_eligible": int(len(el)),
                    "dev_score": float(best.DEV_score), "adapt_score": float(best.ADAPT_score), **vd,
                    "metrics_primary": R[PRIMARY],
                    "cells": {k: {f"o{o}_p{q}": {s: R[(o, q)][k][f"{s}_net4"] for s in SIDES}
                                  for o in OFFSETS for q in PENS} for k in WINDOWS},
                    "bootstrap_p05": {k: {s: [boots[(k, s, bl)] for bl in BLOCKS] for s in ("all", "long", "short")}
                                      for k in WINDOWS}}
        if lab == "RESELECTED_ADAPTIVE":
            sel[lab]["label"] = "RESELECTED_ADAPTIVE (chosen on TEST; not independent OOS)"
        t = books["all"].tr.copy()
        if len(t):
            t["net4_full"], t["gross_full"], t["funding_full"] = books["all"].net4_full, books["all"].gross_full, \
                books["all"].fund_full
            for col in ("decision_idx", "entry_idx", "exit_idx", "exit_decision_idx"):
                ix = t[col].to_numpy().astype(int)
                t[col.replace("idx", "time")] = pd.Series(pd.to_datetime(m.t[np.maximum(ix, 0)], utc=True)).where(ix >= 0)
        t.to_parquet(run_dir / "trades" / f"{lab}.parquet", index=False)
        dl = {s: bk.daily(0, m.N) for s, bk in books.items()}
        assert np.allclose(dl["all"], dl["long"] + dl["short"])
        pd.DataFrame({"day": pd.date_range(pd.Timestamp(m.t[0], tz="UTC"), periods=len(dl["all"]), freq="D"),
                      "net4_all": dl["all"], "net4_long": dl["long"], "net4_short": dl["short"],
                      "held": books["all"].held_day}).to_parquet(run_dir / "daily" / f"{lab}.parquet", index=False)
        print(f"[select] {lab} {c} {vd['verdict']} {time.time()-t0:.0f}s", flush=True)

    hashes = input_hashes()
    g.to_parquet(run_dir / "grid.parquet", index=False)
    pd.DataFrame(fold).to_parquet(run_dir / "fold_metrics.parquet", index=False)
    pd.DataFrame(diag).to_parquet(run_dir / "signal_diagnostics.parquet", index=False)
    pd.DataFrame(boot_rows).to_parquet(run_dir / "bootstrap.parquet", index=False)
    dump = lambda o, f: (run_dir / f).write_text(json.dumps(o, indent=2, default=float), encoding="utf-8")  # noqa: E731
    dev_lab = next(k for k in sel if k.startswith("DEV_"))
    dump({dev_lab: sel[dev_lab]}, "selected_dev.json")
    dump(sel.get("RESELECTED_ADAPTIVE"), "reselected_adaptive.json")
    gate_cov = {k: {gn: {"pass_frac_all_4h": float(np.mean(gm[(dec4 >= a) & (dec4 < b)]))} for gn, gm in masks.items()}
                for k, (a, b) in wb.items()}
    manifest = {
        "run_id": run_id, "parent_run_id": PARENT, "created_utc": datetime.now(timezone.utc).isoformat(),
        "spec": "scratchpad codex_batch3.md section 2 (Codex, 2026-10-10)",
        "frozen_hypothesis": "G short DEV-B loss comes from negative-funding / crowded-short regimes; gating only "
                             "shorts on the latest funding state keeps G long and makes DEV-B and TEST short net4 > 0",
        "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()}, "window_days": WIN_DAYS,
        "data_cutoff": str(b2.END),
        "sources": {"dev_market": str(b2.DEV_MARKET), "test_market": str(b2.SNAP / "market_1m.parquet"),
                    "dev_funding": str(b2.DEV_FUNDING), "test_funding": str(b2.SNAP / "funding_model_input.parquet"),
                    "engine": str(B2_PATH)},
        "input_sha256": hashes, "code_sha256": code_hash, "git": b2.git_state(),
        "counts": {"logical_configs": 120, "simulations": 720, "dev_eligible": int(cfg.DEV_eligible.sum())},
        "bases": BASES, "gates": GATES, "actions": ACTIONS, "db": DB, "svi_g": G_SVI,
        "execution": {"tick": b2.TICK, "offsets_bps": OFFSETS, "penetration_bps": PENS, "ttl_min": b2.TTL_TREND,
                      "exit_quote_bps": b2.EXIT_QUOTE_BPS, "requote_min": b2.REQUOTE_MIN, "cost_bps_rt": 4,
                      "report_only_bps_rt": 8, "slippage": 0, "terminal_open": "MTM + reserved 2 bps exit",
                      "funding": "PESS", "weight": "entry_weight_frozen min(1, tv/sigma_ann)", "flat30": False},
        "selection": {"DEV_ELIGIBLE": "offset{2,5} pen0.5 DEV-FULL/A/B long&short net4>0; primary DEV-FULL each side "
                                      "closed>=20 or exp_days>=180; primary DEV-FULL fill_notional_rate>=0.10",
                      "DEV_score": "min per-day over DEV-A/B x long/short x offset2/5 (pen0.5); ties primary DEV-FULL "
                                   "mdd_1m low, turnover low",
                      "RESELECTED_ADAPTIVE": "eligible; max min TEST per-day over long/short x offset x pen (12); "
                                             "chosen on TEST, not independent OOS"},
        "verdict_rules": {"PROFIT_PASS": "eligible and TEST o2/o5 pen0.5 long&short net4>0",
                          "LOW_N": "primary TEST any side closed<10",
                          "STRONG": "PROFIT_PASS and not LOW_N and TEST all boot60 p05>0",
                          "ROBUST_PASS": "all 4 windows x 12 cells (offset x pen x side) net4>0",
                          "SIDE_STRONG": "ROBUST_PASS and TEST long & short boot60 p05>0", "net8": "report only"},
        "bootstrap": {"type": "stationary", "blocks_days": BLOCKS, "n": NBOOT, "seed": SEED,
                      "stat": "mean daily 1m-MTM net4 (bps/day)"},
        "sanity_vs_batch2": sanity, "gate_pass_fraction_all_4h_decisions": gate_cov,
        "pre_run_diagnostic_note": "Codex read-only diagnostic (G DEV_PICK + fz>=0&daily_ready state_flat) was not "
                                   "an official result; this run is the logged rerun",
        "interpretations": __doc__, "runtime_sec": round(time.time() - t0, 1)}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    picked = {v["config_id"] for v in sel.values()}
    with (run_dir / "runs.jsonl").open("x", encoding="utf-8") as fh:      # write-once
        for r in g.to_dict("records"):
            fh.write(canonical({"run_id": run_id, "parent_run_id": PARENT, "sim_id": r["sim_id"],
                                "config_id": r["config_id"], "selected": r["config_id"] in picked,
                                **{k: v for k, v in r.items() if k.endswith(("net4", "net8", "_closed"))}}) + "\n")
    if not args.no_registry:
        print(f"[registry] {write_registry(g, sel, hashes, run_id)}", flush=True)
    print(f"[done] {run_id} {time.time()-t0:.0f}s", flush=True)
    return run_dir


if __name__ == "__main__":
    main()
