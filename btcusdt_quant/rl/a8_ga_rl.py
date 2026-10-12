"""A8 genome, A8 batch observation, recurrent PPO trainer, and atomic resume contract."""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, replace
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re

import numpy as np

from . import maker_kernel as MK
from . import signal_store as SG
from . import smdp_batch as SB
from . import smdp_reward as RW
from .a8_model import (A8Policy, N_TOKENS, PPOConfig, SL_GRID, TARGETS, TOKEN_CHANNELS, TP_GRID, WAITS,
                       categorical_logp_entropy, decode_joint, recurrent_gae)

POPULATION_SEED = 20261012
FINAL_SEEDS = (20261012, 20261013, 20261014, 20261015, 20261016)
ACCOUNT_CHANNELS = ("executed", "target", "pending", "pending_dq", "position_pnl", "pending_age_h",
                    "flat_streak_days", "log_rv_ratio", "position_age_frac", "cap_remaining_frac",
                    "last_cadence_frac", "cap_event", "previous_target", "renewal_cost_100bps",
                    "sl_distance_100bps", "tp_distance_100bps", "exit_rl", "exit_sl", "exit_tp", "exit_cap")
ACCOUNT_DIM = len(ACCOUNT_CHANNELS)
GA_SELECTION = ("2022-01-01", "2024-01-01")
FINAL_EVALUATION = ("2024-01-01", "2026-01-01")
SELECTION_END_NS = np.datetime64("2024-01-01T00:00:00", "ns").astype(np.int64)


def normalize_gates(values) -> tuple[float, ...]:
    """Project positive gates to [0.1, 2] with geometric mean one."""
    z = np.log(np.asarray(values, float))
    lo, hi = math.log(0.1), math.log(2.0)
    left, right = float(z.min() - hi - 1), float(z.max() - lo + 1)
    for _ in range(80):
        mid = (left + right) / 2
        if np.clip(z - mid, lo, hi).mean() > 0:
            left = mid
        else:
            right = mid
    out = np.exp(np.clip(z - (left + right) / 2, lo, hi))
    return tuple(float(x) for x in out)


@dataclass(frozen=True)
class Genome:
    name: str
    gates: tuple[float, ...]
    idle: float
    slope: float
    risk: float
    turnover: float
    lambda_half_life_h: int
    lr: float
    entropy_joint: float
    entropy_sl: float
    entropy_tp: float
    replay: tuple[float, float, float]
    token_width: int

    def __post_init__(self):
        if len(self.gates) != N_TOKENS or min(self.gates) < 0.1 - 1e-12 or max(self.gates) > 2 + 1e-12:
            raise ValueError("A8 genome requires 44 gates inside [0.1, 2]")
        if abs(float(np.mean(np.log(self.gates)))) > 1e-10:
            raise ValueError("A8 token gates must have geometric mean one")
        if self.lambda_half_life_h not in (6, 12, 24) or self.token_width not in (32, 64):
            raise ValueError("illegal discrete A8 gene")

    def reward_config(self):
        return RW.RewardConfig(self.idle, self.risk, self.turnover, "linear", self.slope, 24.0,
                               quadratic_inventory=True)

    def ppo_config(self):
        return PPOConfig(lr=self.lr, entropy_joint=self.entropy_joint, entropy_sl=self.entropy_sl,
                         entropy_tp=self.entropy_tp, lambda_half_life_h=self.lambda_half_life_h)

    def to_json(self):
        value = asdict(self)
        value["gates"], value["replay"] = list(self.gates), list(self.replay)
        return value

    @staticmethod
    def from_json(value):
        value = dict(value)
        value["gates"], value["replay"] = tuple(value["gates"]), tuple(value["replay"])
        return Genome(**value)


def _log_uniform(rng, lo, hi):
    return float(np.exp(rng.uniform(np.log(lo), np.log(hi))))


