from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp, log, sqrt
from pathlib import Path
from statistics import mean
from typing import Mapping, Sequence

from . import dataset, features, governance


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


@dataclass(frozen=True)
class FoldResult:
    fold_index: int
    split: features.Split
    threshold: float
    calibration_offset: float
    validation_metrics: dict[str, float]
    test_metrics: dict[str, float]


@dataclass(frozen=True)
class TrainingResult:
    output_dir: Path
    dataset_build: dataset.DatasetBuild
    splits: list[features.Split]
    fold_results: list[FoldResult]
    run_summary: dict[str, object]
    artifacts: list[str]


def run_training(input_path: Path | None, output_dir: Path) -> TrainingResult:
    build = dataset.build_dataset(input_path=input_path)
    if len(build.labeled_rows) < 80:
        raise ValueError("at least 80 labeled rows are required for the default offline training run")
    splits = default_splits(len(build.labeled_rows), build.label_horizon)
    if not splits:
        raise ValueError("not enough labeled rows for purged walk-forward split")
    fold_results: list[FoldResult] = []
    for fold_index, split in enumerate(splits):
        train_rows = [build.labeled_rows[index] for index in split.train]
        validation_rows = [build.labeled_rows[index] for index in split.validation]
        test_rows = [build.labeled_rows[index] for index in split.test]
        model = fit_classifier(train_rows, build.feature_names)
        validation_probabilities = [model.probability(row.features) for row in validation_rows]
        offset = calibration_offset(validation_probabilities, [row.label for row in validation_rows])
        calibrated_model = LinearClassifier(model.feature_names, model.standardizer, model.weights, model.intercept, offset)
        calibrated_validation = [calibrated_model.probability(row.features) for row in validation_rows]
        threshold = select_threshold(calibrated_validation, [row.label for row in validation_rows])
        calibrated_test = [calibrated_model.probability(row.features) for row in test_rows]
        fold_results.append(
            FoldResult(
                fold_index=fold_index,
                split=split,
                threshold=threshold,
                calibration_offset=offset,
                validation_metrics=metrics(calibrated_validation, [row.label for row in validation_rows], threshold),
                test_metrics=metrics(calibrated_test, [row.label for row in test_rows], threshold),
            )
        )
    final_model = fit_classifier(build.labeled_rows, build.feature_names)
    artifacts = write_training_artifacts(output_dir, build, splits, fold_results, final_model)
    run_summary = training_summary(build, splits, fold_results, artifacts)
    writer = governance.ArtifactWriter(output_dir)
    writer.write_json("run_summary.json", run_summary)
    manifest = write_manifest(output_dir, artifacts + ["run_summary.json"])
    return TrainingResult(output_dir, build, splits, fold_results, run_summary, manifest)


