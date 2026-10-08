"""numba simulator. Line-for-line translation of reference.simulate; the differential test keeps them equal."""
from __future__ import annotations
import math
import numba
import numpy as np, pandas as pd
from . import costs
from .reference import (TRADE_COLUMNS, SimConfig, SimResult, action_rows, adaptive_inputs, adaptive_state,
                        check_policy, finish)

REASONS = ("stop", "breakeven", "take", "max_hold", "reverse", "flag", "trail", "state")
# R2_52A float state slots (reference._simulate_r2_52a pos dict)
AK, AE0, AR0, AR, ABEST, AARMED, AUP, ALO = range(8)
MAX_LEGS = 8
MINUTE_NS = 60_000_000_000
NO_END = np.iinfo(np.int64).max
# int state slots
NLEG, NTRADE, OPEN, SIDE, TOOK, PENDING_ADD, MAX_HOLD_END, COMPONENT, POS_ID, POS_COUNT = range(10)
MAX_OCO = 16
# float state slots
STOP, TAKE, STOP_BPS, TAKE_BPS = range(4)
# advance_minute state (R2-48 action kernel): one unit held at `side`, entered at minute `entry_i`
STATE_INT = ("side", "entry_i")
STATE_FLOAT = ("entry_price", "exit_price")          # exit_price = this minute's exit fill, if any
A_SIDE, A_ENTRY_I = range(len(STATE_INT))
A_ENTRY, A_EXIT = range(len(STATE_FLOAT))


@numba.njit(cache=True)
def _units(ist, leg_units):
    total = 0.0
    for k in range(ist[NLEG]):
        total += leg_units[k]
    return total


@numba.njit(cache=True)
def _avg(ist, leg_units, leg_price):
    value = 0.0
    for k in range(ist[NLEG]):
        value += leg_units[k] / leg_price[k]
    return _units(ist, leg_units) / value       # quantity-weighted (R2-46)


@numba.njit(cache=True)
def _slip(price, direction, bps):
    return price * (1 + direction * bps / 1e4)          # same as reference.slip: buys +1, sells -1, always adverse


@numba.njit(cache=True)
def advance_minute(i, state_int, state_float, o, h, l, c, fund_ns, fund_rate, t_ns, target_side, fee_per_side,
                   slip_bps):
    """One minute of an action-driven unit position (C1-C3); returns the minute's net bps. A target that differs
    from the held side fills at o[i] with market slippage: close (fee), then open the target (fee), marked to c[i].
    Funding at a settlement minute: a position held through it always pays; one closed or opened at it only if
    the cashflow is negative (PESS, as costs.funding_events). h and l are unused (no stops in action mode)."""
    side = state_int[A_SIDE]
    rate = 0.0
    k = np.searchsorted(fund_ns, t_ns[i])
    if k < len(fund_ns) and fund_ns[k] == t_ns[i]:
        rate = fund_rate[k]
    pnl = 0.0
    if side != 0 and i > 0:
        pnl += side * math.log(o[i] / c[i - 1]) * 1e4                     # overnight gap mark
    if target_side == side:
        if side != 0:
            pnl += side * math.log(c[i] / o[i]) * 1e4 - side * rate * 1e4
        return pnl
    if side != 0:
        price = _slip(o[i], -side, slip_bps)
        state_float[A_EXIT] = price
        pnl += -fee_per_side + side * math.log(price / o[i]) * 1e4 + min(0.0, -side * rate * 1e4)
    if target_side != 0:
        price = _slip(o[i], target_side, slip_bps)
        state_float[A_ENTRY] = price; state_int[A_ENTRY_I] = i
        pnl += -fee_per_side + target_side * math.log(c[i] / price) * 1e4 + min(0.0, -target_side * rate * 1e4)
    state_int[A_SIDE] = target_side
    return pnl


