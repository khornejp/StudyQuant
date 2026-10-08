"""Slow, obvious reference simulator. Correctness over speed; core.py must match it."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
import numpy as np, pandas as pd
from . import costs, orders

TRADE_COLUMNS = ["decision_time", "entry_time", "exit_time", "side", "units", "entry_price", "exit_price",
                 "exit_reason", "gross_bps", "fee_bps", "funding_bps", "net_bps", "position_id"]

@dataclass(frozen=True)
class SimConfig:
    delay_min: int = 1
    reentry: str = "strict"
    exit_style: str = "NATIVE"
    fee_per_side: float = 2.0
    funding_boundary: str = "PESS"
    stop_slippage_bps: float = 0.0
    include_funding: bool = True
    close_at_end: bool = False      # research runs: book any open position at the last close (exit fee charged)
    market_slippage_bps: float = 0.0    # adverse on every market fill: buys at o*(1+s/1e4), sells at o*(1-s/1e4)
    action_mode: bool = False       # rows are target positions (R2-48 C1): only decision_time and side are read
    exit_policy: str = "BASE"       # "R2_52A": adaptive full-position exits (r2_52a_exit_freeze.json), no max hold

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
    position_id: int = 0

    @property
    def units(self) -> float:
        return sum(l.units for l in self.legs)

    @property
    def avg(self) -> float:
        return self.units / sum(l.units / l.price for l in self.legs)   # quantity-weighted (R2-46)

def action_rows(signals: pd.DataFrame, config: SimConfig) -> pd.DataFrame:
    """C1 targets as signal rows: same side holds, flat closes, opposite closes and re-enters at the same fill minute.
    One unit, market fills, no stops or max hold; funding per settlement minute on the size held (C3, PESS)."""
    if (config.reentry != "stop_and_reverse" or config.exit_style != "NATIVE" or config.close_at_end
            or config.funding_boundary != "PESS"):
        raise ValueError("bad config")
    if signals.decision_time.duplicated().any():
        raise ValueError("action mode: one row per decision_time")
    return signals.assign(entry="market", max_hold_min=0, stop_bps=np.nan, take_bps=np.nan, allow_entry=True,
                          component=0, exit_long=signals.side != 1, exit_short=signals.side != -1)

def slip(price: float, direction: int, bps: float) -> float:
    """Market fill price for a buy (direction +1) or a sell (-1): always adverse."""
    return price * (1 + direction * bps / 1e4)

def check_policy(config: SimConfig) -> bool:
    """True for R2_52A, which runs NATIVE/strict rows only (no DETEXIT legs, no action targets)."""
    if config.exit_policy not in ("BASE", "R2_52A") or (config.exit_policy == "R2_52A" and (
            config.exit_style != "NATIVE" or config.reentry != "strict" or config.action_mode)):
        raise ValueError("bad config")
    return config.exit_policy == "R2_52A"

def adaptive_state(component, k, e0, r0, r, best, armed, anchor_upper, anchor_lower) -> dict:
    return {"component": int(component), "max_hold_end": None, "k": float(k), "e0_bps": float(e0),
            "r0_bps": float(r0), "r_bps": float(r), "best_price": float(best), "trail_armed": bool(armed),
            "anchor_upper": float(anchor_upper), "anchor_lower": float(anchor_lower)}

def adaptive_inputs(signals: pd.DataFrame, n: int, e_bps, e_min_bps) -> tuple[np.ndarray, np.ndarray]:
    """R2_52A inputs, one value per minute row (availability, finite >0 and age <=24h applied by the caller):
    e_bps = latest valid E as of open(m), NaN when none (OCO E0); e_min_bps = minimum of every valid E that became
    available in (open(m-1), open(m)], NaN when none (R_t update). Pass both or neither."""
    if "e0_bps" not in signals or "k" not in signals:
        raise ValueError("R2_52A needs signal columns e0_bps and k")
    if (e_bps is None) != (e_min_bps is None):      # no silent fallback: same-minute E arrivals need e_min_bps
        raise ValueError("R2_52A needs both e_bps and e_min_bps (or neither)")
    e = np.full(n, np.nan) if e_bps is None else np.asarray(e_bps, np.float64)
    e_min = np.full(n, np.nan) if e_min_bps is None else np.asarray(e_min_bps, np.float64)
    if len(e) != n or len(e_min) != n:
        raise ValueError("e_bps / e_min_bps must have one value per minute")
    return e, e_min

def simulate(signals: pd.DataFrame, minutes: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
             config: SimConfig, e_bps: np.ndarray | None = None, e_min_bps: np.ndarray | None = None) -> SimResult:
    """e_bps / e_min_bps: R2_52A only, see adaptive_inputs."""
    if config.reentry not in ("strict", "stop_and_reverse") or config.exit_style not in ("NATIVE", "DETEXIT"):
        raise ValueError("bad config")
    if check_policy(config):
        return _simulate_r2_52a(signals, minutes, start, end, config, *adaptive_inputs(signals, len(minutes), e_bps,
                                                                                       e_min_bps))
    if config.action_mode:
        signals = action_rows(signals, config)
    s_bps = config.market_slippage_bps
    t_index = pd.DatetimeIndex(minutes.open_time)
    o, h, l, c = (minutes[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    by_exec = {}
    for row in signals.itertuples(index=False):
        by_exec.setdefault(pd.Timestamp(row.decision_time) + pd.Timedelta(minutes=config.delay_min), []).append(row)
    pnl = np.zeros(len(minutes))
    trades: list[dict] = []
    pos: _Position | None = None
    pending_oco: list = []      # [(row, expiry_time)] in placement order; the first to fill cancels the rest
    positions_opened = 0

    def book_exit(i: int, fraction: float, price: float, reason: str) -> None:
        """Close `fraction` of every leg (R2-46 _close_lots: pro rata, so the remaining average is unchanged)."""
        nonlocal pos
        for leg in pos.legs:
            take_units = leg.units * fraction
            gross = pos.side * math.log(price / leg.price) * 1e4 * take_units
            fee = costs.fee_bps(take_units, config.fee_per_side) * 2
            trades.append({"decision_time": leg.decision, "entry_time": leg.time, "exit_time": t_index[i],
                           "side": pos.side, "units": take_units, "entry_price": leg.price, "exit_price": price,
                           "exit_reason": reason, "gross_bps": gross, "fee_bps": fee, "funding_bps": 0.0,
                           "net_bps": gross - fee, "position_id": pos.position_id})
            pnl[i] += -costs.fee_bps(take_units, config.fee_per_side)
            base = c[i] if leg.time == t_index[i] else o[i]      # a leg opened this minute is already marked to close
            pnl[i] += pos.side * math.log(price / base) * 1e4 * take_units
            leg.units -= take_units
        pos.legs = [leg for leg in pos.legs if leg.units > 1e-12]
        if not pos.legs:
            pos = None

    def open_leg(i: int, side: int, units: float, price: float, decision: pd.Timestamp, row) -> None:
        nonlocal pos, positions_opened
        if pos is None:
            hold = int(row.max_hold_min)
            positions_opened += 1
            pos = _Position(side=side, max_hold_end=t_index[i] + pd.Timedelta(minutes=hold) if hold > 0 else None,
                            stop_bps=float(row.stop_bps), take_bps=float(row.take_bps),
                            pending_add=config.exit_style == "DETEXIT", component=int(row.component),
                            position_id=positions_opened)
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
            book_exit(i, 1.0, price, "breakeven" if pos.took else "stop")
            return
        average = pos.avg                                   # breakeven = the pre-take average (R2-46)
        book_exit(i, 0.5, price, "take")
        pos.took = True; pos.stop = average; pos.take = math.nan
        if (pos.side == 1 and l[i] <= pos.stop) or (pos.side == -1 and h[i] >= pos.stop):
            book_exit(i, 1.0, pos.stop, "breakeven")

    for i, now in enumerate(t_index):
        held_at_open = pos is not None
        if pos is not None and i > 0:
            pnl[i] += pos.side * math.log(o[i] / c[i - 1]) * 1e4 * pos.units   # overnight gap mark
        # 1) stop / take touches
        if pos is not None and not math.isnan(pos.stop):
            touches(i, o[i])
        # 2) max hold
        if pos is not None and pos.max_hold_end is not None and now >= pos.max_hold_end:
            book_exit(i, 1.0, slip(o[i], -pos.side, s_bps), "max_hold")
        # 3) decisions executing this minute
        rows = by_exec.get(now, [])
        exited_now = False
        legs_before = None
        for row in rows:          # a row acts on a held position only through its own component
            if pos is not None and row.component == pos.component:
                reverse = row.side == -pos.side
                flag = (row.exit_long and pos.side == 1) or (row.exit_short and pos.side == -1)
                if reverse or flag:
                    book_exit(i, 1.0, slip(o[i], -pos.side, s_bps), "reverse" if reverse else "flag")
                    exited_now = True
        for row in rows:          # entries in row order = priority
            if pos is not None and row.component == pos.component and pos.pending_add:
                pos.pending_add = False
                if row.side == pos.side and not pos.took and row.allow_entry:
                    open_leg(i, pos.side, .5, slip(o[i], pos.side, s_bps), pd.Timestamp(row.decision_time), row)
                    legs_before = o[i]
                    continue
            blocked = pos is not None or (config.reentry == "strict" and (held_at_open or exited_now))
            if not blocked and row.allow_entry and row.side != 0 and row.entry == "market":
                open_leg(i, int(row.side), .5 if config.exit_style == "DETEXIT" else 1.0,
                         slip(o[i], int(row.side), s_bps), pd.Timestamp(row.decision_time), row)
                legs_before = o[i]
            elif not blocked and row.allow_entry and row.entry == "oco":
                pending_oco.append((row, now + pd.Timedelta(minutes=int(row.expiry_min))))
        # 4) pending OCO orders: expire, then the oldest that fills opens the position and cancels the others
        pending_oco = [(row, expiry) for row, expiry in pending_oco if now < expiry]
        if pos is None:
            for row, expiry in pending_oco:
                hit = orders.fill_oco(float(row.upper), float(row.lower), o[i], h[i], l[i])
                if hit is not None:
                    side, price = hit
                    open_leg(i, side, .5 if config.exit_style == "DETEXIT" else 1.0, price,
                             pd.Timestamp(row.decision_time), row)
                    pending_oco = []
                    legs_before = price
                    break
        # 4b) a fill this minute: its own bar can already touch the new levels (checked from the fill price)
        if legs_before is not None and pos is not None and not math.isnan(pos.stop):
            touches(i, legs_before)
        # 5) mark held position from open to close for legs older than this minute
        if pos is not None:
            for leg in pos.legs:
                if leg.time < now:
                    pnl[i] += pos.side * math.log(c[i] / o[i]) * 1e4 * leg.units
    open_legs = [] if pos is None else [(leg.decision, leg.time, pos.side, leg.units, leg.price, pos.position_id)
                                         for leg in pos.legs]
    return finish(trades, pnl, t_index, c, config, open_legs, start, end)


def _simulate_r2_52a(signals, minutes, start, end, config, e, e_min) -> SimResult:
    """R2-52A frozen minute order: E update -> stop at the open -> known state/native exit at the open -> (flat at
    the open only) market entries / OCO placement -> OCO fills -> entry bar vs hard stop -> carried stop touch ->
    best price / MFE for the next minute. One unit; hard stop entry*exp(-side*R_t), trail best*exp(-side*0.5*R_t)
    once MFE >= R0 on prices up to the previous minute; R_t = min(R_t, k*E_t, 300) from the minute after entry."""
    s_bps, stop_slip, fee = config.market_slippage_bps, config.stop_slippage_bps, config.fee_per_side
    t_index = pd.DatetimeIndex(minutes.open_time)
    o, h, l, c = (minutes[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    signals = signals.assign(**{name: np.nan for name in ("anchor_upper", "anchor_lower", "anchor_price")
                                if name not in signals})
    by_exec = {}
    for row in signals.itertuples(index=False):
        by_exec.setdefault(pd.Timestamp(row.decision_time) + pd.Timedelta(minutes=config.delay_min), []).append(row)
    pnl = np.zeros(len(minutes))
    trades: list[dict] = []
    pos: dict | None = None
    pending: list = []
    opened = 0

    def book_exit(i, price, reason):
        nonlocal pos
        gross = pos["side"] * math.log(price / pos["price"]) * 1e4 * 1.0
        trades.append({"decision_time": pos["decision"], "entry_time": t_index[pos["i"]], "exit_time": t_index[i],
                       "side": pos["side"], "units": 1.0, "entry_price": pos["price"], "exit_price": price,
                       "exit_reason": reason, "gross_bps": gross, "fee_bps": costs.fee_bps(1.0, fee) * 2,
                       "funding_bps": 0.0, "net_bps": gross - costs.fee_bps(1.0, fee) * 2,
                       "position_id": pos["position_id"]})
        pnl[i] += -costs.fee_bps(1.0, fee)
        base = c[i] if pos["i"] == i else o[i]
        pnl[i] += pos["side"] * math.log(price / base) * 1e4 * 1.0
        pos = None

    def open_pos(i, side, price, row, e0):
        nonlocal pos, opened
        opened += 1
        r0 = min(row.k * e0, 300.0)
        pos = {"side": side, "price": price, "i": i, "decision": pd.Timestamp(row.decision_time),
               "component": int(row.component), "k": float(row.k), "e0": e0, "r0": r0, "r": r0, "best": price,
               "armed": False, "anchor_upper": float(row.anchor_upper), "anchor_lower": float(row.anchor_lower),
               "position_id": opened}
        pnl[i] += -costs.fee_bps(1.0, fee)
        pnl[i] += side * math.log(c[i] / price) * 1e4 * 1.0
        pending.clear()                                      # any open cancels every pending OCO

    def active_stop():
        side, r = pos["side"], pos["r"]
        hard = pos["price"] * math.exp(-side * r / 1e4)
        if pos["armed"]:
            trail = pos["best"] * math.exp(-side * 0.5 * r / 1e4)
            if side * (trail - hard) > 0:
                return trail, "trail"
        return hard, "stop"

    def valid(x):
        return math.isfinite(x) and x > 0

    for i, now in enumerate(t_index):
        held_at_open = pos is not None
        rows = by_exec.get(now, [])
        if pos is not None:
            side = pos["side"]
            if i > 0:
                pnl[i] += side * math.log(o[i] / c[i - 1]) * 1e4 * 1.0
            if i > pos["i"] and valid(e_min[i]):
                pos["r"] = min(pos["r"], pos["k"] * e_min[i], 300.0)
            level, reason = active_stop()
            if (side == 1 and o[i] <= level) or (side == -1 and o[i] >= level):
                book_exit(i, o[i] * (1 - side * stop_slip / 1e4), reason)
            else:
                for row in rows:          # a row acts on the held position only through its own component
                    if row.component != pos["component"]:
                        continue
                    reverse = row.side == -side
                    flag = (row.exit_long and side == 1) or (row.exit_short and side == -1)
                    state = ((side == 1 and row.anchor_price <= pos["anchor_upper"])
                             or (side == -1 and row.anchor_price >= pos["anchor_lower"]))   # NaN: no exit
                    if reverse or flag or state:
                        book_exit(i, slip(o[i], -side, s_bps), "reverse" if reverse else "flag" if flag else "state")
                        break
        if not held_at_open:          # no same-minute reentry; rows seen while held are never reused
            for row in rows:
                if pos is not None:
                    break
                if row.allow_entry and row.side != 0 and row.entry == "market":
                    if valid(row.e0_bps):                     # else NO_ENTRY_E
                        open_pos(i, int(row.side), slip(o[i], int(row.side), s_bps), row, float(row.e0_bps))
                elif row.allow_entry and row.entry == "oco":
                    pending.append((row, now + pd.Timedelta(minutes=int(row.expiry_min))))
            pending = [(row, expiry) for row, expiry in pending if now < expiry]
            if pos is None:
                keep = []
                for row, expiry in pending:
                    hit = orders.fill_oco(float(row.upper), float(row.lower), o[i], h[i], l[i])
                    if hit is not None and valid(e[i]):
                        open_pos(i, hit[0], hit[1], row, float(e[i]))
                        keep = []
                        break
                    keep.append((row, expiry))        # untouched, or touched in a NO_ENTRY_E minute: stays live
                pending = keep
            if pos is not None:       # entry bar: full high/low against the new hard stop
                side = pos["side"]
                hard = pos["price"] * math.exp(-side * pos["r"] / 1e4)
                if (side == 1 and l[i] <= hard) or (side == -1 and h[i] >= hard):
                    book_exit(i, hard * (1 - side * stop_slip / 1e4), "stop")
        elif pos is not None:         # carried position: the open was inside the stop, test the bar
            side = pos["side"]
            level, reason = active_stop()
            if (side == 1 and l[i] <= level) or (side == -1 and h[i] >= level):
                book_exit(i, level * (1 - side * stop_slip / 1e4), reason)
        if pos is not None:
            side = pos["side"]
            if pos["i"] < i:
                pnl[i] += side * math.log(c[i] / o[i]) * 1e4 * 1.0
            pos["best"] = max(pos["best"], h[i]) if side == 1 else min(pos["best"], l[i])
            pos["armed"] = pos["armed"] or side * math.log(pos["best"] / pos["price"]) * 1e4 >= pos["r0"]
    open_legs = [] if pos is None else [(pos["decision"], t_index[pos["i"]], pos["side"], 1.0, pos["price"],
                                         pos["position_id"])]
    result = finish(trades, pnl, t_index, c, config, open_legs, start, end)
    if result.open_position is not None:
        result.open_position.update(adaptive_state(pos["component"], pos["k"], pos["e0"], pos["r0"], pos["r"],
                                                   pos["best"], pos["armed"], pos["anchor_upper"],
                                                   pos["anchor_lower"]))
    return result


def finish(trades: list[dict], pnl: np.ndarray, t_index: pd.DatetimeIndex, close: np.ndarray, config: SimConfig,
           open_legs: list[tuple], start: pd.Timestamp, end: pd.Timestamp, funding_booked: bool = False) -> SimResult:
    """Shared by both simulators: optional data-end close, then funding booked at each settlement minute.
    funding_booked: pnl already holds funding (core action mode books it per minute); only trade rows are filled."""
    def book(events, units):
        for when, value in events:
            k = t_index.searchsorted(when)
            if not funding_booked and k < len(t_index) and t_index[k] == when:
                pnl[k] += value * units

    if config.close_at_end and open_legs and len(t_index):
        last = len(t_index) - 1
        for decision, entry_time, side, units, price, position_id in open_legs:
            gross = side * math.log(close[last] / price) * 1e4 * units
            fee = costs.fee_bps(units, config.fee_per_side) * 2
            trades.append({"decision_time": decision, "entry_time": entry_time, "exit_time": t_index[last],
                           "side": side, "units": units, "entry_price": price, "exit_price": float(close[last]),
                           "exit_reason": "data_end", "gross_bps": gross, "fee_bps": fee, "funding_bps": 0.0,
                           "net_bps": gross - fee, "position_id": position_id})
            pnl[last] += -costs.fee_bps(units, config.fee_per_side)    # price already marked to the last close
        open_legs = []
    if config.include_funding:
        for trade in trades:
            events = costs.funding_events(trade["side"], trade["entry_time"], trade["exit_time"], config.funding_boundary)
            trade["funding_bps"] = sum(v for _, v in events) * trade["units"]
            trade["net_bps"] = trade["gross_bps"] - trade["fee_bps"] + trade["funding_bps"]
            book(events, trade["units"])
        if config.action_mode and len(t_index):      # C3: a still-open position pays settlements up to the data end
            for _, entry_time, side, units, _, _ in open_legs:
                book(costs.funding_events(side, entry_time, t_index[-1] + pd.Timedelta(1, "ns"),
                                          config.funding_boundary), units)
    series = pd.Series(pnl, index=t_index)
    inside = (series.index >= start) & (series.index < end)
    frame = pd.DataFrame(trades, columns=TRADE_COLUMNS)
    held = None
    if open_legs:
        units = sum(x[3] for x in open_legs)
        held = {"side": open_legs[0][2], "units": units, "avg_price": units / sum(x[3] / x[4] for x in open_legs),
                "entry_time": open_legs[0][1], "decision_time": open_legs[0][0], "position_id": open_legs[0][5],
                "legs": [{"decision_time": decision, "entry_time": entry_time, "side": side, "units": units,
                          "entry_price": price, "position_id": position_id}
                         for decision, entry_time, side, units, price, position_id in open_legs]}
    return SimResult(trades=frame, minute_pnl=series.loc[inside], open_position=held)
