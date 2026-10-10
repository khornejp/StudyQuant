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


def native_out(s, t_glob, segs, files, avail_rep):
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
    files[f"common/{s}"] = write_sleeve(PRE / "common" / s, gf, rows, t_glob, opp, np.arange(len(opp)))
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
        return AP.Trainer(cells, SMOKE_COUNTS, static_w, train, val, cfg, seed=0, fold=fold)

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
    best = {"key": v["worst_cell_excess"], "update": 0} if not v["all_flat"] else {"key": -math.inf, "update": -1}
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
            if not v["all_flat"] and v["worst_cell_excess"] > best["key"]:
                best = {"key": v["worst_cell_excess"], "update": u}
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


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("freeze", "amend", "amend2", "precompute", "signals", "state", "env-check",
                                       "vec-check", "baselines", "smoke"))
    ap.add_argument("--paths", type=int, default=100)
    ap.add_argument("--updates", type=int, default=30)
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
    if args.command == "precompute":
        sp.require_unlock(args.allow_test_parity, "precompute parity (reported TEST numbers)")
        return cmd_precompute(args)
    return cmd_state(args)


if __name__ == "__main__":
    main()
