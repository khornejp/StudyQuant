"""SMDP env on the real DEV store: short-only bound, reward/ledger identity, bit-exact env resume."""
import copy
import numpy as np, pytest
from btcusdt_quant.rl import dev_data as DD, smdp_env as SE, smdp_ppo as SP, u35

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def data():
    minutes, fund, _ = DD.load_dev()
    fs = u35.assert_settlement_grid(u35.scheduled(fund))
    return SE.SmdpData(ROOT / "out/rl_allocator_20261010/signal_store_5m", minutes, fs, ("2021-01-30", "2022-01-01"),
                       "2023-01-01")


def test_env_identity_bounds_and_resume(data):
    T = (0.0, -0.25, -0.5, -0.75, -1.0)
    cells = [(2, 0.5), (5, 2.0)]
    ev = SE.SmdpEnvs(data, cells, T, 90, seed=3)
    rng = np.random.default_rng(0)
    for _ in range(40):
        for f in ev.step(rng.integers(0, 5, 2), rng.integers(0, 5, 2)):
            assert f["identity_err"] <= 1e-8 and f["u_max"] <= 0 and f["u_absmax"] <= 1
    sd = copy.deepcopy(ev.state_dict())
    acts = [(rng.integers(0, 5, 2), rng.integers(0, 5, 2)) for _ in range(30)]
    a = [ev.step(*x) for x in acts]
    ev2 = SE.SmdpEnvs(data, cells, T, 90, seed=99)
    ev2.load_state_dict(sd)
    b = [ev2.step(*x) for x in acts]
    assert all(p["net4"] == q["net4"] and p["fills"] == q["fills"] for x, y in zip(a, b) for p, q in zip(x, y))
    assert np.isfinite(ev.obs()).all() and ev.obs().shape == (2, data.obs_dim)


def test_trainer_resume_bit_exact(data):
    from btcusdt_quant.rl.allocator_ppo import tensors_equal
    cfg = SP.SmdpConfig(rollout=6, minibatch=12, envs_per_cell=1)
    cells = [(2, 0.5), (5, 2.0)]
    t1 = SP.SmdpTrainer(SE.SmdpEnvs(data, cells, (0.0, -0.5, -1.0, -0.25, -0.75), 90, 1), cfg, 1)
    t1.run_update()
    sd = t1.state_dict()
    t1.run_update(); t1.run_update()
    t2 = SP.SmdpTrainer(SE.SmdpEnvs(data, cells, (0.0, -0.5, -1.0, -0.25, -0.75), 90, 1), cfg, 1)
    t2.load_state_dict(sd)
    t2.run_update(); t2.run_update()
    assert tensors_equal(t1.state_dict()["model"], t2.state_dict()["model"])


def test_val_episode_truncated_at_end(data):
    import pandas as pd
    ev = SE.SmdpEnvs(data, [(2, 0.5)], (0.0, -0.5, -1.0, -0.25, -0.75), 90, seed=0)
    a, b = pd.Timestamp("2022-01-01", tz="UTC").value, pd.Timestamp("2023-01-01", tz="UTC").value
    ev._reset(0, a, b)
    rng = np.random.default_rng(1)
    mins, last, done = 0, -1, False
    while not done:
        f = ev.step_one(0, int(rng.integers(0, 5)), 4 if rng.random() < 0.7 else int(rng.integers(0, 5)))
        mins += f["minutes"]
        last = max(last, f["last_time"])
        done = f["done"]
    assert mins == 525_600 and last == b - 60_000_000_000
