"""Slow, obvious reference simulator. Correctness over speed; core.py must match it."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
import numpy as np, pandas as pd
from . import costs, orders

TRADE_COLUMNS = ["decision_time", "entry_time", "exit_time", "side", "units", "entry_price", "exit_price",
                 "exit_reason", "gross_bps", "fee_bps", "funding_bps", "net_bps"]

@dataclass(frozen=True)
class SimConfig:
    delay_min: int = 1
    reentry: str = "strict"
    exit_style: str = "NATIVE"
    fee_per_side: float = 2.0
    funding_boundary: str = "PESS"
    stop_slippage_bps: float = 0.0
    include_funding: bool = True

@dataclass
class SimResult:
    trades: pd.DataFrame
    minute_pnl: pd.Series
    open_position: dict | None = None     # core only: position still held after the last minute

@dataclass
class _Leg:
    units: float
    price: float
    time: pd.Timestamp
    decision: pd.Timestamp

@dataclass
class _Position:
    side: int
    legs: list = field(default_factory=list)
    max_hold_end: pd.Timestamp | None = None
    stop: float = math.nan
    take: float = math.nan
    took: bool = False
    stop_bps: float = math.nan
    take_bps: float = math.nan
    pending_add: bool = False
    component: int = 0

    @property
    def units(self) -> float:
        return sum(l.units for l in self.legs)

    @property
    def avg(self) -> float:
        return self.units / sum(l.units / l.price for l in self.legs)   # quantity-weighted (R2-46)

def simulate(signals: pd.DataFrame, minutes: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
             config: SimConfig) -> SimResult:
    if config.reentry not in ("strict", "stop_and_reverse") or config.exit_style not in ("NATIVE", "DETEXIT"):
        raise ValueError("bad config")
    t_index = pd.DatetimeIndex(minutes.open_time)
    o, h, l, c = (minutes[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    by_exec = {}
    for row in signals.itertuples(index=False):
        by_exec.setdefault(pd.Timestamp(row.decision_time) + pd.Timedelta(minutes=config.delay_min), []).append(row)
    pnl = np.zeros(len(minutes))
    trades: list[dict] = []
    pos: _Position | None = None
    pending_oco = None   # (row, expiry_time)

    def book_exit(i: int, units: float, price: float, reason: str) -> None:
        nonlocal pos
        remaining = units
        while remaining > 1e-12 and pos.legs:
            leg = pos.legs[0]; take_units = min(leg.units, remaining)
            gross = pos.side * math.log(price / leg.price) * 1e4 * take_units
            fee = costs.fee_bps(take_units, config.fee_per_side) * 2
            fund = (costs.funding_bps(pos.side, leg.time, t_index[i], config.funding_boundary) * take_units
                    if config.include_funding else 0.0)
            trades.append({"decision_time": leg.decision, "entry_time": leg.time, "exit_time": t_index[i],
                           "side": pos.side, "units": take_units, "entry_price": leg.price, "exit_price": price,
                           "exit_reason": reason, "gross_bps": gross, "fee_bps": fee, "funding_bps": fund,
                           "net_bps": gross - fee + fund})
            pnl[i] += -costs.fee_bps(take_units, config.fee_per_side) + fund
            base = c[i] if leg.time == t_index[i] else o[i]      # a leg opened this minute is already marked to close
            pnl[i] += pos.side * math.log(price / base) * 1e4 * take_units
            leg.units -= take_units; remaining -= take_units
            if leg.units <= 1e-12:
                pos.legs.pop(0)
        if not pos.legs:
            pos = None

    def open_leg(i: int, side: int, units: float, price: float, decision: pd.Timestamp, row) -> None:
        nonlocal pos
        if pos is None:
            hold = int(row.max_hold_min)
            pos = _Position(side=side, max_hold_end=t_index[i] + pd.Timedelta(minutes=hold) if hold > 0 else None,
                            stop_bps=float(row.stop_bps), take_bps=float(row.take_bps),
                            pending_add=config.exit_style == "DETEXIT", component=int(row.component))
        pos.legs.append(_Leg(units, price, t_index[i], decision))
        pnl[i] += -costs.fee_bps(units, config.fee_per_side)
        pnl[i] += side * math.log(c[i] / price) * 1e4 * units          # entry-minute mark to close
        if not math.isnan(pos.stop_bps):
            pos.stop = pos.avg * math.exp(-pos.side * pos.stop_bps / 1e4)
            detexit = config.exit_style == "DETEXIT" and not pos.took
            pos.take = pos.avg * math.exp(pos.side * pos.take_bps / 1e4) if detexit else math.nan

    def touches(i: int, o_i: float) -> None:
        """Stop before take; after a take the breakeven stop is live in the same minute (R2-46)."""
        hit = orders.exit_touch(pos.side, pos.stop, pos.take if not math.isnan(pos.take) else
                                (1e18 if pos.side == 1 else -1e18), o_i, h[i], l[i])
        if hit is None:
            return
        kind, price = hit
        if kind == "stop":
            price *= (1 - pos.side * config.stop_slippage_bps / 1e4)
            book_exit(i, pos.units, price, "breakeven" if pos.took else "stop")
            return
        book_exit(i, pos.units / 2, price, "take")
        pos.took = True; pos.stop = pos.avg; pos.take = math.nan
        if (pos.side == 1 and l[i] <= pos.stop) or (pos.side == -1 and h[i] >= pos.stop):
            book_exit(i, pos.units, pos.stop, "breakeven")

    for i, now in enumerate(t_index):
        held_at_open = pos is not None
        if pos is not None and i > 0:
            pnl[i] += pos.side * math.log(o[i] / c[i - 1]) * 1e4 * pos.units   # overnight gap mark
        # 1) stop / take touches
        if pos is not None and not math.isnan(pos.stop):
            touches(i, o[i])
        # 2) max hold
        if pos is not None and pos.max_hold_end is not None and now >= pos.max_hold_end:
            book_exit(i, pos.units, o[i], "max_hold")
        # 3) decisions executing this minute
        rows = by_exec.get(now, [])
        exited_now = False
        legs_before = None
        for row in rows:          # a row acts on a held position only through its own component
            if pos is not None and row.component == pos.component:
                reverse = row.side == -pos.side
                flag = (row.exit_long and pos.side == 1) or (row.exit_short and pos.side == -1)
                if reverse or flag:
                    book_exit(i, pos.units, o[i], "reverse" if reverse else "flag")
                    exited_now = True
        for row in rows:          # entries in row order = priority
            if pos is not None and row.component == pos.component and pos.pending_add:
                pos.pending_add = False
                if row.side == pos.side and not pos.took and row.allow_entry:
                    open_leg(i, pos.side, .5, o[i], pd.Timestamp(row.decision_time), row)
                    legs_before = o[i]
                    continue
            blocked = pos is not None or (config.reentry == "strict" and (held_at_open or exited_now))
            if not blocked and row.allow_entry and row.side != 0 and row.entry == "market":
                open_leg(i, int(row.side), .5 if config.exit_style == "DETEXIT" else 1.0, o[i],
                         pd.Timestamp(row.decision_time), row)
                legs_before = o[i]
            elif not blocked and row.allow_entry and row.entry == "oco":
                pending_oco = (row, now + pd.Timedelta(minutes=int(row.expiry_min)))
        # 4) pending OCO
        if pos is None and pending_oco is not None:
            row, expiry = pending_oco
            if now >= expiry:
                pending_oco = None
            else:
                hit = orders.fill_oco(float(row.upper), float(row.lower), o[i], h[i], l[i])
                if hit is not None:
                    side, price = hit
                    open_leg(i, side, .5 if config.exit_style == "DETEXIT" else 1.0, price,
                             pd.Timestamp(row.decision_time), row)
                    pending_oco = None
                    legs_before = price
        # 4b) a fill this minute: its own bar can already touch the new levels (checked from the fill price)
        if legs_before is not None and pos is not None and not math.isnan(pos.stop):
            touches(i, legs_before)
        # 5) mark held position from open to close for legs older than this minute
        if pos is not None:
            for leg in pos.legs:
                if leg.time < now:
                    pnl[i] += pos.side * math.log(c[i] / o[i]) * 1e4 * leg.units
    series = pd.Series(pnl, index=t_index)
    inside = (series.index >= start) & (series.index < end)
    trade_frame = pd.DataFrame(trades, columns=TRADE_COLUMNS)
    return SimResult(trades=trade_frame, minute_pnl=series.loc[inside])
