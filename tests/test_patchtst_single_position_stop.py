import numpy as np
import pandas as pd
import pytest

from out import run_patchtst_single_position_stop as run


def test_single_position_skips_overlap_without_queue_and_keeps_arm_books_separate():
    frame = pd.DataFrame({
        "arm": [run.ARMS[0], run.ARMS[0], run.ARMS[0], run.ARMS[0], run.ARMS[1]],
        "signal_index": [0, 10, 45, 46, 10],
        "entry_index": [0, 10, 45, 46, 10],
        "exit_index": [45, 55, 90, 91, 55],
    })
    assert run.single_position_mask(frame).tolist() == [True, False, True, False, True]


def test_stop_uses_intrabar_extreme_and_wins_on_time_exit_bar():
    close = np.full(60, 100.0)
    high = np.full(60, 100.1)
    low = np.full(60, 99.9)
    low[2] = 99.5
    high[45] = 100.5

    stopped, exit_index, fill, gross = run.stop_outcomes(
        np.array([0, 0]), np.array([1, -1]), high, low, close)

    assert stopped.tolist() == [True, True]
    assert exit_index.tolist() == [2, 45]
    assert fill.tolist() == pytest.approx([99.5, 100.5])
    assert gross[0] == pytest.approx(1e4 * np.log(0.995))
    assert gross[1] == pytest.approx(-1e4 * np.log(1.005))


def test_stop_scan_excludes_entry_bar_and_keeps_four_bps_cost_contract():
    close = np.full(50, 100.0)
    high = np.full(50, 100.1)
    low = np.full(50, 99.9)
    low[0] = 90.0

    stopped, exit_index, fill, gross = run.stop_outcomes(
        np.array([0]), np.array([1]), high, low, close)

    assert not stopped[0]
    assert exit_index[0] == run.HOLD_MINUTES
    assert fill[0] == 100.0
    assert gross[0] - run.COST_BPS == -4.0


def test_frozen_contract_and_plan_hash():
    assert run.VARIANTS == (
        "A_SINGLE_NO_STOP", "B_SINGLE_STOP_50", "C_CONCURRENT_NO_STOP")
    assert run.STOP_BPS == 50.0
    assert run.COST_BPS == 4.0
    assert run.FIT_CALLS == 0
    expected = run.PLAN_HASH.read_text(encoding="utf-8").split()[0]
    assert run.sha256(run.PLAN) == expected
