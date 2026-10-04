from __future__ import annotations

import numpy as np
import pandas as pd

from out import run_k45_single_book_combo_r2_24 as R


UTC = "UTC"


def _signals() -> pd.DataFrame:
    t = pd.to_datetime([
        "2025-01-01 00:00Z", "2025-01-01 00:30Z", "2025-01-01 00:30Z",
        "2025-01-01 02:00Z",
    ])
    return pd.DataFrame({
        "candidate": ["low", "low", "high", "low"],
        "entry_time": t,
        "exit_time": pd.to_datetime([
            "2025-01-01 01:00Z", "2025-01-01 01:30Z", "2025-01-01 01:30Z",
            "2025-01-01 03:00Z",
        ]),
        "side": [1, -1, -1, 1],
        "entry_price": [100.0, 101.0, 101.0, 102.0],
        "exit_price": [101.0, 100.0, 100.0, 103.0],
    })


def test_never_more_than_one_position_and_no_long_short_overlap():
    accepted, _, _ = R.run_single_book(
        _signals(), ["high", "low"], "SWITCH",
        pd.Series([101.0], index=pd.to_datetime(["2025-01-01 00:30Z"])),
    )
    assert R.max_concurrent(accepted) <= 1
    assert not R.has_opposite_overlap(accepted)


def test_first_drops_signals_while_holding():
    accepted, dropped, _ = R.run_single_book(_signals(), ["high", "low"], "FIRST")
    assert accepted.candidate.tolist() == ["low", "low"]
    assert dropped.reason.value_counts().to_dict() == {"holding": 2}


def test_same_minute_uses_one_priority_signal():
    signals = _signals().iloc[1:3]
    accepted, dropped, _ = R.run_single_book(signals, ["high", "low"], "PRIORITY")
    assert accepted.candidate.tolist() == ["high"]
    assert dropped[["candidate", "reason"]].values.tolist() == [["low", "simultaneous"]]


def test_switch_closes_then_enters_and_charges_two_legs():
    accepted, dropped, switches = R.run_single_book(
        _signals().iloc[:3], ["high", "low"], "SWITCH",
        pd.Series([101.5], index=pd.to_datetime(["2025-01-01 00:30Z"])),
    )
    assert accepted.candidate.tolist() == ["low", "high"]
    assert accepted.exit_time.iloc[0] == accepted.entry_time.iloc[1]
    assert accepted.exit_price.iloc[0] == accepted.entry_price.iloc[1] == 101.5
    assert switches.switch_cost_bps.tolist() == [4.0]
    assert dropped[["candidate", "reason"]].values.tolist() == [["low", "simultaneous"]]


def test_one_candidate_equals_standalone_trade_set():
    source = _signals().loc[[0, 3]].reset_index(drop=True)
    accepted, dropped, switches = R.run_single_book(source, ["low"], "FIRST")
    pd.testing.assert_frame_equal(
        accepted[R.TRADE_COLUMNS].reset_index(drop=True), source[R.TRADE_COLUMNS],
        check_dtype=False,
    )
    assert dropped.empty and switches.empty


def test_priority_uses_dev_values_only():
    frame = pd.DataFrame({
        "candidate": ["a", "b", "a", "b"],
        "segment": ["DEV_COMMON", "DEV_COMMON", "HOLD_B", "HOLD_B"],
        "boundary": ["PESS"] * 4,
        "pw_ci95_lower_daily_bps": [1.0, 2.0, 999.0, -999.0],
    })
    assert R.dev_priority(frame, ["a", "b"]) == ["b", "a"]
