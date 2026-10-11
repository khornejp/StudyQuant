"""A6-P0 parity: batched SoA kernel + batched reward == scalar kernel + scalar reward on 100k random decisions."""
import numpy as np
from btcusdt_quant.rl import maker_kernel as MK, smdp_batch as SB, smdp_reward as RW
from tests.rl.test_maker_kernel import market


def test_batch_equals_scalar_100k():
    m = market(n=60 * 1440, seed=21)
    cfg = RW.RewardConfig(idle_bps_per_h=0.4, inventory_bps_per_h=0.2, turnover_bps=0.05, f_kind="sqrt", f_param=0.3)
    rv = MK.rv24h(m.c)
    mglob = RW.m_of_t(rv, np.full(m.N, float(np.median(rv[1440:]))), cfg)
    fr = SB.frate_global(m.t, m.ft, m.fr)
    rng = np.random.default_rng(0)
    cells = [(o, p) for o in (2, 5) for p in (0.5, 1.0, 2.0)]
    E, D = 60, 20000
    ce = [cells[e % 6] for e in range(E)]
    start = rng.integers(2000, 4000, E)
    scal = [MK.Kernel(m.o, m.h, m.l, m.c, m.t, m.ft, m.fr, c[0], c[1]) for c in ce]
    for e in range(E):
        scal[e].reset(int(start[e]))
        scal[e].mpath = mglob
    ST = np.zeros((E, MK.S_NSTATE))
    gi = start.astype(np.int64).copy()
    endx = np.full(E, m.N, np.int64)
    off = np.array([c[0] for c in ce], float); pen = np.array([c[1] for c in ce], float)
    nb_ = np.zeros(E, np.int64); jo = np.zeros(E, np.int64)
    net_b, u_b, k_b = (np.zeros((E, SB.MAX_BLOCKS)) for _ in range(3))
    last = np.zeros(E)
    worst = 0.0
    n_dec = 0
    for d in range(D):
        a_t = rng.integers(0, 9, E); a_w = rng.integers(0, 5, E)
        tg = np.asarray(MK.TARGETS)[a_t]; wt = np.asarray(MK.WAITS)[a_w]
        for e in np.flatnonzero(gi >= m.N - 1):          # restart finished envs at a new random start (both books)
            s0 = int(rng.integers(2000, 4000))
            scal[e].reset(s0)
            ST[e] = 0.0
            gi[e] = s0
            last[e] = 0.0
        live = gi < m.N - 1
        if n_dec >= 100_000:
            break
        gi0 = gi.copy()
        SB.advance_batch(m.o, m.h, m.l, m.c, m.t, fr, ST, gi, tg, wt, endx, off, pen, net_b, u_b, k_b, nb_, jo)
        rb = SB.batch_reward(net_b, u_b, k_b, mglob, gi0, nb_, np.abs(tg - last), cfg)
        for e in np.flatnonzero(live):
            k = scal[e]
            i0 = k.i
            r = k.step(float(tg[e]), int(wt[e]))
            rs = RW.step_reward(k.pnl, k.upath, k.kpath, mglob, i0, r["j"], r["d_target"], cfg)
            worst = max(worst, abs(rs["net4"] - rb["net4"][e]), abs(rs["reward"] - rb["reward"][e]),
                        abs(rs["reward_discounted"] - rb["reward_discounted"][e]), abs(k.st[MK.S_U] - ST[e, MK.S_U]),
                        abs(k.st[MK.S_FILLS] - ST[e, MK.S_FILLS]), abs(k.st[MK.S_EQ] - ST[e, MK.S_EQ]))
            assert r["j"] == jo[e]
            n_dec += 1
        last = tg.copy()
        gi = jo.copy()
    assert n_dec >= 100_000 and worst <= 1e-8, (n_dec, worst)