@numba.njit(cache=True)
def _action_loop(t_ns, o, h, l, c, exec_start, exec_end, d_side, fund_ns, fund_rate, fee_per_side, slip_bps):
    """Targets per execution minute through advance_minute; trade rows and end state shaped like _loop's."""
    n = len(o)
    pnl = np.zeros(n)
    cap = len(d_side) + 1
    out_int = np.zeros((cap, 6), np.int64)
    out_float = np.zeros((cap, 5))
    ist = np.zeros(10, np.int64)
    si = np.zeros(len(STATE_INT), np.int64); sf = np.zeros(len(STATE_FLOAT))
    dec = 0
    for i in range(n):
        side = si[A_SIDE]; entry_i = si[A_ENTRY_I]; entry = sf[A_ENTRY]
        target = d_side[exec_start[i]] if exec_end[i] > exec_start[i] else side
        pnl[i] = advance_minute(i, si, sf, o, h, l, c, fund_ns, fund_rate, t_ns, target, fee_per_side, slip_bps)
        if target == side:
            continue
        if side != 0:
            k = ist[NTRADE]
            out_int[k, 0] = dec; out_int[k, 1] = entry_i; out_int[k, 2] = i
            out_int[k, 3] = side; out_int[k, 4] = 4 if target == -side else 5      # reverse / flag
            out_int[k, 5] = ist[POS_ID]
            out_float[k, 0] = 1.0; out_float[k, 1] = entry; out_float[k, 2] = sf[A_EXIT]
            out_float[k, 3] = side * math.log(sf[A_EXIT] / entry) * 1e4
            out_float[k, 4] = fee_per_side * 2
            ist[NTRADE] = k + 1
        if target != 0:
            ist[POS_COUNT] += 1; ist[POS_ID] = ist[POS_COUNT]
            dec = exec_start[i]
    held = 1 if si[A_SIDE] != 0 else 0
    ist[OPEN] = held; ist[SIDE] = si[A_SIDE]; ist[MAX_HOLD_END] = NO_END; ist[NLEG] = held
    m = ist[NTRADE]
    return pnl, out_int[:m], out_float[:m], ist, np.full(held, 1.0), np.full(held, sf[A_ENTRY]), \
        np.full(held, si[A_ENTRY_I]), np.full(held, dec)


@numba.njit(cache=True)
def _fill_stop(side, level, o, h, l):
    if side == 1:
        if o >= level:
            return o
        return level if h >= level else math.nan
    if o <= level:
        return o
    return level if l <= level else math.nan


@numba.njit(cache=True)
def _fill_limit(side, level, o, h, l):
    if side == 1:
        if o <= level:
            return o
        return level if l < level else math.nan
    if o >= level:
        return o
    return level if h > level else math.nan


@numba.njit(cache=True)
def _book_exit(i, fraction, price, reason, o, c, pnl, ist, leg_units, leg_price, leg_tidx, leg_dec,
               out_int, out_float, fee_per_side):
    """Close `fraction` of every leg (pro rata, R2-46 _close_lots); the remaining average is unchanged."""
    side = ist[SIDE]
    for q in range(ist[NLEG]):
        take_units = leg_units[q] * fraction
        gross = side * math.log(price / leg_price[q]) * 1e4 * take_units
        fee = (fee_per_side * take_units) * 2
        k = ist[NTRADE]
        if k >= out_int.shape[0]:
            raise ValueError("trade buffer overflow")
        out_int[k, 0] = leg_dec[q]; out_int[k, 1] = leg_tidx[q]; out_int[k, 2] = i
        out_int[k, 3] = side; out_int[k, 4] = reason; out_int[k, 5] = ist[POS_ID]
        out_float[k, 0] = take_units; out_float[k, 1] = leg_price[q]; out_float[k, 2] = price
        out_float[k, 3] = gross; out_float[k, 4] = fee
        ist[NTRADE] = k + 1
        pnl[i] += -(fee_per_side * take_units)
        base = c[i] if leg_tidx[q] == i else o[i]      # a leg opened this minute is already marked to close
        pnl[i] += side * math.log(price / base) * 1e4 * take_units
        leg_units[q] -= take_units
    n = 0
    for q in range(ist[NLEG]):
        if leg_units[q] > 1e-12:
            leg_units[n] = leg_units[q]; leg_price[n] = leg_price[q]
            leg_tidx[n] = leg_tidx[q]; leg_dec[n] = leg_dec[q]
            n += 1
    ist[NLEG] = n
    if n == 0:
        ist[OPEN] = 0


