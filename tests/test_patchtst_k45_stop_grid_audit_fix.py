import math

import numpy as np
import pandas as pd
import pytest

from out import run_patchtst_k45_stop_grid_audit_fix as run


def _bars(rows=80):
    return pd.DataFrame({
        "open_time": pd.date_range("2021-01-08", periods=rows, freq="min", tz="UTC"),
        "open": np.full(rows, 100.0),
        "high": np.full(rows, 100.1),
        "low": np.full(rows, 99.9),
        "close": np.full(rows, 100.0),
    })


def test_touch_gap_late_and_adverse_use_one_stop_bar():
    bars = _bars()
    bars.loc[2, ["open", "low", "close"]] = [99.4, 99.2, 99.3]
    bars.loc[45, ["open", "high", "close"]] = [100.6, 100.9, 100.8]
    outcome = run.stop_path(np.array([0, 0]), np.array([1, -1]), bars, 50.0)
    assert outcome["stopped"].tolist() == [True, True]
    assert outcome["exit_index"].tolist() == [2, 45]
    assert outcome["touch"].tolist() == pytest.approx([99.5, 100.5])
    assert outcome["gap"].tolist() == pytest.approx([99.4, 100.6])
    assert outcome["late"].tolist() == pytest.approx([99.3, 100.8])
    assert outcome["adverse"].tolist() == pytest.approx([99.2, 100.9])


def test_none_is_fill_invariant():
    bars = _bars()
    outcome = run.stop_path(np.array([0]), np.array([1]), bars, None)
    assert not outcome["stopped"][0]
    assert outcome["exit_index"][0] == run.HOLD_MINUTES
    assert outcome["touch"][0] == outcome["gap"][0] == outcome["late"][0]


def test_scheduled_exit_boundary_is_checked_before_any_stop():
    stamps = pd.date_range(run.FOLD_START, periods=4321, freq="min", tz="UTC").asi8
    candidates = pd.DataFrame({"pilot_fold": [0, 0], "entry_index": [4274, 4275]})
    assert run.boundary_mask(candidates, stamps, 45).tolist() == [True, False]


def test_hac_lag_choice_is_fixed_by_g_only():
    values = np.linspace(-1.0, 1.0, 61)
    folds = np.arange(61)
    small = run.hac_mean(values, folds, folds)
    assert small["primary_lag"] == 60
    assert small["alternative_lag"] == math.floor(4 * (61 / 100) ** (2 / 9))
    assert small["selected_rule"] == "alternative_auto"

    values = np.linspace(-1.0, 1.0, 406)
    folds = np.arange(406)
    large = run.hac_mean(values, folds, folds)
    assert large["primary_lag"] == 60
    assert large["selected_rule"] == "primary_60"


def test_frozen_contract_and_plan_hash():
    assert len(run.STOP_LABELS) * len(run.ARMS) * len(run.FILL_MODES) == 48
    assert run.FIT_CALLS == 0
    assert run.PRIOR_STOP_RATES["10"] == pytest.approx(0.8028537226383619)
    expected = run.PLAN_HASH.read_text(encoding="utf-8").split()[0]
    assert run.sha256(run.PLAN) == expected
