from pathlib import Path

import pandas as pd

from out import run_k45_gate_direction_r2_11 as r211
from out import run_k45_gate_direction_r2_9b as run


def test_variants_use_requested_seed_and_parameters():
    expected = {
        "V1": (20261002, 4, .05, 500, 3),
        "V2": (20261003, 4, .05, 500, 3),
        "V3": (20261004, 4, .05, 500, 3),
        "V4": (20261001, 6, .05, 500, 3),
        "V5": (20261001, 4, .03, 833, 3),
    }
    for variant, values in expected.items():
        params = run.variant_parameters(variant)
        assert (params["random_seed"], params["depth"], params["learning_rate"],
                params["iterations"], params["l2_leaf_reg"]) == values
        model = run.make_model("binary", variant)
        actual = model.get_params()
        assert all(actual[key] == value for key, value in params.items())


def test_v0_v6_reuse_existing_predictions_without_training():
    assert not run.needs_training("V0")
    assert not run.needs_training("V6")
    assert run.prediction_source("V0", "r21_long_h45") == Path(
        "out/k45_gate_direction_r2_10b_20261001/r21_long_h45_predictions.parquet")
    assert run.prediction_source("V6", "r21_long_h45") == Path(
        "out/k45_gate_direction_r2_11_20261001/r21_long_h45_tuned_predictions.parquet")
    boundaries = run.dataset_boundaries()
    pd.testing.assert_frame_equal(
        run.load_variant_frame("V0", "r21_long_h45", boundaries),
        r211.fixed_frame("r21_long_h45", boundaries), check_like=True)
    pd.testing.assert_frame_equal(
        run.load_variant_frame("V6", "r21_long_h45", boundaries),
        r211.tuned_frame("r21_long_h45", boundaries), check_like=True)


def test_robust_rule_is_exactly_predefined():
    rows = []
    for variant in run.VARIANTS:
        rows += [
            {"cell_id": "pass", "variant": variant, "segment": "DEV",
             "net_mean_bps": 1.0, "n": 40, "long_net_mean_bps": 2.0,
             "short_net_mean_bps": .5, "pw_ci95_lower": .1},
            {"cell_id": "pass", "variant": variant, "segment": "HOLD_B",
             "net_mean_bps": -1.0 if variant == "V6" else 1.0, "n": 30,
             "long_net_mean_bps": 2.0, "short_net_mean_bps": .5,
             "pw_ci95_lower": -.1},
            {"cell_id": "fail", "variant": variant, "segment": "DEV",
             "net_mean_bps": -1.0 if variant == "V3" else 1.0, "n": 40,
             "long_net_mean_bps": 2.0, "short_net_mean_bps": .5,
             "pw_ci95_lower": .2},
            {"cell_id": "fail", "variant": variant, "segment": "HOLD_B",
             "net_mean_bps": 1.0, "n": 30, "long_net_mean_bps": 2.0,
             "short_net_mean_bps": .5, "pw_ci95_lower": -.1},
        ]
    summary = run.summarize_robustness(pd.DataFrame(rows), pd.DataFrame(
        {"cell_id": ["pass", "fail"] * 7, "variant": sum(([v, v] for v in run.VARIANTS), []),
         "jaccard_v0": [1.0, .5] * 7}))
    passed = summary.set_index("cell_id")
    assert bool(passed.loc["pass", "is_robust"])
    assert passed.loc["pass", "dev_positive_variants"] == 7
    assert passed.loc["pass", "hold_b_positive_variants"] == 6
    assert not bool(passed.loc["fail", "is_robust"])


def test_single_book_never_has_two_simultaneous_positions():
    candidates = pd.DataFrame({"signal_index": [0, 2, 5, 7], "hold": [5, 2, 4, 1]})
    admitted, dropped = run.admit_single(candidates)
    assert admitted.signal_index.tolist() == [0, 5]
    assert dropped.signal_index.tolist() == [2, 7]
    assert run.max_concurrent(admitted) <= 1


def test_train_label_window_never_crosses_stop_start():
    rows = pd.DataFrame({"pilot_fold": [1] * 4, "signal_index": [69, 79, 80, 90]})
    masks = run.fold_masks(rows, fold=2, stop_start_index=80,
                           test_start_index=100, horizon=10)
    assert rows.loc[masks["train"], "signal_index"].tolist() == [69]
    assert (rows.loc[masks["train"], "signal_index"] + 10 < 80).all()
