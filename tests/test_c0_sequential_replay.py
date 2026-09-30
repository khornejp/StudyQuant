from __future__ import annotations

"""Execution-contract tests for frozen C0 sequential replay."""

import numpy as np
import pandas as pd
import pytest

from out import run_c0_sequential_replay as replay


def bars(count: int = 60) -> pd.DataFrame:
    return pd.DataFrame({
        "open_time": pd.date_range("2025-01-01", periods=count, freq="min", tz="UTC"),
        "open": np.full(count, 100.0),
    })


def predictions(*rows: tuple[int, int, int, bool]) -> pd.DataFrame:
    """Rows are (signal_index, fold, predicted_class, accepted)."""
    return pd.DataFrame({
        "arm": "C0",
        "pilot_fold": [row[1] for row in rows],
        "signal_index": [row[0] for row in rows],
        "open_time": [pd.Timestamp("2025-01-01", tz="UTC") + pd.Timedelta(minutes=row[0])
                      for row in rows],
        "forward_bps": 0.0,
        "predicted_class": [row[2] for row in rows],
        "confidence": np.linspace(0.9, 0.8, len(rows)),
        "accepted": [row[3] for row in rows],
    })


def test_entry_and_open_i_plus_16_exit_boundary() -> None:
    frame = bars()
    frame.loc[1, "open"] = 100.0
    frame.loc[16, "open"] = 110.0
    frame.loc[17, "open"] = 999.0
    candidate = replay.build_candidates(predictions((0, 406, 0, True)), frame).iloc[0]
    assert candidate.entry_index == 1
    assert candidate.exit_index == 16
    assert candidate.entry_timestamp == frame.loc[1, "open_time"]
    assert candidate.exit_timestamp == frame.loc[16, "open_time"]
    assert candidate.gross_bps == pytest.approx(1_000.0)
    assert candidate.cost_bps == -4.0
    assert candidate.net_bps == pytest.approx(996.0)


def test_adjacent_trade_closes_and_reopens_without_overlap() -> None:
    candidates = replay.build_candidates(
        predictions((0, 406, 0, True), (15, 407, 0, True)), bars()
    )
    selected, skipped, maximum = replay.apply_concurrency(candidates, 1)
    assert len(selected) == 2
    assert skipped == 0
    assert maximum == 1
    assert selected.iloc[0].exit_index == selected.iloc[1].entry_index


def test_hand_built_overlap_is_skipped_by_single_position_rule() -> None:
    candidates = replay.build_candidates(
        predictions((0, 406, 0, True), (14, 407, 0, True)), bars()
    )
    selected, skipped, maximum = replay.apply_concurrency(candidates, 1)
    assert selected.signal_index.tolist() == [0]
    assert skipped == 1
    assert maximum == 1


def test_up_is_long_and_down_is_short() -> None:
    frame = bars()
    frame.loc[1, "open"] = frame.loc[21, "open"] = 100.0
    frame.loc[16, "open"] = frame.loc[36, "open"] = 110.0
    candidates = replay.build_candidates(
        predictions((0, 406, 0, True), (20, 407, 2, True)), frame
    )
    assert candidates.side.tolist() == ["long", "short"]
    assert candidates.gross_bps.tolist() == pytest.approx([1_000.0, -1_000.0])


def test_forced_flat_folds_never_trade() -> None:
    rows = predictions((0, 418, 0, True), (20, 406, 0, True))
    candidates = replay.build_candidates(rows, bars())
    assert candidates.fold.tolist() == [406]


def test_zero_cost_reproduces_gross() -> None:
    candidates = replay.build_candidates(predictions((0, 406, 0, True)), bars(), cost_bps=0.0)
    assert candidates.cost_bps.iloc[0] == 0.0
    assert candidates.net_bps.iloc[0] == pytest.approx(candidates.gross_bps.iloc[0])
