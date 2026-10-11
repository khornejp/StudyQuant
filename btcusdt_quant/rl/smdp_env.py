"""Vectorized SMDP environment for the single-position maker kernel (Codex A3 2026-10-11).

Observation at decision time t (5-minute clock; everything known at t): 44 technique tokens x 20 channels from the
signal store, the market state row (state_1h without sleeve channels, as of t) and 8 account channels. Continuous
channels are robust-scaled with train-window statistics only (median / IQR), NaN -> 0, clipped to +-10.
Action: target index into `targets` (short-only smoke: 0, -0.25, -0.5, -0.75, -1) and wait index into WAITS.
Reward: maker_kernel.step_reward (net4 - idle - turnover, per 5-minute block); the step also returns gamma(d) for the
duration-aware GAE. Episodes: random start on the clock inside the train window, flat reset, end after
`episode_days` elapsed days."""
from __future__ import annotations
import numpy as np, pandas as pd
from . import maker_kernel as MK
from . import signal_store as SG

FLAG = ("side", "active", "strength_avail", "gate_pass", "gate_avail", "available")
CONT = ("strength", "age_min") + tuple(f"mk{h}_{s}" for h in SG.HORIZONS for s in ("mean", "hit", "vol", "count"))
CHANNELS = FLAG + CONT
N_ACCOUNT = 8


def _robust(x: np.ndarray, train: np.ndarray):
    med = np.nanmedian(x[train], axis=0)
    q1, q3 = np.nanpercentile(x[train], 25, axis=0), np.nanpercentile(x[train], 75, axis=0)
    sc = np.where(np.isfinite(q3 - q1) & (q3 > q1), q3 - q1, 1.0)
    med = np.where(np.isfinite(med), med, 0.0)
    return med, sc


