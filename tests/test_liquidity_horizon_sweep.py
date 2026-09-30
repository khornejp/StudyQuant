import numpy as np
import pandas as pd

from btcusdt_quant.liquidity_horizon_sweep import (
    _asof_prices,
    _binary_fade_correlation,
    _metrics,
    causal_features,
)


def test_endpoint_lookup_is_forward_and_fresh():
    values, valid = _asof_prices(
        np.array([1_000, 2_001, 4_000]), np.array([10.0, 20.0, 30.0]),
        np.array([1_000, 2_000, 2_999]), before=False)
    np.testing.assert_equal(valid, [True, True, False])
    np.testing.assert_allclose(values[:2], [10.0, 20.0])
    assert np.isnan(values[2])


def test_causal_features_use_only_trailing_sixteen_prices():
    origins = pd.DataFrame({
        "origin": pd.date_range("2024-01-01", periods=100, freq="min", tz="UTC"),
        "raw_reference": np.exp(np.arange(100) ** 2 / 1_000_000),
    })
    result = causal_features(origins)
    assert (result.loc[:14, "vol_decile"] == 0).all()
    assert (result.loc[15:, "direction"] == "up").all()
    assert set(result.loc[15:, "vol_decile"]) == set(range(1, 11))


def test_cell_math_and_fade_correlation():
    row = pd.Series({"n": 100, "both_n": 20, "one_n": 50, "side_fills": 90,
                     "y_sum": 10.0, "y_both_sum": 80.0, "y_one_sum": -70.0})
    metrics = _metrics(row)
    assert metrics["y_both"] == 4.0
    assert metrics["y_one"] == -1.4
    assert metrics["required_double_to_one"] == .35
    assert metrics["realised_double_to_one"] == .4
    assert metrics["trade_rate"] == .7
    assert metrics["fill_rate"] == .45
    assert _binary_fade_correlation({"down": 40, "flat": 20, "up": 40}, "down") > 0
    assert _binary_fade_correlation({"down": 40, "flat": 20, "up": 40}, "up") < 0
