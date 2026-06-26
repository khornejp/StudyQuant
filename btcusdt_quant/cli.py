from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from . import backtest, data, dataset, exchange, features, governance, live, secrets, training


def run_demo(output: Path) -> dict[str, object]:
    candles = data.CanonicalTimelineBuilder().build(data.local_fixture())
    policy = data.GapContaminationGovernance()
    last = candles[-1]
    gap_decision = policy.decide("volume_trade_flow_features", last.gap_ratio_20, last.max_gap_run_120, live=True)

    ret = data.returns(candles)[-1]
    clip_result = features.FeatureClipper().clip({
        "return_1": ret,
        "volume_ratio": 250.0,
        "close_zscore_60": 12.0,
        "return_5_vol_adj": 11.0,
    })
    nan_class = features.NaNSourceClassifier().classify({"gap_flag": 1}, "volume")

    rate_limit = live.RateLimitManager(limit_per_minute=10)
    rate_limit.acquire("GET /fapi/v1/klines", 1)
    rate_action = rate_limit.observe_status(429)
    data_quality = governance.DataQualityGate().evaluate(0, 0.0, False)
    source_grade = governance.SourceGradeManager().grade("klines_1m", historical_backfill=True, local_archive_complete=True)
    slo_actions = governance.MonitoringSLOEngine().evaluate({"schema_violation_count": 0, "gap_ratio_20": 0.20})
    clock_action = governance.ClockDriftMonitor().action(10)
    adl_action = governance.ADLMonitor().action(2)
    rolling = features.RollingFeatureEngine().rolling_mean([1.0, 2.0, 3.0], 2)
    calibrator = features.CalibrationModule().select_method(40)
    splits = features.PurgedWalkForwardSplit().split(20, 5, 3, 3, 1)
    core_features = features.FeatureSelectionPipeline().core_features([["return_1", "rv"], ["return_1"], ["return_1", "basis"]])
    ci_lower, ci_upper = features.BootstrapCIEngine().ci95([-0.1, 0.0, 0.1])
    budget = features.OptunaBudgetProfiles().get("practical_start")
    promotion, promotion_reason = features.ChampionChallengerManager().can_promote(
        30, 100, -0.01, 0.01,
        sharpe=1.5,
        mdd=0.10,
        calmar=2.5,
        score_bin_ci=[(0.02, 0.08)],
        threshold_flip_rate=0.02,
        latency_p99_ms=50.0,
        psi=0.05,
    )
    approval_build = dataset.build_dataset()
    fitted_calibrator = features.CalibrationModule().fit([0.40, 0.45, 0.55, 0.60], [0, 0, 1, 1], positive_samples=2)
    fitted_calibration = fitted_calibrator.as_dict()
    calibration_convergence = fitted_calibration.get("convergence", {})
    bootstrap_report = features.BootstrapCIEngine().score_bin_ci([("demo", -0.01, 0), ("demo", 0.02, 1), ("demo", 0.01, 1)], n_iterations=100, seed=11)
    funding_blackout = live.FundingEventManager().blackout_active(3)
    ghost_action = live.GhostFillPrevention().safe_market_exit(active_exit_orders=1, position_qty=0.1, cancel_resolved=True)
    emergency_action = live.EmergencyCloseExecutor().close(priority=0, retries=0)

    guard = live.OneWayPositionGuard()
    can_enter, guard_reason = guard.can_enter(live.PositionState("BTCUSDT", 0.0), "BUY")
    sizing = live.PositionSizer().fixed_notional(
        entry_price=100000.0,
        account_balance_usdt=10000.0,
        trade_notional_ratio=0.05,
        leverage=1.0,
        min_qty=0.001,
        qty_step=0.001,
        max_notional_fraction=0.10,
    )
    exchange_adapter = create_exchange_adapter("mock")
    order = exchange_adapter.submit_order("BTCUSDT", "BUY", "LIMIT", sizing.quantity)

    enforcer = governance.PipelineStageEnforcer()
    for stage in governance.PIPELINE_STAGES:
        enforcer.complete(stage)

    run_summary = {
        "network_used": exchange_adapter.network_enabled,
        "orders_enabled": False,
        "mock_exchange_order_status": order.status,
        "canonical_rows": len(candles),
        "gap_flags": sum(candle.gap_flag for candle in candles),
        "gap_decision": gap_decision.action,
        "nan_class": nan_class,
        "rate_limit_action_after_429": rate_action,
        "data_quality_action": data_quality.action,
        "source_grade": source_grade["availability_grade"],
        "monitoring_gap_action": slo_actions["gap_ratio_20"],
        "clock_drift_action": clock_action,
        "adl_action": adl_action,
        "rolling_warmup_first": rolling[0],
        "calibration_method_low_sample": calibrator,
        "purged_split_count": len(splits),
        "core_features": core_features,
        "bootstrap_ci": [ci_lower, ci_upper],
        "optuna_practical_trials": budget["trials"],
        "challenger_promotion_allowed": promotion,
        "challenger_promotion_reason": promotion_reason,
        "funding_blackout_active": funding_blackout,
        "ghost_exit_action": ghost_action,
        "emergency_close_action": emergency_action,
        "fallback_gap_ratio_20_0_20": governance.fallback_action("gap_ratio_20", 0.20),
        "one_way_guard_allowed": can_enter,
        "one_way_guard_reason": guard_reason,
        "sizing_accepted": sizing.accepted,
        "order_id": order.order_id,
        "stages_completed": len(enforcer.completed),
        "clipped_features": clip_result.values,
    }
    clip_report: Sequence[Mapping[str, object]] = clip_result.report
    stage_rows: Sequence[Mapping[str, object]] = enforcer.manifest_rows()
    governance.ArtifactWriter(output).create_approval_package(
        run_summary,
        clip_report,
        stage_rows,
        dataset_build=approval_build,
        bootstrap_ci_report=bootstrap_report,
        calibration_config={
            "calibrator_type": fitted_calibration["method"],
            "regularization": "l2",
            "convergence_status": "converged" if isinstance(calibration_convergence, Mapping) and calibration_convergence.get("converged") else "not_converged",
            "iterations": calibration_convergence.get("iterations", 0) if isinstance(calibration_convergence, Mapping) else 0,
            "final_loss": calibration_convergence.get("final_loss", 0.0) if isinstance(calibration_convergence, Mapping) else 0.0,
        },
    )
    return run_summary


