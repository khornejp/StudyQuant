"""Tests for btcusdt_quant.edge_validation — the OOS edge-validation harnesses.

Deterministic: synthetic candles + fixed-probability stub models, no CatBoost.
These verify the harnesses wire run_backtest correctly and compute the verdicts
(cost survival, seed dispersion, shuffled-label vanish, 4-way interpretation),
not that any particular model has an edge.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from typing import Mapping, Sequence

from btcusdt_quant import cli, data, dataset, edge_validation, features, live
from btcusdt_quant.models import CentroidLinearClassifier


def _rising_candles(rows: int) -> list[data.Candle]:
    base = data.utc_minute(2026, 1, 2, 0, 0)
    candles: list[data.Candle] = []
    price = 100.0
    for index in range(rows):
        open_price = price
        price += 0.5
        candles.append(
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=open_price,
                high=max(open_price, price) * 1.002,
                low=min(open_price, price) * 0.999,
                close=price,
                volume=10.0,
                quote_volume=10.0 * price,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=5.0 * price,
            )
        )
    return candles


class _FixedModel:
    """Returns a constant probability for every bar."""

    def __init__(self, probability: float) -> None:
        self._p = probability

    @property
    def model_family(self) -> str:
        return "fixed"

    def probability(self, values: Mapping[str, float]) -> float:
        return self._p

    def as_dict(self) -> dict[str, object]:
        return {"model_family": "fixed", "probability": self._p}


class _LongBundle:
    """Minimal regime bundle that prices a long in the given regime."""

    def __init__(self, regime: str = "range", prob: float = 0.9) -> None:
        self.regime = regime
        self._p = prob
        self.long_models = {regime: _FixedModel(prob)}
        self.short_models: dict[str, object] = {}
        self.regime_thresholds = {regime: {"long": 0.3, "short": 0.99}}
        self.direction_policy = {regime: {"LONG"}}
        # Barrier the models were "labeled" on, so backtest's parity guard
        # verifies against the exec barrier instead of only warning.
        self.label_tp_pct = 0.005
        self.label_sl_pct = 0.005

    def has_side_probability(self, regime: str, side: str) -> bool:
        registry = self.long_models if side == "long" else self.short_models
        return regime in registry

    def probability_for(self, regime: str, side: str, features: Mapping[str, float]) -> float | None:
        registry = self.long_models if side == "long" else self.short_models
        model = registry.get(regime)
        return None if model is None else float(model.probability(features))


class _RangeDetector:
    """Stub causal detector: everything is the same regime."""

    def __init__(self, regime: str = "range") -> None:
        self.regime = regime

    def detect_all_directional(
        self,
        rv_values: Sequence[float],
        trend_slopes: Sequence[float],
        thresholds: dict[str, float] | None = None,
    ) -> list[str]:
        return [self.regime] * len(list(rv_values))


_BT_KW = dict(label_horizon=5, cooldown_bars=0, min_hold_bars=0, exec_tp_pct=0.005, exec_sl_pct=0.005)


class CostStressTests(unittest.TestCase):
    def test_levels_and_cost_reduces_net(self) -> None:
        candles = _rising_candles(60)
        model = _FixedModel(0.9)
        report = edge_validation.cost_stress(
            candles, model=model, long_threshold=0.6, short_threshold=0.99,
            base_fee_rate_per_side=0.0004, base_slippage_rate_per_side=0.0004, **_BT_KW,
        )
        self.assertEqual(set(report["levels"]), {"1x", "1.5x", "2x"})
        net_1x = report["levels"]["1x"]["net_total_return"]
        net_2x = report["levels"]["2x"]["net_total_return"]
        self.assertIsNotNone(net_1x)
        self.assertGreater(report["levels"]["1x"]["trade_count"], 0)
        # Same signals, more cost -> net cannot improve.
        self.assertLessEqual(net_2x, net_1x)
        self.assertIsInstance(report["survives_1_5x"], bool)

    def test_rejects_bad_multipliers(self) -> None:
        candles = _rising_candles(10)
        with self.assertRaises(ValueError):
            edge_validation.cost_stress(candles, model=_FixedModel(0.9), multipliers=())
        with self.assertRaises(ValueError):
            edge_validation.cost_stress(candles, model=_FixedModel(0.9), multipliers=(1.0, -1.0))


class CompareTrainedModelsTests(unittest.TestCase):
    def test_dispersion_and_baseline_delta(self) -> None:
        candles = _rising_candles(60)
        report = edge_validation.compare_trained_models(
            candles,
            {"a": _FixedModel(0.9), "b": _FixedModel(0.9)},
            baseline_label="a",
            long_threshold=0.6, short_threshold=0.99, **_BT_KW,
        )
        self.assertEqual(set(report["models"]), {"a", "b"})
        self.assertIn("net_total_return", report["dispersion"])
        self.assertEqual(report["dispersion"]["net_total_return"]["n"], 2)
        # Identical models -> identical net -> zero spread and zero delta.
        self.assertEqual(report["dispersion"]["net_total_return"]["stdev"], 0.0)
        self.assertEqual(report["net_delta_vs_baseline"]["b"], 0.0)

    def test_rejects_empty_and_bad_baseline(self) -> None:
        candles = _rising_candles(10)
        with self.assertRaises(ValueError):
            edge_validation.compare_trained_models(candles, {})
        with self.assertRaises(ValueError):
            edge_validation.compare_trained_models(candles, {"a": _FixedModel(0.9)}, baseline_label="missing")

    def test_non_string_keys_and_baseline_do_not_keyerror(self) -> None:
        # Regression: per_model is keyed by str(label); a raw int baseline must
        # still resolve for the delta lookup instead of raising KeyError.
        candles = _rising_candles(40)
        report = edge_validation.compare_trained_models(
            candles, {1: _FixedModel(0.9), 2: _FixedModel(0.9)}, baseline_label=1,
            long_threshold=0.6, short_threshold=0.99, **_BT_KW,
        )
        self.assertEqual(set(report["models"]), {"1", "2"})
        self.assertEqual(report["net_delta_vs_baseline"]["1"], 0.0)

    def test_controlled_kwarg_collision_raises_typeerror(self) -> None:
        # Regression: a run_backtest arg the harness sets itself must fail with a
        # clear TypeError, not Python's opaque "multiple values" from inside.
        candles = _rising_candles(10)
        with self.assertRaises(TypeError):
            edge_validation.compare_trained_models(candles, {"a": _FixedModel(0.9)}, model=_FixedModel(0.5))
        with self.assertRaises(TypeError):
            edge_validation.cost_stress(candles, model=_FixedModel(0.9), fee_rate_per_side=0.001)


class SeedAndAblationTests(unittest.TestCase):
    def test_seed_stability_labels_and_tags(self) -> None:
        candles = _rising_candles(50)
        report = edge_validation.seed_stability(
            candles, {1: _FixedModel(0.9), 2: _FixedModel(0.9)},
            long_threshold=0.6, short_threshold=0.99, **_BT_KW,
        )
        self.assertEqual(report["experiment"], "seed_stability")
        self.assertEqual(set(report["models"]), {"seed_1", "seed_2"})

    def test_ablation_requires_full_and_keys_deltas_off_it(self) -> None:
        candles = _rising_candles(50)
        with self.assertRaises(ValueError):
            edge_validation.feature_group_ablation(candles, {"no_trend": _FixedModel(0.9)})
        report = edge_validation.feature_group_ablation(
            candles, {"full": _FixedModel(0.9), "no_trend": _FixedModel(0.9)},
            long_threshold=0.6, short_threshold=0.99, **_BT_KW,
        )
        self.assertEqual(report["experiment"], "feature_group_ablation")
        self.assertEqual(report["baseline_label"], "full")
        self.assertIn("no_trend", report["net_delta_vs_baseline"])


class ShuffledLabelControlTests(unittest.TestCase):
    def test_edge_vanishes_when_shuffled_model_does_not_trade(self) -> None:
        candles = _rising_candles(60)
        # Real model enters longs on a rising series (profits); the "shuffled"
        # stand-in never clears the threshold, so it takes no trades (net 0).
        # short_threshold 0.05: real (0.9) buys, shuffled (0.1) is above the
        # short cutoff and below the long cutoff -> HOLD, no trades.
        report = edge_validation.shuffled_label_control(
            candles,
            real_model=_FixedModel(0.9),
            shuffled_model=_FixedModel(0.1),
            long_threshold=0.6, short_threshold=0.05, **_BT_KW,
        )
        self.assertEqual(report["experiment"], "shuffled_label_control")
        self.assertGreater(report["models"]["real"]["trade_count"], 0)
        self.assertEqual(report["models"]["shuffled"]["trade_count"], 0)
        self.assertIsInstance(report["edge_vanished"], bool)
        # real net > 0 on the rising series, shuffled net == 0 -> edge vanished.
        self.assertTrue(report["edge_vanished"])


class RoutingComparisonTests(unittest.TestCase):
    def test_four_way_structure_and_interpretation(self) -> None:
        candles = _rising_candles(60)
        bundle = _LongBundle("range")
        report = edge_validation.routing_comparison(
            candles,
            models_by_regime={"range": bundle},
            unified_model=_FixedModel(0.9),
            regime_detector=_RangeDetector("range"),
            default_regime="range",
            long_threshold=0.6, short_threshold=0.99, **_BT_KW,
        )
        self.assertEqual(set(report["arms"]), {"unified", "predicted"})
        self.assertIn("interpretation", report)
        self.assertIn("detector_diagnostics", report)

    def test_oracle_arm_added_with_user_regime_periods(self) -> None:
        from btcusdt_quant import dataset

        candles = _rising_candles(60)
        periods = [
            dataset.UserRegimePeriod("range", candles[0].open_time, candles[-1].open_time + timedelta(minutes=1)),
        ]
        report = edge_validation.routing_comparison(
            candles,
            models_by_regime={"range": _LongBundle("range")},
            unified_model=_FixedModel(0.9),
            regime_detector=_RangeDetector("range"),
            user_regime_periods=periods,
            default_regime="range",
            long_threshold=0.6, short_threshold=0.99, **_BT_KW,
        )
        self.assertEqual(set(report["arms"]), {"unified", "predicted", "oracle"})

    def test_requires_exactly_one_predicted_source(self) -> None:
        candles = _rising_candles(20)
        with self.assertRaises(ValueError):  # zero sources
            edge_validation.routing_comparison(
                candles, models_by_regime={"range": _LongBundle("range")}, unified_model=_FixedModel(0.9),
            )
        with self.assertRaises(ValueError):  # two sources
            edge_validation.routing_comparison(
                candles, models_by_regime={"range": _LongBundle("range")}, unified_model=_FixedModel(0.9),
                regime_detector=_RangeDetector(), regime_classifier_model=object(),
            )

    def test_requires_unified_model(self) -> None:
        candles = _rising_candles(20)
        with self.assertRaises(ValueError):
            edge_validation.routing_comparison(
                candles, models_by_regime={"range": _LongBundle("range")}, unified_model=None,
                regime_detector=_RangeDetector(),
            )

    def test_accepts_prebuilt_feature_rows_for_metrics_parity(self) -> None:
        # The CLI passes prebuilt rows (with F16 metrics merged) for the
        # unified/predicted arms and a separate periods-built set for oracle.
        candles = _rising_candles(80)
        rows = dataset.build_feature_rows(candles)
        periods = [dataset.UserRegimePeriod("range", candles[0].open_time, candles[-1].open_time + timedelta(minutes=1))]
        oracle_rows = dataset.build_feature_rows(candles, user_regime_periods=periods)
        report = edge_validation.routing_comparison(
            candles,
            models_by_regime={"range": _LongBundle("range")},
            unified_model=_FixedModel(0.9),
            regime_detector=_RangeDetector("range"),
            feature_rows=rows,
            oracle_feature_rows=oracle_rows,
            default_regime="range",
            long_threshold=0.6, short_threshold=0.99, **_BT_KW,
        )
        self.assertEqual(set(report["arms"]), {"unified", "predicted", "oracle"})


class CliEdgeValidateSmokeTests(unittest.TestCase):
    def test_edge_validate_writes_report(self) -> None:
        # Regime-bundle artifact + unified model + --auto-regime predicted source
        # -> both cost_stress and routing_comparison run; exit 0; report written.
        candles = _rising_candles(150)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "candles.csv"
            dataset.write_candles_csv(csv_path, candles)

            artifact = root / "bundle"
            (artifact / "regime_range").mkdir(parents=True)
            model = CentroidLinearClassifier(feature_names=["return_1"]).fit([[0.0], [0.1]], [1, 0])
            (artifact / "regime_range" / "model.json").write_text(json.dumps(model.as_dict()), encoding="utf-8")
            (artifact / "regime_run_summary.json").write_text(json.dumps({
                "regime_results": {"range": {"mean_test_f1": 0.1}},
                "default_regime": "range",
                "tp_pct": 0.005, "sl_pct": 0.005, "threshold_horizon": 5,
                "regime_detector": {"thresholds": {"dir_threshold": 0.0}, "diagnostics": {}, "config": features.RegimeDetector().config_dict()},
            }), encoding="utf-8")

            unified = root / "unified.json"
            unified.write_text(json.dumps(CentroidLinearClassifier(feature_names=["return_1"]).fit([[0.0], [0.1]], [1, 0]).as_dict()), encoding="utf-8")

            out = root / "out"
            code = cli.main([
                "edge-validate", "--input", str(csv_path), "--output", str(out),
                "--model-artifact", str(artifact), "--unified-artifact", str(unified),
                "--auto-regime", "--horizon", "5", "--exec-tp-pct", "0.005", "--exec-sl-pct", "0.005",
                "--cost-multipliers", "1.0,2.0",
                "--backtest-start", "2026-01-02", "--backtest-end", "2026-01-02",
            ])
            self.assertEqual(code, 0)
            report = json.loads((out / "edge_validation_report.json").read_text(encoding="utf-8"))
        self.assertIn("cost_stress", report)
        self.assertEqual(set(report["cost_stress"]["levels"]), {"1x", "2x"})
        self.assertIn("routing_comparison", report)
        self.assertEqual(set(report["routing_comparison"]["arms"]), {"unified", "predicted"})

    def test_edge_validate_skips_routing_when_unified_missing(self) -> None:
        # If --unified-artifact is given but unloadable (e.g. its train phase
        # failed), routing is skipped gracefully; cost_stress still runs.
        candles = _rising_candles(120)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "candles.csv"
            dataset.write_candles_csv(csv_path, candles)
            artifact = root / "bundle"
            (artifact / "regime_range").mkdir(parents=True)
            model = CentroidLinearClassifier(feature_names=["return_1"]).fit([[0.0], [0.1]], [1, 0])
            (artifact / "regime_range" / "model.json").write_text(json.dumps(model.as_dict()), encoding="utf-8")
            (artifact / "regime_run_summary.json").write_text(json.dumps({
                "regime_results": {"range": {"mean_test_f1": 0.1}},
                "default_regime": "range",
                "tp_pct": 0.005, "sl_pct": 0.005, "threshold_horizon": 5,
                "regime_detector": {"thresholds": {"dir_threshold": 0.0}, "diagnostics": {}, "config": features.RegimeDetector().config_dict()},
            }), encoding="utf-8")
            out = root / "out"
            code = cli.main([
                "edge-validate", "--input", str(csv_path), "--output", str(out),
                "--model-artifact", str(artifact),
                "--unified-artifact", str(root / "does_not_exist.json"),
                "--auto-regime", "--horizon", "5", "--exec-tp-pct", "0.005", "--exec-sl-pct", "0.005",
                "--cost-multipliers", "1.0",
            ])
            self.assertEqual(code, 0)
            report = json.loads((out / "edge_validation_report.json").read_text(encoding="utf-8"))
        self.assertIn("cost_stress", report)
        self.assertIn("routing_comparison_skipped", report)
        self.assertNotIn("routing_comparison", report)


if __name__ == "__main__":
    unittest.main()
