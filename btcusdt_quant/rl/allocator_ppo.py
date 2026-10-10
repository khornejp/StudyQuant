"""Vector-action PPO for the RL allocator (Codex design section 5, Step 5). Uses ppo.compute_gae unchanged; the old
single-head ppo.ppo_update/train stay as they are for their existing callers.

  * PooledEnv: one VecAllocatorEnv per execution cell (envs split across cells), random contiguous episodes inside
    the fold train window, synchronous auto-reset; state_dict covers env books, episode RNG and the last observation.
  * rollout -> GAE (reward_scale 0.01, bps -> percent for the learner) -> clipped PPO with value clipping over the
    joint log-prob of the active heads; entropy = mean over active heads.
  * validate(): deterministic argmax, one continuous episode per cell over the validation window, static baseline =
    the fold's frozen static weights; key = worst-cell validation excess (net_rl - net_static); an all-flat policy is
    never promoted.
Everything that evolves (model, optimizer, env, numpy/torch/CUDA RNG, progress) is in Trainer.state_dict, so a split
run resumed from a checkpoint equals an uninterrupted run exactly."""
from __future__ import annotations
import copy, math, os
from dataclasses import asdict, dataclass
import numpy as np
import pandas as pd
import torch
from torch import nn
from . import allocator_contracts as C
from . import allocator_vec_env as AV
from .allocator_model import AllocatorActorCritic, joint
from .ppo import compute_gae

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
HOUR = 3600 * 10**9
OBS_KEYS = ("seq", "seq_nan", "seq_pad", "static", "account")


@dataclass(frozen=True)
class AllocPPOConfig:
    gamma: float = 0.999
    lam: float = 0.95
    clip: float = 0.2
    vclip: float = 0.2
    n_steps: int = 128
    minibatch: int = 2048
    epochs: int = 4
    vf_coef: float = 0.5
    ent_coef: float = 0.01
    max_grad_norm: float = 0.5
    weight_decay: float = 1e-4
    lr: float = 3e-4
    hidden: int = 64
    reward_scale: float = 0.01
    episode_steps: int = 2160


def reward_parts(info: dict):
    dd = C.DD_PENALTY * np.maximum(0.0, info["dmdd_rl"] - info["dmdd_st"])
    to = C.TURNOVER_PENALTY * np.maximum(0.0, info["turnover_rl"] - info["turnover_st"])
    return info["net_rl"] - info["net_st"], dd, to


class PooledEnv:
    def __init__(self, cells: dict, counts: dict, static_w, train: tuple, cfg: AllocPPOConfig, seed: int):
        self.order = list(counts)
        self.counts = counts
        self.envs = {c: AV.VecAllocatorEnv(cells[c], counts[c], static_weights=static_w) for c in self.order}
        self.a, self.b = (pd.Timestamp(x, tz="UTC").value for x in train)
        self.L = cfg.episode_steps
        self.rng = np.random.default_rng(seed)
        self.n = sum(counts.values())
        self.obs = {c: self._reset(c) for c in self.order}

    def _reset(self, c):
        hi = (self.b - self.a) // HOUR - self.L                    # last start so the episode ends <= train end
        starts = self.a + HOUR * self.rng.integers(0, hi + 1, self.counts[c])
        return self.envs[c].reset(starts, self.L)

    def observation(self) -> dict:
        o = {k: np.concatenate([self.obs[c][k] for c in self.order]) for k in OBS_KEYS}
        o["m_entry"] = np.concatenate([self.obs[c]["masks"][0] for c in self.order])
        o["m_open"] = np.concatenate([self.obs[c]["masks"][2] for c in self.order])
        o["m_pending"] = np.concatenate([self.obs[c]["masks"][1] for c in self.order])
        return o

    def step(self, entry, open_):
        rew, done, infos, i = [], [], [], 0
        for c in self.order:
            n = self.counts[c]
            o, r, d, info = self.envs[c].step(entry[i:i + n], np.zeros((n, len(C.SLEEVES)), np.int64), open_[i:i + n])
            rew.append(r)
            done.append(np.full(n, d))
            infos.append(info)
            self.obs[c] = self._reset(c) if d else o
            i += n
        info = {k: np.concatenate([x[k] for x in infos]) for k in infos[0]}
        return np.concatenate(rew), np.concatenate(done), info

    def state_dict(self) -> dict:
        return {"envs": {c: e.state_dict() for c, e in self.envs.items()}, "rng": copy.deepcopy(self.rng.bit_generator.state),
                "obs": copy.deepcopy(self.obs)}

    def load_state_dict(self, st: dict) -> None:
        for c, e in self.envs.items():
            e.load_state_dict(st["envs"][c])
        self.rng.bit_generator.state = copy.deepcopy(st["rng"])
        self.obs = copy.deepcopy(st["obs"])


