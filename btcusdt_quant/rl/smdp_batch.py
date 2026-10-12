"""A6-P0 / P1: batched SoA maker kernel, batched observations, single preloaded feature cache and the GPU PPO policy.

The scalar maker_kernel stays the reference; `advance_batch` runs the same minute logic (`maker_kernel._minute`) for
[E, S_NSTATE] states in parallel over envs on global minute arrays and writes 5-minute block aggregates (net4,
executed U and reward flat-streak k at each block end) instead of minute paths. Parity is tested against the scalar
kernel on random decisions (all targets / waits / cells)."""
from __future__ import annotations
import time
from pathlib import Path
import numba
import numpy as np
from numba import prange
from . import maker_kernel as MK

MAX_BLOCKS = 1440 // 5


@numba.njit(parallel=True, cache=True)
def _advance_batch(o, h, l, c, t, frate, ST, gi, tgt, wait, endx, off, pen, net_b, u_b, k_b, nb, jout,
                   sl_mult, tp_mult, rv_dec):
    """Every env e: decision at global bar gi[e] with target tgt[e]; minutes gi+1 .. min(gi+wait, endx-1) unless a
    fault stops it. Block arrays are [E, MAX_BLOCKS]; nb[e] full blocks, jout[e] last processed minute."""
    E = ST.shape[0]
    for e in prange(E):
        st = ST[e]
        i = gi[e]
        n = endx[e]
        requested_wait = wait[e]
        effective_wait = requested_wait
        if abs(st[MK.S_U]) > MK.EPS and st[MK.S_OPENK] >= 0:
            age = i - int(st[MK.S_OPENK]) + 1
            effective_wait = min(effective_wait, max(MK.CAP_MIN - age, 1))
        j = i + effective_wait
        if j > n - 1:
            j = n - 1
        for b in range(MAX_BLOCKS):
            net_b[e, b] = 0.0
        jout[e] = i
        nb[e] = 0
        if st[MK.S_FAULT] > 0:
            continue
        if st[MK.S_KILL] > 0:
            st[MK.S_FAULT], st[MK.S_FAULTK], st[MK.S_FAULTCODE] = 1.0, i + 1, 5.0
            st[MK.S_KILLCOUNT] += 1
            continue
        st[MK.S_EVENT], st[MK.S_EVENTK], st[MK.S_CAPFLAG], st[MK.S_CURTGT] = 0.0, float(i), 0.0, tgt[e]
        sigma = rv_dec[e] * np.sqrt(requested_wait / MK.CAP_MIN)
        st[MK.S_SL_MULT], st[MK.S_TP_MULT] = sl_mult[e], tp_mult[e]
        st[MK.S_SL_BPS], st[MK.S_TP_BPS] = sl_mult[e] * sigma, tp_mult[e] * sigma
        st[MK.S_LASTWAIT] = requested_wait
        if st[MK.S_REENTRYAWAIT] > 0:
            if abs(tgt[e]) > MK.EPS and st[MK.S_REENTRYACTIVE] == 0:
                st[MK.S_REENTRYREQ] += 1
                st[MK.S_REENTRYACTIVE] = 1.0
            elif abs(tgt[e]) <= MK.EPS:
                st[MK.S_REENTRYAWAIT], st[MK.S_REENTRYACTIVE] = 0.0, 0.0
        if st[MK.S_PEND] > 0:
            if abs(st[MK.S_PTGT] - tgt[e]) > MK.EPS:
                st[MK.S_PEND] = 0.0
                MK._place(st, c, tgt[e], i + 2, off[e], n)
        else:
            MK._place(st, c, tgt[e], i + 1, off[e], n)
        last = i
        for k in range(i + 1, j + 1):
            code = MK._fault_at(o, h, l, c, t, k)
            if code > 0:
                st[MK.S_FAULT], st[MK.S_FAULTK], st[MK.S_FAULTCODE] = 1.0, k, code
                st[MK.S_KILLCOUNT] += 1
                break
            v = MK._minute(o, h, l, c, frate, st, k, off[e], pen[e], n)
            b = (k - i - 1) // 5
            if b < MAX_BLOCKS:
                net_b[e, b] += v
                if (k - i) % 5 == 0 or st[MK.S_EVENT] in (MK.EXIT_SL, MK.EXIT_TP, MK.EXIT_CAP) or k == j:
                    u_b[e, b] = st[MK.S_U]
                    k_b[e, b] = st[MK.S_KSTREAK]
            last = k
            if st[MK.S_EVENT] in (MK.EXIT_SL, MK.EXIT_TP, MK.EXIT_CAP):
                break
        jout[e] = last
        nb[e] = (last - i + 4) // 5


