"""Signed-size maker event kernel for a single BTCUSDT position (Codex SMDP redesign 2026-10-11; A6: no stops).

Decision: target in TARGETS (-1 .. 1 step 0.25) and wait in WAITS minutes. A decision is taken at the close of minute
bar i; the kernel then runs minutes i+1 .. i+wait and stops at the next decision.

Orders (maker only, no partial fills, one live order at a time):
  * only the difference dq = target - executed is ordered;
  * an order that raises |position| rests at limit_price(close[start-1], side, offset) for TTL 60 m and is cancelled
    unfilled at its expiry (never re-quoted by the kernel; the next decision places a new one);
  * an order that lowers |position| (including a flatten) rests at 2 bps (EXIT_QUOTE_BPS) and is re-quoted at the new
    close every 60 m until filled, exactly as the sleeve passive exit (sleeve_precompute.exit_fill);
  * fills: sleeve_precompute.first_fill rule per bar (limit touched with `pen` bps trade-through, gap-through
    rejected), fill price = limit;
  * re-selecting the target of the live order keeps it (no TTL reset); a different target cancels it and the
    replacement rests from the minute after the next one (one minute cancel latency); a fresh order (none live)
    rests from the next minute;
  * reversal: flatten first; the opposite entry is placed only after the flatten fill, from the following minute.
Accounting (bps of notional 1, identical to the Batch-2 Book for single positions): coins Q (units / fill price),
minute P&L = Q_prev x (c_k - c_{k-1}) + sum fills dQ x (c_k - px), maker fee 2 bps x |dq| per fill, funding PESS on the
executed position only: at a settlement minute min(cf(U_before), cf(U_after)), cf(U) = -U x rate x 1e4.
A6: no position / day stop and no forced target. Kill = fault only: a data gap or timestamp discontinuity (minute step
!= 60 s), a non-finite OHLC value, an OHLC invariant violation, a ledger identity error > 1e-8 (checked by the caller)
or a manual kill: processing stops before the faulty minute, the valid prefix is recorded, no flatten is simulated,
and the run fails (done = fault)."""
from __future__ import annotations
import math
import numba
import numpy as np

TARGETS = (-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0)
WAITS = (5, 15, 60, 240, 1440)
TICK, EXIT_QUOTE_BPS, TTL, FEE_SIDE = 0.1, 2.0, 60, 2.0
HALF_LIFE_MIN = 30 * 1440
FLAT_ABS = 0.125                        # |executed| below this counts as flat (idle / flat diagnostics)
K_RESET_MIN = 60                        # reward flat streak k resets after 60 consecutive non-flat minutes
EPS = 1e-12
MIN_NS = 60_000_000_000

(S_U, S_Q, S_EQ, S_POSPNL, S_PEND, S_PDQ, S_PLIM, S_PSTART, S_PEXP, S_PKIND, S_PTGT, S_LEG2, S_PPLACED,
 S_KILL, S_FAULT, S_FAULTK, S_FAULTCODE, S_FILLS, S_FEES, S_FUND, S_TTLX, S_REQ, S_REV, S_RT,
 S_FLATMIN, S_FLATSTREAK, S_FLATMAX, S_F2F_SUM, S_F2F_N, S_KSTREAK, S_NONFLATRUN, S_VALID, S_KILLCOUNT,
 S_NSTATE) = range(34)
K_INC, K_RED = 1.0, 2.0
FAULTS = {0: "none", 1: "data_gap_or_timestamp_discontinuity", 2: "nonfinite_ohlc", 3: "ohlc_invariant",
          4: "ledger_identity", 5: "manual_kill"}


@numba.njit(cache=True)
def _limit(close, side, off):
    if side > 0:
        return math.floor(close * (1 - off / 1e4) / TICK + 1e-9) * TICK
    return math.ceil(close * (1 + off / 1e4) / TICK - 1e-9) * TICK


@numba.njit(cache=True)
def _fills(o, h, l, k, lim, buy, pen):
    if buy:
        return o[k] >= lim and l[k] <= lim * (1 - pen / 1e4)
    return o[k] <= lim and h[k] >= lim * (1 + pen / 1e4)


@numba.njit(cache=True)
def _place(st, c, tgt, start, off, n):
    """Order toward `tgt` from executed U, resting from minute `start` (price from close[start-1])."""
    U = st[S_U]
    if abs(tgt - U) < EPS or start >= n:
        st[S_PEND] = 0.0
        return
    if U * tgt < -EPS:                      # reversal: flatten leg first
        dq, kind, leg2 = -U, K_RED, 1.0
    elif abs(tgt) < abs(U) - EPS:
        dq, kind, leg2 = tgt - U, K_RED, 0.0
    else:
        dq, kind, leg2 = tgt - U, K_INC, 0.0
    side = 1 if dq > 0 else -1
    q = off if kind == K_INC else EXIT_QUOTE_BPS
    st[S_PEND], st[S_PDQ], st[S_PLIM] = 1.0, dq, _limit(c[start - 1], side, q)
    st[S_PSTART], st[S_PEXP], st[S_PKIND], st[S_PTGT], st[S_LEG2] = start, start + TTL, kind, tgt, leg2
    st[S_PPLACED] = start - 1


