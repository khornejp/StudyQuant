"""K10 GRID (R2-47 BRIEF §2) with its own unit-fraction simulator; same ledger rules as reference.simulate."""
from __future__ import annotations
import math
import numpy as np, pandas as pd
from .. import costs, orders, regime
from ..reference import SimConfig, SimResult, finish
from . import Spec, make_table, register
from .context import Context

LEVELS, UNIT, WINDOW_MIN = 3, 1 / 3, 240


def grid_plan(ctx: Context, gated: bool) -> pd.DataFrame:
    """Candidate grids: every 15 m decision with base = close_T and step g = 0.5 x predicted range_1h (bps)."""
    b = ctx.bars(15)
    width = regime._asof(ctx.regime, pd.DatetimeIndex(b.decision_time), "prediction_range_1h", pd.Timedelta(minutes=14))
    ok = np.isfinite(width) & (width > 0)
    if gated:
        ok &= regime.gate_mask(ctx.regime, pd.DatetimeIndex(b.decision_time), "LOW")
    return pd.DataFrame({"decision_time": b.decision_time, "base": b.close, "g": 0.5 * width}).loc[ok]


def simulate_grid(ctx: Context, start: pd.Timestamp, end: pd.Timestamp, gated: bool,
                  config: SimConfig = SimConfig(), plan: pd.DataFrame | None = None) -> SimResult:
    m = ctx.minutes
    t_index = pd.DatetimeIndex(m.open_time)
    o, h, l, c = (m[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    plan = grid_plan(ctx, gated) if plan is None else plan      # live books pass their confirmed decisions
    starts = {pd.Timestamp(r.decision_time) + pd.Timedelta(minutes=config.delay_min): r for r in plan.itertuples()}
    pnl = np.zeros(len(m)); trades: list[dict] = []
    grids_opened = 0
    lots: list[dict] = []          # open lots: side, price, time, take
    grid = None                    # dict: decision, base, g, waiting levels [(side, price)], window_end

    def close_lot(i: int, lot: dict, price: float, reason: str) -> None:
        gross = lot["side"] * math.log(price / lot["price"]) * 1e4 * UNIT
        fee = costs.fee_bps(UNIT, config.fee_per_side) * 2
        trades.append({"decision_time": grid["decision"], "entry_time": lot["time"], "exit_time": t_index[i],
                       "side": lot["side"], "units": UNIT, "entry_price": lot["price"], "exit_price": price,
                       "exit_reason": reason, "gross_bps": gross, "fee_bps": fee, "funding_bps": 0.0,
                       "net_bps": gross - fee, "position_id": grid["id"]})
        pnl[i] += -costs.fee_bps(UNIT, config.fee_per_side) + lot["side"] * math.log(price / o[i]) * 1e4 * UNIT

    for i, now in enumerate(t_index):
        if lots and i > 0:
            pnl[i] += sum(x["side"] for x in lots) * math.log(o[i] / c[i - 1]) * 1e4 * UNIT
        if grid is None and now in starts:
            r = starts.pop(now)
            g = float(r.g); base = float(r.base)
            waiting = [(1, base * math.exp(-j * g / 1e4)) for j in range(1, LEVELS + 1)]
            waiting += [(-1, base * math.exp(j * g / 1e4)) for j in range(1, LEVELS + 1)]
            grids_opened += 1
            grid = {"id": grids_opened, "decision": pd.Timestamp(r.decision_time), "base": base, "g": g, "waiting": waiting,
                    "window_end": now + pd.Timedelta(minutes=WINDOW_MIN)}
        if grid is not None:
            if now >= grid["window_end"]:                                   # window over: flat at the open
                for lot in lots:
                    close_lot(i, lot, o[i], "max_hold")
                lots, grid = [], None
            else:
                low_stop = orders.fill_stop(-1, grid["base"] * math.exp(-4 * grid["g"] / 1e4), o[i], h[i], l[i])
                high_stop = orders.fill_stop(1, grid["base"] * math.exp(4 * grid["g"] / 1e4), o[i], h[i], l[i])
                stop = low_stop if low_stop is not None else high_stop
                if stop is not None:                                        # outside +-4g: everything out
                    for lot in lots:
                        close_lot(i, lot, stop, "stop")
                    lots, grid = [], None
                else:
                    for lot in list(lots):                                  # one step of profit per lot
                        price = orders.fill_limit(-lot["side"], lot["take"], o[i], h[i], l[i])
                        if price is not None:
                            close_lot(i, lot, price, "take")
                            lots.remove(lot)
                    for level in list(grid["waiting"]):                     # resting limits, each fills once
                        side, price = level
                        fill = orders.fill_limit(side, price, o[i], h[i], l[i])
                        if fill is not None:
                            grid["waiting"].remove(level)
                            lots.append({"side": side, "price": fill, "time": now,
                                         "take": fill * math.exp(side * grid["g"] / 1e4)})
                            pnl[i] += -costs.fee_bps(UNIT, config.fee_per_side) + side * math.log(c[i] / fill) * 1e4 * UNIT
        for lot in lots:
            if lot["time"] < now:
                pnl[i] += lot["side"] * math.log(c[i] / o[i]) * 1e4 * UNIT
    # lots still open at the end; position_id = grid id (one grid = one position for reporting)
    open_legs = [(grid["decision"], lot["time"], lot["side"], UNIT, lot["price"], grid["id"]) for lot in lots] if grid else []
    result = finish(trades, pnl, t_index, c, config, open_legs, start, end)
    if open_legs:
        result.open_position["side"] = int(np.sign(sum(side * units for _, _, side, units, _, _ in open_legs)))
    else:
        result.open_position = None
    return result


register(Spec("K10", "reversion", 15, WINDOW_MIN, "1h", "LOW", lambda ctx: make_table([], [], 1, 0),
              simulator="grid"))
