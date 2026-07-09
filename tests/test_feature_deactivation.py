"""Tests for deactivation of scale-dependent (absolute-price/quote-USD) features.

Nine features were moved to scaffold_status="disabled_scale_dependent":
rolling_vwap_20/60, range_high/low/mid_20 (raw price levels passed through
the clipper's "price" class), macd_line/signal/hist (dollar-scale, saturating
the +-100 ratio clip only in high-price regimes -> era leak), and
quote_volume_per_trade (quote-USD per trade, near-always clip-saturated).

Invariants:
1. None of the nine appears in active_feature_names or in built feature rows.
2. Their scale-free counterparts remain active AND still compute correctly,
   because the disabled series are still computed internally as their inputs.
3. The registry still documents all nine (formula registry keeps every
   definition regardless of status).
"""
from __future__ import annotations

import unittest
from datetime import timedelta

from btcusdt_quant import data, dataset, feature_registry

DISABLED = {
    "rolling_vwap_20", "rolling_vwap_60",
    "range_high_20", "range_low_20", "range_mid_20",
    "macd_line", "macd_signal", "macd_hist",
    "quote_volume_per_trade",
}
KEPT_COUNTERPARTS = {
    "vwap_deviation_zscore", "price_vs_rolling_vwap_20", "price_vs_rolling_vwap_60",
    "range_position_20", "distance_to_range_high", "distance_to_range_low",
    "ema_12_26_spread", "volume_per_trade",
}


def _candles(n: int = 80) -> list[data.Candle]:
    base = data.utc_minute(2026, 1, 1, 0, 0)
    out = []
    for i in range(n):
        high, low = (110.0, 90.0) if i < 40 else (105.0, 95.0)
        out.append(data.Candle(
            open_time=base + timedelta(minutes=i), open=100.0, high=high, low=low,
            close=100.0 + (i % 3), volume=10.0 + (i % 5), quote_volume=1000.0,
            number_of_trades=100, taker_buy_base_volume=5.0, taker_buy_quote_volume=500.0,
        ))
    return out


class ScaleDependentDeactivationTests(unittest.TestCase):
    def test_disabled_features_not_active(self) -> None:
        active = set(feature_registry.active_feature_names())
        self.assertEqual(DISABLED & active, set())

    def test_counterparts_still_active(self) -> None:
        active = set(feature_registry.active_feature_names())
        self.assertEqual(KEPT_COUNTERPARTS - active, set())

    def test_registry_still_documents_disabled_definitions(self) -> None:
        registry = dataset.feature_formula_registry()
        names = {str(f["feature_name"]) for f in registry["features"]}
        self.assertEqual(DISABLED - names, set())
        by_name = {str(f["feature_name"]): f for f in registry["features"]}
        for name in DISABLED:
            self.assertEqual(by_name[name]["scaffold_status"], "disabled_scale_dependent")

    def test_built_rows_exclude_disabled_and_compute_counterparts(self) -> None:
        rows = dataset.build_feature_rows(_candles(), _parallel=False)
        row = rows[45]  # past every relevant warmup (vwap zscore needs 39)
        for name in DISABLED:
            self.assertNotIn(name, row.features)
            with self.assertRaises(KeyError):
                _ = row.features[name]
        for name in KEPT_COUNTERPARTS:
            self.assertIn(name, row.features)
        # Derived relative features still compute from the internally-kept
        # disabled series: at bar 45 the 20-bar window spans bars 26..45,
        # which still contains the wide-range bars (i < 40): range = [90,110],
        # close = 100 + (45 % 3) = 100 -> position (100-90)/(110-90) = 0.5.
        self.assertAlmostEqual(float(row.features["range_position_20"]), 0.5, places=5)
        self.assertAlmostEqual(
            float(row.features["distance_to_range_high"]), 100.0 / 110.0 - 1.0, places=5
        )

    def test_feature_vector_width_matches_active_registry(self) -> None:
        rows = dataset.build_feature_rows(_candles(30), _parallel=False)
        self.assertEqual(len(dict(rows[0].features)), len(feature_registry.active_feature_names()))

    def test_registry_metadata_active_names_tuple_equal_feature_names(self) -> None:
        # The artifact-facing metadata (feature_formula_registry()["active_
        # feature_names"], persisted as feature_formula_registry.json) must be
        # TUPLE-equal (same names, same order) to the model-facing
        # dataset.FEATURE_NAMES. v11 shipped with the metadata path still
        # filtering only "pending_data_source", reporting 189 active names
        # while the model trained on 180.
        registry = dataset.feature_formula_registry()
        self.assertEqual(tuple(registry["active_feature_names"]), tuple(dataset.FEATURE_NAMES))

    def test_registry_metadata_excludes_scale_disabled(self) -> None:
        registry = dataset.feature_formula_registry()
        active = set(registry["active_feature_names"])
        self.assertEqual(DISABLED & active, set())
        # pending F11 depth features must stay excluded too (the shared
        # predicate covers both inactive statuses).
        self.assertNotIn("spread_bps", active)

    def test_registry_from_feature_rows_uses_shared_predicate(self) -> None:
        # Row-dict path (external/artifact rows) must honor every inactive
        # status and treat a MISSING status as active ("implemented").
        rows = [
            {"feature_name": "keep_me"},
            {"feature_name": "keep_me_too", "scaffold_status": "implemented"},
            {"feature_name": "drop_pending", "scaffold_status": "pending_data_source"},
            {"feature_name": "drop_scale", "scaffold_status": "disabled_scale_dependent"},
        ]
        registry = feature_registry.registry_from_feature_rows(rows)
        self.assertEqual(list(registry["active_feature_names"]), ["keep_me", "keep_me_too"])


if __name__ == "__main__":
    unittest.main()