def run_train(
    output: Path,
    input_path: Path | None = None,
    model_family: str = "auto",
    cv_mode: str = "walk_forward",
    embargo_size: int = 0,
    n_groups: int = 5,
    test_group_count: int = 1,
    fallback_allowed: bool = True,
    model_params: Mapping[str, object] | None = None,
    feature_selection_enabled: bool = False,
    optuna_enabled: bool = False,
    optuna_trials: int = 0,
    optuna_budget_profile: str = "practical_start",
    champion_challenger_enabled: bool = False,
    external_sources: Mapping[str, object] | None = None,
    regime_aware: bool = False,
    min_regime_rows: int = 80,
    regime_detector_rv_percentile: float = 0.75,
    regime_detector_trend_percentile: float = 0.70,
    regime_detector_min_trend_abs: float = 0.00001,
    regime_detector_low_vol_trend_multiplier: float = 2.0,
    regime_detector_min_regime_run_bars: int = 3,
    feature_selection_target_min: int = 0,
    feature_selection_target_max: int = 0,
    ensemble_enabled: bool = False,
    ensemble_direction_family: str = "catboost",
    ensemble_profitability_family: str = "catboost",
    ensemble_meta_family: str = "catboost",
    multitask: bool = False,
    use_user_regime: bool = False,
    user_regime_file: str | None = None,
    training_start: str | None = None,
    training_end: str | None = None,
    test_start: str | None = None,
    test_end: str | None = None,
    only_build: bool = False,
) -> dict[str, object]:
    if multitask:
        model_family = "pytorch_multitask"
    training_start_dt: datetime | None = None
    if training_start is not None:
        training_start_dt = datetime.fromisoformat(training_start).replace(tzinfo=timezone.utc)
    training_end_dt: datetime | None = None
    if training_end is not None:
        training_end_dt = datetime.fromisoformat(training_end).replace(tzinfo=timezone.utc)
    test_start_dt: datetime | None = None
    if test_start is not None:
        test_start_dt = datetime.fromisoformat(test_start).replace(tzinfo=timezone.utc)
    test_end_dt: datetime | None = None
    if test_end is not None:
        test_end_dt = datetime.fromisoformat(test_end).replace(tzinfo=timezone.utc)
    config = training.TrainingConfig(
        cv_mode=cv_mode,
        embargo_size=embargo_size,
        n_groups=n_groups,
        test_group_count=test_group_count,
        model_family=model_family,
        model_params=dict(model_params or {}),
        fallback_allowed=fallback_allowed,
        feature_selection_enabled=feature_selection_enabled,
        optuna_enabled=optuna_enabled,
        optuna_trials=optuna_trials,
        optuna_budget_profile=optuna_budget_profile,
        champion_challenger_enabled=champion_challenger_enabled,
        regime_aware=regime_aware or use_user_regime,
        min_regime_rows=min_regime_rows,
        regime_detector_rv_percentile=regime_detector_rv_percentile,
        regime_detector_trend_percentile=regime_detector_trend_percentile,
        regime_detector_min_trend_abs=regime_detector_min_trend_abs,
        regime_detector_low_vol_trend_multiplier=regime_detector_low_vol_trend_multiplier,
        regime_detector_min_regime_run_bars=regime_detector_min_regime_run_bars,
        feature_selection_target_min=feature_selection_target_min,
        feature_selection_target_max=feature_selection_target_max,
        ensemble_enabled=ensemble_enabled,
        ensemble_direction_family=ensemble_direction_family,
        ensemble_profitability_family=ensemble_profitability_family,
        ensemble_meta_family=ensemble_meta_family,
        use_user_regime=use_user_regime,
        training_start=training_start_dt,
        training_end=training_end_dt,
        test_start=test_start_dt,
        test_end=test_end_dt,
        only_build=only_build,
    )
    user_regime_periods: Sequence[dataset.UserRegimePeriod] | None = None
    if user_regime_file is not None:
        user_regime_periods = dataset.load_user_regime_periods(Path(user_regime_file))
    archive_dir = None
    if input_path is not None and input_path.is_dir():
        archive_dir = input_path
        input_path = None
    result = training.run_training(input_path, output, config, archive_dir=archive_dir, external_sources=external_sources, user_regime_periods=user_regime_periods)
    summary = dict(result.run_summary)
    summary["requested_model_family"] = model_family
    return summary


