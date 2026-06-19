"""Weekly timeframe feature computation for regime detection.

Computes higher timeframe features from 1-minute candles:
- 20-week / 50-week moving average slopes
- Drawdown from all-time high
- Volatility contraction ratio

These features are pre-computed once per candle sequence and forward-filled
to every 1-minute row to avoid repeated resampling.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Sequence

from . import data


def compute_weekly_features(candles: Sequence[data.Candle]) -> dict[str, list[float]]:
    """Compute weekly timeframe features from 1-minute candles.
    
    Returns a dict mapping feature names to lists of floats with the same
    length as candles (forward-filled from weekly values).
    """
    if len(candles) < 10080:  # Minimum: 1 week of 1m bars
        return {
            "weekly_ma20_slope": [0.0] * len(candles),
            "weekly_ma50_slope": [0.0] * len(candles),
            "weekly_drawdown": [0.0] * len(candles),
            "weekly_vol_contraction": [1.0] * len(candles),
        }
    
    # Extract close prices and timestamps
    timestamps = pd.DatetimeIndex([c.open_time for c in candles])
    closes = np.array([c.close for c in candles], dtype=float)
    
    # Create DataFrame for resampling
    df = pd.DataFrame({"close": closes}, index=timestamps)
    
    # Resample to weekly (right-edge = completed week, Sunday end)
    weekly = df.resample("W").agg({"close": "last"})
    weekly = weekly.dropna()
    
    if len(weekly) < 50:  # Need at least 50 weeks for MA50
        return {
            "weekly_ma20_slope": [0.0] * len(candles),
            "weekly_ma50_slope": [0.0] * len(candles),
            "weekly_drawdown": [0.0] * len(candles),
            "weekly_vol_contraction": [1.0] * len(candles),
        }
    
    # Compute weekly features
    weekly["ma20"] = weekly["close"].rolling(20, min_periods=1).mean()
    weekly["ma50"] = weekly["close"].rolling(50, min_periods=1).mean()
    weekly["ma20_slope"] = weekly["ma20"].pct_change(fill_method=None).fillna(0.0)
    weekly["ma50_slope"] = weekly["ma50"].pct_change(fill_method=None).fillna(0.0)
    weekly["rolling_max"] = weekly["close"].cummax()
    weekly["drawdown"] = (weekly["close"] / weekly["rolling_max"] - 1.0).fillna(0.0)
    weekly["vol20"] = weekly["close"].rolling(20, min_periods=1).std().fillna(0.0)
    weekly["vol50"] = weekly["close"].rolling(50, min_periods=1).std().fillna(0.0)
    
    # Volatility contraction: vol20 / vol50 (clipped to avoid division by zero)
    vol50_safe = weekly["vol50"].replace(0.0, np.nan).fillna(1e-8)
    weekly["vol_contraction"] = (weekly["vol20"] / vol50_safe).fillna(1.0)
    weekly["vol_contraction"] = weekly["vol_contraction"].clip(0.0, 10.0)
    
    # Forward-fill weekly values to 1m rows
    # Create a mapping from each 1m timestamp to the latest completed weekly value
    weekly_values = {
        "weekly_ma20_slope": weekly["ma20_slope"].to_dict(),
        "weekly_ma50_slope": weekly["ma50_slope"].to_dict(),
        "weekly_drawdown": weekly["drawdown"].to_dict(),
        "weekly_vol_contraction": weekly["vol_contraction"].to_dict(),
    }
    
    result: dict[str, list[float]] = {
        "weekly_ma20_slope": [],
        "weekly_ma50_slope": [],
        "weekly_drawdown": [],
        "weekly_vol_contraction": [],
    }
    
    # For each 1m candle, find the latest completed week
    weekly_index = pd.DatetimeIndex(weekly.index)
    for i, ts in enumerate(timestamps):
        # Find the last weekly close that is <= current timestamp
        mask = weekly_index <= ts
        if not mask.any():
            # Before first weekly close
            for key in result:
                result[key].append(0.0)
            continue
        
        latest_week_idx = weekly_index[mask][-1]
        
        result["weekly_ma20_slope"].append(float(weekly_values["weekly_ma20_slope"].get(latest_week_idx, 0.0)))
        result["weekly_ma50_slope"].append(float(weekly_values["weekly_ma50_slope"].get(latest_week_idx, 0.0)))
        result["weekly_drawdown"].append(float(weekly_values["weekly_drawdown"].get(latest_week_idx, 0.0)))
        result["weekly_vol_contraction"].append(float(weekly_values["weekly_vol_contraction"].get(latest_week_idx, 1.0)))
    
    return result