@numba.njit(cache=True)
def _open_leg(i, side, units, price, j, t_ns, c, pnl, ist, fst, leg_units, leg_price, leg_tidx, leg_dec,
              max_hold_min, stop_bps, take_bps, component, detexit, fee_per_side):
    if ist[OPEN] == 0:
        ist[OPEN] = 1; ist[SIDE] = side; ist[TOOK] = 0
        ist[POS_COUNT] += 1; ist[POS_ID] = ist[POS_COUNT]
        ist[MAX_HOLD_END] = t_ns[i] + max_hold_min[j] * MINUTE_NS if max_hold_min[j] > 0 else NO_END
        ist[PENDING_ADD] = detexit
        ist[COMPONENT] = component[j]
        fst[STOP] = math.nan; fst[TAKE] = math.nan
        fst[STOP_BPS] = stop_bps[j]; fst[TAKE_BPS] = take_bps[j]
    n = ist[NLEG]
    if n >= MAX_LEGS:
        raise ValueError("leg buffer overflow")
    leg_units[n] = units; leg_price[n] = price; leg_tidx[n] = i; leg_dec[n] = j
    ist[NLEG] = n + 1
    pnl[i] += -(fee_per_side * units)
    pnl[i] += side * math.log(c[i] / price) * 1e4 * units          # entry-minute mark to close
    if not math.isnan(fst[STOP_BPS]):
        avg = _avg(ist, leg_units, leg_price)
        pside = ist[SIDE]
        fst[STOP] = avg * math.exp(-pside * fst[STOP_BPS] / 1e4)
        fst[TAKE] = avg * math.exp(pside * fst[TAKE_BPS] / 1e4) if detexit == 1 and ist[TOOK] == 0 else math.nan


@numba.njit(cache=True)
def _touches(i, o_i, h, l, o, c, pnl, ist, fst, leg_units, leg_price, leg_tidx, leg_dec, out_int, out_float,
             fee_per_side, stop_slip):
    """Stop before take; after a take the breakeven stop is live in the same minute (R2-46)."""
    side = ist[SIDE]
    take = fst[TAKE]
    if math.isnan(take):
        take = 1e18 if side == 1 else -1e18
    price = _fill_stop(-side, fst[STOP], o_i, h[i], l[i])
    if not math.isnan(price):
        price *= (1 - side * stop_slip / 1e4)
        _book_exit(i, 1.0, price, 1 if ist[TOOK] == 1 else 0, o, c, pnl, ist,
                   leg_units, leg_price, leg_tidx, leg_dec, out_int, out_float, fee_per_side)
        return
    price = _fill_limit(-side, take, o_i, h[i], l[i])
    if math.isnan(price):
        return
    average = _avg(ist, leg_units, leg_price)            # breakeven = the pre-take average (R2-46)
    _book_exit(i, 0.5, price, 2, o, c, pnl, ist,
               leg_units, leg_price, leg_tidx, leg_dec, out_int, out_float, fee_per_side)
    ist[TOOK] = 1; fst[STOP] = average; fst[TAKE] = math.nan
    if (side == 1 and l[i] <= fst[STOP]) or (side == -1 and h[i] >= fst[STOP]):
        _book_exit(i, 1.0, fst[STOP], 1, o, c, pnl, ist,
                   leg_units, leg_price, leg_tidx, leg_dec, out_int, out_float, fee_per_side)


