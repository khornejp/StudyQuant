"""Temporal actor-critic and PPO (plan 3 Task 4, contract C10-C12)."""
import time
import numpy as np, pytest, torch
from btcusdt_quant.rl.models import TemporalActorCritic
from btcusdt_quant.rl.ppo import PPOConfig, compute_gae, train


class ToyEnv:
    """Two states x = +-1 (seq and static carry x). Reward = SIDES[a] * x: long when x > 0, short when x < 0.
    mask_short=True forbids action 2 everywhere; a masked action raises like VecTradingEnv."""
    SIDES = np.array([0, 1, -1])

    def __init__(self, n, seed, steps=16, mask_short=False):
        self.n, self.steps, self.mask_short = n, steps, mask_short
        self.rng = np.random.default_rng(seed)
        self.x = np.zeros(n, np.float32); self.t = np.zeros(n, np.int64)

    def _obs(self):
        self.mask = np.ones((self.n, 3), bool)
        self.mask[:, 2] = not self.mask_short
        seq = np.repeat(self.x[:, None, None], 32, axis=1)
        return seq, self.x[:, None].copy(), self.mask.copy()

    def reset(self):
        self.x = self.rng.choice([-1.0, 1.0], self.n).astype(np.float32); self.t[:] = 0
        return self._obs()

    def step(self, actions):
        a = np.asarray(actions)
        if not self.mask[np.arange(self.n), a].all():
            raise ValueError("masked action")
        reward = self.SIDES[a] * self.x.astype(np.float64)
        self.t += 1
        done = self.t == self.steps
        self.t[done] = 0
        self.x = self.rng.choice([-1.0, 1.0], self.n).astype(np.float32)
        return (*self._obs(), reward, reward, done, {})

    def state_dict(self):
        return {"rng": self.rng.bit_generator.state, "x": self.x.copy(), "t": self.t.copy()}

    def load_state_dict(self, d):
        self.rng.bit_generator.state = d["rng"]; self.x = d["x"].copy(); self.t = d["t"].copy()


def greedy_accuracy(model):
    x = torch.tensor([1.0, -1.0])
    logits, _ = model(x[:, None, None].expand(2, 32, 1), x[:, None], torch.ones(2, 3, dtype=torch.bool))
    return float((logits.argmax(1) == torch.tensor([1, 2])).float().mean())


def test_gae_matches_hand_computation():
    g, lam = 0.9, 0.5
    r = torch.tensor([[1.0], [2.0], [3.0]]); v = torch.tensor([[0.5], [1.0], [1.5]])
    d = torch.tensor([[0.0], [1.0], [0.0]]); last = torch.tensor([2.0])
    d2 = 3 + g * 2 - 1.5                       # t=2 bootstraps last_value
    d1 = 2 - 1.0                               # t=1 is terminal: no bootstrap, no carry
    d0 = 1 + g * 1.0 - 0.5
    want = torch.tensor([[d0 + g * lam * d1], [d1], [d2]])
    adv, ret = compute_gae(r, v, d, last, g, lam)
    torch.testing.assert_close(adv, want)
    torch.testing.assert_close(ret, want + v)


@pytest.mark.parametrize("encoder", ["conv", "gru"])
def test_model_shapes_and_mask(encoder):
    torch.manual_seed(0)
    m = TemporalActorCritic(4, 7, encoder)
    mask = torch.tensor([[True, True, False], [True, False, True]])
    logits, value = m(torch.randn(2, 32, 4), torch.randn(2, 7), mask)
    assert logits.shape == (2, 3) and value.shape == (2,)
    assert torch.isneginf(logits[~mask]).all() and torch.isfinite(logits[mask]).all()
    assert not any(isinstance(x, torch.nn.Dropout) for x in m.modules())


def test_masked_action_never_sampled(tmp_path):
    env = ToyEnv(64, 0, mask_short=True)                   # env raises on a masked action
    cfg = PPOConfig(n_steps=32, minibatch=512)
    res = train(env, greedy_accuracy, cfg, seed=0, max_transitions=3 * 32 * 64, eval_every=1,
                ckpt_dir=tmp_path, device="cpu")
    assert len(res.history) == 3


