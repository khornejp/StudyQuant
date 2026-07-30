from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Mapping, Sequence

from . import backtest, data, dataset, exchange, features, governance, live, secrets, training

if TYPE_CHECKING:
    from btcusdt_quant import regime_classifier


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


# Which sides each regime is allowed to trade. NOT a copy: this is the same
# object training.py's single-horizon path reads, so the multi-horizon pilot
# can never train a different side set and silently make Phase 4 vs Phase 4.5
# incomparable. Change the policy in training.REGIME_SIDES and both follow.
MH_REGIME_SIDES: Mapping[str, tuple[tuple[str, str], ...]] = training.REGIME_SIDES


def _run_train_multi_horizon_regime_aware(
    args,
    train_rows: Sequence["dataset.FeatureRow"],
    candles: Sequence["data.Candle"],
    horizons: list[int],
    output: Path,
    provenance: Mapping[str, object],
) -> int:
    """Fit one multi-horizon ensemble per (regime, allowed side).

    Emits `train --regime-aware`'s artifact layout so backtest/live load it
    through load_regime_aware_models: the fitted rule detector rides in
    regime_run_summary.json (routing matches how rows were bucketed -- no
    train/serve skew), each regime dir holds long_model.json/short_model.json,
    and each side model is trained on its OWN triple-barrier target so a SELL
    probability really is P(short_success). That is what lets Kelly size both
    sides instead of refusing shorts.
    """
    from btcusdt_quant import ensemble as ensemble_mod, regime_rules as rr

    rule_config = rr.MultiFeatureRegimeConfig()
    if args.rule_regime_config:
        rule_config = rr.MultiFeatureRegimeConfig.from_dict(
            json.loads(Path(args.rule_regime_config).read_text(encoding="utf-8"))
        )

    feature_maps = [row.features for row in train_rows]
    detector = rr.MultiFeatureRegimeDetector(rule_config).fit(feature_maps)
    regimes = detector.detect_all(feature_maps)
    diagnostics = detector.diagnostics(regimes)
    regime_counts = {name: regimes.count(name) for name in MH_REGIME_SIDES}
    print(f"[MH] rule regime distribution: {regime_counts}")

    feature_names = list(dataset.FEATURE_NAMES)
    max_horizon = max(horizons)
    # Thresholds are scored on labels of THIS horizon -- set it to the
    # backtest's --horizon so the cutoff is picked against the same time
    # barrier execution enforces. The caller already trimmed the training
    # window by max(max_horizon, threshold_horizon), so these labels never
    # reach past --training-end.
    threshold_horizon = args.threshold_horizon or max_horizon
    label_reach = max(max_horizon, threshold_horizon)
    print(f"[MH] threshold-selection horizon: {threshold_horizon} bars (models blend {horizons})")
    output.mkdir(parents=True, exist_ok=True)

    # Row-count gate BEFORE the destructive cleanup below. A regime short of
    # --min-regime-rows can be known from regime_counts without training, so
    # failing here (rather than after rmtree) preserves the previous artifact:
    # a "not enough data" run leaves the last good model intact instead of
    # wiping it and exiting 1. Only fit-level failures (found after training)
    # leave a partial artifact.
    if not args.allow_partial_sides:
        too_small = {
            name: count for name, count in regime_counts.items()
            if count < args.min_regime_rows
        }
        if too_small:
            detail = ", ".join(f"{name}({count})" for name, count in sorted(too_small.items()))
            print(
                f"multi-horizon training aborted: regime(s) below --min-regime-rows "
                f"{args.min_regime_rows}: {detail}. Every side of those regimes would be "
                f"missing, making the run one-directional. Lower --min-regime-rows, widen "
                f"the training window, or pass --allow-partial-sides. (Previous artifact left intact.)",
                file=sys.stderr,
            )
            return 1

    # Train into a staging dir and only swap it into `output` once every gate
    # has passed. Writing directly into `output` and deleting stale dirs
    # up-front means any later gate failure (missing side, failed refit) leaves
    # the previous GOOD artifact destroyed and only a partial one behind -- a
    # rerun that trips a gate would be strictly worse than not running. With
    # staging, a failed run leaves `output` untouched.
    import shutil as _shutil
    staging = output / ".mh_staging"
    if staging.exists():
        _shutil.rmtree(staging)
    staging.mkdir(parents=True)

    regime_results: dict[str, dict[str, object]] = {}
    trained_regimes: dict[str, dict[str, object]] = {}
    skipped_regimes: dict[str, str] = {}
    # regime -> sides REGIME_SIDES asks for that could not be fitted.
    missing_sides: dict[str, list[str]] = {}

    for regime_name, sides in MH_REGIME_SIDES.items():
        regime_rows = [row for row, regime in zip(train_rows, regimes) if regime == regime_name]
        if len(regime_rows) < args.min_regime_rows:
            skipped_regimes[regime_name] = f"only {len(regime_rows)} rows (< --min-regime-rows {args.min_regime_rows})"
            print(f"[MH] regime {regime_name}: SKIPPED ({skipped_regimes[regime_name]})")
            # A regime with too few rows trains NOTHING, so every side the
            # policy asks for is missing. Feed the gate, or a fully-absent
            # required regime slips through as exit 0.
            missing_sides[regime_name] = [side for side, _ in sides]
            continue

        # Carve a chronological threshold holdout that NO horizon model and no
        # blend weight ever sees; the purge gap keeps the last fitted row's
        # label window from reaching into it. The gap spans the longest label
        # reach of either side (fit labels at max_horizon, holdout labels at
        # threshold_horizon). (Counted in rows, not bars, because a regime's
        # rows are non-contiguous -- same convention as training.py's
        # per-regime holdout.)
        holdout_split = int(len(regime_rows) * 0.8)
        holdout_start = min(len(regime_rows), holdout_split + label_reach)
        fit_rows = regime_rows[:holdout_split]
        holdout_rows = regime_rows[holdout_start:]

        regime_dir = staging / f"regime_{regime_name}"
        regime_dir.mkdir(parents=True, exist_ok=True)
        selected_thresholds: dict[str, float] = {}
        side_summaries: dict[str, object] = {}
        trained_sides: list[str] = []

        # attach_labels builds every target (long_success, short_success,
        # profitability) regardless of which one a side reads, and none of its
        # arguments depend on the side -- so labeling once per regime instead of
        # once per side saves a full triple-barrier pass over the holdout for
        # every two-sided regime (`range`).
        holdout_labeled = dataset.attach_labels(
            holdout_rows, candles, horizon=threshold_horizon,
            label_threshold=args.label_threshold, tp_pct=args.tp_pct, sl_pct=args.sl_pct,
        )
        holdout_matrix = training.feature_matrix(holdout_labeled, feature_names) if holdout_labeled else []

        def _fit(rows, target_key: str, weights=None):
            return ensemble_mod.fit_multi_horizon_ensemble(
                rows,
                candles,
                feature_names,
                horizons=horizons,
                model_family=args.model_family,
                label_threshold=args.label_threshold,
                tp_pct=args.tp_pct,
                sl_pct=args.sl_pct,
                weighting=args.weighting,
                target_key=target_key,
                weights=weights,
            )

        for side, target_key in sides:
            # DIAGNOSTIC ensemble: fit on the prefix only, so the threshold can
            # be chosen on a holdout it has never seen. Mirrors training.py's
            # per-regime diagnostic model.
            print(f"[MH] regime {regime_name}/{side}: fitting {len(horizons)} horizon models on {target_key} ({len(fit_rows):,} prefix rows) ...")
            try:
                diagnostic = _fit(fit_rows, target_key)
            except ValueError as error:
                print(f"[MH] regime {regime_name}/{side}: SKIPPED ({error})", file=sys.stderr)
                continue

            threshold = 0.5
            # Same labeled holdout for every side; only the target column differs.
            holdout_labels = [int(row.targets.get(target_key, row.label)) for row in holdout_labeled]
            if len(set(holdout_labels)) >= 2:
                probs = diagnostic.predict_proba(holdout_matrix)
                threshold = training.select_threshold(
                    probs, holdout_labels,
                    objective=args.threshold_objective,
                    tp_pct=args.tp_pct, sl_pct=args.sl_pct,
                    round_trip_cost=args.round_trip_cost,
                )
                print(f"[MH] regime {regime_name}/{side}: holdout n={len(holdout_labels):,} threshold={threshold:.4f}")
            else:
                print(f"[MH] regime {regime_name}/{side}: holdout single-class; keeping threshold 0.5", file=sys.stderr)

            # DEPLOYED ensemble: refit on ALL of this regime's rows. Without
            # this the shipped model would see only the prefix minus the
            # ensemble's own validation tail (~64% of the regime's data) while
            # Phase 3's shipped model is fit on 100% -- a data handicap that
            # would be mistaken for a horizon-blend effect when the two are
            # compared. The blend WEIGHTS are carried over from the prefix-only
            # diagnostic rather than relearned, so the refit needs no validation
            # tail and every row trains the horizon models; both the weights and
            # the threshold stay out-of-sample, exactly as training.py does it.
            adapter = diagnostic
            refit_rows = len(fit_rows)
            refit_done = False
            if not args.skip_final_refit:
                print(f"[MH] regime {regime_name}/{side}: refitting on all {len(regime_rows):,} regime rows for deployment ...")
                try:
                    adapter = _fit(regime_rows, target_key, weights=dict(zip(diagnostic.horizons, diagnostic.weights)))
                    refit_rows = len(regime_rows)
                    refit_done = True
                except ValueError as error:
                    print(f"[MH] regime {regime_name}/{side}: final refit failed ({error}); shipping the prefix model", file=sys.stderr)

            (regime_dir / f"{side}_model.json").write_text(json.dumps(adapter.as_dict()), encoding="utf-8")
            trained_sides.append(side)
            selected_thresholds[side] = threshold
            side_summaries[side] = {
                "target": target_key,
                "horizons": list(adapter.horizons),
                "weights": list(adapter.weights),
                "holdout_rows": len(holdout_labels),
                # Feature rows handed to each fit (labeling drops warmup rows,
                # so the models see somewhat fewer than these counts).
                "threshold_fit_input_rows": len(fit_rows),
                "deployed_fit_input_rows": refit_rows,
                # What ACTUALLY happened, not what was requested: a refit can
                # fail (single-class slice) and ship the prefix model, and an
                # artifact that claims data parity it does not have would make
                # a Phase 4 vs 4.5 comparison wrong in the model's favour.
                "final_refit": refit_done,
            }

        wanted_sides = [side for side, _ in sides]
        if not trained_sides:
            skipped_regimes[regime_name] = "no side could be fitted"
            # A regime that fit NOTHING is the worst case (its whole direction
            # is missing), so it belongs in missing_sides too -- not only in
            # skipped_regimes, which the gate does not consult.
            missing_sides[regime_name] = wanted_sides
            continue

        missing = [side for side in wanted_sides if side not in trained_sides]
        if missing:
            missing_sides[regime_name] = missing

        regime_results[regime_name] = {
            "selected_thresholds": selected_thresholds,
            "sides": side_summaries,
            "row_count": len(regime_rows),
        }
        trained_regimes[regime_name] = {
            "status": "trained",
            "row_count": len(regime_rows),
            "output_dir": f"regime_{regime_name}",
            "sides": trained_sides,
            "missing_sides": missing,
        }

    if not regime_results:
        print("multi-horizon training failed: no regime had enough rows to train", file=sys.stderr)
        print(f"  previous artifact in {output} left intact (partial run staged at {staging})", file=sys.stderr)
        return 1

    default_regime = max(trained_regimes, key=lambda name: int(trained_regimes[name]["row_count"]))
    run_summary = {
        "regime_aware": True,
        "regime_source": "multi_feature_rule",
        "model_kind": "multi_horizon_ensemble",
        "horizons": list(horizons),
        # The barrier the thresholds were chosen against. backtest compares it
        # to its own --horizon and warns on a mismatch, so a blended model is
        # never silently judged on one barrier and traded on another.
        "threshold_horizon": threshold_horizon,
        # The TP/SL legs of that same triple barrier. Without them
        # load_regime_aware_models reads label_tp_pct=None and the parity check
        # can only warn instead of verify -- the single-horizon path records
        # these for the identical reason (see run_regime_aware_training).
        "tp_pct": args.tp_pct,
        "sl_pct": args.sl_pct,
        "label_reach": label_reach,
        "regime_results": regime_results,
        "regime_counts": regime_counts,
        "trained_regimes": trained_regimes,
        "skipped_regimes": skipped_regimes,
        "default_regime": default_regime,
        "min_regime_rows": args.min_regime_rows,
        "regime_detector": None,
        "multi_feature_regime_detector": detector.to_dict(),
        "regime_diagnostics": diagnostics,
        "threshold_objective": args.threshold_objective,
        "round_trip_cost": args.round_trip_cost,
        # Requested vs achieved. Deployed models are meant to be refit on the
        # full regime data (Phase 3 parity) with thresholds still coming from
        # the prefix-only diagnostic; a refit can fail on a single-class slice
        # and ship the prefix model instead, so the artifact must not claim a
        # data parity it does not have.
        "final_refit_requested": not args.skip_final_refit,
        "final_refit_all_sides": all(
            bool(side_info["final_refit"])
            for regime_info in regime_results.values()
            for side_info in regime_info["sides"].values()
        ),
        "missing_sides": missing_sides,
        "artifacts": ["regime_run_summary.json"],
        **provenance,
    }
    # Summary is written into STAGING (not output) even on the failure paths
    # below, so a failed run leaves the previous good artifact in output intact
    # while the partial staging tree remains for diagnosis. Only a fully
    # successful run promotes staging into output (at the end).
    # json_safe for the same reason the backtest summaries get it: a per-regime
    # holdout metric can come out NaN, and json.dumps would write a bare NaN
    # token that RFC 8259 forbids -- into the artifact live.py loads.
    (staging / "regime_run_summary.json").write_text(
        json.dumps(backtest.json_safe(run_summary), indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    # A side the policy asks for but that could not be fitted never emits a
    # signal, so no skip counter and no coverage number sees it: the backtest
    # trades that regime one-directionally while every published check still
    # reads as passing. `train --regime-aware` raises in the same situation,
    # so accepting it here would make Phase 4.5 asymmetric with Phase 4.
    if missing_sides:
        detail = ", ".join(f"{regime}/{'+'.join(sides)}" for regime, sides in sorted(missing_sides.items()))
        message = f"could not fit required side(s): {detail}"
        if not args.allow_partial_sides:
            print(f"multi-horizon training failed: {message}", file=sys.stderr)
            print(f"  previous artifact in {output} left intact; partial run staged at {staging} for diagnosis", file=sys.stderr)
            print("  fix the data for those sides, or pass --allow-partial-sides to accept a one-directional regime", file=sys.stderr)
            return 1
        print(f"WARNING: {message} (--allow-partial-sides)", file=sys.stderr)
        print("WARNING: those regimes trade one direction only; do not compare this artifact to Phase 4", file=sys.stderr)

    # A refit that was asked for and did not happen leaves some sides trained
    # on ~64% of their regime's rows. Nothing downstream can see that, so a
    # Phase 4 vs 4.5 comparison would silently favour Phase 4. Fail loudly
    # unless the operator opted into a partial artifact. (--skip-final-refit
    # is a deliberate choice and never lands here.) Checked BEFORE the success
    # banner so the output never says "complete" and then fails.
    partial = [
        f"{regime}/{side}"
        for regime, regime_info in regime_results.items()
        for side, side_info in regime_info["sides"].items()
        if not side_info["final_refit"]
    ]
    if run_summary["final_refit_requested"] and partial:
        message = f"final refit failed for {', '.join(partial)}; those sides ship the prefix model"
        if not args.allow_partial_final_refit:
            print(f"multi-horizon training failed: {message}", file=sys.stderr)
            print(f"  previous artifact in {output} left intact; partial run staged at {staging} for diagnosis", file=sys.stderr)
            print("  rerun after fixing the data, or pass --allow-partial-final-refit to accept it", file=sys.stderr)
            return 1
        print(f"WARNING: {message} (--allow-partial-final-refit)", file=sys.stderr)
        print("WARNING: this artifact does NOT have Phase 3 data parity; do not compare it to Phase 4", file=sys.stderr)

    # Every gate passed: promote staging into output. Replace only the regime
    # dirs this policy owns plus the summary, so an unrelated regime dir a
    # shared output holds for another purpose is left alone (the loader keys
    # off the summary, so a leftover dir it does not list is inert anyway).
    for _rn in list(MH_REGIME_SIDES) + [None]:
        name = "regime_run_summary.json" if _rn is None else f"regime_{_rn}"
        src = staging / name
        dst = output / name
        if dst.exists():
            _shutil.rmtree(dst) if dst.is_dir() and not dst.is_symlink() else dst.unlink()
        if src.exists():
            _shutil.move(str(src), str(dst))
    _shutil.rmtree(staging, ignore_errors=True)

    print("BTCUSDT multi-horizon regime-aware training complete")
    for regime_name, info in trained_regimes.items():
        thresholds = regime_results[regime_name]["selected_thresholds"]
        print(f"  {regime_name}: sides={info['sides']} rows={info['row_count']:,} thresholds={ {k: round(v, 4) for k, v in thresholds.items()} }")
    if skipped_regimes:
        print(f"  skipped: {skipped_regimes}")
    print(f"  default_regime={default_regime}")
    print(f"artifacts={output}")
    return 0


def _parse_end_date_exclusive(value: str) -> datetime:
    """Parse an end-of-range date/datetime as an EXCLUSIVE upper bound.

    A bare date like "2024-12-31" (no time component, len==10) means "through
    the end of Dec 31", but fromisoformat parses it as 2024-12-31 00:00:00 --
    which then excludes the entire day when used with a `<=` filter (only the
    00:00 bar survives). Bumping a bare date forward by one day makes the
    filter behave as intended: `row.open_time <= end` now includes all of
    Dec 31. Full datetimes ("2024-12-31T12:00:00") are left as-is since the
    caller explicitly specified a time, not a whole-day boundary.
    """
    dt = datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    if len(value.strip()) == 10:  # bare "YYYY-MM-DD", no time component
        dt = dt + timedelta(days=1) - timedelta(microseconds=1)
    return dt


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
    regime_classifier_model_path: str | None = None,
    multi_feature_regime: bool = False,
    multi_feature_regime_config: dict | None = None,
    feature_selection_target_min: int = 0,
    feature_selection_target_max: int = 0,
    ensemble_enabled: bool = False,
    ensemble_direction_family: str = "catboost",
    ensemble_profitability_family: str = "catboost",
    ensemble_meta_family: str = "catboost",
    multitask: bool = False,
    training_start: str | None = None,
    training_end: str | None = None,
    test_start: str | None = None,
    test_end: str | None = None,
    only_build: bool = False,
    threshold_objective: str = "trading_pnl",
    threshold_min_trades: int | None = None,
    tp_pct: float = dataset.DEFAULT_LABEL_TP_PCT,
    sl_pct: float = dataset.DEFAULT_LABEL_SL_PCT,
    label_horizon: int = 60,
    label_threshold: float = 0.001,
    round_trip_cost: float = 0.0008,
    shuffle_labels: bool = False,
    shuffle_labels_seed: int = 42,
    exclude_fallback_features: bool = True,
    train_target: str = "profitability",
) -> dict[str, object]:
    if multitask:
        model_family = "pytorch_multitask"
    training_start_dt: datetime | None = None
    if training_start is not None:
        training_start_dt = datetime.fromisoformat(training_start).replace(tzinfo=timezone.utc)
    training_end_dt: datetime | None = None
    if training_end is not None:
        training_end_dt = _parse_end_date_exclusive(training_end)
    test_start_dt: datetime | None = None
    if test_start is not None:
        test_start_dt = datetime.fromisoformat(test_start).replace(tzinfo=timezone.utc)
    test_end_dt: datetime | None = None
    if test_end is not None:
        test_end_dt = _parse_end_date_exclusive(test_end)
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
        shuffle_labels=shuffle_labels,
        shuffle_labels_seed=shuffle_labels_seed,
        exclude_fallback_features=exclude_fallback_features,
        train_target=train_target,
        champion_challenger_enabled=champion_challenger_enabled,
        regime_aware=regime_aware,
        min_regime_rows=min_regime_rows,
        regime_detector_rv_percentile=regime_detector_rv_percentile,
        regime_detector_trend_percentile=regime_detector_trend_percentile,
        regime_detector_min_trend_abs=regime_detector_min_trend_abs,
        regime_detector_low_vol_trend_multiplier=regime_detector_low_vol_trend_multiplier,
        regime_detector_min_regime_run_bars=regime_detector_min_regime_run_bars,
        regime_classifier_model_path=regime_classifier_model_path,
        multi_feature_regime=multi_feature_regime,
        multi_feature_regime_config=multi_feature_regime_config,
        feature_selection_target_min=feature_selection_target_min,
        feature_selection_target_max=feature_selection_target_max,
        ensemble_enabled=ensemble_enabled,
        ensemble_direction_family=ensemble_direction_family,
        ensemble_profitability_family=ensemble_profitability_family,
        ensemble_meta_family=ensemble_meta_family,
        training_start=training_start_dt,
        training_end=training_end_dt,
        test_start=test_start_dt,
        test_end=test_end_dt,
        only_build=only_build,
        threshold_objective=threshold_objective,
        threshold_min_trades=threshold_min_trades,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        label_horizon=label_horizon,
        label_threshold=label_threshold,
        round_trip_cost=round_trip_cost,
    )
    archive_dir = None
    if input_path is not None and input_path.is_dir():
        archive_dir = input_path
        input_path = None
    result = training.run_training(input_path, output, config, archive_dir=archive_dir, external_sources=external_sources)
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