def advance_batch(o, h, l, c, t, frate, ST, gi, tgt, wait, endx, off, pen, net_b, u_b, k_b, nb, jout,
                  sl_mult=None, tp_mult=None, rv_dec=None):
    """Python compatibility wrapper. Scalar and batch share ``maker_kernel._minute`` for all fills and exits."""
    E = ST.shape[0]
    z = np.zeros(E, np.float64)
    _advance_batch(o, h, l, c, t, frate, ST, gi, tgt, wait, endx, off, pen, net_b, u_b, k_b, nb, jout,
                   z if sl_mult is None else np.asarray(sl_mult, np.float64),
                   z if tp_mult is None else np.asarray(tp_mult, np.float64),
                   z if rv_dec is None else np.asarray(rv_dec, np.float64))


def frate_global(t_ns: np.ndarray, ft_ns: np.ndarray, fr: np.ndarray) -> np.ndarray:
    out = np.full(len(t_ns), np.nan)
    k = np.searchsorted(t_ns, ft_ns)
    ok = (k < len(t_ns)) & (t_ns[np.minimum(k, len(t_ns) - 1)] == ft_ns)
    out[k[ok]] = np.asarray(fr, float)[ok]
    return out


def batch_reward(net_b, u_b, k_b, m_glob, gi, nb, d_target, cfg, require_set: bool = True, jout=None) -> dict:
    """Vectorized smdp_reward over envs: arrays [E, B] (valid b < nb[e])."""
    from .smdp_reward import f_of_k
    if require_set and not cfg.is_set():
        raise ValueError("reward magnitudes are UNSET (idle / inventory await the user's decision)")
    z = lambda v: 0.0 if v is None else float(v)  # noqa: E731
    E, B = net_b.shape
    bidx = np.arange(B)[None, :]
    valid = bidx < nb[:, None]
    end = gi[:, None] + 5 * (bidx + 1)
    if jout is not None:
        last = np.maximum(nb - 1, 0)
        end[np.arange(E), last] = np.asarray(jout)
    m = m_glob[np.minimum(end, len(m_glob) - 1)]
    flat = np.abs(u_b) < MK.FLAT_ABS
    idle = z(cfg.idle_bps_per_h) / 12.0 * m * f_of_k(k_b / 60.0, cfg) * flat * valid
    inv = z(cfg.inventory_bps_per_h) / 12.0 * ((m * m * u_b * u_b) if cfg.quadratic_inventory
                                                else np.abs(u_b)) * valid
    net = net_b * valid
    turn = z(cfg.turnover_bps) * d_target * (nb > 0)            # like the scalar step: no block, no turnover term
    disc = np.exp(-np.log(2.0) * 5.0 * bidx / MK.HALF_LIFE_MIN)
    r = net - idle - inv
    r_disc = (disc * r).sum(1) - turn
    return {"net4": net.sum(1), "idle": idle.sum(1), "inventory": inv.sum(1), "turnover": turn,
            "reward": r.sum(1) - turn, "reward_discounted": r_disc,
            "gamma_d": np.exp(-np.log(2.0) * (5.0 * nb) / MK.HALF_LIFE_MIN), "flat_blocks": (flat * valid).sum(1)}


