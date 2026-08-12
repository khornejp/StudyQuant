from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Mapping, Sequence


@dataclass(frozen=True)
class SampleInterval:
    sample_index: int
    start_index: int
    end_index: int

    def __post_init__(self) -> None:
        if self.sample_index < 0:
            raise ValueError("sample_index must be non-negative")
        if self.start_index < 0:
            raise ValueError("start_index must be non-negative")
        if self.end_index < self.start_index:
            raise ValueError("end_index must be greater than or equal to start_index")


@dataclass(frozen=True)
class UniquenessWeightResult:
    weights: dict[int, float]
    concurrency: list[int]
    effective_sample_size: float


@dataclass(frozen=True)
class CombinatorialPurgedSplit:
    split_index: int
    train: tuple[int, ...]
    validation: tuple[int, ...]
    test: tuple[int, ...]
    test_groups: tuple[int, ...]
    purged: tuple[int, ...]
    embargoed: tuple[int, ...]


def sample_intervals_from_labeled_rows(
    labeled_rows: Sequence[object],
    label_horizon: int | None = None,
    horizon: int | None = None,
) -> list[SampleInterval]:
    if label_horizon is not None and horizon is not None and label_horizon != horizon:
        raise ValueError("label_horizon and horizon must match when both are supplied")
    effective_horizon = label_horizon if label_horizon is not None else horizon
    if effective_horizon is not None and effective_horizon < 0:
        raise ValueError("label horizon must be non-negative")

    intervals: list[SampleInterval] = []
    for sample_index, row in enumerate(labeled_rows):
        start_index = int(_row_value(row, "index", sample_index))
        if effective_horizon is None:
            end_index = _row_end_index(row, start_index)
        else:
            end_index = start_index + effective_horizon
        intervals.append(SampleInterval(sample_index, start_index, end_index))
    return intervals


def uniqueness_weights(sample_intervals: Sequence[SampleInterval]) -> UniquenessWeightResult:
    intervals = list(sample_intervals)
    if not intervals:
        return UniquenessWeightResult({}, [], 0.0)

    seen: set[int] = set()
    for interval in intervals:
        if interval.sample_index in seen:
            raise ValueError(f"duplicate sample_index: {interval.sample_index}")
        seen.add(interval.sample_index)

    max_end = max(interval.end_index for interval in intervals)
    difference = [0 for _ in range(max_end + 2)]
    for interval in intervals:
        difference[interval.start_index] += 1
        difference[interval.end_index + 1] -= 1

    concurrency: list[int] = []
    inverse_prefix = [0.0]
    running = 0
    for index in range(max_end + 1):
        running += difference[index]
        concurrency.append(running)
        inverse_prefix.append(inverse_prefix[-1] + (1.0 / running if running > 0 else 0.0))

    weights: dict[int, float] = {}
    for interval in intervals:
        length = interval.end_index - interval.start_index + 1
        uniqueness_sum = inverse_prefix[interval.end_index + 1] - inverse_prefix[interval.start_index]
        weights[interval.sample_index] = uniqueness_sum / length

    return UniquenessWeightResult(weights, concurrency, sum(weights.values()))


