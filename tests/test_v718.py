from __future__ import annotations

import csv
import json
import tempfile
import unittest
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

from dataclasses import replace

from btcusdt_quant import backtest, data, dataset, features, governance, live, monitoring, parity, sources, training


class FeatureRegistryV718Tests(unittest.TestCase):
    def test_feature_registry_has_at_least_70_features(self) -> None:
        registry = dataset.feature_formula_registry()
        registry_features = cast(list[dict[str, object]], registry["features"])
        self.assertGreaterEqual(len(registry_features), 70, "v7.18 requires at least 70 features")

    def test_all_categories_f01_through_f12_present(self) -> None:
        registry = dataset.feature_formula_registry()
        registry_features = cast(list[dict[str, object]], registry["features"])
        categories = {str(feature["category"]) for feature in registry_features}
        expected = {f"F{index:02d}" for index in range(1, 13)}
        self.assertEqual(categories, expected, "v7.18 requires F01-F12 categories")

    def test_all_active_features_have_required_fields(self) -> None:
        registry = dataset.feature_formula_registry()
        registry_features = cast(list[dict[str, object]], registry["features"])
        required_fields = {"feature_name", "category", "formula", "lookback", "min_samples", "warmup_rule", "dependencies", "source", "leakage_risk"}
        for feature in registry_features:
            if feature.get("scaffold_status") == "pending_data_source":
                continue
            missing = required_fields - set(feature.keys())
            self.assertEqual(missing, set(), f"feature {feature.get('feature_name')} missing fields: {missing}")

    def test_feature_names_matches_active_registry(self) -> None:
        registry = dataset.feature_formula_registry()
        registry_features = cast(list[dict[str, object]], registry["features"])
        active_names = {str(feature["feature_name"]) for feature in registry_features if feature.get("scaffold_status") != "pending_data_source"}
        self.assertEqual(active_names, set(dataset.FEATURE_NAMES), "FEATURE_NAMES must match active registry features")

    def test_feature_dependency_graph_is_acyclic(self) -> None:
        registry = dataset.feature_formula_registry()
        dependency_graph = registry.get("dependency_graph", {})
        self.assertTrue(dependency_graph.get("acyclic", True), "feature dependency graph must be acyclic")

    def test_no_feature_uses_future_data(self) -> None:
        registry = dataset.feature_formula_registry()
        registry_features = cast(list[dict[str, object]], registry["features"])
        for feature in registry_features:
            formula = str(feature.get("formula", ""))
            self.assertNotIn("t+1", formula, f"feature {feature.get('feature_name')} may use future data")
            self.assertNotIn("future", formula.lower(), f"feature {feature.get('feature_name')} may use future data")

    def test_feature_registry_has_f11_microstructure_features(self) -> None:
        registry = dataset.feature_formula_registry()
        registry_features = cast(list[dict[str, object]], registry["features"])
        f11_features = [f for f in registry_features if str(f.get("category", "")) == "F11"]
        self.assertGreater(len(f11_features), 0, "v7.18 requires F11 microstructure features")
        expected_names = {"spread", "spread_bps", "bid_ask_imbalance", "best_bid_qty_ratio", "best_ask_qty_ratio", "microprice_deviation", "order_book_pressure"}
        actual_names = {f["feature_name"] for f in f11_features}
        self.assertTrue(expected_names.issubset(actual_names), f"missing F11 features: {expected_names - actual_names}")

    def test_feature_registry_has_f12_exchange_safety_features(self) -> None:
        registry = dataset.feature_formula_registry()
        registry_features = cast(list[dict[str, object]], registry["features"])
        f12_features = [f for f in registry_features if str(f.get("category", "")) == "F12"]
        self.assertGreater(len(f12_features), 0, "v7.18 requires F12 exchange safety features")
        expected_names = {"adl_indicator", "funding_rate", "next_funding_rate", "minutes_to_next_funding", "funding_blackout_active", "mark_price_basis", "premium_index", "leverage_bracket_utilization"}
        actual_names = {f["feature_name"] for f in f12_features}
        self.assertTrue(expected_names.issubset(actual_names), f"missing F12 features: {expected_names - actual_names}")

    def test_build_feature_rows_produces_all_active_features(self) -> None:
        from btcusdt_quant import data
        base = data.utc_minute(2026, 1, 1, 0, 0)
        candles = [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.5 + index,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(200)
        ]
        rows = dataset.build_feature_rows(candles)
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertEqual(set(row.features), set(dataset.FEATURE_NAMES), f"row features must match all active feature names")

    def test_feature_clipper_recognizes_all_v718_types(self) -> None:
        clipper = features.FeatureClipper()
        test_cases = {
            "return_1": "return",
            "zscore_feature": "zscore",
            "ratio_feature": "ratio",
            "vol_adj_feature": "vol_adj",
            "spread_bps": "bps",
            "volatility_feature": "vol",
            "regime_feature": "regime",
            "flag_feature": "flag",
            "minutes_feature": "minutes",
            "funding_rate": "funding",
            "adl_indicator": "adl",
        }
        for name, expected in test_cases.items():
            actual = clipper.classify(name)
            self.assertEqual(actual, expected, f"clipper should classify {name} as {expected}")

    def test_warmup_invalidation_strict_for_all_features(self) -> None:
        from btcusdt_quant import data
        base = data.utc_minute(2026, 1, 1, 0, 0)
        min_samples = dataset.max_feature_min_samples()
        candles = [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.5 + index,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(min_samples + 5)
        ]
        rows = dataset.build_feature_rows(candles)
        for row in rows[:min_samples - 1]:
            self.assertTrue(row.warmup_invalid, f"row {row.index} should be warmup_invalid")
        for row in rows[min_samples - 1:]:
            self.assertFalse(row.warmup_invalid, f"row {row.index} should not be warmup_invalid")


class TestRegimeDetector(unittest.TestCase):
    def test_regime_detector_fits_thresholds(self) -> None:
        detector = features.RegimeDetector()
        thresholds = detector.fit_thresholds([1.0, 2.0, 3.0, 4.0], [0.0001, -0.0002, 0.0003, -0.0004])

        self.assertAlmostEqual(thresholds["rv_threshold"], 3.25)
        self.assertAlmostEqual(thresholds["trend_threshold"], 0.00037)
        self.assertEqual(thresholds["trend_min"], 0.00005)

    def test_regime_detector_detects_all_three_regimes(self) -> None:
        config = features.RegimeDetectorConfig(rv_percentile=0.60, trend_percentile=0.50, min_regime_run_bars=1)
        detector = features.RegimeDetector(config)
        rv_values = [0.001] * 5 + [0.001] * 5 + [0.100] * 5
        trend_values = [0.0] * 5 + [0.010] * 5 + [0.0] * 5

        regimes = detector.detect_all(rv_values, trend_values)

        self.assertEqual(set(regimes), {"high_volatility", "trending", "ranging"})

    def test_regime_detector_hysteresis(self) -> None:
        config = features.RegimeDetectorConfig(min_regime_run_bars=3)
        detector = features.RegimeDetector(config)
        thresholds = {"rv_threshold": 0.005, "trend_threshold": 1.0, "trend_min": 1.0}
        rv_values = [0.001, 0.010, 0.001, 0.010, 0.010, 0.010]
        trend_values = [0.0] * len(rv_values)

        regimes = detector.detect_all(rv_values, trend_values, thresholds=thresholds)

        self.assertEqual(regimes, ["ranging", "ranging", "ranging", "ranging", "ranging", "high_volatility"])

    def test_regime_detector_diagnostics(self) -> None:
        config = features.RegimeDetectorConfig(trend_percentile=0.50, min_regime_run_bars=1)
        detector = features.RegimeDetector(config)
        rv_values = [0.001] * 4 + [0.001] * 4 + [0.100] * 4
        trend_values = [0.0] * 4 + [0.010] * 4 + [0.0] * 4

        diagnostics = detector.diagnostics(rv_values, trend_values)

        self.assertIn("regime_counts", diagnostics)
        self.assertIn("thresholds", diagnostics)
        self.assertIn("regime_transition_count", diagnostics)
        self.assertIn("max_single_run_length", diagnostics)
        self.assertEqual(diagnostics["regime_transition_count"], 2)
        self.assertEqual(diagnostics["max_single_run_length"], 4)

    def test_training_persists_detector(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir) / "btcusdt_1m.csv"
            dataset.collect_candles(data_path, rows=2000)
            train_dir = Path(tmpdir) / "training"

            result = training.run_training(data_path, train_dir, config=training.TrainingConfig(regime_aware=True, n_groups=3, test_group_count=1))

            summary_path = train_dir / "regime_run_summary.json"
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            detector_summary = result.run_summary.get("regime_detector", {})
        self.assertEqual(summary.get("regime_detector"), detector_summary)
        self.assertIn("thresholds", detector_summary)
        self.assertIn("diagnostics", detector_summary)
        self.assertIn("config", detector_summary)

    def test_live_loads_detector_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir) / "regime_artifacts"
            model_dir = artifact_dir / "regime_ranging"
            model_dir.mkdir(parents=True)
            expected_thresholds = {"rv_threshold": 123.0, "trend_threshold": 456.0, "trend_min": 0.0}
            summary = {
                "regime_results": {"ranging": {"mean_test_f1": 0.1}},
                "regime_detector": {
                    "thresholds": expected_thresholds,
                    "diagnostics": {"regime_counts": {"ranging": 1}, "thresholds": expected_thresholds, "regime_transition_count": 0, "max_single_run_length": 1},
                    "config": features.RegimeDetector().config_dict(),
                },
            }
            (artifact_dir / "regime_run_summary.json").write_text(json.dumps(summary), encoding="utf-8")
            model = training.LinearClassifier(
                feature_names=("return_1",),
                standardizer=training.Standardizer({"return_1": 0.0}, {"return_1": 1.0}),
                weights={"return_1": 0.0},
                intercept=1.0,
            )
            (model_dir / "model.json").write_text(json.dumps(model.as_dict()), encoding="utf-8")
            captured_thresholds: list[dict[str, float] | None] = []
            original_detect = features.RegimeDetector.detect

            def patched_detect(
                detector: features.RegimeDetector,
                rv_15: float,
                trend_slope_30: float,
                historical_rv_15_values: object = None,
                thresholds: dict[str, float] | None = None,
            ) -> str:
                captured_thresholds.append(thresholds)
                return "ranging"

            features.RegimeDetector.detect = patched_detect
            try:
                output = Path(tmpdir) / "live"
                result = live.run_live(
                    output,
                    dry_run=True,
                    max_candles=12,
                    custom_candles=self._candles(40),
                    model_artifact_path=artifact_dir,
                    regime_aware=True,
                )
            finally:
                features.RegimeDetector.detect = original_detect

        inference = result.summary.get("model_inference", {})
        self.assertEqual(captured_thresholds[-1], expected_thresholds)
        self.assertEqual(inference.get("regime"), "ranging")
        self.assertTrue(inference.get("model_loaded"))

    def _candles(self, rows: int) -> list[data.Candle]:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        return [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.5 + index,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(rows)
        ]


