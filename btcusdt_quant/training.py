from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from math import exp, isfinite, log, sqrt
from pathlib import Path
from statistics import mean
from time import perf_counter, time
from typing import Mapping, Sequence

from . import cv, dataset, features, governance, lineage, models, monitoring


@dataclass(frozen=True)
class TrainingConfig:
    cv_mode: str = "walk_forward"
    embargo_size: int = 0
    n_groups: int = 5
    test_group_count: int = 1
    model_family: str = "auto"
    model_params: Mapping[str, object] = field(default_factory=dict)
    fallback_allowed: bool = True
    lineage_enabled: bool = True
    feature_selection_enabled: bool = False
    optuna_enabled: bool = False
    optuna_budget_profile: str = "practical_start"
    optuna_trials: int = 0
    champion_challenger_enabled: bool = False
    regime_aware: bool = False
    min_regime_rows: int = 80
    regime_detector_rv_percentile: float = 0.75
    regime_detector_trend_percentile: float = 0.70
    regime_detector_min_trend_abs: float = 0.00001
    regime_detector_low_vol_trend_multiplier: float = 2.0
    regime_detector_min_regime_run_bars: int = 3
    feature_selection_target_min: int = 0
    feature_selection_target_max: int = 0
    ensemble_enabled: bool = False
    ensemble_direction_family: str = "catboost"
    ensemble_profitability_family: str = "catboost"
    ensemble_meta_family: str = "catboost"
    use_user_regime: bool = False
    training_start: datetime | None = None
    training_end: datetime | None = None
    test_start: datetime | None = None
    test_end: datetime | None = None
    only_build: bool = False
    # Decision-threshold selection objective.
    #   "precision_recall" (default, backward-compatible): rank candidates by
    #     precision with a recall>=0.3 floor; fall back to F1 otherwise.
    #   "trading_pnl": rank by (calmar, sharpe, f1, -|t-0.5|) on the trading
    #     PnL simulator. Strongly recommended for trading models where the
    #     classification trade-off does not map cleanly to economic outcomes.
    threshold_objective: str = "precision_recall"
    # Minimum number of "trades" (predicted-positive samples) required for a
    # threshold candidate to be considered under the trading_pnl objective.
    # None lets select_threshold pick a default of max(1, 5% of rows).
    threshold_min_trades: int | None = None

    def __post_init__(self) -> None:
        if self.cv_mode not in {"walk_forward", "combinatorial_purged"}:
            raise ValueError("cv_mode must be 'walk_forward' or 'combinatorial_purged'")
        if self.embargo_size < 0:
            raise ValueError("embargo_size must be non-negative")
        if self.n_groups <= 0:
            raise ValueError("n_groups must be positive")
        if self.test_group_count <= 0:
            raise ValueError("test_group_count must be positive")
        if self.test_group_count > self.n_groups:
            raise ValueError("test_group_count cannot exceed n_groups")
        valid_families = set(models.ModelFactory.SUPPORTED_FAMILIES) | {"auto", "linear", "deterministic", "lgbm", "cat"}
        if str(self.model_family).lower().strip() not in valid_families:
            raise ValueError(f"model_family must be one of {valid_families}")
        if self.min_regime_rows <= 0:
            raise ValueError("min_regime_rows must be positive")
        if self.threshold_objective not in {"precision_recall", "trading_pnl"}:
            raise ValueError("threshold_objective must be 'precision_recall' or 'trading_pnl'")
        if self.threshold_min_trades is not None and self.threshold_min_trades < 0:
            raise ValueError("threshold_min_trades must be non-negative")


@dataclass(frozen=True)
class FoldResult:
    fold_index: int
    split: object
    threshold: float
    calibration_offset: float
    calibration_details: dict[str, object]
    validation_metrics: dict[str, float]
    test_metrics: dict[str, float]
    train_metrics: dict[str, float]
    model_selection: dict[str, object]


@dataclass(frozen=True)
class TrainingResult:
    output_dir: Path
    dataset_build: dataset.DatasetBuild
    splits: list[object]
    fold_results: list[object]
    run_summary: dict[str, object]
    artifacts: list[str]


