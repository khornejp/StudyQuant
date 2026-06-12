from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Mapping, Sequence

from . import data, dataset, exchange, features, governance, live, secrets, training


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
    promotion, promotion_reason = features.ChampionChallengerManager().can_promote(30, 100, -0.01, 0.01)
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
) -> dict[str, object]:
    config = training.TrainingConfig(
        cv_mode=cv_mode,
        embargo_size=embargo_size,
        n_groups=n_groups,
        test_group_count=test_group_count,
        model_family=model_family,
        model_params=dict(model_params or {}),
        fallback_allowed=fallback_allowed,
    )
    result = training.run_training(input_path, output, config)
    summary = dict(result.run_summary)
    summary["requested_model_family"] = model_family
    return summary


def run_collect(output: Path, rows: int, allow_public_network: bool = False) -> dict[str, object]:
    result = dataset.collect_candles(output, rows=rows, allow_public_network=allow_public_network)
    return {
        "output_path": result.output_path.as_posix(),
        "source": result.source,
        "symbol": result.symbol,
        "interval": result.interval,
        "rows": result.rows,
        "network_used": result.network_used,
    }


def run_collect_archive(start: str, end: str, output: Path, checkpoint: Path | None = None) -> dict[str, object]:
    summary = dataset.BinanceArchiveDownloader().download_range(start, end, output, checkpoint)
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
) -> dict[str, object]:
    exchange_adapter = create_exchange_adapter(exchange_name, allow_signed_network, allow_prod, approval_artifacts, recv_window_ms)
    summary = dict(live.run_live(output, dry_run=dry_run, allow_public_network=allow_public_network, max_candles=max_candles).summary)
    summary["exchange"] = exchange_name
    summary["signed_network_enabled"] = exchange_adapter.network_enabled
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe local BTCUSDT v7.18 scaffold")
    subparsers = parser.add_subparsers(dest="command")
    demo = subparsers.add_parser("demo", help="run deterministic local dry-run demo")
    demo.add_argument("--output", default="artifacts/demo", help="artifact output directory")
    collect = subparsers.add_parser("collect", help="collect local fixture candles or explicitly allowed public klines to CSV")
    collect.add_argument("--output", default="artifacts/collected/btcusdt_1m.csv", help="CSV output path")
    collect.add_argument("--rows", type=int, default=240, help="number of fixture rows or public klines to write")
    collect.add_argument("--allow-public-network", action="store_true", help="opt in to unsigned public Binance kline download")
    collect_archive = subparsers.add_parser("collect-archive", help="collect Binance data.binance.vision daily BTCUSDT 1m archives")
    collect_archive.add_argument("--start", required=True, help="inclusive start date YYYY-MM-DD")
    collect_archive.add_argument("--end", required=True, help="inclusive end date YYYY-MM-DD")
    collect_archive.add_argument("--output", default="artifacts/archive", help="archive output directory")
    collect_archive.add_argument("--checkpoint", default=None, help="optional checkpoint JSON path; defaults to output/checkpoint.json")
    train = subparsers.add_parser("train", help="run deterministic offline CSV/fixture training pipeline")
    train.add_argument("--output", default="artifacts/training", help="training artifact output directory")
    train.add_argument("--input", default=None, help="optional local CSV candles path; defaults to offline fixture")
    train.add_argument("--model-family", default="auto", help="model family selector; auto keeps the deterministic stdlib model")
    train.add_argument("--cv-mode", choices=("walk_forward", "combinatorial_purged"), default="walk_forward", help="cross-validation splitter mode")
    train.add_argument("--embargo-size", type=int, default=0, help="bars to embargo after combinatorial test windows")
    train.add_argument("--n-groups", type=int, default=5, help="sequential groups for combinatorial purged CV")
    train.add_argument("--test-group-count", type=int, default=1, help="number of groups selected for each combinatorial test fold")
    train.add_argument("--no-model-fallback", action="store_true", help="disable optional model fallback and fail if the requested family is unavailable")
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
            summary = run_collect(output, args.rows, args.allow_public_network)
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
            summary = run_collect_archive(args.start, args.end, output, checkpoint)
        except (OSError, RuntimeError, ValueError) as error:
            print(f"archive collection failed: {error}", file=sys.stderr)
            return 1
        print("BTCUSDT archive collection complete")
        print(f"downloaded={summary['downloaded_days']}/{summary['total_days']} days")
        print(f"failed={summary['failed_days']} days")
        print(f"last_completed_date={summary['last_completed_date']}")
        print(f"checkpoint={summary['checkpoint_file']}")
        print(f"output={summary['output_dir']}")
        return 0
    if args.command == "train":
        output = Path(args.output)
        input_path = Path(args.input) if args.input else None
        try:
            summary = run_train(output, input_path, args.model_family, args.cv_mode, args.embargo_size, args.n_groups, args.test_group_count, not args.no_model_fallback)
        except (OSError, RuntimeError, ValueError) as error:
            print(f"training failed: {error}", file=sys.stderr)
            return 1
        print("BTCUSDT offline training complete")
        print(f"network_used={summary['network_used']}")
        print(f"orders_enabled={summary['orders_enabled']}")
        print(f"labeled_rows={summary['labeled_rows']}")
        print(f"fold_count={summary['fold_count']}")
        print(f"mean_test_f1={summary['mean_test_f1']}")
        print(f"artifacts={output}")
        return 0
    if args.command == "live":
        output = Path(args.output)
        try:
            approval_artifacts = Path(args.approval_artifacts) if args.approval_artifacts else None
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
        print(f"artifacts={output}")
        return 0
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
