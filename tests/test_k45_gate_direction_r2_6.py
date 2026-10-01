import numpy as np
import pandas as pd

from out import run_k45_gate_direction_r2_6 as r26


def test_both_arms_use_the_same_full_horizon_sweep():
    expected = (5, 15, 30, 45, 60, 90, 120, 180, 240)
    assert r26.HORIZONS == {"LONG": expected, "SHORT": expected}


def test_extended_horizon_table_contains_both_arms_and_only_two_to_four_hours():
    core = pd.DataFrame({
        "arm": ["LONG", "LONG", "SHORT", "SHORT"],
        "horizon": [90, 120, 180, 240],
    })
    got = r26.extended_horizon_table(core)
    assert got[["arm", "horizon"]].values.tolist() == [
        ["LONG", 120], ["SHORT", 180], ["SHORT", 240],
    ]


def test_strict_side_rules():
    score = np.array([-.2, -.1, 0, .1, .2])
    assert r26.strict_side(score, .1).tolist() == [-1, 0, 0, 0, 1]


def test_exit_validity_is_strict_at_fold_end_and_reports_data_end_separately():
    frame = pd.DataFrame({"signal_index": [5, 7, 9], "test_end_index": [10, 10, 20]})
    valid, fold_end, data_end = r26.exit_validity(frame, horizon=3, market_rows=11)
    assert valid.tolist() == [True, False, False]
    assert fold_end.tolist() == [False, True, False]
    assert data_end.tolist() == [False, False, True]


def test_actual_funding_uses_entry_open_exit_closed_interval_and_side_sign():
    frame = pd.DataFrame({
        "signal_index": [0, 1],
        "open_time": pd.to_datetime(["2024-01-01 00:00Z", "2024-01-01 00:01Z"]),
        "side": [1, -1],
    })
    close = np.array([100.0, 101.0, 102.0, 103.0])
    events = pd.DataFrame({
        "funding_time": pd.to_datetime(["2024-01-01 00:00Z", "2024-01-01 00:02Z"]),
        "funding_rate": [0.01, 0.001],
    })
    got = r26.attach_trade_values(frame, horizon=2, close=close, events=events)
    np.testing.assert_allclose(got.funding_bps, [10.0, -10.0])
    np.testing.assert_allclose(got.gross_bps, [200.0, -198.01980198019803])
    np.testing.assert_allclose(got.net_bps, got.gross_bps - 4 - got.funding_bps)
    assert got.funding_event_count.tolist() == [1, 1]


def test_single_book_is_first_come_and_all_keeps_every_trade():
    frame = pd.DataFrame({"signal_index": [0, 1, 3, 4]})
    assert r26.apply_book(frame, "SINGLE", 3).signal_index.tolist() == [0, 3]
    assert r26.apply_book(frame, "ALL", 3).signal_index.tolist() == [0, 1, 3, 4]


def test_random_direction_is_seeded_and_preserves_entries():
    frame = pd.DataFrame({"signal_index": np.arange(20), "side": np.ones(20, dtype=np.int8)})
    first = r26.random_directions(frame, 20261001)
    second = r26.random_directions(frame, 20261001)
    assert first.signal_index.tolist() == frame.signal_index.tolist()
    assert first.side.tolist() == second.side.tolist()
    assert set(first.side) == {-1, 1}