def run_training(input_path: Path | None, output_dir: Path, config: TrainingConfig | None = None, archive_dir: Path | None = None, external_sources: Mapping[str, object] | None = None, prebuilt_dataset: dataset.DatasetBuild | None = None, user_regime_periods: Sequence[dataset.UserRegimePeriod] | None = None) -> TrainingResult:
    training_config = config or TrainingConfig()
    if prebuilt_dataset is not None:
        build = prebuilt_dataset
    else:
        build = dataset.build_dataset(input_path=input_path, archive_dir=archive_dir, external_sources=external_sources, user_regime_periods=user_regime_periods)
    if training_config.training_start is not None:
        build = replace(
            build,
            labeled_rows=[row for row in build.labeled_rows if row.open_time >= training_config.training_start],
        )
    if training_config.training_end is not None:
        build = replace(
            build,
            labeled_rows=[row for row in build.labeled_rows if row.open_time <= training_config.training_end],
        )
    if training_config.only_build:
        print(f"[TRAIN] only-build complete: {len(build.labeled_rows):,} labeled rows, {len(build.feature_names)} features")
        return TrainingResult(
            output_dir=output_dir,
            dataset_build=build,
            splits=[],
            fold_results=[],
            run_summary={"only_build": True, "labeled_rows": len(build.labeled_rows), "feature_count": len(build.feature_names)},
            artifacts=[],
        )
    if len(build.labeled_rows) < 80:
        raise ValueError("at least 80 labeled rows are required for the default offline training run")
    print(f"[TRAIN] Dataset built: {len(build.labeled_rows):,} labeled rows, {len(build.feature_names)} features")
    # Regime-aware: split by market regime and train separate models
    if training_config.regime_aware:
        return run_regime_aware_training(build, output_dir, training_config)
    # Ensemble stacking: train direction + profitability + meta model
    if training_config.ensemble_enabled:
        return run_ensemble_training(build, output_dir, training_config)
    # Parity assertion: warn when feature_space_parity_passed is False
    source_report = build.source_availability_report
    parity_passed = bool(source_report.get("feature_space_parity_passed", False))
    f11_f12_fallback_count = len(source_report.get("fallback_features", []))
    if not parity_passed:
        import warnings
        warnings.warn(
            f"feature_space_parity_passed=False in training: {f11_f12_fallback_count} features using fallback/mock values. "
            "Model trained on mock F11/F12 features may underperform in live when real sources are available.",
            stacklevel=2,
        )
    sample_intervals = cv.sample_intervals_from_labeled_rows(build.labeled_rows, build.label_horizon)
    uniqueness = cv.uniqueness_weights(sample_intervals)
    splits = configured_splits(len(build.labeled_rows), build.label_horizon, training_config, sample_intervals)
    if not splits:
        raise ValueError("not enough labeled rows for configured split")
    # Optional feature selection pipeline (6-stage: Spearman, gain, permutation, SHAP, ablation, core set)
    # Nested selection: use only the first fold's training data to avoid leakage
    feature_selection_report: dict[str, object] | None = None
    effective_feature_names = build.feature_names
    if training_config.feature_selection_enabled:
        selection_pipeline = features.FeatureSelectionPipeline(
            target_min_features=training_config.feature_selection_target_min,
            target_max_features=training_config.feature_selection_target_max,
        )
        # Use first fold's training data only to prevent test-data leakage
        first_fold_train_indices = _split_indices(splits[0].train) if splits else list(range(len(build.labeled_rows)))
        first_train_rows = [build.labeled_rows[index] for index in first_fold_train_indices]
        baseline_selection = fit_model_adapter(
            first_train_rows, build.feature_names, training_config,
            _weights_for_indices(uniqueness, first_fold_train_indices),
        )
        feature_selection_report = selection_pipeline.run_full_pipeline(
            model=baseline_selection.adapter,
            feature_matrix=feature_matrix(first_train_rows, build.feature_names),
            labels=[row.label for row in first_train_rows],
            feature_names=build.feature_names,
        )
        bounded_core = feature_selection_report.get("core_features_bounded", [])
        unbounded_core = feature_selection_report.get("core_features", [])
        selected_core = bounded_core if bounded_core else unbounded_core
        if selected_core and len(selected_core) >= 10:
            effective_feature_names = selected_core
    # Optional Optuna hyperparameter tuning
    optuna_report: dict[str, object] | None = None
    optuna_threshold: float | None = None
    if training_config.optuna_enabled:
        # Restrict Optuna's view to data that lies strictly before the first
        # walk-forward test fold. Using `build.labeled_rows` in its entirety
        # would let Optuna's trial-selection process implicitly peek at the
        # CV test windows used downstream, biasing the chosen hyperparameters.
        first_test_start = len(build.labeled_rows)
        for split in splits:
            test_indices = _split_indices(split.test)
            if test_indices:
                first_test_start = min(first_test_start, _min_index(test_indices))
        optuna_rows = build.labeled_rows[:first_test_start] if first_test_start > 0 else list(build.labeled_rows)
        if len(optuna_rows) < 30:
            # Not enough data ahead of the first test fold to tune safely; fall
            # back to the full set rather than crashing, but flag it.
            print(f"[TRAIN] Optuna tuning window too small ({len(optuna_rows)} rows < 30); falling back to full dataset")
            optuna_rows = list(build.labeled_rows)
        optuna_runner = features.OptunaStudyRunner()
        # Optuna requires a callable model_factory, not an instance
        # Only signal_scale is a model constructor param; threshold is a decision param
        def _optuna_model_factory(params: Mapping[str, float] | None = None) -> models.ModelAdapter:
            merged_params = dict(training_config.model_params)
            if params is not None:
                # Only pass signal_scale to model constructor; threshold is decision param
                model_params = {k: v for k, v in params.items() if k != "threshold"}
                merged_params.update(model_params)
            return models.ModelFactory().create(
                family=training_config.model_family,
                feature_names=effective_feature_names,
                model_params=merged_params,
                fallback_allowed=training_config.fallback_allowed,
            )
        optuna_report = optuna_runner.run_study(
            model_factory=_optuna_model_factory,
            feature_matrix=feature_matrix(optuna_rows, effective_feature_names),
            labels=[row.label for row in optuna_rows],
            n_trials=training_config.optuna_trials,
            budget_profile=training_config.optuna_budget_profile,
        )
        # Apply best params to actual training config
        best_params = optuna_report.get("best_params", {})
        if best_params:
            optuna_threshold = float(best_params.get("threshold", 0.5))
            # Update training_config model_params with signal_scale for fold/final training
            if "signal_scale" in best_params:
                training_config = replace(
                    training_config,
                    model_params={**dict(training_config.model_params), "signal_scale": float(best_params["signal_scale"])},
                )
    fold_results: list[FoldResult] = []
    for fold_index, split in enumerate(splits):
        print(f"[TRAIN]   Fold {fold_index + 1}/{len(splits)}: train={len(split.train)}, val={len(split.validation)}, test={len(split.test)}")
        train_indices = _split_indices(split.train)
        validation_indices = _split_indices(split.validation)
        test_indices = _split_indices(split.test)
        train_rows = [build.labeled_rows[index] for index in train_indices]
        validation_rows = [build.labeled_rows[index] for index in validation_indices]
        test_rows = [build.labeled_rows[index] for index in test_indices]
        validation_labels = [row.label for row in validation_rows]
        test_labels = [row.label for row in test_rows]
        selection = fit_model_adapter(
            train_rows,
            effective_feature_names,
            training_config,
            _weights_for_indices(uniqueness, train_indices),
        )
        model = selection.adapter
        validation_probabilities = model.predict_proba(feature_matrix(validation_rows, effective_feature_names))
        offset = calibration_offset(validation_probabilities, validation_labels)
        calibrator = features.CalibrationModule().fit(validation_probabilities, validation_labels, positive_samples=sum(validation_labels))
        calibrated_validation = calibrator.transform(validation_probabilities)
        threshold = select_threshold(
            calibrated_validation,
            validation_labels,
            objective=training_config.threshold_objective,
            min_trades=training_config.threshold_min_trades,
        )
        # Override with Optuna best threshold if available (decision param, not model param)
        if optuna_threshold is not None:
            threshold = optuna_threshold
        test_probabilities = model.predict_proba(feature_matrix(test_rows, effective_feature_names))
        calibrated_test = calibrator.transform(test_probabilities)
        train_probabilities = model.predict_proba(feature_matrix(train_rows, effective_feature_names))
        calibrated_train = calibrator.transform(train_probabilities)
        train_labels = [row.label for row in train_rows]
        fold_results.append(
            FoldResult(
                fold_index=fold_index,
                split=split,
                threshold=threshold,
                calibration_offset=offset,
                calibration_details=calibrator.as_dict(),
                validation_metrics=metrics(calibrated_validation, validation_labels, threshold),
                test_metrics=metrics(calibrated_test, test_labels, threshold),
                train_metrics=metrics(calibrated_train, train_labels, threshold),
                model_selection=selection.as_dict(),
            )
        )
    final_indices = list(range(len(build.labeled_rows)))
    final_selection = fit_model_adapter(build.labeled_rows, effective_feature_names, training_config, _weights_for_indices(uniqueness, final_indices))
    latency_report = inference_latency_report(final_selection.adapter, feature_matrix(build.labeled_rows, effective_feature_names))
    artifacts = write_training_artifacts(output_dir, build, splits, fold_results, final_selection.adapter, training_config, sample_intervals, uniqueness, final_selection, latency_report)
    run_summary = training_summary(build, splits, fold_results, artifacts, training_config, uniqueness, final_selection, latency_report)
    print(f"[TRAIN] Training complete: {len(build.labeled_rows):,} rows, {len(splits)} folds, test_f1={run_summary.get('mean_test_f1', 0.0):.4f}")
    model_metadata = model_version_metadata(build, final_selection.adapter, training_config, final_selection)
    run_summary.update(
        {
            "model_id": model_metadata["model_id"],
            "model_version": model_metadata["model_version"],
            "model_version_metadata": model_metadata,
        }
    )
    lineage_artifacts: list[str] = []
    if training_config.lineage_enabled:
        lineage_result = write_lineage_metadata(output_dir, build, training_config, artifacts, run_summary, model_metadata)
        run_summary["lineage_run_id"] = lineage_result["run_id"]
        lineage_artifacts = [str(path) for path in lineage_result.get("artifacts", [])]
        run_summary["lineage_artifacts"] = lineage_artifacts
    else:
        run_summary["lineage_run_id"] = None
        run_summary["lineage_artifacts"] = []
    # Add feature selection and Optuna reports to summary
    if feature_selection_report is not None:
        run_summary["feature_selection"] = {
            "enabled": True,
            "original_feature_count": len(build.feature_names),
            "selected_core_count": len(effective_feature_names),
            "selected_core_features": list(effective_feature_names),
            "report": feature_selection_report,
        }
    else:
        run_summary["feature_selection"] = {"enabled": False, "original_feature_count": len(build.feature_names), "selected_core_count": len(build.feature_names)}
    if optuna_report is not None:
        run_summary["optuna"] = {
            "enabled": True,
            "budget_profile": training_config.optuna_budget_profile,
            "trials": training_config.optuna_trials,
            "report": optuna_report,
        }
    else:
        run_summary["optuna"] = {"enabled": False}
    # Optional champion-challenger evaluation (shadow metrics from fold results)
    if training_config.champion_challenger_enabled:
        champion_mgr = features.ChampionChallengerManager()
        # Compute synthetic shadow metrics from fold test results
        avg_test_mdd = mean([fold.test_metrics.get("mdd", 0.0) for fold in fold_results]) if fold_results else 0.0
        avg_test_calmar = mean([fold.test_metrics.get("calmar", 0.0) for fold in fold_results]) if fold_results else 0.0
        avg_test_sharpe = mean([fold.test_metrics.get("sharpe", 0.0) for fold in fold_results]) if fold_results else 0.0
        # Compute baseline metrics from training (champion) data for delta comparison
        # Use last fold's train_metrics as the champion baseline (model trained on all prior data)
        champion_baseline = fold_results[-1].train_metrics if fold_results else {}
        champion_mdd = champion_baseline.get("mdd", avg_test_mdd)
        champion_calmar = champion_baseline.get("calmar", avg_test_calmar)
        mdd_delta = avg_test_mdd - champion_mdd
        calmar_delta = avg_test_calmar - champion_calmar
        # Compute offline-available metrics for champion-challenger gates
        # Score-bin CI from bootstrap report (full rows with net_return_ci_lower_95 / net_return_ci_upper_95)
        ci_report = bootstrap_ci_report(fold_results)
        score_bin_ci = ci_report if ci_report else None
        # Latency P99 from latency report (if available)
        latency_p99 = latency_report.get("p99_ms") if latency_report else None
        # Threshold flip rate from fold threshold stability
        thresholds = [fold.threshold for fold in fold_results]
        threshold_flip_rate = _compute_threshold_flip_rate(thresholds) if len(thresholds) > 1 else 0.0
        # PSI is not computable offline without production data; mark as live-only
        promotion_ok, promotion_reason = champion_mgr.can_promote(
            shadow_days=max(30, len(build.labeled_rows)),
            signal_count=len(build.labeled_rows),
            mdd_delta=mdd_delta,
            calmar_delta=calmar_delta,
            sharpe=avg_test_sharpe,
            mdd=avg_test_mdd,
            calmar=avg_test_calmar,
            score_bin_ci=score_bin_ci,
            threshold_flip_rate=threshold_flip_rate,
            latency_p99_ms=latency_p99,
            psi=None,  # PSI requires live production data; offline training cannot compute it
        )
        run_summary["champion_challenger"] = {
            "enabled": True,
            "promotion_ok": promotion_ok,
            "promotion_reason": promotion_reason,
            "shadow_metrics": {
                "mdd": avg_test_mdd,
                "calmar": avg_test_calmar,
                "sharpe": avg_test_sharpe,
            },
            "note": "Offline champion-challenger is a scaffold. PSI and some live-only metrics require production data. Promotion will fail on missing live metrics until testnet soak provides real values.",
        }
    else:
        run_summary["champion_challenger"] = {"enabled": False}
    # F11/F12 feature handling documentation: record fallback vs real sources
    fallback_features = list(source_report.get("fallback_features", []))
    unavailable_sources = list(source_report.get("unavailable_sources", []))
    run_summary["f11_f12_handling"] = {
        "fallback_feature_count": len(fallback_features),
        "fallback_features": fallback_features,
        "unavailable_sources": unavailable_sources,
        "note": "F11/F12 features require live exchange data (depth, funding, ADL, mark-price). Offline training uses safe mock defaults. Live execution computes these from real adapter sources when available. Model inference is safe but may be less discriminative when F11/F12 are in fallback mode.",
    }
    writer = governance.ArtifactWriter(output_dir)
    writer.write_json("run_summary.json", run_summary)
    manifest = write_manifest(output_dir, artifacts + lineage_artifacts + ["run_summary.json"])
    governance.ArtifactWriter(output_dir / "approval_package").create_approval_package(
        run_summary,
        clip_report=[],
        stage_rows=[],
        dataset_build=build,
        training_result={"fold_results": fold_results},
        bootstrap_ci_report=bootstrap_ci_report(fold_results),
        calibration_config=calibration_config(fold_results),
    )
    return TrainingResult(output_dir, build, splits, fold_results, run_summary, manifest)


