import numpy as np
import pandas as pd

from out import run_patchtst_k45_flow_inference as flow


def test_exact_binomial_direction_rules():
    assert flow.binomial_tail(66, 40) == 0.05442848220485805
    assert flow.critical_count(66) == 41
    assert flow.critical_count(66, two_sided=True) == 42
    assert flow.binomial_tail(66, 42, two_sided=True) == 0.03558272445223169


def test_politis_white_and_stationary_bootstrap_are_deterministic():
    rng = np.random.default_rng(7)
    innovations = rng.normal(size=400)
    series = np.empty(400)
    series[0] = innovations[0]
    for index in range(1, len(series)):
        series[index] = .7 * series[index - 1] + innovations[index]
    selected = flow.optimal_block_length(series)
    assert selected["block_length_stationary"] > 1
    first = flow.stationary_bootstrap_errors(series - series.mean(),
                                              selected["block_length_stationary"], 40, 123)
    second = flow.stationary_bootstrap_errors(series - series.mean(),
                                               selected["block_length_stationary"], 40, 123)
    np.testing.assert_array_equal(first, second)
    failed = flow.pw_inference(1.0, np.ones(40), "greater", "constant")
    assert failed["selector_status"] == "UNMEASURABLE"
    assert failed["bootstrap_reps"] == 0


def test_regression_influence_reconstructs_binary_effect():
    frame = pd.DataFrame({
        "entry_day": pd.date_range("2024-01-01", periods=8, tz="UTC"),
        "entry_month": ["2024-01"] * 8,
        "d": [0, 1] * 4,
        "x": np.arange(8, dtype=float),
        "y": np.arange(8, dtype=float) + np.array([0, 2] * 4),
    })
    fit, influence, dates = flow.regression_influence(frame, "y", "d", ("x",))
    assert len(dates) == 8
    assert abs(influence.mean() - fit["estimate"]) < 1e-12
    assert fit["estimate"] > 0


def test_periodic_mask_and_single_slot_admission():
    mask = flow._periodic_mask(10, 4)
    assert mask.sum() == 4
    frame = pd.DataFrame({"signal_index": [0, 1, 2, 3],
                          "entry_index": [0, 10, 45, 50],
                          "scheduled_exit_index": [45, 55, 90, 95]})
    np.testing.assert_array_equal(flow._admit(frame, np.ones(4, bool)),
                                  [True, False, True, False])