def population(seed: int = POPULATION_SEED, n: int = 8) -> list[Genome]:
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        replay = rng.dirichlet((3, 2, 2))
        out.append(Genome(f"G{i:02d}", normalize_gates(np.exp(rng.uniform(np.log(0.1), np.log(2), N_TOKENS))),
                          _log_uniform(rng, 0.005, 0.60), float(rng.uniform(0.005, 0.05)),
                          _log_uniform(rng, 0.02, 0.20), _log_uniform(rng, 0.02, 0.25),
                          int(rng.choice((6, 12, 24))), _log_uniform(rng, 1e-4, 6e-4),
                          _log_uniform(rng, 0.001, 0.02), _log_uniform(rng, 0.001, 0.02),
                          _log_uniform(rng, 0.001, 0.02), tuple(float(x) for x in replay),
                          int(rng.choice((32, 64)))))
    return out


def crossover_mutate(a: Genome, b: Genome, rng, name: str) -> Genome:
    """Uniform genotype crossover plus bounded log-space mutation. No model object enters this function."""
    pick = lambda key: getattr(a if rng.random() < 0.5 else b, key)  # noqa: E731
    gates = np.where(rng.random(N_TOKENS) < 0.5, a.gates, b.gates)
    gates *= np.exp(rng.normal(0, 0.15, N_TOKENS) * (rng.random(N_TOKENS) < 0.20))
    def gene(key, lo, hi):
        value = float(pick(key))
        if rng.random() < 0.25:
            value *= math.exp(rng.normal(0, 0.15))
        return float(np.clip(value, lo, hi))
    replay = np.asarray(pick("replay"), float)
    if rng.random() < 0.25:
        replay = np.exp(np.log(replay) + rng.normal(0, 0.15, 3))
        replay /= replay.sum()
    return Genome(name, normalize_gates(gates), gene("idle", 0.005, 0.60), gene("slope", 0.005, 0.05),
                  gene("risk", 0.02, 0.20), gene("turnover", 0.02, 0.25), int(pick("lambda_half_life_h")),
                  gene("lr", 1e-4, 6e-4), gene("entropy_joint", 0.001, 0.02), gene("entropy_sl", 0.001, 0.02),
                  gene("entropy_tp", 0.001, 0.02), tuple(float(x) for x in replay), int(pick("token_width")))


def raw_net4_fitness(cell_daily: dict) -> tuple[float, float]:
    totals = [float(np.asarray(v, float).sum()) for v in cell_daily.values()]
    return min(totals), float(np.mean(totals))


def selection_months(start: str = "2022-01", end: str = "2023-12") -> list:
    """Inclusive GA months. Selection can never cross into final evaluation."""
    import pandas as pd
    months = [period.to_timestamp().tz_localize("UTC") for period in pd.period_range(start, end, freq="M")]
    if not months or months[0] < pd.Timestamp(GA_SELECTION[0], tz="UTC"):
        raise ValueError("A8 selection must start on or after 2022-01")
    if months[-1] + pd.offsets.MonthBegin(1) > pd.Timestamp(GA_SELECTION[1], tz="UTC"):
        raise PermissionError("A8 selection cannot read 2024 evaluation data")
    return months


def median_seed_fitness(seed_fitness: dict[int, tuple[float, float]]) -> tuple[float, float]:
    """Locked three-seed genotype score: component-wise median raw-net4 fitness."""
    if len(seed_fitness) != 3:
        raise ValueError("A8 genotype confirmation requires exactly three seeds")
    values = np.asarray(list(seed_fitness.values()), np.float64)
    return tuple(float(value) for value in np.median(values, axis=0))