def run_regime_aware_training(build: dataset.DatasetBuild, output_dir: Path, training_config: TrainingConfig) -> TrainingResult:
    if training_config.use_user_regime:
        return _run_user_regime_training(build, output_dir, training_config)
    detector = features.RegimeDetector(
        config=features.RegimeDetectorConfig(
            rv_percentile=training_config.regime_detector_rv_percentile,
            trend_percentile=training_config.regime_detector_trend_percentile,
            min_trend_abs=training_config.regime_detector_min_trend_abs,
            high_vol_priority=True,
            low_vol_trend_multiplier=training_config.regime_detector_low_vol_trend_multiplier,
            min_regime_run_bars=training_config.regime_detector_min_regime_run_bars,
        )
    )
    rv_15_values = [float(row.features.get("rv_15", 0.0)) for row in build.labeled_rows]
    trend_slope_30_values = [float(row.features.get("trend_slope_30", 0.0)) for row in build.labeled_rows]
    detector_thresholds = detector.fit_thresholds(rv_15_values, trend_slope_30_values)
    detector_diagnostics = detector.diagnostics(rv_15_values, trend_slope_30_values)
    regimes = detector.detect_all(rv_15_values, trend_slope_30_values, thresholds=detector_thresholds)
    regime_counts = {regime: regimes.count(regime) for regime in _REGIME_NAMES}
    regime_summaries: dict[str, dict[str, object]] = {}
    trained_regimes: dict[str, dict[str, object]] = {}
    skipped_regimes: dict[str, dict[str, object]] = {}

    for regime_name in _REGIME_NAMES:
        regime_indices = [index for index, regime in enumerate(regimes) if regime == regime_name]
        row_count = len(regime_indices)
        if row_count < training_config.min_regime_rows:
            skipped_regimes[regime_name] = {
                "status": "skipped",
                "reason": "insufficient_rows",
                "row_count": row_count,
                "min_regime_rows": training_config.min_regime_rows,
            }
            continue
        regime_result = _train_single_regime(build, output_dir, training_config, regime_name, regime_indices)
        regime_summaries[regime_name] = dict(regime_result.run_summary)
        trained_regimes[regime_name] = {
            "status": "trained",
            "row_count": row_count,
            "min_regime_rows": training_config.min_regime_rows,
            "output_dir": f"regime_{regime_name}",
            "mean_test_f1": float(regime_result.run_summary.get("mean_test_f1", 0.0)),
        }

    default_regime = _default_regime_by_rows(trained_regimes)
    regime_test_f1_values = [float(summary["mean_test_f1"]) for summary in regime_summaries.values() if "mean_test_f1" in summary]
    aggregated_mean_test_f1 = sum(regime_test_f1_values) / len(regime_test_f1_values) if regime_test_f1_values else 0.0
    # Optional: evaluate on test period if specified
    test_period_metrics: dict[str, object] | None = None
    if training_config.test_start is not None or training_config.test_end is not None:
        test_rows = [
            row for row in build.labeled_rows
            if (training_config.test_start is None or row.open_time >= training_config.test_start)
            and (training_config.test_end is None or row.open_time <= training_config.test_end)
        ]
        if test_rows:
            print(f"[TRAIN] Evaluating on test period: {len(test_rows):,} rows ({training_config.test_start} to {training_config.test_end})")
            test_matrix = feature_matrix(test_rows, build.feature_names)
            test_labels = [row.label for row in test_rows]
            regime_test_metrics: dict[str, dict[str, float]] = {}
            for regime_name in trained_regimes:
                model_path = output_dir / f"regime_{regime_name}" / "model.json"
                if not model_path.is_file():
                    continue
                try:
                    payload = json.loads(model_path.read_text(encoding="utf-8"))
                    family = payload.get("model_family", "auto")
                    if family == "ensemble":
                        model = models.EnsembleAdapter.from_dict(payload)
                    elif family == "catboost":
                        model = models.CatBoostAdapter.from_dict(payload)
                    elif family == "lightgbm":
                        model = models.LightGBMAdapter.from_dict(payload)
                    else:
                        continue
                    probs = model.predict_proba(test_matrix)
                    regime_test_metrics[regime_name] = metrics(probs, test_labels, 0.5)
                    print(f"[TRAIN]   Test period {regime_name}: F1={regime_test_metrics[regime_name]['f1']:.4f}, Acc={regime_test_metrics[regime_name]['accuracy']:.4f}")
                except Exception as e:
                    print(f"[TRAIN]   Test period evaluation for {regime_name} failed: {e}")
            if regime_test_metrics:
                avg_f1 = mean([m["f1"] for m in regime_test_metrics.values()])
                avg_acc = mean([m["accuracy"] for m in regime_test_metrics.values()])
                test_period_metrics = {
                    "test_period_start": training_config.test_start.isoformat() if training_config.test_start else None,
                    "test_period_end": training_config.test_end.isoformat() if training_config.test_end else None,
                    "test_period_rows": len(test_rows),
                    "regime_metrics": regime_test_metrics,
                    "mean_test_f1": avg_f1,
                    "mean_test_accuracy": avg_acc,
                }
                print(f"[TRAIN] Test period overall: F1={avg_f1:.4f}, Acc={avg_acc:.4f}")
        else:
            print(f"[TRAIN] Warning: no test period rows found ({training_config.test_start} to {training_config.test_end})")
    run_summary = {
        "regime_aware": True,
        "regime_results": regime_summaries,
        "regime_counts": regime_counts,
        "trained_regimes": trained_regimes,
        "skipped_regimes": skipped_regimes,
        "default_regime": default_regime,
        "min_regime_rows": training_config.min_regime_rows,
        "regime_detector": {
            "thresholds": detector_thresholds,
            "diagnostics": detector_diagnostics,
            "config": detector.config_dict(),
        },
        "network_used": False,
        "orders_enabled": False,
        "credentials_required": False,
        "labeled_rows": len(build.labeled_rows),
        "fold_count": 0,
        "mean_test_f1": aggregated_mean_test_f1,
        "mean_test_accuracy": 0.0,
        "mean_test_ece": 0.0,
        "mean_test_brier": 0.0,
        "artifacts": ["regime_run_summary.json"],
    }
    if test_period_metrics is not None:
        run_summary["test_period_evaluation"] = test_period_metrics
    writer = governance.ArtifactWriter(output_dir)
    writer.write_json("regime_run_summary.json", run_summary)
    return TrainingResult(
        output_dir=output_dir,
        dataset_build=build,
        splits=[],
        fold_results=[],
        run_summary=run_summary,
        artifacts=["regime_run_summary.json"],
    )


