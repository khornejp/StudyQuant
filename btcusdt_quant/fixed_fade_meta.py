from __future__ import annotations

"""Causal arithmetic shared by the fixed-fade meta-policy experiment.

Direction is a deterministic label transform, never a model output. Funding is
future label information only. Dollar-bar thresholds use complete prior UTC days.
"""

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FixedFadeLabels:
    side: np.ndarray
    prior_sign: np.ndarray
    gross_bps: Mapping[int, np.ndarray]
    funding_bps: Mapping[int, np.ndarray]
    net_bps: Mapping[int, np.ndarray]
    profitable: np.ndarray
    mfe_bps: np.ndarray
    mae_bps: np.ndarray


@dataclass(frozen=True)
class DollarBarOrigins:
    marked: np.ndarray
    threshold: np.ndarray
    crossings: int
    collapsed_crossings: int


def fixed_fade_side(close: Sequence[float], lookback: int = 15) -> tuple[np.ndarray, np.ndarray]:
    """Return `-sign(log(close[t]/close[t-lookback]))` and its prior sign."""
    values = np.asarray(close, dtype=float)
    if lookback < 1 or values.ndim != 1 or len(values) <= lookback:
        raise ValueError("close must be a one-dimensional vector longer than lookback")
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("close must be finite and positive")
    prior_sign = np.zeros(len(values), dtype=np.int8)
    prior_sign[lookback:] = np.sign(np.log(values[lookback:] / values[:-lookback])).astype(np.int8)
    return (-prior_sign).astype(np.int8), prior_sign


def settlement_rate_vector(
    open_time: Sequence[object],
    settlement_time: Sequence[object],
    funding_rate: Sequence[float],
) -> np.ndarray:
    """Align realised funding rates to exact settlement minutes."""
    timeline = pd.DatetimeIndex(pd.to_datetime(open_time, utc=True))
    events = pd.DatetimeIndex(pd.to_datetime(settlement_time, utc=True)).floor("min")
    rates = np.asarray(funding_rate, dtype=float)
    if len(events) != len(rates) or not np.isfinite(rates).all():
        raise ValueError("funding times and finite rates must have equal length")
    if events.has_duplicates:
        raise ValueError("duplicate funding settlement minute")
    locations = timeline.get_indexer(events)
    in_range = (events >= timeline[0]) & (events <= timeline[-1])
    if (locations[in_range] < 0).any():
        raise ValueError("funding settlement is not aligned to an input minute")
    output = np.zeros(len(timeline), dtype=float)
    keep = locations >= 0
    output[locations[keep]] = rates[keep]
    return output


def _forward_sum(values: np.ndarray, horizon: int) -> np.ndarray:
    output = np.full(len(values), np.nan, dtype=float)
    cumulative = np.r_[0.0, np.cumsum(values, dtype=float)]
    usable = len(values) - horizon
    if usable > 0:
        starts = np.arange(usable)
        output[:usable] = cumulative[starts + horizon + 1] - cumulative[starts + 1]
    return output


def _forward_return(close: np.ndarray, horizon: int) -> np.ndarray:
    output = np.full(len(close), np.nan, dtype=float)
    if len(close) > horizon:
        output[:-horizon] = (close[horizon:] / close[:-horizon] - 1.0) * 10_000.0
    return output


def fixed_fade_labels(
    close: Sequence[float],
    high: Sequence[float],
    low: Sequence[float],
    settlement_rates: Sequence[float],
    *,
    lookback: int = 15,
    horizons: tuple[int, ...] = (15, 30, 45, 60),
    cost_bps: float = 4.0,
) -> FixedFadeLabels:
    """Build fixed-side gross, signed funding, net, and H15 path labels."""
    close_array = np.asarray(close, dtype=float)
    high_array = np.asarray(high, dtype=float)
    low_array = np.asarray(low, dtype=float)
    rates = np.asarray(settlement_rates, dtype=float)
    if not (len(close_array) == len(high_array) == len(low_array) == len(rates)):
        raise ValueError("OHLC and settlement vectors must have equal length")
    if not np.isfinite(np.c_[close_array, high_array, low_array, rates]).all():
        raise ValueError("OHLC and settlement vectors must be finite")
    if (close_array <= 0).any() or cost_bps < 0 or not np.isfinite(cost_bps):
        raise ValueError("close must be positive and cost must be finite and non-negative")
    if 15 not in horizons or any(h < 1 for h in horizons):
        raise ValueError("horizons must be positive and include 15")

    side, prior_sign = fixed_fade_side(close_array, lookback)
    gross: dict[int, np.ndarray] = {}
    funding: dict[int, np.ndarray] = {}
    net: dict[int, np.ndarray] = {}
    for horizon in horizons:
        price = side.astype(float) * _forward_return(close_array, horizon)
        paid = side.astype(float) * _forward_sum(rates, horizon) * 10_000.0
        price[side == 0] = np.nan
        paid[side == 0] = np.nan
        gross[horizon], funding[horizon] = price, paid
        net[horizon] = price - cost_bps - paid

    mfe = np.full(len(close_array), np.nan, dtype=float)
    mae = np.full(len(close_array), np.nan, dtype=float)
    usable = len(close_array) - 15
    if usable > 0:
        entry = close_array[:usable]
        own_side = side[:usable]
        best = np.zeros(usable, dtype=float)
        worst = np.zeros(usable, dtype=float)
        for step in range(1, 16):
            up = (high_array[step : step + usable] / entry - 1.0) * 10_000.0
            down = (low_array[step : step + usable] / entry - 1.0) * 10_000.0
            favourable = np.where(own_side == 1, up, -down)
            adverse = np.where(own_side == 1, -down, up)
            best = np.maximum(best, favourable)
            worst = np.maximum(worst, adverse)
        valid_side = own_side != 0
        mfe[:usable] = np.where(valid_side, best, np.nan)
        mae[:usable] = np.where(valid_side, worst, np.nan)

    profitable = np.zeros(len(close_array), dtype=np.int8)
    known = np.isfinite(net[15])
    profitable[known] = (net[15][known] > 0).astype(np.int8)
    profitable[~known] = -1
    return FixedFadeLabels(side, prior_sign, gross, funding, net, profitable, mfe, mae)


