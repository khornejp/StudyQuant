"""A6 continual walk-forward skeleton (monthly prequential; main training P2/P3 waits for the reward values).

For each month M (in order):
  1. normalizers are refit on rows strictly before M (no later data);
  2. EVALUATE FIRST: the current policy trades month M on a continuous evaluation ledger (state carried across months,
     no flat reset), and the frozen-2021 anchor policy trades the same month on its own continuous ledger; the delta
     (policy - anchor) is recorded;
  3. month M joins the training pool; the SAME model and optimizer continue training; episode starts are drawn by the
     replay mix 50 % latest month / 25 % last six months / 25 % all earlier months (cyclic), balanced across regimes
     (sign of the trailing 30-day return at the start), 28-day episodes truncated at the end of the available data,
     7-day rollouts."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

DAY_NS = 86_400 * 10**9
STEP_NS = 5 * 60 * 10**9


@dataclass(frozen=True)
class ContinualConfig:
    episode_days: int = 28
    rollout_days: int = 7
    mix_latest: float = 0.50
    mix_recent6: float = 0.25
    mix_earlier: float = 0.25
    regime_lookback_days: int = 30
    updates_per_month: int = 4


def month_starts(first: str, last: str) -> list:
    return [p.to_timestamp().tz_localize("UTC") for p in pd.period_range(first, last, freq="M")]


def regime_sign(t_ns: np.ndarray, c: np.ndarray, starts_ns: np.ndarray, lookback_days: int) -> np.ndarray:
    """Sign of the trailing return over `lookback_days` ending at each start (closes known before the start)."""
    k = np.searchsorted(t_ns, starts_ns) - 1
    k0 = np.searchsorted(t_ns, starts_ns - lookback_days * DAY_NS) - 1
    ok = (k0 >= 0) & (k >= 0)
    out = np.zeros(len(starts_ns), np.int8)
    out[ok] = np.sign(c[k[ok]] - c[k0[ok]]).astype(np.int8)
    return out


class ReplaySampler:
    """Episode starts for the training pool [pool_start, pool_end): replay mix over month buckets + regime balance."""

    def __init__(self, t_ns, c, months: list, pool_end: pd.Timestamp, cfg: ContinualConfig, data_end_ns: int):
        self.t, self.c, self.cfg = t_ns, c, cfg
        self.months = [m for m in months if m < pool_end]
        self.end_ns = min(pool_end.value, data_end_ns)

    def _bucket_starts(self, rng, lo_ns, hi_ns, n):
        hi_ns = min(hi_ns, self.end_ns - STEP_NS)
        if hi_ns <= lo_ns or n == 0:
            return np.zeros(0, np.int64)
        cand = lo_ns + STEP_NS * rng.integers(0, max((hi_ns - lo_ns) // STEP_NS, 1), 4 * n)
        sg = regime_sign(self.t, self.c, cand, self.cfg.regime_lookback_days)
        up, dn = cand[sg > 0], cand[sg <= 0]
        h = n // 2
        pick = np.r_[up[:h], dn[:n - h]]
        if len(pick) < n:                                    # one regime missing in the bucket: fill from the other
            pick = np.r_[pick, cand[~np.isin(cand, pick)][:n - len(pick)]]
        return pick[:n].astype(np.int64)

    def sample(self, rng, idx):
        n = len(idx)
        m = self.months
        latest = (m[-1].value, self.end_ns)
        recent = (m[max(len(m) - 6, 0)].value, m[-1].value) if len(m) > 1 else latest
        earlier = (m[0].value, m[max(len(m) - 6, 0)].value) if len(m) > 6 else recent
        n1 = int(round(n * self.cfg.mix_latest))
        n2 = int(round(n * self.cfg.mix_recent6))
        n3 = n - n1 - n2
        parts = []
        for (lo, hi), k in ((latest, n1), (recent, n2), (earlier, n3)):
            parts.append(self._bucket_starts(rng, lo, hi, k))
        st = np.concatenate(parts)
        if len(st) < n:
            st = np.r_[st, np.full(n - len(st), latest[0])]
        st = st[rng.permutation(n)]
        en = np.minimum(st + self.cfg.episode_days * DAY_NS, self.end_ns)
        return st, en

    def bucket_of(self, st):
        m = self.months
        lat = m[-1].value
        rec = m[max(len(m) - 6, 0)].value
        return np.where(st >= lat, 0, np.where(st >= rec, 1, 2))


class ContinualLedger:
    """Continuous evaluation ledger across months: one BatchEnv kept alive (no flat reset at month boundaries)."""

    def __init__(self):
        self.rows = []

    def record(self, month: str, who: str, cell: str, net4: float, fills: float, minutes: float):
        self.rows.append({"month": month, "who": who, "cell": cell, "net4": net4, "fills": fills, "minutes": minutes})

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)

    def deltas(self) -> pd.DataFrame:
        f = self.frame()
        if not len(f):
            return f
        p = f.pivot_table(index=["month", "cell"], columns="who", values="net4", aggfunc="sum")
        if "policy" in p and "anchor" in p:
            p["delta"] = p["policy"] - p["anchor"]
        return p.reset_index()


def eval_month(env, policy_fn, month_end_ns: int) -> dict:
    """Run every env of a persistent BatchEnv until its clock reaches month_end_ns (state carried, no reset)."""
    E = env.E
    acc = {"net4": np.zeros(E), "fills": np.zeros(E), "minutes": np.zeros(E)}
    end_idx = np.searchsorted(env.t, month_end_ns)
    env.endx[:] = np.maximum(env.endx, end_idx)
    while True:
        live = env.gi < end_idx - 1
        if not live.any():
            break
        a_t, a_w = policy_fn(env.obs())
        saved = env.endx.copy()
        env.endx[:] = end_idx
        rw = env.step(a_t, a_w)
        env.endx[:] = saved
        for k in acc:
            acc[k] += np.where(live, rw[k], 0.0)
    return acc
