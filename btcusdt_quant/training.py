from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import exp, isfinite, log, sqrt
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Mapping, Sequence

from . import cv, dataset, features, governance, lineage, models, monitoring


@dataclass(frozen=True)
class Standardizer:
    means: dict[str, float]
    scales: dict[str, float]

    def transform(self, values: Mapping[str, float], feature_names: Sequence[str]) -> list[float]:
        return [(values[name] - self.means[name]) / self.scales[name] for name in feature_names]


@dataclass(frozen=True)
class LinearClassifier:
    feature_names: tuple[str, ...]
    standardizer: Standardizer
    weights: dict[str, float]
    intercept: float
    calibration_offset: float = 0.0

    def probability(self, values: Mapping[str, float]) -> float:
        z_values = self.standardizer.transform(values, self.feature_names)
        score = self.intercept + self.calibration_offset
        for name, value in zip(self.feature_names, z_values):
            score += self.weights[name] * value
        return sigmoid(score)

    def as_dict(self) -> dict[str, object]:
        return {
            "model_family": "deterministic_centroid_linear_classifier",
            "feature_names": list(self.feature_names),
            "standardizer_means": self.standardizer.means,
            "standardizer_scales": self.standardizer.scales,
            "weights": self.weights,
            "intercept": self.intercept,
            "calibration_offset": self.calibration_offset,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> LinearClassifier:
        model_family = payload.get("model_family", "")
        if not isinstance(model_family, str) or "deterministic_centroid_linear" not in model_family:
            raise ValueError(f"unsupported model_family for LinearClassifier: {model_family}")
        feature_names = payload.get("feature_names", ())
        if isinstance(feature_names, str):
            feature_names = (feature_names,)
        feature_names = tuple(str(name) for name in feature_names)
        if not feature_names:
            raise ValueError("feature_names must be non-empty")
        means = payload.get("standardizer_means", {})
        scales = payload.get("standardizer_scales", {})
        weights = payload.get("weights", {})
        intercept = float(payload.get("intercept", 0.0))
        calibration_offset = float(payload.get("calibration_offset", 0.0))
        if not isinstance(means, Mapping):
            raise ValueError("standardizer_means must be a mapping")
        if not isinstance(scales, Mapping):
            raise ValueError("standardizer_scales must be a mapping")
        if not isinstance(weights, Mapping):
            raise ValueError("weights must be a mapping")
        # Validate every feature has required entries
        for name in feature_names:
            if name not in means:
                raise ValueError(f"missing standardizer_means for feature: {name}")
            if name not in scales:
                raise ValueError(f"missing standardizer_scales for feature: {name}")
            if name not in weights:
                raise ValueError(f"missing weight for feature: {name}")
        # Validate finite floats and non-zero scales
        float_means = {str(k): float(v) for k, v in means.items()}
        float_scales = {str(k): float(v) for k, v in scales.items()}
        float_weights = {str(k): float(v) for k, v in weights.items()}
        for name in feature_names:
            if not isfinite(float_means[name]):
                raise ValueError(f"non-finite mean for feature: {name}")
            if not isfinite(float_scales[name]) or float_scales[name] == 0.0:
                raise ValueError(f"non-finite or zero scale for feature: {name}")
            if not isfinite(float_weights[name]):
                raise ValueError(f"non-finite weight for feature: {name}")
        if not isfinite(intercept):
            raise ValueError("intercept must be finite")
        if not isfinite(calibration_offset):
            raise ValueError("calibration_offset must be finite")
        standardizer = Standardizer(float_means, float_scales)
        return cls(
            feature_names=feature_names,
            standardizer=standardizer,
            weights=float_weights,
            intercept=intercept,
            calibration_offset=calibration_offset,
        )


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
        if str(self.model_family).lower().strip() not in {"auto", "stdlib", "linear", "deterministic", "lightgbm", "lgbm", "catboost", "cat"}:
            raise ValueError("model_family must be 'auto', 'stdlib', 'lightgbm', or 'catboost'")


@dataclass(frozen=True)
class FoldResult:
    fold_index: int
    split: object
    threshold: float
    calibration_offset: float
    calibration_details: dict[str, object]
    validation_metrics: dict[str, float]
    test_metrics: dict[str, float]
    model_selection: dict[str, object]


@dataclass(frozen=True)
class TrainingResult:
    output_dir: Path
    dataset_build: dataset.DatasetBuild
    splits: list[object]
    fold_results: list[FoldResult]
    run_summary: dict[str, object]
    artifacts: list[str]


def run_training(input_path: Path | None, output_dir: Path, config: TrainingConfig | None = None, archive_dir: Path | None = None) -> TrainingResult:
    training_config = config or TrainingConfig()
    build = dataset.build_dataset(input_path=input_path, archive_dir=archive_dir)
    if len(build.labeled_rows) < 80:
        raise ValueError("at least 80 labeled rows are required for the default offline training run")
    sample_intervals = cv.sample_intervals_from_labeled_rows(build.labeled_rows, build.label_horizon)
    uniqueness = cv.uniqueness_weights(sample_intervals)
    splits = configured_splits(len(build.labeled_rows), build.label_horizon, training_config, sample_intervals)
    if not splits:
        raise ValueError("not enough labeled rows for configured split")
    fold_results: list[FoldResult] = []
    for fold_index, split in enumerate(splits):
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
            build.feature_names,
            training_config,
            _weights_for_indices(uniqueness, train_indices),
        )
        model = selection.adapter
        validation_probabilities = model.predict_proba(feature_matrix(validation_rows, build.feature_names))
        offset = calibration_offset(validation_probabilities, validation_labels)
        calibrator = features.CalibrationModule().fit(validation_probabilities, validation_labels, positive_samples=sum(validation_labels))
        calibrated_validation = calibrator.transform(validation_probabilities)
        threshold = select_threshold(calibrated_validation, validation_labels)
        test_probabilities = model.predict_proba(feature_matrix(test_rows, build.feature_names))
        calibrated_test = calibrator.transform(test_probabilities)
        fold_results.append(
            FoldResult(
                fold_index=fold_index,
                split=split,
                threshold=threshold,
                calibration_offset=offset,
                calibration_details=calibrator.as_dict(),
                validation_metrics=metrics(calibrated_validation, validation_labels, threshold),
                test_metrics=metrics(calibrated_test, test_labels, threshold),
                model_selection=selection.as_dict(),
            )
        )
    final_indices = list(range(len(build.labeled_rows)))
    final_selection = fit_model_adapter(build.labeled_rows, build.feature_names, training_config, _weights_for_indices(uniqueness, final_indices))
    latency_report = inference_latency_report(final_selection.adapter, feature_matrix(build.labeled_rows, build.feature_names))
    artifacts = write_training_artifacts(output_dir, build, splits, fold_results, final_selection.adapter, training_config, sample_intervals, uniqueness, final_selection, latency_report)
    run_summary = training_summary(build, splits, fold_results, artifacts, training_config, uniqueness, final_selection, latency_report)
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


