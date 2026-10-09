"""K01 (R2-39 C1_X), K02-K05 (R2-45 fast components) and composite books B1-B3 (R2-45 simulate_fast)."""
from __future__ import annotations
import numpy as np, pandas as pd
from .. import data, regime
from . import Spec, make_table, register
from .context import Context

F3, E1 = 1, 2                                # K01 components (R2-39)
A2_30, E1_15, F3_30, F3W_30 = 1, 2, 3, 4     # R2-45 priority order
NO_HOLD = 0


def _global_ls(ctx: Context, decisions: pd.Series) -> np.ndarray:
    return data.asof(pd.DatetimeIndex(ctx.metrics.available_time), ctx.metrics.global_ls.to_numpy(float),
                     pd.DatetimeIndex(decisions), ttl=None)


def hourly_levels(ctx: Context) -> pd.DataFrame:
    """R2-39 hourly frame: global_ls at each 1 h decision and its rolling F3/F3W quantile levels."""
    h = ctx.bars(60)
    g = pd.Series(_global_ls(ctx, h.decision_time), index=h.index)
    roll, roll_w = g.rolling(2160, min_periods=720), g.rolling(720, min_periods=720)
    return pd.DataFrame({"decision_time": h.decision_time, "g": g,
                         "f3_lo": roll.quantile(.10), "f3_hi": roll.quantile(.90),
                         "f3w_lo": roll_w.quantile(.20), "f3w_hi": roll_w.quantile(.80),
                         "f3_mid": roll.quantile(.5), "f3w_mid": roll_w.quantile(.5)})   # R2-52A F3/F3W state


def _side(current, lo, hi) -> np.ndarray:
    current, lo, hi = (np.asarray(x, float) for x in (current, lo, hi))
    with np.errstate(invalid="ignore"):
        return np.where(current >= hi, -1, np.where(current <= lo, 1, 0))


def _k01_state(component, h: pd.DataFrame, levels: pd.DataFrame, prior_high: pd.Series, flip: bool = False) -> dict:
    """R2-52A: F3 rows exit long when global_ls >= q50 (short <=); E1 rows carry the prior-20 h high as the anchor
    stored at fill and the completed hourly close as the value compared with it, one-shot (anchor_once): only the
    next completed hourly close after entry is checked (long exits when close <= level). flip (K01_FLIP, F3 side
    flipped): the F3 rule is mirrored (long exits when global_ls <= q50, short >=); E1 unchanged."""
    f3 = np.asarray(component) == F3
    with np.errstate(invalid="ignore"):
        up, down = (levels.g >= levels.f3_mid).to_numpy(), (levels.g <= levels.f3_mid).to_numpy()
        if flip:
            up, down = down, up
        return {"ax_exit_long": f3 & up,
                "ax_exit_short": f3 & down,
                "anchor_upper": np.where(f3, np.nan, prior_high), "anchor_price": np.where(f3, np.nan, h.close),
                "anchor_once": np.where(f3, np.nan, 1.0)}


def k01_c1x(ctx: Context, flip: bool = False) -> pd.DataFrame:
    """R2-39 C1_X: hourly; F3 (24 h, reversed only by F3) has priority over E1 (20 h). flip: K01_FLIP (C1_FLIP_AX),
    the F3 side times -1 (upper extreme long, lower short); rows, priority and E1 unchanged."""
    h = ctx.bars(60)
    levels = hourly_levels(ctx)
    f3 = _side(levels.g, levels.f3_lo, levels.f3_hi) * (-1 if flip else 1)
    vol = h.volume.rolling(20, min_periods=20)
    prior_high = h.high.rolling(20, min_periods=20).max().shift()
    e1 = ((h.volume - vol.mean()) / vol.std(ddof=0) > 3) & (h.close > prior_high)
    e1 = e1.to_numpy(bool)
    use_f3 = f3 != 0
    component = np.where(use_f3 | ~e1, F3, E1)
    return make_table(h.decision_time, np.where(use_f3, f3, np.where(e1, 1, 0)), component,
                      np.where(use_f3, 24 * 60, 20 * 60), **_k01_state(component, h, levels, prior_high, flip))


def k01_ax_rows(ctx: Context, table: pd.DataFrame, flip: bool = False) -> pd.DataFrame:
    """R2-52A: the other component's inert row each hour, so both F3 and E1 positions see every hourly state."""
    h, levels = ctx.bars(60), hourly_levels(ctx)
    other = np.where(table.component.to_numpy() == F3, E1, F3)
    return make_table(h.decision_time, 0, other, table.max_hold_min.to_numpy(), allow_entry=False,
                      **_k01_state(other, h, levels, h.high.rolling(20, min_periods=20).max().shift(), flip))


