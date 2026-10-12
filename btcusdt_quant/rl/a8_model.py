"""A8 token-attention recurrent policy and duration-aware PPO utilities."""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import torch
from torch import nn

N_TOKENS = 44
TOKEN_CHANNELS = 20
TARGETS = np.asarray((-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0), np.float64)
WAITS = np.asarray((5, 15, 60, 240, 1440), np.int64)
SL_GRID = np.asarray((0.0, 1.0, 2.0, 3.0, 5.0), np.float64)
TP_GRID = np.asarray((0.0, 1.0, 2.0, 4.0, 8.0), np.float64)
N_JOINT = len(TARGETS) * len(WAITS)


def encode_joint(target_index, wait_index):
    return np.asarray(target_index) * len(WAITS) + np.asarray(wait_index)


def decode_joint(action):
    action = np.asarray(action, np.int64)
    return action // len(WAITS), action % len(WAITS)


class A8Policy(nn.Module):
    """Shared token encoder, learned identity/family embeddings, gated attention, GRU, and four heads."""

    def __init__(self, market_dim: int, account_dim: int, family_ids, token_gates, token_width: int = 32,
                 hidden: int = 256):
        super().__init__()
        family_ids = torch.as_tensor(family_ids, dtype=torch.long)
        gates = torch.as_tensor(token_gates, dtype=torch.float32)
        if family_ids.shape != (N_TOKENS,) or gates.shape != (N_TOKENS,):
            raise ValueError("A8 requires exactly 44 family ids and 44 token gates")
        if torch.any(gates <= 0):
            raise ValueError("all A8 token gates must be positive")
        self.market_dim, self.account_dim = int(market_dim), int(account_dim)
        self.obs_dim = N_TOKENS * TOKEN_CHANNELS + self.market_dim + self.account_dim
        self.hidden_size = int(hidden)
        self.register_buffer("family_ids", family_ids)
        self.register_buffer("token_gates", gates)
        self.token_encoder = nn.Sequential(nn.Linear(TOKEN_CHANNELS, token_width), nn.SiLU(),
                                           nn.Linear(token_width, token_width), nn.SiLU())
        self.token_embedding = nn.Embedding(N_TOKENS, token_width)
        self.family_embedding = nn.Embedding(int(family_ids.max()) + 1, token_width)
        self.attention = nn.Linear(token_width, 1)
        self.pre_gru = nn.Sequential(nn.Linear(token_width + market_dim + account_dim, hidden), nn.LayerNorm(hidden),
                                     nn.SiLU())
        self.gru = nn.GRU(hidden, hidden)
        self.joint_head = nn.Linear(hidden, N_JOINT)
        self.sl_head = nn.Linear(hidden, len(SL_GRID))
        self.tp_head = nn.Linear(hidden, len(TP_GRID))
        self.value_head = nn.Linear(hidden, 1)
        with torch.no_grad():
            for head in (self.joint_head, self.sl_head, self.tp_head):
                head.weight.mul_(0.01)
                head.bias.zero_()

    def initial_state(self, batch: int, device=None):
        return torch.zeros(1, batch, self.hidden_size, device=device or self.token_gates.device)

    def _features(self, x):
        tokens = x[..., :N_TOKENS * TOKEN_CHANNELS].reshape(*x.shape[:-1], N_TOKENS, TOKEN_CHANNELS)
        rest = x[..., N_TOKENS * TOKEN_CHANNELS:]
        z = self.token_encoder(tokens)
        shape = (1,) * (z.ndim - 2) + (N_TOKENS, -1)
        ids = torch.arange(N_TOKENS, device=x.device)
        z = z + self.token_embedding(ids).view(shape) + self.family_embedding(self.family_ids).view(shape)
        z = z * self.token_gates.view((1,) * (z.ndim - 2) + (N_TOKENS, 1))
        pooled = (torch.softmax(self.attention(z).squeeze(-1), dim=-1).unsqueeze(-1) * z).sum(-2)
        return self.pre_gru(torch.cat((pooled, rest), dim=-1))

    def forward(self, x, hidden=None):
        single = x.ndim == 2
        if single:
            x = x.unsqueeze(0)
        if x.shape[-1] != self.obs_dim:
            raise ValueError(f"observation width {x.shape[-1]} != locked A8 width {self.obs_dim}")
        if hidden is None:
            hidden = self.initial_state(x.shape[1], x.device)
        z, hidden = self.gru(self._features(x), hidden)
        out = (self.joint_head(z), self.sl_head(z), self.tp_head(z), self.value_head(z).squeeze(-1), hidden)
        return tuple(v.squeeze(0) if single and i < 4 else v for i, v in enumerate(out))


@dataclass(frozen=True)
class PPOConfig:
    lr: float = 3e-4
    weight_decay: float = 1e-4
    clip: float = 0.2
    value_clip: float = 0.2
    value_coef: float = 0.5
    max_grad_norm: float = 0.5
    reward_scale: float = 0.01
    entropy_joint: float = 0.01
    entropy_sl: float = 0.005
    entropy_tp: float = 0.005
    lambda_half_life_h: float = 12.0
    rollout_hours: int = 48
    burnin_hours: int = 24


def lambda_for_minutes(minutes, half_life_h: float):
    """Elapsed-time GAE lambda whose multiplicative half-life is the genotype's 6/12/24 hours."""
    return torch.exp(-math.log(2.0) * minutes / (60.0 * float(half_life_h)))


def recurrent_gae(reward, value, done, last_value, gamma_d, minutes, half_life_h: float):
    T = reward.shape[0]
    advantage = torch.zeros_like(reward)
    next_value, next_advantage = last_value, torch.zeros_like(last_value)
    lam = lambda_for_minutes(minutes, half_life_h)
    for t in range(T - 1, -1, -1):
        live = 1.0 - done[t]
        delta = reward[t] + gamma_d[t] * live * next_value - value[t]
        next_advantage = delta + gamma_d[t] * lam[t] * live * next_advantage
        advantage[t] = next_advantage
        next_value = value[t]
    return advantage, advantage + value


def categorical_logp_entropy(logits, action):
    logp = torch.log_softmax(logits, -1)
    return logp.gather(-1, action.unsqueeze(-1)).squeeze(-1), -(logp.exp() * logp).sum(-1)
