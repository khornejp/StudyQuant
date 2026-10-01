import inspect

import pandas as pd

from out import run_k45_gate_direction_r2_11 as run


def _rows():
    return pd.DataFrame({
        "pilot_fold": [9, 9, 9, 10, 10],
        "signal_index": [60, 70, 79, 80, 90],
        "test_end_index": [80, 80, 80, 100, 100],
    })


def test_validation_contains_only_stop_rows():
    masks = run.fold_masks(_rows(), fold=10, stop_start_index=60,
                           test_start_index=80, horizon=5)
    assert _rows().loc[masks["val"], "signal_index"].tolist() == [60, 70]


def test_test_rows_are_not_an_input_to_tuning():
    assert list(inspect.signature(run.tune_model).parameters) == [
        "train_x", "train_y", "val_x", "val_y", "kind", "sample_weight"
    ]
    masks = run.fold_masks(_rows(), fold=10, stop_start_index=60,
                           test_start_index=80, horizon=5)
    assert not (masks["tuning"] & masks["test"]).any()


def test_validation_label_window_never_crosses_test_start():
    rows = _rows()
    masks = run.fold_masks(rows, fold=10, stop_start_index=60,
                           test_start_index=80, horizon=5)
    assert (rows.loc[masks["val"], "signal_index"] + 5 < 80).all()
    assert not masks["val"].iloc[2]


def test_single_book_never_has_two_simultaneous_positions():
    candidates = pd.DataFrame({"signal_index": [0, 2, 5, 7], "hold": [5, 2, 4, 1]})
    admitted, dropped = run.admit_single(candidates)
    assert admitted.signal_index.tolist() == [0, 5]
    assert dropped.signal_index.tolist() == [2, 7]
    assert run.max_concurrent(admitted) <= 1
