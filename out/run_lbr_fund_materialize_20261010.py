"""LBR-FUND materialization (2026-10-10): targeted 1-config x 6-cell replay of the RESELECTED LBR candidate.

Review: scratchpad codex_lbr_review.md section 4 "다음 실험" steps 1-3 (Codex session 01a12542-8ad0-7a73-ad99-13f14da365d6).
Source run: LBR-20261010T094840Z-2a1bb573 (48 configs x 6 cells; DEV pick LBR-EITHER-b-0.5-d0.25-a2-h4 FAILED).
Candidate: LBR-FUND-b-1.0-d0.25-a1-h2 = (FUND, cut -1.0, delta 0.25, arm_bars 1, max_hold 2). It was RESELECTED after
TEST was seen: TEST is now selection evidence, not an independent confirmation.
Frozen semantics (step 1, no change without a separate experiment): the current LBR code as-is, i.e.
  * min_ztaker_since_arm = ztaker at the (latest) arm decision (arm-time ztaker; not a running minimum);
  * setup is checked before recovery: an ARMED decision that satisfies both setup and recovery re-arms.
Everything is reused unchanged via importlib from out/run_long_basis_release_20261010.py (lbr_signal, check_signal,
activation_counts) and through it the LCR runner (features, run_cells, pair_rows, window_metrics, parity_s180, ...).
G3 sleeves: G3_LONG = S180 long-only (G5-S180-c+0.0-W180-P65), G3_SHORT = short-only G5-F180-c+0.0-V-ENS
(btcusdt_quant/paper/g3.py sleeve_signal rule: other side flat). Portfolio = plain P&L sum, each sleeve <= 1x, gross <= 3.
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

LBR_PATH = ROOT / "out/run_long_basis_release_20261010.py"
_s = importlib.util.spec_from_file_location("lbr_base", LBR_PATH)
LB = importlib.util.module_from_spec(_s)
_s.loader.exec_module(LB)
L, b2, b5 = LB.L, LB.b2, LB.b5
SRC_RUN = "LBR-20261010T094840Z-2a1bb573"
SRC_DIR = LB.OUT_BASE / SRC_RUN
CAND = ("FUND", -1.0, 0.25, 1, 2)
CAND_ID = "LBR-FUND-b-1.0-d0.25-a1-h2"
SHORT_ID, SHORT_P = "G5-F180-c+0.0-V-ENS", dict(struct="F180", c=0.0, vol="V-ENS")
CELLS, PRIMARY, BLOCKS, ALLWIN, WINDOWS = L.CELLS, L.PRIMARY, L.BLOCKS, L.ALLWIN, L.WINDOWS
PRIM = L.cell_tag(*PRIMARY)
FOLD_COLS = ("net4", "net8", "gross", "funding", "entries", "closed", "open_n", "open_mtm", "win", "fill", "mdd",
             "sharpe", "exposure_days", "turnover")


def short_signal(st: dict) -> dict:
    ref = b5.core_signal(st, SHORT_P)
    side = np.where(ref["side"] == -1, -1, 0)
    return {"side": side, "w": np.where(side != 0, ref["w"], 0.0)}


def fold_parity(R: dict) -> dict:
    """Every (cell, window) fold value of the candidate equals the stored source-run fold_metrics row."""
    f = pd.read_parquet(SRC_DIR / "fold_metrics.parquet")
    f = f[f.config_id == CAND_ID].set_index(["offset", "pen", "window"])
    assert len(f) == len(CELLS) * len(ALLWIN)
    worst = 0.0
    for o, p in CELLS:
        for w in ALLWIN:
            e, r = R[(o, p)][w], f.loc[(o, p, w)]
            got = {"net4": e["long_net4"], "net8": e["long_net8"], "gross": e["long_gross"],
                   "funding": e["long_funding"], "entries": e["long_entries"], "closed": e["long_closed"],
                   "open_n": e["long_open_n"], "open_mtm": e["long_open_mtm"], "win": e["long_win"],
                   "fill": e["fill_notional_rate"], "mdd": e["mdd_1m"], "sharpe": e["sharpe"],
                   "exposure_days": e["long_exp_days"], "turnover": e["turnover"]}
            for k in FOLD_COLS:
                a, b = float(got[k]), float(r[k])
                if not (a != a and b != b):
                    worst = max(worst, abs(a - b))
    prim = {w: R[PRIMARY][w]["long_net4"] for w in ("TEST", "DEV-FULL")}
    out = {"rows": len(f), "max_abs_diff": worst, "primary_TEST_net4": prim["TEST"],
           "primary_DEV-FULL_net4": prim["DEV-FULL"]}
    assert worst == 0 and abs(prim["TEST"] - 1562.675) < 5e-4 and abs(prim["DEV-FULL"] - 1724.026) < 5e-4, out
    return out


def short_parity(R: dict, pb, wb: dict) -> dict:
    """Short-only re-simulation vs the Batch-5 SHORT_DEV_PICK short sleeve (cells, trades, daily)."""
    old = json.loads((L.PARENT_DIR / "selected_short.json").read_text(encoding="utf-8"))["SHORT_DEV_PICK"]
    assert old["config_id"] == SHORT_ID
    cells = max(abs(R[(o, p)][w]["short_net4"] - old["cells_net4"][w][f"o{o}_p{p}"]["short"])
                for o, p in CELLS for w in WINDOWS)
    ot = pd.read_parquet(L.PARENT_DIR / "trades/SHORT_DEV_PICK.parquet")
    ot = ot[ot.side < 0].reset_index(drop=True)
    cols = ["side", "entry_weight_frozen", "decision_idx", "entry_idx", "entry_px", "exit_idx", "exit_px",
            "open_at_end"]
    nt = pb.tr.reset_index(drop=True)
    tr_eq = len(ot) == len(nt) and all(np.array_equal(ot[c].to_numpy(), nt[c].to_numpy()) for c in cols)
    od = pd.read_parquet(L.PARENT_DIR / "daily/SHORT_DEV_PICK.parquet")
    dd = float(np.max(np.abs(od.net4_short.to_numpy() - pb.daily(0, pb.m.N))))
    return {"cells_max_abs_diff": cells, "trades_equal": bool(tr_eq), "n_trades": len(nt), "n_stored": len(ot),
            "daily_max_abs_diff": dd}


def port_rows(tag, books: dict, held: dict, wb: dict, primary: bool) -> list:
    """G3 (L+S) and G3+candidate portfolio rows per window."""
    rows = []
    for k, (a, b) in wb.items():
        for name, keys in (("G3", ("long", "short")), ("G3+CAND", ("long", "short", "cand"))):
            pnl = sum(books[x].pnl for x in keys)
            ps = b5.pnl_stats(pnl, a, b)
            d = pnl[a:b].reshape(-1, 1440).sum(1)
            gross = sum(held[x][a:b] for x in keys)
            r = {"cell": tag, "window": k, "book": name, "net4": float(pnl[a:b].sum()),
                 **{f"{x}_net4": float(books[x].pnl[a:b].sum()) for x in keys},
                 "mdd": ps["mdd_1m"], "sharpe": ps["sharpe"], "max_gross": float(gross.max(initial=0)),
                 **L.days_count(d)}
            if primary:
                r.update({f"boot{bl}": b2.stationary_boot_p05(d, bl) for bl in BLOCKS})
            if name == "G3+CAND":
                mc, ml, ms = held["cand"][a:b] > 0, held["long"][a:b] > 0, held["short"][a:b] > 0
                r.update(cand_long_overlap_min=int((mc & ml).sum()), cand_short_overlap_min=int((mc & ms).sum()),
                         cand_exposure_min=int(mc.sum()))
            rows.append(r)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-registry", action="store_true")
    args = ap.parse_args(argv)
    t0 = time.time()
    code_hash = provenance.file_sha256(Path(__file__))
    run_id = f"LBR-FUND-MAT-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{code_hash[:8]}"
    run_dir = LB.OUT_BASE / run_id
    run_dir.mkdir(parents=True, exist_ok=False)          # write-once
    (run_dir / "trades").mkdir()
    (run_dir / "daily").mkdir()
    assert LB.cid(CAND) == CAND_ID
    minutes, met, prem, funding = b2.load_all()
    m = b2.Market.from_frames(minutes, funding)
    del minutes
    wb_main = LB.b3.window_bounds(m)
    wb = {**wb_main, **{k: (m.idx(a), m.idx(b)) for k, (a, b) in L.SUBWIN.items()}}
    dec4 = np.arange(239, m.N, 240)
    st = b5.build_state(m, dec4)
    f = L.features(m, dec4, st, met, prem)
    bar = pd.to_datetime(m.t[dec4], utc=True)
    print(f"[feat] {time.time()-t0:.0f}s", flush=True)

    sg = LB.lbr_signal(f, CAND)
    ev = LB.check_signal(f, sg, CAND)
    ev["activations"] = LB.activation_counts(bar, sg["side"])
    src_man = json.loads((SRC_DIR / "manifest.json").read_text(encoding="utf-8"))
    ev_src = {k: v for k, v in src_man["event_counts"][CAND_ID].items()}
    assert ev == ev_src, (ev, ev_src)
    R, _, _ = L.run_cells(m, dec4, wb, sg)
    fpar = fold_parity(R)
    s_sig = L.s180_signal(st)
    sR, s_pb, _ = L.run_cells(m, dec4, wb, s_sig)
    par_s180 = L.parity_s180(sR, s_pb, wb_main)
    h_sig = short_signal(st)
    print(f"[parity] fold {fpar} s180 {par_s180} {time.time()-t0:.0f}s", flush=True)

    days = pd.date_range(b2.START, periods=m.N // 1440, freq="D")
    wm_rows, corr_rows, comb_rows, mon_rows, port, boot = [], [], [], [], [], []
    shR, h_pb, fund_hand = {}, None, None
    for o, p in CELLS:
        tag = L.cell_tag(o, p)
        books, trs = {}, {}
        for key, sig in (("cand", sg), ("long", s_sig), ("short", h_sig)):
            tr, od = b2.simulate(m, "state", dec4, sig["side"], sig["w"], o, b2.TTL_TREND, p, 0, m.N)
            books[key], trs[key] = b2.Book(m, tr, od, 0, m.N), tr
        nb, sb, hb = books["cand"], books["long"], books["short"]
        shR[(o, p)] = {w: hb.window(*wb[w]) for w in WINDOWS}
        if (o, p) == PRIMARY:
            h_pb = hb
        for w in ALLWIN:
            assert L.same(nb.window(*wb[w]), R[(o, p)][w]), "re-simulation != first pass"
        held = {k: L.held_minutes(bk) for k, bk in books.items()}
        for k, h in held.items():
            assert h.max(initial=0) <= 1 + 1e-12, f"{k} weight > 1"
        cnt = np.zeros(m.N + 1, int)
        np.add.at(cnt, nb.j0, 1)
        np.add.at(cnt, np.where(nb.closed, nb.j1 + 1, m.N), -1)
        assert np.cumsum(cnt).max(initial=0) <= 1, "more than one position"
        cr, cb = L.pair_rows(CAND_ID, tag, nb, sb, held["cand"], held["long"], wb)
        corr_rows += cr
        comb_rows += cb
        port += port_rows(tag, books, held, wb, (o, p) == PRIMARY)
        dn, ds, dh = nb.daily(0, m.N), sb.daily(0, m.N), hb.daily(0, m.N)
        pd.DataFrame({"day": days, "cand_net4": dn, "s180_net4": ds, "short_net4": dh, "combined_long_net4": dn + ds,
                      "g3_net4": ds + dh, "portfolio_net4": dn + ds + dh, "cand_held": nb.held_day,
                      "s180_held": sb.held_day, "short_held": hb.held_day}).to_parquet(
            run_dir / f"daily/CAND_{tag}.parquet", index=False)
        t2 = trs["cand"].assign(config_id=CAND_ID, cell=tag, net4_full=nb.net4_full, gross_full=nb.gross_full,
                                funding_full=nb.fund_full)
        t2["decision_time"] = pd.to_datetime(m.t[t2.decision_idx], utc=True)
        t2["entry_time"] = pd.to_datetime(m.t[t2.entry_idx], utc=True)
        t2["exit_time"] = pd.to_datetime(np.where(t2.exit_idx >= 0, m.t[np.maximum(t2.exit_idx, 0)],
                                                  np.iinfo(np.int64).min), utc=True)
        t2.to_parquet(run_dir / f"trades/CAND_{tag}.parquet", index=False)
        for w, (a, b) in wb.items():
            r = {"config_id": CAND_ID, "cell": tag, "window": w,
                 **L.window_metrics(nb.window(a, b), nb.daily(a, b), L.trade_part(nb, a, b))}
            if (o, p) == PRIMARY:
                for bl in BLOCKS:
                    r[f"boot{bl}"] = b2.stationary_boot_p05(nb.daily(a, b), bl)
                    boot.append({"window": w, "scope": "cand_primary", "block_days": bl, "p05_mean_day": r[f"boot{bl}"]})
            wm_rows.append(r)
        mon = pd.DataFrame({"m": days.strftime("%Y-%m"), "n": dn, "s": ds, "h": dh}).groupby("m").sum()
        mon_rows += [{"cell": tag, "month": k, "cand_net4": x.n, "s180_net4": x.s, "short_net4": x.h,
                      "combined_long_net4": x.n + x.s, "portfolio_net4": x.n + x.s + x.h} for k, x in mon.iterrows()]
        if (o, p) == PRIMARY:
            fund_hand = L.funding_hand_check(m, nb)
            assert fund_hand < 1e-9, f"funding hand parity {fund_hand}"
        print(f"[cell] {tag} {time.time()-t0:.0f}s", flush=True)
    sh_par = short_parity(shR, h_pb, wb_main)
    wm, co, comb, mon, pf = (pd.DataFrame(x) for x in (wm_rows, corr_rows, comb_rows, mon_rows, port))
    for cb in comb_rows:
        if cb["cell"] == PRIM:
            boot += [{"window": cb["window"], "scope": sc, "block_days": bl, "p05_mean_day": cb[f"{pre}boot{bl}"]}
                     for bl in BLOCKS for sc, pre in (("combined_long_primary", ""), ("s180_primary", "s180_"))]
    for r in port:
        if r["cell"] == PRIM:
            boot += [{"window": r["window"], "scope": f"{r['book']}_primary", "block_days": bl,
                      "p05_mean_day": r[f"boot{bl}"]} for bl in BLOCKS]

    cell_pos = lambda w: all(R[cl][w]["long_net4"] > 0 for cl in CELLS)  # noqa: E731
    pw = {r["window"]: r for r in L.co_rows_primary(corr_rows)}
    cw = L.COMP_WIN
    pcand = wm[(wm.cell == PRIM)].set_index("window")
    flags = {"DEV-A_6of6": cell_pos("DEV-A"), "DEV-B_6of6": cell_pos("DEV-B"), "TEST_6of6": cell_pos("TEST"),
             "TEST_boot_all_pos": bool(all(pcand.loc["TEST", f"boot{bl}"] > 0 for bl in BLOCKS))}
    cflags = {"JanJul_6of6": cell_pos(cw), "JanJul_comb_pos_days": int(pw[cw]["comb_pos_days"]),
              "JanJul_s180_pos_days": int(pw[cw]["s180_pos_days"]),
              "JanJul_comb_pos_days_gt_s180": bool(pw[cw]["comb_pos_days"] > pw[cw]["s180_pos_days"])}
    decision = {"candidate": CAND_ID, **flags, "PASS_rule_values": all(flags.values()), **cflags,
                "COMPLEMENT_PASS": bool(cflags["JanJul_6of6"] and cflags["JanJul_comb_pos_days_gt_s180"]),
                "caveat": "candidate RESELECTED after TEST was seen; TEST/sub-window values are selection evidence, "
                          "not out-of-sample confirmation", "promotion": "paper-only shadow at most; never live"}
    sel_note = {"source_run": SRC_RUN, "source_dev_pick": src_man["pick"],
                "source_decision": json.loads((SRC_DIR / "decision.json").read_text(encoding="utf-8")),
                "reselected": CAND_ID, "reselection_basis": "TEST results of the 48-config source grid (TEST worst "
                "cell / TEST net4 / TEST bootstrap), after the DEV pick failed PASS",
                "test_used_for_selection": True, "test_is_independent_confirmation": False,
                "reselection_recorded_utc": datetime.now(timezone.utc).isoformat()}
    hashes = {"lbr_code": provenance.file_sha256(LBR_PATH), "lcr_code": provenance.file_sha256(LB.LCR_PATH),
              "batch5_code": provenance.file_sha256(L.B5_PATH), "batch2_code": provenance.file_sha256(L.B2_PATH),
              **{f"src_{n}": provenance.file_sha256(SRC_DIR / n) for n in
                 ("manifest.json", "decision.json", "selection.json", "fold_metrics.parquet", "config_metrics.parquet")},
              "batch5_selected_long": provenance.file_sha256(L.PARENT_DIR / "selected_long.json"),
              "batch5_selected_short": provenance.file_sha256(L.PARENT_DIR / "selected_short.json"),
              "batch5_trades_short": provenance.file_sha256(L.PARENT_DIR / "trades/SHORT_DEV_PICK.parquet"),
              "batch5_daily_short": provenance.file_sha256(L.PARENT_DIR / "daily/SHORT_DEV_PICK.parquet"),
              **{k: v for k, v in b5.input_hashes().items() if k != "code"}, "code": code_hash}

    wm.to_parquet(run_dir / "cand_window_metrics.parquet", index=False)
    co.to_parquet(run_dir / "correlation_overlap.parquet", index=False)
    comb.to_parquet(run_dir / "combined_long_metrics.parquet", index=False)
    mon.to_parquet(run_dir / "monthly.parquet", index=False)
    pf.to_parquet(run_dir / "portfolio_metrics.parquet", index=False)
    pd.DataFrame(boot).to_parquet(run_dir / "bootstrap.parquet", index=False)
    (run_dir / "decision.json").write_text(json.dumps(decision, indent=2, default=str), encoding="utf-8")
    man = {"run_id": run_id, "role": "materialize", "created_utc": datetime.now(timezone.utc).isoformat(),
           "review": "scratchpad codex_lbr_review.md section 4 steps 1-3 (Codex 01a12542-8ad0-7a73-ad99-13f14da365d6)",
           "frozen_semantics": {"min_ztaker": "arm-time ztaker (ztaker at latest arm decision; not running min)",
                                "order": "setup checked before recovery; ARMED + setup re-arms",
                                "rule": "no semantic change without a separate experiment",
                                "source_doc": __doc__},
           "selection": sel_note, "candidate": CAND_ID,
           "candidate_params": dict(zip(("basis_mode", "basis_cut", "recovery_delta", "arm_bars", "max_hold_bars"),
                                        CAND)),
           "comparators": {"G3_LONG": L.S180_ID, "G3_SHORT": SHORT_ID},
           "source": "Binance USD-M BTCUSDT local: artifacts DEV (<2026-01-01) + r2_54 stageb_snapshot TEST",
           "data_cutoff": str(b2.END), "windows": {k: [str(a), str(b)] for k, (a, b) in ALLWIN.items()},
           "counts": {"logical": 1, "cells": len(CELLS), "n_trials": 0}, "event_counts": ev,
           "parity": {"fold_vs_source": fpar, "events_vs_source": True, "s180": par_s180, "short": sh_par},
           "funding_hand_check_max_abs": fund_hand, "decision": decision,
           "max_gross": {"G3+CAND": float(pf[pf.book == "G3+CAND"].max_gross.max()),
                         "G3": float(pf[pf.book == "G3"].max_gross.max())},
           "input_sha256": hashes, "git": b2.git_state(), "runtime_sec": round(time.time() - t0, 1)}
    if not args.no_registry:
        key = hashlib.sha256(canonical({"batch": "LBR-FUND-MAT", "cand": CAND_ID, "inputs": hashlib.sha256(
            canonical(hashes).encode()).hexdigest()}).encode()).hexdigest()
        prim_rows = pf[(pf.cell == PRIM) & (pf.window.isin(list(WINDOWS)))]
        registry.record(L.REGISTRY, {
            "run_id": run_id, "experiment": f"LBR-FUND-MAT {CAND_ID}", "role": "materialize", "n_trials": 0,
            "n_simulations": 0, "idempotency_key": key, "input_hashes": hashes,
            "config": {"candidate": CAND_ID, "source_run": SRC_RUN, "data_cutoff": str(b2.END),
                       "test_used_for_selection": True, "frozen_semantics": "arm-time ztaker + setup-before-recovery"},
            "result_summary": {**{f"cand_{w}_net4": R[PRIMARY][w]["long_net4"] for w in WINDOWS},
                               **{f"{r.book}_{r.window}_net4": r.net4 for r in prim_rows.itertuples()},
                               "COMPLEMENT_PASS": decision["COMPLEMENT_PASS"]}})
        man["registry"] = {"added": 1, "idempotency_key": key}
    (run_dir / "manifest.json").write_text(json.dumps(man, indent=2, default=str), encoding="utf-8")
    print(f"[done] {run_id} {man['runtime_sec']}s", flush=True)
    return run_dir


if __name__ == "__main__":
    main()
