from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass
from typing import Mapping, Sequence

from . import feature_registry, features, sources


FEATURE_SCHEMA_FIELDS: tuple[str, ...] = (
    "feature_name",
    "category",
    "feature_group",
    "formula",
    "lookback",
    "min_samples",
    "warmup_rule",
    "dependencies",
    "source",
    "required_for_training",
    "required_for_live",
    "leakage_risk",
    "scaffold_status",
)

SOURCE_SCHEMA_FIELDS: tuple[str, ...] = (
    "source_name",
    "snapshot_type",
    "description",
    "columns",
    "feature_names",
    "historical_backfill",
    "local_archive_supported",
    "live_capture_required",
    "critical_live",
    "retention_days",
    "live_action",
    "cache_forward_plan",
)

DEFAULT_WARMUP_POLICY: dict[str, object] = {
    "rolling_windows": "strict_no_partial_window",
    "warmup_flag": "warmup_invalid_until_max_feature_min_samples_minus_one",
    "label_policy": "exclude_warmup_rows_unless_explicit_historical_input",
}

DEFAULT_MISSING_VALUE_POLICY: dict[str, object] = {
    "finite_requirement": "features must be finite before model use",
    "non_finite_after_clip": "None",
    "nan_source_classes": ("outage_nan", "warmup_nan", "structural_nan", "isolated_feature_nan"),
    "forward_fill": False,
}

DEFAULT_CLIPPING_POLICY: dict[str, object] = {
    "clipper": "FeatureClipper",
    "limits": dict(sorted(features.FeatureClipper.LIMITS.items())),
    "non_finite_policy": "set_none",
}


@dataclass(frozen=True)
class FeatureParityResult:
    passed: bool
    feature_names_match: bool
    calculation_order_match: bool
    source_requirements_match: bool
    warmup_handling_match: bool
    missing_value_policy_match: bool
    clipping_policy_match: bool
    dependency_graph_hash_match: bool
    source_availability_match: bool
    training_feature_schema_hash: str
    live_feature_schema_hash: str
    training_source_schema_hash: str
    live_source_schema_hash: str
    training_dependency_graph_hash: str
    live_dependency_graph_hash: str
    dependency_graph_hash: str
    documented_grade_c_fallback: bool
    reasons: tuple[str, ...]
    rows: tuple[dict[str, object], ...]

    def checks(self) -> dict[str, bool]:
        return {
            "feature_names_match": self.feature_names_match,
            "calculation_order_match": self.calculation_order_match,
            "source_requirements_match": self.source_requirements_match,
            "warmup_handling_match": self.warmup_handling_match,
            "missing_value_policy_match": self.missing_value_policy_match,
            "clipping_policy_match": self.clipping_policy_match,
            "dependency_graph_hash_match": self.dependency_graph_hash_match,
            "source_availability_match": self.source_availability_match,
        }

    def as_metadata(self) -> dict[str, object]:
        return {
            "feature_parity_passed": self.passed,
            "feature_schema_hash": self.training_feature_schema_hash if self.feature_names_match else "",
            "training_feature_schema_hash": self.training_feature_schema_hash,
            "live_feature_schema_hash": self.live_feature_schema_hash,
            "source_schema_hash": self.training_source_schema_hash if self.training_source_schema_hash == self.live_source_schema_hash else "",
            "training_source_schema_hash": self.training_source_schema_hash,
            "live_source_schema_hash": self.live_source_schema_hash,
            "dependency_graph_hash": self.dependency_graph_hash,
            "training_dependency_graph_hash": self.training_dependency_graph_hash,
            "live_dependency_graph_hash": self.live_dependency_graph_hash,
            "parity_checks": self.checks(),
            "parity_reasons": list(self.reasons),
            "documented_grade_c_fallback": self.documented_grade_c_fallback,
        }


