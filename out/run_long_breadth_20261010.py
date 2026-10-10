"""LONG-THRESH-BREADTH (2026-10-10): long-only S180 threshold breadth ablation.

Spec: scratchpad codex_b5_review.md section "다음 연구: long tail" (Codex session 01a124e0-8cc4-76b2-9038-1e5868334e7e).
Parent run NM-B5-20261010T080025Z-c55285f2 (LONG_DEV_PICK = G5-S180-c+0.0-W180-P65, long sleeve parity source).
Frozen hypothesis: lowering the long score / SVI entry thresholds below (0.50, 0.10) adds enough long trades to
dilute the TEST profit concentration (14 closed, top1 59.29%) without losing DEV edge.
Fixed: long-only, trend (42,168,504), SVI 180, vol W180-P65 (tv = trailing 180d Q0.65 of sigma_ann, weight
min(1, tv/sigma)), maker 4 bps rt, offset {2,5} x pen {0.5,1,2}, continuous 2020-01-01..2026-10-08 sim.
Grid: score thr {0.30,0.40,0.50} x SVI thr {0.00,0.05,0.10} = 9 logical, 54 sims.
Engine: Batch-5 build_state/core_signal/prefix_checks + Batch-2 simulate/Book/bootstrap + Batch-3 side_books/
window_bounds imported unchanged via importlib.
Decision time: T = market_time[dec4] + 1m (dec4 = 239 + 240k, the 4h bar's last 1m bar); score/SVI/sigma use closes
with index <= dec4 (close time <= T); limit price from close[dec4]; fill search starts at bar dec4+1 (opens at T).
Interpretations:
  * long-only: side = 1 iff ready & score >= s_thr & SVI >= v_thr else 0 (no short leg, so long path timing
    differs from the Batch-5 two-sided sim; parity therefore checked twice: Batch-5 core_signal reproduced exactly,
    and long-only (0.50,0.10) reported against it).
  * DEV selection: offset 2/5 pen 0.5 DEV-A and DEV-B long net4 > 0; DEV-FULL primary closed >= 40; DEV-FULL primary
    fill_notional_rate >= 0.10; score = min DEV-A/DEV-B long boot p05 over blocks 20/60/120. Ties: lower DEV-FULL
    MDD, config id. No eligible config -> DEV_BEST_INELIGIBLE (whole pool, flagged).
  * TEST success: 6/6 cells TEST net4 > 0, primary TEST closed >= 30, TEST boot p05 at 20/60/120 all > 0.
  * top1/top3 share: per-trade window net4 contribution (Book.window partition), largest k / window net4.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, sys, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from btcusdt_quant.sim import provenance, registry  # noqa: E402
from btcusdt_quant.sim.store import canonical  # noqa: E402

B5_PATH = ROOT / "out/run_new_model_batch5_20261010.py"
_s = importlib.util.spec_from_file_location("nm_b5", B5_PATH)
b5 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(b5)
b2, b3 = b5.b2, b5.b3
OUT_BASE = ROOT / "out/long_breadth_20261010"
PARENT = "NM-B5-20261010T080025Z-c55285f2"
PARENT_DIR = ROOT / "out/new_model_batch5_20261010" / PARENT
REGISTRY = b2.REGISTRY
WINDOWS, BLOCKS, OFFSETS, PENS, PRIMARY = b2.WINDOWS, b2.BLOCKS, b5.OFFSETS, b5.PENS, b5.PRIMARY
TREND, SW, VOL = (42, 168, 504), 180, "W180-P65"
SCORES, SVIS = (0.30, 0.40, 0.50), (0.00, 0.05, 0.10)
GRID = [(s, v) for s in SCORES for v in SVIS]
BASE = (0.50, 0.10)
B5_PICK = dict(struct="S180", c=0.0, vol=VOL)
B5_REF = {"DEV-FULL": 22996.2267, "TEST": 1684.1156, "TEST_closed": 14}


def cid(s: float, v: float) -> str:
    return f"LB-S180-W180P65-s{s:.2f}-v{v:.2f}"


def long_signal(st: dict, s_thr: float, v_thr: float) -> dict:
    sc, svi, wv = st["score"][TREND], st["svi"][SW], st["w"][VOL]
    with np.errstate(invalid="ignore"):
        lng = np.isfinite(sc) & np.isfinite(svi) & np.isfinite(wv) & (sc >= s_thr) & (svi >= v_thr)
    return dict(side=lng.astype(int), w=np.where(lng, wv, 0.0))


def trade_part(book, a: int, b: int) -> np.ndarray:
    """Per-trade window net4 contribution (same partition as Book.window part4)."""
    if not len(book.s):
        return np.zeros(0)
    legs = ((book.j0 >= a) & (book.j0 < b)).astype(float) + ((book.jx >= a) & (book.jx < b))
    fm = (book.f_min >= a) & (book.f_min < b)
    fund = np.bincount(book.f_tid[fm], book.f_cf[fm], minlength=len(book.s))
    return book.gross_upto(b) - book.gross_upto(a) + fund - 2 * book.w * legs


def top_share(part: np.ndarray, net: float, k: int) -> float:
    return float(np.sort(part)[::-1][:k].sum() / net) if net != 0 and len(part) else np.nan


def select(cm: pd.DataFrame) -> tuple[str, bool]:
    """DEV-only pick over the config table; returns (config_id, eligible_pool)."""
    el = cm[cm.dev_eligible]
    pool = el if len(el) else cm
    return pool.sort_values(["dev_score", "DEV-FULL_mdd", "config_id"], ascending=[False, True, True]).iloc[0].config_id, bool(len(el))


def dev_eligible(R: dict, prim: dict) -> bool:
    ok = all(R[(o, 0.5)][w]["long_net4"] > 0 for o in OFFSETS for w in ("DEV-A", "DEV-B"))
    return bool(ok and prim["DEV-FULL"]["long_closed"] >= 40 and prim["DEV-FULL"]["fill_notional_rate"] >= 0.10)


def test_success(R: dict, boot: dict) -> dict:
    f = {"cells_6of6": all(R[(o, p)]["TEST"]["long_net4"] > 0 for o in OFFSETS for p in PENS),
         "closed_ge30": R[PRIMARY]["TEST"]["long_closed"] >= 30,
         "boot_all_pos": all(boot[("TEST", bl)] > 0 for bl in BLOCKS)}
    return {**f, "SUCCESS": all(f.values())}


def run_cells(m, dec4, wb, sig: dict, side_only: bool):
    """6 exec cells; returns R[(off,pen)][window] (long book), primary long book, primary orders."""
    R, pb = {}, None
    for off in OFFSETS:
        for pen in PENS:
            tr, od = b2.simulate(m, "state", dec4, sig["side"], sig["w"], off, b2.TTL_TREND, pen, 0, m.N)
            book = b2.Book(m, tr, od, 0, m.N)
            bk = b3.side_books(m, book)["long"] if side_only else book
            ev = {k: bk.window(a, b) for k, (a, b) in wb.items()}
            if not side_only:
                assert all(abs(e["short_net4"]) < 1e-12 and e["short_closed"] == 0 for e in ev.values()), "long-only"
            else:   # side book keeps all orders; fill must come from long orders only
                for k, (a, b) in wb.items():
                    ev[k]["fill_notional_rate"] = b5.side_fill(od, a, b, 1)
            R[(off, pen)] = ev
            if (off, pen) == PRIMARY:
                pb = bk
    return R, pb


def config_row(c, R, pb, wb):
    row, boot = {"config_id": c}, {}
    daily = pb.daily(0, pb.m.N)
    for k, (a, b) in wb.items():
        e = R[PRIMARY][k]
        part = trade_part(pb, a, b)
        assert abs(part.sum() - e["long_net4"]) < 1e-6 * max(1, abs(e["long_net4"])), "trade partition"
        row.update({f"{k}_{x}": e[f"long_{x}"] for x in ("net4", "net8", "closed", "win", "entries")})
        row.update({f"{k}_mdd": e["mdd_1m"], f"{k}_sharpe": e["sharpe"], f"{k}_fill": e["fill_notional_rate"],
                    f"{k}_top1": top_share(part, e["long_net4"], 1), f"{k}_top3": top_share(part, e["long_net4"], 3)})
        for o in OFFSETS:
            for p in PENS:
                row[f"{k}_o{o}_p{p}"] = R[(o, p)][k]["long_net4"]
        for bl in BLOCKS:
            boot[(k, bl)] = b2.stationary_boot_p05(daily[a // 1440:b // 1440], bl)
            row[f"{k}_boot{bl}"] = boot[(k, bl)]
    return row, boot


def write_registry(cm: pd.DataFrame, parity: dict, pick: str, hashes: dict, run_id: str, path: Path = REGISTRY) -> dict:
    have = b2.registry_keys(path)
    ih = hashlib.sha256(canonical(hashes).encode()).hexdigest()
    added = skipped = 0
    base = {"run_id": run_id, "parent_run_id": PARENT, "data_cutoff": str(b2.END),
            "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()},
            "costs": "4 bps rt maker flat, 0 slip, PESS funding; 8 bps report-only", "hypothesis": "LONG-THRESH-BREADTH"}

    def put(key_obj, entry):
        nonlocal added, skipped
        key = hashlib.sha256(canonical({"batch": "LB", **key_obj, "inputs": ih}).encode()).hexdigest()
        if key in have:
            skipped += 1
            return
        registry.record(path, {**entry, "idempotency_key": key, "input_hashes": hashes})
        have.add(key)
        added += 1

    for r in cm.to_dict("records"):
        put({"config_id": r["config_id"]}, {
            "experiment": f"LB {r['config_id']}", "role": "trial", "config": {"config_id": r["config_id"], **base},
            "n_trials": 1, "n_simulations": 6, "selected": r["config_id"] == pick,
            "result_summary": {f"{w}_{x}": r[f"{w}_{x}"] for w in WINDOWS for x in ("net4", "net8", "closed")}})
    put({"parity": True}, {"experiment": "LB parity: Batch-5 LONG_DEV_PICK long sleeve re-run", "role": "control",
                           "config": base, "n_trials": 0, "n_simulations": 6, "result_summary": parity})
    return {"added": added, "skipped": skipped}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-registry", action="store_true")
    args = ap.parse_args(argv)
    t0 = time.time()
    code_hash = provenance.file_sha256(Path(__file__))
    run_id = f"LB-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{code_hash[:8]}"
    run_dir = OUT_BASE / run_id
    run_dir.mkdir(parents=True, exist_ok=False)          # write-once
    minutes, met, prem, funding = b2.load_all()
    m = b2.Market.from_frames(minutes, funding)
    del minutes, met, prem
    wb = b3.window_bounds(m)
    dec4 = np.arange(239, m.N, 240)
    st = b5.build_state(m, dec4)
    sigs = {cid(s, v): long_signal(st, s, v) for s, v in GRID}
    ref = b5.core_signal(st, B5_PICK)
    assert np.array_equal(sigs[cid(*BASE)]["side"] == 1, ref["side"] == 1), "baseline long decisions != Batch-5"
    for s, v in GRID:   # lower thresholds only add long decisions
        assert np.all(sigs[cid(s, v)]["side"] >= sigs[cid(*BASE)]["side"])
    pre = b5.prefix_checks(m, dec4, st, {c: (lambda st_, p: long_signal(st_, *p), p)
                                         for c, p in ((cid(*GRID[0]), GRID[0]), (cid(*BASE), BASE))})
    print(f"[state] {time.time()-t0:.0f}s prefix={pre}", flush=True)

    rows, boot_rows, R_all = [], [], {}
    for c, sg in sigs.items():
        R, pb = run_cells(m, dec4, wb, sg, False)
        R_all[c] = R
        row, boot = config_row(c, R, pb, wb)
        s, v = GRID[list(sigs).index(c)]
        row.update({"score_thr": s, "svi_thr": v, "long_decisions": int(sg["side"].sum()),
                    "dev_eligible": dev_eligible(R, R[PRIMARY]),
                    "dev_score": min(boot[(w, bl)] for w in ("DEV-A", "DEV-B") for bl in BLOCKS),
                    **{f"TEST_{k}": x for k, x in test_success(R, boot).items()}})
        rows.append(row)
        boot_rows += [{"config_id": c, "window": w, "block_days": bl, "p05_mean_day": x} for (w, bl), x in boot.items()]
        print(f"[sim] {c} {time.time()-t0:.0f}s", flush=True)
    cm = pd.DataFrame(rows)
    cm["DEV-FULL_mdd"] = cm["DEV-FULL_mdd"].astype(float)
    pick, elig_pool = select(cm)

    # parity: Batch-5 two-sided core_signal, long sleeve
    Rp, pbp = run_cells(m, dec4, wb, ref, True)
    prow, pboot = config_row("B5_LONG_DEV_PICK_long_sleeve", Rp, pbp, wb)
    prow.update({f"TEST_{k}": x for k, x in test_success(Rp, pboot).items()})
    got = {"DEV-FULL": prow["DEV-FULL_net4"], "TEST": prow["TEST_net4"], "TEST_closed": prow["TEST_closed"]}
    old = json.loads((PARENT_DIR / "selected_long.json").read_text(encoding="utf-8"))["LONG_DEV_PICK"]
    parity = {"got": got, "ref": B5_REF, "max_abs_diff_4dp": max(abs(got[k] - B5_REF[k]) for k in B5_REF),
              "cells_max_abs_diff_vs_b5": max(abs(Rp[(o, p)][w]["long_net4"] - old["cells_net4"][w][f"o{o}_p{p}"]["long"])
                                              for o in OFFSETS for p in PENS for w in WINDOWS),
              "boot_TEST_long_max_abs_diff_vs_b5": max(abs(pboot[("TEST", bl)] - x) for bl, x in
                                                       zip(BLOCKS, old["bootstrap_p05"]["TEST"]["long"]))}
    assert parity["max_abs_diff_4dp"] <= 5e-5 and parity["cells_max_abs_diff_vs_b5"] <= 1e-6, parity
    print(f"[parity] {parity}", flush=True)

    hashes = {"batch5_code": provenance.file_sha256(B5_PATH), "batch5_selected_long": provenance.file_sha256(
        PARENT_DIR / "selected_long.json"), **{k: v for k, v in b5.input_hashes().items() if k != "code"},
        "code": code_hash}
    cm.to_parquet(run_dir / "config_metrics.parquet", index=False)
    pd.DataFrame([prow]).to_parquet(run_dir / "parity_b5_long_sleeve.parquet", index=False)
    pd.DataFrame(boot_rows).to_parquet(run_dir / "bootstrap.parquet", index=False)
    pd.DataFrame([{"sim_id": f"{c}|offset={o}|pen={p}", "config_id": c, "offset": o, "pen_bps": p, "window": w,
                   **R_all[c][(o, p)][w]} for c in R_all for o in OFFSETS for p in PENS for w in WINDOWS]
                 ).to_parquet(run_dir / "fold_metrics.parquet", index=False)
    manifest = {"run_id": run_id, "parent_run_id": PARENT, "created_utc": datetime.now(timezone.utc).isoformat(),
                "spec": "scratchpad codex_b5_review.md 'next research: long tail' (Codex 01a124e0-8cc4-76b2-9038-1e5868334e7e)",
                "name": "LONG-THRESH-BREADTH", "interpretations": __doc__,
                "windows": {k: [str(a), str(b)] for k, (a, b) in WINDOWS.items()}, "data_cutoff": str(b2.END),
                "counts": {"logical": len(GRID), "sims": len(GRID) * 6, "n_trials": len(GRID), "parity_sims": 6},
                "pick": pick, "pick_label": "LB_DEV_PICK" if elig_pool else "LB_DEV_BEST_INELIGIBLE",
                "n_dev_eligible": int(cm.dev_eligible.sum()), "pick_TEST": cm.set_index("config_id").loc[pick, [
                    "TEST_cells_6of6", "TEST_closed_ge30", "TEST_boot_all_pos", "TEST_SUCCESS"]].to_dict(),
                "parity": parity, "prefix_checks": pre, "input_sha256": hashes, "git": b2.git_state(),
                "runtime_sec": round(time.time() - t0, 1)}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    if not args.no_registry:
        print(f"[registry] {write_registry(cm, parity, pick, hashes, run_id)}", flush=True)
    print(f"[done] {run_id} pick={pick} {time.time()-t0:.0f}s", flush=True)
    return run_dir


if __name__ == "__main__":
    main()
