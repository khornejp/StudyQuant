import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from btcusdt_quant import backtest, data, dataset, live, models
from btcusdt_quant.gru import GRUAdapter, GRU_FEATURE_NAMES, SEQUENCE_LENGTH
from btcusdt_quant import funding_source, metrics_source, premium_index_source
from btcusdt_quant.short_sequence import Fold, HORIZON, _fold_predictions, build_features, independent_short_labels, walk_forward_folds


def test_legacy_mlp_factory_fit_and_round_trip() -> None:
    selection = models.ModelFactory().fit(
        "pytorch_multitask", [[0.0, 1.0], [1.0, 0.0], [0.2, 0.8], [0.8, 0.2]], [0, 1, 0, 1],
        feature_names=["a", "b"], model_params={"epochs": 1, "batch_size": 4}, fallback_allowed=False,
    )
    payload = selection.adapter.as_dict()
    from btcusdt_quant.multitask_nn import MultitaskNNAdapter
    restored = MultitaskNNAdapter.from_dict(payload)
    assert restored.predict_proba([[0.3, 0.7]]) == pytest.approx(selection.adapter.predict_proba([[0.3, 0.7]]))


def test_gru_training_scaler_causality_and_round_trip() -> None:
    rng = np.random.default_rng(42)
    rows = rng.normal(size=(80, len(GRU_FEATURE_NAMES))).astype(np.float32)
    labels = (rows[:, 0] > 0).astype(int)
    rows[70:] = 1_000.0  # held-out future must not influence the train scaler
    adapter = GRUAdapter().fit_rows(rows, labels, endpoints=range(59, 70))
    assert np.max(np.abs(adapter.scaler_mean)) < 1.0

    before = adapter.predict_endpoints(rows, [69])[0]
    changed_future = rows.copy(); changed_future[70:] = -1_000.0
    assert adapter.predict_endpoints(changed_future, [69])[0] == pytest.approx(before)
    restored = GRUAdapter.from_dict(adapter.as_dict())
    assert restored.predict_endpoints(rows, [69])[0] == pytest.approx(before)
    assert 0.0 <= before <= 1.0


def test_gru_abstains_for_59_rows_and_rejects_nonfinite() -> None:
    adapter = GRUAdapter(scaler_mean=np.zeros(28), scaler_std=np.ones(28))
    row = dict.fromkeys(GRU_FEATURE_NAMES, 0.0)
    for _ in range(SEQUENCE_LENGTH - 1):
        assert adapter.probability(row) == 0.5
        assert not adapter.ready
    probability = adapter.probability(row)
    assert adapter.ready and 0.0 <= probability <= 1.0
    bad = dict(row); bad[GRU_FEATURE_NAMES[0]] = float("nan")
    with pytest.raises(ValueError, match="NaN or infinity"):
        adapter.probability(bad)


class _TrackingGRU:
    model_family = "pytorch_gru"
    train_target = "short_profitability"

    def __init__(self) -> None:
        self.observed = 0

    @property
    def ready(self) -> bool:
        return self.observed >= SEQUENCE_LENGTH

    def reset_history(self) -> None:
        self.observed = 0

    def probability(self, values) -> float:
        self.observed += 1
        return 0.99 if self.ready else 0.5


def _candles(count: int):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [data.Candle(start + timedelta(minutes=i), 100.0, 100.1, 99.9, 100.0, 1.0, 100.0, 1, 0.5, 50.0) for i in range(count)]


def test_gated_bars_advance_gru_history_but_cannot_enter() -> None:
    candles = _candles(70)
    feature_rows = [dataset.FeatureRow(i, candle.open_time, {"rv_60": 0.0}, 0, False, False) for i, candle in enumerate(candles)]
    model = _TrackingGRU()
    with mock.patch("btcusdt_quant.backtest.dataset.build_feature_rows", return_value=feature_rows):
        result = backtest.run_backtest(
            candles, model=model, execution_side="short", vol_gate_feature="rv_60", vol_gate_min=1.0,
            exec_tp_pct=0.006, exec_sl_pct=0.012, label_horizon=45, allow_barrier_mismatch=True,
        )
    assert model.observed == len(candles)
    assert result.trade_count == 0


def test_live_loader_refuses_gru_but_backtest_loader_accepts(tmp_path: Path) -> None:
    adapter = GRUAdapter(scaler_mean=np.zeros(28), scaler_std=np.ones(28))
    path = tmp_path / "model.json"
    path.write_text(json.dumps(adapter.as_dict()), encoding="utf-8")
    with pytest.raises(ValueError, match="explicitly refused"):
        live.load_model_artifact(path, strict=True)
    loaded = backtest.load_model_artifact(path, strict=True)
    assert loaded is not None and loaded.model_family == "pytorch_gru"


def test_short_label_oracle_and_walk_forward_contract() -> None:
    times = pd.date_range("2020-01-01", periods=HORIZON + 2, freq="min", tz="UTC")
    close = np.full(len(times), 100.0); low = np.full(len(times), 100.0); high = np.full(len(times), 100.0)
    low[1] = 99.0  # short TP before SL
    frame = pd.DataFrame({"open_time": times, "open": close, "high": high, "low": low, "close": close})
    labels, payoff, reasons = independent_short_labels(frame)
    assert labels[0] == 1 and payoff[0] == pytest.approx(0.006) and reasons[0] == "short_tp_first"
    folds = walk_forward_folds()
    assert {fold.test_start.year for fold in folds} == {2021, 2022, 2023, 2024, 2025}
    assert all(fold.validation_start - fold.train_end == pd.Timedelta(minutes=45) for fold in folds)
    assert all(fold.test_start - fold.validation_end == pd.Timedelta(minutes=45) for fold in folds)