def next_generation(genomes: list[Genome], fitness: dict[str, tuple], seed: int, generation: int,
                    elite: int = 2) -> list[Genome]:
    """Elite-2 plus tournament-3 offspring. Only genotypes cross generations; model weights are not accepted."""
    if len(genomes) < elite or set(fitness) != {genome.name for genome in genomes}:
        raise ValueError("fitness must cover the complete A8 population")
    ranked = sorted(genomes, key=lambda genome: fitness[genome.name], reverse=True)
    output = [replace(copy.deepcopy(genome), name=f"G{generation:02d}_{i:02d}") for i, genome in enumerate(ranked[:elite])]
    rng = np.random.default_rng([seed, generation])
    def tournament():
        candidates = rng.choice(len(genomes), min(3, len(genomes)), replace=False)
        return max((genomes[int(i)] for i in candidates), key=lambda genome: fitness[genome.name])
    while len(output) < len(genomes):
        output.append(crossover_mutate(tournament(), tournament(), rng, f"G{generation:02d}_{len(output):02d}"))
    return output


def family_ids() -> tuple[int, ...]:
    names = [SG.family_of(token) for token in SG.tokens()]
    unique = {name: i for i, name in enumerate(sorted(set(names)))}
    return tuple(unique[name] for name in names)


def fresh_model(genome: Genome, market_dim: int, seed: int, device="cpu") -> A8Policy:
    """Every call starts from a new seed. GA offspring never receive lineage weights."""
    import torch
    torch.manual_seed(seed)
    return A8Policy(market_dim, ACCOUNT_DIM, family_ids(), genome.gates, genome.token_width).to(device)


