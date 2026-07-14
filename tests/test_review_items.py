"""Tests for the ML4T/G-Research review items (APPLICATION_REVIEW_PLAN.md 1-6).

Covers: Kelly sizing (risk.py), multi-horizon ensemble (ensemble.py),
leakage heuristics + fold-wise IC (ic_diagnostic.py), OU half-life
(verify_range_halflife.py), and gross/net Sharpe (backtest.py).
"""
from __future__ import annotations

import copy
import json
import math
import random
import unittest
from typing import Mapping

from btcusdt_quant import features, risk, training
from btcusdt_quant.backtest import (
    BacktestResult,
    BacktestTrade,
    check_execution_barrier_parity,
    json_safe,
    kelly_fraction_for_entry,
    per_trade_sharpe,
    run_backtest,
)
from btcusdt_quant.ensemble import MultiHorizonEnsembleAdapter

import ic_diagnostic
import verify_range_halflife


class KellySizingTests(unittest.TestCase):
    def test_expected_edge_known_value(self) -> None:
        # p=0.6, tp=1%, sl=1% -> 0.6*0.01 - 0.4*0.01 = 0.002
        self.assertAlmostEqual(risk.expected_edge(0.6, 0.01, 0.01), 0.002)

    def test_expected_edge_nets_out_round_trip_cost(self) -> None:
        # Pipeline defaults: tp=0.30%, sl=0.15%, round trip 0.08%.
        # gross break-even p = sl/(tp+sl) = 0.3333
        # net   break-even p = (sl+rt)/((tp-rt)+(sl+rt)) = 0.5111
        tp, sl, rt = 0.003, 0.0015, 0.0008
        self.assertGreater(risk.expected_edge(0.40, tp, sl), 0.0, "gross edge is positive at p=0.40")
        self.assertLess(risk.expected_edge(0.40, tp, sl, rt), 0.0, "net edge must be negative at p=0.40")
        self.assertAlmostEqual(risk.expected_edge(0.5111111111, tp, sl, rt), 0.0, places=9)
        self.assertGreater(risk.expected_edge(0.60, tp, sl, rt), 0.0)

    def test_expected_edge_refuses_when_tp_below_cost(self) -> None:
        # TP cannot even cover the round trip -> a win is still a loss
        self.assertLess(risk.expected_edge(1.0, 0.0005, 0.001, round_trip_cost=0.0008), 0.0)
        with self.assertRaises(ValueError):
            risk.expected_edge(0.6, 0.01, 0.01, round_trip_cost=-0.001)

    def test_kelly_leverage_for_signal_threads_cost(self) -> None:
        recent = [0.0005, -0.0005] * 500
        cfg = risk.KellySizingConfig(kelly_multiplier=0.5, holding_period_bars=60)
        args = (0.40, 0.003, 0.0015, recent)
        self.assertGreater(risk.kelly_leverage_for_signal(*args, config=cfg, cap=1.0), 0.0)
        self.assertEqual(risk.kelly_leverage_for_signal(*args, config=cfg, cap=1.0, round_trip_cost=0.0008), 0.0)

    def test_expected_edge_validates_inputs(self) -> None:
        with self.assertRaises(ValueError):
            risk.expected_edge(1.5, 0.01, 0.01)
        with self.assertRaises(ValueError):
            risk.expected_edge(0.5, -0.01, 0.01)

    def test_kelly_leverage_half_kelly_and_cap(self) -> None:
        # f* = m/s^2 = 0.002/0.0001 = 20; half-Kelly = 10; uncapped
        config = risk.KellySizingConfig(kelly_multiplier=0.5)
        self.assertAlmostEqual(risk.kelly_leverage(0.002, 0.0001, config), 10.0)
        # max_leverage acts as a hard cap on the Kelly output
        self.assertAlmostEqual(risk.kelly_leverage(0.002, 0.0001, config, max_leverage=3.0), 3.0)

    def test_kelly_leverage_no_edge_or_no_variance_means_no_bet(self) -> None:
        self.assertEqual(risk.kelly_leverage(0.0, 0.0001), 0.0)
        self.assertEqual(risk.kelly_leverage(-0.001, 0.0001), 0.0)
        self.assertEqual(risk.kelly_leverage(0.002, 0.0), 0.0)
        self.assertEqual(risk.kelly_leverage(0.002, float("nan")), 0.0)

    def test_return_variance_skips_non_finite_and_respects_lookback(self) -> None:
        returns = [0.01, float("nan"), -0.01, 0.01, -0.01]
        # finite values: [0.01, -0.01, 0.01, -0.01], mean 0, var 1e-4
        self.assertAlmostEqual(risk.return_variance(returns), 1e-4)
        self.assertEqual(risk.return_variance([0.01]), 0.0)

    def test_return_variance_lookback_counts_bars_not_finite_samples(self) -> None:
        # 10 old high-vol bars followed by a 5-bar window with one NaN gap:
        # lookback=5 must see ONLY the last 5 bars (NaN skipped inside the
        # window), never reach back into the 0.05 regime to refill the window.
        returns = [0.05] * 10 + [0.01, -0.01, float("nan"), 0.01, -0.01]
        self.assertAlmostEqual(risk.return_variance(returns, lookback=5), 1e-4)
        # An all-NaN window yields no estimate (0.0 -> no bet), not old data
        self.assertEqual(risk.return_variance([0.05] * 10 + [float("nan")] * 3, lookback=3), 0.0)

    def test_kelly_leverage_for_signal_end_to_end(self) -> None:
        rng = random.Random(7)
        recent = [rng.gauss(0.0, 0.01) for _ in range(2000)]
        policy = risk.RiskPolicy(max_leverage=2.0)
        lev = risk.kelly_leverage_for_signal(0.6, 0.01, 0.01, recent, policy)
        self.assertGreater(lev, 0.0)
        # With per-bar var ~1e-4 scaled by holding_period_bars=60, half-Kelly
        # is ~0.17 -- the output must be DYNAMIC (below the cap), not pinned
        # to max_leverage by a units mismatch.
        self.assertLess(lev, 2.0)
        # A coin-flip signal has no edge -> no bet regardless of variance
        self.assertEqual(risk.kelly_leverage_for_signal(0.5, 0.01, 0.01, recent, policy), 0.0)

    def test_kelly_scales_bar_variance_to_trade_horizon(self) -> None:
        # Deterministic returns with exact per-bar variance 1e-4, holding 60
        # bars -> trade variance 6e-3; edge 0.002 -> f = 0.5*0.002/6e-3 = 1/6.
        recent = [0.01, -0.01] * 500
        config = risk.KellySizingConfig(kelly_multiplier=0.5, holding_period_bars=60)
        lev = risk.kelly_leverage_for_signal(0.6, 0.01, 0.01, recent, risk.RiskPolicy(max_leverage=10.0), config)
        self.assertAlmostEqual(lev, (0.5 * 0.002) / (1e-4 * 60), places=6)

    def test_config_validation(self) -> None:
        with self.assertRaises(ValueError):
            risk.KellySizingConfig(kelly_multiplier=0.0)
        with self.assertRaises(ValueError):
            risk.KellySizingConfig(kelly_multiplier=1.5)
        with self.assertRaises(ValueError):
            risk.KellySizingConfig(variance_lookback_bars=1)


