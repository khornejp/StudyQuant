import numpy as np
import pandas as pd

from out import run_k45_mtf_persistence_r2_13 as run


def test_training_label_window_is_strictly_before_stop_start():
    times = pd.Series(pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 00:01Z"]))
    stop = pd.Timestamp("2026-01-01 08:00Z")
    assert run.label_window_mask(times, 480, stop).tolist() == [False, False]
    assert run.label_window_mask(times - pd.Timedelta("1min"), 480, stop).tolist() == [True, False]


def test_atr_and_trailing_exit_do_not_use_later_bars():
    bars = pd.DataFrame({
        "high": np.r_[np.arange(100.0, 115.0), [120.0, 999.0]],
        "low": np.r_[np.arange(99.0, 114.0), [118.0, -999.0]],
        "close": np.r_[np.arange(99.5, 114.5), [119.0, 999.0]],
    })
    before = run.causal_atr(bars).iloc[14]
    mutated = bars.copy()
    mutated.loc[15:, ["high", "low", "close"]] *= 10
    assert run.causal_atr(mutated).iloc[14] == before

    closes = np.array([101.0, 104.0, 102.0, 999.0])
    assert run.trailing_exit_bar(closes, 100.0, 1, 2.0) == 3
    closes[3] = -999.0
    assert run.trailing_exit_bar(closes, 100.0, 1, 2.0) == 3


def test_x_pred_exit_uses_decision_time_prediction_only():
    decision = pd.Timestamp("2026-01-01 00:00Z")
    assert run.predicted_exit_time(decision, 2.49, 60, 8) == decision + pd.Timedelta("2h")
    assert run.predicted_exit_time(decision, 20.0, 60, 8) == decision + pd.Timedelta("8h")


def test_single_position_book_never_overlaps():
    candidates = pd.DataFrame({
        "signal_time": pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 00:30Z", "2026-01-01 01:00Z"]),
        "entry_time": pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 00:30Z", "2026-01-01 01:00Z"]),
        "exit_time": pd.to_datetime(["2026-01-01 01:00Z", "2026-01-01 02:00Z", "2026-01-01 02:00Z"]),
    })
    accepted, dropped = run.admit_single_positions(candidates)
    assert accepted.index.tolist() == [0, 2]
    assert dropped.index.tolist() == [1]
    assert run.max_concurrent(accepted) == 1


def test_censor_flag_occurs_only_at_hmax():
    hit = run.path_labels(np.array([99.0, 98.0, 97.0]), np.array([101.0, 102.0, 103.0]),
                          np.array([99.0, 98.0, 97.0]), 100.0, 1.0, 1, 3)
    censored = run.path_labels(np.array([100.0, 101.0, 102.0]), np.array([101.0, 102.0, 103.0]),
                               np.array([101.0, 102.0, 103.0]), 100.0, 1.0, 1, 3)
    assert hit["duration_bars"] == 1 and not hit["censored"]
    assert censored["duration_bars"] == 3 and censored["censored"]
    assert not hit["censored"] or hit["duration_bars"] == 3
    assert not censored["censored"] or censored["duration_bars"] == 3
