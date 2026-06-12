from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ClipResult:
    values: dict[str, float | None]
    report: list[dict[str, str | int | float]]


class FeatureClipper:
    LIMITS = {
        "zscore": 10.0,
        "ratio": 100.0,
        "return": 0.20,
        "vol_adj": 10.0,
    }

    def classify(self, feature_name: str) -> str:
        lower = feature_name.lower()
        if "vol_adj" in lower:
            return "vol_adj"
        if "zscore" in lower:
            return "zscore"
        if "ratio" in lower or "pct" in lower or "vs_" in lower:
            return "ratio"
        if "return" in lower:
            return "return"
        return "ratio"

    def clip(self, features: Mapping[str, float]) -> ClipResult:
        values: dict[str, float | None] = {}
        report: list[dict[str, str | int | float]] = []
        for name, raw in sorted(features.items()):
            feature_type = self.classify(name)
            limit = self.LIMITS[feature_type]
            inf_count = 0 if isfinite(raw) else 1
            clipped_count = 0
            value: float | None
            if not isfinite(raw):
                value = None
            else:
                value = max(-limit, min(limit, raw))
                clipped_count = 1 if value != raw else 0
            values[name] = value
            report.append(
                {
                    "feature_name": name,
                    "feature_type": feature_type,
                    "clip_abs": limit,
                    "inf_count": inf_count,
                    "clipped_count": clipped_count,
                    "nan_after_clip": 1 if value is None else 0,
                }
            )
        return ClipResult(values, report)


class NaNSourceClassifier:
    def __init__(self, optional_noncritical_features: set[str] | None = None) -> None:
        self.optional_noncritical_features = optional_noncritical_features or set()

    def classify(self, row: Mapping[str, int | bool | float | str], feature_name: str) -> str:
        outage_flags = (
            "gap_flag",
            "canonical_candle_repaired",
            "stream_desync_detected",
            "rest_repair_failed",
            "gap_restored_raw_trade_flow_nan",
        )
        if any(bool(row.get(flag, 0)) for flag in outage_flags):
            return "outage_nan"
        if bool(row.get("warmup_invalid", 0)):
            return "warmup_nan"
        if feature_name in self.optional_noncritical_features:
            return "structural_nan"
        return "isolated_feature_nan"


def finite_or_none(value: float) -> float | None:
    return value if isfinite(value) else None


class RollingFeatureEngine:
    """Strict rolling features: no partial windows and no backfill."""

    def rolling_mean(self, values: Sequence[float], window: int) -> list[float | None]:
        if window <= 0:
            raise ValueError("window must be positive")
        output: list[float | None] = []
        for index in range(len(values)):
            if index + 1 < window:
                output.append(None)
            else:
                output.append(mean(values[index + 1 - window:index + 1]))
        return output


class CalibrationModule:
    def select_method(self, positive_samples: int) -> str:
        if positive_samples < 50:
            return "platt"
        if positive_samples < 200:
            return "platt_or_beta"
        if positive_samples < 500:
            return "platt_beta_or_isotonic"
        return "all_methods_allowed"


@dataclass(frozen=True)
class Split:
    train: range
    validation: range
    test: range


class PurgedWalkForwardSplit:
    def split(self, n_rows: int, train_size: int, validation_size: int, test_size: int, purge_gap: int) -> list[Split]:
        if min(n_rows, train_size, validation_size, test_size) <= 0 or purge_gap < 0:
            raise ValueError("invalid split input")
        splits: list[Split] = []
        start = 0
        stride = test_size
        while start + train_size + purge_gap + validation_size + purge_gap + test_size <= n_rows:
            train_end = start + train_size
            validation_start = train_end + purge_gap
            validation_end = validation_start + validation_size
            test_start = validation_end + purge_gap
            test_end = test_start + test_size
            splits.append(Split(range(start, train_end), range(validation_start, validation_end), range(test_start, test_end)))
            start += stride
        return splits


class FeatureSelectionPipeline:
    def core_features(self, fold_masks: Sequence[Sequence[str]], min_survival_ratio: float = 0.60) -> list[str]:
        if not fold_masks:
            return []
        counts: dict[str, int] = {}
        for mask in fold_masks:
            for feature in set(mask):
                counts[feature] = counts.get(feature, 0) + 1
        required = len(fold_masks) * min_survival_ratio
        return sorted(feature for feature, count in counts.items() if count >= required)


class BootstrapCIEngine:
    def ci95(self, values: Sequence[float]) -> tuple[float, float]:
        if not values:
            return (0.0, 0.0)
        ordered = sorted(values)
        lower_index = int((len(ordered) - 1) * 0.025)
        upper_index = int((len(ordered) - 1) * 0.975)
        return (ordered[lower_index], ordered[upper_index])


class OptunaBudgetProfiles:
    PROFILES = {
        "research_fast": {"trials": 50, "bootstrap_samples": 100},
        "practical_start": {"trials": 200, "bootstrap_samples": 500},
        "full_audit_budget": {"trials": 1000, "bootstrap_samples": 1000},
    }

    def get(self, name: str) -> dict[str, int]:
        if name not in self.PROFILES:
            raise ValueError(f"unknown budget profile: {name}")
        return dict(self.PROFILES[name])


class ChampionChallengerManager:
    def can_promote(self, shadow_days: int, signal_count: int, mdd_delta: float, calmar_delta: float) -> tuple[bool, str]:
        if shadow_days < 30:
            return False, "shadow duration too short"
        if signal_count < 100:
            return False, "insufficient shadow signals"
        if mdd_delta > 0.0:
            return False, "challenger worsens MDD"
        if calmar_delta < 0.0:
            return False, "challenger worsens Calmar"
        return True, "promotion gates passed"
