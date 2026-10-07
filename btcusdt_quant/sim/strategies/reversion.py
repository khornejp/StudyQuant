"""Mean-reversion family K15-K17 (R2-47 BRIEF §2)."""
from __future__ import annotations
import numpy as np, pandas as pd
from .. import indicators
from . import Spec, make_table, register
from .context import Context

DAYS30_15M = 30 * 96


def k15_vwap_mr(ctx: Context) -> pd.DataFrame:
    """z of (close / UTC-day VWAP - 1) against the prior 30 days: > 2 short, < -2 long; exit at VWAP; 4 h."""
    b = ctx.bars(15)
    vwap = indicators.vwap_utc(b)
    z = indicators.zscore_past(b.close / vwap - 1, DAYS30_15M, DAYS30_15M // 2)
    side = np.where(z > 2, -1, np.where(z < -2, 1, 0))
    return make_table(b.decision_time, side, 1, 240, exit_long=(b.close >= vwap).to_numpy(),
                      exit_short=(b.close <= vwap).to_numpy(), ind_vwap_gap_z=z.to_numpy(), ind_vwap=vwap.to_numpy(),
                      ind_close=b.close.to_numpy())


def k16_wick_reversal(ctx: Context) -> pd.DataFrame:
    """5 m wick > 3 x ATR(14) with the opposite wick < ATR -> trade against the wick; 1 h hold."""
    b = ctx.bars(5)
    a = indicators.atr(b, 14)
    body_low, body_high = np.minimum(b.open, b.close), np.maximum(b.open, b.close)
    lower, upper = body_low - b.low, b.high - body_high
    side = np.where((lower > 3 * a) & (upper < a), 1, np.where((upper > 3 * a) & (lower < a), -1, 0))
    return make_table(b.decision_time, side, 1, 60, ind_lower_wick_atr=(lower / a).to_numpy(),
                      ind_upper_wick_atr=(upper / a).to_numpy())


def k17_streak_reversal(n: int):
    """After exactly n consecutive same-colour 15 m bars, enter the opposite side; 2 h hold."""
    def build(ctx: Context) -> pd.DataFrame:
        b = ctx.bars(15)
        colour = np.sign(b.close - b.open).to_numpy(int)
        streak = np.zeros(len(b), int)
        for i in range(len(b)):
            streak[i] = (streak[i - 1] + 1 if i and colour[i] == colour[i - 1] else 1) if colour[i] != 0 else 0
        side = np.where(streak == n, -colour, 0)
        return make_table(b.decision_time, side, 1, 120, ind_streak=streak * colour)
    return build


register(Spec("K15", "reversion", 15, 240, "4h", "LOW", k15_vwap_mr))
register(Spec("K16", "reversion", 5, 60, "1h", "LOW", k16_wick_reversal))
for _n in (5, 7):
    register(Spec(f"K17_N{_n}", "reversion", 15, 120, "1h", "LOW", k17_streak_reversal(_n)))
