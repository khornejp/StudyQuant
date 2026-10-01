import json

import numpy as np
import pandas as pd
import pytest

from out import run_k45_gate_direction_r2 as r2


def test_arm_threshold_uses_train_payoffs_only():
    returns = np.array([10.0, 6.0, 2.0, -2.0])
    assert r2.arm_threshold(returns) == 0.5


def test_choose_arm_is_strict_and_resolves_competition_by_edge():
    got = r2.choose_arm(
        np.array([.7, .4, .8, .7]), np.array([.5, .5, .5, .5]),
        np.array([.4, .8, .9, .7]), np.array([.5, .5, .5, .5]),
    )
    assert got.tolist() == [1, -1, -1, 0]


def test_capacity_book_is_first_come_and_reopens_at_exit():
    entries = np.array([0, 1, 2, 3, 5])
    assert r2.admit_capacity(entries, hold=3, capacity=1).tolist() == [True, False, False, True, False]
    assert r2.admit_capacity(entries, hold=3, capacity=3).tolist() == [True, True, True, True, True]


def test_fade_feature_filter_matches_only_named_f_features():
    columns = ["f_return_1", "f_close_zscore_20", "f_volume", "m_return_1", "trend_30d"]
    assert r2.fade_columns(columns) == ["f_return_1", "f_close_zscore_20"]


def test_residualizer_fits_train_and_applies_same_coefficients_to_test():
    train_keep = np.arange(6.0)[:, None]
    train_fade = (2 * train_keep + 3)
    test_keep = np.array([[10.0]])
    test_fade = np.array([[30.0]])
    train_resid, test_resid = r2.residualize(train_keep, train_fade, test_keep, test_fade)
    assert np.max(np.abs(train_resid)) < 1e-10
    assert test_resid[0, 0] == pytest.approx(7.0)


def test_tail_mask_has_exact_ceiling_count_per_tail():
    values = np.arange(101.0)
    low, high = r2.tail_masks(values, .01)
    assert low.sum() == high.sum() == 2
    assert not np.any(low & high)


def test_inference_reports_pw_diagnostics_and_all_fixed_blocks():
    trades = pd.DataFrame({
        "open_time": pd.date_range("2024-01-01", periods=60, freq="D", tz="UTC"),
        "net_bps": np.sin(np.arange(60.0)),
    })
    got = r2.net_inference(trades, "net_bps", reps=99)
    assert got["trade_days"] == 60
    assert got["zero_day_share"] == pytest.approx(1 / 60)
    assert {7, 14, 30} == {int(x) for x in json.loads(got["daily_fixed_blocks"])}
    assert {20, 50} == {int(x) for x in json.loads(got["event_fixed_blocks"])}
