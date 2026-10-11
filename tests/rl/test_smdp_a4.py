"""A4 pieces: block construction, entropy floor, duration-aware lambda, network size, stop-event count."""
import math
import numpy as np, torch
from btcusdt_quant.rl import smdp_env as SE, smdp_ppo as SP, maker_kernel as MK


def test_blocks_nonoverlap_tail():
    b = SE.make_blocks(("2021-01-30", "2022-01-01"))
    assert len(b) == 4 and b[0][1] == np.datetime64("2021-01-30").astype("datetime64[ns]").astype(np.int64)
    assert all(x[2] == y[1] for x, y in zip(b[:-1], b[1:])) and (b[-1][2] - b[-1][1]) // 86_400_000_000_000 == 66
    assert len(SE.make_blocks(("2021-01-30", "2025-01-01"))) == 16


def test_entropy_schedule_and_floor():
    assert SP.a4_schedule(1) == (0.010, 0.020) and SP.a4_schedule(18) == (0.005, 0.015) and SP.a4_schedule(68) == (0.002, 0.010)
    fl = SP.EntropyFloor(SP.A4Config())
    assert fl.betas(5)[1] == 0.020
    fl.observe(0.50)
    assert fl.betas(6)[1] == 0.05
    fl.observe(0.61)
    assert fl.betas(7)[1] == 0.05
    fl.observe(0.58)                                            # not >= .60: the run restarts
    fl.observe(0.62)
    assert fl.betas(8)[1] == 0.05
    fl.observe(0.65)
    assert fl.betas(9)[1] == 0.020


def test_lambda_d_gae_and_param_count():
    assert math.isclose(SP.lam_d(5), 0.95) and math.isclose(SP.lam_d(240), 0.95 ** 48)
    r = torch.tensor([[1.0], [0.0]]); v = torch.zeros(2, 1); d = torch.zeros(2, 1)
    g = torch.tensor([[MK.gamma(15)], [MK.gamma(240)]]); l = torch.tensor([[SP.lam_d(15)], [SP.lam_d(240)]])
    adv, _ = SP.compute_gae_smdp(r, v, d, torch.tensor([2.0]), g, l)
    a1 = 0 + MK.gamma(240) * 2.0
    assert torch.allclose(adv[:, 0], torch.tensor([1.0 + MK.gamma(15) * SP.lam_d(15) * a1, a1]))
    m = SP.SmdpPolicy(948, 5, 3, 64)
    assert sum(p.numel() for p in m.parameters()) == 65_481


def test_stop_event_counted_once():
    n = 400
    c = np.full(n, 100.0); c[200:] = 80.0                       # -2000 bps: position and day stop same minute
    o = np.r_[c[0], c[:-1]]; h, l = np.maximum(o, c), np.minimum(o, c)
    t = (np.arange(n) * 60_000_000_000).astype(np.int64)
    st = np.zeros(MK.S_NSTATE); st[MK.S_U], st[MK.S_Q] = 1.0, 0.01
    MK.advance(o, h, l, c, (t // 86_400_000_000_000).astype(np.int64), np.full(n, np.nan), st, np.zeros(n), np.zeros(n),
               100, 201, 1.0, 2.0, 0.5)
    assert st[MK.S_PSTOP] == 1 and st[MK.S_DSTOP] == 1 and st[MK.S_NEV] == 1 and st[MK.S_DSZ] == 1.0
