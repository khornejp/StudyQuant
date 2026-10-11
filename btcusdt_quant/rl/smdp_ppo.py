"""SMDP PPO pieces for the single-position maker kernel (Codex 2026-10-11). Duration-aware GAE: a decision held for
d minutes discounts by gamma(d) = exp(-ln2 d / 30 d) (maker_kernel.gamma); the within-step reward is already
discounted per 5-minute block (step_reward.reward_discounted). No fixed-gamma path."""
from __future__ import annotations
import torch


def compute_gae_smdp(r_disc: torch.Tensor, values: torch.Tensor, dones: torch.Tensor, last_v: torch.Tensor,
                     gamma_d: torch.Tensor, lam: float):
    """[T, N] tensors. delta_t = r_t + gamma_d_t (1 - done_t) V(s_{t+1}) - V(s_t);
    A_t = delta_t + gamma_d_t lam (1 - done_t) A_{t+1}; returns (advantages, returns = A + V)."""
    T = r_disc.shape[0]
    adv = torch.zeros_like(r_disc)
    nxt_v, nxt_a = last_v, torch.zeros_like(last_v)
    for t in range(T - 1, -1, -1):
        nd = 1.0 - dones[t]
        delta = r_disc[t] + gamma_d[t] * nd * nxt_v - values[t]
        nxt_a = delta + gamma_d[t] * lam * nd * nxt_a
        adv[t] = nxt_a
        nxt_v = values[t]
    return adv, adv + values


# ---------------------------------------------------------------- policy / trainer (smoke scale)
import copy, hashlib, io  # noqa: E402
from dataclasses import dataclass  # noqa: E402
import numpy as np  # noqa: E402
from torch import nn  # noqa: E402
from . import maker_kernel as MK  # noqa: E402


@dataclass(frozen=True)
class SmdpConfig:
    lr: float = 3e-4
    lam: float = 0.95
    clip: float = 0.2
    vclip: float = 0.2
    epochs: int = 4
    minibatch: int = 1200
    reward_scale: float = 0.01
    rollout: int = 100
    updates: int = 34
    envs_per_cell: int = 10
    episode_days: int = 90
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    hidden: int = 256


class SmdpPolicy(nn.Module):
    def __init__(self, obs_dim: int, n_target: int, n_wait: int, hidden: int = 256):
        super().__init__()
        self.trunk = nn.Sequential(nn.Linear(obs_dim, hidden), nn.Tanh(), nn.Linear(hidden, hidden), nn.Tanh())
        self.pt, self.pw, self.v = nn.Linear(hidden, n_target), nn.Linear(hidden, n_wait), nn.Linear(hidden, 1)
        with torch.no_grad():
            for hd in (self.pt, self.pw):
                hd.weight.mul_(0.01)
                hd.bias.zero_()

    def forward(self, x):
        z = self.trunk(x)
        return self.pt(z), self.pw(z), self.v(z).squeeze(-1)


def model_sha(m: nn.Module) -> str:
    buf = io.BytesIO()
    torch.save({k: v.detach().cpu() for k, v in m.state_dict().items()}, buf)
    return hashlib.sha256(buf.getvalue()).hexdigest()


ACC_KEYS = ("net4", "idle", "turnover", "reward", "reward_discounted", "gamma_d", "blocks", "flat_blocks", "minutes",
            "flat_minutes", "exposure_sum", "fills", "round_trips", "ttl_expiry", "requote", "reversal", "pos_stop",
            "day_stop", "fees", "funding", "stop_size_sum", "stop_entry_to_stop_min_sum", "stop_flatten_loss_sum",
            "stop_flattens", "stop_reentry_min_sum", "stop_reentries")