def default_splits(n_rows: int, purge_gap: int) -> list[features.Split]:
    train_size = max(60, n_rows // 3)
    validation_size = max(20, n_rows // 8)
    test_size = max(20, n_rows // 8)
    return features.PurgedWalkForwardSplit().split(n_rows, train_size, validation_size, test_size, purge_gap)


def fit_classifier(rows: Sequence[dataset.LabeledRow], feature_names: Sequence[str]) -> LinearClassifier:
    if not rows:
        raise ValueError("cannot fit classifier with no rows")
    standardizer = fit_standardizer(rows, feature_names)
    positives = [row for row in rows if row.label == 1]
    negatives = [row for row in rows if row.label == 0]
    base_rate = len(positives) / len(rows)
    weights: dict[str, float] = {}
    pos_center: list[float] = []
    neg_center: list[float] = []
    for name_index, name in enumerate(feature_names):
        pos_values = [standardizer.transform(row.features, feature_names)[name_index] for row in positives] or [0.0]
        neg_values = [standardizer.transform(row.features, feature_names)[name_index] for row in negatives] or [0.0]
        pos_mean = mean(pos_values)
        neg_mean = mean(neg_values)
        pos_center.append(pos_mean)
        neg_center.append(neg_mean)
        weights[str(name)] = pos_mean - neg_mean
    intercept = safe_logit(base_rate)
    intercept -= 0.5 * (sum(value * value for value in pos_center) - sum(value * value for value in neg_center))
    return LinearClassifier(tuple(str(name) for name in feature_names), standardizer, weights, intercept)


def fit_standardizer(rows: Sequence[dataset.LabeledRow], feature_names: Sequence[str]) -> Standardizer:
    means: dict[str, float] = {}
    scales: dict[str, float] = {}
    for name in feature_names:
        values = [row.features[name] for row in rows]
        average = mean(values)
        variance = mean([(value - average) ** 2 for value in values]) if values else 0.0
        scale = sqrt(variance) if variance > 0.0 else 1.0
        means[str(name)] = average
        scales[str(name)] = scale
    return Standardizer(means, scales)


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
        return {"rows": 0.0, "accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "brier": 0.0, "positive_rate": 0.0, "predicted_positive_rate": 0.0}
    predictions = [1 if probability >= threshold else 0 for probability in probabilities]
    tp = sum(1 for prediction, label in zip(predictions, labels) if prediction == 1 and label == 1)
    tn = sum(1 for prediction, label in zip(predictions, labels) if prediction == 0 and label == 0)
    fp = sum(1 for prediction, label in zip(predictions, labels) if prediction == 1 and label == 0)
    fn = sum(1 for prediction, label in zip(predictions, labels) if prediction == 0 and label == 1)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    brier = mean([(probability - label) ** 2 for probability, label in zip(probabilities, labels)])
    return {
        "rows": float(len(labels)),
        "accuracy": (tp + tn) / len(labels),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "brier": brier,
        "positive_rate": sum(labels) / len(labels),
        "predicted_positive_rate": sum(predictions) / len(predictions),
    }


def write_training_artifacts(
    output_dir: Path,
    build: dataset.DatasetBuild,
    splits: Sequence[features.Split],
    fold_results: Sequence[FoldResult],
    final_model: LinearClassifier,
) -> list[str]:
    writer = governance.ArtifactWriter(output_dir)
    writer.write_json("dataset_card.json", dataset.dataset_card(build))
    writer.write_text("dataset_card.md", dataset_card_markdown(build))
    writer.write_json("feature_formula_registry.json", dataset.feature_formula_registry())
    writer.write_json("model.json", final_model.as_dict())
    writer.write_json("model_card.json", model_card(build, final_model))
    writer.write_text("model_card.md", model_card_markdown())
    writer.write_csv("split_manifest.csv", split_rows(splits))
    writer.write_csv("fold_metrics.csv", fold_metric_rows(fold_results))
    writer.write_json("calibration_report.json", calibration_report(fold_results))
    writer.write_json("threshold_report.json", threshold_report(fold_results))
    writer.write_csv("labeled_feature_preview.csv", [dataset.labeled_row_dict(row, build.feature_names) for row in build.labeled_rows[:25]])
    return [
        "dataset_card.json",
        "dataset_card.md",
        "feature_formula_registry.json",
        "model.json",
        "model_card.json",
        "model_card.md",
        "split_manifest.csv",
        "fold_metrics.csv",
        "calibration_report.json",
        "threshold_report.json",
        "labeled_feature_preview.csv",
    ]


def training_summary(build: dataset.DatasetBuild, splits: Sequence[features.Split], fold_results: Sequence[FoldResult], artifacts: Sequence[str]) -> dict[str, object]:
    test_f1_values = [fold.test_metrics["f1"] for fold in fold_results]
    test_accuracy_values = [fold.test_metrics["accuracy"] for fold in fold_results]
    return {
        "run_id": "offline_btcusdt_training_v1",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
        "network_used": False,
        "credentials_required": False,
        "orders_enabled": False,
        "source": build.source,
        "canonical_rows": len(build.canonical),
        "labeled_rows": len(build.labeled_rows),
        "feature_count": len(build.feature_names),
        "fold_count": len(splits),
        "mean_test_f1": mean(test_f1_values) if test_f1_values else 0.0,
        "mean_test_accuracy": mean(test_accuracy_values) if test_accuracy_values else 0.0,
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


def split_rows(splits: Sequence[features.Split]) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    for index, split in enumerate(splits):
        rows.append(
            {
                "fold_index": index,
                "train_start": split.train.start,
                "train_stop_exclusive": split.train.stop,
                "validation_start": split.validation.start,
                "validation_stop_exclusive": split.validation.stop,
                "test_start": split.test.start,
                "test_stop_exclusive": split.test.stop,
                "purge_train_validation": split.validation.start - split.train.stop,
                "purge_validation_test": split.test.start - split.validation.stop,
            }
        )
    return rows


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
        "method": "validation_base_rate_logit_offset",
        "selected_by": "purged walk-forward validation folds",
        "fold_offsets": [{"fold_index": fold.fold_index, "calibration_offset": fold.calibration_offset} for fold in fold_results],
    }


def threshold_report(fold_results: Sequence[FoldResult]) -> dict[str, object]:
    return {
        "objective": "maximize validation F1, then accuracy, deterministic tie-break toward 0.5",
        "fold_thresholds": [{"fold_index": fold.fold_index, "threshold": fold.threshold} for fold in fold_results],
    }


def model_card(build: dataset.DatasetBuild, model: LinearClassifier) -> dict[str, object]:
    return {
        "model_id": "offline_btcusdt_centroid_linear_v1",
        "model_family": "deterministic stdlib centroid linear classifier",
        "intended_use": "offline BTCUSDT research scaffold and artifact verification",
        "forbidden_use": "live trading, real order submission, or credentialed exchange access",
        "training_rows": len(build.labeled_rows),
        "feature_names": list(model.feature_names),
        "offline_only": True,
        "network_required": False,
    }


def dataset_card_markdown(build: dataset.DatasetBuild) -> str:
    return "\n".join(
        [
            "# Offline BTCUSDT Dataset Card",
            "",
            f"- Source: `{build.source}`",
            f"- Canonical rows: {len(build.canonical)}",
            f"- Labeled rows: {len(build.labeled_rows)}",
            f"- Repaired rows: {build.gap_report.repaired_rows}",
            "- Network required: false",
            "",
        ]
    )


def model_card_markdown() -> str:
    return "\n".join(
        [
            "# Offline BTCUSDT Model Card",
            "",
            "This model is a deterministic stdlib-only research classifier.",
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
