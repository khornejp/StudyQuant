"""A8 locked design: genome, recurrent model, observation, settlement, period split, and resume."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from btcusdt_quant.rl import a8_ga_rl as A8
from btcusdt_quant.rl import a8_selection as A8S
from btcusdt_quant.rl import maker_kernel as MK
from btcusdt_quant.rl import signal_store as SG
from btcusdt_quant.rl import smdp_reward as RW


def test_all_44_positive_gates_and_action_model_shapes():
    genomes = A8.population(n=8)
    assert len(SG.tokens()) == 44 and all(len(g.gates) == 44 and min(g.gates) >= 0.1 and max(g.gates) <= 2 for g in genomes)
    assert all(abs(np.mean(np.log(g.gates))) < 1e-10 for g in genomes)
    model = A8.fresh_model(genomes[0], market_dim=60, seed=1)
    x = torch.randn(7, model.obs_dim)
    joint, sl, tp, value, hidden = model(x)
    assert model.obs_dim == 44 * 20 + 60 + len(A8.ACCOUNT_CHANNELS)
    assert joint.shape == (7, 45) and sl.shape == tp.shape == (7, 5) and value.shape == (7,)
    assert hidden.shape == (1, 7, 256)
    target, wait = A8.decode_joint(np.arange(45))
    assert np.array_equal(A8.TARGETS[target], np.repeat(A8.TARGETS, 5))
    assert np.array_equal(A8.WAITS[wait], np.tile(A8.WAITS, 9))


def test_ga_has_no_weight_inheritance_and_raw_fitness():
    genome = A8.population(n=2)[0]
    parent = A8.fresh_model(genome, 60, 7)
    with torch.no_grad():
        next(parent.parameters()).add_(100)
    child = A8.fresh_model(genome, 60, 7)
    clean = A8.fresh_model(genome, 60, 7)
    assert all(torch.equal(a, b) for a, b in zip(child.parameters(), clean.parameters()))
    assert not torch.equal(next(parent.parameters()), next(child.parameters()))
    assert A8.raw_net4_fitness({"a": [1, 2], "b": [-1, 4]}) == (3.0, 3.0)
    offspring = A8.crossover_mutate(A8.population(n=2)[0], A8.population(n=2)[1], np.random.default_rng(3), "X")
    assert len(offspring.gates) == 44 and abs(np.mean(np.log(offspring.gates))) < 1e-10
    population = A8.population(n=4)
    fitness = {genome.name: (i, i) for i, genome in enumerate(population)}
    next_gen = A8.next_generation(population, fitness, seed=3, generation=1)
    assert len(next_gen) == 4 and [genome.name for genome in next_gen] == [f"G01_{i:02d}" for i in range(4)]
    assert next_gen[0].gates == population[-1].gates and next_gen[1].gates == population[-2].gates


def test_exit_shaping_genome_bounds_serialization_and_determinism():
    genomes = A8.population(n=64)
    for genome in genomes:
        assert genome.cap_penalty_bps == 0 or A8.CAP_PENALTY_BOUNDS[0] <= genome.cap_penalty_bps <= A8.CAP_PENALTY_BOUNDS[1]
        assert genome.tp_profit_reward == 0 or A8.EXIT_MULTIPLIER_BOUNDS[0] <= genome.tp_profit_reward <= A8.EXIT_MULTIPLIER_BOUNDS[1]
        assert genome.loss_penalty == 0 or A8.EXIT_MULTIPLIER_BOUNDS[0] <= genome.loss_penalty <= A8.EXIT_MULTIPLIER_BOUNDS[1]
        assert A8.Genome.from_json(genome.to_json()) == genome
    assert any(g.cap_penalty_bps == 0 for g in genomes)
    left = A8.crossover_mutate(genomes[0], genomes[1], np.random.default_rng(9), "X")
    right = A8.crossover_mutate(genomes[0], genomes[1], np.random.default_rng(9), "X")
    assert left == right
    rng = np.random.default_rng(10)
    for index in range(1000):
        A8.crossover_mutate(genomes[index % 64], genomes[(index + 1) % 64], rng, f"M{index}")


@pytest.mark.parametrize("reason,pnl,size,expected", [
    (MK.EXIT_CAP, 10.0, 0.5, -1.5),
    (MK.EXIT_CAP, -10.0, 0.5, -5.5),
    (MK.EXIT_TP, 10.0, 0.5, 2.0),
    (MK.EXIT_TP, -10.0, 0.5, -4.0),
    (MK.EXIT_SL, 10.0, 0.5, 0.0),
    (MK.EXIT_SL, -10.0, 0.5, -4.0),
    (MK.EXIT_RL, 10.0, 0.5, 0.0),
    (MK.EXIT_RL, -10.0, 0.5, -4.0),
])
def test_exit_shaping_reason_profit_and_loss(reason, pnl, size, expected):
    assert MK._exit_shaping(reason, pnl, size, 3.0, 0.2, 0.4) == expected


def test_fixed_2021_scaler_rows_evaluate_first_and_test_guard():
    clock = np.array([pd.Timestamp(f"{year}-06-01", tz="UTC").value for year in (2021, 2022, 2023)])
    assert A8.fixed_2021_rows(clock).tolist() == [0]
    protocol = A8.monthly_protocol("2022-01", "2022-02")
    assert protocol == [("evaluate", "2022-01"), ("commit", "2022-01"), ("replay", "2022-01"),
                        ("train", "2022-01"), ("evaluate", "2022-02"), ("commit", "2022-02"),
                        ("replay", "2022-02"), ("train", "2022-02")]
    assert A8.GA_SELECTION == ("2022-01-01", "2024-01-01") and A8.FINAL_EVALUATION == ("2024-01-01", "2026-01-01")
    A8.assert_dev_path("dev_market/btcusdt_2025.parquet")
    A8.assert_dev_path("out/rl_allocator_20261010/dev_market/btcusdt_1m_dev_2020_2025.parquet")
    with pytest.raises(PermissionError):
        A8.assert_dev_path("market/2026-01.parquet")
    with pytest.raises(PermissionError):
        A8.assert_dev_path("market/test.parquet")
    assert [f"{month:%Y-%m}" for month in A8.selection_months()] == list(pd.period_range("2022-01", "2023-12", freq="M").astype(str))
    with pytest.raises(PermissionError):
        A8.selection_months("2023-12", "2024-01")
    with pytest.raises(PermissionError):
        A8.selection_months("2026-01", "2026-01")


def test_checkpoint_hash_refusal_and_rng_resume():
    generator = np.random.default_rng(11)
    state = {"rng": generator.bit_generator.state, "committed": "2023-12", "weights": torch.arange(5)}
    path = Path("out/rl_allocator_20261010/.test_a8_checkpoint.pt")
    try:
        assert len(A8.save_checkpoint(path, state, {"spec": "a"})) == 64
        loaded = A8.load_checkpoint(path, {"spec": "a"})
        resumed = np.random.default_rng(); resumed.bit_generator.state = loaded["rng"]
        generator2 = np.random.default_rng(); generator2.bit_generator.state = state["rng"]
        assert np.array_equal(resumed.integers(0, 100, 20), generator2.integers(0, 100, 20))
        with pytest.raises(RuntimeError):
            A8.load_checkpoint(path, {"spec": "changed"})
    finally:
        path.unlink(missing_ok=True)


def _batch_env(n=4000):
    t0 = SG.CLOCK_START.value
    t = t0 + np.arange(n, dtype=np.int64) * MK.MIN_NS
    c = np.full(n, 100.0)
    market = {"t": t, "o": c.copy(), "h": np.full(n, 101.0), "l": np.full(n, 99.0), "c": c,
              "frate": np.full(n, np.nan), "rv": np.full(n, 1000.0), "rv_ref": np.full(n, 1000.0),
              "m": np.ones(n), "clock0": t0}
    rows = n // 5 + 2
    features = (np.zeros((rows, 44 * 20), np.float32), np.zeros((rows, 60), np.float32))
    genome = A8.population(n=1)[0]
    env = A8.A8BatchEnv(market, features, [(2, 0.5)], tuple(A8.TARGETS), tuple(A8.WAITS),
                        genome.reward_config(), 1000.0, require_set=True)
    env.reset_env(np.array([0]), t[100], t[3500])
    return env


def test_a8_batch_observation_and_cap_step_done_false():
    env = _batch_env()
    obs = env.obs()
    assert obs.shape == (1, 960) and np.isfinite(obs).all()
    result = env.step(np.array([8]), np.array([4]), np.array([0]), np.array([0]))
    assert result["exit_reason"][0] == MK.EXIT_CAP and not result["done"][0]
    assert result["renewal_count"][0] == 1 and result["max_hold_min"][0] == 1440
    next_obs = env.obs()[0, -len(A8.ACCOUNT_CHANNELS):]
    assert next_obs[A8.ACCOUNT_CHANNELS.index("cap_event")] == 1
    assert next_obs[A8.ACCOUNT_CHANNELS.index("exit_cap")] == 1


def test_cap_shaping_is_immediate_and_raw_ledger_unchanged():
    env = _batch_env()
    genome = A8.population(n=1)[0]
    cfg = RW.RewardConfig(genome.idle, genome.risk, genome.turnover, "linear", genome.slope, 24.0,
                          quadratic_inventory=True, cap_penalty_bps=3.0, tp_profit_reward=0.2,
                          loss_penalty=0.4)
    env.cfg = cfg
    eq0 = env.ST[0, MK.S_EQ]
    result = env.step(np.array([8]), np.array([4]), np.array([0]), np.array([0]))
    expected = MK._exit_shaping(MK.EXIT_CAP, result["cap_pnl"][0], 1.0, 3.0, 0.2, 0.4)
    assert np.isclose(result["shaping"][0], expected)
    assert np.isclose(result["net4"][0], env.ST[0, MK.S_EQ] - eq0)
    assert np.isclose(result["reward"][0], result["net4"][0] - result["idle"][0]
                      - result["inventory"][0] - result["turnover"][0] + result["shaping"][0])


def test_recurrent_trainer_resume_is_deterministic():
    genome = A8.population(n=1)[0]
    first = A8.A8Trainer(_batch_env(), genome, 17, device="cpu")
    first.update(2)
    state = first.state_dict()
    resumed = A8.A8Trainer(_batch_env(), genome, 17, device="cpu")
    resumed.load_state_dict(state)
    left, right = first.update(2), resumed.update(2)
    assert left["net4"] == right["net4"] and left["identity_error"] == right["identity_error"]
    assert np.array_equal(first.env.ST, resumed.env.ST) and np.array_equal(first.observation, resumed.observation)
    assert all(torch.equal(a, b) for a, b in zip(first.model.state_dict().values(), resumed.model.state_dict().values()))


def test_selection_driver_resume_identity_and_three_seed_median():
    config_a = A8S.SelectionConfig("unit", population=2, generations=2, envs=2, start="2022-01", end="2022-01",
                                   pretrain_decisions=2, monthly_decisions=2, smoke=True, stop_after_commits=1)
    config_b = A8S.SelectionConfig("unit", population=2, generations=2, envs=2, start="2022-01", end="2022-01",
                                   pretrain_decisions=2, monthly_decisions=2, smoke=True, stop_after_commits=0)
    assert A8S._identity_config(config_a) == A8S._identity_config(config_b)
    assert [f"{month:%Y-%m}" for month in config_a.validate()] == ["2022-01"]
    assert A8.median_seed_fitness({20261012: (1, 10), 20261013: (3, 4), 20261014: (2, 7)}) == (2.0, 7.0)
    with pytest.raises(ValueError):
        A8.median_seed_fitness({1: (1, 1), 2: (2, 2)})


def test_selection_evaluator_refuses_final_evaluation_period():
    env = _batch_env()
    genome = A8.population(n=1)[0]
    market = {key: getattr(env, key) for key in ("t", "o", "h", "l", "c", "frate", "rv", "rv_ref", "m")}
    market["clock0"] = env.clock0
    with pytest.raises(PermissionError):
        A8.A8Evaluator(market, (env.tok, env.mk), genome.reward_config(), 1000.0, [(2, 0.5)],
                       pd.Timestamp("2023-12-01", tz="UTC").value,
                       pd.Timestamp("2024-02-01", tz="UTC").value, 1, device="cpu")


def test_a8_quadratic_reward_scalar_batch_definition():
    cfg = RW.RewardConfig(0.1, 0.2, 0.3, "linear", 0.05, 24, quadratic_inventory=True)
    out = RW.block_terms(np.array([10.0]), np.array([0.5]), np.array([60]), np.array([2.0]), 1.0, cfg)
    expected_risk = 0.2 / 12 * 2.0**2 * 0.5**2
    assert np.isclose(out["inventory"], expected_risk)
    assert np.isclose(out["reward"], 10 - out["idle"] - expected_risk - 0.3)