class KellyBacktestWiringTests(unittest.TestCase):
    def _config(self) -> risk.KellySizingConfig:
        return risk.KellySizingConfig(kelly_multiplier=0.5, variance_lookback_bars=1000, holding_period_bars=60)

    def test_fraction_from_actual_barriers_known_value(self) -> None:
        # edge = 0.6*0.01 - 0.4*0.005 = 0.004; bar var 1e-4 * 60 = 6e-3
        # f = 0.5 * 0.004 / 6e-3 = 1/3, below the cap of 10
        window = [0.01, -0.01] * 500
        fraction = kelly_fraction_for_entry(self._config(), 0.6, 100.0, 101.0, 99.5, window, cap=10.0)
        self.assertAlmostEqual(fraction, (0.5 * 0.004) / (1e-4 * 60), places=9)

    def test_fraction_is_capped_by_position_size(self) -> None:
        window = [0.01, -0.01] * 500
        fraction = kelly_fraction_for_entry(self._config(), 0.6, 100.0, 101.0, 99.5, window, cap=0.1)
        self.assertAlmostEqual(fraction, 0.1)

    def test_no_probability_falls_back_to_cap(self) -> None:
        window = [0.01, -0.01] * 500
        self.assertEqual(kelly_fraction_for_entry(self._config(), None, 100.0, 101.0, 99.5, window, cap=0.1), 0.1)

    def test_negative_edge_skips_entry(self) -> None:
        # p=0.3 with symmetric barriers -> edge = 0.3*0.01 - 0.7*0.01 < 0
        window = [0.01, -0.01] * 500
        self.assertEqual(kelly_fraction_for_entry(self._config(), 0.3, 100.0, 101.0, 99.0, window, cap=0.1), 0.0)

    def test_unusable_variance_skips_entry(self) -> None:
        self.assertEqual(kelly_fraction_for_entry(self._config(), 0.9, 100.0, 101.0, 99.0, [], cap=0.1), 0.0)

    def _make_candles(self, n: int) -> list:
        from datetime import timedelta
        from btcusdt_quant import data
        rng = random.Random(99)
        base = data.utc_minute(2026, 1, 2, 0, 0)
        candles = []
        price = 100000.0
        for index in range(n):
            open_price = price
            price += rng.gauss(20.0, 60.0)
            candles.append(
                data.Candle(
                    open_time=base + timedelta(minutes=index),
                    open=open_price,
                    high=max(open_price, price) + 10.0,
                    low=min(open_price, price) - 10.0,
                    close=price,
                    volume=10.0,
                    quote_volume=10.0 * price,
                    number_of_trades=100,
                    taker_buy_base_volume=5.0,
                    taker_buy_quote_volume=5.0 * price,
                )
            )
        return candles

    def test_run_backtest_kelly_sizes_every_trade_below_cap(self) -> None:
        class _AlwaysLong:
            def probability(self, values) -> float:
                return 0.9

        candles = self._make_candles(400)
        config = risk.KellySizingConfig(kelly_multiplier=0.5, variance_lookback_bars=120, holding_period_bars=10)
        result = run_backtest(
            candles,
            model=_AlwaysLong(),
            position_size=0.1,
            label_horizon=10,
            cooldown_bars=0,
            long_threshold=0.6,
            short_threshold=0.01,
            kelly_config=config,
        )
        self.assertGreater(result.trade_count, 0, "expected trades from the always-long stub")
        for trade in result.trades:
            self.assertIsNotNone(trade.position_size_used)
            self.assertGreater(trade.position_size_used, 0.0)
            self.assertLessEqual(trade.position_size_used, 0.1)
        self.assertTrue(result.kelly_sizing.get("enabled"))
        self.assertEqual(result.kelly_sizing.get("trades_sized"), result.trade_count)

    def test_kelly_refuses_shorts_on_single_model_path(self) -> None:
        # Single-model paths expose only P(long_success); its complement is
        # NOT P(short_success) (label=0 is mostly timeouts). Kelly must not
        # invent a short win probability -- it refuses the entry and reports
        # the refusal, so the run is visibly long-only rather than silently
        # sized on a fabricated edge.
        class _AlwaysShort:
            def probability(self, values) -> float:
                return 0.1

        candles = self._make_candles(400)
        config = risk.KellySizingConfig(kelly_multiplier=0.5, variance_lookback_bars=120, holding_period_bars=10)
        result = run_backtest(
            candles,
            model=_AlwaysShort(),
            position_size=0.1,
            label_horizon=10,
            cooldown_bars=0,
            long_threshold=0.99,
            short_threshold=0.3,
            kelly_config=config,
        )
        self.assertEqual(result.trade_count, 0, "single-model shorts must not be Kelly-sized")
        self.assertGreater(result.kelly_sizing["shorts_skipped_no_short_model"], 0)
        self.assertEqual(result.kelly_sizing["entries_skipped_no_edge"], 0, "refusal must not be misreported as a no-edge skip")

    def test_kelly_sizes_shorts_when_short_model_exists(self) -> None:
        # The regime-bundle path carries a dedicated short model whose output
        # IS P(short_success), so Kelly can size shorts there. The bundle -- not
        # the bar loop -- answers whether a side is priceable.
        class _ShortBundle:
            direction_policy = {"trend": {"SHORT"}}
            long_models: dict = {}
            short_models = {"trend": _StubModel(0.9)}
            regime_thresholds = {"trend": {"long": 0.99, "short": 0.2}}

            def has_side_probability(self, regime, side):
                registry = self.long_models if side == "long" else self.short_models
                return regime in registry

            def probability_for(self, regime, side, features):
                registry = self.long_models if side == "long" else self.short_models
                model = registry.get(regime)
                return None if model is None else float(model.probability(features))

        import dataclasses as _dc
        from btcusdt_quant import dataset as _ds

        candles = self._make_candles(400)
        rows = [_dc.replace(r, user_regime="trend") for r in _ds.build_feature_rows(candles)]
        config = risk.KellySizingConfig(kelly_multiplier=0.5, variance_lookback_bars=120, holding_period_bars=10)
        result = run_backtest(
            candles,
            models_by_regime={"trend": _ShortBundle()},
            feature_rows=rows,
            position_size=0.1,
            label_horizon=10,
            cooldown_bars=0,
            kelly_config=config,
        )
        self.assertEqual(result.kelly_sizing["shorts_skipped_no_short_model"], 0)
        self.assertGreater(result.trade_count, 0, "shorts with a real short model must be sized")
        for trade in result.trades:
            self.assertEqual(trade.side, "SELL")
            self.assertGreater(trade.position_size_used, 0.0)

    def test_kelly_skips_stay_out_of_signal_counts(self) -> None:
        # Whatever the skip count turns out to be, it must live in
        # kelly_sizing, not pollute the per-bar signal_counts histogram.
        class _WeakLong:
            def probability(self, values) -> float:
                return 0.62

        candles = self._make_candles(300)
        config = risk.KellySizingConfig(kelly_multiplier=0.5, variance_lookback_bars=120, holding_period_bars=10)
        result = run_backtest(
            candles,
            model=_WeakLong(),
            position_size=0.1,
            label_horizon=10,
            cooldown_bars=0,
            long_threshold=0.6,
            short_threshold=0.01,
            kelly_config=config,
        )
        self.assertNotIn("KELLY_SKIP", result.signal_counts)
        self.assertIn("entries_skipped_no_edge", result.kelly_sizing)
        self.assertEqual(result.trade_count, result.kelly_sizing.get("trades_sized"))

    def test_run_backtest_without_kelly_keeps_constant_size(self) -> None:
        class _AlwaysLong:
            def probability(self, values) -> float:
                return 0.9

        candles = self._make_candles(300)
        result = run_backtest(
            candles,
            model=_AlwaysLong(),
            position_size=0.1,
            label_horizon=10,
            cooldown_bars=0,
            long_threshold=0.6,
            short_threshold=0.01,
        )
        self.assertGreater(result.trade_count, 0)
        for trade in result.trades:
            self.assertIsNone(trade.position_size_used)
        self.assertEqual(result.kelly_sizing, {})


