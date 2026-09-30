import numpy as np
import pandas as pd

from btcusdt_quant.funding_source import estimate_funding_rate_minutes
from btcusdt_quant.short_direction import (
    DOWN, FUNDING_DIRECTION_FEATURES, FUNDING_FEATURE_NAMES, NEUTRAL, SIGNED_FEATURE_NAMES, UP,
    SHORT_HORIZON_DIRECTION_FEATURES, SHORT_HORIZON_FUNDING_FEATURE_NAMES,
    SHORT_ORIENTED_FEATURE_NAMES,
    MAGNITUDE_CONTEXT_FEATURE_NAMES, SHORT_ORIENTED_WITH_MAGNITUDE_FEATURE_NAMES,
    _direction_score, _two_stage_probabilities, add_funding_direction_features,
    add_short_horizon_funding_features, add_short_oriented_features, add_signed_direction_features,
    close_direction_labels, close_short_return,
    direction_labels, direction_signal_masks,
)


def test_minute_funding_estimate_is_causal_and_fills_initial_gap() -> None:
    premium = np.asarray([np.nan, 0.001, 0.001, 0.001])
    settled = np.asarray([0.0002, 0.0001, 0.0001, 0.0001])
    estimate = estimate_funding_rate_minutes(premium, settled)
    changed = premium.copy(); changed[-1] = 0.01
    changed_estimate = estimate_funding_rate_minutes(changed, settled)
    assert np.isfinite(estimate).all()
    assert estimate[0] == settled[0]
    assert np.allclose(estimate[1:], 0.0005)
    assert np.allclose(estimate[:-1], changed_estimate[:-1])
    assert estimate_funding_rate_minutes([0.01], [0.0], cap=0.003)[0] == 0.003


def test_conditional_direction_score_removes_touch_probability() -> None:
    probabilities = np.asarray([
        [0.10, 0.70, 0.20],
        [0.30, 0.10, 0.60],
    ])
    assert np.allclose(_direction_score(probabilities, "conditional"), [1 / 6, 1 / 6])
    assert _direction_score(probabilities, "margin").tolist() == [0.1, 0.3]


def test_two_stage_score_uses_touch_as_gate_not_rank_multiplier() -> None:
    probabilities, scores = _two_stage_probabilities(
        np.asarray([0.4, 0.8, 0.9]), np.asarray([0.9, 0.6, 0.7]),
    )
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert np.allclose(scores, [-0.5, 0.1, 0.2])


def test_close_short_return_uses_exact_horizon_and_abstains_at_tail() -> None:
    gross = close_short_return(pd.DataFrame({"close": [100.0, 99.0, 101.0, 100.0]}), horizon=2)
    assert np.allclose(gross[:2], [-0.01, -(100.0 / 99.0 - 1.0)])
    assert np.isnan(gross[2:]).all()


def test_close_direction_labels_use_cost_dead_zone() -> None:
    labels, gross = close_direction_labels(
        pd.DataFrame({"close": [100.0, 99.9, 99.89, 100.0]}), horizon=1, deadzone_bps=4.0,
    )
    assert labels.tolist() == [DOWN, NEUTRAL, UP, NEUTRAL]
    assert np.isnan(gross[-1])


def test_funding_direction_features_are_minute_causal() -> None:
    times = pd.date_range("2021-01-01", periods=500, freq="min", tz="UTC")
    frame = pd.DataFrame({
        "open_time": times,
        "premium_index": np.full(500, 0.001),
        "funding_rate": np.full(500, 0.0001),
    })
    before = add_funding_direction_features(frame.copy())
    changed = frame.copy(); changed.loc[499, "premium_index"] = 0.01
    after = add_funding_direction_features(changed)
    assert len(FUNDING_DIRECTION_FEATURES) == 47
    assert len(FUNDING_FEATURE_NAMES) == 6
    assert np.allclose(before.loc[:498, list(FUNDING_FEATURE_NAMES)], after.loc[:498, list(FUNDING_FEATURE_NAMES)])
    assert before.loc[0, "minutes_to_funding"] == 480
    assert before.loc[479, "minutes_to_funding"] == 1
    assert before.loc[480, "minutes_to_funding"] == 480


