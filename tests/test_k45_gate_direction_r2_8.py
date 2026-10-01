import numpy as np
import pandas as pd

from out import run_k45_gate_direction_r2_8 as r28


def test_single_book_never_exceeds_one_and_drops_first_come_signals():
    frame = pd.DataFrame({
        "signal_index": [0, 5, 10, 20],
        "side": [1, -1, 1, -1],
        "hold": [10, 5, 10, 5],
    })
    admitted, dropped = r28.admit_single(frame)
    assert admitted.signal_index.tolist() == [0, 10, 20]
    assert dropped.signal_index.tolist() == [5]
    assert r28.max_concurrent(admitted) == 1


def test_one_bar_chooses_only_the_higher_positive_edge():
    long = np.array([0.2, -0.1, 0.1, 0.0])
    short = np.array([0.1, 0.3, 0.1, 0.0])
    assert r28.choose_edge_side(long, short).tolist() == [1, -1, 0, 0]


def test_causal_margin_never_uses_same_or_future_fold_scores():
    base = pd.DataFrame({
        "pilot_fold": np.repeat([1, 2, 3], 4),
        "score": np.arange(12.0),
    })
    changed = base.copy()
    changed.loc[changed.pilot_fold.ge(2), "score"] = 1_000_000
    left = r28.causal_margins(base, target_rate=.25, min_history=4)
    right = r28.causal_margins(changed, target_rate=.25, min_history=4)
    columns = ["pilot_fold", "margin", "history_n", "history_max_fold"]
    pd.testing.assert_frame_equal(
        left.loc[left.pilot_fold.eq(2), columns].reset_index(drop=True),
        right.loc[right.pilot_fold.eq(2), columns].reset_index(drop=True),
    )
    assert np.isnan(left.loc[left.pilot_fold.eq(1), "margin"].iat[0])
