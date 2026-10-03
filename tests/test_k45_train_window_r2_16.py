import numpy as np
import pandas as pd
import pytest

from out import run_k45_train_window_r2_16 as run


def test_training_rows_stay_inside_window_and_labels_end_before_stop():
    frame = pd.DataFrame({
        "signal_time": pd.date_range("2026-01-06", periods=5, freq="D", tz="UTC"),
    })
    stop = pd.Timestamp("2026-01-10", tz="UTC")

    selected = run.training_window(frame, "signal_time", stop, horizon_minutes=1440,
                                   window_days=3)

    assert selected.signal_time.tolist() == [
        pd.Timestamp("2026-01-07", tz="UTC"),
        pd.Timestamp("2026-01-08", tz="UTC"),
    ]
    assert selected.signal_time.min() >= stop - pd.Timedelta(days=3)
    assert (selected.signal_time + pd.Timedelta(days=1) < stop).all()


def test_time_weights_use_90_day_half_life():
    times = pd.Series(pd.to_datetime(["2026-01-01T00:00:00Z", "2025-10-03T00:00:00Z"]))
    stop = pd.Timestamp("2026-04-01", tz="UTC")

    assert np.allclose(run.time_weights(times, stop), [0.5, 0.25])


def test_expanding_default_seed_must_equal_existing_predictions():
    existing = pd.DataFrame({"pilot_fold": [1], "score": [0.25]})

    run.assert_prediction_parity(existing, existing.copy())
    with pytest.raises(AssertionError):
        run.assert_prediction_parity(existing, existing.assign(score=0.26))


def test_single_position_book_never_overlaps():
    candidates = pd.DataFrame({
        "signal_time": pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 00:30Z",
                                        "2026-01-01 01:00Z"]),
        "entry_time": pd.to_datetime(["2026-01-01 00:00Z", "2026-01-01 01:30Z",
                                       "2026-01-01 01:00Z"]),
        "exit_time": pd.to_datetime(["2026-01-01 01:00Z", "2026-01-01 02:30Z",
                                      "2026-01-01 02:00Z"]),
    })

    accepted, _ = run.admit_single_positions(candidates)

    assert run.max_concurrent(accepted) <= 1


def test_fold_below_500_rows_has_no_trades():
    assert run.fold_has_model(500)
    assert not run.fold_has_model(499)
    assert run.empty_fold_trades(499).empty