class SmdpData:
    """Shared, read-only arrays (market minutes, funding, token / market features) for one fold."""

    def __init__(self, store_dir, minutes: pd.DataFrame, funding_sched: pd.DataFrame, train, end: str):
        """train: one (start, end) window or (A5 LOYO) a list of windows; normalizers / RV median use their union."""
        self.t = minutes.open_time.array.asi8.copy()
        self.o, self.h, self.l, self.c = (minutes[x].to_numpy(float) for x in ("open", "high", "low", "close"))
        self.ft = funding_sched.time.array.asi8.copy()
        self.fr = funding_sched.rate.to_numpy(float)
        self.rv = MK.rv24h(self.c)
        wins = [train] if isinstance(train[0], str) else list(train)
        self.train_windows = [tuple(pd.Timestamp(x, tz="UTC").value for x in w) for w in wins]
        a, b = min(w[0] for w in self.train_windows), max(w[1] for w in self.train_windows)
        self.train = (a, b)
        self.end = pd.Timestamp(end, tz="UTC").value
        clk = SG.clock()
        self.r0 = 0
        self.r1 = int(np.searchsorted(clk, self.end))
        self.clk = clk[:self.r1]
        trn = np.zeros(len(self.clk), bool)
        for wa, wb in self.train_windows:
            trn |= (self.clk >= wa) & (self.clk < wb)
        toks = SG.tokens()
        self.tokens = toks
        feats = []
        for tk in toks:
            f = pd.read_parquet(f"{store_dir}/tokens/{tk}.parquet", columns=["t"] + list(CHANNELS)).iloc[:self.r1]
            if not np.array_equal(f.t.to_numpy(np.int64), self.clk):
                raise ValueError(f"{tk}: clock mismatch")
            fl = f[list(FLAG)].to_numpy(np.float32)
            cn = f[list(CONT)].to_numpy(np.float64)
            cn[:, 1] = np.log1p(cn[:, 1])                       # age
            cn[:, 5::4] = np.log1p(cn[:, 5::4])                 # markout counts
            med, sc = _robust(cn, trn)
            z = np.clip(np.nan_to_num((cn - med) / sc, nan=0.0), -10, 10).astype(np.float32)
            feats.append(np.concatenate([fl, z], 1))
        self.tok = np.stack(feats, 1).reshape(self.r1, -1)      # [rows, 44 x 20]
        mk = pd.read_parquet(f"{store_dir}/market.parquet").iloc[:self.r1]
        if not np.array_equal(mk.t.to_numpy(np.int64), self.clk):
            raise ValueError("market clock mismatch")
        cols = [c for c in mk.columns if c not in ("t", "state_T")]
        x = mk[cols].to_numpy(np.float64)
        med, sc = _robust(x, trn)
        self.mkt = np.clip(np.nan_to_num((x - med) / sc, nan=0.0), -10, 10).astype(np.float32)
        self.market_cols = cols
        rv_tr = np.concatenate([self.rv[int(np.searchsorted(self.t, wa)) + 1440:int(np.searchsorted(self.t, wb))]
                                for wa, wb in self.train_windows])
        self.rv_med = float(np.median(rv_tr))
        self.obs_dim = self.tok.shape[1] + self.mkt.shape[1] + N_ACCOUNT

    def row(self, t_ns: int) -> int:
        return int((t_ns - SG.CLOCK_START.value) // SG.STEP_NS)


class SmdpEnvs:
    def __init__(self, data: SmdpData, cells: list, targets: tuple, episode_days: int, seed: int, waits=MK.WAITS):
        self.d, self.cells, self.targets = data, list(cells), tuple(float(x) for x in targets)
        self.waits = tuple(int(w) for w in waits)
        self.E = len(self.cells)
        self.L = episode_days * 1440
        self.rng = np.random.default_rng(seed)
        self.kern = [None] * self.E
        self.t_now = np.zeros(self.E, np.int64)
        self.t_end = np.zeros(self.E, np.int64)
        self.s0 = np.zeros(self.E, np.int64)
        for e in range(self.E):
            self._reset(e)

    def _reset(self, e: int, start_ns: int | None = None, end_ns: int | None = None):
        d = self.d
        step = SG.STEP_NS
        if start_ns is None:
            a, b = d.train
            lo = -(-max(a, SG.CLOCK_START.value) // step) * step
            n = (b - self.L * SG.MIN_NS - lo) // step
            start_ns = lo + step * int(self.rng.integers(0, n + 1))
            end_ns = start_ns + self.L * SG.MIN_NS
        s = int(np.searchsorted(d.t, start_ns)) - 2                 # slice keeps close[start - 1]
        z = min(int(np.searchsorted(d.t, end_ns)), len(d.t))         # truncate: last minute = end - 1 m
        off, pen = self.cells[e]
        k = MK.Kernel(d.o[s:z], d.h[s:z], d.l[s:z], d.c[s:z], d.t[s:z], d.ft, d.fr, off, pen)
        k.reset(int(np.searchsorted(k.t, start_ns)) - 1)            # decision bar closing at start
        self.kern[e], self.s0[e], self.t_now[e], self.t_end[e] = k, s, start_ns, end_ns

    def obs(self, idx=None) -> np.ndarray:
        idx = np.arange(self.E) if idx is None else np.asarray(idx)
        d = self.d
        rows = np.array([d.row(int(self.t_now[e])) for e in idx])
        acc = np.zeros((len(idx), N_ACCOUNT), np.float32)
        for n, e in enumerate(idx):
            st, k = self.kern[e].st, self.kern[e]
            gi = self.s0[e] + k.i
            acc[n] = (st[MK.S_U], k.last_target, st[MK.S_PEND], st[MK.S_PDQ] * st[MK.S_PEND],
                      np.clip(st[MK.S_POSPNL] / 100, -10, 10), np.clip((st[MK.S_EQ] - st[MK.S_DAY0]) / 100, -10, 10),
                      float(st[MK.S_FPOS] > 0 or st[MK.S_FDAY] > 0), np.log(max(d.rv[gi], 1e-6) / d.rv_med))
        return np.concatenate([d.tok[rows], d.mkt[rows], acc], 1)

    def step_one(self, e: int, a_t: int, a_w: int) -> dict:
        k = self.kern[e]
        st0 = k.st.copy()
        i0 = k.i
        info = k.step(self.targets[a_t], self.waits[a_w])
        gi0 = self.s0[e]
        rv = self.d.rv[gi0:gi0 + len(k.t)]
        rw = MK.step_reward(k.pnl, k.upath, rv, self.d.rv_med, i0, info["j"], info["d_target"])
        u = k.upath[i0 + 1:info["j"] + 1]
        st1 = k.st
        out = {**rw, "identity_err": abs(rw["net4"] - info["net4"]) + abs(rw["reward"] - (rw["net4"] - rw["idle"]
                                                                                          - rw["turnover"])),
               "minutes": int(len(u)), "flat_minutes": int((np.abs(u) < 0.125).sum()), "exposure_sum": float(np.abs(u).sum()),
               "u_max": float(u.max()) if len(u) else 0.0, "u_min": float(u.min()) if len(u) else 0.0, "u_absmax": float(np.abs(u).max()) if len(u) else 0.0,
               "target": self.targets[a_t], "wait": self.waits[a_w], "a_w": int(a_w),
               "last_time": int(k.t[info["j"]]) if len(u) else -1}
        for nm, slot in (("fills", MK.S_FILLS), ("round_trips", MK.S_RT), ("ttl_expiry", MK.S_TTLX),
                         ("requote", MK.S_REQ), ("reversal", MK.S_REV), ("pos_stop", MK.S_PSTOP),
                         ("day_stop", MK.S_DSTOP), ("fees", MK.S_FEES), ("funding", MK.S_FUND),
                         ("stop_size_sum", MK.S_DSZ), ("stop_entry_to_stop_min_sum", MK.S_DE2S),
                         ("stop_flatten_loss_sum", MK.S_DFL), ("stop_flattens", MK.S_DNFL),
                         ("stop_reentry_min_sum", MK.S_DRE), ("stop_reentries", MK.S_DNRE),
                         ("stop_events", MK.S_NEV)):
            out[nm] = float(st1[slot] - st0[slot])
        self.t_now[e] = self.d.t[gi0 + info["j"]] + SG.MIN_NS
        out["done"] = bool(info["j"] >= len(k.t) - 1 or self.t_now[e] >= self.t_end[e])
        return out

    def step(self, a_t: np.ndarray, a_w: np.ndarray):
        infos = [self.step_one(e, int(a_t[e]), int(a_w[e])) for e in range(self.E)]
        for e, inf in enumerate(infos):
            if inf["done"]:
                self._reset(e)
        return infos

    # ---------------------------------------------------------------- bit-exact resume
    def state_dict(self) -> dict:
        return {"rng": self.rng.bit_generator.state, "t_now": self.t_now.copy(), "t_end": self.t_end.copy(),
                "s0": self.s0.copy(), "kern": [(k.st.copy(), k.i, k.i0, k.last_target, len(k.t)) for k in self.kern]}

    def load_state_dict(self, sd: dict) -> None:
        self.rng.bit_generator.state = sd["rng"]
        d = self.d
        for e, (st, i, i0, lt, n) in enumerate(sd["kern"]):
            s = int(sd["s0"][e])
            off, pen = self.cells[e]
            k = MK.Kernel(d.o[s:s + n], d.h[s:s + n], d.l[s:s + n], d.c[s:s + n], d.t[s:s + n], d.ft, d.fr, off, pen)
            k.st, k.i, k.i0, k.last_target = st.copy(), int(i), int(i0), float(lt)
            self.kern[e] = k
        self.t_now, self.t_end, self.s0 = sd["t_now"].copy(), sd["t_end"].copy(), sd["s0"].copy()


def make_blocks(train: tuple, days: int = 90) -> list:
    """A4: non-overlapping chronological blocks [a + days*k, min(a + days*(k+1), b)), tail included."""
    a, b = (pd.Timestamp(x, tz="UTC").value for x in train)
    out, k = [], 0
    while a + k * days * 86_400 * 10**9 < b:
        s_ = a + k * days * 86_400 * 10**9
        out.append((k, s_, min(s_ + days * 86_400 * 10**9, b)))
        k += 1
    for (_, _, e1), (_, s2, _) in zip(out[:-1], out[1:]):
        if s2 < e1:
            raise ValueError("block overlap")
    return out


class SmdpBlockEnvs(SmdpEnvs):
    """A4 episodes: every cell runs min(10, n_blocks) envs over the same block queue (block start = flat reset, no
    random start); a finished env takes the next unconsumed block; after all blocks the cycle restarts."""

    def __init__(self, data: SmdpData, cells6: list, targets: tuple, waits: tuple, max_env_per_cell: int = 10):
        self.d, self.targets, self.waits = data, tuple(float(x) for x in targets), tuple(int(w) for w in waits)
        self.blocks = make_blocks(tuple(pd.Timestamp(int(x), tz="UTC").isoformat() for x in data.train))
        self.n_env = min(max_env_per_cell, len(self.blocks))
        self.cells = [c for c in cells6 for _ in range(self.n_env)]
        self.E = len(self.cells)
        self.kern = [None] * self.E
        self.t_now = np.zeros(self.E, np.int64)
        self.t_end = np.zeros(self.E, np.int64)
        self.s0 = np.zeros(self.E, np.int64)
        self.block_of = np.zeros(self.E, np.int64)
        self.next_block = {c: self.n_env for c in cells6}
        self.reuse = {c: np.zeros(len(self.blocks), np.int64) for c in cells6}
        for e in range(self.E):
            self._start_block(e, e % self.n_env)

    def _start_block(self, e: int, k: int):
        c = self.cells[e]
        self.reuse[c][k] += 1
        _, a, b = self.blocks[k]
        self.block_of[e] = k
        self._reset(e, a, b)

    def advance_block(self, e: int):
        c = self.cells[e]
        k = self.next_block[c] % len(self.blocks)
        self.next_block[c] += 1
        self._start_block(e, k)

    def block_info(self, e: int) -> dict:
        k = int(self.block_of[e])
        _, a, b = self.blocks[k]
        return {"block": k, "start": a, "end": b, "reuse": int(self.reuse[self.cells[e]][k]) - 1}


class SmdpYearBlockEnvs(SmdpBlockEnvs):
    """A5 LOYO episodes: for every cell and every train window (calendar year) `env_per` envs walk that year's
    non-overlapping 90-day blocks (tail included, flat reset at block start) in order, cycling; every year gets the
    same number of envs and the same rollout minutes."""

    def __init__(self, data: SmdpData, cells6: list, targets: tuple, waits: tuple, windows: list, env_per: int = 3):
        self.d, self.targets, self.waits = data, tuple(float(x) for x in targets), tuple(int(w) for w in waits)
        self.year_blocks = [make_blocks(tuple(x if isinstance(x, str) else pd.Timestamp(int(x), tz="UTC").isoformat()
                                                for x in w)) for w in windows]
        self.blocks = [b for yb in self.year_blocks for b in yb]
        self.n_env = env_per
        self.slots = [(c, y) for c in cells6 for y in range(len(windows)) for _ in range(env_per)]
        self.cells = [c for c, _ in self.slots]
        self.E = len(self.cells)
        self.kern = [None] * self.E
        self.t_now = np.zeros(self.E, np.int64)
        self.t_end = np.zeros(self.E, np.int64)
        self.s0 = np.zeros(self.E, np.int64)
        self.block_of = np.zeros(self.E, np.int64)
        self.next_block = {(c, y): env_per for c in cells6 for y in range(len(windows))}
        self.reuse = {(c, y): np.zeros(len(self.year_blocks[y]), np.int64) for c in cells6 for y in range(len(windows))}
        pos = {}
        for e, key in enumerate(self.slots):
            j = pos.get(key, 0)
            pos[key] = j + 1
            self._start_year_block(e, j % len(self.year_blocks[key[1]]))

    def _start_year_block(self, e: int, k: int):
        c, y = self.slots[e]
        self.reuse[(c, y)][k] += 1
        _, a, b = self.year_blocks[y][k]
        self.block_of[e] = k
        self._reset(e, a, b)

    def advance_block(self, e: int):
        key = self.slots[e]
        k = self.next_block[key] % len(self.year_blocks[key[1]])
        self.next_block[key] += 1
        self._start_year_block(e, k)

    def block_info(self, e: int) -> dict:
        c, y = self.slots[e]
        k = int(self.block_of[e])
        _, a, b = self.year_blocks[y][k]
        return {"year_window": int(y), "block": k, "start": a, "end": b, "reuse": int(self.reuse[(c, y)][k]) - 1}
