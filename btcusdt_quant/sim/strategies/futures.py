"""Futures-data family K18-K24 (R2-47 BRIEF §2). Metrics usable after create_time + 5 min, funding after
settlement, premium after its bar close."""
from __future__ import annotations
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from .. import data, indicators
from . import Spec, make_table, register
from .context import Context

DAYS30_15M, DAYS30_1H = 30 * 96, 30 * 24


def _metric(ctx: Context, column: str, decisions) -> np.ndarray:
    return data.asof(pd.DatetimeIndex(ctx.metrics.available_time), ctx.metrics[column].to_numpy(float),
                     pd.DatetimeIndex(decisions), ttl=None)


def _z_side(z: pd.Series, momentum: bool = True) -> np.ndarray:
    side = np.where(z > 2, 1, np.where(z < -2, -1, 0))
    return side if momentum else -side


def _z_state(z, long_sign: int) -> dict:
    """R2-52A: exit when current_z * entry_z <= 0, both finite. A long entered with sign(entry_z) = long_sign
    (a short with the opposite sign), so the row flags need only the current z."""
    z = np.asarray(z, float)
    with np.errstate(invalid="ignore"):
        return {"ax_exit_long": np.isfinite(z) & (z * long_sign <= 0),
                "ax_exit_short": np.isfinite(z) & (z * long_sign >= 0)}


def k18_funding_extreme(ctx: Context) -> pd.DataFrame:
    """At the first 15 m decision after each settlement: rate above the prior-90-day (270 settlements) q95 ->
    short, below q05 -> long; 8 h hold."""
    f = ctx.funding.sort_values("time").reset_index(drop=True)
    prior = f.rate.shift().rolling(270, min_periods=270)
    q95, q05 = prior.quantile(.95), prior.quantile(.05)
    side = np.where(f.rate > q95, -1, np.where(f.rate < q05, 1, 0))
    decisions = f.time.dt.floor("15min") + pd.Timedelta(minutes=15)
    return make_table(decisions, side, 1, 480, ind_funding_bps=f.rate.to_numpy() * 1e4,
                      ind_q05_bps=q05.to_numpy() * 1e4, ind_q95_bps=q95.to_numpy() * 1e4)


