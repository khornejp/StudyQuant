"""Signal-only causal store on a 5-minute clock (Codex SMDP redesign 2026-10-11). Techniques are observations only:
no sleeve P&L, exit or outcome ledger is read here.

Token map (one token per base technique id):
  * every research catalog id (btcusdt_quant.sim.strategies.CATALOG, 41) except K10 (grid book, no directional
    signal: empty table) and exact sign-negation duplicates (K21_B == -K21_A on every decision -> merged into K21_A);
  * gated / DETEXIT expansions are not tokens: the gate becomes the gate_pass channel, DETEXIT differs only in exits;
  * AX / AXC0 paper variants are not separate: their entry rows equal the base id's (B3, K04 checked), only exits
    differ; K01_FLIP stays a token (its entries are not K01's);
  * research signals outside the catalog: G3_LONG, G3_SHORT, LBR_FUND, C1v2, C4v2 (grid timelines, primary cell).
Channels per token at clock time t (everything known at t): side, active, strength (+ availability), age_min,
gate_pass (-1 no gate axis), gate_avail, available, recent markout EWMA (mean / hit / vol / count) for h in
{1h, 4h, 24h}; family_id / source_id live in the manifest. Markout m_h(t) = side(t-h) x (C(t) / C(t-h) - 1) x 1e4 - 4
with C(t) = close of minute t-1, published at t (matured), time-decayed EWMA with a 30-day half-life."""
from __future__ import annotations
import numba
import numpy as np, pandas as pd

CLOCK_START = pd.Timestamp("2021-01-30", tz="UTC")
CLOCK_END = pd.Timestamp("2026-01-01", tz="UTC")
STEP_NS = 5 * 60 * 10**9
MIN_NS = 60 * 10**9
HORIZONS = (60, 240, 1440)
EWMA_HALF_LIFE_MIN = 30 * 1440
COST_BPS = 4.0
EXCLUDED = {"K10": "grid book: empty signal table, no directional signal",
            "K21_B": "exact sign negation of K21_A on every decision group (merged)"}
RESEARCH_TOKENS = ("G3_LONG", "G3_SHORT", "LBR_FUND", "C1v2", "C4v2")
RESEARCH_FAMILY = {"G3_LONG": "G3", "G3_SHORT": "G3", "LBR_FUND": "LBR", "C1v2": "baseline", "C4v2": "baseline"}
VARIANTS_MERGED = {"B3_AXC0": "B3", "K04_AXC0": "K04", "C1_AX": "K01", "C1_FLIP_AX": "K01_FLIP"}   # + every <id>_AX


def clock() -> np.ndarray:
    return np.arange(CLOCK_START.value, CLOCK_END.value, STEP_NS, dtype=np.int64)


def catalog_tokens() -> list[str]:
    from btcusdt_quant.sim.strategies import CATALOG
    return [i for i in CATALOG if i not in EXCLUDED]


def tokens() -> list[str]:
    return catalog_tokens() + list(RESEARCH_TOKENS)


def family_of(tok: str) -> str:
    from btcusdt_quant.sim.strategies import CATALOG
    return RESEARCH_FAMILY[tok] if tok in RESEARCH_FAMILY else CATALOG[tok].family


def reconcile() -> dict:
    """Counts of every technique list in the repo and how each maps to tokens."""
    from btcusdt_quant.sim.strategies import CATALOG, STYLES
    from btcusdt_quant.paper import catalog as PC
    from . import u35
    expand = sum((2 if s.gate else 1) * (1 if s.simulator == "grid" else len(STYLES)) for s in CATALOG.values())
    return {"paper_toml_books": 32, "u35_universe": len(u35.UNIVERSE), "catalog_ids": len(CATALOG),
            "catalog_ids_pre_post_freeze": sum(not s.post_freeze for s in CATALOG.values()),
            "post_freeze_ids": [i for i, s in CATALOG.items() if s.post_freeze],
            "gate_x_style_expansion": expand, "paper_catalog_py_books": len(PC.BOOKS),
            "historical_108": "2026-10-07 paper_catalog: 29 ids x gate x NATIVE/DETEXIT (grid NATIVE only); retired "
                              "2026-10-09 by the R2-52A AX switch (memory #103 -> #116); not a current code list",
            "tokens": len(tokens()), "excluded": EXCLUDED, "variants_merged": VARIANTS_MERGED,
            "paper_book_to_token": {b: (u35.SPEC_ID[b] if b in u35.SPEC_ID else VARIANTS_MERGED.get(b, b))
                                    for b in u35.PAPER_BOOKS}}