@numba.njit(cache=True)
def _loop(t_ns, o, h, l, c, exec_start, exec_end, d_side, d_oco, d_upper, d_lower, d_expiry, d_max_hold,
          d_stop_bps, d_take_bps, d_component, d_exit_long, d_exit_short, d_allow, strict, detexit, fee_per_side,
          stop_slip, mslip):
    n = len(o)
    pnl = np.zeros(n)
    cap = 4 * len(d_side) + 8
    out_int = np.zeros((cap, 6), np.int64)
    out_float = np.zeros((cap, 5))
    ist = np.zeros(10, np.int64)
    fst = np.full(4, math.nan)
    leg_units = np.zeros(MAX_LEGS); leg_price = np.zeros(MAX_LEGS)
    leg_tidx = np.zeros(MAX_LEGS, np.int64); leg_dec = np.zeros(MAX_LEGS, np.int64)
    oco_rows = np.zeros(MAX_OCO, np.int64); oco_exp = np.zeros(MAX_OCO, np.int64); n_oco = 0
    first_units = 0.5 if detexit == 1 else 1.0
    for i in range(n):
        held_at_open = ist[OPEN] == 1
        if ist[OPEN] == 1 and i > 0:
            pnl[i] += ist[SIDE] * math.log(o[i] / c[i - 1]) * 1e4 * _units(ist, leg_units)   # overnight gap mark
        # 1) stop / take touches
        if ist[OPEN] == 1 and not math.isnan(fst[STOP]):
            _touches(i, o[i], h, l, o, c, pnl, ist, fst, leg_units, leg_price, leg_tidx, leg_dec, out_int, out_float,
                     fee_per_side, stop_slip)
        # 2) max hold
        if ist[OPEN] == 1 and t_ns[i] >= ist[MAX_HOLD_END]:
            _book_exit(i, 1.0, _slip(o[i], -ist[SIDE], mslip), 3, o, c, pnl, ist,
                       leg_units, leg_price, leg_tidx, leg_dec, out_int, out_float, fee_per_side)
        # 3) decisions executing this minute: exits for every row, then entries in row (priority) order
        exited_now = False
        fill_price = math.nan
        for j in range(exec_start[i], exec_end[i]):
            if ist[OPEN] == 1 and d_component[j] == ist[COMPONENT]:
                pside = ist[SIDE]
                reverse = d_side[j] == -pside
                flag = (d_exit_long[j] and pside == 1) or (d_exit_short[j] and pside == -1)
                if reverse or flag:
                    _book_exit(i, 1.0, _slip(o[i], -pside, mslip), 4 if reverse else 5, o, c, pnl, ist,
                               leg_units, leg_price, leg_tidx, leg_dec, out_int, out_float, fee_per_side)
                    exited_now = True
        for j in range(exec_start[i], exec_end[i]):
            if ist[OPEN] == 1 and d_component[j] == ist[COMPONENT] and ist[PENDING_ADD] == 1:
                ist[PENDING_ADD] = 0
                if d_side[j] == ist[SIDE] and ist[TOOK] == 0 and d_allow[j]:
                    _open_leg(i, ist[SIDE], .5, _slip(o[i], ist[SIDE], mslip), j, t_ns, c, pnl, ist, fst, leg_units,
                              leg_price, leg_tidx, leg_dec, d_max_hold, d_stop_bps, d_take_bps, d_component, detexit, fee_per_side)
                    fill_price = o[i]
                    continue
            blocked = ist[OPEN] == 1 or (strict == 1 and (held_at_open or exited_now))
            if not blocked and d_allow[j] and d_side[j] != 0 and not d_oco[j]:
                _open_leg(i, d_side[j], first_units, _slip(o[i], d_side[j], mslip), j, t_ns, c, pnl, ist, fst,
                          leg_units, leg_price, leg_tidx, leg_dec, d_max_hold, d_stop_bps, d_take_bps, d_component, detexit, fee_per_side)
                fill_price = o[i]
            elif not blocked and d_allow[j] and d_oco[j]:
                if n_oco >= MAX_OCO:
                    raise ValueError("too many pending OCO orders")
                oco_rows[n_oco] = j; oco_exp[n_oco] = t_ns[i] + d_expiry[j] * MINUTE_NS; n_oco += 1
        # 4) pending OCO orders: expire, then the oldest that fills opens the position and cancels the others
        kept = 0
        for q in range(n_oco):
            if t_ns[i] < oco_exp[q]:
                oco_rows[kept] = oco_rows[q]; oco_exp[kept] = oco_exp[q]; kept += 1
        n_oco = kept
        if ist[OPEN] == 0:
            for q in range(n_oco):
                oco_row = oco_rows[q]
                up = _fill_stop(1, d_upper[oco_row], o[i], h[i], l[i])
                down = _fill_stop(-1, d_lower[oco_row], o[i], h[i], l[i])
                side = 0; price = math.nan
                if not math.isnan(up) and not math.isnan(down):
                    if abs(d_upper[oco_row] - o[i]) < abs(o[i] - d_lower[oco_row]):
                        side = 1; price = up
                    else:
                        side = -1; price = down
                elif not math.isnan(up):
                    side = 1; price = up
                elif not math.isnan(down):
                    side = -1; price = down
                if side != 0:
                    _open_leg(i, side, first_units, price, oco_row, t_ns, c, pnl, ist, fst, leg_units, leg_price,
                              leg_tidx, leg_dec, d_max_hold, d_stop_bps, d_take_bps, d_component, detexit, fee_per_side)
                    n_oco = 0
                    fill_price = price
                    break
        # 4b) a fill this minute: its own bar can already touch the new levels (checked from the fill price)
        if not math.isnan(fill_price) and ist[OPEN] == 1 and not math.isnan(fst[STOP]):
            _touches(i, fill_price, h, l, o, c, pnl, ist, fst, leg_units, leg_price, leg_tidx, leg_dec, out_int,
                     out_float, fee_per_side, stop_slip)
        # 5) mark held position from open to close for legs older than this minute
        if ist[OPEN] == 1:
            for k in range(ist[NLEG]):
                if leg_tidx[k] < i:
                    pnl[i] += ist[SIDE] * math.log(c[i] / o[i]) * 1e4 * leg_units[k]
    m = ist[NTRADE]
    n_legs = ist[NLEG]
    return pnl, out_int[:m], out_float[:m], ist, leg_units[:n_legs].copy(), leg_price[:n_legs].copy(), \
        leg_tidx[:n_legs].copy(), leg_dec[:n_legs].copy()


