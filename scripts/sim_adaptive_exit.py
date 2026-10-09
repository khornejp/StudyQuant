"""R2-52A research run (frozen spec out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json): adaptive exits
(SimConfig.exit_policy="R2_52A") on the NONE/NATIVE signal table of each included id, k in {1.0, 1.5, 2.0} selected on
each rolling validation window (tie -> 2.0), one continuous stitched test, paired daily PW versus BASE NONE/NATIVE,
plus the pre-registered V3 ablation on the selected k (ablation_V3).
Usage: python scripts/sim_adaptive_exit.py [--ids K01 ...] [--windows W01 ...] [--workers 8] [--out DIR] [--no-register]
       python scripts/sim_adaptive_exit.py --flip [--register]   # C1_FLIP_AX: K01_FLIP only, into r2_52a_flip/
"""
from __future__ import annotations
import argparse, json, sys, time, traceback
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from btcusdt_quant.sim import analytics, core, costs, data, guard, provenance, regime, registry, rolling  # noqa: E402
from btcusdt_quant.sim.reference import SimConfig  # noqa: E402
from btcusdt_quant.sim.strategies import CATALOG, Context, build_variant, legacy  # noqa: E402
import sim_strategy_rolling as plan2  # noqa: E402  reuse: positions, input_hashes, prediction gaps

O = ROOT / "out/k45_rl_r2_48_20261007"
FREEZE_PATH = O / "r2_52a_exit_freeze.json"
FREEZE = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
INCLUDED = tuple(FREEZE["scope"]["included_ids"])
ATOMIC = tuple(i for i in INCLUDED if i not in ("B1", "B2", "B3"))          # scope.atomic_only_diagnostic
K_VALUES = (1.0, 1.5, 2.0)
N_TRIALS = len(INCLUDED) * len(K_VALUES)       # freeze trials: 29 x 3 = 87 candidate return series
N_TRIALS_V3 = len(INCLUDED)                     # + 29: the selected-k V3 ablation
V3_MAX_AGE = pd.Timedelta(minutes=14)
OUT = O / "r2_52a"
FLIP_IDS = ("K01_FLIP",)                        # C1_FLIP_AX (Codex 2026-10-09): post-freeze, outside INCLUDED
FLIP_OUT = O / "r2_52a_flip"                   # its own selected_k.csv / manifest; never the frozen 29-id folder
REGISTRY = ROOT / "out/sim_registry.jsonl"
CONFIG = SimConfig(exit_policy="R2_52A")       # strict, NATIVE rows, 4 bps round trip, PESS funding, delay 1
PW_LABEL = "unadjusted diagnostic (no multiplicity correction; no per-id significance claim)"
_CTX: Context | None = None


def select_k(scores: dict[float, float]) -> float:
    """Best validation P&L; ties go to the candidate nearest 2.0 (the largest k)."""
    return max(scores, key=lambda k: (scores[k], k))


def _valid_e(frame: pd.DataFrame, head: str) -> pd.DataFrame:
    column = f"prediction_exc_{head}"
    v = frame[column].to_numpy(float)
    keep = ["timestamp", column] + [c for c in regime.AVAILABILITY if c in frame]
    return frame.loc[np.isfinite(v) & (v > 0), keep]


def e_at(frame: pd.DataFrame, times: pd.DatetimeIndex, head: str) -> np.ndarray:
    """Latest finite >0 E with timestamp and availability (regime.available_ns; research: logical_available_at or
    timestamp) <= t and age <= 24 h."""
    return regime._asof(_valid_e(frame, head), times, f"prediction_exc_{head}", regime.E_MAX_AGE)


def e_series(frame: pd.DataFrame, minute_times: pd.DatetimeIndex, head: str) -> tuple[np.ndarray, np.ndarray]:
    """core.simulate e_bps / e_min_bps for one head: e = latest valid E as of open(m); e_min = min of the valid E
    that became available in (open(m-1), open(m)] (each E goes to the first minute whose open >= its availability)."""
    valid = _valid_e(frame, head)
    t = pd.DatetimeIndex(minute_times).as_unit("ns").asi8
    stamp = pd.DatetimeIndex(valid.timestamp).as_unit("ns").asi8
    avail = regime.available_ns(valid)
    avail = stamp if avail is None else avail
    values = valid[f"prediction_exc_{head}"].to_numpy(float)
    idx = np.searchsorted(t, avail, side="left")
    keep = idx < len(t)
    keep[keep] = t[idx[keep]] - stamp[keep] <= regime.E_MAX_AGE.value      # a data gap must not revive old E
    e_min = np.full(len(t), np.nan)
    np.fmin.at(e_min, idx[keep], values[keep])
    return e_at(frame, minute_times, head), e_min


