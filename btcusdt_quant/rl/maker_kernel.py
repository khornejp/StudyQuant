"""Signed-size maker event kernel for a single BTCUSDT position (Codex SMDP redesign 2026-10-11).

Decision: target in TARGETS (-1 .. 1 step 0.25) and wait in WAITS minutes (5m / 15m / 1h / 4h / 24h). A decision is
taken at the close of minute bar i; the kernel then runs minutes i+1 .. i+wait and stops at the next decision.

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
  * reversal: flatten first; the opposite entry is placed only after the flatten fill, from the following minute
    (never both sides in one minute).
Accounting (bps of notional 1, identical to the Batch-2 Book for single positions): coins Q (units / fill price),
minute P&L = Q_prev x (c_k - c_{k-1}) + sum fills dQ x (c_k - px), maker fee 2 bps x |dq| per fill, funding PESS on the
executed position only: at a settlement minute min(cf(U_before), cf(U_after)), cf(U) = -U x rate x 1e4.
Risk: a position whose P&L since it opened reaches -500 bps, or a UTC-day equity change reaching -1500 bps, forces
target 0 (passive flatten, maker only; the loss bound is NOT guaranteed: fills can lag), released when flat (position
stop) / at the next UTC day (daily stop); a kill switch forces 0 permanently."""
from __future__ import annotations
import math
import numba
import numpy as np

TARGETS = (-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0)
WAITS = (5, 15, 60, 240, 1440)
TICK, EXIT_QUOTE_BPS, TTL, FEE_SIDE = 0.1, 2.0, 60, 2.0
POS_STOP_BPS, DAY_STOP_BPS = -500.0, -1500.0
TURNOVER_BPS = 0.05
IDLE_BPS_DAY = 1.0
HALF_LIFE_MIN = 30 * 1440
EPS = 1e-12

# state vector slots
(S_U, S_Q, S_EQ, S_POSPNL, S_DAY0, S_DAY, S_PEND, S_PDQ, S_PLIM, S_PSTART, S_PEXP, S_PKIND, S_PTGT, S_LEG2,
 S_FPOS, S_FDAY, S_KILL, S_FILLS, S_FEES, S_FUND, S_TURN, S_TTLX, S_REQ, S_REV, S_PSTOP, S_DSTOP, S_RT,
 S_POSSTART, S_SPNL, S_AWFLAT, S_SFLATK, S_AWRE, S_DSZ, S_DE2S, S_DFL, S_DNFL, S_DRE, S_DNRE,
 S_NSTATE) = range(39)
# stop diagnostics (sums over stops): size at stop, entry->stop minutes, flatten loss (P&L from the stop to the flat
# fill), flat->re-entry minutes; counts in S_PSTOP + S_DSTOP / S_DNFL / S_DNRE
K_INC, K_RED = 1.0, 2.0


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
def _place(st, c, tgt, start, off):
    """Order toward `tgt` from executed U, resting from minute `start` (price from close[start-1])."""
    U = st[S_U]
    if abs(tgt - U) < EPS or start >= len(c):
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


@numba.njit(cache=True)
def advance(o, h, l, c, day, frate, st, pnl, upath, i, j, tgt, off, pen):
    """Decision at bar i with agent target tgt; run minutes i+1 .. j (inclusive). Writes pnl[k] and the executed
    position upath[k] (end of minute k). Returns the effective target applied at the decision."""
    eff = tgt
    if st[S_KILL] > 0 or st[S_FPOS] > 0 or st[S_FDAY] > 0:
        eff = 0.0
    if st[S_PEND] > 0:
        if abs(st[S_PTGT] - eff) > EPS:
            st[S_PEND] = 0.0
            _place(st, c, eff, i + 2, off)
    else:
        _place(st, c, eff, i + 1, off)
    for k in range(i + 1, j + 1):
        if day[k] != st[S_DAY]:
            st[S_DAY], st[S_DAY0], st[S_FDAY] = day[k], st[S_EQ], 0.0
        U0, Q0 = st[S_U], st[S_Q]
        v = Q0 * (c[k] - c[k - 1]) * 1e4
        if st[S_PEND] > 0 and k >= st[S_PEXP]:
            if st[S_PKIND] == K_RED:            # re-quote the passive reduction at the new close
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
                if st[S_LEG2] > 0 and abs(st[S_PTGT]) > EPS and st[S_KILL] == 0 and st[S_FPOS] == 0 \
                        and st[S_FDAY] == 0:
                    _place(st, c, st[S_PTGT], k + 1, off)
                    st[S_REV] += 1
        r = frate[k]
        if r == r:                                  # settlement at this minute (PESS on executed units)
            a, b = -U0 * r * 1e4, -st[S_U] * r * 1e4
            f = a if a < b else b
            v += f
            st[S_FUND] += f
        pnl[k] = v
        st[S_EQ] += v
        if abs(U0) < EPS and abs(st[S_U]) > EPS:
            st[S_POSPNL] = v
            st[S_POSSTART] = k
            if st[S_AWRE] > 0:
                st[S_DRE] += k - st[S_SFLATK]
                st[S_DNRE] += 1
                st[S_AWRE] = 0.0
        elif abs(st[S_U]) > EPS:
            st[S_POSPNL] += v
        else:
            if abs(U0) > EPS:
                st[S_RT] += 1                       # completed round trip: position -> flat
                if st[S_AWFLAT] > 0:
                    st[S_DFL] += st[S_POSPNL] + v - st[S_SPNL]
                    st[S_DNFL] += 1
                    st[S_AWFLAT], st[S_SFLATK], st[S_AWRE] = 0.0, k, 1.0
            st[S_POSPNL] = 0.0
        if abs(st[S_U]) < EPS and st[S_FPOS] > 0:
            st[S_FPOS] = 0.0
        upath[k] = st[S_U]
        newly = False
        if abs(st[S_U]) > EPS and st[S_POSPNL] <= POS_STOP_BPS and st[S_FPOS] == 0:
            st[S_FPOS], newly = 1.0, True
            st[S_PSTOP] += 1
        if st[S_EQ] - st[S_DAY0] <= DAY_STOP_BPS and st[S_FDAY] == 0:
            st[S_FDAY], newly = 1.0, True
            st[S_DSTOP] += 1
        if newly and abs(st[S_U]) > EPS:
            st[S_DSZ] += abs(st[S_U])
            st[S_DE2S] += k - st[S_POSSTART]
            st[S_SPNL], st[S_AWFLAT] = st[S_POSPNL], 1.0
        if newly:                                   # any live order is replaced by a full flatten (dq = -U)
            st[S_PEND] = 0.0
            if abs(st[S_U]) > EPS and k + 1 < len(c):
                _place(st, c, 0.0, k + 1, off)
    return eff