def run_collect(output: Path, rows: int, allow_public_network: bool = False, format: str = "csv") -> dict[str, object]:
    result = dataset.collect_candles(output, rows=rows, allow_public_network=allow_public_network, format=format)
    return {
        "output_path": result.output_path.as_posix(),
        "source": result.source,
        "symbol": result.symbol,
        "interval": result.interval,
        "rows": result.rows,
        "network_used": result.network_used,
    }


def run_collect_archive(start: str, end: str, output: Path, checkpoint: Path | None = None, allow_public_network: bool = False, min_rows: int = 0) -> dict[str, object]:
    if not allow_public_network:
        raise RuntimeError("archive collection requires --allow-public-network")
    summary = dataset.BinanceArchiveDownloader().download_range(start, end, output, checkpoint)
    coverage = dataset.archive_date_coverage(output)
    raw_rows = coverage["raw_rows"]
    min_rows_passed = True
    if min_rows > 0 and raw_rows < min_rows:
        print(f"warning: archive raw_rows ({raw_rows}) below min_rows threshold ({min_rows})")
        min_rows_passed = False
    report = {
        "start_date": coverage["start_date"],
        "end_date": coverage["end_date"],
        "raw_rows": raw_rows,
        "canonical_rows": coverage["canonical_rows"],
        "missing_days": coverage["missing_days"],
        "min_rows_passed": min_rows_passed,
    }
    report_path = output / "data_expansion_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "output_dir": summary.output_dir.as_posix(),
        "checkpoint_file": summary.checkpoint_file.as_posix(),
        "start_date": summary.start_date,
        "end_date": summary.end_date,
        "total_days": summary.total_days,
        "downloaded_days": summary.downloaded_days,
        "failed_days": summary.failed_days,
        "last_completed_date": summary.last_completed_date,
        "downloaded_files": list(summary.downloaded_files),
        "failed_dates": list(summary.failed_dates),
        "coverage_report": report,
        "min_rows_passed": min_rows_passed,
    }


