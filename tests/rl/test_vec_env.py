"""Vectorized RL env (plan 3 Task 3, contract C1-C7 + frozen reward): parity with core.simulate via vec_env.replay."""
import math, time
import numpy as np, pandas as pd, pytest
from btcusdt_quant.sim import costs
from btcusdt_quant.rl.state import StateStore
from btcusdt_quant.rl.vec_env import ACCOUNT_NAMES, SIDES, EnvConfig, VecTradingEnv, replay

T0 = pd.Timestamp("2024-03-01", tz="UTC")
MIN = pd.Timedelta(minutes=1)
STEP = pd.Timedelta(minutes=15)
NO_FUNDING = (np.zeros(0, np.int64), np.zeros(0))


def market(seed, days=3, gaps=20):
    rng = np.random.default_rng(seed)
    n = days * 1440
    c = 60000 * np.exp(np.cumsum(rng.normal(0, 8e-4, n)))
    o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 2e-4, n))        # open != previous close: gap marks matter
    m = pd.DataFrame({"open_time": T0 + MIN * np.arange(n), "open": o, "high": np.maximum(o, c) * 1.0005,
                      "low": np.minimum(o, c) * 0.9995, "close": c})
    # gaps never hit a settlement minute: core books trade funding by funding_events even for a missing minute,
    # minute pnl only at existing minutes (real minutes have no gaps: data.validate_minutes)
    settle = np.flatnonzero((m.open_time.dt.minute == 0) & m.open_time.dt.hour.isin([0, 8, 16]))
    return m.drop(rng.choice(np.setdiff1d(np.arange(n), settle), gaps, replace=False)).reset_index(drop=True) \
        if gaps else m


def make_store(start, end, missing=None, seed=0):
    times = pd.date_range(start, end, freq="15min", inclusive="left")
    rng = np.random.default_rng(seed)
    mask = np.zeros(len(times), bool) if missing is None else missing
    return StateStore(times.as_unit("ns").asi8, rng.normal(size=(len(times), 32, 4)).astype(np.float32),
                      rng.normal(size=(len(times), 3)).astype(np.float32), mask, ["a", "b", "c"], "S1")


def flat_market(closes, start=T0, n=None):
    """o = c = 100 except the given {minute offset: close}; each next open equals the previous close."""
    n = n or 4 * 15
    c = np.full(n, 100.0)
    for k, v in closes.items():
        c[k] = v
    o = np.r_[100.0, c[:-1]]
    return pd.DataFrame({"open_time": start + MIN * np.arange(n), "open": o, "high": np.maximum(o, c),
                         "low": np.minimum(o, c), "close": c})


def sample(mask, rng):
    return np.array([rng.choice(np.flatnonzero(row)) for row in mask], np.int8)


@pytest.mark.parametrize("seed", range(100))
def test_env_equals_core_simulate_random_actions(seed):
    rng = np.random.default_rng(seed)
    m, steps, n = market(seed), 64, 4
    start, end = T0, T0 + pd.Timedelta(days=3)
    store = make_store(start, end, missing=rng.random(288) < 0.15, seed=seed)
    fund = costs._settlement_arrays()
    env = VecTradingEnv(store, m, fund, start, end, n, EnvConfig(episode_steps=steps, randomize=seed % 2 == 1), seed)
    seq, static, mask = env.reset()
    assert static.shape == (n, 3 + len(ACCOUNT_NAMES)) and seq.shape == (n, 32, 4)
    for episode in range(2):
        k0, cost, slip, delay = env.k0.copy(), env.cost.copy(), env.slip.copy(), env.delay.copy()
        if seed % 2 == 0:
            assert (cost == 4).all() and (slip == 0).all() and (delay == 1).all()
        sides, minute, info_sum = [], [], {}
        for t in range(steps):
            a = sample(mask, rng)
            seq, static, mask, reward, net, done, info = env.step(a)
            sides.append(SIDES[a]); minute.append(info["minute_net"])
            for k in ("fees", "funding", "trades"):
                info_sum[k] = info_sum.get(k, 0) + info[k]
            np.testing.assert_allclose(net, info["minute_net"].sum(1), rtol=0, atol=1e-9)
            assert done.all() == (t == steps - 1) and done.any() == done.all()
        sides, minute = np.array(sides), np.concatenate(minute, axis=1)
        for e in range(n):
            t0 = pd.Timestamp(int(store.times[k0[e]]), tz="UTC")
            t1 = t0 + steps * STEP
            actions = pd.Series(sides[:, e], index=pd.date_range(t0, t1, freq="15min", inclusive="left"))
            ref = replay(actions, m, t0, t1, cost[e], delay[e], slip[e])
            grid = ref.minute_pnl.reindex(pd.date_range(t0, t1, freq="1min", inclusive="left"), fill_value=0.0)
            np.testing.assert_allclose(minute[e], grid.to_numpy(), rtol=0, atol=1e-9)
            assert ref.open_position is None and len(ref.trades) == info_sum["trades"][e]
            assert np.isclose(info_sum["fees"][e], ref.trades.fee_bps.sum(), rtol=0, atol=1e-9)
            assert np.isclose(info_sum["funding"][e], ref.trades.funding_bps.sum(), rtol=0, atol=1e-9)
        assert (env.t == 0).all() and (env.side == 0).all()          # auto reset: new episode, flat