class CombinatorialPurgedCV:
    def __init__(self, n_groups: int = 5, test_group_count: int = 1, embargo_size: int = 0) -> None:
        if n_groups <= 0:
            raise ValueError("n_groups must be positive")
        if test_group_count <= 0:
            raise ValueError("test_group_count must be positive")
        if test_group_count > n_groups:
            raise ValueError("test_group_count cannot exceed n_groups")
        if embargo_size < 0:
            raise ValueError("embargo_size must be non-negative")
        self.n_groups = n_groups
        self.test_group_count = test_group_count
        self.embargo_size = embargo_size

    def split(self, sample_intervals: Sequence[SampleInterval] | int) -> list[CombinatorialPurgedSplit]:
        intervals = self._coerce_intervals(sample_intervals)
        if self.n_groups > len(intervals):
            raise ValueError("n_groups cannot exceed sample count")
        groups = self._sequential_groups(intervals)
        interval_by_sample = {interval.sample_index: interval for interval in intervals}
        splits: list[CombinatorialPurgedSplit] = []
        for split_index, test_groups in enumerate(combinations(range(self.n_groups), self.test_group_count)):
            splits.append(self._build_split(split_index, test_groups, groups, interval_by_sample))
        return splits

    def get_n_splits(self) -> int:
        total = 1
        selected = 1
        for offset in range(1, self.test_group_count + 1):
            total *= self.n_groups - offset + 1
            selected *= offset
        return total // selected

    def _build_split(
        self,
        split_index: int,
        test_groups: tuple[int, ...],
        groups: Sequence[tuple[int, ...]],
        interval_by_sample: Mapping[int, SampleInterval],
    ) -> CombinatorialPurgedSplit:
        test = tuple(sorted(sample_index for group_index in test_groups for sample_index in groups[group_index]))
        test_set = set(test)
        test_intervals = [interval_by_sample[sample_index] for sample_index in test]
        purged: set[int] = set()
        embargoed: set[int] = set()

        for sample_index, interval in interval_by_sample.items():
            if sample_index in test_set:
                continue
            if any(_intervals_overlap(interval, test_interval) for test_interval in test_intervals):
                purged.add(sample_index)

        windows = self._test_windows(test_groups, groups, interval_by_sample)
        if self.embargo_size > 0:
            for sample_index, interval in interval_by_sample.items():
                if sample_index in test_set or sample_index in purged:
                    continue
                if any(window_end < interval.start_index <= window_end + self.embargo_size for _, window_end in windows):
                    embargoed.add(sample_index)

        excluded = test_set | purged | embargoed
        train = tuple(sorted(sample_index for sample_index in interval_by_sample if sample_index not in excluded))
        return CombinatorialPurgedSplit(
            split_index=split_index,
            train=train,
            validation=test,
            test=test,
            test_groups=tuple(test_groups),
            purged=tuple(sorted(purged)),
            embargoed=tuple(sorted(embargoed)),
        )

    def _sequential_groups(self, intervals: Sequence[SampleInterval]) -> list[tuple[int, ...]]:
        ordered = sorted(intervals, key=lambda interval: interval.sample_index)
        base_size = len(ordered) // self.n_groups
        remainder = len(ordered) % self.n_groups
        groups: list[tuple[int, ...]] = []
        start = 0
        for group_index in range(self.n_groups):
            size = base_size + (1 if group_index < remainder else 0)
            group = ordered[start:start + size]
            groups.append(tuple(interval.sample_index for interval in group))
            start += size
        return groups

    def _test_windows(
        self,
        test_groups: tuple[int, ...],
        groups: Sequence[tuple[int, ...]],
        interval_by_sample: Mapping[int, SampleInterval],
    ) -> list[tuple[int, int]]:
        windows: list[tuple[int, int]] = []
        for group_index in test_groups:
            group_intervals = [interval_by_sample[sample_index] for sample_index in groups[group_index]]
            windows.append((min(interval.start_index for interval in group_intervals), max(interval.end_index for interval in group_intervals)))
        return windows

    def _coerce_intervals(self, sample_intervals: Sequence[SampleInterval] | int) -> list[SampleInterval]:
        if isinstance(sample_intervals, int):
            if sample_intervals <= 0:
                raise ValueError("sample count must be positive")
            return [SampleInterval(index, index, index) for index in range(sample_intervals)]
        intervals = list(sample_intervals)
        if not intervals:
            raise ValueError("sample_intervals must not be empty")
        return intervals


