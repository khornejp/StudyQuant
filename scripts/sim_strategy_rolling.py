"""Plan 2 runner: every catalog combination on the sim engine, sliced into the spec §5 rolling windows,
plus comparison baseline 2 (validation-window best applied to the next test window).
Usage: python scripts/sim_strategy_rolling.py [--ids K04 K09] [--end 2026-01-01] [--workers 8] [--out DIR]
"""
from __future__ import annotations
import argparse, json, sys, time, traceback
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dataclasses import replace  # noqa: E402
from btcusdt_quant.sim import analytics, core, costs, data, guard, provenance, registry, rolling  # noqa: E402
from btcusdt_quant.sim.reference import SimConfig  # noqa: E402
from btcusdt_quant.sim.strategies import CATALOG, Context, build_variant, grid  # noqa: E402

START = rolling.TRAIN_START
OUT = ROOT / "out/k45_rl_r2_48_20261007/strategies"
REGISTRY = ROOT / "out/sim_registry.jsonl"
COSTS = (0.0, 4.0, 8.0, 12.0)
BASE_TRIALS = 5125          # cumulative trials before R2-48 (spec / R2-47 revision 2); frozen, not read from the registry
KNOWN_PREDICTION_GAPS = {"2023-12-31", "2025-12-31"}     # last day of each stage-1 segment (spec §1)
HYPOTHESIS = ("강화학습 정책이 롤링 테스트에서 C1_X·단일 기법 최고·지도학습 정책보다 비용 차감 후 우위 "
              "(Plan 2: 기법 카탈로그 전 조합의 롤링 결과와 비교 기준 ② 산출)")
_CTX: Context | None = None


def combinations(ids) -> list[tuple[str, str, str]]:
    out = []
    for spec_id in ids:
        spec = CATALOG[spec_id]
        for gate in ("NONE", "GATED") if spec.gate is not None else ("NONE",):
            for style in ("NATIVE", "DETEXIT"):
                out.append((spec_id, gate, style))
    return out


def combo_name(combo) -> str:
    return "__".join(combo)


def _init(end: str) -> None:
    global _CTX
    _CTX = Context.load(end=pd.Timestamp(end))