def test_reward_formula():
    # long at T0 (fee 10), dip to -5 bps and back, rise to +10 bps, then forced close at the last close (fee 10)
    up = 100 * math.exp(1e-3)
    m = flat_market({20: 100 * math.exp(-5e-4), **{k: up for k in range(30, 60)}})
    store = make_store(T0, T0 + 4 * STEP)
    cfg = EnvConfig(episode_steps=4, randomize=False, cost_bps=(20, 20))
    env = VecTradingEnv(store, m, NO_FUNDING, T0, T0 + 4 * STEP, 1, cfg, 0)
    env.reset()
    got = [env.step(np.array([1], np.int8)) for _ in range(4)]
    net = [g[4][0] for g in got]
    reward = [g[3][0] for g in got]
    dd = [g[6]["dd_penalty"][0] for g in got]
    np.testing.assert_allclose(net, [-10, 0, 10, -10], rtol=0, atol=1e-9)
    np.testing.assert_allclose(dd, [10, 5, 0, 0], rtol=0, atol=1e-9)
    np.testing.assert_allclose(reward, [-40, -5, 10, -30], rtol=0, atol=1e-9)   # net -10 -> -30; MDD +5 -> -5
    for g in got:
        info = g[6]
        np.testing.assert_allclose(info["loss_penalty"], 2 * np.maximum(0, -info["net"]), rtol=0, atol=0)
        np.testing.assert_allclose(g[3], info["net"] - info["loss_penalty"] - info["dd_penalty"], rtol=0, atol=0)
    assert got[-1][5].all()


def test_account_channels():
    m = flat_market({20: 100 * math.exp(-5e-4), **{k: 100 * math.exp(1e-3) for k in range(30, 60)}})
    store = make_store(T0, T0 + 4 * STEP)
    env = VecTradingEnv(store, m, NO_FUNDING, T0, T0 + 4 * STEP, 1,
                        EnvConfig(episode_steps=4, randomize=False, cost_bps=(20, 20)), 0)
    _, static, _ = env.reset()
    np.testing.assert_allclose(static[0, 3:], [0, 0, 0, 0, 0, 0, 1], rtol=0, atol=1e-6)
    _, static, *_ = env.step(np.array([1], np.int8))       # filled at T0+1, flat price: dd 10, mdd 10
    np.testing.assert_allclose(static[0, 3:], [1, math.log1p(14), 0, 0, .1, .1, .75], rtol=0, atol=1e-6)
    _, static, *_ = env.step(np.array([1], np.int8))       # dip -5 bps and back: MAE 5, dd 10, mdd 15
    np.testing.assert_allclose(static[0, 3:], [1, math.log1p(29), 0, .05, .1, .15, .5], rtol=0, atol=1e-6)
    _, static, *_ = env.step(np.array([1], np.int8))       # +10 bps unrealized, equity back to 0
    np.testing.assert_allclose(static[0, 3:], [1, math.log1p(44), .1, .05, 0, .15, .25], rtol=0, atol=1e-6)


def test_episode_never_crosses_train_end():
    start, end = T0 + pd.Timedelta(days=1), T0 + pd.Timedelta(days=20, minutes=7)
    m = market(0, days=21, gaps=0)
    store = make_store(T0, T0 + pd.Timedelta(days=21))
    env = VecTradingEnv(store, m, NO_FUNDING, start, end, 1000, EnvConfig(randomize=True), 0)
    starts = []
    for _ in range(10):
        env.reset()
        starts.append(store.times[env.k0])
    starts = np.concatenate(starts)
    assert len(starts) == 10_000
    assert (starts >= start.value).all() and (starts + 1344 * STEP.value <= end.value).all()
    assert starts.max() == (T0 + pd.Timedelta(days=6)).value and starts.min() == start.value   # both edges reachable
    assert set(env.delay.tolist()) == {1, 2, 3, 4, 5} and (env.delay == 1).mean() > 0.5
    assert 4 <= env.cost.min() and env.cost.max() <= 12 and 0 <= env.slip.min() and env.slip.max() <= 10


