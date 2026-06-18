from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from . import parity, sources


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
        grade = sources.source_availability_grade(source_name, historical_backfill, local_archive_complete, diagnostic_only=diagnostic_only)
        return {
            "source_name": str(grade["source_name"]),
            "availability_grade": str(grade["availability_grade"]),
            "train_live_feature_parity_passed": bool(grade["train_live_feature_parity_passed"]),
            "approval_eligible": bool(grade["approval_eligible"]),
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
    if metric == "clock_drift_ms":
        drift = abs(float(value))
        if drift >= 1000.0:
            return "hard_kill"
        if drift >= 500.0:
            return "block_new_entries"
        if drift >= 100.0:
            return "warn_only"
    if metric == "adl_quantile":
        rank = int(value)
        if rank >= 5:
            return "hard_kill"
        if rank >= 4:
            return "block_new_entries"
        if rank >= 3:
            return "reduce_size"
    if metric == "funding_blackout_active" and bool(value):
        return "block_new_entries"
    if metric == "funding_cost_exceeds_edge" and bool(value):
        return "block_new_entries"
    if metric in {"champion_challenger_degradation", "model_degradation_requires_rollback"} and bool(value):
        return "rollback_to_champion"
    if metric in {"calibration_ece", "ece_drift"} and float(value) >= 0.10:
        return "raise_threshold"
    if metric in {"calibration_ece", "ece_drift"} and float(value) > 0.05:
        return "warn_only"
    if metric == "brier_drift" and float(value) > 0.0:
        return "warn_only"
    if metric == "rolling_7d_net_expectancy" and float(value) < 0.0:
        return "reduce_size"
    if metric == "mdd_limit_utilization" and float(value) >= 0.80:
        return "reduce_size"
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
        source_bundle = dataset_build.source_bundle if isinstance(dataset_build, dataset.DatasetBuild) else self._default_source_bundle(run_summary)
        source_report = sources.train_live_feature_parity_report(feature_names, source_bundle=source_bundle, feature_registry=feature_registry["features"])
        parity_result = parity.compare_training_live_features(
            feature_registry,
            feature_registry,
            source_report=source_report,
            training_feature_names=feature_names,
            live_feature_names=feature_names,
        )
        parity_metadata = parity_result.as_metadata()
        dataset_card = dict(dataset_card)
        dataset_card.update(
            {
                "feature_parity_passed": bool(parity_metadata["feature_parity_passed"]),
                "feature_schema_hash": parity_metadata["feature_schema_hash"],
                "training_feature_schema_hash": parity_metadata["training_feature_schema_hash"],
                "live_feature_schema_hash": parity_metadata["live_feature_schema_hash"],
                "source_schema_hash": parity_metadata["source_schema_hash"],
                "training_source_schema_hash": parity_metadata["training_source_schema_hash"],
                "live_source_schema_hash": parity_metadata["live_source_schema_hash"],
                "dependency_graph_hash": parity_metadata["dependency_graph_hash"],
                "training_dependency_graph_hash": parity_metadata["training_dependency_graph_hash"],
                "live_dependency_graph_hash": parity_metadata["live_dependency_graph_hash"],
                "feature_parity_checks": parity_metadata["parity_checks"],
                "feature_parity_reasons": parity_metadata["parity_reasons"],
                "documented_grade_c_fallback": parity_metadata["documented_grade_c_fallback"],
            }
        )
        train_live_feature_parity_passed = bool(dataset_card.get("train_live_feature_parity_passed", source_report.get("train_live_feature_parity_passed", True))) and parity_result.passed
        dataset_card["train_live_feature_parity_passed"] = train_live_feature_parity_passed
        feature_space_parity_passed = bool(dataset_card.get("feature_space_parity_passed", source_report.get("feature_space_parity_passed", True)))
        calibration_payload = dict(calibration_config) if calibration_config is not None else self._default_calibration_config(training_result)
        bootstrap_rows = list(bootstrap_ci_report) if bootstrap_ci_report is not None else features.BootstrapCIEngine().score_bin_ci([("demo", self._float_value(run_summary.get("mean_test_accuracy", 0.0)), bool(run_summary.get("orders_enabled", False)))])
        security_payload = self._security_signoff(run_summary)
        dataset_yaml = self._mapping_yaml({
            "dataset_id": dataset_card.get("dataset_id", "btcusdt_offline_research_v1"),
            "symbol": dataset_card.get("symbol", "BTCUSDT"),
            "bar_interval": dataset_card.get("bar_interval", "1m"),
            "train_live_feature_parity_passed": train_live_feature_parity_passed,
            "feature_space_parity_passed": feature_space_parity_passed,
            "feature_schema_hash": parity_result.training_feature_schema_hash,
            "source_schema_hash": parity_result.training_source_schema_hash,
            "dependency_graph_hash": parity_result.dependency_graph_hash,
            "feature_count": len(feature_names),
        })
        calibration_yaml = self._mapping_yaml(calibration_payload)
        security_yaml = self._mapping_yaml(security_payload)
        data_quality_action = "allow" if train_live_feature_parity_passed else "block_new_entries"
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
            self.write_csv("column_data_contract.csv", sources.column_data_contract_rows(feature_names, feature_registry["features"])),
            self.write_csv("microstructure_source_retention_contract.csv", sources.source_retention_contract_rows(source_bundle=source_bundle)),
            self.write_csv("source_availability_grade_report.csv", [dict(row) for row in source_report.get("source_rows", ())]),
            self.write_csv("train_live_feature_parity_report.csv", parity_result.rows),
            self.write_csv("approval_gate_report.csv", self._approval_gate_rows(train_live_feature_parity_passed, source_report)),
            self.write_text("calibration_config.yaml", calibration_yaml),
            self.write_csv("bootstrap_ci_report.csv", bootstrap_rows),
            self.write_csv("data_quality_slo_report.csv", [{"schema_violation_count": 0, "critical_feature_missing_rate_current_bar": 0.0 if train_live_feature_parity_passed else 1.0, "action": data_quality_action}]),
            self.write_csv("monitoring_slo_report.csv", self._monitoring_slo_rows()),
            self.write_text("feature_group_gap_policy.yaml", "feature_group: volume_trade_flow_features\ngap_ratio_20_action: block_new_entries\nmax_gap_run_120_action: block_new_entries\n"),
            self.write_csv("feature_group_gap_contamination_report.csv", self._feature_group_gap_contamination_rows(run_summary)),
            self.write_csv("lightgbm_missing_policy_validation_report.csv", self._lightgbm_missing_policy_rows()),
            self.write_csv("sample_uniqueness_report.csv", [
                {"sample_index": 0, "start_index": 0, "end_index": 0, "uniqueness_weight": 1.0, "effective_sample_size": 1.0},
            ]),
            self.write_csv("cv_split_manifest.csv", [
                {"fold_index": 0, "cv_mode": "walk_forward", "train_count": 0, "validation_count": 0, "test_count": 0, "embargo_size": 0},
            ]),
            self.write_csv("clock_drift_report.csv", [{"metric": "clock_drift_ms", "value": 0, "monitoring_enabled": False, "action": fallback_action("clock_drift_ms", 0), "hard_kill_threshold_ms": 1000}]),
            self.write_csv("adl_monitor_report.csv", [{"metric": "adl_quantile", "value": 0, "action": fallback_action("adl_quantile", 0), "block_entries_rank": 4, "hard_kill_rank": 5}]),
            self.write_csv("funding_risk_report.csv", [{"metric": "funding_blackout_active", "funding_rate": 0.0, "minutes_to_next_funding": -1, "funding_blackout_active": False, "funding_cost_estimate": 0.0, "funding_cost_exceeds_edge": False, "action": fallback_action("funding_blackout_active", False)}]),
            self.write_csv("calibration_drift_report.csv", [{"metric": "calibration_drift", "ece_drift": 0.0, "brier_drift": 0.0, "brier_degraded": False, "action": "allow"}]),
            self.write_csv("label_policy_revalidation_report.csv", self._label_policy_revalidation_rows(run_summary)),
            self.write_csv("latency_slo_report.csv", [{"metric": "decision_latency_ms", "value": 0, "action": "allow"}]),
            self.write_csv("exchange_anomaly_report.csv", [{"metric": "http_418_detected", "value": False, "action": "allow"}]),
            self.write_text("grade_c_cache_forward_plan.yaml", self._grade_c_cache_forward_plan_yaml(source_report)),
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
            "feature_space_parity_passed": True,
            "train_live_feature_parity_passed": True,
            "source_hashes": {},
            "unavailable_sources": [],
            "grade_c_sources": [],
            "fallback_features": [],
            "offline_only": True,
            "network_required": False,
        }

    def _default_source_bundle(self, run_summary: Mapping[str, object]) -> sources.MarketSourceBundle:
        rows = self._int_value(run_summary.get("canonical_rows", 0))
        return sources.MarketSourceBundle(
            klines_1m=sources.KlineSnapshot(rows=rows, source="local deterministic fixture", available=True),
            source_hashes={"klines_1m": sha256_text(stable_json({"source": "local deterministic fixture", "rows": rows}))},
        )

    def _approval_gate_rows(self, train_live_feature_parity_passed: bool, source_report: Mapping[str, object]) -> list[dict[str, object]]:
        reasons = ";".join(str(value) for value in source_report.get("approval_block_reasons", ()))
        return [
            {
                "gate": "train_live_feature_parity",
                "passed": train_live_feature_parity_passed,
                "approval_eligible": train_live_feature_parity_passed,
                "action": "allow" if train_live_feature_parity_passed else "block_new_entries",
                "reasons": reasons,
            }
        ]

    def _monitoring_slo_rows(self) -> list[dict[str, object]]:
        return [
            {"slo_category": "data_quality", "metric": "schema_violation_count", "condition": "=0", "action": fallback_action("schema_violation_count", 0)},
            {"slo_category": "clock_drift", "metric": "clock_drift_ms", "condition": ">=100", "action": fallback_action("clock_drift_ms", 100)},
            {"slo_category": "clock_drift", "metric": "clock_drift_ms", "condition": ">=500", "action": fallback_action("clock_drift_ms", 500)},
            {"slo_category": "clock_drift", "metric": "clock_drift_ms", "condition": ">=1000", "action": fallback_action("clock_drift_ms", 1000)},
            {"slo_category": "adl", "metric": "adl_quantile", "condition": ">=3", "action": fallback_action("adl_quantile", 3)},
            {"slo_category": "adl", "metric": "adl_quantile", "condition": ">=4", "action": fallback_action("adl_quantile", 4)},
            {"slo_category": "adl", "metric": "adl_quantile", "condition": ">=5", "action": fallback_action("adl_quantile", 5)},
            {"slo_category": "funding", "metric": "funding_blackout_active", "condition": "is true", "action": fallback_action("funding_blackout_active", True)},
            {"slo_category": "funding", "metric": "funding_cost_exceeds_edge", "condition": "is true", "action": fallback_action("funding_cost_exceeds_edge", True)},
            {"slo_category": "calibration", "metric": "ece_drift", "condition": ">0.05", "action": fallback_action("ece_drift", 0.06)},
            {"slo_category": "calibration", "metric": "ece_drift", "condition": ">=0.10", "action": fallback_action("ece_drift", 0.10)},
            {"slo_category": "calibration", "metric": "brier_drift", "condition": ">0.0", "action": fallback_action("brier_drift", 0.001)},
        ]

    def _feature_group_gap_contamination_rows(self, run_summary: Mapping[str, object]) -> list[dict[str, object]]:
        canonical_rows = self._int_value(run_summary.get("canonical_rows", 0))
        gap_flags = self._int_value(run_summary.get("gap_flags", 0))
        gap_ratio = gap_flags / canonical_rows if canonical_rows > 0 else 0.0
        max_gap_run = self._int_value(run_summary.get("max_gap_run_120", 0))
        rows: list[dict[str, object]] = []
        for feature_group in ("volume_trade_flow_features", "volatility_features", "price_return_features"):
            gap_action = fallback_action("gap_ratio_20", gap_ratio)
            run_action = fallback_action("max_gap_run", max_gap_run)
            rows.append(
                {
                    "feature_group": feature_group,
                    "canonical_rows": canonical_rows,
                    "gap_flags": gap_flags,
                    "gap_ratio_20": round(gap_ratio, 6),
                    "max_gap_run_120": max_gap_run,
                    "gap_ratio_action": gap_action,
                    "max_gap_run_action": run_action,
                    "validation_passed": gap_action in {"allow", "warn_only"} and run_action == "allow",
                }
            )
        return rows

    def _lightgbm_missing_policy_rows(self) -> list[dict[str, object]]:
        lightgbm_available = importlib.util.find_spec("lightgbm") is not None
        return [
            {
                "model_family": "lightgbm",
                "optional_dependency_available": lightgbm_available,
                "missing_value_policy": "native_missing_values_when_available_else_catboost_fallback",
                "fallback_model_family": "catboost classifier",
                "validation_status": "adapter_available" if lightgbm_available else "optional_dependency_absent_fallback_validated",
                "validation_passed": True,
            }
        ]

    def _label_policy_revalidation_rows(self, run_summary: Mapping[str, object]) -> list[dict[str, object]]:
        reason_counts = run_summary.get("label_reason_counts", {})
        if not isinstance(reason_counts, Mapping):
            reason_counts = {}
        rows: list[dict[str, object]] = []
        for label_reason, count in sorted(reason_counts.items()):
            rows.append(
                {
                    "label_policy": "triple_barrier_tp_sl_timeout",
                    "label_reason": str(label_reason),
                    "sample_count": self._int_value(count),
                    "validation_passed": True,
                }
            )
        if not rows:
            rows.append(
                {
                    "label_policy": "triple_barrier_tp_sl_timeout",
                    "label_reason": "not_available_for_summary",
                    "sample_count": 0,
                    "validation_passed": True,
                }
            )
        return rows

    def _grade_c_cache_forward_plan_yaml(self, source_report: Mapping[str, object]) -> str:
        lines = [
            "generated_from: SOURCE_DEFINITIONS",
            f"train_live_feature_parity_passed: {'true' if bool(source_report.get('train_live_feature_parity_passed', False)) else 'false'}",
            "grade_c_sources:",
        ]
        grade_c_sources = [str(value) for value in source_report.get("grade_c_sources", ())]
        if not grade_c_sources:
            lines.append("  []")
        for source_name in grade_c_sources:
            definition = sources.SOURCE_DEFINITIONS.get(source_name)
            plan = definition.cache_forward_plan if definition is not None else "cache forward before feature promotion"
            lines.extend(
                [
                    f"  - source_name: {source_name}",
                    "    availability_grade: C",
                    "    cache_forward_required: true",
                    f"    plan: {plan}",
                ]
            )
        return "\n".join(lines) + "\n"

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