class A8BatchEnv(SB.BatchEnv):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, sl_grid=SL_GRID, tp_grid=TP_GRID)
        self.startx = np.zeros(self.E, np.int64)

    def reset_env(self, idx, start_ns, end_ns):
        super().reset_env(idx, start_ns, end_ns)
        idx = np.asarray(idx)
        self.startx[idx] = self.gi[idx]

    def obs(self):
        st = self.ST
        rows = ((self.t[self.gi] + MK.MIN_NS - self.clock0) // (5 * MK.MIN_NS)).astype(np.int64)
        rows = np.minimum(rows, len(self.tok) - 1)
        ref = np.where(np.isfinite(self.rv_ref[self.gi]), self.rv_ref[self.gi], self.rv_med)
        pending_age = np.where(st[:, MK.S_PEND] > 0, (self.gi - st[:, MK.S_PPLACED]) / 60.0, 0.0)
        position_age = np.where((np.abs(st[:, MK.S_U]) > MK.EPS) & (st[:, MK.S_OPENK] >= 0),
                                self.gi - st[:, MK.S_OPENK] + 1, 0.0)
        last_exit = st[:, MK.S_LASTEXIT].astype(np.int64)
        onehot = np.stack([last_exit == code for code in (MK.EXIT_RL, MK.EXIT_SL, MK.EXIT_TP, MK.EXIT_CAP)], 1)
        account = np.column_stack((st[:, MK.S_U], self.last_t, st[:, MK.S_PEND],
                                   st[:, MK.S_PDQ] * st[:, MK.S_PEND], np.clip(st[:, MK.S_POSPNL] / 100, -10, 10),
                                   pending_age, np.clip(st[:, MK.S_FLATSTREAK] / MK.CAP_MIN, 0, 4),
                                   np.log(np.maximum(self.rv[self.gi], 1e-6) / ref), position_age / MK.CAP_MIN,
                                   np.clip((MK.CAP_MIN - position_age) / MK.CAP_MIN, 0, 1),
                                   st[:, MK.S_LASTWAIT] / MK.CAP_MIN, st[:, MK.S_CAPFLAG], st[:, MK.S_PREVTGT],
                                   np.clip(st[:, MK.S_RENEWCOST] / 100, -10, 10),
                                   np.clip(st[:, MK.S_SL_BPS] / 100, 0, 10),
                                   np.clip(st[:, MK.S_TP_BPS] / 100, 0, 10), onehot)).astype(np.float32)
        return np.concatenate((self.tok[rows], self.mk[rows], account), 1)

    def burnin_mask(self, burnin_hours=24):
        return (self.gi - self.startx) >= int(burnin_hours * 60)


def fixed_2021_rows(clock) -> np.ndarray:
    import pandas as pd
    a, b = pd.Timestamp("2021-01-01", tz="UTC").value, pd.Timestamp("2022-01-01", tz="UTC").value
    rows = np.flatnonzero((clock >= a) & (clock < b))
    if not len(rows):
        raise ValueError("no 2021 rows for fixed scaler")
    return rows


def scaled_features_fixed_2021(cache: dict, clock, r1: int):
    return SB.scaled_features(cache, fixed_2021_rows(np.asarray(clock)[:r1]), r1)


def assert_dev_path(path) -> None:
    text = str(path).replace("\\", "/").lower()
    if re.search(r"(?:^|[/_.-])(?:2026|test)(?=$|[/_.-])", text):
        raise PermissionError(f"A8 refuses TEST/2026 path: {path}")


def monthly_protocol(start="2022-01", end="2025-12") -> list[tuple[str, str]]:
    import pandas as pd
    months = pd.period_range(start, end, freq="M")
    return [(event, str(month)) for month in months for event in ("evaluate", "commit", "replay", "train")]


def atomic_write(path: Path, data: bytes) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return hashlib.sha256(data).hexdigest()


def save_checkpoint(path: Path, state: dict, hashes: dict) -> str:
    import torch
    buffer = io.BytesIO()
    torch.save({**state, "hashes": copy.deepcopy(hashes)}, buffer)
    return atomic_write(path, buffer.getvalue())


def load_checkpoint(path: Path, hashes: dict) -> dict:
    import torch
    state = torch.load(path, map_location="cpu", weights_only=False)
    if state.get("hashes") != hashes:
        raise RuntimeError(f"checkpoint hash mismatch: {path}")
    return state


def hash_manifest(paths: dict) -> dict:
    return {name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for name, path in paths.items()}


class A8Trainer:
    """Small recurrent PPO engine used by smoke and by the later GA runner. One instance owns one genome."""

    def __init__(self, env: A8BatchEnv, genome: Genome, seed: int, device="cuda", ppo_epochs: int = 1,
                 episode_sampler=None):
        import torch
        self.env, self.genome, self.seed = env, genome, int(seed)
        self.device, self.cfg, self.ppo_epochs = torch.device(device), genome.ppo_config(), int(ppo_epochs)
        self.model = fresh_model(genome, env.mk.shape[1], seed, self.device)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=self.cfg.lr, weight_decay=self.cfg.weight_decay)
        self.generator = torch.Generator(device=self.device).manual_seed(seed)
        self.numpy_rng = np.random.default_rng(seed)
        self.episode_sampler = episode_sampler
        if self.episode_sampler is not None:
            starts, ends = self.episode_sampler(self.numpy_rng, np.arange(env.E))
            self.env.reset_env(np.arange(env.E), starts, ends)
        self.hidden = self.model.initial_state(env.E, self.device)
        self.observation = env.obs()
        self.decisions = 0
        self.stats = {"net4": 0.0, "renewal_count": 0, "sl_count": 0, "tp_count": 0,
                      "round_trips": 0.0,
                      "sl_pnl": 0.0, "tp_pnl": 0.0, "cap_pnl": 0.0, "renewal_cost": 0.0,
                      "reentry_requests": 0, "reentry_fills": 0, "flat_gap_min": 0,
                      "identity_error": 0.0, "faults": 0, "max_hold_min": 0}

    def state_dict(self):
        import torch
        return {"model": copy.deepcopy(self.model.state_dict()), "optimizer": copy.deepcopy(self.optimizer.state_dict()),
                "generator": self.generator.get_state(), "numpy_rng": self.numpy_rng.bit_generator.state,
                "torch_cpu_rng": torch.get_rng_state(), "hidden": self.hidden.detach().cpu(),
                "torch_cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
                "decisions": self.decisions, "stats": copy.deepcopy(self.stats),
                "genome": self.genome.to_json(),
                "env": {"ST": self.env.ST.copy(), "gi": self.env.gi.copy(), "endx": self.env.endx.copy(),
                        "startx": self.env.startx.copy(), "last_t": self.env.last_t.copy()}}

    def load_state_dict(self, state):
        import torch
        self.model.load_state_dict(state["model"])
        self.optimizer.load_state_dict(state["optimizer"])
        self.generator.set_state(state["generator"])
        self.numpy_rng.bit_generator.state = state["numpy_rng"]
        torch.set_rng_state(state["torch_cpu_rng"])
        if self.device.type == "cuda" and state.get("torch_cuda_rng"):
            torch.cuda.set_rng_state_all(state["torch_cuda_rng"])
        self.hidden = state["hidden"].to(self.device)
        self.decisions, self.stats = int(state["decisions"]), copy.deepcopy(state["stats"])
        for key in ("ST", "gi", "endx", "startx", "last_t"):
            getattr(self.env, key)[:] = state["env"][key]
        self.observation = state.get("observation", self.env.obs()).copy()

    def _sequence_forward(self, observations, hidden, done):
        import torch
        outputs = [[], [], [], []]
        current = hidden
        for t in range(len(observations)):
            if t:
                current = current * (1.0 - done[t - 1]).view(1, -1, 1)
            values = self.model(observations[t], current)
            current = values[4]
            for i in range(4):
                outputs[i].append(values[i])
        return tuple(torch.stack(value) for value in outputs), current

    def update(self, steps: int = 32):
        import torch
        E = self.env.E
        records = {key: [] for key in ("obs", "joint", "sl", "tp", "logp", "value", "reward", "gamma", "done",
                                               "minutes", "learn")}
        hidden0 = self.hidden.detach()
        self.model.eval()
        for _ in range(steps):
            x = torch.as_tensor(self.observation, device=self.device)
            with torch.no_grad():
                joint_logits, sl_logits, tp_logits, value, next_hidden = self.model(x, self.hidden)
                actions = [torch.multinomial(torch.softmax(logits, -1), 1, generator=self.generator).squeeze(1)
                           for logits in (joint_logits, sl_logits, tp_logits)]
                parts = [categorical_logp_entropy(logits, action)[0] for logits, action in
                         zip((joint_logits, sl_logits, tp_logits), actions)]
            target_action, wait_action = decode_joint(actions[0].cpu().numpy())
            round_trips_before = self.env.ST[:, MK.S_RT].sum()
            result = self.env.step(target_action, wait_action, actions[1].cpu().numpy(), actions[2].cpu().numpy())
            records["obs"].append(x)
            for key, value_ in zip(("joint", "sl", "tp"), actions):
                records[key].append(value_)
            records["logp"].append(sum(parts))
            records["value"].append(value)
            records["reward"].append(torch.as_tensor(result["reward_discounted"] * self.cfg.reward_scale,
                                                       dtype=torch.float32, device=self.device))
            records["gamma"].append(torch.as_tensor(result["gamma_d"], dtype=torch.float32, device=self.device))
            records["done"].append(torch.as_tensor(result["done"], dtype=torch.float32, device=self.device))
            records["minutes"].append(torch.as_tensor(result["minutes"], dtype=torch.float32, device=self.device))
            records["learn"].append(torch.as_tensor(self.env.burnin_mask(self.cfg.burnin_hours), device=self.device))
            self.stats["net4"] += float(result["net4"].sum())
            self.stats["round_trips"] += float(self.env.ST[:, MK.S_RT].sum() - round_trips_before)
            self.stats["identity_error"] = max(self.stats["identity_error"], float(result["identity_err"].max()))
            self.stats["faults"] += int(result["fault"].sum())
            if result["fault"].any() or float(result["identity_err"].max()) > 1e-8:
                raise RuntimeError(f"A8 ledger/fault abort: faults={int(result['fault'].sum())} "
                                   f"identity={float(result['identity_err'].max())}")
            self.stats["max_hold_min"] = max(self.stats["max_hold_min"], int(self.env.ST[:, MK.S_MAXHOLD].max()))
            reason = result["exit_reason"]
            self.stats["renewal_count"] += int((reason == MK.EXIT_CAP).sum())
            self.stats["sl_count"] += int((reason == MK.EXIT_SL).sum())
            self.stats["tp_count"] += int((reason == MK.EXIT_TP).sum())
            for key in ("sl_pnl", "tp_pnl", "cap_pnl", "renewal_cost", "flat_gap_min"):
                self.stats[key] += float(result[key].sum())
            self.stats["reentry_requests"] += int(result["reentry_requests"].sum())
            self.stats["reentry_fills"] += int(result["reentry_fills"].sum())
            done_index = np.flatnonzero(result["done"])
            if len(done_index):
                if self.episode_sampler is None:
                    starts = self.env.t[self.env.startx[done_index] + 1]
                    ends = self.env.t[self.env.endx[done_index] - 1] + MK.MIN_NS
                else:
                    starts, ends = self.episode_sampler(self.numpy_rng, done_index)
                self.env.reset_env(done_index, starts, ends)
                next_hidden[:, done_index] = 0
            self.hidden = next_hidden
            self.observation = self.env.obs()
        batch = {key: torch.stack(value_) for key, value_ in records.items()}
        with torch.no_grad():
            last_value = self.model(torch.as_tensor(self.observation, device=self.device), self.hidden)[3]
            advantage, returns = recurrent_gae(batch["reward"], batch["value"], batch["done"], last_value,
                                               batch["gamma"], batch["minutes"], self.cfg.lambda_half_life_h)
        mask = batch["learn"].bool()
        if not mask.any():
            mask[-1] = True
        advantage = (advantage - advantage[mask].mean()) / (advantage[mask].std(unbiased=False) + 1e-8)
        self.model.train()
        loss_value = 0.0
        for _ in range(self.ppo_epochs):
            outputs, _ = self._sequence_forward(batch["obs"], hidden0, batch["done"])
            logps, entropies = [], []
            for logits, key in zip(outputs[:3], ("joint", "sl", "tp")):
                logp, entropy = categorical_logp_entropy(logits, batch[key])
                logps.append(logp)
                entropies.append(entropy)
            logp = sum(logps)
            ratio = torch.exp(logp - batch["logp"])
            clipped = torch.clamp(ratio, 1 - self.cfg.clip, 1 + self.cfg.clip)
            policy_loss = -torch.minimum(ratio * advantage, clipped * advantage)[mask].mean()
            value = outputs[3]
            value_clip = batch["value"] + torch.clamp(value - batch["value"], -self.cfg.value_clip, self.cfg.value_clip)
            value_loss = 0.5 * torch.maximum((value - returns) ** 2, (value_clip - returns) ** 2)[mask].mean()
            entropy_loss = (self.cfg.entropy_joint * entropies[0][mask].mean()
                            + self.cfg.entropy_sl * entropies[1][mask].mean()
                            + self.cfg.entropy_tp * entropies[2][mask].mean())
            loss = policy_loss + self.cfg.value_coef * value_loss - entropy_loss
            self.optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.cfg.max_grad_norm)
            self.optimizer.step()
            loss_value = float(loss.detach())
        self.decisions += steps * E
        return {**self.stats, "decisions": self.decisions, "loss": loss_value}

    def train_decisions(self, decisions: int, rollout_steps: int = 32):
        target = self.decisions + int(decisions)
        latest = None
        while self.decisions < target:
            steps = min(rollout_steps, math.ceil((target - self.decisions) / self.env.E))
            latest = self.update(steps)
        return latest