def to_t(o: dict, device) -> dict:
    t = {k: torch.as_tensor(o[k], device=device) for k in OBS_KEYS}
    t["m_entry"] = torch.as_tensor(o["m_entry"], device=device)
    t["m_open"] = torch.as_tensor(o["m_open"], device=device)
    return t


def forward(model, t: dict):
    return model(t["seq"], t["seq_nan"], t["seq_pad"], t["static"], t["account"], t["m_entry"], t["m_open"])


def sample(logits: torch.Tensor, gen: torch.Generator | None = None) -> torch.Tensor:
    p = torch.softmax(logits, -1).flatten(0, 1)
    return torch.multinomial(p, 1, generator=gen).view(logits.shape[:2])


class Trainer:
    def __init__(self, cells: dict, counts: dict, static_w, train: tuple, val: tuple, cfg: AllocPPOConfig,
                 seed: int, device: str | None = None):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.backends.cudnn.benchmark = False
        torch.manual_seed(seed)
        if self.device.type == "cuda":
            torch.cuda.manual_seed(seed)
        self.cfg, self.seed, self.cells, self.static_w, self.val_win = cfg, seed, cells, np.asarray(static_w, float), val
        self.env = PooledEnv(cells, counts, static_w, train, cfg, seed)
        self.model = AllocatorActorCritic(hidden=cfg.hidden, static_weights=static_w).to(self.device)
        self.opt = torch.optim.AdamW(self.model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
        self.update = 0

    # ---------------------------------------------------------------- state
    def state_dict(self) -> dict:
        return {"model": copy.deepcopy(self.model.state_dict()), "opt": copy.deepcopy(self.opt.state_dict()),
                "env": self.env.state_dict(), "update": self.update, "torch_rng": torch.get_rng_state(),
                "cuda_rng": torch.cuda.get_rng_state(self.device) if self.device.type == "cuda" else None,
                "cfg": asdict(self.cfg), "seed": self.seed, "model_args": self.model.model_args}

    def load_state_dict(self, st: dict) -> None:
        if st["cfg"] != asdict(self.cfg) or st["seed"] != self.seed:
            raise ValueError("checkpoint config/seed mismatch")
        self.model.load_state_dict(st["model"])
        self.opt.load_state_dict(st["opt"])
        self.env.load_state_dict(st["env"])
        self.update = st["update"]
        torch.set_rng_state(st["torch_rng"])
        if st["cuda_rng"] is not None:
            torch.cuda.set_rng_state(st["cuda_rng"], self.device)

    # ---------------------------------------------------------------- one update
    def run_update(self) -> dict:
        cfg, dev, env = self.cfg, self.device, self.env
        keys = OBS_KEYS + ("m_entry", "m_open")
        buf = {k: [] for k in keys + ("ae", "ao", "logp", "values", "rewards", "dones")}
        log = {"illegal": 0, "nonfinite": 0, "gross_open_max": 0.0, "gross_reserved_max": 0.0, "identity_err": 0.0,
               "net_rl": 0.0, "net_static": 0.0, "net_excess": 0.0, "dd_pen": 0.0, "to_pen": 0.0, "reward": 0.0,
               "turnover_rl": 0.0, "cap_scaled": 0, "new_alloc": 0, "alloc_sum": 0.0}
        before = {k: np.concatenate([getattr(e.rl, k) for e in env.envs.values()]) for k in ("cap_scaled", "new_alloc",
                                                                                            "alloc_sum")}
        with torch.no_grad():
            for _ in range(cfg.n_steps):
                o = env.observation()
                log["nonfinite"] += int(sum((~np.isfinite(o[k])).sum() for k in OBS_KEYS))
                t = to_t(o, dev)
                le, lo, v = forward(self.model, t)
                ae, ao = sample(le), sample(lo)
                lp, _, _ = joint(le, lo, t["m_entry"], t["m_open"], ae, ao)
                legal = t["m_entry"].gather(2, ae.unsqueeze(2)).all() and t["m_open"].gather(2, ao.unsqueeze(2)).all()
                log["illegal"] += int(not bool(legal))
                log["nonfinite"] += int((~torch.isfinite(v)).sum()) + int((~torch.isfinite(lp)).sum())
                rew, done, info = env.step(ae.cpu().numpy().astype(np.int64), ao.cpu().numpy().astype(np.int64))
                ex, dd, to = reward_parts(info)
                log["identity_err"] = max(log["identity_err"], float(np.abs(rew - (ex - dd - to)).max()))
                for k_, x in (("net_rl", info["net_rl"]), ("net_static", info["net_st"]), ("net_excess", ex),
                              ("dd_pen", dd), ("to_pen", to), ("reward", rew), ("turnover_rl", info["turnover_rl"])):
                    log[k_] += float(np.sum(x))
                log["gross_open_max"] = max(log["gross_open_max"], float(info["gross_open"].max()))
                log["gross_reserved_max"] = max(log["gross_reserved_max"], float(info["gross_reserved"].max()))
                for k_ in keys:
                    buf[k_].append(t[k_])
                buf["ae"].append(ae)
                buf["ao"].append(ao)
                buf["logp"].append(lp)
                buf["values"].append(v)
                buf["rewards"].append(torch.as_tensor(rew, dtype=torch.float32, device=dev))
                buf["dones"].append(torch.as_tensor(done, dtype=torch.float32, device=dev))
            last_v = forward(self.model, to_t(env.observation(), dev))[2]
        after = {k: np.concatenate([getattr(e.rl, k) for e in env.envs.values()]) for k in before}
        for k in before:
            d = after[k] - before[k]
            log[k] = float(np.where(d >= 0, d, after[k]).sum())       # an episode reset restarts the counters
        b = {k: torch.stack(x) for k, x in buf.items()}
        adv, ret = compute_gae(b["rewards"] * cfg.reward_scale, b["values"], b["dones"], last_v, cfg.gamma, cfg.lam)
        flat = {k: b[k].flatten(0, 1) for k in keys + ("ae", "ao", "logp", "values")}
        flat["adv"], flat["ret"] = adv.flatten(), ret.flatten()
        log.update(self._policy_stats(flat))
        log.update(self._ppo(flat))
        self.update += 1
        log["update"] = self.update
        log["transitions"] = self.update * cfg.n_steps * env.n
        return log

    def _policy_stats(self, f: dict) -> dict:
        """Action ratios / entropies per sleeve and head over active samples (denominator reported)."""
        out = {"heads": {}}
        with torch.no_grad():
            le, lo = [], []
            for i in range(0, len(f["ae"]), 4096):
                t = {k: f[k][i:i + 4096] for k in OBS_KEYS + ("m_entry", "m_open")}
                a, b_, _ = forward(self.model, t)
                le.append(a)
                lo.append(b_)
            le, lo = torch.cat(le), torch.cat(lo)
            _, ent, (ene, ace, eno, aco) = joint(le, lo, f["m_entry"], f["m_open"], f["ae"], f["ao"])
        n_e = ace.sum(0).cpu().numpy()
        n_o = aco.sum(0).cpu().numpy()
        for k, s in enumerate(C.SLEEVES):
            ae = f["ae"][:, k][ace[:, k]].cpu().numpy()
            ao = f["ao"][:, k][aco[:, k]].cpu().numpy()
            out["heads"][s] = {
                "entry_active": int(n_e[k]),
                "entry_ratio": {str(C.LEVELS[j]): float((ae == j).mean()) if len(ae) else None for j in range(len(C.LEVELS))},
                "entry_entropy": float(ene[:, k][ace[:, k]].mean()) if n_e[k] else None,
                "open_active": int(n_o[k]),
                "open_ratio": {C.OPEN_ACTIONS[j]: float((ao == j).mean()) if len(ao) else None
                               for j in range(len(C.OPEN_ACTIONS))},
                "open_entropy": float(eno[:, k][aco[:, k]].mean()) if n_o[k] else None}
        tot_act = (ace.sum() + aco.sum()).item()
        out["entropy_active_heads"] = float(((ene * ace).sum() + (eno * aco).sum()).item() / max(tot_act, 1))
        act_e = f["ae"][ace]
        out["nonzero_entry_ratio"] = float((act_e > 0).float().mean()) if len(act_e) else None
        return out

    def _ppo(self, f: dict) -> dict:
        cfg = self.cfg
        n = len(f["ae"])
        mb = min(cfg.minibatch, n)
        stats = torch.zeros(6, device=self.device)
        k = 0
        for _ in range(cfg.epochs):
            perm = torch.randperm(n, device=self.device)
            for i in range(0, n - mb + 1, mb):
                idx = perm[i:i + mb]
                t = {key: f[key][idx] for key in OBS_KEYS + ("m_entry", "m_open")}
                le, lo, v = forward(self.model, t)
                logp, _, (ene, ace, eno, aco) = joint(le, lo, t["m_entry"], t["m_open"], f["ae"][idx], f["ao"][idx])
                ent = ((ene * ace).sum() + (eno * aco).sum()) / (ace.sum() + aco.sum()).clamp(min=1)
                log_ratio = logp - f["logp"][idx]
                ratio = log_ratio.exp()
                adv = f["adv"][idx]
                adv = (adv - adv.mean()) / (adv.std() + 1e-8)
                pg = -torch.min(ratio * adv, ratio.clamp(1 - cfg.clip, 1 + cfg.clip) * adv).mean()
                v_old, ret = f["values"][idx], f["ret"][idx]
                v_clip = v_old + (v - v_old).clamp(-cfg.vclip, cfg.vclip)
                vl = 0.5 * torch.max((v - ret) ** 2, (v_clip - ret) ** 2).mean()
                loss = pg + cfg.vf_coef * vl - cfg.ent_coef * ent
                self.opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), cfg.max_grad_norm)
                self.opt.step()
                with torch.no_grad():
                    stats += torch.stack([pg, vl, ent, loss, ((ratio - 1) - log_ratio).mean(),
                                          ((ratio - 1).abs() > cfg.clip).float().mean()])
                k += 1
        out = dict(zip(("policy_loss", "value_loss", "entropy_loss_term", "loss", "approx_kl", "clip_frac"),
                       (stats / max(k, 1)).tolist()))
        out["explained_var"] = float(1 - (f["ret"] - f["values"]).var() / f["ret"].var())
        out["grad_steps"] = k
        return out

    # ---------------------------------------------------------------- validation
    def validate(self) -> dict:
        """Deterministic argmax over the full validation window, one continuous episode per cell."""
        a, b = (pd.Timestamp(x, tz="UTC").value for x in self.val_win)
        L = (b - a) // HOUR
        res = {}
        with torch.no_grad():
            for c, cd in self.cells.items():
                v = AV.VecAllocatorEnv(cd, 1, static_weights=self.static_w)
                o = v.reset(np.array([a]), L)
                acc = {"net_rl": 0.0, "net_static": 0.0, "reward": 0.0, "dd_pen": 0.0, "to_pen": 0.0,
                       "nonzero_entries": 0, "active_entries": 0, "gross_reserved_max": 0.0, "identity_err": 0.0}
                while True:
                    oo = {k: o[k] for k in OBS_KEYS}
                    oo["m_entry"], oo["m_open"] = o["masks"][0], o["masks"][2]
                    t = to_t(oo, self.device)
                    le, lo, _ = forward(self.model, t)
                    ae, ao = le.argmax(-1), lo.argmax(-1)
                    act = t["m_entry"].sum(-1) >= 2
                    acc["active_entries"] += int(act.sum())
                    acc["nonzero_entries"] += int(((ae > 0) & act).sum())
                    o, r, done, info = v.step(ae.cpu().numpy().astype(np.int64), np.zeros((1, 7), np.int64),
                                              ao.cpu().numpy().astype(np.int64))
                    ex, dd, to = reward_parts(info)
                    acc["identity_err"] = max(acc["identity_err"], float(np.abs(r - (ex - dd - to)).max()))
                    acc["net_rl"] += float(info["net_rl"][0])
                    acc["net_static"] += float(info["net_st"][0])
                    acc["reward"] += float(r[0])
                    acc["dd_pen"] += float(dd[0])
                    acc["to_pen"] += float(to[0])
                    acc["gross_reserved_max"] = max(acc["gross_reserved_max"], float(info["gross_reserved"][0]))
                    if done:
                        break
                acc["excess"] = acc["net_rl"] - acc["net_static"]
                acc["trades"] = int(v.rl.new_alloc[0])
                acc["mdd_rl"], acc["mdd_static"] = float(v.rl.mdd[0]), float(v.st.mdd[0])
                acc["all_flat"] = acc["trades"] == 0
                res[c] = acc
        key = min(r["excess"] for r in res.values())
        return {"cells": res, "worst_cell_excess": key, "all_flat": all(r["all_flat"] for r in res.values()),
                "flat_cells": int(sum(r["all_flat"] for r in res.values()))}


def tensors_equal(a, b) -> bool:
    """Deep equality of nested state (tensors, arrays, dicts, lists, scalars)."""
    if isinstance(a, torch.Tensor):
        return isinstance(b, torch.Tensor) and a.shape == b.shape and bool(torch.equal(a.cpu(), b.cpu()))
    if isinstance(a, np.ndarray):
        return isinstance(b, np.ndarray) and a.shape == b.shape and np.array_equal(a, b, equal_nan=True)
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(tensors_equal(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return isinstance(b, (list, tuple)) and len(a) == len(b) and all(tensors_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b