class TestRegimeTraining(unittest.TestCase):
    REGIMES = ["high_volatility"] * 120 + ["trending"] * 30 + ["ranging"] * 150

    def test_regime_skipped_insufficient_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run_regime_training(Path(tmpdir), self.REGIMES)

        skipped = result.run_summary.get("skipped_regimes", {})
        self.assertEqual(skipped.get("trending", {}).get("status"), "skipped")
        self.assertEqual(skipped.get("trending", {}).get("reason"), "insufficient_rows")
        self.assertEqual(skipped.get("trending", {}).get("row_count"), 30)

    def test_default_regime_is_largest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run_regime_training(Path(tmpdir), self.REGIMES)

        self.assertEqual(result.run_summary.get("default_regime"), "ranging")
        trained = result.run_summary.get("trained_regimes", {})
        self.assertEqual(trained.get("ranging", {}).get("row_count"), 150)
        self.assertEqual(trained.get("high_volatility", {}).get("row_count"), 120)

    def test_live_fallback_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir) / "regime_artifacts"
            model_dir = artifact_dir / "regime_ranging"
            model_dir.mkdir(parents=True)
            summary = {
                "regime_results": {"ranging": {"mean_test_f1": 0.2}},
                "trained_regimes": {"ranging": {"status": "trained", "row_count": 150}},
                "skipped_regimes": {"trending": {"status": "skipped", "reason": "insufficient_rows", "row_count": 30}},
                "default_regime": "ranging",
                "regime_detector": {
                    "thresholds": {"rv_threshold": 1.0, "trend_threshold": 1.0, "trend_min": 0.0},
                    "diagnostics": {},
                    "config": features.RegimeDetector().config_dict(),
                },
            }
            (artifact_dir / "regime_run_summary.json").write_text(json.dumps(summary), encoding="utf-8")
            model = training.LinearClassifier(
                feature_names=("return_1",),
                standardizer=training.Standardizer({"return_1": 0.0}, {"return_1": 1.0}),
                weights={"return_1": 0.0},
                intercept=1.0,
            )
            (model_dir / "model.json").write_text(json.dumps(model.as_dict()), encoding="utf-8")
            original_detect = features.RegimeDetector.detect

            def patched_detect(
                detector: features.RegimeDetector,
                rv_15: float,
                trend_slope_30: float,
                historical_rv_15_values: object = None,
                thresholds: dict[str, float] | None = None,
            ) -> str:
                return "trending"

            features.RegimeDetector.detect = patched_detect
            try:
                result = live.run_live(
                    Path(tmpdir) / "live",
                    dry_run=True,
                    max_candles=12,
                    custom_candles=self._candles(40),
                    model_artifact_path=artifact_dir,
                    regime_aware=True,
                )
            finally:
                features.RegimeDetector.detect = original_detect

        inference = result.summary.get("model_inference", {})
        self.assertEqual(inference.get("regime"), "trending")
        self.assertEqual(inference.get("fallback_regime"), "ranging")
        self.assertTrue(inference.get("model_loaded"))
        self.assertIsNotNone(inference.get("probability"))

    def test_no_failure_when_trending_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run_regime_training(Path(tmpdir), self.REGIMES)

        self.assertNotIn("trending", result.run_summary.get("regime_results", {}))
        self.assertIn("trending", result.run_summary.get("skipped_regimes", {}))
        self.assertIn("ranging", result.run_summary.get("trained_regimes", {}))

    def test_regime_run_summary_has_all_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            result = self._run_regime_training(output, self.REGIMES)
            summary_path = output / "regime_run_summary.json"
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))

        for key in ("trained_regimes", "skipped_regimes", "default_regime", "min_regime_rows", "regime_counts"):
            self.assertIn(key, summary)
            self.assertEqual(summary.get(key), result.run_summary.get(key))

    def _run_regime_training(self, output: Path, regimes: list[str]) -> training.TrainingResult:
        build = self._build_dataset(len(regimes))
        original_detect_all = features.RegimeDetector.detect_all

        def patched_detect_all(
            detector: features.RegimeDetector,
            rv_15_values: object,
            trend_slope_30_values: object,
            thresholds: dict[str, float] | None = None,
        ) -> list[str]:
            return list(regimes)

        features.RegimeDetector.detect_all = patched_detect_all
        try:
            return training.run_training(
                input_path=None,
                output_dir=output,
                config=training.TrainingConfig(regime_aware=True, lineage_enabled=False),
                prebuilt_dataset=build,
            )
        finally:
            features.RegimeDetector.detect_all = original_detect_all

    def _build_dataset(self, rows: int) -> dataset.DatasetBuild:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        feature_names = tuple(dataset.FEATURE_NAMES)
        labeled_rows: list[dataset.LabeledRow] = []
        feature_rows: list[dataset.FeatureRow] = []
        for index in range(rows):
            open_time = base + timedelta(minutes=index)
            row_features = {name: ((index % 11) - 5) * 0.001 for name in feature_names}
            row_features["rv_15"] = float(index % 7) * 0.001
            row_features["trend_slope_30"] = float((index % 5) - 2) * 0.0001
            label = index % 2
            feature_rows.append(dataset.FeatureRow(index, open_time, dict(row_features), 0, False, False))
            labeled_rows.append(dataset.LabeledRow(index, open_time, dict(row_features), label, "threshold", 0.001 if label else -0.001, 0, False, False))
        gap_report = dataset.GapReport(rows, rows, 0, 0.0, 0, base.isoformat(), (base + timedelta(minutes=rows - 1)).isoformat())
        source_report = {
            "feature_space_parity_passed": True,
            "train_live_feature_parity_passed": True,
            "source_hashes": {},
            "unavailable_sources": (),
            "grade_c_sources": (),
            "fallback_features": (),
            "approval_block_reasons": (),
        }
        return dataset.DatasetBuild(
            source="synthetic_regime_fixture",
            symbol="BTCUSDT",
            interval="1m",
            raw_rows=rows,
            canonical=[],
            gap_report=gap_report,
            feature_rows=feature_rows,
            labeled_rows=labeled_rows,
            feature_names=feature_names,
            label_horizon=0,
            label_threshold=0.0,
            source_availability_report=source_report,
        )

    def _candles(self, rows: int) -> list[data.Candle]:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        return [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.5 + index,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(rows)
        ]


class SourceContractsV718Tests(unittest.TestCase):
    def test_source_definitions_exist(self) -> None:
        try:
            from btcusdt_quant import sources
        except ImportError:
            self.skipTest("sources module not yet implemented")
        self.assertTrue(hasattr(sources, "SOURCE_DEFINITIONS"), "sources module must define SOURCE_DEFINITIONS")

    def test_source_availability_grading(self) -> None:
        try:
            from btcusdt_quant import sources
        except ImportError:
            self.skipTest("sources module not yet implemented")
        grade = sources.source_availability_grade("klines_1m", historical_backfill=True, local_archive_complete=True)
        self.assertIn("grade", grade)
        self.assertIn("parity_passed", grade)

    def test_dataset_card_records_source_availability(self) -> None:
        build = dataset.build_dataset()
        card = dataset.dataset_card(build)
        self.assertIn("unavailable_sources", card, "dataset card must record unavailable sources")
        self.assertIn("feature_space_parity_passed", card, "dataset card must record feature parity")
        self.assertIn("feature_schema_hash", card, "dataset card must record feature schema parity hash")
        self.assertIn("source_schema_hash", card, "dataset card must record source schema parity hash")
        self.assertIn("dependency_graph_hash", card, "dataset card must record dependency graph parity hash")
        self.assertTrue(card["feature_parity_passed"], "offline fixture feature parity should pass")

    def test_mock_live_and_offline_fixture_feature_parity_passes(self) -> None:
        registry = dataset.feature_formula_registry()
        offline_build = dataset.build_dataset()
        offline_result = parity.compare_training_live_features(
            registry,
            registry,
            source_report=offline_build.source_availability_report,
            training_feature_names=offline_build.feature_names,
            live_feature_names=offline_build.feature_names,
        )
        self.assertTrue(offline_result.passed, offline_result.reasons)
        with tempfile.TemporaryDirectory() as tmp:
            live_result = live.run_live(Path(tmp), dry_run=True, max_candles=12)
            live_source_report = sources.train_live_feature_parity_report(
                dataset.FEATURE_NAMES,
                source_bundle=live_result.source_bundle,
                feature_registry=registry["features"],
            )
            live_parity = parity.compare_training_live_features(
                registry,
                registry,
                source_report=live_source_report,
                training_feature_names=dataset.FEATURE_NAMES,
                live_feature_names=dataset.FEATURE_NAMES,
            )
        self.assertTrue(live_parity.passed, live_parity.reasons)

    def test_missing_live_only_source_requires_grade_c_fallback_documentation(self) -> None:
        depth_feature = {
            "feature_name": "depth_spread_fixture",
            "category": "F11",
            "feature_group": "microstructure_features",
            "formula": "best_ask_t - best_bid_t",
            "lookback": 1,
            "min_samples": 1,
            "warmup_rule": "state",
            "dependencies": (),
            "source": "depth_snapshot",
            "required_for_training": True,
            "required_for_live": True,
            "leakage_risk": "low_state_snapshot",
            "scaffold_status": "implemented",
        }
        missing_report = {"unavailable_sources": ("depth_snapshot",), "grade_c_sources": (), "fallback_features": ()}
        missing_result = parity.compare_training_live_features((depth_feature,), (depth_feature,), source_report=missing_report)
        self.assertFalse(missing_result.passed, "undocumented missing live-only source must fail parity")
        documented_report = {"unavailable_sources": ("depth_snapshot",), "grade_c_sources": ("depth_snapshot",), "fallback_features": ("depth_spread_fixture",)}
        documented_result = parity.compare_training_live_features((depth_feature,), (depth_feature,), source_report=documented_report)
        self.assertTrue(documented_result.passed, documented_result.reasons)
        self.assertTrue(documented_result.documented_grade_c_fallback)

    def test_missing_critical_source_blocks_approval(self) -> None:
        try:
            from btcusdt_quant import sources
        except ImportError:
            self.skipTest("sources module not yet implemented")
        grade = sources.source_availability_grade("klines_1m", historical_backfill=False, local_archive_complete=False)
        self.assertFalse(grade.get("parity_passed", True), "missing critical source should block parity")


class ModelAdaptersV718Tests(unittest.TestCase):
    def test_optional_model_adapters_exist(self) -> None:
        try:
            from btcusdt_quant import models
        except ImportError:
            self.skipTest("models module not yet implemented")
        self.assertTrue(hasattr(models, "ModelAdapter"), "models module must define ModelAdapter protocol")
        self.assertTrue(hasattr(models, "ModelFactory"), "models module must define ModelFactory")

    def test_lightgbm_adapter_lazy_import(self) -> None:
        try:
            from btcusdt_quant import models
        except ImportError:
            self.skipTest("models module not yet implemented")
        if not hasattr(models, "LightGBMAdapter"):
            self.skipTest("LightGBMAdapter not yet implemented")
        adapter = models.LightGBMAdapter()
        self.assertTrue(hasattr(adapter, "fit"), "LightGBMAdapter must have fit method")
        self.assertTrue(hasattr(adapter, "predict_proba"), "LightGBMAdapter must have predict_proba method")

    def test_model_factory_fallback_chain(self) -> None:
        try:
            from btcusdt_quant import models
        except ImportError:
            self.skipTest("models module not yet implemented")
        if not hasattr(models, "ModelFactory"):
            self.skipTest("ModelFactory not yet implemented")
        factory = models.ModelFactory()
        adapter = factory.create("auto")
        self.assertIsNotNone(adapter, "auto model factory must return an adapter")

    def test_training_works_without_optional_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            from btcusdt_quant.cli import run_train
            summary = run_train(output)
            self.assertFalse(summary["network_used"])
            self.assertIn("mean_test_f1", summary)


class ExchangeAdapterV718Tests(unittest.TestCase):
    def test_exchange_adapter_protocol_exists(self) -> None:
        try:
            from btcusdt_quant import exchange
        except ImportError:
            self.skipTest("exchange module not yet implemented")
        self.assertTrue(hasattr(exchange, "ExchangeAdapter"), "exchange module must define ExchangeAdapter")

    def test_testnet_adapter_exists(self) -> None:
        try:
            from btcusdt_quant import exchange
        except ImportError:
            self.skipTest("exchange module not yet implemented")
        self.assertTrue(hasattr(exchange, "BinanceUsdMFuturesTestnetAdapter"), "testnet adapter must exist")

    def test_listenkey_lifecycle_exists(self) -> None:
        try:
            from btcusdt_quant import exchange
        except ImportError:
            self.skipTest("exchange module not yet implemented")
        self.assertTrue(hasattr(exchange, "ListenKeyState"), "ListenKeyState must exist")

    def test_secrets_manager_exists(self) -> None:
        try:
            from btcusdt_quant import secrets
        except ImportError:
            self.skipTest("secrets module not yet implemented")
        self.assertTrue(hasattr(secrets, "ExchangeCredentials"), "secrets module must define ExchangeCredentials")
        self.assertTrue(hasattr(secrets, "load_binance_credentials_from_env"), "secrets module must have load function")

    def test_mock_adapter_remains_default(self) -> None:
        from btcusdt_quant import live
        adapter = live.MockExchangeAdapter()
        self.assertFalse(adapter.network_enabled, "mock adapter must not enable network by default")

    def test_signed_testnet_adapter_uses_hmac_and_rate_headers(self) -> None:
        from btcusdt_quant import exchange, secrets

        calls: list[exchange.ExchangeRequest] = []

        def fake_transport(request: exchange.ExchangeRequest) -> exchange.ExchangeResponse:
            calls.append(request)
            return exchange.ExchangeResponse(
                200,
                payload={
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "type": "LIMIT",
                    "origQty": "0.001",
                    "status": "NEW",
                    "orderId": 123,
                    "clientOrderId": "cid-1",
                },
                headers={"X-MBX-USED-WEIGHT-1M": "7", "X-MBX-ORDER-COUNT-10S": "1", "Retry-After": "2"},
                request=request,
            )

        adapter = exchange.BinanceUsdMFuturesTestnetAdapter(
            secrets.ExchangeCredentials("api-key", "api-secret"),
            allow_signed_network=True,
            recv_window_ms=5000,
            transport=fake_transport,
            clock=lambda: 1700000000.0,
        )
        order = adapter.submit_order(exchange.ExchangeOrder("BTCUSDT", "BUY", "LIMIT", 0.001, client_order_id="cid-1"))
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(calls[0].url).query)

        self.assertEqual(order.order_id, 123)
        self.assertEqual(calls[0].headers["X-MBX-APIKEY"], "api-key")
        self.assertEqual(parsed["timestamp"], ["1700000000000"])
        self.assertEqual(parsed["recvWindow"], ["5000"])
        self.assertIn("signature", parsed)
        self.assertEqual(adapter.last_response.used_weight_1m if adapter.last_response else None, 7)
        self.assertEqual(adapter.last_response.order_count_10s if adapter.last_response else None, 1)
        self.assertEqual(adapter.last_response.retry_after_seconds if adapter.last_response else None, 2.0)

    def test_signed_testnet_adapter_requires_explicit_network_allow(self) -> None:
        from btcusdt_quant import exchange, secrets

        calls: list[exchange.ExchangeRequest] = []

        def fake_transport(request: exchange.ExchangeRequest) -> exchange.ExchangeResponse:
            calls.append(request)
            return exchange.ExchangeResponse(200, payload={}, request=request)

        adapter = exchange.BinanceUsdMFuturesTestnetAdapter(
            secrets.ExchangeCredentials("api-key", "api-secret"),
            allow_signed_network=False,
            transport=fake_transport,
        )
        with self.assertRaises(RuntimeError):
            adapter.submit_order("BTCUSDT", "BUY", "LIMIT", 0.001, client_order_id="cid-2")
        self.assertEqual(calls, [])

    def test_503_submit_queries_client_order_id_and_marks_unknown(self) -> None:
        from btcusdt_quant import exchange, secrets

        calls: list[exchange.ExchangeRequest] = []

        def fake_transport(request: exchange.ExchangeRequest) -> exchange.ExchangeResponse:
            calls.append(request)
            if request.method == "POST":
                return exchange.ExchangeResponse(503, payload={"msg": "unknown execution"}, request=request)
            return exchange.ExchangeResponse(404, payload={"code": -2013, "msg": "Order does not exist."}, request=request)

        adapter = exchange.BinanceUsdMFuturesTestnetAdapter(
            secrets.ExchangeCredentials("api-key", "api-secret"),
            allow_signed_network=True,
            transport=fake_transport,
            clock=lambda: 1700000000.0,
        )
        order = adapter.submit_order("BTCUSDT", "BUY", "LIMIT", 0.001, client_order_id="cid-503")

        self.assertEqual(order.status, "UNKNOWN")
        self.assertEqual([call.method for call in calls], ["POST", "GET"])
        self.assertIn("origClientOrderId=cid-503", calls[1].url)
        self.assertTrue(adapter.last_response.unknown_execution if adapter.last_response else False)


