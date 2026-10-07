"""Batched 15-minute RL env over core.advance_minute (plan 3 Task 3, contract C1-C7, frozen reward).
Rulings: the last step's action is never executed (its fill could only be force-closed); the open position is
held through the last minute (funding as held) and closed at that minute's close, paying exit fee and slippage.
replay applies the same rule to core.simulate, so env and engine P&L agree to 1e-9."""
from __future__ import annotations
import math
from dataclasses import dataclass
import numba
import numpy as np, pandas as pd
from ..sim import core, costs
from ..sim.core import A_ENTRY, A_ENTRY_I, A_EXIT, A_SIDE, MINUTE_NS
from ..sim.reference import TRADE_COLUMNS, SimConfig, SimResult
from .state import StateStore

SIDES = np.array([0, 1, -1])                 # action index -> target side (flat, long, short); mask columns alike
STEP_MIN = 15
STEP_NS = STEP_MIN * MINUTE_NS
# C6, appended to store.static; bps channels in percent (bps / 100) so they are O(1) like the standardized inputs
ACCOUNT_NAMES = ("acct_side", "acct_log1p_hold_min", "acct_unrealized_pct", "acct_mae_pct", "acct_drawdown_pct",
                 "acct_mdd_pct", "acct_steps_left")
CUM, PEAK, MDD, MAE, UNREAL = range(5)                                 # per-env float account slots
NET, DMDD, FEES, SLIP, FUND, TRADES = range(6)                         # per-step outputs


@dataclass(frozen=True)
class EnvConfig:
    """Randomization drawn once per episode. randomize=False uses the lower bounds and delay 1 (nominal: 4, 0, 1)."""
    episode_steps: int = 1344
    randomize: bool = True
    cost_bps: tuple = (4, 12)        # round trip; fee_per_side = cost / 2
    slip_bps: tuple = (0, 10)        # per market fill, adverse
    delay_mix: float = 0.5           # P(delay ~ U{1..delay_max}), else 1 minute
    delay_max: int = 5


