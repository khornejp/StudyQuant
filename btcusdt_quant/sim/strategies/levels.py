"""Support/resistance rejection family K25-K28 (R2-49, out/k45_rl_r2_48_20261007/r2_49_freeze.json).

Each level must be known at the 15 m bar's start; the bar trades against a wick that pierced the level and closed
back inside it.
"""
from __future__ import annotations
import numpy as np, pandas as pd
from .. import indicators
from . import Spec, make_table, register
from .context import Context

HOLD = 240
SWING_SIDE = 5            # 1 h bars on each side of a swing point
ROUND = 1000.0            # USDT


def _reject(b: pd.DataFrame, above, below) -> np.ndarray:
    """Short when the high reached the level above and the close is back under it; long mirrored."""
    above, below = np.asarray(above, float), np.asarray(below, float)
    with np.errstate(invalid="ignore"):
        short = (b.high.to_numpy() >= above) & (b.close.to_numpy() < above)
        long = (b.low.to_numpy() <= below) & (b.close.to_numpy() > below)
    return np.where(short & ~long, -1, np.where(long & ~short, 1, 0))


def _prior_day(ctx: Context, b: pd.DataFrame) -> pd.DataFrame:
    d = ctx.bars(1440).set_index("bar_start")
    return d[["high", "low", "close"]].reindex(b.bar_start.dt.floor("D") - pd.Timedelta(days=1)).reset_index(drop=True)


def k25_prior_day(ctx: Context) -> pd.DataFrame:
    b = ctx.bars(15)
    p = _prior_day(ctx, b)
    return make_table(b.decision_time, _reject(b, p.high, p.low), 1, HOLD,
                      ind_prior_day_high=p.high.to_numpy(), ind_prior_day_low=p.low.to_numpy(), ind_close=b.close.to_numpy())


def k26_pivot(ctx: Context) -> pd.DataFrame:
    b = ctx.bars(15)
    p = _prior_day(ctx, b)
    pivot = (p.high + p.low + p.close) / 3
    r1, s1 = 2 * pivot - p.low, 2 * pivot - p.high
    close = b.close.to_numpy()
    return make_table(b.decision_time, _reject(b, r1, s1), 1, HOLD,
                      exit_long=close >= pivot.to_numpy(), exit_short=close <= pivot.to_numpy(),
                      ind_pivot=pivot.to_numpy(), ind_r1=r1.to_numpy(), ind_s1=s1.to_numpy())


def _swings(h: pd.DataFrame, column: str, sign: int) -> pd.Series:
    """Swing levels indexed by the time they are confirmed (close of the 5th bar after the swing bar)."""
    x = sign * h[column].to_numpy(float)
    n, k = len(x), SWING_SIDE
    level, when = [], []
    for j in range(k, n - k):
        if x[j] > x[j - k:j].max() and x[j] > x[j + 1:j + k + 1].max():
            level.append(sign * x[j]); when.append(h.decision_time.iloc[j + k])
    return pd.Series(level, index=pd.DatetimeIndex(when), dtype=float)


def _asof(levels: pd.Series, times: pd.Series) -> np.ndarray:
    position = np.searchsorted(levels.index.as_unit("ns").asi8, pd.DatetimeIndex(times).as_unit("ns").asi8, side="right") - 1
    out = np.full(len(times), np.nan)
    out[position >= 0] = levels.to_numpy()[position[position >= 0]]
    return out


def k27_swing(ctx: Context) -> pd.DataFrame:
    b, h = ctx.bars(15), ctx.bars(60)
    high, low = _asof(_swings(h, "high", 1), b.bar_start), _asof(_swings(h, "low", -1), b.bar_start)
    return make_table(b.decision_time, _reject(b, high, low), 1, HOLD, ind_swing_high=high, ind_swing_low=low)


def k28_round(ctx: Context) -> pd.DataFrame:
    b = ctx.bars(15)
    body_hi, body_lo = np.maximum(b.open, b.close).to_numpy(), np.minimum(b.open, b.close).to_numpy()
    above, below = np.floor(body_hi / ROUND) * ROUND + ROUND, np.ceil(body_lo / ROUND) * ROUND - ROUND
    return make_table(b.decision_time, _reject(b, above, below), 1, HOLD, ind_round_above=above, ind_round_below=below)


# ---- R2-50 advanced versions (out/k45_rl_r2_48_20261007/r2_50_freeze.json) ----
BAND = 0.001              # touch / retest tolerance (0.1 %)
STRENGTH_HOURS = 168
MIN_TOUCHES = 2