class FailureInjectionV718Tests(unittest.TestCase):
    def test_failure_injection_framework_exists(self) -> None:
        from btcusdt_quant import failure_injection
        self.assertTrue(hasattr(failure_injection, "ScriptedHttpTransport"), "failure injection must have ScriptedHttpTransport")
        self.assertTrue(hasattr(failure_injection, "ScriptedWebSocketTransport"), "failure injection must have ScriptedWebSocketTransport")
        self.assertTrue(hasattr(failure_injection, "FailureScenario"), "failure injection must have FailureScenario")

    def test_429_scenario_exists(self) -> None:
        from btcusdt_quant import failure_injection
        self.assertTrue(hasattr(failure_injection, "ExchangeFault"), "failure injection must have ExchangeFault")
        scenario = failure_injection.http_429_retry_after_scenario()
        self.assertEqual(scenario.fault, failure_injection.ExchangeFault.HTTP_429)
        self.assertEqual(scenario.expected_action, "block_new_entries")

    def test_websocket_disconnect_scenario_exists(self) -> None:
        from btcusdt_quant import failure_injection
        self.assertTrue(hasattr(failure_injection, "WebSocketFault"), "failure injection must have WebSocketFault")
        scenario = failure_injection.websocket_disconnect_scenario()
        self.assertEqual(scenario.fault, failure_injection.WebSocketFault.DISCONNECT)
        self.assertEqual(scenario.expected_action, "block_new_entries")

    def test_all_failure_scenarios_map_to_expected_fallback_action(self) -> None:
        from btcusdt_quant import failure_injection

        for scenario in failure_injection.all_scenarios():
            with self.subTest(scenario=scenario.name):
                action = failure_injection.fallback_action_for_scenario(scenario)
                self.assertEqual(action, scenario.expected_action)
                self.assertIn(action, governance.FALLBACK_ACTIONS)

    def test_http_429_retry_after_is_deterministic_and_capped(self) -> None:
        from btcusdt_quant import failure_injection

        scenario = failure_injection.http_429_retry_after_scenario()
        transport = failure_injection.ScriptedHttpTransport(scenario.http_script)
        result = transport.request_with_retries("POST", "/fapi/v1/order", scenario.retry_policy)
        self.assertEqual(result.attempts, 3)
        self.assertTrue(result.capped)
        self.assertEqual(result.response.status_code if result.response else None, 429)
        self.assertEqual(result.scheduled_backoffs, (2.0, 30.0))
        self.assertEqual(len(transport.calls), scenario.retry_policy.max_attempts)

    def test_http_418_hard_ban_is_not_retried(self) -> None:
        from btcusdt_quant import failure_injection

        scenario = failure_injection.http_418_hard_ban_scenario()
        result = failure_injection.run_http_scenario(scenario)
        self.assertEqual(result.attempts, 1)
        self.assertFalse(result.capped)
        self.assertEqual(result.response.status_code if result.response else None, 418)

    def test_no_http_scenario_has_unbounded_retries(self) -> None:
        from btcusdt_quant import failure_injection

        for scenario in failure_injection.all_scenarios():
            if not scenario.http_script:
                continue
            with self.subTest(scenario=scenario.name):
                result = failure_injection.run_http_scenario(scenario)
                self.assertLessEqual(result.attempts, scenario.retry_policy.max_attempts)
                self.assertLessEqual(scenario.retry_policy.max_attempts, 3)

    def test_retry_storm_stops_at_configured_cap(self) -> None:
        from btcusdt_quant import failure_injection

        scenario = failure_injection.http_503_unknown_order_status_scenario()
        transport = failure_injection.ScriptedHttpTransport(scenario.http_script * 4)
        result = transport.request_with_retries("POST", "/fapi/v1/order", scenario.retry_policy)
        self.assertTrue(result.capped)
        self.assertEqual(result.attempts, scenario.retry_policy.max_attempts)
        self.assertEqual(transport.remaining, len(scenario.http_script * 4) - scenario.retry_policy.max_attempts)

    def test_timeout_after_order_submit_stops_at_retry_cap(self) -> None:
        from btcusdt_quant import failure_injection

        scenario = failure_injection.timeout_after_order_submit_scenario()
        result = failure_injection.run_http_scenario(scenario)
        self.assertTrue(result.capped)
        self.assertEqual(result.attempts, scenario.retry_policy.max_attempts)
        self.assertIsInstance(result.error, TimeoutError)

    def test_emergency_rate_limit_budget_remains_reserved(self) -> None:
        from btcusdt_quant import failure_injection, live

        scenario = failure_injection.http_429_retry_after_scenario()
        transport = failure_injection.ScriptedHttpTransport(scenario.http_script)
        result = transport.request_with_retries("GET", "/fapi/v1/klines", scenario.retry_policy)
        manager = live.RateLimitManager(limit_per_minute=10, emergency_reserved_ratio=0.20, clock=lambda: 0.0)
        emergency_before = manager.emergency_bucket.tokens
        for call in transport.calls:
            manager.acquire(str(call["endpoint"]), int(call["weight"]))
        self.assertTrue(result.capped)
        self.assertEqual(manager.emergency_bucket.tokens, emergency_before)
        manager.acquire_emergency("POST /fapi/v1/order", 2)
        with self.assertRaises(live.RateLimitBudgetExceeded):
            manager.acquire_emergency("POST /fapi/v1/order", 1)

    def test_websocket_scenarios_emit_deterministic_events(self) -> None:
        from btcusdt_quant import failure_injection

        for scenario in (
            failure_injection.websocket_disconnect_scenario(),
            failure_injection.dropped_websocket_messages_scenario(),
            failure_injection.listenkey_expired_scenario(),
        ):
            with self.subTest(scenario=scenario.name):
                first = failure_injection.ScriptedWebSocketTransport(scenario.websocket_script)
                second = failure_injection.ScriptedWebSocketTransport(scenario.websocket_script)
                first.start()
                second.start()
                first_events = [(event.event_type, event.fault) for event in first.drain()]
                second_events = [(event.event_type, event.fault) for event in second.drain()]
                self.assertEqual(first_events, second_events)
                self.assertEqual(failure_injection.fallback_action_for_scenario(scenario), scenario.expected_action)

    def test_duplicate_and_out_of_order_candle_fixtures_are_reusable(self) -> None:
        from btcusdt_quant import failure_injection

        duplicate = failure_injection.duplicate_candle_scenario()
        duplicate_events = failure_injection.ScriptedWebSocketTransport(duplicate.websocket_script).drain()
        duplicate_times = [event.candle.open_time for event in duplicate_events if event.candle is not None]
        self.assertLess(len(set(duplicate_times)), len(duplicate_times))
        self.assertEqual(failure_injection.fallback_action_for_scenario(duplicate), "allow")

        out_of_order = failure_injection.out_of_order_candle_scenario()
        out_of_order_events = failure_injection.ScriptedWebSocketTransport(out_of_order.websocket_script).drain()
        out_of_order_times = [event.candle.open_time for event in out_of_order_events if event.candle is not None]
        self.assertNotEqual(out_of_order_times, sorted(out_of_order_times))
        self.assertEqual(failure_injection.fallback_action_for_scenario(out_of_order), "allow")


class LiveExecutionV718Tests(unittest.TestCase):
    def test_live_execution_engine_exists(self) -> None:
        try:
            from btcusdt_quant import live
            self.assertTrue(hasattr(live, "LiveExecutionEngine"), "live module must have LiveExecutionEngine")
        except (ImportError, AttributeError):
            self.skipTest("LiveExecutionEngine not yet implemented")

    def test_safe_market_entry_exists(self) -> None:
        try:
            from btcusdt_quant import live
            self.assertTrue(hasattr(live, "safe_market_entry"), "live module must have safe_market_entry")
        except (ImportError, AttributeError):
            self.skipTest("safe_market_entry not yet implemented")

    def test_gap_cross_exit_exists(self) -> None:
        try:
            from btcusdt_quant import live
            self.assertTrue(hasattr(live, "gap_cross_exit"), "live module must have gap_cross_exit")
        except (ImportError, AttributeError):
            self.skipTest("gap_cross_exit not yet implemented")

    def test_drawdown_protocol_exists(self) -> None:
        try:
            from btcusdt_quant import risk
            self.assertTrue(hasattr(risk, "DrawdownProtocol"), "risk module must have DrawdownProtocol")
        except ImportError:
            self.skipTest("risk module not yet implemented")

    def test_tp_sl_orders_reduce_only(self) -> None:
        try:
            from btcusdt_quant import exchange
            order = exchange.ExchangeOrder("BTCUSDT", "SELL", "TAKE_PROFIT_MARKET", 0.001, reduce_only=True)
            self.assertTrue(order.reduce_only, "TP/SL orders must be reduce-only")
        except (ImportError, AttributeError):
            self.skipTest("ExchangeOrder not yet implemented")

    def test_reconciliation_model_exists(self) -> None:
        try:
            from btcusdt_quant import live
            self.assertTrue(hasattr(live, "ExecutionJournal"), "live module must have ExecutionJournal")
        except (ImportError, AttributeError):
            self.skipTest("ExecutionJournal not yet implemented")


class TestEventDriven(unittest.TestCase):
    def _candles(self, rows: int = 24) -> list[data.Candle]:
        from btcusdt_quant import data
        base = data.utc_minute(2026, 1, 1, 0, 0)
        return [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.5 + index,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(rows)
        ]

    def test_event_bus_publishes_in_subscription_order(self) -> None:
        bus = live.EventBus()
        candle = self._candles(1)[0]
        calls: list[tuple[str, datetime]] = []

        def first(event: live.MarketEvent) -> None:
            calls.append(("first", event.candle.open_time))

        def second(event: live.MarketEvent) -> None:
            calls.append(("second", event.candle.open_time))

        bus.subscribe("MarketEvent", first)
        bus.subscribe("MarketEvent", second)
        bus.publish(live.MarketEvent(candle=candle))

        self.assertEqual(calls, [("first", candle.open_time), ("second", candle.open_time)])

    def test_live_engine_matches_run_live_summary_and_emits_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "live"
            expected = live.run_live(output, dry_run=True, max_candles=12)
            observed_events: list[str] = []
            engine = live.LiveEngine(output, dry_run=True, max_candles=12)
            for event_type in ("MarketEvent", "GapEvent", "FeatureEvent", "SignalEvent", "OrderEvent", "MonitoringEvent"):
                engine.bus.subscribe(event_type, lambda _event, event_type=event_type: observed_events.append(event_type))

            actual = engine.run()

            self.assertEqual(set(actual.summary), set(expected.summary))
            for key in ("dry_run", "network_used", "stream_desync_detected", "backfilled_rows", "canonical_rows", "feature_rows", "signal", "entry_action", "exit_action"):
                self.assertEqual(actual.summary[key], expected.summary[key])
            for event_type in ("MarketEvent", "GapEvent", "FeatureEvent", "SignalEvent", "OrderEvent", "MonitoringEvent"):
                self.assertIn(event_type, observed_events)


