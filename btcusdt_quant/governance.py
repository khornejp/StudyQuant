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
    if metric == "schema_violation_count" and int(value) > 0:
        return "block_new_entries"
    if metric == "critical_feature_missing_rate_current_bar" and float(value) > 0.0:
        return "no_trade_current_bar"
    if metric == "gap_ratio_20" and float(value) >= 0.20:
        return "block_new_entries"
    if metric == "max_gap_run" and int(value) >= 3:
        return "block_new_entries"
    if metric == "http_418_detected" and bool(value):
        return "hard_kill"
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

    def create_approval_package(self, run_summary: Mapping[str, object], clip_report: Sequence[Mapping[str, object]], stage_rows: Sequence[Mapping[str, object]]) -> list[Path]:
        files = [
            self.write_text("dataset_card.yaml", "dataset_id: local_btcusdt_fixture_v1\nsymbol: BTCUSDT\nbar_interval: 1m\ntrain_live_feature_parity_passed: true\n"),
            self.write_json("dataset_card.json", {
                "dataset_id": "local_btcusdt_fixture_v1",
                "symbol": "BTCUSDT",
                "bar_interval": "1m",
                "timezone": "UTC",
                "source": "local deterministic fixture",
                "train_live_feature_parity_passed": True,
            }),
            self.write_text("model_card.yaml", "model_id: mock_no_trade_model_v1\nmodel_family: deterministic_mock\nforbidden_use: live trading or real order submission\n"),
            self.write_json("model_card.json", {
                "model_id": "mock_no_trade_model_v1",
                "model_family": "deterministic_mock",
                "intended_use": "local scaffold verification only",
                "forbidden_use": "live trading or real order submission",
            }),
            self.write_json("feature_formula_registry.json", {
                "features": [
                    {"feature_name": "return_1", "formula": "close_t / close_t-1 - 1", "lookback": 2, "min_samples": 2, "warmup_rule": "strict"},
                    {"feature_name": "return_5_vol_adj", "formula": "return_5 / max(RV15,RV60,RV120,ATR_PCT,VOL_EPS)", "lookback": 121, "min_samples": 121, "warmup_rule": "strict"},
                ]
            }),
            self.write_json("feature_dependency_graph.json", {"acyclic": True, "calculation_order": ["return_1", "return_5_vol_adj"]}),
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
            self.write_text("calibration_config.yaml", "calibrator_type: platt\nregularization: l2\nconvergence_status: scaffold_not_fitted\n"),
            self.write_csv("bootstrap_ci_report.csv", [{"score_bin": "mock", "trade_count": 0, "net_return_ci_lower_95": 0.0, "net_return_ci_upper_95": 0.0}]),
            self.write_csv("data_quality_slo_report.csv", [{"schema_violation_count": 0, "critical_feature_missing_rate_current_bar": 0.0, "action": "allow"}]),
            self.write_csv("monitoring_slo_report.csv", [{"slo_category": "data_quality", "metric": "schema_violation_count", "condition": "0", "action": "allow"}]),
            self.write_json("lineage_manifest.json", {"lineage": ["local_fixture", "features", "mock_model", "mock_order", "artifacts"]}),
            self.write_text("serving_runtime_contract.yaml", "runtime_type: local_mock\nfallback_runtime: none\nhot_reload_allowed: false\n"),
            self.write_csv("feature_clip_report.csv", clip_report),
            self.write_csv("pipeline_stage_manifest.csv", stage_rows),
            self.write_json("run_summary.json", dict(run_summary)),
            self.write_text("security_compliance_signoff.yaml", "security_signoff: local_mock_only\ncompliance_signoff: not_for_live_trading\n"),
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