def _level_sets(ctx: Context, b: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(resistance, support) columns known at each bar start: prior-day high/low, pivot R1/S1, 1 h swing high/low."""
    p, h = _prior_day(ctx, b), ctx.bars(60)
    pivot = (p.high + p.low + p.close) / 3
    res = np.column_stack([p.high, 2 * pivot - p.low, _asof(_swings(h, "high", 1), b.bar_start)])
    sup = np.column_stack([p.low, 2 * pivot - p.high, _asof(_swings(h, "low", -1), b.bar_start)])
    return res, sup


def _touches(h: pd.DataFrame, at: pd.Timestamp, level: float, column: str) -> int:
    """Closed 1 h bars in the 168 h before `at` whose high/low lies within +-0.1 % of the level."""
    end = int(np.searchsorted(h.decision_time.array.asi8, pd.Timestamp(at).value, side="right"))
    x = h[column].to_numpy()[max(0, end - STRENGTH_HOURS):end]
    return int(np.count_nonzero(np.abs(x / level - 1) <= BAND))


def _hourly_asof(h: pd.DataFrame, values, times) -> np.ndarray:
    """Value of the latest 1 h bar closed at or before each time."""
    position = np.searchsorted(h.decision_time.array.asi8, pd.DatetimeIndex(times).as_unit("ns").asi8, side="right") - 1
    out = np.full(len(times), np.nan)
    out[position >= 0] = np.asarray(values, float)[position[position >= 0]]
    return out


def _stop_bps(close, stop_price, side) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.maximum(side * np.log(np.asarray(close) / np.asarray(stop_price)) * 1e4, 10.0)


def k29_filtered_fade(ctx: Context) -> pd.DataFrame:
    b, h = ctx.bars(15), ctx.bars(60)
    res, sup = _level_sets(ctx, b)
    a = indicators.atr(b, 14).to_numpy()
    high, low, close = b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy()
    adx = _hourly_asof(h, indicators.adx(h, 14), b.decision_time)
    vz = indicators.zscore_past(b.volume, 96, 96).to_numpy()
    with np.errstate(invalid="ignore"):
        base = (adx < 20) & (vz >= 1.5)
        short_hit = base[:, None] & (high[:, None] >= res) & (close[:, None] <= res - 0.25 * a[:, None])
        long_hit = base[:, None] & (low[:, None] <= sup) & (close[:, None] >= sup + 0.25 * a[:, None])
    side = np.zeros(len(b), int)
    for i in np.flatnonzero(short_hit.any(1) | long_hit.any(1)):
        s = any(_touches(h, b.bar_start.iloc[i], res[i, k], "high") >= MIN_TOUCHES for k in np.flatnonzero(short_hit[i]))
        l = any(_touches(h, b.bar_start.iloc[i], sup[i, k], "low") >= MIN_TOUCHES for k in np.flatnonzero(long_hit[i]))
        side[i] = -1 if s and not l else 1 if l and not s else 0
    stop = np.where(side < 0, _stop_bps(close, high + 0.25 * a, -1), np.where(side > 0, _stop_bps(close, low - 0.25 * a, 1), np.nan))
    p = _prior_day(ctx, b)
    mid = ((p.high + p.low) / 2).to_numpy()
    return make_table(b.decision_time, side, 1, HOLD, stop_bps=stop, exit_long=close >= mid, exit_short=close <= mid,
                      ind_adx_1h=adx, ind_volume_z=vz, ind_atr15=a, ind_day_mid=mid)


def k30_break_retest(ctx: Context) -> pd.DataFrame:
    b, h = ctx.bars(15), ctx.bars(60)
    hres, hsup = _level_sets(ctx, h)
    ha, hadx, hema = indicators.atr(h, 14).to_numpy(), indicators.adx(h, 14).to_numpy(), indicators.ema(h.close, 50).to_numpy()
    rising = np.r_[np.full(6, np.nan), hema[6:] - hema[:-6]]
    hclose, prev = h.close.to_numpy(), h.close.shift().to_numpy()
    bt = b.bar_start.array.asi8
    blow, bhigh, bclose = b.low.to_numpy(), b.high.to_numpy(), b.close.to_numpy()
    a15 = indicators.atr(b, 14).to_numpy()
    side, stop = np.zeros(len(b), int), np.full(len(b), np.nan)
    with np.errstate(invalid="ignore"):
        trend_up, trend_down = (hadx >= 25) & (rising > 0), (hadx >= 25) & (rising < 0)
        # a break is a 1 h close through the level from the other side (previous close not yet beyond it)
        up = trend_up[:, None] & (prev[:, None] < hres) & (hclose[:, None] >= hres + 0.25 * ha[:, None])
        down = trend_down[:, None] & (prev[:, None] > hsup) & (hclose[:, None] <= hsup - 0.25 * ha[:, None])
    for direction, hits, levels, column in ((1, up, hres, "high"), (-1, down, hsup, "low")):
        for j, k in zip(*np.nonzero(hits)):
            level = levels[j, k]
            if _touches(h, h.bar_start.iloc[j], level, column) < MIN_TOUCHES:
                continue
            start = h.decision_time.iloc[j].value
            lo, hi = np.searchsorted(bt, start), np.searchsorted(bt, start + pd.Timedelta(hours=12).value)
            if direction == 1:
                ok = (blow[lo:hi] <= level * (1 + BAND)) & (bclose[lo:hi] > level)
            else:
                ok = (bhigh[lo:hi] >= level * (1 - BAND)) & (bclose[lo:hi] < level)
            first = np.flatnonzero(ok)
            if not len(first):
                continue
            i = lo + int(first[0])
            if side[i] not in (0, direction):
                side[i], stop[i] = 0, np.nan          # opposite retests on one bar cancel
                continue
            side[i] = direction
            stop[i] = _stop_bps(bclose[i], level - direction * 0.5 * a15[i], direction)
    return make_table(b.decision_time, side, 1, 480, stop_bps=stop, ind_atr15=a15)


for _id, _build in (("K25", k25_prior_day), ("K26", k26_pivot), ("K27", k27_swing), ("K28", k28_round)):
    register(Spec(_id, "levels", 15, HOLD, "4h", "LOW", _build))
register(Spec("K29", "levels", 15, HOLD, "4h", "LOW", k29_filtered_fade))
register(Spec("K30", "levels", 15, 480, "4h", "HIGH", k30_break_retest))