def test_feature_builder_uses_sources_not_a_feature_cache(tmp_path: Path) -> None:
    times = pd.date_range("2021-01-01", periods=120, freq="min", tz="UTC")
    source = pd.DataFrame({
        "open_time": times, "open": 100.0, "high": 100.2, "low": 99.8,
        "close": 100.0 + np.arange(len(times)) * 0.01, "volume": 10.0,
        "quote_volume": 1_000.0, "number_of_trades": 10,
        "taker_buy_base_volume": 5.0, "taker_buy_quote_volume": 500.0,
    })
    source["open_time"] = source["open_time"].astype("datetime64[us, UTC]")
    path = tmp_path / "candles.parquet"; source.to_parquet(path)
    funding = [funding_source.FundingRow(times[0].to_pydatetime(), 0.0001)]
    premium = [premium_index_source.PremiumIndexRow(
        times[0].to_pydatetime(), times[0].to_pydatetime(), 0.0002, 0.0002, 0.0002, 0.0002,
    )]
    metric_rows = [metrics_source.MetricsRow(
        times[index].to_pydatetime(), {
            "sum_open_interest": 100.0 + index, "sum_open_interest_value": 1_000.0 + index,
            "count_long_short_ratio": 1.0 + index / 1000.0,
            "sum_taker_long_short_vol_ratio": 1.1 + index / 1000.0,
        },
    ) for index in range(0, len(times), 5)]
    with mock.patch("btcusdt_quant.short_sequence.funding_source.load_funding_dir", return_value=funding), \
         mock.patch("btcusdt_quant.short_sequence.premium_index_source.load_premium_index_dir", return_value=premium), \
         mock.patch("btcusdt_quant.short_sequence.metrics_source.load_metrics_dir", return_value=metric_rows):
        built = build_features(path, tmp_path, tmp_path, tmp_path)
    assert list(built.loc[:, list(GRU_FEATURE_NAMES)].columns) == list(GRU_FEATURE_NAMES)
    assert np.isfinite(built.loc[60:, list(GRU_FEATURE_NAMES)].to_numpy()).all()


def test_lightgbm_fold_dispatch_does_not_fall_through_to_gru() -> None:
    class FakeLightGBM:
        def __init__(self, feature_names, model_params=None):
            assert tuple(feature_names) == GRU_FEATURE_NAMES
            assert model_params is None

        def fit(self, rows, labels):
            return self

        def predict_proba(self, rows):
            return [0.75] * len(rows)

    frame = pd.DataFrame({name: np.zeros(80) for name in GRU_FEATURE_NAMES})
    frame["open_time"] = pd.date_range("2021-01-01", periods=80, freq="min", tz="UTC")
    fold = Fold(0, *(pd.Timestamp("2021-01-01", tz="UTC") for _ in range(6)))
    partitions = [np.arange(40), np.arange(40, 60), np.arange(60, 80)]
    with mock.patch("btcusdt_quant.short_sequence.models.LightGBMAdapter", FakeLightGBM), \
         mock.patch("btcusdt_quant.short_sequence._indices", side_effect=partitions):
        times, probabilities, _, _, reports = _fold_predictions(
            frame, np.zeros(80, dtype=int), np.zeros(80), [fold], "lightgbm",
        )
    assert len(times) == len(probabilities) == 20
    assert reports[0]["q75"] == pytest.approx(0.75)


def test_tuned_lightgbm_uses_validation_only_for_selection() -> None:
    frame = pd.DataFrame({name: np.zeros(80) for name in GRU_FEATURE_NAMES})
    frame["open_time"] = pd.date_range("2021-01-01", periods=80, freq="min", tz="UTC")
    fold = Fold(0, *(pd.Timestamp("2021-01-01", tz="UTC") for _ in range(6)))
    partitions = [np.arange(40), np.arange(40, 60), np.arange(60, 80)]
    fitted = {}

    class FakeModel:
        def predict_proba(self, rows):
            return [0.75] * len(rows)

    def fake_tune(train_x, train_y, validation_x, validation_y):
        assert len(train_x) == len(train_y) == 40
        assert len(validation_x) == len(validation_y) == 20
        return {"num_leaves": 31}, {"objective": "validation_pr_auc"}

    def fake_fit(features, labels, params):
        fitted.update(rows=len(features), params=params)
        return FakeModel()

    with mock.patch("btcusdt_quant.short_sequence._indices", side_effect=partitions), \
         mock.patch("btcusdt_quant.short_sequence._tune_lightgbm", side_effect=fake_tune), \
         mock.patch("btcusdt_quant.short_sequence._fit_lightgbm", side_effect=fake_fit):
        _, _, _, _, reports = _fold_predictions(
            frame, np.zeros(80, dtype=int), np.zeros(80), [fold], "lightgbm_tuned",
        )
    assert fitted == {"rows": 40, "params": {"num_leaves": 31}}
    assert reports[0]["tuning"]["objective"] == "validation_pr_auc"
