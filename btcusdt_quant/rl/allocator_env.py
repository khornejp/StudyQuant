"""RL allocator environment (Codex design 2026-10-10 section 1/3/4/8 step 4; Codex round-2 env contract).

One env = one execution cell, decisions every `cadence_h` hours (1h primary, 4h ablation) on the frozen canonical
shadow schedule of the 7 sleeves:
  * entry head: a standing level in LEVELS for canonical opportunities whose decision time falls in [T, T + cadence).
    It is legal only for sleeves available at T (state row T); a sleeve unavailable at T is OFF for the whole interval
    even if it becomes available inside it (e.g. C4 available from 2020-10-01 00:00 minute, first allocator interval
    2020-10-01 01:00). Independently, an opportunity whose sleeve is unavailable at its own decision minute gets 0.
  * pending head KEEP/CANCEL for allocated, not yet filled opportunities; open head HOLD/EXIT (+TIGHTEN_75/50 for
    B3/K04: R_t = min(R_t, f x R0), never wider). Allocation is fixed from entry to exit; skipped or early-exited
    opportunities never re-enter (only canonical opportunities exist).
  * gross cap 2.0: open/pending allocated exposure first, simultaneous new decisions scaled pro rata
    (allocator_contracts.project_cap); long and short sleeves are separate virtual books (no netting).
  * episodes start flat (canonical positions open/pending at the start stay unallocated); at the end every allocated
    open position is marked and charged its exit fee.
  * reward (design section 3) against a static-weight book run on the same data; identical actions give exactly 0.
    Turnover unit: bps = 2 bps x traded notional (multiplier x base weight per entry leg and per exit leg, terminal
    exit included). The static book takes any weights in [0, 1] (sum <= 2); RL actions only LEVELS, so an off-grid
    static comparator (e.g. equal 2/7) is a reward baseline only, never reproducible by RL actions.
  * caps: gross_open = open allocated exposure; gross_reserved = open + pending (bounded by 2.0 by the projector).
P&L comes only from the precomputed canonical minute rows (sleeve_precompute) and, for modified trades, from the same
ledger functions (lin_trade / log_trade / exit_fill), so the env minute ledger equals a slow replay.
"""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np, pandas as pd
from . import allocator_contracts as C
from . import allocator_state as ast
from . import sleeve_precompute as sp

MIN, HOUR = sp.MIN, ast.HOUR
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out/rl_allocator_20261010"


# ================================================================ data
@dataclass
class SleeveData:
    """Canonical opportunities (index = entry_opportunity_id) and their unit-allocation minute rows."""
    name: str
    kind: str
    pen: float
    dec_idx: np.ndarray          # decision minute index (opportunity time)
    side: np.ndarray
    w: np.ndarray                # base weight (exposure per unit multiplier)
    avail: np.ndarray            # sleeve available at the opportunity's own decision minute
    e: np.ndarray                # entry fill minute (-1 unfilled)
    x: np.ndarray                # canonical last row minute (exit fill / terminal mark)
    xdec: np.ndarray             # lin: canonical exit decision bar (hi when open at end); log: unused
    open_at_end: np.ndarray
    px_in: np.ndarray
    expiry: np.ndarray           # last minute an unfilled order rests
    fund: list                   # per opportunity (ft, fr) arrays
    row_off: np.ndarray          # rows of opportunity k: [row_off[k], row_off[k+1])
    row_min: np.ndarray
    row_cs: np.ndarray           # cumulative net4 within the concatenated rows (leading 0 per opportunity)
    R0: np.ndarray | None = None
    k: np.ndarray | None = None
    R_t: np.ndarray | None = None        # per minute (grid, end-of-minute R)
    armed: np.ndarray | None = None      # per minute (grid, end-of-minute)

    @property
    def n(self) -> int:
        return len(self.dec_idx)

    def rows_sum(self, k: int, a: int, b: int) -> float:
        """Canonical unit net4 of opportunity k over minutes [a, b)."""
        lo, hi = self.row_off[k], self.row_off[k + 1]
        m = self.row_min[lo:hi]
        i, j = np.searchsorted(m, a), np.searchsorted(m, b)
        return float(self.row_cs[lo + k + j] - self.row_cs[lo + k + i])