def run_collect_metrics(start: str, end: str, output: Path, allow_public_network: bool = False, force: bool = False) -> dict[str, object]:
    """Download the Binance futures metrics archive (open interest, long/short
    ratios, taker buy/sell) for the given date range.

    Kept separate from training (Phase 1.5): metrics are downloaded once and
    cached on disk, so re-training reuses them without re-downloading. Already
    downloaded daily files are reused unless force=True. Mirrors the klines
    collect-archive workflow.
    """
    if not allow_public_network:
        raise RuntimeError("metrics collection requires --allow-public-network")
    from btcusdt_quant import metrics_source
    downloader = metrics_source.BinanceMetricsDownloader()
    rows = downloader.download_range(start, end, output, force=force)
    report = {
        "start_date": start,
        "end_date": end,
        "metrics_rows": len(rows),
        "first_create_time": rows[0].create_time.isoformat() if rows else None,
        "last_create_time": rows[-1].create_time.isoformat() if rows else None,
        "output": Path(output).as_posix(),
    }
    print("BTCUSDT metrics collection complete")
    print(f"metrics_rows={len(rows)}")
    if rows:
        print(f"coverage={rows[0].create_time.date()} -> {rows[-1].create_time.date()}")
    print(f"output={output}")
    return report


def _catboost_multiclass_fold_classifier(
    train_x: Sequence[Sequence[float]],
    train_y: Sequence[str],
    train_w: Sequence[float] | None,
    predict_x: Sequence[Sequence[float]],
) -> list[dict[str, float]]:
    """A regime_classifier.FoldClassifierFn backed by CatBoost multiclass.

    Trains fresh for each fold (no leakage between folds) and returns
    per-row {"up":.., "range":.., "down":..} probability dicts.

    IMPORTANT: predict_proba's column order follows whatever classes the
    model actually saw during THIS fold's .fit() call (via model.classes_),
    NOT a fixed assumption about REGIME_CLASSES order. If a fold's training
    slice happens to be missing one of the 3 regimes entirely (plausible with
    walk-forward folds -- an early fold might have no "down" rows yet), a
    fixed-order enumerate(row) would silently misalign columns to the wrong
    class names. Any class missing from model.classes_ for this fold gets an
    explicit 0.0 (not a fabricated share of some other class's probability).
    """
    catboost = _import_optional_module_for_regime_classifier()
    from btcusdt_quant.regime_classifier import REGIME_CLASSES
    label_to_int = {c: i for i, c in enumerate(REGIME_CLASSES)}
    y_int = [label_to_int[y] for y in train_y]
    model = catboost.CatBoostClassifier(
        loss_function="MultiClass",
        iterations=500,
        learning_rate=0.05,
        depth=6,
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
    )
    fit_kwargs: dict[str, object] = {}
    if train_w is not None:
        fit_kwargs["sample_weight"] = list(train_w)
    model.fit(list(train_x), y_int, **fit_kwargs)
    proba = model.predict_proba(list(predict_x))
    # model.classes_ gives the actual int-label order predict_proba's columns
    # correspond to (sorted ints of whatever labels were present during fit).
    seen_classes = list(getattr(model, "classes_", range(len(REGIME_CLASSES))))
    int_to_label = {i: c for c, i in label_to_int.items()}
    column_labels = [int_to_label[int(cls)] for cls in seen_classes]
    results: list[dict[str, float]] = []
    for row in proba:
        row_probs = {c: 0.0 for c in REGIME_CLASSES}
        for col_label, p in zip(column_labels, row):
            row_probs[col_label] = float(p)
        results.append(row_probs)
    return results


def _import_optional_module_for_regime_classifier():
    try:
        import catboost
    except ImportError as exc:
        raise RuntimeError(
            "train-regime-classifier requires catboost, which is not installed in this environment"
        ) from exc
    return catboost


def _fit_final_multiclass_classifier(
    feature_rows: Sequence[Sequence[float]],
    labels: Sequence[str],
    weights: Sequence[float] | None,
    feature_names: Sequence[str],
) -> "regime_classifier.RegimeClassifierModel":
    """Fit ONE multiclass classifier on the complete series and wrap it as a
    persistable RegimeClassifierModel -- this is the model that ACTUALLY gets
    saved to disk and used for regime ROUTING (training bucket assignment,
    backtest, live), as opposed to the per-fold classifiers in
    _catboost_multiclass_fold_classifier which only exist transiently to
    produce leakage-safe OOF probabilities for F18 entry-model features.
    """
    from btcusdt_quant import regime_classifier
    catboost = _import_optional_module_for_regime_classifier()
    label_to_int = {c: i for i, c in enumerate(regime_classifier.REGIME_CLASSES)}
    y_int = [label_to_int[y] for y in labels]
    model = catboost.CatBoostClassifier(
        loss_function="MultiClass",
        iterations=500,
        learning_rate=0.05,
        depth=6,
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
    )
    fit_kwargs: dict[str, object] = {}
    if weights is not None:
        fit_kwargs["sample_weight"] = list(weights)
    model.fit(list(feature_rows), y_int, **fit_kwargs)
    return regime_classifier.RegimeClassifierModel(feature_names=feature_names, model=model)