def k01_c1x_flip(ctx: Context) -> pd.DataFrame:
    return k01_c1x(ctx, flip=True)


def k01_flip_ax_rows(ctx: Context, table: pd.DataFrame) -> pd.DataFrame:
    return k01_ax_rows(ctx, table, flip=True)


def fast_signals(ctx: Context) -> pd.DataFrame:
    """R2-45 build_fast_signals on the 15 m grid: E1-15, A2-30 (+ exit flags), F3-30, F3W-30."""
    b15, b30 = ctx.bars(15), ctx.bars(30)
    vm, vs = b15.volume.rolling(20).mean(), b15.volume.rolling(20).std(ddof=0)
    e1_z, e1_high = (b15.volume - vm) / vs, b15.high.rolling(20).max().shift()
    e1 = ((e1_z > 3) & (b15.close > e1_high)).astype(int)
    e1_ax_long = (b15.high < e1_high).to_numpy()        # R2-52A K04 state: completed bar fails the breakout level
    e1_ax_short = (b15.low > b15.low.rolling(20).min().shift()).to_numpy()   # mirrored (E1 itself never shorts)
    a2_high, a2_low = b30.high.rolling(55).max().shift(), b30.low.rolling(55).min().shift()
    a2 = np.select([b30.close > a2_high, b30.close < a2_low], [1, -1], 0)
    a2_exit_long = (b30.close < b30.low.rolling(10).min().shift()).fillna(False)
    a2_exit_short = (b30.close > b30.high.rolling(10).max().shift()).fillna(False)
    levels = hourly_levels(ctx)
    fixed = pd.merge_asof(b30[["decision_time"]], levels.drop(columns="g"), on="decision_time", direction="backward")
    current = _global_ls(ctx, b30.decision_time)
    s30 = pd.DataFrame({"decision_time": b30.decision_time, "A2-30": a2, "a2_exit_long": a2_exit_long.to_numpy(bool),
                        "a2_exit_short": a2_exit_short.to_numpy(bool),
                        "F3-30": _side(current, fixed.f3_lo, fixed.f3_hi),
                        "F3W-30": _side(current, fixed.f3w_lo, fixed.f3w_hi),
                        "F3_ax_long": current >= fixed.f3_mid.to_numpy(),
                        "F3_ax_short": current <= fixed.f3_mid.to_numpy(),
                        "F3W_ax_long": current >= fixed.f3w_mid.to_numpy(),
                        "F3W_ax_short": current <= fixed.f3w_mid.to_numpy(),
                        "ind_A2_close": b30.close.to_numpy(), "ind_A2_high55": a2_high.to_numpy(),
                        "ind_A2_low55": a2_low.to_numpy(),
                        "ind_A2_low10": b30.low.rolling(10).min().shift().to_numpy(),
                        "ind_A2_high10": b30.high.rolling(10).max().shift().to_numpy(),
                        "ind_F3_ls": current, "ind_F3_q10": fixed.f3_lo.to_numpy(), "ind_F3_q90": fixed.f3_hi.to_numpy(),
                        "ind_F3W_q20": fixed.f3w_lo.to_numpy(), "ind_F3W_q80": fixed.f3w_hi.to_numpy()})
    grid = pd.DataFrame({"decision_time": pd.date_range(b15.decision_time.min(), b15.decision_time.max(),
                                                        freq="15min", tz="UTC")})
    out = grid.merge(pd.DataFrame({"decision_time": b15.decision_time, "E1-15": e1, "E1_ax_long": e1_ax_long, "E1_ax_short": e1_ax_short,
                                   "ind_E1_volume_z": e1_z.to_numpy(),
                                   "ind_E1_close": b15.close.to_numpy(), "ind_E1_high20": e1_high.to_numpy()}),
                     how="left").merge(s30, how="left")
    for name in ("E1-15", "A2-30", "F3-30", "F3W-30"):
        out[name] = out[name].fillna(0).astype(int)
    for name in ("a2_exit_long", "a2_exit_short", "E1_ax_long", "E1_ax_short", "F3_ax_long", "F3_ax_short", "F3W_ax_long",
                 "F3W_ax_short"):
        out[name] = out[name].astype("boolean").fillna(False).astype(bool)
    return out