# ---------------------------------------------------------------- single preload of the signal store
CACHE = Path(__file__).resolve().parents[2] / "out/rl_allocator_20261010/smdp_cache"


def raw_cache(store_dir) -> dict:
    """44 token parquet + market parquet read once into one float32 memmap (raw, unscaled) + a manifest."""
    import json
    import pandas as pd
    from . import signal_store as SG
    from .smdp_env import CHANNELS
    CACHE.mkdir(parents=True, exist_ok=True)
    f_tok, f_mkt, f_man = CACHE / "tok_raw.npy", CACHE / "mkt_raw.npy", CACHE / "manifest.json"
    if f_man.exists():
        man = json.loads(f_man.read_text(encoding="utf-8"))
        return {"tok": np.load(f_tok, mmap_mode="r"), "mkt": np.load(f_mkt, mmap_mode="r"), **man}
    toks = SG.tokens()
    clk = None
    cols = []
    for k, tk in enumerate(toks):
        f = pd.read_parquet(f"{store_dir}/tokens/{tk}.parquet", columns=["t"] + list(CHANNELS))
        if clk is None:
            clk = f.t.to_numpy(np.int64)
            tok = np.lib.format.open_memmap(f_tok, mode="w+", dtype=np.float32, shape=(len(clk), len(toks), len(CHANNELS)))
        tok[:, k, :] = f[list(CHANNELS)].to_numpy(np.float32)
        cols.append(tk)
    tok.flush()
    mk = pd.read_parquet(f"{store_dir}/market.parquet")
    mcols = [c for c in mk.columns if c not in ("t", "state_T")]
    np.save(f_mkt, mk[mcols].to_numpy(np.float32))
    man = {"tokens": cols, "channels": list(CHANNELS), "market_cols": mcols, "rows": int(len(clk)),
           "clock0": int(clk[0])}
    f_man.write_text(json.dumps(man) + "\n", encoding="utf-8")
    return {"tok": np.load(f_tok, mmap_mode="r"), "mkt": np.load(f_mkt, mmap_mode="r"), **man}


def scaled_features(cache: dict, train_rows: np.ndarray, r1: int) -> tuple[np.ndarray, np.ndarray]:
    """Train-row robust scaling (same rule as smdp_env.SmdpData) applied once to the cached raw arrays."""
    from .smdp_env import FLAG
    tok = np.asarray(cache["tok"][:r1], np.float64)
    nf = len(FLAG)
    cont = tok[:, :, nf:].copy()
    cont[:, :, 1] = np.log1p(cont[:, :, 1])
    cont[:, :, 5::4] = np.log1p(cont[:, :, 5::4])
    tr = cont[train_rows]
    with np.errstate(all="ignore"):
        med = np.nanmedian(tr, 0)
        q1, q3 = np.nanpercentile(tr, 25, 0), np.nanpercentile(tr, 75, 0)
    sc = np.where(np.isfinite(q3 - q1) & (q3 > q1), q3 - q1, 1.0)
    med = np.where(np.isfinite(med), med, 0.0)
    z = np.clip(np.nan_to_num((cont - med) / sc, nan=0.0), -10, 10)
    out_tok = np.concatenate([tok[:, :, :nf], z], 2).astype(np.float32).reshape(r1, -1)
    x = np.asarray(cache["mkt"][:r1], np.float64)
    with np.errstate(all="ignore"):
        m2 = np.nanmedian(x[train_rows], 0)
        a1, a3 = np.nanpercentile(x[train_rows], 25, 0), np.nanpercentile(x[train_rows], 75, 0)
    s2 = np.where(np.isfinite(a3 - a1) & (a3 > a1), a3 - a1, 1.0)
    m2 = np.where(np.isfinite(m2), m2, 0.0)
    out_mkt = np.clip(np.nan_to_num((x - m2) / s2, nan=0.0), -10, 10).astype(np.float32)
    return out_tok, out_mkt


