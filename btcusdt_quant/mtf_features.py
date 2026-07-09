"""Multi-timeframe (15m/1h/4h/1d-rolling) features, computed causally from the
existing 1m candle series -- no external data source needed.

Motivation (from review): the auto-regime detector currently looks only at
trend_slope_30 (a 30-bar / 30-minute slope on 1m closes), but hand-labeled
regimes span days to months. A 30-minute window can't see that. This module
builds real higher-timeframe (15m/1h/4h) OHLC bars plus a set of rolling-24h
features, and exposes them on the 1m clock without look-ahead.

CAUSALITY (the one thing that must never be wrong here): a higher-timeframe
bar's information becomes visible only once that bar is FULLY CLOSED. E.g. an
1h bar covering 13:00-14:00 is not "in progress" data usable at 13:30 -- it
only becomes available at 14:00 (its close_time), and every 1m bar from 14:00
onward sees it as the most recent CLOSED 1h bar until the 15:00 bar closes.
This mirrors the causal as-of join already used for the 5m metrics features
(metrics_source.py) and is verified the same way: a bar strictly before the
first closed higher-TF bar must see NO value from that timeframe.

No network, no external files: this is purely a resample + indicator + as-of
join over data.Candle objects already in hand.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Mapping, Sequence

from . import data as data_module

# All indicators below look back at most this many closed bars (24 for the
# 24h-rolling group, <=20 for everything else). Keeping only this many closed
# bars per timeframe (a bounded deque) instead of the full history keeps each
# update O(window) instead of O(elapsed_bars) -- without this, re-slicing an
# ever-growing "closed_prefix" list on every new closed bar makes the whole
# run effectively quadratic in the number of bars (verified: throughput fell
# from ~65k candles/s at 30 days to ~24k candles/s at 120 days before this
# fix; a 6-year run would have taken hours instead of seconds).
_MAX_LOOKBACK_BARS = 24

# Timeframes in minutes. "1d" is intentionally a rolling 24h window built from
# 1h bars (not calendar-day bars), since BTC trades continuously and a
# calendar-day boundary is an arbitrary UTC cut with no market meaning.
TIMEFRAME_MINUTES: dict[str, int] = {"15m": 15, "1h": 60, "4h": 240}

# Feature names this module emits, per timeframe (except the 24h-rolling
# group, which is clock-independent and uses 1h bars internally).
_PER_TF_FEATURE_TEMPLATE: tuple[str, ...] = (
    "trend_slope_{tf}",
    "return_{tf}",
    "ema_gap_{tf}",
    "ma_slope_{tf}",
    "rsi_{tf}",
    "atr_pct_{tf}",
    "bb_width_{tf}",
    "adx_{tf}",
    "volume_z_{tf}",
)

MTF_FEATURE_NAMES: tuple[str, ...] = tuple(
    template.format(tf=tf) for tf in ("15m", "1h", "4h") for template in _PER_TF_FEATURE_TEMPLATE
) + (
    "trend_slope_24h",
    "return_24h",
    "drawdown_from_24h_high",
    "distance_from_24h_high",
    "distance_from_24h_low",
    "rolling_high_breakout_24h",
    "rolling_low_breakdown_24h",
)


@dataclass(frozen=True)
class ResampledBar:
    """One fully-closed higher-timeframe OHLCV bar."""

    open_time: datetime
    close_time: datetime  # exclusive: this bar's data is visible starting here
    open: float
    high: float
    low: float
    close: float
    volume: float


def resample_causal(candles: Sequence[data_module.Candle], minutes: int) -> list[ResampledBar]:
    """Aggregate 1m candles into `minutes`-long OHLCV bars.

    Only emits a bar once ALL of its constituent 1m candles are present in
    `candles` (i.e. the bar is fully closed) -- a partial trailing group
    smaller than `minutes` candles is dropped, not emitted with incomplete
    data. Bars are aligned to minutes-since-epoch boundaries so resampling is
    deterministic regardless of where `candles` starts.
    """
    if minutes <= 0:
        raise ValueError("minutes must be positive")
    if not candles:
        return []
    epoch = datetime(1970, 1, 1, tzinfo=candles[0].open_time.tzinfo)
    bars: list[ResampledBar] = []
    group_start_bucket: int | None = None
    group: list[data_module.Candle] = []

    def _flush(complete: bool) -> None:
        if not group or not complete:
            return
        bars.append(
            ResampledBar(
                open_time=group[0].open_time,
                close_time=group[-1].open_time + timedelta(minutes=1),
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(c.volume for c in group),
            )
        )

    for candle in candles:
        minute_index = int((candle.open_time - epoch).total_seconds() // 60)
        bucket = minute_index // minutes
        if group_start_bucket is None:
            group_start_bucket = bucket
        if bucket != group_start_bucket:
            # A new bucket started. The previous group is complete only if it
            # has exactly `minutes` candles (no gaps assumed -- canonical
            # candle series is contiguous per the pipeline's gap-filling).
            _flush(complete=len(group) == minutes)
            group = []
            group_start_bucket = bucket
        group.append(candle)
    # Trailing group: only emit if it happens to be exactly complete (the
    # series ended precisely on a boundary); otherwise it's an in-progress
    # bar and must NOT be emitted (that would be look-ahead once forward-
    # filled, since its close lies beyond the data we have).
    _flush(complete=len(group) == minutes)
    return bars


def _linreg_slope(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0.0:
        return 0.0
    slope = num / den
    last = values[-1]
    return slope / last if last != 0.0 else 0.0


def _ema(values: Sequence[float], span: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (span + 1.0)
    out = [values[0]]
    for v in values[1:]:
        out.append(alpha * v + (1 - alpha) * out[-1])
    return out


def _rsi(closes: Sequence[float], period: int) -> float:
    if len(closes) < period + 1:
        return 50.0
    window = closes[-(period + 1):]
    gains = [max(0.0, window[i] - window[i - 1]) for i in range(1, len(window))]
    losses = [max(0.0, window[i - 1] - window[i]) for i in range(1, len(window))]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _atr_pct(bars: Sequence[ResampledBar], period: int) -> float:
    if len(bars) < period + 1:
        return 0.0
    window = bars[-(period + 1):]
    trs = []
    for i in range(1, len(window)):
        prev_close = window[i - 1].close
        tr = max(
            window[i].high - window[i].low,
            abs(window[i].high - prev_close),
            abs(window[i].low - prev_close),
        )
        trs.append(tr)
    atr = sum(trs) / period
    last_close = window[-1].close
    return atr / last_close if last_close != 0.0 else 0.0


def _bb_width(closes: Sequence[float], period: int) -> float:
    if len(closes) < period:
        return 0.0
    window = closes[-period:]
    mean = sum(window) / period
    var = sum((c - mean) ** 2 for c in window) / period
    std = math.sqrt(var)
    return (4.0 * std) / mean if mean != 0.0 else 0.0


def _adx(bars: Sequence[ResampledBar], period: int) -> float:
    """Simplified Wilder ADX over the trailing `period` closed bars."""
    if len(bars) < period + 1:
        return 0.0
    window = bars[-(period + 1):]
    plus_dm = []
    minus_dm = []
    trs = []
    for i in range(1, len(window)):
        up_move = window[i].high - window[i - 1].high
        down_move = window[i - 1].low - window[i].low
        plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
        minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0.0)
        prev_close = window[i - 1].close
        trs.append(max(
            window[i].high - window[i].low,
            abs(window[i].high - prev_close),
            abs(window[i].low - prev_close),
        ))
    atr = sum(trs) / period
    if atr == 0.0:
        return 0.0
    plus_di = 100.0 * (sum(plus_dm) / period) / atr
    minus_di = 100.0 * (sum(minus_dm) / period) / atr
    denom = plus_di + minus_di
    if denom == 0.0:
        return 0.0
    return 100.0 * abs(plus_di - minus_di) / denom


def _volume_zscore(volumes: Sequence[float], period: int) -> float:
    if len(volumes) < period:
        return 0.0
    window = volumes[-period:]
    mean = sum(window) / period
    var = sum((v - mean) ** 2 for v in window) / period
    std = math.sqrt(var)
    if std == 0.0:
        return 0.0
    return (window[-1] - mean) / std


def _features_from_closed_bars(bars: Sequence[ResampledBar], tf: str) -> dict[str, float]:
    """Compute one timeframe's indicator set from its trailing closed bars.

    All lookbacks are small (<=20 bars) relative to the resample size, so
    "24h" of 15m bars (96 bars) comfortably covers every period used here.
    Returns 0.0 / neutral defaults when history is too short -- this matches
    the rest of the codebase's warmup convention (zero, not NaN) so the
    feature clips cleanly.
    """
    if not bars:
        return {t.format(tf=tf): (50.0 if "rsi" in t else 0.0) for t in _PER_TF_FEATURE_TEMPLATE}
    closes = [b.close for b in bars]
    volumes = [b.volume for b in bars]
    period = min(14, len(bars))
    ema_period = min(20, len(bars))
    ema_series = _ema(closes[-max(ema_period, 1):], ema_period) if ema_period > 0 else []
    ema_now = ema_series[-1] if ema_series else closes[-1]
    ma_window = closes[-min(10, len(closes)):]
    ma_now = sum(ma_window) / len(ma_window)
    ma_prev_window = closes[-min(10, len(closes)) - 1:-1] if len(closes) > min(10, len(closes)) else ma_window
    ma_prev = sum(ma_prev_window) / len(ma_prev_window) if ma_prev_window else ma_now
    slope_window = closes[-min(10, len(closes)):]
    ret_window = min(10, len(closes) - 1)
    values = {
        "trend_slope_{tf}": _linreg_slope(slope_window),
        "return_{tf}": ((closes[-1] - closes[-1 - ret_window]) / closes[-1 - ret_window]) if ret_window > 0 and closes[-1 - ret_window] != 0.0 else 0.0,
        "ema_gap_{tf}": ((closes[-1] - ema_now) / closes[-1]) if closes[-1] != 0.0 else 0.0,
        "ma_slope_{tf}": ((ma_now - ma_prev) / ma_prev) if ma_prev != 0.0 else 0.0,
        "rsi_{tf}": _rsi(closes, period),
        "atr_pct_{tf}": _atr_pct(bars, period),
        "bb_width_{tf}": _bb_width(closes, min(20, len(closes))),
        "adx_{tf}": _adx(bars, period),
        "volume_z_{tf}": _volume_zscore(volumes, min(20, len(volumes))),
    }
    return {k.format(tf=tf): v for k, v in values.items()}


def _rolling_24h_features(bars_1h: Sequence[ResampledBar]) -> dict[str, float]:
    """Distance/drawdown from the trailing 24h (last 24 closed 1h bars) high/low."""
    if not bars_1h:
        return {
            "trend_slope_24h": 0.0,
            "return_24h": 0.0,
            "drawdown_from_24h_high": 0.0,
            "distance_from_24h_high": 0.0,
            "distance_from_24h_low": 0.0,
            "rolling_high_breakout_24h": 0.0,
            "rolling_low_breakdown_24h": 0.0,
        }
    window = bars_1h[-24:]
    high_24h = max(b.high for b in window)
    low_24h = min(b.low for b in window)
    last_close = window[-1].close
    closes_24h = [b.close for b in window]
    first_close = closes_24h[0]
    return {
        # Directional 24h context: price-normalized linreg slope over the last
        # <=24 closed 1h bars, and the full 24h window return. Same conventions
        # as trend_slope_{tf}/return_{tf} so weights are comparable.
        "trend_slope_24h": _linreg_slope(closes_24h),
        "return_24h": ((last_close - first_close) / first_close) if first_close != 0.0 else 0.0,
        "drawdown_from_24h_high": ((high_24h - last_close) / high_24h) if high_24h != 0.0 else 0.0,
        "distance_from_24h_high": ((last_close - high_24h) / high_24h) if high_24h != 0.0 else 0.0,
        "distance_from_24h_low": ((last_close - low_24h) / low_24h) if low_24h != 0.0 else 0.0,
        "rolling_high_breakout_24h": 1.0 if last_close >= high_24h else 0.0,
        "rolling_low_breakdown_24h": 1.0 if last_close <= low_24h else 0.0,
    }


def extract_feature_vector(features: Mapping[str, float]) -> list[float]:
    """Pull the F17 multi-timeframe feature vector, in MTF_FEATURE_NAMES
    order, out of a row's full feature dict. Used to feed the regime
    classifier consistently wherever it's called (training bucket
    assignment, backtest routing, live routing) from the SAME underlying
    per-row feature dict every other feature comes from -- no separate
    recomputation path that could drift out of sync.
    """
    return [float(features.get(name, 0.0)) for name in MTF_FEATURE_NAMES]


def compute_mtf_features_to_minutes(
    candles: Sequence[data_module.Candle],
) -> dict[datetime, dict[str, float]]:
    """Compute all multi-timeframe features and forward-fill onto the 1m clock.

    Causal by construction: for each timeframe, closed bars are built with
    resample_causal (never a partial trailing bar), then features are computed
    incrementally over the closed-bar prefix and assigned to the FIRST 1m
    candle at/after that bar's close_time; every 1m candle strictly before the
    first closed bar of a timeframe gets that timeframe's neutral defaults
    (not an error, not a future value).
    """
    if not candles:
        return {}
    minute_times = [c.open_time for c in candles]
    aligned: dict[datetime, dict[str, float]] = {t: {} for t in minute_times}

    bars_by_tf: dict[str, list[ResampledBar]] = {
        tf: resample_causal(candles, minutes) for tf, minutes in TIMEFRAME_MINUTES.items()
    }

    for tf, bars in bars_by_tf.items():
        idx = 0
        n_bars = len(bars)
        current: dict[str, float] | None = None
        closed_prefix: deque[ResampledBar] = deque(maxlen=_MAX_LOOKBACK_BARS)
        for minute in minute_times:
            while idx < n_bars and bars[idx].close_time <= minute:
                closed_prefix.append(bars[idx])
                current = _features_from_closed_bars(list(closed_prefix), tf)
                idx += 1
            if current is not None:
                aligned[minute].update(current)
            else:
                aligned[minute].update(_features_from_closed_bars([], tf))

    # 24h-rolling group, built from 1h closed bars.
    bars_1h = bars_by_tf.get("1h", [])
    idx = 0
    n_bars = len(bars_1h)
    current_24h: dict[str, float] | None = None
    closed_prefix_1h: deque[ResampledBar] = deque(maxlen=24)
    for minute in minute_times:
        while idx < n_bars and bars_1h[idx].close_time <= minute:
            closed_prefix_1h.append(bars_1h[idx])
            current_24h = _rolling_24h_features(list(closed_prefix_1h))
            idx += 1
        aligned[minute].update(current_24h if current_24h is not None else _rolling_24h_features([]))

    return aligned
