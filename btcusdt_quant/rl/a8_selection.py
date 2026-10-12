"""A8 GA selection runner. Selection stops before 2024 and never performs final evaluation."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import threading
import time
import traceback

import numpy as np
import pandas as pd

from . import a8_ga_rl as A8
from . import dev_data as DD
from . import maker_kernel as MK
from . import signal_store as SG
from . import smdp_batch as SB
from . import smdp_continual as CT
from . import u35

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out/rl_allocator_20261010"
SIGNAL_STORE = OUT / "signal_store_5m"
SPEC = ROOT / ".superpowers/sdd/rl_allocator/a8_ga_rl_spec_2026-10-12.md"
AMENDMENT = OUT / "freeze_amendment_A8.json"
CELLS = [(offset, penetration) for offset in (2, 5) for penetration in (0.5, 1.0, 2.0)]
CELL_NAMES = [f"o{offset}_p{penetration}" for offset, penetration in CELLS]
PRETRAIN_START = "2021-01-30"
PRETRAIN_END = "2022-01-01"
FULL_SELECTION_DECISIONS = 3_016_000_000
AMENDMENT_REVISION = "r2.1"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _canonical_sha(value) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class SelectionConfig:
    run_id: str
    population: int = 8
    generations: int = 6
    envs: int = 2048
    start: str = "2022-01"
    end: str = "2023-12"
    pretrain_decisions: int = 10_000_000
    monthly_decisions: int = 2_000_000
    seed: int = A8.POPULATION_SEED
    smoke: bool = False
    stop_after_commits: int = 0

    def validate(self) -> list:
        months = A8.selection_months(self.start, self.end)
        if min(self.population, self.generations, self.envs, self.pretrain_decisions, self.monthly_decisions) <= 0:
            raise ValueError("A8 selection counts must be positive")
        if self.population < 2:
            raise ValueError("A8 selection needs at least two genomes")
        if not self.smoke:
            locked = (self.population, self.generations, self.start, self.end, self.pretrain_decisions,
                      self.monthly_decisions, self.seed)
            expected = (8, 6, "2022-01", "2023-12", 10_000_000, 2_000_000, A8.POPULATION_SEED)
            if locked != expected:
                raise ValueError(f"full A8 selection must use locked values {expected}, got {locked}")
        return months


def _identity_config(config: SelectionConfig) -> dict:
    value = asdict(config)
    value.pop("stop_after_commits", None)
    return value


class RunLog:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(path, "a", encoding="utf-8", buffering=1)

    def write(self, message: str) -> None:
        line = f"{_utc()} {message}"
        self.handle.write(line + "\n")
        print(line, flush=True)

    def close(self) -> None:
        self.handle.close()


class PlannedStop(RuntimeError):
    pass


class CommitCounter:
    def __init__(self, stop_after: int):
        self.count, self.stop_after = 0, int(stop_after)

    def committed(self, unit: str) -> None:
        self.count += 1
        if self.stop_after and self.count >= self.stop_after:
            raise PlannedStop(f"planned stop after commit {self.count}: {unit}")


def _code_hashes() -> dict:
    files = {
        "spec": SPEC,
        "amendment": AMENDMENT,
        "driver": Path(__file__),
        "entrypoint": ROOT / "scripts/precompute_rl_allocator.py",
        **{name: ROOT / f"btcusdt_quant/rl/{name}.py" for name in
           ("a8_ga_rl", "a8_model", "maker_kernel", "smdp_batch", "smdp_reward", "smdp_continual",
            "signal_store", "dev_data")},
    }
    return {name: _sha(path) for name, path in files.items()}


def _git_head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _window_sampler(start_ns: int, end_ns: int, episode_hours: int = 48):
    episode_ns = episode_hours * 3600 * 10**9
    step_ns = 5 * MK.MIN_NS
    if end_ns - start_ns <= episode_ns:
        raise ValueError("training window shorter than recurrent episode")

    def sample(rng, indices):
        slots = (end_ns - start_ns - episode_ns) // step_ns
        starts = start_ns + step_ns * rng.integers(0, slots + 1, len(indices))
        return starts, starts + episode_ns
    return sample


def _load_inputs(reward_config):
    minutes, funding, input_hash = DD.load_dev()
    path = input_hash.get("market", {}).get("path", "")
    A8.assert_dev_path(path)
    settlement = u35.assert_settlement_grid(u35.scheduled(funding))
    market = SB.market_arrays(minutes, settlement, reward_config)
    cutoff = pd.Timestamp(A8.GA_SELECTION[1], tz="UTC").value
    end_index = int(np.searchsorted(market["t"], cutoff))
    market = {key: (value[:end_index] if isinstance(value, np.ndarray) and len(value) == len(minutes) else value)
              for key, value in market.items()}
    del minutes, funding
    if len(market["t"]) == 0 or int(market["t"][-1]) >= cutoff:
        raise PermissionError("A8 selection market slice must end before 2024-01-01")
    clock = SG.clock()
    r1 = int(np.searchsorted(clock, cutoff))
    clock = clock[:r1]
    cache = SB.raw_cache(SIGNAL_STORE)
    features = A8.scaled_features_fixed_2021(cache, clock, r1)
    market["clock0"] = int(clock[0])
    rows = A8.fixed_2021_rows(clock)
    scaler = {"mode": "fixed-2021", "row_count": int(len(rows)), "first_row": int(rows[0]),
              "last_row": int(rows[-1]), "rows_sha256": hashlib.sha256(rows.tobytes()).hexdigest(),
              "token_shape": list(features[0].shape), "market_shape": list(features[1].shape)}
    a21 = pd.Timestamp(PRETRAIN_START, tz="UTC").value
    b21 = pd.Timestamp(PRETRAIN_END, tz="UTC").value
    ia, ib = np.searchsorted(market["t"], [a21, b21])
    rv_median = float(np.nanmedian(market["rv"][ia + 1440:ib]))
    return market, features, clock, rv_median, input_hash, scaler


def _make_trainer(market, features, rv_median, genome, seed: int, envs: int):
    a21 = pd.Timestamp(PRETRAIN_START, tz="UTC").value
    b21 = pd.Timestamp(PRETRAIN_END, tz="UTC").value
    cells = [CELLS[index % len(CELLS)] for index in range(envs)]
    environment = A8.A8BatchEnv(market, features, cells, tuple(A8.TARGETS), tuple(A8.WAITS),
                                 genome.reward_config(), rv_median, require_set=True)
    return A8.A8Trainer(environment, genome, seed, device="cuda", episode_sampler=_window_sampler(a21, b21))


def _make_evaluator(market, features, rv_median, genome, seed: int, months: list):
    start_ns = months[0].value
    end_ns = (months[-1] + pd.offsets.MonthBegin(1)).value
    return A8.A8Evaluator(market, features, genome.reward_config(), rv_median, CELLS, start_ns, end_ns,
                          seed + 100_000, device="cuda")


def _continual_sampler(market, genome, month, all_months):
    end = month + pd.offsets.MonthBegin(1)
    config = CT.ContinualConfig(episode_days=2, rollout_days=2, mix_latest=genome.replay[0],
                                mix_recent6=genome.replay[1], mix_earlier=genome.replay[2])
    return CT.ReplaySampler(market["t"], market["c"], [value for value in all_months if value <= month], end,
                            config, A8.SELECTION_END_NS)


def _stats_delta(before: dict, after: dict) -> dict:
    additive = ("net4", "shaping", "round_trips", "renewal_count", "sl_count", "tp_count", "rl_count",
                "sl_pnl", "tp_pnl", "cap_pnl", "rl_pnl", "renewal_cost", "reentry_requests", "reentry_fills",
                "flat_gap_min", "faults")
    output = {key: float(after[key] - before[key]) for key in additive}
    output.update(identity_error=float(after["identity_error"]), max_hold_min=int(after["max_hold_min"]))
    return output


def _month_record(raw: dict) -> dict:
    cells = {}
    for index, name in enumerate(CELL_NAMES):
        cells[name] = {key: (int(raw[key][index]) if key in ("renewal_count", "sl_count", "tp_count", "rl_count",
                                                             "reentry_requests", "reentry_fills")
                              else float(raw[key][index]))
                       for key in A8.A8Evaluator.METRICS}
        cells[name]["round_trips"] = float(raw["round_trips"][index])
    return {"cells": cells, "decisions": int(raw["decisions"]), "identity_error": float(raw["identity_error"]),
            "faults": int(raw["faults"]), "max_hold_min": int(raw["max_hold_min"]),
            "raw_net4_mean_cells": float(np.mean(raw["net4"])), "raw_net4_sum_cells": float(np.sum(raw["net4"])),
            "round_trips": float(np.sum(raw["round_trips"])), "sl_count": int(np.sum(raw["sl_count"])),
            "tp_count": int(np.sum(raw["tp_count"])), "renewal_count": int(np.sum(raw["renewal_count"])),
            "rl_count": int(np.sum(raw["rl_count"])), "sl_pnl": float(np.sum(raw["sl_pnl"])),
            "tp_pnl": float(np.sum(raw["tp_pnl"])), "cap_pnl": float(np.sum(raw["cap_pnl"])),
            "rl_pnl": float(np.sum(raw["rl_exit_pnl"])), "reentry_fills": int(np.sum(raw["reentry_fills"])),
            "shaping": float(np.sum(raw["shaping"]))}


def _fitness(monthly: list) -> tuple[float, float]:
    by_cell = {cell: [month["cells"][cell]["net4"] for month in monthly] for cell in CELL_NAMES}
    return A8.raw_net4_fitness(by_cell)


def _progress_path(genome_dir: Path) -> Path:
    return genome_dir / "progress.json"


def _save_progress(genome_dir: Path, trainer, evaluator, phase: str, month_index: int, monthly: list, hashes: dict,
                   scaler: dict, sampler: dict, counter: CommitCounter) -> dict:
    old_progress = None
    if _progress_path(genome_dir).exists():
        old_progress = json.loads(_progress_path(genome_dir).read_text(encoding="utf-8"))
    checkpoint_dir = genome_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    label = ("pretrain_latest" if phase.startswith("pretrain:") else phase.replace(":", "_").replace("-", ""))
    path = checkpoint_dir / f"{label}.pt"
    state = {"trainer": trainer.state_dict(), "evaluator": evaluator.state_dict(), "phase": phase,
             "month_index": month_index, "monthly": monthly, "scaler": scaler, "sampler": sampler,
             "last_committed_unit": phase}
    checkpoint_sha = A8.save_checkpoint(path, state, hashes)
    progress = {"phase": phase, "month_index": month_index, "checkpoint": str(path.relative_to(genome_dir)),
                "checkpoint_sha256": checkpoint_sha, "updated_utc": _utc()}
    A8.json_write(_progress_path(genome_dir), progress)
    replace_old = (phase == "pretrained" and old_progress and old_progress["phase"].startswith("pretrain:"))
    replace_old = replace_old or (phase.startswith("trained:") and old_progress
                                  and old_progress["phase"] == phase.replace("trained:", "evaluated:"))
    if replace_old:
        old_checkpoint = genome_dir / old_progress["checkpoint"]
        if old_checkpoint != path:
            old_checkpoint.unlink(missing_ok=True)
    counter.committed(f"{genome_dir.name}:{phase}")
    return progress


def _load_progress(genome_dir: Path, hashes: dict) -> tuple[dict, dict] | tuple[None, None]:
    path = _progress_path(genome_dir)
    if not path.exists():
        return None, None
    progress = json.loads(path.read_text(encoding="utf-8"))
    checkpoint = genome_dir / progress["checkpoint"]
    if _sha(checkpoint) != progress["checkpoint_sha256"]:
        raise RuntimeError(f"checkpoint file hash mismatch: {checkpoint}")
    return progress, A8.load_checkpoint(checkpoint, hashes)


def _write_genome_report(path: Path, base: dict, monthly: list, trainer, status: str, progress=None) -> None:
    report = {**base, "status": status, "months": monthly, "training_decisions": int(trainer.decisions),
              "trainer_stats": trainer.stats, "progress": progress, "updated_utc": _utc()}
    if status == "complete":
        report["fitness_raw_net4"] = list(_fitness(monthly))
    A8.json_write(path, report)


def _run_genome(genome, generation, seed: int, config: SelectionConfig, months, market, features, rv_median,
                hashes: dict, hash_id: str, scaler: dict, run_dir: Path, logger: RunLog,
                counter: CommitCounter, recheck=False, compatible_hash_ids=None) -> dict:
    branch = run_dir / ("rechecks" if recheck else "genomes")
    generation_name = "confirmation" if recheck else f"generation_{int(generation):02d}"
    genome_dir = branch / generation_name / genome.name / f"seed_{seed}"
    genome_dir.mkdir(parents=True, exist_ok=True)
    report_path = genome_dir / "result.json"
    if report_path.exists():
        existing = json.loads(report_path.read_text(encoding="utf-8"))
        if existing.get("status") == "complete":
            if existing.get("hash_id") not in (compatible_hash_ids or {hash_id}):
                raise RuntimeError(f"completed genome hash mismatch: {report_path}")
            return existing
    base = {"generation": generation_name, "genome": genome.to_json(), "seed": seed, "hash_id": hash_id,
            "fresh_model": True, "weight_inheritance": False, "selection_period": [config.start, config.end],
            "evaluation_2024_2025_executed": False, "profit_judgment": False}
    trainer = _make_trainer(market, features, rv_median, genome, seed, config.envs)
    evaluator = _make_evaluator(market, features, rv_median, genome, seed, months)
    progress, state = _load_progress(genome_dir, hashes)
    monthly, phase, month_index = [], "fresh", -1
    if state is not None:
        trainer.load_state_dict(state["trainer"])
        evaluator.load_state_dict(state["evaluator"])
        monthly, phase, month_index = state["monthly"], state["phase"], int(state["month_index"])
        logger.write(f"event=resume generation={generation_name} genome={genome.name} seed={seed} "
                     f"unit={phase} decisions={trainer.decisions}")
    _write_genome_report(report_path, base, monthly, trainer, "running", progress)

    if not phase.startswith("pretrained") and not phase.startswith("evaluated:") and not phase.startswith("trained:"):
        chunk = min(1_000_000, config.pretrain_decisions)
        while trainer.decisions < config.pretrain_decisions:
            before, before_decisions, start = dict(trainer.stats), trainer.decisions, time.perf_counter()
            target = min(config.pretrain_decisions, trainer.decisions + chunk)
            trainer.train_decisions(target - trainer.decisions)
            wall = time.perf_counter() - start
            delta = _stats_delta(before, trainer.stats)
            phase = f"pretrain:{min(trainer.decisions, config.pretrain_decisions)}"
            progress = _save_progress(genome_dir, trainer, evaluator, phase, -1, monthly, hashes, scaler,
                                      {"kind": "2021", "window": [PRETRAIN_START, PRETRAIN_END]}, counter)
            logger.write(f"event=pretrain generation={generation_name} genome={genome.name} seed={seed} month=2021 "
                         f"decisions={trainer.decisions} dec/s={(trainer.decisions - before_decisions) / max(wall, 1e-9):.3f} "
                         f"raw_net4={delta['net4']:.6f} RT={delta['round_trips']:.3f} "
                         f"cap_count={int(delta['renewal_count'])} cap_pnl={delta['cap_pnl']:.6f} "
                         f"SL_count={int(delta['sl_count'])} SL_pnl={delta['sl_pnl']:.6f} "
                         f"TP_count={int(delta['tp_count'])} TP_pnl={delta['tp_pnl']:.6f} "
                         f"RL_count={int(delta['rl_count'])} RL_pnl={delta['rl_pnl']:.6f} "
                         f"reentry_fills={int(delta['reentry_fills'])} shaping={delta['shaping']:.6f} "
                         f"max_hold={delta['max_hold_min']} "
                         f"identity_error={delta['identity_error']:.3e} fault={int(delta['faults'])}")
        phase = "pretrained"
        progress = _save_progress(genome_dir, trainer, evaluator, phase, -1, monthly, hashes, scaler,
                                  {"kind": "2021", "window": [PRETRAIN_START, PRETRAIN_END]}, counter)
        _write_genome_report(report_path, base, monthly, trainer, "running", progress)

    all_months = CT.month_starts("2021-02", config.end)
    start_index = 0
    if phase.startswith(("evaluated:", "trained:")):
        if not 0 <= month_index < len(months) or phase.split(":", 1)[1] != f"{months[month_index]:%Y-%m}":
            raise RuntimeError(f"invalid A8 resume phase/index: {phase} {month_index}")
        if len(monthly) != month_index + 1:
            raise RuntimeError(f"invalid A8 resume monthly length: {len(monthly)} for {phase}")
        start_index = month_index + int(phase.startswith("trained:"))
    for index in range(start_index, len(months)):
        month = months[index]
        month_name = f"{month:%Y-%m}"
        if phase == f"evaluated:{month_name}":
            record = monthly[index]
        else:
            start = time.perf_counter()
            raw = evaluator.run_month(trainer.model, (month + pd.offsets.MonthBegin(1)).value)
            wall = time.perf_counter() - start
            record = {"month": month_name, **_month_record(raw), "evaluation_wall_sec": wall}
            if record["faults"] or record["identity_error"] > 1e-8:
                raise RuntimeError(f"A8 evaluation fault {generation_name} {genome.name} {month_name}")
            if len(monthly) == index:
                monthly.append(record)
            else:
                monthly[index] = record
            month_path = genome_dir / "months" / f"{month:%Y%m}.json"
            A8.json_write(month_path, record)
            phase, month_index = f"evaluated:{month_name}", index
            progress = _save_progress(genome_dir, trainer, evaluator, phase, index, monthly, hashes, scaler,
                                      {"kind": "evaluation", "month": month_name}, counter)
            _write_genome_report(report_path, base, monthly, trainer, "running", progress)
            logger.write(f"event=evaluate generation={generation_name} genome={genome.name} seed={seed} month={month_name} "
                         f"decisions={record['decisions']} dec/s={record['decisions'] / max(wall, 1e-9):.3f} "
                         f"raw_net4={record['raw_net4_mean_cells']:.6f} RT={record['round_trips']:.3f} "
                         f"cap_count={record['renewal_count']} cap_pnl={record['cap_pnl']:.6f} "
                         f"SL_count={record['sl_count']} SL_pnl={record['sl_pnl']:.6f} "
                         f"TP_count={record['tp_count']} TP_pnl={record['tp_pnl']:.6f} "
                         f"RL_count={record['rl_count']} RL_pnl={record['rl_pnl']:.6f} "
                         f"reentry_fills={record['reentry_fills']} shaping={record['shaping']:.6f} "
                         f"max_hold={record['max_hold_min']} identity_error={record['identity_error']:.3e} "
                         f"fault={record['faults']}")

        sampler = _continual_sampler(market, genome, month, all_months)
        trainer.episode_sampler = sampler.sample
        indices = np.arange(trainer.env.E)
        starts, ends = sampler.sample(trainer.numpy_rng, indices)
        trainer.env.reset_env(indices, starts, ends)
        trainer.hidden.zero_()
        trainer.observation = trainer.env.obs()
        before_decisions, before_stats, start = trainer.decisions, dict(trainer.stats), time.perf_counter()
        trainer.train_decisions(config.monthly_decisions)
        wall = time.perf_counter() - start
        delta = _stats_delta(before_stats, trainer.stats)
        phase, month_index = f"trained:{month_name}", index
        progress = _save_progress(genome_dir, trainer, evaluator, phase, index, monthly, hashes, scaler,
                                  {"kind": "continual", "month": month_name, "replay": list(genome.replay)}, counter)
        _write_genome_report(report_path, base, monthly, trainer, "running", progress)
        logger.write(f"event=train generation={generation_name} genome={genome.name} seed={seed} month={month_name} "
                     f"decisions={trainer.decisions - before_decisions} "
                     f"dec/s={(trainer.decisions - before_decisions) / max(wall, 1e-9):.3f} "
                     f"raw_net4={record['raw_net4_mean_cells']:.6f} RT={record['round_trips']:.3f} "
                     f"cap_count={int(delta['renewal_count'])} cap_pnl={delta['cap_pnl']:.6f} "
                     f"SL_count={int(delta['sl_count'])} SL_pnl={delta['sl_pnl']:.6f} "
                     f"TP_count={int(delta['tp_count'])} TP_pnl={delta['tp_pnl']:.6f} "
                     f"RL_count={int(delta['rl_count'])} RL_pnl={delta['rl_pnl']:.6f} "
                     f"reentry_fills={int(delta['reentry_fills'])} shaping={delta['shaping']:.6f} "
                     f"max_hold={max(record['max_hold_min'], delta['max_hold_min'])} "
                     f"identity_error={max(record['identity_error'], delta['identity_error']):.3e} "
                     f"fault={record['faults'] + int(delta['faults'])}")

    _write_genome_report(report_path, base, monthly, trainer, "complete", progress)
    return json.loads(report_path.read_text(encoding="utf-8"))


def _report_base(config: SelectionConfig, hashes: dict, input_hash: dict, scaler: dict) -> dict:
    return {"run_id": config.run_id, "status": "running", "created_utc": _utc(),
            "amendment_revision": AMENDMENT_REVISION,
            "config": asdict(config),
            "locked": {"population": 8, "generations": 6, "elite": 2, "tournament": 3,
                       "crossover": "uniform", "mutation": "log-space", "seed": A8.POPULATION_SEED,
                       "pretrain_decisions": 10_000_000, "monthly_decisions": 2_000_000,
                       "weight_inheritance": False, "fitness": "raw net4",
                       "amendment_revision": AMENDMENT_REVISION},
            "hashes": hashes, "hash_id": _canonical_sha({"hashes": hashes, "config": _identity_config(config),
                                                           "input": input_hash, "scaler": scaler}),
            "input_hash": input_hash, "scaler": scaler, "git_head": _git_head(), "data_cutoff": "< 2026-01-01",
            "selection_boundary": "< 2024-01-01", "evaluation_2024_2025_executed": False,
            "test_rows_used": 0, "physical_test_reads": 0, "profit_judgment": False, "generations": []}


def run_selection(config: SelectionConfig, resume: bool = False) -> dict:
    import numba
    import torch
    months = config.validate()
    if not torch.cuda.is_available():
        raise RuntimeError("A8 selection requires CUDA")
    torch.set_num_threads(1)
    numba.set_num_threads(16)
    base_dir = OUT / "smdp_a8"
    run_dir = base_dir / config.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger = RunLog(run_dir / "selection.log")
    report_path = run_dir / "selection_report.json"
    started = time.time()
    counter = CommitCounter(config.stop_after_commits)
    report = None
    try:
        initial = A8.population(config.seed, config.population)
        market, features, clock, rv_median, input_hash, scaler = _load_inputs(initial[0].reward_config())
        hashes = {"code": _code_hashes(), "input": input_hash, "config": _identity_config(config)}
        candidate = _report_base(config, hashes["code"], input_hash, scaler)
        hash_id = _canonical_sha(hashes)
        candidate["hash_id"] = hash_id
        compatible_hash_ids = {hash_id}
        if report_path.exists():
            if not resume:
                raise FileExistsError(f"A8 run exists; use --resume: {run_dir}")
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("hash_id") != hash_id:
                amendment = json.loads(AMENDMENT.read_text(encoding="utf-8"))
                migration = amendment.get("resume_migration", {})
                stored_config = dict(report.get("config", {}))
                stored_config.pop("stop_after_commits", None)
                if (migration.get("run_id") != config.run_id
                        or migration.get("from_hash_id") != report.get("hash_id")
                        or migration.get("to_revision") != AMENDMENT_REVISION
                        or stored_config != _identity_config(config)
                        or report.get("input_hash") != input_hash or report.get("scaler") != scaler):
                    raise RuntimeError("A8 run hash/config mismatch")
                previous_hash_id = report["hash_id"]
                compatible_hash_ids.add(previous_hash_id)
                report.update(hash_id=hash_id, hashes=candidate["hashes"],
                              amendment_revision=AMENDMENT_REVISION,
                              previous_hash_id=previous_hash_id,
                              compatible_hash_ids=sorted(compatible_hash_ids),
                              bugfix_migration={"from_revision": report.get("amendment_revision"),
                                                "to_revision": AMENDMENT_REVISION,
                                                "reason": migration["reason"], "migrated_utc": _utc()})
                report["locked"]["amendment_revision"] = AMENDMENT_REVISION
            else:
                compatible_hash_ids.update(report.get("compatible_hash_ids", []))
            report["resume_count"] = int(report.get("resume_count", 0)) + 1
            report["status"] = "running"
        else:
            if resume:
                raise FileNotFoundError(f"A8 resume report missing: {report_path}")
            report = candidate
            report["resume_count"] = 0
            A8.json_write(base_dir / "latest_run.json", {"run_id": config.run_id, "run_dir": str(run_dir),
                                                           "created_utc": _utc()})
        A8.json_write(report_path, report)
        logger.write(f"event=start run_id={config.run_id} resume={resume} smoke={config.smoke} envs={config.envs} "
                     f"population={config.population} generations={config.generations} months={len(months)}")

        population = initial
        generation_results = []
        for generation in range(config.generations):
            summary_path = run_dir / f"generation_{generation:02d}_summary.json"
            if summary_path.exists():
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                if summary.get("status") != "complete" or summary.get("hash_id") not in compatible_hash_ids:
                    raise RuntimeError(f"invalid generation summary: {summary_path}")
                generation_results = summary["results"]
                if generation + 1 < config.generations:
                    population = [A8.Genome.from_json(value) for value in summary["next_population"]]
                continue
            generation_results = []
            for genome in population:
                result = _run_genome(genome, generation, config.seed, config, months, market, features, rv_median,
                                     hashes, hash_id, scaler, run_dir, logger, counter,
                                     compatible_hash_ids=compatible_hash_ids)
                generation_results.append({"genome": genome.to_json(), "fitness_raw_net4": result["fitness_raw_net4"],
                                           "result": str((run_dir / "genomes" / f"generation_{generation:02d}" /
                                                          genome.name / f"seed_{config.seed}" / "result.json").relative_to(run_dir))})
            fitness = {row["genome"]["name"]: tuple(row["fitness_raw_net4"]) for row in generation_results}
            next_population = (A8.next_generation(population, fitness, config.seed, generation + 1, elite=2)
                               if generation + 1 < config.generations else [])
            summary = {"generation": generation, "status": "complete", "hash_id": hash_id,
                       "population": [genome.to_json() for genome in population], "results": generation_results,
                       "ranking": sorted(fitness, key=fitness.get, reverse=True),
                       "next_population": [genome.to_json() for genome in next_population], "created_utc": _utc()}
            A8.json_write(summary_path, summary)
            report["generations"] = [*report.get("generations", [])[:generation],
                                     {"generation": generation, "summary": summary_path.name,
                                      "ranking": summary["ranking"]}]
            A8.json_write(report_path, report)
            logger.write(f"event=generation_complete generation={generation} ranking={','.join(summary['ranking'])}")
            population = next_population

        ranked = sorted(generation_results, key=lambda row: tuple(row["fitness_raw_net4"]), reverse=True)
        top_two = ranked[:2]
        confirmations = []
        for row in top_two:
            genome = A8.Genome.from_json(row["genome"])
            seed_scores = {config.seed: tuple(row["fitness_raw_net4"])}
            seed_results = {str(config.seed): row["result"]}
            for seed in (config.seed + 1, config.seed + 2):
                result = _run_genome(genome, "confirmation", seed, config, months, market, features, rv_median,
                                     hashes, hash_id, scaler, run_dir, logger, counter, recheck=True,
                                     compatible_hash_ids=compatible_hash_ids)
                seed_scores[seed] = tuple(result["fitness_raw_net4"])
                seed_results[str(seed)] = str((run_dir / "rechecks" / "confirmation" / genome.name /
                                                f"seed_{seed}" / "result.json").relative_to(run_dir))
            confirmations.append({"genome": genome.to_json(),
                                  "seed_fitness_raw_net4": {str(seed): list(value) for seed, value in seed_scores.items()},
                                  "median_fitness_raw_net4": list(A8.median_seed_fitness(seed_scores)),
                                  "results": seed_results})
            A8.json_write(run_dir / f"confirmation_{genome.name}.json", confirmations[-1])
        winner = max(confirmations, key=lambda row: tuple(row["median_fitness_raw_net4"]))
        report.update(status="complete", completed_utc=_utc(), wall_sec=round(time.time() - started, 3),
                      top_two_confirmation=confirmations,
                      selected_genotype={"genome": winner["genome"],
                                         "median_fitness_raw_net4": winner["median_fitness_raw_net4"],
                                         "weights_discarded": True, "checkpoint_for_final_retrain": None},
                      evaluation_2024_2025_executed=False, test_rows_used=0, physical_test_reads=0)
        A8.json_write(report_path, report)
        logger.write(f"event=complete winner={winner['genome']['name']} "
                     f"median_raw_net4={winner['median_fitness_raw_net4']} wall_sec={report['wall_sec']}")
        return report
    except PlannedStop as error:
        report = report or {"run_id": config.run_id}
        report.update(status="stopped", stop_reason=str(error), stopped_utc=_utc(),
                      wall_sec=round(time.time() - started, 3), evaluation_2024_2025_executed=False,
                      test_rows_used=0, physical_test_reads=0, profit_judgment=False)
        A8.json_write(report_path, report)
        logger.write(f"event=planned_stop reason={error}")
        return report
    except BaseException as error:
        trace = traceback.format_exc()
        report = report or {"run_id": config.run_id}
        report.update(status="failed", error=f"{type(error).__name__}: {error}", traceback=trace,
                      failed_utc=_utc(), wall_sec=round(time.time() - started, 3),
                      evaluation_2024_2025_executed=False, test_rows_used=0, physical_test_reads=0,
                      profit_judgment=False)
        A8.json_write(report_path, report)
        logger.write(f"event=crash error={type(error).__name__}:{error}\n{trace}")
        raise
    finally:
        logger.close()


def _gpu_memory_used_mib() -> int | None:
    result = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                            capture_output=True, text=True)
    try:
        return int(result.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return None


def run_calibration(run_id: str, env_counts: list[int], decisions: int = 131_072) -> dict:
    import numba
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("A8 calibration requires CUDA")
    torch.set_num_threads(1)
    numba.set_num_threads(16)
    run_dir = OUT / "smdp_a8" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger = RunLog(run_dir / "calibration.log")
    report_path = run_dir / "calibration_report.json"
    report = {"run_id": run_id, "status": "running", "created_utc": _utc(), "env_counts": env_counts,
              "measurement_decisions_target": decisions, "gpu": torch.cuda.get_device_name(0),
              "shared_process_pid": 34640, "shared_process_killed": False, "rows": [],
              "locked_assumptions_changed": False, "amendment_revision": AMENDMENT_REVISION,
              "test_rows_used": 0, "physical_test_reads": 0, "profit_judgment": False}
    A8.json_write(report_path, report)
    try:
        genome = A8.population(n=1)[0]
        market, features, _, rv_median, input_hash, scaler = _load_inputs(genome.reward_config())
        for envs in env_counts:
            row = {"envs": int(envs), "status": "running"}
            A8.json_write(report_path, report)
            trainer = None
            stop = threading.Event()
            sampled_memory = []

            def sample_memory():
                while not stop.wait(0.05):
                    value = _gpu_memory_used_mib()
                    if value is not None:
                        sampled_memory.append(value)

            thread = threading.Thread(target=sample_memory, daemon=True)
            thread.start()
            try:
                torch.cuda.empty_cache()
                torch.cuda.reset_peak_memory_stats()
                trainer = _make_trainer(market, features, rv_median, genome, A8.POPULATION_SEED, envs)
                trainer.update(4)
                before = trainer.decisions
                start = time.perf_counter()
                trainer.train_decisions(decisions)
                wall = time.perf_counter() - start
                measured = trainer.decisions - before
                row.update(status="passed", decisions=measured, wall_sec=wall,
                           decisions_per_sec=measured / wall,
                           torch_peak_allocated_mib=torch.cuda.max_memory_allocated() / 1024**2,
                           torch_peak_reserved_mib=torch.cuda.max_memory_reserved() / 1024**2,
                           gpu_peak_used_mib=max(sampled_memory) if sampled_memory else _gpu_memory_used_mib(),
                           identity_error=float(trainer.stats["identity_error"]), faults=int(trainer.stats["faults"]))
                logger.write(f"event=calibration envs={envs} decisions={measured} dec/s={row['decisions_per_sec']:.3f} "
                             f"vram_peak_mib={row['gpu_peak_used_mib']} reserved_mib={row['torch_peak_reserved_mib']:.1f} "
                             f"identity_error={row['identity_error']:.3e} fault={row['faults']}")
            except torch.cuda.OutOfMemoryError as error:
                row.update(status="oom", error=str(error), gpu_peak_used_mib=max(sampled_memory) if sampled_memory else None)
                logger.write(f"event=calibration envs={envs} status=oom")
            finally:
                stop.set()
                thread.join(timeout=1)
                del trainer
                torch.cuda.empty_cache()
            report["rows"].append(row)
            A8.json_write(report_path, report)
        valid = [row for row in report["rows"] if row["status"] == "passed" and row["faults"] == 0
                 and row["identity_error"] <= 1e-8]
        if not valid:
            raise RuntimeError("no valid A8 calibration candidate")
        best = max(valid, key=lambda row: row["decisions_per_sec"])
        seconds = FULL_SELECTION_DECISIONS / best["decisions_per_sec"]
        report.update(status="complete", completed_utc=_utc(), selected_envs=best["envs"],
                      selected_decisions_per_sec=best["decisions_per_sec"],
                      estimated_training_sec=seconds, estimated_training_hours=seconds / 3600,
                      estimated_wall_hours_with_10pct_overhead=seconds * 1.10 / 3600,
                      input_hash=input_hash, scaler=scaler, hashes=_code_hashes())
        A8.json_write(report_path, report)
        logger.write(f"event=calibration_complete selected_envs={best['envs']} dec/s={best['decisions_per_sec']:.3f} "
                     f"eta_hours={report['estimated_wall_hours_with_10pct_overhead']:.3f}")
        return report
    except BaseException as error:
        trace = traceback.format_exc()
        report.update(status="failed", error=f"{type(error).__name__}: {error}", traceback=trace, failed_utc=_utc())
        A8.json_write(report_path, report)
        logger.write(f"event=crash error={type(error).__name__}:{error}\n{trace}")
        raise
    finally:
        logger.close()
