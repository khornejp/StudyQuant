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
