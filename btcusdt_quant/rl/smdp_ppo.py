"""SMDP PPO pieces for the single-position maker kernel (Codex 2026-10-11). Duration-aware GAE: a decision held for
d minutes discounts by gamma(d) = exp(-ln2 d / 30 d) (maker_kernel.gamma); the within-step reward is already
discounted per 5-minute block (step_reward.reward_discounted). No fixed-gamma path."""
from __future__ import annotations
import torch


def compute_gae_smdp(r_disc: torch.Tensor, values: torch.Tensor, dones: torch.Tensor, last_v: torch.Tensor,
                     gamma_d: torch.Tensor, lam):
    """[T, N] tensors. delta_t = r_t + gamma_d_t (1 - done_t) V(s_{t+1}) - V(s_t);
    A_t = delta_t + gamma_d_t lam (1 - done_t) A_{t+1}; returns (advantages, returns = A + V)."""
    T = r_disc.shape[0]
    adv = torch.zeros_like(r_disc)
    nxt_v, nxt_a = last_v, torch.zeros_like(last_v)
    for t in range(T - 1, -1, -1):
        nd = 1.0 - dones[t]
        delta = r_disc[t] + gamma_d[t] * nd * nxt_v - values[t]
        lt = lam[t] if torch.is_tensor(lam) else lam                 # A4: lambda_d = 0.95^(dt / 5 m) per step
        nxt_a = delta + gamma_d[t] * lt * nd * nxt_a
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


ACC_KEYS = ("net4", "idle", "inventory", "turnover", "reward", "reward_discounted", "gamma_d", "blocks", "flat_blocks",
            "minutes", "flat_minutes", "exposure_sum", "fills", "round_trips", "ttl_expiry", "requote", "reversal",
            "fees", "funding", "kill_count")


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
        return evaluate([self.model], data, cells, self.envs.targets, start, end)


def evaluate(models: list, data, cells, targets, start: str, end: str, waits=MK.WAITS) -> dict:
    """Deterministic policy over [start, end): one flat-start episode per cell, truncated at `end`. With several models
    the target logits and the wait logits are averaged across models before each argmax (seed ensemble)."""
    from .smdp_env import SmdpEnvs
    ev = SmdpEnvs(data, cells, targets, 1, seed=0, waits=waits)
    a, b = pd_ts(start), pd_ts(end)
    for e in range(ev.E):
        ev._reset(e, a, b)
    live = np.ones(ev.E, bool)
    acc = [{k: 0.0 for k in ACC_KEYS} | {"u_max": -9.0, "u_absmax": 0.0, "identity_err": 0.0, "nonfinite": 0,
                                       "last_time": -1, "t_cnt": np.zeros(len(ev.targets)),
                                       "w_cnt": np.zeros(len(ev.waits)), "decisions": 0} for _ in range(ev.E)]
    daily = [dict() for _ in range(ev.E)]
    with torch.no_grad():
        while live.any():
            idx = np.flatnonzero(live)
            x = torch.as_tensor(ev.obs(idx))
            outs = [m(x) for m in models]
            lt = torch.stack([o[0] for o in outs]).mean(0)
            lw = torch.stack([o[1] for o in outs]).mean(0)
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
    d0, d1 = a // 86_400_000_000_000, b // 86_400_000_000_000
    for e, c in enumerate(cells):
        r = acc[e]
        dser = np.array([daily[e].get(dd_, 0.0) for dd_ in range(d0, d1)])
        eq = np.r_[0.0, np.cumsum(dser)]
        out[f"o{c[0]}_p{c[1]}"] = {**{kk: (vv.tolist() if isinstance(vv, np.ndarray) else vv) for kk, vv in r.items()},
                                   "flat_minute_ratio": r["flat_minutes"] / max(r["minutes"], 1),
                                   "flat_block_ratio": r["flat_blocks"] / max(r["blocks"], 1),
                                   "exposure": r["exposure_sum"] / max(r["minutes"], 1),
                                   "mdd_daily": float((np.maximum.accumulate(eq) - eq).max()), "daily": dser.tolist()}
    return out


def pd_ts(x: str) -> int:
    import pandas as pd
    return pd.Timestamp(x, tz="UTC").value


