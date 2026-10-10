"""Event-kind maker simulator with a per-decision hold (Batch-2 `simulate(kind="event")` semantics, line for line,
generalized from one scalar hold to an array). Used to stitch folds whose selected horizons differ into ONE
continuous run. With a constant hold it reproduces Batch-2 exactly (tests/rl/test_event_sim.py)."""
from __future__ import annotations
import numpy as np, pandas as pd
from . import sleeve_precompute as sp

TRADE_COLS = ["side", "entry_weight_frozen", "decision_idx", "entry_idx", "entry_px", "exit_decision_idx", "exit_idx",
              "exit_px", "open_at_end"]


def simulate_event(o, h, l, c, dec, side, weight, hold, offset: float, ttl: int, pen: float, lo: int, hi: int):
    dec, side, weight, hold = (np.asarray(x) for x in (dec, side, weight, hold))
    sel = (dec >= lo) & (dec < hi - 1)
    D, S, W, Hd = dec[sel], side[sel], weight[sel].astype(float), hold[sel].astype(np.int64)
    if np.any(np.diff(D) <= 0):
        raise ValueError("decisions must be strictly increasing")
    trades, orders, busy, k = [], [], lo, 0

    def rec(p, xdec, j1, xpx):
        trades.append({"side": p[0], "entry_weight_frozen": p[1], "decision_idx": p[2], "entry_idx": p[3],
                       "entry_px": p[4], "exit_decision_idx": xdec, "exit_idx": j1, "exit_px": xpx,
                       "open_at_end": j1 < 0})

    while k < len(D):
        if D[k] < busy:
            k += int(np.searchsorted(D[k:], busy))
            continue
        i, s, w, hd = int(D[k]), int(S[k]), float(W[k]), int(Hd[k])
        k += 1
        if s == 0 or not w > 0:
            continue
        lim = sp.limit_price(c[i], s, offset)
        j0 = sp.first_fill(o, h, l, i + 1, min(i + 1 + ttl, hi), lim, s > 0, pen)
        orders.append((i, s, w, j0 >= 0))
        if j0 < 0:
            busy = i + ttl
            continue
        p = (s, w, i, j0, lim)
        xdec = j0 + hd
        if xdec >= hi - 1:
            rec(p, -1, -1, np.nan)
            break
        j1, xpx = sp.exit_fill(o, h, l, c, xdec, s, hi, pen)
        rec(p, xdec, j1, xpx)
        if j1 < 0:
            break
        busy = j1
    return (pd.DataFrame(trades, columns=TRADE_COLS),
            pd.DataFrame(orders, columns=["decision_idx", "side", "weight", "filled"]))
