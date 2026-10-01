import numpy as np
import pandas as pd

from out import run_k45_gate_direction_r2_7 as r27


def _scores(values):
    return pd.DataFrame({
        "pilot_fold": np.repeat([1, 2, 3], 4),
        "open_time": pd.date_range("2024-01-01", periods=12, freq="30D", tz="UTC"),
        "score": values,
    })


def test_fold_threshold_never_uses_same_or_future_fold_scores():
    base = _scores(np.arange(12.0))
    changed = base.copy()
    changed.loc[changed.pilot_fold.ge(2), "score"] = 1_000_000
    left = r27.causal_thresholds(base, (.25,), min_history=4)
    right = r27.causal_thresholds(changed, (.25,), min_history=4)
    columns = ["pilot_fold", "q", "low_threshold", "high_threshold", "history_n"]
    pd.testing.assert_frame_equal(
        left.loc[left.pilot_fold.eq(2), columns].reset_index(drop=True),
        right.loc[right.pilot_fold.eq(2), columns].reset_index(drop=True),
    )


def test_threshold_skips_until_minimum_prior_oos_count():
    got = r27.causal_thresholds(_scores(np.arange(12.0)), (.25,), min_history=5)
    assert got.set_index("pilot_fold").eligible.to_dict() == {1: False, 2: False, 3: True}
    assert got.set_index("pilot_fold").history_n.to_dict() == {1: 0, 2: 4, 3: 8}


def test_top_profit_trim_removes_largest_values():
    values = np.array([-10.0, 0.0, 5.0, 100.0])
    assert r27.trim_top_profits(values, 1) == np.mean([-10.0, 0.0, 5.0])
    assert np.isnan(r27.trim_top_profits(values, 4))
