"""Minimal PPO for VecTradingEnv (plan 3 C11 hyper-parameters, C12 stopping). The loop knows nothing about
replay: validation is the caller's val_fn(model) -> net. last.pt carries model, optimizer, env and RNG state so a
resumed run is bitwise identical to an uninterrupted one (same device); best.pt is the best validation model."""
from __future__ import annotations
import math, os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable
import numpy as np
import torch
from torch import nn
from .models import TemporalActorCritic

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")   # deterministic cuBLAS; read at first CUDA matmul


@dataclass(frozen=True)
class PPOConfig:
    gamma: float = 0.999
    lam: float = 0.95
    clip: float = 0.2
    vclip: float = 0.2
    n_steps: int = 128          # rollout length; n_envs comes from the env (C11: 256)
    minibatch: int = 4096
    epochs: int = 4
    vf_coef: float = 0.5
    ent_coef: float = 0.01
    max_grad_norm: float = 0.5
    weight_decay: float = 1e-4
    lr: float = 3e-4            # C11: {1e-4, 3e-4}
    encoder: str = "conv"


@dataclass
class TrainResult:
    best_val: float
    best_step: int              # update index of the best validation
    history: list
    ckpt_path: Path


def compute_gae(rewards, values, dones, last_value, gamma, lam):
    """[T, n] tensors; dones[t] marks the step that ended an episode (the env auto-resets, so the next
    observation belongs to a new episode and is not bootstrapped)."""
    adv = torch.zeros_like(rewards)
    gae = torch.zeros_like(last_value)
    nxt = last_value
    for t in range(len(rewards) - 1, -1, -1):
        live = 1.0 - dones[t]
        delta = rewards[t] + gamma * nxt * live - values[t]
        gae = delta + gamma * lam * live * gae
        adv[t] = gae
        nxt = values[t]
    return adv, adv + values


def ppo_update(model, optimizer, batch, cfg: PPOConfig) -> dict:
    """batch: flat tensors seq, static, mask, actions, logp, values, adv, returns. Returns mean loss terms."""
    n = len(batch["actions"])
    mb = min(cfg.minibatch, n)
    ret, v_old = batch["returns"], batch["values"]
    stats = torch.zeros(6, device=ret.device)
    k = 0
    for _ in range(cfg.epochs):
        perm = torch.randperm(n, device=ret.device)
        for i in range(0, n - mb + 1, mb):
            idx = perm[i:i + mb]
            logits, v = model(batch["seq"][idx], batch["static"][idx], batch["mask"][idx])
            logp_all = torch.log_softmax(logits, 1)
            logp = logp_all.gather(1, batch["actions"][idx, None]).squeeze(1)
            # masked entries are -inf: zero them before p * log p (0 * -inf would be nan, also in the gradient)
            ent = -(logp_all.exp() * logp_all.masked_fill(~batch["mask"][idx], 0.0)).sum(1).mean()
            log_ratio = logp - batch["logp"][idx]
            ratio = log_ratio.exp()
            adv = batch["adv"][idx]
            adv = (adv - adv.mean()) / (adv.std() + 1e-8)
            pg = -torch.min(ratio * adv, ratio.clamp(1 - cfg.clip, 1 + cfg.clip) * adv).mean()
            v_clip = v_old[idx] + (v - v_old[idx]).clamp(-cfg.vclip, cfg.vclip)
            vl = 0.5 * torch.max((v - ret[idx]) ** 2, (v_clip - ret[idx]) ** 2).mean()
            loss = pg + cfg.vf_coef * vl - cfg.ent_coef * ent
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg.max_grad_norm)
            optimizer.step()
            with torch.no_grad():
                stats += torch.stack([pg, vl, ent, loss, ((ratio - 1) - log_ratio).mean(),
                                      ((ratio - 1).abs() > cfg.clip).float().mean()])
            k += 1
    out = dict(zip(("policy_loss", "value_loss", "entropy", "loss", "approx_kl", "clip_frac"),
                   (stats / k).tolist()))
    out["explained_var"] = float(1 - (ret - v_old).var() / ret.var())
    return out


def _save(path, obj):
    tmp = Path(str(path) + ".tmp")
    torch.save(obj, tmp)
    os.replace(tmp, path)


