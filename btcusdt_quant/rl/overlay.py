"""G3 1.0/1.0 + residual-gross NEW overlay (Codex 2026-10-11). G3 keeps priority: its orders and reservations are
processed first and are never changed by NEW, so the G3 books of the joint run equal their standalone runs. NEW is an
event sleeve (one position at a time) simulated against the G3 open+pending gross g(t):

* entry weight at decision i = min(wmax, max(0, cap - g[i+1])) (g[i+1] already holds G3 orders placed at i);
* a NEW entry order is cancelled before the first minute b with g[b] + w > cap (no fill at or after b);
* an open NEW position with such a breach at b <= its exit decision is exited early: exit decision b - 1 (passive
  exit quote from close[b-1], re-quoted every 60 m as usual).

The passive exit tail after a forced exit can still overlap a G3 activation; those minutes are counted and reported
(`exit_tail_exceed_min`), never hidden. With g = 0 the run equals event_sim.simulate_event line for line."""
from __future__ import annotations
import numpy as np, pandas as pd
from . import sleeve_precompute as sp
from .event_sim import TRADE_COLS

EPS = 1e-9


def gross_profile(N: int, tr: pd.DataFrame, orders: pd.DataFrame, ttl: int, hi: int) -> np.ndarray:
    """Per-minute open+pending gross of one sleeve. Pending: [i+1, fill) or [i+1, i+1+ttl) if never filled; open:
    [fill, exit fill] inclusive (to hi-1 when open at the end)."""
    dif = np.zeros(N + 1)
    fill_of = dict(zip(tr.decision_idx.to_numpy(int), tr.entry_idx.to_numpy(int)))
    for i, w, ok in zip(orders.decision_idx.to_numpy(int), orders.weight.to_numpy(float), orders.filled.to_numpy(bool)):
        end = fill_of[i] if ok else min(i + 1 + ttl, hi)
        dif[i + 1] += w
        dif[end] -= w
    j1 = np.where(tr.open_at_end.to_numpy(bool), hi - 1, tr.exit_idx.to_numpy(int))
    np.add.at(dif, tr.entry_idx.to_numpy(int), tr.entry_weight_frozen.to_numpy(float))
    np.add.at(dif, j1 + 1, -tr.entry_weight_frozen.to_numpy(float))
    return np.cumsum(dif)[:N]


def _breach(g: np.ndarray, a: int, b: int, w: float, cap: float) -> int:
    """First minute in [a, b) with g + w > cap, else -1."""
    hit = np.flatnonzero(g[a:b] + w > cap + EPS)
    return a + int(hit[0]) if len(hit) else -1


def simulate_overlay(o, h, l, c, dec, side, hold: int, offset: float, ttl: int, pen: float, lo: int, hi: int,
                     g: np.ndarray, cap: float = 2.0, wmax: float = 1.0):
    """Event run of NEW under the residual gross cap. Returns (trades, orders, stats)."""
    dec, side = np.asarray(dec), np.asarray(side)
    sel = (dec >= lo) & (dec < hi - 1)
    D, S = dec[sel], side[sel]
    if np.any(np.diff(D) <= 0):
        raise ValueError("decisions must be strictly increasing")
    trades, orders, busy, k = [], [], lo, 0
    st = {"entry_limited": 0, "entry_blocked": 0, "order_cancelled": 0, "forced_exit": 0}

    def rec(p, xdec, j1, xpx):
        trades.append({"side": p[0], "entry_weight_frozen": p[1], "decision_idx": p[2], "entry_idx": p[3],
                       "entry_px": p[4], "exit_decision_idx": xdec, "exit_idx": j1, "exit_px": xpx,
                       "open_at_end": j1 < 0})

    while k < len(D):
        if D[k] < busy:
            k += int(np.searchsorted(D[k:], busy))
            continue
        i, s = int(D[k]), int(S[k])
        k += 1
        if s == 0:
            continue
        w = min(wmax, max(0.0, cap - float(g[i + 1])))
        if w < wmax - EPS:
            st["entry_limited"] += 1
        if not w > EPS:
            st["entry_blocked"] += 1
            continue
        end = min(i + 1 + ttl, hi)
        b = _breach(g, i + 1, end, w, cap)
        lim = sp.limit_price(c[i], s, offset)
        j0 = sp.first_fill(o, h, l, i + 1, end if b < 0 else b, lim, s > 0, pen)
        orders.append((i, s, w, j0 >= 0))
        if j0 < 0:
            st["order_cancelled"] += int(b >= 0)
            busy = i + ttl
            continue
        p = (s, w, i, j0, lim)
        xdec = j0 + hold
        b = _breach(g, j0 + 1, min(xdec + 1, hi), w, cap)
        if b >= 0:
            xdec = b - 1
            st["forced_exit"] += 1
        if xdec >= hi - 1:
            rec(p, -1, -1, np.nan)
            break
        j1, xpx = sp.exit_fill(o, h, l, c, xdec, s, hi, pen)
        rec(p, xdec, j1, xpx)
        if j1 < 0:
            break
        busy = j1
    tr = pd.DataFrame(trades, columns=TRADE_COLS)
    od = pd.DataFrame(orders, columns=["decision_idx", "side", "weight", "filled"])
    tot = g[:hi] + gross_profile(len(g), tr, od, ttl, hi)[:hi]
    st.update(max_total_gross=float(tot[lo:].max()) if hi > lo else 0.0,
              exit_tail_exceed_min=int((tot[lo:] > cap + EPS).sum()), max_g3_gross=float(g[lo:hi].max()))
    return tr, od, st
