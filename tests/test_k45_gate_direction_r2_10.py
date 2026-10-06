from pathlib import Path

import pandas as pd

from out import run_k45_gate_direction_r2_10 as run


def test_purge_uses_requested_horizon():
    signal_index = pd.Series([70, 80, 89, 90])

    assert run.purge_mask(signal_index, stop_start_index=100, horizon=10).tolist() == [True, True, True, False]
    assert run.purge_mask(signal_index, stop_start_index=100, horizon=20).tolist() == [True, False, False, False]


def test_every_matched_model_label_horizon_equals_hold_horizon():
    specs = run.matched_model_specs()

    assert run.ROOT == Path("out/k45_gate_direction_r2_10b_20261001")
    assert run.HORIZONS == (5, 15, 30, 45, 60, 90, 120, 180, 240)
    assert run.RESIDUAL_LONG_HOLDS == (45, 120, 180, 240)
    assert run.RESIDUAL_SHORT_HOLDS == (5, 15, 60)
    assert len(specs["R2_1_MATCHED"]) == 81
    assert len(specs["RESIDUAL_MATCHED"]) == 12
    assert all(spec["label_h_long"] == spec["h_long"] and spec["label_h_short"] == spec["h_short"]
               for group in specs.values() for spec in group)


def test_feature_exclusion_is_explicit_opt_in_and_default_is_original():
    columns = ["other", "f_signal", "m_spread_valid", "m_book_depth_total"]

    assert run.feature_candidates(columns) == [
        "f_signal", "m_spread_valid", "m_book_depth_total"]
    assert run.feature_candidates(
        columns, frozenset({"m_spread_valid"})) == ["f_signal", "m_book_depth_total"]


def test_single_book_never_has_two_simultaneous_positions():
    candidates = pd.DataFrame({"signal_index": [0, 2, 5, 7], "hold": [5, 2, 4, 1]})

    admitted, dropped = run.admit_single(candidates)

    assert admitted.signal_index.tolist() == [0, 5]
    assert dropped.signal_index.tolist() == [2, 7]
    assert run.max_concurrent(admitted) <= 1
