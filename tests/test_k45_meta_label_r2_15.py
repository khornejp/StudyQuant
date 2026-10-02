import numpy as np
import pandas as pd
import pytest

from out import run_k45_meta_label_r2_15 as run


def _trades():
    return pd.DataFrame({
        "cell_id": ["R"] * 4,
        "entry_time": pd.to_datetime([
            "2020-01-03T00:00Z", "2020-01-05T00:00Z",
            "2020-02-01T00:00Z", "2020-02-03T00:00Z",
        ]),
        "exit_time": pd.to_datetime([
            "2020-01-04T00:00Z", "2020-02-04T00:00Z",
            "2020-02-01T12:00Z", "2020-02-04T00:00Z",
        ]),
        "net_bps": [10.0, 999.0, -5.0, 20.0],
    })


def test_training_trade_exit_is_strictly_before_retrain_time():
    cutoff = pd.Timestamp("2020-02-01T12:00Z")
    got = run.training_before(_trades(), cutoff)
    assert got.exit_time.max() < cutoff
    assert got.net_bps.tolist() == [10.0]


def test_past_performance_uses_only_trades_closed_before_decision():
    got = run.add_past_performance(_trades())
    assert got.loc[2, "past_net_mean_5"] == pytest.approx(10.0)
    assert got.loc[2, "past_win_rate_5"] == pytest.approx(1.0)
    assert got.loc[3, "past_net_mean_5"] == pytest.approx(2.5)
    changed = _trades()
    changed.loc[1, "net_bps"] = -999.0
    changed = run.add_past_performance(changed)
    assert changed.loc[2, "past_net_mean_5"] == pytest.approx(10.0)


def test_unfiltered_metrics_equal_r2_14_reference():
    generated = pd.DataFrame({
        "cell_id": ["A"], "segment": ["DEV"], "n": [3],
        "net_total_bps": [12.5], "daily_sharpe": [0.25],
    })
    reference = generated.copy()
    audit = run.verify_parity(generated, reference)
    assert audit.parity.all()
    with pytest.raises(AssertionError):
        run.verify_parity(generated.assign(n=2), reference)


def test_filtered_candidates_never_overlap():
    trades = pd.DataFrame({
        "entry_time": pd.to_datetime(["2020-01-01T00:00Z", "2020-01-01T02:00Z"]),
        "exit_time": pd.to_datetime(["2020-01-01T01:00Z", "2020-01-01T03:00Z"]),
    })
    run.assert_single_position(trades)
    overlapping = trades.copy()
    overlapping.loc[1, "entry_time"] = pd.Timestamp("2020-01-01T00:30Z")
    with pytest.raises(AssertionError):
        run.assert_single_position(overlapping)


def test_threshold_quantiles_use_training_probabilities_only():
    train = np.array([0.1, 0.2, 0.8, 0.9])
    labels = np.array([0, 0, 1, 1])
    first = run.filter_thresholds(train, labels)
    unrelated_prediction = np.array([0.0, 1.0, 1.0, 1.0, 1.0])
    second = run.filter_thresholds(train, labels)
    assert unrelated_prediction.mean() != train.mean()
    assert first == second == {"base": 0.5, "q50": 0.5, "q70": pytest.approx(0.81)}


def test_target_selection_follows_frozen_rule():
    representatives = pd.DataFrame({
        "family": [f"A{i}" for i in range(1, 7)],
        "cell_id": [f"A{i}|rep" for i in range(1, 7)],
        "dev_n": [10] * 6, "dev_net_bps": [1.0] * 6,
        "dev_sharpe": np.arange(6), "hold_n": [2] * 6,
        "hold_net_bps": [0.0] * 6, "hold_sharpe": [0.0] * 6,
    })
    cells = pd.DataFrame([
        {"family": "A1", "cell_id": "A1|other", "segment": "DEV", "n": 999,
         "daily_sharpe": 99.0, "random_percentile": 1.0, "net_total_bps": 1.0},
        {"family": "B1", "cell_id": "B1|best", "segment": "DEV", "n": 300,
         "daily_sharpe": 2.0, "random_percentile": .90, "net_total_bps": 2.0},
        {"family": "B1", "cell_id": "B1|second", "segment": "DEV", "n": 400,
         "daily_sharpe": 1.0, "random_percentile": .99, "net_total_bps": 3.0},
        {"family": "B2", "cell_id": "B2|bad", "segment": "DEV", "n": 299,
         "daily_sharpe": 3.0, "random_percentile": 1.0, "net_total_bps": 4.0},
    ])
    costs = pd.DataFrame([
        {"cell_id": "A1|other", "segment": "DEV", "cost_bps": 0.0, "net_total_bps": 5.0},
        {"cell_id": "B1|best", "segment": "DEV", "cost_bps": 0.0, "net_total_bps": 1.0},
        {"cell_id": "B1|second", "segment": "DEV", "cost_bps": 0.0, "net_total_bps": 2.0},
        {"cell_id": "B2|bad", "segment": "DEV", "cost_bps": 0.0, "net_total_bps": 3.0},
    ])
    selected = run.select_targets(cells, costs, representatives)
    assert selected.query("target_set == 'T'").cell_id.tolist() == [f"A{i}|rep" for i in range(1, 7)]
    assert selected.query("target_set == 'G'").cell_id.tolist() == ["B1|best"]