@numba.njit(cache=True)
def _adaptive_stop(side, entry, ast):
    hard = entry * math.exp(-side * ast[AR] / 1e4)
    if ast[AARMED] == 1.0:
        trail = ast[ABEST] * math.exp(-side * 0.5 * ast[AR] / 1e4)
        if side * (trail - hard) > 0:
            return trail, 6
    return hard, 0


@numba.njit(cache=True)
def _adaptive_open(i, side, price, j, e0, t_ns, c, pnl, ist, fst, leg_units, leg_price, leg_tidx, leg_dec,
                   no_hold, no_bps, d_component, d_k, d_up, d_lo, ast, fee_per_side):
    _open_leg(i, side, 1.0, price, j, t_ns, c, pnl, ist, fst, leg_units, leg_price, leg_tidx, leg_dec,
              no_hold, no_bps, no_bps, d_component, 0, fee_per_side)
    ast[AK] = d_k[j]; ast[AE0] = e0; ast[AR0] = min(d_k[j] * e0, 300.0); ast[AR] = ast[AR0]
    ast[ABEST] = price; ast[AARMED] = 0.0; ast[AUP] = d_up[j]; ast[ALO] = d_lo[j]


@numba.njit(cache=True)
def _valid(x):
    return np.isfinite(x) and x > 0