class BatchEnv:
    """E envs on global minute arrays; episodes [start, end) chosen by the caller (`reset_env`)."""

    def __init__(self, mkt: dict, feats: tuple, cells: list, targets: tuple, waits: tuple, reward_cfg, rv_med: float,
                 require_set: bool = False, sl_grid=(0.0,), tp_grid=(0.0,)):
        self.o, self.h, self.l, self.c, self.t = mkt["o"], mkt["h"], mkt["l"], mkt["c"], mkt["t"]
        self.frate, self.rv, self.rv_ref, self.m = mkt["frate"], mkt["rv"], mkt["rv_ref"], mkt["m"]
        self.clock0 = mkt["clock0"]
        self.tok, self.mk = feats
        self.E = len(cells)
        self.off = np.array([c[0] for c in cells], float)
        self.pen = np.array([c[1] for c in cells], float)
        self.targets = np.asarray(targets, float)
        self.waits = np.asarray(waits, np.int64)
        self.sl_grid, self.tp_grid = np.asarray(sl_grid, float), np.asarray(tp_grid, float)
        self.cfg, self.require_set, self.rv_med = reward_cfg, require_set, rv_med
        self.ST = np.zeros((self.E, MK.S_NSTATE))
        self.gi = np.zeros(self.E, np.int64)
        self.endx = np.zeros(self.E, np.int64)
        self.last_t = np.zeros(self.E)
        self.net_b = np.zeros((self.E, MAX_BLOCKS))
        self.u_b = np.zeros((self.E, MAX_BLOCKS))
        self.k_b = np.zeros((self.E, MAX_BLOCKS))
        self.nb = np.zeros(self.E, np.int64)
        self.jout = np.zeros(self.E, np.int64)

    def reset_env(self, idx, start_ns, end_ns):
        idx = np.asarray(idx)
        self.ST[idx] = 0.0
        self.ST[idx, MK.S_OPENK] = -1.0
        self.gi[idx] = np.searchsorted(self.t, start_ns) - 1
        self.endx[idx] = np.searchsorted(self.t, end_ns)
        self.last_t[idx] = 0.0

    def obs(self) -> np.ndarray:
        st = self.ST
        rows = ((self.t[self.gi] + MK.MIN_NS - self.clock0) // (5 * MK.MIN_NS)).astype(np.int64)
        rows = np.minimum(rows, len(self.tok) - 1)       # envs that finished at the data end (their obs is unused)
        ref = self.rv_ref[self.gi]
        ref = np.where(np.isfinite(ref), ref, self.rv_med)
        age = np.where(st[:, MK.S_PEND] > 0, (self.gi - st[:, MK.S_PPLACED]) / 60.0, 0.0)
        acc = np.stack([st[:, MK.S_U], self.last_t, st[:, MK.S_PEND], st[:, MK.S_PDQ] * st[:, MK.S_PEND],
                        np.clip(st[:, MK.S_POSPNL] / 100, -10, 10), age, np.clip(st[:, MK.S_FLATSTREAK] / 1440.0, 0, 4),
                        np.log(np.maximum(self.rv[self.gi], 1e-6) / ref)], 1).astype(np.float32)
        return np.concatenate([self.tok[rows], self.mk[rows], acc], 1)

    def step(self, a_t: np.ndarray, a_w: np.ndarray, a_sl=None, a_tp=None) -> dict:
        tg = self.targets[a_t]
        wt = self.waits[a_w]
        a_sl = np.zeros(self.E, np.int64) if a_sl is None else np.asarray(a_sl, np.int64)
        a_tp = np.zeros(self.E, np.int64) if a_tp is None else np.asarray(a_tp, np.int64)
        sl, tp = self.sl_grid[a_sl], self.tp_grid[a_tp]
        eq0 = self.ST[:, MK.S_EQ].copy()
        f0 = self.ST[:, MK.S_FILLS].copy()
        st0 = self.ST.copy()
        gi0 = self.gi.copy()
        advance_batch(self.o, self.h, self.l, self.c, self.t, self.frate, self.ST, self.gi, tg, wt, self.endx,
                      self.off, self.pen, self.net_b, self.u_b, self.k_b, self.nb, self.jout, sl, tp, self.rv[self.gi])
        dtg = np.abs(tg - self.last_t)
        rw = batch_reward(self.net_b, self.u_b, self.k_b, self.m, gi0, self.nb, dtg, self.cfg, self.require_set,
                          self.jout)
        eqd = self.ST[:, MK.S_EQ] - eq0
        ident = np.abs(rw["net4"] - eqd)
        bad = ident > 1e-8
        if bad.any():
            for e in np.flatnonzero(bad):
                if self.ST[e, MK.S_FAULT] == 0:
                    self.ST[e, MK.S_FAULT], self.ST[e, MK.S_FAULTK], self.ST[e, MK.S_FAULTCODE] = 1.0, self.jout[e], 4.0
        self.last_t = tg
        self.gi = self.jout.copy()
        done = (self.gi >= self.endx - 1) | (self.ST[:, MK.S_FAULT] > 0)
        rw["gamma_d"] = np.exp(-np.log(2.0) * (self.jout - gi0) / MK.HALF_LIFE_MIN)
        rw.update(identity_err=ident, fills=self.ST[:, MK.S_FILLS] - f0, done=done, minutes=self.jout - gi0,
                  fault=self.ST[:, MK.S_FAULT] > 0, u=self.ST[:, MK.S_U].copy(),
                  exit_reason=self.ST[:, MK.S_EVENT].astype(np.int64).copy(),
                  renewal_count=self.ST[:, MK.S_CAPCOUNT] - st0[:, MK.S_CAPCOUNT],
                  renewal_cost=self.ST[:, MK.S_RENEWCOST] - st0[:, MK.S_RENEWCOST],
                  reentry_requests=self.ST[:, MK.S_REENTRYREQ] - st0[:, MK.S_REENTRYREQ],
                  reentry_fills=self.ST[:, MK.S_REENTRYFILL] - st0[:, MK.S_REENTRYFILL],
                  flat_gap_min=self.ST[:, MK.S_FLATGAP] - st0[:, MK.S_FLATGAP],
                  sl_count=self.ST[:, MK.S_SLCOUNT] - st0[:, MK.S_SLCOUNT],
                  tp_count=self.ST[:, MK.S_TPCOUNT] - st0[:, MK.S_TPCOUNT],
                  sl_pnl=self.ST[:, MK.S_SLPNL] - st0[:, MK.S_SLPNL],
                  tp_pnl=self.ST[:, MK.S_TPPNL] - st0[:, MK.S_TPPNL],
                  cap_pnl=self.ST[:, MK.S_CAPPNL] - st0[:, MK.S_CAPPNL],
                  rl_exit_pnl=self.ST[:, MK.S_RLPNL] - st0[:, MK.S_RLPNL],
                  max_hold_min=self.ST[:, MK.S_MAXHOLD].copy())
        return rw


def market_arrays(minutes, fund_sched, reward_cfg) -> dict:
    from .smdp_reward import m_of_t
    t = minutes.open_time.array.asi8.copy()
    c = minutes.close.to_numpy(float)
    rv = MK.rv24h(c)
    rv_ref = MK.rv_ref_monthly(t, rv)
    return {"t": t, "o": minutes.open.to_numpy(float), "h": minutes.high.to_numpy(float),
            "l": minutes.low.to_numpy(float), "c": c, "frate": frate_global(t, fund_sched.time.array.asi8,
                                                                           fund_sched.rate.to_numpy(float)),
            "rv": rv, "rv_ref": rv_ref, "m": m_of_t(rv, rv_ref, reward_cfg)}


def timer():
    return time.perf_counter()