class KellyLiveSizerTests(unittest.TestCase):
    def test_kelly_notional_accepted_and_dynamic(self) -> None:
        from btcusdt_quant import live
        recent = [0.01, -0.01] * 500  # per-bar var exactly 1e-4
        config = risk.KellySizingConfig(kelly_multiplier=0.5, holding_period_bars=60)
        sizing = live.PositionSizer().kelly_notional(
            entry_price=100.0,
            account_balance_usdt=10000.0,
            probability=0.6,
            tp_pct=0.01,
            sl_pct=0.01,
            recent_returns=recent,
            max_trade_notional_ratio=0.5,
            leverage=1.0,
            min_qty=0.001,
            qty_step=0.001,
            max_notional_fraction=0.5,
        )
        self.assertTrue(sizing.accepted, sizing.reason)
        # f = 0.5*0.002/(1e-4*60) = 1/6 -> notional 10000/6, dynamic (below the 0.5 cap ratio)
        self.assertAlmostEqual(sizing.notional, 10000.0 * (0.5 * 0.002) / (1e-4 * 60), places=6)

    def test_kelly_notional_rejects_no_edge(self) -> None:
        from btcusdt_quant import live
        recent = [0.01, -0.01] * 500
        sizing = live.PositionSizer().kelly_notional(
            entry_price=100.0,
            account_balance_usdt=10000.0,
            probability=0.5,
            tp_pct=0.01,
            sl_pct=0.01,
            recent_returns=recent,
            max_trade_notional_ratio=0.5,
            leverage=1.0,
            min_qty=0.001,
            qty_step=0.001,
            max_notional_fraction=0.5,
        )
        self.assertFalse(sizing.accepted)
        self.assertEqual(sizing.reason, "kelly_no_edge_or_variance")

    def test_kelly_notional_clamps_to_max_notional_fraction(self) -> None:
        # Kelly cap must be min(static ratio, account guard): with ratio 0.5
        # but max_notional_fraction 0.3, a large raw Kelly must CLAMP to 0.3
        # and be accepted -- not hard-reject a positive-edge entry.
        from btcusdt_quant import live
        recent = [0.001, -0.001] * 500  # tiny variance -> huge raw Kelly
        sizing = live.PositionSizer().kelly_notional(
            entry_price=100.0,
            account_balance_usdt=10000.0,
            probability=0.9,
            tp_pct=0.01,
            sl_pct=0.01,
            recent_returns=recent,
            max_trade_notional_ratio=0.5,
            leverage=1.0,
            min_qty=0.001,
            qty_step=0.001,
            max_notional_fraction=0.3,
        )
        self.assertTrue(sizing.accepted, sizing.reason)
        self.assertAlmostEqual(sizing.notional, 10000.0 * 0.3)

    def test_kelly_leverage_for_signal_explicit_cap(self) -> None:
        recent = [0.001, -0.001] * 500
        lev = risk.kelly_leverage_for_signal(0.9, 0.01, 0.01, recent, cap=0.25)
        self.assertAlmostEqual(lev, 0.25)

    def test_kelly_notional_capped_by_static_ratio(self) -> None:
        from btcusdt_quant import live
        recent = [0.001, -0.001] * 500  # tiny variance -> huge raw Kelly
        sizing = live.PositionSizer().kelly_notional(
            entry_price=100.0,
            account_balance_usdt=10000.0,
            probability=0.9,
            tp_pct=0.01,
            sl_pct=0.01,
            recent_returns=recent,
            max_trade_notional_ratio=0.05,
            leverage=1.0,
            min_qty=0.001,
            qty_step=0.001,
            max_notional_fraction=0.5,
        )
        self.assertTrue(sizing.accepted, sizing.reason)
        self.assertAlmostEqual(sizing.notional, 10000.0 * 0.05)


class _StubModel:
    """Minimal ModelAdapter stand-in returning a fixed probability."""

    def __init__(self, probability: float) -> None:
        self._probability = probability

    @property
    def model_family(self) -> str:
        return "stub"

    def probability(self, values: Mapping[str, float]) -> float:
        return self._probability

    def as_dict(self) -> dict[str, object]:
        return {"model_family": "stub", "probability": self._probability}


class MultiHorizonEnsembleTests(unittest.TestCase):
    def test_probability_is_weighted_average(self) -> None:
        adapter = MultiHorizonEnsembleAdapter(
            feature_names=("f1",),
            horizons=(30, 60),
            horizon_models=(_StubModel(0.8), _StubModel(0.4)),
            weights=(0.75, 0.25),
        )
        self.assertAlmostEqual(adapter.probability({"f1": 0.0}), 0.75 * 0.8 + 0.25 * 0.4)
        self.assertEqual(adapter.model_family, "multi_horizon_ensemble")

    def test_unnormalized_weights_are_handled(self) -> None:
        adapter = MultiHorizonEnsembleAdapter(
            feature_names=("f1",),
            horizons=(30, 60),
            horizon_models=(_StubModel(0.8), _StubModel(0.4)),
            weights=(3.0, 1.0),
        )
        self.assertAlmostEqual(adapter.probability({"f1": 0.0}), 0.75 * 0.8 + 0.25 * 0.4)

    def test_predict_proba_maps_rows_to_features(self) -> None:
        adapter = MultiHorizonEnsembleAdapter(
            feature_names=("f1", "f2"),
            horizons=(30,),
            horizon_models=(_StubModel(0.7),),
            weights=(1.0,),
        )
        self.assertEqual(adapter.predict_proba([[1.0, 2.0], [3.0, 4.0]]), [0.7, 0.7])

    def test_invalid_construction_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MultiHorizonEnsembleAdapter(
                feature_names=("f1",),
                horizons=(30, 60),
                horizon_models=(_StubModel(0.5),),
                weights=(1.0,),
            )
        with self.assertRaises(ValueError):
            MultiHorizonEnsembleAdapter(
                feature_names=("f1",),
                horizons=(30,),
                horizon_models=(_StubModel(0.5),),
                weights=(-1.0,),
            )
        with self.assertRaises(ValueError):
            MultiHorizonEnsembleAdapter(
                feature_names=("f1",),
                horizons=(),
                horizon_models=(),
                weights=(),
            )

    def test_fit_is_blocked(self) -> None:
        adapter = MultiHorizonEnsembleAdapter(
            feature_names=("f1",),
            horizons=(30,),
            horizon_models=(_StubModel(0.5),),
            weights=(1.0,),
        )
        with self.assertRaises(RuntimeError):
            adapter.fit([[0.0]], [0])

    def test_as_dict_contains_all_submodels(self) -> None:
        adapter = MultiHorizonEnsembleAdapter(
            feature_names=("f1",),
            horizons=(30, 60),
            horizon_models=(_StubModel(0.8), _StubModel(0.4)),
            weights=(0.5, 0.5),
        )
        payload = adapter.as_dict()
        self.assertEqual(payload["model_family"], "multi_horizon_ensemble")
        self.assertEqual(payload["horizons"], [30, 60])
        self.assertEqual(len(payload["horizon_models"]), 2)


class LeakageHeuristicTests(unittest.TestCase):
    def test_forward_beats_past_is_flagged(self) -> None:
        self.assertIn("fwd>past", ic_diagnostic._leak_flags(ic_now=0.20, ic_lag1=0.19, ic_past=0.05))

    def test_lag1_collapse_is_flagged(self) -> None:
        self.assertIn("lag1-collapse", ic_diagnostic._leak_flags(ic_now=0.08, ic_lag1=0.01, ic_past=0.20))

    def test_causal_feature_is_clean(self) -> None:
        # Modest IC, survives a one-bar lag, remembers the past more than
        # it predicts the future: the profile of a legitimate feature.
        self.assertEqual(ic_diagnostic._leak_flags(ic_now=0.03, ic_lag1=0.028, ic_past=0.15), [])

    def test_past_returns_mirror_forward_returns(self) -> None:
        class _C:
            def __init__(self, close: float) -> None:
                self.close = close

        candles = [_C(100.0), _C(110.0), _C(121.0)]
        past = ic_diagnostic._past_returns(candles, 1)
        self.assertTrue(math.isnan(past[0]))
        self.assertAlmostEqual(past[1], 0.10)
        self.assertAlmostEqual(past[2], 0.10)