def create_exchange_adapter(
    exchange_name: str = "mock",
    allow_signed_network: bool = False,
    allow_prod: bool = False,
    approval_artifacts: Path | None = None,
    recv_window_ms: int = 5000,
) -> exchange.ExchangeAdapter:
    if exchange_name == "mock":
        return exchange.MockExchangeAdapter()
    if exchange_name == "binance-testnet":
        if not allow_signed_network:
            raise RuntimeError("binance-testnet requires --allow-signed-network")
        credentials = secrets.load_binance_credentials_from_env()
        return exchange.BinanceUsdMFuturesTestnetAdapter(
            credentials,
            allow_signed_network=allow_signed_network,
            recv_window_ms=recv_window_ms,
        )
    if exchange_name == "binance-prod":
        if not allow_prod or approval_artifacts is None:
            raise RuntimeError("binance-prod requires --allow-prod and --approval-artifacts")
        credentials = secrets.load_binance_credentials_from_env()
        return exchange.BinanceUsdMFuturesProdAdapter(
            credentials,
            environment="prod",
            allow_prod=allow_prod,
            approval_artifacts=approval_artifacts,
            allow_signed_network=allow_signed_network,
            recv_window_ms=recv_window_ms,
        )
    raise ValueError(f"unsupported exchange: {exchange_name}")