def build_sleeve(name: str, pen: float, dec: pd.DataFrame, outc: pd.DataFrame, ledger: pd.DataFrame,
                 grid_avail: np.ndarray, t: np.ndarray, fund: dict, grid_R=None, grid_armed=None) -> SleeveData:
    """From the precompute decisions / private outcomes / ledger tables (env-internal use of outcomes)."""
    dec = dec.sort_values("entry_opportunity_id").reset_index(drop=True)
    outc = outc.sort_values("entry_opportunity_id").reset_index(drop=True)
    if not np.array_equal(dec.entry_opportunity_id.to_numpy(), np.arange(len(dec))) or \
            not np.array_equal(outc.entry_opportunity_id.to_numpy(), np.arange(len(dec))):
        raise ValueError(f"{name}: opportunity ids not contiguous")
    n = len(dec)
    kind = C.KIND[name]
    dec_idx = np.searchsorted(t, dec.decision_time.to_numpy(np.int64))
    filled = outc.filled.to_numpy(bool)
    e = np.where(filled, outc.entry_idx.to_numpy(float), -1).astype(np.int64)
    N = len(t)
    oae = outc.open_at_end.to_numpy(bool) if "open_at_end" in outc else np.zeros(n, bool)
    xi = outc.exit_idx.to_numpy(float)
    x = np.where(filled, np.where(oae, N - 1, xi), -1).astype(np.int64)
    xdec = (np.where(oae, N, outc.exit_decision_idx.to_numpy(float)).astype(np.int64)
            if "exit_decision_idx" in outc else np.full(n, -1, np.int64))
    seg = dec.segment.astype(str).to_numpy()
    fl = [fund[sg] for sg in seg]
    # canonical rows per opportunity (ledger is per (minute, opportunity))
    lo = ledger.entry_opportunity_id.to_numpy(np.int64)
    order = np.lexsort((ledger.minute_idx.to_numpy(np.int64), lo))
    lo = lo[order]
    mins = ledger.minute_idx.to_numpy(np.int64)[order]
    net = ledger.net4.to_numpy(float)[order]
    off = np.searchsorted(lo, np.arange(n + 1))
    cs = np.zeros(len(net) + n)                              # per-opportunity leading zero
    for k in range(n):
        a, b = off[k], off[k + 1]
        cs[a + k + 1:b + k + 1] = np.cumsum(net[a:b])
    sd = SleeveData(name=name, kind=kind, pen=pen, dec_idx=dec_idx, side=dec.side.to_numpy(int),
                    w=dec.base_weight.to_numpy(float), avail=grid_avail[np.minimum(dec_idx, N - 1)].astype(bool),
                    e=e, x=x, xdec=xdec, open_at_end=oae, px_in=outc.entry_px.to_numpy(float),
                    expiry=np.where(filled, e - 1, np.minimum(dec_idx + 59, N - 1)), fund=fl,
                    row_off=off, row_min=mins, row_cs=cs)
    if name in C.TIGHTEN_SLEEVES:
        sd.R0 = np.minimum(outc.k.to_numpy(float) * outc.e0.to_numpy(float), 300.0)
        sd.k = outc.k.to_numpy(float)
        sd.R_t, sd.armed = np.asarray(grid_R, float), np.asarray(grid_armed, float)
    return sd


@dataclass
class CellData:
    cell: str
    t: np.ndarray
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    sleeves: dict
    T1h: np.ndarray                  # 1h state decision times (sorted)
    static: np.ndarray               # [len(T1h), N_STATIC] normalized observation vectors
    seq_raw: pd.DataFrame            # T, exec_cell, SEQ_COLUMNS (raw) for history()
    seq_norm: dict                   # col -> (median, scale)
    avail_T: np.ndarray              # [len(T1h), 7] sleeve availability seen at T
    feature_order: list

    @property
    def logc(self) -> np.ndarray:
        if getattr(self, "_logc", None) is None:
            self._logc = np.log(self.c)
        return self._logc

    def mk(self) -> dict:
        return {"t": self.t, "o": self.o, "h": self.h, "l": self.l, "c": self.c}