def run_train_regime_classifier(
    input_path: Path,
    regime_file: Path,
    output: Path,
    n_folds: int = 5,
    purge_gap: int = 60,
    transition_zone_days: float = 1.0,
    smoothing_window: int = 30,
    smoothing_min_duration: int = 60,
    smoothing_confidence: float = 0.45,
) -> dict[str, object]:
    """Stage 2 of the multi-timeframe regime work (Method B): train a
    multiclass up/range/down probability classifier on F17 features via
    LEAKAGE-SAFE walk-forward out-of-fold prediction, apply transition-zone
    downweighting and post-hoc smoothing, evaluate against the hand-labeled
    regimes, and write per-minute regime probabilities to disk for the
    training pipeline's --regime-classifier-dir to consume as F18 features.

    This computes OOF probabilities for the training-period rows (each fold
    trained ONLY on chronologically earlier rows, purged at the boundary --
    see regime_classifier.py; the earliest fold has no prior data and is
    left at a neutral 1/3 default rather than fabricated) and ALSO trains one
    final classifier on the complete series for live/backtest use.
    """
    from btcusdt_quant import mtf_features, regime_classifier as rc

    print(f"Loading candles from {input_path} ...")
    candles = dataset.load_parquet_candles(input_path) if input_path.suffix.lower() == ".parquet" else dataset.load_csv_candles(input_path)
    print(f"  {len(candles):,} candles loaded")

    print("Computing F17 multi-timeframe features ...")
    mtf_values = mtf_features.compute_mtf_features_to_minutes(candles)
    feature_names = list(mtf_features.MTF_FEATURE_NAMES)

    print(f"Loading regime labels from {regime_file} ...")
    periods = dataset.load_user_regime_periods(regime_file)
    labels: list[str] = []
    times: list[object] = []
    feature_rows: list[list[float]] = []
    for candle in candles:
        regime = dataset.resolve_user_regime(candle.open_time, periods)
        if regime is None:
            continue
        row_features = mtf_values.get(candle.open_time, {})
        feature_rows.append([float(row_features.get(name, 0.0)) for name in feature_names])
        labels.append(regime)
        times.append(candle.open_time)
    print(f"  {len(labels):,} rows have a resolved regime label (others excluded, no default-fallback guessing)")
    if len(labels) < 1000:
        raise ValueError("too few labeled rows to train a regime classifier (need >=1000)")

    print(f"Computing sample weights (transition zones downweighted +/-{transition_zone_days}d) ...")
    from datetime import timedelta
    weights = rc.transition_zone_sample_weights(labels, times, zone=timedelta(days=transition_zone_days))

    print(f"Generating out-of-fold probabilities (purged {n_folds}-fold, purge_gap={purge_gap}) ...")
    oof_probs = rc.generate_oof_regime_probabilities(
        feature_rows, labels, _catboost_multiclass_fold_classifier,
        n_folds=n_folds, purge_gap=purge_gap, sample_weight=weights,
    )

    print("Smoothing OOF probabilities ...")
    smoothing_config = rc.SmoothingConfig(
        rolling_window=smoothing_window,
        min_duration_bars=smoothing_min_duration,
        confidence_threshold=smoothing_confidence,
    )
    smoothed_probs, assigned_regimes = rc.smooth_regime_probabilities(oof_probs, smoothing_config)

    print("Evaluating OOF classifier against hand-labeled regimes ...")
    evaluation = rc.evaluate_regime_classifier(labels, assigned_regimes)
    print(f"  macro_f1={evaluation.macro_f1:.4f} accuracy={evaluation.accuracy:.4f}")
    print(f"  up<->down confusion (dangerous): {evaluation.up_down_confusion_count}")
    print(f"  range<->trend confusion (less dangerous): {evaluation.range_confusion_count}")
    for c in rc.REGIME_CLASSES:
        print(f"  {c}: precision={evaluation.per_class_precision[c]:.4f} recall={evaluation.per_class_recall[c]:.4f}")

    print("Training final classifier on the complete series (for live/backtest use) ...")
    final_model = _fit_final_multiclass_classifier(feature_rows, labels, weights, feature_names)

    output.mkdir(parents=True, exist_ok=True)
    model_path = output / "regime_classifier_model.cbm"
    final_model.save(str(model_path))
    print(f"Saved routing model to {model_path}")

    probs_by_minute = {
        t.isoformat(): {
            "regime_prob_up": smoothed_probs[i]["up"],
            "regime_prob_range": smoothed_probs[i]["range"],
            "regime_prob_down": smoothed_probs[i]["down"],
        }
        for i, t in enumerate(times)
    }
    (output / "regime_probabilities.json").write_text(json.dumps(probs_by_minute), encoding="utf-8")
    report = {
        "n_labeled_rows": len(labels),
        "n_folds": n_folds,
        "purge_gap": purge_gap,
        "macro_f1": evaluation.macro_f1,
        "accuracy": evaluation.accuracy,
        "up_down_confusion_count": evaluation.up_down_confusion_count,
        "range_confusion_count": evaluation.range_confusion_count,
        "confusion_matrix": evaluation.confusion_matrix,
        "per_class_precision": evaluation.per_class_precision,
        "per_class_recall": evaluation.per_class_recall,
        "model_path": model_path.as_posix(),
        "feature_names": feature_names,
    }
    (output / "regime_classifier_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {output / 'regime_probabilities.json'} and {output / 'regime_classifier_report.json'}")
    return report


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
    long_threshold_override: float | None = None,
    short_threshold_override: float | None = None,
    regime_classifier_dir: str | None = None,
) -> dict[str, object]:
    exchange_adapter = create_exchange_adapter(exchange_name, allow_signed_network, allow_prod, approval_artifacts, recv_window_ms)
    # Load the SAVED regime classifier so live routes with the same model that
    # trained the up/down/range buckets and that backtest routes with. Pass the
    # SAME --regime-classifier-dir used for training/backtest. Without it, live
    # falls back to the trend_slope_30 detector (a train/serve routing skew).
    regime_classifier_model = None
    if regime_classifier_dir:
        from btcusdt_quant import mtf_features as _mtf, regime_classifier as _rc
        model_path = Path(regime_classifier_dir) / "regime_classifier_model.cbm"
        if not model_path.is_file():
            raise FileNotFoundError(
                f"--regime-classifier-dir given but {model_path} not found (run train-regime-classifier first)"
            )
        regime_classifier_model = _rc.RegimeClassifierModel.load(str(model_path), _mtf.MTF_FEATURE_NAMES)
        print(f"[LIVE] regime-classifier: routing via saved model at {model_path}")
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
        long_threshold_override=long_threshold_override,
        short_threshold_override=short_threshold_override,
        regime_classifier_model=regime_classifier_model,
    )
    summary = dict(result.summary)
    summary["exchange"] = exchange_name
    summary["signed_network_enabled"] = exchange_adapter.network_enabled
    return summary


def merge_metrics_external_sources(
    metrics_dir: Path,
    candles: "list[data.Candle]",
    external_sources: dict | None,
) -> dict:
    """Merge F16 derivatives-metrics features into per-candle external_sources.

    SINGLE implementation shared by the train and backtest dispatch paths so
    both sides derive metrics features IDENTICALLY (load zips -> causal 5m
    features -> forward-fill onto the 1m clock -> pack as
    external_sources[minute]["metrics"]). Training a model with --metrics-dir
    and then backtesting without it feeds the model F16=0.0 inputs it never
    saw in training -- a train/serve feature-distribution skew -- so any
    caller that trains with metrics MUST backtest with the same directory.
    """
    from btcusdt_quant import metrics_source
    metrics_rows = metrics_source.load_metrics_dir(metrics_dir)
    minute_times = [c.open_time for c in candles]
    metrics_by_minute = metrics_source.metrics_features_to_minutes(metrics_rows, minute_times)
    print(f"Loaded metrics: {len(metrics_rows)} rows -> {len(metrics_by_minute)} aligned minutes")
    if not metrics_by_minute:
        print(f"WARNING: no metrics rows aligned to the candle window from {metrics_dir}; F16 features will be 0.", file=sys.stderr)
    merged = dict(external_sources or {})
    for minute, feats in metrics_by_minute.items():
        entry = dict(merged.get(minute, {}))
        entry["metrics"] = feats
        merged[minute] = entry
    return merged