class FoldICTests(unittest.TestCase):
    def test_consistent_signal_has_low_fold_std(self) -> None:
        rng = random.Random(11)
        x = [rng.gauss(0.0, 1.0) for _ in range(1000)]
        y = [v + rng.gauss(0.0, 0.5) for v in x]
        mean, std, folds = ic_diagnostic._fold_ic_stats(x, y, 5)
        self.assertEqual(folds, 5)
        self.assertGreater(mean, 0.5)
        self.assertLess(std, 0.2)

    def test_sign_flipping_signal_has_high_fold_std(self) -> None:
        rng = random.Random(12)
        x = [rng.gauss(0.0, 1.0) for _ in range(1000)]
        # Correlation +1 in even folds, -1 in odd folds -> unstable
        y = [v if (i * 5 // 1000) % 2 == 0 else -v for i, v in enumerate(x)]
        mean, std, folds = ic_diagnostic._fold_ic_stats(x, y, 5)
        self.assertEqual(folds, 5)
        self.assertGreater(std, abs(mean))

    def test_too_little_data_reports_zero_folds(self) -> None:
        mean, std, folds = ic_diagnostic._fold_ic_stats([1.0] * 40, [1.0] * 40, 5)
        self.assertEqual(folds, 0)


class CachedSpearmanTests(unittest.TestCase):
    def test_cached_path_matches_exact_path(self) -> None:
        rng = random.Random(21)
        x = [rng.gauss(0.0, 1.0) for _ in range(500)]
        y = [v * 0.5 + rng.gauss(0.0, 1.0) for v in x]
        cache = ic_diagnostic._make_y_cache(y)
        self.assertIsNotNone(cache)
        exact = ic_diagnostic._spearman_ic(x, y)
        cached = ic_diagnostic._spearman_ic_cached(x, y, cache)
        self.assertAlmostEqual(cached[0], exact[0], places=12)
        self.assertEqual(cached[1], exact[1])

    def test_non_finite_x_falls_back_to_exact_path(self) -> None:
        rng = random.Random(22)
        x = [rng.gauss(0.0, 1.0) for _ in range(500)]
        y = [v * 0.5 + rng.gauss(0.0, 1.0) for v in x]
        x[3] = float("nan")
        cache = ic_diagnostic._make_y_cache(y)
        exact = ic_diagnostic._spearman_ic(x, y)
        cached = ic_diagnostic._spearman_ic_cached(x, y, cache)
        self.assertAlmostEqual(cached[0], exact[0], places=12)
        self.assertEqual(cached[1], exact[1])

    def test_cache_refuses_non_finite_y(self) -> None:
        y = [1.0] * 100
        y[50] = float("nan")
        self.assertIsNone(ic_diagnostic._make_y_cache(y))


class HalfLifeTests(unittest.TestCase):
    def test_ou_process_recovers_known_halflife(self) -> None:
        # dz = theta*z + noise with theta=-0.05 -> half-life = ln2/0.05 ~ 13.9
        rng = random.Random(42)
        theta = -0.05
        z = [0.0]
        for _ in range(5000):
            z.append(z[-1] + theta * z[-1] + rng.gauss(0.0, 1.0))
        hl = verify_range_halflife.estimate_ou_halflife(z)
        self.assertGreater(hl, 9.0)
        self.assertLess(hl, 20.0)

    def test_mean_averting_series_has_no_mean_reversion(self) -> None:
        # Explosive AR(1) (theta > 0): deviations grow instead of decaying
        rng = random.Random(43)
        z = [1.0]
        for _ in range(500):
            z.append(z[-1] * 1.01 + rng.gauss(0.0, 0.001))
        self.assertTrue(math.isinf(verify_range_halflife.estimate_ou_halflife(z)))

    def test_too_short_series_is_nan(self) -> None:
        self.assertTrue(math.isnan(verify_range_halflife.estimate_ou_halflife([1.0, 2.0, 3.0])))


class SizeWeightedMetricsTests(unittest.TestCase):
    def _trade(self, gross: float, size: float) -> BacktestTrade:
        net = gross - 0.0008
        return BacktestTrade(
            entry_time="", exit_time="", side="BUY", entry_price=100.0,
            exit_price=100.0, tp_price=101.0, sl_price=99.0,
            pnl_pct=net, outcome="tp", strategy="t",
            gross_pnl_pct=gross, position_size_used=size,
            trade_return_pct=net * size, gross_trade_return_pct=gross * size,
        )

    def test_size_weighted_sharpe_sees_what_price_sharpe_hides(self) -> None:
        # Big winner sized 0.5, equal-magnitude loser sized 0.1.
        # Price returns are symmetric -> price-based Sharpe ~ 0.
        # Equity returns are asymmetric -> the account made money.
        trades = [self._trade(+0.02, 0.5), self._trade(-0.02, 0.1)]
        price_sharpe = per_trade_sharpe([t.pnl_pct for t in trades])
        equity_sharpe = per_trade_sharpe([t.trade_return_pct for t in trades])
        self.assertGreater(equity_sharpe, price_sharpe)
        self.assertGreater(sum(t.trade_return_pct for t in trades), 0.0)

    def test_constant_size_leaves_sharpe_unchanged(self) -> None:
        # A constant multiplier cancels in mean/std, so fixed-size runs must
        # report exactly the Sharpe they reported before size weighting.
        rng = random.Random(5)
        pnls = [rng.gauss(0.001, 0.01) for _ in range(200)]
        size = 0.1
        self.assertAlmostEqual(
            per_trade_sharpe(pnls),
            per_trade_sharpe([p * size for p in pnls]),
            places=12,
        )

    def test_run_backtest_populates_equity_returns(self) -> None:
        class _AlwaysLong:
            def probability(self, values) -> float:
                return 0.9

        candles = KellyBacktestWiringTests()._make_candles(300)
        result = run_backtest(
            candles, model=_AlwaysLong(), position_size=0.1, label_horizon=10,
            cooldown_bars=0, long_threshold=0.6, short_threshold=0.01,
        )
        self.assertGreater(result.trade_count, 0)
        for t in result.trades:
            self.assertAlmostEqual(t.trade_return_pct, t.pnl_pct * 0.1, places=12)
            self.assertAlmostEqual(t.gross_trade_return_pct, t.gross_pnl_pct * 0.1, places=12)


class MultiHorizonRegimeAwareTests(unittest.TestCase):
    def test_direction_policy_mirrors_regime_training(self) -> None:
        # The pilot must trade the same sides per regime the regime model does,
        # or Phase 4.5 is not comparable to Phase 4.
        from btcusdt_quant.cli import MH_REGIME_SIDES

        sides = {r: tuple(s for s, _ in v) for r, v in MH_REGIME_SIDES.items()}
        self.assertEqual(sides, {"up": ("long",), "down": ("short",), "range": ("long", "short")})
        targets = {r: dict(v) for r, v in MH_REGIME_SIDES.items()}
        self.assertEqual(targets["up"]["long"], "long_success")
        self.assertEqual(targets["down"]["short"], "short_success")
        self.assertEqual(targets["range"]["short"], "short_success")

    def test_fit_rejects_unknown_target_key(self) -> None:
        from btcusdt_quant.ensemble import fit_multi_horizon_ensemble

        with self.assertRaises(ValueError):
            fit_multi_horizon_ensemble([], [], ["f1"], horizons=(5,), target_key="direction_of_travel")

    def test_short_target_is_not_the_complement_of_long(self) -> None:
        # The reason a short model needs its own target: a long that times out
        # is not a short win, so P(long)+P(short) != 1 and 1-P(long) is not a
        # short probability.
        from btcusdt_quant import dataset as _ds

        candles = KellyBacktestWiringTests()._make_candles(500)
        rows = _ds.build_feature_rows(candles)
        labeled = _ds.attach_labels(rows, candles, horizon=20, label_threshold=0.001, tp_pct=0.003, sl_pct=0.0015, include_warmup=True)
        self.assertGreater(len(labeled), 0)
        p_long = sum(r.targets["long_success"] for r in labeled) / len(labeled)
        p_short = sum(r.targets["short_success"] for r in labeled) / len(labeled)
        self.assertNotAlmostEqual(p_long + p_short, 1.0, places=2)
        # and label=0 is dominated by non-short outcomes
        long_fails = [r for r in labeled if r.targets["long_success"] == 0]
        if long_fails:
            short_wins = sum(r.targets["short_success"] for r in long_fails)
            self.assertLess(short_wins, len(long_fails), "most long failures are not short wins")


class ReconciliationTests(unittest.TestCase):
    def test_trade_returns_compound_to_net_total_return(self) -> None:
        # _close_trade advances equity by net_pnl_pct * position_size * equity,
        # and trade_return_pct IS net_pnl_pct * position_size, so the run
        # telescopes into prod(1 + trade_return_pct) - 1 == net_total_return.
        # This must hold under Kelly too, where size varies per trade.
        class _AlwaysLong:
            def probability(self, values) -> float:
                return 0.9

        candles = KellyBacktestWiringTests()._make_candles(500)
        config = risk.KellySizingConfig(kelly_multiplier=0.5, variance_lookback_bars=120, holding_period_bars=10)
        for kelly in (None, config):
            result = run_backtest(
                candles, model=_AlwaysLong(), position_size=0.1, label_horizon=10,
                cooldown_bars=0, long_threshold=0.6, short_threshold=0.01, kelly_config=kelly,
            )
            self.assertGreater(result.trade_count, 0)
            compounded = 1.0
            for trade in result.trades:
                compounded *= 1.0 + trade.trade_return_pct
            self.assertAlmostEqual(compounded - 1.0, result.total_return, places=12,
                                   msg=f"kelly={kelly is not None}")

    def test_reconcile_reports_ok_and_skips_legacy(self) -> None:
        import compare_backtests as cb
        import io
        from contextlib import redirect_stdout

        trades = [{"trade_return_pct": 0.10}, {"trade_return_pct": -0.05}]
        good = {"net_total_return": 1.10 * 0.95 - 1.0}
        out = io.StringIO()
        with redirect_stdout(out):
            cb._reconcile(trades, good)
        self.assertIn("reconcile     OK", out.getvalue())

        out = io.StringIO()
        with redirect_stdout(out):
            cb._reconcile(trades, {"net_total_return": 0.5})
        self.assertIn("RECONCILE FAIL", out.getvalue())

        out = io.StringIO()
        with redirect_stdout(out):
            cb._reconcile([{"net_pnl_pct": 0.1}], {"net_total_return": 0.0})
        self.assertIn("skipped (legacy artifact", out.getvalue())

    def test_reconcile_tolerates_float_drift_near_breakeven(self) -> None:
        # A near-break-even, high-turnover run: the equity curve (dollar space)
        # and this product (unit space) drift by ~n*eps. A tolerance that
        # collapses to abs_tol near zero would call a healthy artifact corrupt.
        import compare_backtests as cb
        import io
        from contextlib import redirect_stdout

        rng = random.Random(4)
        rets = [rng.gauss(0.0, 0.002) for _ in range(5000)]
        trades = [{"trade_return_pct": r} for r in rets]
        exact = cb._compounded(rets)
        self.assertLess(abs(exact), 0.5, "sanity: this run is near break-even")
        # Inject drift of the size real float accumulation produces.
        drifted = {"net_total_return": exact + 1e-11}
        out = io.StringIO()
        with redirect_stdout(out):
            cb._reconcile(trades, drifted)
        self.assertIn("reconcile     OK", out.getvalue())

        # A genuine corruption must still be caught.
        out = io.StringIO()
        with redirect_stdout(out):
            cb._reconcile(trades, {"net_total_return": exact + 1e-6})
        self.assertIn("RECONCILE FAIL", out.getvalue())


class CompareBacktestsTests(unittest.TestCase):
    def test_sum_and_compounded_returns_differ(self) -> None:
        import compare_backtests as cb

        # Sum is additive (contribution); compounding is multiplicative and can
        # even flip the sign. Reporting the sum as "total_return" was wrong.
        rets = [0.30, -0.25]
        stats = cb._stats(rets)
        self.assertAlmostEqual(stats["sum_trade_returns"], 0.05)
        self.assertAlmostEqual(stats["compounded_subset_return"], 1.30 * 0.75 - 1.0)
        self.assertGreater(stats["sum_trade_returns"], 0.0)
        self.assertLess(stats["compounded_subset_return"], 0.0)

    def test_compounded_of_empty_is_zero(self) -> None:
        import compare_backtests as cb

        self.assertEqual(cb._compounded([]), 0.0)
        self.assertEqual(cb._stats([])["trades"], 0)

    def test_comparability_warns_on_run_config_mismatch(self) -> None:
        import compare_backtests as cb

        base = {"round_trip_cost_pct": 0.0008, "min_hold_bars": 0, "cooldown_bars": 30, "threshold_floor": 0.45,
                "run_config": {key: 1 for key in cb.COMPARABILITY_KEYS}}
        same = copy.deepcopy(base)
        self.assertEqual(cb._comparability_warnings(base, same), [])

        differing = copy.deepcopy(base)
        differing["run_config"]["execution_horizon"] = 90
        differing["threshold_floor"] = 0.0
        warnings = cb._comparability_warnings(base, differing)
        self.assertTrue(any("execution_horizon" in w for w in warnings))
        self.assertTrue(any("threshold_floor" in w for w in warnings))

    def test_missing_run_config_is_reported(self) -> None:
        import compare_backtests as cb

        warnings = cb._comparability_warnings({}, {})
        self.assertTrue(any("run_config missing" in w for w in warnings))

    def test_strategy_config_and_overrides_are_compared(self) -> None:
        # Two runs on different strategies (or with a threshold override) execute
        # different barriers; the tool must not call them comparable.
        import compare_backtests as cb

        self.assertIn("strategy_config", cb.COMPARABILITY_KEYS)
        self.assertIn("long_threshold_override", cb.COMPARABILITY_KEYS)
        self.assertIn("short_threshold_override", cb.COMPARABILITY_KEYS)

        base = {"run_config": {key: 1 for key in cb.COMPARABILITY_KEYS}}
        base["run_config"]["strategy_config"] = {"name": "balanced", "use_atr_pricing": True}
        other = copy.deepcopy(base)
        other["run_config"]["strategy_config"] = {"name": "balanced", "use_atr_pricing": False}
        warnings = cb._comparability_warnings(base, other)
        self.assertTrue(any("strategy_config" in w for w in warnings))

    def test_strategy_as_dict_records_use_atr_pricing(self) -> None:
        # Without it, a fixed-barrier config and an ATR-priced one serialize
        # identically while executing entirely different TP/SL.
        from btcusdt_quant import live

        strategy = live.strategy_for_regime(None, "balanced")
        self.assertIn("use_atr_pricing", strategy.as_dict())


class MultiHorizonFinalRefitTests(unittest.TestCase):
    def test_weights_mapping_must_cover_every_horizon(self) -> None:
        from btcusdt_quant.ensemble import fit_multi_horizon_ensemble

        with self.assertRaises(ValueError):  # missing 90
            fit_multi_horizon_ensemble([], [], ["f"], horizons=(30, 60, 90), weights={30: 0.5, 60: 0.5})
        with self.assertRaises(ValueError):  # extra horizon
            fit_multi_horizon_ensemble([], [], ["f"], horizons=(30, 60), weights={30: 0.5, 60: 0.5, 90: 0.1})
        with self.assertRaises(ValueError):  # negative
            fit_multi_horizon_ensemble([], [], ["f"], horizons=(30, 60), weights={30: -1.0, 60: 2.0})
        with self.assertRaises(ValueError):  # zero sum
            fit_multi_horizon_ensemble([], [], ["f"], horizons=(30, 60), weights={30: 0.0, 60: 0.0})

    def test_non_finite_weights_are_rejected(self) -> None:
        # NaN passes every `<`/`<=` comparison and inf normalizes to NaN, so
        # both would silently make every blended probability NaN at serve time.
        from btcusdt_quant.ensemble import fit_multi_horizon_ensemble

        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError, msg=f"weights={bad}"):
                fit_multi_horizon_ensemble([], [], ["f"], horizons=(30, 60), weights={30: bad, 60: 1.0})
            with self.assertRaises(ValueError, msg=f"adapter weights={bad}"):
                MultiHorizonEnsembleAdapter(
                    feature_names=("f",),
                    horizons=(30, 60),
                    horizon_models=(_StubModel(0.5), _StubModel(0.5)),
                    weights=(bad, 1.0),
                )

    def test_weights_are_keyed_by_horizon_not_position(self) -> None:
        # fit() sorts horizons internally. A positional sequence in the
        # caller's order would attach each weight to the wrong model; the
        # mapping makes that impossible. Round-tripping an adapter's own
        # (horizons, weights) pair must therefore be order-safe.
        adapter = MultiHorizonEnsembleAdapter(
            feature_names=("f",),
            horizons=(30, 60, 90),
            horizon_models=(_StubModel(0.1), _StubModel(0.2), _StubModel(0.3)),
            weights=(0.2, 0.3, 0.5),
        )
        self.assertEqual(adapter.horizons, tuple(sorted({90, 30, 60})))
        carried = dict(zip(adapter.horizons, adapter.weights))
        self.assertEqual(carried, {30: 0.2, 60: 0.3, 90: 0.5})
        # An unsorted caller order still lands on the right horizons.
        self.assertEqual([carried[h] for h in sorted({90, 30, 60})], [0.2, 0.3, 0.5])

    def test_regime_side_policy_is_one_shared_object(self) -> None:
        # Not "equal to" -- literally the same mapping. Two hand-kept copies
        # would let the pilot and the Phase 3 models train different side sets
        # while every comment claims they are comparable.
        from btcusdt_quant import training
        from btcusdt_quant.cli import MH_REGIME_SIDES

        self.assertIs(MH_REGIME_SIDES, training.REGIME_SIDES)
        # Aliased, so it must be read-only or one consumer could rewrite the
        # policy for every other consumer.
        with self.assertRaises(TypeError):
            training.REGIME_SIDES["up"] = ()  # type: ignore[index]
        self.assertEqual(set(MH_REGIME_SIDES["range"]), {("long", "long_success"), ("short", "short_success")})
        self.assertEqual(training.sides_for_regime("up"), (("long", "long_success"),))
        self.assertEqual(training.sides_for_regime("down"), (("short", "short_success"),))
        # An unrecognised regime is a programming error: guessing "both sides"
        # would ship models for a bucket with no policy; guessing "no sides"
        # would leave a silently missing model.
        with self.assertRaises(ValueError):
            training.sides_for_regime("sideways")


class SideCapabilityTests(unittest.TestCase):
    """A missing side model emits no signal, so no skip counter can see it.

    The bundle must answer "can I price this side?", and the run must report a
    side it could never trade -- otherwise `shorts_skipped_no_short_model == 0`
    and `default_fallback == 0` both read as passing while the strategy is
    silently one-directional.
    """

    def _bundle(self, *, with_short: bool):
        from btcusdt_quant.live import RegimeModelBundle
        from btcusdt_quant import features as _features

        return RegimeModelBundle(
            models={"range": _StubModel(0.9)},
            long_models={"range": _StubModel(0.9)},
            short_models=({"range": _StubModel(0.8)} if with_short else {}),
            detector_thresholds={},
            detector_config=_features.RegimeDetectorConfig(),
            detector_diagnostics={},
            direction_policy={"range": {"LONG", "SHORT"} if with_short else {"LONG"}},
        )

    def test_has_side_probability_reflects_the_models_present(self) -> None:
        both = self._bundle(with_short=True)
        self.assertTrue(both.has_side_probability("range", "long"))
        self.assertTrue(both.has_side_probability("range", "short"))

        long_only = self._bundle(with_short=False)
        self.assertTrue(long_only.has_side_probability("range", "long"))
        self.assertFalse(long_only.has_side_probability("range", "short"))

    def test_probability_for_returns_none_not_zero(self) -> None:
        # None means "cannot price"; 0.0 would mean "zero chance" and would be
        # sized as a confident bet against the move.
        long_only = self._bundle(with_short=False)
        self.assertIsNone(long_only.probability_for("range", "short", {}))
        self.assertAlmostEqual(long_only.probability_for("range", "long", {}), 0.9)

    def test_missing_side_models_compares_against_the_policy(self) -> None:
        from btcusdt_quant import training

        # These bundles only carry a `range` regime, so the policy's up/down are
        # entirely absent -- the worst case, and it must be reported. Iterating
        # loaded models instead of the policy would hide it.
        both = self._bundle(with_short=True).missing_side_models(training.REGIME_SIDES)
        self.assertEqual(both, {"up": ["long"], "down": ["short"]})

        long_only = self._bundle(with_short=False).missing_side_models(training.REGIME_SIDES)
        self.assertEqual(long_only, {"up": ["long"], "down": ["short"], "range": ["short"]})

    def test_unknown_side_raises(self) -> None:
        bundle = self._bundle(with_short=True)
        for bad in ("SHORT", "up", ""):
            with self.assertRaises(ValueError):
                bundle.has_side_probability("range", bad)
            with self.assertRaises(ValueError):
                bundle.probability_for("range", bad, {})

    def test_missing_side_models_surfaced_in_compare(self) -> None:
        # An entirely absent side never trips the kelly skip counters, so
        # missing_side_models is the only record of a one-directional run; the
        # comparison tool must print it.
        import compare_backtests as cb
        import io
        from contextlib import redirect_stdout

        out = io.StringIO()
        with redirect_stdout(out):
            cb.summarize("t", {"trades": [], "missing_side_models": {"range": ["short"]}})
        self.assertIn("missing side models", out.getvalue())
        self.assertIn("range/short", out.getvalue())

    def test_loader_ignores_undeclared_stale_side_file(self) -> None:
        # A side model on disk that the summary does not declare is stale (left
        # by an earlier run under a different policy). Loading it would trade a
        # forbidden direction, which missing_side_models cannot catch (it only
        # sees ABSENT sides). The loader must skip it.
        import json as _json
        import tempfile
        from pathlib import Path as _Path
        from btcusdt_quant import live
        from btcusdt_quant.models import CentroidLinearClassifier

        model = CentroidLinearClassifier(feature_names=["a"]).fit([[1.0], [-1.0], [1.0], [-1.0]], [1, 0, 1, 0])
        with tempfile.TemporaryDirectory() as tmp:
            root = _Path(tmp)
            # Summary declares up as long-only, but a stale short file sits on disk.
            (root / "regime_run_summary.json").write_text(_json.dumps({
                "regime_results": {"up": {"selected_thresholds": {"long": 0.5}, "sides": {"long": True}}},
                "default_regime": "up",
            }), encoding="utf-8")
            up = root / "regime_up"
            up.mkdir()
            (up / "long_model.json").write_text(_json.dumps(model.as_dict()), encoding="utf-8")
            (up / "short_model.json").write_text(_json.dumps(model.as_dict()), encoding="utf-8")  # stale
            bundle = live.load_regime_aware_models(root, strict=False)

        self.assertIsNotNone(bundle)
        self.assertIn("up", bundle.long_models)
        self.assertNotIn("up", bundle.short_models, "undeclared stale short must be ignored")
        self.assertEqual(bundle.direction_policy["up"], {"LONG"})

    def test_backtest_records_missing_side_models(self) -> None:
        from btcusdt_quant.backtest import BacktestResult

        result = BacktestResult()
        result.missing_side_models = {"range": ["short"]}
        self.assertEqual(result.as_dict()["missing_side_models"], {"range": ["short"]})

    def test_kelly_reports_both_one_sided_refusals(self) -> None:
        from btcusdt_quant.backtest import BacktestResult

        payload = BacktestResult().as_dict()
        # Present even when Kelly is off, so a consumer can key on them.
        self.assertIn("missing_side_models", payload)

    def test_kelly_guard_fails_closed_on_empty_genuine_sides(self) -> None:
        # The guard is `entered_side not in genuine_sides` with NO
        # `genuine_sides and ...` short-circuit, so an empty set refuses rather
        # than falling through and sizing on a None probability.
        import inspect
        from btcusdt_quant import backtest

        src = inspect.getsource(backtest.run_backtest)
        self.assertIn("if entered_side not in _ctx_genuine_sides:", src)
        self.assertNotIn("if _ctx_genuine_sides and entered_side not in", src)


class CentroidLinearClassifierTests(unittest.TestCase):
    """The fast smoke scripts imported training.Standardizer/LinearClassifier,
    which never existed -- their inline-training branch raised ImportError."""

    def _data(self) -> tuple[list[list[float]], list[int]]:
        rng = random.Random(3)
        rows, labels = [], []
        for _ in range(300):
            label = rng.randint(0, 1)
            rows.append([rng.gauss(1.0 if label else -1.0, 1.0), rng.gauss(0.0, 1.0), 5.0])
            labels.append(label)
        return rows, labels

    def test_phantom_symbols_are_gone(self) -> None:
        from btcusdt_quant import training

        self.assertFalse(hasattr(training, "LinearClassifier"))
        self.assertFalse(hasattr(training, "Standardizer"))

    def test_separates_classes_and_stays_unsaturated(self) -> None:
        from btcusdt_quant.models import CentroidLinearClassifier

        rows, labels = self._data()
        model = CentroidLinearClassifier(feature_names=["a", "b", "const"]).fit(rows, labels)
        probs = model.predict_proba(rows)
        accuracy = sum(1 for p, y in zip(probs, labels) if (p >= 0.5) == bool(y)) / len(labels)
        self.assertGreater(accuracy, 0.7)
        self.assertGreater(min(probs), 0.0)
        self.assertLess(max(probs), 1.0)

    def test_constant_feature_does_not_divide_by_zero(self) -> None:
        from btcusdt_quant.models import CentroidLinearClassifier

        rows, labels = self._data()  # third column is constant 5.0
        model = CentroidLinearClassifier(feature_names=["a", "b", "const"]).fit(rows, labels)
        self.assertTrue(all(math.isfinite(p) for p in model.predict_proba(rows)))

    def test_round_trip_serialization(self) -> None:
        from btcusdt_quant.models import CentroidLinearClassifier

        rows, labels = self._data()
        model = CentroidLinearClassifier(feature_names=["a", "b", "const"]).fit(rows, labels)
        restored = CentroidLinearClassifier.from_dict(model.as_dict())
        self.assertEqual(model.predict_proba(rows), restored.predict_proba(rows))

    def test_ensemble_can_load_it_as_a_submodel(self) -> None:
        from btcusdt_quant.ensemble import _load_submodel
        from btcusdt_quant.models import CentroidLinearClassifier

        rows, labels = self._data()
        model = CentroidLinearClassifier(feature_names=["a", "b", "const"]).fit(rows, labels)
        loaded = _load_submodel(model.as_dict())
        self.assertIsInstance(loaded, CentroidLinearClassifier)

    def test_saved_artifact_round_trips_through_live_loader(self) -> None:
        # A model you can save but not load back is a trap that only surfaces
        # at serve time.
        import json as _json
        import tempfile
        from pathlib import Path as _Path
        from btcusdt_quant import live
        from btcusdt_quant.models import CentroidLinearClassifier

        rows, labels = self._data()
        model = CentroidLinearClassifier(feature_names=["a", "b", "const"]).fit(rows, labels)
        features = dict(zip(["a", "b", "const"], rows[0]))
        with tempfile.TemporaryDirectory() as tmp:
            path = _Path(tmp) / "model.json"
            path.write_text(_json.dumps(model.as_dict()), encoding="utf-8")
            loaded = live.load_model_artifact(path, strict=True)
        self.assertIsInstance(loaded, CentroidLinearClassifier)
        self.assertAlmostEqual(model.probability(features), loaded.probability(features), places=12)

    def test_degenerate_inputs_raise(self) -> None:
        from btcusdt_quant.models import CentroidLinearClassifier

        with self.assertRaises(ValueError):
            CentroidLinearClassifier(["a"]).fit([], [])
        with self.assertRaises(ValueError):
            CentroidLinearClassifier(["a"]).fit([[1.0], [2.0]], [1, 1])  # single class
        with self.assertRaises(ValueError):
            CentroidLinearClassifier(["a", "b"]).fit([[1.0]], [1])  # width mismatch
        with self.assertRaises(ValueError):  # NaN must not reach the weights
            CentroidLinearClassifier(["a"]).fit([[1.0], [float("nan")]], [0, 1])
        with self.assertRaises(ValueError):  # coincident centroids -> constant 0.5
            CentroidLinearClassifier(["a"]).fit([[1.0], [1.0], [1.0], [1.0]], [0, 1, 0, 1])

    def test_nan_feature_is_neutral_not_confident(self) -> None:
        # min(60, max(-60, nan)) == -60 in CPython, so an unguarded clamp turns
        # a corrupted feature row into probability ~0: "certain short".
        from btcusdt_quant.models import CentroidLinearClassifier

        rows, labels = self._data()
        model = CentroidLinearClassifier(feature_names=["a", "b", "const"]).fit(rows, labels)
        self.assertEqual(model.probability({"a": float("nan"), "b": 0.0, "const": 5.0}), 0.5)

    def test_large_scale_noise_feature_gets_no_weight(self) -> None:
        # An absolute std floor lets a near-constant 1e9-scale column's float
        # dust standardize to ~10 and earn a real weight.
        from btcusdt_quant.models import CentroidLinearClassifier

        rng = random.Random(11)
        rows, labels = [], []
        for index in range(400):
            label = index % 2
            rows.append([rng.gauss(1.0 if label else -1.0, 1.0), 1e9 + rng.gauss(0.0, 1e-7)])
            labels.append(label)
        model = CentroidLinearClassifier(feature_names=["signal", "noise"]).fit(rows, labels)
        weights = model.as_dict()["weights"]
        self.assertLess(abs(weights["noise"]), 0.1 * abs(weights["signal"]))


class ThresholdHorizonGuardTests(unittest.TestCase):
    """The training window must be trimmed by the LONGEST label reach.

    Horizon models label at max(horizons); the threshold holdout labels at
    --threshold-horizon. Trimming by max(horizons) alone would let a longer
    threshold horizon score its holdout against candles past --training-end,
    i.e. the out-of-sample backtest span.
    """

    @staticmethod
    def _label_reach(horizons: list[int], threshold_horizon: int | None) -> int:
        return max(max(horizons), threshold_horizon or max(horizons))

    def test_label_reach_covers_longer_threshold_horizon(self) -> None:
        self.assertEqual(self._label_reach([30, 60, 90], 120), 120)
        self.assertEqual(self._label_reach([30, 60, 90], 60), 90)
        self.assertEqual(self._label_reach([30, 60, 90], None), 90)

    def test_holdout_labels_stay_inside_the_training_window(self) -> None:
        # A row at train_end-1 labels forward `threshold_horizon` bars; with
        # the widened trim it lands at i1-1 at worst -- never past it.
        i1 = 10_000
        for horizons, th in (([30, 60, 90], 120), ([30, 60, 90], 60), ([60], 60)):
            reach = self._label_reach(horizons, th)
            train_end = i1 - reach
            furthest = (train_end - 1) + max(max(horizons), th)
            self.assertLess(furthest, i1, f"label reached past the training window for {horizons}/{th}")

    def test_backtest_warns_on_threshold_horizon_mismatch(self) -> None:
        import io
        import json as _json
        import tempfile
        from contextlib import redirect_stderr
        from pathlib import Path as _Path
        from btcusdt_quant import cli as _cli

        with tempfile.TemporaryDirectory() as tmp:
            artifact = _Path(tmp) / "mh"
            artifact.mkdir()
            (artifact / "regime_run_summary.json").write_text(
                _json.dumps({"regime_results": {}, "threshold_horizon": 90, "model_kind": "multi_horizon_ensemble", "horizons": [30, 60, 90]}),
                encoding="utf-8",
            )
            err = io.StringIO()
            with redirect_stderr(err):
                _cli.main(["backtest", "--model-artifact", str(artifact), "--horizon", "60", "--output", str(_Path(tmp) / "out")])
            message = err.getvalue()
        self.assertIn("thresholds were selected on 90-bar labels", message)
        self.assertIn("--horizon is 60", message)


class MultiHorizonSliceAlignmentTests(unittest.TestCase):
    def test_labels_use_full_candles_not_sliced(self) -> None:
        # FeatureRow.index indexes the FULL candle list; attach_labels reads
        # candles[row.index]. Slicing the candle list alongside the rows makes
        # every label read a price i0 bars in the future.
        from btcusdt_quant import dataset as _ds

        candles = KellyBacktestWiringTests()._make_candles(600)
        rows = _ds.build_feature_rows(candles)
        i0 = 200
        sliced_rows = rows[i0:]
        self.assertEqual(sliced_rows[0].index, i0, "row.index stays a full-series index after slicing")

        correct = _ds.attach_labels(sliced_rows, candles, horizon=10, label_threshold=0.001, tp_pct=0.01, sl_pct=0.005, include_warmup=True)
        aliased = _ds.attach_labels(sliced_rows, candles[i0:], horizon=10, label_threshold=0.001, tp_pct=0.01, sl_pct=0.005, include_warmup=True)
        self.assertGreater(len(correct), len(aliased), "the aliased call silently drops rows past the sliced end")
        self.assertNotEqual(
            [r.target_return for r in correct[:50]],
            [r.target_return for r in aliased[:50]],
            "the aliased call labels from the wrong candles",
        )


class GrossNetSharpeTests(unittest.TestCase):
    def test_per_trade_sharpe_known_value(self) -> None:
        # mean=0.005, population std=0.005 -> sharpe=1.0
        self.assertAlmostEqual(per_trade_sharpe([0.0, 0.01]), 1.0)

    def test_per_trade_sharpe_is_nan_when_undefined(self) -> None:
        self.assertTrue(math.isnan(per_trade_sharpe([])))
        self.assertTrue(math.isnan(per_trade_sharpe([0.01])))
        self.assertTrue(math.isnan(per_trade_sharpe([0.01, 0.01])))  # zero std

    def test_per_trade_sharpe_rejects_float_noise_dispersion(self) -> None:
        # The two TP exits of the 2-trade run: identical to ~1e-18. std that
        # small is noise, and the old `std > 0` guard turned it into 1.08e14.
        self.assertTrue(
            math.isnan(per_trade_sharpe([0.00021999999999999586, 0.0002199999999999918])),
            "float-noise dispersion must not be reported as a Sharpe",
        )

    def test_as_dict_reports_gross_and_net_side_by_side(self) -> None:
        result = BacktestResult(sharpe=0.4, gross_sharpe=1.1)
        payload = result.as_dict()
        self.assertEqual(payload["net_sharpe"], 0.4)
        self.assertEqual(payload["gross_sharpe"], 1.1)
        self.assertAlmostEqual(payload["cost_impact_sharpe"], 0.7)


class _StubBundle:
    """Minimal stand-in for RegimeModelBundle's barrier-parity surface."""

    def __init__(self, label_tp_pct: float | None, label_sl_pct: float | None) -> None:
        self.label_tp_pct = label_tp_pct
        self.label_sl_pct = label_sl_pct


class ExecutionBarrierParityTests(unittest.TestCase):
    def test_matching_barrier_passes_silently(self) -> None:
        self.assertEqual(
            check_execution_barrier_parity(_StubBundle(0.010, 0.005), 0.010, 0.005),
            [],
        )

    def test_mismatched_barrier_raises(self) -> None:
        # The artifacts on disk were labeled 0.003/0.0015; the pipeline now
        # executes 0.010/0.005. Backtesting one against the other must refuse.
        with self.assertRaises(ValueError) as caught:
            check_execution_barrier_parity(_StubBundle(0.003, 0.0015), 0.010, 0.005)
        self.assertIn("tp_pct", str(caught.exception))
        self.assertIn("sl_pct", str(caught.exception))

    def test_mismatch_is_allowed_only_when_asked_and_still_warns(self) -> None:
        warnings = check_execution_barrier_parity(
            _StubBundle(0.003, 0.0015), 0.010, 0.005, allow_mismatch=True
        )
        self.assertTrue(any("BARRIER MISMATCH" in w for w in warnings))

    def test_legacy_artifact_without_recorded_barrier_warns_but_runs(self) -> None:
        warnings = check_execution_barrier_parity(_StubBundle(None, None), 0.010, 0.005)
        self.assertTrue(warnings, "an unverifiable barrier must not pass silently")

    def test_no_exec_override_is_not_a_mismatch(self) -> None:
        # Without --exec-tp/sl-pct the strategy's own barrier is executed; there
        # is no fixed barrier to compare against.
        self.assertEqual(
            check_execution_barrier_parity(_StubBundle(0.003, 0.0015), None, None),
            [],
        )


class NoisyMetricGuardTests(unittest.TestCase):
    def test_promotion_gate_rejects_nan_instead_of_failing_open(self) -> None:
        # NaN makes every `value < limit` veto False, so an unmeasurable metric
        # used to sail through the gate it should have tripped.
        manager = features.ChampionChallengerManager()
        self.assertIsNone(manager._optional_float({"sharpe": float("nan")}, "sharpe"))
        self.assertIsNone(manager._optional_float({"sharpe": float("inf")}, "sharpe"))
        self.assertEqual(manager._optional_float({"sharpe": 1.5}, "sharpe"), 1.5)

    def test_calmar_folds_float_noise_drawdown_to_zero(self) -> None:
        # calmar is the FIRST key of select_threshold's sort tuple, so a
        # noise-level mdd handing back ~1e18 would win the threshold outright.
        noisy = [0.001, 0.001, -1e-18, 0.001]
        self.assertLess(training._calmar(noisy), 1e6)

    def test_calmar_and_sharpe_never_return_nan(self) -> None:
        # Both are max() sort keys in select_threshold: a NaN there corrupts the
        # ordering silently rather than losing, so they must fold to 0.0.
        flat = [0.001, 0.001, 0.001]
        self.assertFalse(math.isnan(training._sharpe(flat)))
        self.assertFalse(math.isnan(training._calmar(flat)))

    def test_gross_sharpe_exceeds_net_when_costs_bite(self) -> None:
        trades = []
        for gross in (0.004, 0.006, 0.005, 0.0045):
            trade = BacktestTrade(
                entry_time="", exit_time="", side="BUY", entry_price=100.0,
                exit_price=100.5, tp_price=101.0, sl_price=99.0,
                pnl_pct=gross - 0.0008, outcome="tp", strategy="test",
                gross_pnl_pct=gross,
            )
            trades.append(trade)
        net = per_trade_sharpe([t.pnl_pct for t in trades])
        gross = per_trade_sharpe([t.gross_pnl_pct for t in trades])
        # Same dispersion, lower mean: costs must strictly reduce Sharpe
        self.assertLess(net, gross)


def _reject_constant(token: str) -> float:
    raise AssertionError(f"summary carries the non-RFC-8259 literal {token!r}")


class SummaryJsonIsValidJsonTests(unittest.TestCase):
    """backtest_summary.json must parse in a strict JSON reader (jq), not just
    in Python and PowerShell, which accept NaN/Infinity as an extension."""

    def test_non_finite_metrics_serialize_as_null(self) -> None:
        # A sub-MIN_TRADES_FOR_RISK_METRICS run: sharpe NaN, profit_factor inf.
        result = BacktestResult(sharpe=float("nan"), gross_sharpe=float("nan"))
        result.profit_factor = float("inf")
        text = json.dumps(json_safe({"backtest": result.as_dict()}))
        self.assertNotIn("NaN", text)
        self.assertNotIn("Infinity", text)
        # parse_constant fires on exactly the tokens a strict parser rejects.
        payload = json.loads(text, parse_constant=_reject_constant)["backtest"]
        self.assertIsNone(payload["net_sharpe"])
        self.assertIsNone(payload["profit_factor"])
        self.assertIsNone(payload["cost_impact_sharpe"])

    def test_null_means_undefined_not_zero(self) -> None:
        # The distinction the fix exists for: a metric with no answer must not
        # come back as a number a reader would take for flat performance.
        self.assertIsNone(json_safe(float("nan")))
        self.assertIsNone(json_safe(float("-inf")))

    def test_finite_values_and_structure_survive(self) -> None:
        payload = {"a": 0.0, "b": [1, 2.5, float("nan")], "c": {"d": True, "e": None}, "f": "x"}
        self.assertEqual(
            json_safe(payload),
            {"a": 0.0, "b": [1, 2.5, None], "c": {"d": True, "e": None}, "f": "x"},
        )


class CompareBacktestsMetricTests(unittest.TestCase):
    def test_empty_slice_profit_factor_is_nan_not_zero(self) -> None:
        # 0.0 is the value of the worst possible slice, so an empty grid cell
        # printing pf=0.00 read as a catastrophe instead of "no trades here".
        import compare_backtests as cb

        self.assertTrue(math.isnan(cb._profit_factor([])))
        self.assertTrue(math.isnan(cb._stats([])["profit_factor"]))
        self.assertTrue(math.isnan(cb._stats([])["sharpe"]), "sharpe already agreed; pf now matches")

    def test_populated_slice_profit_factor_unchanged(self) -> None:
        import compare_backtests as cb

        self.assertAlmostEqual(cb._profit_factor([0.02, -0.01]), 2.0)
        self.assertEqual(cb._profit_factor([0.02, 0.01]), float("inf"))  # no losers
        self.assertEqual(cb._profit_factor([-0.01]), 0.0)  # all losers: genuinely 0

    def test_sharpe_is_the_backtests_own_formula(self) -> None:
        # Not a copy: the report is supposed to reconcile with the summary, and
        # the duplicate carried its own noise floor free to drift from this one.
        import compare_backtests as cb

        returns = [0.01, -0.005, 0.02, -0.01]
        self.assertEqual(cb._sharpe(returns), per_trade_sharpe(returns))
        self.assertTrue(
            math.isnan(cb._sharpe([0.00021999999999999586, 0.0002199999999999918])),
            "the float-noise floor must apply here too",
        )


if __name__ == "__main__":
    unittest.main()