@numba.njit(cache=True)
def _step(target, last, t_dec, lo, hi, delay, fee, slip, si, sf, acc, t_ns, o, h, l, c, fund_ns, fund_rate,
          out, minute_net):
    for e in range(len(target)):
        out[e, :] = 0.0
        minute_net[e, :] = 0.0
        mdd0 = acc[e, MDD]
        fill = t_dec[e] + delay[e] * MINUTE_NS
        for i in range(lo[e], hi[e]):
            side = si[e, A_SIDE]
            tgt = target[e] if t_ns[i] == fill and not last else side
            # diagnostics only, P&L comes from the kernel. Fills land at T+1..T+14 and settlements at :00, so a fill
            # minute is never a settlement minute (delay < 15 is enforced) and funding is only ever "held through".
            if tgt != side:
                out[e, FEES] += fee[e] * ((side != 0) + (tgt != 0))
                out[e, SLIP] += -side * math.log(1 - side * slip[e] / 1e4) * 1e4 \
                    + tgt * math.log(1 + tgt * slip[e] / 1e4) * 1e4
                out[e, TRADES] += side != 0
                acc[e, MAE] = 0.0
            elif side != 0:
                k = np.searchsorted(fund_ns, t_ns[i])
                if k < len(fund_ns) and fund_ns[k] == t_ns[i]:
                    out[e, FUND] += -side * fund_rate[k] * 1e4
            pnl = core.advance_minute(i, si[e], sf[e], o, h, l, c, fund_ns, fund_rate, t_ns, tgt, fee[e], slip[e])
            side = si[e, A_SIDE]
            if last and i == hi[e] - 1 and side != 0:                # C4 forced close at the last minute's close
                price = c[i] * (1 - side * slip[e] / 1e4)
                pnl += -fee[e] + side * math.log(price / c[i]) * 1e4
                out[e, FEES] += fee[e]
                out[e, SLIP] += -side * math.log(1 - side * slip[e] / 1e4) * 1e4
                out[e, TRADES] += 1
                si[e, A_SIDE] = 0; sf[e, A_EXIT] = price
                side = 0
            acc[e, UNREAL] = side * math.log(c[i] / sf[e, A_ENTRY]) * 1e4 if side != 0 else 0.0
            acc[e, MAE] = max(acc[e, MAE], -acc[e, UNREAL]) if side != 0 else 0.0
            acc[e, CUM] += pnl
            acc[e, PEAK] = max(acc[e, PEAK], acc[e, CUM])
            acc[e, MDD] = max(acc[e, MDD], acc[e, PEAK] - acc[e, CUM])
            minute_net[e, (t_ns[i] - t_dec[e]) // MINUTE_NS] = pnl
            out[e, NET] += pnl
        out[e, DMDD] = acc[e, MDD] - mdd0


class VecTradingEnv:
    """n_envs synchronized episodes of episode_steps 15-minute decisions inside [start, end] (C4).
    Actions are indices into SIDES. A done env auto-resets: step returns the new episode's first observation."""

    def __init__(self, store: StateStore, minutes: pd.DataFrame, funding, start, end, n_envs: int,
                 config: EnvConfig, seed: int):
        if len(store.times) and not (np.diff(store.times) == STEP_NS).all():
            raise ValueError("store times must be a contiguous 15-minute grid")
        if not 1 <= config.delay_max < STEP_MIN:
            raise ValueError("delay must fill inside its own 15-minute step")
        self.store, self.n, self.config = store, n_envs, config
        self.t_ns = pd.DatetimeIndex(minutes.open_time).as_unit("ns").asi8
        self.o, self.h, self.l, self.c = (minutes[k].to_numpy(np.float64) for k in ("open", "high", "low", "close"))
        self.fund_ns, self.fund_rate = np.asarray(funding[0], np.int64), np.asarray(funding[1], np.float64)
        self.m_lo = np.searchsorted(self.t_ns, np.r_[store.times, store.times[-1] + STEP_NS])  # step k: [m_lo[k], m_lo[k+1])
        steps = config.episode_steps
        k = np.arange(max(len(store.times) - steps + 1, 0))
        valid = np.flatnonzero(~store.mask_missing)          # warm-up rows (detector not yet valid) never start one
        first = store.times[valid[0]] if len(valid) else np.iinfo(np.int64).max
        ok = ((store.times[k] >= max(pd.Timestamp(start).value, first)) &(store.times[k] + steps * STEP_NS <= pd.Timestamp(end).value)
              & (self.m_lo[k + steps] > self.m_lo[k + steps - 1]))      # the last step has a minute to close at
        self.starts = k[ok]
        if not len(self.starts):
            raise ValueError("no episode fits in [start, end]")
        self.rng = np.random.default_rng(seed)
        self.si = np.zeros((n_envs, len(core.STATE_INT)), np.int64)
        self.sf = np.zeros((n_envs, len(core.STATE_FLOAT)))
        self.acc = np.zeros((n_envs, 5))
        self.k0 = np.zeros(n_envs, np.int64); self.t = np.zeros(n_envs, np.int64)
        self.cost = np.zeros(n_envs); self.slip = np.zeros(n_envs); self.delay = np.ones(n_envs, np.int64)
        self.out = np.zeros((n_envs, 6)); self.minute_net = np.zeros((n_envs, STEP_MIN))

    @property
    def side(self) -> np.ndarray:
        return self.si[:, A_SIDE]

    def _reset(self, idx: np.ndarray) -> None:
        cfg, rng, m = self.config, self.rng, len(idx)
        self.k0[idx] = rng.choice(self.starts, m)
        self.t[idx] = 0; self.si[idx] = 0; self.sf[idx] = 0.0; self.acc[idx] = 0.0
        if cfg.randomize:
            self.cost[idx] = rng.uniform(*cfg.cost_bps, m)
            self.slip[idx] = rng.uniform(*cfg.slip_bps, m)
            self.delay[idx] = np.where(rng.random(m) < cfg.delay_mix, rng.integers(1, cfg.delay_max + 1, m), 1)
        else:
            self.cost[idx], self.slip[idx], self.delay[idx] = cfg.cost_bps[0], cfg.slip_bps[0], 1

    def _obs(self):
        k = self.k0 + self.t
        side = self.side
        hold = np.where(side != 0, (self.store.times[k] - self.t_ns[self.si[:, A_ENTRY_I]]) / MINUTE_NS, 0.0)
        a = self.acc
        account = np.column_stack([side, np.log1p(hold), a[:, UNREAL] / 100, a[:, MAE] / 100,
                                   (a[:, PEAK] - a[:, CUM]) / 100, a[:, MDD] / 100,
                                   (self.config.episode_steps - self.t) / self.config.episode_steps])
        missing = self.store.mask_missing[k]
        self.mask = np.column_stack([np.ones(self.n, bool), ~missing | (side == 1), ~missing | (side == -1)])  # C7
        return (self.store.seq[k], np.concatenate([self.store.static[k], account.astype(np.float32)], axis=1),
                self.mask.copy())

    def reset(self):
        self._reset(np.arange(self.n))
        return self._obs()

    def step(self, actions):
        a = np.asarray(actions)
        if a.shape != (self.n,) or ((a < 0) | (a > 2)).any() or not self.mask[np.arange(self.n), a].all():
            raise ValueError("action outside {0, 1, 2} or masked (C7)")
        k = self.k0 + self.t
        last = int(self.t[0]) == self.config.episode_steps - 1       # synchronized episodes
        _step(SIDES[a].astype(np.int64), last, self.store.times[k], self.m_lo[k], self.m_lo[k + 1], self.delay,
              self.cost / 2, self.slip, self.si, self.sf, self.acc, self.t_ns, self.o, self.h, self.l, self.c,
              self.fund_ns, self.fund_rate, self.out, self.minute_net)
        out = self.out
        net = out[:, NET].copy()
        loss, dd = 2 * np.maximum(0.0, -net), out[:, DMDD].copy()
        reward = net - loss - dd                                     # frozen: r = net - 2 max(0, -net) - dMDD
        info = {"net": net, "loss_penalty": loss, "dd_penalty": dd, "fees": out[:, FEES].copy(),
                "slippage": out[:, SLIP].copy(), "funding": out[:, FUND].copy(),
                "trades": out[:, TRADES].astype(np.int64), "minute_net": self.minute_net.copy()}
        self.t += 1
        done = self.t == self.config.episode_steps
        if done.any():
            self._reset(np.flatnonzero(done))
        return (*self._obs(), reward, net, done, info)


def replay(actions: pd.Series, minutes: pd.DataFrame, start, end, cost_bps: float, delay: int,
           slip: float) -> SimResult:
    """Deterministic evaluation with the env's rules: target sides indexed by decision time, flat start, the last
    15-minute step's action dropped, any open position closed at the last minute's close with exit fee and slippage."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    m = minutes[(minutes.open_time >= start) & (minutes.open_time < end)].reset_index(drop=True)
    actions = actions.sort_index()
    keep = (actions.index >= start) & (actions.index < end - pd.Timedelta(minutes=STEP_MIN))
    rows = pd.DataFrame({"decision_time": actions.index[keep], "side": actions.to_numpy()[keep].astype(int)})
    cfg = SimConfig(delay_min=int(delay), reentry="stop_and_reverse", fee_per_side=float(cost_bps) / 2,
                    market_slippage_bps=float(slip), action_mode=True)
    r = core.simulate(rows, m, start, end, cfg)
    p = r.open_position
    if p is None:
        return r
    side, last, close = p["side"], m.open_time.iloc[-1], float(m.close.iloc[-1])
    price = close * (1 - side * cfg.market_slippage_bps / 1e4)
    r.minute_pnl.iloc[-1] += -cfg.fee_per_side + side * math.log(price / close) * 1e4
    funding = sum(v for _, v in costs.funding_events(side, p["entry_time"], last + pd.Timedelta(1, "ns")))
    gross, fee = side * math.log(price / p["avg_price"]) * 1e4, 2 * cfg.fee_per_side
    trade = {"decision_time": p["decision_time"], "entry_time": p["entry_time"], "exit_time": last, "side": side,
             "units": 1.0, "entry_price": p["avg_price"], "exit_price": price, "exit_reason": "data_end",
             "gross_bps": gross, "fee_bps": fee, "funding_bps": funding, "net_bps": gross - fee + funding,
             "position_id": p["position_id"]}
    return SimResult(pd.DataFrame(r.trades.to_dict("records") + [trade], columns=TRADE_COLUMNS), r.minute_pnl)
