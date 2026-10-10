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
import argparse, hashlib, importlib.util, json, subprocess, sys, time
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
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


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
    return dict(m=m, mk=mk, dec4=dec4, b2=b2, sleeves=out, st=st, f=f)


# ================================================================ C1v2 / C4v2
def c_family(args, rec: dict) -> dict:
    F = load("sim_r2_56_fix1_rl", "scripts/sim_r2_56_fix1.py")
    rp, r237 = F.rp, F.r237
    F.verify_inputs()
    rows_ls, _ = F.ls_rows()
    market, features, fund, *_ = F.inputs(rows_ls)
    leg, books = F.books_for(market, features)
    t = market.open_time.array.asi8.copy()
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
        out[(s, "native")] = dict(tr=tr, bk=bk, rows=rows, net=net)
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
    return dict(market=market, fund=fund, mk=mk, ft=ft, fr=fr, r237=r237, sleeves=out)


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
            g.update(tr=tr, rows=rows, net=net, t=tt)
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


def grid_frame(n, t, s, cell_id, *, side_sig, w_sig, active, pending, open_, exit_pending, opp, sched, R0, Rt,
               lvl, armed, rows, snap, available) -> pd.DataFrame:
    g = np.bincount(rows["minute"], rows["gross"], minlength=n)[:n]
    fe = np.bincount(rows["minute"], rows["fee"], minlength=n)[:n]
    fu = np.bincount(rows["minute"], rows["funding"], minlength=n)[:n]
    return pd.DataFrame({
        "minute_time": t, "sleeve_id": np.full(n, SLEEVE_ID[s], np.int8), "exec_cell": np.full(n, cell_id, np.int8),
        "available": available, "base_side": side_sig.astype(np.int8), "base_weight": w_sig.astype(np.float32),
        "signal_active": active, "pending": pending, "open": open_, "exit_pending": exit_pending,
        "entry_opportunity_id": opp.astype(np.int32), "base_exit_sched_time": sched.astype(np.int64),
        "R0_bps": R0.astype(np.float32), "R_t_bps": Rt.astype(np.float32), "stop_level": lvl.astype(np.float32),
        "trail_armed": armed.astype(np.int8), "gross_pnl": g, "fee": fe, "funding": fu, "net4": g + fe + fu,
        "available_time": t + sp.MIN, "feature_snapshot_id": snap.astype(np.int32)})


def ledger_frame(rows, t, opp_of_tid) -> pd.DataFrame:
    return pd.DataFrame({"minute_time": t[rows["minute"]], "minute_idx": rows["minute"],
                         "entry_opportunity_id": opp_of_tid[rows["tid"]].astype(np.int32),
                         "tid": rows["tid"].astype(np.int32), "gross_pnl": rows["gross"], "fee": rows["fee"],
                         "funding": rows["funding"], "net4": rows["gross"] + rows["fee"] + rows["funding"]})