class FeatureParityCheck:
    def __init__(
        self,
        training_features: Mapping[str, object] | Sequence[Mapping[str, object]],
        live_features: Mapping[str, object] | Sequence[Mapping[str, object]] | None = None,
        training_source_schema: Mapping[str, object] | Sequence[Mapping[str, object]] | None = None,
        live_source_schema: Mapping[str, object] | Sequence[Mapping[str, object]] | None = None,
        source_report: Mapping[str, object] | None = None,
        training_missing_value_policy: Mapping[str, object] | None = None,
        live_missing_value_policy: Mapping[str, object] | None = None,
        training_clipping_policy: Mapping[str, object] | None = None,
        live_clipping_policy: Mapping[str, object] | None = None,
        training_feature_names: Sequence[str] | None = None,
        live_feature_names: Sequence[str] | None = None,
    ) -> None:
        self.training_features = training_features
        self.live_features = live_features if live_features is not None else training_features
        self.training_source_schema = training_source_schema
        self.live_source_schema = live_source_schema if live_source_schema is not None else training_source_schema
        self.source_report = source_report
        self.training_missing_value_policy = dict(training_missing_value_policy or DEFAULT_MISSING_VALUE_POLICY)
        self.live_missing_value_policy = dict(live_missing_value_policy or DEFAULT_MISSING_VALUE_POLICY)
        self.training_clipping_policy = dict(training_clipping_policy or DEFAULT_CLIPPING_POLICY)
        self.live_clipping_policy = dict(live_clipping_policy or DEFAULT_CLIPPING_POLICY)
        self.training_feature_names = tuple(training_feature_names) if training_feature_names is not None else None
        self.live_feature_names = tuple(live_feature_names) if live_feature_names is not None else None

    def run(self) -> FeatureParityResult:
        training_rows = _feature_rows(self.training_features, self.training_feature_names)
        live_rows = _feature_rows(self.live_features, self.live_feature_names)
        training_names = _feature_names(training_rows)
        live_names = _feature_names(live_rows)
        training_order = _calculation_order(training_rows)
        live_order = _calculation_order(live_rows)
        training_sources = _source_requirements(training_rows)
        live_sources = _source_requirements(live_rows)
        training_warmup = _warmup_handling(training_rows)
        live_warmup = _warmup_handling(live_rows)
        training_feature_hash = _hash(training_rows)
        live_feature_hash = _hash(live_rows)
        training_source_hash = source_schema_hash(self.training_source_schema)
        live_source_hash = source_schema_hash(self.live_source_schema)
        training_graph_hash = _dependency_graph_hash(training_rows)
        live_graph_hash = _dependency_graph_hash(live_rows)
        source_availability_match, source_availability_detail, documented_grade_c = _source_availability_check(live_sources, self.source_report)

        feature_names_match = training_names == live_names
        calculation_order_match = training_order == live_order
        source_requirements_match = training_sources == live_sources
        warmup_handling_match = training_warmup == live_warmup and DEFAULT_WARMUP_POLICY == DEFAULT_WARMUP_POLICY
        missing_value_policy_match = _jsonable(self.training_missing_value_policy) == _jsonable(self.live_missing_value_policy)
        clipping_policy_match = _jsonable(self.training_clipping_policy) == _jsonable(self.live_clipping_policy)
        dependency_graph_hash_match = training_graph_hash == live_graph_hash

        checks = {
            "feature_names_match": feature_names_match,
            "calculation_order_match": calculation_order_match,
            "source_requirements_match": source_requirements_match,
            "warmup_handling_match": warmup_handling_match,
            "missing_value_policy_match": missing_value_policy_match,
            "clipping_policy_match": clipping_policy_match,
            "dependency_graph_hash_match": dependency_graph_hash_match,
            "source_availability_match": source_availability_match,
        }
        reasons = tuple(check_name for check_name, passed in checks.items() if not passed)
        passed = all(checks.values())
        rows = (
            _report_row("feature_names_match", feature_names_match, training_names, live_names),
            _report_row("calculation_order_match", calculation_order_match, training_order, live_order),
            _report_row("source_requirements_match", source_requirements_match, training_sources, live_sources),
            _report_row("warmup_handling_match", warmup_handling_match, training_warmup, live_warmup),
            _report_row("missing_value_policy_match", missing_value_policy_match, self.training_missing_value_policy, self.live_missing_value_policy),
            _report_row("clipping_policy_match", clipping_policy_match, self.training_clipping_policy, self.live_clipping_policy),
            _report_row("dependency_graph_hash_match", dependency_graph_hash_match, training_graph_hash, live_graph_hash),
            _report_row("source_availability_match", source_availability_match, source_availability_detail, source_availability_detail),
        )
        return FeatureParityResult(
            passed=passed,
            feature_names_match=feature_names_match,
            calculation_order_match=calculation_order_match,
            source_requirements_match=source_requirements_match,
            warmup_handling_match=warmup_handling_match,
            missing_value_policy_match=missing_value_policy_match,
            clipping_policy_match=clipping_policy_match,
            dependency_graph_hash_match=dependency_graph_hash_match,
            source_availability_match=source_availability_match,
            training_feature_schema_hash=training_feature_hash,
            live_feature_schema_hash=live_feature_hash,
            training_source_schema_hash=training_source_hash,
            live_source_schema_hash=live_source_hash,
            training_dependency_graph_hash=training_graph_hash,
            live_dependency_graph_hash=live_graph_hash,
            dependency_graph_hash=training_graph_hash if dependency_graph_hash_match else "",
            documented_grade_c_fallback=documented_grade_c,
            reasons=reasons,
            rows=rows,
        )


