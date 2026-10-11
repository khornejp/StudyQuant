"""RL allocator steps 1-2 (Codex design .superpowers/sdd/rl_allocator/codex_design_2026-10-10.md, sections 1/6/8).

  freeze      write out/rl_allocator_20261010/freeze.json (write-once): source, timestamp, cutoff, hypothesis,
              7 sleeves with source run ids + file hashes, exec cells, action space, cap, folds, TEST guard.
  precompute  regenerate every sleeve with its unchanged source engine (importlib, no edits), decompose the source
              ledger into per-opportunity minute rows (btcusdt_quant/rl/sleeve_precompute.py), check parity
              (reported numbers, trades, minute ledger, all-off, prefix/future tamper, 100 random counterfactual
              control paths per sleeve-cell vs a direct recompute), then write year-partitioned outputs.
              Any parity failure aborts before outputs/registry are written.

TEST rows are read here only for integrity parity (explicit allow_test); nothing is fitted or selected.
Usage: venv_btcusdt\\Scripts\\python.exe scripts\\precompute_rl_allocator.py freeze|precompute [--paths 100]
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, math, subprocess, sys, time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from btcusdt_quant.rl import sleeve_precompute as sp  # noqa: E402
from btcusdt_quant.sim import provenance, registry  # noqa: E402

OUT = ROOT / "out/rl_allocator_20261010"
FREEZE = OUT / "freeze.json"
PRE = OUT / "precompute"
REGISTRY = ROOT / "out/sim_registry.jsonl"
DESIGN = ROOT / ".superpowers/sdd/rl_allocator/codex_design_2026-10-10.md"
NM_B5 = ROOT / "out/new_model_batch5_20261010/NM-B5-20261010T080025Z-c55285f2"
LBR_SRC = ROOT / "out/long_basis_release_20261010/LBR-20261010T094840Z-2a1bb573"
LBR_MAT = ROOT / "out/long_basis_release_20261010/LBR-FUND-MAT-20261010T101154Z-407303fe"
R256 = ROOT / "out/k45_rl_r2_48_20261007/r2_56"
CELLS = [(2, 0.5), (2, 1.0), (2, 2.0), (5, 0.5), (5, 1.0), (5, 2.0)]
CELL_TAG = {c: f"o{c[0]}_p{c[1]}" for c in CELLS}
PRIMARY = (2, 0.5)
SLEEVES = ("G3_LONG", "G3_SHORT", "LBR_FUND", "B3_AXC0", "K04_AXC0", "C1v2", "C4v2")
SLEEVE_ID = {s: i for i, s in enumerate(SLEEVES)}
G3_FAMILY = ("G3_LONG", "G3_SHORT", "LBR_FUND")
NATIVE = ("B3_AXC0", "K04_AXC0", "C1v2", "C4v2")
SEED = 20261010
ATOL_MIN, ATOL_TOT = 1e-9, 1e-6
REF = {  # design section 6 parity numbers (primary cell / native)
    ("G3_LONG", "DEV-FULL"): 22996.226652, ("G3_SHORT", "DEV-FULL"): 5787.747466,
    ("G3_LONG", "TEST"): 1684.115630, ("G3_SHORT", "TEST"): 1614.933205,
    ("LBR_FUND", "DEV-FULL"): 1724.025589, ("LBR_FUND", "TEST"): 1562.674997,
    ("B3_AXC0", "TEST"): 2347.842552, ("K04_AXC0", "TEST"): 2587.292720,
    ("C1v2", "TEST"): 4809.605689, ("C4v2", "TEST"): 5467.390927}
SOURCE_CODE = ["out/run_new_model_batch1_20261010.py", "out/run_new_model_batch2_20261010.py",
               "out/run_new_model_batch3_20261010.py", "out/run_new_model_batch4_20261010.py",
               "out/run_new_model_batch5_20261010.py", "out/run_long_cap_recovery_20261010.py",
               "out/run_long_basis_release_20261010.py", "out/run_lbr_fund_materialize_20261010.py",
               "scripts/sim_r2_55.py", "scripts/sim_r2_56_replay.py", "scripts/sim_r2_56_fix1.py",
               "scripts/sim_adaptive_exit.py", "btcusdt_quant/sim/core.py", "btcusdt_quant/sim/reference.py",
               "btcusdt_quant/sim/costs.py", "btcusdt_quant/sim/strategies/legacy.py",
               "out/run_k45_decision_cadence_r2_37.py", "out/k45_funding.py"]
T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - T0:7.0f}s] {msg}", flush=True)


def sha(p: Path) -> str:
    return provenance.file_sha256(p)


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def load(name: str, rel: str):
    s = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(s)
    sys.modules[name] = mod
    s.loader.exec_module(mod)
    return mod


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")


# ================================================================ step 1: freeze
def freeze_doc() -> dict:
    files = {
        "design": DESIGN,
        "nm_b5_manifest": NM_B5 / "manifest.json", "nm_b5_selected_long": NM_B5 / "selected_long.json",
        "nm_b5_selected_short": NM_B5 / "selected_short.json",
        "nm_b5_trades_long": NM_B5 / "trades/LONG_DEV_PICK.parquet",
        "nm_b5_trades_short": NM_B5 / "trades/SHORT_DEV_PICK.parquet",
        "lbr_src_manifest": LBR_SRC / "manifest.json", "lbr_src_fold_metrics": LBR_SRC / "fold_metrics.parquet",
        "lbr_mat_manifest": LBR_MAT / "manifest.json", "lbr_mat_portfolio_metrics": LBR_MAT / "portfolio_metrics.parquet",
        **{f"lbr_mat_trades_{CELL_TAG[c]}": LBR_MAT / f"trades/CAND_{CELL_TAG[c]}.parquet" for c in CELLS},
        **{f"lbr_mat_daily_{CELL_TAG[c]}": LBR_MAT / f"daily/CAND_{CELL_TAG[c]}.parquet" for c in CELLS},
        "r2_56_report": R256 / "report.json", "r2_56_report_r0": R256 / "report_r0.json",
        "r2_56_B3_positions": R256 / "B3_AXC0_positions_2026.parquet",
        "r2_56_K04_positions": R256 / "K04_AXC0_positions_2026.parquet",
        "r2_56_C1v2_trades": R256 / "C1v2_trades_2020_2026.parquet",
        "r2_56_C4v2_trades": R256 / "C4v2_trades_2020_2026.parquet",
        "r2_55_selected_k": ROOT / "out/k45_rl_r2_48_20261007/r2_55/selection/selected_k.csv",
        "r2_55_freeze": ROOT / "out/k45_rl_r2_48_20261007/r2_55_k0607_c0_freeze.json",
        "stageb_snapshot_manifest": ROOT / "out/k45_rl_r2_48_20261007/r2_54/stageb_snapshot/manifest.json",
        **{f"code:{p}": ROOT / p for p in SOURCE_CODE}}
    hashes = {k: {"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(p)} for k, p in files.items()}
    g3_head = subprocess.run(["git", "show", "HEAD:btcusdt_quant/paper/g3.py"], cwd=ROOT, capture_output=True).stdout
    g3_cell = {"cells": [CELL_TAG[c] for c in CELLS], "primary": CELL_TAG[PRIMARY],
               "offset_bps": [2, 5], "penetration_bps": [0.5, 1.0, 2.0], "ttl_min": 60, "exit_quote_bps": 2,
               "requote_min": 60, "cost_bps_rt": 4, "slippage": 0}
    sleeves = {
        "G3_LONG": {"config_id": "G5-S180-c+0.0-W180-P65", "side": "long only (short targets -> flat)",
                    "source_run": NM_B5.name, "materialized_in": LBR_MAT.name, "exec": "G3 6 cells",
                    "ledger": "lin (Batch-2 Book)", "selection": "NM-B5 LONG_DEV_PICK (DEV-only)",
                    "test_selected": False},
        "G3_SHORT": {"config_id": "G5-F180-c+0.0-V-ENS", "side": "short only (long targets -> flat)",
                     "source_run": NM_B5.name, "materialized_in": LBR_MAT.name, "exec": "G3 6 cells",
                     "ledger": "lin (Batch-2 Book)", "selection": "NM-B5 SHORT_DEV_PICK (DEV-only)",
                     "test_selected": False},
        "LBR_FUND": {"config_id": "LBR-FUND-b-1.0-d0.25-a1-h2", "params": {"basis_mode": "FUND", "basis_cut": -1.0,
                     "recovery_delta": 0.25, "arm_bars": 1, "max_hold_bars": 2}, "side": "long",
                     "source_run": LBR_SRC.name, "materialized_in": LBR_MAT.name, "exec": "G3 6 cells",
                     "ledger": "lin (Batch-2 Book)", "test_selected": True,
                     "flag": "RESELECTED after TEST was seen (LBR-FUND-MAT manifest): TEST is selection evidence"},
        "B3_AXC0": {"id": "B3", "variant": "AXC0 R2-52A adaptive exit, causal_guard=True",
                    "source_run": "R2-56 (scripts/sim_r2_56_replay.py axc0_runs; R2-55 W10 k)",
                    "exec": "native core fill (delay 1, market at open / OCO stop, 2 bps per side)",
                    "ledger": "log (sim core)", "available": "2023-09-01..2025-12-31 native rolling-k, "
                    "2026-01-01..2026-10-07 TEST (flat start)", "test_selected": False,
                    "flag": "R2-55 k chosen on pre-2026; AXC0 family repair fixed before the 2026 replay"},
        "K04_AXC0": {"id": "K04", "variant": "AXC0 R2-52A adaptive exit, causal_guard=True",
                     "source_run": "R2-56 (scripts/sim_r2_56_replay.py axc0_runs; R2-55 W10 k)",
                     "exec": "native core fill", "ledger": "log (sim core)",
                     "available": "same as B3_AXC0", "test_selected": False},
        "C1v2": {"spec": "C1 F_V5+E_V1a (F3/V5 + E1/V1a, single book FIRST)", "source_run": "R2-56 fix1",
                 "exec": "native R2-37 fill at decision-minute open, 4 bps rt", "ledger": "log (R2-37 fast_ledger)",
                 "test_selected": True, "flag": "v2 = single-delay LS rerun adopted after the 2026 TEST "
                 "(round-0) results were seen; TEST is not independent"},
        "C4v2": {"spec": "C4 F_V0+E_V1a (F3-w30/V0 + E1/V1a, single book FIRST)", "source_run": "R2-56 fix1",
                 "exec": "native R2-37 fill", "ledger": "log (R2-37 fast_ledger)", "test_selected": True,
                 "flag": "same as C1v2"}}
    return {
        "name": "RL allocator contract freeze (steps 1-2)", "status": "FROZEN",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "design": {"path": str(DESIGN.relative_to(ROOT)), "codex_session": "01a12553-57cf-7101-8be4-52c53c397d28",
                   "sections": "1, 6, 8 steps 1-2"},
        "source": "Binance USD-M BTCUSDT futures, local only: artifacts DEV (< 2026-01-01) + R2-54 FINAL "
                  "stageb_snapshot (2026-01-01..2026-10-07); no spot/DEX; public data only",
        "data_cutoff": "2026-10-08 00:00:00+00:00 (exclusive)",
        "frozen_hypothesis": "[가설] A 7-sleeve allocator choosing a per-opportunity multiplier {0,.25,.5,.75,1} "
                             "and HOLD/EXIT (TIGHTEN for R0 sleeves) at a 1h cadence beats the frozen static "
                             "DEV-best allocation after 4 bps maker round trip in every DEV fold and every exec "
                             "cell; 4h is an ablation. Edge comes from the sleeves; the allocator only sizes/exits.",
        "sleeves": sleeves, "sleeve_ids": SLEEVE_ID,
        "test_selected_sleeves": [s for s, v in sleeves.items() if v["test_selected"]],
        "exec_cells": {"G3_family (G3_LONG, G3_SHORT, LBR_FUND)": g3_cell,
                       "native (B3_AXC0, K04_AXC0, C1v2, C4v2)": "native fill contract of each source, one cell"},
        "costs": "maker 4 bps round trip flat, slippage 0, PESS funding; 8 bps report-only, never a gate",
        "action_space": {
            "new_opportunity": ["OFF", 0.25, 0.50, 0.75, 1.00], "pending": ["KEEP", "CANCEL"],
            "open": {"B3_AXC0/K04_AXC0": ["HOLD", "TIGHTEN_75", "TIGHTEN_50", "EXIT"],
                     "G3_LONG/G3_SHORT/LBR_FUND/C1v2/C4v2": ["HOLD", "EXIT"]},
            "rules": ["allocation fixed from entry to exit; no increase while open",
                      "base mandatory exit / stop / trail never cancelled",
                      "TIGHTEN: R_t = min(R_t, 0.75 R0 or 0.50 R0); no widening",
                      "early EXIT: next allowed maker exit (G3-family: 2 bps quote, 60m requote, cell penetration; "
                      "native: next-minute open), 2 bps per side, slippage 0",
                      "allocation only at canonical entry opportunities; canonical shadow schedule fixed; "
                      "skip or early exit -> no re-entry until the canonical trade ends"]},
        "constraints": {"multiplier": [0, 1], "exposure": "multiplier x base_weight", "gross_cap": 2.0,
                        "cap_projection": "existing open exposure first; simultaneous new entries scaled "
                                          "proportionally to the remaining cap",
                        "books": "long/short separate virtual books, no netting; net exposure reported"},
        "cadence": {"primary": "1h", "ablation": "4h"},
        "folds": {"F1": {"train": ["2020-01-01", "2021-01-01"], "val": ["2021-01-01", "2022-01-01"]},
                  "F2": {"train": ["2020-01-01", "2022-01-01"], "val": ["2022-01-01", "2023-01-01"]},
                  "F3": {"train": ["2020-01-01", "2023-01-01"], "val": ["2023-01-01", "2024-01-01"]},
                  "F4": {"train": ["2020-01-01", "2024-01-01"], "val": ["2024-01-01", "2025-01-01"]},
                  "F5": {"train": ["2020-01-01", "2025-01-01"], "val": ["2025-01-01", "2026-01-01"]}},
        "test": {"window": ["2026-01-01", "2026-10-08"], "guard": "btcusdt_quant.rl.sleeve_precompute."
                 "guard_times/read_partitioned raise TestAccessError on rows >= 2026-01-01 unless allow_test=True",
                 "allowed_use_before_unlock": "precompute integrity parity only (no fit, no selection)"},
        "source_hashes": hashes,
        "g3_definition": {"path": "btcusdt_quant/paper/g3.py", "head_sha256": hashlib.sha256(g3_head).hexdigest(),
                          "note": "reference only (not imported); working tree is being edited by another agent"},
        "git": {"head": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD")}}


def cmd_freeze(_args) -> None:
    if FREEZE.exists():
        raise SystemExit(f"{FREEZE} exists (write-once)")
    dump(FREEZE, freeze_doc())
    log(f"freeze written sha256 {sha(FREEZE)}")


def check_freeze() -> dict:
    f = json.loads(FREEZE.read_text(encoding="utf-8"))
    bad = sorted(k for k, v in f["source_hashes"].items() if sha(ROOT / v["path"]) != v["sha256"])
    if bad:
        raise SystemExit(f"freeze hash mismatch: {bad}")
    return f


# ================================================================ helpers
class Fail(Exception):
    pass


def need(ok: bool, what: str, rec: dict) -> None:
    rec.setdefault("checks", []).append({"check": what, "pass": bool(ok)})
    if not ok:
        raise Fail(what)


def window_sum(x: np.ndarray, t: np.ndarray, a, b) -> float:
    lo, hi = np.searchsorted(t, pd.Timestamp(a).value), np.searchsorted(t, pd.Timestamp(b).value)
    return float(x[lo:hi].sum())


WIN = {"DEV-FULL": ("2020-01-01", "2026-01-01"), "TEST": ("2026-01-01", "2026-10-08")}


def hour_choices(t: np.ndarray, lo: int, hi: int) -> np.ndarray:
    """Hour-aligned minutes in [lo, hi]."""
    if hi < lo:
        return np.zeros(0, np.int64)
    idx = np.arange(lo, hi + 1)
    return idx[(t[idx] % (60 * sp.MIN)) == 0]


# ================================================================ G3 family
def g3_family(args, rec: dict) -> dict:
    MAT = load("lbr_mat", "out/run_lbr_fund_materialize_20261010.py")
    LB, L, b2, b4, b5 = MAT.LB, MAT.L, MAT.b2, MAT.LB.b4, MAT.b5
    minutes, met, prem, funding = b2.load_all()
    m = b2.Market.from_frames(minutes, funding)
    del minutes
    dec4 = np.arange(239, m.N, 240)
    st = b5.build_state(m, dec4)
    f = L.features(m, dec4, st, met, prem)
    sigs = {"G3_LONG": L.s180_signal(st), "G3_SHORT": MAT.short_signal(st), "LBR_FUND": LB.lbr_signal(f, MAT.CAND)}
    log(f"G3 family inputs N={m.N} dec4={len(dec4)}")
    mk = {"t": m.t, "o": m.o, "h": m.h, "l": m.l, "c": m.c}
    port = pd.read_parquet(LBR_MAT / "portfolio_metrics.parquet")
    port = port[port.book == "G3+CAND"].set_index(["cell", "window"])
    col = {"G3_LONG": "long_net4", "G3_SHORT": "short_net4", "LBR_FUND": "cand_net4"}
    dcol = {"G3_LONG": "s180_net4", "G3_SHORT": "short_net4", "LBR_FUND": "cand_net4"}
    out = {}
    for s in G3_FAMILY:
        sig = sigs[s]
        for cell in CELLS:
            tag = CELL_TAG[cell]
            r = rec.setdefault(f"{s}|{tag}", {})
            tr, od = b2.simulate(m, "state", dec4, sig["side"], sig["w"], cell[0], b2.TTL_TREND, cell[1], 0, m.N)
            bk = b2.Book(m, tr, od, 0, m.N)
            tr = tr.reset_index(drop=True).assign(tid=np.arange(len(tr)))
            rows = sp.lin_rows(m.t, m.c, tr, m.N, m.ft, m.fr)
            net = sp.minute_sum(rows, m.N)
            r["minute_max_abs_vs_source_book"] = float(np.abs(net - bk.pnl).max())
            need(r["minute_max_abs_vs_source_book"] <= ATOL_MIN, f"{s} {tag} minute ledger vs Book", r)
            for w, (a, b) in WIN.items():
                got = window_sum(net, m.t, a, b)
                ref = float(port.loc[(tag, w), col[s]])
                r[f"{w}_net4"], r[f"{w}_ref"] = got, ref
                need(abs(got - ref) <= ATOL_TOT, f"{s} {tag} {w} net4 vs LBR-FUND-MAT portfolio", r)
                if cell == PRIMARY:
                    r[f"{w}_design_ref"] = REF[(s, w)]
                    need(abs(got - REF[(s, w)]) <= 5e-6, f"{s} {w} vs design 6dp", r)
            dd = pd.read_parquet(LBR_MAT / f"daily/CAND_{tag}.parquet")[dcol[s]].to_numpy()
            r["daily_max_abs_vs_stored"] = float(np.abs(net.reshape(-1, 1440).sum(1) - dd).max())
            need(r["daily_max_abs_vs_stored"] <= 1e-9, f"{s} {tag} daily vs stored", r)
            r["trades"], r["orders"], r["fills"] = int(len(tr)), int(len(od)), int(od.filled.sum())
            r["closed"], r["open_at_end"] = int((~tr.open_at_end).sum()), int(tr.open_at_end.sum())
            need(r["fills"] == r["trades"], f"{s} {tag} fills == trades", r)
            cols = ["side", "entry_weight_frozen", "decision_idx", "entry_idx", "entry_px", "exit_decision_idx",
                    "exit_idx", "exit_px", "open_at_end"]
            if s == "LBR_FUND":
                ref_tr = pd.read_parquet(LBR_MAT / f"trades/CAND_{tag}.parquet")
            elif cell == PRIMARY:
                ref_tr = pd.read_parquet(NM_B5 / f"trades/{'LONG' if s == 'G3_LONG' else 'SHORT'}_DEV_PICK.parquet")
                ref_tr = ref_tr[np.sign(ref_tr.side) == (1 if s == "G3_LONG" else -1)]
            else:
                ref_tr = None
            if ref_tr is not None:
                ref_tr = ref_tr.reset_index(drop=True)
                eq = len(ref_tr) == len(tr) and all(np.array_equal(ref_tr[c].to_numpy(), tr[c].to_numpy(),
                                                                   equal_nan=True) for c in cols)
                r["trades_equal_stored"], r["stored_trades"] = bool(eq), int(len(ref_tr))
                need(eq, f"{s} {tag} trades == stored", r)
            out[(s, tag)] = dict(tr=tr, od=od, rows=rows, net=net, sig=sig, pen=cell[1])
        log(f"{s} 6 cells parity ok")
    # prefix / future tamper (primary cell, cut 2026-01-01)
    cut = b5.CUT
    ci = int(np.searchsorted(m.t, cut.value))
    mt, met2, prem2 = L.tamper_inputs(m, met, prem, cut)
    stt = b5.build_state(mt, dec4)
    ft_ = L.features(mt, dec4, stt, met2, prem2)
    mp = b4.prefix_market(m, cut)
    dp = dec4[dec4 < mp.N]
    stp = b5.build_state(mp, dp)
    fp = L.features(mp, dp, stp, met[met.available_time.array.asi8 <= cut.value].reset_index(drop=True),
                    prem[prem.available_time.array.asi8 <= cut.value].reset_index(drop=True))
    tamp_sig = {"G3_LONG": L.s180_signal(stt), "G3_SHORT": MAT.short_signal(stt), "LBR_FUND": LB.lbr_signal(ft_, MAT.CAND)}
    pre_sig = {"G3_LONG": L.s180_signal(stp), "G3_SHORT": MAT.short_signal(stp), "LBR_FUND": LB.lbr_signal(fp, MAT.CAND)}
    for s in G3_FAMILY:
        r = rec[f"{s}|{CELL_TAG[PRIMARY]}"]
        base = out[(s, CELL_TAG[PRIMARY])]["rows"]
        for tag_, mm, sg, dd_, lim in (("tamper", mt, tamp_sig[s], dec4, ci), ("prefix", mp, pre_sig[s], dp, ci - 1)):
            tr2, _ = b2.simulate(mm, "state", dd_, sg["side"], sg["w"], PRIMARY[0], b2.TTL_TREND, PRIMARY[1], 0, mm.N)
            tr2 = tr2.reset_index(drop=True).assign(tid=np.arange(len(tr2)))
            rows2 = sp.lin_rows(mm.t, mm.c, tr2, mm.N, mm.ft, mm.fr)
            a_, b_ = (base["minute"] < lim), (rows2["minute"] < lim)
            eq = all(np.array_equal(base[k][a_], rows2[k][b_]) for k in sp.ROW_COLS)
            r[f"{tag_}_rows_compared"] = int(a_.sum())
            r[f"{tag_}_invariant"] = bool(eq)
            need(eq, f"{s} {tag_} invariance at {cut}", r)
    log("G3 family prefix/tamper ok")
    return dict(m=m, mk=mk, dec4=dec4, b2=b2, sleeves=out, st=st, f=f, lbr_events=sigs["LBR_FUND"]["events"])


# ================================================================ C1v2 / C4v2
def c_family(args, rec: dict) -> dict:
    F = load("sim_r2_56_fix1_rl", "scripts/sim_r2_56_fix1.py")
    rp, r237 = F.rp, F.r237
    F.verify_inputs()
    rows_ls, _ = F.ls_rows()
    market, features, fund, *_ = F.inputs(rows_ls)
    leg, books = F.books_for(market, features)
    bars = r237.hourly_bars(market)                       # same calls as books_for: the full decision timeline
    full = {**r237.build_f3_signals(market, features, bars)[1], **r237.build_e1_signals(market, bars)[1]}
    t = market.open_time.array.asi8.copy()
    # LS archive starts 2020-09; before it the legacy cache is zero-filled and the F leg trades on fake LS.
    # Sleeve available from the first real LS minute + the F-leg quantile warm-up (720 hourly decisions).
    ls = features.global_ls_account.to_numpy(float)
    first_ls = int(t[np.argmax(np.isfinite(ls) & (ls != 0))])
    c_avail = t >= first_ls + 720 * 60 * sp.MIN
    mk = {"t": t, "o": market.open.to_numpy(float), "h": market.high.to_numpy(float),
          "l": market.low.to_numpy(float), "c": market.close.to_numpy(float)}
    ft, fr = pd.DatetimeIndex(fund.time).as_unit("ns").asi8, fund.rate.to_numpy(float)
    rep = json.loads((R256 / "report.json").read_text(encoding="utf-8"))
    A, B, NA, NB = rp.A, rp.B, rp.NA, rp.NB
    out = {}
    for s in ("C1v2", "C4v2"):
        r = rec.setdefault(f"{s}|native", {})
        bk = books[s].reset_index(drop=True)
        stored = pd.read_parquet(R256 / f"{s}_trades_2020_2026.parquet").reset_index(drop=True)
        eq = len(stored) == len(bk) and all(
            np.array_equal(stored[c].to_numpy(), bk[c].to_numpy()) if bk[c].dtype.kind in "fiub" else
            bool((stored[c].astype(str) == bk[c].astype(str)).all()) for c in stored.columns)
        r["trades_equal_stored"], r["trades_total"] = bool(eq), int(len(bk))
        need(eq, f"{s} trades == stored R2-56 fix1", r)
        tr = c_trades(bk, t)
        rows = sp.log_rows(t, mk["c"], tr, 2.0, ft, fr)
        net = sp.minute_sum(rows, len(t))
        pnl0, units = r237.fast_ledger(bk, market, fund, "PESS")
        src = pnl0 - 4.0 * units
        r["minute_max_abs_vs_source_fast_ledger"] = float(np.abs(net - src).max())
        need(r["minute_max_abs_vs_source_fast_ledger"] <= ATOL_MIN, f"{s} minute ledger vs r237.fast_ledger", r)
        for w, (a, b, n_ref, t_ref) in {"TEST": (A, B, rep["candidates"][s]["net_4bps"], rep["candidates"][s]["trades"]),
                                        "NATIVE_2023_2025": (NA, NB, rep["native"][s]["net_4bps"],
                                                             rep["native"][s]["trades"])}.items():
            got = window_sum(net, t, a, b)
            cnt = int(((bk.entry_time < b) & (bk.exit_time >= a)).sum())
            r[f"{w}_net4"], r[f"{w}_ref"], r[f"{w}_trades"], r[f"{w}_trades_ref"] = got, n_ref, cnt, t_ref
            need(abs(got - n_ref) <= ATOL_TOT and cnt == t_ref, f"{s} {w} net4/trades vs R2-56 report", r)
        r["TEST_design_ref"] = REF[(s, "TEST")]
        need(abs(r["TEST_net4"] - REF[(s, "TEST")]) <= 5e-6, f"{s} TEST vs design 6dp", r)
        out[(s, "native")] = dict(tr=tr, bk=bk, rows=rows, net=net, sig=c_signal(t, full, s), avail=c_avail)
    log("C family parity ok")
    # prefix / future tamper at 2026-01-01 (market o/h/l/c and LS x1.7 after the cut; truncation)
    cut = A
    ci = int(np.searchsorted(t, cut.value))
    mt_ = market.copy()
    after = (mt_.open_time >= cut).to_numpy()
    for c in ("open", "high", "low", "close"):
        mt_.loc[after, c] = mt_.loc[after, c] * 1.7
    ftmp = features.copy()
    ftmp.loc[after, "global_ls_account"] = ftmp.loc[after, "global_ls_account"] * 1.7
    _, books_t = F.books_for(mt_, ftmp)
    mp_, fp_ = market.loc[~after].reset_index(drop=True), features.loc[~after].reset_index(drop=True)
    _, books_p = F.books_for(mp_, fp_)
    for s in ("C1v2", "C4v2"):
        r = rec[f"{s}|native"]
        base = out[(s, "native")]["rows"]
        for tag_, bks, mm, lim in (("tamper", books_t, mt_, ci), ("prefix", books_p, mp_, ci - 1)):
            tt = mm.open_time.array.asi8.copy()
            tr2 = c_trades(bks[s].reset_index(drop=True), tt)
            rows2 = sp.log_rows(tt, mm.close.to_numpy(float), tr2, 2.0, ft, fr)
            a_, b_ = base["minute"] < lim, rows2["minute"] < lim
            eq = all(np.array_equal(base[k][a_], rows2[k][b_]) for k in sp.ROW_COLS)
            r[f"{tag_}_rows_compared"], r[f"{tag_}_invariant"] = int(a_.sum()), bool(eq)
            need(eq, f"{s} {tag_} invariance at {cut}", r)
    log("C family prefix/tamper ok")
    return dict(market=market, fund=fund, mk=mk, ft=ft, fr=fr, r237=r237, sleeves=out,
                f_events={s: full[C_LEGS[s]] for s in ("C1v2", "C4v2")})


C_LEGS = {"C1v2": ("F3", "V5"), "C4v2": ("F3-w30", "V0")}


def c_signal(t: np.ndarray, full: dict, s: str) -> dict:
    """Per-minute causal C signal: each leg's latest decision (decision_time <= minute open; R2-37 zero-latency
    contract), book side = F leg if nonzero else E1/V1a (single book FIRST priority). No pending state exists: the
    source fills at the decision minute open."""
    (tf, sf), (te, se) = full[C_LEGS[s]], full[("E1", "V1a")]
    tf, te = pd.DatetimeIndex(tf).as_unit("ns").asi8, pd.DatetimeIndex(te).as_unit("ns").asi8
    a = sp.event_ffill(t, tf, sf, 0, np.int8)
    b = sp.event_ffill(t, te, se, 0, np.int8)
    return {"side": np.where(a != 0, a, b).astype(np.int8), "pending": np.zeros(len(t), bool),
            "snap": sp.event_index(t, tf), "aux": sp.event_index(t, te)}


def c_trades(bk: pd.DataFrame, t: np.ndarray) -> pd.DataFrame:
    en = pd.DatetimeIndex(bk.entry_time).as_unit("ns").asi8
    ex = pd.DatetimeIndex(bk.exit_time).as_unit("ns").asi8
    hold = bk.candidate.map({"F3/V5": 24, "F3/V5r": 24, "F3-w30/V0": 12, "E1/V1a": 20}).to_numpy(float)
    return pd.DataFrame({"tid": np.arange(len(bk)), "side": bk.side.to_numpy(int), "units": 1.0,
                         "e": np.searchsorted(t, en, "left"), "x": np.searchsorted(t, ex, "right") - 1,
                         "px_in": bk.entry_price.to_numpy(float), "px_out": bk.exit_price.to_numpy(float),
                         "entry_ns": en, "exit_ns": ex, "sched_exit_ns": en + (hold * 3600e9).astype(np.int64),
                         "candidate": bk.candidate.astype(str).to_numpy(), "reason": bk.exit_reason.astype(str).to_numpy(),
                         "snapshot_id": bk.source_signal_id.to_numpy(np.int64)})


# ================================================================ B3 / K04 (sim core AXC0)
def ax_family(args, rec: dict) -> dict:
    r255 = load("sim_r2_55_rl", "scripts/sim_r2_55.py")
    ax = r255.ax
    from btcusdt_quant.sim import costs, rolling
    from btcusdt_quant.sim.strategies import Context
    rep0 = json.loads((R256 / "report_r0.json").read_text(encoding="utf-8"))
    sel = pd.read_csv(ROOT / "out/k45_rl_r2_48_20261007/r2_55/selection/selected_k.csv")
    A, B = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-10-08", tz="UTC")
    run = r255.stageb_runner()
    run.verify_snapshot(read_frames=False)
    ctx, _, settle = run.test_context()
    nctx = Context.load(end=rolling.END)
    windows = [w for w in rolling.WINDOWS if w.test_start >= pd.Timestamp("2023-09-01", tz="UTC")]
    out = {}
    for i in ("B3", "K04"):
        s = f"{i}_AXC0"
        r = rec.setdefault(f"{s}|native", {})
        segs = []
        for seg, c_, a, b in (("NATIVE", nctx, windows[0].test_start, windows[-1].test_end), ("TEST", ctx, A, B)):
            times = pd.DatetimeIndex(c_.minutes.open_time)
            table = r255.ax_table(c_, i, True)
            e, e_min = ax.e_matrix(c_.regime, times, ax.heads(i))
            if seg == "TEST":
                kk = float(sel.loc[(sel.id == i) & (sel.window == r255.LAST_WINDOW), "k"].iloc[0])
                km = np.full(len(c_.minutes), kk)
            else:
                km = ax.k_schedule(times, sel.loc[sel.id == i].set_index("window").k.to_dict(), windows)
            cfg = replace(ax.CONFIG, close_at_end=True, fee_per_side=r255.FEE4, causal_guard=True)
            if seg == "TEST":
                with run.sb.ledger_settlements(settle):
                    res = ax.run_ax(table, c_.minutes, e, e_min, a, b, cfg, km)
                    ft, fr = costs._settlement_arrays()
            else:
                res = ax.run_ax(table, c_.minutes, e, e_min, a, b, cfg, km)
                ft, fr = costs._settlement_arrays()
            inside = ((c_.minutes.open_time >= a) & (c_.minutes.open_time < b)).to_numpy()
            mm = c_.minutes.loc[inside].reset_index(drop=True)
            segs.append(dict(seg=seg, a=a, b=b, res=res, mm=mm, ft=ft, fr=fr, table=table,
                             e=e[inside], e_min=e_min[inside], km=np.asarray(km, float)[inside], cfg=cfg))
        rr = []
        for g in segs:
            tt = g["mm"].open_time.array.asi8.copy()
            tr = ax_trades(g["res"].trades, tt, g, ax)
            rows = sp.log_rows(tt, g["mm"].close.to_numpy(float), tr, r255.FEE4, g["ft"], g["fr"])
            net = sp.minute_sum(rows, len(tt))
            src = g["res"].minute_pnl.to_numpy(float)
            r[f"{g['seg']}_minute_max_abs_vs_core"] = float(np.abs(net - src).max())
            need(r[f"{g['seg']}_minute_max_abs_vs_core"] <= ATOL_MIN, f"{s} {g['seg']} minute ledger vs core", r)
            r[f"{g['seg']}_net4"] = float(net.sum())
            r[f"{g['seg']}_positions"] = int(len(tr))
            g.update(tr=tr, rows=rows, net=net, t=tt, sig=ax_signal(tt, g, tr))
            rr.append(g)
        ref_t = rep0["candidates"][s]
        ref_n = rep0["native"][s]
        r["TEST_ref"], r["TEST_positions_ref"] = ref_t["net_4bps"], ref_t["trades"]
        r["NATIVE_ref"], r["NATIVE_positions_ref"] = ref_n["net_4bps"], ref_n["trades"]
        need(abs(r["TEST_net4"] - ref_t["net_4bps"]) <= ATOL_TOT and r["TEST_positions"] == ref_t["trades"],
             f"{s} TEST vs R2-56 r0", r)
        need(abs(r["NATIVE_net4"] - ref_n["net_4bps"]) <= ATOL_TOT and r["NATIVE_positions"] == ref_n["trades"],
             f"{s} NATIVE vs R2-56 r0", r)
        r["TEST_design_ref"] = REF[(s, "TEST")]
        need(abs(r["TEST_net4"] - REF[(s, "TEST")]) <= 5e-6, f"{s} TEST vs design 6dp", r)
        pos = pd.read_parquet(R256 / f"{s}_positions_2026.parquet")
        tr = rr[1]["tr"]
        eqp = len(pos) == len(tr) and np.allclose(pos.net_bps.to_numpy(), tr.net_full.to_numpy(), rtol=0, atol=1e-9) \
            and (pd.DatetimeIndex(pos.entry_time).as_unit("ns").asi8 == tr.entry_ns.to_numpy()).all()
        r["TEST_positions_equal_stored"] = bool(eqp)
        need(eqp, f"{s} TEST positions == stored R2-56", r)
        # prefix / engine-tamper on the TEST segment (cut 2026-05-01)
        g = rr[1]
        cut = pd.Timestamp("2026-05-01", tz="UTC")
        ci = int(np.searchsorted(g["t"], cut.value))
        for tag_ in ("prefix", "tamper"):
            mins = ctx.minutes.copy()
            hi_ = B
            if tag_ == "tamper":
                aft = (mins.open_time >= cut).to_numpy()
                for c in ("open", "high", "low", "close"):
                    mins.loc[aft, c] = mins.loc[aft, c] * 1.7
            else:
                hi_ = cut
            with run.sb.ledger_settlements(settle):
                res2 = ax.run_ax(g["table"], mins, ax.e_matrix(ctx.regime, pd.DatetimeIndex(mins.open_time),
                                                               ax.heads(i))[0], ax.e_matrix(
                    ctx.regime, pd.DatetimeIndex(mins.open_time), ax.heads(i))[1], A, hi_, g["cfg"],
                    np.full(len(mins), g["km"][0]))
            p2 = res2.minute_pnl.to_numpy(float)
            lim = ci if tag_ == "tamper" else ci - 1
            eq = np.array_equal(p2[:lim], g["res"].minute_pnl.to_numpy(float)[:lim])
            r[f"{tag_}_minutes_compared"], r[f"{tag_}_invariant"] = int(lim), bool(eq)
            need(eq, f"{s} {tag_} invariance at {cut} (engine; table fixed)", r)
        out[(s, "native")] = dict(segs=rr)
        log(f"{s} parity ok")
    return dict(sleeves=out)


def ax_signal(t: np.ndarray, g: dict, tr: pd.DataFrame) -> dict:
    """Per-minute causal AXC0 signal from the source decision table (15 m groups, executed at decision + 1 m):
    side of the first row the core would open on (allow_entry, side != 0, finite E0 > 0) of the latest decision group
    with decision_time <= minute open; pending = that group's entry decision at this minute while flat at its open
    (order waits for the next-minute open). snapshot = first table row of the latest group (segment table index)."""
    tb = g["table"].reset_index(drop=True)
    dt = pd.DatetimeIndex(tb.decision_time).as_unit("ns").asi8
    ok = tb.allow_entry.to_numpy(bool) & (tb.side.to_numpy() != 0) & np.isfinite(tb.e0_bps.to_numpy(float))         & (tb.e0_bps.to_numpy(float) > 0)
    first = np.r_[True, dt[1:] != dt[:-1]]
    gid = np.cumsum(first) - 1
    g_t, g_row = dt[first], np.flatnonzero(first)
    g_side = np.zeros(len(g_t), np.int8)
    cand = np.flatnonzero(ok)
    pick = pd.Series(cand).groupby(gid[cand]).first()
    g_side[pick.index.to_numpy()] = tb.side.to_numpy()[pick.to_numpy()]
    side = sp.event_ffill(t, g_t, g_side, 0, np.int8)
    k = sp.event_index(t, g_t)
    openm = sp.interval_mask(len(t), tr.e.to_numpy(), tr.x.to_numpy())
    at_dec = (k >= 0) & (g_t[np.maximum(k, 0)] == t)
    return {"side": side, "pending": at_dec & (side != 0) & ~openm, "snap": np.where(k >= 0, g_row[np.maximum(k, 0)], -1),
            "aux": np.full(len(t), -1)}


def ax_trades(trades: pd.DataFrame, t: np.ndarray, g: dict, ax) -> pd.DataFrame:
    """Positions (one leg each) -> log trades with adaptive-exit metadata (row lookup by decision time)."""
    if trades.position_id.duplicated().any():
        raise Fail("multi-leg position in AXC0 ledger")
    tb = g["table"].reset_index(drop=True)
    dt = pd.DatetimeIndex(tb.decision_time).as_unit("ns").asi8
    en = pd.DatetimeIndex(trades.entry_time).as_unit("ns").asi8
    ex = pd.DatetimeIndex(trades.exit_time).as_unit("ns").asi8
    e, x = np.searchsorted(t, en), np.searchsorted(t, ex)
    dec = pd.DatetimeIndex(trades.decision_time).as_unit("ns").asi8
    rows, e0s, cols, ks, kinds = [], [], [], [], []
    for q in range(len(trades)):
        cand = np.flatnonzero(dt == dec[q])
        side = int(trades.side.iloc[q])
        mkt = [j for j in cand if bool(tb.allow_entry.iloc[j]) and tb.side.iloc[j] == side and tb.entry.iloc[j] != "oco"
               and np.isfinite(tb.e0_bps.iloc[j]) and tb.e0_bps.iloc[j] > 0]
        oco = [j for j in cand if bool(tb.allow_entry.iloc[j]) and tb.entry.iloc[j] == "oco"]
        if mkt:
            j = mkt[0]; c_ = int(tb.e_col.iloc[j]); e0 = float(tb.e0_bps.iloc[j]); kinds.append("market")
        elif oco:
            j = oco[0]; c_ = int(tb.e_col.iloc[j]); e0 = float(g["e"][e[q], c_]); kinds.append("oco")
        else:
            j, c_, e0 = -1, 0, np.nan; kinds.append("unmatched")
        rows.append(j); cols.append(c_); e0s.append(e0); ks.append(float(g["km"][e[q]]))
    return pd.DataFrame({"tid": np.arange(len(trades)), "side": trades.side.to_numpy(int),
                         "units": trades.units.to_numpy(float), "e": e, "x": x,
                         "px_in": trades.entry_price.to_numpy(float), "px_out": trades.exit_price.to_numpy(float),
                         "entry_ns": en, "exit_ns": ex, "decision_ns": dec, "reason": trades.exit_reason.astype(str),
                         "net_full": trades.net_bps.to_numpy(float), "snapshot_id": np.asarray(rows, np.int64),
                         "e_col": cols, "e0": e0s, "k": ks, "entry_kind": kinds,
                         "position_id": trades.position_id.to_numpy(np.int64)})


# ================================================================ counterfactual parity
def cf_paths(t, tr: pd.DataFrame, kind: str, rng, n_paths: int, hi: int):
    for _ in range(n_paths):
        mult = rng.choice(sp.LEVELS, size=len(tr))
        ex = np.full(len(tr), -1, np.int64)
        for q in np.flatnonzero((rng.random(len(tr)) < 0.3) & (mult > 0)):
            r = tr.iloc[q]
            if kind == "lin":
                lo = int(r.entry_idx) + 1
                up = (int(r.exit_decision_idx) if not r.open_at_end else hi - 1)
            else:
                lo, up = int(r.e) + 1, int(r.x)
            ch = hour_choices(t, lo, up)
            if len(ch):
                ex[q] = int(rng.choice(ch))
        yield mult, ex


def cf_direct_lin(b2, m, tr, od, mult, ex, pen):
    t2 = tr.copy()
    t2["entry_weight_frozen"] = t2.entry_weight_frozen * mult
    changed = 0
    for q in np.flatnonzero(ex >= 0):
        r = t2.iloc[q]
        if mult[q] == 0:
            continue
        xd = int(ex[q]) - 1
        xc = int(r.exit_decision_idx) if not r.open_at_end else m.N
        if not (int(r.entry_idx) <= xd < xc):
            continue
        j, px = b2.exit_fill(m, xd, int(r.side), m.N, pen)       # source engine fill
        if j < 0 or (not r.open_at_end and j > int(r.exit_idx)):
            continue
        t2.loc[q, ["exit_decision_idx", "exit_idx", "exit_px", "open_at_end"]] = [xd, j, px, False]
        changed += 1
    t2 = t2[mult > 0].drop(columns="tid").reset_index(drop=True)
    for c in ("exit_decision_idx", "exit_idx"):
        t2[c] = t2[c].astype(np.int64)
    t2["open_at_end"] = t2.open_at_end.astype(bool)
    return b2.Book(m, t2, od, 0, m.N).pnl, changed


def cf_direct_c(r237, market, fund, bk, mk, mult, ex):
    b = bk.copy()
    t = mk["t"]
    changed = 0
    for q in np.flatnonzero(ex >= 0):
        e_ = int(np.searchsorted(t, pd.Timestamp(b.entry_time.iloc[q]).value))
        x_ = int(np.searchsorted(t, pd.Timestamp(b.exit_time.iloc[q]).value, "right")) - 1
        x = int(ex[q])
        if mult[q] == 0 or not (e_ < x <= x_):
            continue
        b.loc[q, "exit_time"] = pd.Timestamp(int(t[x]), tz="UTC")
        b.loc[q, "exit_price"] = float(mk["o"][x])
        changed += 1
    out = np.zeros(len(t))
    for lv in sp.LEVELS[1:]:
        sub = b[mult == lv]
        if len(sub):
            p0, u = r237.fast_ledger(sub, market, fund, "PESS")
            out += lv * (p0 - 4.0 * u)
    return out, changed


def cf_direct_ax(g, mult, ex):
    tr = g["tr"].copy()
    o = g["mm"].open.to_numpy(float)
    changed = 0
    for q in np.flatnonzero(ex >= 0):
        x = int(ex[q])
        if mult[q] == 0 or not (int(tr.e.iloc[q]) < x <= int(tr.x.iloc[q])):
            continue
        tr.loc[q, ["x", "px_out", "exit_ns"]] = [x, o[x], int(g["t"][x])]
        changed += 1
    tr["units"] = tr.units * mult
    tr = tr[mult > 0]
    tr["x"] = tr.x.astype(np.int64); tr["exit_ns"] = tr.exit_ns.astype(np.int64)
    rows = sp.log_rows(g["t"], g["mm"].close.to_numpy(float), tr, 2.0, g["ft"], g["fr"])
    return sp.minute_sum(rows, len(g["t"])), changed


def counterfactual(args, G, C, X, rec):
    res = {}
    n_paths = args.paths
    for (s, tag), d in (G["sleeves"].items() if G else []):
        r = rec[f"{s}|{tag}"]
        m, mk = G["m"], G["mk"]
        rng = np.random.default_rng(SEED + SLEEVE_ID[s] * 100 + CELLS.index(tuple(
            (int(tag[1]), float(tag.split("_p")[1])))))
        worst_m, worst_t, n_ex, n_ch = 0.0, 0.0, 0, 0
        zero = sp.replay("lin", d["rows"], d["tr"], mk, m.ft, m.fr, np.zeros(len(d["tr"])),
                         np.full(len(d["tr"]), -1), pen=d["pen"])
        r["all_off_max_abs"] = float(np.abs(zero).max())
        need(r["all_off_max_abs"] == 0.0, f"{s} {tag} all-off exactly 0", r)
        one = sp.replay("lin", d["rows"], d["tr"], mk, m.ft, m.fr, np.ones(len(d["tr"])), np.full(len(d["tr"]), -1),
                        pen=d["pen"])
        need(np.array_equal(one, d["net"]), f"{s} {tag} all-on replay == canonical", r)
        for mult, ex in cf_paths(m.t, d["tr"], "lin", rng, n_paths, m.N):
            fast = sp.replay("lin", d["rows"], d["tr"], mk, m.ft, m.fr, mult, ex, pen=d["pen"])
            slow, ch = cf_direct_lin(G["b2"], m, d["tr"], d["od"], mult, ex, d["pen"])
            worst_m = max(worst_m, float(np.abs(fast - slow).max()))
            worst_t = max(worst_t, abs(float(fast.sum() - slow.sum())))
            n_ex += int((ex >= 0).sum()); n_ch += ch
        res[f"{s}|{tag}"] = {"paths": n_paths, "max_abs_minute": worst_m, "max_abs_total": worst_t,
                             "exit_requests": n_ex, "early_exits_applied": n_ch}
        r["counterfactual"] = res[f"{s}|{tag}"]
        need(worst_m <= ATOL_MIN and worst_t <= ATOL_TOT, f"{s} {tag} counterfactual fast vs Book", r)
        log(f"cf {s} {tag} {res[f'{s}|{tag}']}")
    for (s, tag), d in (C["sleeves"].items() if C else []):
        r = rec[f"{s}|{tag}"]
        mk = C["mk"]
        rng = np.random.default_rng(SEED + SLEEVE_ID[s] * 100)
        zero = sp.replay("log", d["rows"], d["tr"], mk, C["ft"], C["fr"], np.zeros(len(d["tr"])),
                         np.full(len(d["tr"]), -1))
        r["all_off_max_abs"] = float(np.abs(zero).max())
        need(r["all_off_max_abs"] == 0.0, f"{s} all-off exactly 0", r)
        worst_m, worst_t, n_ex, n_ch = 0.0, 0.0, 0, 0
        for mult, ex in cf_paths(mk["t"], d["tr"], "log", rng, n_paths, len(mk["t"])):
            fast = sp.replay("log", d["rows"], d["tr"], mk, C["ft"], C["fr"], mult, ex)
            slow, ch = cf_direct_c(C["r237"], C["market"], C["fund"], d["bk"], mk, mult, ex)
            worst_m = max(worst_m, float(np.abs(fast - slow).max()))
            worst_t = max(worst_t, abs(float(fast.sum() - slow.sum())))
            n_ex += int((ex >= 0).sum()); n_ch += ch
        res[f"{s}|{tag}"] = {"paths": n_paths, "max_abs_minute": worst_m, "max_abs_total": worst_t,
                             "exit_requests": n_ex, "early_exits_applied": n_ch}
        r["counterfactual"] = res[f"{s}|{tag}"]
        need(worst_m <= ATOL_MIN and worst_t <= ATOL_TOT, f"{s} counterfactual fast vs r237.fast_ledger", r)
        log(f"cf {s} {res[f'{s}|{tag}']}")
    for (s, tag), d in (X["sleeves"].items() if X else []):
        r = rec[f"{s}|{tag}"]
        rng = np.random.default_rng(SEED + SLEEVE_ID[s] * 100)
        agg = {"paths": n_paths, "max_abs_minute": 0.0, "max_abs_total": 0.0, "exit_requests": 0,
               "early_exits_applied": 0}
        for g in d["segs"]:
            mk = {"t": g["t"], "o": g["mm"].open.to_numpy(float), "h": g["mm"].high.to_numpy(float),
                  "l": g["mm"].low.to_numpy(float), "c": g["mm"].close.to_numpy(float)}
            zero = sp.replay("log", g["rows"], g["tr"], mk, g["ft"], g["fr"], np.zeros(len(g["tr"])),
                             np.full(len(g["tr"]), -1))
            r[f"{g['seg']}_all_off_max_abs"] = float(np.abs(zero).max())
            need(r[f"{g['seg']}_all_off_max_abs"] == 0.0, f"{s} {g['seg']} all-off exactly 0", r)
            for mult, ex in cf_paths(g["t"], g["tr"], "log", rng, n_paths, len(g["t"])):
                fast = sp.replay("log", g["rows"], g["tr"], mk, g["ft"], g["fr"], mult, ex)
                slow, ch = cf_direct_ax(g, mult, ex)
                agg["max_abs_minute"] = max(agg["max_abs_minute"], float(np.abs(fast - slow).max()))
                agg["max_abs_total"] = max(agg["max_abs_total"], abs(float(fast.sum() - slow.sum())))
                agg["exit_requests"] += int((ex >= 0).sum()); agg["early_exits_applied"] += ch
        res[f"{s}|{tag}"] = agg
        r["counterfactual"] = agg
        need(agg["max_abs_minute"] <= ATOL_MIN and agg["max_abs_total"] <= ATOL_TOT,
             f"{s} counterfactual fast vs direct log ledger", r)
        log(f"cf {s} {agg}")
    return res


# ================================================================ outputs
def write_part(frame: pd.DataFrame, d: Path, stem: str, tcol: str = "minute_time") -> dict:
    d.mkdir(parents=True, exist_ok=True)
    yrs = np.asarray(pd.to_datetime(frame[tcol].to_numpy(np.int64), utc=True).year)
    out = {}
    for y in np.unique(yrs):
        p = d / f"{stem}_{y}.parquet"
        frame.loc[yrs == y].to_parquet(p, index=False, compression="zstd")
        out[p.name] = {"rows": int((yrs == y).sum()), "bytes": p.stat().st_size, "sha256": sha(p)}
    return out


DECISION_COLS = sp.OBS_COLUMNS["decisions"]


def grid_frame(n, t, s, cell_id, *, side_sig, w_sig, active, pending, open_, exit_pending, opp, mand, R0, Rt,
               lvl, armed, rows, snap, aux, available, closed) -> pd.DataFrame:
    g = np.bincount(rows["minute"], rows["gross"], minlength=n)[:n]
    fe = np.bincount(rows["minute"], rows["fee"], minlength=n)[:n]
    fu = np.bincount(rows["minute"], rows["funding"], minlength=n)[:n]
    f = pd.DataFrame({
        "minute_time": t, "sleeve_id": np.full(n, SLEEVE_ID[s], np.int8), "exec_cell": np.full(n, cell_id, np.int8),
        "available": available, "base_side": side_sig.astype(np.int8), "base_weight": w_sig.astype(np.float32),
        "signal_active": active, "pending": pending, "open": open_, "exit_pending": exit_pending,
        "entry_opportunity_id": opp.astype(np.int32), "base_mandatory_exit_time": mand.astype(np.int64),
        "R0_bps": R0.astype(np.float32), "R_t_bps": Rt.astype(np.float32), "stop_level": lvl.astype(np.float32),
        "trail_armed": armed.astype(np.int8), "gross_pnl": g, "fee": fe, "funding": fu, "net4": g + fe + fu,
        "available_time": t + sp.MIN, "feature_snapshot_id": snap.astype(np.int32),
        "snapshot_id_aux": aux.astype(np.int32), "closed_opp_id": closed.astype(np.int32)})
    sp.obs_columns("grid", f.columns)
    return f


def ledger_frame(rows, t, opp_of_tid) -> pd.DataFrame:
    return pd.DataFrame({"minute_time": t[rows["minute"]], "available_time": t[rows["minute"]] + sp.MIN,
                         "minute_idx": rows["minute"], "entry_opportunity_id": opp_of_tid[rows["tid"]].astype(np.int32),
                         "tid": rows["tid"].astype(np.int32), "gross_pnl": rows["gross"], "fee": rows["fee"],
                         "funding": rows["funding"], "net4": rows["gross"] + rows["fee"] + rows["funding"]})


def split_opp(opp: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Physical split: decisions (observation-safe, allowlisted) vs outcomes (private replay/accounting)."""
    dec = opp[[c for c in DECISION_COLS if c in opp]].copy()
    sp.obs_columns("decisions", dec.columns)
    out = opp[["entry_opportunity_id"] + [c for c in opp.columns if c not in DECISION_COLS]].copy()
    out["decision_time"] = opp.decision_time.to_numpy()          # partition key only
    return dec, out