class SplitManager:
    def __init__(self) -> None:
        self._cache: dict[tuple[object, ...], list[object]] = {}

    def get_splits(
        self,
        n_samples: int,
        label_horizon: int = 0,
        cv_mode: str = "walk_forward",
        embargo_size: int = 0,
        walk_forward_test_gap: int = 0,
        n_groups: int = 5,
        test_group_count: int = 1,
        train_size: int | None = None,
        validation_size: int | None = None,
        test_size: int | None = None,
        purge_gap: int | None = None,
        sample_intervals: Sequence[SampleInterval] | None = None,
    ) -> list[object]:
        if n_samples <= 0:
            raise ValueError("n_samples must be positive")
        interval_key = tuple((interval.sample_index, interval.start_index, interval.end_index) for interval in sample_intervals or [])
        key = (
            cv_mode,
            n_samples,
            label_horizon,
            embargo_size,
            walk_forward_test_gap,
            n_groups,
            test_group_count,
            train_size,
            validation_size,
            test_size,
            purge_gap,
            interval_key,
        )
        if key not in self._cache:
            self._cache[key] = self._create_splits(
                n_samples,
                label_horizon,
                cv_mode,
                embargo_size,
                walk_forward_test_gap,
                n_groups,
                test_group_count,
                train_size,
                validation_size,
                test_size,
                purge_gap,
                sample_intervals,
            )
        return self._cache[key]

    def get_stage_splits(self, stage: str, *args: object, **kwargs: object) -> list[object]:
        return self.get_splits(*args, **kwargs)  # type: ignore[arg-type]

    def get_feature_selection_splits(self, *args: object, **kwargs: object) -> list[object]:
        return self.get_splits(*args, **kwargs)  # type: ignore[arg-type]

    def get_hpo_splits(self, *args: object, **kwargs: object) -> list[object]:
        return self.get_splits(*args, **kwargs)  # type: ignore[arg-type]

    def get_calibration_splits(self, *args: object, **kwargs: object) -> list[object]:
        return self.get_splits(*args, **kwargs)  # type: ignore[arg-type]

    def get_threshold_splits(self, *args: object, **kwargs: object) -> list[object]:
        return self.get_splits(*args, **kwargs)  # type: ignore[arg-type]

    def get_test_splits(self, *args: object, **kwargs: object) -> list[object]:
        return self.get_splits(*args, **kwargs)  # type: ignore[arg-type]

    def _create_splits(
        self,
        n_samples: int,
        label_horizon: int,
        cv_mode: str,
        embargo_size: int,
        walk_forward_test_gap: int,
        n_groups: int,
        test_group_count: int,
        train_size: int | None,
        validation_size: int | None,
        test_size: int | None,
        purge_gap: int | None,
        sample_intervals: Sequence[SampleInterval] | None,
    ) -> list[object]:
        if cv_mode == "walk_forward":
            from . import features

            effective_train_size = train_size if train_size is not None else max(60, n_samples // 3)
            effective_validation_size = validation_size if validation_size is not None else max(20, n_samples // 8)
            effective_test_size = test_size if test_size is not None else max(20, n_samples // 8)
            effective_purge_gap = purge_gap if purge_gap is not None else label_horizon
            return list(features.PurgedWalkForwardSplit().split(
                n_samples, effective_train_size, effective_validation_size,
                effective_test_size, effective_purge_gap, walk_forward_test_gap,
            ))
        if cv_mode == "combinatorial_purged":
            intervals = list(sample_intervals) if sample_intervals is not None else [SampleInterval(index, index, index + label_horizon) for index in range(n_samples)]
            return list(CombinatorialPurgedCV(n_groups, test_group_count, embargo_size).split(intervals))
        raise ValueError(f"unknown cv_mode: {cv_mode}")


def _row_end_index(row: object, start_index: int) -> int:
    for name in ("end_index", "label_end_index", "event_end_index", "t1"):
        value = _row_value(row, name, None)
        if value is not None:
            return int(value)
    return start_index


def _row_value(row: object, key: str, default: object) -> object:
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def _intervals_overlap(left: SampleInterval, right: SampleInterval) -> bool:
    return max(left.start_index, right.start_index) <= min(left.end_index, right.end_index)


__all__ = [
    "CombinatorialPurgedCV",
    "CombinatorialPurgedSplit",
    "SampleInterval",
    "SplitManager",
    "UniquenessWeightResult",
    "sample_intervals_from_labeled_rows",
    "uniqueness_weights",
]
