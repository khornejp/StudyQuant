"""Tests for stacking ensemble and multitarget labels."""
import unittest
from datetime import timedelta

from btcusdt_quant import data, dataset


class MetaModelTests(unittest.TestCase):
    def test_meta_model_catboost(self) -> None:
        from btcusdt_quant.ensemble import _fit_meta_model
        import numpy as np
        X = np.array([[0.9, 0.8], [0.1, 0.2], [0.8, 0.9], [0.2, 0.1]])
        y = np.array([1, 0, 1, 0])
        model = _fit_meta_model(X, y, "catboost")
        self.assertIsNotNone(model)
        prob = model.predict_proba(X[:1])[0]
        self.assertGreaterEqual(prob, 0.0)
        self.assertLessEqual(prob, 1.0)



class MultitargetLabelTests(unittest.TestCase):
    def test_labeled_row_has_targets_and_reasons(self) -> None:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        candles = [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0,
                high=101.0 + index * 0.5,
                low=99.0,
                close=100.0 + index * 0.3,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(30)
        ]
        feature_rows = dataset.build_feature_rows(candles)
        labeled_rows = dataset.attach_labels(feature_rows, candles, horizon=15, label_threshold=0.0002, tp_pct=0.01, sl_pct=0.005, include_warmup=True)
        self.assertGreater(len(labeled_rows), 0)
        row = labeled_rows[0]
        self.assertIn("direction", row.targets, "direction target must exist")
        self.assertIn("profitability", row.targets, "profitability target must exist")
        self.assertIn("direction", row.target_reasons, "direction reason must exist")
        self.assertIn("profitability", row.target_reasons, "profitability reason must exist")

    def test_direction_label_matches_future_return(self) -> None:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        candles = [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0 + index * 0.5,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(30)
        ]
        feature_rows = dataset.build_feature_rows(candles)
        labeled_rows = dataset.attach_labels(feature_rows, candles, horizon=5, label_threshold=0.0002, tp_pct=0.50, sl_pct=0.50, include_warmup=True)
        self.assertGreater(len(labeled_rows), 0)
        row = labeled_rows[0]
        # future close at index 5 = 102.5, current close = 100.0
        self.assertEqual(row.targets["direction"], 1, "rising price should have direction=1")
        self.assertEqual(row.label, 1, "backward-compatible label should be direction")

    def test_profitability_label_tp_first(self) -> None:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        candles = [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0,
                high=100.0 + index * 0.1,
                low=99.0,
                close=100.0 + index * 0.05,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(30)
        ]
        feature_rows = dataset.build_feature_rows(candles)
        labeled_rows = dataset.attach_labels(feature_rows, candles, horizon=10, label_threshold=0.0002, tp_pct=0.001, sl_pct=0.0005, include_warmup=True)
        self.assertGreater(len(labeled_rows), 0)
        # At least some rows should have tp_first or sl_first profitability
        reasons = {row.target_reasons["profitability"] for row in labeled_rows}
        self.assertTrue(
            reasons.intersection({"tp_first", "sl_first", "timeout_no_tp"}),
            f"profitability reasons should include tp/sl/timeout, got {reasons}",
        )

    def test_backward_compatible_label(self) -> None:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        candles = [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(30)
        ]
        feature_rows = dataset.build_feature_rows(candles)
        labeled_rows = dataset.attach_labels(feature_rows, candles, horizon=5, label_threshold=0.0002, tp_pct=0.50, sl_pct=0.50, include_warmup=True)
        self.assertGreater(len(labeled_rows), 0)
        row = labeled_rows[0]
        self.assertEqual(row.label, row.targets["profitability"], "backward-compatible label must match profitability target")
        self.assertEqual(row.label_reason, row.target_reasons["profitability"], "backward-compatible label_reason must match profitability reason")


if __name__ == "__main__":
    unittest.main()
