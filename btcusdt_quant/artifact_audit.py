"""Independent, data-only reconstruction of recorded execution artifacts.

This module intentionally does not import :mod:`btcusdt_quant.backtest`.  It is
the small shadow specification used to check that a serialized trade is
actually possible under the OHLC data that accompanies it.
"""

from __future__ import annotations

from typing import Mapping, Sequence


def resolve_ohlc_exit(
    candle: Mapping[str, float], side: str, tp: float, sl: float,
    held_bars: int, min_hold_bars: int, horizon: int,
) -> tuple[str, float, str] | None:
    """Resolve one bar without using the backtest implementation."""
    high, low, opening, close = (float(candle[k]) for k in ("high", "low", "open", "close"))
    hit_tp = high >= tp if side == "BUY" else low <= tp
    hit_sl = low <= sl if side == "BUY" else high >= sl
    if not ((held_bars >= min_hold_bars and (hit_tp or hit_sl)) or held_bars >= horizon):
        return None
    if hit_sl and held_bars >= min_hold_bars and (
        (side == "BUY" and opening <= sl) or (side == "SELL" and opening >= sl)
    ):
        return "SL", opening, "gapped_stop"
    if hit_tp and held_bars >= min_hold_bars and side == "SELL" and opening <= tp:
        return "TP", opening, "gapped_tp"
    if hit_tp and hit_sl and held_bars >= min_hold_bars:
        tp_first = close > opening if side == "BUY" else close < opening
        return ("TP", tp, "same_bar_tp_sl") if tp_first else ("SL", sl, "same_bar_tp_sl")
    if hit_tp and held_bars >= min_hold_bars:
        return "TP", tp, "tp"
    if hit_sl and held_bars >= min_hold_bars:
        return "SL", sl, "sl"
    return "TIMEOUT", close, "timeout"


def reconstruct_exit(
    candles: Sequence[Mapping[str, float]], side: str, tp: float, sl: float,
    horizon: int, min_hold_bars: int, maker_entry: bool,
) -> tuple[str, float, int, str] | None:
    """Reconstruct an exit from the fill bar onward.

    ``candles[0]`` is the recorded entry/fill bar.  A resting maker fill can
    participate in it; a close/taker entry cannot.  A same-fill-bar TP is not
    credited because OHLC has no evidence that its favourable excursion was
    after the fill.  An SL remains decisive when it is observable.
    """
    start = 0 if maker_entry else 1
    for offset, candle in enumerate(candles[start:horizon + start], start=1):
        decision = resolve_ohlc_exit(candle, side, tp, sl, offset, min_hold_bars, horizon)
        if decision is None:
            continue
        outcome, price, rule = decision
        if maker_entry and offset == 1 and outcome == "TP":
            high, low = float(candle["high"]), float(candle["low"])
            hit_sl = low <= sl if side == "BUY" else high >= sl
            if hit_sl:
                return "SL", sl, 0, "same_bar_entry_tp_sl"
            continue
        return outcome, price, offset - 1 + start, rule
    return None
