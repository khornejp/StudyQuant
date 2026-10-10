"""Allocator actor-critic heads (btcusdt_quant/rl/allocator_model.py) and the vector-action PPO helpers: masking,
joint log-prob over active heads, entropy over active heads, static initialisation, resume equality helper."""
import numpy as np, torch
from btcusdt_quant.rl import allocator_contracts as C
from btcusdt_quant.rl.allocator_model import AllocatorActorCritic, joint
from btcusdt_quant.rl.allocator_ppo import tensors_equal

B = 6


def inputs(seed=0):
    g = torch.Generator().manual_seed(seed)
    me = torch.ones(B, 7, 5, dtype=torch.bool)
    mo = torch.zeros(B, 7, 4, dtype=torch.bool)
    mo[:, :, 0] = True
    me[0, :, 1:] = False                              # sample 0: every entry head single-legal (OFF)
    mo[1, 3, :] = True                                # sample 1: B3 open head fully legal
    mo[2, 5, 3] = True                                # sample 2: C1 HOLD / EXIT
    return (torch.randn(B, 32, 11, generator=g), torch.zeros(B, 32, 11), torch.zeros(B, 32),
            torch.randn(B, C.N_STATIC, generator=g), torch.randn(B, 28, generator=g), me, mo)


def test_masks_and_static_init_argmax():
    torch.manual_seed(0)
    m = AllocatorActorCritic(static_weights=[0, 0, 0, 0, 0, 1, 1])
    le, lo, v = m(*inputs())
    assert torch.isinf(le[0, :, 1:]).all() and torch.isfinite(le[1]).all() and v.shape == (B,)
    a = le.argmax(-1)
    assert (a[1:, :5] == 0).all() and (a[1:, 5:] == 4).all() and (a[0] == 0).all()
    assert (lo.argmax(-1) == 0).all()                 # HOLD


def test_joint_logprob_and_entropy_over_active_heads():
    torch.manual_seed(1)
    m = AllocatorActorCritic()
    x = inputs(1)
    le, lo, _ = m(*x)
    me, mo = x[5], x[6]
    ae, ao = le.argmax(-1), lo.argmax(-1)
    logp, ent, (ene, ace, eno, aco) = joint(le, lo, me, mo, ae, ao)
    assert not ace[0].any() and ace[1:].all() and aco[1, 3] and aco[2, 5] and aco.sum() == 2
    assert logp[0] == 0 and ent[0] == 0                # no active head
    lp = torch.log_softmax(le[1], -1)
    want = lp.gather(1, ae[1][:, None]).sum() + torch.log_softmax(lo[1, 3], -1)[ao[1, 3]]
    assert torch.isclose(logp[1], want)
    e_entry = -(lp.exp() * lp).sum(1)
    e_open = -(torch.softmax(lo[1, 3], -1) * torch.log_softmax(lo[1, 3], -1)).sum()
    assert torch.isclose(ent[1], (e_entry.sum() + e_open) / 8)
    assert torch.isfinite(logp).all() and torch.isfinite(ent).all()
    logp.sum().backward()
    assert all(torch.isfinite(p.grad).all() for p in m.parameters() if p.grad is not None)


def test_tensors_equal_deep():
    a = {"x": [torch.ones(2), np.arange(3)], "y": 1.0}
    assert tensors_equal(a, {"x": [torch.ones(2), np.arange(3)], "y": 1.0})
    assert not tensors_equal(a, {"x": [torch.ones(2) * 2, np.arange(3)], "y": 1.0})