def test_short_horizon_funding_features_are_causal_and_use_prior_zscore_baselines() -> None:
    rows = 1_600
    times = pd.date_range("2021-01-01", periods=rows, freq="min", tz="UTC")
    premium = np.sin(np.arange(rows) / 37.0) * 0.001
    frame = pd.DataFrame({
        "open_time": times,
        "premium_index": premium,
        "funding_rate": np.full(rows, 0.0001),
    })
    before = add_short_horizon_funding_features(frame.copy())
    changed = frame.copy(); changed.loc[1_550:, "premium_index"] += 0.01
    after = add_short_horizon_funding_features(changed)
    assert len(SHORT_HORIZON_FUNDING_FEATURE_NAMES) == 10
    assert len(SHORT_HORIZON_DIRECTION_FEATURES) == 51
    np.testing.assert_allclose(
        before.loc[:1_549, list(SHORT_HORIZON_FUNDING_FEATURE_NAMES)],
        after.loc[:1_549, list(SHORT_HORIZON_FUNDING_FEATURE_NAMES)],
        equal_nan=True,
    )
    assert np.isnan(before.loc[479, "funding_pressure_zscore_8h"])
    assert np.isfinite(before.loc[480, "funding_pressure_zscore_8h"])
    assert np.isnan(before.loc[1_439, "funding_pressure_zscore_24h"])
    assert np.isfinite(before.loc[1_440, "funding_pressure_zscore_24h"])


def test_short_oriented_features_preserve_sign_and_are_causal() -> None:
    rows = 100
    close = 100.0 - np.arange(rows) * 0.01
    frame = pd.DataFrame({
        "open": close + 0.02, "close": close, "volume": np.linspace(10.0, 20.0, rows),
        "return_1": pd.Series(close).pct_change().fillna(0.0),
        "return_3": pd.Series(close).pct_change(3).fillna(0.0),
        "return_5": pd.Series(close).pct_change(5).fillna(0.0),
        "close_location_value": np.full(rows, -0.5),
        "upper_shadow": np.full(rows, 0.003), "lower_shadow": np.full(rows, 0.001),
        "taker_imbalance": np.full(rows, -0.2),
        "taker_imbalance_3m": np.full(rows, -0.15),
        "taker_imbalance_5m": np.full(rows, -0.1),
        "taker_imbalance_15m": np.full(rows, -0.05),
        "oi_change_rate_5m": np.full(rows, 0.01), "oi_change_rate_15m": np.full(rows, 0.02),
        "global_ls_account_change_5m": np.full(rows, 0.03),
        "taker_ls_ratio_change_5m": np.full(rows, -0.04),
        "premium_change_5m": np.full(rows, 0.0001),
        "estimated_funding_pressure_uncapped": np.full(rows, 0.0002),
        "funding_pressure_change_5m": np.full(rows, 0.00001),
        "funding_pressure_change_15m": np.full(rows, 0.00002),
        "funding_pressure_acceleration_15m": np.full(rows, 0.00003),
    })
    before = add_short_oriented_features(frame.copy())
    changed = frame.copy(); changed.loc[80:, "close"] *= 2.0; changed.loc[80:, "volume"] *= 10.0
    after = add_short_oriented_features(changed)
    assert len(SHORT_ORIENTED_FEATURE_NAMES) == 30
    assert len(MAGNITUDE_CONTEXT_FEATURE_NAMES) == 5
    assert len(SHORT_ORIENTED_WITH_MAGNITUDE_FEATURE_NAMES) == 35
    assert set(SHORT_ORIENTED_FEATURE_NAMES).isdisjoint({
        "body_pct", "high_low_range", "upper_shadow", "lower_shadow",
        "rv_5", "rv_15", "rv_30", "atr_pct", "volume_zscore_20", "trade_count_zscore_20",
    })
    assert before.loc[20, "short_return_5"] > 0.0
    assert before.loc[20, "short_body"] > 0.0
    assert before.loc[20, "taker_sell_imbalance_1m"] > 0.0
    np.testing.assert_allclose(
        before.loc[:79, list(SHORT_ORIENTED_FEATURE_NAMES)],
        after.loc[:79, list(SHORT_ORIENTED_FEATURE_NAMES)],
        equal_nan=True,
    )


