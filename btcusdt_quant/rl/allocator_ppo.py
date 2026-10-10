"""Vector-action PPO for the RL allocator (Codex design section 5, Step 5 + smoke review fixes). Uses ppo.compute_gae
unchanged; the old single-head ppo.ppo_update/train stay as they are for their existing callers.

  * PooledEnv: one VecAllocatorEnv per execution cell (envs split across cells), random contiguous episodes of
    `episode_days` inside the fold train window on the cadence grid (1h: 2,160 steps, 4h: 540), synchronous
    auto-reset; state_dict covers env books, episode RNG and the last observation.
  * rollout -> GAE (reward_scale 0.01, bps -> percent) -> advantages normalized ONCE per rollout (global mean / std,
    unbiased=False) -> clipped PPO with value clipping over the joint log-prob of the active heads; entropy = mean over
    active heads, coefficient ent_coef decayed linearly to 0 at ent_decay_frac of total_updates; early stop of the
    remaining epochs when a minibatch approx-KL exceeds 1.5 x target_kl (0.015 for 0.01).
  * validate(): deterministic argmax, one continuous episode per cell over the validation window; all cells advance
    together and share one batched forward (B = cells); key = worst-cell validation excess; all-flat never promoted.
  * identity: fold, cadence, normalizer / state / precompute hashes, cell counts, windows, static weights, model biases;
    a checkpoint with a different identity is refused (fail closed).
Trainer.state_dict holds model, optimizer, env, numpy/torch/CUDA RNG and progress: a split run resumed from a
checkpoint equals an uninterrupted run exactly."""
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
COUNTERS = ("cap_scaled", "new_alloc", "alloc_sum")


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
    ent_coef: float = 0.001
    ent_decay_frac: float = 0.5          # ent_coef -> 0 linearly by this fraction of total_updates
    total_updates: int = 30
    target_kl: float = 0.01              # stop remaining epochs when a minibatch approx-KL > 1.5 x target_kl
    max_grad_norm: float = 0.5
    weight_decay: float = 1e-4
    lr: float = 3e-4
    hidden: int = 64
    reward_scale: float = 0.01
    cadence_h: int = 1
    episode_days: int = 90
    entry_bias: float = 4.0
    open_bias: float = 4.0
    active_sleeves: tuple | None = None   # heads restricted to these sleeves; others fixed OFF / HOLD (allocation 0)
    ckpt_score: str = "max_baseline"      # "max_baseline": min_cell[net_rl - max(static, comparators)]; "static"

    @property
    def episode_steps(self) -> int:
        return self.episode_days * 24 // self.cadence_h

    def ent_coef_at(self, update: int) -> float:
        """Entropy coefficient for the update about to run (0-based)."""
        end = self.ent_decay_frac * self.total_updates
        return self.ent_coef * max(0.0, 1.0 - update / end) if end > 0 else 0.0


def reward_parts(info: dict):
    dd = C.DD_PENALTY * np.maximum(0.0, info["dmdd_rl"] - info["dmdd_st"])
    to = C.TURNOVER_PENALTY * np.maximum(0.0, info["turnover_rl"] - info["turnover_st"])
    return info["net_rl"] - info["net_st"], dd, to