class SmdpTrainer:
    def __init__(self, envs, cfg: SmdpConfig, seed: int):
        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(True)
        self.envs, self.cfg, self.seed = envs, cfg, seed
        self.model = SmdpPolicy(envs.d.obs_dim, len(envs.targets), len(MK.WAITS), cfg.hidden)
        self.opt = torch.optim.Adam(self.model.parameters(), lr=cfg.lr)
        self.gen = torch.Generator().manual_seed(seed)
        self.update = 0
        self.obs = envs.obs()

    def state_dict(self) -> dict:
        return {"model": copy.deepcopy(self.model.state_dict()), "opt": copy.deepcopy(self.opt.state_dict()),
                "gen": self.gen.get_state(), "update": self.update, "obs": self.obs.copy(),
                "envs": copy.deepcopy(self.envs.state_dict())}

    def load_state_dict(self, sd: dict) -> None:
        self.model.load_state_dict(sd["model"])
        self.opt.load_state_dict(sd["opt"])
        self.gen.set_state(sd["gen"])
        self.update, self.obs = sd["update"], sd["obs"].copy()
        self.envs.load_state_dict(copy.deepcopy(sd["envs"]))

    def run_update(self) -> dict:
        cfg, E = self.cfg, self.envs.E
        B = {k: [] for k in ("obs", "at", "aw", "logp", "v", "r", "g", "done")}
        lg = {"nonfinite": 0, "identity_err": 0.0, "u_max": -9.0, "u_absmax": 0.0, "last_time": -1}
        acc = {k: 0.0 for k in ACC_KEYS}
        per_cell = {}
        t_cnt, w_cnt = np.zeros(len(self.envs.targets)), np.zeros(len(MK.WAITS))
        with torch.no_grad():
            for _ in range(cfg.rollout):
                x = torch.as_tensor(self.obs)
                lg["nonfinite"] += int((~torch.isfinite(x)).sum())
                lt, lw, v = self.model(x)
                at = torch.multinomial(torch.softmax(lt, -1), 1, generator=self.gen).squeeze(1)
                aw = torch.multinomial(torch.softmax(lw, -1), 1, generator=self.gen).squeeze(1)
                lp = (torch.log_softmax(lt, -1).gather(1, at[:, None]).squeeze(1)
                      + torch.log_softmax(lw, -1).gather(1, aw[:, None]).squeeze(1))
                infos = self.envs.step(at.numpy(), aw.numpy())
                for e, f in enumerate(infos):
                    for k in acc:
                        acc[k] += f[k]
                    c = self.envs.cells[e]
                    pc = per_cell.setdefault(f"o{c[0]}_p{c[1]}", {"fills": 0.0, "round_trips": 0.0})
                    pc["fills"] += f["fills"]
                    pc["round_trips"] += f["round_trips"]
                    lg["identity_err"] = max(lg["identity_err"], f["identity_err"])
                    lg["u_max"] = max(lg["u_max"], f["u_max"])
                    lg["u_absmax"] = max(lg["u_absmax"], f["u_absmax"])
                    lg["last_time"] = max(lg["last_time"], f["last_time"])
                np.add.at(t_cnt, at.numpy(), 1)
                np.add.at(w_cnt, aw.numpy(), 1)
                for k_, val in (("obs", x), ("at", at), ("aw", aw), ("logp", lp), ("v", v)):
                    B[k_].append(val)
                B["r"].append(torch.as_tensor([f["reward_discounted"] for f in infos], dtype=torch.float32))
                B["g"].append(torch.as_tensor([f["gamma_d"] for f in infos], dtype=torch.float32))
                B["done"].append(torch.as_tensor([float(f["done"]) for f in infos], dtype=torch.float32))
                self.obs = self.envs.obs()
            last_v = self.model(torch.as_tensor(self.obs))[2]
        b = {k: torch.stack(v) for k, v in B.items()}
        lg["nonfinite"] += int((~torch.isfinite(b["v"])).sum() + (~torch.isfinite(b["logp"])).sum())
        adv, ret = compute_gae_smdp(b["r"] * cfg.reward_scale, b["v"], b["done"], last_v, b["g"], cfg.lam)
        f = {k: b[k].flatten(0, 1) for k in ("obs", "at", "aw", "logp", "v")}
        a = adv.flatten()
        f["adv"] = (a - a.mean()) / (a.std(unbiased=False) + 1e-8)
        f["ret"] = ret.flatten()
        lg.update(self._ppo(f))
        self.update += 1
        n = cfg.rollout * E
        lg.update(acc)
        lg.update(update=self.update, transitions=self.update * n,
                  flat_minute_ratio=acc["flat_minutes"] / max(acc["minutes"], 1),
                  flat_block_ratio=acc["flat_blocks"] / max(acc["blocks"], 1),
                  exposure=acc["exposure_sum"] / max(acc["minutes"], 1), gamma_d_mean=acc["gamma_d"] / n,
                  target_counts=t_cnt.tolist(), wait_counts=w_cnt.tolist(), per_cell=per_cell)
        return lg

    def _ppo(self, f: dict) -> dict:
        cfg = self.cfg
        n = len(f["at"])
        st = {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0, "approx_kl": 0.0, "clip_frac": 0.0,
              "grad_norm": 0.0}
        k = 0
        for _ in range(cfg.epochs):
            perm = torch.randperm(n, generator=self.gen)
            for i in range(0, n - cfg.minibatch + 1, cfg.minibatch):
                idx = perm[i:i + cfg.minibatch]
                lt, lw, v = self.model(f["obs"][idx])
                plt, plw = torch.log_softmax(lt, -1), torch.log_softmax(lw, -1)
                lp = plt.gather(1, f["at"][idx][:, None]).squeeze(1) + plw.gather(1, f["aw"][idx][:, None]).squeeze(1)
                ent = (-(plt.exp() * plt).sum(-1) - (plw.exp() * plw).sum(-1)).mean()
                lr_ = lp - f["logp"][idx]
                ratio = lr_.exp()
                adv = f["adv"][idx]
                pg = -torch.min(ratio * adv, ratio.clamp(1 - cfg.clip, 1 + cfg.clip) * adv).mean()
                v_old, ret = f["v"][idx], f["ret"][idx]
                vc = v_old + (v - v_old).clamp(-cfg.vclip, cfg.vclip)
                vl = 0.5 * torch.max((v - ret) ** 2, (vc - ret) ** 2).mean()
                loss = pg + cfg.vf_coef * vl - cfg.ent_coef * ent
                self.opt.zero_grad()
                loss.backward()
                gn = nn.utils.clip_grad_norm_(self.model.parameters(), cfg.max_grad_norm)
                self.opt.step()
                with torch.no_grad():
                    st["policy_loss"] += float(pg)
                    st["value_loss"] += float(vl)
                    st["entropy"] += float(ent)
                    st["approx_kl"] += float(((ratio - 1) - lr_).mean())
                    st["clip_frac"] += float(((ratio - 1).abs() > cfg.clip).float().mean())
                    st["grad_norm"] += float(gn)
                k += 1
        out = {kk: vv / max(k, 1) for kk, vv in st.items()}
        out["explained_var"] = float(1 - (f["ret"] - f["v"]).var() / f["ret"].var())
        out["grad_steps"] = k
        return out

    def validate(self, data, cells, start: str, end: str) -> dict:
        """Deterministic argmax, one continuous flat-start episode per cell over [start, end); cells advance
        independently (one batched forward per iteration over the unfinished cells)."""
        from .smdp_env import SmdpEnvs
        ev = SmdpEnvs(data, cells, self.envs.targets, 1, seed=0)
        a, b = (pd_ts(x) for x in (start, end))
        for e in range(ev.E):
            ev._reset(e, a, b)
        live = np.ones(ev.E, bool)
        acc = [{k: 0.0 for k in ACC_KEYS} | {"u_max": -9.0, "u_absmax": 0.0, "identity_err": 0.0, "nonfinite": 0,
                                           "last_time": -1,
                                           "t_cnt": np.zeros(len(ev.targets)), "w_cnt": np.zeros(len(MK.WAITS)),
                                           "decisions": 0} for _ in range(ev.E)]
        daily = [dict() for _ in range(ev.E)]
        with torch.no_grad():
            while live.any():
                idx = np.flatnonzero(live)
                x = torch.as_tensor(ev.obs(idx))
                lt, lw, _ = self.model(x)
                at, aw = lt.argmax(-1).numpy(), lw.argmax(-1).numpy()
                for n, e in enumerate(idx):
                    k = ev.kern[e]
                    i0 = k.i
                    f = ev.step_one(e, int(at[n]), int(aw[n]))
                    r = acc[e]
                    r["nonfinite"] += int((~torch.isfinite(x[n])).sum())
                    for kk in ACC_KEYS:
                        r[kk] += f[kk]
                    r["u_max"], r["u_absmax"] = max(r["u_max"], f["u_max"]), max(r["u_absmax"], f["u_absmax"])
                    r["identity_err"] = max(r["identity_err"], f["identity_err"])
                    r["last_time"] = max(r["last_time"], f["last_time"])
                    r["t_cnt"][at[n]] += 1
                    r["w_cnt"][aw[n]] += 1
                    r["decisions"] += 1
                    seg = k.pnl[i0 + 1:k.i + 1]
                    days = k.day[i0 + 1:k.i + 1]
                    for dd_ in np.unique(days):
                        daily[e][int(dd_)] = daily[e].get(int(dd_), 0.0) + float(seg[days == dd_].sum())
                    if f["done"]:
                        live[e] = False
        out = {}
        for e, c in enumerate(cells):
            r = acc[e]
            dser = np.array([daily[e][k_] for k_ in sorted(daily[e])])
            eq = np.r_[0.0, np.cumsum(dser)]
            out[f"o{c[0]}_p{c[1]}"] = {**{kk: (vv.tolist() if isinstance(vv, np.ndarray) else vv) for kk, vv in r.items()},
                                       "flat_minute_ratio": r["flat_minutes"] / max(r["minutes"], 1),
                                       "flat_block_ratio": r["flat_blocks"] / max(r["blocks"], 1),
                                       "exposure": r["exposure_sum"] / max(r["minutes"], 1),
                                       "mdd_daily": float((np.maximum.accumulate(eq) - eq).max())}
        return out


def pd_ts(x: str) -> int:
    import pandas as pd
    return pd.Timestamp(x, tz="UTC").value
