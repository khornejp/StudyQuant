"""A6-P1: GPU PPO for the batched SMDP env (engineering / throughput). Policy 948 -> 256 -> 256 (LayerNorm + SiLU),
heads target 9 / wait 3 / value 1 (dropout 0.1 before the value head, none on the actor), AdamW (wd 1e-4), rollout
batch >= 65,536 decisions, minibatch 8,192, 4 epochs, duration-aware GAE on the GPU (gamma_d, lambda_d = 0.95^(dt/5)).
Observations go host -> device through two pinned buffers (double buffering)."""
from __future__ import annotations
import time
from dataclasses import dataclass
import numpy as np
import torch
from torch import nn
from .smdp_ppo import compute_gae_smdp


class PolicyA6(nn.Module):
    def __init__(self, obs_dim: int, n_target: int = 9, n_wait: int = 3, hidden: int = 256, v_dropout: float = 0.1):
        super().__init__()
        self.trunk = nn.Sequential(nn.Linear(obs_dim, hidden), nn.LayerNorm(hidden), nn.SiLU(),
                                   nn.Linear(hidden, hidden), nn.LayerNorm(hidden), nn.SiLU())
        self.pt, self.pw = nn.Linear(hidden, n_target), nn.Linear(hidden, n_wait)
        self.v = nn.Sequential(nn.Dropout(v_dropout), nn.Linear(hidden, 1))
        with torch.no_grad():
            for hd in (self.pt, self.pw):
                hd.weight.mul_(0.01)
                hd.bias.zero_()

    def forward(self, x):
        z = self.trunk(x)
        return self.pt(z), self.pw(z), self.v(z).squeeze(-1)


@dataclass(frozen=True)
class GPUConfig:
    lr: float = 3e-4
    weight_decay: float = 1e-4
    clip: float = 0.2
    vclip: float = 0.2
    epochs: int = 4
    minibatch: int = 8192
    rollout_batch: int = 65_536
    reward_scale: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    beta_target: float = 0.00732
    beta_wait: float = 0.020


