import numpy as np
import pandas as pd

from btcusdt_quant.short_fast_regime import (
    ADDED_FAST_FEATURE_NAMES,
    MODEL_FEATURE_NAMES,
    QUANTILES,
    SLOW_REGIME_FEATURE_NAMES,
    _sequence_batch,
    add_fast_regime_features,
    assign_regimes,
    fit_regime_thresholds,
    fold_signal_masks,
    tune_fold,
)


def _frame(rows: int = 3_000) -> pd.DataFrame:
    times = pd.date_range("2021-01-01", periods=rows, freq="min", tz="UTC")
    close = 100.0 + np.sin(np.arange(rows) / 17.0) + np.arange(rows) / 100_000.0
    return pd.DataFrame({"open_time": times, "close": close, "rv_60": np.linspace(0.001, 0.003, rows)})


def test_fast_features_are_causal_and_slow_features_are_not_model_inputs() -> None:
    original = _frame()
    changed = original.copy()
    changed.loc[2_000:, "close"] += 1_000.0
    before = add_fast_regime_features(original)
    after = add_fast_regime_features(changed)
    np.testing.assert_allclose(
        before.loc[:1_999, list(ADDED_FAST_FEATURE_NAMES)],
        after.loc[:1_999, list(ADDED_FAST_FEATURE_NAMES)],
        equal_nan=True,
    )
    assert set(SLOW_REGIME_FEATURE_NAMES).isdisjoint(MODEL_FEATURE_NAMES)


def test_regime_thresholds_use_only_supplied_training_rows() -> None:
    frame = add_fast_regime_features(_frame())
    train = np.arange(500, 1_500)
    expected = fit_regime_thresholds(frame, train)
    assert {"return_24h_q33", "return_24h_q67"} <= set(expected)
    changed = frame.copy()
    changed.loc[1_500:, "ema_gap_15m"] = 999.0
    changed.loc[1_500:, "rv_60"] = 999.0
    assert fit_regime_thresholds(changed, train) == expected
    regimes = assign_regimes(frame, expected)
    assert set(regimes[1_500:]) <= {*("unknown",), "down_low_vol", "down_high_vol", "neutral_low_vol",
                                    "neutral_high_vol", "up_low_vol", "up_high_vol"}


def test_regime_direction_combines_five_hour_ema_and_24h_return() -> None:
    frame = pd.DataFrame({
        "ema_gap_15m": [0.0, 0.0, 2.0, -2.0],
        "return_24h": [2.0, -2.0, -2.0, 2.0],
        "rv_60": [2.0, 2.0, 2.0, 2.0],
    })
    thresholds = {
        "ema_gap_15m_q33": -1.0, "ema_gap_15m_q67": 1.0,
        "return_24h_q33": -1.0, "return_24h_q67": 1.0,
        "rv_60_median": 1.0,
    }
    assert assign_regimes(frame, thresholds).tolist() == [
        "up_high_vol", "down_high_vol", "neutral_high_vol", "neutral_high_vol",
    ]


def test_regime_gate_has_no_trade_count_filter() -> None:
    times = pd.date_range("2021-01-01", periods=12, freq="15min", tz="UTC")
    validation_scores = np.arange(12, dtype=float)
    validation_gross = np.full(12, -0.01)
    validation_gross[-1] = 0.02
    regimes = np.full(12, "up_high_vol", dtype=object)
    masks, audit = fold_signal_masks(
        times, validation_scores, validation_gross, regimes,
        np.asarray([99.0]), np.asarray(["up_high_vol"], dtype=object), 15,
    )
    assert set(masks) == {f"q{q * 100:g}" for q in QUANTILES}
    assert audit["q98"]["regimes"]["up_high_vol"]["validation_trades"] == 1
    assert audit["q98"]["regimes"]["up_high_vol"]["allowed"] is True
    assert masks["q98"]["regime_filtered"].tolist() == [True]


def test_external_volatility_gate_is_reported_without_trade_count_filter() -> None:
    times = pd.date_range("2021-01-01", periods=4, freq="15min", tz="UTC")
    scores = np.asarray([0.1, 0.2, 0.3, 0.4])
    regimes = np.full(4, "down_high_vol", dtype=object)
    masks, audit = fold_signal_masks(
        times, scores, np.asarray([0.01, 0.01, 0.01, 0.01]), regimes,
        np.asarray([0.3, 0.4]), np.asarray(["down_high_vol", "down_high_vol"]), 15,
        {"rv15_train_q75": np.asarray([False, False, False, True])},
        {"rv15_train_q75": np.asarray([False, True])},
    )
    assert masks["q98"]["rv15_train_q75"].tolist() == [False, True]
    assert audit["q98"]["external_gates"]["rv15_train_q75"]["validation_trades"] == 1


def test_sequence_batch_never_reads_after_endpoint() -> None:
    values = np.arange(200 * 2, dtype=np.float32).reshape(200, 2)
    before = _sequence_batch(values, [80])
    values[81:] = -999.0
    after = _sequence_batch(values, [80])
    np.testing.assert_array_equal(before, after)
    assert before.shape == (1, 60, 2)


def test_three_model_tuning_smoke() -> None:
    rng = np.random.default_rng(42)
    values = rng.normal(size=(260, len(MODEL_FEATURE_NAMES))).astype(np.float32)
    targets = (values[:, 0] * 2.0 - values[:, 1]).astype(float)
    train = np.arange(59, 180, 3)
    validation = np.arange(180, 240, 3)
    for family in ("catboost", "lightgbm", "gru"):
        model, predictions, report = tune_fold(family, values, targets, train, validation, trials=1)
        assert len(predictions) == len(validation)
        assert np.isfinite(predictions).all()
        assert report["trials"][0]["selected"] is True
        del model
