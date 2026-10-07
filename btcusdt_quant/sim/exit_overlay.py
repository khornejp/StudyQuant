"""Minute-path exit overlays shared by research and paper books."""
from __future__ import annotations

import numpy as np
import pandas as pd

FEE = 4.0


def _first(mask: np.ndarray) -> int:
    hits = np.flatnonzero(mask)
    return int(hits[0]) if len(hits) else -1


def overlay(side, entry, i0, i_exit, o, h, l, rule, atr_bps):
    """Exit (minute index, price) or None; native exit fills at ``i_exit`` open."""
    a, b = i0 + 1, i_exit
    if b <= a:
        return None
    fav = side * np.log((h if side == 1 else l)[a:b] / entry) * 1e4
    adv = side * np.log((l if side == 1 else h)[a:b] / entry) * 1e4
    opn = side * np.log(o[a:b] / entry) * 1e4
    if rule.startswith("S"):
        stop = -float(rule[1:])
        k = _first(adv <= stop)
        return None if k < 0 else (a + k, entry * np.exp(side * min(stop, opn[k]) / 1e4))
    if rule == "R3_ATR":
        if not np.isfinite(atr_bps) or atr_bps <= 0:
            return None
        stop, take = -1.0 * atr_bps, 1.5 * atr_bps
        hit_stop, hit_take = adv <= stop, fav >= take
        k = _first(hit_stop | hit_take)
        if k < 0:
            return None
        level = stop if hit_stop[k] else take
        level = min(level, opn[k]) if hit_stop[k] else max(level, opn[k])
        return a + k, entry * np.exp(side * level / 1e4)
    best_before = np.maximum.accumulate(np.r_[fav[:1] * 0 - np.inf, fav[:-1]])
    best_before = np.maximum(best_before, side * np.log((h if side == 1 else l)[i0] / entry) * 1e4)
    if rule == "R1_BREAKEVEN":
        active, stop = best_before >= 30, np.full(len(fav), FEE)
    else:
        active, stop = best_before >= 50, 0.5 * best_before
    k = _first(active & (adv <= stop))
    if k < 0:
        return None
    level = min(stop[k], opn[k])
    return a + k, entry * np.exp(side * level / 1e4)


def m_series(minutes: pd.DataFrame, frame: pd.DataFrame | None) -> np.ndarray:
    """15-minute-grid M known at each minute open, with the frozen 14-minute age limit."""
    from btcusdt_quant.sim import regime
    if frame is None:
        return np.full(len(minutes), np.nan)
    if len(frame):
        timestamps = pd.DatetimeIndex(frame.timestamp)
        frame = frame.loc[timestamps.floor("15min") == timestamps]
    return regime._asof(frame, pd.DatetimeIndex(minutes.open_time), "M", pd.Timedelta(minutes=14))


def dynamic_series(minutes: pd.DataFrame, frame: pd.DataFrame | None = None) -> dict[str, np.ndarray]:
    """Frozen R2-49 minute series shared by research and paper."""
    if frame is None:
        from btcusdt_quant.sim import data, regime, rolling
        frame = regime.load_regime(data.load_predictions(end=rolling.END))
    h, l, c = (minutes[k] for k in ("high", "low", "close"))
    prev = c.shift()
    tr = pd.concat([h, prev], axis=1).max(axis=1) - pd.concat([l, prev], axis=1).min(axis=1)
    returns = np.log(c).diff()
    return {"atr60": tr.rolling(60).mean().to_numpy(), "rv60": returns.rolling(60).std().to_numpy(),
            "rv1440": returns.rolling(1440).std().to_numpy(), "m": m_series(minutes, frame)}


def dynamic(side, entry, i0, i_exit, o, h, l, c, rule, series):
    """Exit (minute index, price) or None for the frozen V1/V2/V3 rules."""
    a, b = i0 + 1, i_exit
    if b <= a:
        return None
    if rule == "V1_CHANDELIER":
        extreme = np.maximum.accumulate(h[i0:b - 1]) if side == 1 else np.minimum.accumulate(l[i0:b - 1])
        stop = extreme - side * 3 * series["atr60"][i0:b - 1]
        stop = np.fmax.accumulate(stop) if side == 1 else -np.fmax.accumulate(-stop)
        hit = l[a:b] <= stop if side == 1 else h[a:b] >= stop
        k = np.flatnonzero(hit)
        if not len(k):
            return None
        k = int(k[0])
        return a + k, min(stop[k], o[a + k]) if side == 1 else max(stop[k], o[a + k])
    loss = side * (c[i0:b - 1] - entry) < 0
    trigger = (series["rv60"][i0:b - 1] >= 2 * series["rv1440"][i0] if rule == "V2_RV_SPIKE_LOSS"
               else series["m"][a:b] >= 0.9)
    with np.errstate(invalid="ignore"):
        k = np.flatnonzero(loss & trigger)
    return None if not len(k) else (a + int(k[0]), o[a + int(k[0])])


__all__ = ["dynamic", "dynamic_series", "m_series", "overlay"]