class PooledEnv:
    def __init__(self, cells: dict, counts: dict, static_w, train: tuple, cfg: AllocPPOConfig, seed: int):
        self.order = list(counts)
        self.counts = counts
        self.cad = cfg.cadence_h
        self.envs = {c: AV.VecAllocatorEnv(cells[c], counts[c], cadence_h=cfg.cadence_h, static_weights=static_w)
                     for c in self.order}
        self.a, self.b = (pd.Timestamp(x, tz="UTC").value for x in train)
        self.L = cfg.episode_steps
        self.rng = np.random.default_rng(seed)
        self.n = sum(counts.values())
        self.obs = {c: self._reset(c) for c in self.order}

    def _reset(self, c):
        step = self.cad * HOUR
        lo = -(-self.a // step) * step                               # first start on the cadence grid
        hi = (self.b - lo) // step - self.L                          # episode ends <= train end
        starts = lo + step * self.rng.integers(0, hi + 1, self.counts[c])
        return self.envs[c].reset(starts, self.L)

    def observation(self) -> dict:
        o = {k: np.concatenate([self.obs[c][k] for c in self.order]) for k in OBS_KEYS}
        o["m_entry"] = np.concatenate([self.obs[c]["masks"][0] for c in self.order])
        o["m_open"] = np.concatenate([self.obs[c]["masks"][2] for c in self.order])
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

    def counters(self) -> dict:
        return {k: np.concatenate([getattr(e.rl, k) for e in self.envs.values()]) for k in COUNTERS}

    def state_dict(self) -> dict:
        return {"envs": {c: e.state_dict() for c, e in self.envs.items()},
                "rng": copy.deepcopy(self.rng.bit_generator.state), "obs": copy.deepcopy(self.obs)}

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


def sample(logits: torch.Tensor) -> torch.Tensor:
    p = torch.softmax(logits, -1).flatten(0, 1)
    return torch.multinomial(p, 1).view(logits.shape[:2])


class Trainer:
    def __init__(self, cells: dict, counts: dict, static_w, train: tuple, val: tuple, cfg: AllocPPOConfig,
                 seed: int, fold: str, device: str | None = None, env=None, comparators: dict | None = None):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.backends.cudnn.benchmark = False
        torch.manual_seed(seed)
        if self.device.type == "cuda":
            torch.cuda.manual_seed(seed)
        for c, cd in cells.items():                                   # fold / cadence / windows must agree
            if cd.fold != fold or cd.cadence_h != cfg.cadence_h:
                raise ValueError(f"{c}: loaded for fold {cd.fold} / {cd.cadence_h}h, trainer {fold} / {cfg.cadence_h}h")
            fw = cd.identity["fold_windows"]
            if (fw["train"][0], fw["train"][1]) != tuple(train) or (fw["val"][0], fw["val"][1]) != tuple(val):
                raise ValueError(f"{c}: train/val windows differ from fold {fold}: {fw}")
        self.cfg, self.seed, self.fold, self.cells = cfg, seed, fold, cells
        self.static_w, self.val_win = np.asarray(static_w, float), val
        self.env = env if env is not None else PooledEnv(cells, counts, static_w, train, cfg, seed)
        self.model = AllocatorActorCritic(hidden=cfg.hidden, static_weights=static_w, entry_bias=cfg.entry_bias,
                                          open_bias=cfg.open_bias).to(self.device)
        self.opt = torch.optim.AdamW(self.model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
        self.update = 0
        self.comparators = {k: np.asarray(v, float) for k, v in (comparators or {}).items()}
        act = C.SLEEVES if cfg.active_sleeves is None else tuple(cfg.active_sleeves)
        if not set(act) <= set(C.SLEEVES):
            raise ValueError(f"unknown active sleeves {act}")
        self.inactive = torch.as_tensor([s not in act for s in C.SLEEVES], device=self.device)
        self.identity = {"fold": fold, "cadence_h": cfg.cadence_h, "counts": dict(counts), "train": list(train),
                         "val": list(val), "static_weights": [float(x) for x in static_w], "seed": seed,
                         "cfg": asdict(cfg), "comparators": {k: v.tolist() for k, v in self.comparators.items()},
                         "cells": {c: cd.identity for c, cd in sorted(cells.items())}}

    def restrict(self, t: dict) -> dict:
        """Inactive sleeves: entry OFF only, open HOLD only (single-legal heads: no log-prob / entropy)."""
        if not bool(self.inactive.any()):
            return t
        inact = self.inactive.to(t["m_entry"].device)
        me, mo = t["m_entry"].clone(), t["m_open"].clone()
        me[:, inact, 1:] = False
        mo[:, inact, 1:] = False
        return {**t, "m_entry": me, "m_open": mo}

    # ---------------------------------------------------------------- state
    def state_dict(self) -> dict:
        return {"model": copy.deepcopy(self.model.state_dict()), "opt": copy.deepcopy(self.opt.state_dict()),
                "env": self.env.state_dict(), "update": self.update, "torch_rng": torch.get_rng_state(),
                "cuda_rng": torch.cuda.get_rng_state(self.device) if self.device.type == "cuda" else None,
                "identity": copy.deepcopy(self.identity), "model_args": self.model.model_args}

    def load_state_dict(self, st: dict) -> None:
        if st.get("identity") != self.identity:
            diff = sorted(k for k in set(self.identity) | set(st.get("identity", {}))
                          if self.identity.get(k) != st.get("identity", {}).get(k))
            raise ValueError(f"checkpoint identity mismatch: {diff}")
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
               "turnover_rl": 0.0}
        before = env.counters()
        with torch.no_grad():
            for _ in range(cfg.n_steps):
                o = env.observation()
                log["nonfinite"] += int(sum((~np.isfinite(o[k])).sum() for k in OBS_KEYS))
                t = self.restrict(to_t(o, dev))
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
            last_v = forward(self.model, self.restrict(to_t(env.observation(), dev)))[2]
        after = env.counters()
        for k in COUNTERS:
            d = after[k] - before[k]
            log[k] = float(np.where(d >= 0, d, after[k]).sum())       # an episode reset restarts the counters
        b = {k: torch.stack(x) for k, x in buf.items()}
        adv, ret = compute_gae(b["rewards"] * cfg.reward_scale, b["values"], b["dones"], last_v, cfg.gamma, cfg.lam)
        flat = {k: b[k].flatten(0, 1) for k in keys + ("ae", "ao", "logp", "values")}
        a = adv.flatten()
        flat["adv"] = (a - a.mean()) / (a.std(unbiased=False) + 1e-8)          # once per rollout
        flat["ret"] = ret.flatten()
        log["reward_rms_scaled"] = float((b["rewards"] * cfg.reward_scale).pow(2).mean().sqrt())
        log.update(self._policy_stats(flat))
        log["ent_coef"] = cfg.ent_coef_at(self.update)
        log.update(self._ppo(flat, log["ent_coef"]))
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

    def _ppo(self, f: dict, ent_coef: float) -> dict:
        cfg = self.cfg
        n = len(f["ae"])
        mb = min(cfg.minibatch, n)
        stats = torch.zeros(6, device=self.device)
        k, stopped, kl_max = 0, False, 0.0
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
                approx_kl = ((ratio - 1) - log_ratio).mean()
                kl_max = max(kl_max, float(approx_kl.detach()))
                if cfg.target_kl and float(approx_kl.detach()) > 1.5 * cfg.target_kl:
                    stopped = True                                    # skip this and all remaining minibatches
                    break
                adv = f["adv"][idx]
                pg = -torch.min(ratio * adv, ratio.clamp(1 - cfg.clip, 1 + cfg.clip) * adv).mean()
                v_old, ret = f["values"][idx], f["ret"][idx]
                v_clip = v_old + (v - v_old).clamp(-cfg.vclip, cfg.vclip)
                vl = 0.5 * torch.max((v - ret) ** 2, (v_clip - ret) ** 2).mean()
                loss = pg + cfg.vf_coef * vl - ent_coef * ent
                self.opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), cfg.max_grad_norm)
                self.opt.step()
                with torch.no_grad():
                    stats += torch.stack([pg, vl, ent, loss, approx_kl, ((ratio - 1).abs() > cfg.clip).float().mean()])
                k += 1
            if stopped:
                break
        out = dict(zip(("policy_loss", "value_loss", "entropy", "loss", "approx_kl", "clip_frac"),
                       (stats / max(k, 1)).tolist()))
        out["explained_var"] = float(1 - (f["ret"] - f["values"]).var() / f["ret"].var())
        out.update(grad_steps=k, kl_early_stop=stopped, approx_kl_max=kl_max)
        return out

    # ---------------------------------------------------------------- validation
    def validate(self, batched: bool = True, device=None, policy=None) -> dict:
        """Deterministic policy over the full validation window, one continuous episode per cell. batched: all cells
        advance together and share one forward per step (B = number of cells); otherwise B = 1 per cell. policy(t) ->
        (entry idx, open idx) tensors; default argmax of this trainer's model. Comparator static books run alongside
        (RL actions OFF) on the same data; per-step series are returned for paired bootstrap."""
        device = torch.device(device) if device is not None else self.device
        model = self.model if device == self.device else copy.deepcopy(self.model).to(device)
        if policy is None:
            def policy(t):
                le, lo, _ = forward(model, t)
                return le.argmax(-1), lo.argmax(-1)
        cad = self.cfg.cadence_h
        a, b = (pd.Timestamp(x, tz="UTC").value for x in self.val_win)
        L = (b - a) // (cad * HOUR)
        names = list(self.cells)
        envs = {c: AV.VecAllocatorEnv(self.cells[c], 1, cadence_h=cad, static_weights=self.static_w) for c in names}
        cmp = {(c, k): comparator_book(self.cells[c], a, L, cad, w) for c in names for k, w in self.comparators.items()}
        obs = {c: envs[c].reset(np.array([a]), L) for c in names}
        z = np.zeros((1, len(C.SLEEVES)), np.int64)
        acc = {c: {"net_rl": 0.0, "net_static": 0.0, "reward": 0.0, "dd_pen": 0.0, "to_pen": 0.0,
                   "nonzero_entries": 0, "active_entries": 0, "deviate_entries": 0, "nonhold_open": 0,
                   "active_open": 0, "gross_reserved_max": 0.0, "identity_err": 0.0} for c in names}
        series = {c: {"rl": np.zeros(L), "static": np.zeros(L), **{k: np.zeros(L) for k in self.comparators}}
                  for c in names}
        actions = {c: [] for c in names}
        static_idx = torch.as_tensor([C.LEVELS.index(float(w)) for w in self.static_w], device=device)
        groups = [names] if batched else [[c] for c in names]
        with torch.no_grad():
            for step in range(L):
                for grp in groups:
                    oo = {k: np.concatenate([obs[c][k] for c in grp]) for k in OBS_KEYS}
                    oo["m_entry"] = np.concatenate([obs[c]["masks"][0] for c in grp])
                    oo["m_open"] = np.concatenate([obs[c]["masks"][2] for c in grp])
                    t = self.restrict(to_t(oo, device))
                    ae, ao = policy(t)
                    act_e = t["m_entry"].sum(-1) >= 2
                    act_o = t["m_open"].sum(-1) >= 2
                    ae_n, ao_n = ae.cpu().numpy().astype(np.int64), ao.cpu().numpy().astype(np.int64)
                    for j, c in enumerate(grp):
                        r_ = acc[c]
                        r_["active_entries"] += int(act_e[j].sum())
                        r_["nonzero_entries"] += int(((ae[j] > 0) & act_e[j]).sum())
                        r_["deviate_entries"] += int(((ae[j] != static_idx) & act_e[j]).sum())
                        r_["active_open"] += int(act_o[j].sum())
                        r_["nonhold_open"] += int(((ao[j] > 0) & act_o[j]).sum())
                        actions[c].append((ae_n[j].copy(), ao_n[j].copy()))
                        o, r, done, info = envs[c].step(ae_n[j:j + 1], z, ao_n[j:j + 1])
                        ex, dd, to = reward_parts(info)
                        r_["identity_err"] = max(r_["identity_err"], float(np.abs(r - (ex - dd - to)).max()))
                        r_["net_rl"] += float(info["net_rl"][0])
                        r_["net_static"] += float(info["net_st"][0])
                        r_["reward"] += float(r[0])
                        r_["dd_pen"] += float(dd[0])
                        r_["to_pen"] += float(to[0])
                        r_["gross_reserved_max"] = max(r_["gross_reserved_max"], float(info["gross_reserved"][0]))
                        series[c]["rl"][step] = info["net_rl"][0]
                        series[c]["static"][step] = info["net_st"][0]
                        obs[c] = o
        res = {}
        for c in names:
            for k in self.comparators:
                series[c][k][:] = cmp[(c, k)][0]
            r_ = acc[c]
            r_["excess"] = r_["net_rl"] - r_["net_static"]
            r_["trades"] = int(envs[c].rl.new_alloc[0])
            r_["mdd_rl"], r_["mdd_static"] = float(envs[c].rl.mdd[0]), float(envs[c].st.mdd[0])
            for k in self.comparators:
                r_[f"net_{k}"] = float(series[c][k].sum())
                r_[f"mdd_{k}"] = cmp[(c, k)][1]
            r_["max_baseline"] = max([r_["net_static"]] + [r_[f"net_{k}"] for k in self.comparators])
            r_["excess_vs_max_baseline"] = r_["net_rl"] - r_["max_baseline"]
            r_["all_flat"] = r_["trades"] == 0
            r_["entry_deviation_ratio"] = r_["deviate_entries"] / max(r_["active_entries"], 1)
            r_["open_nonhold_ratio"] = r_["nonhold_open"] / max(r_["active_open"], 1)
            res[c] = r_
        out = {"cells": res, "worst_cell_excess": min(r["excess"] for r in res.values()),
               "all_flat": all(r["all_flat"] for r in res.values()),
               "flat_cells": int(sum(r["all_flat"] for r in res.values())), "_actions": actions, "_series": series}
        out["score"] = checkpoint_score(res, self.cfg.ckpt_score)
        return out