@numba.njit(cache=True)
def _adaptive_loop(t_ns, o, h, l, c, exec_start, exec_end, d_side, d_oco, d_upper, d_lower, d_expiry, d_component,
                   d_exit_long, d_exit_short, d_allow, d_e0, d_k, d_up, d_lo, d_px, e, e_min, fee_per_side, stop_slip,
                   mslip):
    """R2_52A; line-for-line reference._simulate_r2_52a. One leg, so leg slot 0 is the position."""
    n = len(o)
    pnl = np.zeros(n)
    cap = len(d_side) + 8
    out_int = np.zeros((cap, 6), np.int64)
    out_float = np.zeros((cap, 5))
    ist = np.zeros(10, np.int64)
    fst = np.full(4, math.nan)
    ast = np.full(8, math.nan)
    leg_units = np.zeros(MAX_LEGS); leg_price = np.zeros(MAX_LEGS)
    leg_tidx = np.zeros(MAX_LEGS, np.int64); leg_dec = np.zeros(MAX_LEGS, np.int64)
    no_hold = np.zeros(len(d_side), np.int64); no_bps = np.full(len(d_side), math.nan)
    oco_rows = np.zeros(MAX_OCO, np.int64); oco_exp = np.zeros(MAX_OCO, np.int64); n_oco = 0
    for i in range(n):
        held_at_open = ist[OPEN] == 1
        if held_at_open:
            side = ist[SIDE]
            if i > 0:
                pnl[i] += side * math.log(o[i] / c[i - 1]) * 1e4 * 1.0
            if i > leg_tidx[0] and _valid(e_min[i]):
                ast[AR] = min(ast[AR], ast[AK] * e_min[i], 300.0)
            level, reason = _adaptive_stop(side, leg_price[0], ast)
            if (side == 1 and o[i] <= level) or (side == -1 and o[i] >= level):
                _book_exit(i, 1.0, o[i] * (1 - side * stop_slip / 1e4), reason, o, c, pnl, ist, leg_units, leg_price,
                           leg_tidx, leg_dec, out_int, out_float, fee_per_side)
            else:
                for j in range(exec_start[i], exec_end[i]):
                    if d_component[j] != ist[COMPONENT]:
                        continue
                    reverse = d_side[j] == -side
                    flag = (d_exit_long[j] and side == 1) or (d_exit_short[j] and side == -1)
                    state = (side == 1 and d_px[j] <= ast[AUP]) or (side == -1 and d_px[j] >= ast[ALO])
                    if reverse or flag or state:
                        _book_exit(i, 1.0, _slip(o[i], -side, mslip), 4 if reverse else 5 if flag else 7, o, c, pnl,
                                   ist, leg_units, leg_price, leg_tidx, leg_dec, out_int, out_float, fee_per_side)
                        break
        if not held_at_open:
            for j in range(exec_start[i], exec_end[i]):
                if ist[OPEN] == 1:
                    break
                if d_allow[j] and d_side[j] != 0 and not d_oco[j]:
                    if _valid(d_e0[j]):
                        _adaptive_open(i, d_side[j], _slip(o[i], d_side[j], mslip), j, d_e0[j], t_ns, c, pnl, ist,
                                       fst, leg_units, leg_price, leg_tidx, leg_dec, no_hold, no_bps, d_component,
                                       d_k, d_up, d_lo, ast, fee_per_side)
                        n_oco = 0
                elif d_allow[j] and d_oco[j]:
                    if n_oco >= MAX_OCO:
                        raise ValueError("too many pending OCO orders")
                    oco_rows[n_oco] = j; oco_exp[n_oco] = t_ns[i] + d_expiry[j] * MINUTE_NS; n_oco += 1
            kept = 0
            for q in range(n_oco):
                if t_ns[i] < oco_exp[q]:
                    oco_rows[kept] = oco_rows[q]; oco_exp[kept] = oco_exp[q]; kept += 1
            n_oco = kept
            if ist[OPEN] == 0:
                kept = 0
                for q in range(n_oco):
                    oco_row = oco_rows[q]
                    up = _fill_stop(1, d_upper[oco_row], o[i], h[i], l[i])
                    down = _fill_stop(-1, d_lower[oco_row], o[i], h[i], l[i])
                    side = 0; price = math.nan
                    if not math.isnan(up) and not math.isnan(down):
                        if abs(d_upper[oco_row] - o[i]) < abs(o[i] - d_lower[oco_row]):
                            side = 1; price = up
                        else:
                            side = -1; price = down
                    elif not math.isnan(up):
                        side = 1; price = up
                    elif not math.isnan(down):
                        side = -1; price = down
                    if side != 0 and _valid(e[i]):
                        _adaptive_open(i, side, price, oco_row, e[i], t_ns, c, pnl, ist, fst, leg_units, leg_price,
                                       leg_tidx, leg_dec, no_hold, no_bps, d_component, d_k, d_up, d_lo, ast,
                                       fee_per_side)
                        kept = 0
                        break
                    oco_rows[kept] = oco_rows[q]; oco_exp[kept] = oco_exp[q]; kept += 1
                n_oco = kept
            if ist[OPEN] == 1:
                side = ist[SIDE]
                hard = leg_price[0] * math.exp(-side * ast[AR] / 1e4)
                if (side == 1 and l[i] <= hard) or (side == -1 and h[i] >= hard):
                    _book_exit(i, 1.0, hard * (1 - side * stop_slip / 1e4), 0, o, c, pnl, ist, leg_units, leg_price,
                               leg_tidx, leg_dec, out_int, out_float, fee_per_side)
        elif ist[OPEN] == 1:
            side = ist[SIDE]
            level, reason = _adaptive_stop(side, leg_price[0], ast)
            if (side == 1 and l[i] <= level) or (side == -1 and h[i] >= level):
                _book_exit(i, 1.0, level * (1 - side * stop_slip / 1e4), reason, o, c, pnl, ist, leg_units, leg_price,
                           leg_tidx, leg_dec, out_int, out_float, fee_per_side)
        if ist[OPEN] == 1:
            side = ist[SIDE]
            if leg_tidx[0] < i:
                pnl[i] += side * math.log(c[i] / o[i]) * 1e4 * 1.0
            ast[ABEST] = max(ast[ABEST], h[i]) if side == 1 else min(ast[ABEST], l[i])
            if ast[AARMED] == 1.0 or side * math.log(ast[ABEST] / leg_price[0]) * 1e4 >= ast[AR0]:
                ast[AARMED] = 1.0
    m = ist[NTRADE]
    n_legs = ist[NLEG]
    return pnl, out_int[:m], out_float[:m], ist, leg_units[:n_legs].copy(), leg_price[:n_legs].copy(), \
        leg_tidx[:n_legs].copy(), leg_dec[:n_legs].copy(), ast


