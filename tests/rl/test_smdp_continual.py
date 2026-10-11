"""A6 continual skeleton: replay mix + regime balance, continuous evaluation ledger across months, anchor delta."""
import numpy as np, pandas as pd
from btcusdt_quant.rl import smdp_batch as SB, smdp_continual as CT, smdp_reward as RW, smdp_ppo as SP
from btcusdt_quant.rl import signal_store as SG


def synth(days=200, seed=0):
    rng = np.random.default_rng(seed)
    n = days * 1440
    t = SG.CLOCK_START.value + np.arange(n, dtype=np.int64) * 60_000_000_000
    c = 30_000 * np.exp(np.cumsum(rng.normal(0, 6e-4, n)) + np.sin(np.arange(n) / 40_000) * 0.2)
    o = np.r_[c[0], c[:-1]]
    h, l = np.maximum(o, c) * 1.0003, np.minimum(o, c) * 0.9997
    rv = np.full(n, 50.0)
    mk = {"t": t, "o": o, "h": h, "l": l, "c": c, "frate": np.full(n, np.nan), "rv": rv, "rv_ref": rv.copy(),
          "m": np.ones(n), "clock0": int(SG.CLOCK_START.value)}
    rows = n // 5 + 10
    return mk, (np.zeros((rows, 880), np.float32), np.zeros((rows, 60), np.float32))


def test_replay_mix_and_regime_balance():
    mk, _ = synth()
    months = CT.month_starts("2021-02", "2021-08")
    smp = CT.ReplaySampler(mk["t"], mk["c"], months, months[-1] + pd.offsets.MonthBegin(1), CT.ContinualConfig(),
                           int(mk["t"][-1]))
    st, en = smp.sample(np.random.default_rng(1), np.arange(400))
    b = smp.bucket_of(st)
    share = np.bincount(b, minlength=3) / len(b)
    assert abs(share[0] - 0.5) < 0.02 and abs(share[1] - 0.25) < 0.02 and abs(share[2] - 0.25) < 0.02
    sg = CT.regime_sign(mk["t"], mk["c"], st, 30)
    assert 0.35 < (sg > 0).mean() < 0.65 and np.all(en <= int(mk["t"][-1])) and np.all(en - st <= 28 * CT.DAY_NS)


def test_continuous_eval_ledger_and_anchor_delta():
    mk, feats = synth(days=120)
    env = SB.BatchEnv(mk, feats, [(2, 0.5), (5, 2.0)], SP.A5_TARGETS, SP.A4_WAITS, RW.RewardConfig(), 50.0)
    m1, m2, m3 = (pd.Timestamp(x, tz="UTC").value for x in ("2021-03-01", "2021-04-01", "2021-05-01"))
    env.reset_env(np.arange(2), np.array([m1, m1]), np.array([m2, m2]))
    rng = np.random.default_rng(0)
    pol = lambda x: (rng.integers(0, 9, len(x)), rng.integers(0, 3, len(x)))  # noqa: E731
    led = CT.ContinualLedger()
    a = CT.eval_month(env, pol, m2)
    u_carry = env.ST[:, 0].copy()
    b = CT.eval_month(env, pol, m3)                                   # same env, no flat reset at the boundary
    for k, cell in enumerate(("o2_p0.5", "o5_p2.0")):
        led.record("2021-03", "policy", cell, a["net4"][k], a["fills"][k], a["minutes"][k])
        led.record("2021-03", "anchor", cell, 0.0, 0.0, a["minutes"][k])
    assert np.all(a["minutes"] == (m2 - m1) // 60_000_000_000) and np.all(b["minutes"] == (m3 - m2) // 60_000_000_000)
    assert np.isfinite(u_carry).all()
    d = led.deltas()
    assert "delta" in d and np.allclose(d.delta.to_numpy(), d.policy.to_numpy())
