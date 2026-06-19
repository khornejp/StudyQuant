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


def compute_weekly_features(candles: Sequence[data.Candle]) -> dict[str, list[float]]:
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
    
    # Build result arrays
    result: dict[str, list[float]] = {
        "weekly_ma20_slope_closed": [],
        "weekly_ma50_slope_closed": [],
        "weekly_ma20_above_ma50": [],
        "weekly_drawdown": [],
        "weekly_vol_contraction": [],
        "close_vs_weekly_ma20": [],
        "close_vs_weekly_ma50": [],
    }
    
    # For each 1m candle:
    # - weekly_ma20/50/slope/above: use latest COMPLETED week (fixed for the week)
    # - close_vs_weekly_ma20/50: current_close / that_week's_ma - 1 (changes every minute)
    weekly_index = pd.DatetimeIndex(weekly.index)
    
    for i, ts in enumerate(timestamps):
        # Find the last completed weekly close (<= current timestamp)
        mask = weekly_index <= ts
        if not mask.any():
            # Before first weekly close
            for key in result:
                result[key].append(0.0 if key != "weekly_vol_contraction" else 1.0)
            continue
        
        latest_week_idx = weekly_index[mask][-1]
        
        # Fixed per week: based on completed weekly closes only
        ma20_val = float(weekly["ma20"].get(latest_week_idx, 0.0))
        ma50_val = float(weekly["ma50"].get(latest_week_idx, 0.0))
        
        result["weekly_ma20_slope_closed"].append(float(weekly["ma20_slope"].get(latest_week_idx, 0.0)))
        result["weekly_ma50_slope_closed"].append(float(weekly["ma50_slope"].get(latest_week_idx, 0.0)))
        result["weekly_ma20_above_ma50"].append(float(weekly["ma20_above_ma50"].get(latest_week_idx, 0.0)))
        result["weekly_drawdown"].append(float(weekly["drawdown"].get(latest_week_idx, 0.0)))
        result["weekly_vol_contraction"].append(float(weekly["vol_contraction"].get(latest_week_idx, 1.0)))
        
        # Changes every minute: current close vs fixed weekly MA
        current_close = closes[i]
        result["close_vs_weekly_ma20"].append(current_close / ma20_val - 1.0 if ma20_val != 0.0 else 0.0)
        result["close_vs_weekly_ma50"].append(current_close / ma50_val - 1.0 if ma50_val != 0.0 else 0.0)
    
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