def run_live(
    output: Path,
    dry_run: bool = True,
    allow_public_network: bool = False,
    max_candles: int = 12,
    exchange_name: str = "mock",
    allow_signed_network: bool = False,
    allow_prod: bool = False,
    approval_artifacts: Path | None = None,
    recv_window_ms: int = 5000,
    model_artifact_path: Path | None = None,
    regime_aware: bool = False,
    strategy_profile: str = "balanced",
    soak_duration_hours: float = 0.0,
    soak_report_interval_minutes: float = 60.0,
) -> dict[str, object]:
    exchange_adapter = create_exchange_adapter(exchange_name, allow_signed_network, allow_prod, approval_artifacts, recv_window_ms)
    result = live.run_live(
        output,
        dry_run=dry_run,
        allow_public_network=allow_public_network,
        max_candles=max_candles,
        exchange_adapter=exchange_adapter,
        model_artifact_path=model_artifact_path,
        regime_aware=regime_aware,
        strategy_profile=strategy_profile,
        soak_duration_hours=soak_duration_hours,
        soak_report_interval_minutes=soak_report_interval_minutes,
    )
    summary = dict(result.summary)
    summary["exchange"] = exchange_name
    summary["signed_network_enabled"] = exchange_adapter.network_enabled
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe local BTCUSDT v7.18 scaffold")
    subparsers = parser.add_subparsers(dest="command")
    demo = subparsers.add_parser("demo", help="run deterministic local dry-run demo")
    demo.add_argument("--output", default="artifacts/demo", help="artifact output directory")
    collect = subparsers.add_parser("collect", help="collect local fixture candles or explicitly allowed public klines to CSV/Parquet")
    collect.add_argument("--output", default="artifacts/collected/btcusdt_1m.csv", help="CSV or Parquet output path")
    collect.add_argument("--rows", type=int, default=240, help="number of fixture rows or public klines to write")
    collect.add_argument("--allow-public-network", action="store_true", help="opt in to unsigned public Binance kline download")
    collect.add_argument("--format", choices=("csv", "parquet"), default="csv", help="output format (default: csv)")
    collect_archive = subparsers.add_parser("collect-archive", help="collect Binance data.binance.vision daily BTCUSDT 1m archives")
    collect_archive.add_argument("--start", required=True, help="inclusive start date YYYY-MM-DD")
    collect_archive.add_argument("--end", required=True, help="inclusive end date YYYY-MM-DD")
    collect_archive.add_argument("--output", default="artifacts/archive", help="archive output directory")
    collect_archive.add_argument("--checkpoint", default=None, help="optional checkpoint JSON path; defaults to output/checkpoint.json")
    collect_archive.add_argument("--allow-public-network", action="store_true", help="opt in to public Binance archive download")
    collect_archive.add_argument("--min-rows", type=int, default=0, help="minimum expected raw rows; warns if not met")
    train = subparsers.add_parser("train", help="run deterministic offline CSV/fixture training pipeline")
    train.add_argument("--output", default="artifacts/training", help="training artifact output directory")
    train.add_argument("--input", default=None, help="optional local CSV candles path; defaults to offline fixture")
    train.add_argument("--model-family", default="auto", help="model family selector; auto tries lightgbm/catboost/pytorch_multitask first if installed")
    train.add_argument("--cv-mode", choices=("walk_forward", "combinatorial_purged"), default="walk_forward", help="cross-validation splitter mode")
    train.add_argument("--embargo-size", type=int, default=0, help="bars to embargo after combinatorial test windows")
    train.add_argument("--n-groups", type=int, default=5, help="sequential groups for combinatorial purged CV")
    train.add_argument("--test-group-count", type=int, default=1, help="number of groups selected for each combinatorial test fold")
    train.add_argument("--no-model-fallback", action="store_true", help="disable optional model fallback and fail if the requested family is unavailable")
    train.add_argument("--feature-selection", action="store_true", help="enable 6-stage feature selection pipeline (Spearman, gain, permutation, SHAP, ablation, core set)")
    train.add_argument("--optuna", action="store_true", help="enable Optuna hyperparameter tuning for threshold and signal scale")
    train.add_argument("--optuna-trials", type=int, default=0, help="number of Optuna trials (0 uses budget profile default)")
    train.add_argument("--optuna-budget", default="practical_start", choices=("research_fast", "practical_start", "full_audit_budget"), help="Optuna budget profile")
    train.add_argument("--champion-challenger", action="store_true", help="enable champion-challenger promotion evaluation from fold test metrics")
    train.add_argument("--collect-external-sources", action="store_true", help="collect real F11/F12 external sources (funding rate, mark price) from Binance API for training")
    train.add_argument("--regime-aware", action="store_true", help="enable 2-Stage regime-aware training: separate models for high_volatility, trending, and ranging regimes")
    train.add_argument("--min-regime-rows", type=int, default=80, help="minimum rows required per regime to train a sub-model")
    train.add_argument("--regime-rv-percentile", type=float, default=0.75, help="realized volatility percentile threshold for high-vol regime detection")
    train.add_argument("--regime-trend-percentile", type=float, default=0.70, help="trend slope percentile threshold for trending regime detection")
    train.add_argument("--regime-min-trend-abs", type=float, default=0.00001, help="minimum absolute trend slope to qualify as trending")
    train.add_argument("--regime-low-vol-multiplier", type=float, default=2.0, help="multiplier for trend threshold in low-volatility periods")
    train.add_argument("--regime-min-run-bars", type=int, default=3, help="minimum consecutive bars to confirm a regime change")
    train.add_argument("--feature-selection-target-min", type=int, default=0, help="minimum number of features to select (0 disables lower bound)")
    train.add_argument("--feature-selection-target-max", type=int, default=0, help="maximum number of features to select (0 disables upper bound)")
    train.add_argument("--ensemble", action="store_true", help="enable stacking ensemble: train direction + profitability + meta model")
    train.add_argument("--ensemble-direction-family", default="catboost", help="base model family for direction prediction")
    train.add_argument("--ensemble-profitability-family", default="catboost", help="base model family for profitability prediction")
    train.add_argument("--ensemble-meta-family", default="catboost", choices=("catboost",), help="meta model family for final probability")
    train.add_argument("--use-user-regime", action="store_true", help="use user-specified trend periods instead of automatic RegimeDetector for regime-aware training")
    train.add_argument("--user-regime-file", default=None, help="path to JSON file with user-specified regime periods")
    train.add_argument("--training-start", default=None, help="start date for training data (ISO format, e.g., 2020-01-01); rows before this date are excluded after feature computation")
    train.add_argument("--training-end", default=None, help="end date for training data (ISO format, e.g., 2024-12-31); rows after this date are excluded from training")
    train.add_argument("--test-start", default=None, help="start date for test/validation period (ISO format, e.g., 2025-01-01); used for out-of-sample evaluation after training")
    train.add_argument("--test-end", default=None, help="end date for test/validation period (ISO format, e.g., 2025-06-30)")
    train.add_argument("--only-build", action="store_true", help="only compute features/labels, skip model training")
    train.add_argument("--multitask", action="store_true", help="use PyTorch multitask neural network as the model family (shorthand for --model-family pytorch_multitask)")
    train.add_argument("--long-threshold", type=float, default=0.55, help="minimum probability threshold for LONG entry signals")
    train.add_argument("--short-threshold", type=float, default=0.55, help="minimum probability threshold for SHORT entry signals")
    train.add_argument("--min-ev", type=float, default=0.0001, help="minimum expected value for entry signals (0.01%% = 0.0001)")
    train.add_argument("--tp-pct", type=float, default=0.0015, help="take profit percentage for triple-barrier labeling (0.15%% = 0.0015)")
    train.add_argument("--sl-pct", type=float, default=0.0010, help="stop loss percentage for triple-barrier labeling (0.10%% = 0.0010)")
    live_parser = subparsers.add_parser("live", help="run 1m kline WebSocket collection with gap repair")
    live_parser.add_argument("--output", default="artifacts/live", help="live artifact output directory")
    live_parser.add_argument("--dry-run", action="store_true", help="use deterministic fixture WebSocket and REST backfill")
    live_parser.add_argument("--allow-public-network", action="store_true", help="opt in to unsigned public Binance WebSocket and REST klines")
    live_parser.add_argument("--max-candles", type=int, default=12, help="maximum closed klines to process before returning")
    live_parser.add_argument("--exchange", choices=("mock", "binance-testnet", "binance-prod"), default="mock", help="exchange adapter for signed execution path")
    live_parser.add_argument("--allow-signed-network", action="store_true", help="opt in to signed Binance REST requests")
    live_parser.add_argument("--allow-prod", action="store_true", help="opt in to production exchange adapter after artifact approval")
    live_parser.add_argument("--approval-artifacts", default=None, help="approval artifact directory required for production")
    live_parser.add_argument("--recv-window-ms", type=int, default=5000, help="Binance signed request recvWindow in milliseconds")
    live_parser.add_argument("--model-artifact", default=None, help="path to trained model artifact JSON (e.g., artifacts/training/model.json) or regime-aware directory (e.g., artifacts/training_regime_50k)")
    live_parser.add_argument("--regime-aware", action="store_true", help="enable regime-aware inference: load multiple regime models and select by detected market regime")
    live_parser.add_argument("--strategy-profile", choices=live.STRATEGY_PROFILE_CHOICES, default="balanced", help="strategy profile for regime-aware signal thresholds and TP/SL pricing")
    live_parser.add_argument("--long-threshold", type=float, default=0.55, help="minimum probability threshold for LONG entry signals")
    live_parser.add_argument("--short-threshold", type=float, default=0.55, help="minimum probability threshold for SHORT entry signals")
    live_parser.add_argument("--min-ev", type=float, default=0.0001, help="minimum expected value for entry signals (0.01%% = 0.0001)")
    live_parser.add_argument("--soak-duration-hours", type=float, default=0.0, help="soak test duration in hours (0 = normal mode, >0 = soak mode)")
    live_parser.add_argument("--soak-report-interval-minutes", type=float, default=60.0, help="soak test periodic report interval in minutes")
    backtest_parser = subparsers.add_parser("backtest", help="run backtest on historical candles")
    backtest_parser.add_argument("--input", default=None, help="CSV candles path; defaults to fixture")
    backtest_parser.add_argument("--output", default="artifacts/backtest", help="backtest output directory")
    backtest_parser.add_argument("--model-artifact", default=None, help="trained model artifact JSON path or regime-aware directory")
    backtest_parser.add_argument("--user-regime-file", default=None, help="path to JSON file with user-specified regime periods for backtest")
    backtest_parser.add_argument("--backtest-start", default="2025-07-01", help="start date for backtest (ISO format, e.g., 2025-07-01); candles before this date are used for feature computation only")
    artifacts = subparsers.add_parser("artifacts", help="verify generated artifact hashes")
    artifacts.add_argument("--path", default="artifacts/demo", help="artifact directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "demo":
        output = Path(args.output)
        summary = run_demo(output)
        print("BTCUSDT v7.18 local dry-run complete")
        print(f"mock_exchange_order_status={summary['mock_exchange_order_status']}")
        print(f"network_used={summary['network_used']}")
        print(f"gap_decision={summary['gap_decision']}")
        print(f"nan_class={summary['nan_class']}")
        print(f"artifacts={output}")
        return 0
    if args.command == "collect":
        output = Path(args.output)
        try:
            summary = run_collect(output, args.rows, args.allow_public_network, args.format)
        except (OSError, RuntimeError, ValueError) as error:
            print(f"collect failed: {error}", file=sys.stderr)
            return 1
        print("BTCUSDT candle collection complete")
        print(f"source={summary['source']}")
        print(f"network_used={summary['network_used']}")
        print(f"rows={summary['rows']}")
        print(f"output={summary['output_path']}")
        return 0
    if args.command == "collect-archive":
        output = Path(args.output)
        checkpoint = Path(args.checkpoint) if args.checkpoint else None
        try:
            summary = run_collect_archive(args.start, args.end, output, checkpoint, args.allow_public_network, args.min_rows)
        except (OSError, RuntimeError, ValueError) as error:
            print(f"archive collection failed: {error}", file=sys.stderr)
            return 1
        print("BTCUSDT archive collection complete")
        print(f"downloaded={summary['downloaded_days']}/{summary['total_days']} days")
        print(f"failed={summary['failed_days']} days")
        print(f"last_completed_date={summary['last_completed_date']}")
        print(f"checkpoint={summary['checkpoint_file']}")
        print(f"output={summary['output_dir']}")
        if not summary["min_rows_passed"]:
            print(f"warning: min_rows not met (raw_rows={summary['coverage_report']['raw_rows']}, min_rows={args.min_rows})")
        return 0
    if args.command == "train":
        output = Path(args.output)
        input_path = Path(args.input) if args.input else None
        external_sources = None
        if args.collect_external_sources:
            if input_path is None:
                print("--collect-external-sources requires --input to specify candle data", file=sys.stderr)
                return 1
            print("Collecting external sources (funding rate, mark price) from Binance API...")
            candles = dataset.load_parquet_candles(input_path) if input_path.suffix.lower() == ".parquet" else dataset.load_csv_candles(input_path)
            collector = dataset.ExternalSourcesCollector(allow_network=True)
            external_sources = collector.build_external_sources_for_candles(candles)
            print(f"Collected external sources for {len(external_sources)} candles")
        try:
            summary = run_train(
                output, input_path, args.model_family, args.cv_mode, args.embargo_size, args.n_groups, args.test_group_count,
                not args.no_model_fallback,
                feature_selection_enabled=args.feature_selection,
                optuna_enabled=args.optuna,
                optuna_trials=args.optuna_trials,
                optuna_budget_profile=args.optuna_budget,
                champion_challenger_enabled=args.champion_challenger,
                external_sources=external_sources,
                regime_aware=args.regime_aware,
                min_regime_rows=args.min_regime_rows,
                regime_detector_rv_percentile=args.regime_rv_percentile,
                regime_detector_trend_percentile=args.regime_trend_percentile,
                regime_detector_min_trend_abs=args.regime_min_trend_abs,
                regime_detector_low_vol_trend_multiplier=args.regime_low_vol_multiplier,
                regime_detector_min_regime_run_bars=args.regime_min_run_bars,
                feature_selection_target_min=args.feature_selection_target_min,
                feature_selection_target_max=args.feature_selection_target_max,
                ensemble_enabled=args.ensemble,
                ensemble_direction_family=args.ensemble_direction_family,
                ensemble_profitability_family=args.ensemble_profitability_family,
                ensemble_meta_family=args.ensemble_meta_family,
                multitask=args.multitask,
                use_user_regime=args.use_user_regime,
                user_regime_file=args.user_regime_file,
                training_start=args.training_start,
                training_end=args.training_end,
                test_start=args.test_start,
                test_end=args.test_end,
                only_build=args.only_build,
            )
        except (OSError, RuntimeError, ValueError) as error:
            print(f"training failed: {error}", file=sys.stderr)
            return 1
        print("BTCUSDT offline training complete")
        print(f"network_used={summary.get('network_used', False)}")
        print(f"orders_enabled={summary.get('orders_enabled', False)}")
        print(f"labeled_rows={summary.get('labeled_rows', 0)}")
        print(f"fold_count={summary.get('fold_count', 0)}")
        print(f"mean_test_f1={summary.get('mean_test_f1', 0.0)}")
        print(f"artifacts={output}")
        return 0
    if args.command == "live":
        output = Path(args.output)
        try:
            approval_artifacts = Path(args.approval_artifacts) if args.approval_artifacts else None
            model_artifact_path = Path(args.model_artifact) if args.model_artifact else None
            summary = run_live(
                output,
                dry_run=args.dry_run,
                allow_public_network=args.allow_public_network,
                max_candles=args.max_candles,
                exchange_name=args.exchange,
                allow_signed_network=args.allow_signed_network,
                allow_prod=args.allow_prod,
                approval_artifacts=approval_artifacts,
                recv_window_ms=args.recv_window_ms,
                model_artifact_path=model_artifact_path,
                regime_aware=args.regime_aware,
                strategy_profile=args.strategy_profile,
                soak_duration_hours=args.soak_duration_hours,
                soak_report_interval_minutes=args.soak_report_interval_minutes,
            )
        except (OSError, RuntimeError, ValueError) as error:
            print(f"live failed: {error}", file=sys.stderr)
            return 1
        print("BTCUSDT live collection complete")
        print(f"dry_run={summary['dry_run']}")
        print(f"network_used={summary['network_used']}")
        print(f"exchange={summary['exchange']}")
        print(f"stream_desync_detected={summary['stream_desync_detected']}")
        print(f"backfilled_rows={summary['backfilled_rows']}")
        print(f"canonical_rows={summary['canonical_rows']}")
        print(f"signal={summary['signal']}")
        strategy_decision = summary.get("strategy_decision", {})
        if strategy_decision:
            print(f"strategy_profile={strategy_decision.get('profile')}")
        model_inference = summary.get("model_inference", {})
        if model_inference:
            print(f"model_loaded={model_inference.get('model_loaded')}")
            print(f"probability={model_inference.get('probability')}")
            print(f"regime={model_inference.get('regime')}")
            if model_inference.get("error"):
                print(f"model_error={model_inference.get('error')}")
        print(f"artifacts={output}")
        return 0
    if args.command == "backtest":
        output = Path(args.output)
        try:
            input_path = Path(args.input) if args.input else None
            if input_path is not None:
                if input_path.suffix.lower() == ".parquet":
                    candles = dataset.load_parquet_candles(input_path)
                else:
                    candles = dataset.load_csv_candles(input_path)
            else:
                candles = data.local_fixture()
            model = None
            models_by_regime: dict[str, object] | None = None
            user_regime_periods = None
            if args.user_regime_file:
                user_regime_periods = dataset.load_user_regime_periods(Path(args.user_regime_file))
            if args.model_artifact:
                model_path = Path(args.model_artifact)
                if model_path.is_file():
                    model = live.load_model_artifact(model_path)
                elif model_path.is_dir():
                    if (model_path / "regime_run_summary.json").is_file():
                        regime_bundle = live.load_regime_aware_models(model_path)
                        models_by_regime = regime_bundle.models if regime_bundle else None
                    elif (model_path / "model.json").is_file():
                        model = live.load_model_artifact(model_path / "model.json")
            strategies = {
                "balanced": live.strategy_for_regime(None, "balanced"),
                "conservative": live.strategy_for_regime(None, "conservative"),
                "aggressive": live.strategy_for_regime(None, "aggressive"),
            }
            comparison = backtest.compare_strategies(
                candles,
                model,
                strategies,
                models_by_regime=models_by_regime,
                user_regime_periods=user_regime_periods,
                default_regime=max(models_by_regime, key=lambda k: 1) if models_by_regime else None,
                start_date=args.backtest_start,
            )
            result = backtest.run_backtest(
                candles,
                model,
                strategies["balanced"],
                models_by_regime=models_by_regime,
                user_regime_periods=user_regime_periods,
                default_regime=max(models_by_regime, key=lambda k: 1) if models_by_regime else None,
                start_date=args.backtest_start,
            )
            summary = {
                "backtest": result.as_dict(),
                "strategy_comparison": comparison,
            }
            output.mkdir(parents=True, exist_ok=True)
            (output / "backtest_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print("BTCUSDT backtest complete")
            print(f"trades={result.trade_count}")
            print(f"total_return={result.total_return:.4f}")
            print(f"win_rate={result.win_rate:.4f}")
            print(f"best_strategy={comparison['best_strategy']}")
            print(f"artifacts={output}")
            return 0
        except (OSError, RuntimeError, ValueError) as error:
            print(f"backtest failed: {error}", file=sys.stderr)
            return 1
    if args.command == "artifacts":
        ok, errors = governance.verify_manifest(Path(args.path))
        if ok:
            print("artifact verification passed")
            return 0
        for error in errors:
            print(error)
        return 1
    parser.print_help()
    return 0