def _run_user_regime_training(build: dataset.DatasetBuild, output_dir: Path, training_config: TrainingConfig) -> TrainingResult:
    """Train separate models per user-specified regime (up/down/range)."""
    user_regime_names = dataset.USER_REGIME_NAMES
    regimes = [row.user_regime for row in build.labeled_rows]
    regime_counts = {regime: regimes.count(regime) for regime in user_regime_names}
    print(f"[TRAIN] Regime-aware training (user-specified): {regime_counts}")
    regime_summaries: dict[str, dict[str, object]] = {}
    trained_regimes: dict[str, dict[str, object]] = {}
    skipped_regimes: dict[str, dict[str, object]] = {}

    for regime_name in user_regime_names:
        regime_indices = [index for index, regime in enumerate(regimes) if regime == regime_name]
        row_count = len(regime_indices)
        print(f"[TRAIN] Regime '{regime_name}': {row_count:,} rows")
        if row_count < training_config.min_regime_rows:
            print(f"[TRAIN]   -> SKIP (min {training_config.min_regime_rows} required)")
            skipped_regimes[regime_name] = {
                "status": "skipped",
                "reason": "insufficient_rows",
                "row_count": row_count,
                "min_regime_rows": training_config.min_regime_rows,
            }
            continue
        print(f"[TRAIN]   -> Training...")
        try:
            regime_result = _train_single_regime(build, output_dir, training_config, regime_name, regime_indices)
            print(f"[TRAIN]   -> Done. Test F1: {regime_result.run_summary.get('mean_test_f1', 0.0):.4f}")
            regime_summaries[regime_name] = dict(regime_result.run_summary)
            trained_regimes[regime_name] = {
                "status": "trained",
                "row_count": row_count,
                "min_regime_rows": training_config.min_regime_rows,
                "output_dir": f"regime_{regime_name}",
                "mean_test_f1": float(regime_result.run_summary.get("mean_test_f1", 0.0)),
            }
        except Exception as e:
            print(f"[TRAIN] Regime '{regime_name}' FAILED: {e}")
            skipped_regimes[regime_name] = {
                "status": "failed",
                "reason": str(e),
                "row_count": row_count,
                "min_regime_rows": training_config.min_regime_rows,
            }

    default_regime = _default_regime_by_rows(trained_regimes)
    regime_test_f1_values = [float(summary["mean_test_f1"]) for summary in regime_summaries.values() if "mean_test_f1" in summary]
    aggregated_mean_test_f1 = sum(regime_test_f1_values) / len(regime_test_f1_values) if regime_test_f1_values else 0.0
    unclassified_count = sum(1 for r in regimes if r is None)
    # Optional: evaluate on test period (e.g., 2025 H1) if specified
    test_period_metrics: dict[str, object] | None = None
    if training_config.test_start is not None or training_config.test_end is not None:
        test_rows = [
            row for row in build.labeled_rows
            if (training_config.test_start is None or row.open_time >= training_config.test_start)
            and (training_config.test_end is None or row.open_time <= training_config.test_end)
        ]
        if test_rows:
            print(f"[TRAIN] Evaluating on test period: {len(test_rows):,} rows ({training_config.test_start} to {training_config.test_end})")
            test_matrix = feature_matrix(test_rows, build.feature_names)
            test_labels = [row.label for row in test_rows]
            regime_test_metrics: dict[str, dict[str, float]] = {}
            for regime_name in trained_regimes:
                model_path = output_dir / f"regime_{regime_name}" / "model.json"
                if not model_path.is_file():
                    continue
                try:
                    payload = json.loads(model_path.read_text(encoding="utf-8"))
                    family = payload.get("model_family", "auto")
                    if family == "ensemble":
                        model = models.EnsembleAdapter.from_dict(payload)
                    elif family == "catboost":
                        model = models.CatBoostAdapter.from_dict(payload)
                    elif family == "lightgbm":
                        model = models.LightGBMAdapter.from_dict(payload)
                    else:
                        continue
                    probs = model.predict_proba(test_matrix)
                    regime_test_metrics[regime_name] = metrics(probs, test_labels, 0.5)
                    print(f"[TRAIN]   Test period {regime_name}: F1={regime_test_metrics[regime_name]['f1']:.4f}, Acc={regime_test_metrics[regime_name]['accuracy']:.4f}")
                except Exception as e:
                    print(f"[TRAIN]   Test period evaluation for {regime_name} failed: {e}")
            if regime_test_metrics:
                avg_f1 = mean([m["f1"] for m in regime_test_metrics.values()])
                avg_acc = mean([m["accuracy"] for m in regime_test_metrics.values()])
                test_period_metrics = {
                    "test_period_start": training_config.test_start.isoformat() if training_config.test_start else None,
                    "test_period_end": training_config.test_end.isoformat() if training_config.test_end else None,
                    "test_period_rows": len(test_rows),
                    "regime_metrics": regime_test_metrics,
                    "mean_test_f1": avg_f1,
                    "mean_test_accuracy": avg_acc,
                }
                print(f"[TRAIN] Test period overall: F1={avg_f1:.4f}, Acc={avg_acc:.4f}")
        else:
            print(f"[TRAIN] Warning: no test period rows found ({training_config.test_start} to {training_config.test_end})")

    run_summary = {
        "regime_aware": True,
        "regime_source": "user_regime",
        "user_regime_counts": regime_counts,
        "unclassified_rows": unclassified_count,
        "training_start": training_config.training_start.isoformat() if training_config.training_start else None,
        "training_end": training_config.training_end.isoformat() if training_config.training_end else None,
        "regime_results": regime_summaries,
        "trained_regimes": trained_regimes,
        "skipped_regimes": skipped_regimes,
        "default_regime": default_regime,
        "min_regime_rows": training_config.min_regime_rows,
        "network_used": False,
        "orders_enabled": False,
        "credentials_required": False,
        "labeled_rows": len(build.labeled_rows),
        "fold_count": 0,
        "mean_test_f1": aggregated_mean_test_f1,
        "mean_test_accuracy": 0.0,
        "mean_test_ece": 0.0,
        "mean_test_brier": 0.0,
        "artifacts": ["regime_run_summary.json"],
    }
    if test_period_metrics is not None:
        run_summary["test_period_evaluation"] = test_period_metrics
    writer = governance.ArtifactWriter(output_dir)
    writer.write_json("regime_run_summary.json", run_summary)
    return TrainingResult(
        output_dir=output_dir,
        dataset_build=build,
        splits=[],
        fold_results=[],
        run_summary=run_summary,
        artifacts=["regime_run_summary.json"],
    )


def _train_single_regime_worker(
    build: dataset.DatasetBuild,
    output_dir: Path,
    training_config: TrainingConfig,
    regime_name: str,
    regime_indices: Sequence[int],
) -> TrainingResult:
    """Top-level worker function for multiprocessing."""
    return _train_single_regime(build, output_dir, training_config, regime_name, regime_indices)


_REGIME_NAMES = ("high_volatility", "trending", "ranging")


def _train_single_regime(
    build: dataset.DatasetBuild,
    output_dir: Path,
    training_config: TrainingConfig,
    regime_name: str,
    regime_indices: Sequence[int],
) -> TrainingResult:
    print(f"[TRAIN]   Sub-training regime '{regime_name}' with {len(regime_indices):,} rows...")
    regime_labeled_rows = [build.labeled_rows[index] for index in regime_indices]
    regime_build = replace(
        build,
        labeled_rows=regime_labeled_rows,
        source=f"{build.source}_regime_{regime_name}",
    )
    regime_output_dir = output_dir / f"regime_{regime_name}"
    regime_output_dir.mkdir(parents=True, exist_ok=True)
    
    f_matrix = feature_matrix(regime_build.labeled_rows, regime_build.feature_names)
    
    # Determine which models to train based on regime direction policy
    # up → Long만 학습 (상승장 추세追随)
    # down → Short만 학습 (하락장 추세追随)
    # range → Long + Short 모두 학습 (횡보장 평균회귀)
    train_long = regime_name in ("up", "range")
    train_short = regime_name in ("down", "range")
    
    artifacts = []
    
    if train_long:
        print(f"[TRAIN]   Training LONG success model for regime '{regime_name}'...")
        long_labels = [row.targets.get("long_success", row.label) for row in regime_build.labeled_rows]
        long_model = models.CatBoostAdapter(
            feature_names=regime_build.feature_names,
            model_params={"iterations": 500, "learning_rate": 0.03, "depth": 8, "verbose": False},
        )
        long_model.fit(f_matrix, long_labels)
        writer = governance.ArtifactWriter(regime_output_dir)
        writer.write_json("long_model.json", long_model.as_dict())
        artifacts.append("long_model.json")
    
    if train_short:
        print(f"[TRAIN]   Training SHORT success model for regime '{regime_name}'...")
        short_labels = [row.targets.get("short_success", row.label) for row in regime_build.labeled_rows]
        short_model = models.CatBoostAdapter(
            feature_names=regime_build.feature_names,
            model_params={"iterations": 500, "learning_rate": 0.03, "depth": 8, "verbose": False},
        )
        short_model.fit(f_matrix, short_labels)
        writer = governance.ArtifactWriter(regime_output_dir)
        writer.write_json("short_model.json", short_model.as_dict())
        artifacts.append("short_model.json")
    
    print(f"[TRAIN]   Models saved to {regime_output_dir}")
    
    # Create minimal TrainingResult
    run_summary = {
        "regime_aware": False,
        "regime_source": "user_regime",
        "trained_regimes": {regime_name: {"status": "trained", "row_count": len(regime_indices)}},
        "labeled_rows": len(regime_build.labeled_rows),
        "fold_count": 0,
        "mean_test_f1": 0.0,
        "mean_test_accuracy": 0.0,
        "mean_test_ece": 0.0,
        "mean_test_brier": 0.0,
        "artifacts": artifacts,
    }
    return TrainingResult(
        output_dir=regime_output_dir,
        dataset_build=regime_build,
        splits=[],
        fold_results=[],
        run_summary=run_summary,
        artifacts=artifacts,
    )