def out_g3(G, files):
    m, dec4 = G["m"], G["dec4"]
    n, t = m.N, m.t
    sig_min = np.searchsorted(dec4, np.arange(n), "left") - 1          # latest decision with dec4 < i (closed)
    for (s, tag), d in G["sleeves"].items():
        tr, od = d["tr"], d["od"].reset_index(drop=True)
        cell_id = [CELL_TAG[c] for c in CELLS].index(tag)
        k = (od.decision_idx.to_numpy() - 239) // 240
        opp = pd.DataFrame({"entry_opportunity_id": np.arange(len(od), dtype=np.int32),
                            "decision_idx": od.decision_idx.to_numpy(np.int64),
                            "decision_time": t[od.decision_idx.to_numpy()],
                            "available_time": t[od.decision_idx.to_numpy()] + sp.MIN,
                            "side": od.side.to_numpy(np.int8), "base_weight": od.weight.to_numpy(float),
                            "filled": od.filled.to_numpy(bool), "feature_snapshot_id": k.astype(np.int32)})
        fill_opp = np.flatnonzero(opp.filled.to_numpy())
        if len(fill_opp) != len(tr) or not np.array_equal(od.decision_idx.to_numpy()[fill_opp], tr.decision_idx.to_numpy()):
            raise Fail(f"{s} {tag} order->trade map")
        opp["tid"] = -1
        opp.loc[fill_opp, "tid"] = tr.tid.to_numpy()
        for c in ("entry_idx", "entry_px", "exit_decision_idx", "exit_idx", "exit_px", "open_at_end"):
            opp[c] = np.nan if c.endswith("px") else (-1 if c != "open_at_end" else False)
            opp.loc[fill_opp, c] = tr[c].to_numpy()
        if s == "LBR_FUND":
            sched = np.full(len(opp), -1, np.int64)
            kk = opp.feature_snapshot_id.to_numpy() + 2
            okk = kk < len(dec4)
            sched[okk] = t[dec4[kk[okk]]] + sp.MIN            # exit decision bar close (max_hold 2 bars)
        else:
            sched = np.full(len(opp), -1, np.int64)
        opp["base_exit_sched_time"] = sched
        tot = pd.DataFrame({"tid": d["rows"]["tid"], "g": d["rows"]["gross"], "f": d["rows"]["fee"],
                            "u": d["rows"]["funding"]}).groupby("tid").sum()
        for nm, c in (("gross_pnl", "g"), ("fee", "f"), ("funding", "u")):
            opp[nm] = 0.0
            opp.loc[fill_opp, nm] = tot[c].reindex(tr.tid).to_numpy()
        opp["net4"] = opp.gross_pnl + opp.fee + opp.funding
        dec = opp.decision_idx.to_numpy()
        j0 = np.where(opp.filled, opp.entry_idx, -1).astype(np.int64)
        pend_end = np.where(opp.filled, j0 - 1, np.minimum(dec + 60, n - 1))
        oa, ob = tr.entry_idx.to_numpy(), np.where(tr.open_at_end, n - 1, tr.exit_idx).astype(np.int64)
        xa = np.where(tr.open_at_end, n, tr.exit_decision_idx + 1).astype(np.int64)
        oid = opp.entry_opportunity_id.to_numpy()
        opp_min = sp.interval_fill(n, dec + 1, pend_end, oid, -1, np.int32)
        opp_open = sp.interval_fill(n, oa, ob, oid[fill_opp], -1, np.int32)
        opp_min = np.where(opp_open >= 0, opp_open, opp_min)
        sched_min = np.full(n, -1, np.int64)
        if s == "LBR_FUND":
            sched_min = sp.interval_fill(n, oa, ob, sched[fill_opp], -1, np.int64)
        side_sig = np.where(sig_min >= 0, d["sig"]["side"][np.maximum(sig_min, 0)], 0)
        w_sig = np.where(sig_min >= 0, d["sig"]["w"][np.maximum(sig_min, 0)], 0.0)
        openm = sp.interval_mask(n, oa, ob)
        w_open = sp.interval_fill(n, oa, ob, tr.entry_weight_frozen.to_numpy(), np.nan, float)
        w_sig = np.where(openm, w_open, w_sig)
        nanf = np.full(n, np.nan)
        gf = grid_frame(n, t, s, cell_id, side_sig=side_sig, w_sig=w_sig, active=side_sig != 0,
                        pending=sp.interval_mask(n, dec + 1, pend_end), open_=openm,
                        exit_pending=sp.interval_mask(n, xa, ob), opp=opp_min, sched=sched_min, R0=nanf, Rt=nanf,
                        lvl=nanf, armed=np.zeros(n), rows=d["rows"], snap=sig_min,
                        available=np.ones(n, bool))
        need_eq = float(np.abs(gf.net4.to_numpy() - d["net"]).max())
        if need_eq > ATOL_MIN:
            raise Fail(f"{s} {tag} grid net4")
        dd = PRE / "g3_family" / tag / s
        files[f"g3_family/{tag}/{s}"] = {"grid": write_part(gf, dd, "grid"),
                                         "ledger": write_part(ledger_frame(d["rows"], t, opp_of(opp, len(tr))), dd, "ledger"),
                                         "opportunities": write_part(opp, dd, "opportunities", "decision_time"),
                                         "n_opportunities": int(len(opp)), "n_trades": int(len(tr))}
        log(f"wrote {s} {tag}")


def opp_of(opp: pd.DataFrame, ntr: int) -> np.ndarray:
    o = np.full(ntr, -1, np.int64)
    f = opp[opp.tid >= 0]
    o[f.tid.to_numpy(int)] = f.entry_opportunity_id.to_numpy()
    return o