class GPUTrainer:
    def __init__(self, env, episode_sampler, cfg: GPUConfig, seed: int, device: str = "cuda"):
        torch.manual_seed(seed)
        self.env, self.sample_episode, self.cfg = env, episode_sampler, cfg
        self.dev = torch.device(device)
        self.E = env.E
        self.T = int(np.ceil(cfg.rollout_batch / self.E))
        self.rng = np.random.default_rng(seed)
        st, en = episode_sampler(self.rng, np.arange(self.E))
        env.reset_env(np.arange(self.E), st, en)
        self.obs_dim = env.obs().shape[1]
        self.model = PolicyA6(self.obs_dim, len(env.targets), len(env.waits)).to(self.dev)
        self.opt = torch.optim.AdamW(self.model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
        self.pin = [torch.empty((self.E, self.obs_dim), dtype=torch.float32).pin_memory() for _ in range(2)]
        self.gen = torch.Generator(device=self.dev).manual_seed(seed)
        self.timing = {"env_step": 0.0, "obs_gather": 0.0, "h2d": 0.0, "policy_fwd": 0.0, "ppo_update": 0.0,
                       "reset": 0.0}
        self.decisions = 0

    def _to_gpu(self, k: int, x: np.ndarray) -> torch.Tensor:
        b = self.pin[k % 2]
        b.numpy()[:] = x
        return b.to(self.dev, non_blocking=True)

    def rollout_and_update(self) -> dict:
        cfg, E, T, dev = self.cfg, self.E, self.T, self.dev
        OBS = torch.empty((T, E, self.obs_dim), device=dev)
        AT = torch.empty((T, E), dtype=torch.long, device=dev)
        AW = torch.empty((T, E), dtype=torch.long, device=dev)
        LP, V, R, G, L, D = (torch.empty((T, E), device=dev) for _ in range(6))
        stats = {"net4": 0.0, "reward": 0.0, "fills": 0.0, "minutes": 0.0, "faults": 0, "identity_max": 0.0}
        model = self.model
        model.eval()
        t0 = time.perf_counter()
        x_np = self.env.obs()
        self.timing["obs_gather"] += time.perf_counter() - t0
        with torch.no_grad():
            for s in range(T):
                t1 = time.perf_counter()
                x = self._to_gpu(s, x_np)
                self.timing["h2d"] += time.perf_counter() - t1
                t1 = time.perf_counter()
                lt, lw, v = model(x)
                pt, pw = torch.softmax(lt, -1), torch.softmax(lw, -1)
                at = torch.multinomial(pt, 1, generator=self.gen).squeeze(1)
                aw = torch.multinomial(pw, 1, generator=self.gen).squeeze(1)
                lp = torch.log(pt.gather(1, at[:, None]).squeeze(1)) + torch.log(pw.gather(1, aw[:, None]).squeeze(1))
                a_t, a_w = at.cpu().numpy(), aw.cpu().numpy()
                self.timing["policy_fwd"] += time.perf_counter() - t1
                t1 = time.perf_counter()
                rw = self.env.step(a_t, a_w)
                self.timing["env_step"] += time.perf_counter() - t1
                OBS[s], AT[s], AW[s], LP[s], V[s] = x, at, aw, lp, v
                R[s] = torch.as_tensor(rw["reward_discounted"] * cfg.reward_scale, dtype=torch.float32, device=dev)
                G[s] = torch.as_tensor(rw["gamma_d"], dtype=torch.float32, device=dev)
                L[s] = torch.as_tensor(0.95 ** (rw["minutes"] / 5.0), dtype=torch.float32, device=dev)
                D[s] = torch.as_tensor(rw["done"].astype(np.float32), device=dev)
                stats["net4"] += float(rw["net4"].sum())
                stats["reward"] += float(rw["reward"].sum())
                stats["fills"] += float(rw["fills"].sum())
                stats["minutes"] += float(rw["minutes"].sum())
                stats["faults"] += int(rw["fault"].sum())
                stats["identity_max"] = max(stats["identity_max"], float(rw["identity_err"].max()))
                t1 = time.perf_counter()
                done = np.flatnonzero(rw["done"])
                if len(done):
                    st, en = self.sample_episode(self.rng, done)
                    self.env.reset_env(done, st, en)
                self.timing["reset"] += time.perf_counter() - t1
                t1 = time.perf_counter()
                x_np = self.env.obs()
                self.timing["obs_gather"] += time.perf_counter() - t1
            last_v = model(self._to_gpu(T, x_np))[2]
        t1 = time.perf_counter()
        adv, ret = compute_gae_smdp(R, V, D, last_v, G, L)
        out = self._ppo(OBS.flatten(0, 1), AT.flatten(), AW.flatten(), LP.flatten(), V.flatten(), adv.flatten(),
                        ret.flatten())
        torch.cuda.synchronize()
        self.timing["ppo_update"] += time.perf_counter() - t1
        self.decisions += T * E
        stats.update(out)
        stats["decisions"] = T * E
        return stats

    def _ppo(self, obs, at, aw, lp_old, v_old, adv, ret) -> dict:
        cfg = self.cfg
        self.model.train()
        n = len(at)
        adv = (adv - adv.mean()) / (adv.std(unbiased=False) + 1e-8)
        k, agg = 0, torch.zeros(5, device=self.dev)
        for _ in range(cfg.epochs):
            perm = torch.randperm(n, device=self.dev, generator=self.gen)
            for i in range(0, n, cfg.minibatch):
                idx = perm[i:i + cfg.minibatch]
                lt, lw, v = self.model(obs[idx])
                plt, plw = torch.log_softmax(lt, -1), torch.log_softmax(lw, -1)
                lp = plt.gather(1, at[idx][:, None]).squeeze(1) + plw.gather(1, aw[idx][:, None]).squeeze(1)
                et, ew = -(plt.exp() * plt).sum(-1).mean(), -(plw.exp() * plw).sum(-1).mean()
                ratio = (lp - lp_old[idx]).exp()
                a = adv[idx]
                pg = -torch.min(ratio * a, ratio.clamp(1 - cfg.clip, 1 + cfg.clip) * a).mean()
                vc = v_old[idx] + (v - v_old[idx]).clamp(-cfg.vclip, cfg.vclip)
                vl = 0.5 * torch.max((v - ret[idx]) ** 2, (vc - ret[idx]) ** 2).mean()
                loss = pg + cfg.vf_coef * vl - cfg.beta_target * et - cfg.beta_wait * ew
                self.opt.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), cfg.max_grad_norm)
                self.opt.step()
                agg += torch.stack([pg.detach(), vl.detach(), et.detach(), ew.detach(),
                                    ((ratio - 1).abs() > cfg.clip).float().mean().detach()])
                k += 1
        a = (agg / max(k, 1)).tolist()
        return {"policy_loss": a[0], "value_loss": a[1], "entropy_target": a[2], "entropy_wait": a[3], "clip_frac": a[4],
                "grad_steps": k}