class Kernel:
    """Python wrapper: one continuous run over a minute range of one market / execution cell."""

    def __init__(self, o, h, l, c, t_ns, ft_ns, fr, offset: float, pen: float):
        self.o, self.h, self.l, self.c = (np.ascontiguousarray(x, np.float64) for x in (o, h, l, c))
        self.t = np.asarray(t_ns, np.int64)
        self.day = (self.t // (86400 * 10**9)).astype(np.int64)
        self.frate = np.full(len(self.t), np.nan)
        k = np.searchsorted(self.t, ft_ns)
        ok = (k < len(self.t)) & (self.t[np.minimum(k, len(self.t) - 1)] == ft_ns)
        self.frate[k[ok]] = np.asarray(fr, float)[ok]
        self.offset, self.pen = float(offset), float(pen)
        self.pnl = np.zeros(len(self.t))
        self.upath = np.zeros(len(self.t))

    def reset(self, i0: int, kill: bool = False):
        self.st = np.zeros(S_NSTATE)
        self.st[S_DAY], self.st[S_KILL] = self.day[i0], float(kill)
        self.i, self.i0 = int(i0), int(i0)
        self.pnl[:] = 0.0
        self.upath[:] = 0.0
        self.last_target = 0.0
        return self.i

    def step(self, target: float, wait: int) -> dict:
        if float(target) not in TARGETS or int(wait) not in WAITS:
            raise ValueError(f"illegal action target={target} wait={wait}")
        j = min(self.i + int(wait), len(self.t) - 1)
        eq0, f0 = self.st[S_EQ], self.st[S_FILLS]
        eff = advance(self.o, self.h, self.l, self.c, self.day, self.frate, self.st, self.pnl, self.upath, self.i, j,
                      float(target), self.offset, self.pen)
        info = {"i": self.i, "j": j, "target": float(target), "effective_target": float(eff),
                "d_target": abs(float(eff) - self.last_target), "net4": float(self.st[S_EQ] - eq0),
                "fills": int(self.st[S_FILLS] - f0), "executed": float(self.st[S_U]),
                "forced_pos": bool(self.st[S_FPOS]), "forced_day": bool(self.st[S_FDAY]), "pending": bool(self.st[S_PEND])}
        self.last_target = float(eff)
        self.i = j
        return info


def rv24h(c: np.ndarray) -> np.ndarray:
    """Trailing 24h realised volatility (bps) from 1m log returns ending at each minute's close (causal at close)."""
    r = np.r_[0.0, np.diff(np.log(c))]
    cs = np.r_[0.0, np.cumsum(r * r)]
    n = np.arange(len(c))
    lo = np.maximum(n + 1 - 1440, 0)
    return np.sqrt(cs[n + 1] - cs[lo]) * 1e4


def gamma(d_min: float) -> float:
    return math.exp(-math.log(2.0) * d_min / HALF_LIFE_MIN)


def step_reward(pnl: np.ndarray, upath: np.ndarray, rv: np.ndarray, rv_med: float, i: int, j: int,
                d_target: float) -> dict:
    """Reward decomposition of one SMDP step (minutes i+1 .. j), per 5-minute block b:
    r_b = net4_b - idle_b - turnover (first block only), idle_b = 1.0 bps / 288 x clip(RV24h / train median, 0.25, 4)
    x I(|executed| < 0.125) (RV and position at the block's last minute); discounted sum with gamma(5 m x b)."""
    nb = (j - i) // 5
    net = np.array([pnl[i + 1 + 5 * b:i + 6 + 5 * b].sum() for b in range(nb)])
    end = i + 5 * (np.arange(nb) + 1)
    idle = IDLE_BPS_DAY / 288.0 * np.clip(rv[end] / rv_med, 0.25, 4.0) * (np.abs(upath[end]) < 0.125)
    turn = np.zeros(nb)
    if nb:
        turn[0] = TURNOVER_BPS * d_target
    r = net - idle - turn
    disc = np.array([gamma(5.0 * b) for b in range(nb)])
    return {"net4": float(net.sum()), "idle": float(idle.sum()), "turnover": float(turn.sum()),
            "reward": float(r.sum()), "reward_discounted": float((disc * r).sum()), "gamma_d": gamma(float(j - i)),
            "blocks": int(nb), "flat_blocks": int((np.abs(upath[end]) < 0.125).sum())}