def eligibility_mask(
    feature_valid: Sequence[bool], side: Sequence[int], profitable: Sequence[int]
) -> np.ndarray:
    """Keep feature-valid, non-tie origins with a known H15 label."""
    valid = np.asarray(feature_valid, dtype=bool)
    side_array = np.asarray(side, dtype=np.int8)
    profitable_array = np.asarray(profitable, dtype=np.int8)
    if not (len(valid) == len(side_array) == len(profitable_array)):
        raise ValueError("feature validity, side, and profitable label must align")
    return valid & (side_array != 0) & (profitable_array >= 0)


def assert_fixed_side(
    side: Sequence[int], prior_sign: Sequence[int], eligible: Sequence[bool]
) -> float | None:
    """Assert fixed fade and report correlation when both signs are present."""
    side_array = np.asarray(side, dtype=np.int8)
    prior_array = np.asarray(prior_sign, dtype=np.int8)
    mask = np.asarray(eligible, dtype=bool)
    if len(side_array) != len(prior_array) or len(side_array) != len(mask) or not mask.any():
        raise ValueError("side, prior sign, and nonempty eligibility must align")
    if not np.isin(side_array[mask], (-1, 1)).all() or not np.array_equal(side_array[mask], -prior_array[mask]):
        raise AssertionError("fixed side differs from -sign(prior15)")
    if np.unique(side_array[mask]).size < 2:
        return None
    return float(np.corrcoef(side_array[mask], prior_array[mask])[0, 1])


def fit_coverage_threshold(stop_q: Sequence[float], coverage: float) -> float:
    """Fit a top-coverage threshold from STOP scores only."""
    scores = np.asarray(stop_q, dtype=float)
    if not 0 < coverage < 1 or scores.ndim != 1 or not len(scores) or not np.isfinite(scores).all():
        raise ValueError("finite nonempty STOP scores and coverage in (0,1) required")
    return float(np.quantile(scores, 1.0 - coverage, method="linear"))


def apply_coverage_threshold(q: Sequence[float], threshold: float) -> np.ndarray:
    """Accept scores strictly above the STOP cutoff; boundary ties abstain."""
    scores = np.asarray(q, dtype=float)
    if scores.ndim != 1 or not np.isfinite(scores).all() or not np.isfinite(threshold):
        raise ValueError("finite one-dimensional scores and threshold required")
    return scores > threshold


def dollar_bar_origins(
    open_time: Sequence[object],
    quote_volume: Sequence[float],
    *,
    prior_days: int = 30,
    bars_per_day: int = 96,
) -> DollarBarOrigins:
    """Emit causal dollar-bar crossings with prior-complete-day thresholds."""
    times = pd.DatetimeIndex(pd.to_datetime(open_time, utc=True))
    volume = np.asarray(quote_volume, dtype=float)
    if (
        len(times) != len(volume)
        or not len(times)
        or not times.is_monotonic_increasing
        or times.has_duplicates
        or not times.equals(times.floor("min"))
    ):
        raise ValueError("ordered timestamps and quote volume must align")
    if not np.isfinite(volume).all() or (volume < 0).any() or prior_days < 1 or bars_per_day < 1:
        raise ValueError("quote volume must be finite/non-negative and configuration positive")

    days = times.normalize()
    grouped = pd.DataFrame({"time": times, "volume": volume}, index=days).groupby(level=0, sort=True)
    daily = grouped.volume.sum()
    complete = (
        grouped.size().eq(1_440)
        & grouped.time.min().eq(daily.index)
        & grouped.time.max().eq(daily.index + pd.Timedelta(minutes=1_439))
    )
    day_threshold: dict[pd.Timestamp, float] = {}
    for day in daily.index:
        prior = pd.date_range(end=day - pd.Timedelta(days=1), periods=prior_days, freq="D")
        if not complete.reindex(prior, fill_value=False).all():
            continue
        threshold = float(np.median(daily.reindex(prior))) / bars_per_day
        if threshold > 0 and np.isfinite(threshold):
            day_threshold[day] = threshold

    thresholds = np.array([day_threshold.get(day, np.nan) for day in days], dtype=float)
    marked = np.zeros(len(volume), dtype=bool)
    accumulator = 0.0
    crossings = collapsed = 0
    for index, (amount, threshold) in enumerate(zip(volume, thresholds)):
        if not np.isfinite(threshold):
            accumulator = 0.0
            continue
        accumulator += amount
        minute_crossings = 0
        while accumulator >= threshold:
            accumulator -= threshold
            minute_crossings += 1
        if minute_crossings:
            marked[index] = True
            crossings += minute_crossings
            collapsed += minute_crossings - 1
    return DollarBarOrigins(marked, thresholds, crossings, collapsed)


__all__ = [
    "DollarBarOrigins",
    "FixedFadeLabels",
    "apply_coverage_threshold",
    "assert_fixed_side",
    "dollar_bar_origins",
    "eligibility_mask",
    "fit_coverage_threshold",
    "fixed_fade_labels",
    "fixed_fade_side",
    "settlement_rate_vector",
]