@numba.njit(cache=True)
def _fault_at(o, h, l, c, t, k):
    if t[k] - t[k - 1] != MIN_NS:
        return 1
    if not (math.isfinite(o[k]) and math.isfinite(h[k]) and math.isfinite(l[k]) and math.isfinite(c[k])):
        return 2
    if h[k] < o[k] or h[k] < c[k] or h[k] < l[k] or l[k] > o[k] or l[k] > c[k]:
        return 3
    return 0


@numba.njit(cache=True)
def _minute(o, h, l, c, frate, st, k, off, pen, n):
    """One minute k of the book; returns its net4 P&L (bps)."""
    U0, Q0 = st[S_U], st[S_Q]
    v = Q0 * (c[k] - c[k - 1]) * 1e4
    if st[S_PEND] > 0 and k >= st[S_PEXP]:
        if st[S_PKIND] == K_RED:                # re-quote the passive reduction at the new close
            side = 1 if st[S_PDQ] > 0 else -1
            st[S_PLIM], st[S_PSTART], st[S_PEXP] = _limit(c[k - 1], side, EXIT_QUOTE_BPS), k, k + TTL
            st[S_REQ] += 1
        else:
            st[S_PEND] = 0.0
            st[S_TTLX] += 1
    if st[S_PEND] > 0 and k >= st[S_PSTART]:
        dq, lim = st[S_PDQ], st[S_PLIM]
        if _fills(o, h, l, k, lim, dq > 0, pen):
            U = st[S_U]
            if abs(U + dq) < EPS:
                dQ = -st[S_Q]
            elif U * dq < 0:
                dQ = -st[S_Q] * abs(dq) / abs(U)
            else:
                dQ = dq / lim
            v += dQ * (c[k] - lim) * 1e4 - FEE_SIDE * abs(dq)
            st[S_Q] += dQ
            st[S_U] = 0.0 if abs(U + dq) < EPS else U + dq
            st[S_FILLS] += 1
            st[S_FEES] += FEE_SIDE * abs(dq)
            st[S_PEND] = 0.0
            if st[S_LEG2] > 0 and abs(st[S_PTGT]) > EPS:
                _place(st, c, st[S_PTGT], k + 1, off, n)
                st[S_REV] += 1
    r = frate[k]
    if r == r:                                  # settlement at this minute (PESS on executed units)
        a, b = -U0 * r * 1e4, -st[S_U] * r * 1e4
        f = a if a < b else b
        v += f
        st[S_FUND] += f
    st[S_EQ] += v
    if abs(U0) < EPS and abs(st[S_U]) > EPS:
        st[S_POSPNL] = v
    elif abs(st[S_U]) > EPS:
        st[S_POSPNL] += v
    else:
        if abs(U0) > EPS:
            st[S_RT] += 1                       # completed round trip: position -> flat
        st[S_POSPNL] = 0.0
    flat0, flat1 = abs(U0) < FLAT_ABS, abs(st[S_U]) < FLAT_ABS
    if flat1:
        st[S_FLATMIN] += 1
        st[S_FLATSTREAK] += 1
        if st[S_FLATSTREAK] > st[S_FLATMAX]:
            st[S_FLATMAX] = st[S_FLATSTREAK]
        st[S_KSTREAK] += 1
        st[S_NONFLATRUN] = 0.0
    else:
        if flat0:                               # flat streak ended by a fill
            st[S_F2F_SUM] += st[S_FLATSTREAK]
            st[S_F2F_N] += 1
        st[S_FLATSTREAK] = 0.0
        st[S_NONFLATRUN] += 1
        if st[S_NONFLATRUN] >= K_RESET_MIN:
            st[S_KSTREAK] = 0.0
    st[S_VALID] += 1
    return v


@numba.njit(cache=True)
def advance(o, h, l, c, t, frate, st, pnl, upath, kpath, i, j, tgt, off, pen):
    """Decision at bar i with agent target tgt; run minutes i+1 .. j (inclusive) unless a fault stops it first.
    Writes pnl[k], executed position upath[k] and the reward flat streak kpath[k] (minutes, end of minute k)."""
    n = len(c)
    if st[S_FAULT] > 0:
        return
    if st[S_KILL] > 0:
        st[S_FAULT], st[S_FAULTK], st[S_FAULTCODE] = 1.0, i + 1, 5.0
        st[S_KILLCOUNT] += 1
        return
    if st[S_PEND] > 0:
        if abs(st[S_PTGT] - tgt) > EPS:
            st[S_PEND] = 0.0
            _place(st, c, tgt, i + 2, off, n)
    else:
        _place(st, c, tgt, i + 1, off, n)
    for k in range(i + 1, j + 1):
        code = _fault_at(o, h, l, c, t, k)
        if code > 0:
            st[S_FAULT], st[S_FAULTK], st[S_FAULTCODE] = 1.0, k, code
            st[S_KILLCOUNT] += 1
            return
        pnl[k] = _minute(o, h, l, c, frate, st, k, off, pen, n)
        upath[k] = st[S_U]
        kpath[k] = st[S_KSTREAK]