def test_episode_never_starts_in_warmup():
    t0 = pd.Timestamp("2022-03-01", tz="UTC")                 # rolling.TRAIN_START; M/L need 7 days of warm-up
    missing = np.zeros(22 * 96, bool)
    missing[:7 * 96 + 5] = True
    missing[[800, 900]] = True                                 # later missing rows do not move the first valid T
    store = make_store(t0, t0 + pd.Timedelta(days=22), missing=missing)
    m = market(0, days=22, gaps=0).assign(open_time=lambda f: f.open_time - T0 + t0)
    env = VecTradingEnv(store, m, NO_FUNDING, t0, t0 + pd.Timedelta(days=22), 1000, EnvConfig(randomize=True), 0)
    first = store.times[7 * 96 + 5]
    starts = np.concatenate([store.times[(env.reset(), env.k0)[1]] for _ in range(10)])
    assert len(starts) == 10_000 and starts.min() == first and (starts >= first).all()
    with pytest.raises(ValueError):
        VecTradingEnv(make_store(t0, t0 + pd.Timedelta(days=21), missing=np.ones(21 * 96, bool)), m, NO_FUNDING,
                      t0, t0 + pd.Timedelta(days=21), 1, EnvConfig(), 0)


def test_pending_fill_after_episode_end_cancelled():
    m = flat_market({k: 100 * math.exp(2e-3) for k in range(50, 60)})
    store = make_store(T0, T0 + 4 * STEP)
    cfg = EnvConfig(episode_steps=4, randomize=False, cost_bps=(6, 6), slip_bps=(5, 5))
    for held, last in ((0, 1), (1, 2)):        # flat -> long at the last step: no fill; long -> short: no reversal
        env = VecTradingEnv(store, m, NO_FUNDING, T0, T0 + 4 * STEP, 1, cfg, 0)
        env.reset()
        for _ in range(3):
            *_, info = env.step(np.array([held], np.int8))
        *_, net, done, info = env.step(np.array([last], np.int8))
        assert done.all()
        if held == 0:
            assert net[0] == 0 and info["trades"][0] == 0 and info["fees"][0] == 0
        else:                                  # held over the jump (+20 bps), closed at the last close c*(1-s)
            exit_ = 20 + 1e4 * math.log(1 - 5e-4)
            assert np.isclose(net[0], exit_ - 3, rtol=0, atol=1e-9)
            assert info["trades"][0] == 1 and info["fees"][0] == 3
            assert np.isclose(info["slippage"][0], -1e4 * math.log(1 - 5e-4), rtol=0, atol=1e-12)
            assert np.isclose(info["minute_net"][0, -1], 1e4 * math.log(1 - 5e-4) - 3, rtol=0, atol=1e-9)
        actions = pd.Series(SIDES[[held, held, held, last]], index=pd.date_range(T0, periods=4, freq="15min"))
        ref = replay(actions, m, T0, T0 + 4 * STEP, 6.0, 1, 5.0)
        assert ref.open_position is None and (ref.trades.exit_reason == "data_end").sum() == held
        if held:
            t = ref.trades.iloc[-1]
            assert t.exit_time == T0 + 59 * MIN and np.isclose(t.exit_price, m.close.iloc[-1] * (1 - 5e-4))


def test_action_mask_on_missing_detector():
    store = make_store(T0, T0 + 4 * STEP, missing=np.array([False, True, False, True]))
    env = VecTradingEnv(store, flat_market({}), NO_FUNDING, T0, T0 + 4 * STEP, 1,
                        EnvConfig(episode_steps=4, randomize=False), 0)
    _, _, mask = env.reset()
    assert mask.tolist() == [[True, True, True]]
    _, _, mask, *_ = env.step(np.array([1], np.int8))          # long; next T missing
    assert mask.tolist() == [[True, True, False]]               # hold or flat, no reversal
    with pytest.raises(ValueError):
        env.step(np.array([2], np.int8))
    _, _, mask, *_ = env.step(np.array([0], np.int8))          # flat at a missing T is allowed
    assert mask.tolist() == [[True, True, True]]
    _, _, mask, *_ = env.step(np.array([0], np.int8))
    assert mask.tolist() == [[True, False, False]]              # flat at a missing T: only flat
    with pytest.raises(ValueError):
        env.step(np.array([1], np.int8))
    with pytest.raises(ValueError):
        env.step(np.array([3], np.int8))


