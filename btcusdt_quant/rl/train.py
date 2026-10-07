"""One RL training run per (window, variant, encoder, lr, seed) (plan 3 Task 5): normalizer fit on the train window,
PPO with validation-only checkpoint selection (C12), manifest with a validation-only selection trace."""
from __future__ import annotations
import json, math, time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd, torch
from ..sim import costs
from ..sim.rolling import END, TRAIN_START, Window
from ..sim.strategies import Context
from . import state
from .ppo import PPOConfig, train
from .vec_env import SIDES, STEP_NS, EnvConfig, VecTradingEnv, replay

HYPOTHESIS = "강화학습 정책이 롤링 테스트에서 C1_X·단일 기법 최고·지도학습 정책보다 비용 차감 후 우위"
NOMINAL = {"cost_bps": 4.0, "delay": 1, "slip": 0.0, "funding": "PESS", "units": 1}


def make_val_fn(store, minutes, funding, start, end, device):
    """val_fn(model) -> raw-bps net of the deterministic masked-argmax policy over the whole window, via replay."""
    steps = int(((store.times >= pd.Timestamp(start).value) & (store.times < pd.Timestamp(end).value)).sum())
    env = VecTradingEnv(store, minutes, funding, start, end, 1, EnvConfig(episode_steps=steps, randomize=False), 0)

    def val_fn(model) -> float:
        was = model.training
        model.eval()
        obs, acts = env.reset(), []
        t0 = store.times[env.k0[0]]
        for _ in range(steps):
            logits, _ = model(*(torch.as_tensor(x, device=device) for x in obs))   # masked entries are -inf
            a = logits.argmax(1).cpu().numpy().astype(np.int8)
            acts.append(SIDES[a[0]])
            *obs, _r, _n, _d, _i = env.step(a)
        model.train(was)
        idx = pd.DatetimeIndex(t0 + STEP_NS * np.arange(steps), tz="UTC")
        pnl = replay(pd.Series(acts, index=idx), minutes, start, end, NOMINAL["cost_bps"], NOMINAL["delay"],
                     NOMINAL["slip"]).minute_pnl
        net = float(np.sum(pnl.to_numpy()))                         # pandas .sum() would skip NaN
        if not math.isfinite(net):
            raise RuntimeError(f"non-finite validation value {net}")
        return net
    return val_fn


def run_config(window: Window, variant: str, encoder: str, lr: float, seed: int, out: Path, smoke: bool = False) -> dict:
    t_start, out = time.time(), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    day = pd.Timedelta(days=1)
    if smoke:   # 1 week train + 1 week validation, 2-day episodes, 2 updates, validate every update
        train_start, val_end = window.train_end - 7 * day, window.val_start + 7 * day
        ctx = Context.load(end=val_end, start=train_start - 30 * day)
        full = state.build_state_store(ctx, train_start, val_end, variant)
        env_n, steps, max_tr, ev = 8, 192, 2 * 8 * 128, 1
    else:
        train_start, val_end = TRAIN_START, window.val_end
        ctx = Context.load(end=END)
        full = state.cached_state_store(ctx, TRAIN_START, END, variant)    # prefix-invariant: slice per window
        env_n, steps, max_tr, ev = 256, 1344, 5_000_000, 10
    store = state.fit_normalizer(full, window.train_end).apply(full)       # C9: train rows only
    minutes, funding = ctx.minutes, costs._settlement_arrays()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    env = VecTradingEnv(store, minutes, funding, train_start, window.train_end, env_n,
                        EnvConfig(episode_steps=steps, randomize=True), seed)
    val_fn = make_val_fn(store, minutes, funding, window.val_start, val_end, device)
    cfg = PPOConfig(lr=lr, encoder=encoder)
    res = train(env, val_fn, cfg, seed, max_transitions=max_tr, eval_every=ev, patience=5, ckpt_dir=out, device=device)
    if not math.isfinite(res.best_val) or not Path(res.ckpt_path).exists():
        raise RuntimeError("no finite validation value: no best checkpoint")
    trace = [{"update": r["update"], "transitions": r["transitions"], "val_net_bps": r["val"]}
             for r in res.history if "val" in r]
    summary = {"window": window.name, "variant": variant, "encoder": encoder, "lr": lr, "seed": seed, "smoke": smoke,
               "val_net_bps": res.best_val, "best_step": res.best_step, "transitions": res.history[-1]["transitions"],
               "wall_seconds": time.time() - t_start,
               "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
               "checkpoint": str(res.ckpt_path)}
    manifest = {**summary, "source": "Binance USD-M BTCUSDT futures, local data (sim.strategies.Context)",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(), "data_cutoff": "2026-01-01",
                "hypothesis": HYPOTHESIS, "input_hashes": state._input_hash(ctx),
                "split": {"train": [str(train_start), str(window.train_end)],
                          "validation": [str(window.val_start), str(val_end)]},
                "nominal_validation": NOMINAL, "ppo": asdict(cfg), "env_episode_steps": steps, "n_envs": env_n,
                "selection_trace": trace}     # validation only: no test-window metric is ever computed here
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, default=str), encoding="utf-8")
    return summary
