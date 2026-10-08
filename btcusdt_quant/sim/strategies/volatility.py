"""Volatility family K06-K09 (R2-47 BRIEF §2)."""
from __future__ import annotations
import numpy as np, pandas as pd
from .. import indicators, regime
from . import Spec, make_table, register
from .context import Context

PREDICTION_AGE = pd.Timedelta(minutes=14)


def _prediction(ctx: Context, decisions, column: str) -> np.ndarray:
    return regime._asof(ctx.regime, pd.DatetimeIndex(decisions), column, PREDICTION_AGE)


def _oco_band(ctx: Context, cadence: int, column: str, k: float) -> pd.DataFrame:
    b = ctx.bars(cadence)
    width = _prediction(ctx, b.decision_time, column)
    close = b.close.to_numpy(float)
    with np.errstate(invalid="ignore"):
        upper, lower = close * np.exp(k * width / 1e4), close * np.exp(-k * width / 1e4)
    return make_table(b.decision_time, 0, 1, 240, entry="oco", upper=upper, lower=lower, expiry_min=60,
                      allow_entry=np.isfinite(width) & (width > 0), ind_close=close,
                      anchor_upper=upper, anchor_lower=lower, anchor_price=close,   # R2-52A: band stored at fill
                      **{f"ind_pred_{column.split('_', 1)[1]}_bps": width})


def k06_vb(k: float):
    """Each hour: OCO stop entries at close_T * exp(+-k * predicted range_1h); 1 h expiry; 4 h hold."""
    return lambda ctx: _oco_band(ctx, 60, "prediction_range_1h", k)


def k07_straddle(k: float):
    """Each 15 m: OCO stop entries at close_T * exp(+-k * predicted exc_1h); 1 h expiry; 4 h hold."""
    return lambda ctx: _oco_band(ctx, 15, "prediction_exc_1h", k)


def k08_squeeze(ctx: Context) -> pd.DataFrame:
    """BB(20,2) inside KC(20,1.5) for >= 6 bars, then the first bar outside: side = sign(close - BB middle)."""
    b = ctx.bars(15)
    bb, kc = indicators.bollinger(b.close, 20, 2.0), indicators.keltner(b, 20, 1.5)
    inside = ((bb.upper < kc.upper) & (bb.lower > kc.lower)).to_numpy(bool)
    run = np.zeros(len(b), int)
    for i in range(len(b)):
        run[i] = run[i - 1] + 1 if inside[i] and i > 0 else int(inside[i])
    release = ~inside & (np.r_[0, run[:-1]] >= 6)
    side = np.where(release, np.sign(b.close - bb.middle).fillna(0).astype(int), 0)
    return make_table(b.decision_time, side, 1, 480, exit_long=(b.close < kc.lower).to_numpy(),
                      exit_short=(b.close > kc.upper).to_numpy(), ind_squeeze_bars=np.r_[0, run[:-1]],
                      ind_close=b.close.to_numpy(), ind_bb_mid=bb.middle.to_numpy(), ind_kc_upper=kc.upper.to_numpy(),
                      ind_kc_lower=kc.lower.to_numpy())


def k09_lowvol_mr(ctx: Context) -> pd.DataFrame:
    """Close outside BB(20,2) with RSI(14) < 30 (long) / > 70 (short); exit at the BB middle; 4 h hold."""
    b = ctx.bars(15)
    bb, r = indicators.bollinger(b.close, 20, 2.0), indicators.rsi(b.close, 14)
    side = np.where((b.close < bb.lower) & (r < 30), 1, np.where((b.close > bb.upper) & (r > 70), -1, 0))
    return make_table(b.decision_time, side, 1, 240, exit_long=(b.close >= bb.middle).to_numpy(),
                      exit_short=(b.close <= bb.middle).to_numpy(), ind_rsi=r.to_numpy(), ind_close=b.close.to_numpy(),
                      ind_bb_lower=bb.lower.to_numpy(), ind_bb_mid=bb.middle.to_numpy(), ind_bb_upper=bb.upper.to_numpy())


for _k in (0.5, 1.0):
    register(Spec(f"K06_k{_k}", "volatility", 60, 240, "1h", "HIGH", k06_vb(_k)))
    register(Spec(f"K07_k{_k}", "volatility", 15, 240, "1h", "HIGH", k07_straddle(_k)))
register(Spec("K08", "volatility", 15, 480, "4h", "HIGH", k08_squeeze))
register(Spec("K09", "reversion", 15, 240, "4h", "LOW", k09_lowvol_mr))