def write_sleeve(dd: Path, gf, rows, t, opp, opp_tid) -> dict:
    dec, outc = split_opp(opp)
    return {"grid": write_part(gf, dd, "grid"), "ledger": write_part(ledger_frame(rows, t, opp_tid), dd, "ledger"),
            "decisions": write_part(dec, dd, "decisions", "decision_time"),
            "outcomes": write_part(outc, dd, "outcomes", "decision_time"), "n_opportunities": int(len(opp))}


def g3_ready(G, s: str) -> np.ndarray:
    """Per 4h decision: the sleeve's signal inputs are ready (not-ready decisions are forced flat by the source)."""
    st, f = G["st"], G["f"]
    with np.errstate(invalid="ignore"):
        if s == "G3_LONG":
            return np.isfinite(st["score"][(42, 168, 504)]) & np.isfinite(st["svi"][180]) & np.isfinite(st["w"]["W180-P65"])
        if s == "G3_SHORT":
            return (np.isfinite(st["score"][(6, 18, 42)]) & np.isfinite(st["svi"][180]) & np.isfinite(st["w"]["V-ENS"])
                    & (st["j"] >= 0) & np.isfinite(st["med"]))
        return np.isfinite(f["zr4"]) & np.isfinite(f["ztaker"]) & np.isfinite(f["zfund"]) & np.isfinite(f["w"])


def out_g3(G, files, avail_rep):
    m, dec4 = G["m"], G["dec4"]
    n, t = m.N, m.t
    sig_min = np.searchsorted(dec4, np.arange(n), "left") - 1          # latest decision with dec4 < i (closed)
    for (s, tag), d in G["sleeves"].items():
        tr, od = d["tr"], d["od"].reset_index(drop=True)
        cell_id = [CELL_TAG[c] for c in CELLS].index(tag)
        k = (od.decision_idx.to_numpy() - 239) // 240
        dec = od.decision_idx.to_numpy(np.int64)
        opp = pd.DataFrame({"entry_opportunity_id": np.arange(len(od), dtype=np.int32),
                            "decision_time": t[dec] + sp.MIN, "available_time": t[dec] + sp.MIN,
                            "side": od.side.to_numpy(np.int8), "base_weight": od.weight.to_numpy(float),
                            "feature_snapshot_id": k.astype(np.int32), "segment": "ALL",
                            "decision_idx": dec, "filled": od.filled.to_numpy(bool)})
        fill_opp = np.flatnonzero(opp.filled.to_numpy())
        if len(fill_opp) != len(tr) or not np.array_equal(dec[fill_opp], tr.decision_idx.to_numpy()):
            raise Fail(f"{s} {tag} order->trade map")
        opp["tid"] = -1
        opp.loc[fill_opp, "tid"] = tr.tid.to_numpy()
        for c in ("entry_idx", "entry_px", "exit_decision_idx", "exit_idx", "exit_px", "open_at_end"):
            opp[c] = np.nan if c.endswith("px") else (-1 if c != "open_at_end" else False)
            opp.loc[fill_opp, c] = tr[c].to_numpy()
        mand = np.full(len(opp), -1, np.int64)
        if s == "LBR_FUND":                                   # max_hold 2 bars: exit decision bar close, known at T
            kk = k + 2
            okk = kk < len(dec4)
            mand[okk] = t[dec4[kk[okk]]] + sp.MIN
        opp["base_mandatory_exit_time"] = mand
        tot = pd.DataFrame({"tid": d["rows"]["tid"], "g": d["rows"]["gross"], "f": d["rows"]["fee"],
                            "u": d["rows"]["funding"]}).groupby("tid").sum()
        for nm, c in (("gross_pnl", "g"), ("fee", "f"), ("funding", "u")):
            opp[nm] = 0.0
            opp.loc[fill_opp, nm] = tot[c].reindex(tr.tid).to_numpy()
        opp["net4"] = opp.gross_pnl + opp.fee + opp.funding
        j0 = np.where(opp.filled, opp.entry_idx, -1).astype(np.int64)
        pend_end = np.where(opp.filled, j0 - 1, np.minimum(dec + 60, n - 1))
        oa, ob = tr.entry_idx.to_numpy(), np.where(tr.open_at_end, n - 1, tr.exit_idx).astype(np.int64)
        xa = np.where(tr.open_at_end, n, tr.exit_decision_idx + 1).astype(np.int64)
        oid = opp.entry_opportunity_id.to_numpy()
        opp_min = sp.interval_fill(n, dec + 1, pend_end, oid, -1, np.int32)
        opp_open = sp.interval_fill(n, oa, ob, oid[fill_opp], -1, np.int32)
        opp_min = np.where(opp_open >= 0, opp_open, opp_min)
        mand_min = sp.interval_fill(n, dec + 1, pend_end, mand, -1, np.int64)
        mand_min = np.where(opp_open >= 0, sp.interval_fill(n, oa, ob, mand[fill_opp], -1, np.int64), mand_min)
        closed = np.full(n, -1, np.int64)
        cl = ~tr.open_at_end.to_numpy(bool)
        closed[tr.exit_idx.to_numpy()[cl].astype(np.int64)] = oid[fill_opp][cl]   # exit fill minute
        side_sig = np.where(sig_min >= 0, d["sig"]["side"][np.maximum(sig_min, 0)], 0)
        w_sig = np.where(sig_min >= 0, d["sig"]["w"][np.maximum(sig_min, 0)], 0.0)
        ready = g3_ready(G, s)
        avail = (sig_min >= 0) & ready[np.maximum(sig_min, 0)]
        openm = sp.interval_mask(n, oa, ob)
        w_open = sp.interval_fill(n, oa, ob, tr.entry_weight_frozen.to_numpy(), np.nan, float)
        w_sig = np.where(openm, w_open, w_sig)
        nanf = np.full(n, np.nan)
        gf = grid_frame(n, t, s, cell_id, side_sig=side_sig, w_sig=w_sig, active=side_sig != 0,
                        pending=sp.interval_mask(n, dec + 1, pend_end), open_=openm,
                        exit_pending=sp.interval_mask(n, xa, ob), opp=opp_min, mand=mand_min, R0=nanf, Rt=nanf,
                        lvl=nanf, armed=np.zeros(n), rows=d["rows"], snap=sig_min, aux=np.full(n, -1),
                        available=avail, closed=closed)
        if float(np.abs(gf.net4.to_numpy() - d["net"]).max()) > ATOL_MIN:
            raise Fail(f"{s} {tag} grid net4")
        if tag == CELL_TAG[PRIMARY]:
            avail_rep[s] = availability(t, avail, gf.open.to_numpy())
        files[f"g3_family/{tag}/{s}"] = write_sleeve(PRE / "g3_family" / tag / s, gf, d["rows"], t, opp,
                                                     opp_of(opp, len(tr)))
        log(f"wrote {s} {tag}")


# amendment A2 r1 (user 2026-10-10, supersedes the 2021-12-01 A2): RL data usable from 2021-01-30 00:00 UTC
# (G3_SHORT first availability; weekly MA20/50 valid since 2020-12-21); four expanding folds
USABLE_FROM = "2021-01-30"
FOLDS_A2 = {"F1": (("2021-01-30", "2022-01-01"), ("2022-01-01", "2023-01-01")),
            "F2": (("2021-01-30", "2023-01-01"), ("2023-01-01", "2024-01-01")),
            "F3": (("2021-01-30", "2024-01-01"), ("2024-01-01", "2025-01-01")),
            "F4": (("2021-01-30", "2025-01-01"), ("2025-01-01", "2026-01-01"))}
FOLDS = {"F1": (("2020-01-01", "2021-01-01"), ("2021-01-01", "2022-01-01")),   # A1 folds (precompute report only)
         "F2": (("2020-01-01", "2022-01-01"), ("2022-01-01", "2023-01-01")),
         "F3": (("2020-01-01", "2023-01-01"), ("2023-01-01", "2024-01-01")),
         "F4": (("2020-01-01", "2024-01-01"), ("2024-01-01", "2025-01-01")),
         "F5": (("2020-01-01", "2025-01-01"), ("2025-01-01", "2026-01-01"))}


def availability(t, avail, openm) -> dict:
    out = {"first_available": str(pd.Timestamp(int(t[np.argmax(avail)]), tz="UTC")) if avail.any() else None,
           "available_minutes": int(avail.sum()), "grid_minutes": int(len(t)),
           "open_while_unavailable_minutes": int((openm & ~avail).sum())}
    for f, wins in FOLDS.items():
        for nm, (a, b) in zip(("train", "val"), wins):
            lo = np.searchsorted(t, pd.Timestamp(a, tz="UTC").value)
            hi = np.searchsorted(t, pd.Timestamp(b, tz="UTC").value)
            out[f"{f}_{nm}_available_pct"] = round(100 * float(avail[lo:hi].mean()), 3)
            out[f"{f}_{nm}_exposure_pct"] = round(100 * float(openm[lo:hi].mean()), 3)
    lo = np.searchsorted(t, sp.TEST_START.value)
    out["TEST_available_pct"] = round(100 * float(avail[lo:].mean()), 3)
    out["TEST_exposure_pct"] = round(100 * float(openm[lo:].mean()), 3)
    return out


def opp_of(opp: pd.DataFrame, ntr: int) -> np.ndarray:
    o = np.full(ntr, -1, np.int64)
    f = opp[opp.tid >= 0]
    o[f.tid.to_numpy(int)] = f.entry_opportunity_id.to_numpy()
    return o


def native_out(s, t_glob, segs, files, avail_rep, root=None):
    """segs: dict(t, tr, rows, sig, seg[, mm, e_min]) on their own minute arrays, mapped onto the global grid."""
    n = len(t_glob)
    rows_all, opps, R0, Rt, lvl, arm = [], [], np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan), np.zeros(n)
    side, pend = np.zeros(n, np.int8), np.zeros(n, bool)
    openm = np.zeros(n, bool)
    opp_min = np.full(n, -1, np.int32)
    mand = np.full(n, -1, np.int64)
    snap, aux = np.full(n, -1, np.int64), np.full(n, -1, np.int64)
    avail = np.zeros(n, bool)
    closed = np.full(n, -1, np.int64)
    base = 0
    for g in segs:
        off = int(np.searchsorted(t_glob, g["t"][0]))
        L = len(g["t"])
        if not np.array_equal(t_glob[off:off + L], g["t"]):
            raise Fail(f"{s} segment minutes not on the global grid")
        avail[off:off + L] = g["avail"] if "avail" in g else True
        side[off:off + L], pend[off:off + L] = g["sig"]["side"], g["sig"]["pending"]
        snap[off:off + L], aux[off:off + L] = g["sig"]["snap"], g["sig"]["aux"]
        tr = g["tr"].reset_index(drop=True)
        oid = base + np.arange(len(tr))
        rr = {k: v.copy() for k, v in g["rows"].items()}
        rr["minute"] = rr["minute"] + off
        rr["tid"] = rr["tid"] + base
        rows_all.append(rr)
        e, x = tr.e.to_numpy() + off, tr.x.to_numpy() + off
        closed[x] = oid                                       # exit fill minute (incl. data_end marks)
        for q in range(len(tr)):
            a, b = e[q], x[q]
            openm[a:b + 1] = True
            opp_min[a:b + 1] = oid[q]
            if "sched_exit_ns" in tr:
                mand[a:b + 1] = tr.sched_exit_ns.iloc[q]
            if "e0" in tr and np.isfinite(tr.e0.iloc[q]):
                R0_, R_, _, A_, L_ = sp.adaptive_path(g["mm"].open.to_numpy(float), g["mm"].high.to_numpy(float),
                                                      g["mm"].low.to_numpy(float), g["e_min"][:, int(tr.e_col.iloc[q])],
                                                      int(tr.e.iloc[q]), int(tr.x.iloc[q]), int(tr.side.iloc[q]),
                                                      float(tr.px_in.iloc[q]), float(tr.k.iloc[q]), float(tr.e0.iloc[q]))
                R0[a:b + 1], Rt[a:b + 1], arm[a:b + 1], lvl[a:b + 1] = R0_, R_, A_, L_
        tot = pd.DataFrame({"tid": g["rows"]["tid"], "g": g["rows"]["gross"], "f": g["rows"]["fee"],
                            "u": g["rows"]["funding"]}).groupby("tid").sum().reindex(tr.tid, fill_value=0.0)
        dec_t = (tr.decision_ns if "decision_ns" in tr else tr.entry_ns).to_numpy(np.int64)  # data closed before it
        o = pd.DataFrame({"entry_opportunity_id": oid.astype(np.int32), "decision_time": dec_t, "available_time": dec_t,
                          "side": tr.side.to_numpy(np.int8), "base_weight": tr.units.to_numpy(float),
                          "feature_snapshot_id": tr.snapshot_id.to_numpy(np.int64),
                          "base_mandatory_exit_time": tr.sched_exit_ns.to_numpy() if "sched_exit_ns" in tr else -1,
                          "segment": g.get("seg", "ALL"), "tid": oid, "filled": True,
                          "entry_idx": e, "entry_px": tr.px_in.to_numpy(), "exit_idx": x,
                          "exit_px": tr.px_out.to_numpy(), "exit_reason": tr.reason.to_numpy(),
                          "gross_pnl": tot.g.to_numpy(), "fee": tot.f.to_numpy(), "funding": tot.u.to_numpy()})
        o["net4"] = o.gross_pnl + o.fee + o.funding
        for c in ("candidate", "e0", "k", "e_col", "entry_kind", "position_id"):
            if c in tr:
                o[c] = tr[c].to_numpy()
        opps.append(o)
        base += len(tr)
    w = np.where(openm | (side != 0), 1.0, 0.0)
    rows = {k: np.concatenate([r[k] for r in rows_all]) for k in sp.ROW_COLS}
    opp = pd.concat(opps, ignore_index=True)
    gf = grid_frame(n, t_glob, s, 0, side_sig=side, w_sig=w, active=side != 0, pending=pend, open_=openm,
                    exit_pending=np.zeros(n, bool), opp=opp_min, mand=mand, R0=R0, Rt=Rt, lvl=lvl, armed=arm,
                    rows=rows, snap=snap, aux=aux, available=avail, closed=closed)
    avail_rep[s] = availability(t_glob, avail, openm)
    avail_rep[s].update(signal_active_ne_open_minutes=int(((side != 0) != openm).sum()),
                        pending_minutes=int(pend.sum()), distinct_snapshots=int(len(np.unique(snap[snap >= 0]))))
    files[f"common/{s}"] = write_sleeve((PRE if root is None else root) / "common" / s, gf, rows, t_glob, opp,
                                        np.arange(len(opp)))
    log(f"wrote {s}")
    return gf


def stop_check(X) -> dict:
    """Stop/trail exits: exit price == min/max(open, reconstructed level) inside the exit minute."""
    out = {}
    for (s, _), d in X["sleeves"].items():
        n_chk = n_ok = 0
        for g in d["segs"]:
            o, h, l = (g["mm"][c].to_numpy(float) for c in ("open", "high", "low"))
            for r in g["tr"].itertuples():
                if r.reason not in ("stop", "trail") or not np.isfinite(r.e0):
                    continue
                _, _, _, _, L_ = sp.adaptive_path(o, h, l, g["e_min"][:, int(r.e_col)], int(r.e), int(r.x), int(r.side),
                                                  float(r.px_in), float(r.k), float(r.e0))
                lv = L_[-1]
                want = o[r.x] if (r.side == 1 and o[r.x] <= lv) or (r.side == -1 and o[r.x] >= lv) else lv
                if int(r.x) == int(r.e):
                    want = r.px_in * np.exp(-r.side * min(r.k * r.e0, 300) / 1e4)
                n_chk += 1
                n_ok += bool(abs(want - r.px_out) <= 1e-6 * r.px_out)
        unmatched = sum(int((g["tr"].entry_kind == "unmatched").sum()) for g in d["segs"])
        out[s] = {"stop_trail_exits": n_chk, "level_matches": n_ok, "unmatched_rows": unmatched}
    return out


