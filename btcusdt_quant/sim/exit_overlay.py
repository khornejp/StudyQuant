"""Minute-path exit overlays shared by research and paper books."""
from __future__ import annotations

import numpy as np

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


__all__ = ["overlay"]
