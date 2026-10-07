"""Trend and momentum family K11-K14 (R2-47 BRIEF §2)."""
from __future__ import annotations
import numpy as np, pandas as pd
from .. import data, indicators
from . import Spec, make_table, register
from .context import Context

SESSIONS = ("00:00", "07:00", "13:30")


def k11_ema_cross(minutes_per_bar: int):
    """EMA 9/21 cross on complete bars: +1 on an up cross, -1 on a down cross; opposite cross reverses."""
    def build(ctx: Context) -> pd.DataFrame:
        b = ctx.bars(minutes_per_bar)
        fast, slow = indicators.ema(b.close, 9), indicators.ema(b.close, 21)
        diff = fast - slow
        prev = diff.shift()
        side = np.where((diff > 0) & (prev <= 0), 1, np.where((diff < 0) & (prev >= 0), -1, 0))
        return make_table(b.decision_time, side, 1, 720, ind_ema9_minus_ema21=diff.to_numpy(),
                          ind_ema9=fast.to_numpy(), ind_ema21=slow.to_numpy())
    return build


def k12_supertrend(minutes_per_bar: int):
    """Supertrend(10, 3) direction change: enter the new direction; the next change reverses."""
    def build(ctx: Context) -> pd.DataFrame:
        b = ctx.bars(minutes_per_bar)
        direction = indicators.supertrend(b, 10, 3.0)
        side = np.where(direction != direction.shift(), direction, 0)
        side[0] = 0
        return make_table(b.decision_time, side, 1, 720, ind_supertrend_direction=direction.to_numpy(),
                          ind_close=b.close.to_numpy())
    return build


def _last_return_sign(ctx: Context, minutes_per_bar: int, decisions: pd.Series) -> np.ndarray:
    b = ctx.bars(minutes_per_bar)
    sign = np.sign(np.log(b.close / b.close.shift())).to_numpy(float)
    # the latest bar complete at or before T: its decision_time <= T, so "strictly earlier than T + 1 ns"
    return data.asof(pd.DatetimeIndex(b.decision_time), sign, pd.DatetimeIndex(decisions) + pd.Timedelta(1, "ns"), None)


def k13_mtf_momentum(ctx: Context) -> pd.DataFrame:
    """Signs of the last complete 15 m, 1 h and 4 h bar returns all equal -> that side; exit when any differs."""
    b = ctx.bars(15)
    signs = np.vstack([_last_return_sign(ctx, m, b.decision_time) for m in (15, 60, 240)])
    up, down = (signs == 1).all(axis=0), (signs == -1).all(axis=0)
    return make_table(b.decision_time, np.where(up, 1, np.where(down, -1, 0)), 1, 720,
                      exit_long=~up, exit_short=~down, ind_sign_15m=signs[0], ind_sign_1h=signs[1], ind_sign_4h=signs[2])


def k14_session_orb(ctx: Context) -> pd.DataFrame:
    """First 30 min range of each UTC session (00:00, 07:00, 13:30); OCO breakout until start + 4 h;
    native stop at the opposite edge; flat at session start + 8 h."""
    b = ctx.bars(5)
    # the sixth 5 m bar of a session closes its 30 min range; the six bars must be contiguous
    first = b.bar_start - pd.Timedelta(minutes=25)
    is_last = first.dt.strftime("%H:%M").isin(SESSIONS) & (b.bar_start.shift(5) == first)
    high, low = b.high.rolling(6).max(), b.low.rolling(6).min()
    frame = pd.DataFrame({"decision_time": b.decision_time, "upper": high, "lower": low}).loc[is_last]
    # executes at decision + 1 min = start + 31 min; flat at start + 8 h
    return make_table(frame.decision_time, 0, 1, 8 * 60 - 31, entry="oco", upper=frame.upper.to_numpy(),
                      lower=frame.lower.to_numpy(), expiry_min=210,
                      stop_bps=np.log(frame.upper.to_numpy() / frame.lower.to_numpy()) * 1e4,
                      ind_range_high=frame.upper.to_numpy(), ind_range_low=frame.lower.to_numpy(),
                      ind_range_bps=np.log(frame.upper.to_numpy() / frame.lower.to_numpy()) * 1e4)


for _m, _name in ((15, "15m"), (60, "1h")):
    register(Spec(f"K11_{_name}", "trend", _m, 720, "4h", "HIGH", k11_ema_cross(_m)))
for _m, _name, _head in ((30, "30m", "4h"), (60, "1h", "12h")):
    register(Spec(f"K12_{_name}", "trend", _m, 720, _head, "HIGH", k12_supertrend(_m)))
register(Spec("K13", "trend", 15, 720, "4h", "HIGH", k13_mtf_momentum))
register(Spec("K14", "trend", 0, 8 * 60 - 31, "4h", "HIGH", k14_session_orb))