FAST = {"A2-30": (A2_30, NO_HOLD), "E1-15": (E1_15, 5 * 60), "F3-30": (F3_30, 4 * 60), "F3W-30": (F3W_30, 12 * 60)}
E_HEAD = {"A2-30": "4h", "E1-15": "4h", "F3-30": "4h", "F3W-30": "12h"}     # R2-46 E_COLUMN


def _component_rows(fast: pd.DataFrame, name: str, cadence: int | None = None) -> pd.DataFrame:
    component, hold = FAST[name]
    rows = fast if cadence is None else fast.loc[fast.decision_time.dt.minute % cadence == 0]
    prefix = {"A2-30": "ind_A2_", "E1-15": "ind_E1_", "F3-30": None, "F3W-30": None}[name]
    if name == "F3-30":
        flags = {"ind_global_ls": rows.ind_F3_ls.to_numpy(), "ind_q10": rows.ind_F3_q10.to_numpy(),
                 "ind_q90": rows.ind_F3_q90.to_numpy()}
    elif name == "F3W-30":
        flags = {"ind_global_ls": rows.ind_F3_ls.to_numpy(), "ind_q20": rows.ind_F3W_q20.to_numpy(),
                 "ind_q80": rows.ind_F3W_q80.to_numpy()}
    else:
        flags = {"ind_" + c[len(prefix):]: rows[c].to_numpy() for c in rows if c.startswith(prefix)}
    if name == "A2-30":
        flags.update({"exit_long": rows.a2_exit_long.to_numpy(), "exit_short": rows.a2_exit_short.to_numpy()})
    # R2-52A state: A2 keeps its native flags; E1 breakout level (short mirrored); F3/F3W exit at the q50
    long, short = {"E1-15": ("E1_ax_long", "E1_ax_short"), "F3-30": ("F3_ax_long", "F3_ax_short"),
                   "F3W-30": ("F3W_ax_long", "F3W_ax_short")}.get(name, (None, None))
    flags["ax_exit_long"] = rows[long].to_numpy() if long else False
    flags["ax_exit_short"] = rows[short].to_numpy() if short else False
    return make_table(rows.decision_time, rows[name], component, hold, **flags)


def _single(name: str, cadence: int):
    return lambda ctx: _component_rows(fast_signals(ctx), name, cadence)


def _composite(book: str):
    def build(ctx: Context) -> pd.DataFrame:
        fast = fast_signals(ctx)
        parts = [_component_rows(fast, name).assign(_order=k, _row=np.arange(len(fast)), e_head=E_HEAD[name])
                 for k, name in enumerate(FAST)]
        table = pd.concat(parts, ignore_index=True).sort_values(["_row", "_order"], kind="stable")
        times = pd.DatetimeIndex(table.decision_time)
        m = regime._asof(ctx.regime, times, "M", pd.Timedelta(0))
        l = regime._asof(ctx.regime, times, "L", pd.Timedelta(0))
        with np.errstate(invalid="ignore"):
            high, low = m >= 2 / 3, (m <= 1 / 3) & (l < 2 / 3)
        if book == "B2":
            table["allow_entry"] = high
        elif book == "B3":
            fast_part = table.component.isin([A2_30, E1_15]).to_numpy()
            table["allow_entry"] = np.where(fast_part, high, low)
        return table.drop(columns=["_order", "_row"]).reset_index(drop=True)
    return build


register(Spec("K01", "baseline", 60, 24 * 60, "24h", None, k01_c1x, reentry="stop_and_reverse", ax_rows=k01_ax_rows))
# C1_FLIP_AX (Codex 2026-10-09): post-freeze, run only by scripts/sim_adaptive_exit.py --flip
register(Spec("K01_FLIP", "baseline", 60, 24 * 60, "24h", None, k01_c1x_flip, reentry="stop_and_reverse",
              ax_rows=k01_flip_ax_rows, post_freeze=True))
register(Spec("K02", "reversion", 30, 4 * 60, "4h", "LOW", _single("F3-30", 30)))
register(Spec("K03", "reversion", 30, 12 * 60, "12h", "LOW", _single("F3W-30", 30)))
register(Spec("K04", "volatility", 15, 5 * 60, "4h", "HIGH", _single("E1-15", 15)))
register(Spec("K05", "volatility", 30, NO_HOLD, "4h", "HIGH", _single("A2-30", 30)))
for _book in ("B1", "B2", "B3"):
    register(Spec(_book, "composite", 15, 12 * 60, "4h", None, _composite(_book)))
