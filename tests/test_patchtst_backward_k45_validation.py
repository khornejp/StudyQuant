import json
from pathlib import Path

import numpy as np
import pandas as pd

from out import run_patchtst_backward_k45_validation as run


def test_frozen_calendar_fit_budget_and_separate_output():
    plan = run.calendar.fold_plan()
    assert run.FOLDS == tuple(range(406))
    assert len(run.FOLDS) * len(run.SEEDS) == 1218
    assert plan[0]["train_start"] == "2020-07-09T00:00:00+00:00"
    assert plan[0]["test_start"] == "2021-01-08T00:00:00+00:00"
    assert plan[405]["test_end"] == "2024-05-10T00:00:00+00:00"
    assert run.ROOT != run.forecast.ROOT
    assert run.HOLD_MINUTES == 45


def test_gate_ties_pass_and_only_k45_is_exposed():
    threshold, passed = run.q90_gate(np.arange(10.0), np.array([8.1, 9.0]))
    assert threshold == 8.1
    assert passed.tolist() == [True, True]
    assert not hasattr(run, "HOLDS")


def test_cr1_mean_and_primary_minus_control():
    frame = pd.DataFrame({
        "pilot_fold": [0, 0, 1, 1, 2, 2],
        "arm": [run.ARMS[0], run.ARMS[1]] * 3,
        "net_bps": [4.0, 1.0, 5.0, 2.0, 6.0, 3.0],
    })
    primary = run.mean_cr1(frame.loc[frame.arm.eq(run.ARMS[0])])
    difference = run.difference_cr1(frame)
    assert primary["estimate_bps"] == 5.0
    assert difference["estimate_bps"] == 3.0
    assert difference["ci95_lower_bps"] == 3.0


def test_concurrency_uses_half_open_k45_intervals():
    ledger = pd.DataFrame({
        "arm": [run.ARMS[0], run.ARMS[1], run.ARMS[0]],
        "entry_index": [0, 15, 30],
        "exit_index": [45, 60, 75],
    })
    rows = {row["arm"]: row for row in run.concurrency_report(ledger, 0, 75)}
    assert rows["BOTH_ARMS"]["maximum_concurrency"] == 3
    assert rows["BOTH_ARMS"]["mean_concurrency_full_clock"] == 1.8


def test_four_conditions_are_frozen_in_plan_and_manifest_contract():
    text = run.PLAN.read_text(encoding="utf-8")
    assert "lineage-specific reverse-time validation" in text
    assert "not fresh OOS" in text
    assert "No other verdict" in text
    assert "Per-year results are descriptive only" in text
    assert run.RATE_BAND == (0.20, 0.60)
    assert run.MIN_CLUSTERS == 30
    assert run.ARMS == ("DOWN_BREAKOUT_LONG", "UP_BREAKOUT_SHORT")


def test_plan_hash_frozen_before_fit():
    expected = run.PLAN_HASH.read_text(encoding="utf-8").split()[0]
    assert run.sha256(run.PLAN) == expected
    if run.ROOT.exists() and (run.ROOT / "manifest.json").exists():
        manifest = json.loads((run.ROOT / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["plan_sha256"] == expected
        assert manifest["fit_count"] == 1218


def test_checkpoint_path_cannot_touch_frozen_artifact():
    path = run.checkpoint(0, 42)
    assert path.parent == Path("out/patchtst_backward_k45_validation_20260929")
    assert run.forecast.ROOT not in path.parents