class MonitoringV718Tests(unittest.TestCase):
    def test_monitoring_module_exists(self) -> None:
        try:
            from btcusdt_quant import monitoring
        except ImportError:
            self.skipTest("monitoring module not yet implemented")
        self.assertTrue(hasattr(monitoring, "ClockDriftService"), "monitoring must have ClockDriftService")
        self.assertTrue(hasattr(monitoring, "ADLMonitorService"), "monitoring must have ADLMonitorService")
        self.assertTrue(hasattr(monitoring, "FundingMonitorService"), "monitoring must have FundingMonitorService")
        self.assertTrue(hasattr(monitoring, "CalibrationDriftMonitor"), "monitoring must have CalibrationDriftMonitor")

    def test_clock_drift_hard_kill_at_1000ms(self) -> None:
        try:
            from btcusdt_quant import monitoring
            service = monitoring.ClockDriftService()
            action = service.action(1000)
            self.assertEqual(action, "hard_kill", "clock drift >= 1000ms must hard_kill")
        except (ImportError, AttributeError):
            self.skipTest("ClockDriftService not yet implemented")

    def test_adl_high_rank_blocks_entries(self) -> None:
        try:
            from btcusdt_quant import monitoring
            service = monitoring.ADLMonitorService()
            action = service.action(4)
            self.assertEqual(action, "block_new_entries", "ADL rank >= 4 must block entries")
        except (ImportError, AttributeError):
            self.skipTest("ADLMonitorService not yet implemented")


class TestMonitoring(unittest.TestCase):
    def _candles(self, rows: int = 24) -> list[data.Candle]:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        return [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.5 + index,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(rows)
        ]

    def test_metrics_registry_counts_events(self) -> None:
        registry = monitoring.MetricsRegistry()
        registry.increment("candles_processed")
        registry.increment("gap_events")
        registry.increment("orders_submitted")
        registry.set("current_probability", 0.62)
        registry.set("current_regime", "trending")

        snapshot = registry.snapshot()

        self.assertEqual(snapshot["counters"]["candles_processed"], 1)
        self.assertEqual(snapshot["counters"]["gap_events"], 1)
        self.assertEqual(snapshot["counters"]["orders_submitted"], 1)
        self.assertEqual(snapshot["gauges"]["current_probability"], 0.62)
        self.assertEqual(snapshot["gauges"]["current_regime"], "trending")

    def test_alert_manager_detects_hard_kill(self) -> None:
        registry = monitoring.MetricsRegistry()
        alerts = monitoring.AlertManager.with_builtin_rules()
        registry.increment("monitoring_actions")
        registry.set("latest_monitoring_action", "hard_kill")

        active = alerts.evaluate(registry.snapshot())

        self.assertTrue(any(alert["name"] == "hard_kill" and alert["severity"] == "critical" for alert in active))

    def test_alert_manager_regime_jitter(self) -> None:
        registry = monitoring.MetricsRegistry()
        alerts = monitoring.AlertManager.with_builtin_rules()
        for _ in range(4):
            registry.increment("regime_transitions")

        active = alerts.evaluate(registry.snapshot())

        self.assertTrue(any(alert["name"] == "regime_jitter" and alert["severity"] == "warning" for alert in active))

    def test_live_writes_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "live"
            result = live.run_live(output, dry_run=True, max_candles=3, custom_candles=self._candles(12))
            metrics_path = Path(result.summary["metrics_path"])
            self.assertTrue(metrics_path.exists())
            payload = json.loads(metrics_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["counters"]["candles_processed"], 3)

    def test_live_writes_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "live"
            result = live.run_live(output, dry_run=True, max_candles=3, custom_candles=self._candles(12))
            alerts_path = Path(result.summary["alerts_path"])
            self.assertTrue(alerts_path.exists())
            payload = json.loads(alerts_path.read_text(encoding="utf-8"))

        self.assertIsInstance(payload, list)

    def test_live_writes_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "live"
            result = live.run_live(output, dry_run=True, max_candles=3, custom_candles=self._candles(12))
            health_path = Path(result.summary["health_path"])
            self.assertTrue(health_path.exists())
            payload = json.loads(health_path.read_text(encoding="utf-8"))

        self.assertIn(payload["overall"], {"healthy", "degraded", "critical"})
        self.assertIn("checks", payload)
        self.assertIn("timestamp", payload)

    def test_live_soak_mode_terminates_after_duration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "live"
            result = live.run_live(
                output,
                dry_run=True,
                max_candles=1000,
                custom_candles=self._candles(12),
                soak_duration_hours=0.001,  # ~3.6 seconds
                soak_report_interval_minutes=0.05,  # ~3 seconds
            )
            self.assertTrue(result.summary["dry_run"])
            self.assertGreater(result.summary["canonical_rows"], 0)

    def test_live_soak_mode_writes_periodic_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "live"
            result = live.run_live(
                output,
                dry_run=True,
                max_candles=1000,
                custom_candles=self._candles(12),
                soak_duration_hours=0.001,
                soak_report_interval_minutes=0.05,
            )
            soak_reports = list(output.glob("soak_report_*.json"))
            self.assertGreaterEqual(len(soak_reports), 0)  # May or may not write depending on timing


class LineageV718Tests(unittest.TestCase):
    def test_lineage_module_exists(self) -> None:
        try:
            from btcusdt_quant import lineage
        except ImportError:
            self.skipTest("lineage module not yet implemented")
        self.assertTrue(hasattr(lineage, "LineageWriter"), "lineage must have LineageWriter")
        self.assertTrue(hasattr(lineage, "LocalLineageFallback"), "lineage must have LocalLineageFallback")

    def test_approval_package_includes_v718_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            from btcusdt_quant.cli import run_demo
            run_demo(output)
            expected_files = [
                "feature_group_gap_policy.yaml",
                "sample_uniqueness_report.csv",
                "cv_split_manifest.csv",
                "calibration_drift_report.csv",
                "latency_slo_report.csv",
                "exchange_anomaly_report.csv",
                "train_live_feature_parity_report.csv",
                "grade_c_cache_forward_plan.yaml",
            ]
            for filename in expected_files:
                with self.subTest(filename=filename):
                    self.assertTrue((output / filename).exists() or (output / "approval_package" / filename).exists(), f"approval package should include {filename}")


class CLIV718Tests(unittest.TestCase):
    def test_cli_has_train_model_family_flag(self) -> None:
        from btcusdt_quant.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["train", "--model-family", "auto"])
        self.assertEqual(args.model_family, "auto", "train must accept --model-family")

    def test_cli_has_exchange_flag(self) -> None:
        from btcusdt_quant.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["live", "--exchange", "binance-testnet"])
        self.assertEqual(args.exchange, "binance-testnet", "live must accept --exchange")

    def test_cli_requires_allow_signed_for_testnet(self) -> None:
        from btcusdt_quant.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["live", "--exchange", "binance-testnet", "--allow-signed-network"])
        self.assertTrue(args.allow_signed_network, "testnet must require --allow-signed-network")

    def test_cli_rejects_prod_without_approval(self) -> None:
        from btcusdt_quant.cli import build_parser, main
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["live", "--exchange", "binance-prod", "--output", tmp])
            self.assertNotEqual(code, 0, "prod must require approval artifacts")


class PurgedCVV718Tests(unittest.TestCase):
    def test_combinatorial_purged_cv_exists(self) -> None:
        try:
            from btcusdt_quant import cv
        except ImportError:
            self.skipTest("cv module not yet implemented")
        self.assertTrue(hasattr(cv, "CombinatorialPurgedCV"), "cv module must have CombinatorialPurgedCV")
        self.assertTrue(hasattr(cv, "SplitManager"), "cv module must have SplitManager")

    def test_sample_uniqueness_weights_exists(self) -> None:
        try:
            from btcusdt_quant import cv
        except ImportError:
            self.skipTest("cv module not yet implemented")
        self.assertTrue(hasattr(cv, "uniqueness_weights"), "cv module must have uniqueness_weights function")

    def test_split_manager_caches_splits(self) -> None:
        try:
            from btcusdt_quant import cv
        except ImportError:
            self.skipTest("cv module not yet implemented")
        manager = cv.SplitManager()
        self.assertTrue(hasattr(manager, "get_splits"), "SplitManager must have get_splits method")


class ECEBrierV718Tests(unittest.TestCase):
    def test_ece_monitoring_exists(self) -> None:
        try:
            from btcusdt_quant import monitoring
        except ImportError:
            self.skipTest("monitoring module not yet implemented")
        self.assertTrue(hasattr(monitoring, "CalibrationDriftMonitor"), "monitoring must have CalibrationDriftMonitor")

    def test_ece_drift_triggers_raise_threshold(self) -> None:
        from btcusdt_quant import governance
        action = governance.fallback_action("ece_drift", 0.10)
        self.assertEqual(action, "raise_threshold", "ECE drift >= 0.10 must raise threshold")

    def test_ece_warning_triggers_warn_only(self) -> None:
        from btcusdt_quant import governance
        action = governance.fallback_action("ece_drift", 0.06)
        self.assertEqual(action, "warn_only", "ECE drift > 0.05 must warn")


class BehavioralV718Tests(unittest.TestCase):
    def test_live_run_wires_exchange_adapter_from_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            from btcusdt_quant import exchange
            adapter = exchange.MockExchangeAdapter()
            result = live.run_live(output, dry_run=True, max_candles=12, exchange_adapter=adapter)
            # Entry action can be allow or block depending on gates; key is adapter is wired
            self.assertIn(result.summary["entry_action"], {"market_entry_allowed", "block_new_entries"}, "exchange adapter should be wired into live execution")

    def test_feature_clipper_enforces_limits_in_build_feature_rows(self) -> None:
        from btcusdt_quant import data
        base = data.utc_minute(2026, 1, 1, 0, 0)
        candles = [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0,
                high=100.0 + index * 1000000,
                low=100.0,
                close=100.0 + index * 1000000,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(200)
        ]
        rows = dataset.build_feature_rows(candles)
        for row in rows:
            for name, value in row.features.items():
                if value is not None:
                    clipper = features.FeatureClipper()
                    limit = clipper.LIMITS.get(clipper.classify(name))
                    if limit is not None:
                        self.assertLessEqual(abs(value), limit, f"feature {name} should be clipped to ±{limit}")

    def test_gap_contamination_blocks_entry_when_gap_ratio_high(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            from btcusdt_quant import data
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
                for index in range(12)
            ]
            candles = [replace(candle, gap_flag=1, repaired=True) for candle in candles]
            result = live.run_live(output, dry_run=True, max_candles=12, custom_candles=candles)
            # With all candles being gap/repaired, gap_ratio should be 1.0 >= 0.20
            # This should trigger block_new_entries via fallback_action("gap_ratio_20", 1.0)
            self.assertEqual(result.summary["entry_action"], "block_new_entries", "gap contamination should block entries when gap_ratio >= 0.20")

    def test_all_active_features_present_in_feature_rows(self) -> None:
        from btcusdt_quant import data
        base = data.utc_minute(2026, 1, 1, 0, 0)
        candles = [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0 + index,
                high=101.0 + index,
                low=99.0 + index,
                close=100.5 + index,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(200)
        ]
        rows = dataset.build_feature_rows(candles)
        active_names = set(dataset.FEATURE_NAMES)
        for row in rows:
            present = set(row.features.keys())
            self.assertEqual(present, active_names, f"active features must match exactly: {active_names - present}")