# ---------------------------------------------------------------- per-token event streams
def _groups(tb: pd.DataFrame):
    tb = tb.sort_values("decision_time", kind="stable").reset_index(drop=True)
    dt = pd.DatetimeIndex(tb.decision_time).as_unit("ns").asi8
    first = np.r_[True, dt[1:] != dt[:-1]] if len(dt) else np.zeros(0, bool)
    gid = np.cumsum(first) - 1
    return tb, dt, first, gid


def market_events(tb: pd.DataFrame, ctx, e_head: str):
    """Decision groups -> (time, side of the first enterable row, strength E bps at T); exit-flag times."""
    from btcusdt_quant.sim import regime
    tb, dt, first, gid = _groups(tb)
    ok = tb.allow_entry.to_numpy(bool) & (tb.side.to_numpy() != 0)
    g_t = dt[first]
    side = np.zeros(len(g_t), np.int8)
    head = np.full(len(g_t), e_head, object)
    cand = np.flatnonzero(ok)
    pick = pd.Series(cand).groupby(gid[cand]).first()
    side[pick.index.to_numpy()] = tb.side.to_numpy()[pick.to_numpy()]
    if "e_head" in tb:
        head[pick.index.to_numpy()] = tb.e_head.to_numpy()[pick.to_numpy()]
    nz = side != 0
    st = np.full(len(g_t), np.nan)
    for hd in set(head[nz].tolist()):
        sel = nz & (head == hd)
        st[sel] = regime.e_bps(ctx.regime, pd.DatetimeIndex(g_t[sel], tz="UTC"), hd)
    xl = dt[tb.exit_long.to_numpy(bool)] if "exit_long" in tb else np.zeros(0, np.int64)
    xs = dt[tb.exit_short.to_numpy(bool)] if "exit_short" in tb else np.zeros(0, np.int64)
    return g_t[nz], side[nz], st[nz], np.unique(xl), np.unique(xs)


def oco_events(tb: pd.DataFrame, ctx, e_head: str, delay_min: int = 1):
    """OCO brackets -> trigger events: the first minute in [T + delay, T + delay + expiry) whose bar fills the upper
    (+1) or lower (-1) stop (sim.orders.fill_oco rule); known at that minute's close."""
    from btcusdt_quant.sim import regime
    t = ctx.minutes.open_time.array.asi8
    o, h, l = (ctx.minutes[c].to_numpy(float) for c in ("open", "high", "low"))
    tb = tb[tb.allow_entry.to_numpy(bool) & (tb.entry == "oco")].sort_values("decision_time", kind="stable")
    dt = pd.DatetimeIndex(tb.decision_time).as_unit("ns").asi8
    up, lo_, ex = tb.upper.to_numpy(float), tb.lower.to_numpy(float), tb.expiry_min.to_numpy(int)
    k0 = np.searchsorted(t, dt + delay_min * MIN_NS)
    ev_t, ev_s, ev_e = [], [], []
    e = regime.e_bps(ctx.regime, pd.DatetimeIndex(dt, tz="UTC"), e_head) if len(dt) else np.zeros(0)
    for r in range(len(dt)):
        a, b = int(k0[r]), min(int(k0[r]) + int(ex[r]), len(t))
        if a >= b or not (np.isfinite(up[r]) and np.isfinite(lo_[r])):
            continue
        hu = (o[a:b] >= up[r]) | (h[a:b] >= up[r])
        hd = (o[a:b] <= lo_[r]) | (l[a:b] <= lo_[r])
        hit = np.flatnonzero(hu | hd)
        if not len(hit):
            continue
        k = a + int(hit[0])
        if hu[hit[0]] and hd[hit[0]]:
            s = 1 if abs(up[r] - o[k]) < abs(o[k] - lo_[r]) else -1
        else:
            s = 1 if hu[hit[0]] else -1
        ev_t.append(t[k] + MIN_NS)
        ev_s.append(s)
        ev_e.append(e[r])
    order = np.argsort(np.asarray(ev_t, np.int64), kind="stable")
    T = np.asarray(ev_t, np.int64)[order]
    keep = np.r_[True, T[1:] != T[:-1]] if len(T) else np.zeros(0, bool)      # one event per minute (first row)
    return (T[keep], np.asarray(ev_s, np.int8)[order][keep], np.asarray(ev_e, float)[order][keep],
            np.zeros(0, np.int64), np.zeros(0, np.int64))


