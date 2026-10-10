"""Vector-action PPO (btcusdt_quant/rl/allocator_ppo.py): a tiny allocator MDP whose optimal action differs from the
static initialisation is learned (learning path), and a single PPO update moves log-probs in the advantage direction.
Synthetic, CPU."""
import numpy as np, torch
from btcusdt_quant.rl import allocator_contracts as C
from btcusdt_quant.rl import allocator_ppo as AP

N = 64


class ToyEnv:
    """One decision per step; only sleeve 0's entry head is active. Reward +1 for level 0.25, -1 otherwise
    (the static initialisation favours OFF)."""
    n = N

    def __init__(self, seed=0):
        self.rng = np.random.default_rng(seed)
        self.t = 0

    def observation(self):
        me = np.zeros((N, 7, 5), bool)
        me[:, :, 0] = True
        me[:, 0, :] = True
        mo = np.zeros((N, 7, 4), bool)
        mo[:, :, 0] = True
        return {"seq": np.zeros((N, 32, 11), np.float32), "seq_nan": np.zeros((N, 32, 11), np.float32),
                "seq_pad": np.zeros((N, 32), np.float32), "static": self.rng.normal(size=(N, C.N_STATIC)).astype(np.float32),
                "account": np.zeros((N, 28), np.float32), "m_entry": me, "m_open": mo}

    def step(self, entry, open_):
        rew = np.where(entry[:, 0] == 1, 1.0, -1.0) * 100      # bps; reward_scale 0.01 -> +-1
        self.t += 1
        z = np.zeros(N)
        info = {"net_rl": rew, "net_st": z, "dmdd_rl": z, "dmdd_st": z, "turnover_rl": z, "turnover_st": z,
                "gross_open": z, "gross_reserved": z}
        return rew, np.full(N, self.t % 16 == 0), info

    def counters(self):
        return {k: np.zeros(N) for k in AP.COUNTERS}

    def state_dict(self):
        return {"t": self.t, "rng": self.rng.bit_generator.state}

    def load_state_dict(self, st):
        self.t = st["t"]
        self.rng.bit_generator.state = st["rng"]


def prob_level1(tr):
    o = tr.env.observation()
    with torch.no_grad():
        le, _, _ = AP.forward(tr.model, AP.to_t(o, tr.device))
    return float(torch.softmax(le[:, 0], -1)[:, 1].mean()), int((le[:, 0].argmax(-1) == 1).float().mean() > 0.5)


def test_tiny_mdp_learns_non_static_action():
    cfg = AP.AllocPPOConfig(n_steps=16, minibatch=256, total_updates=40, lr=1e-3)
    tr = AP.Trainer({}, {"toy": N}, [0.0] * 7, ("a", "b"), ("c", "d"), cfg, seed=0, fold="F4", device="cpu",
                    env=ToyEnv())
    p0, arg0 = prob_level1(tr)
    hist = [tr.run_update() for _ in range(40)]
    p1, arg1 = prob_level1(tr)
    assert arg0 == 0 and p0 < 0.05                         # static init: OFF
    assert arg1 == 1 and p1 > 0.5                          # learned the non-static optimum
    assert all(h["illegal"] == 0 and h["nonfinite"] == 0 for h in hist)
    assert hist[-1]["ent_coef"] == 0.0 and hist[0]["ent_coef"] == cfg.ent_coef
    s = tr.state_dict()
    tr2 = AP.Trainer({}, {"toy": N}, [0.0] * 7, ("a", "b"), ("c", "d"), cfg, seed=0, fold="F4", device="cpu",
                     env=ToyEnv())
    tr2.load_state_dict(s)
    bad = dict(s, identity=dict(s["identity"], fold="F3"))
    try:
        tr2.load_state_dict(bad)
        raise AssertionError("identity mismatch accepted")
    except ValueError:
        pass


def test_single_update_moves_logprob_with_advantage():
    cfg = AP.AllocPPOConfig(n_steps=8, minibatch=128, epochs=1, target_kl=0.0, lr=1e-3)
    tr = AP.Trainer({}, {"toy": N}, [0.0] * 7, ("a", "b"), ("c", "d"), cfg, seed=1, fold="F4", device="cpu",
                    env=ToyEnv(1))
    p0, _ = prob_level1(tr)
    rec = tr.run_update()
    p1, _ = prob_level1(tr)
    assert rec["grad_steps"] == 4 and not rec["kl_early_stop"] and p1 > p0


def test_checkpoint_score_uses_max_baseline():
    cells = {"a": {"net_rl": 100.0, "net_static": 50.0, "max_baseline": 120.0},
             "b": {"net_rl": 300.0, "net_static": 250.0, "max_baseline": 250.0}}
    assert AP.checkpoint_score(cells, "max_baseline") == -20.0          # cell a loses to its comparator
    assert AP.checkpoint_score(cells, "static") == 50.0
    try:
        AP.checkpoint_score(cells, "bogus")
        raise AssertionError("unknown mode accepted")
    except ValueError:
        pass


def test_inactive_sleeves_are_fixed_and_ensemble_median():
    cfg = AP.AllocPPOConfig(n_steps=4, minibatch=64, active_sleeves=("G3_LONG", "G3_SHORT"))
    tr = AP.Trainer({}, {"toy": N}, [1.0, 1.0, 0, 0, 0, 0, 0], ("a", "b"), ("c", "d"), cfg, seed=0, fold="F4",
                    device="cpu", env=ToyEnv())
    t = tr.restrict(AP.to_t(tr.env.observation(), tr.device))
    assert not t["m_entry"][:, 2:, 1:].any() and t["m_entry"][:, 0].all()
    rec = tr.run_update()
    assert rec["heads"]["C1v2"]["entry_active"] == 0 and rec["heads"]["G3_LONG"]["entry_active"] == 4 * N
    # ensemble: median level, majority exit
    class M(torch.nn.Module):
        def __init__(self, e, o):
            super().__init__()
            self.e, self.o = e, o

        def forward(self, *a):
            le = torch.full((1, 7, 5), -1.0)
            le[0, 0, self.e] = 1.0
            lo = torch.full((1, 7, 4), -1.0)
            lo[0, 0, self.o] = 1.0
            return le, lo, torch.zeros(1)
    pol = AP.ensemble_policy([M(0, 3), M(4, 3), M(2, 0)])
    e, o = pol({k: None for k in ("seq", "seq_nan", "seq_pad", "static", "account", "m_entry", "m_open")})
    assert e[0, 0] == 2 and o[0, 0] == 3


def test_mdd_gate_is_strict():
    import importlib.util, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("pra_mdd_t", root / "scripts/precompute_rl_allocator.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    assert mod.mdd_gate({"mdd_rl": 99.0, "mdd_G3_ONLY": 100.0})
    assert not mod.mdd_gate({"mdd_rl": 100.0, "mdd_G3_ONLY": 100.0})              # equal fails (strict <)
    assert mod.E2_CANDIDATES == (20, 40, 60, 80, 100, 123)
    cfg = mod.e2_cfg()
    assert cfg.lr == 3e-4 and cfg.epochs == 4 and cfg.entry_bias == 2.5 and cfg.ent_decay_frac == 0.8