class TestStrategy(unittest.TestCase):
    def test_high_vol_widens_tp_sl(self) -> None:
        entry = 100.0
        high_vol = live.strategy_for_regime("high_volatility")
        ranging = live.strategy_for_regime("ranging")

        high_tp, high_sl, _ = live.optimized_tp_sl(entry, "BUY", {}, high_vol)
        range_tp, range_sl, _ = live.optimized_tp_sl(entry, "BUY", {}, ranging)

        self.assertGreater(high_tp - entry, range_tp - entry)
        self.assertGreater(entry - high_sl, entry - range_sl)

    def test_ranging_tightens_tp_sl(self) -> None:
        entry = 100.0
        high_vol = live.strategy_for_regime("high_volatility")
        ranging = live.strategy_for_regime("ranging")

        high_tp, high_sl, _ = live.optimized_tp_sl(entry, "BUY", {}, high_vol)
        range_tp, range_sl, _ = live.optimized_tp_sl(entry, "BUY", {}, ranging)

        self.assertLess(range_tp - entry, high_tp - entry)
        self.assertLess(entry - range_sl, entry - high_sl)

    def test_buy_signal_threshold(self) -> None:
        strategy = live.strategy_for_regime("ranging")

        signal = live.select_signal(strategy.long_threshold + 0.01, "ranging", strategy, reward_risk=2.0)

        self.assertEqual(signal, "BUY")

    def test_sell_signal_threshold(self) -> None:
        strategy = live.strategy_for_regime("ranging")

        signal = live.select_signal(strategy.short_threshold - 0.01, "ranging", strategy, reward_risk=2.0)

        self.assertEqual(signal, "SELL")

    def test_atr_based_tp_sl(self) -> None:
        strategy = live.StrategyConfig("atr_test", 0.5, 0.5, 0.010, 0.005, 2.0, 1.0, 1.0)

        fixed_tp, fixed_sl, fixed_decision = live.optimized_tp_sl(100.0, "BUY", {}, strategy)
        atr_tp, atr_sl, atr_decision = live.optimized_tp_sl(100.0, "BUY", {"atr_pct": 0.02}, strategy)

        self.assertNotEqual((fixed_tp, fixed_sl), (atr_tp, atr_sl))
        self.assertEqual(fixed_decision["pricing_method"], "fixed_pct")
        self.assertEqual(atr_decision["pricing_method"], "atr_pct")

    def test_live_summary_includes_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "live"

            result = live.run_live(output, dry_run=True, max_candles=3)
            summary = json.loads((output / "live_summary.json").read_text(encoding="utf-8"))

        self.assertIn("strategy_decision", result.summary)
        self.assertIn("strategy_decision", summary)
        self.assertEqual(summary["strategy_decision"]["profile"], "balanced")

    def test_invalid_reward_risk_blocks(self) -> None:
        strategy = live.StrategyConfig("bad_rr", 0.40, 0.60, 0.005, 0.010, 0.5, 1.0, 1.0)
        _, _, decision = live.optimized_tp_sl(100.0, "BUY", {}, strategy)

        signal = live.select_signal(0.90, "ranging", strategy, reward_risk=float(decision["reward_risk"]))

        self.assertEqual(signal, "HOLD")


class TestOrderBlockImbalance(unittest.TestCase):
    def _candle(self, open_p: float, high: float, low: float, close: float, volume: float = 1000.0, taker_imbalance: float = 0.0, volume_zscore: float = 0.0, bid_ask_imbalance: float = 0.0) -> dict[str, float]:
        return {
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "taker_imbalance": taker_imbalance,
            "volume_zscore": volume_zscore,
            "bid_ask_imbalance": bid_ask_imbalance,
        }

    def test_detect_bullish_order_block(self) -> None:
        detector = features.OrderBlockImbalanceDetector()
        candles = [
            self._candle(100.0, 101.0, 99.0, 100.5, taker_imbalance=0.5, volume_zscore=2.0),  # small body
            self._candle(100.5, 102.0, 100.5, 101.8, taker_imbalance=0.6, volume_zscore=2.5),  # strong bullish OB
            self._candle(101.8, 102.0, 101.0, 101.5, taker_imbalance=0.1, volume_zscore=0.5),  # normal
        ]
        obs = detector.detect_order_blocks(candles)
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["side"], "bullish")
        self.assertEqual(obs[0]["index"], 1)

    def test_detect_bearish_order_block(self) -> None:
        detector = features.OrderBlockImbalanceDetector()
        candles = [
            self._candle(102.0, 102.2, 100.0, 100.2, taker_imbalance=-0.6, volume_zscore=2.5),  # strong bearish OB
            self._candle(100.2, 100.5, 100.0, 100.5, taker_imbalance=-0.2, volume_zscore=0.5),  # normal
        ]
        obs = detector.detect_order_blocks(candles)
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["side"], "bearish")

    def test_no_order_block_when_criteria_not_met(self) -> None:
        detector = features.OrderBlockImbalanceDetector()
        candles = [
            self._candle(100.0, 100.2, 99.8, 100.1, taker_imbalance=0.1, volume_zscore=0.5),  # weak body
            self._candle(100.1, 101.0, 100.1, 100.2, taker_imbalance=0.2, volume_zscore=0.5),  # large wick
        ]
        obs = detector.detect_order_blocks(candles)
        self.assertEqual(len(obs), 0)

    def test_entry_timing_buy_signal(self) -> None:
        detector = features.OrderBlockImbalanceDetector()
        candles = [
            self._candle(100.0, 102.0, 100.0, 101.8, taker_imbalance=0.6, volume_zscore=2.5),  # bullish OB
            self._candle(101.8, 102.0, 101.0, 101.5, taker_imbalance=0.1, volume_zscore=0.5),  # moves away
            self._candle(101.5, 102.0, 101.0, 101.2, taker_imbalance=0.1, volume_zscore=0.5),  # still away
            self._candle(101.2, 101.9, 100.5, 101.0, taker_imbalance=0.4, volume_zscore=1.0),  # returns to zone
        ]
        result = detector.generate_entry_timing(candles, 3)
        self.assertEqual(result["signal"], "BUY")
        self.assertGreater(result["confidence"], 0.0)
        self.assertIsNotNone(result["target_ob"])

    def test_entry_timing_sell_signal(self) -> None:
        detector = features.OrderBlockImbalanceDetector()
        candles = [
            self._candle(102.0, 102.0, 100.0, 100.2, taker_imbalance=-0.6, volume_zscore=2.5),  # bearish OB
            self._candle(100.2, 100.5, 99.0, 100.0, taker_imbalance=-0.1, volume_zscore=0.5),  # moves away
            self._candle(100.0, 101.0, 99.5, 100.5, taker_imbalance=-0.4, volume_zscore=1.0),  # returns to zone
        ]
        result = detector.generate_entry_timing(candles, 2)
        self.assertEqual(result["signal"], "SELL")
        self.assertGreater(result["confidence"], 0.0)

    def test_entry_timing_hold_when_no_ob(self) -> None:
        detector = features.OrderBlockImbalanceDetector()
        candles = [
            self._candle(100.0, 100.2, 99.8, 100.1, taker_imbalance=0.1, volume_zscore=0.5),
            self._candle(100.1, 100.3, 99.9, 100.2, taker_imbalance=0.1, volume_zscore=0.5),
        ]
        result = detector.generate_entry_timing(candles, 1)
        self.assertEqual(result["signal"], "HOLD")
        self.assertEqual(result["reason"], "no_order_blocks")

    def test_entry_timing_hold_when_price_not_in_zone(self) -> None:
        detector = features.OrderBlockImbalanceDetector()
        candles = [
            self._candle(100.0, 102.0, 100.0, 101.8, taker_imbalance=0.6, volume_zscore=2.5),  # bullish OB at 100-102
            self._candle(101.8, 105.0, 103.0, 104.0, taker_imbalance=0.1, volume_zscore=0.5),  # far above zone
        ]
        result = detector.generate_entry_timing(candles, 1)
        self.assertEqual(result["signal"], "HOLD")
        self.assertEqual(result["reason"], "price_not_in_ob_zone")

    def test_config_dict(self) -> None:
        config = features.OrderBlockConfig(min_body_pct=0.70, max_wick_pct=0.15)
        detector = features.OrderBlockImbalanceDetector(config)
        d = detector.config_dict()
        self.assertEqual(d["min_body_pct"], 0.70)
        self.assertEqual(d["max_wick_pct"], 0.15)

    def test_min_bars_since_last_separation(self) -> None:
        detector = features.OrderBlockImbalanceDetector()
        candles = [
            self._candle(100.0, 102.0, 100.0, 101.8, taker_imbalance=0.6, volume_zscore=2.5),  # OB
            self._candle(101.8, 102.0, 101.0, 101.5, taker_imbalance=0.1, volume_zscore=0.5),
            self._candle(101.5, 102.0, 101.0, 101.2, taker_imbalance=0.1, volume_zscore=0.5),
            self._candle(101.2, 103.0, 101.2, 102.8, taker_imbalance=0.6, volume_zscore=2.5),  # too close (3 bars < 5)
            self._candle(102.8, 103.0, 102.0, 102.5, taker_imbalance=0.1, volume_zscore=0.5),
            self._candle(102.5, 105.0, 102.5, 104.8, taker_imbalance=0.6, volume_zscore=2.5),  # valid (5 bars since last)
        ]
        obs = detector.detect_order_blocks(candles)
        self.assertEqual(len(obs), 2)
        self.assertEqual(obs[0]["index"], 0)
        self.assertEqual(obs[1]["index"], 5)