def test_always_flat_zero_reward():
    m = market(1)
    store = make_store(T0, T0 + pd.Timedelta(days=3))
    env = VecTradingEnv(store, m, costs._settlement_arrays(), T0, T0 + pd.Timedelta(days=3), 8,
                        EnvConfig(episode_steps=64, randomize=True), 1)
    env.reset()
    for _ in range(130):
        _, static, _, reward, net, done, info = env.step(np.zeros(8, np.int8))
        assert (reward == 0).all() and (net == 0).all()
        for k in ("net", "loss_penalty", "dd_penalty", "fees", "slippage", "funding", "trades"):
            assert (info[k] == 0).all(), k
        assert (static[:, 3:9] == 0).all()


def test_state_dict_round_trip():
    """PPO resume: restoring a saved env state replays the same future exactly."""
    m, rng = market(2), np.random.default_rng(0)
    make = lambda seed: VecTradingEnv(make_store(T0, T0 + pd.Timedelta(days=3)), m, costs._settlement_arrays(), T0,
                                      T0 + pd.Timedelta(days=3), 8, EnvConfig(episode_steps=16), seed)
    env = make(1)
    _, _, mask = env.reset()
    for _ in range(21):
        _, _, mask, *_ = env.step(sample(mask, rng))
    state, acts = env.state_dict(), [sample(mask, rng) for _ in range(30)]
    other = make(7)
    other.reset()
    other.load_state_dict(state)
    for a in acts:
        a = np.where(env.mask[np.arange(8), a], a, 0).astype(np.int8)
        for x, y in zip(env.step(a)[:6], other.step(a)[:6]):
            np.testing.assert_array_equal(x, y)


@pytest.mark.slow
def test_real_data_parity_and_benchmark():
    from btcusdt_quant.rl.state import cached_state_store
    from btcusdt_quant.sim.rolling import END, TRAIN_START, WINDOWS
    from btcusdt_quant.sim.strategies import Context
    ctx = Context.load()
    store = cached_state_store(ctx, TRAIN_START, END, "S1")
    w, n = WINDOWS[0], 256
    env = VecTradingEnv(store, ctx.minutes, costs._settlement_arrays(), w.train_start, w.train_end, n,
                        EnvConfig(randomize=True), 0)
    rng = np.random.default_rng(0)
    _, static, mask = env.reset()
    assert static.shape == (n, len(store.feature_names) + len(ACCOUNT_NAMES))
    k0, cost, slip, delay = env.k0.copy(), env.cost.copy(), env.slip.copy(), env.delay.copy()
    first = store.times[np.flatnonzero(~store.mask_missing)[0]]
    assert first > w.train_start.value and env.starts.min() == np.searchsorted(store.times, first)   # no warm-up start
    sides, minute = [], []
    tic = time.perf_counter()
    for _ in range(1344):
        a = sample(mask, rng)
        _, _, mask, _, _, done, info = env.step(a)
        sides.append(SIDES[a[:4]]); minute.append(info["minute_net"][:4])
    wall = time.perf_counter() - tic
    assert done.all()
    sides, minute = np.array(sides), np.concatenate(minute, axis=1)
    for e in range(4):
        t0 = pd.Timestamp(int(store.times[k0[e]]), tz="UTC")
        t1 = t0 + 1344 * STEP
        ref = replay(pd.Series(sides[:, e], index=pd.date_range(t0, t1, freq="15min", inclusive="left")),
                     ctx.minutes, t0, t1, cost[e], delay[e], slip[e])
        grid = ref.minute_pnl.reindex(pd.date_range(t0, t1, freq="1min", inclusive="left"), fill_value=0.0)
        np.testing.assert_allclose(minute[e], grid.to_numpy(), rtol=0, atol=1e-9)
    tic = time.perf_counter()
    for _ in range(1344):
        env.step(np.zeros(n, np.int8))
    fast = time.perf_counter() - tic
    print(f"\nBENCH n_envs={n}: {1344 / fast:.0f} vec-steps/s ({1344 * n / fast:.0f} transitions/s) env only; "
          f"{1344 / wall:.0f} vec-steps/s incl. python random-action sampling")
