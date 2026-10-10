"""Allocator actor-critic (Codex design section 5, Step 5): 32-step Conv encoder (hidden 64) over the 1h sequence
(values, NaN masks, timestep padding) + static vector + account channels, factorized masked categorical heads:
per sleeve an entry head (5 levels) and an open head (HOLD / TIGHTEN_75 / TIGHTEN_50 / EXIT). The pending head is fixed
to KEEP (an order's 60 m TTL ends before the next decision at 1h; pending occupancy 0 % in env-check) and is not part
of the policy, its log-prob or its entropy. TemporalActorCritic (models.py) is untouched."""
from __future__ import annotations
import torch
from torch import nn
from . import allocator_contracts as C

NS, NL, NO = len(C.SLEEVES), len(C.LEVELS), len(C.OPEN_ACTIONS)
BIAS = 2.0                       # static-policy initialisation strength (logit gap of the argmax action)


class AllocatorActorCritic(nn.Module):
    def __init__(self, k_seq: int = len(C.SEQ_COLUMNS), k_static: int = C.N_STATIC,
                 k_account: int = NS * len(C.ACCOUNT_CHANNELS), hidden: int = 64, static_weights=None):
        super().__init__()
        self.model_args = {"k_seq": k_seq, "k_static": k_static, "k_account": k_account, "hidden": hidden,
                           "static_weights": None if static_weights is None else [float(x) for x in static_weights]}
        c_in = 2 * k_seq + 1
        self.enc = nn.Sequential(nn.Conv1d(c_in, hidden, 3), nn.ReLU(), nn.Conv1d(hidden, hidden, 3), nn.ReLU(),
                                 nn.Flatten())
        d = hidden * (C.SEQ_LEN - 4) + k_static + k_account
        self.trunk = nn.Sequential(nn.Linear(d, hidden), nn.Tanh(), nn.Linear(hidden, hidden), nn.Tanh())
        self.entry = nn.Linear(hidden, NS * NL)
        self.open = nn.Linear(hidden, NS * NO)
        self.v = nn.Sequential(nn.Linear(d, hidden), nn.Tanh(), nn.Linear(hidden, hidden), nn.Tanh(),
                               nn.Linear(hidden, 1))
        with torch.no_grad():
            for head in (self.entry, self.open):
                head.weight.mul_(0.01)
                head.bias.zero_()
            if static_weights is not None:      # argmax reproduces the static baseline: reward exactly 0
                b = self.entry.bias.view(NS, NL)
                for k, w in enumerate(static_weights):
                    b[k, C.LEVELS.index(float(w))] = BIAS
            self.open.bias.view(NS, NO)[:, 0] = BIAS          # HOLD

    def forward(self, seq, seq_nan, seq_pad, static, account, m_entry, m_open):
        """seq/seq_nan [B,32,k], seq_pad [B,32], static [B,453], account [B,28], masks bool [B,7,5] / [B,7,4]
        -> masked logits [B,7,5], [B,7,4] (-inf where illegal), value [B]."""
        x = torch.cat([seq, seq_nan, seq_pad.unsqueeze(2)], 2).transpose(1, 2)
        z = torch.cat([self.enc(x), static, account], 1)
        h = self.trunk(z)
        le = self.entry(h).view(-1, NS, NL).masked_fill(~m_entry, float("-inf"))
        lo = self.open(h).view(-1, NS, NO).masked_fill(~m_open, float("-inf"))
        return le, lo, self.v(z).squeeze(1)


def head_stats(logits: torch.Tensor, mask: torch.Tensor, actions: torch.Tensor):
    """Per head: log-prob of the taken action [B,7], entropy [B,7], active flag [B,7] (>= 2 legal actions)."""
    lp_all = torch.log_softmax(logits, -1)
    lp = lp_all.gather(-1, actions.unsqueeze(-1)).squeeze(-1)
    ent = -(lp_all.exp() * lp_all.masked_fill(~mask, 0.0)).sum(-1)
    active = mask.sum(-1) >= 2
    return lp, ent, active


def joint(le, lo, me, mo, ae, ao):
    """Joint log-prob = sum over active heads; entropy = mean over active heads (0 when none is active)."""
    lpe, ene, ace = head_stats(le, me, ae)
    lpo, eno, aco = head_stats(lo, mo, ao)
    logp = (lpe * ace).sum(1) + (lpo * aco).sum(1)
    n_act = ace.sum(1) + aco.sum(1)
    ent = ((ene * ace).sum(1) + (eno * aco).sum(1)) / n_act.clamp(min=1)
    return logp, ent, (ene, ace, eno, aco)