# ---------------------------------------------------------------- A4 (Codex final): block episodes, 7-day rollouts, entropy floor
A4_WAITS = (15, 60, 240)
A4_TARGETS = (0.0, -0.25, -0.5, -0.75, -1.0)
A4_TARGETS_LONG = (0.0, 0.25, 0.5, 0.75, 1.0)
A5_TARGETS = (-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0)
TRACE_COLS = ("time", "cell_index", "seed", "rng", "expected_target", "sampled_target", "wait", "executed_U", "ret_24h_bps",
              "consensus")


def wrong_side(f: dict, side: int) -> bool:
    """Exposure on the forbidden side: short-only -> any long minute, long-only -> any short minute."""
    if side == 0:
        return False
    return f["u_max"] > 1e-12 if side < 0 else f["u_min"] < -1e-12
A4_ROLLOUT_MIN = 7 * 1440


@dataclass(frozen=True)
class A4Config:
    lr: float = 3e-4
    clip: float = 0.2
    vclip: float = 0.2
    epochs: int = 4
    minibatch: int = 512
    reward_scale: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    hidden: int = 64
    updates: int = 68
    rollout_min: int = A4_ROLLOUT_MIN
    lam_base: float = 0.95
    floor_beta_wait: float = 0.05
    floor_low: float = 0.55
    floor_release: float = 0.60
    collapse_h_wait: float = 0.30
    collapse_dominant: float = 0.95
    collapse_updates: int = 3
    target_betas: tuple = (0.010, 0.005, 0.002)          # A5: (0.00732, 0.00366, 0.00147)
    wait_betas: tuple = (0.020, 0.015, 0.010)


def a4_schedule(update: int) -> tuple[float, float]:
    """(beta_target, beta_wait) for a 1-based update."""
    if update <= 17:
        return 0.010, 0.020
    if update <= 34:
        return 0.005, 0.015
    return 0.002, 0.010


class EntropyFloor:
    """Wait-entropy floor: normalized wait entropy < 0.55 -> next update beta_wait = 0.05; back to the schedule after
    two consecutive updates with h_wait >= 0.60."""

    def __init__(self, cfg: A4Config):
        self.cfg, self.on, self.ok_run = cfg, False, 0

    def betas(self, update: int) -> tuple[float, float, bool]:
        k = 0 if update <= 17 else 1 if update <= 34 else 2
        bt, bw = self.cfg.target_betas[k], self.cfg.wait_betas[k]
        return bt, (self.cfg.floor_beta_wait if self.on else bw), self.on

    def observe(self, h_wait: float) -> None:
        if h_wait < self.cfg.floor_low:
            self.on, self.ok_run = True, 0
        elif self.on:
            self.ok_run = self.ok_run + 1 if h_wait >= self.cfg.floor_release else 0
            if self.ok_run >= 2:
                self.on, self.ok_run = False, 0


def lam_d(dt_min) -> float:
    return 0.95 ** (float(dt_min) / 5.0)


class A4Abort(RuntimeError):
    pass