def test_signed_direction_features_are_causal_and_keep_body_sign() -> None:
    rows = 30
    frame = pd.DataFrame({
        "open": np.full(rows, 100.0),
        "close": np.linspace(99.0, 101.0, rows),
        "volume": np.arange(1, rows + 1, dtype=float),
        "taker_buy_base_volume": np.arange(1, rows + 1, dtype=float) * 0.6,
        "return_5": np.linspace(-0.01, 0.01, rows),
        "oi_change_rate_5m": np.linspace(0.01, -0.01, rows),
        "oi_change_rate_15m": np.linspace(-0.02, 0.02, rows),
        "premium_index": np.linspace(-0.001, 0.001, rows),
    })
    before = add_signed_direction_features(frame.copy())
    changed = frame.copy()
    changed.loc[25:, ["close", "volume", "taker_buy_base_volume", "premium_index"]] *= 10.0
    after = add_signed_direction_features(changed)
    assert before.loc[0, "signed_body_pct"] < 0.0 < before.loc[29, "signed_body_pct"]
    assert np.allclose(
        before.loc[:24, list(SIGNED_FEATURE_NAMES)],
        after.loc[:24, list(SIGNED_FEATURE_NAMES)],
        equal_nan=True,
    )


def test_direction_labels_resolve_down_up_timeout_and_same_bar() -> None:
    times = pd.date_range("2021-01-01", periods=6, freq="min", tz="UTC")
    frame = pd.DataFrame({
        "open_time": times,
        "open": [100.0, 100.1, 100.0, 100.0, 100.0, 100.0],
        "high": [100.0, 100.3, 100.0, 100.0, 100.0, 100.0],
        "low": [100.0, 99.7, 100.0, 100.0, 100.0, 100.0],
        "close": [100.0, 99.9, 100.0, 100.0, 100.0, 100.0],
    })
    labels, gross = direction_labels(frame, horizon=3, barrier=0.002)
    assert labels[0] == DOWN
    assert gross[0] == 0.002
    assert labels[2] == NEUTRAL
    assert labels[-1] == NEUTRAL and np.isnan(gross[-1])
    rising = frame.copy()
    rising.loc[1, "close"] = 100.2
    labels, _ = direction_labels(rising, horizon=3, barrier=0.002)
    assert labels[0] == UP


def test_direction_margin_requires_down_probability_above_up_without_count_filter() -> None:
    times = pd.date_range("2021-01-01", periods=4, freq="15min", tz="UTC")
    validation_margin = np.asarray([-0.2, -0.1, 0.1, 0.9])
    validation_gross = np.asarray([-0.002, -0.002, -0.002, 0.002])
    regimes = np.full(4, "up_high_vol", dtype=object)
    masks, audit = direction_signal_masks(
        times, validation_margin, validation_gross, regimes,
        np.asarray([-0.5, 1.0]), np.asarray(["up_high_vol", "up_high_vol"], dtype=object),
    )
    assert audit["q98"]["regimes"]["up_high_vol"]["validation_trades"] == 1
    assert audit["q98"]["regimes"]["up_high_vol"]["allowed"] is True
    assert masks["q98"]["regime_filtered"].tolist() == [False, True]