class Kernel:
    """Python wrapper: one continuous run over a minute range of one market / execution cell."""

    def __init__(self, o, h, l, c, t_ns, ft_ns, fr, offset: float, pen: float):
        self.o, self.h, self.l, self.c = (np.ascontiguousarray(x, np.float64) for x in (o, h, l, c))
        self.t = np.asarray(t_ns, np.int64)
        self.frate = np.full(len(self.t), np.nan)
        k = np.searchsorted(self.t, ft_ns)
        ok = (k < len(self.t)) & (self.t[np.minimum(k, len(self.t) - 1)] == ft_ns)
        self.frate[k[ok]] = np.asarray(fr, float)[ok]
        self.offset, self.pen = float(offset), float(pen)
        self.pnl = np.zeros(len(self.t))
        self.upath = np.zeros(len(self.t))
        self.kpath = np.zeros(len(self.t))

    def reset(self, i0: int, kill: bool = False):
        self.st = np.zeros(S_NSTATE)
        self.st[S_KILL] = float(kill)
        self.i, self.i0 = int(i0), int(i0)
        self.pnl[:] = 0.0
        self.upath[:] = 0.0
        self.kpath[:] = 0.0
        self.last_target = 0.0
        return self.i

    def fault(self, code: int, k: int) -> None:
        """Caller-detected fault (ledger identity): stop here, no flatten."""
        if self.st[S_FAULT] == 0:
            self.st[S_FAULT], self.st[S_FAULTK], self.st[S_FAULTCODE] = 1.0, k, float(code)
            self.st[S_KILLCOUNT] += 1

    def step(self, target: float, wait: int) -> dict:
        if float(target) not in TARGETS or int(wait) not in WAITS:
            raise ValueError(f"illegal action target={target} wait={wait}")
        j = min(self.i + int(wait), len(self.t) - 1)
        eq0, f0, v0 = self.st[S_EQ], self.st[S_FILLS], self.st[S_VALID]
        advance(self.o, self.h, self.l, self.c, self.t, self.frate, self.st, self.pnl, self.upath, self.kpath,
                self.i, j, float(target), self.offset, self.pen)
        fault = bool(self.st[S_FAULT])
        jj = j if not fault else int(self.st[S_FAULTK]) - 1
        info = {"i": self.i, "j": max(jj, self.i), "target": float(target), "effective_target": float(target),
                "d_target": abs(float(target) - self.last_target), "net4": float(self.st[S_EQ] - eq0),
                "fills": int(self.st[S_FILLS] - f0), "executed": float(self.st[S_U]), "pending": bool(self.st[S_PEND]),
                "fault": fault, "minutes_valid": int(self.st[S_VALID] - v0), **diagnostics(self.st, self.t)}
        self.last_target = float(target)
        self.i = info["j"]
        return info


def diagnostics(st: np.ndarray, t: np.ndarray | None = None) -> dict:
    """Kill / flat diagnostics (A6)."""
    fk = int(st[S_FAULTK])
    return {"kill_count": int(st[S_KILLCOUNT]), "kill_reason": FAULTS[int(st[S_FAULTCODE])],
            "fault_time": (int(t[fk]) if (t is not None and st[S_FAULT] > 0 and 0 <= fk < len(t)) else None),
            "valid_prefix_minutes": int(st[S_VALID]), "episode_aborted": bool(st[S_FAULT]),
            "flat_hours": float(st[S_FLATMIN] / 60.0), "flat_streak_max_h": float(st[S_FLATMAX] / 60.0),
            "flat_to_fill_h": float(st[S_F2F_SUM] / st[S_F2F_N] / 60.0) if st[S_F2F_N] else None}


def rv24h(c: np.ndarray) -> np.ndarray:
    """Trailing 24h realised volatility (bps) from 1m log returns ending at each minute's close (causal at close)."""
    r = np.r_[0.0, np.diff(np.log(c))]
    cs = np.r_[0.0, np.cumsum(r * r)]
    n = np.arange(len(c))
    lo = np.maximum(n + 1 - 1440, 0)
    return np.sqrt(cs[n + 1] - cs[lo]) * 1e4


def rv_ref_monthly(t_ns: np.ndarray, rv: np.ndarray, min_days: int = 30) -> np.ndarray:
    """RV_ref per minute: median RV24h of all minutes strictly before the minute's UTC month start (expanding past,
    fixed within the month); NaN until min_days of history exist."""
    import pandas as pd
    month = pd.DatetimeIndex(t_ns, tz="UTC").to_period("M")
    starts = np.flatnonzero(np.r_[True, month[1:] != month[:-1]])
    out = np.full(len(t_ns), np.nan)
    ends = np.r_[starts[1:], len(t_ns)]
    for a, b in zip(starts, ends):
        if a >= min_days * 1440 + 1440:
            out[a:b] = np.median(rv[1440:a])
    return out


def gamma(d_min: float) -> float:
    return math.exp(-math.log(2.0) * d_min / HALF_LIFE_MIN)
