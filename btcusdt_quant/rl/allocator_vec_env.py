"""Vectorized batch of allocator envs (Codex Step 4 review B): N independent episodes of equal length on one execution
cell, numpy over envs x opportunities, no per-minute Python loop. Semantics are those of allocator_env.AllocatorEnv
(same masks, heads, cap projector, P&L, reward); parity is tested step by step against the scalar env.

Exactness: canonical opportunity rows are consecutive minutes, so a window sum is two cumulative-sum lookups. A
modified trade (early exit / tighten) keeps its canonical rows before the new exit minute (identical by construction
of lin_trade / log_trade) plus one replacement exit row, taken from allocator_env.trade_rows. Python runs only per
EXIT/TIGHTEN request (an event), never per minute. No minute ledger is recorded (training mode)."""
from __future__ import annotations
import numpy as np
from . import allocator_contracts as C
from . import allocator_env as AE

HOUR = AE.HOUR


class _Sleeve:
    """Static per-sleeve arrays derived from allocator_env.SleeveData."""

    def __init__(self, sd: AE.SleeveData):
        self.sd = sd
        n = sd.n
        self.n = n
        self.dec = sd.dec_idx.astype(np.int64)
        self.e = sd.e.astype(np.int64)
        self.x = sd.x.astype(np.int64)
        self.exp = sd.expiry.astype(np.int64)
        self.w = sd.w.astype(float)
        self.side = sd.side.astype(float)
        self.avail = sd.avail.astype(bool)
        self.L = (sd.row_off[1:] - sd.row_off[:-1]).astype(np.int64)
        self.rs = np.where(self.L > 0, sd.row_min[np.minimum(sd.row_off[:-1], max(len(sd.row_min) - 1, 0))], 0)
        self.base = (sd.row_off[:-1] + np.arange(n)).astype(np.int64)
        self.cs = sd.row_cs
        for q in np.flatnonzero(self.L > 0)[:: max(1, n // 200)]:      # consecutive-minute rows (spot check)
            m = sd.row_min[sd.row_off[q]:sd.row_off[q + 1]]
            if not np.array_equal(m, self.rs[q] + np.arange(len(m))):
                raise ValueError(f"{sd.name}: rows of opportunity {q} are not consecutive minutes")
        endres = np.where(self.e >= 0, self.x, self.exp)
        self.endres_cmax = np.maximum.accumulate(endres) if n else endres
        if n and np.any(np.diff(self.dec) < 0):
            raise ValueError(f"{sd.name}: opportunities not sorted by decision minute")

    def wsum(self, q, a, b):
        """Canonical unit sum over [a, b) for opportunity indices q (broadcast)."""
        L, rs, base = self.L[q], self.rs[q], self.base[q]
        return self.cs[base + np.clip(b - rs, 0, L)] - self.cs[base + np.clip(a - rs, 0, L)]


class _Book:
    def __init__(self, N: int, sl: list):
        self.mult = [np.zeros((N, s.n)) for s in sl]
        self.end = [np.broadcast_to(np.where(s.e >= 0, s.x, s.exp), (N, s.n)).copy() for s in sl]
        self.tf = [np.ones((N, s.n)) for s in sl]
        self.mod = [np.zeros((N, s.n), bool) for s in sl]
        self.xval = [np.zeros((N, s.n)) for s in sl]
        self.equity = np.zeros(N)
        self.peak = np.zeros(N)
        self.mdd = np.zeros(N)


class VecAllocatorEnv:
    def __init__(self, data: AE.CellData, n_envs: int, cadence_h: int = 1, static_weights=None,
                 terminal_fee: bool = True):
        if cadence_h not in (1, 4):
            raise ValueError("cadence 1h or 4h")
        self.d, self.N, self.cad, self.terminal_fee = data, int(n_envs), cadence_h, terminal_fee
        w = np.asarray(static_weights if static_weights is not None else np.zeros(len(C.SLEEVES)), float)
        w = np.broadcast_to(w, (self.N, len(C.SLEEVES))).copy()
        for r in w:
            C.validate_static_weights(r)
        self.static_w = w
        self.sl = [_Sleeve(data.sleeves[s]) for s in C.SLEEVES]
        # global decision groups (same decision minute across sleeves)
        allq = sorted((int(s.dec[q]), si, q) for si, s in enumerate(self.sl) for q in range(s.n))
        taus = np.array([t for t, _, _ in allq], np.int64)
        self.G_tau, start = np.unique(taus, return_index=True)
        cnt = np.diff(np.r_[start, len(taus)])
        M = int(cnt.max()) if len(cnt) else 1
        self.G_s = np.zeros((len(self.G_tau), M), np.int64)
        self.G_q = np.zeros((len(self.G_tau), M), np.int64)
        self.G_ok = np.zeros((len(self.G_tau), M), bool)
        for g, (st, c) in enumerate(zip(start, cnt)):
            for m in range(c):
                _, si, q = allq[st + m]
                self.G_s[g, m], self.G_q[g, m], self.G_ok[g, m] = si, q, True
        # 1h sequence store (raw), strict 1h continuity segments; per-env start boundary applied at reset
        sr = data.seq_raw.sort_values("T", kind="stable")
        self.T1 = sr["T"].to_numpy(np.int64)
        self.seq_x = sr[list(C.SEQ_COLUMNS)].to_numpy(np.float32)
        brk = np.r_[True, np.diff(self.T1) != HOUR]
        self.seg0 = np.maximum.accumulate(np.where(brk, np.arange(len(self.T1)), 0))
        self.med = np.array([data.seq_norm[c][0] for c in C.SEQ_COLUMNS], np.float32)
        self.scl = np.array([data.seq_norm[c][1] for c in C.SEQ_COLUMNS], np.float32)

    # ---------------------------------------------------------------- episodes
    def reset(self, starts, length_steps: int):
        d, step = self.d, self.cad * HOUR
        starts = np.asarray(starts, np.int64)
        if starts.shape != (self.N,) or np.any(starts % step):
            raise ValueError("one cadence-aligned start per env")
        if np.any(starts < d.usable_from):
            raise ValueError("episode starts before the A2 usable window (2021-01-30)")
        self.L = int(length_steps)
        self.Ts = starts[:, None] + step * np.arange(self.L + 1, dtype=np.int64)[None, :]
        self.ti = np.searchsorted(d.T1h, self.Ts[:, :-1])
        if np.any(self.ti >= len(d.T1h)) or np.any(d.T1h[np.minimum(self.ti, len(d.T1h) - 1)] != self.Ts[:, :-1]):
            raise ValueError("episode decision time missing from the state store")
        self.mi = np.searchsorted(d.t, self.Ts)
        self.start_j = np.searchsorted(self.T1, starts)
        self.k = 0
        self.rl, self.st = _Book(self.N, self.sl), _Book(self.N, self.sl)
        return self.observation()

    # ---------------------------------------------------------------- candidates / state
    def _cands(self, a, b):
        """Per sleeve (N, K) opportunity indices that can matter in [a, b) and their validity."""
        out = []
        for s in self.sl:
            lo = np.searchsorted(s.endres_cmax, a, "left")
            hi = np.searchsorted(s.dec, b, "left")
            K = max(int((hi - lo).max(initial=0)), 1)
            idx = lo[:, None] + np.arange(K)[None, :]
            ok = idx < hi[:, None]
            out.append((np.minimum(idx, max(s.n - 1, 0)), ok))
        return out

    def _occupancy(self, book: _Book, cands, a):
        """pending / open masks (N, K) per sleeve at minute a."""
        res = []
        rows = np.arange(self.N)[:, None]
        for si, (s, (idx, ok)) in enumerate(zip(self.sl, cands)):
            m = book.mult[si][rows, idx] if s.n else np.zeros(idx.shape)
            e, end, ex, dec = s.e[idx], book.end[si][rows, idx], s.exp[idx], s.dec[idx]
            live = ok & (m > 0)
            opn = live & (e >= 0) & (e < a[:, None]) & (a[:, None] <= end)
            pend = live & ~opn & (dec < a[:, None]) & ((e >= a[:, None]) | ((e < 0) & (ex >= a[:, None])))
            res.append((pend, opn))
        return res

    def masks(self, book=None, cands=None):
        book = self.rl if book is None else book
        a = self.mi[:, self.k]
        cands = self._cands(a, self.mi[:, self.k + 1]) if cands is None else cands
        occ = self._occupancy(book, cands, a)
        av = self.d.avail_T[self.ti[:, self.k]]                       # (N, 7)
        S = len(C.SLEEVES)
        me = np.zeros((self.N, S, len(C.LEVELS)), bool)
        mp = np.zeros((self.N, S, 2), bool)
        mo = np.zeros((self.N, S, len(C.OPEN_ACTIONS)), bool)
        rows = np.arange(self.N)[:, None]
        for si, s in enumerate(C.SLEEVES):
            pend, opn = occ[si]
            idx = cands[si][0]
            tfmin = np.where(opn, book.tf[si][rows, idx], 1.0).min(axis=1)
            hp, ho = pend.any(1), opn.any(1)
            me[:, si, 0] = True
            me[:, si, 1:] = av[:, si:si + 1]
            mp[:, si, 0] = True
            mp[:, si, 1] = av[:, si] & hp
            mo[:, si, 0] = True
            ok = av[:, si] & ho
            mo[:, si, 3] = ok
            if s in C.TIGHTEN_SLEEVES:
                mo[:, si, 1] = ok & (tfmin > 0.75)
                mo[:, si, 2] = ok & (tfmin > 0.50)
        return me, mp, mo

    def observation(self):
        d, k = self.d, self.k
        a = self.mi[:, k]
        cands = self._cands(a, self.mi[:, k + 1])
        me, mp, mo = self.masks(cands=cands)
        occ = self._occupancy(self.rl, cands, a)
        rows = np.arange(self.N)[:, None]
        acc = np.zeros((self.N, len(C.SLEEVES), len(C.ACCOUNT_CHANNELS)), np.float32)
        for si, s in enumerate(self.sl):
            pend, opn = occ[si]
            idx = cands[si][0]
            m = self.rl.mult[si][rows, idx]
            acc[:, si, 0] = np.where(opn, m, 0).sum(1)
            acc[:, si, 1] = np.where(opn | pend, m * s.w[idx], 0).sum(1)
            acc[:, si, 2] = pend.any(1)
            acc[:, si, 3] = np.where(opn, self.rl.tf[si][rows, idx], 1.0).min(1)
        j = np.searchsorted(self.T1, self.Ts[:, k])
        hidx = j[:, None] - np.arange(C.SEQ_LEN - 1, -1, -1)[None, :]
        valid = hidx >= np.maximum(self.seg0[j], self.start_j)[:, None]
        raw = np.where(valid[..., None], self.seq_x[np.maximum(hidx, 0)], np.nan)
        nan = np.isnan(raw)
        seq = np.clip(np.where(nan, 0.0, (raw - self.med) / self.scl), -10, 10).astype(np.float32)
        return {"static": d.static[self.ti[:, k]], "seq": seq,
                "seq_nan": (nan & valid[..., None]).astype(np.float32), "seq_pad": (~valid).astype(np.float32),
                "account": acc.reshape(self.N, -1), "T": self.Ts[:, k], "masks": (me, mp, mo)}

    # ---------------------------------------------------------------- dynamics
    def _heads(self, book: _Book, cands, occ, pend_a, open_a, a):
        for si, s in enumerate(self.sl):
            pend, opn = occ[si]
            idx = cands[si][0]
            cancel = pend & (pend_a[:, si] == 1)[:, None]
            if cancel.any():
                r, c = np.nonzero(cancel)
                book.mult[si][r, idx[r, c]] = 0.0
            act = open_a[:, si]
            ev = opn & (act > 0)[:, None]
            if not ev.any():
                continue
            for r, c in zip(*np.nonzero(ev)):
                q = int(idx[r, c])
                op = C.OPEN_ACTIONS[act[r]]
                end = int(book.end[si][r, q])
                ai = int(a[r])
                if op == "EXIT":
                    ch = (AE.lin_exit_change(self.d, s.sd, q, ai, end) if s.sd.kind == "lin"
                          else ((ai, float(self.d.o[ai])) if s.e[q] < ai <= end else None))
                else:
                    f = C.TIGHTEN_F[op]
                    if f >= book.tf[si][r, q]:
                        continue
                    book.tf[si][r, q] = f
                    ch = AE.tighten_exit(self.d, s.sd, q, ai, f, end)
                if ch is not None:
                    j, px = ch
                    mins, cs = AE.trade_rows(self.d, s.sd, q, j, px)
                    book.xval[si][r, q] = cs[-1] - cs[-2]
                    book.mod[si][r, q] = True
                    book.end[si][r, q] = j

    def _entries(self, book: _Book, levels, cands, a, b):
        glo, ghi = np.searchsorted(self.G_tau, a), np.searchsorted(self.G_tau, b)
        R = int((ghi - glo).max(initial=0))
        rows = np.arange(self.N)[:, None]
        for r in range(R):
            has = glo + r < ghi
            if not has.any():
                continue
            g = np.minimum(glo + r, len(self.G_tau) - 1)
            tau = self.G_tau[g]
            gs, gq, gok = self.G_s[g], self.G_q[g], self.G_ok[g] & has[:, None]
            req = np.zeros(gs.shape)
            for si, s in enumerate(self.sl):
                sel = gok & (gs == si)
                if sel.any():
                    q = np.where(sel, gq, 0)
                    req = np.where(sel, levels[:, si:si + 1] * s.w[q] * s.avail[q], req)
            gross = np.zeros(self.N)
            for si, (s, (idx, ok)) in enumerate(zip(self.sl, cands)):
                m = book.mult[si][rows, idx]
                e, end, ex, dec = s.e[idx], book.end[si][rows, idx], s.exp[idx], s.dec[idx]
                res = np.where(e >= 0, end > tau[:, None], ex >= tau[:, None])
                gross += np.where(ok & (m > 0) & (dec < tau[:, None]) & res, m * s.w[idx], 0).sum(1)
            tot = req.sum(1)
            room = np.maximum(C.GROSS_CAP - gross, 0.0)
            scale = np.where((tot <= room) | (tot == 0), 1.0, room / np.where(tot > 0, tot, 1))
            for si, s in enumerate(self.sl):
                sel = gok & (gs == si) & (req > 0)
                if sel.any():
                    r_, c_ = np.nonzero(sel)
                    q = gq[r_, c_]
                    book.mult[si][r_, q] = req[r_, c_] / s.w[q] * scale[r_]

    def _pnl(self, book: _Book, cands, a, b, last):
        rows = np.arange(self.N)[:, None]
        net = np.zeros(self.N)
        legs = np.zeros(self.N)
        A, B = a[:, None], b[:, None]
        for si, (s, (idx, ok)) in enumerate(zip(self.sl, cands)):
            m = book.mult[si][rows, idx]
            e, end = s.e[idx], book.end[si][rows, idx]
            mod = book.mod[si][rows, idx]
            live = ok & (m > 0) & (e >= 0) & (end >= A) & (e < B)
            if not live.any():
                continue
            hi = np.where(mod, np.minimum(B, end), B)
            v = s.wsum(idx, A, hi) + np.where(mod & (end >= A) & (end < B), book.xval[si][rows, idx], 0.0)
            w = s.w[idx]
            net += np.where(live, m * v, 0).sum(1)
            lg = ((e >= A) & (e < B)).astype(float) + ((end >= A) & (end < B))
            if last and self.terminal_fee:
                term = end >= B
                fee = -2.0 * w if s.sd.kind == "lin" else np.full(w.shape, -C.FEE_SIDE_BPS)
                net += np.where(live & term, m * fee, 0).sum(1)
                lg = lg + term
            legs += np.where(live, m * w * lg, 0).sum(1)
        return net, legs * C.FEE_SIDE_BPS

    def step(self, entry, pending, open_):
        entry, pending, open_ = (np.asarray(x) for x in (entry, pending, open_))
        for nm, x, n in (("entry", entry, len(C.LEVELS)), ("pending", pending, 2), ("open", open_, len(C.OPEN_ACTIONS))):
            if x.shape != (self.N, len(C.SLEEVES)) or not np.issubdtype(x.dtype, np.integer) or x.min() < 0 \
                    or x.max() >= n:
                raise ValueError(f"{nm}: need ({self.N}, 7) integer indices in range")
        k = self.k
        a, b = self.mi[:, k], self.mi[:, k + 1]
        cands = self._cands(a, b)
        me, mp, mo = self.masks(cands=cands)
        rr, cc = np.arange(self.N)[:, None], np.arange(len(C.SLEEVES))[None, :]
        if not (me[rr, cc, entry].all() and mp[rr, cc, pending].all() and mo[rr, cc, open_].all()):
            raise ValueError("masked action")
        last = k + 1 == self.L
        lv_rl = np.asarray(C.LEVELS)[entry]
        av = self.d.avail_T[self.ti[:, k]]
        lv_st = np.where(av, self.static_w, 0.0)
        out = {}
        for tag, book, lv, pa, oa in (("rl", self.rl, lv_rl, pending, open_),
                                      ("st", self.st, lv_st, np.zeros_like(pending), np.zeros_like(open_))):
            occ = self._occupancy(book, cands, a)
            self._heads(book, cands, occ, pa, oa, a)
            self._entries(book, lv, cands, a, b)
            net, to = self._pnl(book, cands, a, b, last)
            book.equity += net
            book.peak = np.maximum(book.peak, book.equity)
            mdd = np.maximum(book.mdd, book.peak - book.equity)
            out[tag] = (net, mdd - book.mdd, to)
            book.mdd = mdd
        rew = (out["rl"][0] - out["st"][0]) - C.DD_PENALTY * np.maximum(0.0, out["rl"][1] - out["st"][1]) \
            - C.TURNOVER_PENALTY * np.maximum(0.0, out["rl"][2] - out["st"][2])
        self.k += 1
        done = self.k == self.L
        info = {"net_rl": out["rl"][0], "net_st": out["st"][0], "turnover_rl": out["rl"][2],
                "turnover_st": out["st"][2], "dmdd_rl": out["rl"][1], "dmdd_st": out["st"][1]}
        return (None if done else self.observation()), rew, done, info