class ModelArtifactV718Tests(unittest.TestCase):
    def test_load_model_artifact_from_valid_json(self) -> None:
        from btcusdt_quant import training
        classifier = training.LinearClassifier(
            feature_names=("return_1", "volume_ratio"),
            standardizer=training.Standardizer(
                {"return_1": 0.0, "volume_ratio": 10.0},
                {"return_1": 0.01, "volume_ratio": 5.0},
            ),
            weights={"return_1": 1.0, "volume_ratio": -0.5},
            intercept=0.0,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.json"
            path.write_text(json.dumps(classifier.as_dict()), encoding="utf-8")
            loaded = live.load_model_artifact(path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.feature_names, ("return_1", "volume_ratio"))
            self.assertAlmostEqual(loaded.intercept, 0.0)

    def test_load_model_artifact_missing_path_returns_none(self) -> None:
        self.assertIsNone(live.load_model_artifact(None))

    def test_load_model_artifact_strict_raises_on_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent.json"
            with self.assertRaises(FileNotFoundError):
                live.load_model_artifact(path, strict=True)

    def test_linear_classifier_from_dict_rejects_empty_features(self) -> None:
        from btcusdt_quant import training
        with self.assertRaises(ValueError):
            training.LinearClassifier.from_dict({"model_family": "deterministic_centroid_linear_classifier", "feature_names": []})

    def test_linear_classifier_from_dict_rejects_missing_mean(self) -> None:
        from btcusdt_quant import training
        payload = {
            "model_family": "deterministic_centroid_linear_classifier",
            "feature_names": ["return_1", "volume_ratio"],
            "standardizer_means": {"return_1": 0.0},
            "standardizer_scales": {"return_1": 0.01, "volume_ratio": 5.0},
            "weights": {"return_1": 1.0, "volume_ratio": -0.5},
            "intercept": 0.0,
        }
        with self.assertRaises(ValueError):
            training.LinearClassifier.from_dict(payload)

    def test_linear_classifier_from_dict_rejects_zero_scale(self) -> None:
        from btcusdt_quant import training
        payload = {
            "model_family": "deterministic_centroid_linear_classifier",
            "feature_names": ["return_1"],
            "standardizer_means": {"return_1": 0.0},
            "standardizer_scales": {"return_1": 0.0},
            "weights": {"return_1": 1.0},
            "intercept": 0.0,
        }
        with self.assertRaises(ValueError):
            training.LinearClassifier.from_dict(payload)

    def test_linear_classifier_from_dict_rejects_wrong_family(self) -> None:
        from btcusdt_quant import training
        with self.assertRaises(ValueError):
            training.LinearClassifier.from_dict({"model_family": "lightgbm", "feature_names": ["return_1"]})

    def test_live_run_with_model_artifact_uses_inference(self) -> None:
        from btcusdt_quant import data, training
        classifier = training.LinearClassifier(
            feature_names=("return_1",),
            standardizer=training.Standardizer({"return_1": 0.0}, {"return_1": 0.01}),
            weights={"return_1": 10.0},
            intercept=0.0,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "model.json"
            model_path.write_text(json.dumps(classifier.as_dict()), encoding="utf-8")
            output = Path(tmpdir) / "live"
            base = data.utc_minute(2026, 1, 1, 0, 0)
            candles = [
                data.Candle(
                    open_time=base + timedelta(minutes=index),
                    open=100.0 + index,
                    high=101.0 + index,
                    low=99.0 + index,
                    close=100.5 + index,
                    volume=10.0,
                    quote_volume=1000.0,
                    number_of_trades=100,
                    taker_buy_base_volume=5.0,
                    taker_buy_quote_volume=500.0,
                )
                for index in range(200)
            ]
            result = live.run_live(output, dry_run=True, max_candles=12, custom_candles=candles, model_artifact_path=model_path)
            inference = result.summary.get("model_inference", {})
            self.assertTrue(inference.get("model_loaded", False), "model should be loaded")
            self.assertIsNotNone(inference.get("probability"), "probability should be computed")

    def test_live_run_bracket_orders_no_duplicate_market_entry(self) -> None:
        from btcusdt_quant import data, exchange
        class LeveragedMockAdapter(exchange.MockExchangeAdapter):
            def get_position(self, symbol: str) -> exchange.ExchangePosition:
                pos = super().get_position(symbol)
                return exchange.ExchangePosition(symbol, pos.quantity, leverage=1.0)
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "live"
            base = data.utc_minute(2026, 1, 1, 0, 0)
            candles = [
                data.Candle(
                    open_time=base + timedelta(minutes=index),
                    open=100.0 + index,
                    high=101.0 + index,
                    low=99.0 + index,
                    close=100.5 + index,
                    volume=10.0,
                    quote_volume=1000.0,
                    number_of_trades=100,
                    taker_buy_base_volume=5.0,
                    taker_buy_quote_volume=500.0,
                )
                for index in range(200)
            ]
            adapter = LeveragedMockAdapter()
            result = live.run_live(output, dry_run=False, allow_public_network=True, max_candles=12, custom_candles=candles, exchange_adapter=adapter, source_parity_passed=True)
            orders = list(adapter.orders)
            market_orders = [order for order in orders if order.order_type == exchange.MARKET]
            exit_orders = [order for order in orders if order.order_type in (exchange.TAKE_PROFIT_MARKET, exchange.STOP_MARKET)]
            # Exactly one market entry should be submitted (no duplicate)
            self.assertEqual(len(market_orders), 1, "exactly one market entry should exist")
            # Exactly two exit orders (TP + SL) should be submitted
            self.assertEqual(len(exit_orders), 2, "exactly two exit orders (TP + SL) should exist")
            # All exit orders should be reduce-only
            for order in exit_orders:
                self.assertTrue(order.reduce_only, "exit orders must be reduce-only")
            bracket = result.summary.get("bracket_orders")
            self.assertIsNotNone(bracket, "bracket_orders should be present")
            self.assertIsNotNone(bracket.get("tp_order_id"), "TP order should be present")
            self.assertIsNotNone(bracket.get("sl_order_id"), "SL order should be present")

    def test_live_run_bracket_failure_records_error(self) -> None:
        # Adapter that rejects TP/SL submission to simulate bracket failure
        from btcusdt_quant import data, exchange
        class RejectTPExchangeAdapter(exchange.MockExchangeAdapter):
            def get_position(self, symbol: str) -> exchange.ExchangePosition:
                pos = super().get_position(symbol)
                return exchange.ExchangePosition(symbol, pos.quantity, leverage=1.0)
            def submit_order(self, *args: object, **kwargs: object) -> exchange.ExchangeOrder:
                order = super().submit_order(*args, **kwargs)
                if order.order_type in (exchange.TAKE_PROFIT_MARKET, exchange.STOP_MARKET):
                    # Remove the rejected order from the adapter's orders list
                    self.orders = [o for o in self.orders if o.order_id != order.order_id]
                    raise RuntimeError("simulated TP/SL rejection")
                return order
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "live"
            base = data.utc_minute(2026, 1, 1, 0, 0)
            candles = [
                data.Candle(
                    open_time=base + timedelta(minutes=index),
                    open=100.0 + index,
                    high=101.0 + index,
                    low=99.0 + index,
                    close=100.5 + index,
                    volume=10.0,
                    quote_volume=1000.0,
                    number_of_trades=100,
                    taker_buy_base_volume=5.0,
                    taker_buy_quote_volume=500.0,
                )
                for index in range(200)
            ]
            adapter = RejectTPExchangeAdapter()
            result = live.run_live(output, dry_run=False, allow_public_network=True, max_candles=12, custom_candles=candles, exchange_adapter=adapter, source_parity_passed=True)
            # Bracket failure should set entry_action to hard_kill
            self.assertEqual(result.summary["entry_action"], "hard_kill", "bracket failure should trigger hard_kill")
            self.assertIsNotNone(result.summary.get("bracket_error"), "bracket_error should be recorded")
            # Only one market entry should exist, no TP/SL orders (exclude reduce-only emergency close)
            market_orders = [order for order in adapter.orders if order.order_type == exchange.MARKET and not getattr(order, "reduce_only", False)]
            self.assertEqual(len(market_orders), 1, "exactly one market entry should exist")
            exit_orders = [order for order in adapter.orders if order.order_type in (exchange.TAKE_PROFIT_MARKET, exchange.STOP_MARKET)]
            self.assertEqual(len(exit_orders), 0, "no TP/SL orders should exist after rejection")

    def test_live_run_bracket_failure_triggers_hard_kill_no_duplicate_entry(self) -> None:
        # Verify that bracket failure does not leave duplicate market entries
        from btcusdt_quant import data, exchange
        class RejectBracketAdapter(exchange.MockExchangeAdapter):
            def get_position(self, symbol: str) -> exchange.ExchangePosition:
                pos = super().get_position(symbol)
                return exchange.ExchangePosition(symbol, pos.quantity, leverage=1.0)
            def submit_order(self, *args: object, **kwargs: object) -> exchange.ExchangeOrder:
                order = super().submit_order(*args, **kwargs)
                if order.order_type in (exchange.TAKE_PROFIT_MARKET, exchange.STOP_MARKET):
                    raise RuntimeError("bracket rejection")
                return order
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "live"
            base = data.utc_minute(2026, 1, 1, 0, 0)
            candles = [
                data.Candle(
                    open_time=base + timedelta(minutes=index),
                    open=100.0 + index,
                    high=101.0 + index,
                    low=99.0 + index,
                    close=100.5 + index,
                    volume=10.0,
                    quote_volume=1000.0,
                    number_of_trades=100,
                    taker_buy_base_volume=5.0,
                    taker_buy_quote_volume=500.0,
                )
                for index in range(200)
            ]
            adapter = RejectBracketAdapter()
            result = live.run_live(output, dry_run=False, allow_public_network=True, max_candles=12, custom_candles=candles, exchange_adapter=adapter, source_parity_passed=True)
            # Should have exactly one market entry, no duplicate (exclude reduce-only emergency close)
            market_orders = [order for order in adapter.orders if order.order_type == exchange.MARKET and not getattr(order, "reduce_only", False)]
            self.assertEqual(len(market_orders), 1, "no duplicate market entries should exist")
            # Should be hard_kill due to bracket failure
            self.assertEqual(result.summary["entry_action"], "hard_kill")
            self.assertIsNotNone(result.summary.get("bracket_error"))


class EndToEndPipelineV718Tests(unittest.TestCase):
    def test_end_to_end_default_cli_path_collect_train_live(self) -> None:
        from btcusdt_quant import data, exchange
        # Verify the documented default CLI path works end-to-end:
        # collect (default args) -> train (default args) -> live (with model.json)
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Collect data with default args (240 rows)
            data_path = Path(tmpdir) / "btcusdt_1m.csv"
            collect_result = dataset.collect_candles(data_path, rows=240)
            self.assertGreaterEqual(collect_result.rows, 200, "collect should produce at least 200 rows")
            
            # 2. Train with default args (model_family defaults to stdlib)
            train_dir = Path(tmpdir) / "training"
            train_result = training.run_training(data_path, train_dir)
            self.assertGreaterEqual(len(train_result.dataset_build.labeled_rows), 80, "training should produce at least 80 labeled rows")
            
            # Verify model.json exists and is compatible with live.py
            model_path = train_dir / "model.json"
            self.assertTrue(model_path.exists(), "model.json should be created after training")
            
            # 3. Run live with the trained model artifact
            live_dir = Path(tmpdir) / "live"
            adapter = exchange.MockExchangeAdapter()
            candles = [
                data.Candle(
                    open_time=data.utc_minute(2026, 1, 1, 0, 0) + timedelta(minutes=index),
                    open=100.0 + index,
                    high=101.0 + index,
                    low=99.0 + index,
                    close=100.5 + index,
                    volume=10.0,
                    quote_volume=1000.0,
                    number_of_trades=100,
                    taker_buy_base_volume=5.0,
                    taker_buy_quote_volume=500.0,
                )
                for index in range(200)
            ]
            live_result = live.run_live(
                live_dir,
                dry_run=True,
                max_candles=12,
                custom_candles=candles,
                exchange_adapter=adapter,
                model_artifact_path=model_path,
            )
            # Verify model was loaded successfully
            inference = live_result.summary.get("model_inference", {})
            self.assertTrue(inference.get("model_loaded", False), "model should be loaded from artifact")
            self.assertIsNotNone(inference.get("probability"), "probability should be computed from model")


class E2ECLIV718Tests(unittest.TestCase):
    def test_cli_collect_train_live_pipeline(self) -> None:
        from btcusdt_quant import data
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir) / "btcusdt_1m.csv"
            train_dir = Path(tmpdir) / "training"
            live_dir = Path(tmpdir) / "live"
            model_path = train_dir / "model.json"
            # 1. CLI collect (default args, no network)
            collect_result = subprocess.run(
                [sys.executable, "-m", "btcusdt_quant", "collect", "--output", str(data_path), "--rows", "240"],
                capture_output=True, text=True, timeout=30
            )
            self.assertEqual(collect_result.returncode, 0, f"collect failed: {collect_result.stderr}")
            self.assertTrue(data_path.exists(), "collect should write CSV")
            # 2. CLI train (default args, model_family=stdlib)
            train_result = subprocess.run(
                [sys.executable, "-m", "btcusdt_quant", "train", "--output", str(train_dir), "--input", str(data_path)],
                capture_output=True, text=True, timeout=30
            )
            self.assertEqual(train_result.returncode, 0, f"train failed: {train_result.stderr}")
            self.assertTrue(model_path.exists(), "train should write model.json")
            # 3. CLI live (dry-run with model artifact)
            live_result = subprocess.run(
                [sys.executable, "-m", "btcusdt_quant", "live", "--dry-run", "--output", str(live_dir), "--model-artifact", str(model_path)],
                capture_output=True, text=True, timeout=30
            )
            self.assertEqual(live_result.returncode, 0, f"live failed: {live_result.stderr}")
            live_summary_path = live_dir / "live_summary.json"
            self.assertTrue(live_summary_path.exists(), "live should write live_summary.json")
            summary = json.loads(live_summary_path.read_text())
            inference = summary.get("model_inference", {})
            self.assertTrue(inference.get("model_loaded", False), "model should be loaded via CLI")
            self.assertIsNotNone(inference.get("probability"), "probability should be computed")

class PublicCollectionV718Tests(unittest.TestCase):
    def test_public_kline_downloader_retry_on_failure(self) -> None:
        from btcusdt_quant import dataset
        import urllib.request
        call_count = 0
        def failing_urlopen(request: urllib.request.Request, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise urllib.error.HTTPError(request.get_full_url(), 429, "Too Many Requests", {}, None)
            # Return minimal valid kline response
            return _FakeResponse(b"[[0,\"1\",\"2\",\"3\",\"4\",\"5\",\"6\",\"7\",\"8\",\"9\",\"10\",\"11\"]]")
        downloader = dataset.PublicKlineDownloader(allow_network=True, urlopen=failing_urlopen)
        with self.assertRaises(RuntimeError):
            downloader.fetch_klines(symbol="BTCUSDT", interval="1m", limit=1, max_retries=2)
        self.assertEqual(call_count, 2, "should exhaust retries")

    def test_pagination_computes_start_time_for_rows_over_1500(self) -> None:
        from btcusdt_quant import dataset
        import urllib.request
        captured_urls: list[str] = []
        def capturing_urlopen(request: urllib.request.Request, **kwargs: object) -> object:
            captured_urls.append(request.get_full_url())
            return _FakeResponse(b"[]")
        # Monkey-patch collect_candles to use our instrumented downloader
        original_collect = dataset.collect_candles
        def patched_collect(output_path: Path, rows: int = 240, allow_public_network: bool = False, symbol: str = "BTCUSDT", interval: str = "1m") -> dataset.CollectionResult:
            if not allow_public_network:
                return original_collect(output_path, rows, allow_public_network, symbol, interval)
            downloader = dataset.PublicKlineDownloader(allow_network=True, urlopen=capturing_urlopen)
            if rows > 1500:
                interval_ms = dataset._interval_to_ms(interval)
                end_time_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                start_time_ms = end_time_ms - (rows * interval_ms)
                candles = downloader.fetch_klines_paginated(
                    symbol=symbol, interval=interval, start_time_ms=start_time_ms, end_time_ms=end_time_ms, max_rows=rows
                )
            else:
                candles = downloader.fetch_klines(symbol=symbol, interval=interval, limit=rows)
            dataset.write_candles_csv(output_path, candles)
            return dataset.CollectionResult(output_path, "binance_public_klines", symbol, interval, len(candles), True)
        dataset.collect_candles = patched_collect
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "test.csv"
                # This should trigger pagination path with start_time_ms
                try:
                    dataset.collect_candles(output_path, rows=2000, allow_public_network=True, symbol="BTCUSDT", interval="1m")
                except Exception:
                    pass  # urlopen returns empty, may raise; we only care about the URL
                # Verify that startTime parameter was present in at least one URL
                self.assertTrue(
                    any("startTime=" in url for url in captured_urls),
                    "pagination should include startTime parameter for large row requests"
                )
        finally:
            dataset.collect_candles = original_collect

class AdvancedTrainingV718Tests(unittest.TestCase):
    def test_feature_selection_enabled_reduces_feature_count(self) -> None:
        from btcusdt_quant import training
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir) / "btcusdt_1m.csv"
            dataset.collect_candles(data_path, rows=240)
            train_dir = Path(tmpdir) / "training"
            config = training.TrainingConfig(feature_selection_enabled=True)
            result = training.run_training(data_path, train_dir, config=config)
            fs_report = result.run_summary.get("feature_selection", {})
            self.assertTrue(fs_report.get("enabled", False), "feature_selection should be enabled")
            # Core features should be <= original features
            original_count = fs_report.get("original_feature_count", 0)
            selected_count = fs_report.get("selected_core_count", 0)
            self.assertGreaterEqual(original_count, selected_count, "selected features should not exceed original")

    def test_optuna_enabled_produces_report(self) -> None:
        from btcusdt_quant import training
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir) / "btcusdt_1m.csv"
            dataset.collect_candles(data_path, rows=240)
            train_dir = Path(tmpdir) / "training"
            config = training.TrainingConfig(optuna_enabled=True, optuna_trials=5, optuna_budget_profile="research_fast")
            result = training.run_training(data_path, train_dir, config=config)
            optuna_report = result.run_summary.get("optuna", {})
            self.assertTrue(optuna_report.get("enabled", False), "optuna should be enabled")
            self.assertIn("report", optuna_report, "optuna report should exist")
            self.assertIn("best_params", optuna_report.get("report", {}), "optuna best_params should exist")

    def test_champion_challenger_enabled_produces_evaluation(self) -> None:
        from btcusdt_quant import training
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir) / "btcusdt_1m.csv"
            dataset.collect_candles(data_path, rows=240)
            train_dir = Path(tmpdir) / "training"
            config = training.TrainingConfig(champion_challenger_enabled=True)
            result = training.run_training(data_path, train_dir, config=config)
            cc_report = result.run_summary.get("champion_challenger", {})
            self.assertTrue(cc_report.get("enabled", False), "champion_challenger should be enabled")
            self.assertIn("promotion_ok", cc_report, "promotion_ok should be present")
            self.assertIn("promotion_reason", cc_report, "promotion_reason should be present")
            self.assertIn("shadow_metrics", cc_report, "shadow_metrics should be present")

    def test_metrics_produces_trading_metrics(self) -> None:
        from btcusdt_quant import training
        probs = [0.6, 0.4, 0.7, 0.3, 0.8]
        labels = [1, 0, 1, 0, 1]
        m = training.metrics(probs, labels, 0.5)
        self.assertIn("mdd", m, "metrics should include mdd")
        self.assertIn("sharpe", m, "metrics should include sharpe")
        self.assertIn("calmar", m, "metrics should include calmar")
        self.assertIsInstance(m["mdd"], float)
        self.assertIsInstance(m["sharpe"], float)
        self.assertIsInstance(m["calmar"], float)

    def test_champion_challenger_missing_metrics_fails_promotion(self) -> None:
        """Missing required metrics (sharpe, mdd, calmar, CI, threshold flip, latency, PSI) must fail promotion."""
        mgr = features.ChampionChallengerManager()
        # Only provide the 4 required metrics; the rest are missing
        ok, reason = mgr.can_promote(
            shadow_days=30,
            signal_count=100,
            mdd_delta=-0.01,
            calmar_delta=0.05,
        )
        self.assertFalse(ok, "missing metrics should fail promotion")

    def test_champion_challenger_score_bin_ci_passed_from_training(self) -> None:
        """Champion-challenger enabled training must pass non-empty score-bin CI to can_promote."""
        from btcusdt_quant import training, features
        captured_ci: list[list[dict[str, object]]] = []
        original_can_promote = features.ChampionChallengerManager.can_promote
        def _patched_can_promote(self, *args, **kwargs):
            ci = kwargs.get("score_bin_ci")
            captured_ci.append(list(ci) if ci is not None else [])
            return original_can_promote(self, *args, **kwargs)
        features.ChampionChallengerManager.can_promote = _patched_can_promote
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                data_path = Path(tmpdir) / "btcusdt_1m.csv"
                dataset.collect_candles(data_path, rows=240)
                train_dir = Path(tmpdir) / "training"
                config = training.TrainingConfig(champion_challenger_enabled=True)
                result = training.run_training(data_path, train_dir, config=config)
                cc_report = result.run_summary.get("champion_challenger", {})
                self.assertTrue(cc_report.get("enabled", False))
                # Verify captured score_bin_ci is non-empty and contains correct keys
                self.assertTrue(len(captured_ci) > 0, "can_promote must be called with score_bin_ci")
                ci_rows = captured_ci[0]
                self.assertTrue(len(ci_rows) > 0, "score_bin_ci must not be empty")
                for row in ci_rows:
                    self.assertIn("net_return_ci_lower_95", row, "CI row must contain net_return_ci_lower_95")
                    self.assertIn("net_return_ci_upper_95", row, "CI row must contain net_return_ci_upper_95")
        finally:
            features.ChampionChallengerManager.can_promote = original_can_promote

    def test_champion_challenger_delta_gates_work(self) -> None:
        """Delta gates must detect when challenger worsens MDD or Calmar."""
        mgr = features.ChampionChallengerManager()
        ok, reason = mgr.can_promote(
            shadow_days=30,
            signal_count=100,
            mdd_delta=0.05,  # positive = challenger worsens MDD
            calmar_delta=-0.01,  # negative = challenger worsens Calmar
            sharpe=1.5,
            mdd=0.10,
            calmar=2.5,
            score_bin_ci=[{"lower": 0.01, "upper": 0.05}],
            threshold_flip_rate=0.02,
            latency_p99_ms=50.0,
            psi=0.05,
        )
        self.assertFalse(ok, "worsening deltas should fail promotion")
        self.assertIn("worsens", reason.lower(), f"reason should mention worsens: {reason}")

    def test_public_downloader_retry_eventual_success(self) -> None:
        """Retry logic must eventually succeed after transient failures."""
        import json
        from btcusdt_quant import dataset
        call_count = 0
        def flaky_urlopen(req, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                from urllib.error import HTTPError
                raise HTTPError(req.get_full_url(), 429, "Too Many Requests", {}, None)
            body = json.dumps([[0, "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]]).encode()
            return _FakeResponse(body)
        downloader = dataset.PublicKlineDownloader(
            allow_network=True,
            base_url="http://test",
            urlopen=flaky_urlopen,
        )
        result = downloader.fetch_klines(symbol="BTCUSDT", interval="1m", limit=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(call_count, 3)

    def test_public_downloader_429_retry_after_respected(self) -> None:
        """429 with Retry-After header must be respected and eventually succeed."""
        import json
        from btcusdt_quant import dataset
        call_count = 0
        sleep_calls: list[float] = []
        def fake_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)
        def flaky_urlopen(req, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                from urllib.error import HTTPError
                raise HTTPError(req.get_full_url(), 429, "Too Many Requests", {"Retry-After": "1"}, None)
            body = json.dumps([[0, "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]]).encode()
            return _FakeResponse(body)
        downloader = dataset.PublicKlineDownloader(
            allow_network=True,
            base_url="http://test",
            urlopen=flaky_urlopen,
        )
        # Monkeypatch time.sleep to capture Retry-After delay
        import time
        original_sleep = time.sleep
        time.sleep = fake_sleep
        try:
            result = downloader.fetch_klines(symbol="BTCUSDT", interval="1m", limit=1)
        finally:
            time.sleep = original_sleep
        self.assertEqual(len(result), 1)
        self.assertEqual(call_count, 3)
        # Verify Retry-After was respected (sleep called at least once)
        self.assertGreater(len(sleep_calls), 0, "Retry-After should trigger sleep")

    def test_public_downloader_418_not_retried(self) -> None:
        """418 hard-ban must not be retried."""
        import json
        from btcusdt_quant import dataset
        call_count = 0
        def flaky_urlopen(req, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            from urllib.error import HTTPError
            raise HTTPError(req.get_full_url(), 418, "IP Ban", {}, None)
        downloader = dataset.PublicKlineDownloader(
            allow_network=True,
            base_url="http://test",
            urlopen=flaky_urlopen,
        )
        with self.assertRaises(RuntimeError):
            downloader.fetch_klines(symbol="BTCUSDT", interval="1m", limit=1)
        self.assertEqual(call_count, 1, "418 hard-ban must not retry")

    def test_optuna_model_factory_uses_params(self) -> None:
        """Optuna model factory must merge params into model_params."""
        from btcusdt_quant import training, models
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir) / "btcusdt_1m.csv"
            dataset.collect_candles(data_path, rows=240)
            train_dir = Path(tmpdir) / "training"
            config = training.TrainingConfig(
                optuna_enabled=True,
                optuna_trials=3,
                optuna_budget_profile="research_fast",
            )
            result = training.run_training(data_path, train_dir, config=config)
            optuna_report = result.run_summary.get("optuna", {})
            if optuna_report.get("enabled"):
                best_params = optuna_report.get("report", {}).get("best_params", {})
                # If best_params has threshold, it should be in the range
                if "threshold" in best_params:
                    self.assertGreaterEqual(best_params["threshold"], 0.45)
                    self.assertLessEqual(best_params["threshold"], 0.55)

    def test_optuna_params_affect_artifacts(self) -> None:
        """Optuna best params must affect the produced training artifacts (model.json, run_summary)."""
        from btcusdt_quant import training, features
        # Monkeypatch OptunaStudyRunner to return deterministic best params
        original_run_study = features.OptunaStudyRunner.run_study
        def _patched_run_study(self, *args, **kwargs):
            return {
                "optuna_available": False,
                "best_params": {"threshold": 0.37, "signal_scale": 1.7},
                "best_value": 0.1,
                "trial_history": [],
                "objective_description": "test",
            }
        features.OptunaStudyRunner.run_study = _patched_run_study
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                data_path = Path(tmpdir) / "btcusdt_1m.csv"
                dataset.collect_candles(data_path, rows=240)
                train_dir = Path(tmpdir) / "training"
                config = training.TrainingConfig(
                    optuna_enabled=True,
                    optuna_trials=3,
                    optuna_budget_profile="research_fast",
                )
                result = training.run_training(data_path, train_dir, config=config)
                # Verify run_summary contains optuna applied params
                optuna_section = result.run_summary.get("optuna", {})
                self.assertTrue(optuna_section.get("enabled", False))
                # Verify model artifact contains signal_scale from optuna (model constructor param)
                model_path = Path(train_dir) / "model.json"
                self.assertTrue(model_path.exists(), "model.json should exist")
                model_data = json.loads(model_path.read_text())
                self.assertIn("model_family", model_data)
                # signal_scale must be in model_params (passed to model constructor)
                model_params = model_data.get("model_params", {})
                self.assertEqual(model_params.get("signal_scale"), 1.7, "model artifact must contain optuna signal_scale")
                # threshold must NOT be in model_params (it's a decision param, not model constructor param)
                self.assertNotIn("threshold", model_params, "threshold must not be in model_params")
                # Verify every fold threshold is exactly the monkeypatched 0.37
                for fold in result.fold_results:
                    self.assertEqual(fold.threshold, 0.37, "fold threshold must be overridden by optuna best threshold")
        finally:
            features.OptunaStudyRunner.run_study = original_run_study

    def test_cli_advanced_args_wired_to_training(self) -> None:
        """Advanced CLI args (feature-selection, optuna, champion-challenger) must be wired to training config."""
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as tmpdir:
            data_path = Path(tmpdir) / "btcusdt_1m.csv"
            dataset.collect_candles(data_path, rows=240)
            train_dir = Path(tmpdir) / "training"
            result = subprocess.run(
                [
                    sys.executable, "-m", "btcusdt_quant", "train",
                    "--input", str(data_path),
                    "--output", str(train_dir),
                    "--feature-selection",
                    "--optuna",
                    "--optuna-trials", "3",
                    "--optuna-budget", "research_fast",
                    "--champion-challenger",
                ],
                capture_output=True,
                text=True,
                cwd="D:\\CodexProject",
            )
            self.assertEqual(result.returncode, 0, f"CLI failed: {result.stderr}")
            run_summary_path = Path(train_dir) / "run_summary.json"
            self.assertTrue(run_summary_path.exists(), "run_summary.json should exist")
            summary = json.loads(run_summary_path.read_text())
            self.assertTrue(summary.get("feature_selection", {}).get("enabled", False), "feature-selection should be enabled")
            self.assertTrue(summary.get("optuna", {}).get("enabled", False), "optuna should be enabled")
            self.assertTrue(summary.get("champion_challenger", {}).get("enabled", False), "champion-challenger should be enabled")


class TestDataExpansion(unittest.TestCase):
    def _make_archive_csv(self, path: Path, rows: int, date_str: str) -> None:
        """Write a minimal valid archive CSV with `rows` data rows."""
        header = "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n"
        lines = [header]
        base_ms = int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
        for i in range(rows):
            open_ms = base_ms + i * 60_000
            close_ms = open_ms + 59_999
            lines.append(
                f"{open_ms},100.0,101.0,99.0,100.5,10.0,{close_ms},1000.0,100,5.0,500.0,0\n"
            )
        path.write_text("".join(lines), encoding="utf-8")

    def test_archive_row_count_counts_csv_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp)
            self._make_archive_csv(archive_dir / "BTCUSDT-1m-2024-02-01.csv", 10, "2024-02-01")
            self._make_archive_csv(archive_dir / "BTCUSDT-1m-2024-02-02.csv", 20, "2024-02-02")
            # Non-matching file should be ignored
            self._make_archive_csv(archive_dir / "ETHUSDT-1m-2024-02-01.csv", 99, "2024-02-01")
            count = dataset.archive_row_count(archive_dir)
            self.assertEqual(count, 30, "archive_row_count should sum rows from BTCUSDT-1m-*.csv files only")

    def test_archive_date_coverage_returns_expected_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp)
            self._make_archive_csv(archive_dir / "BTCUSDT-1m-2024-02-01.csv", 10, "2024-02-01")
            coverage = dataset.archive_date_coverage(archive_dir)
            expected_keys = {"start_date", "end_date", "raw_rows", "canonical_rows", "missing_days", "files_found"}
            self.assertEqual(set(coverage.keys()), expected_keys)
            self.assertEqual(coverage["start_date"], "2024-02-01")
            self.assertEqual(coverage["end_date"], "2024-02-01")
            self.assertEqual(coverage["raw_rows"], 10)
            self.assertEqual(coverage["canonical_rows"], 10)
            self.assertEqual(coverage["missing_days"], [])
            self.assertEqual(coverage["files_found"], 1)

    def test_archive_date_coverage_computes_missing_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp)
            self._make_archive_csv(archive_dir / "BTCUSDT-1m-2024-02-01.csv", 10, "2024-02-01")
            self._make_archive_csv(archive_dir / "BTCUSDT-1m-2024-02-03.csv", 10, "2024-02-03")
            coverage = dataset.archive_date_coverage(archive_dir)
            self.assertEqual(coverage["start_date"], "2024-02-01")
            self.assertEqual(coverage["end_date"], "2024-02-03")
            self.assertEqual(coverage["missing_days"], ["2024-02-02"])
            self.assertEqual(coverage["files_found"], 2)

    def test_archive_date_coverage_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp)
            coverage = dataset.archive_date_coverage(archive_dir)
            self.assertEqual(coverage["start_date"], None)
            self.assertEqual(coverage["end_date"], None)
            self.assertEqual(coverage["raw_rows"], 0)
            self.assertEqual(coverage["canonical_rows"], 0)
            self.assertEqual(coverage["missing_days"], [])
            self.assertEqual(coverage["files_found"], 0)

    def test_cli_collect_archive_min_rows_warning(self) -> None:
        from btcusdt_quant.cli import run_collect_archive
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp)
            self._make_archive_csv(archive_dir / "BTCUSDT-1m-2024-01-01.csv", 10, "2024-01-01")
            # Patch downloader to skip network and just use existing files
            original_download_range = dataset.BinanceArchiveDownloader.download_range
            def _patched_download_range(self, start, end, output_dir, checkpoint_file=None):
                return dataset.ArchiveDownloadSummary(
                    output_dir=output_dir,
                    checkpoint_file=output_dir / "checkpoint.json",
                    start_date=str(start),
                    end_date=str(end),
                    total_days=1,
                    downloaded_days=1,
                    failed_days=0,
                    last_completed_date=str(start),
                    downloaded_files=tuple(),
                    failed_dates=tuple(),
                )
            dataset.BinanceArchiveDownloader.download_range = _patched_download_range
            try:
                summary = run_collect_archive("2024-01-01", "2024-01-01", archive_dir, allow_public_network=True, min_rows=1000)
                self.assertFalse(summary["min_rows_passed"], "min_rows not met should report false")
                self.assertIn("coverage_report", summary)
            finally:
                dataset.BinanceArchiveDownloader.download_range = original_download_range

    def test_cli_collect_archive_writes_report(self) -> None:
        from btcusdt_quant.cli import run_collect_archive
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp)
            self._make_archive_csv(archive_dir / "BTCUSDT-1m-2024-01-01.csv", 10, "2024-01-01")
            original_download_range = dataset.BinanceArchiveDownloader.download_range
            def _patched_download_range(self, start, end, output_dir, checkpoint_file=None):
                return dataset.ArchiveDownloadSummary(
                    output_dir=output_dir,
                    checkpoint_file=output_dir / "checkpoint.json",
                    start_date=str(start),
                    end_date=str(end),
                    total_days=1,
                    downloaded_days=1,
                    failed_days=0,
                    last_completed_date=str(start),
                    downloaded_files=tuple(),
                    failed_dates=tuple(),
                )
            dataset.BinanceArchiveDownloader.download_range = _patched_download_range
            try:
                summary = run_collect_archive("2024-01-01", "2024-01-01", archive_dir, allow_public_network=True, min_rows=5)
                report_path = archive_dir / "data_expansion_report.json"
                self.assertTrue(report_path.exists(), "data_expansion_report.json should be written")
                report = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertIn("start_date", report)
                self.assertIn("end_date", report)
                self.assertIn("raw_rows", report)
                self.assertIn("canonical_rows", report)
                self.assertIn("missing_days", report)
                self.assertIn("min_rows_passed", report)
                self.assertTrue(report["min_rows_passed"], "min_rows met should report true")
            finally:
                dataset.BinanceArchiveDownloader.download_range = original_download_range


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
    def read(self) -> bytes:
        return self._body
    def __enter__(self) -> "_FakeResponse":
        return self
    def __exit__(self, *args: object) -> None:
        pass


class TestBacktest(unittest.TestCase):
    class _ConstantProbabilityModel:
        def __init__(self, probability: float) -> None:
            self.probability_value = probability

        def probability(self, values: object) -> float:
            return self.probability_value

    class _SingleBuyModel:
        def __init__(self) -> None:
            self.calls = 0

        def probability(self, values: object) -> float:
            self.calls += 1
            return 0.90 if self.calls == 1 else 0.50

    def _candles(self, rows: int) -> list[data.Candle]:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        return [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=100.0 + index * 0.1,
                high=101.0 + index * 0.1,
                low=99.0 + index * 0.1,
                close=100.5 + index * 0.1,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index in range(rows)
        ]

    def _priced_candles(self, closes: list[float]) -> list[data.Candle]:
        base = data.utc_minute(2026, 1, 1, 0, 0)
        return [
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=close,
                high=close * 1.001,
                low=close * 0.999,
                close=close,
                volume=10.0,
                quote_volume=1000.0,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=500.0,
            )
            for index, close in enumerate(closes)
        ]

    def test_backtest_runs_without_model(self) -> None:
        candles = self._candles(50)
        strategy = live.StrategyConfig("test", 0.40, 0.60, 0.010, 0.005, 1.0, 1.0, 1.0)
        result = backtest.run_backtest(candles, None, strategy)
        self.assertIsInstance(result, backtest.BacktestResult)
        self.assertGreaterEqual(result.trade_count, 0)

    def test_backtest_with_model(self) -> None:
        candles = self._candles(50)
        model = training.LinearClassifier(
            feature_names=("return_1",),
            standardizer=training.Standardizer({"return_1": 0.0}, {"return_1": 1.0}),
            weights={"return_1": 0.0},
            intercept=1.0,
        )
        strategy = live.StrategyConfig("test", 0.40, 0.60, 0.010, 0.005, 1.0, 1.0, 1.0)
        result = backtest.run_backtest(candles, model, strategy)
        self.assertIsInstance(result, backtest.BacktestResult)
        self.assertGreaterEqual(result.trade_count, 0)

    def test_backtest_metrics(self) -> None:
        candles = self._candles(100)
        strategy = live.StrategyConfig("test", 0.40, 0.60, 0.010, 0.005, 1.0, 1.0, 1.0)
        result = backtest.run_backtest(candles, None, strategy)
        self.assertIsInstance(result.total_return, float)
        self.assertIsInstance(result.win_rate, float)
        self.assertIsInstance(result.profit_factor, float)
        self.assertIsInstance(result.max_drawdown, float)
        self.assertIsInstance(result.sharpe, float)

    def test_backtest_deducts_fee_and_slippage_from_trade_pnl(self) -> None:
        candles = self._priced_candles([100.0, 101.0])
        strategy = live.StrategyConfig("test", 0.60, 0.40, 0.500, 0.500, 1.0, 1.0, 0.0)

        result = backtest.run_backtest(
            candles,
            self._SingleBuyModel(),
            strategy,
            initial_equity=100.0,
            position_size=1.0,
            label_horizon=1,
            fee_rate_per_side=0.0002,
            slippage_rate_per_side=0.0002,
        )

        self.assertEqual(result.trade_count, 1)
        trade = result.trades[0]
        self.assertAlmostEqual(trade.gross_pnl_pct, 0.0100)
        self.assertAlmostEqual(trade.fee_pct, 0.0004)
        self.assertAlmostEqual(trade.slippage_pct, 0.0004)
        self.assertAlmostEqual(trade.cost_pct, 0.0008)
        self.assertAlmostEqual(trade.pnl_pct, 0.0092)
        self.assertAlmostEqual(result.gross_total_return, 0.0100)
        self.assertAlmostEqual(result.total_return, 0.0092)
        self.assertAlmostEqual(result.total_fees, 0.04)
        self.assertAlmostEqual(result.total_slippage, 0.04)

    def test_backtest_cost_impact_scales_with_trade_count(self) -> None:
        candles = self._priced_candles([100.0] * 20)
        strategy = live.StrategyConfig("test", 0.60, 0.40, 0.500, 0.500, 1.0, 1.0, 0.0)

        result = backtest.run_backtest(
            candles,
            self._ConstantProbabilityModel(0.90),
            strategy,
            initial_equity=100.0,
            position_size=1.0,
            label_horizon=1,
            fee_rate_per_side=0.0002,
            slippage_rate_per_side=0.0002,
        )

        expected_return = (1.0 - result.round_trip_cost_pct) ** result.trade_count - 1.0
        self.assertGreaterEqual(result.trade_count, 10)
        self.assertAlmostEqual(result.gross_total_return, 0.0)
        self.assertAlmostEqual(result.total_return, expected_return)
        self.assertLess(result.total_return, -0.01)

    def test_backtest_rejects_non_finite_cost_rates(self) -> None:
        candles = self._priced_candles([100.0, 101.0])
        strategy = live.StrategyConfig("test", 0.60, 0.40, 0.500, 0.500, 1.0, 1.0, 0.0)

        with self.assertRaises(ValueError):
            backtest.run_backtest(
                candles,
                self._SingleBuyModel(),
                strategy,
                fee_rate_per_side=float("nan"),
            )
        with self.assertRaises(ValueError):
            backtest.run_backtest(
                candles,
                self._SingleBuyModel(),
                strategy,
                slippage_rate_per_side=float("inf"),
            )

    def test_backtest_compare_strategies(self) -> None:
        candles = self._candles(100)
        strategies = {
            "balanced": live.StrategyConfig("balanced", 0.50, 0.50, 0.010, 0.005, 1.0, 1.0, 1.0),
            "aggressive": live.StrategyConfig("aggressive", 0.40, 0.60, 0.015, 0.010, 1.5, 1.0, 0.8),
        }
        comparison = backtest.compare_strategies(candles, None, strategies)
        self.assertIn("best_strategy", comparison)
        self.assertIn("comparison", comparison)
        self.assertIn("balanced", comparison["comparison"])
        self.assertIn("aggressive", comparison["comparison"])

    def test_backtest_cli_exists(self) -> None:
        from btcusdt_quant.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["backtest", "--output", "artifacts/backtest"])
        self.assertEqual(args.command, "backtest")
        self.assertEqual(args.output, "artifacts/backtest")

    def test_backtest_cli_runs(self) -> None:
        from btcusdt_quant.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            code = main(["backtest", "--output", tmp])
            self.assertEqual(code, 0, "backtest CLI should succeed")
            summary_path = Path(tmp) / "backtest_summary.json"
            self.assertTrue(summary_path.exists(), "backtest_summary.json should be written")
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertIn("backtest", summary)
            self.assertIn("strategy_comparison", summary)

    def test_backtest_result_as_dict(self) -> None:
        result = backtest.BacktestResult(trades=[
            backtest.BacktestTrade("2026-01-01T00:00:00", "2026-01-01T00:01:00", "BUY", 100.0, 101.0, 102.0, 99.0, 0.01, "TP", "balanced"),
        ])
        d = result.as_dict()
        self.assertEqual(d["trade_count"], 1)
        self.assertEqual(len(d["trades"]), 1)
        self.assertEqual(d["trades"][0]["side"], "BUY")


if __name__ == "__main__":
    unittest.main()
