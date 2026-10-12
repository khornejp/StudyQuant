"""A8 selection driver resume boundaries."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from btcusdt_quant.rl import a8_ga_rl as A8
from btcusdt_quant.rl import a8_selection as A8S


class _ReachedMonth(RuntimeError):
    def __init__(self, month):
        self.month = month


class _Trainer:
    decisions = 50_000_000
    model = object()
    stats = {}

    def __init__(self):
        self.loaded = None

    def load_state_dict(self, state):
        self.loaded = state


class _Evaluator:
    def __init__(self):
        self.loaded = None
        self.month_ends = []

    def load_state_dict(self, state):
        self.loaded = state

    def run_month(self, model, month_end):
        self.month_ends.append(pd.Timestamp(month_end, tz="UTC"))
        raw = {key: [0.0] * len(A8S.CELLS) for key in A8.A8Evaluator.METRICS}
        return {**raw, "round_trips": [0.0] * len(A8S.CELLS), "identity_error": 0.0,
                "faults": 0, "max_hold_min": 0, "decisions": 0}


def test_mid_generation_resume_keeps_completed_genome(tmp_path):
    genome = A8.population(n=1)[0]
    genome_dir = tmp_path / "genomes" / "generation_02" / genome.name / f"seed_{A8.POPULATION_SEED}"
    old_hash_id = "old"
    expected = {"status": "complete", "hash_id": old_hash_id, "fitness_raw_net4": [1.0, 2.0]}
    A8.json_write(genome_dir / "result.json", expected)
    config = A8S.SelectionConfig("unit", population=2, generations=2, envs=2, start="2022-01", end="2022-01",
                                 pretrain_decisions=2, monthly_decisions=2, smoke=True)

    result = A8S._run_genome(genome, 2, config.seed, config, config.validate(), {}, (), 1.0, {}, "new", {},
                             tmp_path, SimpleNamespace(write=lambda message: None), A8S.CommitCounter(0),
                             compatible_hash_ids={old_hash_id, "new"})

    assert result == expected


def test_resume_immediately_after_evaluation_continues_same_month(tmp_path, monkeypatch):
    months = A8.selection_months("2022-01", "2023-12")
    trainer, evaluator = _Trainer(), _Evaluator()
    state = {"trainer": "trainer-state", "evaluator": "evaluator-state",
             "monthly": [{"month": f"{month:%Y-%m}"} for month in months[:21]],
             "phase": "evaluated:2023-09", "month_index": 20}
    monkeypatch.setattr(A8S, "_make_trainer", lambda *args: trainer)
    monkeypatch.setattr(A8S, "_make_evaluator", lambda *args: evaluator)
    monkeypatch.setattr(A8S, "_load_progress", lambda *args: ({"phase": state["phase"]}, state))
    monkeypatch.setattr(A8S, "_write_genome_report", lambda *args: None)
    monkeypatch.setattr(A8S, "_save_progress", lambda *args: {})
    monkeypatch.setattr(A8S, "_continual_sampler",
                        lambda market, genome, month, all_months: (_ for _ in ()).throw(_ReachedMonth(month)))
    config = A8S.SelectionConfig("unit", population=2, generations=2, envs=2, start="2022-01",
                                 end="2023-12", pretrain_decisions=2, monthly_decisions=2, smoke=True)

    with pytest.raises(_ReachedMonth) as stopped:
        A8S._run_genome(A8.population(n=1)[0], 2, config.seed, config, months, {}, (), 1.0,
                        {}, "hash", {}, tmp_path, SimpleNamespace(write=lambda message: None),
                        A8S.CommitCounter(0))

    assert f"{stopped.value.month:%Y-%m}" == "2023-09"
    assert evaluator.month_ends == []
    assert trainer.loaded == "trainer-state" and evaluator.loaded == "evaluator-state"


def test_resume_after_trained_month_starts_next_evaluation(tmp_path, monkeypatch):
    months = A8.selection_months("2022-01", "2023-12")
    trainer, evaluator = _Trainer(), _Evaluator()
    state = {"trainer": {}, "evaluator": {}, "monthly": [{"month": f"{month:%Y-%m}"} for month in months[:21]],
             "phase": "trained:2023-09", "month_index": 20}
    monkeypatch.setattr(A8S, "_make_trainer", lambda *args: trainer)
    monkeypatch.setattr(A8S, "_make_evaluator", lambda *args: evaluator)
    monkeypatch.setattr(A8S, "_load_progress", lambda *args: ({"phase": state["phase"]}, state))
    monkeypatch.setattr(A8S, "_write_genome_report", lambda *args: None)
    monkeypatch.setattr(A8S, "_save_progress", lambda *args: {})
    monkeypatch.setattr(A8S, "_continual_sampler",
                        lambda market, genome, month, all_months: (_ for _ in ()).throw(_ReachedMonth(month)))
    config = A8S.SelectionConfig("unit", population=2, generations=2, envs=2, start="2022-01",
                                 end="2023-12", pretrain_decisions=2, monthly_decisions=2, smoke=True)

    with pytest.raises(_ReachedMonth) as stopped:
        A8S._run_genome(A8.population(n=1)[0], 2, config.seed, config, months, {}, (), 1.0,
                        {}, "hash", {}, tmp_path, SimpleNamespace(write=lambda message: None),
                        A8S.CommitCounter(0))

    assert f"{stopped.value.month:%Y-%m}" == "2023-10"
    assert evaluator.month_ends == [pd.Timestamp("2023-11-01", tz="UTC")]


def test_generation_boundary_resume_skips_completed_generation(tmp_path, monkeypatch):
    config = A8S.SelectionConfig("a8_ga_selection_r2_20261012", population=2, generations=2, envs=2,
                                 start="2022-01", end="2022-01",
                                 pretrain_decisions=2, monthly_decisions=2, smoke=True)
    code_hashes, input_hash, scaler = {"driver": "unit"}, {}, {}
    hashes = {"code": code_hashes, "input": input_hash, "config": A8S._identity_config(config)}
    hash_id = A8S._canonical_sha(hashes)
    old_hash_id = "d927ce0c8201ed153180b894385c20720c2c45fdbe983b56ffee9d08f3484687"
    run_dir = tmp_path / "smdp_a8" / config.run_id
    run_dir.mkdir(parents=True)
    initial = A8.population(config.seed, config.population)
    fitness = {genome.name: (float(index), float(index)) for index, genome in enumerate(initial)}
    next_population = A8.next_generation(initial, fitness, config.seed, 1, elite=2)
    summary = {"generation": 0, "status": "complete", "hash_id": old_hash_id,
               "population": [genome.to_json() for genome in initial], "results": [],
               "ranking": list(reversed(list(fitness))),
               "next_population": [genome.to_json() for genome in next_population]}
    A8.json_write(run_dir / "generation_00_summary.json", summary)
    report = A8S._report_base(config, code_hashes, input_hash, scaler)
    report.update(hash_id=old_hash_id, resume_count=0, amendment_revision="r2")
    report["locked"]["amendment_revision"] = "r2"
    A8.json_write(run_dir / "selection_report.json", report)
    calls = []

    def fake_run(genome, generation, seed, *args, **kwargs):
        calls.append((generation, genome.name, seed))
        return {"fitness_raw_net4": [float(seed), float(seed)]}

    monkeypatch.setattr(A8S, "OUT", tmp_path)
    monkeypatch.setattr(A8S, "_code_hashes", lambda: code_hashes)
    monkeypatch.setattr(A8S, "_load_inputs", lambda reward: ({}, (), np.array([]), 1.0, input_hash, scaler))
    monkeypatch.setattr(A8S, "_run_genome", fake_run)
    monkeypatch.setattr("torch.cuda.is_available", lambda: True)
    monkeypatch.setattr("torch.set_num_threads", lambda value: None)
    monkeypatch.setattr("numba.set_num_threads", lambda value: None)

    result = A8S.run_selection(config, resume=True)

    assert result["status"] == "complete"
    assert result["hash_id"] == hash_id and result["previous_hash_id"] == old_hash_id
    assert result["amendment_revision"] == "r2.1"
    assert not any(generation == 0 for generation, _, _ in calls)
    assert [(generation, name) for generation, name, _ in calls[:2]] == [(1, "G01_00"), (1, "G01_01")]
