from __future__ import annotations

import numpy as np
import pandas as pd

from out import run_k45_classic_rules_r2_14 as R214
from out import run_k45_combo_robust_r2_25 as R
from out import run_k45_single_book_combo_r2_24 as R224


def _trades() -> pd.DataFrame:
    return pd.DataFrame({
        "candidate": ["a", "b", "a"],
        "entry_time": pd.to_datetime(["2025-01-01 00:00Z", "2025-01-01 00:30Z",
                                      "2025-01-01 02:00Z"]),
        "exit_time": pd.to_datetime(["2025-01-01 01:00Z", "2025-01-01 01:30Z",
                                     "2025-01-01 03:00Z"]),
        "side": [1, -1, 1], "entry_price": [100.0, 101.0, 102.0],
        "exit_price": [101.0, 100.0, 103.0],
    })


def test_single_position_invariant():
    accepted, _, _ = R224.run_single_book(_trades(), ["a", "b"], "FIRST")
    assert R224.max_concurrent(accepted) <= 1
    assert not R224.has_opposite_overlap(accepted)


def test_r2_24_reproduction():
    frame = pd.read_parquet(R.OUT / "reproduction.parquet")
    assert len(frame) == 16
    assert frame.match.all()
    assert frame.n_difference.eq(0).all()
    assert frame.max_abs_difference.le(R.REPRO_TOLERANCE).all()


def test_delayed_entry_uses_only_delayed_minute_price():
    source = _trades().iloc[[0]].copy()
    index = pd.date_range("2025-01-01", periods=120, freq="min", tz="UTC")
    opens = pd.Series(np.arange(120, dtype=float) + 100, index=index)
    actual = R.delay_entries(source, opens, 5)
    changed = opens.copy()
    changed.loc[changed.index > pd.Timestamp("2025-01-01 00:05Z")] = 999999.0
    pd.testing.assert_frame_equal(actual, R.delay_entries(source, changed, 5))
    assert actual.entry_time.iat[0] == pd.Timestamp("2025-01-01 00:05Z")
    assert actual.entry_price.iat[0] == opens.loc[pd.Timestamp("2025-01-01 00:05Z")]


def test_e1_z25_signal_matches_r2_14_definition():
    bars = pd.DataFrame({
        "volume_z20": [0.0, 2.6, 2.7, 3.0],
        "close": [10.0, 12.0, 8.0, 11.0],
        "high_20": [11.0, 11.0, 13.0, 10.0],
        "low_20": [9.0, 9.0, 9.0, 7.0],
    })
    expected = np.zeros(len(bars), np.int8)
    expected[(bars.volume_z20 > 2.5).to_numpy() &
             bars.close.gt(bars.high_20.shift()).fillna(False).to_numpy()] = 1
    expected[(bars.volume_z20 > 2.5).to_numpy() &
             bars.close.lt(bars.low_20.shift()).fillna(False).to_numpy()] = -1
    np.testing.assert_array_equal(R.e1_entry_signal(bars, 2.5), expected)
    spec = R214.Spec("E1", "1h", "2.5", "signal", "L")
    assert spec.cell_id == "E1|1h|2.5|signal|L"


def test_model_perturbation_uses_only_requested_variant():
    frame = pd.DataFrame({
        "variant": ["V0", "V1", "V1"],
        "cell_id": [R.R29_CELL, R.R29_CELL, "other"],
        "signal_index": [1, 2, 3],
    })
    selected = R.r29_variant_entries(frame, "V1")
    assert selected.signal_index.tolist() == [2]
    assert selected.variant.eq("V1").all()
    assert selected.cell_id.eq(R.R29_CELL).all()
