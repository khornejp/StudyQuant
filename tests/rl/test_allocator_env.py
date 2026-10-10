"""RL allocator env (btcusdt_quant/rl/allocator_env.py, allocator_contracts.py): action contract, cap, availability,
history padding, fixed schema, ledger identities, slow-replay equality, fail-closed loading. Contract unit tests are
synthetic; env tests use the local DEV precompute/state (TEST rows are never loaded here) and skip if absent."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path
import numpy as np, pandas as pd, pytest
from btcusdt_quant.rl import allocator_contracts as C
from btcusdt_quant.rl import allocator_env as E

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out/rl_allocator_20261010"
HAVE = (OUT / "state/state_1h.parquet").exists() and (OUT / "provenance.json").exists()
real = pytest.mark.skipif(not HAVE, reason="local precompute/state not present")
TS = lambda x: pd.Timestamp(x, tz="UTC").value  # noqa: E731
SI = {s: i for i, s in enumerate(C.SLEEVES)}


# ---------------------------------------------------------------- contracts (synthetic)
def test_cap_projector_existing_first_pro_rata():
    assert np.allclose(C.project_cap(0.5, [0.5, 0.5]), 1.0)
    sc = C.project_cap(1.5, [0.5, 0.25, 0.25])
    assert np.allclose(sc, 0.5) and np.isclose((sc * [0.5, 0.25, 0.25]).sum(), 0.5)
    assert np.allclose(C.project_cap(2.0, [1.0]), 0.0) and np.allclose(C.project_cap(2.7, [1.0]), 0.0)


def test_sleeve_masks_unavailable_and_no_widening():
    e, p, o = C.sleeve_masks(False, True, True, "B3_AXC0", 1.0)
    assert e.tolist() == [True, False, False, False, False] and p.tolist() == [True, False]
    assert o.tolist() == [True, False, False, False]
    e, p, o = C.sleeve_masks(True, False, True, "B3_AXC0", 0.5)
    assert e.all() and o.tolist() == [True, False, False, True]                # 75 after 50 = widening: masked
    e, p, o = C.sleeve_masks(True, True, True, "C1v2", 1.0)
    assert o.tolist() == [True, False, False, True] and p.tolist() == [True, True]
    assert C.step_reward(5, 5, 1, 1, 3, 3) == 0.0
    assert C.step_reward(5, 2, 4, 1, 6, 2) == 3 - 0.10 * 3 - 0.25 * 4


# ---------------------------------------------------------------- real-data env (DEV only)
@pytest.fixture(scope="module")
def cell():
    return E.load_cell("o2_p1.0", allow_test=False)


def run(env, policy):
    obs, steps, tot, rs = None, 0, 0.0, 0.0
    obs = env.obs0
    infos = []
    while True:
        obs, r, done, info = env.step(policy(obs, env))
        tot += info["net_rl"]
        rs += r
        infos.append(info)
        steps += 1
        if done:
            return tot, rs, infos


def start(env, a, b):
    env.obs0 = env.reset(TS(a), TS(b))
    return env


def level_policy(levels):
    def p(obs, env):
        m = obs["masks"]
        return C.Action(tuple(lv if m.entry[k, lv] else 0 for k, lv in enumerate(levels)), (0,) * 7, (0,) * 7)
    return p


@real
def test_load_fail_closed(tmp_path):
    root = tmp_path / "rl"
    (root / "state").mkdir(parents=True)
    (root / "precompute").mkdir()
    for rel in ("provenance.json", "state/manifest.json", "state/normalizers.json", "precompute/manifest.json"):
        shutil.copyfile(OUT / rel, root / rel)
    p = root / "state/manifest.json"
    p.write_bytes(p.read_bytes().replace(b'"runtime_sec"', b'"runtime_sec_"'))
    with pytest.raises(E.SchemaError):
        E.load_cell("o2_p0.5", root=root)
    shutil.copyfile(OUT / "state/manifest.json", p)
    n = json.loads((root / "state/normalizers.json").read_text())
    n["1h"]["feature_order"] = n["1h"]["feature_order"][::-1]
    (root / "state/normalizers.json").write_text(json.dumps(n))
    with pytest.raises(E.SchemaError):                                      # hash and order both guarded
        E.load_cell("o2_p0.5", root=root)


@real
def test_fixed_schema_and_cell_history(cell):
    env = start(E.AllocatorEnv(cell), "2024-03-01", "2024-03-05")
    o = env.obs0
    assert o["static"].shape == (C.N_STATIC,) and np.isfinite(o["static"]).all()
    assert o["seq"].shape == (32, len(C.SEQ_COLUMNS)) and np.isfinite(o["seq"]).all()
    assert o["seq_pad"][:-1].all() and o["seq_pad"][-1] == 0                 # nothing before the episode start
    assert np.isfinite(o["account"]).all() and o["account"].shape == (len(C.SLEEVES) * len(C.ACCOUNT_CHANNELS),)
    for _ in range(40):
        o, *_ = env.step(C.Action.hold())
    assert o["seq_pad"].sum() == 0
    other = E.load_cell("o5_p2.0", allow_test=False)
    assert other.static.shape[1] == cell.static.shape[1] == C.N_STATIC and other.feature_order == cell.feature_order
    e4 = E.AllocatorEnv(cell, cadence_h=4)
    o4 = e4.reset(TS("2024-03-01"), TS("2024-03-11"))
    for _ in range(12):
        o4, *_ = e4.step(C.Action.hold())
    assert o4["seq"].shape == (32, len(C.SEQ_COLUMNS)) and o4["seq_pad"].sum() == 0   # 4h step, 32 x 1h rows


@real
def test_c_unavailable_hard_mask_and_cap_zero(cell):
    env = start(E.AllocatorEnv(cell, static_weights=[0, 0, 0, 0, 0, 1.0, 1.0]), "2020-08-01", "2020-11-15")
    m = env.obs0["masks"]
    assert not m.entry[SI["C1v2"], 1:].any() and not m.entry[SI["C4v2"], 1:].any()
    with pytest.raises(ValueError):
        env.step(C.Action((0, 0, 0, 0, 0, 4, 0), (0,) * 7, (0,) * 7))
    tot, rs, infos = run(env, level_policy([0, 0, 0, 0, 0, 4, 4]))
    first = TS("2020-10-01")
    for book in (env.rl, env.st):
        for s in ("C1v2", "C4v2"):
            sd = cell.sleeves[s]
            for q, mlt in book.mult[SI[s]].items():
                assert mlt > 0 and cell.t[sd.dec_idx[q]] >= first and sd.avail[q]
    assert sum(len(env.rl.mult[SI[s]]) for s in ("C1v2", "C4v2")) > 0      # activates after availability


@real
def test_cap_pro_rata_and_net_exposure(cell):
    env = start(E.AllocatorEnv(cell), "2024-01-01", "2024-07-01")
    tot, rs, infos = run(env, level_policy([4] * 7))
    g = np.array([i["gross"] for i in infos])
    assert g.max() <= C.GROSS_CAP + 1e-12 and g.max() > 1.5
    scaled = [m for d in env.rl.mult for m in d.values() if 0 < m < 1]
    assert scaled                                                           # pro-rata binding observed
    assert all(abs(i["net_exposure"]) <= i["gross"] + 1e-12 for i in infos)


@real
def test_all_off_zero_and_static_reward_zero(cell):
    env = start(E.AllocatorEnv(cell, record_minutes=True), "2024-02-01", "2024-04-01")
    tot, rs, _ = run(env, lambda o, e: C.Action.hold())
    assert tot == 0.0 and not env.minutes["rl"].any()
    w = [0.25, 0.5, 0.25, 0.25, 0.25, 0.25, 0.25]
    env = start(E.AllocatorEnv(cell, static_weights=w), "2024-02-01", "2024-04-01")
    rewards = []
    while True:
        o, r, done, info = env.step(C.static_action(env.static_w, env.masks()))
        rewards.append(r)
        if done:
            break
    assert all(r == 0.0 for r in rewards) and env.rl.equity == env.st.equity != 0.0


@real
def test_canonical_parity_dev_minute_ledger(cell):
    pm = json.loads((OUT / "precompute/manifest.json").read_text(encoding="utf-8"))["parity"]
    for s, a, b, key, field in (("G3_LONG", "2020-01-01 01:00", "2026-01-01", "G3_LONG|o2_p1.0", "DEV-FULL_net4"),
                                ("C1v2", "2023-01-01", "2026-01-01", "C1v2|native", "NATIVE_2023_2025_net4")):
        env = start(E.AllocatorEnv(cell, inherit_open=[s], terminal_fee=False, record_minutes=True), a, b)
        lv = [4 if k == SI[s] else 0 for k in range(7)]
        tot, rs, _ = run(env, level_policy(lv))
        assert abs(tot - pm[key][field]) <= 1e-6, (s, tot, pm[key][field])
        assert abs(env.minutes["rl"].sum() - tot) <= 1e-6


def load_script():
    spec = importlib.util.spec_from_file_location("pra_env_t", ROOT / "scripts/precompute_rl_allocator.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@real
def test_random_policy_vs_slow_replay_no_reentry_no_widening(cell):
    mod = load_script()
    b2 = mod.load("nm_b2_env_t", "out/run_new_model_batch2_20261010.py")
    rng = np.random.default_rng(7)
    env = start(E.AllocatorEnv(cell, static_weights=[0.25] * 7, record_minutes=True), "2024-09-01", "2024-12-01")
    o = env.obs0
    while True:
        o, r, done, info = env.step(mod.random_action(rng, o["masks"], p_exit=0.1, p_tight=0.3))
        if done:
            break
    sl = mod.slow_replay(cell, env, env.rl, b2)
    assert np.abs(sl - env.minutes["rl"]).max() <= 1e-9
    assert sum(len(x) for x in env.rl.mod) > 0
    for si, s in enumerate(C.SLEEVES):
        sd = cell.sleeves[s]
        exited = [q for (sj, q, act, a, v) in env.rl.events if sj == si and act == "EXIT" and q in env.rl.mod[si]]
        for q in exited:                                    # no re-entry before the canonical trade ends
            later = [k for k in env.rl.mult[si] if sd.dec_idx[k] > sd.dec_idx[q]]
            assert all(sd.dec_idx[k] >= sd.x[q] for k in later)
        seq = {}
        for (sj, q, act, a, v) in env.rl.events:            # tighten fractions only ever decrease
            if sj == si and act.startswith("TIGHTEN"):
                assert v < seq.get(q, 1.0)
                seq[q] = v
        for q, f in env.rl.tf[si].items():
            assert f in (0.5, 0.75) and s in C.TIGHTEN_SLEEVES
    with pytest.raises(ValueError):                         # widening request is masked
        env2 = start(E.AllocatorEnv(cell), "2024-09-01", "2024-12-01")
        env2.step(C.Action((0,) * 7, (0,) * 7, (0, 0, 0, 2, 0, 0, 0)))   # TIGHTEN_50 with nothing open
