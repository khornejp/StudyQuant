from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Callable, Mapping, Sequence

from . import sources


@dataclass(frozen=True)
class MonitoringDecision:
    metric: str
    value: float | int | bool
    action: str
    reason: str

    def as_row(self) -> dict[str, object]:
        return {
            "metric": self.metric,
            "value": self.value,
            "action": self.action,
            "reason": self.reason,
        }


class ClockDriftService:
    allow_threshold_ms = 100
    block_threshold_ms = 500
    hard_kill_threshold_ms = 1000

    def __init__(
        self,
        server_time_reader: Callable[[], datetime | int | float | str] | None = None,
        local_clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.server_time_reader = server_time_reader
        self.local_clock = local_clock or (lambda: datetime.now(timezone.utc))

    def drift_ms(self, server_time: datetime | int | float | str, local_time: datetime | int | float | str | None = None) -> int:
        local_value = local_time if local_time is not None else self.local_clock()
        return int(round(abs(_millis(server_time) - _millis(local_value))))

    def action(self, clock_drift_ms: int | float) -> str:
        drift = abs(float(clock_drift_ms))
        if drift >= self.hard_kill_threshold_ms:
            return "hard_kill"
        if drift >= self.block_threshold_ms:
            return "block_new_entries"
        if drift >= self.allow_threshold_ms:
            return "warn_only"
        return "allow"

    def evaluate(self, server_time: datetime | int | float | str | None = None) -> dict[str, object]:
        if server_time is None:
            if self.server_time_reader is None:
                return {
                    "metric": "clock_drift_ms",
                    "clock_drift_ms": 0,
                    "action": "allow",
                    "reason": "clock drift monitor disabled; no server_time_reader configured",
                    "monitoring_enabled": False,
                    "allow_threshold_ms": self.allow_threshold_ms,
                    "block_threshold_ms": self.block_threshold_ms,
                    "hard_kill_threshold_ms": self.hard_kill_threshold_ms,
                }
            server_time = self.server_time_reader()
        drift = self.drift_ms(server_time)
        action = self.action(drift)
        return {
            "metric": "clock_drift_ms",
            "clock_drift_ms": drift,
            "action": action,
            "reason": f"clock drift {drift}ms -> {action}",
            "monitoring_enabled": True,
            "allow_threshold_ms": self.allow_threshold_ms,
            "block_threshold_ms": self.block_threshold_ms,
            "hard_kill_threshold_ms": self.hard_kill_threshold_ms,
        }


class ADLMonitorService:
    reduce_size_rank = 3
    block_entries_rank = 4
    hard_kill_rank = 5

    def rank(self, snapshot: int | Mapping[str, object] | sources.ADLSnapshot | None) -> int:
        if snapshot is None:
            return 0
        if isinstance(snapshot, int):
            return snapshot
        if isinstance(snapshot, Mapping):
            return int(snapshot.get("rank", snapshot.get("quantile", 0)))
        return int(getattr(snapshot, "quantile", 0))

    def action(self, adl_quantile: int | float) -> str:
        rank = int(adl_quantile)
        if rank >= self.hard_kill_rank:
            return "hard_kill"
        if rank >= self.block_entries_rank:
            return "block_new_entries"
        if rank >= self.reduce_size_rank:
            return "reduce_size"
        return "allow"

    def evaluate(self, snapshot: int | Mapping[str, object] | sources.ADLSnapshot | None) -> dict[str, object]:
        rank = self.rank(snapshot)
        action = self.action(rank)
        return {
            "metric": "adl_quantile",
            "adl_quantile": rank,
            "action": action,
            "reason": f"ADL rank {rank} -> {action}",
            "reduce_size_rank": self.reduce_size_rank,
            "block_entries_rank": self.block_entries_rank,
            "hard_kill_rank": self.hard_kill_rank,
        }


class FundingMonitorService:
    def __init__(self, blackout_window_minutes: int = 5, funding_interval: timedelta = timedelta(hours=8)) -> None:
        self.blackout_window_minutes = blackout_window_minutes
        self.funding_interval = funding_interval

    def evaluate(
        self,
        snapshot: sources.FundingSnapshot | Mapping[str, object] | None,
        now: datetime | None = None,
        position_notional: float = 0.0,
        expected_edge: float = 0.0,
    ) -> dict[str, object]:
        current_time = _aware_utc(now or datetime.now(timezone.utc))
        funding_rate = _float_from_snapshot(snapshot, "funding_rate", 0.0)
        next_funding_time = _datetime_from_snapshot(snapshot, "next_funding_time")
        minutes_to_next = self.minutes_to_next_funding(current_time, next_funding_time)
        blackout_active = self.blackout_active(minutes_to_next)
        funding_cost_estimate = abs(float(position_notional) * funding_rate)
        funding_cost_exceeds_edge = funding_cost_estimate > abs(float(expected_edge)) if expected_edge != 0.0 else False
        action = "block_new_entries" if blackout_active else "warn_only" if funding_cost_exceeds_edge else "allow"
        return {
            "metric": "funding_risk",
            "funding_rate": funding_rate,
            "next_funding_time": next_funding_time.isoformat() if next_funding_time is not None else "",
            "funding_interval_minutes": int(self.funding_interval.total_seconds() // 60),
            "minutes_to_next_funding": minutes_to_next,
            "funding_blackout_active": blackout_active,
            "funding_cost_estimate": funding_cost_estimate,
            "expected_edge": float(expected_edge),
            "funding_cost_exceeds_edge": funding_cost_exceeds_edge,
            "action": action,
        }

    def minutes_to_next_funding(self, now: datetime, next_funding_time: datetime | None) -> int:
        if next_funding_time is None:
            return -1
        elapsed = next_funding_time - _aware_utc(now)
        return int(elapsed.total_seconds() // 60)

    def blackout_active(self, minutes_to_next_funding: int) -> bool:
        return 0 <= minutes_to_next_funding <= self.blackout_window_minutes


class CalibrationDriftMonitor:
    warning_ece = 0.05
    raise_threshold_ece = 0.10

    def ece(self, probabilities: Sequence[float], labels: Sequence[int], bins: int = 10) -> float:
        return self.expected_calibration_error(probabilities, labels, bins)

    def expected_calibration_error(self, probabilities: Sequence[float], labels: Sequence[int], bins: int = 10) -> float:
        if not probabilities or not labels:
            return 0.0
        _validate_probability_inputs(probabilities, labels, bins)
        total = len(labels)
        error = 0.0
        for bucket_probabilities, bucket_labels in _calibration_bins(probabilities, labels, bins):
            if not bucket_probabilities:
                continue
            confidence = mean(bucket_probabilities)
            accuracy = mean(bucket_labels)
            error += (len(bucket_labels) / total) * abs(accuracy - confidence)
        return error

    def mce(self, probabilities: Sequence[float], labels: Sequence[int], bins: int = 10) -> float:
        return self.maximum_calibration_error(probabilities, labels, bins)

    def maximum_calibration_error(self, probabilities: Sequence[float], labels: Sequence[int], bins: int = 10) -> float:
        if not probabilities or not labels:
            return 0.0
        _validate_probability_inputs(probabilities, labels, bins)
        maximum = 0.0
        for bucket_probabilities, bucket_labels in _calibration_bins(probabilities, labels, bins):
            if not bucket_probabilities:
                continue
            maximum = max(maximum, abs(mean(bucket_labels) - mean(bucket_probabilities)))
        return maximum

    def brier(self, probabilities: Sequence[float], labels: Sequence[int]) -> float:
        return self.brier_score(probabilities, labels)

    def brier_score(self, probabilities: Sequence[float], labels: Sequence[int]) -> float:
        if not probabilities or not labels:
            return 0.0
        _validate_probability_inputs(probabilities, labels, bins=1)
        return mean([(probability - label) ** 2 for probability, label in zip(probabilities, labels)])

    def brier_skill_score(self, probabilities: Sequence[float], labels: Sequence[int], baseline_probability: float | None = None) -> float:
        if not probabilities or not labels:
            return 0.0
        baseline = mean(labels) if baseline_probability is None else float(baseline_probability)
        baseline_brier = mean([(baseline - label) ** 2 for label in labels])
        current_brier = self.brier_score(probabilities, labels)
        if baseline_brier == 0.0:
            return 1.0 if current_brier == 0.0 else 0.0
        return 1.0 - current_brier / baseline_brier

    def action(self, ece_value: float) -> str:
        if ece_value >= self.raise_threshold_ece:
            return "raise_threshold"
        if ece_value > self.warning_ece:
            return "warn_only"
        return "allow"

    def evaluate(
        self,
        probabilities: Sequence[float],
        labels: Sequence[int],
        baseline: Mapping[str, object] | None = None,
        bins: int = 10,
    ) -> dict[str, object]:
        current_ece = self.expected_calibration_error(probabilities, labels, bins)
        current_mce = self.maximum_calibration_error(probabilities, labels, bins)
        current_brier = self.brier_score(probabilities, labels)
        skill_score = self.brier_skill_score(probabilities, labels)
        baseline_ece = _float_from_mapping(baseline, "ece", 0.0)
        baseline_brier = _float_from_mapping(baseline, "brier", current_brier)
        ece_drift = current_ece - baseline_ece
        brier_drift = current_brier - baseline_brier
        action = self.action(current_ece)
        return {
            "metric": "calibration_drift",
            "ece": current_ece,
            "mce": current_mce,
            "brier": current_brier,
            "brier_skill_score": skill_score,
            "baseline_ece": baseline_ece,
            "baseline_brier": baseline_brier,
            "ece_drift": ece_drift,
            "brier_drift": brier_drift,
            "brier_degraded": brier_drift > 0.0,
            "action": action,
        }

    def rolling_window_comparison(
        self,
        probabilities: Sequence[float],
        labels: Sequence[int],
        baseline: Mapping[str, object] | None = None,
        window_size: int = 100,
        bins: int = 10,
    ) -> dict[str, object]:
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        return self.evaluate(probabilities[-window_size:], labels[-window_size:], baseline=baseline, bins=bins)


class MonitoringReportWriter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_clock_drift_report(self, rows: Sequence[Mapping[str, object]]) -> Path:
        return self.write_csv("clock_drift_report.csv", rows)

    def write_adl_monitor_report(self, rows: Sequence[Mapping[str, object]]) -> Path:
        return self.write_csv("adl_monitor_report.csv", rows)

    def write_funding_risk_report(self, rows: Sequence[Mapping[str, object]]) -> Path:
        return self.write_csv("funding_risk_report.csv", rows)

    def write_calibration_drift_report(self, rows: Sequence[Mapping[str, object]]) -> Path:
        return self.write_csv("calibration_drift_report.csv", rows)

    def write_all(
        self,
        clock_rows: Sequence[Mapping[str, object]],
        adl_rows: Sequence[Mapping[str, object]],
        funding_rows: Sequence[Mapping[str, object]],
        calibration_rows: Sequence[Mapping[str, object]],
    ) -> list[Path]:
        return [
            self.write_clock_drift_report(clock_rows),
            self.write_adl_monitor_report(adl_rows),
            self.write_funding_risk_report(funding_rows),
            self.write_calibration_drift_report(calibration_rows),
        ]

    def write_csv(self, relative_path: str, rows: Sequence[Mapping[str, object]]) -> Path:
        path = self.output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized_rows = [dict(row) for row in rows]
        fieldnames = sorted({key for row in normalized_rows for key in row.keys()}) or ["metric", "action"]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in normalized_rows:
                writer.writerow(row)
        return path


def _calibration_bins(probabilities: Sequence[float], labels: Sequence[int], bins: int) -> list[tuple[list[float], list[int]]]:
    buckets: list[tuple[list[float], list[int]]] = [([], []) for _ in range(bins)]
    for probability, label in zip(probabilities, labels):
        index = min(bins - 1, int(max(0.0, min(1.0, probability)) * bins))
        buckets[index][0].append(float(probability))
        buckets[index][1].append(int(label))
    return buckets


def _validate_probability_inputs(probabilities: Sequence[float], labels: Sequence[int], bins: int) -> None:
    if len(probabilities) != len(labels):
        raise ValueError("probabilities and labels must have the same length")
    if bins <= 0:
        raise ValueError("bins must be positive")


def _float_from_snapshot(snapshot: sources.FundingSnapshot | Mapping[str, object] | None, field_name: str, default: float) -> float:
    if snapshot is None:
        return default
    if isinstance(snapshot, Mapping):
        return float(snapshot.get(field_name, default) or default)
    return float(getattr(snapshot, field_name, default) or default)


def _datetime_from_snapshot(snapshot: sources.FundingSnapshot | Mapping[str, object] | None, field_name: str) -> datetime | None:
    if snapshot is None:
        return None
    value = snapshot.get(field_name) if isinstance(snapshot, Mapping) else getattr(snapshot, field_name, None)
    if value in (None, ""):
        return None
    return _datetime(value)


def _float_from_mapping(payload: Mapping[str, object] | None, field_name: str, default: float) -> float:
    if payload is None:
        return default
    return float(payload.get(field_name, default) or default)


def _datetime(value: datetime | int | float | str) -> datetime:
    if isinstance(value, datetime):
        return _aware_utc(value)
    if isinstance(value, (int, float)):
        number = float(value)
        if abs(number) > 10_000_000_000:
            number /= 1000.0
        return datetime.fromtimestamp(number, tz=timezone.utc)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return _aware_utc(parsed)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _millis(value: datetime | int | float | str) -> int:
    if isinstance(value, (int, float)):
        number = float(value)
        return int(number if abs(number) > 10_000_000_000 else number * 1000.0)
    return int(_datetime(value).timestamp() * 1000)