def legacy_heads() -> dict[int, str]:
    """Composite component -> its E head (R2-46 E_COLUMN); only the opening component supplies E metadata."""
    return {legacy.FAST[name][0]: legacy.E_HEAD[name] for name in legacy.FAST}


def heads(spec_id: str) -> list[str]:
    spec = CATALOG[spec_id]
    return sorted(set(legacy_heads().values())) if spec.family == "composite" else [spec.e_head]


def e_cols(table: pd.DataFrame, spec_id: str) -> np.ndarray:
    """Row -> column of e_matrix: the component's head (composites), else 0. Core locks it at the fill."""
    if CATALOG[spec_id].family != "composite":
        return np.zeros(len(table), np.int64)
    names = heads(spec_id)
    return table.component.map(legacy_heads()).map(names.index).to_numpy(np.int64)


def e_matrix(frame: pd.DataFrame, minute_times: pd.DatetimeIndex, names: list[str]) -> tuple[np.ndarray, np.ndarray]:
    pairs = [e_series(frame, minute_times, head) for head in names]
    return np.column_stack([p[0] for p in pairs]), np.column_stack([p[1] for p in pairs])


def row_e0(table: pd.DataFrame, regime_frame: pd.DataFrame, spec_id: str) -> np.ndarray:
    """E0 for market entries: E known at the decision time T of each row, from the row's own head."""
    times = pd.DatetimeIndex(table.decision_time)
    names, cols = heads(spec_id), e_cols(table, spec_id)
    out = np.full(len(table), np.nan)
    for c, head in enumerate(names):
        rows = cols == c
        out[rows] = e_at(regime_frame, times[rows], head)
    return out


def k_schedule(minute_times, picks: dict[str, float], windows) -> np.ndarray:
    """k per minute = the pick of the test window containing that minute; core reads it at the fill minute (market
    or OCO) and locks it on the position, so a boundary never changes an open position."""
    t = pd.DatetimeIndex(minute_times)
    k = np.full(len(t), np.nan)
    for w in windows:
        k[(t >= w.test_start) & (t < w.test_end)] = picks[w.name]
    return k


def v3_series(frame: pd.DataFrame, minute_times) -> np.ndarray:
    """ablation_V3 M per minute: latest M with timestamp and available_at <= open(m) and age <= 14 min, else NaN."""
    return regime._asof(frame, pd.DatetimeIndex(minute_times), "M", V3_MAX_AGE)


def run_ax(table, minutes, e, e_min, a, b, config, k_minute, v3=None):
    """R2_52A from a flat position at a (earlier rows are only indicator warm-up already inside the table)."""
    inside = ((minutes.open_time >= a) & (minutes.open_time < b)).to_numpy()
    return core.simulate(table, minutes.loc[inside].reset_index(drop=True), a, b, config, e_bps=e[inside],
                         e_min_bps=e_min[inside], k_minute=np.asarray(k_minute, float)[inside],
                         v3_m=None if v3 is None else v3[inside])


def validation_pnl(table, minutes, e, e_min, a, b, config, k: float) -> float:
    """Minute-ledger P&L on [a, b) with a constant k; an open position is marked to the last close without an exit
    fee and pays the settlements it held through."""
    result = run_ax(table, minutes, e, e_min, a, b, replace(config, close_at_end=False), np.full(len(minutes), k))
    pnl = float(result.minute_pnl.sum())
    held = result.open_position
    if held is not None and config.include_funding:
        events = costs.funding_events(held["side"], held["entry_time"], b - pd.Timedelta(minutes=1),
                                      config.funding_boundary)
        pnl += sum(v for _, v in events) * held["units"]
    return pnl


def carried(trades: pd.DataFrame, windows) -> list[dict]:
    """Positions open at a later test boundary (opened before it, closed at or after its first minute)."""
    pos = plan2.positions(trades)
    out = []
    for w in windows[1:]:
        for p in pos.loc[(pos.entry_time < w.test_start) & (pos.exit_time >= w.test_start)].itertuples(index=False):
            out.append({"boundary": w.test_start, "window": w.name, "position_id": int(p.position_id),
                        "entry_time": p.entry_time, "exit_time": p.exit_time, "side": int(p.side)})
    return out