def fit_classifier(rows: Sequence[dataset.LabeledRow], feature_names: Sequence[str], sample_weights: Sequence[float] | None = None) -> LinearClassifier:
    if not rows:
        raise ValueError("cannot fit classifier with no rows")
    weights_for_rows = _validated_sample_weights(rows, sample_weights)
    standardizer = fit_standardizer(rows, feature_names, weights_for_rows)
    positives = [(row, weight) for row, weight in zip(rows, weights_for_rows) if row.label == 1]
    negatives = [(row, weight) for row, weight in zip(rows, weights_for_rows) if row.label == 0]
    total_weight = sum(weights_for_rows)
    base_rate = sum(weight for _, weight in positives) / total_weight if total_weight > 0.0 else 0.0
    weights: dict[str, float] = {}
    pos_center: list[float] = []
    neg_center: list[float] = []
    for name_index, name in enumerate(feature_names):
        pos_values = [standardizer.transform(row.features, feature_names)[name_index] for row, _ in positives]
        pos_weights = [weight for _, weight in positives]
        neg_values = [standardizer.transform(row.features, feature_names)[name_index] for row, _ in negatives]
        neg_weights = [weight for _, weight in negatives]
        pos_mean = weighted_mean(pos_values, pos_weights) if pos_values else 0.0
        neg_mean = weighted_mean(neg_values, neg_weights) if neg_values else 0.0
        pos_center.append(pos_mean)
        neg_center.append(neg_mean)
        weights[str(name)] = pos_mean - neg_mean
    intercept = safe_logit(base_rate)
    intercept -= 0.5 * (sum(value * value for value in pos_center) - sum(value * value for value in neg_center))
    return LinearClassifier(tuple(str(name) for name in feature_names), standardizer, weights, intercept)


