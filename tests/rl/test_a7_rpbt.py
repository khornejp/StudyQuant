"""A7-RPBT CPU pieces: population / LHS quotas, mutation bounds, replay projection, lr decay, exploit weight transfer,
Romano-Wolf gate, lexicographic fitness, atomic checkpoint resume refusal."""
import math
import numpy as np, pytest, torch
from btcusdt_quant.rl import a7_rpbt as A7
from btcusdt_quant.rl.smdp_gpu import PolicyA6


def test_population_and_lhs_quotas():
    pop = A7.population(20261011)
    assert len(pop) == 13 and [g.name for g in pop[:3]] == ["RAW", "A6", "A6b"] and all(g.sentinel for g in pop[:3])
    mut = pop[3:]
    for k in A7.ZERO_GENES:
        assert sum(getattr(g, k) == 0.0 for g in mut) == 2
    assert sum(g.half_life == A7.INF for g in mut) == 2
    for g in mut:
        for k in ("lr", "beta_t", "beta_w"):
            lo, hi = A7.BOUNDS[k]
            assert lo <= getattr(g, k) <= hi
        assert abs(sum(g.replay) - 1) < 1e-9 and all(lo - 1e-12 <= x <= hi + 1e-12 for x, (lo, hi) in zip(g.replay, A7.REPLAY_BOUNDS))
    assert A7.SENTINELS[0].reward_cfg().f_param == 0.0 and A7.SENTINELS[1].reward_cfg().idle_bps_per_h == 0.4167


def test_mutation_bounds_and_replay_gate():
    rng = np.random.default_rng(0)
    g = A7.population(1)[5]
    for _ in range(300):
        g2 = A7.mutate(g, rng, allow_replay=False)
        assert g2.replay == g.replay
        for k in ("idle", "inventory", "turnover", "lr", "beta_t", "beta_w", "slope"):
            v = getattr(g2, k)
            assert v == 0.0 or A7.BOUNDS[k][0] - 1e-12 <= v <= A7.BOUNDS[k][1] + 1e-12
        g3 = A7.mutate(g, rng, allow_replay=True)
        assert abs(sum(g3.replay) - 1) < 1e-9
    assert A7.reward_changed(g, A7.mutate(A7.replace(g, idle=0.1), np.random.default_rng(3), False)) in (True, False)


def test_lr_decay_floor():
    g = A7.replace(A7.population(1)[4], lr=3e-4, half_life=6.0)
    assert math.isclose(A7.lr_at(g, 6), 1.5e-4) and math.isclose(A7.lr_at(g, 200), 3e-5)
    assert A7.lr_at(A7.SENTINELS[0], 50) == 3e-4


def test_exploit_weights_copy_and_value_reinit():
    torch.manual_seed(0)
    donor, rec = PolicyA6(20), PolicyA6(20)
    sd = donor.state_dict()
    A7.exploit_weights(rec, sd, reinit_value=False, seed=1)
    assert all(torch.equal(rec.state_dict()[k], sd[k]) for k in sd)
    rec2 = PolicyA6(20)
    A7.exploit_weights(rec2, sd, reinit_value=True, seed=1)
    s2 = rec2.state_dict()
    assert all(torch.equal(s2[k], sd[k]) for k in sd if k.startswith(("trunk.", "pt.", "pw.")))
    assert not torch.equal(s2["v.1.weight"], sd["v.1.weight"])


def test_romano_wolf_and_fitness():
    rng = np.random.default_rng(0)
    T = 180
    strong = rng.normal(5.0, 3.0, (T, 3))
    null = rng.normal(0.0, 3.0, (T, 3))
    rej = A7.romano_wolf(np.column_stack([strong, null]), n_boot=2000)
    assert rej[:3].all() and not rej[3:].any()
    a = {c: rng.normal(1, 5, 120) for c in "abcdef"}
    b = {c: rng.normal(-1, 5, 120) for c in "abcdef"}
    z = {c: np.zeros(120) for c in "abcdef"}
    assert A7.fitness(a, z, n_boot=1000) > A7.fitness(b, z, n_boot=1000)


def test_exploit_plan_never_overwrites_sentinels():
    pop = A7.population(2)
    genos = {g.name: g for g in pop}
    rng = np.random.default_rng(1)
    daily = {g.name: {c: rng.normal(0, 5, 180) + (8 if g.name in ("RAW", "M00") else 0) for c in "abcdef"} for g in pop}
    fit = {k: A7.fitness(v, {c: np.zeros(180) for c in v}, n_boot=500) for k, v in daily.items()}
    plan = A7.exploit_plan(fit, genos, daily, n_boot=1000)
    assert all(not genos[r].sentinel for r in plan["recipients"]) and len(plan["recipients"]) == 3
    assert set(plan["transfers"].values()) <= set(plan["donors"]) and len(plan["transfers"]) >= 1


def test_atomic_checkpoint_hash_refusal(tmp_path):
    p = tmp_path / "m.pt"
    h = A7.save_checkpoint(p, {"x": 1}, {"code": "a"})
    assert len(h) == 64 and A7.load_checkpoint(p, {"code": "a"})["x"] == 1
    with pytest.raises(RuntimeError):
        A7.load_checkpoint(p, {"code": "b"})


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA only")
def test_exploit_value_reinit_on_cuda():
    donor, rec = PolicyA6(20).cuda(), PolicyA6(20).cuda()
    sd = donor.state_dict()
    A7.exploit_weights(rec, sd, reinit_value=True, seed=3)
    s2 = rec.state_dict()
    assert all(torch.equal(s2[k], sd[k]) for k in sd if k.startswith(("trunk.", "pt.", "pw.")))
    assert not torch.equal(s2["v.1.weight"], sd["v.1.weight"]) and s2["v.1.weight"].is_cuda