def daily(minute_pnl: pd.Series, days: pd.DatetimeIndex) -> pd.Series:
    return minute_pnl.groupby(minute_pnl.index.floor("D")).sum().reindex(days, fill_value=0.0)


def _drawdown(d: pd.Series) -> float:
    cum = d.cumsum()
    return float((cum.cummax().clip(lower=0) - cum).max()) if len(cum) else 0.0


def _worst(trades: pd.DataFrame) -> float | None:
    pos = plan2.positions(trades)
    return float(pos.net_bps.min()) if len(pos) else None


def compare(p4, p8, n4, n8, days) -> dict:
    """Policy vs NATIVE on the same calendar: every UTC day, zero-filled, before differencing."""
    d4 = daily(p4.minute_pnl, days) - daily(n4.minute_pnl, days)
    trade_n = int(plan2.positions(p4.trades).shape[0])
    return {"trade_n": trade_n, "zero_reason": None if trade_n else "no positions in the stitched test",
            "exit_reasons": p4.trades.exit_reason.value_counts().to_dict(),
            "data_end_closes": int((p4.trades.exit_reason == "data_end").sum()),
            "net_4bps": float(p4.minute_pnl.sum()), "delta_4bps": float(d4.sum()),
            "delta_8bps": float((daily(p8.minute_pnl, days) - daily(n8.minute_pnl, days)).sum()),
            "pw_delta": analytics.pw_mean_ci(d4.to_numpy()), "pw_label": PW_LABEL,
            "worst_position_bps": _worst(p4.trades), "native_worst_position_bps": _worst(n4.trades),
            "max_drawdown_bps": _drawdown(daily(p4.minute_pnl, days)),
            "native_max_drawdown_bps": _drawdown(daily(n4.minute_pnl, days))}


def _init(end: str) -> None:
    global _CTX
    _CTX = Context.load(end=pd.Timestamp(end))