def train(env, val_fn: Callable[[nn.Module], float], cfg: PPOConfig, seed: int, max_transitions: int = 5_000_000,
          eval_every: int = 10, patience: int = 5, ckpt_dir=None, device=None, resume: bool = False) -> TrainResult:
    """C12: validate every eval_every updates and at the final update; keep best.pt by validation; stop after
    `patience` evaluations without improvement or once max_transitions are collected."""
    device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    torch.use_deterministic_algorithms(True, warn_only=True)
    torch.backends.cudnn.benchmark = False
    ckpt_dir = Path(ckpt_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    last_path, best_path = ckpt_dir / "last.pt", ckpt_dir / "best.pt"
    torch.manual_seed(seed)
    obs = env.reset()
    model = TemporalActorCritic(obs[0].shape[2], obs[1].shape[1], cfg.encoder).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    st = {"update": 0, "transitions": 0, "history": [], "best_val": -math.inf, "best_update": -1, "bad": 0}
    if resume and last_path.exists():
        ck = torch.load(last_path, map_location="cpu", weights_only=False)
        if ck["seed"] != seed or ck["cfg"] != asdict(cfg):
            raise ValueError("resume checkpoint has a different seed or config")
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["optimizer"])
        env.load_state_dict(ck["env"]); obs, st = ck["obs"], ck["progress"]
        torch.set_rng_state(ck["rng"])
        if device.type == "cuda":
            torch.cuda.set_rng_state(ck["cuda_rng"], device)
    n, T = env.n, cfg.n_steps
    meta = {"seed": seed, "cfg": asdict(cfg), "model_args": model.model_args}
    as_t = lambda o: tuple(torch.as_tensor(x, device=device) for x in o)
    while st["transitions"] < max_transitions:
        buf = {k: [] for k in ("seq", "static", "mask", "actions", "logp", "values", "rewards", "dones")}
        with torch.no_grad():
            for _ in range(T):
                seq, static, mask = as_t(obs)
                logits, value = model(seq, static, mask)
                a = torch.multinomial(torch.softmax(logits, 1), 1).squeeze(1)   # p(masked) = 0: never drawn
                *obs, reward, _net, done, _info = env.step(a.cpu().numpy().astype(np.int8))
                for key, x in zip(buf, (seq, static, mask, a, torch.log_softmax(logits, 1).gather(1, a[:, None])
                                        .squeeze(1), value, torch.as_tensor(reward, dtype=torch.float32),
                                        torch.as_tensor(done, dtype=torch.float32))):
                    buf[key].append(x.to(device))
            last_value = model(*as_t(obs))[1]
        b = {k: torch.stack(v) for k, v in buf.items()}
        adv, ret = compute_gae(b["rewards"], b["values"], b["dones"], last_value, cfg.gamma, cfg.lam)
        flat = {k: b[k].flatten(0, 1) for k in ("seq", "static", "mask", "actions", "logp", "values")}
        flat["adv"], flat["returns"] = adv.flatten(), ret.flatten()
        rec = ppo_update(model, opt, flat, cfg)
        st["update"] += 1; st["transitions"] += T * n
        rec.update(update=st["update"], transitions=st["transitions"], reward_mean=float(b["rewards"].mean()))
        stop = st["transitions"] >= max_transitions
        if st["update"] % eval_every == 0 or stop:
            with torch.no_grad():
                rec["val"] = float(val_fn(model))
            if rec["val"] > st["best_val"]:
                st["best_val"], st["best_update"], st["bad"] = rec["val"], st["update"], 0
                _save(best_path, {**meta, "model": model.state_dict(), "update": st["update"],
                                  "transitions": st["transitions"], "val": rec["val"]})
            else:
                st["bad"] += 1
                stop = stop or st["bad"] >= patience
        st["history"].append(rec)
        if "val" in rec:
            _save(last_path, {**meta, "model": model.state_dict(), "optimizer": opt.state_dict(),
                              "env": env.state_dict(), "obs": tuple(obs), "progress": st, "update": st["update"],
                              "rng": torch.get_rng_state(),
                              "cuda_rng": torch.cuda.get_rng_state(device) if device.type == "cuda" else None})
        if stop:
            break
    return TrainResult(st["best_val"], st["best_update"], st["history"], best_path)