def token_state(clk: np.ndarray, ev_t, ev_side, ev_strength, xl, xs, hold_min: int) -> dict:
    """Latest event at or before t (events stamped with the time they are known). Active while age < hold
    (hold 0 = until an exit flag or the next event) and no exit flag of that side since the event."""
    j = np.searchsorted(ev_t, clk, "right") - 1
    has = j >= 0
    jj = np.maximum(j, 0)
    side = np.where(has, ev_side[jj] if len(ev_t) else 0, 0).astype(np.int8)
    age = np.where(has, (clk - (ev_t[jj] if len(ev_t) else 0)) / MIN_NS, np.nan)
    active = has & (side != 0)
    if hold_min > 0:
        active &= age < hold_min
    for x, sd in ((xl, 1), (xs, -1)):
        if len(x):
            lx = np.searchsorted(x, clk, "right") - 1
            last = np.where(lx >= 0, x[np.maximum(lx, 0)], np.iinfo(np.int64).min)
            active &= ~((side == sd) & (last > (ev_t[jj] if len(ev_t) else 0)))
    strength = np.where(active, ev_strength[jj] if len(ev_t) else np.nan, np.nan)
    return {"side": np.where(active, side, 0).astype(np.int8), "active": active.astype(np.int8),
            "strength": strength.astype(np.float32), "strength_avail": np.isfinite(strength).astype(np.int8),
            "age_min": np.where(active, age, np.nan).astype(np.float32)}


def timeline_state(clk: np.ndarray, tl: pd.DataFrame) -> dict:
    """Research grid timeline (rows at change points; available_time = minute + 1 m) as of t."""
    at = tl.available_time.to_numpy(np.int64)
    j = np.searchsorted(at, clk, "right") - 1
    has = j >= 0
    jj = np.maximum(j, 0)
    av = has & tl.available.to_numpy(bool)[jj]
    act = av & tl.signal_active.to_numpy(bool)[jj] & (tl.base_side.to_numpy()[jj] != 0)
    side = np.where(act, tl.base_side.to_numpy()[jj], 0).astype(np.int8)
    w = np.where(act, tl.base_weight.to_numpy(float)[jj], np.nan)
    sv = np.where(act, tl.base_side.to_numpy()[jj], 0)
    chg = np.r_[True, sv[1:] != sv[:-1]]
    start = np.maximum.accumulate(np.where(chg, np.arange(len(clk)), 0))
    age = np.where(act, (clk - clk[start]) / MIN_NS, np.nan)
    return {"side": side, "active": act.astype(np.int8), "strength": w.astype(np.float32),
            "strength_avail": np.isfinite(w).astype(np.int8), "age_min": age.astype(np.float32),
            "available": av.astype(np.int8)}


def close_at(clk: np.ndarray, t_min: np.ndarray, c: np.ndarray) -> np.ndarray:
    """C(t) = close of the minute ending at t (open_time t - 1 m)."""
    k = np.searchsorted(t_min, clk - MIN_NS)
    ok = (k < len(t_min)) & (t_min[np.minimum(k, len(t_min) - 1)] == clk - MIN_NS)
    return np.where(ok, c[np.minimum(k, len(c) - 1)], np.nan)


@numba.njit(cache=True)
def _ewma(x, a):
    n = len(x)
    mean, hit, vol, cnt = (np.full(n, np.nan, np.float32), np.full(n, np.nan, np.float32),
                           np.full(n, np.nan, np.float32), np.zeros(n, np.float32))
    W = M1 = M2 = HT = 0.0
    for k in range(n):
        W, M1, M2, HT = W * a, M1 * a, M2 * a, HT * a
        v = x[k]
        if v == v:
            W += 1.0
            M1 += v
            M2 += v * v
            HT += 1.0 if v > 0 else 0.0
        if W > 0:
            m = M1 / W
            mean[k], hit[k], cnt[k] = m, HT / W, W
            vol[k] = np.sqrt(max(M2 / W - m * m, 0.0))
    return mean, hit, vol, cnt


def markouts(side: np.ndarray, C: np.ndarray) -> dict:
    """EWMA (30-day half-life on the 5-minute clock) of matured markouts per horizon: mean / hit / vol / count."""
    n = len(side)
    a = 2.0 ** (-(STEP_NS / MIN_NS) / EWMA_HALF_LIFE_MIN)
    out = {}
    for hm in HORIZONS:
        lag = hm * MIN_NS // STEP_NS
        x = np.full(n, np.nan)
        s0 = side[:-lag].astype(float)
        ret = (C[lag:] / C[:-lag] - 1.0) * 1e4
        mk = s0 * ret - COST_BPS
        valid = (s0 != 0) & np.isfinite(ret)
        x[lag:] = np.where(valid, mk, np.nan)
        mean, hit, vol, cnt = _ewma(x, a)
        out.update({f"mk{hm}_mean": mean, f"mk{hm}_hit": hit, f"mk{hm}_vol": vol, f"mk{hm}_count": cnt})
    return out