# ================================================================ main
def cmd_precompute(args) -> None:
    fz = check_freeze()
    rec: dict = {}
    t_start = time.time()
    try:
        G = g3_family(args, rec) if "g3" in args.only else None
        C = c_family(args, rec) if "c" in args.only else None
        X = ax_family(args, rec) if "ax" in args.only else None
        if G and C:
            ov = np.searchsorted(G["m"].t, C["mk"]["t"][0])
            same = np.array_equal(G["m"].t[ov:ov + len(C["mk"]["t"])], C["mk"]["t"])
            rec["market_C_vs_G3"] = {"minutes_equal": bool(same), "close_max_abs": float(np.abs(
                G["m"].c[ov:ov + len(C["mk"]["t"])] - C["mk"]["c"]).max()) if same else None}
        if G and X:
            for g in X["sleeves"][("B3_AXC0", "native")]["segs"]:
                ov = int(np.searchsorted(G["m"].t, g["t"][0]))
                sl = slice(ov, ov + len(g["t"]))
                same = np.array_equal(G["m"].t[sl], g["t"])
                rec[f"market_AX_{g['seg']}_vs_G3"] = {"minutes_equal": bool(same), **({
                    f"{c}_max_abs": float(np.abs(getattr(G["m"], c)[sl] - g["mm"][n_].to_numpy(float)).max())
                    for c, n_ in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close"))} if same else {})}
        cf = counterfactual(args, G, C, X, rec)
        stops = stop_check(X) if X else {}
    except Fail as e:
        dump(OUT / "precompute_FAIL.json", {"failed": str(e), "records": rec})
        raise SystemExit(f"PARITY FAIL: {e}")
    files, avail_rep = {}, {}
    t_glob = G["m"].t
    out_g3(G, files, avail_rep)
    mk_common = pd.DataFrame({"minute_time": t_glob, "available_time": t_glob + sp.MIN,
                              **{k: G["mk"][k] for k in ("o", "h", "l", "c")}})
    files["common/market"] = write_part(mk_common, PRE / "common" / "market", "market")
    files["common/funding_g3"] = write_part(pd.DataFrame({"minute_time": G["m"].ft, "rate": G["m"].fr}),
                                            PRE / "common" / "funding", "funding_g3")
    files["signals/g3_state"], files["signals/lbr_features"] = g3_signal_files(G)
    if C:
        for s in ("C1v2", "C4v2"):
            d = C["sleeves"][(s, "native")]
            native_out(s, t_glob, [dict(t=C["mk"]["t"], tr=d["tr"], rows=d["rows"], sig=d["sig"], seg="ALL",
                                        avail=d["avail"])],
                       files, avail_rep)
        files["common/funding_c"] = write_part(pd.DataFrame({"minute_time": C["ft"], "rate": C["fr"]}),
                                               PRE / "common" / "funding", "funding_c")
        for s, (tf, sf) in C["f_events"].items():
            tf = pd.DatetimeIndex(tf).as_unit("ns").asi8
            files[f"signals/{s}_F"] = write_part(pd.DataFrame({"decision_time": tf, "available_time": tf,
                                                               "side": np.asarray(sf, np.int8)}),
                                                 PRE / "signals", f"{s}_F", "decision_time")
    if X:
        for s in ("B3_AXC0", "K04_AXC0"):
            segs = X["sleeves"][(s, "native")]["segs"]
            native_out(s, t_glob, segs, files, avail_rep)
            tabs = []
            for g in segs:
                tb = g["table"].reset_index(drop=True)
                dt = pd.DatetimeIndex(tb.decision_time).as_unit("ns").asi8
                w = (dt >= g["a"].value) & (dt < g["b"].value)
                ki = np.searchsorted(g["t"], dt[w])
                tabs.append(pd.DataFrame({"decision_time": dt[w], "available_time": dt[w], "segment": g["seg"],
                                          "feature_snapshot_id": np.flatnonzero(w), "component": tb.component[w].to_numpy(),
                                          "side": tb.side[w].to_numpy(np.int8), "allow_entry": tb.allow_entry[w].to_numpy(),
                                          "e0_bps": tb.e0_bps[w].to_numpy(float),
                                          "k": g["km"][np.minimum(ki, len(g["km"]) - 1)]}))
            files[f"signals/{s}_table"] = write_part(pd.concat(tabs, ignore_index=True), PRE / "signals",
                                                     f"{s}_table", "decision_time")
        for g in X["sleeves"][("B3_AXC0", "native")]["segs"]:
            files[f"common/funding_ax_{g['seg']}"] = write_part(pd.DataFrame({"minute_time": g["ft"], "rate": g["fr"]}),
                                                               PRE / "common" / "funding", f"funding_ax_{g['seg']}")
    total_bytes = sum(p.stat().st_size for p in PRE.rglob("*.parquet"))
    runtime = round(time.time() - t_start, 1)
    manifest = {
        "name": "RL allocator sleeve precompute (step 2, fix round 1)", "created_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_sha256": sha(FREEZE), "data_cutoff": fz["data_cutoff"], "frozen_hypothesis": fz["frozen_hypothesis"],
        "code_sha256": {"script": sha(Path(__file__)), "module": sha(ROOT / "btcusdt_quant/rl/sleeve_precompute.py")},
        "git_head": git("rev-parse", "HEAD"),
        "git_dirty_own_files": git("status", "--porcelain", "--", "btcusdt_quant/rl", "scripts/precompute_rl_allocator.py",
                                   "tests/rl"),
        "test_unlock": "--allow-test-parity (integrity parity only)", "runtime_sec": runtime, "parity": rec,
        "counterfactual": cf, "adaptive_stop_check": stops, "availability": avail_rep, "files": files,
        "total_bytes": total_bytes,
        "layout": {"common/<sleeve>": "B3_AXC0, K04_AXC0, C1v2, C4v2 (native fill, one cell)",
                   "g3_family/<cell>/<sleeve>": "G3_LONG, G3_SHORT, LBR_FUND x 6 cells",
                   "grid_<year>": "per-minute causal state + canonical P&L (observation-safe; row usable at T only if "
                                  "available_time <= T)",
                   "ledger_<year>": "per (minute, opportunity) realized canonical rows (replay input; observation-safe "
                                    "by available_time)",
                   "decisions_<year>": "canonical entry opportunities, decision-time columns only (observation-safe)",
                   "outcomes_<year>": "PRIVATE: fill result, realized exits, reasons, trade P&L (replay/accounting "
                                      "only; read_observation refuses it)",
                   "signals/": "decision-time source features (G3 state, LBR features, AXC0 tables, C F-leg events)",
                   "observation_cache_1h": "placeholder; step 3 writes out/rl_allocator_20261010/state/"},
        "test_guard": "read_partitioned/read_observation refuse *_2026 partitions without allow_test=True; the "
                      "precompute itself refuses to start without --allow-test-parity",
        "notes": ["G3/LBR grid minutes 2020-01-01..2026-10-07; available = source signal inputs ready",
                  "B3/K04 available 2023-09-01..2026-10-07 in two segments (native rolling-k segment ends with a "
                  "data_end close at 2025-12-31 23:59; TEST restarts flat); unavailable before 2023-09-01",
                  "terminal rule (all sleeves): a position open at a ledger end is marked to the last close and "
                  "charged the exit fee (G3/LBR: reserved 2 bps x w; native: 2 bps per side at the last close)",
                  "base_mandatory_exit_time: LBR exit decision bar close (activation + 2 bars), C max_hold expiry; "
                  "G3 and B3/K04 -1; never the realized exit",
                  "C decision_time = available_time = fill minute T (R2-37 zero-latency contract): observations at "
                  "T must exclude the minute-T market row",
                  "native pending: C has none (fill at the decision minute open); B3/K04 pending = decision minute "
                  "while flat (market order executes at the next open)"]}
    dump(PRE / ("manifest.json" if args.only == {"g3", "c", "ax"} else "manifest_partial.json"), manifest)
    (PRE / "observation_cache_1h").mkdir(exist_ok=True)
    if not args.no_registry and args.only == {"g3", "c", "ax"}:
        registry.record(REGISTRY, {"experiment": "RL allocator sleeve precompute (steps 1-2, fix round 1)",
                                   "role": "precompute", "n_trials": 0, "n_simulations": 0,
                                   "config": {"freeze_sha256": sha(FREEZE), "sleeves": list(SLEEVES),
                                              "cells": [CELL_TAG[c] for c in CELLS], "paths": args.paths,
                                              "data_cutoff": fz["data_cutoff"], "round": "fix1"},
                                   "input_hashes": {k: v["sha256"] for k, v in fz["source_hashes"].items()},
                                   "result_summary": {k: {x: v.get(x) for x in ("DEV-FULL_net4", "TEST_net4")}
                                                      for k, v in rec.items() if isinstance(v, dict)}})
    log(f"done runtime {runtime}s bytes {total_bytes}")


def g3_signal_files(G) -> tuple[dict, dict]:
    st, f = G["st"], G["f"]
    T = st["T"]
    g3 = pd.DataFrame({"decision_time": T, "available_time": T, "feature_snapshot_id": np.arange(len(T)),
                       "score_F": st["score"][(6, 18, 42)], "score_S": st["score"][(42, 168, 504)],
                       "svi42": st["svi"][42], "svi180": st["svi"][180], "sigma_ann": st["sig"],
                       "w_W180_P65": st["w"]["W180-P65"], "w_V_ENS": st["w"]["V-ENS"], "funding_z90": st["fz"],
                       "funding_rate_last": st["fund"]})
    ev = G["lbr_events"]
    armed, age = np.zeros(len(T), np.int8), np.full(len(T), np.nan)
    for e in ev:
        end = e["end_idx"] if e["end_idx"] >= 0 else len(T)
        armed[e["arm_idx"]:end] = 1
        age[e["arm_idx"]:end] = np.arange(end - e["arm_idx"])
    lbr = pd.DataFrame({"decision_time": T, "available_time": T, "feature_snapshot_id": np.arange(len(T)),
                        "zr4": f["zr4"], "ztaker": f["ztaker"], "zprem": f["zprem"], "zfund": f["zfund"], "w": f["w"],
                        "armed": armed, "armed_age_bars": age})
    return (write_part(g3, PRE / "signals", "g3_state", "decision_time"),
            write_part(lbr, PRE / "signals", "lbr_features", "decision_time"))


# ================================================================ step 3: state store
STATE = OUT / "state"
NATIVE_DIRS = {s: ("common", s) for s in NATIVE}
G3_SIG_COLS = ("score_F", "score_S", "svi42", "svi180", "sigma_ann", "w_W180_P65", "w_V_ENS", "funding_z90")
AX_FAST_COLS = ("M", "L", "e1_volume_z", "e1_breakout_bps", "a2_breakout_hi_bps", "a2_breakout_lo_bps", "f3_ls_pos",
                "f3w_ls_pos")
SEQ_COLUMNS = ("ret_1h", "range_1h", "logvol_1h", "taker_share_1h") + tuple(f"{s}_net4_1h" for s in SLEEVES)
LBR_SIG_COLS = ("zr4", "ztaker", "zprem", "zfund", "w", "armed", "armed_age_bars")


def _sig(stem: str, allow_test: bool, T_max: int) -> pd.DataFrame:
    years = set(range(2020, pd.Timestamp(int(T_max), tz="UTC").year + 1))
    f = sp.read_partitioned(PRE / "signals", stem, allow_test=allow_test, time_col="decision_time", years=years)
    return f[f.available_time.to_numpy(np.int64) <= T_max].sort_values("available_time", kind="stable") \
        .reset_index(drop=True)


def _sleeve_inputs(rel: Path, T_max: int, allow_test: bool):
    gcols = [c for c in sp.OBS_COLUMNS["grid"] if c not in ("sleeve_id", "exec_cell")]
    g = sp.read_observation(rel, "grid", T_max, columns=gcols, allow_test=allow_test)
    led = sp.read_observation(rel, "ledger", T_max, allow_test=allow_test)
    return g, led


def state_inputs(allow_test: bool, T_max: int, tamper_cut: int | None = None) -> dict:
    """Raw inputs truncated at T_max (and optionally tampered strictly after tamper_cut)."""
    b2 = load("nm_b2_state", "out/run_new_model_batch2_20261010.py")
    minutes, met, prem, funding = b2.load_all()
    t = minutes.open_time.array.asi8.copy()
    keep = t + sp.MIN <= T_max
    mk = {"t": t[keep], **{k: minutes[c].to_numpy(float)[keep] for k, c in
                           (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close"), ("v", "volume"),
                            ("tb", "taker_buy_base_volume"))}}
    met = met.assign(available_time=met.available_time.array.asi8)
    prem = prem.assign(available_time=prem.available_time.array.asi8)
    met = met[met.available_time <= T_max].reset_index(drop=True)
    prem = prem[prem.available_time <= T_max].reset_index(drop=True)
    ft, fr = funding.time.array.asi8.copy(), funding.rate.to_numpy(float)
    fk = ft < T_max
    ft, fr = ft[fk], fr[fk]
    sp.guard_times(mk["t"], allow_test, "state market")
    if tamper_cut is not None:
        aft = mk["t"] >= tamper_cut                          # includes the minute-T row (minute_time == T)
        for k in ("o", "h", "l", "c", "v", "tb"):
            mk[k] = np.where(aft, mk[k] * 1.7, mk[k])
        met.loc[met.available_time > tamper_cut, ["oi", "global_ls", "top_ls", "taker_lsr"]] *= 1.7
        prem.loc[prem.available_time > tamper_cut, "premium"] *= 1.7
        fr = np.where(ft >= tamper_cut, fr * 1.7, fr)
    return {"mk": mk, "met": met, "prem": prem, "ft": ft, "fr": fr}


def _tamper_frame(f: pd.DataFrame, cut: int, cols) -> pd.DataFrame:
    f = f.copy()
    m = f.available_time.to_numpy(np.int64) > cut
    for c in cols:
        if c not in f:
            continue
        x = f[c]
        if x.dtype == bool:
            f.loc[m, c] = ~x[m]
        elif np.issubdtype(x.dtype, np.integer):
            f.loc[m, c] = x[m] + 1
        else:
            f.loc[m, c] = x[m] * 1.7 + 0.3
    return f


def build_state_frames(inp: dict, T: np.ndarray, allow_test: bool, T_max: int, cells, tamper_cut=None) -> pd.DataFrame:
    from btcusdt_quant.rl import allocator_state as ast
    mk = inp["mk"]
    common = ast.common_channels(mk, inp["met"], inp["prem"], inp["ft"], inp["fr"], T)
    tam = (lambda f, cols: _tamper_frame(f, tamper_cut, cols)) if tamper_cut is not None else (lambda f, cols: f)
    g3s = tam(_sig("g3_state", allow_test, T_max), G3_SIG_COLS)
    lbr = tam(_sig("lbr_features", allow_test, T_max), LBR_SIG_COLS)
    parts = [common, ast.asof_features(g3s, T, G3_SIG_COLS, "g3_"), ast.asof_features(lbr, T, LBR_SIG_COLS, "lbr_")]
    for s in ("B3_AXC0", "K04_AXC0"):
        tab = tam(_sig(f"{s}_table", allow_test, T_max), ("e0_bps", "k", "side", "allow_entry"))
        parts.append(ast.ax_table_features(tab, T, f"{s}_"))
    for s in ("C1v2", "C4v2"):
        parts.append(ast.asof_features(tam(_sig(f"{s}_F", allow_test, T_max), ("side",)), T, ("side",), f"{s}_F_"))
        lv = tam(_sig(f"{s}_F_levels", allow_test, T_max), ("ls", "ls_pos"))
        parts.append(ast.asof_features(lv, T, ("ls_pos",), f"{s}_Flv_").drop(columns=f"{s}_Flv_age_h"))
    e1 = tam(_sig("C_E1", allow_test, T_max), ("volume_z", "breakout_bps"))
    parts.append(ast.asof_features(e1, T, ("volume_z", "breakout_bps"), "c_e1_").drop(columns="c_e1_age_h"))
    axf = tam(_sig("AX_fast", allow_test, T_max), AX_FAST_COLS)
    parts.append(ast.asof_features(axf, T, AX_FAST_COLS, "ax_"))
    gcols_t = [c for c in sp.OBS_COLUMNS["grid"] if c not in ("minute_time", "available_time", "sleeve_id", "exec_cell")]
    lcols_t = ("gross_pnl", "fee", "funding", "net4")
    for s in NATIVE:
        g, led = _sleeve_inputs(PRE / "common" / s, T_max, allow_test)
        g, led = tam(g, gcols_t), tam(led, lcols_t)
        parts.append(drop_na_channels(s, ast.sleeve_channels(s, g, led, mk["c"], T)))
        log(f"state {s}")
    base = neutralize(pd.concat(parts, axis=1), NATIVE)
    out = []
    for tag in cells:
        cp = []
        for s in G3_FAMILY:
            g, led = _sleeve_inputs(PRE / "g3_family" / tag / s, T_max, allow_test)
            g, led = tam(g, gcols_t), tam(led, lcols_t)
            cp.append(drop_na_channels(s, ast.sleeve_channels(s, g, led, mk["c"], T)))
        f = neutralize(pd.concat([base] + cp, axis=1), G3_FAMILY)
        f.insert(1, "exec_cell", tag)
        out.append(f)
        log(f"state cell {tag}")
    return pd.concat(out, ignore_index=True)


def neutralize(f: pd.DataFrame, sleeves) -> pd.DataFrame:
    """Unavailable sleeve: every `<sleeve>_*` channel (incl. its source signal snapshot) is neutral: flags/ages 0,
    other numbers NaN (masked downstream)."""
    from btcusdt_quant.rl import allocator_state as ast
    zero = tuple(ast.SLEEVE_FLAGS) + ("base_side", "base_weight", "signal_age_h", "pending_age_h", "hold_age_h")
    for s in sleeves:
        off = f[f"{s}_available"].to_numpy() == 0
        for c in f.columns:
            if c.startswith(s + "_") and c != f"{s}_available":
                x = f[c].to_numpy(float).copy()
                x[off] = 0.0 if c[len(s) + 1:] in zero else np.nan
                f[c] = x
    return f


def contamination(f: pd.DataFrame) -> dict:
    """Rows where a sleeve is unavailable but any of its channels is non-neutral (flag != 0 or finite number)."""
    out = {}
    for s in SLEEVES:
        av = f[f"{s}_available"].to_numpy() == 0
        cols = [c for c in f.columns if c.startswith(s + "_") and c != f"{s}_available"]
        x = f.loc[av, cols].to_numpy(float)
        out[s] = int(((np.isfinite(x)) & (x != 0)).any(axis=1).sum())
    return out


def drop_na_channels(s: str, f: pd.DataFrame) -> pd.DataFrame:
    """Structurally inapplicable channels (static rule, identical for DEV/TEST builds)."""
    drop = []
    if s not in ("B3_AXC0", "K04_AXC0"):
        drop += [f"{s}_{c}" for c in ("R0_bps", "Rt_over_R0", "stop_dist_bps", "trail_armed")]
    if s not in ("LBR_FUND", "C1v2", "C4v2"):
        drop.append(f"{s}_to_mandatory_exit_h")
    if s not in G3_FAMILY:
        drop.append(f"{s}_exit_pending")
    return f.drop(columns=drop)


def frames_equal(a: pd.DataFrame, b: pd.DataFrame) -> tuple[bool, list]:
    bad = [c for c in a.columns if not (a[c].dtype == object and a[c].equals(b[c]))
           and not (a[c].dtype != object and np.array_equal(a[c].to_numpy(), b[c].to_numpy(), equal_nan=True))]
    return not bad, bad


def cmd_state(args) -> None:
    from btcusdt_quant.rl import allocator_state as ast
    if not (PRE / "manifest.json").exists():
        raise SystemExit("run precompute first")
    t0 = time.time()
    STATE.mkdir(parents=True, exist_ok=True)
    cells = [CELL_TAG[c] for c in CELLS]
    dev_end = sp.TEST_START.value - ast.HOUR                     # last DEV decision time 2025-12-31 23:00
    start = pd.Timestamp("2020-01-01", tz="UTC")
    T_dev = ast.hour_grid(start, pd.Timestamp(dev_end, tz="UTC"))
    inp = state_inputs(False, dev_end)
    dev = build_state_frames(inp, T_dev, False, dev_end, cells)
    log(f"DEV state rows {len(dev)}")
    rep = {"dev_rows_1h": int(len(dev)), "T_dev": [str(pd.Timestamp(T_dev[0], tz="UTC")),
                                                  str(pd.Timestamp(T_dev[-1], tz="UTC"))],
           "columns": list(dev.columns)}
    # real-data future tamper (cut 2025-06-01, primary cell): rows T <= cut identical
    cut = pd.Timestamp("2025-06-01", tz="UTC").value
    Tw = T_dev[(T_dev > cut - 10 * 86400 * 10**9) & (T_dev <= cut + 5 * 86400 * 10**9)]
    a = build_state_frames(state_inputs(False, dev_end), Tw, False, dev_end, [CELL_TAG[PRIMARY]])
    b = build_state_frames(state_inputs(False, dev_end, tamper_cut=cut), Tw, False, dev_end, [CELL_TAG[PRIMARY]],
                           tamper_cut=cut)
    pre = a["T"].to_numpy() <= cut
    eq, bad = frames_equal(a[pre].reset_index(drop=True), b[pre].reset_index(drop=True))
    post_changed = [c for c in a.columns if c not in ("T", "exec_cell") and not np.array_equal(
        a.loc[~pre, c].to_numpy(), b.loc[~pre, c].to_numpy(), equal_nan=True)]
    rep["tamper"] = {"cut": "2025-06-01", "rows_compared": int(pre.sum()), "equal": eq, "diff_cols": bad,
                     "cols_changed_after_cut": len(post_changed)}
    if not eq:
        raise SystemExit(f"STATE TAMPER FAIL {bad}")
    log(f"tamper ok {rep['tamper']}")
    rep["usable_from"] = USABLE_FROM
    rep["folds"] = {f: {"train": list(w[0]), "val": list(w[1])} for f, w in FOLDS_A2.items()}
    rep["rows_before_usable_1h"] = int((dev["T"].to_numpy() < pd.Timestamp(USABLE_FROM, tz="UTC").value).sum())
    prim = dev[dev.exec_cell == CELL_TAG[PRIMARY]]
    Tp = prim["T"].to_numpy(np.int64)
    rep["availability_A2_1h"] = {}
    for s_ in SLEEVES:
        av_ = prim[f"{s_}_available"].to_numpy() == 1
        op_ = prim[f"{s_}_open"].to_numpy() == 1
        r_ = {}
        for f, wins in FOLDS_A2.items():
            for nm, (a_, b_) in zip(("train", "val"), wins):
                k_ = (Tp > pd.Timestamp(a_, tz="UTC").value) & (Tp <= pd.Timestamp(b_, tz="UTC").value)
                r_[f"{f}_{nm}_available_pct"] = round(100 * float(av_[k_].mean()), 3)
                r_[f"{f}_{nm}_open_pct"] = round(100 * float(op_[k_].mean()), 3)
        rep["availability_A2_1h"][s_] = r_
    rep["contaminated_unavailable_rows"] = contamination(dev)
    if any(rep["contaminated_unavailable_rows"].values()):
        raise SystemExit(f"STATE CONTAMINATION {rep['contaminated_unavailable_rows']}")
    h = ast.history(dev, SEQ_COLUMNS, ast.SEQ_LEN, query=dev.groupby("exec_cell").head(1))
    rep["history_first_row_per_cell_nonnan_steps"] = int(np.isfinite(h[:, :-1, :]).sum())
    rep["seq_columns"] = list(SEQ_COLUMNS)
    dev.to_parquet(STATE / "state_1h.parquet", index=False, compression="zstd")
    dev4 = dev[dev["T"].to_numpy() % (4 * ast.HOUR) == 0].reset_index(drop=True)
    dev4.to_parquet(STATE / "state_4h.parquet", index=False, compression="zstd")
    norms = {}
    for nm, fr_ in (("1h", dev), ("4h", dev4)):
        norms[nm] = {f: ast.fit_normalizer(fr_, *FOLDS_A2[f][0]) for f in FOLDS_A2}
        orders = {f: ast.feature_order(fr_.columns, n_) for f, n_ in norms[nm].items()}
        if len({tuple(o) for o in orders.values()}) != 1:
            raise SystemExit(f"feature order differs across folds ({nm})")
        norms[nm]["feature_order"] = orders["F1"]
        rep[f"features_{nm}"] = {"scaled": len(norms[nm]["F1"]), "masks": len(norms[nm]["F1"]),
                                 "observation_columns": len(orders["F1"])}
    dump(STATE / "normalizers.json", norms)
    if args.allow_test_parity:
        sp.require_unlock(True, "TEST state rows")
        T_all = ast.hour_grid(start, sp.DATA_END)
        full = build_state_frames(state_inputs(True, sp.DATA_END.value), T_all, True, sp.DATA_END.value, cells)
        fd = full[full["T"].to_numpy() <= dev_end].reset_index(drop=True)
        eq2, bad2 = frames_equal(dev.sort_values(["exec_cell", "T"]).reset_index(drop=True),
                                 fd.sort_values(["exec_cell", "T"]).reset_index(drop=True))
        rep["dev_prefix_vs_full"] = {"equal": eq2, "diff_cols": bad2}
        if not eq2:
            raise SystemExit(f"STATE PREFIX FAIL {bad2}")
        test = full[full["T"].to_numpy() > dev_end].reset_index(drop=True)
        test.to_parquet(STATE / "state_1h_TEST.parquet", index=False, compression="zstd")
        test[test["T"].to_numpy() % (4 * ast.HOUR) == 0].reset_index(drop=True).to_parquet(
            STATE / "state_4h_TEST.parquet", index=False, compression="zstd")
        rep["test_rows_1h"] = int(len(test))
    rep["files"] = {p.name: {"bytes": p.stat().st_size, "sha256": sha(p)} for p in sorted(STATE.glob("*"))
                    if p.is_file() and p.name != "manifest.json"}
    rep.update(created_utc=datetime.now(timezone.utc).isoformat(), git_head=git("rev-parse", "HEAD"),
               code_sha256={"script": sha(Path(__file__)), "allocator_state": sha(ROOT / "btcusdt_quant/rl/allocator_state.py"),
                            "sleeve_precompute": sha(ROOT / "btcusdt_quant/rl/sleeve_precompute.py")},
               precompute_manifest_sha256=sha(PRE / "manifest.json"), runtime_sec=round(time.time() - t0, 1),
               rules={"market": "minute_time + 1m <= T (minute-T row excluded)", "grid/ledger/signals": "available_time <= T",
                      "metrics/premium": "available_time <= T", "funding": "funding_time < T",
                      "normalizer": "median/IQR on fold train rows only", "history": "allocator_state.history 32 x 1h",
                      "dev_build": "inputs truncated at the last DEV T before any computation"})
    dump(STATE / "manifest.json", rep)
    log(f"state done {rep['runtime_sec']}s")


# ================================================================ freeze amendment A1 (Codex review fix round 1)
AMEND = OUT / "freeze_amendment_A1.json"
ARCHIVE = OUT / "inputs_archive"


def cmd_amend(_args) -> None:
    """Write-once amendment: observation contract, renames, TEST unlock, terminal rule, availability, provenance.
    Untracked frozen inputs are copied byte-exact into a content-addressed archive (inputs_archive/<sha256>)."""
    import shutil
    if AMEND.exists():
        raise SystemExit(f"{AMEND} exists (write-once)")
    fz = check_freeze()
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    inputs = {}
    for k, v in fz["source_hashes"].items():
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", v["path"]], cwd=ROOT,
                                 capture_output=True).returncode == 0
        rec = {"path": v["path"], "sha256": v["sha256"], "tracked": tracked}
        if tracked:
            rec["git_index_blob"] = git("ls-files", "-s", v["path"]).split()[1]
        else:
            dst = ARCHIVE / v["sha256"]
            if not dst.exists():
                shutil.copyfile(ROOT / v["path"], dst)
            if sha(dst) != v["sha256"]:
                raise SystemExit(f"archive copy mismatch {k}")
            rec["archive"] = str(dst.relative_to(ROOT)).replace("\\", "/")
        inputs[k] = rec
    doc = {
        "id": "A1", "status": "FROZEN", "created_utc": datetime.now(timezone.utc).isoformat(),
        "amends": {"freeze": "out/rl_allocator_20261010/freeze.json", "freeze_sha256_lf": sha(FREEZE),
                   "freeze_sha256_crlf_as_written": "78c5f91d1cb6571c945eb90316f1d5fed51f46fa96e5dfbb07bd185ea96ca3e4",
                   "freeze_commit": "3c14ff6", "note": "same content; LF is canonical (git blob / fresh checkout)"},
        "review": {"codex_session": "01a125b7-1030-7b91-998c-890070158908", "verdict": "conditional NO-GO Step 4; "
                   "Step 3 limited GO"},
        "observation_contract": {
            "allowlist": {k: list(v) for k, v in sp.OBS_COLUMNS.items()},
            "private": "outcomes_<year> (filled, tid, entry_idx/px, exit_*, exit_reason, trade P&L, e0/k/position "
                       "metadata): replay/accounting only; read_observation refuses it",
            "row_rule": "a row is observable at T only if available_time <= T; minute market rows only if "
                        "minute_time + 1m <= T (the minute-T row is excluded, incl. C zero-latency decisions); "
                        "funding only if funding_time < T",
            "enforced_by": "sleeve_precompute.obs_columns/read_observation; allocator_state.sleeve_channels"},
        "renames": {"base_exit_sched_time": "base_mandatory_exit_time (LBR activation + 2 bars exit decision close, "
                                            "C max_hold expiry; G3, B3/K04 = -1; never the realized exit)",
                    "opportunities_<year>": "decisions_<year> (observable) + outcomes_<year> (private)"},
        "native_timelines": {
            "C1v2/C4v2": "signal = latest decision of the F leg (F3/V5 5 m LS events | F3-w30/V0 hourly) and of E1/V1a "
                         "(minute) with decision_time <= minute open; book side = F leg if nonzero else E1; "
                         "pending none (fill at the decision minute open); snapshot = F-leg event index, aux = E1 "
                         "event index",
            "B3_AXC0/K04_AXC0": "signal = first enterable row (allow_entry, side != 0, finite E0 > 0) of the latest "
                                "15 m decision group; pending = decision minute while flat (market order fills at "
                                "the next open); snapshot = first table row of the latest group (segment table "
                                "index)",
            "closed_opp_id": "grid marks the exit-fill minute of each closed opportunity (causal trade-close flag)"},
        "availability": {
            "G3_LONG/G3_SHORT/LBR_FUND": "available = the source signal inputs of the latest 4h decision are ready",
            "C1v2/C4v2": "available from the first real LS minute + 720 h F-leg warm-up (before 2020-09 the legacy "
                         "LS cache is zero-filled; ledger/parity unchanged, those minutes are masked)",
            "B3_AXC0/K04_AXC0": "available 2023-09-01..2026-10-07 only; F1/F2 0 %, F3 val 2023-09.. only",
            "reporting": "per sleeve and fold availability/exposure in precompute manifest; early folds are never "
                         "described as a 7-sleeve comparison"},
        "terminal_rule": "every sleeve: a position open at a ledger end is marked to the last close and charged its "
                         "exit fee (G3/LBR reserved 2 bps x w; native 2 bps per side). B3/K04 native segment ends "
                         "2025-12-31 23:59 (data_end close; 0 such closes B3/K04 in DEV), TEST restarts flat. Step 4 "
                         "episode ends use the same rule.",
        "test_unlock": "scripts/precompute_rl_allocator.py precompute refuses to start without --allow-test-parity; "
                       "state writes TEST rows only with it; read_partitioned/read_observation need allow_test",
        "line_endings": ".gitattributes pins eol=lf for the RL allocator code/tests; manifests record LF-file sha256 "
                        "and the git commit of the code that produced them",
        "inputs": inputs,
        "inputs_note": "sha256 = bytes hashed at freeze time (working tree). Untracked inputs: byte-exact archive "
                       "copy (tracked in git). Tracked inputs: git index blob id at amendment time."}
    dump(AMEND, doc)
    log(f"amendment written sha256 {sha(AMEND)}; archived {sum('archive' in v for v in inputs.values())} files")


# ================================================================ design section 2 signal features (fix round 2)
def cmd_signals(args) -> None:
    """Causal decision-time features of the native sleeves (design section 2), each verified to reproduce the source
    side exactly before it is written. Adds files under precompute/signals/; precompute ledgers/parity untouched."""
    sp.require_unlock(args.allow_test_parity, "signal snapshots (rows through 2026-10-07)")
    t0 = time.time()
    rep: dict = {}
    files: dict = {}
    # ---------------- C1v2 / C4v2: F-leg LS quantile position, E1/V1a volume z and breakout distance
    F = load("sim_r2_56_fix1_sig", "scripts/sim_r2_56_fix1.py")
    r237 = F.r237
    F.verify_inputs()
    rows_ls, _ = F.ls_rows()
    market, features, *_ = F.inputs(rows_ls)
    bars = r237.hourly_bars(market)
    full = {**r237.build_f3_signals(market, features, bars)[1], **r237.build_e1_signals(market, bars)[1]}
    fl = c_f_levels(market, features, bars)
    for s, key in C_LEGS.items():
        lv = fl[key]
        ref_t, ref_s = full[key]
        ok = np.array_equal(pd.DatetimeIndex(ref_t).as_unit("ns").asi8, lv["decision_time"]) and \
            np.array_equal(np.asarray(ref_s), lv["side"])
        rep[f"{s}_F_side_reproduced"] = bool(ok)
        if not ok:
            raise SystemExit(f"{s} F-leg level copy does not reproduce the source side")
        f = pd.DataFrame(lv)
        f["available_time"] = f.decision_time
        files[f"signals/{s}_F_levels"] = write_part(f, PRE / "signals", f"{s}_F_levels", "decision_time")
    e1 = c_e1_features(market, bars)
    ref_t, ref_s = full[("E1", "V1a")]
    ok = np.array_equal(pd.DatetimeIndex(ref_t).as_unit("ns").asi8, e1["decision_time"]) and \
        np.array_equal(np.asarray(ref_s), e1["side"])
    rep["C_E1_side_reproduced"] = bool(ok)
    if not ok:
        raise SystemExit("E1/V1a feature copy does not reproduce the source side")
    f = pd.DataFrame(e1)
    f["available_time"] = f.decision_time
    files["signals/C_E1"] = write_part(f, PRE / "signals", "C_E1", "decision_time")
    log("C features ok")
    # ---------------- B3 / K04: legacy.fast_signals indicators + M/L regime at each 15 m decision
    r255 = load("sim_r2_55_sig", "scripts/sim_r2_55.py")
    from btcusdt_quant.sim import regime as regime_mod, rolling
    from btcusdt_quant.sim.strategies import Context, legacy
    run = r255.stageb_runner()
    run.verify_snapshot(read_frames=False)
    ctx, _, _ = run.test_context()
    nctx = Context.load(end=rolling.END)
    segs = (("NATIVE", nctx, pd.Timestamp("2023-09-01", tz="UTC"), sp.TEST_START),
            ("TEST", ctx, sp.TEST_START, sp.DATA_END))
    parts = []
    for seg, c_, a, b in segs:
        fast = legacy.fast_signals(c_)
        times = pd.DatetimeIndex(fast.decision_time)
        M = regime_mod._asof(c_.regime, times, "M", pd.Timedelta(0))
        Lr = regime_mod._asof(c_.regime, times, "L", pd.Timedelta(0))
        w = ((times >= a) & (times < b))
        with np.errstate(invalid="ignore", divide="ignore"):
            out = pd.DataFrame({
                "decision_time": times.as_unit("ns").asi8[w], "segment": seg, "M": M[w], "L": Lr[w],
                "e1_volume_z": fast.ind_E1_volume_z.to_numpy(float)[w],
                "e1_breakout_bps": (np.log(fast.ind_E1_close / fast.ind_E1_high20) * 1e4).to_numpy(float)[w],
                "a2_breakout_hi_bps": (np.log(fast.ind_A2_close / fast.ind_A2_high55) * 1e4).to_numpy(float)[w],
                "a2_breakout_lo_bps": (np.log(fast.ind_A2_close / fast.ind_A2_low55) * 1e4).to_numpy(float)[w],
                "f3_ls_pos": ((fast.ind_F3_ls - fast.ind_F3_q10) / (fast.ind_F3_q90 - fast.ind_F3_q10)).to_numpy(float)[w],
                "f3w_ls_pos": ((fast.ind_F3_ls - fast.ind_F3W_q20) / (fast.ind_F3W_q80 - fast.ind_F3W_q20)).to_numpy(float)[w]})
        # verification: the K04 table side and the B3 M/L gate are exactly these inputs
        for i_ in ("K04", "B3"):
            tb = r255.ax_table(c_, i_, True)
            dt = pd.DatetimeIndex(tb.decision_time)
            sel = (dt >= a) & (dt < b)
            ml = pd.DataFrame({"decision_time": times.as_unit("ns").asi8, "M": M, "L": Lr,
                               "e1": fast["E1-15"].to_numpy()}).set_index("decision_time")
            j = ml.reindex(dt.as_unit("ns").asi8[sel])
            if i_ == "K04":
                okk = np.array_equal(tb.side.to_numpy()[sel], j.e1.to_numpy())
            else:
                fp = tb.component.isin([legacy.A2_30, legacy.E1_15]).to_numpy()[sel]
                with np.errstate(invalid="ignore"):
                    high = j.M.to_numpy() >= 2 / 3
                    low = (j.M.to_numpy() <= 1 / 3) & (j.L.to_numpy() < 2 / 3)
                okk = np.array_equal(tb.allow_entry.to_numpy(bool)[sel], np.where(fp, high, low))
            rep[f"{i_}_{seg}_inputs_reproduce_table"] = bool(okk)
            if not okk:
                raise SystemExit(f"{i_} {seg}: fast-signal/regime inputs do not reproduce the source table")
        parts.append(out)
        log(f"AX features {seg} ok")
    f = pd.concat(parts, ignore_index=True)
    f["available_time"] = f.decision_time
    files["signals/AX_fast"] = write_part(f, PRE / "signals", "AX_fast", "decision_time")
    dump(PRE / "signals" / "manifest.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(), "git_head": git("rev-parse", "HEAD"),
        "code_sha256": sha(Path(__file__)), "checks": rep, "files": files, "runtime_sec": round(time.time() - t0, 1),
        "rule": "every row: available_time = decision_time (source decision clock); state reads available_time <= T"})
    log(f"signals done {rep}")


def c_f_levels(market, features, bars) -> dict:
    """Copy of R2-37 build_f3_signals level arithmetic (verified against the source sides): per F-leg decision the LS
    value and its quantile band."""
    feature_times = pd.DatetimeIndex(features.open_time).as_unit("ns").asi8
    decisions = pd.DatetimeIndex(bars.decision_time)
    positions = np.searchsorted(feature_times + pd.Timedelta(minutes=5).value, decisions.as_unit("ns").asi8,
                                side="left") - 1
    hourly_ls = pd.Series(features.global_ls_account.to_numpy(float)[positions])
    create_mask = features.open_time.dt.minute.mod(5).eq(0)
    events = features.loc[create_mask, ["open_time", "global_ls_account"]].copy()
    events["available_time"] = events.open_time + pd.Timedelta(minutes=5)
    event_values = events.global_ls_account.reset_index(drop=True)
    out = {}
    for strategy, (window, minimum, ql, qh) in {"F3": (2_160, 720, .10, .90), "F3-w30": (720, 720, .20, .80)}.items():
        roll = hourly_ls.rolling(window, min_periods=minimum)
        lo, hi = roll.quantile(ql), roll.quantile(qh)
        out[(strategy, "V0")] = {"decision_time": decisions.as_unit("ns").asi8, "ls": hourly_ls.to_numpy(float),
                                 "q_lo": lo.to_numpy(float), "q_hi": hi.to_numpy(float),
                                 "side": c_sides(hourly_ls, lo, hi)}
        levels = pd.DataFrame({"decision_time": decisions, "lower": lo.to_numpy(float), "upper": hi.to_numpy(float)})
        fixed = pd.merge_asof(events[["available_time"]].sort_values("available_time"),
                              levels.sort_values("decision_time"), left_on="available_time", right_on="decision_time",
                              direction="backward")
        out[(strategy, "V5")] = {"decision_time": pd.DatetimeIndex(events.available_time).as_unit("ns").asi8,
                                 "ls": event_values.to_numpy(float), "q_lo": fixed.lower.to_numpy(float),
                                 "q_hi": fixed.upper.to_numpy(float),
                                 "side": c_sides(event_values, fixed.lower, fixed.upper)}
    for v in out.values():
        with np.errstate(invalid="ignore", divide="ignore"):
            v["ls_pos"] = (v["ls"] - v["q_lo"]) / (v["q_hi"] - v["q_lo"])
    return out


def c_sides(values, lower, upper) -> np.ndarray:
    result = np.zeros(len(values), np.int8)
    result[pd.Series(values).ge(pd.Series(np.asarray(upper, float))).fillna(False).to_numpy()] = -1
    result[pd.Series(values).le(pd.Series(np.asarray(lower, float))).fillna(False).to_numpy()] = 1
    return result


def c_e1_features(market, bars) -> dict:
    """Copy of R2-37 build_e1_signals V1a arithmetic (verified against the source side): partial-hour volume z and
    close vs the prior-20-bar high, per minute decision (minute open + 1 m)."""
    bar_index = bars.set_index("bar_start")
    hour_key = market.open_time.dt.floor("h")
    partial_volume = market.volume.groupby(hour_key, sort=False).cumsum().to_numpy(float)
    prior19_sum = bars.volume.shift().rolling(19).sum()
    prior19_sq = bars.volume.pow(2).shift().rolling(19).sum()
    prior_high = bars.high.rolling(20).max().shift()
    mapped_sum = hour_key.map(pd.Series(prior19_sum.to_numpy(), index=bar_index.index)).to_numpy(float)
    mapped_sq = hour_key.map(pd.Series(prior19_sq.to_numpy(), index=bar_index.index)).to_numpy(float)
    mapped_high = hour_key.map(pd.Series(prior_high.to_numpy(), index=bar_index.index)).to_numpy(float)
    mean_a = (mapped_sum + partial_volume) / 20
    variance_a = (mapped_sq + partial_volume ** 2) / 20 - mean_a ** 2
    with np.errstate(invalid="ignore", divide="ignore"):
        z_a = (partial_volume - mean_a) / np.sqrt(np.maximum(variance_a, 0))
        close = market.close.to_numpy(float)
        side = ((z_a > 3) & (close > mapped_high)).astype(np.int8)
        brk = np.log(close / mapped_high) * 1e4
    t = (pd.DatetimeIndex(market.open_time) + pd.Timedelta(minutes=1)).as_unit("ns").asi8
    return {"decision_time": t, "side": side, "volume_z": z_a, "breakout_bps": brk}


# ================================================================ step 4: env checks
def slow_tighten(cd, sd, k: int, x0: int, f: float, end: int):
    """Independent minute loop of the tightened R2-52A stop (reference for allocator_env.tighten_exit)."""
    s, e, px = int(sd.side[k]), int(sd.e[k]), float(sd.px_in[k])
    if x0 >= end or x0 <= e:
        return None
    best = px
    for i in range(e, x0):
        best = max(best, cd.h[i]) if s == 1 else min(best, cd.l[i])
    for i in range(x0, end):
        R = min(float(sd.R_t[i]), f * float(sd.R0[k]))
        hard = px * math.exp(-s * R / 1e4)
        lvl = hard
        if sd.armed[i - 1] == 1:
            trail = best * math.exp(-s * 0.5 * R / 1e4)
            if s * (trail - hard) > 0:
                lvl = trail
        if (s == 1 and cd.o[i] <= lvl) or (s == -1 and cd.o[i] >= lvl):
            return i, float(cd.o[i])
        if (s == 1 and cd.l[i] <= lvl) or (s == -1 and cd.h[i] >= lvl):
            return i, float(lvl)
        best = max(best, cd.h[i]) if s == 1 else min(best, cd.l[i])
    return None


def slow_replay(cd, env, book, b2) -> np.ndarray:
    """Rebuild the book's minute ledger from scratch: final exits re-derived from the action log with the source
    Batch-2 exit_fill (lin), next-open fills (log) and the independent stop loop; rows from lin_rows / log_rows."""
    from btcusdt_quant.rl import allocator_contracts as AC
    a0, b0 = int(env.mi[0]), int(env.mi[-1])
    out = np.zeros(b0 - a0)
    m = b2.Market(cd.t, cd.o, cd.h, cd.l, cd.c, np.ones(len(cd.t)), np.ones(len(cd.t)), np.zeros(0, np.int64),
                  np.zeros(0))
    for si, s in enumerate(AC.SLEEVES):
        sd = env.sd[si]
        ev = {}
        for (sj, q, act, minute, val) in book.events:
            if sj == si:
                ev.setdefault(q, []).append((act, minute, val))
        for q, mult in book.mult[si].items():
            if mult <= 0 or sd.e[q] < 0:
                continue
            end, px_end, tf = int(sd.x[q]), None, 1.0
            for act, a, val in ev.get(q, []):
                if act == "EXIT":
                    if sd.kind == "lin":
                        if not (sd.e[q] <= a - 1 < sd.xdec[q]) or a - 1 >= end:
                            continue
                        j, px = b2.exit_fill(m, a - 1, int(sd.side[q]), len(cd.t), sd.pen)
                        if j >= 0 and j <= end:
                            end, px_end = j, px
                    elif sd.e[q] < a <= end:
                        end, px_end = a, float(cd.o[a])
                elif act in AC.TIGHTEN_F:
                    tf = min(tf, val)
                    ch = slow_tighten(cd, sd, q, a, tf, end)
                    if ch is not None:
                        end, px_end = ch
            ft, fr = sd.fund[q]
            if px_end is None:
                lo, hi = sd.row_off[q], sd.row_off[q + 1]
                mins, net = sd.row_min[lo:hi], np.diff(sd.row_cs[lo + q:hi + q + 1])
            elif sd.kind == "lin":
                tr = pd.DataFrame({"tid": [0], "side": [sd.side[q]], "entry_weight_frozen": [sd.w[q]],
                                   "entry_idx": [sd.e[q]], "entry_px": [sd.px_in[q]], "open_at_end": [False],
                                   "exit_idx": [end], "exit_px": [px_end]})
                r = sp.lin_rows(cd.t, cd.c, tr, len(cd.t), ft, fr)
                mins, net = r["minute"], r["gross"] + r["fee"] + r["funding"]
            else:
                tr = pd.DataFrame({"tid": [0], "side": [sd.side[q]], "units": [1.0], "e": [sd.e[q]], "x": [end],
                                   "px_in": [sd.px_in[q]], "px_out": [px_end], "entry_ns": [cd.t[sd.e[q]]],
                                   "exit_ns": [cd.t[end]]})
                r = sp.log_rows(cd.t, cd.c, tr, 2.0, ft, fr)
                mins, net = r["minute"], r["gross"] + r["fee"] + r["funding"]
            w = (mins >= a0) & (mins < b0)
            np.add.at(out, mins[w] - a0, mult * net[w])
            if env.terminal_fee and end >= b0 and sd.e[q] < b0:
                out[b0 - 1 - a0] += mult * (-2.0 * sd.w[q] if sd.kind == "lin" else -2.0)
    return out


def random_action(rng, masks, p_exit=0.05, p_tight=0.15, p_cancel=0.2):
    from btcusdt_quant.rl import allocator_contracts as AC
    n = len(AC.SLEEVES)
    entry = tuple(int(rng.choice(np.flatnonzero(masks.entry[k]))) for k in range(n))
    pend = tuple(1 if masks.pending[k, 1] and rng.random() < p_cancel else 0 for k in range(n))
    op = []
    for k in range(n):
        legal = np.flatnonzero(masks.open[k])
        r = rng.random()
        if 3 in legal and r < p_exit:
            op.append(3)
        elif len([x for x in legal if x in (1, 2)]) and r < p_exit + p_tight:
            op.append(int(rng.choice([x for x in legal if x in (1, 2)])))
        else:
            op.append(0)
    return AC.Action(entry, pend, tuple(op))


def cmd_env_check(args) -> None:
    from btcusdt_quant.rl import allocator_contracts as AC, allocator_env as AE
    sp.require_unlock(args.allow_test_parity, "env parity on TEST windows")
    b2 = load("nm_b2_env", "out/run_new_model_batch2_20261010.py")
    pm = json.loads((PRE / "manifest.json").read_text(encoding="utf-8"))["parity"]
    ts = lambda x: pd.Timestamp(x, tz="UTC").value  # noqa: E731
    win = {"TEST": (ts("2026-01-01"), ts("2026-10-08")), "DEV-FULL": (ts("2020-01-01 01:00"), ts("2026-01-01")),
           "NATIVE_C": (ts("2023-01-01"), ts("2026-01-01")), "NATIVE_AX": (ts("2023-09-01"), ts("2026-01-01"))}
    rep: dict = {"parity": {}, "random": {}, "static": {}, "throughput": {}}
    t0 = time.time()
    worst_tot = worst_min = 0.0
    for cell in [CELL_TAG[c] for c in CELLS]:
        tl = time.time()
        cd = AE.load_cell(cell, fold="F4", allow_test=True)
        rep.setdefault("load_sec", {})[cell] = round(time.time() - tl, 2)
        for si, s in enumerate(AC.SLEEVES):
            if s not in G3_FAMILY and cell != CELL_TAG[PRIMARY]:
                continue                                      # native sleeves are cell independent
            checks = [("TEST", f"{s}|{cell if s in G3_FAMILY else 'native'}", "TEST_net4")]
            if s in G3_FAMILY:
                checks.append(("DEV-FULL", f"{s}|{cell}", "DEV-FULL_net4"))
            elif s.startswith("C"):
                checks.append(("NATIVE_C", f"{s}|native", "NATIVE_2023_2025_net4"))
            else:
                checks.append(("NATIVE_AX", f"{s}|native", "NATIVE_net4"))
            for wname, key, field_ in checks:
                env = AE.AllocatorEnv(cd, inherit_open=[s], terminal_fee=False, record_minutes=True,
                                      allow_pre_usable=True)
                obs = env.reset(*win[wname])
                tot = 0.0
                while True:
                    lv = [4 if (k == si and obs["masks"].entry[k, 4]) else 0 for k in range(len(AC.SLEEVES))]
                    obs, r, done, info = env.step(AC.Action(tuple(lv), (0,) * 7, (0,) * 7))
                    tot += info["net_rl"]
                    if done:
                        break
                ref = pm[key][field_]
                sl = slow_replay(cd, env, env.rl, b2)
                dmin = float(np.abs(sl - env.minutes["rl"]).max())
                rep["parity"][f"{s}|{cell}|{wname}"] = {"env": tot, "ref": ref, "abs_diff": abs(tot - ref),
                                                       "minute_vs_slow": dmin,
                                                       "steps_sum_vs_minutes": abs(tot - env.minutes["rl"].sum())}
                worst_tot, worst_min = max(worst_tot, abs(tot - ref)), max(worst_min, dmin)
        # random legal policies (all 7 sleeves) vs slow replay; static-equal actions -> reward 0
        rng = np.random.default_rng(SEED + CELLS.index(next(c for c in CELLS if CELL_TAG[c] == cell)))
        starts = [ts("2021-03-01"), ts("2022-06-01"), ts("2023-11-01"), ts("2024-08-01"), ts("2025-05-01"),
                  ts("2026-02-01")]
        rr = {"episodes": 0, "steps": 0, "max_minute_diff": 0.0, "max_total_diff": 0.0, "max_gross": 0.0,
              "max_gross_reserved": 0.0, "steps_sum_vs_minutes": 0.0, "events": 0, "pending_steps": 0,
              "cancel_legal_sleeve_steps": 0, "effects": {}}
        tsec = 0.0
        for st_ in starts:
            env = AE.AllocatorEnv(cd, static_weights=[0.25] * 7, record_minutes=True)
            obs = env.reset(st_, st_ + 90 * 86400 * 10**9)
            tot, rsum, nst = 0.0, 0.0, 0
            t1 = time.time()
            while True:
                mk_ = obs["masks"]
                rr["pending_steps"] += int(mk_.pending[:, 1].any())
                rr["cancel_legal_sleeve_steps"] += int(mk_.pending[:, 1].sum())
                obs, r, done, info = env.step(random_action(rng, mk_))
                tot += info["net_rl"]
                rsum += r
                nst += 1
                rr["max_gross"] = max(rr["max_gross"], info["gross"])
                rr["max_gross_reserved"] = max(rr["max_gross_reserved"], info["gross_reserved"])
                if done:
                    break
            tsec += time.time() - t1
            sl = slow_replay(cd, env, env.rl, b2)
            rr["max_minute_diff"] = max(rr["max_minute_diff"], float(np.abs(sl - env.minutes["rl"]).max()))
            rr["max_total_diff"] = max(rr["max_total_diff"], abs(sl.sum() - tot))
            rr["steps_sum_vs_minutes"] = max(rr["steps_sum_vs_minutes"], abs(tot - env.minutes["rl"].sum()))
            rr["episodes"] += 1
            rr["steps"] += nst
            rr["events"] += len(env.rl.events)
            for k_, v_ in env.rl.effects.items():
                rr["effects"][k_] = rr["effects"].get(k_, 0) + v_
            for (_, _, a_, _, _) in env.rl.events:
                rr["effects"][a_ + "_requests"] = rr["effects"].get(a_ + "_requests", 0) + 1
            rr["modified_exits"] = rr.get("modified_exits", 0) + sum(len(x) for x in env.rl.mod)
            rr["tighten_exits"] = rr.get("tighten_exits", 0) + sum(1 for (si_, q_, a_, m_, v_) in env.rl.events
                                                                   if a_.startswith("TIGHTEN") and q_ in env.rl.mod[si_])
        rr["steps_per_sec"] = round(rr["steps"] / tsec, 1)
        rr["pending_occupancy_pct"] = round(100 * rr["pending_steps"] / rr["steps"], 4)
        rr["cancel_active_mask_pct"] = round(100 * rr["cancel_legal_sleeve_steps"] / (rr["steps"] * 7), 4)
        rep["random"][cell] = rr
        # static-baseline actions: reward exactly 0 every step
        env = AE.AllocatorEnv(cd, static_weights=[0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.5])
        obs = env.reset(ts("2024-01-01"), ts("2024-07-01"))
        rs, nz = 0.0, 0
        while True:
            obs, r, done, info = env.step(AC.static_action(env.static_w, env.masks()))
            nz += int(r != 0.0)
            rs += abs(r)
            if done:
                break
        rep["static"][cell] = {"nonzero_reward_steps": nz, "sum_abs_reward": rs}
        log(f"env-check {cell}: random {rr} static {rep['static'][cell]}")
    # 4h ablation throughput (uses 32 x 1h history from the 1h store)
    cd = AE.load_cell(CELL_TAG[PRIMARY], fold="F4", cadence_h=4, allow_test=True)
    env = AE.AllocatorEnv(cd, cadence_h=4)
    obs = env.reset(ts("2024-01-01"), ts("2025-01-01"))
    t1, n4 = time.time(), 0
    rng = np.random.default_rng(SEED)
    while True:
        obs, r, done, info = env.step(random_action(rng, obs["masks"]))
        n4 += 1
        if done:
            break
    rep["throughput"]["4h_steps_per_sec"] = round(n4 / (time.time() - t1), 1)
    rep["summary"] = {"parity_runs": len(rep["parity"]), "max_abs_total_vs_ref": worst_tot,
                      "max_minute_vs_slow": worst_min,
                      "random_max_minute_diff": max(v["max_minute_diff"] for v in rep["random"].values()),
                      "random_max_gross": max(v["max_gross"] for v in rep["random"].values()),
                      "random_max_gross_reserved": max(v["max_gross_reserved"] for v in rep["random"].values()),
                      "random_max_total_diff": max(v["max_total_diff"] for v in rep["random"].values()),
                      "random_steps_sum_vs_minutes": max(v["steps_sum_vs_minutes"] for v in rep["random"].values()),
                      "static_sum_abs_reward": sum(v["sum_abs_reward"] for v in rep["static"].values()),
                      "static_nonzero_reward_steps": sum(v["nonzero_reward_steps"] for v in rep["static"].values())}
    rep.update(created_utc=datetime.now(timezone.utc).isoformat(), git_head=git("rev-parse", "HEAD"),
               code_sha256={"allocator_env": sha(ROOT / "btcusdt_quant/rl/allocator_env.py"),
                            "allocator_contracts": sha(ROOT / "btcusdt_quant/rl/allocator_contracts.py"),
                            "script": sha(Path(__file__))}, runtime_sec=round(time.time() - t0, 1))
    S = rep["summary"]
    rep["gates"] = {"parity_total<=1e-6": worst_tot <= 1e-6, "parity_minute<=1e-9": worst_min <= 1e-9,
                    "random_minute<=1e-9": S["random_max_minute_diff"] <= 1e-9,
                    "random_total<=1e-6": S["random_max_total_diff"] <= 1e-6,
                    "steps_sum_vs_minutes<=1e-6": S["random_steps_sum_vs_minutes"] <= 1e-6,
                    "gross_open<=2": S["random_max_gross"] <= AC.GROSS_CAP + 1e-12,
                    "gross_reserved<=2": S["random_max_gross_reserved"] <= AC.GROSS_CAP + 1e-12,
                    "static_nonzero_reward_steps==0": S["static_nonzero_reward_steps"] == 0,
                    "static_sum_abs_reward==0": S["static_sum_abs_reward"] == 0.0}
    rep["turnover_unit"] = "bps = 2 bps x traded notional (mult x base weight per entry and exit leg, terminal exit included)"
    rep["gates"] = {k: bool(v) for k, v in rep["gates"].items()}
    ok = all(rep["gates"].values())
    rep["pass"] = bool(ok)
    dump(OUT / "env" / "env_check.json", rep)
    log(f"env-check {'PASS' if ok else 'FAIL'} {rep['summary']}")
    if not ok:
        raise SystemExit("ENV CHECK FAIL")


# ================================================================ freeze amendment A2 (user 2026-10-10)
AMEND2 = OUT / "freeze_amendment_A2.json"          # SUPERSEDED (2021-12-01 version)
AMEND2R1 = OUT / "freeze_amendment_A2r1.json"      # final A2


def cmd_amend2(_args) -> None:
    if AMEND2R1.exists():
        raise SystemExit(f"{AMEND2R1} exists (write-once)")
    doc = {
        "id": "A2", "revision": 1, "status": "FROZEN", "created_utc": datetime.now(timezone.utc).isoformat(),
        "supersedes": {"path": "out/rl_allocator_20261010/freeze_amendment_A2.json", "sha256": sha(AMEND2),
                       "status": "SUPERSEDED (usable from 2021-12-01, folds F1..F3) by user change 2026-10-10"},
        "amends": {"freeze_sha256_lf": sha(FREEZE), "amendment_A1_sha256": sha(AMEND)},
        "source": "user instruction 2026-10-10 (relayed by coordinator): RL usable data starts 2021-01-30 00:00 UTC "
                  "(G3_SHORT first availability; weekly MA20/50 features valid since 2020-12-21); G3 warm-up "
                  "unavailability accepted",
        "dev_usable_window": [USABLE_FROM, "2026-01-01"],
        "folds": {f: {"train": list(w[0]), "val": list(w[1])} for f, w in FOLDS_A2.items()},
        "dropped_folds": "A1 F1 (train 2020, val 2021); A1 F2..F5 become F1..F4 with train starting 2021-01-30",
        "normalizers": "median/IQR per A2 fold train window only (state/normalizers.json keys F1..F4)",
        "pre_usable_rows": "state/precompute rows before 2021-01-30 are kept on disk but never used for training, "
                           "selection, normalizers or static DEV-best scoring; the env refuses episodes starting "
                           "before 2021-01-30 unless allow_pre_usable=True (canonical parity checks only)",
        "static_dev_best": "scored on A2 fold train windows only; TEST never scored",
        "availability": "B3/K04 available from 2023-09-01; C1v2/C4v2 from 2020-10-01 (LS + 720h warm-up); LBR as "
                        "is (no imputation, masked); G3 warm-up unavailability accepted",
        "unchanged": "sleeves, exec cells, action space, gross cap, costs, reward, TEST window and guard"}
    dump(AMEND2R1, doc)
    log(f"amendment A2 r1 written sha256 {sha(AMEND2R1)}")


# ================================================================ vectorized env: parity vs scalar + benchmark
def vec_random_actions(rng, me, mp, mo, p_exit=0.05, p_tight=0.15, p_cancel=0.2):
    """Legal random batch actions (same distribution as random_action, vectorized)."""
    N, S, _ = me.shape
    u = rng.random((N, S, me.shape[2]))
    entry = np.argmax(np.where(me, u, -1.0), axis=2)
    pend = np.where(mp[:, :, 1] & (rng.random((N, S)) < p_cancel), 1, 0)
    r = rng.random((N, S))
    op = np.where(mo[:, :, 3] & (r < p_exit), 3, 0)
    t2 = mo[:, :, 2] & (r >= p_exit) & (r < p_exit + p_tight)
    t1 = mo[:, :, 1] & (r >= p_exit) & (r < p_exit + p_tight)
    pick = rng.random((N, S)) < 0.5
    op = np.where((op == 0) & t1 & t2, np.where(pick, 1, 2), op)
    op = np.where((op == 0) & t1, 1, op)
    op = np.where((op == 0) & t2, 2, op)
    return entry.astype(np.int64), pend.astype(np.int64), op.astype(np.int64)


def vec_parity(cd, n_envs: int, steps: int, starts, rng, static_w, cadence_h: int = 1) -> dict:
    """Run the vectorized batch and n scalar envs on the same random legal actions; compare masks, observations,
    nets, rewards per step."""
    from btcusdt_quant.rl import allocator_contracts as AC, allocator_env as AE, allocator_vec_env as AV
    H = cadence_h * 3600 * 10**9
    venv = AV.VecAllocatorEnv(cd, n_envs, cadence_h=cadence_h, static_weights=static_w)
    obs = venv.reset(starts, steps)
    envs = [AE.AllocatorEnv(cd, cadence_h=cadence_h, static_weights=static_w) for _ in range(n_envs)]
    so = [e.reset(int(s), int(s) + steps * H) for e, s in zip(envs, starts)]
    rep = {"envs": n_envs, "steps": steps, "mask_mismatch": 0, "obs_max_abs": 0.0, "net_max_abs": 0.0,
           "reward_max_abs": 0.0, "events": 0}
    for _ in range(steps):
        me, mp, mo = obs["masks"]
        for n in range(n_envs):
            m = so[n]["masks"]
            rep["mask_mismatch"] += int(not ((m.entry == me[n]).all() and (m.pending == mp[n]).all()
                                             and (m.open == mo[n]).all()))
            for key in ("static", "seq", "seq_nan", "seq_pad", "account"):
                rep["obs_max_abs"] = max(rep["obs_max_abs"], float(np.abs(so[n][key] - obs[key][n]).max()))
        ent, pen, op = vec_random_actions(rng, me, mp, mo)
        rep["events"] += int((op > 0).sum() + (pen > 0).sum())
        obs, rew, done, info = venv.step(ent, pen, op)
        for n in range(n_envs):
            o, r, d, inf = envs[n].step(AC.Action(tuple(int(x) for x in ent[n]), tuple(int(x) for x in pen[n]),
                                                  tuple(int(x) for x in op[n])))
            so[n] = o
            rep["net_max_abs"] = max(rep["net_max_abs"], abs(inf["net_rl"] - info["net_rl"][n]),
                                     abs(inf["net_st"] - info["net_st"][n]))
            rep["reward_max_abs"] = max(rep["reward_max_abs"], abs(r - rew[n]))
            rep["gross_max_abs"] = max(rep.get("gross_max_abs", 0.0), abs(inf["gross_open"] - info["gross_open"][n]),
                                       abs(inf["gross_reserved"] - info["gross_reserved"][n]))
    rep["equity_max_abs"] = float(max(abs(e.rl.equity - venv.rl.equity[n]) for n, e in enumerate(envs)))
    return rep


def vec_bench(cd, n_envs: int, steps: int, rng, cadence_h: int = 1) -> float:
    from btcusdt_quant.rl import allocator_vec_env as AV
    lo, hi = cd.usable_from, pd.Timestamp("2025-09-01", tz="UTC").value
    step = cadence_h * 3600 * 10**9
    starts = lo + step * rng.integers(0, (hi - lo) // step - steps, n_envs)
    v = AV.VecAllocatorEnv(cd, n_envs, cadence_h=cadence_h, static_weights=[0.25] * 7)
    obs = v.reset(starts, steps)
    t0, n = time.time(), 0
    while True:
        obs, r, done, info = v.step(*vec_random_actions(rng, *obs["masks"]))
        n += 1
        if done:
            break
    return n_envs * n / (time.time() - t0)


def cmd_vec_check(args) -> None:
    from btcusdt_quant.rl import allocator_env as AE
    t0 = time.time()
    rep: dict = {"parity": {}, "bench_1h": {}, "bench_4h": {}}
    H = 3600 * 10**9
    for cell in [CELL_TAG[c] for c in CELLS]:
        cd = AE.load_cell(cell, fold="F4", allow_test=False)
        rng = np.random.default_rng(SEED + len(rep["parity"]))
        days = rng.choice(np.arange(0, (pd.Timestamp("2025-11-01", tz="UTC").value - cd.usable_from) // (24 * H)),
                          16, replace=False)
        starts = cd.usable_from + 24 * H * days
        rep["parity"][cell] = vec_parity(cd, 16, 720, starts, rng, [0.25, 0.25, 0.25, 0.5, 0.25, 0.25, 0.25])
        log(f"vec parity {cell} {rep['parity'][cell]}")
    cd = AE.load_cell(CELL_TAG[PRIMARY], fold="F4", cadence_h=4, allow_test=False)
    rng = np.random.default_rng(SEED)
    starts4 = cd.usable_from + 4 * H * rng.choice(np.arange(0, 6000), 8, replace=False)
    rep["parity_4h"] = vec_parity(cd, 8, 540, starts4, rng, [0.25] * 7, cadence_h=4)
    cd = AE.load_cell(CELL_TAG[PRIMARY], fold="F4", allow_test=False)
    for n in (32, 128, 256):
        rep["bench_1h"][str(n)] = round(vec_bench(cd, n, 2160, np.random.default_rng(n)), 1)
    cd4 = AE.load_cell(CELL_TAG[PRIMARY], fold="F4", cadence_h=4, allow_test=False)
    rep["bench_4h"]["128"] = round(vec_bench(cd4, 128, 540, np.random.default_rng(4), cadence_h=4), 1)
    P = list(rep["parity"].values()) + [rep["parity_4h"]]
    rep["gates"] = {"mask_mismatch==0": all(p["mask_mismatch"] == 0 for p in P),
                    "obs<=1e-6": all(p["obs_max_abs"] <= 1e-6 for p in P),
                    "net<=1e-9": all(p["net_max_abs"] <= 1e-9 for p in P),
                    "reward<=1e-9": all(p["reward_max_abs"] <= 1e-9 for p in P),
                    "equity<=1e-9": all(p["equity_max_abs"] <= 1e-9 for p in P),
                    "bench128_1h>=4630": rep["bench_1h"]["128"] >= 4630,
                    "bench128_1h>=9804_target": rep["bench_1h"]["128"] >= 9804}
    rep.update(policy="random legal (entry uniform over legal levels, EXIT 5%, TIGHTEN 15%, CANCEL 20%)",
               record_minutes="off (vectorized env never records minutes)", git_head=git("rev-parse", "HEAD"),
               code_sha256={"allocator_vec_env": sha(ROOT / "btcusdt_quant/rl/allocator_vec_env.py")},
               created_utc=datetime.now(timezone.utc).isoformat(), runtime_sec=round(time.time() - t0, 1))
    dump(OUT / "env" / "vec_check.json", rep)
    ok = all(v for k, v in rep["gates"].items() if not k.endswith("_target"))
    log(f"vec-check {'PASS' if ok else 'FAIL'} gates {rep['gates']} bench {rep['bench_1h']} {rep['bench_4h']}")
    if not ok:
        raise SystemExit("VEC CHECK FAIL")


# ================================================================ step 6: static baselines (analytic scorer)
def unit_series(cd, start: int, end: int):
    """Per-step unit net4 / turnover of each sleeve's static book (weight 1, availability-gated, flat start,
    terminal mark + fee) from the vectorized env; one env per sleeve."""
    from btcusdt_quant.rl import allocator_vec_env as AV
    H = 3600 * 10**9
    L = (end - start) // H
    v = AV.VecAllocatorEnv(cd, len(SLEEVES), static_weights=np.eye(len(SLEEVES)))
    v.reset(np.full(len(SLEEVES), start), L)
    z = np.zeros((len(SLEEVES), len(SLEEVES)), np.int64)
    net, turn = np.zeros((L, len(SLEEVES))), np.zeros((L, len(SLEEVES)))
    for k in range(L):
        _, _, done, info = v.step(z, z, z)
        net[k], turn[k] = info["net_st"], info["turnover_st"]
    day = ((v.Ts[0, :-1] - start) // (24 * H)).astype(np.int64)
    return net, turn, day


def cmd_baselines(args) -> None:
    from btcusdt_quant.rl import allocator_baselines as BL, allocator_env as AE, allocator_vec_env as AV
    t0 = time.time()
    W = BL.candidate_grid()
    named = BL.named_baselines()
    BD = OUT / "baselines"
    BD.mkdir(parents=True, exist_ok=True)
    ts = lambda x: pd.Timestamp(x, tz="UTC").value  # noqa: E731
    cells = [CELL_TAG[c] for c in CELLS]
    scores = {f: {"train": {}, "val": {}} for f in FOLDS_A2}
    named_scores = {f: {"train": {}, "val": {}} for f in FOLDS_A2}
    units = {}
    boot_cache = {}
    parity = {"vectors": 0, "runs": 0, "max_net_diff": 0.0, "max_mdd_diff": 0.0, "max_turnover_diff": 0.0}
    rng = np.random.default_rng(SEED)
    sample = rng.choice(len(W), 48, replace=False)
    PW = np.vstack([W[sample], np.vstack(list(named.values()))])          # 48 grid + 2 named = 50 vectors
    parity["vectors"] = len(PW)
    for cell in cells:
        cd = AE.load_cell(cell, fold="F4", allow_test=False)
        for f, (tr, va) in FOLDS_A2.items():
            for nm, (a, b) in (("train", tr), ("val", va)):
                net, turn, day = unit_series(cd, ts(a), ts(b))
                units[(cell, f, nm)] = (net, turn)
                D = int(day.max()) + 1
                if D not in boot_cache:
                    boot_cache[D] = BL.stationary_indices(D)
                scores[f][nm][cell] = BL.score(net, turn, day, W, boot_cache[D])
                named_scores[f][nm][cell] = BL.score(net, turn, day, np.vstack(list(named.values())), boot_cache[D])
                if nm == "train":                               # scorer <-> env parity on 50 vectors
                    L = (ts(b) - ts(a)) // (3600 * 10**9)
                    v = AV.VecAllocatorEnv(cd, len(PW), static_weights=PW)
                    v.reset(np.full(len(PW), ts(a)), L)
                    z = np.zeros((len(PW), len(SLEEVES)), np.int64)
                    to = np.zeros(len(PW))
                    for _ in range(L):
                        _, _, _, info = v.step(z, z, z)
                        to += info["turnover_st"]
                    sc = BL.score(net, turn, day, PW, boot_cache[D])
                    parity["runs"] += len(PW)
                    parity["max_net_diff"] = max(parity["max_net_diff"], float(np.abs(sc.net4 - v.st.equity).max()))
                    parity["max_mdd_diff"] = max(parity["max_mdd_diff"], float(np.abs(sc.mdd - v.st.mdd).max()))
                    parity["max_turnover_diff"] = max(parity["max_turnover_diff"], float(np.abs(sc.turnover - to).max()))
                log(f"baselines {cell} {f} {nm} days {D}")
    sel = {}
    for f in FOLDS_A2:
        rk = BL.rank(scores[f]["train"], W)
        rk.to_parquet(BD / f"ranking_{f}_train.parquet", index=False)
        best = int(rk.cand.iloc[0])
        w_best = W[best]
        def metrics(fr: dict, i: int) -> dict:
            return {c: {k: float(fr[c][k].iloc[i]) for k in ("net4", "boot_p05", "mdd", "turnover")} for c in cells}
        sel[f] = {"train": list(FOLDS_A2[f][0]), "val": list(FOLDS_A2[f][1]),
                  "weights": dict(zip(SLEEVES, w_best.tolist())), "rank_keys_top": rk.head(5).to_dict("records"),
                  "selected_train": metrics(scores[f]["train"], best), "selected_val": metrics(scores[f]["val"], best),
                  "named": {k: {"train": metrics(named_scores[f]["train"], i), "val": metrics(named_scores[f]["val"], i)}
                            for i, k in enumerate(named)},
                  "n_candidates": int(len(W)), "ties_at_top": int((rk[["min_net4", "min_boot_p05", "max_mdd",
                                                                       "mean_turnover"]].iloc[:2].nunique() == 1).all())}
    parity["gate_1e-6"] = bool(max(parity["max_net_diff"], parity["max_mdd_diff"], parity["max_turnover_diff"]) <= 1e-6)
    rep = {"name": "static baselines (design section 4) - A2 r1 folds, train windows only", "selection": sel,
           "named_baselines": {k: v.tolist() for k, v in named.items()}, "parity_scorer_vs_env": parity,
           "ranking_rule": BL.__doc__, "bootstrap": {"n": BL.BOOT_N, "block_days": BL.BOOT_BLOCK, "seed": BL.BOOT_SEED},
           "test_scored": False, "git_head": git("rev-parse", "HEAD"),
           "code_sha256": {"allocator_baselines": sha(ROOT / "btcusdt_quant/rl/allocator_baselines.py")},
           "created_utc": datetime.now(timezone.utc).isoformat(), "runtime_sec": round(time.time() - t0, 1)}
    dump(BD / "static_selection.json", rep)
    log(f"baselines done parity {parity} selected { {f_: sel[f_]['weights'] for f_ in sel} }")
    if not parity["gate_1e-6"]:
        raise SystemExit("SCORER PARITY FAIL")


# ================================================================ step 5: PPO smoke (Codex spec, F4 seed 0)
SMOKE_COUNTS = {"o2_p0.5": 22, "o2_p1.0": 22, "o2_p2.0": 21, "o5_p0.5": 21, "o5_p1.0": 21, "o5_p2.0": 21}


def cmd_smoke(args) -> None:
    """Smoke r2 (Codex smoke review): F4 seed 0, 30 updates with validation at 0/10/20/30 (batched B=6), split-resume
    exactness (3 + 4 updates vs the first 7 of the main run), batched vs serial validation parity and timing, CPU
    inference timing, fold-mismatch refusal, 4h construction check."""
    import torch
    from btcusdt_quant.rl import allocator_env as AE, allocator_ppo as AP
    t0 = time.time()
    SD = OUT / "smoke"
    SD.mkdir(parents=True, exist_ok=True)
    selj = json.loads((OUT / "baselines/static_selection.json").read_text(encoding="utf-8"))["selection"]["F4"]
    static_w = np.array([selj["weights"][s] for s in SLEEVES])
    if not np.array_equal(static_w, [0, 0, 0, 0, 0, 1, 1]):
        raise SystemExit(f"F4 static weights changed: {static_w}")
    g3_val = {c: v["net4"] for c, v in selj["named"]["G3_ONLY"]["val"].items()}
    eq_val = {c: v["net4"] for c, v in selj["named"]["STATIC_EQUAL_2_7"]["val"].items()}
    fold = "F4"
    train, val = FOLDS_A2[fold]
    cells = {c: AE.load_cell(c, fold=fold, allow_test=False) for c in SMOKE_COUNTS}
    n_up = int(getattr(args, "updates", 30) or 30)
    cfg = AP.AllocPPOConfig(total_updates=n_up)
    log(f"smoke r2: cells loaded {time.time() - t0:.0f}s; fold {fold} train {train} val {val}; cfg {cfg}")

    def trainer():
        return AP.Trainer(cells, SMOKE_COUNTS, static_w, train, val, cfg, seed=0, fold=fold,
                          comparators={"G3_ONLY": [1.0, 1.0, 0, 0, 0, 0, 0]})

    rep: dict = {"spec": {"fold": fold, "seed": 0, "train": list(train), "val": list(val), "counts": SMOKE_COUNTS,
                          "cfg": dataclasses_asdict(cfg), "updates": n_up, "static_weights": static_w.tolist()},
                 "updates": [], "val": {}}
    try:                                                              # fold mismatch must fail closed
        AP.Trainer(cells, SMOKE_COUNTS, static_w, FOLDS_A2["F3"][0], FOLDS_A2["F3"][1], cfg, seed=0, fold="F3")
        rep["fold_mismatch_refused"] = False
    except ValueError as e:
        rep["fold_mismatch_refused"] = True
        rep["fold_mismatch_error"] = str(e)[:200]

    def val_summary(v):
        out = {"worst_cell_excess": v["worst_cell_excess"], "flat_cells": v["flat_cells"], "cells": {}}
        for c, r in v["cells"].items():
            best_static = max(r["net_static"], g3_val[c])
            out["cells"][c] = {k: r[k] for k in ("net_rl", "net_static", "excess", "reward", "dd_pen", "to_pen",
                                                 "trades", "mdd_rl", "mdd_static", "entry_deviation_ratio",
                                                 "open_nonhold_ratio", "identity_err", "gross_reserved_max")}
            out["cells"][c].update(g3_only_net=g3_val[c], equal_2_7_net=eq_val[c],
                                   excess_vs_max_static_g3=r["net_rl"] - best_static)
        return out

    tr = trainer()
    t1 = time.time()
    v = tr.validate()
    rep["val"]["0"] = val_summary(v)
    rep["val_sec"] = {"0": round(time.time() - t1, 1)}
    best = {"key": v["score"], "update": 0} if not v["all_flat"] else {"key": -math.inf, "update": -1}
    if best["update"] == 0:
        torch.save({"model": tr.model.state_dict(), "update": 0, "key": best["key"], "identity": tr.identity}, SD / "best.pt")
    state7 = None
    tt = time.time()
    for u in range(1, n_up + 1):
        tu = time.time()
        rec = tr.run_update()
        rec["sec"] = round(time.time() - tu, 2)
        rep["updates"].append(rec)
        log(f"u{u}: reward {rec['reward']:.0f} excess {rec['net_excess']:.0f} ent {rec['entropy_active_heads']:.3f} "
            f"entc {rec['ent_coef']:.5f} kl {rec['approx_kl']:.4f} max {rec['approx_kl_max']:.4f} "
            f"stop {rec['kl_early_stop']} steps {rec['grad_steps']} {rec['sec']}s")
        if u == 7:
            state7 = tr.state_dict()
        if u % 10 == 0:
            tv = time.time()
            v = tr.validate()
            rep["val"][str(u)] = val_summary(v)
            rep["val_sec"][str(u)] = round(time.time() - tv, 1)
            if not v["all_flat"] and v["score"] > best["key"]:
                best = {"key": v["score"], "update": u}
                torch.save({"model": tr.model.state_dict(), "update": u, "key": best["key"], "identity": tr.identity},
                           SD / "best.pt")
            if u == 10:                                               # batched vs serial parity + timings
                ts_ = time.time()
                vs = tr.validate(batched=False)
                t_serial = time.time() - ts_
                tc_ = time.time()
                vc = tr.validate(device="cpu")
                t_cpu = time.time() - tc_
                same = all(len(v["_actions"][c]) == len(vs["_actions"][c]) and all(
                    np.array_equal(x[0], y[0]) and np.array_equal(x[1], y[1])
                    for x, y in zip(v["_actions"][c], vs["_actions"][c])) for c in v["cells"])
                num = max(abs(v["cells"][c][k] - vs["cells"][c][k]) for c in v["cells"] for k in ("net_rl", "mdd_rl"))
                same_cpu = all(all(np.array_equal(x[0], y[0]) and np.array_equal(x[1], y[1])
                                   for x, y in zip(v["_actions"][c], vc["_actions"][c])) for c in v["cells"])
                rep["val_parity"] = {"actions_equal_batched_vs_serial": same, "net_mdd_max_abs": num,
                                     "actions_equal_gpu_vs_cpu": same_cpu,
                                     "sec_batched_gpu": rep["val_sec"]["10"], "sec_serial_gpu": round(t_serial, 1),
                                     "sec_batched_cpu": round(t_cpu, 1)}
                log(f"val parity {rep['val_parity']}")
    rep["train_sec"] = round(time.time() - tt, 1)
    rep["best"] = best
    torch.save(tr.state_dict(), SD / "last.pt")
    # split resume: 3 updates, checkpoint to disk, fresh trainer, 4 updates == main run state at update 7
    tb = trainer()
    for _ in range(3):
        tb.run_update()
    torch.save(tb.state_dict(), SD / "split_u3.pt")
    del tb
    tc = trainer()
    tc.load_state_dict(torch.load(SD / "split_u3.pt", map_location="cpu", weights_only=False))
    for _ in range(4):
        tc.run_update()
    s7 = tc.state_dict()
    rep["split_resume"] = {k: AP.tensors_equal(state7[k], s7[k])
                           for k in ("model", "opt", "env", "torch_rng", "cuda_rng", "update", "identity")}
    bad = dict(s7, identity=dict(s7["identity"], static_weights=[0.0] * 7))
    try:
        tc.load_state_dict(bad)
        rep["split_resume"]["identity_mismatch_refused"] = False
    except ValueError:
        rep["split_resume"]["identity_mismatch_refused"] = True
    # 4h construction / one update on two cells (540-step episodes, 32 x 1h history)
    c4 = {c: AE.load_cell(c, fold=fold, cadence_h=4, allow_test=False) for c in ("o2_p0.5", "o5_p2.0")}
    cfg4 = AP.AllocPPOConfig(cadence_h=4, n_steps=32, total_updates=1)
    t4 = AP.Trainer(c4, {"o2_p0.5": 8, "o5_p2.0": 8}, static_w, train, val, cfg4, seed=0, fold=fold)
    r4 = t4.run_update()
    rep["cadence_4h"] = {"episode_steps": cfg4.episode_steps, "illegal": r4["illegal"], "nonfinite": r4["nonfinite"],
                         "identity_err": r4["identity_err"], "gross_reserved_max": r4["gross_reserved_max"],
                         "env_L": t4.env.envs["o2_p0.5"].L}
    U = rep["updates"]
    vals = [x for x in rep["val"].values()]
    rep["contracts"] = {
        "illegal_actions==0": sum(u["illegal"] for u in U) == 0,
        "nan_inf==0": sum(u["nonfinite"] for u in U) == 0,
        "reward_identity<=1e-6": max(u["identity_err"] for u in U) <= 1e-6
        and max(c["identity_err"] for v_ in vals for c in v_["cells"].values()) <= 1e-6,
        "gross_reserved<=2": max(u["gross_reserved_max"] for u in U) <= C_GROSS + 1e-12
        and max(c["gross_reserved_max"] for v_ in vals for c in v_["cells"].values()) <= C_GROSS + 1e-12,
        "update0_val_reward==0": all(c["reward"] == 0.0 and c["excess"] == 0.0 for c in rep["val"]["0"]["cells"].values()),
        "split_resume_exact": all(rep["split_resume"].values()),
        "fold_mismatch_refused": rep["fold_mismatch_refused"],
        "val_batched==serial": rep["val_parity"]["actions_equal_batched_vs_serial"]
        and rep["val_parity"]["net_mdd_max_abs"] == 0.0,
        "cadence_4h_ok": rep["cadence_4h"]["episode_steps"] == 540 and rep["cadence_4h"]["env_L"] == 540
        and rep["cadence_4h"]["illegal"] == 0 and rep["cadence_4h"]["nonfinite"] == 0}
    last = rep["val"][str(n_up)]
    rep["activity"] = {"rollout_new_alloc": sum(u["new_alloc"] for u in U),
                       "rollout_nonzero_entry": all((u["nonzero_entry_ratio"] or 0) > 0 for u in U),
                       "final_flat_cells": last["flat_cells"], "kl_early_stops": sum(u["kl_early_stop"] for u in U)}
    rep["smoke_pass"] = bool(all(rep["contracts"].values()) and rep["activity"]["rollout_new_alloc"] > 0
                             and rep["activity"]["rollout_nonzero_entry"] and last["flat_cells"] == 0)
    sec_u = float(np.mean([u["sec"] for u in U]))
    n_full = math.ceil(2_000_000 / (cfg.n_steps * 128))
    rep["budget"] = {"sec_per_update_mean": round(sec_u, 2), "val_sec_batched_gpu": rep["val_parity"]["sec_batched_gpu"],
                     "updates_for_2M_transitions": n_full,
                     "est_run_sec_val_every_10": round(n_full * sec_u + (n_full // 10 + 1) * rep["val_parity"]["sec_batched_gpu"], 0),
                     "throughput_transitions_per_sec": round(cfg.n_steps * 128 / sec_u, 1)}
    rep.update(git_head=git("rev-parse", "HEAD"), created_utc=datetime.now(timezone.utc).isoformat(),
               runtime_sec=round(time.time() - t0, 1),
               code_sha256={k: sha(ROOT / f"btcusdt_quant/rl/{k}.py") for k in
                            ("allocator_model", "allocator_ppo", "allocator_vec_env", "allocator_env")},
               note="positive excess is not a smoke criterion; TEST never accessed")
    dump(SD / "smoke_report_r2.json", rep)
    registry.record(REGISTRY, {"experiment": f"RL allocator PPO smoke r2 (F4 seed 0, {n_up} updates)", "role": "smoke",
                               "n_trials": 0, "n_simulations": 0,
                               "config": {"fold": fold, "seed": 0, "updates": n_up, "cfg": dataclasses_asdict(cfg),
                                          "static_weights": static_w.tolist()},
                               "result_summary": {"smoke_pass": rep["smoke_pass"],
                                                  "val_worst_excess": {k: v_["worst_cell_excess"] for k, v_ in rep["val"].items()}}})
    log(f"smoke r2 {'PASS' if rep['smoke_pass'] else 'FAIL'} contracts {rep['contracts']} activity {rep['activity']} "
        f"budget {rep['budget']}")
    if not rep["smoke_pass"]:
        raise SystemExit("SMOKE FAIL")


C_GROSS = 2.0


def dataclasses_asdict(x):
    import dataclasses
    return dataclasses.asdict(x)


# ================================================================ pilot (e): F4 G3-only heads (Codex spec)
G3_ONLY_W = [1.0, 1.0, 0, 0, 0, 0, 0]
C1C4_W = [0, 0, 0, 0, 0, 1.0, 1.0]
PILOT_VAL_AT = (0, 20, 40, 60, 80, 100, 123)


def boot_p05(daily: np.ndarray, block: int) -> float:
    from btcusdt_quant.rl import allocator_baselines as BL
    idx = BL.stationary_indices(len(daily), n_boot=BL.BOOT_N, block=block, seed=BL.BOOT_SEED)
    return float(np.quantile(daily[idx].mean(axis=1), 0.05))


def val_report(v: dict, with_boot: bool) -> dict:
    out = {"score": v["score"], "flat_cells": v["flat_cells"], "cells": {}}
    pooled = []
    for c, r in v["cells"].items():
        ser = v["_series"][c]
        best_k = "static" if r["net_static"] >= r["net_C1C4"] else "C1C4"
        d = (ser["rl"] - ser[best_k]).reshape(-1, 24).sum(1)
        pooled.append(d)
        x = {k: r[k] for k in ("net_rl", "net_static", "net_C1C4", "excess", "excess_vs_max_baseline", "mdd_rl",
                               "mdd_static", "mdd_C1C4", "trades", "entry_deviation_ratio", "open_nonhold_ratio",
                               "deviate_entries", "nonhold_open", "reward", "dd_pen", "to_pen", "identity_err",
                               "gross_reserved_max")}
        x.update(net_G3_ONLY=r["net_static"], mdd_G3_ONLY=r["mdd_static"], paired_baseline=best_k)
        if with_boot:
            x["boot_p05"] = {str(bl): boot_p05(d, bl) for bl in (20, 60, 120)}
        out["cells"][c] = x
    if with_boot:
        pm = np.mean(pooled, axis=0)
        out["pooled_boot_p05"] = {str(bl): boot_p05(pm, bl) for bl in (20, 60, 120)}
    return out


def cmd_pilot_g3(args) -> None:
    import torch
    from btcusdt_quant.rl import allocator_env as AE, allocator_ppo as AP
    t0 = time.time()
    PD = OUT / "pilot_g3"
    PD.mkdir(parents=True, exist_ok=True)
    fold = "F4"
    train, val = FOLDS_A2[fold]
    cells = {c: AE.load_cell(c, fold=fold, allow_test=False) for c in SMOKE_COUNTS}
    cfg = AP.AllocPPOConfig(total_updates=123, lr=1e-3, entry_bias=2.5, open_bias=2.5, ent_coef=0.001,
                            ent_decay_frac=0.8, target_kl=0.01, active_sleeves=("G3_LONG", "G3_SHORT"),
                            ckpt_score="max_baseline")
    seeds = [int(x) for x in str(getattr(args, "seeds", "0,1,2")).split(",")]
    comps = {"C1C4": C1C4_W}

    def trainer(seed):
        return AP.Trainer(cells, SMOKE_COUNTS, G3_ONLY_W, train, val, cfg, seed=seed, fold=fold, comparators=comps)

    rep: dict = {"spec": {"fold": fold, "train": list(train), "val": list(val), "counts": SMOKE_COUNTS,
                          "cfg": dataclasses_asdict(cfg), "seeds": seeds, "reward_comparator": G3_ONLY_W,
                          "score_baselines": {"G3_ONLY": G3_ONLY_W, "C1C4": C1C4_W}, "val_at": PILOT_VAL_AT,
                          "val_device": "cpu batched"}, "seeds": {}}
    try:
        AP.Trainer(cells, SMOKE_COUNTS, G3_ONLY_W, FOLDS_A2["F3"][0], FOLDS_A2["F3"][1], cfg, seed=0, fold="F3")
        fold_refused = False
    except ValueError:
        fold_refused = True
    best_models, contracts_u = [], []
    state7 = None
    for seed in seeds:
        ts = time.time()
        tr = trainer(seed)
        R = {"updates": [], "val": {}, "val_sec": {}}
        v = tr.validate(device="cpu")
        R["val"]["0"] = val_report(v, with_boot=False)
        if seed == seeds[0]:                                  # batched vs serial (CPU) at u0
            vs = tr.validate(batched=False, device="cpu")
            same = all(all(np.array_equal(x[0], y[0]) and np.array_equal(x[1], y[1])
                           for x, y in zip(v["_actions"][c], vs["_actions"][c])) for c in v["cells"])
            num = max(abs(v["cells"][c][k] - vs["cells"][c][k]) for c in v["cells"] for k in ("net_rl", "mdd_rl"))
            rep["val_parity"] = {"actions_equal": same, "net_mdd_max_abs": num}
        u0_reward_zero = all(c["reward"] == 0.0 for c in v["cells"].values())
        best = {"score": v["score"], "update": 0, "state": copy_state(tr)} if not v["all_flat"] else \
            {"score": -math.inf, "update": -1, "state": None}
        for u in range(1, cfg.total_updates + 1):
            tu = time.time()
            rec = tr.run_update()
            rec["sec"] = round(time.time() - tu, 2)
            if u not in PILOT_VAL_AT:
                rec.pop("heads", None)
            R["updates"].append(rec)
            if seed == seeds[0] and u == 7:
                state7 = tr.state_dict()
            if u in PILOT_VAL_AT:
                tv = time.time()
                v = tr.validate(device="cpu")
                R["val"][str(u)] = val_report(v, with_boot=False)
                R["val_sec"][str(u)] = round(time.time() - tv, 1)
                if not v["all_flat"] and v["score"] > best["score"]:
                    best = {"score": v["score"], "update": u, "state": copy_state(tr)}
                log(f"pilot seed {seed} u{u}: score {v['score']:.1f} dev "
                    f"{np.mean([c['entry_deviation_ratio'] for c in v['cells'].values()]):.4f} "
                    f"ent {rec['entropy_active_heads']:.3f} kl {rec['approx_kl']:.4f} ev {rec['explained_var']:.3f}")
        R["best"] = {"score": best["score"], "update": best["update"]}
        m = AP.AllocatorActorCritic(hidden=cfg.hidden, static_weights=G3_ONLY_W, entry_bias=cfg.entry_bias,
                                    open_bias=cfg.open_bias)
        m.load_state_dict(best["state"])
        m.eval()
        best_models.append(m)
        torch.save({"model": best["state"], "identity": tr.identity, "update": best["update"], "score": best["score"]},
                   PD / f"best_seed{seed}.pt")
        tr.model.load_state_dict(best["state"])
        vb = tr.validate(device="cpu")
        R["best_val"] = val_report(vb, with_boot=True)
        contracts_u.append({"illegal": sum(x["illegal"] for x in R["updates"]),
                            "nonfinite": sum(x["nonfinite"] for x in R["updates"]),
                            "identity_err": max([x["identity_err"] for x in R["updates"]]
                                                + [c["identity_err"] for vv in R["val"].values() for c in vv["cells"].values()]),
                            "gross": max([x["gross_reserved_max"] for x in R["updates"]]
                                         + [c["gross_reserved_max"] for vv in R["val"].values() for c in vv["cells"].values()]),
                            "u0_reward_zero": u0_reward_zero})
        R["curves"] = {k: [x[k] for x in R["updates"]] for k in ("entropy_active_heads", "approx_kl", "approx_kl_max",
                                                                 "explained_var", "kl_early_stop", "reward",
                                                                 "net_excess", "nonzero_entry_ratio", "new_alloc")}
        R["runtime_sec"] = round(time.time() - ts, 1)
        rep["seeds"][str(seed)] = R
        registry.record(REGISTRY, {"experiment": f"RL allocator pilot (e) F4 G3-only heads seed {seed}", "role": "trial",
                                   "n_trials": 1, "n_simulations": 1,
                                   "config": {"fold": fold, "seed": seed, "cfg": dataclasses_asdict(cfg),
                                              "reward_comparator": "G3_ONLY", "score": "min_cell[RL - max(C1C4, G3_ONLY)]"},
                                   "result_summary": {"best_update": best["update"], "best_score": best["score"],
                                                      "val_scores": {k: x["score"] for k, x in R["val"].items()}}})
        log(f"pilot seed {seed} done best u{best['update']} score {best['score']:.1f} {R['runtime_sec']}s")
    # split resume (first seed): 3 updates, disk checkpoint, fresh trainer, 4 updates == main run at update 7
    tb = trainer(seeds[0])
    for _ in range(3):
        tb.run_update()
    torch.save(tb.state_dict(), PD / "split_u3.pt")
    del tb
    tc = trainer(seeds[0])
    tc.load_state_dict(torch.load(PD / "split_u3.pt", map_location="cpu", weights_only=False))
    for _ in range(4):
        tc.run_update()
    s7 = tc.state_dict()
    split_ok = all(AP.tensors_equal(state7[k], s7[k]) for k in ("model", "opt", "env", "torch_rng", "cuda_rng", "update"))
    c4 = {c: AE.load_cell(c, fold=fold, cadence_h=4, allow_test=False) for c in ("o2_p0.5", "o5_p2.0")}
    cfg4 = AP.AllocPPOConfig(**{**dataclasses_asdict(cfg), "cadence_h": 4, "n_steps": 32})
    t4 = AP.Trainer(c4, {"o2_p0.5": 8, "o5_p2.0": 8}, G3_ONLY_W, train, val, cfg4, seed=0, fold=fold)
    r4 = t4.run_update()
    ok4 = cfg4.episode_steps == 540 and r4["illegal"] == 0 and r4["nonfinite"] == 0
    # ensemble of the per-seed best checkpoints
    te = trainer(seeds[0])
    ve = te.validate(device="cpu", policy=AP.ensemble_policy(best_models))
    E = val_report(ve, with_boot=True)
    rep["ensemble"] = E
    rep["contracts"] = {
        "illegal_actions==0": all(c["illegal"] == 0 for c in contracts_u),
        "nan_inf==0": all(c["nonfinite"] == 0 for c in contracts_u),
        "reward_identity<=1e-6": all(c["identity_err"] <= 1e-6 for c in contracts_u)
        and all(c["identity_err"] <= 1e-6 for c in E["cells"].values()),
        "gross_reserved<=2": all(c["gross"] <= C_GROSS + 1e-12 for c in contracts_u),
        "update0_val_reward==0": all(c["u0_reward_zero"] for c in contracts_u),
        "split_resume_exact": split_ok, "fold_mismatch_refused": fold_refused,
        "val_batched==serial": rep["val_parity"]["actions_equal"] and rep["val_parity"]["net_mdd_max_abs"] == 0.0,
        "cadence_4h_ok": ok4}
    cells_e = E["cells"].values()
    rep["pass_criteria"] = {
        "contracts_9of9": all(rep["contracts"].values()),
        "ensemble_differs_from_baseline": sum(c["deviate_entries"] + c["nonhold_open"] for c in cells_e) > 0,
        "net4>0_6of6": all(c["net_rl"] > 0 for c in cells_e),
        "net4>max(C1C4,G3_ONLY)_6of6": all(c["excess_vs_max_baseline"] > 0 for c in cells_e),
        "mdd<G3_ONLY_6of6": all(mdd_gate(c) for c in cells_e),
        "boot_p05>0_all_cells_20_60_120": all(p > 0 for c in cells_e for p in c["boot_p05"].values())}
    rep["pilot_pass"] = bool(all(rep["pass_criteria"].values()))
    rep.update(git_head=git("rev-parse", "HEAD"), created_utc=datetime.now(timezone.utc).isoformat(),
               runtime_sec=round(time.time() - t0, 1), test_accessed=False,
               boot_note="paired daily excess vs the cell's larger baseline (C1C4 or G3_ONLY); gate = every cell "
                         "and every block; pooled (mean over cells) reported too",
               code_sha256={k: sha(ROOT / f"btcusdt_quant/rl/{k}.py") for k in ("allocator_model", "allocator_ppo",
                                                                                 "allocator_vec_env", "allocator_env")})
    dump(PD / "pilot_report.json", rep)
    log(f"pilot (e) {'PASS' if rep['pilot_pass'] else 'FAIL'} {rep['pass_criteria']} contracts {rep['contracts']}")


def copy_state(tr):
    import copy as _c
    return {k: v.detach().cpu().clone() for k, v in _c.deepcopy(tr.model.state_dict()).items()}


# ================================================================ pilot (e2): F3 update selection -> F4 single evaluation
E2_CANDIDATES = (20, 40, 60, 80, 100, 123)


def mdd_gate(c: dict) -> bool:
    """Design gate: RL max drawdown strictly below the G3_ONLY static book."""
    return c["mdd_rl"] < c["mdd_G3_ONLY"]


def e2_cfg():
    from btcusdt_quant.rl import allocator_ppo as AP
    return AP.AllocPPOConfig(total_updates=123, lr=3e-4, epochs=4, entry_bias=2.5, open_bias=2.5, ent_coef=0.001,
                             ent_decay_frac=0.8, target_kl=0.01, active_sleeves=("G3_LONG", "G3_SHORT"),
                             ckpt_score="max_baseline")


def e2_model(cfg, state):
    from btcusdt_quant.rl import allocator_ppo as AP
    m = AP.AllocatorActorCritic(hidden=cfg.hidden, static_weights=G3_ONLY_W, entry_bias=cfg.entry_bias,
                                open_bias=cfg.open_bias)
    m.load_state_dict(state)
    m.eval()
    return m


def e2_curves(updates: list) -> dict:
    keys = ("entropy_active_heads", "approx_kl", "approx_kl_max", "explained_var", "kl_early_stop", "reward",
            "net_excess", "nonzero_entry_ratio", "new_alloc", "grad_steps", "sec")
    return {k: [u[k] for u in updates] for k in keys}


def cmd_pilot_e2(args) -> None:
    import torch
    from btcusdt_quant.rl import allocator_env as AE, allocator_ppo as AP
    t0 = time.time()
    PD = OUT / "pilot_g3_e2"
    PD.mkdir(parents=True, exist_ok=True)
    cfg = e2_cfg()
    seeds = [0, 1, 2]
    comps = {"C1C4": C1C4_W}
    rep: dict = {"spec": {"cfg": dataclasses_asdict(cfg), "seeds": seeds, "candidates": E2_CANDIDATES,
                          "selection_fold": "F3", "eval_fold": "F4", "reward_comparator": G3_ONLY_W,
                          "score": "min_cell[ensemble RL - max(C1C4, G3_ONLY)]", "tie": "earliest update",
                          "ensemble": "entry median + EXIT majority", "counts": SMOKE_COUNTS},
                 "independence_note": "lr/epochs and the selection protocol were changed after seeing 2025 (pilot e) "
                                      "results: the F4 2025 evaluation is NOT a fully independent OOS test"}
    # ---------------- stage 1: F3 selection of a common update U*
    fold = "F3"
    train, val = FOLDS_A2[fold]
    cells = {c: AE.load_cell(c, fold=fold, allow_test=False) for c in SMOKE_COUNTS}
    snaps, upd_logs, split_ok = {}, {}, None
    for seed in seeds:
        tr = AP.Trainer(cells, SMOKE_COUNTS, G3_ONLY_W, train, val, cfg, seed=seed, fold=fold, comparators=comps)
        v0 = tr.validate(device="cpu")
        rep.setdefault("u0_reward_zero", {})[f"F3_seed{seed}"] = all(c["reward"] == 0.0 for c in v0["cells"].values())
        logs = []
        state7 = None
        for u in range(1, cfg.total_updates + 1):
            tu = time.time()
            rec = tr.run_update()
            rec["sec"] = round(time.time() - tu, 2)
            rec.pop("heads", None)
            logs.append(rec)
            if seed == 0 and u == 7:
                state7 = tr.state_dict()
            if u in E2_CANDIDATES:
                snaps[(seed, u)] = copy_state(tr)
        upd_logs[f"F3_seed{seed}"] = logs
        if seed == 0:                                       # split-resume exactness on the selection fold
            tb = AP.Trainer(cells, SMOKE_COUNTS, G3_ONLY_W, train, val, cfg, seed=0, fold=fold, comparators=comps)
            for _ in range(3):
                tb.run_update()
            torch.save(tb.state_dict(), PD / "split_u3.pt")
            del tb
            tcx = AP.Trainer(cells, SMOKE_COUNTS, G3_ONLY_W, train, val, cfg, seed=0, fold=fold, comparators=comps)
            tcx.load_state_dict(torch.load(PD / "split_u3.pt", map_location="cpu", weights_only=False))
            for _ in range(4):
                tcx.run_update()
            s7 = tcx.state_dict()
            split_ok = all(AP.tensors_equal(state7[k], s7[k]) for k in ("model", "opt", "env", "torch_rng",
                                                                        "cuda_rng", "update"))
            vb = tr.validate(device="cpu")
            vs = tr.validate(batched=False, device="cpu")
            rep["val_parity"] = {"actions_equal": all(all(np.array_equal(x[0], y[0]) and np.array_equal(x[1], y[1])
                                                          for x, y in zip(vb["_actions"][c], vs["_actions"][c]))
                                                      for c in vb["cells"]),
                                 "net_mdd_max_abs": max(abs(vb["cells"][c][k] - vs["cells"][c][k]) for c in vb["cells"]
                                                        for k in ("net_rl", "mdd_rl"))}
        log(f"e2 F3 seed {seed} trained {sum(x['sec'] for x in logs):.0f}s")
    probe = AP.Trainer(cells, SMOKE_COUNTS, G3_ONLY_W, train, val, cfg, seed=0, fold=fold, comparators=comps)
    table = []
    for u in E2_CANDIDATES:
        row = {"update": u}
        for seed in seeds:
            probe.model.load_state_dict(snaps[(seed, u)])
            v = probe.validate(device="cpu")
            row[f"seed{seed}_score"] = v["score"]
            row[f"seed{seed}_cells"] = {c: x["excess_vs_max_baseline"] for c, x in v["cells"].items()}
        ve = probe.validate(device="cpu", policy=AP.ensemble_policy([e2_model(cfg, snaps[(s_, u)]) for s_ in seeds]))
        row["ensemble_score"] = ve["score"]
        row["ensemble"] = val_report(ve, with_boot=False)
        table.append(row)
        log(f"e2 F3 u{u}: ensemble {ve['score']:.1f} seeds "
            f"{[round(row[f'seed{s_}_score'], 1) for s_ in seeds]}")
    best = max(table, key=lambda r: (r["ensemble_score"], -r["update"]))
    U = int(best["update"])
    rep["selection_F3"] = {"table": table, "U_star": U, "U_star_score": best["ensemble_score"]}
    for seed in seeds:
        registry.record(REGISTRY, {"experiment": f"RL allocator pilot (e2) F3 selection seed {seed}", "role": "trial",
                                   "n_trials": 1, "n_simulations": 1,
                                   "config": {"fold": fold, "seed": seed, "cfg": dataclasses_asdict(cfg),
                                              "candidates": E2_CANDIDATES},
                                   "result_summary": {"seed_scores": {r["update"]: r[f"seed{seed}_score"] for r in table},
                                                      "U_star": U}})
    del cells, probe
    AP._CMP_CACHE.clear()
    # ---------------- stage 2: F4 retrain to U* and a single 2025 evaluation
    fold = "F4"
    train, val = FOLDS_A2[fold]
    cells = {c: AE.load_cell(c, fold=fold, allow_test=False) for c in SMOKE_COUNTS}
    try:
        AP.Trainer(cells, SMOKE_COUNTS, G3_ONLY_W, FOLDS_A2["F3"][0], FOLDS_A2["F3"][1], cfg, seed=0, fold="F3")
        fold_refused = False
    except ValueError:
        fold_refused = True
    models, per_seed = [], {}
    for seed in seeds:
        tr = AP.Trainer(cells, SMOKE_COUNTS, G3_ONLY_W, train, val, cfg, seed=seed, fold=fold, comparators=comps)
        logs = []
        for _ in range(U):
            tu = time.time()
            rec = tr.run_update()
            rec["sec"] = round(time.time() - tu, 2)
            rec.pop("heads", None)
            logs.append(rec)
        upd_logs[f"F4_seed{seed}"] = logs
        st = copy_state(tr)
        torch.save({"model": st, "identity": tr.identity, "update": U}, PD / f"F4_seed{seed}_u{U}.pt")
        models.append(e2_model(cfg, st))
        per_seed[seed] = tr
        log(f"e2 F4 seed {seed} retrained to u{U} {sum(x['sec'] for x in logs):.0f}s")
    te = per_seed[seeds[0]]
    ve = te.validate(device="cpu", policy=AP.ensemble_policy(models))            # the single gated 2025 evaluation
    E = val_report(ve, with_boot=True)
    rep["F4_ensemble"] = E
    rep["F4_seeds_report_only"] = {}
    for seed in seeds:
        vs_ = per_seed[seed].validate(device="cpu")
        rep["F4_seeds_report_only"][str(seed)] = val_report(vs_, with_boot=True)
    c4 = {c: AE.load_cell(c, fold=fold, cadence_h=4, allow_test=False) for c in ("o2_p0.5", "o5_p2.0")}
    cfg4 = AP.AllocPPOConfig(**{**dataclasses_asdict(cfg), "cadence_h": 4, "n_steps": 32})
    r4 = AP.Trainer(c4, {"o2_p0.5": 8, "o5_p2.0": 8}, G3_ONLY_W, train, val, cfg4, seed=0, fold=fold).run_update()
    allu = [x for L_ in upd_logs.values() for x in L_]
    rep["contracts"] = {
        "illegal_actions==0": sum(x["illegal"] for x in allu) == 0,
        "nan_inf==0": sum(x["nonfinite"] for x in allu) == 0,
        "reward_identity<=1e-6": max(x["identity_err"] for x in allu) <= 1e-6
        and all(c["identity_err"] <= 1e-6 for c in E["cells"].values()),
        "gross_reserved<=2": max(x["gross_reserved_max"] for x in allu) <= C_GROSS + 1e-12
        and all(c["gross_reserved_max"] <= C_GROSS + 1e-12 for c in E["cells"].values()),
        "update0_val_reward==0": all(rep["u0_reward_zero"].values()),
        "split_resume_exact": bool(split_ok), "fold_mismatch_refused": fold_refused,
        "val_batched==serial": rep["val_parity"]["actions_equal"] and rep["val_parity"]["net_mdd_max_abs"] == 0.0,
        "cadence_4h_ok": cfg4.episode_steps == 540 and r4["illegal"] == 0 and r4["nonfinite"] == 0}
    ce = E["cells"].values()
    boots = [p for c in ce for p in c["boot_p05"].values()]
    rep["pass_criteria"] = {
        "contracts_9of9": all(rep["contracts"].values()),
        "net4>0_6of6": all(c["net_rl"] > 0 for c in ce),
        "net4>max(C1C4,G3_ONLY)_6of6": all(c["excess_vs_max_baseline"] > 0 for c in ce),
        "mdd<G3_ONLY_6of6": all(mdd_gate(c) for c in ce),
        "boot_p05>0_18of18": all(p > 0 for p in boots),
        "ensemble_differs_from_baseline": sum(c["deviate_entries"] + c["nonhold_open"] for c in ce) > 0}
    rep["boot_positive_count"] = f"{sum(p > 0 for p in boots)}/{len(boots)}"
    rep["pilot_pass"] = bool(all(rep["pass_criteria"].values()))
    rep["curves"] = {k: e2_curves(v) for k, v in upd_logs.items()}
    rep["kl_early_stop_ratio"] = {k: float(np.mean([x["kl_early_stop"] for x in v])) for k, v in upd_logs.items()}
    rep.update(git_head=git("rev-parse", "HEAD"), created_utc=datetime.now(timezone.utc).isoformat(),
               runtime_sec=round(time.time() - t0, 1), test_accessed=False,
               code_sha256={k: sha(ROOT / f"btcusdt_quant/rl/{k}.py") for k in ("allocator_model", "allocator_ppo",
                                                                                 "allocator_vec_env", "allocator_env")})
    dump(PD / "pilot_e2_report.json", rep)
    for seed in seeds:
        registry.record(REGISTRY, {"experiment": f"RL allocator pilot (e2) F4 eval seed {seed} (U*={U})", "role": "trial",
                                   "n_trials": 1, "n_simulations": 1,
                                   "config": {"fold": "F4", "seed": seed, "U_star": U, "cfg": dataclasses_asdict(cfg)},
                                   "result_summary": {"ensemble_pass": rep["pilot_pass"],
                                                      "seed_score": rep["F4_seeds_report_only"][str(seed)]["score"]}})
    log(f"pilot (e2) {'PASS' if rep['pilot_pass'] else 'FAIL'} U*={U} {rep['pass_criteria']} boots {rep['boot_positive_count']}")


# ================================================================ causal 7-sleeve regime router (information check)
ROUTER_WINDOWS = {"F1": ("2022-01-01", "2023-01-01"), "F2": ("2023-01-01", "2024-01-01"),
                  "F3": ("2024-01-01", "2025-01-01"), "F4": ("2025-01-01", "2026-01-01")}


def router_features(cd, T: np.ndarray, grid_cache: dict) -> dict:
    """Per sleeve causal unit-net4 lookback sums (30/90/180 d, availability epoch only) and availability at T."""
    from btcusdt_quant.rl import allocator_state as ast
    T_max = int(T.max())
    out = {}
    for s in SLEEVES:
        rel = PRE / ("g3_family/" + cd.cell + "/" + s if s in G3_FAMILY else "common/" + s)
        key = str(rel)
        if key not in grid_cache:
            gcols = [c for c in sp.OBS_COLUMNS["grid"] if c not in ("sleeve_id", "exec_cell")]
            grid_cache[key] = (sp.read_observation(rel, "grid", T_max, columns=gcols),
                               sp.read_observation(rel, "ledger", T_max))
        g, led = grid_cache[key]
        f = ast.sleeve_channels(s, g, led, cd.c[:len(g)], T, long_mtm=True)
        out[s] = {"avail": f[f"{s}_available"].to_numpy() == 1,
                  **{lb: f[f"{s}_{col}"].to_numpy(float) for lb, col in
                     (("30d", "mtm_30d"), ("90d", "mtm_90d"), ("180d", "mtm_180d"))}}
    return out


def run_router(cd, feats: dict, Tf: np.ndarray, lookback: str, a: int, b: int) -> dict:
    from btcusdt_quant.rl import allocator_router as AR, allocator_vec_env as AV, allocator_ppo as AP
    H = 3600 * 10**9
    L = (b - a) // H
    env = AV.VecAllocatorEnv(cd, 1, static_weights=C1C4_W)
    obs = env.reset(np.array([a]), L)
    z = np.zeros((1, len(SLEEVES)), np.int64)
    k0 = int(np.searchsorted(Tf, a))
    if Tf[k0] != a:
        raise SystemExit("router feature grid misaligned")
    sc = np.stack([feats[s][lookback] for s in SLEEVES], 1)
    av = np.stack([feats[s]["avail"] for s in SLEEVES], 1)
    ser, sel = np.zeros(L), np.zeros(len(SLEEVES))
    gmax, ident, avail_mismatch = 0.0, 0.0, 0
    for i in range(L):
        lv = AR.router_levels(sc[k0 + i:k0 + i + 1], av[k0 + i:k0 + i + 1])
        me = obs["masks"][0]
        avail_mismatch += int((av[k0 + i] != me[0, :, 4]).sum())
        lv = np.where(me[np.arange(1)[:, None], np.arange(len(SLEEVES))[None, :], lv], lv, 0)
        sel += (lv[0] > 0)
        obs, r, done, info = env.step(lv, z, z)
        ex, dd, to = AP.reward_parts(info)
        ident = max(ident, float(np.abs(r - (ex - dd - to)).max()))
        gmax = max(gmax, float(info["gross_reserved"][0]))
        ser[i] = info["net_rl"][0]
    c1c4, mdd_c = AP.comparator_book(cd, a, L, 1, C1C4_W)
    g3, mdd_g = AP.comparator_book(cd, a, L, 1, G3_ONLY_W)
    return {"rl": ser, "C1C4": c1c4, "G3_ONLY": g3, "mdd_rl": float(env.rl.mdd[0]), "mdd_C1C4": mdd_c,
            "mdd_G3_ONLY": mdd_g, "trades": int(env.rl.new_alloc[0]), "selection_hours": sel.tolist(), "hours": L,
            "gross_reserved_max": gmax, "identity_err": ident, "avail_mismatch": avail_mismatch}


def series_mdd(x: np.ndarray) -> float:
    eq = np.r_[0.0, np.cumsum(x)]
    return float((np.maximum.accumulate(eq) - eq).max())


def cell_metrics(rs: list, boot: bool) -> dict:
    """rs: one or more consecutive window results (stitched)."""
    rl = np.concatenate([r["rl"] for r in rs])
    c1, g3 = np.concatenate([r["C1C4"] for r in rs]), np.concatenate([r["G3_ONLY"] for r in rs])
    best = "C1C4" if c1.sum() >= g3.sum() else "G3_ONLY"
    base = c1 if best == "C1C4" else g3
    out = {"net_router": float(rl.sum()), "net_C1C4": float(c1.sum()), "net_G3_ONLY": float(g3.sum()),
           "max_baseline": best, "excess_vs_max": float(rl.sum() - base.sum()),
           "excess_vs_C1C4": float(rl.sum() - c1.sum()), "excess_vs_G3_ONLY": float(rl.sum() - g3.sum()),
           "mdd_router": series_mdd(rl), "mdd_C1C4": series_mdd(c1), "mdd_G3_ONLY": series_mdd(g3),
           "trades": int(sum(r["trades"] for r in rs)),
           "differs_from_C1C4": bool(np.abs(rl - c1).max() > 1e-9), "differs_from_G3_ONLY": bool(np.abs(rl - g3).max() > 1e-9)}
    out["mdd_max_baseline"] = out[f"mdd_{best}"]
    if boot:
        d = (rl - base).reshape(-1, 24).sum(1)
        out["boot_p05"] = {str(bl): boot_p05(d, bl) for bl in (20, 60, 120)}
    return out


def cmd_router(args) -> None:
    from btcusdt_quant.rl import allocator_env as AE
    t0 = time.time()
    RD = OUT / "router"
    RD.mkdir(parents=True, exist_ok=True)
    ts = lambda x: pd.Timestamp(x, tz="UTC").value  # noqa: E731
    cells = list(SMOKE_COUNTS)
    lbs = ("30d", "90d", "180d")
    res = {lb: {w: {} for w in ROUTER_WINDOWS} for lb in lbs}
    grid_cache: dict = {}
    contracts = {"identity_err_max": 0.0, "gross_reserved_max": 0.0, "avail_mismatch": 0}
    for cell in cells:
        cd = AE.load_cell(cell, fold="F4", allow_test=False)     # P&L data are fold-independent; no observations used
        Tf = cd.T1h[(cd.T1h >= ts("2022-01-01")) & (cd.T1h < ts("2026-01-01"))]
        feats = router_features(cd, Tf, grid_cache)
        for k in [k for k in grid_cache if "g3_family" in k]:
            del grid_cache[k]
        for lb in lbs:
            for w, (a, b) in ROUTER_WINDOWS.items():
                r = run_router(cd, feats, Tf, lb, ts(a), ts(b))
                res[lb][w][cell] = r
                contracts["identity_err_max"] = max(contracts["identity_err_max"], r["identity_err"])
                contracts["gross_reserved_max"] = max(contracts["gross_reserved_max"], r["gross_reserved_max"])
                contracts["avail_mismatch"] += r["avail_mismatch"]
        log(f"router {cell} done {time.time() - t0:.0f}s")
    rep: dict = {"spec": {"lookbacks": lbs, "top_k": 2, "level": 1.0, "cadence_h": 1, "windows": ROUTER_WINDOWS,
                          "selection": "F1-F3 stitched min_cell[router - max(C1C4, G3_ONLY)]; ties: min-cell boot "
                                       "p05 (60d), lower max-cell MDD, longer lookback",
                          "score_input": "causal unit net4 sum over the lookback (sleeve_channels mtm, availability "
                                         "epoch only)", "keep_hold_fixed": True,
                          "data": "F4 cell load (router uses no model observations; P&L rows fold-independent)"},
                 "per_window": {}, "selection": {}}
    sel_rows = []
    for lb in lbs:
        rep["per_window"][lb] = {w: {c: cell_metrics([res[lb][w][c]], boot=True) for c in cells} for w in ROUTER_WINDOWS}
        st = {c: cell_metrics([res[lb][w][c] for w in ("F1", "F2", "F3")], boot=True) for c in cells}
        row = {"lookback": lb, "score": min(x["excess_vs_max"] for x in st.values()),
               "min_boot60": min(x["boot_p05"]["60"] for x in st.values()),
               "max_mdd": max(x["mdd_router"] for x in st.values()), "cells": st}
        sel_rows.append(row)
    order = sorted(sel_rows, key=lambda r: (-r["score"], -r["min_boot60"], r["max_mdd"], -int(r["lookback"][:-1])))
    chosen = order[0]["lookback"]
    rep["selection"] = {"rows": [{k: v for k, v in r.items() if k != "cells"} for r in sel_rows],
                        "stitched_cells": {r["lookback"]: r["cells"] for r in sel_rows}, "chosen": chosen}
    F4 = {c: cell_metrics([res[chosen]["F4"][c]], boot=True) for c in cells}
    rep["F4"] = F4
    sel_freq = {}
    for lb in lbs:
        for w in ROUTER_WINDOWS:
            tot = np.sum([res[lb][w][c]["selection_hours"] for c in cells], axis=0)
            hrs = sum(res[lb][w][c]["hours"] for c in cells)
            sel_freq.setdefault(lb, {})[w] = {s: round(float(tot[i] / hrs), 4) for i, s in enumerate(SLEEVES)}
    rep["selection_frequency"] = sel_freq
    rep["contracts"] = {"reward_identity<=1e-6": contracts["identity_err_max"] <= 1e-6,
                        "gross_reserved<=2": contracts["gross_reserved_max"] <= C_GROSS + 1e-12,
                        "router_avail==env_mask": contracts["avail_mismatch"] == 0,
                        "economic_difference_vs_both_baselines_6of6": all(
                            x["differs_from_C1C4"] and x["differs_from_G3_ONLY"] for x in F4.values()),
                        "test_accessed": False, "raw": contracts}
    boots = [p for x in F4.values() for p in x["boot_p05"].values()]
    rep["pass_criteria"] = {
        "net4>max(C1C4,G3_ONLY)_6of6": all(x["excess_vs_max"] > 0 for x in F4.values()),
        "mdd<mdd(max-net baseline)_6of6": all(x["mdd_router"] < x["mdd_max_baseline"] for x in F4.values()),
        "boot_p05>0_18of18": all(p > 0 for p in boots),
        "contracts": all(v for k, v in rep["contracts"].items() if k not in ("test_accessed", "raw"))}
    rep["boot_positive_count"] = f"{sum(p > 0 for p in boots)}/{len(boots)}"
    rep["mdd_gate_baseline"] = {c: x["max_baseline"] for c, x in F4.items()}
    rep["router_pass"] = bool(all(rep["pass_criteria"].values()))
    rep.update(git_head=git("rev-parse", "HEAD"), created_utc=datetime.now(timezone.utc).isoformat(),
               runtime_sec=round(time.time() - t0, 1),
               code_sha256={k: sha(ROOT / f"btcusdt_quant/rl/{k}.py") for k in ("allocator_router", "allocator_state",
                                                                                 "allocator_vec_env", "allocator_env")})
    dump(RD / "router_report.json", rep)
    registry.record(REGISTRY, {"experiment": "RL allocator causal regime router (lookback selection F1-F3)",
                               "role": "trial", "n_trials": len(lbs), "n_simulations": len(lbs) * 4 * len(cells),
                               "config": rep["spec"],
                               "result_summary": {"chosen": chosen, "scores": {r["lookback"]: r["score"] for r in sel_rows}}})
    registry.record(REGISTRY, {"experiment": f"RL allocator causal regime router F4 2025 eval ({chosen})",
                               "role": "evaluation", "n_trials": 0, "n_simulations": len(cells),
                               "config": {"lookback": chosen},
                               "result_summary": {"pass": rep["router_pass"], "boot": rep["boot_positive_count"]}})
    log(f"router {'PASS' if rep['router_pass'] else 'FAIL'} chosen {chosen} {rep['pass_criteria']} boots "
        f"{rep['boot_positive_count']}")


# ================================================================ REGIME-SHORT-24H (Codex spec 2026-10-11)
def cmd_regime_short(args) -> None:
    regime_experiment("short")


def cmd_regime_bidir(args) -> None:
    regime_experiment("bidir")


def cmd_regime_bidir_r2(args) -> None:
    regime_experiment("bidir_r2")


def regime_inputs():
    """DEV-only market / funding (never opens a TEST path) + causal state features at 4h decisions."""
    from btcusdt_quant.rl import dev_data as DD, regime_short as RS
    b2 = load("nm_b2_rs", "out/run_new_model_batch2_20261010.py")
    minutes, funding, in_hash = DD.load_dev()
    m = b2.Market.from_frames(minutes, funding)
    del minutes
    st = pd.read_parquet(OUT / "state/state_1h.parquet", columns=["T", "exec_cell"] + list(RS.FEATURES))
    st = st[st.exec_cell == CELL_TAG[PRIMARY]].sort_values("T").reset_index(drop=True)
    sp.guard_times(st["T"].to_numpy(np.int64), False, "regime state")
    st = st[st["T"].to_numpy(np.int64) % (4 * 3600 * 10**9) == 0].reset_index(drop=True)
    in_hash["state_1h"] = sha(OUT / "state/state_1h.parquet")
    return b2, m, st, in_hash


def ma100_bear(m, T: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Bear regime: close_T < mean close of the last 100 completed UTC days (the running day excluded)."""
    day = m.t // (86400 * 10**9)
    last = np.r_[day[1:] != day[:-1], True]                       # last minute of each UTC day
    dclose, dday = m.c[last], day[last]
    end_t = (dday + 1) * 86400 * 10**9                             # day complete at its end
    cs = np.r_[0.0, np.cumsum(dclose)]
    k = np.searchsorted(end_t, T, "right")                         # completed days by T
    ma = np.where(k >= 100, (cs[k] - cs[np.maximum(k - 100, 0)]) / 100.0, np.nan)
    return np.where(np.isfinite(ma), m.c[d] < ma, False), ma


def regime_experiment(mode: str) -> None:
    from btcusdt_quant.rl import regime_short as RS
    t0 = time.time()
    name = {"short": "regime_short_24h", "bidir": "regime_bidir_24h_r1", "bidir_r2": "regime_bidir_24h_r2"}[mode]
    RD = OUT / name
    RD.mkdir(parents=True, exist_ok=True)
    b2, m, st, in_hash = regime_inputs()
    T = st["T"].to_numpy(np.int64)
    X = st[list(RS.FEATURES)].to_numpy(float)
    d = np.searchsorted(m.t, T) - 1
    if not np.array_equal(m.t[d] + sp.MIN, T):
        raise SystemExit("decision bars misaligned")
    y_s, lend = RS.short_labels(m.t, m.c, m.ft, m.fr, d)
    y_l, _ = RS.long_labels(m.t, m.c, m.ft, m.fr, d)
    bear, ma = ma100_bear(m, T, d)
    ts = lambda x: pd.Timestamp(x, tz="UTC").value  # noqa: E731
    cells = [(o, p) for o in (2, 5) for p in (0.5, 1.0, 2.0)]
    rep: dict = {"spec": {"mode": mode, "cadence": "4h", "features": RS.FEATURES, "lambdas": RS.LAMBDAS,
                          "model": "ridge, fold-train median/IQR, NaN->0, clip 10",
                          "lambda_cv": "train-internal year blocks (quarters if one year), score = held-out rule net",
                          "entry": "pred > 0", "hold_min": RS.HOLD_MIN, "weight": 1.0, "max_gross": 1,
                          "execution": "Batch-2 maker engine (event kind), 2 bps exit quote, 6 cells, 4 bps rt",
                          "regime": None if mode == "short" else "bear: close_T < MA100 (last 100 completed UTC "
                                                                  "daily closes) -> short model; bull -> long model",
                          "regime_training": ("short model on train & bear rows, long model on train & bull rows; "
                                              "normalizer and lambda CV on that subset" if mode == "bidir_r2"
                                              else "both models on all train rows, one normalizer"),
                          "train_rows": "label end <= val start - 24h (embargo)", "folds": FOLDS_A2,
                          "source": "local Binance USD-M BTCUSDT 1m + monthly funding archives, DEV loader "
                                    "(btcusdt_quant/rl/dev_data.py, TEST paths refused); state_1h DEV",
                          "data_cutoff": "2026-01-01 exclusive", "input_sha256": in_hash},
                 "folds": {}}
    sides = ("short",) if mode == "short" else ("short", "long")
    labels = {"short": y_s, "long": y_l}
    passes = {"net": [], "boot": [], "closed": []}
    for f, (tr_w, va_w) in FOLDS_A2.items():
        a_tr, b_tr = ts(tr_w[0]), ts(tr_w[1])
        a_va, b_va = ts(va_w[0]), ts(va_w[1])
        emb = a_va - RS.HOLD_MIN * sp.MIN
        tr = (T >= a_tr) & (T < b_tr) & (lend <= emb) & np.isfinite(y_s)
        va = (T >= a_va) & (T < b_va)
        med0, sc0 = RS.fit_norm(X[tr])
        c2 = m.c.copy()
        c2[int(np.searchsorted(m.t, emb)):] *= 1.7
        fr2 = np.where(m.ft > emb, m.fr * 1.7, m.fr)
        tam2 = {"short": RS.short_labels(m.t, c2, m.ft, fr2, d)[0], "long": RS.long_labels(m.t, c2, m.ft, fr2, d)[0]}
        X3 = X.copy()
        cut = a_va + (b_va - a_va) // 2
        X3[T > cut] = 99.0
        models, F = {}, {"train": tr_w, "val": va_w, "train_rows": int(tr.sum()), "val_decisions": int(va.sum()),
                         "bear_share_val": float(bear[va].mean()), "bear_share_train": float(bear[tr].mean()),
                         "models": {}, "tamper": {}}
        side = np.zeros(int(va.sum()), int)
        for sd in sides:
            y = labels[sd]
            trs = (tr & (bear if sd == "short" else ~bear)) if mode == "bidir_r2" else tr
            med, sc = RS.fit_norm(X[trs]) if mode == "bidir_r2" else (med0, sc0)
            lam, cvres = RS.cv_lambda(X[trs], y[trs], T[trs], lend[trs])
            w, b0 = RS.ridge(RS.apply_norm(X[trs], med, sc), y[trs], lam)
            pred = RS.apply_norm(X[va], med, sc) @ w + b0
            lam2, _ = RS.cv_lambda(X[trs], tam2[sd][trs], T[trs], lend[trs])
            w2, b02 = RS.ridge(RS.apply_norm(X[trs], med, sc), tam2[sd][trs], lam2)
            tr_used = trs
            p3 = RS.apply_norm(X3[va], med, sc) @ w + b0
            F["tamper"][sd] = {"train_labels_equal": bool(np.array_equal(y[tr_used], tam2[sd][tr_used])),
                               "model_equal": bool(lam2 == lam and np.array_equal(w, w2) and b0 == b02),
                               "pred_before_cut_equal": bool(np.array_equal(p3[T[va] <= cut], pred[T[va] <= cut]))}
            top = np.argsort(-np.abs(w))[:8]
            F["models"][sd] = {"lambda": lam, "cv": {str(k_): v for k_, v in cvres.items()}, "intercept": b0,
                               "coef_top": {RS.FEATURES[i]: float(w[i]) for i in top},
                               "pred_positive_share": float((pred > 0).mean()),
                               "label_mean_train": float(np.nanmean(y[tr_used])), "train_rows": int(tr_used.sum()),
                               "rule_label_sum_val": float(np.nansum(y[va][pred > 0]))}
            if mode == "short":
                side = np.where(pred > 0, -1, side)
            elif sd == "short":
                side = np.where(bear[va] & (pred > 0), -1, side)
            else:
                side = np.where(~bear[va] & (pred > 0), 1, side)
            models[sd] = (w, b0)
        F["side_share"] = {"short": float((side < 0).mean()), "long": float((side > 0).mean()),
                           "flat": float((side == 0).mean())}
        lo, hi = m.idx(pd.Timestamp(a_va, tz="UTC")), m.idx(pd.Timestamp(b_va, tz="UTC"))
        F["cells"] = {}
        for o, p in cells:
            trd, od = b2.simulate(m, "event", d[va], side, np.ones(int(va.sum())), o, b2.TTL_TREND, p, lo, hi,
                                  hold=RS.HOLD_MIN)
            bk = b2.Book(m, trd, od, lo, hi)
            wnd = bk.window(lo, hi)
            daily = bk.daily(lo, hi)
            boots = {str(bl): b2.stationary_boot_p05(daily, bl) for bl in (20, 60, 120)}
            days = pd.date_range(pd.Timestamp(a_va, tz="UTC"), periods=len(daily), freq="D")
            mon = pd.Series(daily, index=days).groupby(days.strftime("%Y-%m")).sum()
            top2 = float(mon.sort_values(ascending=False).iloc[:2].sum() / wnd["net4"]) if wnd["net4"] > 0 else None
            F["cells"][f"o{o}_p{p}"] = {"top2_month_share": top2,
                "net4": wnd["net4"], "net8_report_only": wnd["net8"], "closed": wnd["closed"], "win": wnd["win"],
                "mdd": wnd["mdd_1m"], "funding": wnd["funding"], "fill_rate": wnd["fill_notional_rate"],
                "long_net4": wnd["long_net4"], "short_net4": wnd["short_net4"], "long_closed": wnd["long_closed"],
                "short_closed": wnd["short_closed"], "boot_p05": boots,
                "monthly": {k_: float(v) for k_, v in mon.items()}}
            passes["net"].append(wnd["net4"] > 0)
            passes["boot"] += [v > 0 for v in boots.values()]
            passes["closed"].append(wnd["closed"] >= 30)
        rep["folds"][f] = F
        log(f"{name} {f}: lambdas {[F['models'][s]['lambda'] for s in sides]} sides {F['side_share']} net4 "
            f"{[round(v['net4'], 1) for v in F['cells'].values()]} closed {[v['closed'] for v in F['cells'].values()]}")
    tam_ok = all(all(v for x in F["tamper"].values() for v in x.values()) for F in rep["folds"].values())
    rep["pass_criteria"] = {"net4>0": f"{sum(passes['net'])}/{len(passes['net'])}",
                            "boot_p05>0": f"{sum(passes['boot'])}/{len(passes['boot'])}",
                            "closed>=30": f"{sum(passes['closed'])}/{len(passes['closed'])}", "tamper_all": tam_ok}
    rep["pass"] = bool(all(passes["net"]) and all(passes["boot"]) and all(passes["closed"]) and tam_ok)
    rep["yearly_o2_p0.5_net4"] = {F["val"][0][:4]: F["cells"]["o2_p0.5"]["net4"] for F in rep["folds"].values()}
    rep["yearly_rule_label_sum_short"] = {F["val"][0][:4]: F["models"]["short"]["rule_label_sum_val"]
                                          for F in rep["folds"].values()}
    rep.update(git_head=git("rev-parse", "HEAD"), created_utc=datetime.now(timezone.utc).isoformat(),
               runtime_sec=round(time.time() - t0, 1), test_accessed=False,
               test_access_note="DEV loader refuses the stage-B snapshot and 2026 funding archives. The mixed market "
                                "parquet is read with an open_time < 2026-01-01 predicate: its last row group "
                                "(2025-12-24..2026-06-30) is decoded and the 2026 rows dropped before use; the input "
                                "hash covers the DEV slice only. state_1h was generated earlier through b2.load_all "
                                "(which opened the stage-B snapshot); its DEV rows are prefix/tamper-verified causal",
               code_sha256={"regime_short": sha(ROOT / "btcusdt_quant/rl/regime_short.py"),
                            "dev_data": sha(ROOT / "btcusdt_quant/rl/dev_data.py"), "script": sha(Path(__file__))})
    dump(RD / {"short": "regime_short_report_devloader.json", "bidir": "regime_bidir_report.json",
               "bidir_r2": "regime_bidir_r2_report.json"}[mode], rep)
    registry.record(REGISTRY, {"experiment": {"short": "REGIME-SHORT-24H rerun (DEV-only loader)",
                                              "bidir": "REGIME-BIDIR-24H-r1 (MA100 regime, short/long ridge)",
                                              "bidir_r2": "REGIME-BIDIR-24H-r2 (regime-specific training)"}[mode],
                               "role": "trial", "n_trials": len(RS.LAMBDAS) * len(sides),
                               "n_simulations": 4 * len(cells),
                               "config": {k_: v for k_, v in rep["spec"].items() if k_ not in ("folds", "input_sha256")},
                               "input_hashes": in_hash,
                               "result_summary": {"pass": rep["pass"], **rep["pass_criteria"]}})
    log(f"{name} {'PASS' if rep['pass'] else 'FAIL'} {rep['pass_criteria']} {rep['runtime_sec']}s")


# ================================================================ consistent gates: G3 baseline, r1 rescoring, MA100 veto
G_CELLS = [(o, p) for o in (2, 5) for p in (0.5, 1.0, 2.0)]


def g3_setup():
    """DEV-only market (dev_data), G3 causal state and the paper G3 sleeve signals (long-only S180 W180-P65,
    short-only F180 V-ENS), built with the unchanged LBR-FUND-MAT / Batch-5 code."""
    from btcusdt_quant.rl import dev_data as DD
    MAT = load("lbr_mat_gates", "out/run_lbr_fund_materialize_20261010.py")
    minutes, funding, in_hash = DD.load_dev()
    m = MAT.b2.Market.from_frames(minutes, funding)
    del minutes
    dec4 = np.arange(239, m.N, 240)
    st = MAT.b5.build_state(m, dec4)
    return MAT, m, dec4, st, in_hash


def g3_signals(MAT, st) -> dict:
    return {"long": MAT.L.s180_signal(st), "short": MAT.short_signal(st)}


def book_series(b2, m, dec, side, w, cell, kind="state", entry_ok=None, lo=0, hold=0):
    """Continuous run -> (daily net4 2022-01-01..2025-12-31, closed per year, Book)."""
    from btcusdt_quant.rl import gates as GT
    o, p = cell
    tr, od = b2.simulate(m, kind, dec, side, w, o, b2.TTL_TREND, p, lo, m.N, hold=hold, entry_ok=entry_ok)
    bk = b2.Book(m, tr, od, lo, m.N)
    a, b = m.idx(GT.START), m.idx(GT.END)
    if b != m.N:
        raise SystemExit("DEV market must end at 2025-12-31 23:59")
    closed = {}
    for y in GT.YEARS:
        ya, yb = m.idx(pd.Timestamp(f"{y}-01-01", tz="UTC")), m.idx(pd.Timestamp(f"{y + 1}-01-01", tz="UTC"))
        closed[y] = bk.window(ya, yb)["closed"]
    return bk.daily(a, b), closed, bk, tr


def daily8(bk, a: int, b: int) -> np.ndarray:
    """net8 daily (report only): net4 minus another 2 bps x weight at every entry and exit leg."""
    extra = np.zeros(bk.m.N)
    if len(bk.s):
        np.add.at(extra, bk.j0, 2 * bk.w)
        np.add.at(extra, bk.jx, 2 * bk.w)
    return (bk.pnl - extra)[a:b].reshape(-1, 1440).sum(1)


def stitch_folds(parts: list) -> tuple[np.ndarray, ...]:
    """Concatenate per-fold decision arrays (fold order); decisions must be strictly increasing across folds."""
    cols = [np.concatenate([p_[k] for p_ in parts]) for k in range(len(parts[0]))]
    if len(cols[0]) and np.any(np.diff(cols[0]) <= 0):
        raise ValueError("stitched decisions not strictly increasing (fold windows overlap or unsorted)")
    return tuple(cols)


def g3_combined(b2, m, dec4, sig: dict, entry_ok: dict | None = None) -> dict:
    out = {}
    for cell in G_CELLS:
        parts = {}
        for sd in ("long", "short"):
            parts[sd] = book_series(b2, m, dec4, sig[sd]["side"], sig[sd]["w"], cell,
                                    entry_ok=None if entry_ok is None else entry_ok[sd])
        dl, cl, bkl, trl = parts["long"]
        ds, cs, bks, trs = parts["short"]
        import btcusdt_quant.rl.gates as GT
        a8, b8 = m.idx(GT.START), m.idx(GT.END)
        out[f"o{cell[0]}_p{cell[1]}"] = {"daily": dl + ds, "closed": {y: cl[y] + cs[y] for y in cl},
                                         "daily8": daily8(bkl, a8, b8) + daily8(bks, a8, b8),
                                         "long_daily": dl, "short_daily": ds, "books": (bkl, bks), "trades": (trl, trs)}
    return out


def veto_entry_ok(side: np.ndarray, allowed_at: np.ndarray) -> tuple[np.ndarray, list]:
    """Episode = maximal run of the same nonzero target side. Its permission is fixed at its first decision; a vetoed
    episode stays vetoed until the target goes flat (no late entry after an in-episode regime flip)."""
    ok = np.ones(len(side), bool)
    eps, k = [], 0
    n = len(side)
    while k < n:
        if side[k] == 0:
            k += 1
            continue
        j = k
        while j + 1 < n and side[j + 1] == side[k]:
            j += 1
        allow = bool(allowed_at[k])
        ok[k:j + 1] = allow
        eps.append((k, j, int(side[k]), allow))
        k = j + 1
    return ok, eps


def cmd_gates(args) -> None:
    import btcusdt_quant.rl.gates as GT
    t0 = time.time()
    GD = OUT / "gates"
    GD.mkdir(parents=True, exist_ok=True)
    MAT, m, dec4, st, in_hash = g3_setup()
    b2 = MAT.b2
    sig = g3_signals(MAT, st)
    log(f"gates: G3 state/signals {time.time() - t0:.0f}s")
    # ---------------- baseline: paper G3 combined (reference reproduction)
    base = g3_combined(b2, m, dec4, sig)
    gb = GT.evaluate({c: {"daily": v["daily"], "closed": v["closed"]} for c, v in base.items()})
    pooled = [x["pooled_net4"] for x in gb["cells"].values()]
    p60 = [x["pooled_boot_p05"]["60"] for x in gb["cells"].values()]
    gb["reference_check"] = {"diag_year_boot": gb["diagnostics"]["year_cell_block_boot_p05>0"],
                             "pooled_boot60_range": [min(p60), max(p60)], "pooled_net4_range": [min(pooled), max(pooled)],
                             "expected": {"diag": "37/72", "boot60": [5.068, 5.872], "net4": [16136.077, 16967.267]}}
    gb["reference_ok"] = bool(gb["diagnostics"]["year_cell_block_boot_p05>0"] == "37/72"
                              and abs(min(p60) - 5.068) < 5e-4 and abs(max(p60) - 5.872) < 5e-4
                              and abs(min(pooled) - 16136.077) < 5e-3 and abs(max(pooled) - 16967.267) < 5e-3)
    gb.update(input_sha256=in_hash, git_head=git("rev-parse", "HEAD"))
    dump(GD / "gate_g3_combined_baseline.json", gb)
    log(f"gates: G3 baseline {gb['absolute']} diag {gb['diagnostics']} ref_ok {gb['reference_ok']} "
        f"boot60 {min(p60):.3f}~{max(p60):.3f} net {min(pooled):.3f}~{max(pooled):.3f}")
    base_daily = {c: v["daily"] for c, v in base.items()}
    # ---------------- experiment 1: REGIME-BIDIR-24H-r1 rescored on one continuous 2022..2025 run
    from btcusdt_quant.rl import regime_short as RS
    r1 = json.loads((OUT / "regime_bidir_24h_r1/regime_bidir_report.json").read_text(encoding="utf-8"))
    stx = pd.read_parquet(OUT / "state/state_1h.parquet", columns=["T", "exec_cell"] + list(RS.FEATURES))
    stx = stx[stx.exec_cell == CELL_TAG[PRIMARY]].sort_values("T").reset_index(drop=True)
    sp.guard_times(stx["T"].to_numpy(np.int64), False, "state")
    stx = stx[stx["T"].to_numpy(np.int64) % (4 * 3600 * 10**9) == 0].reset_index(drop=True)
    T = stx["T"].to_numpy(np.int64)
    X = stx[list(RS.FEATURES)].to_numpy(float)
    d = np.searchsorted(m.t, T) - 1
    y_s, lend = RS.short_labels(m.t, m.c, m.ft, m.fr, d)
    y_l, _ = RS.long_labels(m.t, m.c, m.ft, m.fr, d)
    bear, _ = ma100_bear(m, T, d)
    ts = lambda x: pd.Timestamp(x, tz="UTC").value  # noqa: E731
    dd_all, side_all, same_model = [], [], {}
    for f, (tr_w, va_w) in FOLDS_A2.items():
        emb = ts(va_w[0]) - RS.HOLD_MIN * sp.MIN
        tr = (T >= ts(tr_w[0])) & (T < ts(tr_w[1])) & (lend <= emb) & np.isfinite(y_s)
        va = (T >= ts(va_w[0])) & (T < ts(va_w[1]))
        med, sc = RS.fit_norm(X[tr])
        side = np.zeros(int(va.sum()), int)
        chk = []
        for sd, y in (("short", y_s), ("long", y_l)):
            lam, _ = RS.cv_lambda(X[tr], y[tr], T[tr], lend[tr])
            w, b0 = RS.ridge(RS.apply_norm(X[tr], med, sc), y[tr], lam)
            pred = RS.apply_norm(X[va], med, sc) @ w + b0
            ref = r1["folds"][f]["models"][sd]
            chk.append(lam == ref["lambda"] and abs(b0 - ref["intercept"]) < 1e-9
                       and abs(float((pred > 0).mean()) - ref["pred_positive_share"]) < 1e-12)
            side = np.where((bear[va] if sd == "short" else ~bear[va]) & (pred > 0), -1 if sd == "short" else 1, side)
        same_model[f] = bool(all(chk))
        dd_all.append(d[va])
        side_all.append(side)
    dd_all, side_all = stitch_folds(list(zip(dd_all, side_all)))
    lo = m.idx(GT.START)
    r1c = {}
    for cell in G_CELLS:
        daily, closed, bk, _ = book_series(b2, m, dd_all, side_all, np.ones(len(side_all)), cell, kind="event", lo=lo,
                                           hold=RS.HOLD_MIN)
        r1c[f"o{cell[0]}_p{cell[1]}"] = {"daily": daily, "closed": closed}
    g1 = GT.evaluate(r1c, baseline=base_daily)
    g1.update(model_recomputed_equal_r1=same_model, continuous=True,
              note="fold models recomputed by the same deterministic code (lambda, intercept and positive share equal "
                   "the r1 report); decisions 2022..2025 stitched by fold and executed in ONE continuous simulation "
                   "from 2022-01-01 (positions may carry across year ends, unlike the per-fold r1 runs)",
              git_head=git("rev-parse", "HEAD"))
    dump(GD / "r1_rescore_continuous.json", g1)
    log(f"gates: r1 rescore {g1['absolute']} {g1['replacement']} same_model {same_model}")
    # ---------------- experiment 2: G3-MA100-ENTRY-VETO-r1
    T4 = m.t[dec4] + sp.MIN
    bear4, _ = ma100_bear(m, T4, dec4)
    ok, eps = {}, {}
    ok["long"], eps["long"] = veto_entry_ok(sig["long"]["side"], ~bear4)
    ok["short"], eps["short"] = veto_entry_ok(sig["short"]["side"], bear4)
    veto = g3_combined(b2, m, dec4, sig, entry_ok=ok)
    g2 = GT.evaluate({c: {"daily": v["daily"], "closed": v["closed"]} for c, v in veto.items()}, baseline=base_daily)
    # vetoed episodes (start in 2022..2025) and the original G3 P&L of their trades
    s22, s26 = m.idx(GT.START), m.idx(GT.END)
    vstat = {}
    for sd in ("long", "short"):
        v_eps = [e for e in eps[sd] if not e[3] and s22 <= dec4[e[0]] < s26]
        a_eps = [e for e in eps[sd] if e[3] and s22 <= dec4[e[0]] < s26]
        cells_pnl = {}
        for c, v in base.items():
            trd = v["trades"][0 if sd == "long" else 1]
            bk = v["books"][0 if sd == "long" else 1]
            k = (trd.decision_idx.to_numpy() - 239) // 240
            inv = np.zeros(len(trd), bool)
            for (k0, k1, _, _) in v_eps:
                inv |= (k >= k0) & (k <= k1)
            cells_pnl[c] = {"trades": int(inv.sum()), "net4_full": float(bk.net4_full[inv].sum()) if len(trd) else 0.0}
        vstat[sd] = {"episodes_2022_2025": len(v_eps) + len(a_eps), "vetoed": len(v_eps), "allowed": len(a_eps),
                     "vetoed_original_pnl": cells_pnl}
    # tamper: prices / funding after 2024-01-01 x1.7 -> entry permissions and trades closed before the cut unchanged
    cut = pd.Timestamp("2024-01-01", tz="UTC")
    n = m.idx(cut)
    k_ = lambda x: np.concatenate([x[:n], x[n:] * 1.7])  # noqa: E731
    mt = b2.Market(m.t, k_(m.o), k_(m.h), k_(m.l), k_(m.c), m.v, m.tb, m.ft, np.where(m.ft >= cut.value, m.fr * 1.7, m.fr))
    st_t = MAT.b5.build_state(mt, dec4)
    sig_t = g3_signals(MAT, st_t)
    bear_t, _ = ma100_bear(mt, T4, dec4)
    ok_t = {"long": veto_entry_ok(sig_t["long"]["side"], ~bear_t)[0], "short": veto_entry_ok(sig_t["short"]["side"], bear_t)[0]}
    pre = T4 <= cut.value
    tam = {"signals_prefix_equal": all(np.array_equal(sig[s]["side"][pre], sig_t[s]["side"][pre]) for s in ok),
           "regime_prefix_equal": bool(np.array_equal(bear4[pre], bear_t[pre])),
           "entry_ok_prefix_equal": all(np.array_equal(ok[s][pre], ok_t[s][pre]) for s in ok)}
    trades_eq = True
    for s in ("long", "short"):
        ta, _ = b2.simulate(m, "state", dec4, sig[s]["side"], sig[s]["w"], 2, b2.TTL_TREND, 0.5, 0, m.N, entry_ok=ok[s])
        tb, _ = b2.simulate(mt, "state", dec4, sig_t[s]["side"], sig_t[s]["w"], 2, b2.TTL_TREND, 0.5, 0, m.N,
                            entry_ok=ok_t[s])
        ca = ta[(~ta.open_at_end) & (ta.exit_idx < n)].reset_index(drop=True)
        trades_eq &= bool(len(ca) > 0 and ca.equals(tb.iloc[:len(ca)].reset_index(drop=True)))
    tam["closed_trades_prefix_equal"] = trades_eq
    g2.update(veto=vstat, tamper=tam, tamper_all=bool(all(tam.values())), git_head=git("rev-parse", "HEAD"),
              spec="G3_LONG S180/W180-P65 + G3_SHORT F180/V-ENS, each 1x, gross <= 2; MA100 (last 100 completed UTC "
                   "daily closes) at each episode's first decision: bull allows LONG / vetoes SHORT, bear allows SHORT / "
                   "vetoes LONG; vetoed episode refused until the target goes flat; Batch-2 simulate(entry_ok); 6 cells; "
                   "run 2020-01-01..2025-12-31 (2020-21 warm-up), scored 2022..2025",
              pass_=bool(g2["absolute"]["pass"] and g2["replacement"]["pass"] and all(tam.values())))
    g2["pass"] = g2.pop("pass_")
    dump(GD / "g3_ma100_entry_veto_r1.json", g2)
    registry.record(REGISTRY, {"experiment": "REGIME-BIDIR-24H-r1 rescored (continuous 2022-2025, consistent gate)",
                               "role": "evaluation", "n_trials": 0, "n_simulations": len(G_CELLS),
                               "input_hashes": in_hash, "result_summary": {"absolute": g1["absolute"],
                                                                           "replacement": g1["replacement"]}})
    registry.record(REGISTRY, {"experiment": "G3-MA100-ENTRY-VETO-r1", "role": "trial", "n_trials": 1,
                               "n_simulations": 2 * len(G_CELLS), "input_hashes": in_hash,
                               "result_summary": {"absolute": g2["absolute"], "replacement": g2["replacement"],
                                                  "tamper": g2["tamper_all"], "pass": g2["pass"]}})
    log(f"gates: veto {g2['absolute']} {g2['replacement']} tamper {tam} pass {g2['pass']} {time.time() - t0:.0f}s")


# ================================================================ SHORT-HSEL-4H-r1 (Codex spec 2026-10-11)
HSEL_H = (240, 480, 720, 1440)
HSEL_W = {"G3_LONG": 0.8, "G3_SHORT": 0.8, "NEW_SHORT": 0.4}


def hsel_cv(b2, m, X, T, d, y, lend, h, lam, trows, cells) -> dict:
    """Blocked CV inside the train window for one (horizon, lambda): per held-out block fit on the other blocks
    (rows whose label window touches the block are dropped), trade the block in every cell, score."""
    from btcusdt_quant.rl import regime_short as RS
    import btcusdt_quant.rl.gates as GT
    idx = np.flatnonzero(trows)
    blk = RS.block_ids(T[idx])
    per_cell = {f"o{o}_p{p}": [] for o, p in cells}
    block_net = []
    for b in np.unique(blk):
        te = idx[blk == b]
        t0_, t1_ = T[te].min(), T[te].max()
        trn = idx[(blk != b) & ((lend[idx] < t0_) | (T[idx] > t1_ + h * sp.MIN))]
        med, sc = RS.fit_norm(X[trn])
        w, b0 = RS.ridge(RS.apply_norm(X[trn], med, sc), y[trn], lam)
        pred = RS.apply_norm(X[te], med, sc) @ w + b0
        side = np.where(pred > 0, -1, 0)
        lo = m.idx(pd.Timestamp(int(t0_), tz="UTC"))
        hi = min(m.idx(pd.Timestamp(int(t1_ + 4 * 3600 * 10**9), tz="UTC")), m.N)
        lo -= lo % 1440
        hi -= hi % 1440
        for o, p in cells:
            tr_, od = b2.simulate(m, "event", d[te], side, np.ones(len(te)), o, b2.TTL_TREND, p, lo, hi, hold=h)
            bk = b2.Book(m, tr_, od, lo, hi)
            dly = bk.daily(lo, hi)
            per_cell[f"o{o}_p{p}"].append(dly)
            block_net.append(float(dly.sum()))
    cat = {c: np.concatenate(v) for c, v in per_cell.items()}
    return {"worst_block_cell_net4": float(min(block_net)), "blocks": int(len(np.unique(blk))),
            "boot60_min_cell": float(min(GT.boot_p05(v, 60) for v in cat.values())),
            "mdd_max_cell": float(max(GT.mdd(v) for v in cat.values())),
            "net4_mean_cell": float(np.mean([v.sum() for v in cat.values()]))}


def cmd_hsel(args) -> None:
    from btcusdt_quant.rl import event_sim as ES, gates as GT, regime_short as RS
    t0 = time.time()
    HD = OUT / "short_hsel_4h_r1"
    HD.mkdir(parents=True, exist_ok=True)
    b2, m, st, in_hash = regime_inputs()
    T = st["T"].to_numpy(np.int64)
    X = st[list(RS.FEATURES)].to_numpy(float)
    d = np.searchsorted(m.t, T) - 1
    if not np.array_equal(m.t[d] + sp.MIN, T):
        raise SystemExit("decision bars misaligned")
    lab = {h: RS.short_labels(m.t, m.c, m.ft, m.fr, d, hold=h) for h in HSEL_H}
    ts = lambda x: pd.Timestamp(x, tz="UTC").value  # noqa: E731
    cells = G_CELLS
    rep: dict = {"spec": {"side": "short only", "features": RS.FEATURES, "lambdas": RS.LAMBDAS, "horizons_min": HSEL_H,
                          "selection": "train-internal blocked CV (years, quarters if one year); rank worst block x "
                                       "cell net4 desc -> min-cell boot60 desc -> max-cell MDD asc -> shorter horizon",
                          "label": "short net4 over the horizon (4 bps + funding received)", "embargo": "= horizon",
                          "entry": "pred > 0", "hold": "selected horizon", "cadence": "4h", "weight": 1.0,
                          "execution": "Batch-2 maker rules (event kind), one continuous 2022..2025 run with a "
                                       "per-decision hold (btcusdt_quant/rl/event_sim.py)", "cells": 6,
                          "portfolio": HSEL_W, "folds": FOLDS_A2, "input_sha256": in_hash,
                          "data": "DEV loader (< 2026-01-01), state_1h DEV"}, "folds": {}}
    parts, tamper = [], {}
    for f, (tr_w, va_w) in FOLDS_A2.items():
        a_tr, b_tr, a_va, b_va = ts(tr_w[0]), ts(tr_w[1]), ts(va_w[0]), ts(va_w[1])
        table = []
        for h in HSEL_H:
            y, lend = lab[h]
            trows = (T >= a_tr) & (T < b_tr) & (lend <= a_va - h * sp.MIN) & np.isfinite(y)
            for lam in RS.LAMBDAS:
                r = hsel_cv(b2, m, X, T, d, y, lend, h, lam, trows, cells)
                table.append({"horizon": h, "lambda": lam, **r})
        best = sorted(table, key=lambda r: (-r["worst_block_cell_net4"], -r["boot60_min_cell"], r["mdd_max_cell"],
                                            r["horizon"]))[0]
        h, lam = best["horizon"], best["lambda"]
        y, lend = lab[h]
        trows = (T >= a_tr) & (T < b_tr) & (lend <= a_va - h * sp.MIN) & np.isfinite(y)
        med, sc = RS.fit_norm(X[trows])
        w, b0 = RS.ridge(RS.apply_norm(X[trows], med, sc), y[trows], lam)
        va = (T >= a_va) & (T < b_va)
        pred = RS.apply_norm(X[va], med, sc) @ w + b0
        side = np.where(pred > 0, -1, 0)
        parts.append((d[va], side, np.full(int(va.sum()), h)))
        # tamper: future after the embargo point x1.7 -> same train labels / model; feature tamper after a val cut
        emb = a_va - h * sp.MIN
        c2 = m.c.copy()
        c2[int(np.searchsorted(m.t, emb)):] *= 1.7
        y2, _ = RS.short_labels(m.t, c2, m.ft, np.where(m.ft > emb, m.fr * 1.7, m.fr), d, hold=h)
        w2, b02 = RS.ridge(RS.apply_norm(X[trows], med, sc), y2[trows], lam)
        X3 = X.copy()
        cut = a_va + (b_va - a_va) // 2
        X3[T > cut] = 99.0
        p3 = RS.apply_norm(X3[va], med, sc) @ w + b0
        tamper[f] = {"train_labels_equal": bool(np.array_equal(y[trows], y2[trows])),
                     "model_equal": bool(np.array_equal(w, w2) and b0 == b02),
                     "pred_before_cut_equal": bool(np.array_equal(p3[T[va] <= cut], pred[T[va] <= cut]))}
        top = np.argsort(-np.abs(w))[:8]
        rep["folds"][f] = {"train": tr_w, "val": va_w, "selected": {"horizon": h, "lambda": lam}, "cv_table": table,
                           "train_rows": int(trows.sum()), "short_share_val": float((pred > 0).mean()),
                           "coef_top": {RS.FEATURES[i]: float(w[i]) for i in top}, "intercept": b0, "tamper": tamper[f]}
        log(f"hsel {f}: selected h={h} lam={lam} worst {best['worst_block_cell_net4']:.1f} short {(pred > 0).mean():.3f}")
    dd_all, side_all, hold_all = stitch_folds(parts)
    lo = m.idx(GT.START)
    new = {}
    for o, p in cells:
        tr_, od = ES.simulate_event(m.o, m.h, m.l, m.c, dd_all, side_all, np.ones(len(dd_all)), hold_all, o,
                                    b2.TTL_TREND, p, lo, m.N)
        bk = b2.Book(m, tr_, od, lo, m.N)
        closed = {}
        for yv in GT.YEARS:
            ya, yb = m.idx(pd.Timestamp(f"{yv}-01-01", tz="UTC")), m.idx(pd.Timestamp(f"{yv + 1}-01-01", tz="UTC"))
            closed[yv] = bk.window(ya, yb)["closed"]
        new[f"o{o}_p{p}"] = {"daily": bk.daily(lo, m.N), "daily8": daily8(bk, lo, m.N), "closed": closed}
    g_new = GT.evaluate(new)
    MAT, mg, dec4, stg, _ = g3_setup()
    base = g3_combined(MAT.b2, mg, dec4, g3_signals(MAT, stg))
    port = {c: {"daily": HSEL_W["G3_LONG"] * base[c]["long_daily"] + HSEL_W["G3_SHORT"] * base[c]["short_daily"]
                + HSEL_W["NEW_SHORT"] * new[c]["daily"],
                "closed": {yv: base[c]["closed"][yv] + new[c]["closed"][yv] for yv in GT.YEARS}} for c in new}
    g_port = GT.evaluate(port, baseline={c: v["daily"] for c, v in base.items()})
    corr = {c: float(np.corrcoef(new[c]["daily"], base[c]["daily"])[0, 1]) for c in new}
    days = pd.date_range(GT.START, periods=GT.N_DAYS, freq="D")
    monthly = {c: {k_: float(v) for k_, v in pd.Series(new[c]["daily"], index=days).groupby(days.strftime("%Y-%m")).sum().items()}
               for c in ("o2_p0.5", "o5_p2.0")}
    tam_ok = all(all(v.values()) for v in tamper.values())
    rep.update(new_short=g_new, portfolio=g_port, corr_new_vs_g3=corr, monthly_new=monthly, tamper_all=tam_ok)
    rep["pass"] = bool(g_new["absolute"]["pass"] and g_port["replacement"]["pass"] and tam_ok)
    rep.update(git_head=git("rev-parse", "HEAD"), created_utc=datetime.now(timezone.utc).isoformat(),
               runtime_sec=round(time.time() - t0, 1), test_accessed=False,
               code_sha256={k: sha(ROOT / f"btcusdt_quant/rl/{k}.py") for k in ("regime_short", "event_sim", "gates",
                                                                                 "dev_data")})
    dump(HD / "short_hsel_report.json", rep)
    registry.record(REGISTRY, {"experiment": "SHORT-HSEL-4H-r1 (horizon x lambda CV, continuous 2022-2025)",
                               "role": "trial", "n_trials": len(HSEL_H) * len(RS.LAMBDAS), "n_simulations": 6,
                               "input_hashes": in_hash,
                               "config": {"horizons": HSEL_H, "lambdas": RS.LAMBDAS, "portfolio": HSEL_W},
                               "result_summary": {"pass": rep["pass"], "new_absolute": g_new["absolute"],
                                                  "portfolio_replacement": g_port["replacement"],
                                                  "selected": {f: x["selected"] for f, x in rep["folds"].items()}}})
    log(f"hsel {'PASS' if rep['pass'] else 'FAIL'} new {g_new['absolute']} port {g_port['replacement']} tamper {tam_ok} "
        f"{rep['runtime_sec']}s")


# ================================================================ LONG-PULLBACK-GBM-24H-r1 (Codex spec 2026-10-11)
PB_HOLD = 1440


def pb_trade(b2, m, dec, side, cell, lo, hi):
    """Event run (TTL 15 m, hold 1440 m) -> Book."""
    o, p = cell
    tr, od = b2.simulate(m, "event", dec, side, np.ones(len(dec)), o, b2.TTL_EVENT, p, lo, hi, hold=PB_HOLD)
    return b2.Book(m, tr, od, lo, hi)


def cmd_long_pullback(args) -> None:
    from btcusdt_quant.rl import gates as GT, pullback as PB, regime_short as RS
    t0 = time.time()
    PD = OUT / "long_pullback_gbm_24h_r1"
    PD.mkdir(parents=True, exist_ok=True)
    b2, m, st, in_hash = regime_inputs()
    MAT, mg, dec4, stg, _ = g3_setup()
    sig = g3_signals(MAT, stg)
    T = st["T"].to_numpy(np.int64)
    T4 = mg.t[dec4] + sp.MIN
    k = np.searchsorted(T4, T)
    if np.any(k >= len(T4)) or not np.array_equal(T4[k], T):
        raise SystemExit("state / G3 decision grids misaligned")
    if not np.array_equal(m.t, mg.t):
        raise SystemExit("market grids differ")
    fast, slow = stg["score"][(6, 18, 42)][k], stg["score"][(42, 168, 504)][k]
    extra = np.column_stack([fast, slow, stg["svi"][42][k], stg["svi"][180][k], stg["sig"][k],
                             (stg["fund"] - stg["med"])[k], stg["mad"][k]])
    X = np.column_stack([st[list(RS.FEATURES)].to_numpy(float), extra])
    names = list(RS.FEATURES) + list(PB.EXTRA)
    uni = PB.universe(sig["long"]["side"][k], slow, fast)
    d = np.searchsorted(m.t, T) - 1
    y, lend = RS.long_labels(m.t, m.c, m.ft, m.fr, d, hold=PB_HOLD)
    ts = lambda x: pd.Timestamp(x, tz="UTC").value  # noqa: E731
    cells = G_CELLS
    rep: dict = {"spec": {"universe": "G3_LONG target 0 & slow score(42,168,504) > 0 & fast score(6,18,42) < 0",
                          "label": "24h long price return - 4 bps - actual funding (PESS settlements in (T, T+24h])",
                          "features": names, "model": PB.GBM_PARAMS,
                          "model_note": "subsample_freq=1 so that subsample .8 is applied; deterministic/force_row_wise "
                                        "for reproducibility",
                          "threshold": "inner blocked OOF prediction quantile in {0.50, 0.65, 0.80}; rank worst block x "
                                       "cell net4 -> min boot60 -> max MDD (smaller) -> higher quantile; inner year x "
                                       "cell closed >= 30 enforced",
                          "execution": "event, weight 1, entry TTL 15 m, hold 1440 m, 2 bps exit quote 60 m requote, "
                                       "6 cells, PESS funding, maker 4 bps; outer folds stitched into one continuous "
                                       "2022..2025 run (year-end carry)", "purge": "24h", "folds": FOLDS_A2,
                          "portfolio": {"G3_LONG": 0.8, "G3_SHORT": 0.8, "NEW_LONG": 0.4},
                          "data": "DEV loader (< 2026-01-01)", "input_sha256": in_hash}, "folds": {}}
    parts, tamper = [], {}
    for f, (tr_w, va_w) in FOLDS_A2.items():
        a_tr, b_tr, a_va, b_va = ts(tr_w[0]), ts(tr_w[1]), ts(va_w[0]), ts(va_w[1])
        purge = a_va - PB_HOLD * sp.MIN
        trn = (T >= a_tr) & (T < b_tr) & (lend <= purge) & np.isfinite(y) & uni
        idx = np.flatnonzero(trn)
        blk = RS.block_ids(T[idx])
        oof = np.full(len(idx), np.nan)
        for b in np.unique(blk):
            te = blk == b
            t0_, t1_ = T[idx][te].min(), T[idx][te].max()
            fit_rows = idx[~te & ((lend[idx] < t0_) | (T[idx] > t1_ + PB_HOLD * sp.MIN))]
            oof[te] = PB.fit(X[fit_rows], y[fit_rows]).predict(X[idx][te])
        table = []
        for q in PB.QUANTILES:
            thr = float(np.quantile(oof, q))
            nets, dailies, closed_y = [], {c: [] for c in cells}, {}
            for b in np.unique(blk):
                te = blk == b
                rows = idx[te]
                take = oof[te] > thr
                t0_, t1_ = T[rows].min(), T[rows].max()
                lo = m.idx(pd.Timestamp(int(t0_), tz="UTC"))
                hi = min(m.idx(pd.Timestamp(int(t1_ + 4 * 3600 * 10**9), tz="UTC")), m.N)
                lo -= lo % 1440
                hi -= hi % 1440
                yr = pd.Timestamp(int(t0_), tz="UTC").year
                for cell in cells:
                    bk = pb_trade(b2, m, d[rows][take], np.ones(int(take.sum()), int), cell, lo, hi)
                    dly = bk.daily(lo, hi)
                    nets.append(float(dly.sum()))
                    dailies[cell].append(dly)
                    closed_y[(yr, cell)] = closed_y.get((yr, cell), 0) + bk.window(lo, hi)["closed"]
            cat = {c: np.concatenate(v) for c, v in dailies.items()}
            table.append({"quantile": q, "threshold": thr, "worst_block_cell_net4": min(nets),
                          "boot60_min_cell": min(GT.boot_p05(v, 60) for v in cat.values()),
                          "mdd_max_cell": max(GT.mdd(v) for v in cat.values()),
                          "min_year_cell_closed": int(min(closed_y.values())),
                          "closed_ok": bool(min(closed_y.values()) >= 30), "entries_inner": int((oof > thr).sum())})
        valid = [r for r in table if r["closed_ok"]]
        pool = valid if valid else table
        best = sorted(pool, key=lambda r: (-r["worst_block_cell_net4"], -r["boot60_min_cell"], r["mdd_max_cell"],
                                           -r["quantile"]))[0]
        model = PB.fit(X[trn], y[trn])
        va = (T >= a_va) & (T < b_va) & uni
        pred = model.predict(X[va])
        take = pred > best["threshold"]
        parts.append((d[va][take], np.ones(int(take.sum()), int)))
        # tamper: future prices / funding after the purge point x1.7 -> same train labels and model predictions;
        # features after a val cut -> predictions before it unchanged
        c2 = m.c.copy()
        c2[int(np.searchsorted(m.t, purge)):] *= 1.7
        y2, _ = RS.long_labels(m.t, c2, m.ft, np.where(m.ft > purge, m.fr * 1.7, m.fr), d, hold=PB_HOLD)
        m2 = PB.fit(X[trn], y2[trn])
        X3 = X.copy()
        cut = a_va + (b_va - a_va) // 2
        X3[T > cut] = 99.0
        p3 = model.predict(X3[va])
        tamper[f] = {"train_labels_equal": bool(np.array_equal(y[trn], y2[trn])),
                     "model_equal": bool(np.array_equal(m2.predict(X[va]), pred)),
                     "pred_before_cut_equal": bool(np.array_equal(p3[T[va] <= cut], pred[T[va] <= cut]))}
        imp = model.booster_.feature_importance(importance_type="gain")
        top = np.argsort(-imp)[:8]
        rep["folds"][f] = {"train": tr_w, "val": va_w, "threshold_table": table, "selected": best,
                           "no_valid_threshold": not valid, "universe_train_rows": int(trn.sum()),
                           "universe_val_rows": int(va.sum()), "val_entries_signalled": int(take.sum()),
                           "importance_gain_top": {names[i]: float(imp[i]) for i in top}, "tamper": tamper[f]}
        log(f"pullback {f}: rows {trn.sum()} val {va.sum()} q {best['quantile']} thr {best['threshold']:.2f} "
            f"signals {take.sum()} valid {len(valid)}")
    dd_all, side_all = stitch_folds(parts)
    lo, hi = m.idx(GT.START), m.N
    new = {}
    for cell in cells:
        bk = pb_trade(b2, m, dd_all, side_all, cell, lo, hi)
        closed, win = {}, {}
        for yv in GT.YEARS:
            ya, yb = m.idx(pd.Timestamp(f"{yv}-01-01", tz="UTC")), m.idx(pd.Timestamp(f"{yv + 1}-01-01", tz="UTC"))
            w_ = bk.window(ya, yb)
            closed[yv], win[yv] = w_["closed"], w_["win"]
        new[f"o{cell[0]}_p{cell[1]}"] = {"daily": bk.daily(lo, hi), "daily8": daily8(bk, lo, hi), "closed": closed,
                                         "win": win, "win_all": bk.window(lo, hi)["win"]}
    g_new = GT.evaluate({c: {k_: v[k_] for k_ in ("daily", "daily8", "closed")} for c, v in new.items()})
    base = g3_combined(MAT.b2, mg, dec4, sig)
    port = {c: {"daily": 0.8 * base[c]["long_daily"] + 0.8 * base[c]["short_daily"] + 0.4 * new[c]["daily"],
                "closed": {yv: base[c]["closed"][yv] + new[c]["closed"][yv] for yv in GT.YEARS}} for c in new}
    g_port = GT.evaluate(port, baseline={c: v["daily"] for c, v in base.items()})
    corr = {c: float(np.corrcoef(new[c]["daily"], base[c]["daily"])[0, 1]) for c in new}
    tam_ok = all(all(v.values()) for v in tamper.values())
    rep.update(new_long=g_new, portfolio=g_port, corr_new_vs_g3=corr, tamper_all=tam_ok,
               win={c: {"all": v["win_all"], **{str(y_): v["win"][y_] for y_ in GT.YEARS}} for c, v in new.items()})
    rep["pass"] = bool(g_new["absolute"]["pass"] and g_port["replacement"]["pass"] and tam_ok)
    rep.update(git_head=git("rev-parse", "HEAD"), created_utc=datetime.now(timezone.utc).isoformat(),
               runtime_sec=round(time.time() - t0, 1), test_accessed=False,
               code_sha256={k_: sha(ROOT / f"btcusdt_quant/rl/{k_}.py") for k_ in ("pullback", "regime_short", "gates",
                                                                                   "dev_data")})
    dump(PD / "long_pullback_report.json", rep)
    registry.record(REGISTRY, {"experiment": "LONG-PULLBACK-GBM-24H-r1", "role": "trial", "n_trials": len(PB.QUANTILES),
                               "n_simulations": 6, "input_hashes": in_hash,
                               "config": {"universe": rep["spec"]["universe"], "model": PB.GBM_PARAMS},
                               "result_summary": {"pass": rep["pass"], "new_absolute": g_new["absolute"],
                                                  "portfolio_replacement": g_port["replacement"],
                                                  "selected_q": {f: x["selected"]["quantile"] for f, x in rep["folds"].items()}}})
    log(f"pullback {'PASS' if rep['pass'] else 'FAIL'} new {g_new['absolute']} port {g_port['replacement']} tamper "
        f"{tam_ok} {rep['runtime_sec']}s")


# ================================================================ G3-IDLE-EXTRATREES-4H-r1 (Codex spec 2026-10-11)
def ev_book(b2, m, dec, side, cell, lo, hi, hold):
    """Standalone NEW event run (weight 1, entry TTL 15 m) -> Book."""
    tr, od = b2.simulate(m, "event", dec, side, np.ones(len(dec)), cell[0], b2.TTL_EVENT, cell[1], lo, hi, hold=hold)
    return b2.Book(m, tr, od, lo, hi)


def overlay_cells(b2, m, base: dict, dec, side, hold: int) -> dict:
    """G3 1.0/1.0 (priority, unchanged books) + NEW under the residual gross cap 2.0, one joint run per cell."""
    from btcusdt_quant.rl import gates as GT, overlay as OV
    lo = m.idx(GT.START)
    out = {}
    for cell in G_CELLS:
        c = f"o{cell[0]}_p{cell[1]}"
        bkl, bks = base[c]["books"]
        g = sum(OV.gross_profile(m.N, bk.tr, bk.orders, b2.TTL_TREND, bk.hi) for bk in (bkl, bks))
        tr, od, st = OV.simulate_overlay(m.o, m.h, m.l, m.c, dec, side, hold, cell[0], b2.TTL_EVENT, cell[1], lo, m.N,
                                         g)
        bk = b2.Book(m, tr, od, lo, m.N)
        closed = {}
        for y in GT.YEARS:
            closed[y] = bk.window(m.idx(pd.Timestamp(f"{y}-01-01", tz="UTC")),
                                  m.idx(pd.Timestamp(f"{y + 1}-01-01", tz="UTC")))["closed"]
        out[c] = {"new_daily": bk.daily(lo, m.N), "new_closed": closed, "new_daily8": daily8(bk, lo, m.N),
                  "stats": st}
    return out


def cmd_g3_idle_et(args) -> None:
    from btcusdt_quant.rl import gates as GT, idle_et as IE, regime_short as RS
    t0 = time.time()
    PD = OUT / "g3_idle_extratrees_4h_r1"
    PD.mkdir(parents=True, exist_ok=True)
    b2, m, _, in_hash = regime_inputs()
    st = pd.read_parquet(OUT / "state/state_4h.parquet", columns=["T", "exec_cell"] + list(IE.FEATURES) +
                         list(IE.IDLE_COLS))
    st = st[st.exec_cell == CELL_TAG[PRIMARY]].sort_values("T").reset_index(drop=True)
    T = st["T"].to_numpy(np.int64)
    sp.guard_times(T, False, "state_4h")
    if T.max() >= pd.Timestamp("2026-01-01", tz="UTC").value:
        raise SystemExit("state_4h holds TEST rows")
    in_hash["state_4h"] = sha(OUT / "state/state_4h.parquet")
    MAT, mg, dec4, stg, _ = g3_setup()
    sig = g3_signals(MAT, stg)
    if not (np.array_equal(m.t, mg.t) and np.array_equal(m.c, mg.c)):
        raise SystemExit("market grids differ")
    d = np.searchsorted(m.t, T) - 1
    if not np.array_equal(m.t[d] + sp.MIN, T):
        raise SystemExit("decision bars misaligned")
    X = st[list(IE.FEATURES)].to_numpy(float)
    uni = IE.idle(st)
    yl, lend = RS.long_labels(m.t, m.c, m.ft, m.fr, d, hold=IE.HOLD)
    y = yl + RS.COST_BPS                                   # target: 4h long price return - actual PESS funding
    ts = lambda x: pd.Timestamp(x, tz="UTC").value  # noqa: E731
    H = IE.HOLD * sp.MIN
    rep: dict = {"spec": {"universe": "G3_LONG and G3_SHORT open = pending = signal_active = 0 (state_4h, "
                                      f"{CELL_TAG[PRIMARY]}; identical in all 6 cells)",
                          "target": "4h long price return - actual PESS funding (bps); directional P&L = side x "
                                    "target - 4 bps", "features": list(IE.FEATURES), "model": IE.ET_PARAMS,
                          "impute": "train median", "purge": "4h", "folds": FOLDS_A2,
                          "selection": "inner blocked OOF, {LONG, SHORT, BOTH} x |pred| quantile {0.50, 0.65, 0.80}; "
                                       "valid only if every inner block x cell closed >= 30; rank worst block x cell "
                                       "net4 -> min-cell boot60 -> max-cell MDD; no valid candidate -> FAIL, no "
                                       "fallback (fold emits no signals)",
                          "execution": "4h cadence, one NEW position, entry TTL 15 m, hold 240 m, exit 2 bps / 60 m "
                                       "requote, maker 4 bps, PESS funding, 6 cells, folds stitched into one 2022..2025 "
                                       "run", "portfolio": "G3 1.0/1.0 + NEW residual gross overlay (cap 2.0), joint "
                                                           "event sim (btcusdt_quant/rl/overlay.py)",
                          "data": "DEV loader (< 2026-01-01) + state_4h DEV", "input_sha256": in_hash},
                 "folds": {}}
    parts, tamper, fold_fail = [], {}, []
    for f, (tr_w, va_w) in FOLDS_A2.items():
        a_tr, b_tr, a_va, b_va = ts(tr_w[0]), ts(tr_w[1]), ts(va_w[0]), ts(va_w[1])
        in_tr = uni & (T >= a_tr) & (T < b_tr)
        trn = in_tr & (lend <= a_va - H) & np.isfinite(y)
        idx = np.flatnonzero(trn)
        blk = RS.block_ids(T[idx])
        oof = np.full(len(idx), np.nan)
        for b in np.unique(blk):
            te = blk == b
            t0_, t1_ = T[idx][te].min(), T[idx][te].max()
            fit_rows = idx[~te & ((lend[idx] < t0_) | (T[idx] > t1_ + H))]
            oof[te] = IE.Model(X[fit_rows], y[fit_rows]).predict(X[idx][te])
        table = []
        for mode in IE.MODES:
            for q in IE.QUANTILES:
                thr = float(np.quantile(np.abs(oof), q))
                nets, dailies, closed_bc = [], {c: [] for c in G_CELLS}, []
                for b in np.unique(blk):
                    te = blk == b
                    rows = idx[te]
                    sd = IE.sides(oof[te], mode, thr)
                    lo = m.idx(pd.Timestamp(int(T[rows].min()), tz="UTC"))
                    hi = min(m.idx(pd.Timestamp(int(T[rows].max() + H), tz="UTC")), m.N)
                    lo -= lo % 1440
                    hi -= hi % 1440
                    for cell in G_CELLS:
                        bk = ev_book(b2, m, d[rows][sd != 0], sd[sd != 0], cell, lo, hi, IE.HOLD)
                        dly = bk.daily(lo, hi)
                        nets.append(float(dly.sum()))
                        dailies[cell].append(dly)
                        closed_bc.append(bk.window(lo, hi)["closed"])
                cat = {c: np.concatenate(v) for c, v in dailies.items()}
                table.append({"mode": mode, "quantile": q, "threshold": thr, "worst_block_cell_net4": min(nets),
                              "boot60_min_cell": min(GT.boot_p05(v, 60) for v in cat.values()),
                              "mdd_max_cell": max(GT.mdd(v) for v in cat.values()),
                              "min_block_cell_closed": int(min(closed_bc)), "valid": bool(min(closed_bc) >= 30),
                              "sum_net4_all_cells": float(sum(nets))})
        valid = [r for r in table if r["valid"]]
        best = sorted(valid, key=lambda r: (-r["worst_block_cell_net4"], -r["boot60_min_cell"], r["mdd_max_cell"]))[0] \
            if valid else None
        model = IE.Model(X[trn], y[trn])
        va = uni & (T >= a_va) & (T < b_va)
        pred = model.predict(X[va])
        if best is None:
            fold_fail.append(f)
            sd = np.zeros(int(va.sum()), int)
        else:
            sd = IE.sides(pred, best["mode"], best["threshold"])
        parts.append((d[va][sd != 0], sd[sd != 0]))
        c2 = m.c.copy()
        c2[int(np.searchsorted(m.t, a_va - H)):] *= 1.7
        y2 = RS.long_labels(m.t, c2, m.ft, np.where(m.ft > a_va - H, m.fr * 1.7, m.fr), d, hold=IE.HOLD)[0] + RS.COST_BPS
        X3 = X.copy()
        cut = a_va + (b_va - a_va) // 2
        X3[T > cut] = 99.0
        p3 = model.predict(X3[va])
        tamper[f] = {"train_labels_equal": bool(np.array_equal(y[trn], y2[trn])),
                     "model_equal": bool(np.array_equal(IE.Model(X[trn], y2[trn]).predict(X[va]), pred)),
                     "pred_before_cut_equal": bool(np.array_equal(p3[T[va] <= cut], pred[T[va] <= cut]))}
        imp = model.et.feature_importances_
        top = np.argsort(-imp)[:8]
        rep["folds"][f] = {"train": tr_w, "val": va_w, "rows_universe_train": int(in_tr.sum()),
                           "rows_train_after_purge": int(trn.sum()), "rows_val": int(va.sum()),
                           "inner_blocks": [int(b) for b in np.unique(blk)], "candidates": table, "selected": best,
                           "val_signals": {"long": int((sd > 0).sum()), "short": int((sd < 0).sum())},
                           "importance_top": {IE.FEATURES[i]: float(imp[i]) for i in top}, "tamper": tamper[f]}
        log(f"idle-et {f}: rows {in_tr.sum()}/{trn.sum()} val {va.sum()} valid {len(valid)} sel "
            f"{None if best is None else (best['mode'], best['quantile'])} sig +{(sd > 0).sum()} -{(sd < 0).sum()}")
    dd_all, side_all = stitch_folds(parts)
    lo = m.idx(GT.START)
    base = g3_combined(MAT.b2, mg, dec4, sig)
    new, gb = {}, {}
    for cell in G_CELLS:
        c = f"o{cell[0]}_p{cell[1]}"
        bk = ev_book(b2, m, dd_all, side_all, cell, lo, m.N, IE.HOLD)
        closed, win = {}, {}
        for yv in GT.YEARS:
            w_ = bk.window(m.idx(pd.Timestamp(f"{yv}-01-01", tz="UTC")), m.idx(pd.Timestamp(f"{yv + 1}-01-01", tz="UTC")))
            closed[yv], win[str(yv)] = w_["closed"], w_["win"]
        wa = bk.window(lo, m.N)
        new[c] = {"daily": bk.daily(lo, m.N), "daily8": daily8(bk, lo, m.N), "closed": closed}
        gb[c] = {"win": {"all": wa["win"], **win}, "long_net4": wa["long_net4"], "short_net4": wa["short_net4"],
                 "entries_long": wa["long_entries"], "entries_short": wa["short_entries"]}
    g_new = GT.evaluate(new)
    ov = overlay_cells(b2, m, base, dd_all, side_all, IE.HOLD)
    port = {c: {"daily": base[c]["daily"] + ov[c]["new_daily"], "daily8": base[c]["daily8"] + ov[c]["new_daily8"],
                "closed": {yv: base[c]["closed"][yv] + ov[c]["new_closed"][yv] for yv in GT.YEARS}} for c in new}
    g_port = GT.evaluate(port, baseline={c: v["daily"] for c, v in base.items()})
    corr = {c: float(np.corrcoef(new[c]["daily"], base[c]["daily"])[0, 1]) for c in new}
    same = {c: bool(np.allclose(ov[c]["new_daily"], new[c]["daily"])) for c in new}
    tam_ok = all(all(v.values()) for v in tamper.values())
    rep.update(new_standalone=g_new, overlay=g_port, overlay_stats={c: v["stats"] for c, v in ov.items()},
               overlay_new_equals_standalone=same, corr_new_vs_g3=corr, new_detail=gb, tamper_all=tam_ok,
               folds_without_valid_candidate=fold_fail)
    rep["pass"] = bool(not fold_fail and g_new["absolute"]["pass"] and g_port["replacement"]["pass"] and tam_ok)
    rep.update(git_head=git("rev-parse", "HEAD"), created_utc=datetime.now(timezone.utc).isoformat(),
               runtime_sec=round(time.time() - t0, 1), test_accessed=False,
               code_sha256={k_: sha(ROOT / f"btcusdt_quant/rl/{k_}.py") for k_ in ("idle_et", "overlay", "gates",
                                                                                   "regime_short", "dev_data")})
    dump(PD / "g3_idle_et_report.json", rep)
    registry.record(REGISTRY, {"experiment": "G3-IDLE-EXTRATREES-4H-r1", "role": "trial",
                               "n_trials": len(IE.MODES) * len(IE.QUANTILES), "n_simulations": 12,
                               "input_hashes": in_hash, "config": {"model": IE.ET_PARAMS, "hold": IE.HOLD},
                               "result_summary": {"pass": rep["pass"], "new_absolute": g_new["absolute"],
                                                  "overlay_replacement": g_port["replacement"],
                                                  "folds_without_valid": fold_fail,
                                                  "selected": {f: None if x["selected"] is None else
                                                               [x["selected"]["mode"], x["selected"]["quantile"]]
                                                               for f, x in rep["folds"].items()}}})
    log(f"idle-et {'PASS' if rep['pass'] else 'FAIL'} new {g_new['absolute']} overlay {g_port['replacement']} "
        f"no-valid {fold_fail} tamper {tam_ok} {rep['runtime_sec']}s")


# ================================================================ U35 precompute (Codex A3 2026-10-11): 28 paper AX books
PRE35 = OUT / "precompute_u35"
U35_CUT = pd.Timestamp("2025-05-01", tz="UTC")            # engine tamper / prefix cut inside the DEV AX window


def u35_timeline_ax(table: pd.DataFrame, km_full: np.ndarray, t_full: np.ndarray) -> pd.DataFrame:
    """Causal decision-group signal timeline of an AX book: one row per decision time T (signal computed from data
    closed before T, executed at T + 1 m): side / strength (E0 bps) of the first enterable row, k in force at T + 1 m,
    available = inside the rolling AX window (k defined)."""
    tb = table.reset_index(drop=True)
    dt = pd.DatetimeIndex(tb.decision_time).as_unit("ns").asi8
    e0 = tb.e0_bps.to_numpy(float)
    ok = tb.allow_entry.to_numpy(bool) & (tb.side.to_numpy() != 0) & np.isfinite(e0) & (e0 > 0)
    first = np.r_[True, dt[1:] != dt[:-1]]
    gid = np.cumsum(first) - 1
    g_t = dt[first]
    side, strength, ecol = np.zeros(len(g_t), np.int8), np.full(len(g_t), np.nan), np.full(len(g_t), -1)
    cand = np.flatnonzero(ok)
    pick = pd.Series(cand).groupby(gid[cand]).first()
    side[pick.index.to_numpy()] = tb.side.to_numpy()[pick.to_numpy()]
    strength[pick.index.to_numpy()] = e0[pick.to_numpy()]
    ecol[pick.index.to_numpy()] = tb.e_col.to_numpy()[pick.to_numpy()]
    j = np.searchsorted(t_full, g_t)                      # execution minute T + 1 m opens at index of T
    k = np.where(j < len(t_full), km_full[np.minimum(j, len(t_full) - 1)], np.nan)
    f = pd.DataFrame({"decision_time": g_t, "available_time": g_t, "side": side, "signal_active": side != 0,
                      "strength_e0_bps": strength, "e_col": ecol, "k": k, "available": np.isfinite(k),
                      "rows_in_group": np.bincount(gid)})
    return f[(f.decision_time >= pd.Timestamp(USABLE_FROM, tz="UTC").value) & (f.decision_time < sp.TEST_START.value)]


def u35_timeline_grid(d: Path) -> pd.DataFrame:
    """Signal timeline of an existing sleeve from its DEV grid partitions: minutes where the causal signal columns
    (available, base_side, base_weight, signal_active) change; available_time = minute + 1 m."""
    cols = ["minute_time", "available_time", "available", "base_side", "base_weight", "signal_active"]
    g = sp.read_partitioned(d, "grid", years=set(range(2020, 2026)))[cols]
    v = g[cols[2:]].to_numpy(float)
    ch = np.r_[True, np.any(v[1:] != v[:-1], axis=1)]
    return g.loc[ch].reset_index(drop=True)


def u35_ax_book(b, ctx, fund, ax, t_glob, files, avail_rep, rec) -> dict:
    from dataclasses import replace as _rp
    from btcusdt_quant.rl import u35
    from btcusdt_quant.sim import costs, rolling
    from btcusdt_quant.sim.strategies import build_variant
    sid = u35.SPEC_ID[b]
    r = rec.setdefault(b, {"spec_id": sid, "family": u35.FAMILY[b], "catalog_family": u35.catalog_family(b)})
    a, z = u35.AX_START, u35.DEV_END
    times = pd.DatetimeIndex(ctx.minutes.open_time)
    with u35.dev_settlements(fund):
        table, _ = build_variant(ctx, sid, False, "NATIVE", ax=True)
        table = table.assign(e0_bps=ax.row_e0(table, ctx.regime, sid), e_col=ax.e_cols(table, sid).astype(float))
        e, e_min = ax.e_matrix(ctx.regime, times, ax.heads(sid))
        km = ax.k_schedule(times, u35.k_picks(b), rolling.WINDOWS)
        cfg = _rp(ax.CONFIG, close_at_end=True)
        res = ax.run_ax(table, ctx.minutes, e, e_min, a, z, cfg, km)
        ft, fr = costs._settlement_arrays()
        if int(ft.max()) >= sp.TEST_START.value:
            raise Fail("TEST funding settlement reached the AX run")
        inside = ((ctx.minutes.open_time >= a) & (ctx.minutes.open_time < z)).to_numpy()
        ci = int(np.searchsorted(ctx.minutes.open_time.array.asi8[inside], U35_CUT.value))
        base = res.minute_pnl.to_numpy(float)
        for tag in ("prefix", "tamper"):                  # engine invariance before the cut (table, E, k fixed)
            mins, hi = ctx.minutes, z
            if tag == "tamper":
                mins = ctx.minutes.copy()
                aft = (mins.open_time >= U35_CUT).to_numpy()
                for c in ("open", "high", "low", "close"):
                    mins.loc[aft, c] = mins.loc[aft, c] * 1.7
            else:
                hi = U35_CUT
            p2 = ax.run_ax(table, mins, e, e_min, a, hi, cfg, km).minute_pnl.to_numpy(float)
            lim = ci if tag == "tamper" else ci - 1
            r[f"{tag}_invariant"] = bool(np.array_equal(p2[:lim], base[:lim]))
            need(r[f"{tag}_invariant"], f"{b} {tag} invariance at {U35_CUT.date()}", r)
    mm = ctx.minutes.loc[inside].reset_index(drop=True)
    tt = mm.open_time.array.asi8.copy()
    trades = res.trades.reset_index(drop=True)
    ref = pd.read_parquet(u35.REF_TRADES[b]).reset_index(drop=True)
    same = len(trades) == len(ref) and all(np.array_equal(trades[c].to_numpy(), ref[c].to_numpy())
                                           for c in ("decision_time", "entry_time", "exit_time", "side", "units",
                                                     "entry_price", "exit_price", "exit_reason"))
    r["trades"], r["trades_ref"], r["trades_exact"] = int(len(trades)), int(len(ref)), bool(same)
    need(same, f"{b} trades (count, decision/entry/exit time, side, units, prices, reason) == R2-52A research", r)
    if same:
        r["trade_net_max_abs_vs_ref"] = float(np.abs(trades.net_bps.to_numpy() - ref.net_bps.to_numpy()).max()) \
            if len(ref) else 0.0
        need(r["trade_net_max_abs_vs_ref"] <= ATOL_TOT, f"{b} per-trade net4 vs research", r)
    rd = pd.read_parquet(u35.REF_DAILY[b])
    days = pd.DatetimeIndex(rd.index)
    mine = res.minute_pnl.groupby(res.minute_pnl.index.floor("D")).sum().reindex(days, fill_value=0.0)
    r["daily_max_abs_vs_ref"] = float(np.abs(mine.to_numpy() - rd.ax_4bps.to_numpy()).max())
    need(r["daily_max_abs_vs_ref"] <= ATOL_TOT, f"{b} daily net4 vs research", r)
    g = dict(seg="DEV", a=a, b=z, res=res, mm=mm, table=table, e=e[inside], e_min=e_min[inside], km=km[inside],
             cfg=cfg, t=tt)
    tr = ax_trades(trades, tt, g, ax)
    rows = sp.log_rows(tt, mm.close.to_numpy(float), tr, cfg.fee_per_side, ft, fr)
    net = sp.minute_sum(rows, len(tt))
    r["minute_max_abs_vs_core"] = float(np.abs(net - base).max())
    need(r["minute_max_abs_vs_core"] <= ATOL_MIN, f"{b} minute ledger vs core", r)
    r["net4_total"], r["net4_total_core"] = float(net.sum()), float(base.sum())
    need(abs(r["net4_total"] - r["net4_total_core"]) <= ATOL_TOT, f"{b} total net4 vs core", r)
    r["unmatched_entries"] = int((tr.entry_kind == "unmatched").sum())
    g.update(tr=tr, rows=rows, net=net, sig=ax_signal(tt, g, tr))
    native_out(b, t_glob, [g], files, avail_rep, root=PRE35)
    tl = u35_timeline_ax(table, km, times.asi8)
    p = PRE35 / "timeline" / f"{b}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    tl.to_parquet(p, index=False, compression="zstd")
    files[f"timeline/{b}"] = {"rows": int(len(tl)), "bytes": p.stat().st_size, "sha256": sha(p)}
    ex = pd.DatetimeIndex(trades.exit_time)
    r["closed_by_year"] = {str(y): int(((ex.year == y) & (trades.exit_reason != "data_end")).sum()) for y in (2023, 2024, 2025)}
    r["net4_by_year"] = {str(y): float(net[pd.DatetimeIndex(tt).year == y].sum()) for y in (2023, 2024, 2025)}
    log(f"u35 {b}: trades {len(trades)} exact {same} net {net.sum():.1f} min-ledger {r['minute_max_abs_vs_core']:.2e}")
    return r


def cmd_u35_precompute(args) -> None:
    import sys as _sys
    from btcusdt_quant.rl import u35
    t0 = time.time()
    if str(ROOT / "scripts") not in _sys.path:
        _sys.path.insert(0, str(ROOT / "scripts"))
    import sim_adaptive_exit as ax
    PRE35.mkdir(parents=True, exist_ok=True)
    SLEEVE_ID.update({b: len(SLEEVES) + i for i, b in enumerate(u35.AX_NEW)})   # new ids 7..34, existing 7 unchanged
    ctx, fund, in_hash = u35.dev_context()
    t_glob = ctx.minutes.open_time.array.asi8.copy()
    sp.guard_times(t_glob, False, "u35 grid")
    files, avail_rep, rec = {}, {}, {}
    only = [x for x in str(getattr(args, "books", "") or "").split(",") if x] or list(u35.AX_NEW)
    for b in only:
        u35_ax_book(b, ctx, fund, ax, t_glob, files, avail_rep, rec)
    # existing 7: reuse unchanged; verify DEV-year partition bytes against the precompute manifest (2026 files untouched)
    man = json.loads((PRE / "manifest.json").read_text(encoding="utf-8"))
    reuse = {"checked_files": 0, "mismatch": [], "skipped_test_year_files": 0}
    for key, parts in man["files"].items():
        if not isinstance(parts, dict):
            continue
        for stem in ("grid", "ledger", "decisions", "outcomes"):
            for fn, meta in (parts.get(stem) or {}).items():
                if int(fn.rsplit("_", 1)[1].split(".")[0]) >= sp.TEST_START.year:
                    reuse["skipped_test_year_files"] += 1
                    continue
                reuse["checked_files"] += 1
                if sha(PRE / key / fn) != meta["sha256"]:
                    reuse["mismatch"].append(f"{key}/{fn}")
    reuse["pass"] = not reuse["mismatch"]
    for s in u35.EXISTING7:                               # timelines of the existing 7 (G3 family: every cell checked)
        if s in G3_FAMILY:
            tls = {c: u35_timeline_grid(PRE / "g3_family" / c / s) for c in CELL_TAG.values()}
            ref_tl = tls[CELL_TAG[PRIMARY]]
            reuse.setdefault("timeline_cells_equal", {})[s] = all(
                len(v) == len(ref_tl) and np.array_equal(v.to_numpy(float), ref_tl.to_numpy(float)) for v in tls.values())
            tl = ref_tl
        else:
            tl = u35_timeline_grid(PRE / "common" / s)
        p = PRE35 / "timeline" / f"{s}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        tl.to_parquet(p, index=False, compression="zstd")
        files[f"timeline/{s}"] = {"rows": int(len(tl)), "bytes": p.stat().st_size, "sha256": sha(p)}
    tot_bytes = sum(p_.stat().st_size for p_ in PRE35.rglob("*.parquet"))
    ok = all(all(c["pass"] for c in r_["checks"]) for r_ in rec.values()) and reuse["pass"]
    manifest = {"name": "RL U35 precompute (28 AX books; existing 7 reused)", "created_utc": datetime.now(timezone.utc).isoformat(),
                "universe": list(u35.UNIVERSE), "family": u35.FAMILY, "ax_books": list(only),
                "window": {"ax_available": [str(u35.AX_START), str(u35.DEV_END)], "grid": [str(pd.Timestamp(int(t_glob[0]), tz="UTC")),
                                                                                  str(pd.Timestamp(int(t_glob[-1]), tz="UTC"))]},
                "engine": "build_variant(ax=True) -> row_e0/e_matrix -> rolling k (research selected_k, W01..W10) -> "
                          "sim core R2_52A (scripts/sim_adaptive_exit.run_ax, close_at_end) = R2-52A research run; "
                          "native fill, one cell (not replicated per exec cell)",
                "input_sha256": in_hash, "code_sha256": {k_: sha(ROOT / f"btcusdt_quant/rl/{k_}.py") for k_ in ("u35", "dev_data", "sleeve_precompute")},
                "git_head": git("rev-parse", "HEAD"), "parity": rec, "existing7_reuse": reuse, "availability": avail_rep,
                "files": files, "total_bytes": int(tot_bytes), "runtime_sec": round(time.time() - t0, 1), "pass": bool(ok),
                "test_accessed": False}
    dump(PRE35 / "manifest.json", manifest)
    log(f"u35 precompute {'PASS' if ok else 'FAIL'} books {len(only)} reuse {reuse['pass']} {manifest['runtime_sec']}s "
        f"{tot_bytes / 1e9:.2f} GB")


# ================================================================ signal-only 5m store (Codex SMDP redesign 2026-10-11)
SS = OUT / "signal_store_5m"
SS_CUT = pd.Timestamp("2024-07-01", tz="UTC")


def ss_catalog(ctx, clk: np.ndarray) -> dict:
    """Catalog tokens from one research context (ungated NATIVE tables; gate as a state channel)."""
    from btcusdt_quant.rl import signal_store as SG
    from btcusdt_quant.sim import regime
    from btcusdt_quant.sim.strategies import CATALOG, build_variant
    T = pd.DatetimeIndex(clk, tz="UTC")
    m = regime._asof(ctx.regime, T, "M", pd.Timedelta(minutes=14))
    gate_avail = np.isfinite(m).astype(np.int8)
    C = SG.close_at(clk, ctx.minutes.open_time.array.asi8, ctx.minutes.close.to_numpy(float))
    out = {}
    for tok in SG.catalog_tokens():
        spec = CATALOG[tok]
        tb, _ = build_variant(ctx, tok, False, "NATIVE")
        ev = SG.oco_events(tb, ctx, spec.e_head) if (tb.entry == "oco").any() else SG.market_events(tb, ctx, spec.e_head)
        st = SG.token_state(clk, *ev, hold_min=spec.hold_min)
        st["gate_pass"] = (regime.gate_mask(ctx.regime, T, spec.gate).astype(np.int8) if spec.gate
                           else np.full(len(clk), -1, np.int8))
        st["gate_avail"] = gate_avail if spec.gate else np.zeros(len(clk), np.int8)
        st["available"] = (clk >= (ev[0][0] if len(ev[0]) else np.iinfo(np.int64).max)).astype(np.int8)
        st.update(SG.markouts(st["side"], C))
        st["_events"] = int(len(ev[0]))
        out[tok] = st
    return out, C


def ss_equal(a: dict, b: dict, upto: int) -> list:
    bad = []
    for tok, ch in a.items():
        for k, v in ch.items():
            if k.startswith("_"):
                continue
            x, y = np.asarray(v)[:upto], np.asarray(b[tok][k])[:upto]
            if not np.array_equal(x, y, equal_nan=np.issubdtype(x.dtype, np.floating)):
                bad.append(f"{tok}.{k}")
    return bad


def patchtst_proof() -> dict:
    """Existing R2-44 w730_raw predictions (DEV_FRONT / DEV_BACK only): checkpoint and prediction hashes vs the fold
    records, rows inside [retrain_time, prediction_end), training code = archived code; cutoff rule from the code."""
    base = ROOT / "out/k45_vol_detector_r2_44_window_20261006/folds/w730_raw"
    res = {"folds": 0, "ckpt_hash_ok": 0, "pred_hash_ok": 0, "rows_in_window_ok": 0, "bad": [], "elapsed_sec": []}
    for seg in ("DEV_FRONT", "DEV_BACK"):
        for js in sorted((base / seg).glob("fold_*.json")):
            rec = json.loads(js.read_text(encoding="utf-8"))
            res["folds"] += 1
            ck, pr = js.with_suffix(".pt"), js.with_name(js.stem + "_predictions.parquet")
            ok1 = sha(ck) == rec["checkpoint_sha256"]
            ok2 = sha(pr) == rec["predictions_sha256"]
            p = pd.read_parquet(pr, columns=["timestamp", "retrain_time"])
            a, b = pd.Timestamp(rec["retrain_time"]), pd.Timestamp(rec["prediction_end"])
            ts = pd.to_datetime(p.timestamp, utc=True)
            ok3 = bool((ts >= a).all() and (ts < b).all() and (pd.to_datetime(p.retrain_time, utc=True) == a).all()
                       and b <= sp.TEST_START)
            res["ckpt_hash_ok"] += ok1
            res["pred_hash_ok"] += ok2
            res["rows_in_window_ok"] += ok3
            res["elapsed_sec"].append(float(rec.get("elapsed_seconds", np.nan)))
            if not (ok1 and ok2 and ok3):
                res["bad"].append(f"{seg}/{js.stem}")
    code = ROOT / "out/run_k45_vol_detector_r2_44_window.py"
    arch = ROOT / "docs/results/k45_vol_detector_r2_44_20261006/code/run_k45_vol_detector_r2_44_window.py"
    res.update(code_sha256=sha(code), archived_code_equal=sha(code) == sha(arch),
               cutoff_rule="split_indices: label_end = origin + 24h; train/stop rows need label_end < retrain_time - "
                           "24h; window 730 d; scaler on train origins only (fit_fold scaler_end)",
               first3_elapsed_sec=res["elapsed_sec"][:3], median_elapsed_sec=float(np.nanmedian(res["elapsed_sec"])))
    res["pass"] = not res["bad"] and res["archived_code_equal"]
    res.pop("elapsed_sec")
    return res


def cmd_signal_store(args) -> None:
    from btcusdt_quant.rl import signal_store as SG, u35
    t0 = time.time()
    SS.mkdir(parents=True, exist_ok=True)
    clk = SG.clock()
    ctx, fund, in_hash = u35.dev_context()
    base, C = ss_catalog(ctx, clk)
    log(f"signal store: catalog {len(base)} tokens {time.time() - t0:.0f}s")
    # prefix / tamper on the catalog part (research timelines come from the tamper-checked precompute)
    cut_i = int(np.searchsorted(clk, SS_CUT.value, "right"))
    pre, _ = ss_catalog(ctx.truncate(SS_CUT), clk[:cut_i])
    mins = ctx.minutes.copy()
    aft = (mins.open_time >= SS_CUT).to_numpy()
    for c in ("open", "high", "low", "close"):
        mins.loc[aft, c] = mins.loc[aft, c] * 1.7
    from btcusdt_quant.sim.strategies import Context
    tam, _ = ss_catalog(Context(minutes=mins, metrics=ctx.metrics, premium=ctx.premium, funding=ctx.funding,
                                regime=ctx.regime, end=ctx.end), clk)
    checks = {"prefix_mismatch": ss_equal(pre, base, cut_i), "tamper_mismatch": ss_equal(base, tam, cut_i),
              "tamper_changed_after_cut_tokens": sum(
                  any(not np.array_equal(np.asarray(v)[cut_i:], np.asarray(tam[t_][k])[cut_i:], equal_nan=True)
                      for k, v in ch.items() if not k.startswith("_") and np.asarray(v).dtype.kind == "f")
                  for t_, ch in base.items())}
    log(f"signal store: prefix/tamper {len(checks['prefix_mismatch'])}/{len(checks['tamper_mismatch'])} mismatches")
    for s in SG.RESEARCH_TOKENS:
        st = SG.timeline_state(clk, pd.read_parquet(PRE35 / "timeline" / f"{s}.parquet"))
        st["gate_pass"] = np.full(len(clk), -1, np.int8)
        st["gate_avail"] = np.zeros(len(clk), np.int8)
        st.update(SG.markouts(st["side"], C))
        base[s] = st
    toks = SG.tokens()
    sides = {t_: base[t_]["side"] for t_ in toks}
    dup = [[a, b] for i_, a in enumerate(toks) for b in toks[i_ + 1:]
           if (sides[a] != 0).any() and (np.array_equal(sides[a], sides[b]) or np.array_equal(sides[a], -sides[b]))]
    files, summ = {}, {}
    (SS / "tokens").mkdir(exist_ok=True)
    for tid, t_ in enumerate(toks):
        ch = {k: v for k, v in base[t_].items() if not k.startswith("_")}
        f = pd.DataFrame({"t": clk, **ch})
        p = SS / "tokens" / f"{t_}.parquet"
        f.to_parquet(p, index=False, compression="zstd")
        files[t_] = {"bytes": p.stat().st_size, "sha256": sha(p)}
        summ[t_] = {"token_id": tid, "family": SG.family_of(t_), "source_id": t_,
                    "active_share": float(ch["active"].mean()), "long_share": float((ch["side"] > 0).mean()),
                    "short_share": float((ch["side"] < 0).mean()), "strength_avail_share": float(ch["strength_avail"].mean()),
                    "available_from": str(pd.Timestamp(int(clk[np.argmax(ch["available"] > 0)]), tz="UTC"))
                    if (ch["available"] > 0).any() else None,
                    "gate": "none" if (ch["gate_pass"] < 0).all() else "gated",
                    "mk1440_mean_last": float(ch["mk1440_mean"][-1]), "mk1440_count_last": float(ch["mk1440_count"][-1])}
    # market features: existing causal 1h state, primary cell, sleeve channels removed, as of the 5m clock
    st1 = pd.read_parquet(OUT / "state/state_1h.parquet")
    st1 = st1[st1.exec_cell == CELL_TAG[PRIMARY]].sort_values("T").reset_index(drop=True)
    sp.guard_times(st1["T"].to_numpy(np.int64), False, "state_1h")
    drop = [c for c in st1 if c in ("exec_cell",) or c.startswith("mask_") or any(c.startswith(s + "_") for s in SLEEVES)]
    keep = [c for c in st1 if c not in drop]
    j = np.searchsorted(st1["T"].to_numpy(np.int64), clk, "right") - 1
    mk = st1[keep].iloc[np.maximum(j, 0)].reset_index(drop=True)
    mk.loc[j < 0, [c for c in keep if c != "T"]] = np.nan
    mk.insert(0, "t", clk)
    mk = mk.rename(columns={"T": "state_T"})
    p = SS / "market.parquet"
    mk.to_parquet(p, index=False, compression="zstd")
    files["market"] = {"bytes": p.stat().st_size, "sha256": sha(p), "columns": list(mk.columns), "dropped": drop}
    proof = patchtst_proof()
    man = {"name": "signal-only causal store, 5m clock", "created_utc": datetime.now(timezone.utc).isoformat(),
           "clock": [str(SG.CLOCK_START), str(SG.CLOCK_END), "5min"], "rows": int(len(clk)),
           "token_map": SG.reconcile(), "tokens": summ, "duplicates_or_negations": dup,
           "channels": ["side", "active", "strength", "strength_avail", "age_min", "gate_pass", "gate_avail", "available"]
           + [f"mk{h}_{s}" for h in SG.HORIZONS for s in ("mean", "hit", "vol", "count")],
           "rules": SG.__doc__, "prefix_tamper": {"cut": str(SS_CUT), **checks,
                                                  "pass": not checks["prefix_mismatch"] and not checks["tamper_mismatch"]},
           "patchtst_reuse_proof": proof, "input_sha256": in_hash,
           "code_sha256": {k_: sha(ROOT / f"btcusdt_quant/rl/{k_}.py") for k_ in ("signal_store", "u35", "dev_data")},
           "research_timelines": {s: sha(PRE35 / "timeline" / f"{s}.parquet") for s in SG.RESEARCH_TOKENS},
           "files": files, "total_bytes": int(sum(v["bytes"] for v in files.values())),
           "git_head": git("rev-parse", "HEAD"), "runtime_sec": round(time.time() - t0, 1), "test_accessed": False}
    dump(SS / "manifest.json", man)
    log(f"signal store: {len(toks)} tokens, prefix/tamper {'PASS' if man['prefix_tamper']['pass'] else 'FAIL'}, "
        f"dups {dup}, patchtst proof {proof['pass']} {man['total_bytes'] / 1e9:.2f} GB {man['runtime_sec']}s")


# ================================================================ scripted baselines on the maker kernel (Codex SMDP 2026-10-11)
SB_WAIT = 60                     # decision every hour on the 5m clock (scripted baselines only)
U35_YEARS = (2022, 2023, 2024, 2025)
U35_FOLD_OF = {2022: "F1", 2023: "F2", 2024: "F3", 2025: "F4"}


def sb_token_arrays():
    from btcusdt_quant.rl import signal_store as SG
    toks = SG.tokens()
    side, avail = [], []
    for t_ in toks:
        f = pd.read_parquet(SS / "tokens" / f"{t_}.parquet", columns=["t", "side", "available"])
        side.append(f.side.to_numpy(np.int8))
        avail.append(f.available.to_numpy(np.int8))
    return toks, np.stack(side, 1), np.stack(avail, 1), f.t.to_numpy(np.int64)


def sb_invvol_weights(toks, side, clk, C, a_ns: int, b_ns: int) -> dict:
    """Fold-train statistics for the family-balanced inverse-vol vote: sigma_i = std of the token's raw matured 24h
    markouts on [a, b) (needs >= 60 distinct days, else the 75th percentile of the valid sigmas); u_i within family
    ~ 1/sigma_i; sigma_f = std of sum_i u_i m_i; q_f ~ 1/sigma_f."""
    from btcusdt_quant.rl import signal_store as SG
    lag = 1440 * SG.MIN_NS // SG.STEP_NS
    sel = np.flatnonzero((clk >= a_ns) & (clk < b_ns))
    sel = sel[sel >= lag]
    ret = (C[sel] / C[sel - lag] - 1.0) * 1e4
    s0 = side[sel - lag].astype(float)
    mk = s0 * ret[:, None] - SG.COST_BPS * (s0 != 0)
    day = clk[sel] // (86400 * 10**9)
    sig = {}
    for k, t_ in enumerate(toks):
        on = (s0[:, k] != 0) & np.isfinite(mk[:, k])
        sig[t_] = float(np.std(mk[on, k], ddof=1)) if len(np.unique(day[on])) >= 60 else None
    valid = [v for v in sig.values() if v and v > 0]
    fb = float(np.percentile(valid, 75)) if valid else 1.0
    sig = {k: (v if v and v > 0 else fb) for k, v in sig.items()}
    fam = {t_: SG.family_of(t_) for t_ in toks}
    u, fsig = np.zeros(len(toks)), {}
    for f in set(fam.values()):
        idx = [k for k, t_ in enumerate(toks) if fam[t_] == f]
        inv = np.array([1 / sig[toks[k]] for k in idx])
        u[idx] = inv / inv.sum()
        r = np.nansum(mk[:, idx] * u[idx], axis=1)
        fsig[f] = float(np.std(r, ddof=1)) if np.std(r) > 0 else fb
    return {"sigma": sig, "fallback": fb, "u": u, "family_sigma": fsig, "family": fam}


def sb_targets(kind: str, side, avail, W) -> np.ndarray:
    """Per decision row: quantized vote in TARGETS."""
    s = side.astype(float) * (avail > 0)
    if kind == "flat":
        v = np.zeros(len(s))
    elif kind == "ewa":
        n = (avail > 0).sum(1)
        v = np.where(n > 0, s.sum(1) / np.maximum(n, 1), 0.0)
    else:
        fams = sorted(set(W["family"].values()))
        toks = list(W["family"])
        fidx = {f: [k for k, t_ in enumerate(toks) if W["family"][t_] == f] for f in fams}
        num = np.zeros(len(s))
        den = np.zeros(len(s))
        for f in fams:
            ix = fidx[f]
            av = avail[:, ix] > 0
            uu = W["u"][ix] * av
            tot = uu.sum(1)
            vf = np.where(tot > 0, (s[:, ix] * uu).sum(1) / np.where(tot > 0, tot, 1), 0.0)
            q = np.where(tot > 0, 1.0 / W["family_sigma"][f], 0.0)
            num += q * vf
            den += q
        v = np.where(den > 0, num / np.where(den > 0, den, 1), 0.0)
    return np.clip(np.round(v * 4) / 4, -1, 1)


def sb_run(K, dec_i: np.ndarray, tg: np.ndarray, rv, rv_med: float) -> dict:
    from btcusdt_quant.rl import maker_kernel as MK
    K.reset(int(dec_i[0]))
    tot = {"net4": 0.0, "idle": 0.0, "turnover": 0.0, "reward": 0.0}
    for q in range(len(dec_i)):
        w = SB_WAIT
        i0 = K.i
        info = K.step(float(tg[q]), w)
        d = MK.step_reward(K.pnl, K.upath, rv, rv_med, i0, info["j"], info["d_target"])
        for k_ in tot:
            tot[k_] += d[k_]
    return tot


def cmd_scripted_baselines(args) -> None:
    from btcusdt_quant.rl import gates as GT, maker_kernel as MK, signal_store as SG, u35, dev_data as DD
    t0 = time.time()
    BD = OUT / "scripted_baselines"
    BD.mkdir(parents=True, exist_ok=True)
    minutes, fund, in_hash = DD.load_dev()
    fs = u35.scheduled(fund)
    t_min = minutes.open_time.array.asi8.copy()
    o, h, l, c = (minutes[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    rv = MK.rv24h(c)
    toks, side, avail, clk = sb_token_arrays()
    C = SG.close_at(clk, t_min, c)
    ts = lambda x: pd.Timestamp(x, tz="UTC").value  # noqa: E731
    kinds = ("famvol", "ewa", "flat")
    rep: dict = {"spec": {"kernel": MK.__doc__, "decision": f"every {SB_WAIT} m on the 5m clock (t = hour), target = "
                                                          "vote quantized to 0.25, wait 1h",
                          "votes": {"famvol": sb_invvol_weights.__doc__, "ewa": "mean side over available tokens",
                                    "flat": "always 0"},
                          "reward": MK.step_reward.__doc__, "rv_median": "fold train [2021-01-30, year start) median "
                                                                          "of RV24h at minute closes",
                          "tokens": toks, "data": "DEV loader (< 2026-01-01), funding snapped to settlements"},
                 "folds": {}, "yearly": {}, "continuous": {}}
    W_by_year, tg_by = {}, {k: {} for k in kinds}
    for y in U35_YEARS:
        a_tr, b_tr = ts(FOLDS_A2[U35_FOLD_OF[y]][0][0]), ts(FOLDS_A2[U35_FOLD_OF[y]][0][1])
        W = sb_invvol_weights(toks, side, clk, C, a_tr, b_tr)
        W_by_year[y] = W
        ia, ib = np.searchsorted(t_min, [a_tr, b_tr])
        rep["folds"][U35_FOLD_OF[y]] = {"sigma": W["sigma"], "fallback": W["fallback"], "family_sigma": W["family_sigma"],
                                        "rv24h_train_median": float(np.median(rv[ia + 1440:ib]))}
    for cell in G_CELLS:
        ctag = f"o{cell[0]}_p{cell[1]}"
        K = MK.Kernel(o, h, l, c, t_min, fs.time.array.asi8, fs.rate.to_numpy(float), cell[0], cell[1])
        for kind in kinds:
            days_all, stats = [], {}
            for y in U35_YEARS:
                a, b = ts(f"{y}-01-01"), ts(f"{y + 1}-01-01")
                dts = np.arange(a, b, SB_WAIT * SG.MIN_NS, dtype=np.int64)
                row = (dts - SG.CLOCK_START.value) // SG.STEP_NS
                tg = sb_targets(kind, side[row], avail[row], W_by_year[y])
                tg_by[kind][(ctag, y)] = tg
                dec_i = np.searchsorted(t_min, dts) - 1
                med = rep["folds"][U35_FOLD_OF[y]]["rv24h_train_median"]
                tot = sb_run(K, dec_i, tg, rv, med)
                ia, ib = np.searchsorted(t_min, [a, b])
                pnl, up = K.pnl[ia:ib].copy(), K.upath[ia:ib].copy()
                d = pnl.reshape(-1, 1440).sum(1)
                days_all.append(d)
                flat = np.abs(up) < 0.125
                stats[str(y)] = {"net4": float(pnl.sum()), "mdd": GT.mdd(d), "boot60_p05": GT.boot_p05(d, 60),
                                 "round_trips": int((flat[:-1] & ~flat[1:]).sum()), "flat_ratio": float(flat.mean()),
                                 "fills": int(K.st[MK.S_FILLS]), "fees": float(K.st[MK.S_FEES]),
                                 "funding": float(K.st[MK.S_FUND]), "reward": tot,
                                 "target_change_decisions": int((np.diff(np.r_[0.0, tg]) != 0).sum())}
            dd = np.concatenate(days_all)
            rep["yearly"].setdefault(ctag, {})[kind] = {"years": stats, "pooled_net4": float(dd.sum()), "mdd": GT.mdd(dd),
                                                        "boot60_p05": GT.boot_p05(dd, 60)}
            # continuous 2022..2025 run (one episode, year-end carry; fold weights switch at each year start)
            a, b = ts("2022-01-01"), ts("2026-01-01")
            dts = np.arange(a, b, SB_WAIT * SG.MIN_NS, dtype=np.int64)
            tg = np.concatenate([tg_by[kind][(ctag, y)] for y in U35_YEARS])
            dec_i = np.searchsorted(t_min, dts) - 1
            tot = sb_run(K, dec_i, tg, rv, rep["folds"]["F4"]["rv24h_train_median"])
            ia, ib = np.searchsorted(t_min, [a, b])
            pnl, up = K.pnl[ia:ib].copy(), K.upath[ia:ib].copy()
            d = pnl.reshape(-1, 1440).sum(1)
            flat = np.abs(up) < 0.125
            yrs = pd.DatetimeIndex(t_min[ia:ib], tz="UTC").year
            rep["continuous"].setdefault(ctag, {})[kind] = {
                "net4": float(pnl.sum()), "mdd": GT.mdd(d), "boot60_p05": GT.boot_p05(d, 60),
                "boot20_p05": GT.boot_p05(d, 20), "boot120_p05": GT.boot_p05(d, 120),
                "round_trips": int((flat[:-1] & ~flat[1:]).sum()), "flat_ratio": float(flat.mean()),
                "fills": int(K.st[MK.S_FILLS]), "net4_by_year": {str(y): float(pnl[yrs == y].sum()) for y in U35_YEARS},
                "reward_rv_median_note": "F4 train median used for the whole continuous run", "reward": tot}
        log(f"baselines {ctag}: " + " ".join(f"{k}={rep['continuous'][ctag][k]['net4']:.0f}" for k in kinds))
    rep.update(git_head=git("rev-parse", "HEAD"), created_utc=datetime.now(timezone.utc).isoformat(),
               runtime_sec=round(time.time() - t0, 1), test_accessed=False, input_sha256=in_hash,
               signal_store_manifest_sha256=sha(SS / "manifest.json"),
               code_sha256={k_: sha(ROOT / f"btcusdt_quant/rl/{k_}.py") for k_ in ("maker_kernel", "signal_store")})
    dump(BD / "scripted_baselines_report.json", rep)
    registry.record(REGISTRY, {"experiment": "SMDP scripted baselines (famvol / ewa / flat) on the maker kernel",
                               "role": "trial", "n_trials": 3, "n_simulations": 36,
                               "config": {"wait_min": SB_WAIT, "tokens": len(toks)},
                               "result_summary": {c_: {k: round(v["net4"], 3) for k, v in r.items()}
                                                  for c_, r in rep["continuous"].items()}})
    log(f"scripted baselines done {rep['runtime_sec']}s")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("freeze", "amend", "amend2", "precompute", "signals", "state", "env-check",
                                       "vec-check", "baselines", "smoke", "pilot-g3", "pilot-e2", "router",
                                       "regime-short", "regime-bidir", "regime-bidir-r2", "gates",
                                       "short-hsel", "long-pullback", "g3-idle-et", "u35-precompute", "signal-store", "scripted-baselines"))
    ap.add_argument("--paths", type=int, default=100)
    ap.add_argument("--updates", type=int, default=30)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--books", default="")
    ap.add_argument("--only", default="g3,c,ax")
    ap.add_argument("--no-registry", action="store_true")
    ap.add_argument("--allow-test-parity", action="store_true",
                    help="explicit TEST unlock: precompute integrity parity / TEST state rows only")
    args = ap.parse_args(argv)
    args.only = set(args.only.split(","))
    if args.command == "freeze":
        return cmd_freeze(args)
    if args.command == "amend":
        return cmd_amend(args)
    if args.command == "amend2":
        return cmd_amend2(args)
    if args.command == "signals":
        return cmd_signals(args)
    if args.command == "env-check":
        return cmd_env_check(args)
    if args.command == "vec-check":
        return cmd_vec_check(args)
    if args.command == "baselines":
        return cmd_baselines(args)
    if args.command == "smoke":
        return cmd_smoke(args)
    if args.command == "pilot-g3":
        return cmd_pilot_g3(args)
    if args.command == "pilot-e2":
        return cmd_pilot_e2(args)
    if args.command == "router":
        return cmd_router(args)
    if args.command == "regime-short":
        return cmd_regime_short(args)
    if args.command == "regime-bidir":
        return cmd_regime_bidir(args)
    if args.command == "regime-bidir-r2":
        return cmd_regime_bidir_r2(args)
    if args.command == "gates":
        return cmd_gates(args)
    if args.command == "short-hsel":
        return cmd_hsel(args)
    if args.command == "long-pullback":
        return cmd_long_pullback(args)
    if args.command == "g3-idle-et":
        return cmd_g3_idle_et(args)
    if args.command == "u35-precompute":
        return cmd_u35_precompute(args)
    if args.command == "signal-store":
        return cmd_signal_store(args)
    if args.command == "scripted-baselines":
        return cmd_scripted_baselines(args)
    if args.command == "precompute":
        sp.require_unlock(args.allow_test_parity, "precompute parity (reported TEST numbers)")
        return cmd_precompute(args)
    return cmd_state(args)


if __name__ == "__main__":
    main()
