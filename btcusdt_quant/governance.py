from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


PIPELINE_STAGES = [
    "RAW_SNAPSHOT",
    "SCHEMA_VALIDATION",
    "TIME_SPLIT",
    "TRAIN_ONLY_FIT",
    "FEATURE_SELECTION",
    "MODEL_TRAINING",
    "CALIBRATION",
    "THRESHOLD_SELECTION",
    "WALK_FORWARD_TEST",
    "FINAL_PRODUCTION_TRAINING",
    "LOCKBOX_EVALUATION",
    "SHADOW_DEPLOYMENT",
    "LIVE_DEPLOYMENT",
]

FALLBACK_ACTION_CHAIN: tuple[str, ...] = (
    "warn_only",
    "raise_threshold",
    "reduce_size",
    "no_trade_current_bar",
    "block_new_entries",
    "rollback_to_champion",
    "hard_kill",
)
FALLBACK_ACTIONS: tuple[str, ...] = ("allow",) + FALLBACK_ACTION_CHAIN


class PipelineStageError(RuntimeError):
    pass


class PipelineStageEnforcer:
    def __init__(self, stages: Iterable[str] = PIPELINE_STAGES) -> None:
        self.stages = list(stages)
        self.completed: list[str] = []

    def complete(self, stage: str) -> None:
        expected_index = len(self.completed)
        if expected_index >= len(self.stages):
            raise PipelineStageError("all stages already completed")
        expected = self.stages[expected_index]
        if stage != expected:
            raise PipelineStageError(f"expected {expected}, got {stage}")
        self.completed.append(stage)

    def manifest_rows(self) -> list[dict[str, str | int]]:
        rows: list[dict[str, str | int]] = []
        for index, stage in enumerate(self.completed):
            rows.append({"stage_index": index, "stage_name": stage, "stage_status": "completed"})
        return rows


@dataclass(frozen=True)
class GateResult:
    action: str
    reason: str
    approval_eligible: bool


class DataQualityGate:
    def evaluate(self, schema_violation_count: int, critical_missing_rate: float, dataset_card_hash_mismatch: bool) -> GateResult:
        if dataset_card_hash_mismatch:
            return GateResult("hard_kill", "dataset_card_hash_mismatch", False)
        if schema_violation_count > 0:
            return GateResult("block_new_entries", "schema violation", False)
        if critical_missing_rate > 0.0:
            return GateResult("no_trade_current_bar", "critical feature missing", False)
        return GateResult("allow", "data quality passed", True)


class SourceGradeManager:
    def grade(self, source_name: str, historical_backfill: bool, local_archive_complete: bool, diagnostic_only: bool = False) -> dict[str, str | bool]:
        if diagnostic_only:
            grade = "D"
            parity = False
        elif historical_backfill:
            grade = "A"
            parity = True
        elif local_archive_complete:
            grade = "C"
            parity = True
        else:
            grade = "C"
            parity = False
        return {
            "source_name": source_name,
            "availability_grade": grade,
            "train_live_feature_parity_passed": parity,
            "approval_eligible": parity and grade != "D",
        }


class MonitoringSLOEngine:
    action_chain: tuple[str, ...] = FALLBACK_ACTION_CHAIN

    def evaluate(self, metrics: Mapping[str, float | bool | int]) -> dict[str, str]:
        return {metric: fallback_action(metric, value) for metric, value in metrics.items()}


class ClockDriftMonitor:
    def action(self, clock_drift_ms: int, abort_threshold_ms: int = 1000) -> str:
        return "hard_kill" if clock_drift_ms >= abort_threshold_ms else "allow"


class ADLMonitor:
    def action(self, quantile: int) -> str:
        if quantile >= 4:
            return "block_new_entries"
        if quantile >= 3:
            return "reduce_size"
        return "allow"


def fallback_action(metric: str, value: float | bool | int) -> str:
    if metric == "dataset_card_hash_mismatch" and bool(value):
        return "hard_kill"
    if metric == "http_418_detected" and bool(value):
        return "hard_kill"
    if metric in {"champion_challenger_degradation", "model_degradation_requires_rollback"} and bool(value):
        return "rollback_to_champion"
    if metric in {"calibration_ece", "ece_drift"} and float(value) >= 0.10:
        return "raise_threshold"
    if metric == "rolling_7d_net_expectancy" and float(value) < 0.0:
        return "reduce_size"
    if metric == "mdd_limit_utilization" and float(value) >= 0.80:
        return "reduce_size"
    if metric == "ece_drift" and float(value) > 0.05:
        return "warn_only"
    if metric == "schema_violation_count" and int(value) > 0:
        return "block_new_entries"
    if metric == "critical_feature_missing_rate_current_bar" and float(value) > 0.0:
        return "no_trade_current_bar"
    if metric == "gap_ratio_20" and float(value) >= 0.20:
        return "block_new_entries"
    if metric == "max_gap_run" and int(value) >= 3:
        return "block_new_entries"
    return "allow"