# ================================================================ trade modifications
def lin_exit_change(cd: CellData, sd: SleeveData, k: int, x: int, cur_end: int):
    """Early exit request at minute x for a lin trade: (exit minute, exit px) or None (canonical exits first)."""
    if not (sd.e[k] <= x - 1 < sd.xdec[k]) or x - 1 >= cur_end:
        return None
    j, px = sp.exit_fill(cd.o, cd.h, cd.l, cd.c, x - 1, int(sd.side[k]), len(cd.t), sd.pen)
    if j < 0 or j > cur_end:
        return None
    return j, px


def tighten_exit(cd: CellData, sd: SleeveData, k: int, x0: int, f: float, cur_end: int):
    """R2-52A stop with R_t' = min(R_t, f x R0) from minute x0: first trigger in [x0, cur_end) -> (minute, px)."""
    s, e, px = int(sd.side[k]), int(sd.e[k]), float(sd.px_in[k])
    if x0 >= cur_end or x0 <= e:
        return None
    rng = np.arange(x0, cur_end)
    R = np.minimum(sd.R_t[rng], f * sd.R0[k])
    hl = cd.h[e:cur_end] if s == 1 else cd.l[e:cur_end]
    best_end = (np.maximum.accumulate(np.r_[px, hl]) if s == 1 else np.minimum.accumulate(np.r_[px, hl]))[1:]
    best_prev = best_end[rng - 1 - e]                      # best through the previous minute
    armed_prev = sd.armed[rng - 1]
    hard = px * np.exp(-s * R / 1e4)
    trail = best_prev * np.exp(-s * 0.5 * R / 1e4)
    lvl = np.where((armed_prev == 1) & (s * (trail - hard) > 0), trail, hard)
    o, lo_hi = cd.o[rng], (cd.l[rng] if s == 1 else cd.h[rng])
    gap = (o <= lvl) if s == 1 else (o >= lvl)
    touch = (lo_hi <= lvl) if s == 1 else (lo_hi >= lvl)
    hit = np.flatnonzero(gap | touch)
    if not len(hit):
        return None
    q = hit[0]
    return int(rng[q]), float(o[q] if gap[q] else lvl[q])


def trade_rows(cd: CellData, sd: SleeveData, k: int, j: int, px: float):
    """Rows of trade k with exit fill at minute j / price px (same ledger functions as the precompute)."""
    ft, fr = sd.fund[k]
    if sd.kind == "lin":
        r = sp.lin_trade(cd.t, cd.c, k, int(sd.side[k]), float(sd.w[k]), int(sd.e[k]), float(sd.px_in[k]), True, j,
                         px, len(cd.t), ft, fr)
    else:
        r = sp.log_trade(cd.t, cd.logc, k, int(sd.side[k]), 1.0,
                         int(sd.e[k]), j, float(sd.px_in[k]), px, C.FEE_SIDE_BPS, int(cd.t[sd.e[k]]), int(cd.t[j]),
                         ft, fr)
    net = r["gross"] + r["fee"] + r["funding"]
    return r["minute"], np.r_[0.0, np.cumsum(net)]


# ================================================================ book
@dataclass
class Book:
    """Allocations of one policy (RL or static) over one episode."""
    mult: list = field(default_factory=list)                 # per sleeve: {opp: multiplier}
    end: list = field(default_factory=list)                  # per sleeve: {opp: current last row minute}
    mod: list = field(default_factory=list)                  # per sleeve: {opp: (minutes, cs)}
    tf: list = field(default_factory=list)                   # per sleeve: {opp: tighten fraction}
    events: list = field(default_factory=list)               # (sleeve, opp, action, minute, value)
    active: list = field(default_factory=list)               # per sleeve: allocated opps not yet finished
    effects: dict = field(default_factory=dict)              # action -> count of requests that changed a position
    equity: float = 0.0
    peak: float = 0.0
    mdd: float = 0.0

    @staticmethod
    def new() -> "Book":
        n = len(C.SLEEVES)
        return Book(mult=[{} for _ in range(n)], end=[{} for _ in range(n)], mod=[{} for _ in range(n)],
                    tf=[{} for _ in range(n)], active=[set() for _ in range(n)])