class A4Trainer:
    def __init__(self, envs, cfg: A4Config, seed: int):
        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(True)
        self.envs, self.cfg, self.seed = envs, cfg, seed
        self.model = SmdpPolicy(envs.d.obs_dim, len(envs.targets), len(envs.waits), cfg.hidden)
        self.opt = torch.optim.Adam(self.model.parameters(), lr=cfg.lr)
        self.gen = torch.Generator().manual_seed(seed)
        self.update = 0
        self.floor = EntropyFloor(cfg)
        self.collapse_run = 0
        self.side = 0 if min(envs.targets) < 0 < max(envs.targets) else (1 if max(envs.targets) > 0 else -1)
        self.obs = envs.obs()

    def run_update(self) -> dict:
        cfg, ev = self.cfg, self.envs
        E = ev.E
        nT, nW = len(ev.targets), len(ev.waits)
        traj = [[] for _ in range(E)]
        elapsed = np.zeros(E)
        blocks_seen = []
        lg = {"nonfinite": 0, "identity_err": 0.0, "u_max": -9.0, "u_min": 9.0, "u_absmax": 0.0, "wrong_side": 0}
        acc = {k: 0.0 for k in ACC_KEYS}
        with torch.no_grad():
            live = np.ones(E, bool)
            while live.any():
                idx = np.flatnonzero(live)
                x = torch.as_tensor(ev.obs(idx))
                lg["nonfinite"] += int((~torch.isfinite(x)).sum())
                lt, lw, v = self.model(x)
                pt, pw = torch.softmax(lt, -1), torch.softmax(lw, -1)
                at = torch.multinomial(pt, 1, generator=self.gen).squeeze(1)
                aw = torch.multinomial(pw, 1, generator=self.gen).squeeze(1)
                lp = torch.log(pt.gather(1, at[:, None]).squeeze(1)) + torch.log(pw.gather(1, aw[:, None]).squeeze(1))
                for n, e in enumerate(idx):
                    binfo = ev.block_info(e)
                    f = ev.step_one(e, int(at[n]), int(aw[n]))
                    for k in acc:
                        acc[k] += f[k]
                    lg["identity_err"] = max(lg["identity_err"], f["identity_err"])
                    lg["u_max"] = max(lg["u_max"], f["u_max"])
                    lg["u_absmax"] = max(lg["u_absmax"], f["u_absmax"])
                    lg["u_min"] = min(lg["u_min"], f["u_min"])
                    lg["wrong_side"] += int(wrong_side(f, self.side))
                    dt = f["minutes"]
                    traj[e].append({"obs": x[n], "at": int(at[n]), "aw": int(aw[n]), "logp": float(lp[n]),
                                    "v": float(v[n]), "r": f["reward_discounted"], "reward": f["reward"],
                                    "g": f["gamma_d"], "l": lam_d(dt), "done": f["done"], "dt": dt,
                                    "pt": pt[n].numpy().copy(), "pw": pw[n].numpy().copy()})
                    elapsed[e] += dt
                    if f["done"]:
                        blocks_seen.append({"env": int(e), **binfo})
                        ev.advance_block(e)
                    if elapsed[e] >= cfg.rollout_min:
                        live[e] = False
            last_v = self.model(torch.as_tensor(ev.obs()))[2]
        if lg["nonfinite"] or lg["identity_err"] > 1e-8 or lg["wrong_side"] or lg["u_absmax"] > 1 + 1e-12:
            raise A4Abort(f"integrity abort: {lg}")
        # per-env duration-aware GAE (gamma_d, lambda_d per step)
        rows, advs, rets = [], [], []
        for e in range(E):
            tr = traj[e]
            if not tr:
                continue
            r = torch.tensor([[q["r"] * cfg.reward_scale] for q in tr], dtype=torch.float32)
            vv = torch.tensor([[q["v"]] for q in tr], dtype=torch.float32)
            dn = torch.tensor([[float(q["done"])] for q in tr], dtype=torch.float32)
            gd = torch.tensor([[q["g"]] for q in tr], dtype=torch.float32)
            ld = torch.tensor([[q["l"]] for q in tr], dtype=torch.float32)
            a_, r_ = compute_gae_smdp(r, vv, dn, last_v[e:e + 1], gd, ld)
            rows += tr
            advs.append(a_[:, 0])
            rets.append(r_[:, 0])
        adv, ret = torch.cat(advs), torch.cat(rets)
        f = {"obs": torch.stack([q["obs"] for q in rows]), "at": torch.tensor([q["at"] for q in rows]),
             "aw": torch.tensor([q["aw"] for q in rows]), "logp": torch.tensor([q["logp"] for q in rows]),
             "v": torch.tensor([q["v"] for q in rows]), "ret": ret}
        f["adv"] = (adv - adv.mean()) / (adv.std(unbiased=False) + 1e-8)
        self.update += 1
        bt, bw, floor_on = self.floor.betas(self.update)
        lg.update(self._ppo(f, bt, bw))
        # head statistics at sampling time
        PT, PW = np.stack([q["pt"] for q in rows]), np.stack([q["pw"] for q in rows])
        AT, AW = f["at"].numpy(), f["aw"].numpy()
        H_t = -(PT * np.log(np.clip(PT, 1e-12, 1))).sum(1)
        H_w = -(PW * np.log(np.clip(PW, 1e-12, 1))).sum(1)
        h_t, h_w = float(H_t.mean() / np.log(nT)), float(H_w.mean() / np.log(nW))
        wc = np.bincount(AW, minlength=nW)
        dom = float(wc.max() / wc.sum())
        self.floor.observe(h_w)
        if floor_on and (h_w < cfg.collapse_h_wait or dom > cfg.collapse_dominant):
            self.collapse_run += 1
        else:
            self.collapse_run = 0
        raw_adv = adv.numpy()
        nadv = f["adv"].numpy()
        rew = np.array([q["reward"] for q in rows])
        dts = np.array([q["dt"] for q in rows])
        per_wait = {}
        for j, w in enumerate(ev.waits):
            m = AW == j
            per_wait[str(w)] = ({"n": int(m.sum()), "adv_mean": float(raw_adv[m].mean()), "adv_std": float(raw_adv[m].std()),
                                 "adv_p05": float(np.percentile(raw_adv[m], 5)), "adv_p50": float(np.percentile(raw_adv[m], 50)),
                                 "adv_p95": float(np.percentile(raw_adv[m], 95)), "nadv_mean": float(nadv[m].mean()),
                                 "reward_mean": float(rew[m].mean()),
                                 "reward_per_5m": float(rew[m].sum() / max(dts[m].sum() / 5.0, 1e-9)),
                                 "gamma_d_mean": float(np.mean([q["g"] for q, mm in zip(rows, m) if mm])),
                                 "lambda_d_mean": float(np.mean([q["l"] for q, mm in zip(rows, m) if mm]))}
                                if m.any() else {"n": 0})
        heads = {"target": {"count": np.bincount(AT, minlength=nT).tolist(), "mean_prob": PT.mean(0).tolist(),
                            "argmax_share": (np.bincount(PT.argmax(1), minlength=nT) / len(PT)).tolist(),
                            "entropy_raw": float(H_t.mean()), "entropy_norm": h_t},
                 "wait": {"count": wc.tolist(), "mean_prob": PW.mean(0).tolist(),
                          "argmax_share": (np.bincount(PW.argmax(1), minlength=nW) / len(PW)).tolist(),
                          "entropy_raw": float(H_w.mean()), "entropy_norm": h_w, "dominant_share": dom}}
        lg.update(acc)
        lg.update(update=self.update, transitions=len(rows), elapsed_minutes=float(elapsed.sum()),
                  beta_target=bt, beta_wait=bw, floor_on=bool(floor_on), floor_next=bool(self.floor.on),
                  collapse_run=self.collapse_run, heads=heads, per_wait=per_wait, blocks_finished=blocks_seen,
                  flat_minute_ratio=acc["flat_minutes"] / max(acc["minutes"], 1),
                  exposure=acc["exposure_sum"] / max(acc["minutes"], 1))
        return lg

    def _ppo(self, f: dict, bt: float, bw: float) -> dict:
        cfg = self.cfg
        n = len(f["at"])
        st = {"policy_loss": 0.0, "value_loss": 0.0, "entropy_target": 0.0, "entropy_wait": 0.0, "approx_kl": 0.0,
              "clip_frac": 0.0, "grad_norm": 0.0}
        k = 0
        for _ in range(cfg.epochs):
            perm = torch.randperm(n, generator=self.gen)
            for i in range(0, n, cfg.minibatch):
                idx = perm[i:i + cfg.minibatch]
                if len(idx) < 2:
                    continue
                lt, lw, v = self.model(f["obs"][idx])
                plt, plw = torch.log_softmax(lt, -1), torch.log_softmax(lw, -1)
                lp = plt.gather(1, f["at"][idx][:, None]).squeeze(1) + plw.gather(1, f["aw"][idx][:, None]).squeeze(1)
                et, ew = -(plt.exp() * plt).sum(-1).mean(), -(plw.exp() * plw).sum(-1).mean()
                lr_ = lp - f["logp"][idx]
                ratio = lr_.exp()
                adv = f["adv"][idx]
                pg = -torch.min(ratio * adv, ratio.clamp(1 - cfg.clip, 1 + cfg.clip) * adv).mean()
                v_old, ret = f["v"][idx], f["ret"][idx]
                vc = v_old + (v - v_old).clamp(-cfg.vclip, cfg.vclip)
                vl = 0.5 * torch.max((v - ret) ** 2, (vc - ret) ** 2).mean()
                loss = pg + cfg.vf_coef * vl - bt * et - bw * ew
                self.opt.zero_grad()
                loss.backward()
                gn = nn.utils.clip_grad_norm_(self.model.parameters(), cfg.max_grad_norm)
                self.opt.step()
                with torch.no_grad():
                    st["policy_loss"] += float(pg)
                    st["value_loss"] += float(vl)
                    st["entropy_target"] += float(et)
                    st["entropy_wait"] += float(ew)
                    st["approx_kl"] += float(((ratio - 1) - lr_).mean())
                    st["clip_frac"] += float(((ratio - 1).abs() > cfg.clip).float().mean())
                    st["grad_norm"] += float(gn)
                k += 1
        out = {kk: vv / max(k, 1) for kk, vv in st.items()}
        out["explained_var"] = float(1 - (f["ret"] - f["v"]).var() / f["ret"].var())
        out["grad_steps"] = k
        return out