def k19_premium_mr(ctx: Context) -> pd.DataFrame:
    """z of the complete 1 h mean premium against the prior 30 days: > 2 short, < -2 long; 4 h hold."""
    p = ctx.premium
    minute_open = p.available_time - pd.Timedelta(minutes=1)          # available_time = close_time + 1 ms
    hour = minute_open.dt.floor("h")
    g = p.premium.groupby(hour)
    hourly = pd.DataFrame({"mean": g.mean(), "n": g.size()})
    hourly = hourly.loc[hourly.n == 60]
    z = pd.Series(indicators.zscore_past(hourly["mean"].reset_index(drop=True), DAYS30_1H, DAYS30_1H // 2).to_numpy(),
                  index=hourly.index + pd.Timedelta(hours=1))
    decisions = ctx.bars(60).decision_time          # one row per hour; hours without a full premium bar stay flat
    return make_table(decisions, -_z_side(z.reindex(decisions)), 1, 240, ind_premium_z=z.reindex(decisions).to_numpy(),
                      **_z_state(z.reindex(decisions), -1))


def k20_oi_price(variant: str):
    """1 h OI change z (30 days) with the 1 h return: A = trend (z > 2 follows the return),
    B = flush reversal (z < -2 fades the return); 4 h hold."""
    def build(ctx: Context) -> pd.DataFrame:
        b = ctx.bars(60)
        oi_now = _metric(ctx, "oi", b.decision_time)
        oi_before = _metric(ctx, "oi", b.decision_time - pd.Timedelta(hours=1))
        z = indicators.zscore_past(pd.Series(np.log(oi_now / oi_before)), DAYS30_1H, DAYS30_1H // 2).to_numpy()
        ret = np.sign(np.log(b.close / b.close.shift())).to_numpy()
        if variant == "A":
            side = np.where(z > 2, ret, 0)
        else:
            side = np.where(z < -2, -ret, 0)
        return make_table(b.decision_time, np.nan_to_num(side).astype(int), 1, 240, ind_oi_change_z=z, ind_return_sign=ret)
    return build


def k21_taker_imbalance(variant: str):
    """15 m taker-buy share z (30 days): A momentum (z > 2 long), B the opposite; 2 h hold."""
    def build(ctx: Context) -> pd.DataFrame:
        b = ctx.bars(15)
        share = b.taker_buy / b.volume.replace(0, np.nan)
        z = indicators.zscore_past(share, DAYS30_15M, DAYS30_15M // 2)
        return make_table(b.decision_time, _z_side(z, variant == "A"), 1, 120, ind_taker_share_z=z.to_numpy(),
                          ind_taker_share=share.to_numpy(), **_z_state(z, 1 if variant == "A" else -1))
    return build


def _value_at_prior_extreme(close: np.ndarray, value: np.ndarray, window: int, high: bool) -> np.ndarray:
    """value at the bar holding the max (or min) close of the previous `window` bars."""
    out = np.full(len(close), np.nan)
    if len(close) <= window:
        return out
    view = sliding_window_view(close, window)[:-1]          # windows ending at i - 1, for i = window..n-1
    position = (view.argmax(axis=1) if high else view.argmin(axis=1)) + np.arange(len(view))
    out[window:] = value[position]
    return out


def k22_cvd_divergence(ctx: Context) -> pd.DataFrame:
    """New 20-bar closing high with CVD below CVD at the prior closing high -> short; mirror -> long; 4 h."""
    b = ctx.bars(15)
    cvd = (2 * b.taker_buy - b.volume).cumsum().to_numpy(float)
    close = b.close.to_numpy(float)
    new_high = (b.close > b.close.rolling(20).max().shift()).to_numpy()
    new_low = (b.close < b.close.rolling(20).min().shift()).to_numpy()
    cvd_high = _value_at_prior_extreme(close, cvd, 20, True)
    cvd_low = _value_at_prior_extreme(close, cvd, 20, False)
    side = np.where(new_high & (cvd < cvd_high), -1, np.where(new_low & (cvd > cvd_low), 1, 0))
    return make_table(b.decision_time, side, 1, 240, ind_cvd=cvd, ind_cvd_at_prior_high=cvd_high,
                      ind_cvd_at_prior_low=cvd_low, ind_new_high=new_high.astype(int), ind_new_low=new_low.astype(int))


def k23_toptrader_ls(ctx: Context) -> pd.DataFrame:
    """Top-trader account long/short ratio vs its 30-day q10/q90 (current included, like F3): fade; 4 h."""
    b = ctx.bars(60)
    top = pd.Series(_metric(ctx, "top_ls", b.decision_time))
    roll = top.rolling(DAYS30_1H, min_periods=DAYS30_1H)
    side = np.where(top >= roll.quantile(.90), -1, np.where(top <= roll.quantile(.10), 1, 0))
    q50 = roll.quantile(.5)                                          # R2-52A state: exit at the median
    return make_table(b.decision_time, side, 1, 240, ax_exit_long=(top >= q50).to_numpy(),
                      ax_exit_short=(top <= q50).to_numpy())


def k24_taker_lsr(ctx: Context) -> pd.DataFrame:
    """Taker long/short volume ratio z (30 days): > 2 long, < -2 short; 2 h hold."""
    b = ctx.bars(15)
    z = indicators.zscore_past(pd.Series(_metric(ctx, "taker_lsr", b.decision_time)), DAYS30_15M, DAYS30_15M // 2)
    return make_table(b.decision_time, _z_side(z), 1, 120, **_z_state(z, 1))


register(Spec("K18", "futures", 0, 480, "12h", "HIGH", k18_funding_extreme))
register(Spec("K19", "reversion", 60, 240, "4h", "LOW", k19_premium_mr))
for _v in ("A", "B"):
    register(Spec(f"K20_{_v}", "futures", 60, 240, "4h", "HIGH", k20_oi_price(_v)))
    register(Spec(f"K21_{_v}", "futures", 15, 120, "1h", "HIGH", k21_taker_imbalance(_v)))
register(Spec("K22", "futures", 15, 240, "4h", "HIGH", k22_cvd_divergence))
register(Spec("K23", "reversion", 60, 240, "4h", "LOW", k23_toptrader_ls))
register(Spec("K24", "futures", 15, 120, "1h", "HIGH", k24_taker_lsr))