def run_id(spec_id: str, names: list[str], out_dir: str) -> dict:
    try:
        ctx = _CTX
        windows = [w for w in rolling.WINDOWS if w.name in names]
        table, _ = build_variant(ctx, spec_id, False, "NATIVE", ax=True)
        table = table.assign(e0_bps=row_e0(table, ctx.regime, spec_id), e_col=e_cols(table, spec_id).astype(float))
        minutes = ctx.minutes
        times = pd.DatetimeIndex(minutes.open_time)
        e, e_min = e_matrix(ctx.regime, times, heads(spec_id))
        picks, selection = {}, []
        for w in windows:
            scores = {k: validation_pnl(table, minutes, e, e_min, w.val_start, w.val_end, CONFIG, k) for k in K_VALUES}
            picks[w.name] = select_k(scores)
            selection.append({"id": spec_id, "window": w.name, "val_start": w.val_start, "val_end": w.val_end,
                              **{f"val_net_4bps_k{k}": v for k, v in scores.items()}, "k": picks[w.name]})
        a, b = windows[0].test_start, windows[-1].test_end
        k_minute = k_schedule(times, picks, windows)
        final = replace(CONFIG, close_at_end=True)       # data end: administrative close, flagged data_end
        fee8 = replace(final, fee_per_side=4.0)          # same k sequence, no reselection
        ax4 = run_ax(table, minutes, e, e_min, a, b, final, k_minute)
        ax8 = run_ax(table, minutes, e, e_min, a, b, fee8, k_minute)
        fixed_r, m = np.full_like(e_min, np.nan), v3_series(ctx.regime, times)   # V3: R_t = R0, causal M exit
        v34 = run_ax(table, minutes, e, fixed_r, a, b, final, k_minute, m)
        v38 = run_ax(table, minutes, e, fixed_r, a, b, fee8, k_minute, m)
        native, native_config = build_variant(ctx, spec_id, False, "NATIVE")
        inside = ((minutes.open_time >= a) & (minutes.open_time < b)).to_numpy()
        test_minutes = minutes.loc[inside].reset_index(drop=True)
        nat4 = core.simulate(native, test_minutes, a, b, replace(native_config, close_at_end=True))
        nat8 = core.simulate(native, test_minutes, a, b, replace(native_config, close_at_end=True, fee_per_side=4.0))
        days = pd.date_range(a, b, freq="D", inclusive="left")
        frame = pd.DataFrame({f"{n}_{c}": daily(r.minute_pnl, days) for n, c, r in (
            ("ax", "4bps", ax4), ("ax", "8bps", ax8), ("v3", "4bps", v34), ("v3", "8bps", v38),
            ("native", "4bps", nat4), ("native", "8bps", nat8))})
        for name, value in (("daily", frame), ("trades_ax", ax4.trades), ("trades_v3", v34.trades),
                            ("trades_native", nat4.trades)):
            Path(out_dir, name).mkdir(parents=True, exist_ok=True)
            value.to_parquet(Path(out_dir, name, f"{spec_id}.parquet"))
        executes = pd.DatetimeIndex(table.decision_time) + pd.Timedelta(minutes=CONFIG.delay_min)
        wants = ((table.side != 0) & table.allow_entry & (table.entry == "market") & (executes >= a)
                 & (executes < b)).to_numpy()
        e0 = table.e0_bps.to_numpy()
        return {"id": spec_id, "status": "ok", "selection": selection, "carried": carried(ax4.trades, windows),
                **compare(ax4, ax8, nat4, nat8, days), "native_trade_n": int(plan2.positions(nat4.trades).shape[0]),
                "native_net_4bps": float(nat4.minute_pnl.sum()),
                "no_entry_e_market_rows": int((wants & ~(np.isfinite(e0) & (e0 > 0))).sum()),
                "v3": compare(v34, v38, nat4, nat8, days)}
    except Exception as error:      # a failed id invalidates the run (pass_criteria.catalog); never dropped
        return {"id": spec_id, "status": "error", "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(limit=5)}


def k01_gates(r: dict) -> dict:
    worst, native_worst = r["worst_position_bps"], r["native_worst_position_bps"]
    gates = {"pw_lower_gt_0": r["pw_delta"]["lower"] > 0, "delta_8bps_ge_0": r["delta_8bps"] >= 0,
             "worst_position_ge_native": worst is not None and native_worst is not None and worst >= native_worst,
             "max_drawdown_le_native": r["max_drawdown_bps"] <= r["native_max_drawdown_bps"]}
    return {**gates, "pass": all(gates.values()), "delta_4bps": r["delta_4bps"], "delta_8bps": r["delta_8bps"],
            "pw_delta": r["pw_delta"]}


def aggregate(deltas: pd.DataFrame, ids, results: dict) -> dict:
    """Equal-weight (1/len(ids)) mean of each id's zero-filled daily policy-minus-NATIVE delta."""
    mean = deltas[list(ids)].mean(axis=1)
    return {"n_ids": len(ids), "improved_ids": int(sum(results[i]["delta_4bps"] > 0 for i in ids)),
            "pw_mean_delta": analytics.pw_mean_ci(mean.to_numpy()), "cum_mean_delta_4bps": float(mean.sum())}


def catalog_gate(k01_pass: bool, deltas: pd.DataFrame, ids, results: dict, full_scope: bool) -> dict:
    """Second research gate, evaluated only after K01 passes (pass_criteria.hierarchy)."""
    if not k01_pass:
        return {"evaluated": False, "pass": None, "reason": "K01 primary did not pass (pass_criteria.hierarchy)"}
    out = aggregate(deltas, ids, results)
    return {"evaluated": True, **out,
            "pass": bool(full_scope and out["improved_ids"] >= 15 and out["pw_mean_delta"]["lower"] > 0)}


def evaluate(results: dict, ok: list[str], deltas: pd.DataFrame, full_scope: bool) -> dict:
    """K01 primary, then catalog, then the atomic-only diagnostic, for one policy (base or V3)."""
    out = {}
    if "K01" in ok:
        out["K01_primary"] = k01_gates(results["K01"])
    out["catalog_secondary"] = catalog_gate(out.get("K01_primary", {}).get("pass", False), deltas, ok, results,
                                            full_scope)
    atomic = [i for i in ATOMIC if i in ok]
    out["atomic_only_diagnostic"] = {**aggregate(deltas, atomic, results), "gate": False} if atomic else None
    return out


def trials(ids) -> tuple[int, int]:
    """(candidate series, V3 ablation series) of a run scope: the freeze's 87 + 29, or 3 + 1 for the flip run."""
    scope = FLIP_IDS if tuple(ids) == FLIP_IDS else INCLUDED
    return len(scope) * len(K_VALUES), len(scope)


def parse_scope(argv=None):
    """CLI -> (args, windows, full_scope). --flip runs FLIP_IDS only into FLIP_OUT, unregistered unless --register."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="*", default=None)
    parser.add_argument("--windows", nargs="*", default=[w.name for w in rolling.WINDOWS])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", default=None)
    parser.add_argument("--no-register", action="store_true", help="smoke runs: do not append to the trial registry")
    parser.add_argument("--experiment", default=None)
    parser.add_argument("--flip", action="store_true", help="C1_FLIP_AX: K01_FLIP only, into r2_52a_flip/")
    parser.add_argument("--register", action="store_true", help="--flip only: append the flip run to the registry")
    args = parser.parse_args(argv)
    if args.flip:
        if args.ids is not None or (args.out is not None and Path(args.out).resolve() == OUT.resolve()):
            raise SystemExit("--flip fixes its ids (K01_FLIP) and may not write the frozen r2_52a folder")
        args.ids, args.out, args.no_register = list(FLIP_IDS), args.out or str(FLIP_OUT), not args.register
        args.experiment = args.experiment or "R2-52A adaptive exit rolling C1_FLIP_AX (K01_FLIP)"
    elif args.register:
        raise SystemExit("--register is only for --flip")
    args.ids = list(INCLUDED) if args.ids is None else args.ids
    args.out = args.out or str(OUT)
    args.experiment = args.experiment or "R2-52A adaptive exit rolling"
    scope = FLIP_IDS if args.flip else INCLUDED
    unknown = sorted(set(args.ids) - set(scope))
    names = [w.name for w in rolling.WINDOWS]
    picked = sorted(names.index(n) for n in args.windows)
    if unknown or picked != list(range(picked[0], picked[-1] + 1)):
        raise SystemExit(f"ids outside the freeze scope {unknown} or non-contiguous windows {args.windows}")
    windows = [rolling.WINDOWS[i] for i in picked]
    full_scope = tuple(args.ids) == scope and len(windows) == len(rolling.WINDOWS)
    if not full_scope and not args.no_register:
        raise SystemExit("a subset run is a smoke run: pass --no-register")
    return args, windows, full_scope


def main() -> None:
    args, windows, full_scope = parse_scope()
    n_trials, n_trials_v3 = trials(args.ids)
    end = windows[-1].test_end
    if end > rolling.END:
        raise SystemExit("end after 2026-01-01: 2026H1 is untouched (freeze data_cutoff)")
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    predictions = data.load_predictions(end=end)
    coverage = data.prediction_coverage(predictions, rolling.TRAIN_START, end)
    if coverage["retrain_after_timestamp"] or set(coverage["missing_days"]) - plan2.KNOWN_PREDICTION_GAPS:
        raise SystemExit(f"prediction availability check failed: {coverage}")
    prior = registry.cumulative_trials(REGISTRY)
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "source": "scripts/sim_adaptive_exit.py",
                "freeze": str(FREEZE_PATH.relative_to(ROOT)), "freeze_sha256": provenance.file_sha256(FREEZE_PATH),
                "experiment": FREEZE["experiment"], "frozen_hypothesis": FREEZE["pass_criteria"],
                "ablation_V3": FREEZE["ablation_V3"], "data_cutoff": FREEZE["data_cutoff"], "full_scope": full_scope,
                "simulation": {"exit_policy": "R2_52A", "k_values": list(K_VALUES), "costs": FREEZE["costs"],
                               "test_start": windows[0].test_start, "test_end": end,
                               "selection": FREEZE["selection"], "comparator": "BASE NONE/NATIVE, same test calendar"},
                "included_ids": list(FLIP_IDS if args.flip else INCLUDED), "ids_run": args.ids,
                "windows": [w.name for w in windows],
                "input_sha256": plan2.input_hashes(end), "prediction_coverage": coverage,
                "n_trials": n_trials + n_trials_v3, "n_trials_split": {"r2_52a": n_trials, "v3_ablation": n_trials_v3},
                "prior_trials_registry": prior, "cumulative_trials": prior + n_trials + n_trials_v3,
                "n_trials_rule": FREEZE["trials"],
                "paper_records": "effective_switch_time, retired_books snapshot, AX config hash and retired-table hashes "
                                 "are recorded by the paper rollout (Task D); this research run touches no paper table"}
    if args.flip:
        manifest["flip"] = {"paper_book": "C1_FLIP_AX", "registered": not args.no_register,
                            "design": "Codex 2026-10-09, user-approved: C1_FLIP = F3 side *= -1 + E1; R2-52A F3 state "
                                      "exit mirrored (long <= q50, short >= q50); E1 one-shot anchor unchanged; k per "
                                      "window by select_k (4 bps validation P&L, tie -> 2.0)",
                            "note": "post-freeze id outside the frozen 29-id scope; frozen_hypothesis above is the "
                                    "R2-52A text, not a pre-registered K01_FLIP gate"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    with ProcessPoolExecutor(max_workers=min(args.workers, 8), initializer=_init, initargs=(str(end),)) as pool:
        rows = list(pool.map(run_id, args.ids, [args.windows] * len(args.ids), [str(out)] * len(args.ids)))
    results = {r["id"]: r for r in rows}
    failed = [r for r in rows if r["status"] != "ok"]
    ok = [i for i in args.ids if results[i]["status"] == "ok"]
    pd.DataFrame([s for i in ok for s in results[i]["selection"]]).to_csv(out / "selected_k.csv", index=False)
    frames = {i: pd.read_parquet(out / "daily" / f"{i}.parquet") for i in ok}
    deltas = pd.DataFrame({i: f.ax_4bps - f.native_4bps for i, f in frames.items()})
    deltas_v3 = pd.DataFrame({i: f.v3_4bps - f.native_4bps for i, f in frames.items()})
    report = {"valid_run": full_scope and not failed, "failed_ids": [{k: r[k] for k in ("id", "error")} for r in failed],
              "pw_label": f"per-id pw_delta: {PW_LABEL}; Holm not computed (no p-value helper in analytics)",
              "diagnostics": {"runtime_seconds": {"value": round(time.time() - started, 1)}},
              "strategies": [{k: v for k, v in results[i].items() if k not in ("selection", "carried", "v3")}
                             for i in ok]}
    if not failed and ok:
        report.update(evaluate(results, ok, deltas, full_scope))
        v3 = {i: results[i]["v3"] for i in ok}
        report["v3_ablation"] = {"scope": "separate pre-registered ablation; does not gate the base R2-52A switch",
                                 **evaluate(v3, ok, deltas_v3, full_scope),
                                 "per_id": [{"id": i, **v3[i]} for i in ok]}
    guard.check(report)
    (out / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    manifest.update({"selected_k": {i: {s["window"]: s["k"] for s in results[i]["selection"]} for i in ok},
                     "carried_positions": {i: results[i]["carried"] for i in ok},
                     "failed_ids": report["failed_ids"], "valid_run": report["valid_run"]})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    if not args.no_register:
        config = {k: str(v) for k, v in manifest["simulation"].items()}
        registry.record(REGISTRY, {"experiment": args.experiment, "n_trials": n_trials, "config": config,
                                   "input_hashes": manifest["input_sha256"],
                                   "result_summary": {"valid_run": report["valid_run"],
                                                      "K01_pass": report.get("K01_primary", {}).get("pass"),
                                                      "catalog_pass": report.get("catalog_secondary", {}).get("pass")}})
        v3 = report.get("v3_ablation", {})
        registry.record(REGISTRY, {"experiment": f"{args.experiment} V3 ablation", "n_trials": n_trials_v3,
                                   "config": {**config, "ablation_V3": FREEZE["ablation_V3"]},
                                   "input_hashes": manifest["input_sha256"],
                                   "result_summary": {"valid_run": report["valid_run"],
                                                      "K01_pass": v3.get("K01_primary", {}).get("pass"),
                                                      "catalog_pass": v3.get("catalog_secondary", {}).get("pass")}})
    print(json.dumps({"valid_run": report["valid_run"], "failed": [r["id"] for r in failed],
                      "K01_primary": report.get("K01_primary"), "catalog": report.get("catalog_secondary"),
                      "v3_K01": report.get("v3_ablation", {}).get("K01_primary"),
                      "runtime_seconds": report["diagnostics"]["runtime_seconds"]["value"]}, indent=1, default=str))


if __name__ == "__main__":
    main()