_CMP_CACHE: dict = {}


def comparator_book(cd, start: int, L: int, cad: int, w) -> tuple:
    """Per-step net4 series and MDD of a static comparator book (RL actions OFF) on one cell; cached because it
    does not depend on the policy."""
    key = (id(cd), cd.fold, int(start), int(L), int(cad), tuple(float(x) for x in w))
    if key not in _CMP_CACHE:
        e = AV.VecAllocatorEnv(cd, 1, cadence_h=cad, static_weights=w)
        e.reset(np.array([start]), L)
        z = np.zeros((1, len(C.SLEEVES)), np.int64)
        ser = np.zeros(L)
        for i in range(L):
            _, _, _, info = e.step(z, z, z)
            ser[i] = info["net_st"][0]
        _CMP_CACHE[key] = (ser, float(e.st.mdd[0]))
    return _CMP_CACHE[key]


def checkpoint_score(cells: dict, mode: str = "max_baseline") -> float:
    """Checkpoint key: min over cells of RL net4 minus the best baseline ("max_baseline": max of the env static book
    and every comparator) or minus the env static book only ("static")."""
    if mode == "static":
        return min(r["net_rl"] - r["net_static"] for r in cells.values())
    if mode == "max_baseline":
        return min(r["net_rl"] - r["max_baseline"] for r in cells.values())
    raise ValueError(f"unknown checkpoint score {mode!r}")


def ensemble_policy(models: list):
    """Design section 5: sleeve-wise median of the members' argmax entry levels; EXIT when a majority exits,
    otherwise the most conservative non-exit open action is HOLD."""
    def pol(t):
        es, os_ = [], []
        for m in models:
            le, lo, _ = forward(m, t)
            es.append(le.argmax(-1))
            os_.append(lo.argmax(-1))
        e = torch.stack(es).sort(0).values[len(models) // 2]
        o = torch.stack(os_)
        ex = (o == C.OPEN_ACTIONS.index("EXIT")).sum(0) * 2 > len(models)
        return e, torch.where(ex, torch.full_like(e, C.OPEN_ACTIONS.index("EXIT")), torch.zeros_like(e))
    return pol


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