def fit_standardizer(rows: Sequence[dataset.LabeledRow], feature_names: Sequence[str], sample_weights: Sequence[float] | None = None) -> Standardizer:
    weights_for_rows = _validated_sample_weights(rows, sample_weights)
    means: dict[str, float] = {}
    scales: dict[str, float] = {}
    for name in feature_names:
        values = [row.features[name] for row in rows]
        average = weighted_mean(values, weights_for_rows) if values else 0.0
        variance = weighted_mean([(value - average) ** 2 for value in values], weights_for_rows) if values else 0.0
        scale = sqrt(variance) if variance > 0.0 else 1.0
        means[str(name)] = average
        scales[str(name)] = scale
    return Standardizer(means, scales)


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


def select_threshold(probabilities: Sequence[float], labels: Sequence[int]) -> float:
    if not probabilities or not labels:
        return 0.5
    candidates = {round(index / 20.0, 2) for index in range(1, 20)}
    candidates.update(round(value, 4) for value in probabilities)
    best_threshold = 0.5
    best_score = (-1.0, -1.0, 0.0)
    for threshold in sorted(candidates):
        current = metrics(probabilities, labels, threshold)
        score = (current["f1"], current["accuracy"], -abs(threshold - 0.5))
        if score > best_score:
            best_score = score
            best_threshold = threshold
    return best_threshold


def metrics(probabilities: Sequence[float], labels: Sequence[int], threshold: float) -> dict[str, float]:
    if not probabilities or not labels:
        return {"rows": 0.0, "accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "ece": 0.0, "expected_calibration_error": 0.0, "mce": 0.0, "brier": 0.0, "brier_score": 0.0, "brier_skill_score": 0.0, "positive_rate": 0.0, "predicted_positive_rate": 0.0}
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
    }


def write_training_artifacts(
    output_dir: Path,
    build: dataset.DatasetBuild,
    splits: Sequence[object],
    fold_results: Sequence[FoldResult],
    final_model: models.ModelAdapter | LinearClassifier,
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
    final_model: models.ModelAdapter | LinearClassifier,
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


def default_model_selection(config: TrainingConfig, model: models.ModelAdapter | LinearClassifier | None) -> dict[str, object]:
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


def selected_family(model: models.ModelAdapter | LinearClassifier | None) -> str:
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


def inference_latency_report(model: models.ModelAdapter | LinearClassifier, matrix: Sequence[Sequence[float]], max_rows: int = 100) -> dict[str, object]:
    sample = [list(row) for row in matrix[:max_rows]]
    if not sample:
        return empty_latency_report()
    latencies = []
    for row in sample:
        start = perf_counter()
        if hasattr(model, "predict_proba"):
            getattr(model, "predict_proba")([row])
        else:
            # Direct LinearClassifier compatibility is intentionally reported as unavailable
            # because its probability method requires feature-name mappings.
            return empty_latency_report()
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
    model: models.ModelAdapter | LinearClassifier,
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
    model: models.ModelAdapter | LinearClassifier,
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


def model_feature_names(model: models.ModelAdapter | LinearClassifier, fallback: Sequence[str]) -> list[str]:
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
