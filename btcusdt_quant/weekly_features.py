"""Weekly timeframe feature computation for regime detection.

Computes traditional weekly MA features from 1-minute candles:
- 20-week / 50-week moving averages (completed weekly closes only)
- MA slopes (golden/dead cross signals)
- Current close distance from weekly MAs (changes every minute)

Implementation rules:
1. Use ONLY completed weekly closes (last week's close, not current week)
2. weekly_ma20/50 are fixed for the entire week
3. close_vs_weekly_ma20/50 change every minute as current_close changes
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Sequence

from . import data


def compute_weekly_features(candles: Sequence[data.Candle]) -> dict[str, "np.ndarray | list[float]"]:
    """Compute weekly timeframe features from 1-minute candles.
    
    Returns a dict mapping feature names to lists of floats with the same
    length as candles.
    
    Key design:
    - weekly_ma20/50: fixed per week (based on completed weekly closes)
    - close_vs_weekly_ma20/50: changes every minute (current_close / fixed_ma - 1)
    """
    n = len(candles)
    if n < 5040:  # Minimum: ~3.5 days of 1m bars for weekly resampling
        return _empty_weekly_features(n)
    
    # Extract close prices and timestamps
    timestamps = pd.DatetimeIndex([c.open_time for c in candles])
    closes = np.array([c.close for c in candles], dtype=float)
    
    # Create DataFrame for resampling
    df = pd.DataFrame({"close": closes}, index=timestamps)
    
    # Resample to weekly (right-edge = completed week)
    # .resample("W") uses Sunday as the end of week by default
    weekly = df.resample("W").agg({"close": "last"})
    weekly = weekly.dropna()
    
    if len(weekly) < 50:  # Need at least 50 completed weeks for MA50
        return _empty_weekly_features(n)
    
    # Compute traditional weekly MAs: require FULL window (20 or 50 weeks)
    # Before window is full, value is NaN → forward-filled as 0.0 later
    weekly["ma20"] = weekly["close"].rolling(20, min_periods=20).mean()
    weekly["ma50"] = weekly["close"].rolling(50, min_periods=50).mean()
    
    # MA slopes: NaN before window full → fillna(0.0)
    weekly["ma20_slope"] = weekly["ma20"].pct_change(fill_method=None).fillna(0.0)
    weekly["ma50_slope"] = weekly["ma50"].pct_change(fill_method=None).fillna(0.0)
    
    # Golden/Dead cross: NaN comparison → False → 0.0
    weekly["ma20_above_ma50"] = (weekly["ma20"] > weekly["ma50"]).astype(float).fillna(0.0)
    
    # Drawdown from weekly ATH (cummax works from week 1)
    weekly["rolling_max"] = weekly["close"].cummax()
    weekly["drawdown"] = (weekly["close"] / weekly["rolling_max"] - 1.0).fillna(0.0)
    
    # Volatility contraction: require FULL window
    weekly["vol20"] = weekly["close"].rolling(20, min_periods=20).std()
    weekly["vol50"] = weekly["close"].rolling(50, min_periods=50).std()
    vol50_safe = weekly["vol50"].replace(0.0, np.nan).fillna(1e-8)
    weekly["vol_contraction"] = (weekly["vol20"] / vol50_safe).fillna(1.0).clip(0.0, 10.0)
    
    # Build result arrays (float64 ndarrays; indexed per-row by callers and
    # sliced/cast to float32 by the parallel feature builder)
    result: dict[str, np.ndarray] = {}
    
    # For each 1m candle:
    # - weekly_ma20/50/slope/above: use latest COMPLETED week (fixed for the week)
    # - close_vs_weekly_ma20/50: current_close / that_week's_ma - 1 (changes every minute)
    #
    # CAUSALITY (Sunday look-ahead fix): pandas resample("W") labels each
    # weekly bin with the Sunday DATE at midnight, but the bin's "last" close
    # is the Sunday 23:59 bar. Selecting rows with ``label <= ts`` therefore
    # exposed the week's FINAL close to every bar of that same Sunday
    # (00:00-23:58 -- up to ~24h of look-ahead, once a week), and near the
    # series end it exposed a PARTIAL current-week close for the same reason.
    # A completed week's close is only knowable from the first bar AFTER the
    # week ends, so each weekly row becomes AVAILABLE at label + 1 day
    # (Monday 00:00). Monday-Saturday values are unchanged by this shift;
    # only Sundays previously leaked.
    weekly_index = pd.DatetimeIndex(weekly.index)
    available_index = weekly_index + pd.Timedelta(days=1)

    # Vectorized minute mapping (replaces the per-minute boolean-mask loop,
    # which was O(n_minutes * n_weeks) and dominated weekly-feature cost on
    # multi-year 1m data). pos[i] = number of weekly rows available at or
    # before timestamps[i]; row pos[i]-1 is the latest available week.
    pos = np.searchsorted(available_index.asi8, timestamps.asi8, side="right")
    valid = pos > 0
    row = np.maximum(pos - 1, 0)

    def _pick(column: str, default: float) -> np.ndarray:
        col = weekly[column].to_numpy(dtype=float)
        return np.where(valid, col[row], default)

    ma20_sel = _pick("ma20", 0.0)
    ma50_sel = _pick("ma50", 0.0)
    # NaN semantics preserved from the scalar loop: before a full 20/50-week
    # window, ma20/ma50 are NaN and close_vs_* propagates NaN (these rows are
    # dropped by the 50-week warmup filter in build_dataset); before the
    # FIRST available week, everything defaults to 0.0 (vol_contraction 1.0).
    with np.errstate(divide="ignore", invalid="ignore"):
        cv20 = closes / ma20_sel - 1.0
        cv50 = closes / ma50_sel - 1.0
    cv20 = np.where(ma20_sel != 0.0, cv20, 0.0)
    cv50 = np.where(ma50_sel != 0.0, cv50, 0.0)

    result["weekly_ma20_slope_closed"] = _pick("ma20_slope", 0.0)
    result["weekly_ma50_slope_closed"] = _pick("ma50_slope", 0.0)
    result["weekly_ma20_above_ma50"] = _pick("ma20_above_ma50", 0.0)
    result["weekly_drawdown"] = _pick("drawdown", 0.0)
    result["weekly_vol_contraction"] = _pick("vol_contraction", 1.0)
    result["close_vs_weekly_ma20"] = cv20
    result["close_vs_weekly_ma50"] = cv50
    return result


def _empty_weekly_features(n: int) -> dict[str, list[float]]:
    """Return zero-filled weekly features when insufficient data."""
    return {
        "weekly_ma20_slope_closed": [0.0] * n,
        "weekly_ma50_slope_closed": [0.0] * n,
        "weekly_ma20_above_ma50": [0.0] * n,
        "weekly_drawdown": [0.0] * n,
        "weekly_vol_contraction": [0.0] * n,
        "close_vs_weekly_ma20": [0.0] * n,
        "close_vs_weekly_ma50": [0.0] * n,
    }