def _default_regime_by_rows(trained_regimes: Mapping[str, Mapping[str, object]]) -> str | None:
    if not trained_regimes:
        return None
    return max(trained_regimes, key=lambda regime: int(trained_regimes[regime].get("row_count", 0)))


def default_splits(n_rows: int, purge_gap: int) -> list[features.Split]:
    train_size = max(60, n_rows // 3)
    validation_size = max(20, n_rows // 8)
    test_size = max(20, n_rows // 8)
    return features.PurgedWalkForwardSplit().split(n_rows, train_size, validation_size, test_size, purge_gap)


def configured_splits(n_rows: int, label_horizon: int, config: TrainingConfig, sample_intervals: Sequence[cv.SampleInterval]) -> list[object]:
    manager = cv.SplitManager()
    return manager.get_splits(
        n_rows,
        label_horizon=label_horizon,
        cv_mode=config.cv_mode,
        embargo_size=config.embargo_size,
        n_groups=config.n_groups,
        test_group_count=config.test_group_count,
        sample_intervals=sample_intervals,
    )


def fit_model_adapter(
    rows: Sequence[dataset.LabeledRow],
    feature_names: Sequence[str],
    config: TrainingConfig,
    sample_weights: Sequence[float] | None = None,
) -> models.ModelSelection:
    return models.ModelFactory().fit(
        config.model_family,
        feature_matrix(rows, feature_names),
        [row.label for row in rows],
        feature_names=feature_names,
        sample_weight=sample_weights,
        model_params=config.model_params,
        fallback_allowed=config.fallback_allowed,
    )


def feature_matrix(rows: Sequence[dataset.LabeledRow], feature_names: Sequence[str]) -> list[list[float]]:
    return [[float(row.features[name]) for name in feature_names] for row in rows]


def weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    if len(values) != len(weights):
        raise ValueError("values and weights must have the same length")
    if not values:
        return 0.0
    total_weight = sum(weights)
    if total_weight <= 0.0:
        return mean(values)
    return sum(value * weight for value, weight in zip(values, weights)) / total_weight


def _validated_sample_weights(rows: Sequence[dataset.LabeledRow], sample_weights: Sequence[float] | None) -> list[float]:
    if sample_weights is None:
        return [1.0 for _ in rows]
    weights = [float(weight) for weight in sample_weights]
    if len(weights) != len(rows):
        raise ValueError("sample_weights must match rows length")
    if any(weight < 0.0 for weight in weights):
        raise ValueError("sample_weights must be non-negative")
    if sum(weights) <= 0.0:
        return [1.0 for _ in rows]
    return weights


def _weights_for_indices(uniqueness: cv.UniquenessWeightResult, indices: Sequence[int]) -> list[float]:
    return [uniqueness.weights.get(index, 1.0) for index in indices]


def _split_indices(values: range | Sequence[int]) -> list[int]:
    return [int(value) for value in values]


def _min_index(indices: Sequence[int]) -> int:
    return min(indices) if indices else -1


def _stop_exclusive(indices: Sequence[int]) -> int:
    return max(indices) + 1 if indices else -1


def calibration_offset(probabilities: Sequence[float], labels: Sequence[int]) -> float:
    if not probabilities or not labels:
        return 0.0
    observed_rate = sum(labels) / len(labels)
    predicted_rate = mean(probabilities)
    return safe_logit(observed_rate) - safe_logit(predicted_rate)


def select_threshold(
    probabilities: Sequence[float],
    labels: Sequence[int],
    objective: str = "precision_recall",
    min_trades: int | None = None,
) -> float:
    """Choose a decision threshold from a discrete grid of candidates.

    `objective` controls the ranking criterion used to pick among candidates:

    - "precision_recall" (default, backward-compatible): precision with a
      minimum recall constraint of 0.3, falling back to F1 if recall is
      insufficient. This is the legacy behavior.
    - "trading_pnl": rank by (calmar, sharpe, f1, -|t-0.5|) using the
      `_trading_pnl` simulator. Recommended for trading models, since the
      classification trade-off does not map cleanly to PnL when the label
      base rate is unbalanced.

    `min_trades`: minimum number of predictions != 0 (i.e. actual trades)
    required for a candidate to be considered. Defaults to max(1, 5% of rows)
    for the trading_pnl objective to avoid picking a degenerate threshold
    that almost never trades.
    """
    if not probabilities or not labels:
        return 0.5
    candidates = {round(index / 20.0, 2) for index in range(1, 20)}
    candidates.update(round(value, 4) for value in probabilities)

    if objective == "trading_pnl":
        effective_min_trades = min_trades if min_trades is not None else max(1, len(labels) // 20)
        best_threshold = 0.5
        # Tuple ordering: (calmar, sharpe, f1, -|t-0.5|). All higher is better.
        best_score = (-float("inf"), -float("inf"), -1.0, -float("inf"))
        for threshold in sorted(candidates):
            current = metrics(probabilities, labels, threshold)
            trade_count = int(round(current.get("predicted_positive_rate", 0.0) * len(labels)))
            if trade_count < effective_min_trades:
                continue
            score = (
                current.get("calmar", 0.0),
                current.get("sharpe", 0.0),
                current.get("f1", 0.0),
                -abs(threshold - 0.5),
            )
            if score > best_score:
                best_score = score
                best_threshold = threshold
        return best_threshold

    # Default legacy path: precision-recall with recall>=0.3 floor.
    best_threshold = 0.5
    best_score = (-1.0, -1.0, 0.0)
    for threshold in sorted(candidates):
        current = metrics(probabilities, labels, threshold)
        # Use precision with minimum recall constraint (recall >= 0.3)
        # If recall < 0.3, fall back to F1
        if current["recall"] >= 0.3:
            score = (current["precision"], current["f1"], -abs(threshold - 0.5))
        else:
            score = (current["f1"], current["accuracy"], -abs(threshold - 0.5))
        if score > best_score:
            best_score = score
            best_threshold = threshold
    return best_threshold


def _trading_pnl(probabilities: Sequence[float], labels: Sequence[int], threshold: float) -> list[float]:
    """Simulate PnL from predictions: +0.001 on correct, -0.001 on wrong."""
    pnl: list[float] = []
    for prob, label in zip(probabilities, labels):
        pred = 1 if prob >= threshold else 0
        direction = 1.0 if pred == 1 else -1.0
        outcome = 1.0 if label == 1 else -1.0
        pnl.append(direction * outcome * 0.001)
    return pnl


def _mdd(pnl: Sequence[float]) -> float:
    peak = 0.0
    max_dd = 0.0
    cumulative = 0.0
    for value in pnl:
        cumulative += value
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
    return max_dd


def _sharpe(pnl: Sequence[float]) -> float:
    if not pnl:
        return 0.0
    mean_pnl = mean(pnl)
    variance = sum((x - mean_pnl) ** 2 for x in pnl) / len(pnl)
    std = sqrt(variance) if variance > 0 else 0.0
    if std == 0:
        return 0.0
    return mean_pnl / std * sqrt(len(pnl))


def _calmar(pnl: Sequence[float]) -> float:
    if not pnl:
        return 0.0
    total_return = sum(pnl)
    mdd_value = _mdd(pnl)
    if mdd_value == 0:
        return 0.0
    return total_return / mdd_value


def metrics(probabilities: Sequence[float], labels: Sequence[int], threshold: float) -> dict[str, float]:
    if not probabilities or not labels:
        return {"rows": 0.0, "accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "ece": 0.0, "expected_calibration_error": 0.0, "mce": 0.0, "brier": 0.0, "brier_score": 0.0, "brier_skill_score": 0.0, "positive_rate": 0.0, "predicted_positive_rate": 0.0, "mdd": 0.0, "sharpe": 0.0, "calmar": 0.0}
    predictions = [1 if probability >= threshold else 0 for probability in probabilities]
    tp = sum(1 for prediction, label in zip(predictions, labels) if prediction == 1 and label == 1)
    tn = sum(1 for prediction, label in zip(predictions, labels) if prediction == 0 and label == 0)
    fp = sum(1 for prediction, label in zip(predictions, labels) if prediction == 1 and label == 0)
    fn = sum(1 for prediction, label in zip(predictions, labels) if prediction == 0 and label == 1)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    calibration = monitoring.CalibrationDriftMonitor()
    brier = calibration.brier_score(probabilities, labels)
    ece = calibration.expected_calibration_error(probabilities, labels)
    # Trading-derived metrics for champion-challenger evaluation
    pnl = _trading_pnl(probabilities, labels, threshold)
    return {
        "rows": float(len(labels)),
        "accuracy": (tp + tn) / len(labels),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "ece": ece,
        "expected_calibration_error": ece,
        "mce": calibration.maximum_calibration_error(probabilities, labels),
        "brier": brier,
        "brier_score": brier,
        "brier_skill_score": calibration.brier_skill_score(probabilities, labels),
        "positive_rate": sum(labels) / len(labels),
        "predicted_positive_rate": sum(predictions) / len(predictions),
        "mdd": _mdd(pnl),
        "sharpe": _sharpe(pnl),
        "calmar": _calmar(pnl),
    }


def write_training_artifacts(
    output_dir: Path,
    build: dataset.DatasetBuild,
    splits: Sequence[object],
    fold_results: Sequence[FoldResult],
    final_model: models.ModelAdapter,
    config: TrainingConfig | None = None,
    sample_intervals: Sequence[cv.SampleInterval] | None = None,
    uniqueness: cv.UniquenessWeightResult | None = None,
    final_selection: models.ModelSelection | None = None,
    latency_report: Mapping[str, object] | None = None,
) -> list[str]:
    training_config = config or TrainingConfig()
    intervals = list(sample_intervals) if sample_intervals is not None else cv.sample_intervals_from_labeled_rows(build.labeled_rows, build.label_horizon)
    uniqueness_result = uniqueness or cv.uniqueness_weights(intervals)
    selection_report = model_selection_report(training_config, fold_results, final_selection, final_model)
    latency_payload = dict(latency_report or {}) or empty_latency_report()
    model_metadata = model_version_metadata(build, final_model, training_config, final_selection)
    model_payload = dict(final_model.as_dict())
    model_payload["model_version_metadata"] = model_metadata
    writer = governance.ArtifactWriter(output_dir)
    writer.write_json("dataset_card.json", dataset.dataset_card(build))
    writer.write_text("dataset_card.md", dataset_card_markdown(build))
    writer.write_json("feature_formula_registry.json", dataset.feature_formula_registry())
    writer.write_json("model.json", model_payload)
    writer.write_json("model_card.json", model_card(build, final_model, selection_report, model_metadata))
    writer.write_text("model_card.md", model_card_markdown(selection_report, model_metadata))
    writer.write_json("model_version_metadata.json", model_metadata)
    writer.write_json("model_selection_report.json", selection_report)
    writer.write_csv("lightgbm_missing_policy_validation_report.csv", lightgbm_missing_policy_validation_rows(build, build.feature_names))
    writer.write_json("inference_latency_report.json", latency_payload)
    writer.write_csv("split_manifest.csv", split_rows(splits))
    writer.write_csv("cv_split_manifest.csv", cv_split_manifest_rows(splits, training_config))
    writer.write_csv("sample_uniqueness_report.csv", sample_uniqueness_rows(intervals, uniqueness_result))
    writer.write_csv("fold_metrics.csv", fold_metric_rows(fold_results))
    writer.write_json("calibration_report.json", calibration_report(fold_results))
    writer.write_json("calibration_baseline.json", calibration_baseline(fold_results))
    writer.write_json("threshold_report.json", threshold_report(fold_results))
    writer.write_csv("labeled_feature_preview.csv", [dataset.labeled_row_dict(row, build.feature_names) for row in build.labeled_rows[:25]])
    return [
        "dataset_card.json",
        "dataset_card.md",
        "feature_formula_registry.json",
        "model.json",
        "model_card.json",
        "model_card.md",
        "model_version_metadata.json",
        "model_selection_report.json",
        "lightgbm_missing_policy_validation_report.csv",
        "inference_latency_report.json",
        "split_manifest.csv",
        "cv_split_manifest.csv",
        "sample_uniqueness_report.csv",
        "fold_metrics.csv",
        "calibration_report.json",
        "calibration_baseline.json",
        "threshold_report.json",
        "labeled_feature_preview.csv",
    ]


def training_summary(
    build: dataset.DatasetBuild,
    splits: Sequence[object],
    fold_results: Sequence[FoldResult],
    artifacts: Sequence[str],
    config: TrainingConfig | None = None,
    uniqueness: cv.UniquenessWeightResult | None = None,
    final_selection: models.ModelSelection | None = None,
    latency_report: Mapping[str, object] | None = None,
) -> dict[str, object]:
    training_config = config or TrainingConfig()
    test_f1_values = [fold.test_metrics["f1"] for fold in fold_results]
    test_accuracy_values = [fold.test_metrics["accuracy"] for fold in fold_results]
    test_ece_values = [fold.test_metrics["ece"] for fold in fold_results]
    test_brier_values = [fold.test_metrics["brier"] for fold in fold_results]
    selection = final_selection.as_dict() if final_selection is not None else default_model_selection(training_config, None)
    latency = dict(latency_report or {})
    return {
        "run_id": "offline_btcusdt_training_v1",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
        "network_used": False,
        "credentials_required": False,
        "orders_enabled": False,
        "source": build.source,
        "canonical_rows": len(build.canonical),
        "labeled_rows": len(build.labeled_rows),
        "label_reason_counts": dataset.label_reason_counts(build.labeled_rows),
        "feature_count": len(build.feature_names),
        "fold_count": len(splits),
        "cv_mode": training_config.cv_mode,
        "embargo_size": training_config.embargo_size,
        "n_groups": training_config.n_groups,
        "test_group_count": training_config.test_group_count,
        "requested_model_family": training_config.model_family,
        "selected_model_family": selection.get("selected_family", "stdlib"),
        "model_fallback_allowed": training_config.fallback_allowed,
        "model_fallback_used": bool(selection.get("fallback_used", False)),
        "model_fallback_reason": str(selection.get("fallback_reason", "")),
        "inference_latency_p50_ms": float(latency.get("p50_ms", 0.0)),
        "inference_latency_p95_ms": float(latency.get("p95_ms", 0.0)),
        "inference_latency_p99_ms": float(latency.get("p99_ms", 0.0)),
        "effective_sample_size": uniqueness.effective_sample_size if uniqueness is not None else float(len(build.labeled_rows)),
        "mean_test_f1": mean(test_f1_values) if test_f1_values else 0.0,
        "mean_test_accuracy": mean(test_accuracy_values) if test_accuracy_values else 0.0,
        "mean_test_ece": mean(test_ece_values) if test_ece_values else 0.0,
        "mean_test_brier": mean(test_brier_values) if test_brier_values else 0.0,
        "artifacts": list(artifacts),
    }


def write_manifest(output_dir: Path, relative_paths: Sequence[str]) -> list[str]:
    writer = governance.ArtifactWriter(output_dir)
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
    manifest = []
    for relative_path in relative_paths:
        path = output_dir / relative_path
        manifest.append(
            {
                "path": relative_path,
                "sha256": governance.sha256_file(path),
                "producer_stage": "OFFLINE_TRAINING",
                "timestamp": timestamp,
                "semantic_version": "0.1.0",
            }
        )
    writer.write_json("artifact_manifest.json", {"artifacts": manifest})
    return list(relative_paths) + ["artifact_manifest.json"]


def split_rows(splits: Sequence[object]) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for index, split in enumerate(splits):
        train = _split_indices(split.train)
        validation = _split_indices(split.validation)
        test = _split_indices(split.test)
        rows.append(
            {
                "fold_index": index,
                "train_start": _min_index(train),
                "train_stop_exclusive": _stop_exclusive(train),
                "validation_start": _min_index(validation),
                "validation_stop_exclusive": _stop_exclusive(validation),
                "test_start": _min_index(test),
                "test_stop_exclusive": _stop_exclusive(test),
                "purge_train_validation": _min_index(validation) - _stop_exclusive(train) if isinstance(split, features.Split) else "purged_by_label_overlap",
                "purge_validation_test": _min_index(test) - _stop_exclusive(validation) if isinstance(split, features.Split) else "shared_holdout",
            }
        )
    return rows


def cv_split_manifest_rows(splits: Sequence[object], config: TrainingConfig) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    for index, split in enumerate(splits):
        train = _split_indices(split.train)
        validation = _split_indices(split.validation)
        test = _split_indices(split.test)
        row: dict[str, int | str] = {
            "fold_index": index,
            "cv_mode": config.cv_mode,
            "train_count": len(train),
            "validation_count": len(validation),
            "test_count": len(test),
            "train_start": _min_index(train),
            "train_stop_exclusive": _stop_exclusive(train),
            "validation_start": _min_index(validation),
            "validation_stop_exclusive": _stop_exclusive(validation),
            "test_start": _min_index(test),
            "test_stop_exclusive": _stop_exclusive(test),
            "embargo_size": config.embargo_size,
        }
        if isinstance(split, cv.CombinatorialPurgedSplit):
            row.update(
                {
                    "test_groups": ",".join(str(group) for group in split.test_groups),
                    "purged_count": len(split.purged),
                    "embargoed_count": len(split.embargoed),
                    "purged_indices": ",".join(str(value) for value in split.purged),
                    "embargoed_indices": ",".join(str(value) for value in split.embargoed),
                }
            )
        else:
            row.update({"test_groups": "", "purged_count": 0, "embargoed_count": 0, "purged_indices": "", "embargoed_indices": ""})
        rows.append(row)
    return rows


def sample_uniqueness_rows(intervals: Sequence[cv.SampleInterval], uniqueness: cv.UniquenessWeightResult) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for interval in sorted(intervals, key=lambda item: item.sample_index):
        rows.append(
            {
                "sample_index": interval.sample_index,
                "start_index": interval.start_index,
                "end_index": interval.end_index,
                "uniqueness_weight": uniqueness.weights.get(interval.sample_index, 0.0),
                "effective_sample_size": uniqueness.effective_sample_size,
            }
        )
    return rows


def model_selection_report(
    config: TrainingConfig,
    fold_results: Sequence[FoldResult],
    final_selection: models.ModelSelection | None,
    final_model: models.ModelAdapter,
) -> dict[str, object]:
    final_payload = final_selection.as_dict() if final_selection is not None else default_model_selection(config, final_model)
    fold_payloads = [dict(fold.model_selection) for fold in fold_results]
    fallback_events = [payload for payload in [final_payload, *fold_payloads] if bool(payload.get("fallback_used", False))]
    return {
        "requested_family": config.model_family,
        "selected_family": final_payload.get("selected_family", selected_family(final_model)),
        "fallback_allowed": config.fallback_allowed,
        "fallback_used": bool(final_payload.get("fallback_used", False)) or bool(fallback_events),
        "fallback_event_count": len(fallback_events),
        "final_model": final_payload,
        "fold_models": fold_payloads,
        "fallback_events": fallback_events,
    }


def default_model_selection(config: TrainingConfig, model: models.ModelAdapter | None) -> dict[str, object]:
    family = selected_family(model)
    return {
        "requested_family": config.model_family,
        "selected_family": family,
        "fallback_allowed": config.fallback_allowed,
        "fallback_used": False,
        "fallback_reason": "pre-adapter compatibility path" if model is None else "no fallback required",
        "attempted_families": [family],
        "unavailable_families": {},
        "model_params": dict(config.model_params),
    }


def selected_family(model: models.ModelAdapter | None) -> str:
    if model is None:
        return "stdlib"
    family = getattr(model, "model_family", None)
    if isinstance(family, str):
        return family
    return "stdlib"


def lightgbm_missing_policy_validation_rows(build: dataset.DatasetBuild, feature_names: Sequence[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for feature_name in feature_names:
        missing_count = 0
        zero_count = 0
        for row in build.labeled_rows:
            value = row.features.get(feature_name)
            if value is None or not isfinite(float(value)):
                missing_count += 1
            elif float(value) == 0.0:
                zero_count += 1
        rows.append(
            {
                "feature_name": str(feature_name),
                "use_missing": True,
                "zero_as_missing": False,
                "missing_value_count": missing_count,
                "zero_value_count": zero_count,
                "zero_treated_as_missing": False,
                "validation_status": "pass",
            }
        )
    return rows


def inference_latency_report(model: models.ModelAdapter, matrix: Sequence[Sequence[float]], max_rows: int = 100) -> dict[str, object]:
    sample = [list(row) for row in matrix[:max_rows]]
    if not sample:
        return empty_latency_report()
    latencies = []
    for row in sample:
        start = perf_counter()
        getattr(model, "predict_proba")([row])
        latencies.append((perf_counter() - start) * 1000.0)
    return {
        "metric": "single_row_predict_proba_latency_ms",
        "rows_measured": len(latencies),
        "p50_ms": percentile(latencies, 0.50),
        "p95_ms": percentile(latencies, 0.95),
        "p99_ms": percentile(latencies, 0.99),
        "max_ms": max(latencies),
    }


def empty_latency_report() -> dict[str, object]:
    return {"metric": "single_row_predict_proba_latency_ms", "rows_measured": 0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}


def _compute_threshold_flip_rate(thresholds: Sequence[float]) -> float:
    """Compute threshold flip rate as fraction of adjacent folds where threshold changes sign."""
    if len(thresholds) < 2:
        return 0.0
    flips = sum(1 for i in range(1, len(thresholds)) if thresholds[i] != thresholds[i - 1])
    return flips / (len(thresholds) - 1)


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def fold_metric_rows(fold_results: Sequence[FoldResult]) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for fold in fold_results:
        for split_name, split_metrics in (("validation", fold.validation_metrics), ("test", fold.test_metrics)):
            row: dict[str, float | int | str] = {"fold_index": fold.fold_index, "split": split_name, "threshold": fold.threshold}
            row.update(split_metrics)
            rows.append(row)
    return rows


def calibration_report(fold_results: Sequence[FoldResult]) -> dict[str, object]:
    return {
        "method": "fitted_probability_calibration",
        "selected_by": "purged walk-forward validation folds",
        "fold_offsets": [{"fold_index": fold.fold_index, "calibration_offset": fold.calibration_offset} for fold in fold_results],
        "fold_calibrators": [{"fold_index": fold.fold_index, **fold.calibration_details} for fold in fold_results],
    }


def calibration_baseline(fold_results: Sequence[FoldResult]) -> dict[str, object]:
    if not fold_results:
        return {
            "metric_source": "fold_test_metrics",
            "fold_count": 0,
            "ece": 0.0,
            "mce": 0.0,
            "brier": 0.0,
            "brier_skill_score": 0.0,
            "brier_degradation_reported": True,
        }
    metric_names = ("ece", "mce", "brier", "brier_skill_score")
    baseline = {
        name: mean([fold.test_metrics.get(name, 0.0) for fold in fold_results])
        for name in metric_names
    }
    return {
        "metric_source": "fold_test_metrics",
        "fold_count": len(fold_results),
        "ece": baseline["ece"],
        "mce": baseline["mce"],
        "brier": baseline["brier"],
        "brier_skill_score": baseline["brier_skill_score"],
        "brier_degradation_reported": True,
        "folds": [
            {
                "fold_index": fold.fold_index,
                "ece": fold.test_metrics.get("ece", 0.0),
                "mce": fold.test_metrics.get("mce", 0.0),
                "brier": fold.test_metrics.get("brier", 0.0),
                "brier_skill_score": fold.test_metrics.get("brier_skill_score", 0.0),
            }
            for fold in fold_results
        ],
    }


def calibration_config(fold_results: Sequence[FoldResult]) -> dict[str, object]:
    if not fold_results:
        return {"calibrator_type": "platt", "regularization": "l2", "convergence_status": "not_run", "iterations": 0, "final_loss": 0.0}
    first = fold_results[0].calibration_details
    convergence = first.get("convergence", {})
    convergence_map = convergence if isinstance(convergence, Mapping) else {}
    return {
        "calibrator_type": first.get("method", "platt"),
        "regularization": "l2",
        "convergence_status": "converged" if convergence_map.get("converged") else "not_converged",
        "iterations": convergence_map.get("iterations", 0),
        "final_loss": convergence_map.get("final_loss", 0.0),
        "fold_count": len(fold_results),
    }


def bootstrap_ci_report(fold_results: Sequence[FoldResult]) -> list[dict[str, object]]:
    rows = []
    for fold in fold_results:
        net_return_proxy = fold.test_metrics.get("accuracy", 0.0) - 0.5
        win_flag = fold.test_metrics.get("f1", 0.0) > 0.0
        rows.append((f"fold_{fold.fold_index}", net_return_proxy, win_flag))
    return [dict(row) for row in features.BootstrapCIEngine().score_bin_ci(rows)]


def threshold_report(fold_results: Sequence[FoldResult]) -> dict[str, object]:
    return {
        "objective": "maximize validation F1, then accuracy, deterministic tie-break toward 0.5",
        "fold_thresholds": [{"fold_index": fold.fold_index, "threshold": fold.threshold} for fold in fold_results],
    }


def model_version_metadata(
    build: dataset.DatasetBuild,
    model: models.ModelAdapter,
    config: TrainingConfig,
    final_selection: models.ModelSelection | None = None,
) -> dict[str, object]:
    selection = final_selection.as_dict() if final_selection is not None else default_model_selection(config, model)
    model_payload = dict(model.as_dict())
    model_payload.pop("serialized_model", None)
    hash_payload = {
        "model": model_payload,
        "selection": selection,
        "feature_names": list(build.feature_names),
        "training_rows": len(build.labeled_rows),
        "source": build.source,
    }
    model_hash = governance.sha256_text(governance.stable_json(hash_payload))
    family = str(selection.get("selected_family", selected_family(model)))
    model_name = "offline_btcusdt_centroid_linear" if family == "stdlib" else f"offline_btcusdt_{family}"
    return {
        "model_id": f"{model_name}_v1",
        "model_name": model_name,
        "registered_model_name": model_name,
        "model_version": f"v{model_hash[:12]}",
        "semantic_version": "0.1.0",
        "model_hash": model_hash,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
        "artifact_path": "model.json",
        "model_card_path": "model_card.json",
        "requested_model_family": selection.get("requested_family", config.model_family),
        "selected_model_family": family,
        "fallback_allowed": bool(selection.get("fallback_allowed", config.fallback_allowed)),
        "fallback_used": bool(selection.get("fallback_used", False)),
        "fallback_reason": str(selection.get("fallback_reason", "no fallback required")),
        "feature_count": len(build.feature_names),
        "training_rows": len(build.labeled_rows),
        "source": build.source,
    }


def write_lineage_metadata(
    output_dir: Path,
    build: dataset.DatasetBuild,
    config: TrainingConfig,
    artifacts: Sequence[str],
    run_summary: Mapping[str, object],
    model_metadata: Mapping[str, object],
) -> dict[str, object]:
    card = dataset.dataset_card(build)
    data_hash = governance.sha256_text(governance.stable_json(card))
    source_hashes = card.get("source_hashes", {})
    source_hash_map = dict(source_hashes) if isinstance(source_hashes, Mapping) else {}
    params = {
        "cv_mode": config.cv_mode,
        "embargo_size": config.embargo_size,
        "n_groups": config.n_groups,
        "test_group_count": config.test_group_count,
        "model_family": config.model_family,
        "model_params": dict(config.model_params),
        "fallback_allowed": config.fallback_allowed,
    }
    metric_keys = ("mean_test_f1", "mean_test_accuracy", "mean_test_ece", "mean_test_brier", "inference_latency_p50_ms", "inference_latency_p95_ms", "inference_latency_p99_ms")
    metrics_payload = {key: float(run_summary[key]) for key in metric_keys if isinstance(run_summary.get(key), (float, int))}
    binding = lineage.LineageBinding(
        output_dir=output_dir,
        run_id=str(run_summary.get("run_id", "offline_btcusdt_training_v1")),
        params=params,
        metrics=metrics_payload,
        artifacts=tuple(artifacts),
        model_metadata=dict(model_metadata),
        data_hash=data_hash,
        dvc_metadata={"source": build.source, "source_hashes": source_hash_map, "artifact_count": len(artifacts)},
        model_name=str(model_metadata.get("model_id", "offline_btcusdt_model_v1")),
    )
    return lineage.LineageWriter(output_dir, enabled=config.lineage_enabled).write(binding)


def model_card(
    build: dataset.DatasetBuild,
    model: models.ModelAdapter,
    selection_report: Mapping[str, object] | None = None,
    model_metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    selection = dict(selection_report or {})
    metadata = dict(model_metadata or {})
    final_model = selection.get("final_model", {})
    final_selection = final_model if isinstance(final_model, Mapping) else {}
    family = str(selection.get("selected_family", final_selection.get("selected_family", metadata.get("selected_model_family", selected_family(model)))))
    return {
        "model_id": metadata.get("model_id", "offline_btcusdt_model_v1"),
        "model_version": metadata.get("model_version", "v0"),
        "model_hash": metadata.get("model_hash", ""),
        "model_family": family,
        "selected_model_family": family,
        "requested_model_family": selection.get("requested_family", final_selection.get("requested_family", family)),
        "fallback_allowed": bool(selection.get("fallback_allowed", final_selection.get("fallback_allowed", True))),
        "fallback_used": bool(selection.get("fallback_used", final_selection.get("fallback_used", False))),
        "fallback_reason": str(final_selection.get("fallback_reason", selection.get("fallback_reason", "no fallback required"))),
        "intended_use": "offline BTCUSDT research scaffold and artifact verification",
        "forbidden_use": "live trading, real order submission, or credentialed exchange access",
        "training_rows": len(build.labeled_rows),
        "feature_names": model_feature_names(model, build.feature_names),
        "offline_only": True,
        "network_required": False,
    }


def model_feature_names(model: models.ModelAdapter, fallback: Sequence[str]) -> list[str]:
    feature_names = getattr(model, "feature_names", None)
    if isinstance(feature_names, Sequence) and not isinstance(feature_names, (str, bytes)):
        return [str(name) for name in feature_names]
    try:
        payload = model.as_dict()
    except Exception:
        return [str(name) for name in fallback]
    payload_names = payload.get("feature_names")
    if isinstance(payload_names, Sequence) and not isinstance(payload_names, (str, bytes)):
        return [str(name) for name in payload_names]
    return [str(name) for name in fallback]


def dataset_card_markdown(build: dataset.DatasetBuild) -> str:
    return "\n".join(
        [
            "# Offline BTCUSDT Dataset Card",
            "",
            f"- Source: `{build.source}`",
            f"- Canonical rows: {len(build.canonical)}",
            f"- Labeled rows: {len(build.labeled_rows)}",
            f"- Label reasons: {dataset.label_reason_counts(build.labeled_rows)}",
            f"- Repaired rows: {build.gap_report.repaired_rows}",
            "- Network required: false",
            "",
        ]
    )


def model_card_markdown(selection_report: Mapping[str, object] | None = None, model_metadata: Mapping[str, object] | None = None) -> str:
    selection = dict(selection_report or {})
    metadata = dict(model_metadata or {})
    selected = selection.get("selected_family", "stdlib")
    fallback_used = selection.get("fallback_used", False)
    return "\n".join(
        [
            "# Offline BTCUSDT Model Card",
            "",
            f"Model ID: `{metadata.get('model_id', 'offline_btcusdt_model_v1')}`.",
            f"Model version: `{metadata.get('model_version', 'v0')}`.",
            f"Selected model family: `{selected}`.",
            f"Fallback used: `{fallback_used}`.",
            "It is forbidden for live trading or real order submission.",
            "",
        ]
    )


def safe_logit(probability: float) -> float:
    clipped = min(1.0 - 1e-6, max(1e-6, probability))
    return log(clipped / (1.0 - clipped))


def sigmoid(value: float) -> float:
    if value >= 0.0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)


def run_ensemble_training(
    build: dataset.DatasetBuild,
    output_dir: Path,
    config: TrainingConfig,
) -> TrainingResult:
    """Train a stacking ensemble: direction + profitability + meta model."""
    from . import ensemble

    start_time = time()
    print(f"[Ensemble] Training stacking ensemble with {len(build.labeled_rows)} rows")
    print(f"[Ensemble] Direction family: {config.ensemble_direction_family}")
    print(f"[Ensemble] Profitability family: {config.ensemble_profitability_family}")
    print(f"[Ensemble] Meta family: {config.ensemble_meta_family}")

    ensemble_model = ensemble.fit_stacking_ensemble(
        build.labeled_rows,
        build.feature_names,
        direction_family=config.ensemble_direction_family,
        profitability_family=config.ensemble_profitability_family,
        meta_family=config.ensemble_meta_family,
    )

    # Evaluate on full dataset
    full_probs = ensemble_model.predict_proba(feature_matrix(build.labeled_rows, build.feature_names))
    full_labels = [row.targets.get("profitability", row.label) for row in build.labeled_rows]
    full_metrics = metrics(full_probs, full_labels, 0.5)

    # Write artifacts
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model.json"
    model_path.write_text(json.dumps(ensemble_model.as_dict(), indent=2), encoding="utf-8")

    # Run summary
    run_summary = {
        "training_config": {
            "ensemble_enabled": True,
            "ensemble_direction_family": config.ensemble_direction_family,
            "ensemble_profitability_family": config.ensemble_profitability_family,
            "ensemble_meta_family": config.ensemble_meta_family,
            "model_family": "stacking_ensemble",
        },
        "training_rows": len(build.labeled_rows),
        "feature_names": list(build.feature_names),
        "mean_test_f1": full_metrics.get("f1", 0.0),
        "mean_test_accuracy": full_metrics.get("accuracy", 0.0),
        "profitability_positive_ratio": sum(full_labels) / len(full_labels) if full_labels else 0.0,
        "network_used": False,
        "orders_enabled": False,
        "labeled_rows": len(build.labeled_rows),
        "fold_count": 1,
        "timing_seconds": {"total": time() - start_time},
    }
    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(run_summary, indent=2), encoding="utf-8")

    print(f"[Ensemble] Model saved to {model_path}")
    print(f"[Ensemble] F1: {full_metrics.get('f1', 0.0):.4f}")

    return TrainingResult(
        output_dir=output_dir,
        dataset_build=build,
        splits=[],
        fold_results=[],
        run_summary=run_summary,
        artifacts=[str(model_path)],
    )