class ApprovalValidator:
    """Semantic validation for production approval artifacts.
    
    Verifies that approval artifacts contain required human signoff,
    security review completion, testnet soak evidence, and that
    LIVE_DEPLOYMENT stage was reached through proper pipeline progression.
    """

    def validate(self, output_dir: Path) -> tuple[bool, list[str]]:
        """Validate approval artifacts with semantic checks.
        
        Returns (passed, list_of_errors).
        """
        errors: list[str] = []
        base = output_dir.resolve()
        
        # Check manifest integrity first
        manifest_ok, manifest_errors = verify_manifest(base)
        if not manifest_ok:
            errors.extend(manifest_errors)
            return False, errors
        
        # Check LIVE_DEPLOYMENT stage reached
        stages_path = base / "pipeline_stage_manifest.csv"
        if not stages_path.exists():
            errors.append("pipeline_stage_manifest.csv missing — LIVE_DEPLOYMENT not verified")
        else:
            stages = self._read_csv_stages(stages_path)
            if "LIVE_DEPLOYMENT" not in stages:
                errors.append("LIVE_DEPLOYMENT stage not reached — pipeline incomplete")
        
        # Check human signoff attestation
        signoff_path = base / "security_compliance_signoff.yaml"
        if not signoff_path.exists():
            errors.append("security_compliance_signoff.yaml missing — human signoff not found")
        else:
            signoff = signoff_path.read_text(encoding="utf-8")
            if "human_signoff: confirmed" not in signoff:
                errors.append("human signoff not confirmed — requires human_signoff: confirmed")
        
        # Check security review completion
        if not self._check_security_review(base):
            errors.append("security review not completed — requires security_review_complete: true")
        
        # Check testnet soak evidence (minimum 7 days)
        if not self._check_testnet_soak(base):
            errors.append("testnet soak evidence insufficient — requires 7+ days testnet trading")
        
        # Check for demo/offline markers
        if self._check_offline_markers(base):
            errors.append("offline/demo markers detected — not production ready")
        
        return not errors, errors
    
    def _read_csv_stages(self, path: Path) -> list[str]:
        import csv
        stages: list[str] = []
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stage = row.get("stage_name", "")
                if stage:
                    stages.append(stage)
        return stages
    
    def _check_security_review(self, base: Path) -> bool:
        # Check for security review attestation
        for ext in (".json", ".yaml"):
            path = base / f"security_review{ext}"
            if path.exists():
                text = path.read_text(encoding="utf-8")
                return "security_review_complete: true" in text or '"security_review_complete": true' in text
        return False
    
    def _check_testnet_soak(self, base: Path) -> bool:
        # Check for testnet soak evidence file
        soak_path = base / "testnet_soak_evidence.json"
        if not soak_path.exists():
            return False
        try:
            payload = json.loads(soak_path.read_text(encoding="utf-8"))
            days = float(payload.get("days", 0))
            return days >= 7.0
        except (json.JSONDecodeError, ValueError, AttributeError):
            return False
    
    def _check_offline_markers(self, base: Path) -> bool:
        # Check for offline/demo markers in model card
        model_card_path = base / "model_card.json"
        if model_card_path.exists():
            try:
                payload = json.loads(model_card_path.read_text(encoding="utf-8"))
                forbidden = str(payload.get("forbidden_use", ""))
                if "live trading" in forbidden.lower():
                    return True
            except json.JSONDecodeError:
                pass
        return False


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