class AllocatorEnv:
    def __init__(self, data: CellData, cadence_h: int = 1, static_weights=None, inherit_open=False,
                 terminal_fee: bool = True, record_minutes: bool = False):
        if cadence_h not in (1, 4):
            raise ValueError("cadence 1h or 4h")
        self.d = data
        self.cad = cadence_h
        self.static_w = C.validate_static_weights(static_weights)
        self.inherit, self.terminal_fee, self.record = inherit_open, terminal_fee, record_minutes
        self.sd = [data.sleeves[s] for s in C.SLEEVES]
        # all opportunities ordered by decision minute
        di = [(sd.dec_idx[k], si, k) for si, sd in enumerate(self.sd) for k in range(sd.n)]
        di.sort()
        self.opp_min = np.array([x[0] for x in di], np.int64)
        self.opp_sk = np.array([(x[1], x[2]) for x in di], np.int64).reshape(-1, 2)

    # ---------------------------------------------------------------- episode
    def reset(self, start_T: int, end_T: int):
        d = self.d
        step = self.cad * HOUR
        if start_T % step or end_T % step or end_T <= start_T:
            raise ValueError("episode bounds must be on the cadence grid")
        self.Ts = np.arange((end_T - start_T) // step + 1, dtype=np.int64) * step + start_T
        ti = np.searchsorted(d.T1h, self.Ts[:-1])
        if np.any(ti >= len(d.T1h)) or np.any(d.T1h[np.minimum(ti, len(d.T1h) - 1)] != self.Ts[:-1]):
            raise ValueError("episode decision time missing from the state store")
        self.ti = ti
        self.mi = np.searchsorted(d.t, self.Ts)                # minute index of each T (first minute after T)
        q = pd.DataFrame({"T": self.Ts[:-1], "exec_cell": d.cell})
        cols = list(C.SEQ_COLUMNS) + ["__one"]
        h = ast.history(d.seq_raw, cols, C.SEQ_LEN, query=q, boundaries=[start_T])   # 32 x 1h, no pre-start rows
        self.pad = np.isnan(h[:, :, -1])
        raw = h[:, :, :-1]
        nan = np.isnan(raw)
        med = np.array([d.seq_norm[c][0] for c in C.SEQ_COLUMNS], np.float32)
        scl = np.array([d.seq_norm[c][1] for c in C.SEQ_COLUMNS], np.float32)
        self.seq = np.clip(np.where(nan, 0.0, (raw - med) / scl), -10, 10).astype(np.float32)
        self.seq_nan = (nan & ~self.pad[:, :, None]).astype(np.float32)
        self.k = 0
        self.rl, self.st = Book.new(), Book.new()
        self.minutes = {"rl": np.zeros(self.mi[-1] - self.mi[0]), "st": np.zeros(self.mi[-1] - self.mi[0])} \
            if self.record else None
        if self.inherit:                                       # parity mode only: adopt canonical positions at 1.0
            a = self.mi[0]
            keep = C.SLEEVES if self.inherit is True else tuple(self.inherit)
            for si, sd in enumerate(self.sd):
                if C.SLEEVES[si] not in keep:
                    continue
                for k in np.flatnonzero((sd.dec_idx < a) & (np.maximum(sd.x, sd.expiry) >= a)):
                    for b in (self.rl, self.st):
                        b.mult[si][int(k)] = 1.0
                        b.end[si][int(k)] = int(sd.x[k]) if sd.e[k] >= 0 else int(sd.expiry[k])
                        b.active[si].add(int(k))
        return self.observation()

    # ---------------------------------------------------------------- observation / masks
    def _state(self, book: Book, si: int, T_idx: int):
        sd = self.sd[si]
        pend, opn = [], []
        for k in sorted(book.active[si]):
            if book.mult[si][k] <= 0:
                continue
            if sd.e[k] >= 0 and sd.e[k] < T_idx <= book.end[si][k]:
                opn.append(k)
            elif sd.dec_idx[k] < T_idx and ((sd.e[k] >= T_idx) or (sd.e[k] < 0 and sd.expiry[k] >= T_idx)):
                pend.append(k)
        return pend, opn

    def masks(self, book: Book | None = None) -> C.Masks:
        book = self.rl if book is None else book
        T_idx = self.mi[self.k]
        av = self.d.avail_T[self.ti[self.k]]
        m = C.Masks()
        for si, s in enumerate(C.SLEEVES):
            pend, opn = self._state(book, si, T_idx)
            f = min([book.tf[si].get(k, 1.0) for k in opn], default=1.0)
            m.entry[si], m.pending[si], m.open[si] = C.sleeve_masks(bool(av[si]), bool(pend), bool(opn), s, f)
        return m

    def observation(self) -> dict:
        d, k = self.d, self.k
        T_idx = self.mi[k]
        acc = np.zeros((len(C.SLEEVES), len(C.ACCOUNT_CHANNELS)), np.float32)
        for si in range(len(C.SLEEVES)):
            pend, opn = self._state(self.rl, si, T_idx)
            sd = self.sd[si]
            acc[si, 0] = sum(self.rl.mult[si][q] for q in opn)
            acc[si, 1] = sum(self.rl.mult[si][q] * sd.w[q] for q in opn + pend)
            acc[si, 2] = float(bool(pend))
            acc[si, 3] = min([self.rl.tf[si].get(q, 1.0) for q in opn], default=1.0)
        obs = {"static": d.static[self.ti[k]], "seq": self.seq[k], "seq_nan": self.seq_nan[k],
               "seq_pad": self.pad[k].astype(np.float32), "account": acc.ravel(), "T": int(self.Ts[k])}
        obs["masks"] = self.masks()
        return obs

    # ---------------------------------------------------------------- dynamics
    def _apply_heads(self, book: Book, action: C.Action, a: int):
        for si, s in enumerate(C.SLEEVES):
            sd = self.sd[si]
            pend, opn = self._state(book, si, a)
            if C.PENDING_ACTIONS[action.pending[si]] == "CANCEL":
                for q in pend:
                    book.effects["CANCEL"] = book.effects.get("CANCEL", 0) + 1
                    book.mult[si][q] = 0.0
                    book.events.append((si, q, "CANCEL", a, 0.0))
            op = C.OPEN_ACTIONS[action.open[si]]
            for q in opn:
                end = book.end[si][q]
                if op == "EXIT":
                    ch = (lin_exit_change(self.d, sd, q, a, end) if sd.kind == "lin"
                          else ((a, float(self.d.o[a])) if sd.e[q] < a <= end else None))
                    book.events.append((si, q, "EXIT", a, 0.0))
                elif op in C.TIGHTEN_F:
                    f = C.TIGHTEN_F[op]
                    if f >= book.tf[si].get(q, 1.0):
                        continue                               # no widening (masked anyway)
                    book.tf[si][q] = f
                    ch = tighten_exit(self.d, sd, q, a, f, end)
                    book.events.append((si, q, op, a, f))
                else:
                    continue
                if ch is not None:
                    book.effects[op] = book.effects.get(op, 0) + 1
                    j, px = ch
                    book.mod[si][q] = trade_rows(self.d, sd, q, j, px)
                    book.end[si][q] = j

    def _entries(self, book: Book, levels: np.ndarray, a: int, b: int):
        lo, hi = np.searchsorted(self.opp_min, a), np.searchsorted(self.opp_min, b)
        k = lo
        while k < hi:
            tau = self.opp_min[k]
            g = k
            while g < hi and self.opp_min[g] == tau:
                g += 1
            grp = self.opp_sk[k:g]
            req = np.array([levels[si] * self.sd[si].w[q] if self.sd[si].avail[q] else 0.0 for si, q in grp])
            gross = 0.0
            for si in range(len(C.SLEEVES)):
                sd = self.sd[si]
                for q in book.active[si]:
                    m = book.mult[si][q]
                    if m > 0 and sd.dec_idx[q] < tau and C.reserved_at(sd.e[q], book.end[si][q], sd.expiry[q], tau):
                        gross += m * sd.w[q]
            scale = C.project_cap(gross, req)
            for (si, q), r, sc in zip(grp, req, scale):
                si, q = int(si), int(q)
                m = (r / self.sd[si].w[q]) * sc if r > 0 else 0.0
                if m > 0:
                    book.mult[si][q] = m
                    book.end[si][q] = int(self.sd[si].x[q]) if self.sd[si].e[q] >= 0 else int(self.sd[si].expiry[q])
                    book.active[si].add(q)
            k = g

    def _pnl(self, book: Book, a: int, b: int, last: bool, tag: str):
        net, legs = 0.0, 0.0
        for si in range(len(C.SLEEVES)):
            sd = self.sd[si]
            done = []
            for q in book.active[si]:
                m = book.mult[si][q]
                end = book.end[si][q]
                if end < b:
                    done.append(q)
                if m <= 0 or sd.e[q] < 0:
                    continue
                if end < a or sd.e[q] >= b:
                    continue
                if q in book.mod[si]:
                    mins, cs = book.mod[si][q]
                    i, j = np.searchsorted(mins, a), np.searchsorted(mins, b)
                    v = cs[j] - cs[i]
                    if self.record:
                        self._rec(tag, mins[i:j], np.diff(cs)[i:j] * m, a)
                else:
                    v = sd.rows_sum(q, a, b)
                    if self.record:
                        lo, hi = sd.row_off[q], sd.row_off[q + 1]
                        mm = sd.row_min[lo:hi]
                        i, j = np.searchsorted(mm, a), np.searchsorted(mm, b)
                        self._rec(tag, mm[i:j], np.diff(sd.row_cs[lo + q:hi + q + 1])[i:j] * m, a)
                net += m * v
                if a <= sd.e[q] < b:
                    legs += m * sd.w[q]
                if a <= end < b:
                    legs += m * sd.w[q]
                if last and self.terminal_fee and end >= b:
                    fee = -2.0 * sd.w[q] if sd.kind == "lin" else -C.FEE_SIDE_BPS
                    net += m * fee
                    legs += m * sd.w[q]
                    if self.record:
                        self._rec(tag, np.array([b - 1]), np.array([m * fee]), a)
            book.active[si].difference_update(done)
        return net, legs * C.FEE_SIDE_BPS

    def _rec(self, tag, mins, vals, a):
        np.add.at(self.minutes[tag], mins - self.mi[0], vals)

    def step(self, action: C.Action):
        m = self.masks()
        C.validate_action(action, m)
        a, b = int(self.mi[self.k]), int(self.mi[self.k + 1])
        last = self.k + 1 == len(self.Ts) - 1
        lv_rl = np.array([C.LEVELS[i] for i in action.entry])
        av = self.d.avail_T[self.ti[self.k]]
        lv_st = np.where(av, self.static_w, 0.0)               # static book: frozen weights, HOLD/KEEP
        sa = C.Action.hold()
        out = {}
        for tag, book, act, lv in (("rl", self.rl, action, lv_rl), ("st", self.st, sa, lv_st)):
            self._apply_heads(book, act, a)
            self._entries(book, lv, a, b)
            net, to = self._pnl(book, a, b, last, tag)
            book.equity += net
            book.peak = max(book.peak, book.equity)
            mdd = max(book.mdd, book.peak - book.equity)
            out[tag] = (net, mdd - book.mdd, to)
            book.mdd = mdd
        r = C.step_reward(out["rl"][0], out["st"][0], out["rl"][1], out["st"][1], out["rl"][2], out["st"][2])
        self.k += 1
        done = self.k == len(self.Ts) - 1
        info = {"net_rl": out["rl"][0], "net_st": out["st"][0], "dmdd_rl": out["rl"][1], "dmdd_st": out["st"][1],
                "turnover_rl": out["rl"][2], "turnover_st": out["st"][2], "gross": self.gross(self.rl, b),
                "gross_open": self.gross(self.rl, b), "gross_reserved": self.gross_reserved(self.rl, b),
                "net_exposure": self.net_exposure(self.rl, b)}
        return (None if done else self.observation()), r, done, info

    def gross(self, book: Book, idx: int) -> float:
        g = 0.0
        for si, sd in enumerate(self.sd):
            for q in book.active[si]:
                m = book.mult[si][q]
                if m > 0 and sd.e[q] >= 0 and sd.e[q] < idx <= book.end[si][q]:
                    g += m * sd.w[q]
        return g

    def gross_reserved(self, book: Book, idx: int) -> float:
        """Open + pending allocated exposure at the start of minute idx (the quantity the cap projector bounds)."""
        g = 0.0
        for si, sd in enumerate(self.sd):
            for q in book.active[si]:
                m = book.mult[si][q]
                if m > 0 and sd.dec_idx[q] < idx and C.reserved_at(sd.e[q], book.end[si][q], sd.expiry[q], idx):
                    g += m * sd.w[q]
        return g

    def net_exposure(self, book: Book, idx: int) -> float:
        g = 0.0
        for si, sd in enumerate(self.sd):
            for q in book.active[si]:
                m = book.mult[si][q]
                if m > 0 and sd.e[q] >= 0 and sd.e[q] < idx <= book.end[si][q]:
                    g += m * sd.w[q] * sd.side[q]
        return g


# ================================================================ loading (fail closed)
def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


class SchemaError(RuntimeError):
    pass


def _read_cols(directory: Path, stem: str, allow_test: bool, tcol: str, years, columns) -> pd.DataFrame:
    """sleeve_precompute.read_partitioned with a column subset (same TEST guard: partition year, then row times)."""
    if columns is None:
        return sp.read_partitioned(directory, stem, allow_test=allow_test, time_col=tcol, years=years)
    out = []
    for f in sorted(Path(directory).glob(f"{stem}_*.parquet")):
        y = int(f.stem.rsplit("_", 1)[1])
        if y not in years:
            continue
        if y >= sp.TEST_START.year and not allow_test:
            raise sp.TestAccessError(f"{f.name}: TEST partition read without allow_test=True")
        out.append(pd.read_parquet(f, columns=columns))
    frame = pd.concat(out, ignore_index=True)
    sp.guard_times(frame[tcol], allow_test, str(directory))
    return frame


def load_cell(cell: str, cadence_h: int = 1, fold: str = "F1", allow_test: bool = False, root: Path = OUT,
              verify_hashes: bool = True) -> CellData:
    """Load one execution cell; any hash / schema / feature-order mismatch raises SchemaError (fail closed)."""
    pre, st = root / "precompute", root / "state"
    prov = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    sm_path = st / "manifest.json"
    smf = json.loads(sm_path.read_text(encoding="utf-8"))
    r2 = prov["round2"]["state"]
    if _sha(sm_path) != r2["sha256"] or _sha(st / "normalizers.json") != r2["normalizers_sha256"]:
        raise SchemaError("state manifest / normalizers hash != provenance")
    pm_path = pre / "manifest.json"
    if _sha(pm_path) != smf["precompute_manifest_sha256"]:
        raise SchemaError("precompute manifest hash != state manifest")
    pm = json.loads(pm_path.read_text(encoding="utf-8"))
    if list(C.SEQ_COLUMNS) != smf["seq_columns"]:
        raise SchemaError("SEQ_COLUMNS contract != state manifest")
    norms = json.loads((st / "normalizers.json").read_text(encoding="utf-8"))[f"{cadence_h}h"]
    order = norms["feature_order"]
    norm = {k: tuple(v) for k, v in norms[fold].items()}
    if len(order) != C.N_STATIC or order != ast.feature_order(smf["columns"], norm):
        raise SchemaError("feature-order contract violated")
    names = ["state_1h.parquet"] + (["state_1h_TEST.parquet"] if allow_test else [])
    if allow_test:
        sp.require_unlock(True, "TEST state")
    for nm in names:                                          # verify bytes before reading
        if nm not in smf["files"] or _sha(st / nm) != smf["files"][nm]["sha256"]:
            raise SchemaError(f"state file hash mismatch {nm}")
    frames = [pd.read_parquet(st / nm) for nm in names]
    sf = pd.concat(frames, ignore_index=True)
    if list(sf.columns) != smf["columns"]:
        raise SchemaError("state columns != manifest")
    sf = sf[sf.exec_cell == cell].sort_values("T").reset_index(drop=True)
    sp.guard_times(sf["T"].to_numpy(np.int64), allow_test, "state")
    static = ast.apply_normalizer(sf, norm, order)[order].to_numpy(np.float32)
    if static.shape[1] != C.N_STATIC or not np.isfinite(static).all():
        raise SchemaError("static observation not finite / wrong width")
    seq_raw = sf[["T", "exec_cell"] + list(C.SEQ_COLUMNS)].assign(__one=1.0)
    avail_T = sf[[f"{s}_available" for s in C.SLEEVES]].to_numpy() == 1
    files = pm["files"]
    years = set(range(2020, (2026 if allow_test else 2025) + 1))

    def part(rel: str, stem: str, tcol: str = "minute_time", key: str | None = None, columns=None) -> pd.DataFrame:
        entry = files[key or rel]
        entry = entry.get(stem, entry)
        yr = lambda nm: int(nm[:-len(".parquet")].rsplit("_", 1)[1])  # noqa: E731
        expect = {nm for nm in entry if nm.startswith(stem + "_") and yr(nm) in years}
        actual = {p.name for p in (pre / rel).glob(f"{stem}_*.parquet") if yr(p.name) in years}
        if expect != actual:                                   # missing or extra partition -> fail closed
            raise SchemaError(f"partition set mismatch {rel}/{stem}: missing {sorted(expect - actual)} "
                              f"extra {sorted(actual - expect)}")
        if verify_hashes:
            for nm in sorted(expect):
                if entry[nm]["sha256"] != _sha(pre / rel / nm):
                    raise SchemaError(f"hash mismatch {rel}/{nm}")
        return _read_cols(pre / rel, stem, allow_test, tcol, years, columns)

    mk = part("common/market", "market")
    t = mk.minute_time.to_numpy(np.int64)
    funds = {}
    for nm in ("funding_g3", "funding_c", "funding_ax_NATIVE", "funding_ax_TEST"):
        f = part("common/funding", nm, key=f"common/{nm}")
        funds[nm] = (f.minute_time.to_numpy(np.int64), f.rate.to_numpy(float))
    sleeves = {}
    for s in C.SLEEVES:
        rel = f"g3_family/{cell}/{s}" if s in C.G3_FAMILY else f"common/{s}"
        g = part(rel, "grid", columns=["minute_time", "available", "R_t_bps", "trail_armed"])
        if not np.array_equal(g.minute_time.to_numpy(np.int64), t):
            raise SchemaError(f"{s} grid minutes != market")
        dec = part(rel, "decisions", "decision_time")
        out = part(rel, "outcomes", "decision_time")
        led = part(rel, "ledger")
        fmap = ({"ALL": funds["funding_g3"]} if s in C.G3_FAMILY else {"ALL": funds["funding_c"]}
                if s.startswith("C") else {"NATIVE": funds["funding_ax_NATIVE"], "TEST": funds["funding_ax_TEST"]})
        sleeves[s] = build_sleeve(s, C.CELL_PEN[cell], dec, out, led, g.available.to_numpy(bool), t, fmap,
                                  g.R_t_bps.to_numpy(float), g.trail_armed.to_numpy(float))
    seq_norm = {c: norm[c] for c in C.SEQ_COLUMNS}
    return CellData(cell=cell, t=t, o=mk.o.to_numpy(float), h=mk.h.to_numpy(float), l=mk.l.to_numpy(float),
                    c=mk.c.to_numpy(float), sleeves=sleeves, T1h=sf["T"].to_numpy(np.int64), static=static,
                    seq_raw=seq_raw, seq_norm=seq_norm, avail_T=avail_T, feature_order=order)
