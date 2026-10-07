"""Actor-critic over the 32-step window in each observation (plan 3 C10). No recurrent state across steps,
no dropout (a dropout mask differing between rollout and update breaks the PPO ratio)."""
from __future__ import annotations
import torch
from torch import nn

N_ACTIONS = 3
WINDOW = 32


def _mlp(d_in, d_out, hidden):
    return nn.Sequential(nn.Linear(d_in, hidden), nn.Tanh(), nn.Linear(hidden, hidden), nn.Tanh(),
                         nn.Linear(hidden, d_out))


class TemporalActorCritic(nn.Module):
    def __init__(self, k_seq: int, k_static: int, encoder: str = "conv", hidden: int = 64):
        super().__init__()
        if encoder not in ("conv", "gru"):
            raise ValueError(f"encoder {encoder!r}")
        self.model_args = {"k_seq": k_seq, "k_static": k_static, "encoder": encoder, "hidden": hidden}
        if encoder == "conv":   # 2 layers kernel 3, flattened so the time position survives
            self.enc = nn.Sequential(nn.Conv1d(k_seq, 64, 3), nn.ReLU(), nn.Conv1d(64, 64, 3), nn.ReLU(),
                                     nn.Flatten())
            d_enc = 64 * (WINDOW - 4)
        else:
            self.enc = nn.GRU(k_seq, 64, batch_first=True)
            d_enc = 64
        self.pi = _mlp(d_enc + k_static, N_ACTIONS, hidden)
        self.v = _mlp(d_enc + k_static, 1, hidden)
        with torch.no_grad():   # near-uniform initial policy
            self.pi[-1].weight.mul_(0.01); self.pi[-1].bias.zero_()

    def forward(self, seq, static, mask):
        """seq [B,32,k_seq], static [B,k_static], mask bool [B,3] -> logits [B,3] (masked = -inf), value [B]."""
        if isinstance(self.enc, nn.GRU):
            h = self.enc(seq)[1][-1]
        else:
            h = self.enc(seq.transpose(1, 2))
        x = torch.cat([h, static], 1)
        return self.pi(x).masked_fill(~mask, float("-inf")), self.v(x).squeeze(1)