def native_out(s, t_glob, segs, files, kind):
    """segs: list of dict(t, tr, rows, mk?, R state...) on their own minute arrays; mapped onto the global grid."""
    n = len(t_glob)
    rows_all, opps, R0, Rt, lvl, arm = [], [], np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan), np.zeros(n)
    side, w = np.zeros(n, np.int8), np.zeros(n)
    openm = np.zeros(n, bool)
    opp_min = np.full(n, -1, np.int32)
    sched = np.full(n, -1, np.int64)
    snap = np.full(n, -1, np.int32)
    avail = np.zeros(n, bool)
    base = 0
    for g in segs:
        off = int(np.searchsorted(t_glob, g["t"][0]))
        if not np.array_equal(t_glob[off:off + len(g["t"])], g["t"]):
            raise Fail(f"{s} segment minutes not on the global grid")
        avail[off:off + len(g["t"])] = True
        tr = g["tr"].reset_index(drop=True)
        oid = base + np.arange(len(tr))
        rr = {k: v.copy() for k, v in g["rows"].items()}
        rr["minute"] = rr["minute"] + off
        rr["tid"] = rr["tid"] + base
        rows_all.append(rr)
        e, x = tr.e.to_numpy() + off, tr.x.to_numpy() + off
        for q in range(len(tr)):
            a, b = e[q], x[q]
            openm[a:b + 1] = True
            opp_min[a:b + 1] = oid[q]
            side[a:b + 1] = tr.side.iloc[q]
            w[a:b + 1] = 1.0
            if "sched_exit_ns" in tr:
                sched[a:b + 1] = tr.sched_exit_ns.iloc[q]
            if "e0" in tr and np.isfinite(tr.e0.iloc[q]):
                R0_, R_, _, A_, L_ = sp.adaptive_path(g["mm"].open.to_numpy(float), g["mm"].high.to_numpy(float),
                                                      g["mm"].low.to_numpy(float), g["e_min"][:, int(tr.e_col.iloc[q])],
                                                      int(tr.e.iloc[q]), int(tr.x.iloc[q]), int(tr.side.iloc[q]),
                                                      float(tr.px_in.iloc[q]), float(tr.k.iloc[q]), float(tr.e0.iloc[q]))
                R0[a:b + 1], Rt[a:b + 1], arm[a:b + 1], lvl[a:b + 1] = R0_, R_, A_, L_
        snap_seg = np.searchsorted(tr.e.to_numpy(), np.arange(len(g["t"])), "right") - 1
        snap[off:off + len(g["t"])] = np.where(snap_seg >= 0, oid[np.maximum(snap_seg, 0)], -1)
        tot = pd.DataFrame({"tid": g["rows"]["tid"], "g": g["rows"]["gross"], "f": g["rows"]["fee"],
                            "u": g["rows"]["funding"]}).groupby("tid").sum().reindex(tr.tid, fill_value=0.0)
        dec_t = (tr.decision_ns if "decision_ns" in tr else tr.entry_ns).to_numpy(np.int64)  # data closed through it
        o = pd.DataFrame({"entry_opportunity_id": oid.astype(np.int32), "tid": oid, "segment": g.get("seg", "ALL"),
                          "decision_time": dec_t, "available_time": dec_t,
                          "side": tr.side.to_numpy(np.int8), "base_weight": tr.units.to_numpy(float), "filled": True,
                          "entry_idx": e, "entry_px": tr.px_in.to_numpy(), "exit_idx": x,
                          "exit_px": tr.px_out.to_numpy(), "exit_reason": tr.reason.to_numpy(),
                          "base_exit_sched_time": tr.sched_exit_ns.to_numpy() if "sched_exit_ns" in tr else -1,
                          "feature_snapshot_id": tr.snapshot_id.to_numpy(np.int64),
                          "gross_pnl": tot.g.to_numpy(), "fee": tot.f.to_numpy(), "funding": tot.u.to_numpy()})
        o["net4"] = o.gross_pnl + o.fee + o.funding
        for c in ("candidate", "e0", "k", "e_col", "entry_kind", "position_id"):
            if c in tr:
                o[c] = tr[c].to_numpy()
        opps.append(o)
        base += len(tr)
    rows = {k: np.concatenate([r[k] for r in rows_all]) for k in sp.ROW_COLS}
    opp = pd.concat(opps, ignore_index=True)
    gf = grid_frame(n, t_glob, s, 0, side_sig=side, w_sig=w, active=openm, pending=np.zeros(n, bool), open_=openm,
                    exit_pending=np.zeros(n, bool), opp=opp_min, sched=sched, R0=R0, Rt=Rt, lvl=lvl, armed=arm,
                    rows=rows, snap=snap, available=avail)
    dd = PRE / "common" / s
    files[f"common/{s}"] = {"grid": write_part(gf, dd, "grid"),
                            "ledger": write_part(ledger_frame(rows, t_glob, np.arange(len(opp))), dd, "ledger"),
                            "opportunities": write_part(opp, dd, "opportunities", "decision_time"),
                            "n_opportunities": int(len(opp))}
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
    files = {}
    t_glob = G["m"].t
    out_g3(G, files)
    mk_common = pd.DataFrame({"minute_time": t_glob, **{k: G["mk"][k] for k in ("o", "h", "l", "c")}})
    files["common/market"] = write_part(mk_common, PRE / "common" / "market", "market")
    files["common/funding_g3"] = write_part(pd.DataFrame({"minute_time": G["m"].ft, "rate": G["m"].fr}),
                                            PRE / "common" / "funding", "funding_g3")
    if C:
        for s in ("C1v2", "C4v2"):
            d = C["sleeves"][(s, "native")]
            native_out(s, t_glob, [dict(t=C["mk"]["t"], tr=d["tr"], rows=d["rows"], seg="ALL")], files, "log")
        files["common/funding_c"] = write_part(pd.DataFrame({"minute_time": C["ft"], "rate": C["fr"]}),
                                               PRE / "common" / "funding", "funding_c")
    if X:
        for s in ("B3_AXC0", "K04_AXC0"):
            native_out(s, t_glob, X["sleeves"][(s, "native")]["segs"], files, "log")
        for g in X["sleeves"][("B3_AXC0", "native")]["segs"]:
            files[f"common/funding_ax_{g['seg']}"] = write_part(pd.DataFrame({"minute_time": g["ft"], "rate": g["fr"]}),
                                                               PRE / "common" / "funding", f"funding_ax_{g['seg']}")
    total_bytes = sum(p.stat().st_size for p in PRE.rglob("*.parquet"))
    runtime = round(time.time() - t_start, 1)
    manifest = {
        "name": "RL allocator sleeve precompute (step 2)", "created_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_sha256": sha(FREEZE), "data_cutoff": fz["data_cutoff"], "frozen_hypothesis": fz["frozen_hypothesis"],
        "code_sha256": {"script": sha(Path(__file__)), "module": sha(ROOT / "btcusdt_quant/rl/sleeve_precompute.py")},
        "git_head": git("rev-parse", "HEAD"), "runtime_sec": runtime, "parity": rec, "counterfactual": cf,
        "adaptive_stop_check": stops, "files": files, "total_bytes": total_bytes,
        "layout": {"common/<sleeve>": "B3_AXC0, K04_AXC0, C1v2, C4v2 (native fill, one cell)",
                   "g3_family/<cell>/<sleeve>": "G3_LONG, G3_SHORT, LBR_FUND x 6 cells",
                   "grid_<year>": "per minute state + canonical P&L (float64 P&L, float32 state)",
                   "ledger_<year>": "per (minute, opportunity) canonical rows: fast counterfactual replay input",
                   "opportunities_<year>": "canonical entry opportunity schedule (env-only: realized exit fields are "
                                           "future information and must never enter observations)",
                   "observation_cache_1h": "placeholder (step 3)"},
        "test_guard": "read_partitioned refuses *_2026 partitions without allow_test=True",
        "notes": ["G3/LBR grid minutes 2020-01-01..2026-10-07; B3/K04 available 2023-09-01..2026-10-07 in two "
                  "segments (native rolling-k ends with a data_end close at 2025-12-31 23:59; TEST restarts flat)",
                  "base_exit_sched_time: LBR exit decision bar close (activation + 2 bars), C max_hold expiry; "
                  "G3 and B3/K04 have no scheduled exit (-1)"]}
    dump(PRE / ("manifest.json" if args.only == {"g3", "c", "ax"} else "manifest_partial.json"), manifest)
    (PRE / "observation_cache_1h").mkdir(exist_ok=True)
    if not args.no_registry and args.only == {"g3", "c", "ax"}:
        registry.record(REGISTRY, {"experiment": "RL allocator sleeve precompute (steps 1-2)", "role": "precompute",
                                   "n_trials": 0, "n_simulations": 0,
                                   "config": {"freeze_sha256": sha(FREEZE), "sleeves": list(SLEEVES),
                                              "cells": [CELL_TAG[c] for c in CELLS], "paths": args.paths,
                                              "data_cutoff": fz["data_cutoff"]},
                                   "input_hashes": fz["source_hashes"],
                                   "result_summary": {k: {x: v.get(x) for x in ("DEV-FULL_net4", "TEST_net4")}
                                                      for k, v in rec.items() if isinstance(v, dict)}})
    log(f"done runtime {runtime}s bytes {total_bytes}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("freeze", "precompute"))
    ap.add_argument("--paths", type=int, default=100)
    ap.add_argument("--only", default="g3,c,ax")
    ap.add_argument("--no-registry", action="store_true")
    args = ap.parse_args()
    args.only = set(args.only.split(","))
    cmd_freeze(args) if args.command == "freeze" else cmd_precompute(args)


if __name__ == "__main__":
    main()