def run_edge_validate(
    input_path: str | None,
    output: Path,
    model_artifact: str,
    unified_artifact: str | None = None,
    user_regime_file: str | None = None,
    auto_regime: bool = False,
    regime_classifier_dir: str | None = None,
    horizon: int = 60,
    exec_tp_pct: float | None = None,
    exec_sl_pct: float | None = None,
    long_threshold: float | None = None,
    short_threshold: float | None = None,
    fee_rate_per_side: float | None = None,
    slippage_rate_per_side: float | None = None,
    cost_multipliers: tuple[float, ...] = (1.0, 1.5, 2.0),
    allow_barrier_mismatch: bool = False,
    metrics_dir: str | None = None,
    backtest_start: str | None = None,
    backtest_end: str | None = None,
    threshold_floor: float = 0.0,
    kelly_sizing: bool = False,
    kelly_multiplier: float = 0.5,
    kelly_lookback_bars: int = 1440,
    range_gate_enabled: bool = True,
    maker_fill_window: int = 0,
    maker_fill_penetration: float = 0.0,
) -> dict[str, object]:
    """Run the OOS edge-validation harnesses over a trained backtest artifact.

    cost_stress always runs (on the loaded model or regime bundle). The 4-way
    routing_comparison additionally runs when the artifact is a regime bundle,
    --unified-artifact supplies the no-regime model, and exactly one predicted
    routing source is available (the artifact's own multi-feature rule detector,
    --regime-classifier-dir, or --auto-regime). --user-regime-file adds the
    hindsight oracle arm. Reuses the same loaders the backtest command uses, so
    routing matches how the entry models were trained (edge_validation.py).
    """
    from btcusdt_quant import edge_validation

    output.mkdir(parents=True, exist_ok=True)
    if input_path:
        path = Path(input_path)
        candles = dataset.load_parquet_candles(path) if path.suffix.lower() == ".parquet" else dataset.load_csv_candles(path)
    else:
        candles = data.local_fixture()

    model = None
    regime_bundle = None
    models_by_regime: dict[str, object] | None = None
    multi_feature_regime_detector = None
    regime_detector = None
    regime_classifier_model = None

    artifact = Path(model_artifact)
    if artifact.is_file():
        model = live.load_model_artifact(artifact)
    elif artifact.is_dir() and (artifact / "regime_run_summary.json").is_file():
        regime_bundle = live.load_regime_aware_models(artifact)
        if regime_bundle is not None:
            models_by_regime = {regime: regime_bundle for regime in regime_bundle.models}
            summary = json.loads((artifact / "regime_run_summary.json").read_text(encoding="utf-8"))
            rule_payload = summary.get("multi_feature_regime_detector")
            if rule_payload:
                from btcusdt_quant import regime_rules as _rr
                multi_feature_regime_detector = _rr.MultiFeatureRegimeDetector.from_dict(rule_payload)
    elif artifact.is_dir() and (artifact / "model.json").is_file():
        model = live.load_model_artifact(artifact / "model.json")

    # Predicted routing source (skip if the artifact already carries the rule
    # detector, which the training bucketing used and therefore takes priority).
    if multi_feature_regime_detector is None:
        if regime_classifier_dir:
            from btcusdt_quant import mtf_features as _mtf, regime_classifier as _rc
            classifier_path = Path(regime_classifier_dir) / "regime_classifier_model.cbm"
            if classifier_path.is_file():
                regime_classifier_model = _rc.RegimeClassifierModel.load(str(classifier_path), _mtf.MTF_FEATURE_NAMES)
        elif auto_regime:
            from btcusdt_quant.features import RegimeDetector, RegimeDetectorConfig
            regime_detector = RegimeDetector(RegimeDetectorConfig())

    user_regime_periods = dataset.load_user_regime_periods(Path(user_regime_file)) if user_regime_file else None

    fee = fee_rate_per_side if fee_rate_per_side is not None else backtest.DEFAULT_FEE_RATE_PER_SIDE
    slippage = slippage_rate_per_side if slippage_rate_per_side is not None else backtest.DEFAULT_SLIPPAGE_RATE_PER_SIDE
    # Metrics parity: the pipeline trains WITH --metrics-dir (F16 features), so
    # the validation backtests must merge the SAME metrics or every F16 input is
    # 0.0 here -- a train/serve skew that would make the numbers meaningless.
    # Build the feature matrix once (with metrics if given) and hand it to the
    # harnesses; the oracle arm needs its own rows carrying the hindsight regime.
    external_sources = None
    plain_feature_rows = None
    oracle_feature_rows = None
    if metrics_dir:
        external_sources = merge_metrics_external_sources(Path(metrics_dir), candles, None)
        plain_feature_rows = dataset.build_feature_rows(candles, external_sources=external_sources)
        if user_regime_periods is not None:
            oracle_feature_rows = dataset.build_feature_rows(
                candles, user_regime_periods=user_regime_periods, external_sources=external_sources
            )
    # Execution parity with the Phase 4 backtest: the shipped strategy is
    # Kelly-sized (position_size is the CAP) with the same threshold floor, so
    # the validation must size the SAME way or "does the edge survive cost?" is
    # answered for a strategy nobody deploys. kelly round-trip cost tracks the
    # fee/slippage cost_stress varies, so Kelly sizes down as cost rises.
    kelly_config = None
    if kelly_sizing:
        from . import risk as _risk
        kelly_config = _risk.KellySizingConfig(
            kelly_multiplier=kelly_multiplier,
            variance_lookback_bars=kelly_lookback_bars,
            holding_period_bars=horizon,
        )
    bt_common: dict[str, object] = {
        "label_horizon": horizon,
        "exec_tp_pct": exec_tp_pct,
        "exec_sl_pct": exec_sl_pct,
        "long_threshold": long_threshold,
        "short_threshold": short_threshold,
        "default_regime": regime_bundle.default_regime if regime_bundle is not None else None,
        "allow_barrier_mismatch": allow_barrier_mismatch,
        "start_date": backtest_start,
        "end_date": backtest_end,
        "threshold_floor": threshold_floor,
        "kelly_config": kelly_config,
        # Execution parity with the Phase 4 backtest, same argument as
        # kelly_config above: these three change WHICH signals become trades
        # and what each trade costs. Left at their defaults the harness would
        # cost-stress the gated TAKER strategy while the experiment under test
        # ran gate-off with maker fills -- answering "does the edge survive
        # cost?" for a strategy nobody is proposing to deploy.
        "range_gate_enabled": range_gate_enabled,
        "maker_fill_window": maker_fill_window,
        "maker_fill_penetration": maker_fill_penetration,
    }
    cost_kwargs = dict(bt_common)
    if plain_feature_rows is not None:
        cost_kwargs["feature_rows"] = plain_feature_rows

    report: dict[str, object] = {
        "artifact": str(artifact),
        "backtest_horizon": horizon,
        "kelly_sizing": kelly_sizing,
        "threshold_floor": threshold_floor,
    }
    # cost_stress routes with the PREDICTED source (not the oracle periods).
    report["cost_stress"] = edge_validation.cost_stress(
        candles,
        model=model,
        models_by_regime=models_by_regime,
        base_fee_rate_per_side=fee,
        base_slippage_rate_per_side=slippage,
        multipliers=cost_multipliers,
        regime_detector=regime_detector,
        regime_classifier_model=regime_classifier_model,
        multi_feature_regime_detector=multi_feature_regime_detector,
        **cost_kwargs,
    )

    predicted_sources = [s for s in (regime_detector, regime_classifier_model, multi_feature_regime_detector) if s is not None]
    unified_model = live.load_model_artifact(Path(unified_artifact)) if unified_artifact else None
    if regime_bundle is not None and unified_model is not None and len(predicted_sources) == 1:
        report["routing_comparison"] = edge_validation.routing_comparison(
            candles,
            models_by_regime=models_by_regime,
            unified_model=unified_model,
            user_regime_periods=user_regime_periods,
            regime_detector=regime_detector,
            regime_classifier_model=regime_classifier_model,
            multi_feature_regime_detector=multi_feature_regime_detector,
            feature_rows=plain_feature_rows,
            oracle_feature_rows=oracle_feature_rows,
            **bt_common,
        )
    else:
        # unified_artifact may be given but unloadable (e.g. its train phase
        # failed) -- skip routing gracefully rather than crash on a None model.
        report["routing_comparison_skipped"] = (
            "needs a regime-bundle artifact, a loadable --unified-artifact, and exactly one "
            f"predicted routing source (have bundle={regime_bundle is not None}, "
            f"unified_loaded={unified_model is not None}, predicted_sources={len(predicted_sources)})"
        )

    safe_report = backtest.json_safe(report)
    (output / "edge_validation_report.json").write_text(json.dumps(safe_report, indent=2), encoding="utf-8")
    print(f"[EDGE-VALIDATE] wrote {output / 'edge_validation_report.json'}")
    cs = safe_report.get("cost_stress", {})
    if isinstance(cs, dict):
        print(f"[EDGE-VALIDATE] cost survival: 1.5x={cs.get('survives_1_5x')}, 2x={cs.get('survives_2x')}")
    rc = safe_report.get("routing_comparison")
    if isinstance(rc, dict):
        print(f"[EDGE-VALIDATE] routing: {rc.get('interpretation')}")
    return safe_report


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
    collect_metrics = subparsers.add_parser("collect-metrics", help="collect Binance futures metrics archive (open interest, long/short ratios, taker buy/sell)")
    collect_metrics.add_argument("--start", required=True, help="inclusive start date YYYY-MM-DD")
    collect_metrics.add_argument("--end", required=True, help="inclusive end date YYYY-MM-DD")
    collect_metrics.add_argument("--output", default="artifacts/metrics", help="metrics archive output directory")
    collect_metrics.add_argument("--allow-public-network", action="store_true", help="opt in to public Binance metrics download")
    collect_metrics.add_argument("--force", action="store_true", help="re-download even if the daily zip already exists on disk (default: reuse cached files)")
    train_regime_classifier = subparsers.add_parser("train-regime-classifier", help="Stage 2 of the multi-timeframe regime work: train a leakage-safe (walk-forward OOF) up/range/down probability classifier on F17 multi-timeframe features, for use as F18 features in the entry (long/short) models.")
    train_regime_classifier.add_argument("--input", required=True, help="path to candle Parquet or CSV")
    train_regime_classifier.add_argument("--regime-file", required=True, help="regimes.json with hand-labeled up/down/range periods (the classifier's training target)")
    train_regime_classifier.add_argument("--output", default="artifacts/regime_classifier", help="output directory for regime_probabilities.json and regime_classifier_report.json")
    train_regime_classifier.add_argument("--n-folds", type=int, default=5, help="number of walk-forward folds for out-of-fold probability generation")
    train_regime_classifier.add_argument("--purge-gap", type=int, default=60, help="bars purged from training on each side of a fold boundary (in minutes; default 60 covers the default label_horizon)")
    train_regime_classifier.add_argument("--transition-zone-days", type=float, default=1.0, help="downweight (not exclude) rows within this many days of a hand-labeled regime boundary")
    train_regime_classifier.add_argument("--smoothing-window", type=int, default=30, help="rolling-mean window (bars) applied to raw probabilities before hysteresis")
    train_regime_classifier.add_argument("--smoothing-min-duration", type=int, default=60, help="bars a new regime must persist before a switch is accepted")
    train_regime_classifier.add_argument("--smoothing-confidence", type=float, default=0.45, help="minimum rolling-mean probability required to accept a regime switch")
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
    train.add_argument("--metrics-dir", default=None, help="directory of downloaded Binance metrics archive (collect-metrics output). When set, F16 derivatives-metrics features (open interest, long/short, taker) are computed from it and merged into training. Without it those features degrade to 0.")
    train.add_argument("--regime-classifier-dir", default=None, help="output directory from train-regime-classifier (contains regime_probabilities.json and regime_classifier_model.cbm). When set: (1) F18 regime probability features (regime_prob_up/range/down) are merged into training as inputs, AND (2) training bucket assignment (which regime's model a row's data trains) uses the argmax of those SAME walk-forward-OOF-safe F18 values -- NOT a fresh prediction from the .cbm file (re-predicting on training rows with a classifier fit on the complete span would leak later rows' influence into earlier rows' bucket assignment). The .cbm file itself is used at backtest/live time instead, where classifying genuinely unseen rows is safe -- pass the SAME directory to backtest's --regime-classifier-dir. Without --regime-classifier-dir, training falls back to trend_slope_30-only detection and F18 features degrade to 0. Ignored if --multi-feature-regime is given.")
    train.add_argument("--multi-feature-regime", action="store_true", help="assign regime buckets with the multi-feature rule-based detector (regime_rules.MultiFeatureRegimeDetector: trend/vol/range/breakout scores over F17, hysteresis + min-hold) instead of the learned classifier or single-slope detector. Takes priority over --regime-classifier-dir. The fitted detector is saved to regime_run_summary.json; pass --multi-feature-regime to backtest/live so routing matches. Entry models MUST be (re)trained with this flag for the buckets to match serving.")
    train.add_argument("--rule-regime-config", default=None, help="path to a JSON file of MultiFeatureRegimeConfig overrides (trend_enter, fast_exit, min_hold_bars, switch_confirm_bars, allow_direct_reversal, trend_weights, fast_trend_weights, ...). Only used with --multi-feature-regime. The fitted detector embeds these overrides and is saved to the artifact, so backtest/live inherit them automatically. Missing keys fall back to defaults.")
    train.add_argument("--regime-aware", action="store_true", help="enable regime-aware training with real-time DIRECTIONAL detection: separate up/down/range models (up->long, down->short, range->both) driven by the trend slope. Matches the --auto-regime backtest.")
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
    train.add_argument("--training-start", default=None, help="start date for training data (ISO format, e.g., 2020-01-01); rows before this date are excluded after feature computation")
    train.add_argument("--training-end", default=None, help="end date for training data (ISO format, e.g., 2024-12-31); rows after this date are excluded from training")
    train.add_argument("--test-start", default=None, help="start date for test/validation period (ISO format, e.g., 2025-01-01); used for out-of-sample evaluation after training")
    train.add_argument("--test-end", default=None, help="end date for test/validation period (ISO format, e.g., 2025-06-30)")
    train.add_argument("--only-build", action="store_true", help="only compute features/labels, skip model training")
    train.add_argument("--multitask", action="store_true", help="use PyTorch multitask neural network as the model family (shorthand for --model-family pytorch_multitask)")
    train.add_argument("--long-threshold", type=float, default=0.55, help="minimum probability threshold for LONG entry signals")
    train.add_argument("--short-threshold", type=float, default=0.55, help="minimum probability threshold for SHORT entry signals")
    train.add_argument("--min-ev", type=float, default=0.0001, help="minimum expected value for entry signals (0.01%% = 0.0001)")
    train.add_argument("--tp-pct", type=float, default=dataset.DEFAULT_LABEL_TP_PCT, help=f"take profit %% for triple-barrier labeling. The backtest MUST execute this same barrier (--exec-tp-pct) or the model is answering about a trade you did not take. (default {dataset.DEFAULT_LABEL_TP_PCT} = 1.00%%)")
    train.add_argument("--sl-pct", type=float, default=dataset.DEFAULT_LABEL_SL_PCT, help=f"stop loss %% for triple-barrier labeling. The backtest MUST execute this same barrier (--exec-sl-pct). (default {dataset.DEFAULT_LABEL_SL_PCT} = 0.50%%)")
    train.add_argument("--horizon", type=int, default=60, help="triple-barrier horizon in bars (minutes for 1m data); default 60")
    train.add_argument("--label-threshold", type=float, default=0.001, help="return threshold for directional labeling (0.10%% = 0.001)")
    train.add_argument("--shuffle-labels", action="store_true", help="SHUFFLED-LABEL NEGATIVE CONTROL: permute every row's label/targets across rows (features untouched) before training. A leak-free pipeline must lose its edge under this; comparable net profit from the shuffled model means leakage, threshold overfit, a backtest bug or selection bias. The artifact records shuffled_labels=true -- NEVER deploy it.")
    train.add_argument("--shuffle-labels-seed", type=int, default=42, help="seed for --shuffle-labels permutation (default 42); vary it to repeat the control")
    train.add_argument("--keep-fallback-features", action="store_true", help="keep features whose training-time values are fallback/mock constants (source unavailable offline, e.g. F12 exchange-safety). Default behavior now EXCLUDES them: mock constants carry zero information and become a train/serve input skew when live feeds real values. Pass this only to reproduce the old behavior.")
    train.add_argument("--target", default="profitability", choices=["profitability", "long_success", "short_success", "direction"], help="NON-regime triple-barrier target to learn (default profitability = long-side). --target short_success trains a SHORT model on the same features (its own triple barrier: -tp before +sl); use for a mean-reversion short experiment. The regime-aware path ignores this (it trains long_success/short_success per regime side).")
    train.add_argument(
        "--threshold-objective",
        default="trading_pnl",
        choices=("precision_recall", "trading_pnl"),
        help="objective used by select_threshold: 'trading_pnl' (default; rank by calmar/sharpe/f1 on the cost-aware trading PnL simulator — matches the pipeline) or 'precision_recall' (legacy; precision with recall>=0.3 floor, can select sub-cost thresholds on weak models)",
    )
    train.add_argument(
        "--threshold-min-trades",
        type=int,
        default=None,
        help="minimum number of trades (predicted-positives) for a candidate threshold to be considered under --threshold-objective=trading_pnl. Defaults to max(1, 5%% of rows).",
    )
    train.add_argument(
        "--round-trip-cost",
        type=float,
        default=0.0008,
        help="total round-trip cost fraction (fees + slippage, both sides) used by the trading_pnl threshold objective and holdout metrics. Default 0.0008 = 0.08%% = 2*(0.02%% fee + 0.02%% slippage), matching the backtest's DEFAULT_ROUND_TRIP_COST_PCT. Keep this equal to 2*(--fee-rate-per-side + --slippage-rate-per-side) passed to backtest so threshold selection and execution share one cost basis.",
    )
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
    live_parser.add_argument("--regime-classifier-dir", default=None, help="output directory from train-regime-classifier (contains regime_classifier_model.cbm). When set with --regime-aware, live routes with this SAME saved classifier over F17 multi-timeframe features and injects regime_prob_up/range/down onto the entry-model inputs -- matching how training assigned buckets and how backtest routes. Pass the identical directory used for training/backtest --regime-classifier-dir. Without it, live falls back to trend_slope_30-only detection (a train/serve routing skew).")
    live_parser.add_argument("--strategy-profile", choices=live.STRATEGY_PROFILE_CHOICES, default="balanced", help="strategy profile for regime-aware signal thresholds and TP/SL pricing")
    live_parser.add_argument("--long-threshold", type=float, default=None, help="explicit LONG-entry probability threshold. When omitted, live uses the learned per-regime holdout threshold (selected_thresholds) if the artifact has one, else 0.55. Pass a value to override both.")
    live_parser.add_argument("--short-threshold", type=float, default=None, help="explicit SHORT-entry probability threshold. When omitted, live uses the learned per-regime holdout threshold (selected_thresholds) if the artifact has one, else 0.55. Pass a value to override both.")
    live_parser.add_argument("--min-ev", type=float, default=0.0001, help="minimum expected value for entry signals (0.01%% = 0.0001)")
    live_parser.add_argument("--soak-duration-hours", type=float, default=0.0, help="soak test duration in hours (0 = normal mode, >0 = soak mode)")
    live_parser.add_argument("--soak-report-interval-minutes", type=float, default=60.0, help="soak test periodic report interval in minutes")
    backtest_parser = subparsers.add_parser("backtest", help="run backtest on historical candles")
    backtest_parser.add_argument("--input", default=None, help="CSV candles path; defaults to fixture")
    backtest_parser.add_argument("--output", default="artifacts/backtest", help="backtest output directory")
    backtest_parser.add_argument("--model-artifact", default=None, help="trained model artifact JSON path or regime-aware directory")
    backtest_parser.add_argument("--user-regime-file", default=None, help="path to JSON file with user-specified regime periods for backtest")
    backtest_parser.add_argument("--backtest-start", default="2025-01-01", help="start date for backtest (ISO format); candles before this date are used for feature computation only. Default 2025-01-01 matches the pipeline's full-year 2025 out-of-sample window (was 2025-07-01 when 2025 H1 was a held-out validation span; that split no longer exists).")
    backtest_parser.add_argument("--tp-floor", type=float, default=None, help="override TP floor (fraction, e.g. 0.003 = 0.30%%) for all strategy profiles. Use to match the tp_pct used at training time for a consistent sweep.")
    backtest_parser.add_argument("--sl-floor", type=float, default=None, help="override SL floor (fraction, e.g. 0.0015 = 0.15%%) for all strategy profiles.")
    backtest_parser.add_argument("--fixed-tp-sl", action="store_true", help="disable ATR-based TP/SL sizing and trade EXACTLY the tp-floor/sl-floor. Use for the TP/SL sweep so backtest barriers match the training labels.")
    backtest_parser.add_argument("--auto-regime", action="store_true", help="detect regimes in real time with RegimeDetector (directional up/down/range from trend slope) instead of a hand-labeled --user-regime-file. This is what a live deployment does, since future regimes can't be known in advance. Ignored if --user-regime-file is given. Ignored if --regime-classifier-dir is given (the classifier takes priority when both are set).")
    backtest_parser.add_argument("--long-threshold", type=float, default=None, help="override the LONG-entry probability threshold for all regimes. When omitted, the backtest uses the learned per-regime holdout threshold (selected_thresholds) if the artifact has one, else the strategy profile default -- matching live.")
    backtest_parser.add_argument("--short-threshold", type=float, default=None, help="override the SHORT-entry probability threshold for all regimes. When omitted, uses the learned per-regime threshold if present, else the strategy default.")
    backtest_parser.add_argument("--exec-tp-pct", type=float, default=None, help="execute with a FIXED take-profit of this fraction (e.g. 0.003 = 0.30%%) for every trade instead of the strategy's ATR-based barrier. Set equal to the training --tp-pct so the backtest executes the SAME barrier the model was labeled/trained on (avoids the train/execution mismatch where the model predicts a 0.30%% move but the backtest trades a 0.84%% ATR barrier). Requires --exec-sl-pct too.")
    backtest_parser.add_argument("--exec-sl-pct", type=float, default=None, help="execute with a FIXED stop-loss of this fraction (e.g. 0.0015 = 0.15%%). Set equal to training --sl-pct. Requires --exec-tp-pct too.")
    backtest_parser.add_argument("--allow-barrier-mismatch", action="store_true", help="permit --exec-tp-pct/--exec-sl-pct to differ from the tp_pct/sl_pct the loaded models were LABELED on (recorded in regime_run_summary.json). Off by default: the model predicts P(TP before SL) for the barrier it was trained on, so executing a different one denominates every probability, threshold and win rate in a barrier nobody trained on, and the run reports a meaningless number without erroring. No pipeline needs this -- tp_sl_sweep.sh RETRAINS each cell at its own tp/sl, so its barriers match. Pass it only for a deliberate one-off probe of how a fixed model behaves under a barrier it was not trained for, and read the result as a sensitivity check, not as performance.")
    backtest_parser.add_argument("--backtest-end", default=None, help="inclusive end date (YYYY-MM-DD) of the trading window. Without it the backtest silently trades from --backtest-start to the END OF FILE, so a parquet extended past 2025 would silently widen the traded span. Routing diagnostics are sliced to the same window.")
    backtest_parser.add_argument("--metrics-dir", default=None, help="directory of downloaded Binance metrics archive (collect-metrics output) -- pass the SAME directory used for training's --metrics-dir. Training with metrics and backtesting without them feeds the model F16 derivatives-metrics features (open interest change rates/z-scores, long/short ratios, taker ratio) as 0.0 -- inputs it never saw in training (train/serve feature skew). Without this flag those features are 0 in the backtest.")
    backtest_parser.add_argument("--fee-rate-per-side", type=float, default=None, help="override the per-side TAKER fee fraction (default 0.0005 = 0.05%%, Binance USDT-M VIP0). This is what an immediate fill pays, and the exit is modeled taker on every path. Together with --slippage-rate-per-side this sets the executed round-trip cost; keep 2*(fee+slippage) equal to training's --round-trip-cost so the threshold objective and execution share one cost basis.")
    backtest_parser.add_argument("--maker-exit", action="store_true", help="price the EXIT leg as a resting limit (maker fee, no slippage) instead of an immediate fill -- Bitget lets TP/SL be attached as limit orders at open. ASSUMES the exit limit always fills at the modeled exit price. That holds for TP and is defensible for the horizon exit, but it is the OPTIMISTIC case for SL: a stop-limit fills only if someone crosses it, and the fast one-way move that triggers a stop is exactly the one that blows through the level, leaving you still in and losing more than sl_pct. High average BTC volume does not help -- the risk is in the liquidation-cascade tail. Treat maker-exit vs default as a RANGE, not a number.")
    backtest_parser.add_argument("--maker-fee-rate-per-side", type=float, default=None, help="override the per-side MAKER fee fraction (default 0.0002 = 0.02%%, Binance USDT-M VIP0). Applies only to a resting-limit ENTRY under --maker-fill-window; set it negative only if the account genuinely has a maker rebate. Not the same number as --fee-rate-per-side -- charging the maker rate for taker fills under-counted every taker round trip by 6bps before 2026-07-30.")
    backtest_parser.add_argument("--slippage-rate-per-side", type=float, default=None, help="override the per-side slippage fraction (default 0.0002 = 0.02%%). See --fee-rate-per-side.")
    backtest_parser.add_argument("--horizon", type=int, default=60, help="max holding bars before forced TIMEOUT exit (minutes for 1m data). MUST match the training --horizon so backtest execution and triple-barrier labels share the same time barrier (a train horizon of 120 with a backtest horizon of 60 silently misaligns label vs execution). Default 60 = training default.")
    backtest_parser.add_argument("--threshold-floor", type=float, default=0.0, help="hard lower bound on the learned/strategy entry thresholds (does NOT clamp an explicit --long/--short-threshold override). Learned selected_thresholds can drop to ~0.32 on weak models; e.g. --threshold-floor 0.45 keeps entries above a minimum confidence so sub-cost signals don't flood the backtest. Default 0 = disabled.")
    backtest_parser.add_argument("--kelly-sizing", action="store_true", help="size each trade with fractional Kelly (f* = edge/variance, Half-Kelly by default) from the entry probability, executed TP/SL distances, and trailing bar-return variance scaled to --horizon. The fixed position_size becomes the CAP; entries with non-positive Kelly edge are skipped (kelly_sizing.entries_skipped_no_edge in the summary). Applies to the main backtest only; the strategy_comparison block stays fixed-size (marked sizing=fixed_position_size).")
    backtest_parser.add_argument("--kelly-multiplier", type=float, default=0.5, help="fraction of full Kelly to bet (default 0.5 = Half-Kelly: ~18.5%% less growth for ~43%% less max drawdown). Only used with --kelly-sizing.")
    backtest_parser.add_argument("--kelly-lookback-bars", type=int, default=1440, help="trailing bars for the Kelly variance estimate (default 1440 = 1 day of 1m bars). Only used with --kelly-sizing.")
    backtest_parser.add_argument("--regime-classifier-dir", default=None, help="output directory from train-regime-classifier (contains regime_classifier_model.cbm). When set, this SAME saved classifier drives regime routing here via F17 multi-timeframe features -- pass the identical directory used for training's --regime-classifier-dir so routing stays consistent with how the up/down/range models were trained. Takes priority over --auto-regime. Ignored if --user-regime-file is given.")
    backtest_parser.add_argument("--maker-fill-window", type=int, default=0, help="model MAKER (resting limit) entries instead of the default instant taker fill at the signal-bar close. A BUY places a limit at the signal close and fills only when a LATER bar's low returns to it within this many bars (a SELL uses the high); unfilled within the window = the order is cancelled and the trade is MISSED. Maker entries pay no entry-side fee/slippage (only exit). This surfaces the two costs a taker backtest hides: adverse selection (you only fill when price came back to you) and missed trades (the moves that ran away). 0 = disabled (instant taker fill). See maker_fill_diagnostics in the summary for fill rate.")
    backtest_parser.add_argument("--maker-fill-penetration-bps", type=float, default=0.0, help="queue-priority stress for --maker-fill-window: require the price to PENETRATE the resting limit by this many bps before it fills, not merely touch it (a resting order sits behind others at its price, so a bare touch may only fill the front of the queue). E.g. 2 = a BUY limit fills only when a bar's low reaches 2bps BELOW the limit. 0 = touch fills (optimistic). Only meaningful with --maker-fill-window > 0.")
    backtest_parser.add_argument("--disable-range-gate", action="store_true", help="A/B experiment flag: skip the range mean-reversion direction gate (which blocks entries at range_position_20 0.25-0.75 and forces LONG-only/SHORT-only at the extremes). With 2025 ~91%% range, the gate suppresses most entries; disabling it lets the model's own probability decide direction everywhere. Backtest-only -- live keeps the gate. Recorded in run_config for comparability.")
    mh_parser = subparsers.add_parser(
        "train-multi-horizon",
        help="pilot: train one entry model per label horizon (e.g. 30/60/90m) and blend their probabilities (G-Research 7th-place pattern). Saves a single model.json loadable by `backtest --model-artifact <dir>/model.json`.",
    )
    mh_parser.add_argument("--input", required=True, help="candle Parquet or CSV")
    mh_parser.add_argument("--output", required=True, help="output directory for model.json + multi_horizon_summary.json")
    mh_parser.add_argument("--horizons", default="30,60,90", help="comma-separated label horizons in bars (default 30,60,90)")
    mh_parser.add_argument("--model-family", default="catboost", help="base model family per horizon (default catboost)")
    mh_parser.add_argument("--weighting", default="validation", choices=["equal", "validation"], help="blend weights: equal average or validation-accuracy-edge weighted (default validation)")
    mh_parser.add_argument("--training-start", default=None, help="ISO date; rows before this are excluded from training")
    mh_parser.add_argument("--training-end", default=None, help="ISO date; final training day (inclusive)")
    mh_parser.add_argument("--tp-pct", type=float, default=dataset.DEFAULT_LABEL_TP_PCT, help=f"triple-barrier TP fraction for labeling (default {dataset.DEFAULT_LABEL_TP_PCT})")
    mh_parser.add_argument("--sl-pct", type=float, default=dataset.DEFAULT_LABEL_SL_PCT, help=f"triple-barrier SL fraction for labeling (default {dataset.DEFAULT_LABEL_SL_PCT})")
    mh_parser.add_argument("--label-threshold", type=float, default=0.001, help="direction label threshold (default 0.001)")
    mh_parser.add_argument("--metrics-dir", default=None, help="optional futures metrics archive dir (collect-metrics output) so training features match a backtest run with the same --metrics-dir")
    mh_parser.add_argument("--regime-aware", action="store_true", help="bucket rows with the multi-feature rule detector and fit one multi-horizon ensemble per regime AND side (up->long, down->short, range->both), each on its own long_success/short_success target. Emits the same artifact layout as `train --regime-aware`, so `backtest --model-artifact <dir>` routes and sizes it exactly like the regime model (including two-sided Kelly). Without this flag a single flat model is trained on the long-side profitability target, which cannot price shorts.")
    mh_parser.add_argument("--rule-regime-config", default=None, help="path to a MultiFeatureRegimeConfig JSON (regime-aware mode only); defaults to the built-in config")
    mh_parser.add_argument("--min-regime-rows", type=int, default=2000, help="skip a regime with fewer labeled rows than this (regime-aware mode; default 2000)")
    mh_parser.add_argument("--threshold-objective", default="trading_pnl", choices=["trading_pnl", "precision_recall"], help="objective used to select each regime/side decision threshold on its own holdout (regime-aware mode; default trading_pnl)")
    mh_parser.add_argument("--allow-partial-sides", action="store_true", help="do not fail when a regime cannot fit every side the direction policy asks for (e.g. range/short is single-class). Without this the command exits non-zero, because a missing side model never emits a signal: the backtest silently trades that regime one-directionally while `shorts_skipped_no_short_model` and `default_fallback` both still read 0. Note `train --regime-aware` raises in the same situation, so allowing it here makes Phase 4.5 asymmetric with Phase 4.")
    mh_parser.add_argument("--allow-partial-final-refit", action="store_true", help="do not fail when a requested final refit fails on some regime/side and the prefix model is shipped instead. Without this the command exits non-zero, because a partially-refit artifact trains some sides on ~64%% of the data and would make a Phase 4 vs 4.5 comparison unfair in a way nothing downstream can see. Distinct from --skip-final-refit, which is a deliberate opt-out.")
    mh_parser.add_argument("--skip-final-refit", action="store_true", help="ship the prefix-fitted diagnostic ensemble instead of refitting on the full regime data (regime-aware mode). Halves training time but leaves the deployed model trained on ~64%% of the rows the Phase 3 model sees, so a Phase 4 vs 4.5 comparison would confound the horizon blend with a data handicap. Use only for quick pilots.")
    mh_parser.add_argument("--threshold-horizon", type=int, default=None, help="label horizon (bars) used to score the threshold-selection holdout. Set it to the backtest's --horizon so the threshold is chosen against the SAME time barrier execution enforces; otherwise the blended model is judged on one horizon and traded on another. Default: max(--horizons), which reproduces the pre-flag behaviour. The training window is trimmed by max(this, max(--horizons)) so a longer threshold horizon can never label from candles past --training-end.")
    mh_parser.add_argument("--round-trip-cost", type=float, default=0.0008, help="2*(fee+slippage) used by the trading_pnl threshold objective (default 0.0008); keep equal to the backtest's cost basis")
    ev_parser = subparsers.add_parser(
        "edge-validate",
        help="run OOS edge-validation harnesses (cost stress + 4-way regime routing) over a trained backtest artifact",
    )
    ev_parser.add_argument("--input", default=None, help="candle CSV or Parquet; defaults to the local fixture")
    ev_parser.add_argument("--output", default="artifacts/edge_validation", help="output directory for edge_validation_report.json")
    ev_parser.add_argument("--model-artifact", required=True, help="trained model.json path OR a regime-aware directory (containing regime_run_summary.json)")
    ev_parser.add_argument("--unified-artifact", default=None, help="a no-regime single model.json for the routing_comparison 'unified' arm (only used when --model-artifact is a regime bundle)")
    ev_parser.add_argument("--user-regime-file", default=None, help="hindsight regime periods JSON (e.g. regimes.json) for the oracle routing arm; diagnostic upper bound only, not forward performance")
    ev_parser.add_argument("--auto-regime", action="store_true", help="use the trend_slope_30 directional detector as the predicted routing source (ignored if the artifact carries a multi-feature rule detector, which takes priority)")
    ev_parser.add_argument("--regime-classifier-dir", default=None, help="train-regime-classifier output dir; its saved .cbm is the predicted routing source. Pass the SAME dir used for training so routing matches the trained bucketing")
    ev_parser.add_argument("--horizon", type=int, default=60, help="max holding bars; MUST match training --horizon (default 60)")
    ev_parser.add_argument("--exec-tp-pct", type=float, default=None, help="fixed take-profit fraction to execute (set equal to training --tp-pct so the executed barrier matches the labels)")
    ev_parser.add_argument("--exec-sl-pct", type=float, default=None, help="fixed stop-loss fraction to execute (set equal to training --sl-pct)")
    ev_parser.add_argument("--long-threshold", type=float, default=None, help="override LONG-entry probability threshold (default: learned per-regime threshold)")
    ev_parser.add_argument("--short-threshold", type=float, default=None, help="override SHORT-entry probability threshold")
    ev_parser.add_argument("--fee-rate-per-side", type=float, default=None, help="base per-side fee fraction (default 0.0002); stress runs multiply it")
    ev_parser.add_argument("--slippage-rate-per-side", type=float, default=None, help="base per-side slippage fraction (default 0.0002); stress runs multiply it")
    ev_parser.add_argument("--cost-multipliers", default="1.0,1.5,2.0", help="comma-separated cost multipliers for the stress sweep (default 1.0,1.5,2.0)")
    ev_parser.add_argument("--allow-barrier-mismatch", action="store_true", help="permit --exec-tp/sl-pct to differ from the barrier the models were labeled on (sensitivity probe only, not performance)")
    ev_parser.add_argument("--metrics-dir", default=None, help="Binance metrics archive dir (collect-metrics output) -- pass the SAME dir used for training so the validation backtests see real F16 features instead of 0.0 (train/serve parity)")
    ev_parser.add_argument("--backtest-start", default=None, help="ISO date; trade only from here (earlier candles feed feature computation only). Match the backtest's --backtest-start so the OOS window is the same")
    ev_parser.add_argument("--backtest-end", default=None, help="inclusive ISO end date of the trading window; match the backtest's --backtest-end")
    ev_parser.add_argument("--threshold-floor", type=float, default=0.0, help="hard lower bound on the entry thresholds; match the backtest's --threshold-floor for parity (default 0)")
    ev_parser.add_argument("--kelly-sizing", action="store_true", help="size each trade with fractional Kelly (position_size becomes the cap), matching a Phase-4 backtest run with --kelly-sizing. Without it the validation is fixed-size and its cost survival will not match the deployed strategy")
    ev_parser.add_argument("--kelly-multiplier", type=float, default=0.5, help="fraction of full Kelly (default 0.5 = Half-Kelly); match the backtest")
    ev_parser.add_argument("--kelly-lookback-bars", type=int, default=1440, help="trailing bars for the Kelly variance estimate (default 1440); match the backtest")
    ev_parser.add_argument("--disable-range-gate", action="store_true", help="skip the range mean-reversion direction gate, matching a backtest run with --disable-range-gate. The gate changes WHICH signals become trades, so leaving it on here cost-stresses a different strategy than the one under test")
    ev_parser.add_argument("--maker-fill-window", type=int, default=0, help="model MAKER (resting limit) entries, matching a backtest run with --maker-fill-window. Entries save the entry-side slippage and only fill when a later bar returns to the limit; 0 = instant taker fill. Match the backtest or the cost stress answers for a different execution model")
    ev_parser.add_argument("--maker-fill-penetration-bps", type=float, default=0.0, help="queue-priority stress for --maker-fill-window (bps the price must trade THROUGH the limit before it fills); match the backtest")
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
    if args.command == "collect-metrics":
        output = Path(args.output)
        try:
            run_collect_metrics(args.start, args.end, output, args.allow_public_network, args.force)
        except (OSError, RuntimeError, ValueError) as error:
            print(f"metrics collection failed: {error}", file=sys.stderr)
            return 1
        return 0
    if args.command == "train-regime-classifier":
        try:
            run_train_regime_classifier(
                Path(args.input),
                Path(args.regime_file),
                Path(args.output),
                n_folds=args.n_folds,
                purge_gap=args.purge_gap,
                transition_zone_days=args.transition_zone_days,
                smoothing_window=args.smoothing_window,
                smoothing_min_duration=args.smoothing_min_duration,
                smoothing_confidence=args.smoothing_confidence,
            )
        except (OSError, RuntimeError, ValueError) as error:
            print(f"regime classifier training failed: {error}", file=sys.stderr)
            return 1
        return 0
    if args.command == "train":
        output = Path(args.output)
        input_path = Path(args.input) if args.input else None
        # --long-threshold / --short-threshold / --min-ev only affect the
        # live/backtest DECISION stage, not label-based model training. They
        # were previously parsed but never used anywhere; warn so users don't
        # assume they influenced the trained model.
        train_noop_flags: list[str] = []
        if abs(args.long_threshold - 0.55) > 1e-12:
            train_noop_flags.append(f"--long-threshold {args.long_threshold}")
        if abs(args.short_threshold - 0.55) > 1e-12:
            train_noop_flags.append(f"--short-threshold {args.short_threshold}")
        if abs(args.min_ev - 0.0001) > 1e-12:
            train_noop_flags.append(f"--min-ev {args.min_ev}")
        if train_noop_flags:
            print(
                "WARNING: the following flags do not affect model training "
                "(they are decision-stage parameters for live/backtest) and "
                f"are ignored here: {', '.join(train_noop_flags)}.",
                file=sys.stderr,
            )
        if args.regime_aware:
            # Regime-aware training (real-time directional detection) trains
            # one fixed-hyperparameter CatBoost long/short model per regime
            # directly via .fit() — it does not run the ensemble stacking
            # pipeline or cross-validation. threshold-objective IS applied
            # (see _train_single_regime's regime-scoped holdout threshold
            # selection). Warn loudly if the user also asked for options that
            # still silently have no effect on this path, so they don't
            # believe those options were applied to the model.
            ignored_flags: list[str] = []
            if args.ensemble:
                ignored_flags.append("--ensemble")
            if args.cv_mode != "walk_forward":
                ignored_flags.append(f"--cv-mode {args.cv_mode}")
            if args.n_groups != 5:
                ignored_flags.append(f"--n-groups {args.n_groups}")
            if args.test_group_count != 1:
                ignored_flags.append(f"--test-group-count {args.test_group_count}")
            if args.feature_selection:
                ignored_flags.append("--feature-selection")
            if ignored_flags:
                print(
                    "WARNING: --regime-aware trains one CatBoost model per "
                    "regime via direct .fit() (Optuna tuning IS applied when "
                    "--optuna is set, and --threshold-objective IS applied via "
                    "regime-scoped holdout threshold selection, but the "
                    "following flags are NOT applied on this path and are "
                    "silently ignored: "
                    f"{', '.join(ignored_flags)}. See "
                    "btcusdt_quant/training.py::_train_single_regime.",
                    file=sys.stderr,
                )
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
        # Merge derivatives-metrics features (F16) from a downloaded metrics
        # archive. Computed offline (no network): load rows, derive causal
        # features on the 5m grid, forward-fill onto each candle's 1m clock,
        # and pack as external_sources[candle_time]["metrics"] = {feat: value}.
        if args.metrics_dir:
            if input_path is None:
                print("--metrics-dir requires --input to specify candle data", file=sys.stderr)
                return 1
            metrics_candles = dataset.load_parquet_candles(input_path) if input_path.suffix.lower() == ".parquet" else dataset.load_csv_candles(input_path)
            external_sources = merge_metrics_external_sources(Path(args.metrics_dir), metrics_candles, external_sources)
        # Merge regime probability features (F18) from a train-regime-classifier
        # run. regime_probabilities.json maps ISO timestamp -> {regime_prob_up,
        # regime_prob_range, regime_prob_down}, already leakage-safe
        # (walk-forward OOF) and smoothed. The SAME directory's saved
        # classifier model (.cbm) also drives regime bucket assignment for
        # training (see regime_classifier_model_path below) -- keeping F18
        # features and routing sourced from one directory guarantees they
        # can never drift out of sync with each other.
        regime_classifier_model_path: str | None = None
        if args.multi_feature_regime and args.regime_classifier_dir:
            print(
                "WARNING: --regime-classifier-dir ignored because "
                "--multi-feature-regime takes priority (rule-based bucketing).",
                file=sys.stderr,
            )
        if args.regime_classifier_dir and not args.multi_feature_regime:
            probs_path = Path(args.regime_classifier_dir) / "regime_probabilities.json"
            if not probs_path.is_file():
                print(f"--regime-classifier-dir given but {probs_path} not found (run train-regime-classifier first)", file=sys.stderr)
                return 1
            raw_probs = json.loads(probs_path.read_text(encoding="utf-8"))
            print(f"Loaded regime probabilities: {len(raw_probs)} timestamps")
            if external_sources is None:
                external_sources = {}
            merged = dict(external_sources)
            for iso_time, feats in raw_probs.items():
                minute = datetime.fromisoformat(iso_time)
                entry = dict(merged.get(minute, {}))
                entry["regime_classifier"] = feats
                merged[minute] = entry
            external_sources = merged
            model_path = Path(args.regime_classifier_dir) / "regime_classifier_model.cbm"
            if model_path.is_file():
                # Passed to TrainingConfig only as a signal "the F18 OOF
                # probabilities just merged above are safe to use for bucket
                # assignment" -- training bucket assignment reads those
                # already-merged regime_prob_* feature values directly (see
                # training.py's run_regime_aware_training) rather than
                # loading/re-predicting with this .cbm file. The .cbm itself
                # is only loaded later, for backtest/live routing on
                # genuinely out-of-sample rows.
                regime_classifier_model_path = str(model_path)
                print(f"Found {model_path}; training bucket assignment will use the walk-forward OOF F18 probabilities merged above (not a fresh in-sample prediction from this file -- see training.py for why).")
            else:
                print(f"WARNING: {model_path} not found; falling back to trend_slope_30-only regime detection for bucket assignment. Re-run train-regime-classifier with the current code to get a saved model.", file=sys.stderr)
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
                regime_classifier_model_path=regime_classifier_model_path,
                multi_feature_regime=args.multi_feature_regime,
                multi_feature_regime_config=(
                    json.loads(Path(args.rule_regime_config).read_text(encoding="utf-8"))
                    if args.rule_regime_config else None
                ),
                feature_selection_target_min=args.feature_selection_target_min,
                feature_selection_target_max=args.feature_selection_target_max,
                ensemble_enabled=args.ensemble,
                ensemble_direction_family=args.ensemble_direction_family,
                ensemble_profitability_family=args.ensemble_profitability_family,
                ensemble_meta_family=args.ensemble_meta_family,
                multitask=args.multitask,
                training_start=args.training_start,
                training_end=args.training_end,
                test_start=args.test_start,
                test_end=args.test_end,
                only_build=args.only_build,
                threshold_objective=args.threshold_objective,
                threshold_min_trades=args.threshold_min_trades,
                tp_pct=args.tp_pct,
                sl_pct=args.sl_pct,
                label_horizon=args.horizon,
                label_threshold=args.label_threshold,
                round_trip_cost=args.round_trip_cost,
                shuffle_labels=args.shuffle_labels,
                shuffle_labels_seed=args.shuffle_labels_seed,
                exclude_fallback_features=not args.keep_fallback_features,
                train_target=args.target,
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
            # --min-ev is parsed but there is no EV gate wired into the live
            # decision path, so warn instead of silently ignoring it.
            if abs(args.min_ev - 0.0001) > 1e-12:
                print(
                    f"WARNING: --min-ev {args.min_ev} has no effect; expected-value "
                    "gating is not wired into the live decision path.",
                    file=sys.stderr,
                )
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
                long_threshold_override=args.long_threshold,
                short_threshold_override=args.short_threshold,
                regime_classifier_dir=args.regime_classifier_dir,
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
    if args.command == "edge-validate":
        try:
            multipliers = tuple(float(x) for x in str(args.cost_multipliers).split(",") if x.strip())
        except ValueError:
            print(f"invalid --cost-multipliers: {args.cost_multipliers!r}", file=sys.stderr)
            return 1
        run_edge_validate(
            input_path=args.input,
            output=Path(args.output),
            model_artifact=args.model_artifact,
            unified_artifact=args.unified_artifact,
            user_regime_file=args.user_regime_file,
            auto_regime=args.auto_regime,
            regime_classifier_dir=args.regime_classifier_dir,
            horizon=args.horizon,
            exec_tp_pct=args.exec_tp_pct,
            exec_sl_pct=args.exec_sl_pct,
            long_threshold=args.long_threshold,
            short_threshold=args.short_threshold,
            fee_rate_per_side=args.fee_rate_per_side,
            slippage_rate_per_side=args.slippage_rate_per_side,
            cost_multipliers=multipliers,
            allow_barrier_mismatch=args.allow_barrier_mismatch,
            metrics_dir=args.metrics_dir,
            backtest_start=args.backtest_start,
            backtest_end=args.backtest_end,
            threshold_floor=args.threshold_floor,
            kelly_sizing=args.kelly_sizing,
            kelly_multiplier=args.kelly_multiplier,
            kelly_lookback_bars=args.kelly_lookback_bars,
            range_gate_enabled=not args.disable_range_gate,
            maker_fill_window=args.maker_fill_window,
            maker_fill_penetration=args.maker_fill_penetration_bps / 1e4,
        )
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
            regime_bundle = None
            missing_side_models: dict[str, list[str]] = {}
            user_regime_periods = None
            if args.user_regime_file:
                user_regime_periods = dataset.load_user_regime_periods(Path(args.user_regime_file))
            # Real-time regime routing (live-compatible). Only used when no
            # explicit regime file is given — a hand-labeled file always wins.
            # --regime-classifier-dir (F17-based saved classifier) takes
            # priority over --auto-regime (trend_slope_30-only detector) when
            # both are given, since the classifier is the richer signal.
            regime_detector = None
            regime_classifier_model = None
            multi_feature_regime_detector = None
            if args.regime_classifier_dir:
                if user_regime_periods is not None:
                    print(
                        "WARNING: --regime-classifier-dir ignored because --user-regime-file was provided.",
                        file=sys.stderr,
                    )
                else:
                    from btcusdt_quant import mtf_features as _mtf, regime_classifier as _rc
                    model_path = Path(args.regime_classifier_dir) / "regime_classifier_model.cbm"
                    if not model_path.is_file():
                        print(f"--regime-classifier-dir given but {model_path} not found (run train-regime-classifier first)", file=sys.stderr)
                        return 1
                    regime_classifier_model = _rc.RegimeClassifierModel.load(str(model_path), _mtf.MTF_FEATURE_NAMES)
                    print(f"[BACKTEST] regime-classifier: routing via saved model at {model_path}")
                    if args.auto_regime:
                        print("[BACKTEST] --auto-regime ignored because --regime-classifier-dir takes priority", file=sys.stderr)
            elif args.auto_regime:
                if user_regime_periods is not None:
                    print(
                        "WARNING: --auto-regime ignored because --user-regime-file was provided.",
                        file=sys.stderr,
                    )
                else:
                    from btcusdt_quant.features import RegimeDetector, RegimeDetectorConfig
                    regime_detector = RegimeDetector(RegimeDetectorConfig())
                    print("[BACKTEST] auto-regime: detecting up/down/range in real time via RegimeDetector")
            if args.model_artifact:
                model_path = Path(args.model_artifact)
                if model_path.is_file():
                    model = live.load_model_artifact(model_path)
                elif model_path.is_dir():
                    if (model_path / "regime_run_summary.json").is_file():
                        regime_bundle = live.load_regime_aware_models(model_path)
                        # If the artifact was trained with --multi-feature-regime,
                        # load the SAME fitted rule detector and route with it
                        # (takes priority over classifier/auto-regime so serving
                        # matches how the entry models were bucketed).
                        try:
                            _summary = json.loads((model_path / "regime_run_summary.json").read_text(encoding="utf-8"))
                            # A model whose entry thresholds were chosen against
                            # one time barrier and executed against another is
                            # not the model that was validated: the threshold's
                            # PnL objective assumed a different holding period.
                            _thr_h = _summary.get("threshold_horizon")
                            if _thr_h is not None and int(_thr_h) != int(args.horizon):
                                print(
                                    f"WARNING: artifact thresholds were selected on {int(_thr_h)}-bar labels but "
                                    f"--horizon is {int(args.horizon)}. Entry cutoffs were optimized for a different "
                                    f"time barrier than the one this backtest enforces; retrain with "
                                    f"--threshold-horizon {int(args.horizon)} for a like-for-like result.",
                                    file=sys.stderr,
                                )
                            _mh_horizons = _summary.get("horizons")
                            if _summary.get("model_kind") == "multi_horizon_ensemble" and _mh_horizons:
                                print(f"[BACKTEST] multi-horizon artifact: blend={_mh_horizons}, threshold_horizon={_thr_h}")
                            # A partially-refit artifact trains some sides on a
                            # fraction of their regime's rows; comparing it to a
                            # fully-refit model attributes the data handicap to
                            # the model. The training run already warns, but the
                            # artifact can outlive that terminal.
                            if _summary.get("final_refit_requested") and _summary.get("final_refit_all_sides") is False:
                                print(
                                    "WARNING: this artifact has partial final-refit (some regime/side models were "
                                    "trained on the prefix only). Its results are not comparable to a fully-refit model.",
                                    file=sys.stderr,
                                )
                            _rule_payload = _summary.get("multi_feature_regime_detector")
                            if _rule_payload:
                                from btcusdt_quant import regime_rules as _rr
                                multi_feature_regime_detector = _rr.MultiFeatureRegimeDetector.from_dict(_rule_payload)
                                print("[BACKTEST] regime routing: multi-feature rule detector loaded from artifact")
                                if regime_classifier_model is not None:
                                    print("[BACKTEST] --regime-classifier-dir ignored because the artifact uses multi-feature rule routing", file=sys.stderr)
                                    regime_classifier_model = None
                                regime_detector = None
                        except (OSError, ValueError, KeyError):
                            pass
                        # backtest expects models_by_regime[regime] to be the
                        # RegimeModelBundle itself (it reads .direction_policy /
                        # .long_models / .short_models off the value). Passing
                        # regime_bundle.models (a {regime: ModelAdapter} dict)
                        # made hasattr(value, 'direction_policy') always False,
                        # silently disabling per-direction (long/short) routing
                        # and letting long-only regimes emit short signals.
                        # Map every regime name to the same bundle so the
                        # direction-aware path activates.
                        if regime_bundle is not None:
                            models_by_regime = {
                                regime_name: regime_bundle
                                for regime_name in regime_bundle.models.keys()
                            }
                            # A side the policy asks for but the artifact lacks
                            # never emits a signal, so no skip counter and no
                            # coverage number can see it: the run is quietly
                            # one-directional in that regime while every check
                            # ("shorts_skipped == 0", "default_fallback == 0")
                            # still reads as passing. Compare against the policy.
                            missing_side_models = regime_bundle.missing_side_models(training.REGIME_SIDES)
                            for _regime, _sides in missing_side_models.items():
                                print(
                                    f"WARNING: regime '{_regime}' has no model for side(s) {_sides} that the "
                                    f"direction policy requires. Those entries can never fire, so this run is "
                                    f"one-directional in '{_regime}' -- retrain that side before comparing results.",
                                    file=sys.stderr,
                                )
                        else:
                            models_by_regime = None
                    elif (model_path / "model.json").is_file():
                        model = live.load_model_artifact(model_path / "model.json")
            strategies = {
                "balanced": live.strategy_for_regime(None, "balanced"),
                "conservative": live.strategy_for_regime(None, "conservative"),
                "aggressive": live.strategy_for_regime(None, "aggressive"),
            }
            # Sweep support: override the TP/SL floors on every profile so the
            # backtest trades the same barriers the model was trained against.
            if args.tp_floor is not None or args.sl_floor is not None or args.fixed_tp_sl:
                import dataclasses as _dc
                overridden: dict[str, live.StrategyConfig] = {}
                for name, strat in strategies.items():
                    kwargs: dict[str, object] = {}
                    if args.tp_floor is not None:
                        kwargs["min_tp_floor_pct"] = args.tp_floor
                    if args.sl_floor is not None:
                        kwargs["min_sl_floor_pct"] = args.sl_floor
                    if args.fixed_tp_sl:
                        kwargs["use_atr_pricing"] = False
                    overridden[name] = _dc.replace(strat, **kwargs)
                strategies = overridden
                print(f"[BACKTEST] TP/SL floor override: tp={args.tp_floor}, sl={args.sl_floor}, fixed={args.fixed_tp_sl}")
            resolved_default_regime = regime_bundle.default_regime if regime_bundle is not None else None
            # Build feature rows ONCE and share across compare_strategies and
            # run_backtest. Both would otherwise call build_feature_rows on the
            # full candle set independently (minutes of duplicated feature
            # computation on multi-year 1m data). Safe to share: all routing
            # paths rebuild rows via dataclasses.replace (non-destructive), so
            # the original list is never mutated.
            # F16 metrics parity with training: merge the SAME derivatives-
            # metrics external sources the train dispatch merges (shared
            # helper), so a model trained with --metrics-dir sees real F16
            # values here instead of 0.0 defaults.
            backtest_external_sources = None
            if args.metrics_dir:
                backtest_external_sources = merge_metrics_external_sources(Path(args.metrics_dir), candles, None)
            shared_feature_rows = dataset.build_feature_rows(candles, user_regime_periods=user_regime_periods, external_sources=backtest_external_sources)
            # Rule routing runs ONCE here (detect_all over the full series) and
            # the routed rows + windowed diagnostics are shared by both calls
            # below -- previously compare_strategies and run_backtest each
            # re-ran detect_all over ~3.15M rows.
            shared_routing_diag = None
            if multi_feature_regime_detector is not None and user_regime_periods is None:
                shared_feature_rows, shared_routing_diag = backtest.apply_multi_feature_routing(
                    shared_feature_rows,
                    multi_feature_regime_detector,
                    start_date=args.backtest_start,
                    end_date=args.backtest_end,
                )
                print(
                    "[BACKTEST] regime routing stats (window): "
                    f"counts={shared_routing_diag.get('regime_counts')} "
                    f"transitions={shared_routing_diag.get('regime_transition_count')} "
                    f"direct_up<->down={shared_routing_diag.get('direct_reversal_count')}"
                )
                multi_feature_regime_detector = None  # already applied
            resolved_fee = args.fee_rate_per_side if args.fee_rate_per_side is not None else backtest.DEFAULT_FEE_RATE_PER_SIDE
            resolved_maker_fee = args.maker_fee_rate_per_side if args.maker_fee_rate_per_side is not None else backtest.DEFAULT_MAKER_FEE_RATE_PER_SIDE
            resolved_slippage = args.slippage_rate_per_side if args.slippage_rate_per_side is not None else backtest.DEFAULT_SLIPPAGE_RATE_PER_SIDE
            # Always print the cost basis, not only on override: a net figure is
            # meaningless without the fee tier it assumed, and this project has
            # already published numbers that quietly used the maker rate for
            # taker fills. Show what the run will actually charge.
            _maker_rt = resolved_maker_fee + resolved_fee + resolved_slippage
            print(
                f"[BACKTEST] cost basis: taker_fee={resolved_fee} maker_fee={resolved_maker_fee} "
                f"slippage={resolved_slippage} | taker round_trip={2.0 * (resolved_fee + resolved_slippage)}"
                + (f", maker-entry round_trip={_maker_rt}" if args.maker_fill_window > 0 else "")
            )
            comparison = backtest.compare_strategies(
                candles,
                model,
                strategies,
                fee_rate_per_side=resolved_fee,
                maker_fee_rate_per_side=resolved_maker_fee,
                maker_exit=args.maker_exit,
                slippage_rate_per_side=resolved_slippage,
                models_by_regime=models_by_regime,
                user_regime_periods=user_regime_periods,
                default_regime=resolved_default_regime,
                start_date=args.backtest_start,
                end_date=args.backtest_end,
                regime_detector=regime_detector,
                regime_classifier_model=regime_classifier_model,
                multi_feature_regime_detector=multi_feature_regime_detector,
                exec_tp_pct=args.exec_tp_pct,
                exec_sl_pct=args.exec_sl_pct,
                threshold_floor=args.threshold_floor,
                label_horizon=args.horizon,
                feature_rows=shared_feature_rows,
                allow_barrier_mismatch=args.allow_barrier_mismatch,
            )
            kelly_config = None
            if args.kelly_sizing:
                from . import risk as _risk
                # holding_period_bars follows --horizon so the Kelly variance
                # is scaled to the same time barrier the backtest exits on.
                kelly_config = _risk.KellySizingConfig(
                    kelly_multiplier=args.kelly_multiplier,
                    variance_lookback_bars=args.kelly_lookback_bars,
                    holding_period_bars=args.horizon,
                )
                print(
                    "[BACKTEST] kelly sizing: "
                    f"multiplier={args.kelly_multiplier}, lookback={args.kelly_lookback_bars} bars, "
                    f"holding={args.horizon} bars, cap=position_size"
                )
            result = backtest.run_backtest(
                candles,
                model,
                strategies["balanced"],
                fee_rate_per_side=resolved_fee,
                maker_fee_rate_per_side=resolved_maker_fee,
                maker_exit=args.maker_exit,
                slippage_rate_per_side=resolved_slippage,
                models_by_regime=models_by_regime,
                user_regime_periods=user_regime_periods,
                default_regime=resolved_default_regime,
                start_date=args.backtest_start,
                end_date=args.backtest_end,
                long_threshold=args.long_threshold,
                short_threshold=args.short_threshold,
                exec_tp_pct=args.exec_tp_pct,
                exec_sl_pct=args.exec_sl_pct,
                threshold_floor=args.threshold_floor,
                label_horizon=args.horizon,
                precomputed_routing_diagnostics=shared_routing_diag,
                regime_detector=regime_detector,
                regime_classifier_model=regime_classifier_model,
                multi_feature_regime_detector=multi_feature_regime_detector,
                feature_rows=shared_feature_rows,
                kelly_config=kelly_config,
                allow_barrier_mismatch=args.allow_barrier_mismatch,
                range_gate_enabled=not args.disable_range_gate,
                maker_fill_window=args.maker_fill_window,
                maker_fill_penetration=args.maker_fill_penetration_bps / 1e4,
            )
            for _warning in result.barrier_warnings:
                print(f"[BACKTEST] WARNING: {_warning}")
            # Carried in the artifact, not just the terminal: an operator
            # auditing backtest_summary.json later must be able to see that a
            # side was never tradeable.
            result.missing_side_models = missing_side_models
            summary = {
                "backtest": result.as_dict(),
                "strategy_comparison": comparison,
                # Recorded so a result can be audited against the training
                # --horizon (label/execution time-barrier alignment).
                "label_horizon": args.horizon,
            }
            output.mkdir(parents=True, exist_ok=True)
            # json_safe: an undefined metric (too few trades, no losing trade)
            # is NaN/inf, and json.dumps would write those as bare NaN/Infinity
            # tokens that RFC 8259 forbids. They go out as null instead.
            (output / "backtest_summary.json").write_text(
                json.dumps(backtest.json_safe(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print("BTCUSDT backtest complete")
            print(f"trades={result.trade_count}")
            print(f"total_return={result.total_return:.4f}")
            print(f"win_rate={result.win_rate:.4f}")
            if comparison.get("indistinguishable_profiles"):
                # Not a winner, not even a tie: the arms were the same run.
                print(f"strategy_comparison=SKIPPED ({comparison['indistinguishable_reason']})")
            else:
                print(f"best_strategy={comparison['best_strategy']}")
            # Warn if the regime file does not cover the backtest window. When
            # most bars fall back to default_regime, direction routing is
            # effectively single-regime (e.g. a long-only default emits zero
            # SELLs), which silently defeats regime-aware backtesting.
            if models_by_regime is not None:
                cov = result.regime_coverage
                matched = cov.get("matched", 0)
                fallback = cov.get("default_fallback", 0)
                no_model = cov.get("no_model", 0)
                total_eval = matched + fallback + no_model
                if total_eval > 0:
                    fb_share = fallback / total_eval
                    if matched == 0:
                        print(
                            f"WARNING: no backtest bar matched any configured regime period; "
                            f"all {total_eval:,} bars fell back to default_regime="
                            f"'{resolved_default_regime}'. Your regime file likely does not "
                            f"cover the backtest window (--backtest-start {args.backtest_start}). "
                            f"Direction routing is effectively single-regime.",
                            file=sys.stderr,
                        )
                    elif fallback > 0:
                        # With a hand-labeled --user-regime-file, gaps are the
                        # operator's choice, so only warn past the old 20% line.
                        # With auto/rule routing every bar gets a regime, so ANY
                        # fallback means a whole regime has no model -- the exact
                        # silent-one-directional case, worth flagging at once.
                        auto_routed = user_regime_periods is None
                        if auto_routed or fb_share > 0.20:
                            print(
                                f"WARNING: {fallback:,} of {total_eval:,} backtest bars ({fb_share*100:.1f}%) fell back "
                                f"to default_regime='{resolved_default_regime}' because their own regime has no model. "
                                f"Regime-aware routing applied to {matched:,} bars."
                                + (" Train the missing regime(s): `default_fallback` should be 0." if auto_routed else ""),
                                file=sys.stderr,
                            )
                    if no_model > 0:
                        print(
                            f"WARNING: {no_model:,} bars had neither their own regime model nor a usable "
                            f"default_regime; those bars could never trade.",
                            file=sys.stderr,
                        )
            print(f"artifacts={output}")
            return 0
        except (OSError, RuntimeError, ValueError) as error:
            print(f"backtest failed: {error}", file=sys.stderr)
            return 1
    if args.command == "train-multi-horizon":
        try:
            from btcusdt_quant import ensemble as ensemble_mod

            # Validate before the expensive candle load + feature pass, so a
            # typo fails in milliseconds rather than after a full feature build.
            horizons = [int(h) for h in args.horizons.split(",") if h.strip()]
            if not horizons or any(h <= 0 for h in horizons):
                raise ValueError("--horizons must be a comma-separated list of positive bar counts")
            if args.threshold_horizon is not None and args.threshold_horizon <= 0:
                raise ValueError("--threshold-horizon must be a positive number of bars")
            input_path = Path(args.input)
            output = Path(args.output)

            print(f"[MH] loading candles from {input_path} ...")
            candles = dataset.load_parquet_candles(input_path) if input_path.suffix.lower() == ".parquet" else dataset.load_csv_candles(input_path)
            print(f"[MH]   {len(candles):,} candles")

            external_sources = None
            if args.metrics_dir:
                from btcusdt_quant import metrics_source
                metrics_rows = metrics_source.load_metrics_dir(Path(args.metrics_dir))
                minute_times = [c.open_time for c in candles]
                metrics_by_minute = metrics_source.metrics_features_to_minutes(metrics_rows, minute_times)
                external_sources = {t: {"metrics": feats} for t, feats in metrics_by_minute.items()}
                print(f"[MH]   metrics: {len(metrics_rows):,} rows aligned")

            # Features are computed over the FULL series (so long-lookback
            # features keep their warmup context), then the training window is
            # taken as one contiguous candle/feature slice -- the two lists
            # must stay index-aligned for per-horizon labeling.
            print("[MH] computing features (single pass) ...")
            feature_rows = dataset.build_feature_rows(candles, external_sources=external_sources)

            start_dt = datetime.fromisoformat(args.training_start).replace(tzinfo=timezone.utc) if args.training_start else None
            end_dt = _parse_end_date_exclusive(args.training_end) if args.training_end else None
            i0 = 0
            i1 = len(candles)
            if start_dt is not None:
                while i0 < i1 and candles[i0].open_time < start_dt:
                    i0 += 1
            if end_dt is not None:
                while i1 > i0 and candles[i1 - 1].open_time >= end_dt:
                    i1 -= 1
            # FeatureRow.index is an index into the FULL candle list, and
            # attach_labels dereferences candles[row.index]. Passing a SLICED
            # candle list alongside sliced rows would silently read prices i0
            # bars in the future -- label corruption, not an error. So the
            # rows are sliced but the candle list is passed whole, and the
            # slice's tail is trimmed so no label's forward window reaches
            # past --training-end into the backtest span.
            #
            # The trim must cover the LONGEST forward reach of any label the
            # run will build: the horizon models label at max(horizons), and
            # the regime-aware threshold holdout labels at --threshold-horizon.
            # Trimming by max(horizons) alone would let a longer threshold
            # horizon score its holdout against out-of-sample candles.
            max_horizon = max(horizons)
            threshold_horizon = args.threshold_horizon or max_horizon
            label_reach = max(max_horizon, threshold_horizon)
            train_end = i1 - label_reach
            if train_end <= i0:
                raise ValueError(
                    f"training window [{i0}, {i1}) is shorter than the longest label reach ({label_reach} bars); widen --training-start/--training-end"
                )
            train_rows = feature_rows[i0:train_end]
            labelable = sum(1 for r in train_rows if not r.warmup_invalid)
            print(f"[MH] training slice: {i1 - i0:,} candles ({i0}..{i1}); {len(train_rows):,} rows after {label_reach}-bar label trim; {labelable:,} past warmup")
            if args.regime_aware and args.threshold_horizon is None:
                print(
                    f"[MH] WARNING: --threshold-horizon not set; thresholds will be selected on {max_horizon}-bar labels. "
                    f"Pass --threshold-horizon <backtest --horizon> so the threshold is chosen against the barrier execution enforces.",
                    file=sys.stderr,
                )

            provenance = {
                "window_candles": i1 - i0,
                "rows_after_label_trim": len(train_rows),
                "rows_past_warmup": labelable,
                "tp_pct": args.tp_pct,
                "sl_pct": args.sl_pct,
                "label_threshold": args.label_threshold,
                "weighting": args.weighting,
                "base_model_family": args.model_family,
            }

            if args.regime_aware:
                return _run_train_multi_horizon_regime_aware(args, train_rows, candles, horizons, output, provenance)

            print(f"[MH] training {len(horizons)} horizon models ({args.model_family}, weighting={args.weighting}) ...")
            print("[MH] NOTE: flat mode trains on the long-side profitability target; the model")
            print("[MH]       cannot price shorts, so Kelly will refuse SELL entries. Use")
            print("[MH]       --regime-aware for a two-sided, regime-routed pilot.")
            adapter = ensemble_mod.fit_multi_horizon_ensemble(
                train_rows,
                candles,
                list(dataset.FEATURE_NAMES),
                horizons=horizons,
                model_family=args.model_family,
                label_threshold=args.label_threshold,
                tp_pct=args.tp_pct,
                sl_pct=args.sl_pct,
                weighting=args.weighting,
            )

            output.mkdir(parents=True, exist_ok=True)
            (output / "model.json").write_text(json.dumps(adapter.as_dict()), encoding="utf-8")
            summary = {
                "model_family": adapter.model_family,
                "regime_aware": False,
                "horizons": list(adapter.horizons),
                "weights": list(adapter.weights),
                "target": "profitability",
                # Provenance: the raw window, the rows left after trimming the
                # label lookahead, and how many of those clear feature warmup.
                # The last number is the ceiling on what actually trained --
                # fit_multi_horizon_ensemble further reserves a validation tail
                # and a max(horizons) purge gap.
                **provenance,
            }
            (output / "multi_horizon_summary.json").write_text(
                json.dumps(backtest.json_safe(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print("BTCUSDT multi-horizon training complete")
            print(f"horizons={list(adapter.horizons)}")
            print(f"weights={[round(w, 4) for w in adapter.weights]}")
            print(f"artifacts={output}")
            return 0
        except (OSError, RuntimeError, ValueError) as error:
            print(f"multi-horizon training failed: {error}", file=sys.stderr)
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