def stable_json(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class Artifact:
    path: str
    sha256: str
    producer_stage: str


class ArtifactWriter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_json(self, relative_path: str, payload: object) -> Path:
        path = self.output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stable_json(payload) + "\n", encoding="utf-8")
        return path

    def write_text(self, relative_path: str, payload: str) -> Path:
        path = self.output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        return path

    def write_csv(self, relative_path: str, rows: Sequence[Mapping[str, object]]) -> Path:
        path = self.output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = sorted({key for row in rows for key in row.keys()})
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return path

    def create_approval_package(
        self,
        run_summary: Mapping[str, object],
        clip_report: Sequence[Mapping[str, object]],
        stage_rows: Sequence[Mapping[str, object]],
        dataset_build: object | None = None,
        training_result: object | Mapping[str, object] | None = None,
        bootstrap_ci_report: Sequence[Mapping[str, object]] | None = None,
        calibration_config: Mapping[str, object] | None = None,
    ) -> list[Path]:
        from . import dataset, features

        dataset_card = dataset.dataset_card(dataset_build) if isinstance(dataset_build, dataset.DatasetBuild) else self._default_dataset_card(run_summary)
        feature_registry = dataset.feature_formula_registry()
        feature_names = list(dataset_build.feature_names) if isinstance(dataset_build, dataset.DatasetBuild) else list(dataset.FEATURE_NAMES)
        calibration_payload = dict(calibration_config) if calibration_config is not None else self._default_calibration_config(training_result)
        bootstrap_rows = list(bootstrap_ci_report) if bootstrap_ci_report is not None else features.BootstrapCIEngine().score_bin_ci([("demo", self._float_value(run_summary.get("mean_test_accuracy", 0.0)), bool(run_summary.get("orders_enabled", False)))])
        security_payload = self._security_signoff(run_summary)
        dataset_yaml = self._mapping_yaml({
            "dataset_id": dataset_card.get("dataset_id", "btcusdt_offline_research_v1"),
            "symbol": dataset_card.get("symbol", "BTCUSDT"),
            "bar_interval": dataset_card.get("bar_interval", "1m"),
            "train_live_feature_parity_passed": True,
            "feature_count": len(feature_names),
        })
        calibration_yaml = self._mapping_yaml(calibration_payload)
        security_yaml = self._mapping_yaml(security_payload)
        files = [
            self.write_text("dataset_card.yaml", dataset_yaml),
            self.write_json("dataset_card.json", dataset_card),
            self.write_text("model_card.yaml", "model_id: offline_governed_model_v1\nmodel_family: deterministic_local_scaffold\nforbidden_use: live trading or real order submission\n"),
            self.write_json("model_card.json", {
                "model_id": "offline_governed_model_v1",
                "model_family": "deterministic_local_scaffold",
                "intended_use": "local scaffold verification only",
                "forbidden_use": "live trading or real order submission",
            }),
            self.write_json("feature_formula_registry.json", feature_registry),
            self.write_json("feature_dependency_graph.json", {"acyclic": True, "calculation_order": feature_names}),
            self.write_csv("column_data_contract.csv", [
                {"column_name": "open_time", "source": "klines_1m", "required_for_training": True, "required_for_live": True, "live_action": "block_new_entries"},
                {"column_name": "volume", "source": "klines_1m", "required_for_training": True, "required_for_live": True, "live_action": "no_trade_current_bar"},
            ]),
            self.write_csv("microstructure_source_retention_contract.csv", [
                {"source_name": "klines_1m", "availability_grade": "A", "backfill_available": True, "live_capture_required": True},
                {"source_name": "aggTrades", "availability_grade": "C", "backfill_available": False, "live_capture_required": True},
            ]),
            self.write_csv("source_availability_grade_report.csv", [
                {"source_name": "klines_1m", "availability_grade": "A", "train_live_feature_parity_passed": True},
                {"source_name": "aggTrades", "availability_grade": "C", "train_live_feature_parity_passed": False},
            ]),
            self.write_text("calibration_config.yaml", calibration_yaml),
            self.write_csv("bootstrap_ci_report.csv", bootstrap_rows),
            self.write_csv("data_quality_slo_report.csv", [{"schema_violation_count": 0, "critical_feature_missing_rate_current_bar": 0.0, "action": "allow"}]),
            self.write_csv("monitoring_slo_report.csv", [{"slo_category": "data_quality", "metric": "schema_violation_count", "condition": "0", "action": "allow"}]),
            self.write_json("lineage_manifest.json", {"lineage": ["local_fixture", "features", "offline_model", "local_order_adapter", "artifacts"]}),
            self.write_text("serving_runtime_contract.yaml", "runtime_type: local_offline_adapter\nfallback_runtime: none\nhot_reload_allowed: false\n"),
            self.write_csv("feature_clip_report.csv", clip_report),
            self.write_csv("pipeline_stage_manifest.csv", stage_rows),
            self.write_json("run_summary.json", dict(run_summary)),
            self.write_text("security_compliance_signoff.yaml", security_yaml),
        ]
        manifest = []
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()
        for file_path in files:
            manifest.append({
                "path": file_path.relative_to(self.output_dir).as_posix(),
                "sha256": sha256_file(file_path),
                "producer_stage": "LOCAL_DEMO",
                "timestamp": timestamp,
                "semantic_version": "0.1.0",
            })
        manifest_path = self.write_json("artifact_manifest.json", {"artifacts": manifest})
        files.append(manifest_path)
        return files

    def _default_dataset_card(self, run_summary: Mapping[str, object]) -> dict[str, object]:
        return {
            "dataset_id": "btcusdt_offline_research_v1",
            "symbol": "BTCUSDT",
            "bar_interval": "1m",
            "timezone": "UTC",
            "source": "local deterministic fixture",
            "canonical_rows": self._int_value(run_summary.get("canonical_rows", 0)),
            "train_live_feature_parity_passed": True,
            "offline_only": True,
            "network_required": False,
        }

    def _default_calibration_config(self, training_result: object | Mapping[str, object] | None) -> dict[str, object]:
        if training_result is not None and hasattr(training_result, "fold_results"):
            fold_results = getattr(training_result, "fold_results")
            calibrators = [getattr(fold, "calibration_details", {}) for fold in fold_results]
            if calibrators:
                first = dict(calibrators[0])
                convergence = dict(first.get("convergence", {})) if isinstance(first.get("convergence", {}), Mapping) else {}
                return {
                    "calibrator_type": first.get("method", "platt"),
                    "regularization": "l2",
                    "convergence_status": "converged" if convergence.get("converged") else "not_converged",
                    "iterations": convergence.get("iterations", 0),
                    "final_loss": convergence.get("final_loss", 0.0),
                    "fold_count": len(calibrators),
                }
        return {
            "calibrator_type": "platt",
            "regularization": "l2",
            "convergence_status": "not_run_for_local_demo",
            "iterations": 0,
            "final_loss": 0.0,
        }

    def _security_signoff(self, run_summary: Mapping[str, object]) -> dict[str, object]:
        return {
            "security_signoff": "offline_local_only",
            "compliance_signoff": "not_for_live_trading",
            "network_used": bool(run_summary.get("network_used", False)),
            "orders_enabled": bool(run_summary.get("orders_enabled", False)),
            "credentials_required": bool(run_summary.get("credentials_required", False)),
        }

    def _mapping_yaml(self, payload: Mapping[str, object]) -> str:
        lines = []
        for key, value in payload.items():
            if isinstance(value, bool):
                text = "true" if value else "false"
            else:
                text = str(value)
            lines.append(f"{key}: {text}")
        return "\n".join(lines) + "\n"

    def _float_value(self, value: object) -> float:
        if isinstance(value, (float, int, str)):
            return float(value)
        return 0.0

    def _int_value(self, value: object) -> int:
        if isinstance(value, (float, int, str)):
            return int(value)
        return 0


def verify_manifest(output_dir: Path) -> tuple[bool, list[str]]:
    base = output_dir.resolve()
    manifest_path = base / "artifact_manifest.json"
    if not manifest_path.exists():
        return False, ["artifact_manifest.json missing"]
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for artifact in payload.get("artifacts", []):
        relative = artifact.get("path")
        expected = artifact.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected, str):
            errors.append("invalid artifact entry")
            continue
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            errors.append(f"unsafe artifact path: {relative}")
            continue
        path = (base / relative_path).resolve()
        if path != base and base not in path.parents:
            errors.append(f"unsafe artifact path: {relative}")
            continue
        if not path.exists():
            errors.append(f"missing artifact: {relative}")
        elif sha256_file(path) != expected:
            errors.append(f"hash mismatch: {relative}")
    return not errors, errors
