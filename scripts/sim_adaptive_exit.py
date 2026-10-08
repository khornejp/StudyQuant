"""R2-52A research run (frozen spec out/k45_rl_r2_48_20261007/r2_52a_exit_freeze.json): adaptive exits
(SimConfig.exit_policy="R2_52A") on the NONE/NATIVE signal table of each included id, k in {1.0, 1.5, 2.0} selected on
each rolling validation window (tie -> 2.0), one continuous stitched test, paired daily PW versus BASE NONE/NATIVE.
Usage: python scripts/sim_adaptive_exit.py [--ids K01 ...] [--windows W01 ...] [--workers 8] [--out DIR] [--no-register]
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
N_TRIALS = len(INCLUDED) * len(K_VALUES)       # freeze trials: 29 x 3 = 87 (V3 ablation, +29, is a separate run)
OUT = O / "r2_52a"
REGISTRY = ROOT / "out/sim_registry.jsonl"
CONFIG = SimConfig(exit_policy="R2_52A")       # strict, NATIVE rows, 4 bps round trip, PESS funding, delay 1
_CTX: Context | None = None


def select_k(scores: dict[float, float]) -> float:
    """Best validation P&L; ties go to the candidate nearest 2.0 (the largest k)."""
    return max(scores, key=lambda k: (scores[k], k))


def _valid_e(frame: pd.DataFrame, head: str) -> pd.DataFrame:
    column = f"prediction_exc_{head}"
    v = frame[column].to_numpy(float)
    return frame.loc[np.isfinite(v) & (v > 0), ["timestamp", column]]


def e_at(frame: pd.DataFrame, times: pd.DatetimeIndex, head: str) -> np.ndarray:
    """Latest finite >0 E with available_at (= timestamp, research convention) <= t and age <= 24 h."""
    return regime._asof(_valid_e(frame, head), times, f"prediction_exc_{head}", regime.E_MAX_AGE)


def e_series(frame: pd.DataFrame, minute_times: pd.DatetimeIndex, head: str) -> tuple[np.ndarray, np.ndarray]:
    """core.simulate e_bps / e_min_bps: e = latest valid E as of open(m); e_min = min of the valid E that became
    available in (open(m-1), open(m)] (each E goes to the first minute whose open >= its timestamp)."""
    valid = _valid_e(frame, head)
    t = pd.DatetimeIndex(minute_times).as_unit("ns").asi8
    e_t = pd.DatetimeIndex(valid.timestamp).as_unit("ns").asi8
    values = valid[f"prediction_exc_{head}"].to_numpy(float)
    idx = np.searchsorted(t, e_t, side="left")
    keep = idx < len(t)
    keep[keep] = t[idx[keep]] - e_t[keep] <= regime.E_MAX_AGE.value      # a data gap must not revive old E
    e_min = np.full(len(t), np.nan)
    np.fmin.at(e_min, idx[keep], values[keep])
    return e_at(frame, minute_times, head), e_min


def legacy_heads() -> dict[int, str]:
    """Composite component -> its E head (R2-46 E_COLUMN); only the opening component supplies E0."""
    return {legacy.FAST[name][0]: legacy.E_HEAD[name] for name in legacy.FAST}


def row_e0(table: pd.DataFrame, regime_frame: pd.DataFrame, spec_id: str) -> np.ndarray:
    """E0 for market entries: E known at the decision time T of each row."""
    spec = CATALOG[spec_id]
    times = pd.DatetimeIndex(table.decision_time)
    if spec.family != "composite":
        return e_at(regime_frame, times, spec.e_head)
    heads = table.component.map(legacy_heads())
    out = np.full(len(table), np.nan)
    for head in heads.dropna().unique():
        rows = (heads == head).to_numpy()
        out[rows] = e_at(regime_frame, times[rows], head)
    return out


def assign_k(table: pd.DataFrame, picks: dict[str, float], windows, delay_min: int = CONFIG.delay_min) -> pd.DataFrame:
    """Each row takes the k selected for the test window its execution minute falls in; a position keeps the k of
    the row that opened it (core reads k at the fill), so a boundary never changes an open position."""
    executes = pd.DatetimeIndex(table.decision_time) + pd.Timedelta(minutes=delay_min)
    k = np.full(len(table), np.nan)
    for w in windows:
        k[(executes >= w.test_start) & (executes < w.test_end)] = picks[w.name]
    return table.assign(k=k)


def run_ax(table, minutes, e, e_min, a, b, config):
    """R2_52A from a flat position at a (earlier rows are only indicator warm-up already inside the table)."""
    inside = ((minutes.open_time >= a) & (minutes.open_time < b)).to_numpy()
    return core.simulate(table, minutes.loc[inside].reset_index(drop=True), a, b, config,
                         e_bps=e[inside], e_min_bps=e_min[inside])


def validation_pnl(table, minutes, e, e_min, a, b, config) -> float:
    """Minute-ledger P&L on [a, b); an open position is marked to the last close without an exit fee and pays the
    settlements it held through."""
    result = run_ax(table, minutes, e, e_min, a, b, replace(config, close_at_end=False))
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


def _init(end: str) -> None:
    global _CTX
    _CTX = Context.load(end=pd.Timestamp(end))


def run_id(spec_id: str, names: list[str], out_dir: str) -> dict:
    try:
        ctx, spec = _CTX, CATALOG[spec_id]
        windows = [w for w in rolling.WINDOWS if w.name in names]
        table, _ = build_variant(ctx, spec_id, False, "NATIVE", ax=True)
        table = table.assign(e0_bps=row_e0(table, ctx.regime, spec_id))
        minutes = ctx.minutes
        e, e_min = e_series(ctx.regime, pd.DatetimeIndex(minutes.open_time), spec.e_head)
        picks, selection = {}, []
        for w in windows:
            scores = {k: validation_pnl(table.assign(k=k), minutes, e, e_min, w.val_start, w.val_end, CONFIG)
                      for k in K_VALUES}
            picks[w.name] = select_k(scores)
            selection.append({"id": spec_id, "window": w.name, "val_start": w.val_start, "val_end": w.val_end,
                              **{f"val_net_4bps_k{k}": v for k, v in scores.items()}, "k": picks[w.name]})
        a, b = windows[0].test_start, windows[-1].test_end
        stitched = assign_k(table, picks, windows)
        final = replace(CONFIG, close_at_end=True)       # data end: administrative close, flagged data_end
        ax4 = run_ax(stitched, minutes, e, e_min, a, b, final)
        ax8 = run_ax(stitched, minutes, e, e_min, a, b, replace(final, fee_per_side=4.0))   # same k, no reselection
        native, native_config = build_variant(ctx, spec_id, False, "NATIVE")
        inside = ((minutes.open_time >= a) & (minutes.open_time < b)).to_numpy()
        test_minutes = minutes.loc[inside].reset_index(drop=True)
        nat4 = core.simulate(native, test_minutes, a, b, replace(native_config, close_at_end=True))
        nat8 = core.simulate(native, test_minutes, a, b, replace(native_config, close_at_end=True, fee_per_side=4.0))
        days = pd.date_range(a, b, freq="D", inclusive="left")
        frame = pd.DataFrame({"ax_4bps": daily(ax4.minute_pnl, days), "native_4bps": daily(nat4.minute_pnl, days),
                              "ax_8bps": daily(ax8.minute_pnl, days), "native_8bps": daily(nat8.minute_pnl, days)})
        for name, value in (("daily", frame), ("trades_ax", ax4.trades), ("trades_native", nat4.trades)):
            Path(out_dir, name).mkdir(parents=True, exist_ok=True)
            value.to_parquet(Path(out_dir, name, f"{spec_id}.parquet"))
        executes = pd.DatetimeIndex(table.decision_time) + pd.Timedelta(minutes=CONFIG.delay_min)
        wants = ((table.side != 0) & table.allow_entry & (table.entry == "market") & (executes >= a)
                 & (executes < b)).to_numpy()
        d4 = frame.ax_4bps - frame.native_4bps
        trade_n = int(plan2.positions(ax4.trades).shape[0])
        return {"id": spec_id, "status": "ok", "selection": selection, "carried": carried(ax4.trades, windows),
                "trade_n": trade_n, "native_trade_n": int(plan2.positions(nat4.trades).shape[0]),
                "zero_reason": None if trade_n else "no R2-52A positions in the stitched test",
                "data_end_closes": int((ax4.trades.exit_reason == "data_end").sum()),
                "exit_reasons": ax4.trades.exit_reason.value_counts().to_dict(),
                "no_entry_e_market_rows": int((wants & ~(np.isfinite(table.e0_bps.to_numpy()) &
                                                         (table.e0_bps.to_numpy() > 0))).sum()),
                "ax_net_4bps": float(frame.ax_4bps.sum()), "native_net_4bps": float(frame.native_4bps.sum()),
                "delta_4bps": float(d4.sum()), "delta_8bps": float((frame.ax_8bps - frame.native_8bps).sum()),
                "pw_delta": analytics.pw_mean_ci(d4.to_numpy()),
                "worst_position_bps": _worst(ax4.trades), "native_worst_position_bps": _worst(nat4.trades),
                "max_drawdown_bps": _drawdown(frame.ax_4bps), "native_max_drawdown_bps": _drawdown(frame.native_4bps)}
    except Exception as error:      # a failed id invalidates the run (pass_criteria.catalog); never dropped
        return {"id": spec_id, "status": "error", "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(limit=5)}


def k01_gates(r: dict) -> dict:
    worst, native_worst = r["worst_position_bps"], r["native_worst_position_bps"]
    gates = {"pw_lower_gt_0": r["pw_delta"]["lower"] > 0, "delta_8bps_ge_0": r["delta_8bps"] >= 0,
             "worst_position_ge_native": worst is not None and native_worst is not None and worst >= native_worst,
             "max_drawdown_le_native": r["max_drawdown_bps"] <= r["native_max_drawdown_bps"]}
    return {**gates, "pass": all(gates.values())}


def aggregate(deltas: pd.DataFrame, ids, results: dict) -> dict:
    """Equal-weight (1/len(ids)) mean of each id's zero-filled daily adaptive-minus-NATIVE delta."""
    mean = deltas[list(ids)].mean(axis=1)
    return {"n_ids": len(ids), "improved_ids": int(sum(results[i]["delta_4bps"] > 0 for i in ids)),
            "pw_mean_delta": analytics.pw_mean_ci(mean.to_numpy()), "cum_mean_delta_4bps": float(mean.sum())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="*", default=list(INCLUDED))
    parser.add_argument("--windows", nargs="*", default=[w.name for w in rolling.WINDOWS])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--no-register", action="store_true", help="smoke runs: do not append to the trial registry")
    parser.add_argument("--experiment", default="R2-52A adaptive exit rolling")
    args = parser.parse_args()
    unknown = sorted(set(args.ids) - set(INCLUDED))
    names = [w.name for w in rolling.WINDOWS]
    picked = sorted(names.index(n) for n in args.windows)
    if unknown or picked != list(range(picked[0], picked[-1] + 1)):
        raise SystemExit(f"ids outside the freeze scope {unknown} or non-contiguous windows {args.windows}")
    windows = [rolling.WINDOWS[i] for i in picked]
    full_scope = tuple(args.ids) == INCLUDED and len(windows) == len(rolling.WINDOWS)
    if not full_scope and not args.no_register:
        raise SystemExit("a subset run is a smoke run: pass --no-register")
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
                "data_cutoff": FREEZE["data_cutoff"], "full_scope": full_scope,
                "simulation": {"exit_policy": "R2_52A", "k_values": list(K_VALUES), "costs": FREEZE["costs"],
                               "test_start": windows[0].test_start, "test_end": end,
                               "selection": FREEZE["selection"], "comparator": "BASE NONE/NATIVE, same test calendar"},
                "included_ids": list(INCLUDED), "ids_run": args.ids, "windows": [w.name for w in windows],
                "input_sha256": plan2.input_hashes(end), "prediction_coverage": coverage,
                "n_trials": N_TRIALS, "prior_trials_registry": prior, "cumulative_trials": prior + N_TRIALS,
                "n_trials_rule": FREEZE["trials"],
                "paper_records": "effective_switch_time, retired_books snapshot, AX config hash and retired-table hashes "
                                 "are recorded by the paper rollout (Task D); this research run touches no paper table"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    with ProcessPoolExecutor(max_workers=min(args.workers, 8), initializer=_init, initargs=(str(end),)) as pool:
        rows = list(pool.map(run_id, args.ids, [args.windows] * len(args.ids), [str(out)] * len(args.ids)))
    results = {r["id"]: r for r in rows}
    failed = [r for r in rows if r["status"] != "ok"]
    ok = [i for i in args.ids if results[i]["status"] == "ok"]
    selection = pd.DataFrame([s for i in ok for s in results[i]["selection"]])
    selection.to_csv(out / "selected_k.csv", index=False)
    deltas = pd.DataFrame({i: (lambda f: f.ax_4bps - f.native_4bps)(pd.read_parquet(out / "daily" / f"{i}.parquet"))
                           for i in ok})
    report = {"valid_run": full_scope and not failed, "failed_ids": [{k: r[k] for k in ("id", "error")} for r in failed],
              "diagnostics": {"runtime_seconds": {"value": round(time.time() - started, 1)}},
              "strategies": [{k: v for k, v in results[i].items() if k not in ("selection", "carried")} for i in ok]}
    if "K01" in ok:
        report["K01_primary"] = {**k01_gates(results["K01"]), "delta_4bps": results["K01"]["delta_4bps"],
                                 "delta_8bps": results["K01"]["delta_8bps"], "pw_delta": results["K01"]["pw_delta"]}
    if not failed and ok:
        catalog = aggregate(deltas, ok, results)
        catalog["pass"] = (full_scope and catalog["improved_ids"] >= 15 and catalog["pw_mean_delta"]["lower"] > 0)
        catalog["evaluated"] = "only after K01 passes (pass_criteria.hierarchy)"
        report["catalog_secondary"] = catalog
        atomic = [i for i in ATOMIC if i in ok]
        report["atomic_only_diagnostic"] = {**aggregate(deltas, atomic, results), "gate": False} if atomic else None
    guard.check(report)
    (out / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    manifest.update({"selected_k": {i: {s["window"]: s["k"] for s in results[i]["selection"]} for i in ok},
                     "carried_positions": {i: results[i]["carried"] for i in ok},
                     "failed_ids": report["failed_ids"], "valid_run": report["valid_run"]})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    if not args.no_register:
        registry.record(REGISTRY, {"experiment": args.experiment, "n_trials": N_TRIALS,
                                   "config": {k: str(v) for k, v in manifest["simulation"].items()},
                                   "input_hashes": manifest["input_sha256"],
                                   "result_summary": {"valid_run": report["valid_run"],
                                                      "K01_pass": report.get("K01_primary", {}).get("pass"),
                                                      "catalog_pass": report.get("catalog_secondary", {}).get("pass"),
                                                      "v3_ablation": "not run (+29 trials when run)"}})
    print(json.dumps({"valid_run": report["valid_run"], "failed": [r["id"] for r in failed],
                      "K01_primary": report.get("K01_primary"), "catalog": report.get("catalog_secondary"),
                      "runtime_seconds": report["diagnostics"]["runtime_seconds"]["value"]}, indent=1, default=str))


if __name__ == "__main__":
    main()