class A8Evaluator:
    """Continuous six-cell sampled-policy ledger for 2022-2023 selection only."""

    METRICS = ("net4", "fills", "minutes", "renewal_count", "sl_count", "tp_count", "sl_pnl", "tp_pnl",
               "cap_pnl", "rl_exit_pnl", "renewal_cost", "reentry_requests", "reentry_fills", "flat_gap_min")

    def __init__(self, market: dict, features: tuple, reward_config, rv_median: float, cells: list,
                 start_ns: int, end_ns: int, seed: int, device="cuda"):
        import torch
        if int(end_ns) > int(SELECTION_END_NS):
            raise PermissionError("A8 evaluator refuses 2024-2025 evaluation during selection")
        self.device = torch.device(device)
        self.env = A8BatchEnv(market, features, cells, tuple(TARGETS), tuple(WAITS), reward_config, rv_median,
                              require_set=True)
        self.env.reset_env(np.arange(len(cells)), np.full(len(cells), start_ns), np.full(len(cells), end_ns))
        self.hidden = None
        self.observation = self.env.obs()
        self.generator = torch.Generator(device=self.device).manual_seed(int(seed))
        self.total_decisions = 0

    def state_dict(self):
        return {"generator": self.generator.get_state(), "hidden": None if self.hidden is None else self.hidden.cpu(),
                "observation": self.observation.copy(), "total_decisions": self.total_decisions,
                "env": {key: getattr(self.env, key).copy() for key in ("ST", "gi", "endx", "startx", "last_t")}}

    def load_state_dict(self, state):
        self.generator.set_state(state["generator"])
        self.hidden = None if state["hidden"] is None else state["hidden"].to(self.device)
        self.observation = state["observation"].copy()
        self.total_decisions = int(state["total_decisions"])
        for key, value in state["env"].items():
            getattr(self.env, key)[:] = value

    def run_month(self, model, month_end_ns: int) -> dict:
        import torch
        if int(month_end_ns) > int(SELECTION_END_NS):
            raise PermissionError("A8 evaluator refuses 2024-2025 evaluation during selection")
        env, E = self.env, self.env.E
        end_index = int(np.searchsorted(env.t, month_end_ns))
        if end_index > int(env.endx.min()):
            raise ValueError("month exceeds evaluator selection boundary")
        metrics = {key: np.zeros(E, np.float64) for key in self.METRICS}
        round_trips_start = env.ST[:, MK.S_RT].copy()
        identity_error = 0.0
        faults = decisions = 0
        max_hold = int(env.ST[:, MK.S_MAXHOLD].max())
        model.eval()
        while True:
            live = env.gi < end_index - 1
            if not live.any():
                break
            x = torch.as_tensor(self.observation, device=self.device)
            with torch.no_grad():
                joint, sl, tp, _, next_hidden = model(x, self.hidden)
                actions = [torch.multinomial(torch.softmax(logits, -1), 1, generator=self.generator).squeeze(1)
                           for logits in (joint, sl, tp)]
            if self.hidden is not None and (~live).any():
                next_hidden[:, ~torch.as_tensor(live, device=self.device)] = self.hidden[:, ~torch.as_tensor(live, device=self.device)]
            target_action, wait_action = decode_joint(actions[0].cpu().numpy())
            dead = np.flatnonzero(~live)
            saved_dead = ({key: getattr(env, key)[dead].copy() for key in ("ST", "gi", "endx", "startx", "last_t")}
                          if len(dead) else None)
            saved_end = env.endx.copy()
            env.endx[:] = np.minimum(env.endx, end_index)
            result = env.step(target_action, wait_action, actions[1].cpu().numpy(), actions[2].cpu().numpy())
            env.endx[:] = saved_end
            if saved_dead is not None:
                for key, value in saved_dead.items():
                    getattr(env, key)[dead] = value
            for key in self.METRICS:
                metrics[key] += np.where(live, result[key], 0.0)
            identity_error = max(identity_error, float(result["identity_err"][live].max()))
            faults += int(result["fault"][live].sum())
            max_hold = max(max_hold, int(result["max_hold_min"][live].max()))
            decisions += int(live.sum())
            self.hidden = next_hidden
            self.observation = env.obs()
        self.total_decisions += decisions
        return {**{key: value.tolist() for key, value in metrics.items()},
                "round_trips": (env.ST[:, MK.S_RT] - round_trips_start).tolist(),
                "identity_error": identity_error, "faults": faults, "max_hold_min": max_hold,
                "decisions": decisions}


def json_write(path: Path, value) -> str:
    return atomic_write(path, (json.dumps(value, indent=2, default=str) + "\n").encode())
