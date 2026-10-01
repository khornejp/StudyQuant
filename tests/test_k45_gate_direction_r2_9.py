import numpy as np
import pandas as pd
import pytest

from out import run_k45_gate_direction_r2_9 as r29


def test_single_book_never_exceeds_one_and_drops_first_come_signals():
    frame = pd.DataFrame({
        "signal_index": [0, 5, 10, 20],
        "side": [1, -1, 1, -1],
        "hold": [10, 5, 10, 5],
    })
    admitted, dropped = r29.admit_single(frame)
    assert admitted.signal_index.tolist() == [0, 10, 20]
    assert dropped.signal_index.tolist() == [5]
    assert r29.max_concurrent(admitted) <= 1


def test_each_bar_has_at_most_one_direction():
    reg = np.array([1, 1, -1, 0, -1], dtype=np.int8)
    wgt = np.array([1, -1, -1, 1, 0], dtype=np.int8)
    assert r29.combine_sides(reg, wgt, "AGREE").tolist() == [1, 0, -1, 0, 0]
    assert r29.combine_sides(reg, wgt, "EITHER").tolist() == [1, 0, -1, 1, -1]


def test_threshold_never_uses_same_or_future_fold_scores():
    base = pd.DataFrame({
        "pilot_fold": np.repeat([1, 2, 3], 4),
        "open_time": pd.date_range("2024-01-01", periods=12, freq="30D", tz="UTC"),
        "score": np.arange(12.0),
    })
    changed = base.copy()
    changed.loc[changed.pilot_fold.ge(2), "score"] = 1_000_000
    left = r29.causal_thresholds(base, (.25,), min_history=4)
    right = r29.causal_thresholds(changed, (.25,), min_history=4)
    columns = ["pilot_fold", "q", "low_threshold", "high_threshold", "history_n"]
    pd.testing.assert_frame_equal(
        left.loc[left.pilot_fold.eq(2), columns].reset_index(drop=True),
        right.loc[right.pilot_fold.eq(2), columns].reset_index(drop=True),
    )


def test_primary_selection_refuses_hold_b_rows():
    dev = pd.DataFrame({
        "segment": ["DEV", "DEV"], "combination": ["REG", "WGT"],
        "method": ["EXPANDING_OOS"] * 2, "q": [.01, .02],
        "h_long": [45, 45], "h_short": [45, 45],
        "net_mean_bps": [1.0, 2.0],
    })
    assert r29.select_primary(dev).combination == "WGT"
    with pytest.raises(AssertionError, match="DEV-only"):
        r29.select_primary(pd.concat([dev, dev.assign(segment="HOLD_B")]))