def test_learns_tiny_mdp(tmp_path):
    env = ToyEnv(32, 1)
    cfg = PPOConfig(n_steps=128, minibatch=1024)
    t0 = time.time()
    res = train(env, greedy_accuracy, cfg, seed=1, max_transitions=200_000, eval_every=10, patience=100,
                ckpt_dir=tmp_path, device="cpu")
    print("curve", [(h["transitions"], round(h["reward_mean"], 3), round(h["entropy"], 3)) for h in res.history],
          f"{time.time() - t0:.1f}s")
    assert res.history[-1]["val"] == 1.0
    # sampled (stochastic) policy is >95% optimal at the end (best.pt is the first greedy 1.0, far earlier)
    ck = torch.load(tmp_path / "last.pt", weights_only=False)
    m = TemporalActorCritic(**ck["model_args"]); m.load_state_dict(ck["model"])
    x = torch.tensor([1.0, -1.0])
    with torch.no_grad():
        p = torch.softmax(m(x[:, None, None].expand(2, 32, 1), x[:, None], torch.ones(2, 3, dtype=torch.bool))[0], 1)
    print("p(optimal)", p[0, 1].item(), p[1, 2].item())
    assert p[0, 1] > 0.95 and p[1, 2] > 0.95


def test_resume_is_bitwise_identical(tmp_path):
    cfg = PPOConfig(n_steps=16, minibatch=128, encoder="gru")
    per = 16 * 32
    full = train(ToyEnv(32, 2), greedy_accuracy, cfg, seed=3, max_transitions=6 * per, eval_every=100,
                 ckpt_dir=tmp_path / "full", device="cpu")
    train(ToyEnv(32, 2), greedy_accuracy, cfg, seed=3, max_transitions=3 * per, eval_every=100,
          ckpt_dir=tmp_path / "split", device="cpu")
    env = ToyEnv(32, 99)                                   # wrong seed: state must come from the checkpoint
    split = train(env, greedy_accuracy, cfg, seed=3, max_transitions=6 * per, eval_every=100,
                  ckpt_dir=tmp_path / "split", device="cpu", resume=True)
    a = torch.load(tmp_path / "full" / "last.pt", weights_only=False)
    b = torch.load(tmp_path / "split" / "last.pt", weights_only=False)
    assert a["update"] == b["update"] == 6 and a["seed"] == b["seed"] == 3
    for k in a["model"]:
        assert torch.equal(a["model"][k], b["model"][k]), k
    strip = lambda h: [{k: v for k, v in r.items() if k != "val"} for r in h]   # split also validated at update 3
    assert strip(full.history) == strip(split.history)


def test_early_stop_keeps_best_validation_checkpoint(tmp_path):
    vals = iter([1.0, 3.0, 2.0, 2.0, 3.0, 0.0, 2.0, 9.0, 9.0])
    snaps = []

    def val_fn(model):
        snaps.append({k: v.clone() for k, v in model.state_dict().items()})
        return next(vals)

    res = train(ToyEnv(16, 4), val_fn, PPOConfig(n_steps=8, minibatch=64), seed=5, max_transitions=10**9,
                eval_every=2, patience=5, ckpt_dir=tmp_path, device="cpu")
    # 5 evals without improvement (a tie is not an improvement); one eval per 2 updates
    assert [h["val"] for h in res.history if "val" in h] == [1.0, 3.0, 2.0, 2.0, 3.0, 0.0, 2.0]
    assert len(res.history) == 14
    assert res.best_val == 3.0 and res.best_step == 4
    ck = torch.load(res.ckpt_path, weights_only=False)
    assert ck["update"] == 4 and ck["seed"] == 5 and ck["val"] == 3.0
    for k, v in snaps[1].items():
        assert torch.equal(ck["model"][k], v), k