def compare_training_live_features(
    training_features: Mapping[str, object] | Sequence[Mapping[str, object]],
    live_features: Mapping[str, object] | Sequence[Mapping[str, object]] | None = None,
    training_source_schema: Mapping[str, object] | Sequence[Mapping[str, object]] | None = None,
    live_source_schema: Mapping[str, object] | Sequence[Mapping[str, object]] | None = None,
    source_report: Mapping[str, object] | None = None,
    training_missing_value_policy: Mapping[str, object] | None = None,
    live_missing_value_policy: Mapping[str, object] | None = None,
    training_clipping_policy: Mapping[str, object] | None = None,
    live_clipping_policy: Mapping[str, object] | None = None,
    training_feature_names: Sequence[str] | None = None,
    live_feature_names: Sequence[str] | None = None,
) -> FeatureParityResult:
    return FeatureParityCheck(
        training_features,
        live_features,
        training_source_schema,
        live_source_schema,
        source_report,
        training_missing_value_policy,
        live_missing_value_policy,
        training_clipping_policy,
        live_clipping_policy,
        training_feature_names,
        live_feature_names,
    ).run()


def feature_schema_hash(feature_schema: Mapping[str, object] | Sequence[Mapping[str, object]], feature_names: Sequence[str] | None = None) -> str:
    return _hash(_feature_rows(feature_schema, tuple(feature_names) if feature_names is not None else None))


def source_schema_hash(source_schema: Mapping[str, object] | Sequence[Mapping[str, object]] | None = None) -> str:
    return _hash(_source_schema_rows(source_schema))


def _feature_rows(feature_schema: Mapping[str, object] | Sequence[Mapping[str, object]], feature_names: Sequence[str] | None = None) -> tuple[dict[str, object], ...]:
    if isinstance(feature_schema, Mapping):
        raw_rows = feature_schema.get("features", ())
    else:
        raw_rows = feature_schema
    requested = tuple(str(name) for name in feature_names) if feature_names is not None else None
    requested_set = set(requested) if requested is not None else None
    rows: list[dict[str, object]] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping):
            continue
        row = _normalize_feature_row(raw_row)
        name = str(row.get("feature_name", ""))
        if requested_set is not None and name not in requested_set:
            continue
        # Include all registered features (even pending_data_source) in parity checks
        rows.append(row)
    if requested is None:
        return tuple(rows)
    by_name = {str(row.get("feature_name", "")): row for row in rows}
    return tuple(by_name[name] for name in requested if name in by_name)


