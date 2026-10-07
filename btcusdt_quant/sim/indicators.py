from __future__ import annotations
import numpy as np, pandas as pd

def ema(x: pd.Series, span: int) -> pd.Series:
    return x.ewm(span=span, adjust=False).mean()

def _wilder(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(alpha=1 / n, adjust=False).mean()

def true_range(b: pd.DataFrame) -> pd.Series:
    prev = b.close.shift()
    return pd.concat([b.high - b.low, (b.high - prev).abs(), (b.low - prev).abs()], axis=1).max(axis=1)

def atr(b: pd.DataFrame, n: int = 14) -> pd.Series:
    return _wilder(true_range(b), n)

def adx(b: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder ADX."""
    up, down = b.high.diff(), -b.low.diff()
    plus = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=b.index)
    minus = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=b.index)
    a = atr(b, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi, mdi = 100 * _wilder(plus, n) / a, 100 * _wilder(minus, n) / a
        dx = 100 * (pdi - mdi).abs() / (pdi + mdi)
    return _wilder(dx.fillna(0.0), n)

def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up, down = _wilder(d.clip(lower=0), n), _wilder((-d).clip(lower=0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 100 - 100 / (1 + up / down)
    return out.where(down != 0, 100.0)

def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    m = close.rolling(n).mean(); s = close.rolling(n).std(ddof=0)
    return pd.DataFrame({"middle": m, "upper": m + k * s, "lower": m - k * s})

def keltner(b: pd.DataFrame, n: int = 20, k: float = 1.5) -> pd.DataFrame:
    m = ema(b.close, n); a = atr(b, n)
    return pd.DataFrame({"middle": m, "upper": m + k * a, "lower": m - k * a})

def supertrend(b: pd.DataFrame, n: int = 10, k: float = 3.0) -> pd.Series:
    a = atr(b, n).to_numpy(); mid = ((b.high + b.low) / 2).to_numpy(); close = b.close.to_numpy()
    upper, lower = mid + k * a, mid - k * a
    direction = np.ones(len(b), dtype=np.int8)
    fu, fl = upper.copy(), lower.copy()
    for i in range(1, len(b)):
        fu[i] = upper[i] if (upper[i] < fu[i - 1] or close[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = lower[i] if (lower[i] > fl[i - 1] or close[i - 1] < fl[i - 1]) else fl[i - 1]
        if direction[i - 1] == 1:
            direction[i] = -1 if close[i] < fl[i] else 1
        else:
            direction[i] = 1 if close[i] > fu[i] else -1
    return pd.Series(direction, index=b.index)

def vwap_utc(b: pd.DataFrame) -> pd.Series:
    typical = b[["high", "low", "close"]].mean(axis=1)
    day = b.bar_start.dt.floor("D")
    pv = (typical * b.volume).groupby(day).cumsum(); vol = b.volume.groupby(day).cumsum()
    return pv / vol

def zscore_past(x: pd.Series, window: int, min_periods: int) -> pd.Series:
    past = x.shift()
    m = past.rolling(window, min_periods=min_periods).mean()
    s = past.rolling(window, min_periods=min_periods).std(ddof=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (x - m) / s