def simulate(signals: pd.DataFrame, minutes: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
             config: SimConfig, e_bps: np.ndarray | None = None, e_min_bps: np.ndarray | None = None) -> SimResult:
    """e_bps / e_min_bps: R2_52A per-minute E series, contract in reference.adaptive_inputs."""
    if config.reentry not in ("strict", "stop_and_reverse") or config.exit_style not in ("NATIVE", "DETEXIT"):
        raise ValueError("bad config")
    adaptive = check_policy(config)
    t_index = pd.DatetimeIndex(minutes.open_time)
    t_ns = t_index.as_unit("ns").asi8
    decisions = pd.DatetimeIndex(signals.decision_time)
    exec_ns = decisions.as_unit("ns").asi8 + config.delay_min * MINUTE_NS
    # rows are sorted by decision time (schema), so each minute's rows form one contiguous range
    where = np.searchsorted(t_ns, exec_ns)
    hit = where < len(t_ns)
    hit[hit] = t_ns[where[hit]] == exec_ns[hit]
    exec_start = np.zeros(len(t_ns), np.int64); exec_end = np.zeros(len(t_ns), np.int64)
    rows = np.flatnonzero(hit)
    if len(rows):
        minute = where[rows]
        first = np.r_[True, minute[1:] != minute[:-1]]
        last = np.r_[minute[1:] != minute[:-1], True]
        exec_start[minute[first]] = rows[first]
        exec_end[minute[last]] = rows[last] + 1
    o, h, l, c = (minutes[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
    ast = None
    if adaptive:
        e, e_min = adaptive_inputs(signals, len(t_ns), e_bps, e_min_bps)
        col = lambda name: (signals[name] if name in signals else pd.Series(np.nan, index=signals.index)).to_numpy(
            np.float64)
        *loop, ast = _adaptive_loop(
            t_ns, o, h, l, c, exec_start, exec_end, signals.side.to_numpy(np.int64),
            (signals.entry == "oco").to_numpy(), signals.upper.to_numpy(np.float64),
            signals.lower.to_numpy(np.float64), signals.expiry_min.to_numpy(np.int64),
            (signals.component if "component" in signals else pd.Series(0, index=signals.index)).to_numpy(np.int64),
            signals.exit_long.to_numpy(bool), signals.exit_short.to_numpy(bool), signals.allow_entry.to_numpy(bool),
            signals.e0_bps.to_numpy(np.float64), signals.k.to_numpy(np.float64), col("anchor_upper"),
            col("anchor_lower"), col("anchor_price"), e, e_min, float(config.fee_per_side), float(config.stop_slippage_bps),
            float(config.market_slippage_bps))
    elif config.action_mode:
        side = action_rows(signals, config).side.to_numpy(np.int64)
        fund = costs._settlement_arrays() if config.include_funding else (np.zeros(0, np.int64), np.zeros(0))
        loop = _action_loop(t_ns, o, h, l, c, exec_start, exec_end, side, fund[0], fund[1],
                            float(config.fee_per_side), float(config.market_slippage_bps))
    else:
        loop = _loop(
            t_ns, o, h, l, c, exec_start, exec_end, signals.side.to_numpy(np.int64),
            (signals.entry == "oco").to_numpy(),
            signals.upper.to_numpy(np.float64), signals.lower.to_numpy(np.float64),
            signals.expiry_min.to_numpy(np.int64), signals.max_hold_min.to_numpy(np.int64),
            signals.stop_bps.to_numpy(np.float64), signals.take_bps.to_numpy(np.float64),
            (signals.component if "component" in signals else pd.Series(0, index=signals.index)).to_numpy(np.int64),
            signals.exit_long.to_numpy(bool), signals.exit_short.to_numpy(bool), signals.allow_entry.to_numpy(bool),
            int(config.reentry == "strict"), int(config.exit_style == "DETEXIT"),
            float(config.fee_per_side), float(config.stop_slippage_bps), float(config.market_slippage_bps))
    pnl, out_int, out_float, ist, leg_units, leg_price, leg_tidx, leg_dec = loop

    reason_names = REASONS
    trades = [{"decision_time": decisions[j], "entry_time": t_index[entry_i], "exit_time": t_index[exit_i],
               "side": side, "units": units, "entry_price": entry_price, "exit_price": exit_price,
               "exit_reason": reason_names[reason], "gross_bps": gross, "fee_bps": fee, "funding_bps": 0.0,
               "net_bps": gross - fee, "position_id": position_id}
              for (j, entry_i, exit_i, side, reason, position_id), (units, entry_price, exit_price, gross, fee)
              in zip(out_int.tolist(), out_float.tolist())]
    open_legs = ([(decisions[int(leg_dec[q])], t_index[int(leg_tidx[q])], int(ist[SIDE]), float(leg_units[q]),
                   float(leg_price[q]), int(ist[POS_ID])) for q in range(len(leg_units))] if ist[OPEN] == 1 else [])
    result = finish(trades, pnl, t_index, c, config, open_legs, start, end, funding_booked=config.action_mode)
    if result.open_position is not None:
        result.open_position.update(component=int(ist[COMPONENT]), max_hold_end=(
            None if ist[MAX_HOLD_END] == NO_END else pd.Timestamp(int(ist[MAX_HOLD_END]), tz="UTC")))
        if adaptive:
            result.open_position.update(adaptive_state(ist[COMPONENT], ast[AK], ast[AE0], ast[AR0], ast[AR],
                                                       ast[ABEST], ast[AARMED] == 1.0, ast[AUP], ast[ALO]))
    return result