def run_combo(combo, out_dir: str, end: str) -> dict:
    spec_id, gate, style = combo
    name = combo_name(combo)
    try:
        ctx = _CTX
        spec = CATALOG[spec_id]
        end_t = pd.Timestamp(end)
        if spec.simulator == "grid":
            if style == "DETEXIT":
                return {"combo": name, "status": "skipped", "zero_reason": "DETEXIT not defined for GRID"}
            minutes = ctx.minutes.loc[ctx.minutes.open_time >= START].reset_index(drop=True)
            result = grid.simulate_grid(Context(minutes=minutes, metrics=ctx.metrics, premium=ctx.premium,
                                                funding=ctx.funding, regime=ctx.regime, end=ctx.end, _bars=ctx._bars),
                                        START, end_t, gate == "GATED", SimConfig(close_at_end=True))
        else:
            table, config = build_variant(ctx, spec_id, gate == "GATED", style)
            minutes = ctx.minutes.loc[ctx.minutes.open_time >= START].reset_index(drop=True)
            result = core.simulate(table, minutes, START, end_t, replace(config, close_at_end=True))
        trades = result.trades
        daily = result.minute_pnl.groupby(result.minute_pnl.index.floor("D")).sum().rename("net_bps").to_frame()
        Path(out_dir, "trades").mkdir(parents=True, exist_ok=True)
        Path(out_dir, "daily").mkdir(parents=True, exist_ok=True)
        trades.to_parquet(Path(out_dir, "trades", f"{name}.parquet"))
        daily.to_parquet(Path(out_dir, "daily", f"{name}.parquet"))
        return {"combo": name, "status": "ok", "trades": int(len(trades))}
    except Exception as error:  # keep going; every combination keeps a recorded status
        return {"combo": name, "status": "error", "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(limit=5)}


def _fill_units(trades: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp) -> float:
    if trades.empty:
        return 0.0
    entries = trades.units[(trades.entry_time >= a) & (trades.entry_time < b)].sum()
    exits = trades.units[(trades.exit_time >= a) & (trades.exit_time < b)].sum()
    return float(entries + exits)


def positions(trades: pd.DataFrame) -> pd.DataFrame:
    """One row per position (DETEXIT legs and partial exits merged): first entry, last exit, side, net."""
    if trades.empty:
        return pd.DataFrame(columns=["position_id", "entry_time", "exit_time", "side", "net_bps", "legs"])
    return trades.groupby("position_id", as_index=False).agg(
        entry_time=("entry_time", "min"), exit_time=("exit_time", "max"), side=("side", "first"),
        net_bps=("net_bps", "sum"), legs=("units", "size"))


def position_window_pnl(trades: pd.DataFrame, closes: pd.Series, a: pd.Timestamp, b: pd.Timestamp,
                        fee_per_side: float = 2.0, boundary: str = "PESS") -> pd.Series:
    """Each position's P&L inside [a, b) on the minute-ledger rules: marks close to close (entry/exit at fill
    prices), fees at the fill minutes, funding at settlement minutes."""
    if trades.empty:
        return pd.Series(dtype=float)
    legs = trades.loc[(trades.entry_time < b) & (trades.exit_time >= a)]
    out = {}
    before_a, before_b = closes.asof(a - pd.Timedelta(minutes=1)), closes.asof(b - pd.Timedelta(minutes=1))
    for leg in legs.itertuples(index=False):
        start = leg.entry_price if leg.entry_time >= a else before_a
        stop = leg.exit_price if leg.exit_time < b else before_b
        value = leg.side * np.log(stop / start) * 1e4 * leg.units
        value -= fee_per_side * leg.units * ((leg.entry_time >= a) + (leg.exit_time < b))
        value += sum(v for when, v in costs.funding_events(leg.side, leg.entry_time, leg.exit_time, boundary)
                     if a <= when < b) * leg.units
        out[leg.position_id] = out.get(leg.position_id, 0.0) + value
    return pd.Series(out, dtype=float)


def window_rows(name: str, daily: pd.Series, trades: pd.DataFrame, closes: pd.Series | None = None) -> list[dict]:
    """Per window part: net at 0/4/8/12 bps from the minute ledger (fees at fills), position counts, top-2
    positions removed (their in-window P&L), drawdown."""
    rows = []
    pos = positions(trades)
    for w in rolling.WINDOWS:
        for part, a, b in (("val", w.val_start, w.val_end), ("test", w.test_start, w.test_end)):
            d = daily.loc[(daily.index >= a) & (daily.index < b)]
            net4 = float(d.sum())
            units = _fill_units(trades, a, b)
            exited = pos.loc[(pos.exit_time >= a) & (pos.exit_time < b)] if len(pos) else pos
            inside = (position_window_pnl(trades, closes, a, b) if closes is not None and len(trades)
                      else pd.Series(dtype=float))
            row = {"combo": name, "window": w.name, "part": part, "start": a, "end": b,
                   "trades": int(len(exited)), "long": int((exited.side == 1).sum()) if len(exited) else 0,
                   "short": int((exited.side == -1).sum()) if len(exited) else 0,
                   "top2_removed_bps": net4 - float(inside.nlargest(2).sum()),
                   "max_drawdown_bps": float((d.cumsum().cummax().clip(lower=0) - d.cumsum()).max()) if len(d) else 0.0,
                   "zero_reason": None if units > 0 else "no trades in window"}
            for cost in COSTS:   # fee per unit per side = cost / 2; the ledger was booked at 4 bps
                row[f"net_{int(cost)}bps"] = net4 - (cost - 4.0) / 2 * units
            rows.append(row)
    return rows


def baseline2(windows: pd.DataFrame, daily: dict[str, pd.Series]) -> tuple[pd.DataFrame, pd.Series]:
    """For each window: the combination with the best validation net at 4 bps (ties: lowest name), and its test days."""
    picks, parts = [], []
    for w in rolling.WINDOWS:
        val = windows.loc[(windows.window == w.name) & (windows.part == "val")]
        best = val.sort_values(["net_4bps", "combo"], ascending=[False, True]).iloc[0]
        test = windows.loc[(windows.window == w.name) & (windows.part == "test") & (windows.combo == best.combo)].iloc[0]
        picks.append({"window": w.name, "combo": best.combo, "val_net_4bps": float(best.net_4bps),
                      "test_net_4bps": float(test.net_4bps), "test_start": w.test_start, "test_end": w.test_end})
        s = daily[best.combo]
        parts.append(s.loc[(s.index >= w.test_start) & (s.index < w.test_end)])
    return pd.DataFrame(picks), pd.concat(parts)


def summarize(name: str, daily: pd.Series, trades: pd.DataFrame, trial_sharpes: np.ndarray, n_trials: int) -> dict:
    a, b = rolling.WINDOWS[0].test_start, rolling.WINDOWS[-1].test_end
    d = daily.loc[(daily.index >= a) & (daily.index < b)]
    pos = positions(trades)
    inside = pos.loc[(pos.entry_time >= a) & (pos.entry_time < b)] if len(pos) else pos
    sample = inside.sample(min(10, len(inside)), random_state=0).sort_values("entry_time") if len(inside) else inside
    units = _fill_units(trades, a, b)
    return {"id": name, "trade_n": int(len(inside)), "long_n": int((inside.side == 1).sum()) if len(inside) else 0,
            "short_n": int((inside.side == -1).sum()) if len(inside) else 0,
            "zero_reason": None if len(inside) else "no trades in 2023-09..2025-12",
            "net_4bps": float(d.sum()), "net_8bps": float(d.sum() - 2.0 * units),
            "pw": analytics.pw_mean_ci(d.to_numpy()), "hac": analytics.hac_mean_ci(d.to_numpy()),
            "dsr": analytics.deflated_sharpe(d.to_numpy(), trial_sharpes, n_trials),
            "sample_trades": json.loads(sample.to_json(orient="records", date_format="iso")) if len(sample) else []}


def _files_hash(paths) -> str:
    import hashlib
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(Path(path).name.encode()); digest.update(provenance.file_sha256(path).encode())
    return digest.hexdigest()


def input_hashes(end: pd.Timestamp) -> dict:
    """Only inputs dated before the cutoff are hashed (the market parquet is one file; rows >= cutoff are not read)."""
    segments = [s for s, start in data.SEGMENT_STARTS.items() if pd.Timestamp(start, tz="UTC") < end]
    return {"market_file": provenance.file_sha256(data.MARKET_PATH),
            "market_note": "single parquet to 2026-06-30; load_minutes filters open_time < cutoff at read",
            "metrics_before_cutoff": _files_hash(data.archive_files(data.METRICS_DIR, end)),
            "premium_before_cutoff": _files_hash(data.archive_files(data.PREMIUM_DIR, end)),
            "funding": provenance.tree_sha256(ROOT / "artifacts/funding_2020_2026h1", "*")["sha256"],
            "predictions_segments": segments,
            "predictions": _files_hash([p for s in segments for p in (data.PREDICTIONS_DIR / s).glob("fold_*_predictions.parquet")]),
            "code": provenance.tree_sha256(ROOT / "btcusdt_quant/sim", "**/*.py")["sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="*", default=sorted(CATALOG))
    parser.add_argument("--end", default=str(rolling.END))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--no-register", action="store_true", help="smoke runs: do not append to the trial registry")
    parser.add_argument("--base-trials", type=int, default=BASE_TRIALS,
                        help="prior trials for DSR; follow-up runs add earlier R2-48 runs (R2-49: 5125 + 128)")
    parser.add_argument("--experiment", default="R2-48 plan2 strategy rolling")
    args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if pd.Timestamp(args.end) > rolling.END:
        raise SystemExit("end after 2026-01-01: 2026H1 is the one-shot final check")
    combos = combinations(args.ids)
    started = time.time()
    end_t = pd.Timestamp(args.end)
    predictions = data.load_predictions(end=end_t)                       # fail-closed checks (Codex #7)
    coverage = data.prediction_coverage(predictions, START, end_t)
    if coverage["retrain_after_timestamp"] or set(coverage["missing_days"]) - KNOWN_PREDICTION_GAPS:
        raise SystemExit(f"prediction availability check failed: {coverage}")
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "source": "scripts/sim_strategy_rolling.py",
                "spec": "docs/superpowers/specs/2026-10-07-rl-trading-design.md §3",
                "plan": "docs/superpowers/plans/2026-10-07-strategy-rolling.md", "data_cutoff": "2025-12-31",
                "simulation": {"start": str(START), "end": args.end, "cost_bps_round_trip": 4.0, "funding": "PESS",
                               "delay_min": 1},
                "frozen_hypothesis": HYPOTHESIS, "ids": args.ids, "combinations": [combo_name(c) for c in combos],
                "n_combinations": len(combos), "input_sha256": input_hashes(end_t),
                "prediction_coverage": {k: v for k, v in coverage.items()},
                "n_trials": args.base_trials + len(combos), "n_trials_rule": f"{args.base_trials} prior + this run's combinations"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    with ProcessPoolExecutor(max_workers=min(args.workers, 8), initializer=_init, initargs=(args.end,)) as pool:
        statuses = list(pool.map(run_combo, combos, [str(out)] * len(combos), [args.end] * len(combos)))
    status = pd.DataFrame(statuses)
    status.to_parquet(out / "combos.parquet")
    ok = status.loc[status.status == "ok", "combo"].tolist()
    daily = {n: pd.read_parquet(out / "daily" / f"{n}.parquet").net_bps for n in ok}
    trades = {n: pd.read_parquet(out / "trades" / f"{n}.parquet") for n in ok}
    closes = data.load_minutes(end=end_t).set_index("open_time").close
    windows = pd.DataFrame([r for n in ok for r in window_rows(n, daily[n], trades[n], closes)])
    windows.to_parquet(out / "windows.parquet")
    picks, concat = baseline2(windows, daily)
    picks.to_parquet(out / "baseline2.parquet")
    concat.rename("net_bps").to_frame().to_parquet(out / "baseline2_daily.parquet")
    a, b = rolling.WINDOWS[0].test_start, rolling.WINDOWS[-1].test_end
    sharpes = np.array([s.loc[(s.index >= a) & (s.index < b)].mean() / s.loc[(s.index >= a) & (s.index < b)].std(ddof=1)
                        for s in daily.values() if s.loc[(s.index >= a) & (s.index < b)].std(ddof=1) > 0])
    n_trials = args.base_trials + len(combos)
    manifest["trial_sharpes"] = {"n": int(len(sharpes)), "mean": float(sharpes.mean()), "var": float(sharpes.var(ddof=1)),
                                 "values_daily": [float(x) for x in sharpes]}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    strategies = [summarize(n, daily[n], trades[n], sharpes, n_trials) for n in ok]
    strategies += [{"id": r["combo"], "trade_n": 0, "zero_reason": r.get("zero_reason") or r.get("error")}
                   for r in statuses if r["status"] != "ok"]
    report = {"diagnostics": {"baseline2_test_net_4bps": {"value": float(concat.sum())},
                              "runtime_seconds": {"value": round(time.time() - started, 1)}},
              "strategies": strategies}
    guard.check(report)
    (out / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    if not args.no_register:
        registry.record(REGISTRY, {"experiment": args.experiment, "n_trials": len(combos),
                                   "config": manifest["simulation"], "input_hashes": manifest["input_sha256"],
                                   "result_summary": {"ok": len(ok), "baseline2_test_net_4bps": float(concat.sum())}})
    print(json.dumps({"combinations": len(combos), "ok": len(ok), "errors": int((status.status == "error").sum()),
                      "baseline2": picks[["window", "combo", "test_net_4bps"]].to_dict("records"),
                      "baseline2_test_net_4bps": float(concat.sum())}, indent=1, default=str))


if __name__ == "__main__":
    main()