def evaluate_sampled(models: dict, data, cells, targets, waits, start: str, end: str, rng_seeds, trace=None) -> dict:
    """A4 evaluation: for every training seed s (models[s]) x action RNG seed r x cell, one flat-start trajectory
    over [start, end) with categorical sampling of both heads (numpy Generator seeded with (r, s, cell index))."""
    from .smdp_env import SmdpEnvs
    keys = [(s, r, ci) for s in models for r in rng_seeds for ci in range(len(cells))]
    ev = SmdpEnvs(data, [cells[ci] for _, _, ci in keys], targets, 1, seed=0, waits=waits)
    a, b = pd_ts(start), pd_ts(end)
    for e in range(ev.E):
        ev._reset(e, a, b)
    rngs = [np.random.default_rng([r, s, ci]) for s, r, ci in keys]
    live = np.ones(ev.E, bool)
    acc = [{k: 0.0 for k in ACC_KEYS} | {"u_max": -9.0, "u_min": 9.0, "u_absmax": 0.0, "identity_err": 0.0,
                                       "nonfinite": 0, "last_time": -1, "t_cnt": np.zeros(len(targets)),
                                       "w_cnt": np.zeros(len(waits)), "decisions": 0} for _ in range(ev.E)]
    d0, d1 = a // 86_400_000_000_000, b // 86_400_000_000_000
    daily = np.zeros((ev.E, d1 - d0))
    seeds_of = np.array([s for s, _, _ in keys])
    with torch.no_grad():
        while live.any():
            for s in models:
                idx = np.flatnonzero(live & (seeds_of == s))
                if not len(idx):
                    continue
                x = torch.as_tensor(ev.obs(idx))
                lt, lw, _ = models[s](x)
                pt, pw = torch.softmax(lt, -1).numpy(), torch.softmax(lw, -1).numpy()
                for n, e in enumerate(idx):
                    g = rngs[e]
                    at = int(min(np.searchsorted(np.cumsum(pt[n]), g.random(), "right"), len(targets) - 1))
                    aw = int(min(np.searchsorted(np.cumsum(pw[n]), g.random(), "right"), len(waits) - 1))
                    k = ev.kern[e]
                    i0 = k.i
                    if trace is not None:
                        gi = ev.s0[e] + i0
                        c_ = data.c
                        r24 = (c_[gi] / c_[gi - 1440] - 1.0) * 1e4 if gi >= 1440 else np.nan
                        row = data.row(int(ev.t_now[e]))
                        sd = data.tok[row].reshape(-1, 20)
                        av = sd[:, 5] > 0
                        cons = float(sd[av, 0].mean()) if av.any() else 0.0
                        trace.append((int(ev.t_now[e]), keys[e][2], keys[e][0], keys[e][1],
                                      float(np.dot(pt[n], np.asarray(targets))), float(targets[at]), int(waits[aw]),
                                      float(k.st[MK.S_U]), float(r24), cons))
                    f = ev.step_one(e, at, aw)
                    r_ = acc[e]
                    r_["nonfinite"] += int((~torch.isfinite(x[n])).sum())
                    for kk in ACC_KEYS:
                        r_[kk] += f[kk]
                    r_["u_max"], r_["u_absmax"] = max(r_["u_max"], f["u_max"]), max(r_["u_absmax"], f["u_absmax"])
                    r_["u_min"] = min(r_["u_min"], f["u_min"])
                    r_["identity_err"] = max(r_["identity_err"], f["identity_err"])
                    r_["last_time"] = max(r_["last_time"], f["last_time"])
                    r_["t_cnt"][at] += 1
                    r_["w_cnt"][aw] += 1
                    r_["decisions"] += 1
                    seg = k.pnl[i0 + 1:k.i + 1]
                    days = k.day[i0 + 1:k.i + 1] - d0
                    np.add.at(daily[e], days, seg)
                    if f["done"]:
                        live[e] = False
    out = {}
    for e, (s, r, ci) in enumerate(keys):
        c = cells[ci]
        out[(s, r, f"o{c[0]}_p{c[1]}")] = {**{kk: (vv.tolist() if isinstance(vv, np.ndarray) else vv)
                                               for kk, vv in acc[e].items()}, "daily": daily[e]}
    return out