def _normalize_feature_row(row: Mapping[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for field in FEATURE_SCHEMA_FIELDS:
        value = row.get(field)
        if field == "dependencies":
            normalized[field] = tuple(str(dependency) for dependency in _sequence(value))
        elif field in {"lookback", "min_samples"}:
            normalized[field] = int(value or 0)
        elif field in {"required_for_training", "required_for_live"}:
            normalized[field] = bool(True if value is None else value)
        else:
            normalized[field] = "" if value is None else str(value)
    return normalized


def _feature_names(rows: Sequence[Mapping[str, object]]) -> tuple[str, ...]:
    return tuple(str(row.get("feature_name", "")) for row in rows)


def _calculation_order(rows: Sequence[Mapping[str, object]]) -> tuple[str, ...]:
    graph = feature_registry.dependency_graph_from_feature_rows(rows)
    return tuple(str(name) for name in graph.get("calculation_order", ()))


def _dependency_graph_hash(rows: Sequence[Mapping[str, object]]) -> str:
    graph = feature_registry.dependency_graph_from_feature_rows(rows)
    return _hash(graph)


def _source_requirements(rows: Sequence[Mapping[str, object]]) -> dict[str, tuple[str, ...]]:
    names = _feature_names(rows)
    return sources.required_sources_for_features(names, rows)


def _warmup_handling(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return {
        "policy": dict(DEFAULT_WARMUP_POLICY),
        "features": {
            str(row.get("feature_name", "")): {
                "warmup_rule": str(row.get("warmup_rule", "strict")),
                "min_samples": int(row.get("min_samples", 1)),
                "lookback": int(row.get("lookback", 1)),
            }
            for row in rows
        },
    }


def _source_schema_rows(source_schema: Mapping[str, object] | Sequence[Mapping[str, object]] | None) -> tuple[dict[str, object], ...]:
    raw_schema: Mapping[str, object] | Sequence[Mapping[str, object]] = sources.SOURCE_DEFINITIONS if source_schema is None else source_schema
    rows: list[dict[str, object]] = []
    if isinstance(raw_schema, Mapping):
        if "sources" in raw_schema and isinstance(raw_schema["sources"], Sequence):
            for row in raw_schema["sources"]:
                if isinstance(row, Mapping):
                    rows.append(_normalize_source_row(row))
        elif "source_rows" in raw_schema and isinstance(raw_schema["source_rows"], Sequence):
            for row in raw_schema["source_rows"]:
                if isinstance(row, Mapping):
                    rows.append(_normalize_source_row(row))
        else:
            for source_name in sorted(str(key) for key in raw_schema.keys()):
                value = raw_schema[source_name]
                if is_dataclass(value):
                    row = asdict(value)
                elif isinstance(value, Mapping):
                    row = dict(value)
                else:
                    continue
                row.setdefault("source_name", source_name)
                rows.append(_normalize_source_row(row))
    else:
        for row in raw_schema:
            if isinstance(row, Mapping):
                rows.append(_normalize_source_row(row))
    return tuple(rows)


def _normalize_source_row(row: Mapping[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for field in SOURCE_SCHEMA_FIELDS:
        value = row.get(field)
        if field in {"columns", "feature_names"}:
            normalized[field] = tuple(str(item) for item in _sequence(value))
        elif field in {"historical_backfill", "local_archive_supported", "live_capture_required", "critical_live"}:
            normalized[field] = bool(value)
        elif field == "retention_days":
            normalized[field] = int(value or 0)
        else:
            normalized[field] = "" if value is None else str(value)
    return normalized


def _source_availability_check(live_sources: Mapping[str, Sequence[str]], source_report: Mapping[str, object] | None) -> tuple[bool, dict[str, object], bool]:
    required_sources = sorted({source_name for source_names in live_sources.values() for source_name in source_names})
    if source_report is None:
        return True, {"required_sources": required_sources, "unavailable_sources": (), "grade_c_sources": (), "fallback_features": ()}, False
    unavailable_sources = _string_set(source_report.get("unavailable_sources", ()))
    grade_c_sources = _string_set(source_report.get("grade_c_sources", ()))
    fallback_features = _string_set(source_report.get("fallback_features", ()))
    documented_grade_c_sources = _string_set(source_report.get("documented_grade_c_fallbacks", ()))
    missing_required = sorted(source_name for source_name in required_sources if source_name in unavailable_sources)
    undocumented_missing: list[str] = []
    documented_missing: list[str] = []
    for source_name in missing_required:
        dependent_features = sorted(feature_name for feature_name, source_names in live_sources.items() if source_name in source_names)
        documented = _documented_grade_c_fallback(source_name, dependent_features, grade_c_sources, fallback_features, documented_grade_c_sources)
        if documented:
            documented_missing.append(source_name)
        else:
            undocumented_missing.append(source_name)
    return (
        not undocumented_missing,
        {
            "required_sources": tuple(required_sources),
            "unavailable_sources": tuple(sorted(unavailable_sources)),
            "grade_c_sources": tuple(sorted(grade_c_sources)),
            "fallback_features": tuple(sorted(fallback_features)),
            "documented_grade_c_sources": tuple(sorted(documented_missing)),
            "undocumented_missing_sources": tuple(undocumented_missing),
        },
        bool(documented_missing),
    )


def _documented_grade_c_fallback(
    source_name: str,
    dependent_features: Sequence[str],
    grade_c_sources: set[str],
    fallback_features: set[str],
    documented_grade_c_sources: set[str],
) -> bool:
    if source_name in documented_grade_c_sources:
        return True
    if source_name not in grade_c_sources:
        return False
    if dependent_features and any(feature_name not in fallback_features for feature_name in dependent_features):
        return False
    definition = sources.SOURCE_DEFINITIONS.get(source_name)
    return bool(definition is not None and definition.cache_forward_plan)


def _report_row(check_name: str, passed: bool, training_value: object, live_value: object) -> dict[str, object]:
    return {
        "check_name": check_name,
        "passed": passed,
        "training_value_hash": _hash(training_value),
        "live_value_hash": _hash(live_value),
        "training_value": _compact_json(training_value),
        "live_value": _compact_json(live_value),
    }


def _hash(payload: object) -> str:
    return hashlib.sha256(_compact_json(payload).encode("utf-8")).hexdigest()


def _compact_json(payload: object) -> str:
    return json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _jsonable(payload: object) -> object:
    if is_dataclass(payload):
        return _jsonable(asdict(payload))
    if isinstance(payload, Mapping):
        return {str(key): _jsonable(value) for key, value in sorted(payload.items(), key=lambda item: str(item[0]))}
    if isinstance(payload, (str, int, float, bool)) or payload is None:
        return payload
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return [_jsonable(value) for value in payload]
    return str(payload)


def _sequence(value: object) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    return (value,)


def _string_set(value: object) -> set[str]:
    return {str(item) for item in _sequence(value)}
