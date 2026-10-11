"""Duration-aware GAE against hand-computed values (variable durations, episode end)."""
import math
import torch
from btcusdt_quant.rl import maker_kernel as MK
from btcusdt_quant.rl.smdp_ppo import compute_gae_smdp


def test_gae_variable_duration_by_hand():
    g = [MK.gamma(5), MK.gamma(1440), MK.gamma(240)]
    r = torch.tensor([[1.0], [-2.0], [0.5]])
    v = torch.tensor([[0.3], [0.1], [-0.2]])
    d = torch.tensor([[0.0], [0.0], [1.0]])
    last = torch.tensor([9.9])                                    # ignored: the last step ends the episode
    gd = torch.tensor([[x] for x in g])
    lam = 0.95
    d2 = 0.5 - (-0.2)                                             # done: no bootstrap
    a2 = d2
    d1 = -2.0 + g[1] * (-0.2) - 0.1
    a1 = d1 + g[1] * lam * a2
    d0 = 1.0 + g[0] * 0.1 - 0.3
    a0 = d0 + g[0] * lam * a1
    adv, ret = compute_gae_smdp(r, v, d, last, gd, lam)
    assert torch.allclose(adv[:, 0], torch.tensor([a0, a1, a2]), atol=1e-6)
    assert torch.allclose(ret, adv + v)
    assert math.isclose(MK.gamma(30 * 1440), 0.5)


def test_gae_bootstraps_with_duration_gamma():
    r = torch.zeros(1, 2)
    v = torch.zeros(1, 2)
    adv, _ = compute_gae_smdp(r, v, torch.zeros(1, 2), torch.tensor([1.0, 1.0]),
                              torch.tensor([[MK.gamma(5), MK.gamma(1440)]]), 0.95)
    assert torch.allclose(adv[0], torch.tensor([MK.gamma(5), MK.gamma(1440)]))
