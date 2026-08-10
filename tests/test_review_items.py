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
from unittest import mock

from btcusdt_quant import backtest as backtest_module
from btcusdt_quant import features, risk, training
from btcusdt_quant.backtest import (
    BacktestResult,
    BacktestTrade,
    check_execution_barrier_parity,
    indistinguishable_profiles,
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

        # The guard now lives in the nested _open_trade helper (shared by the
        # taker and maker fill paths); getsource(run_backtest) includes it. The
        # side set is passed in as `genuine`.
        src = inspect.getsource(backtest.run_backtest)
        self.assertIn("if entered_side not in genuine:", src)
        self.assertNotIn("if genuine and entered_side not in", src)


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


class _ThresholdBundle:
    """Regime bundle stand-in carrying learned per-regime thresholds.

    Serves no side probabilities: the degeneracy question is decided entirely by
    the barrier and the thresholds, so the arms can be compared without any
    model emitting a signal.
    """

    def __init__(self, regime_thresholds: dict[str, dict[str, float]]) -> None:
        self.regime_thresholds = regime_thresholds
        self.direction_policy = {regime: {"LONG", "SHORT"} for regime in regime_thresholds}

    def has_side_probability(self, regime: str, side: str) -> bool:
        return False

    def probability_for(self, regime: str, side: str, features) -> float | None:
        return None


def _linear_candles(count: int) -> list:
    from datetime import timedelta

    from btcusdt_quant import data

    base = data.utc_minute(2026, 1, 2, 0, 0)
    price = 100000.0
    candles = []
    for index in range(count):
        open_price = price
        price += 5.0
        candles.append(
            data.Candle(
                open_time=base + timedelta(minutes=index),
                open=open_price,
                high=max(open_price, price) + 5.0,
                low=min(open_price, price) - 5.0,
                close=price,
                volume=10.0,
                quote_volume=10.0 * price,
                number_of_trades=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=5.0 * price,
            )
        )
    return candles


def _profiles() -> dict[str, object]:
    from btcusdt_quant import live

    return {
        name: live.strategy_for_regime(None, name)
        for name in ("balanced", "conservative", "aggressive")
    }


class IndistinguishableProfileTests(unittest.TestCase):
    """The strategy_comparison block reported three IDENTICAL rows to every
    decimal and then crowned a 'best' one. The profiles differ only in the entry
    thresholds, tp_pct and min_reward_risk -- and in a regime-aware run with
    exec barriers, all three of those are overridden or never read."""

    def test_regime_run_with_exec_barrier_is_degenerate(self) -> None:
        bundle = _ThresholdBundle({"up": {"long": 0.35, "short": 0.36}, "range": {"long": 0.34, "short": 0.35}})
        reason = indistinguishable_profiles(
            _profiles(),
            models_by_regime={"up": bundle, "range": bundle},
            exec_tp_pct=0.010,
            exec_sl_pct=0.005,
        )
        self.assertIsNotNone(reason)
        self.assertIn("exec-tp-pct", reason)
        self.assertIn("learned per-regime", reason)

    def test_profiles_differ_when_thresholds_are_not_overridden(self) -> None:
        # No learned thresholds anywhere: each profile's own cutoff survives, so
        # the arms really do trade differently and the comparison is real.
        reason = indistinguishable_profiles(
            _profiles(),
            models_by_regime={"up": _ThresholdBundle({})},
            exec_tp_pct=0.010,
            exec_sl_pct=0.005,
        )
        self.assertIsNone(reason)

    def test_profiles_differ_when_the_barrier_is_not_overridden(self) -> None:
        # Without exec barriers, aggressive's tp_pct * 1.10 reaches execution.
        bundle = _ThresholdBundle({"up": {"long": 0.35, "short": 0.36}})
        self.assertIsNone(
            indistinguishable_profiles(_profiles(), models_by_regime={"up": bundle})
        )

    def test_partial_learned_thresholds_still_differ(self) -> None:
        # A regime whose thresholds were never learned falls back to the
        # profile's own cutoff, so that regime alone keeps the arms apart.
        bundle_learned = _ThresholdBundle({"up": {"long": 0.35, "short": 0.36}})
        bundle_bare = _ThresholdBundle({})
        self.assertIsNone(
            indistinguishable_profiles(
                _profiles(),
                models_by_regime={"up": bundle_learned, "range": bundle_bare},
                exec_tp_pct=0.010,
                exec_sl_pct=0.005,
            )
        )

    def test_single_profile_is_not_a_degenerate_comparison(self) -> None:
        self.assertIsNone(indistinguishable_profiles({"balanced": _profiles()["balanced"]}))

    def test_min_reward_risk_alone_does_not_make_profiles_distinguishable(self) -> None:
        # conservative's only surviving difference under exec barriers + learned
        # thresholds. The backtest never reads it, so it cannot change a trade --
        # and a fingerprint that included it would call this a real comparison.
        from btcusdt_quant import live

        base = live.strategy_for_regime(None, "balanced")
        strict = copy.copy(base)
        object.__setattr__(strict, "min_reward_risk", base.min_reward_risk + 5.0)
        bundle = _ThresholdBundle({"up": {"long": 0.35, "short": 0.36}})
        self.assertIsNotNone(
            indistinguishable_profiles(
                {"balanced": base, "strict": strict},
                models_by_regime={"up": bundle},
                exec_tp_pct=0.010,
                exec_sl_pct=0.005,
            ),
            "a knob the backtest never reads cannot make two profiles a comparison",
        )


class DegenerateComparisonRunTests(unittest.TestCase):
    def test_degenerate_comparison_runs_one_arm_and_says_so(self) -> None:
        # Three profiles in, one backtest out: the other two would reproduce it
        # exactly, and 525,600 bars is too expensive to spend proving that.
        candles = _linear_candles(240)
        bundle = _ThresholdBundle({"up": {"long": 0.35, "short": 0.36}})
        with mock.patch.object(backtest_module, "run_backtest", wraps=backtest_module.run_backtest) as spy:
            comparison = backtest_module.compare_strategies(
                candles,
                None,
                _profiles(),
                models_by_regime={"up": bundle},
                default_regime="up",
                exec_tp_pct=0.010,
                exec_sl_pct=0.005,
                allow_barrier_mismatch=True,
            )
        self.assertEqual(spy.call_count, 1, "the redundant arms must not be backtested")
        self.assertTrue(comparison["indistinguishable_profiles"])
        self.assertIsNone(comparison["best_strategy"], "a tie has no winner")
        self.assertEqual(comparison["profiles_evaluated"], ["balanced"], "the shipped profile is the one that runs")
        self.assertEqual(comparison["profiles_requested"], ["aggressive", "balanced", "conservative"])
        self.assertIn("min_reward_risk", comparison["indistinguishable_reason"])

    def test_real_comparison_still_runs_every_arm(self) -> None:
        candles = _linear_candles(240)
        strategies = _profiles()
        with mock.patch.object(backtest_module, "run_backtest", wraps=backtest_module.run_backtest) as spy:
            comparison = backtest_module.compare_strategies(candles, None, strategies)
        self.assertEqual(spy.call_count, 3)
        self.assertFalse(comparison["indistinguishable_profiles"])
        self.assertIsNone(comparison["indistinguishable_reason"])
        self.assertIsNotNone(comparison["best_strategy"])
        self.assertEqual(sorted(comparison["comparison"]), ["aggressive", "balanced", "conservative"])


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


class ShuffledLabelHelperTests(unittest.TestCase):
    def _rows(self, n: int = 40):
        from datetime import timedelta
        from btcusdt_quant import data as _data, dataset as _ds

        base = _data.utc_minute(2026, 1, 2, 0, 0)
        rows = []
        for i in range(n):
            label = i % 3 == 0
            rows.append(_ds.LabeledRow(
                index=i, open_time=base + timedelta(minutes=i),
                features={"f": float(i)}, label=int(label),
                label_reason="tp_first" if label else "timeout_no_tp",
                target_return=0.01 if label else -0.002,
                gap_flag=0, repaired=False, warmup_invalid=False,
                targets={"long_success": int(label), "short_success": int(not label)},
                target_reasons={"long_success": "x", "short_success": "y"},
            ))
        return rows

    def test_deterministic_and_multiset_preserved(self) -> None:
        rows = self._rows()
        a = training.shuffle_labeled_row_targets(rows, seed=7)
        b = training.shuffle_labeled_row_targets(rows, seed=7)
        c = training.shuffle_labeled_row_targets(rows, seed=8)
        self.assertEqual([r.label for r in a], [r.label for r in b])
        self.assertNotEqual([r.label for r in a], [r.label for r in c])
        # Same label multiset (class balance preserved), decoupled from features.
        self.assertEqual(sorted(r.label for r in a), sorted(r.label for r in rows))
        self.assertNotEqual([r.label for r in a], [r.label for r in rows])

    def test_features_stay_and_payload_moves_together(self) -> None:
        rows = self._rows()
        shuffled = training.shuffle_labeled_row_targets(rows, seed=7)
        for orig, sh in zip(rows, shuffled):
            self.assertEqual(orig.features, sh.features)
            self.assertEqual(orig.index, sh.index)
            # label and its targets/reason must be internally consistent: they
            # came from ONE source row.
            self.assertEqual(sh.targets["long_success"], sh.label)
            self.assertEqual(sh.label_reason, "tp_first" if sh.label else "timeout_no_tp")


class TrainingTargetRemapTests(unittest.TestCase):
    def _rows(self, n: int = 8):
        from datetime import timedelta
        from btcusdt_quant import data as _data, dataset as _ds

        base = _data.utc_minute(2026, 1, 2, 0, 0)
        return [_ds.LabeledRow(
            index=i, open_time=base + timedelta(minutes=i), features={"f": float(i)},
            label=1, label_reason="x", target_return=0.0, gap_flag=0, repaired=False, warmup_invalid=False,
            targets={"long_success": i % 2, "short_success": 1 - i % 2, "direction": 1},
            target_reasons={},
        ) for i in range(n)]

    def test_remaps_label_to_short_success_features_untouched(self) -> None:
        rows = self._rows()
        out = training.apply_training_target(rows, "short_success")
        self.assertEqual([r.label for r in out], [1 - i % 2 for i in range(8)])
        for orig, r in zip(rows, out):
            self.assertEqual(orig.features, r.features)  # features never move

    def test_profitability_is_noop(self) -> None:
        rows = self._rows()
        out = training.apply_training_target(rows, "profitability")
        self.assertEqual([r.label for r in out], [r.label for r in rows])

    def test_rejects_unknown_target(self) -> None:
        with self.assertRaises(ValueError):
            training.apply_training_target(self._rows(), "bogus")


class FallbackFeatureExclusionTests(unittest.TestCase):
    def _build(self, feature_names, fallback):
        from btcusdt_quant import dataset as _ds

        return _ds.DatasetBuild(
            source="t", symbol="BTCUSDT", interval="1m", raw_rows=0, canonical=[],
            gap_report=_ds.GapReport(0, 0, 0, 0.0, 0, "", ""),
            feature_rows=[], labeled_rows=[], feature_names=tuple(feature_names),
            label_horizon=60, label_threshold=0.001,
            source_availability_report={"fallback_features": tuple(fallback)},
        )

    def test_drops_listed_fallback_features(self) -> None:
        names = tuple(f"f{i}" for i in range(15))
        build, dropped = training.drop_fallback_features(self._build(names, ["f1", "f3"]))
        self.assertEqual(sorted(dropped), ["f1", "f3"])
        self.assertEqual(len(build.feature_names), 13)
        self.assertNotIn("f1", build.feature_names)

    def test_refuses_to_drop_below_ten_features(self) -> None:
        names = tuple(f"f{i}" for i in range(12))
        build, dropped = training.drop_fallback_features(self._build(names, [f"f{i}" for i in range(5)]))
        # 12-5=7 < 10 -> refuse, unchanged.
        self.assertEqual(dropped, [])
        self.assertEqual(len(build.feature_names), 12)

    def test_noop_without_fallback_report(self) -> None:
        names = tuple(f"f{i}" for i in range(15))
        build, dropped = training.drop_fallback_features(self._build(names, []))
        self.assertEqual(dropped, [])
        self.assertEqual(build.feature_names, names)


class RangeGateToggleTests(unittest.TestCase):
    """--disable-range-gate: at range_position 0.5 the gate blocks every entry;
    disabling it must let the model's probability trade."""

    class _LongBundle:
        def __init__(self) -> None:
            self.long_models = {"range": _StubModel(0.9)}
            self.short_models: dict = {}
            self.regime_thresholds = {"range": {"long": 0.5, "short": 0.99}}
            self.direction_policy = {"range": {"LONG"}}
            self.label_tp_pct = 0.01
            self.label_sl_pct = 0.005

        def has_side_probability(self, regime, side):
            return regime in (self.long_models if side == "long" else self.short_models)

        def probability_for(self, regime, side, features):
            registry = self.long_models if side == "long" else self.short_models
            model = registry.get(regime)
            return None if model is None else float(model.probability(features))

    def _run(self, gate_enabled: bool):
        import dataclasses as _dc
        from btcusdt_quant import dataset as _ds

        candles = KellyBacktestWiringTests()._make_candles(300)
        rows = [
            _dc.replace(r, user_regime="range", features={**r.features, "range_position_20": 0.5})
            for r in _ds.build_feature_rows(candles)
        ]
        return run_backtest(
            candles,
            models_by_regime={"range": self._LongBundle()},
            feature_rows=rows,
            label_horizon=10,
            cooldown_bars=0,
            exec_tp_pct=0.01,
            exec_sl_pct=0.005,
            range_gate_enabled=gate_enabled,
        )

    def test_gate_blocks_and_toggle_frees_entries(self) -> None:
        gated = self._run(gate_enabled=True)
        ungated = self._run(gate_enabled=False)
        self.assertEqual(gated.trade_count, 0, "mid-range position must be blocked by the gate")
        self.assertGreater(ungated.trade_count, 0, "disabling the gate must allow probability-driven entries")
        self.assertIs(gated.run_config["range_gate_enabled"], True)
        self.assertIs(ungated.run_config["range_gate_enabled"], False)


_ALL_EXITS = sorted(backtest_module.EXIT_OUTCOMES)


def _ohlc_candles(specs):
    from datetime import timedelta
    from btcusdt_quant import data
    base = data.utc_minute(2026, 1, 2, 0, 0)
    return [
        data.Candle(
            open_time=base + timedelta(minutes=index),
            open=o, high=h, low=l, close=c,
            volume=10.0, quote_volume=10.0 * c, number_of_trades=100,
            taker_buy_base_volume=5.0, taker_buy_quote_volume=5.0 * c,
        )
        for index, (o, h, l, c) in enumerate(specs)
    ]


_ALL_EXITS = sorted(backtest_module.EXIT_OUTCOMES)


def _ohlc_candles(specs):
    from datetime import timedelta
    from btcusdt_quant import data
    base = data.utc_minute(2026, 1, 2, 0, 0)
    return [
        data.Candle(
            open_time=base + timedelta(minutes=index),
            open=o, high=h, low=l, close=c,
            volume=10.0, quote_volume=10.0 * c, number_of_trades=100,
            taker_buy_base_volume=5.0, taker_buy_quote_volume=5.0 * c,
        )
        for index, (o, h, l, c) in enumerate(specs)
    ]


class MakerFillTests(unittest.TestCase):
    """--maker-fill-window: resting-limit entries with adverse selection and
    missed (unfilled) orders, vs the default instant taker fill."""

    class _AlwaysLong:
        def probability(self, values) -> float:
            return 0.9

    def _candles(self, specs):
        return _ohlc_candles(specs)

    def _run(self, specs, window, penetration=0.0):
        return run_backtest(
            self._candles(specs),
            model=self._AlwaysLong(),
            position_size=0.1,
            label_horizon=10,
            cooldown_bars=0,
            long_threshold=0.6,
            short_threshold=0.01,
            maker_fill_window=window,
            maker_fill_penetration=penetration,
            # These cases are about the ENTRY leg. The default execution is
            # limit-only on both legs, so pin taker exits to keep the entry the
            # only thing under test.
            maker_exit_outcomes=[],
        )

    def test_taker_default_fills_at_close(self) -> None:
        # window 0 = unchanged instant taker fill at bar-0 close.
        specs = [(100.0, 101.0, 99.0, 100.0)] + [(100.0, 101.0, 99.0, 100.0)] * 20
        result = self._run(specs, window=0)
        self.assertGreater(result.trade_count, 0)
        first = result.trades[0]
        self.assertFalse(first.entry_maker)
        self.assertAlmostEqual(first.entry_price, 100.0)
        # taker charges BOTH sides: fee_pct == 2 * fee_rate_per_side
        self.assertAlmostEqual(first.fee_pct, 2.0 * result.fee_rate_per_side)
        self.assertEqual(result.maker_fill_diagnostics, {})
        # mean_*_bps_per_trade is the SIMPLE per-trade mean, not
        # total_return / trade_count (which is equity-weighted, because trade
        # PnL compounds). Comparing expectancy against a per-trade constant
        # cost requires the simple mean.
        expected = sum(t.pnl_pct for t in result.trades) / len(result.trades) * 1e4
        self.assertAlmostEqual(result.mean_net_bps_per_trade, expected)

    def test_maker_fills_when_price_returns_and_waives_entry_cost(self) -> None:
        # bar 0 signals BUY -> limit at close 100. bar 1 dips to low 99 <= 100
        # -> fill at 100 on bar 1 (a LATER bar), entry_maker True.
        specs = [(100.0, 100.2, 99.8, 100.0)]              # signal bar
        specs += [(100.1, 100.6, 99.0, 100.2)]             # bar1: low 99 <= 100 -> fills
        specs += [(100.2, 100.4, 100.0, 100.3)] * 20       # hold to timeout
        result = self._run(specs, window=5)
        self.assertGreater(result.trade_count, 0)
        first = result.trades[0]
        self.assertTrue(first.entry_maker)
        self.assertAlmostEqual(first.entry_price, 100.0)
        # A resting limit saves the entry SLIPPAGE (you named the price) and
        # gets the cheaper MAKER fee -- but it is not free: only a rebate tier
        # makes a resting fill cost nothing, and this account has none. So the
        # entry pays the maker rate and the exit the taker rate.
        # Both halves were wrong at different times: the entry fee was waived
        # entirely, and before that the maker rate was charged on taker fills.
        self.assertAlmostEqual(
            first.fee_pct, result.maker_fee_rate_per_side + result.fee_rate_per_side
        )
        self.assertLess(result.maker_fee_rate_per_side, result.fee_rate_per_side)
        self.assertAlmostEqual(first.slippage_pct, 1.0 * result.slippage_rate_per_side)
        self.assertGreaterEqual(result.maker_fill_diagnostics["orders_filled"], 1)

    def test_maker_unfilled_when_price_runs_away(self) -> None:
        # Monotonic ramp: every later low is above every prior close, so no
        # resting BUY limit is ever touched -> no trade, all orders unfilled.
        specs = [(100.0 + 5 * k, 100.0 + 5 * k + 1.0, 100.0 + 5 * k - 1.0, 100.0 + 5 * k) for k in range(20)]
        result = self._run(specs, window=5)
        self.assertEqual(result.trade_count, 0)
        self.assertGreaterEqual(result.maker_fill_diagnostics["orders_placed"], 1)
        self.assertEqual(result.maker_fill_diagnostics["orders_filled"], 0)
        self.assertGreaterEqual(result.maker_fill_diagnostics["orders_expired"], 1)
        # The accounting must close: every order placed ends up filled, expired
        # or Kelly-refused. An order still resting at the window edge used to
        # vanish from the totals.
        diag = result.maker_fill_diagnostics
        self.assertEqual(
            diag["orders_placed"],
            diag["orders_filled"] + diag["orders_expired"] + diag["orders_kelly_refused"],
        )

    def test_taker_and_maker_rates_are_distinct(self) -> None:
        # The maker and taker fees are DIFFERENT numbers (Bitget VIP0: 0.02% vs
        # 0.06%). A single rate applied to both sides charged the maker rate for
        # taker fills and under-counted a taker round trip by 8bps. Pin that a taker
        # trade pays 2x taker while a maker-entry trade pays maker + taker, with
        # explicit rates so the assertion does not just restate the defaults.
        specs = [(100.0, 100.2, 99.8, 100.0)]
        specs += [(100.0, 100.05, 99.5, 100.2)]
        specs += [(100.2, 100.4, 100.0, 100.3)] * 20
        common = dict(
            model=self._AlwaysLong(), position_size=0.1, label_horizon=10,
            cooldown_bars=0, long_threshold=0.6, short_threshold=0.01,
            fee_rate_per_side=0.0006, maker_fee_rate_per_side=0.0002,
            slippage_rate_per_side=0.0, maker_exit_outcomes=[],
        )
        taker = run_backtest(self._candles(specs), maker_fill_window=0, **common)
        maker = run_backtest(self._candles(specs), maker_fill_window=5, **common)
        self.assertFalse(taker.trades[0].entry_maker)
        self.assertAlmostEqual(taker.trades[0].fee_pct, 0.0012)   # 6 + 6 bps
        self.assertTrue(maker.trades[0].entry_maker)
        self.assertAlmostEqual(maker.trades[0].fee_pct, 0.0008)   # 2 + 6 bps
        # A maker rebate is representable (negative rate), but must be opt-in.
        rebate = run_backtest(
            self._candles(specs), maker_fill_window=5,
            **{**common, "maker_fee_rate_per_side": -0.0001},
        )
        self.assertAlmostEqual(rebate.trades[0].fee_pct, 0.0005)  # -1 + 6 bps

    def test_cost_basis_is_shared_between_training_and_backtest(self) -> None:
        # Threshold selection charges training.DEFAULT_ROUND_TRIP_COST while
        # execution charges backtest.DEFAULT_ROUND_TRIP_COST_PCT. They are
        # separate literals (backtest imports live, training does not), and they
        # drifted: training stayed at 0.0008 -- 2 x (MAKER fee + slippage) --
        # after the backtest moved to the real taker rate, so thresholds were
        # picked against half the cost execution pays and admitted signals whose
        # gross edge dies in fees. Whoever re-tiers the account must move both.
        self.assertAlmostEqual(
            training.DEFAULT_ROUND_TRIP_COST, backtest_module.DEFAULT_ROUND_TRIP_COST_PCT
        )
        # And it is the LIMIT-ONLY round trip: both legs rest, so two maker fees
        # and no slippage. It was the taker round trip (4x larger) until
        # 2026-08-04, which priced an execution this account does not use and
        # rejected every edge living between the two numbers.
        self.assertAlmostEqual(
            backtest_module.DEFAULT_ROUND_TRIP_COST_PCT,
            2.0 * backtest_module.DEFAULT_MAKER_FEE_RATE_PER_SIDE,
        )
        self.assertLess(
            backtest_module.DEFAULT_ROUND_TRIP_COST_PCT,
            2.0 * (backtest_module.DEFAULT_TAKER_FEE_RATE_PER_SIDE
                   + backtest_module.DEFAULT_SLIPPAGE_RATE_PER_SIDE),
        )
        self.assertGreater(
            backtest_module.DEFAULT_TAKER_FEE_RATE_PER_SIDE,
            backtest_module.DEFAULT_MAKER_FEE_RATE_PER_SIDE,
        )

    def test_maker_exit_prices_the_exit_leg_as_a_resting_limit(self) -> None:
        # Bitget can attach TP/SL as limit orders at open, so the exit leg can be
        # maker too. Cost is per LEG: each side pays maker-or-taker fee and pays
        # slippage only if it crossed. The exit used to be hardcoded taker.
        specs = [(100.0, 100.2, 99.8, 100.0)]
        specs += [(100.0, 100.05, 99.5, 100.2)]
        specs += [(100.2, 100.4, 100.0, 100.3)] * 20
        common = dict(
            model=self._AlwaysLong(), position_size=0.1, label_horizon=10,
            cooldown_bars=0, long_threshold=0.6, short_threshold=0.01,
            fee_rate_per_side=0.0006, maker_fee_rate_per_side=0.0002,
            slippage_rate_per_side=0.0001,
        )
        # maker entry + maker exit: 2+2 bps fee, no slippage on either leg.
        both = run_backtest(self._candles(specs), maker_fill_window=5, maker_exit_outcomes=_ALL_EXITS, **common)
        self.assertAlmostEqual(both.trades[0].fee_pct, 0.0004)
        self.assertAlmostEqual(both.trades[0].slippage_pct, 0.0)
        # maker entry + taker exit: 2+6 bps fee, slippage on the exit leg only.
        mixed = run_backtest(self._candles(specs), maker_fill_window=5, maker_exit_outcomes=[], **common)
        self.assertAlmostEqual(mixed.trades[0].fee_pct, 0.0008)
        self.assertAlmostEqual(mixed.trades[0].slippage_pct, 0.0001)
        # taker entry + maker exit: 6+2 bps fee, slippage on the entry leg only.
        taker_in = run_backtest(self._candles(specs), maker_fill_window=0, maker_exit_outcomes=_ALL_EXITS, **common)
        self.assertAlmostEqual(taker_in.trades[0].fee_pct, 0.0008)
        self.assertAlmostEqual(taker_in.trades[0].slippage_pct, 0.0001)
        # Resting both legs must be the cheapest of the three.
        self.assertLess(both.trades[0].cost_pct, mixed.trades[0].cost_pct)
        self.assertLess(both.trades[0].cost_pct, taker_in.trades[0].cost_pct)

    def test_short_trained_model_is_not_traded_backwards(self) -> None:
        # A model artifact is just a score unless it says which side a high one
        # means. The single-model backtest path assumed high = long, so a model
        # trained on short_success or short_profitability would have been BOUGHT
        # exactly where it says to sell, and its reported performance would have
        # been for the opposite trades. Only the regime-bundle path escaped it,
        # and only because the file is named short_model.json.
        specs = [(100.0, 100.2, 99.8, 100.0)]
        specs += [(100.0, 100.05, 99.5, 100.2)]
        specs += [(100.2, 100.4, 100.0, 100.3)] * 20

        class _ShortModel:
            train_target = "short_profitability"
            def probability(self, values) -> float:
                return 0.9

        common = dict(position_size=0.1, label_horizon=10, cooldown_bars=0,
                      long_threshold=0.6, short_threshold=0.01)
        long_run = run_backtest(_ohlc_candles(specs), model=self._AlwaysLong(), **common)
        short_run = run_backtest(_ohlc_candles(specs), model=_ShortModel(), **common)
        # Same score, opposite side, because the artifact says what it learned.
        self.assertEqual(long_run.signal_counts["BUY"] > 0, True)
        self.assertEqual(long_run.signal_counts["SELL"], 0)
        self.assertEqual(short_run.signal_counts["SELL"] > 0, True)
        self.assertEqual(short_run.signal_counts["BUY"], 0)
        # An artifact written before the marker existed is read as long, which
        # is what it was.
        self.assertFalse(backtest_module.model_is_short_sided(self._AlwaysLong()))
        self.assertTrue(backtest_module.model_is_short_sided(_ShortModel()))

        # And it must survive the LOAD, which the check above does not prove:
        # this test's models carry the attribute because the test set it, while
        # every adapter's from_dict reads only the fields it needs to rebuild
        # the estimator and drops the rest. The marker was written to model.json
        # and then thrown away on the way back in, so a real short artifact
        # loaded through the CLI still answered "long" -- the exact backwards
        # trade this whole guard exists to stop.
        import json as _json, tempfile
        from pathlib import Path as _Path
        from btcusdt_quant import live as _live, models as _models
        fitted = _models.CentroidLinearClassifier()
        fitted.fit([[0.0], [1.0]], [0, 1])
        fitted.feature_names = ["a"]
        payload = dict(fitted.as_dict())
        payload["train_target"] = "short_profitability"
        with tempfile.TemporaryDirectory() as tmp:
            artifact = _Path(tmp) / "model.json"
            artifact.write_text(_json.dumps(payload), encoding="utf-8")
            loaded = _live.load_model_artifact(artifact)
            self.assertEqual(backtest_module.model_train_target(loaded), "short_profitability")
            self.assertTrue(backtest_module.model_is_short_sided(loaded))
            # No marker still means long, not "unknown, refuse to trade".
            payload.pop("train_target")
            artifact.write_text(_json.dumps(payload), encoding="utf-8")
            self.assertIsNone(backtest_module.model_train_target(_live.load_model_artifact(artifact)))

    def test_train_target_survives_a_frozen_adapter(self) -> None:
        # Two adapters are frozen dataclasses, where plain assignment raises
        # FrozenInstanceError -- a subclass of AttributeError. The loader caught
        # that and moved on, so the load succeeded, the marker vanished, and a
        # short-trained stacking or multi-horizon ensemble was read as LONG and
        # bought exactly where it said to sell. Same bug as the one the marker
        # was added to fix, wearing a different hat.
        import dataclasses
        from btcusdt_quant import ensemble as _ens, live as _live

        for cls in (_ens.StackingEnsembleAdapter, _ens.MultiHorizonEnsembleAdapter):
            self.assertTrue(dataclasses.fields(cls) is not None)
            self.assertTrue(cls.__dataclass_params__.frozen, cls.__name__)
            frozen = object.__new__(cls)
            with self.assertRaises(dataclasses.FrozenInstanceError):
                frozen.train_target = "short_profitability"
            # The loader's mechanism must reach it anyway.
            object.__setattr__(frozen, "train_target", "short_profitability")
            self.assertTrue(backtest_module.model_is_short_sided(frozen))

        # And a target that genuinely cannot be attached must raise rather than
        # load a model whose side is unknown -- unknown reads as long.
        class _Slotted:
            __slots__ = ()
        import json as _json, tempfile
        from pathlib import Path as _Path
        from btcusdt_quant import models as _models
        fitted = _models.CentroidLinearClassifier()
        fitted.fit([[0.0], [1.0]], [0, 1])
        fitted.feature_names = ["a"]
        payload = dict(fitted.as_dict())
        payload["train_target"] = "short_profitability"
        with tempfile.TemporaryDirectory() as tmp:
            artifact = _Path(tmp) / "model.json"
            artifact.write_text(_json.dumps(payload), encoding="utf-8")
            loaded = _live.load_model_artifact(artifact)
            self.assertEqual(backtest_module.model_train_target(loaded), "short_profitability")

    def test_two_sided_checks_the_long_slot_not_only_the_short(self) -> None:
        # Nothing stopped a short artifact being passed as --model-artifact,
        # where it becomes the LONG probability: P(short wins) would drive BUY
        # signals on the bars most likely to fall, and the run would print a
        # reassuring "two-sided" line. Only the short slot was ever validated.
        import inspect
        from btcusdt_quant import cli as _cli

        src = inspect.getsource(_cli.main)
        self.assertIn("long_target = backtest.model_train_target(model)", src)
        self.assertIn("backtest.model_is_short_sided(model)", src)
        # Both slots warn when the artifact predates the marker, rather than
        # assuming the caller got the order right.
        self.assertIn("the long slot's", src)

    def test_two_sided_models_score_both_sides_without_a_regime(self) -> None:
        # Before this, the ONLY backtest path that scored long and short on the
        # same bar was the regime bundle, so running two-sided meant writing a
        # fake bundle to disk with both models in a "range" cell -- which also
        # switched on the range mean-reversion gate by accident. The synthetic
        # cell is named "all" so that gate stays a separate lever.
        from btcusdt_quant.cli import TwoSidedModels

        class _P:
            def __init__(self, p: float, target: str | None = None) -> None:
                self._p, self.train_target = p, target
            def probability(self, values) -> float:
                return self._p

        specs = [(100.0, 100.2, 99.8, 100.0)]
        specs += [(100.0, 100.05, 99.5, 100.2)]
        specs += [(100.2, 100.4, 100.0, 100.3)] * 20
        candles = _ohlc_candles(specs)
        common = dict(position_size=0.1, label_horizon=10, cooldown_bars=0,
                      default_regime="all", model=None)

        # The short model's score is used AS-IS, not inverted: a short-target
        # model already outputs P(short wins). Inverting it here (as the
        # single-model path must, having only one score) would sell the bars it
        # rates least likely to fall.
        shorty = TwoSidedModels(_P(0.05), _P(0.95, "short_profitability"))
        short_run = run_backtest(candles, models_by_regime={"all": shorty},
                                 long_threshold=0.6, short_threshold=0.6, **common)
        self.assertGreater(short_run.signal_counts["SELL"], 0)
        self.assertEqual(short_run.signal_counts["BUY"], 0)

        longy = TwoSidedModels(_P(0.95), _P(0.05, "short_profitability"))
        long_run = run_backtest(candles, models_by_regime={"all": longy},
                                long_threshold=0.6, short_threshold=0.6, **common)
        self.assertGreater(long_run.signal_counts["BUY"], 0)
        self.assertEqual(long_run.signal_counts["SELL"], 0)

        # One side missing must produce no signal for it, not a 0.0 that reads
        # as a confident "no" -- has_side_probability is what the backtest asks.
        long_only = TwoSidedModels(_P(0.95), None)
        self.assertEqual(sorted(long_only.direction_policy["all"]), ["LONG"])
        self.assertFalse(long_only.has_side_probability("all", "short"))
        self.assertIsNone(long_only.probability_for("all", "short", {}))
        one_sided = run_backtest(candles, models_by_regime={"all": long_only},
                                 long_threshold=0.6, short_threshold=0.99, **common)
        self.assertEqual(one_sided.signal_counts["SELL"], 0)

        # Not "range": the range gate keys off that literal name.
        self.assertNotIn("range", TwoSidedModels(_P(0.5), _P(0.5)).direction_policy)
        with self.assertRaises(ValueError):
            TwoSidedModels(None, None)

    def test_rolling_quantile_threshold_holds_selectivity_not_a_level(self) -> None:
        # A fixed probability cutoff fixes a NUMBER, not a selectivity: once the
        # score distribution moves, the cut that took the top 5% of bars takes
        # some other fraction. Measured on 2026 H1, the horizon-return model
        # kept its ranking (top 2% still separated from top 10%) while the level
        # drifted, so the trained cutoff selected a different slice.
        import numpy as np
        from btcusdt_quant.backtest import RollingQuantileThreshold, QuantileEntryThresholds

        rng = random.Random(11)
        sample = [rng.random() for _ in range(40_000)]
        est = RollingQuantileThreshold(0.95, warmup=1_000)
        for value in sample:
            est.observe(value)
        # Bucketed to 1e-4, so it must agree with the exact quantile to a bucket.
        self.assertAlmostEqual(est.threshold(), float(np.quantile(sample, 0.95)), places=3)

        # A finite window must FORGET, which is the whole point: expanding over
        # 2.65M banked rows barely moves when 130k new ones arrive, so it
        # reproduces a fixed threshold at greater cost.
        rolling = RollingQuantileThreshold(0.5, window=1_000, warmup=100)
        for _ in range(3_000):
            rolling.observe(rng.uniform(0.0, 0.2))
        low = rolling.threshold()
        for _ in range(3_000):
            rolling.observe(rng.uniform(0.8, 1.0))
        self.assertLess(low, 0.25)
        self.assertGreater(rolling.threshold(), 0.75)

        # Strictly past-only: reading happens before folding this bar in, so a
        # bar is never part of the reference set that judges it.
        one = RollingQuantileThreshold(0.5, warmup=1)
        self.assertIsNone(one.resolve(0.9))          # nothing seen yet
        self.assertEqual(one.resolve(0.9), 0.9)      # now judged by the first
        # Warmup abstains rather than trading on an estimate built from a
        # handful of bars.
        cold = RollingQuantileThreshold(0.9, warmup=50)
        self.assertIsNone(cold.threshold())
        self.assertEqual(QuantileEntryThresholds(long=cold).resolve(0.5, 0.5), (None, None))
        with self.assertRaises(ValueError):
            RollingQuantileThreshold(0.0)
        with self.assertRaises(ValueError):
            RollingQuantileThreshold(1.0)

        # Warmup scales with how thin the tail is, because what makes a tail
        # quantile stable is the count IN the tail. A flat default sized for an
        # ungated 260k-bar window starved a gated one: behind a gate passing
        # 11% of bars it ate two thirds of the run before the first trade.
        self.assertEqual(RollingQuantileThreshold(0.5)._warmup, 2_000)     # floor
        self.assertEqual(RollingQuantileThreshold(0.95)._warmup, 3_999)    # 200/0.05
        self.assertEqual(RollingQuantileThreshold(0.99)._warmup, 19_999)   # 200/0.01
        self.assertEqual(RollingQuantileThreshold(0.95, warmup=50)._warmup, 50)

    def test_entry_quantile_stands_aside_during_warmup(self) -> None:
        # None from the estimator means "no basis yet", not "no threshold". If
        # it fell through to the learned/strategy cutoff, the opening stretch of
        # every run would silently trade on the fixed threshold the flag was
        # passed to replace -- and it is the longest stretch nobody looks at.
        from btcusdt_quant.cli import TwoSidedModels

        class _P:
            train_target = None
            def __init__(self, p: float) -> None:
                self._p = p
            def probability(self, values) -> float:
                return self._p

        specs = [(100.0, 100.2, 99.8, 100.0)]
        specs += [(100.0, 100.05, 99.5, 100.2)]
        specs += [(100.2, 100.4, 100.0, 100.3)] * 20
        candles = _ohlc_candles(specs)
        both = TwoSidedModels(_P(0.99), _P(0.10))
        common = dict(models_by_regime={"all": both}, default_regime="all", model=None,
                      position_size=0.1, label_horizon=10, cooldown_bars=0)
        # A near-certain probability trades on a fixed cutoff...
        hot = run_backtest(candles, long_threshold=0.6, short_threshold=0.6, **common)
        self.assertGreater(hot.signal_counts["BUY"] + hot.signal_counts["SELL"], 0)
        # ...and stands aside under a quantile that has not warmed up.
        cold = run_backtest(candles, entry_quantile=0.05, **common)
        self.assertEqual(cold.signal_counts["BUY"], 0)
        self.assertEqual(cold.signal_counts["SELL"], 0)

    def test_vol_gate_suppresses_entries_without_stranding_positions(self) -> None:
        # The gate sits before model inference, and the exit and maker-fill
        # blocks sit AFTER it. Skipping the rest of a gated bar would leave an
        # open position unable to close and a resting order unable to fill, so
        # the gate would rewrite the execution model instead of filtering
        # entries -- and a backtest whose trades never exit still reports a
        # number.
        from btcusdt_quant.cli import TwoSidedModels

        class _P:
            train_target = None
            def __init__(self, p: float) -> None:
                self._p = p
            def probability(self, values) -> float:
                return self._p

        specs = [(100.0, 100.2, 99.8, 100.0)]
        specs += [(100.0, 100.05, 99.5, 100.2)]
        specs += [(100.2, 100.4, 100.0, 100.3)] * 40
        candles = _ohlc_candles(specs)
        common = dict(models_by_regime={"all": TwoSidedModels(_P(0.99), _P(0.10))},
                      default_regime="all", model=None, position_size=0.1,
                      label_horizon=10, cooldown_bars=0,
                      long_threshold=0.6, short_threshold=0.6)

        ungated = run_backtest(candles, **common)
        self.assertGreater(len(ungated.trades), 0)
        # Every trade must still have an exit -- this is what the naive
        # `continue` broke.
        self.assertTrue(all(t.exit_time for t in ungated.trades))

        # rv_60 is a real feature but is ~0 on this flat fixture, so a positive
        # minimum gates every bar.
        gated = run_backtest(candles, vol_gate_feature="rv_60", vol_gate_min=1.0, **common)
        self.assertEqual(gated.signal_counts["BUY"], 0)
        self.assertEqual(gated.signal_counts["SELL"], 0)
        self.assertEqual(len(gated.trades), 0)
        diag = gated.vol_gate_diagnostics
        self.assertEqual(diag["bars_eligible"], 0)
        self.assertGreater(diag["bars_skipped"], 0)
        self.assertEqual(diag["eligible_share"], 0.0)

        # A minimum of 0 lets everything through and must reproduce the ungated
        # run exactly: the gate is a filter, not a change of execution.
        passthrough = run_backtest(candles, vol_gate_feature="rv_60", vol_gate_min=0.0, **common)
        self.assertEqual(len(passthrough.trades), len(ungated.trades))
        self.assertEqual(passthrough.signal_counts, ungated.signal_counts)
        self.assertEqual(passthrough.vol_gate_diagnostics["eligible_share"], 1.0)

        # A missing feature is gated, not treated as zero-and-eligible.
        absent = run_backtest(candles, vol_gate_feature="not_a_feature", vol_gate_min=0.0, **common)
        self.assertEqual(len(absent.trades), 0)

    def test_fold_trading_metrics_can_be_restricted_to_gated_bars(self) -> None:
        # The ungated fold metric averages in the bars a gate would refuse, so a
        # gated strategy cannot be judged from it at all -- and the fold test
        # slices are the ONLY unseen windows this pipeline makes, since the
        # saved model is refit over every labeled row. Without an eligibility
        # mask the only way left to score a gate is the single real holdout,
        # which then stops being a holdout.
        from btcusdt_quant import training as _tr

        # Two winners at high probability, two losers at low -- but the winners
        # are the INELIGIBLE ones, so gating must change the answer, not just
        # shrink the sample.
        probs = [0.9, 0.8, 0.3, 0.2]
        payoffs = [0.004, 0.004, -0.002, -0.002]
        ungated = _tr.oos_trading_metrics(probs, payoffs, 0.5, round_trip_cost=0.0004)
        gated = _tr.oos_trading_metrics(probs, payoffs, 0.5, round_trip_cost=0.0004,
                                        eligible=[False, False, True, True])
        self.assertEqual(ungated["eligible_share"], 1.0)
        self.assertEqual(ungated["rows"], 4.0)
        self.assertEqual(gated["eligible_share"], 0.5)
        self.assertEqual(gated["rows"], 2.0)
        # No eligible row is above the threshold, so the gated primary book is
        # empty and cannot report a gross -- not zero, which would read as a
        # measured break-even.
        self.assertEqual(gated["entry_rate"], 0.0)
        self.assertNotEqual(gated["long_gross_bps"], gated["long_gross_bps"])  # NaN
        self.assertGreater(ungated["long_gross_bps"], 0.0)
        # An empty mask still REPORTS the fold -- see the dedicated test for
        # why returning {} was wrong -- but carries no gross, because a zero
        # there would read as a measured break-even.
        empty = _tr.oos_trading_metrics(probs, payoffs, 0.5, eligible=[False] * 4)
        self.assertTrue(empty["no_eligible_rows"])
        self.assertNotIn("long_gross_bps", empty)
        # The gate is configuration, not a change to the model.
        cfg = _tr.TrainingConfig(vol_gate_feature="rv_60", vol_gate_min=0.001)
        self.assertEqual((cfg.vol_gate_feature, cfg.vol_gate_min), ("rv_60", 0.001))
        self.assertIsNone(_tr.TrainingConfig().vol_gate_feature)
        self.assertIn("rv_60", _tr._PERSISTED_VOLATILITY_FEATURES)

    def test_a_fold_the_gate_emptied_is_still_counted(self) -> None:
        # A fold with no eligible bars used to return {} and be filtered out by
        # the aggregate's `if result:`. That removes exactly the folds the gate
        # refused hardest -- the likeliest bad ones -- and leaves fold_count
        # describing a different set of folds than the summary claims. The
        # gate would then look better the worse it was.
        from btcusdt_quant import training as _tr

        good = _tr.oos_trading_metrics([0.9, 0.1], [0.004, -0.002], 0.5,
                                       round_trip_cost=0.0004, eligible=[True, True])
        emptied = _tr.oos_trading_metrics([0.9, 0.1], [0.004, -0.002], 0.5,
                                          round_trip_cost=0.0004, eligible=[False, False])
        # Truthy, so no `if result:` caller can drop it.
        self.assertTrue(emptied)
        self.assertTrue(emptied["no_eligible_rows"])
        self.assertEqual(emptied["eligible_share"], 0.0)

        summary = _tr.summarise_fold_trading([good, emptied, good])
        self.assertEqual(summary["fold_count"], 3)
        self.assertEqual(summary["folds_without_eligible_rows"], 1)
        self.assertEqual(summary["folds_without_eligible_rows"], 1)
        # The emptied fold contributes no net figure -- but it must not crash
        # the aggregate either. `x == x` alone is False only for NaN; a MISSING
        # key returns None and None == None is True, so the old filter would
        # have indexed a key the emptied fold does not have.
        self.assertEqual(len(summary["long_net_bps_by_fold"]), 2)
        self.assertEqual(summary["long_folds_profitable"], 2)

    def test_fold_mean_does_not_let_a_28_trade_fold_outvote_a_765_trade_one(self) -> None:
        # The plain mean averages fold MEANS, so it weights folds equally no
        # matter how many trades each made. Ungated the counts are similar and
        # it does not matter; under a gate they diverge by more than an order
        # of magnitude. The first gated long run reported +7.63 bps and "3/4
        # folds profitable" while its trade-weighted result was -1.66 -- the
        # two profitable folds had 28 and 29 trades against a per-trade sigma
        # near 26 bps, and the one fold with real size lost 5.7 bps at t=-5.7.
        from btcusdt_quant import training as _tr

        # 28 trades at +10 bps gross, against 765 trades at -2 bps gross.
        tiny = _tr.oos_trading_metrics([0.9] * 28, [0.0014] * 28, 0.5, round_trip_cost=0.0004)
        big = _tr.oos_trading_metrics([0.9] * 765 + [0.1] * 100,
                                      [-0.0002] * 765 + [0.001] * 100, 0.5,
                                      round_trip_cost=0.0004)
        summary = _tr.summarise_fold_trading([tiny, big])
        self.assertEqual(summary["long_trades_by_fold"], [28.0, 765.0])
        # Equal weighting calls it profitable; trade weighting does not.
        self.assertGreater(summary["long_net_bps_mean"], 0.0)
        self.assertLess(summary["long_net_bps_trade_weighted"], 0.0)

    def test_gate_cutoff_can_be_chosen_inside_the_fold(self) -> None:
        # An absolute cutoff derived over the whole span is not fold-clean:
        # that span contains every fold's test slice. Selecting the cutoff from
        # the fold's own TRAIN rows is what keeps the gated metric out of
        # sample, and the number actually used has to be on the record -- a
        # config value that was overridden per fold is not evidence.
        from btcusdt_quant import training as _tr

        cfg = _tr.TrainingConfig(vol_gate_feature="rv_60", vol_gate_train_quantile=0.8)
        self.assertEqual(cfg.vol_gate_train_quantile, 0.8)
        self.assertIsNone(_tr.TrainingConfig().vol_gate_train_quantile)
        self.assertIsNone(_tr.FoldResult(
            fold_index=0, split=None, threshold=0.5, calibration_offset=0.0,
            calibration_details={}, validation_metrics={}, test_metrics={},
            train_metrics={}, model_selection={},
        ).vol_gate_min_used)

    def test_trend_filter_blocks_entries_against_the_trend(self) -> None:
        # The gated long edge is directional, not universal: on the fold test
        # slices it paid +2.55 and +2.38 bps in the two uptrend folds and gave
        # it all back at -3.37 in the -41% crash fold, and the short side could
        # not hedge because it loses everywhere. Requiring close > SMA removed
        # the crash fold entirely and took the pooled result from +0.18 bps
        # (t=+0.34) to +1.98 (t=+2.47).
        from btcusdt_quant.cli import TwoSidedModels

        class _P:
            train_target = None
            def __init__(self, p: float) -> None:
                self._p = p
            def probability(self, values) -> float:
                return self._p

        common = dict(models_by_regime={"all": TwoSidedModels(_P(0.99), _P(0.10))},
                      default_regime="all", model=None, position_size=0.1,
                      label_horizon=10, cooldown_bars=0,
                      long_threshold=0.6, short_threshold=0.6)

        # A series that falls and then dips further: close sits below its own
        # trailing mean, so a long is against the trend.
        falling = [(100.0 - i, 100.5 - i, 99.0 - i, 100.0 - i) for i in range(40)]
        candles = _ohlc_candles(falling)
        unfiltered = run_backtest(candles, **common)
        self.assertGreater(unfiltered.signal_counts["BUY"], 0)

        filtered = run_backtest(candles, trend_filter_sma_bars=5, **common)
        self.assertEqual(filtered.signal_counts["BUY"], 0)
        self.assertGreater(filtered.trend_filter_diagnostics["signals_blocked"], 0)
        self.assertEqual(filtered.trend_filter_diagnostics["sma_bars"], 5)

        # Rising: the same model is allowed through, so the filter is reading
        # the trend rather than simply refusing everything.
        rising = [(100.0 + i, 100.5 + i, 99.5 + i, 100.0 + i) for i in range(40)]
        allowed = run_backtest(_ohlc_candles(rising), trend_filter_sma_bars=5, **common)
        self.assertGreater(allowed.signal_counts["BUY"], 0)

        # Before the window fills there is no trend, and an unknown trend is not
        # an uptrend -- a warmup bar must be refused, not waved through.
        cold = run_backtest(_ohlc_candles(rising), trend_filter_sma_bars=10_000, **common)
        self.assertEqual(cold.signal_counts["BUY"], 0)
        self.assertEqual(cold.signal_counts["SELL"], 0)

        # 0 disables it, reproducing the unfiltered run exactly: a filter, not a
        # change to execution.
        off = run_backtest(candles, trend_filter_sma_bars=0, **common)
        self.assertEqual(off.signal_counts, unfiltered.signal_counts)
        self.assertEqual(len(off.trades), len(unfiltered.trades))

    def test_a_fold_vote_reports_whether_its_folds_are_independent(self) -> None:
        # "12 of 15 folds positive" reads as fifteen confirmations. In CPCV the
        # same rows recur across test combinations, and the first gated run put
        # 86% of its entries in calendar 2021 with none at all in 2022 -- one
        # regime counted fifteen times. The vote cannot be read alone, so the
        # numbers that qualify it ship beside it.
        from datetime import datetime, timedelta, timezone as _tz
        from btcusdt_quant import training as _tr

        stamps = [datetime(2021, 3, 1, tzinfo=_tz.utc)] * 3 + [datetime(2022, 7, 1, tzinfo=_tz.utc)]
        metrics = _tr.oos_trading_metrics(
            [0.9, 0.9, 0.1, 0.9], [0.004, -0.002, 0.004, 0.004], 0.5,
            round_trip_cost=0.0004, row_times=stamps,
        )
        self.assertEqual(metrics["coverage"]["entries_by_year"], {2021: 2, 2022: 1})
        self.assertEqual(metrics["coverage"]["unique_months"], 2)
        # Coverage is additional, not a replacement: the payoff figures survive.
        self.assertGreater(metrics["long_gross_bps"], 0.0)
        self.assertEqual(metrics["long_trades"], 3.0)
        # Under a gate the timestamps must follow the SURVIVING rows, not the
        # original positions -- an off-by-one here would attribute entries to
        # the wrong year and the independence check would pass on noise.
        gated = _tr.oos_trading_metrics(
            [0.9, 0.9, 0.1, 0.9], [0.004, -0.002, 0.004, 0.004], 0.5,
            round_trip_cost=0.0004, eligible=[False, False, True, True], row_times=stamps,
        )
        self.assertEqual(gated["coverage"]["entries_by_year"], {2022: 1})

        class _Split:
            def __init__(self, test):
                self.test = test

        def _disjoint(n):
            return [_Split(range(i * 1000, (i + 1) * 1000)) for i in range(n)]

        def _overlapping(n):
            # What CPCV produces: test windows that share rows.
            return [_Split(range(i * 500, i * 500 + 1000)) for i in range(n)]

        def _at(year, count, start_minute=0):
            base = datetime(year, 1, 1, tzinfo=_tz.utc)
            return [base + timedelta(minutes=start_minute + i) for i in range(count)]

        def _fold(times):
            return _tr.oos_trading_metrics(
                [0.9] * len(times), [0.004] * len(times), 0.5,
                round_trip_cost=0.0004, row_times=times,
            )

        # The hazard: ONE set of 500 entries replicated across four CPCV folds.
        # Summing per-fold counts saw 2000 entries and two years past any
        # threshold, and certified duplicates as independent evidence.
        shared = _at(2021, 250) + _at(2022, 250)
        duplicated = _tr.summarise_fold_trading(
            [_fold(shared) for _ in range(4)], splits=_disjoint(2))
        self.assertEqual(duplicated["entries_total"], 2000)
        self.assertEqual(duplicated["entries_unique"], 500)
        self.assertEqual(duplicated["overlap_factor"], 4.0)
        # Both years clear the entry floor on the deduplicated count, so the
        # calendar looks fine -- and the vote is still four re-scorings of one
        # set of rows. Overlap has to be part of the flag or the name lies.
        self.assertEqual(duplicated["independent_years"], 2)
        self.assertFalse(duplicated["fold_vote_is_independent_evidence"])

        # Genuinely distinct entries over the same two years do qualify.
        distinct = _tr.summarise_fold_trading([
            _fold(_at(2021, 125) + _at(2022, 125)),
            _fold(_at(2021, 125, 125) + _at(2022, 125, 125)),
        ], splits=_disjoint(2))
        self.assertEqual(distinct["entries_total"], 500)
        self.assertEqual(distinct["entries_unique"], 500)
        self.assertEqual(distinct["overlap_factor"], 1.0)
        self.assertEqual(distinct["independent_years"], 2)
        self.assertTrue(distinct["fold_vote_is_independent_evidence"])

        # One year carrying almost everything is not two years of evidence.
        lopsided = _tr.summarise_fold_trading(
            [_fold(_at(2021, 900) + _at(2022, 5))], splits=_disjoint(2))
        self.assertEqual(lopsided["independent_years"], 1)
        self.assertFalse(lopsided["fold_vote_is_independent_evidence"])

        # Topology decides first. The same folds under a combinatorial splitter
        # cannot be independent evidence however clean their entry overlap
        # looks: CPCV folds can share most of their test rows and still select
        # disjoint entries, which lands overlap_factor at 1.0 and would have
        # certified a correlated vote.
        cpcv = _tr.summarise_fold_trading([
            _fold(_at(2021, 125) + _at(2022, 125)),
            _fold(_at(2021, 125, 125) + _at(2022, 125, 125)),
        ], splits=_overlapping(2))
        self.assertEqual(cpcv["overlap_factor"], 1.0)
        self.assertEqual(cpcv["independent_years"], 2)
        self.assertFalse(cpcv["fold_vote_is_independent_evidence"])
        self.assertGreater(cpcv["shared_test_rows"], 0)
        # Topology is MEASURED, not declared. An earlier version took a cv_mode
        # string, so a caller could hand it CPCV metrics labelled walk_forward
        # and be certified -- the function had no way to check. Now the split
        # index sets are intersected, and no splits means no certification,
        # because unknown is not independent.
        self.assertFalse(_tr.summarise_fold_trading(
            [_fold(_at(2021, 250)), _fold(_at(2022, 250, 250))]
        )["fold_vote_is_independent_evidence"])

        # Summarising must not consume its input. Popping entry_keys in place
        # made a second call see no identities, compute overlap 0.0, and report
        # different numbers than the first.
        again = _tr.summarise_fold_trading([
            _fold(_at(2021, 125) + _at(2022, 125)),
            _fold(_at(2021, 125, 125) + _at(2022, 125, 125)),
        ], splits=_disjoint(2))
        twice = _tr.summarise_fold_trading(again["folds"], splits=_disjoint(2))
        self.assertEqual(again["entries_unique"], 500)
        # The reported copy has no identities, so a re-summary of it cannot
        # invent independence out of nothing.
        self.assertNotIn("entry_keys", again["folds"][0]["coverage"])
        self.assertFalse(twice["fold_vote_is_independent_evidence"])
        # The floor is published, because it is a reporting choice and not a
        # statistical guarantee.
        self.assertEqual(distinct["min_entries_for_an_independent_year"],
                         _tr.MIN_ENTRIES_FOR_AN_INDEPENDENT_YEAR)

    def test_long_only_lets_a_single_model_use_the_entry_quantile(self) -> None:
        # The single-model branch resolved its cutoffs inline and never saw the
        # rolling quantile the bundle paths consult, and the CLI refused the
        # combination outright. Both were right about the danger -- a short
        # there fires because the ONE score is low, so a top-fraction (high)
        # quantile gates it backwards -- and both were too broad: long-only is a
        # legitimate configuration with one score and one side.
        class _Rising:
            train_target = None
            def __init__(self) -> None:
                self._n = 0
            def probability(self, values) -> float:
                self._n += 1
                return min(0.99, 0.30 + self._n * 0.01)

        specs = [(100.0 + i * 0.1, 100.5 + i * 0.1, 99.5 + i * 0.1, 100.0 + i * 0.1) for i in range(60)]
        candles = _ohlc_candles(specs)
        common = dict(position_size=0.1, label_horizon=10, cooldown_bars=0)

        # Without long_only the low-side short still fires on a rising score.
        two_way = run_backtest(candles, model=_Rising(), long_threshold=0.9,
                               short_threshold=0.5, **common)
        self.assertGreater(two_way.signal_counts["SELL"], 0)
        # long_only removes that side rather than gating it wrongly.
        one_way = run_backtest(candles, model=_Rising(), long_threshold=0.9,
                               short_threshold=0.5, long_only=True, **common)
        self.assertEqual(one_way.signal_counts["SELL"], 0)

        # And the quantile now reaches this branch: with warmup unmet nothing
        # trades, which is the "no basis yet" contract, not a fallback to the
        # fixed cutoff the flag replaced.
        cold = run_backtest(candles, model=_Rising(), entry_quantile=0.02,
                            long_only=True, **common)
        self.assertEqual(cold.signal_counts["BUY"], 0)
        self.assertEqual(cold.signal_counts["SELL"], 0)
        warm = run_backtest(candles, model=_Rising(), entry_quantile=0.5,
                            entry_quantile_warmup=5, long_only=True, **common)
        self.assertGreater(warm.signal_counts["BUY"], 0)

        # A short-target model cannot be long-only: there a high score is a SELL.
        class _ShortModel:
            train_target = "short_profitability"
            def probability(self, values) -> float:
                return 0.9
        with self.assertRaises(ValueError):
            run_backtest(candles, model=_ShortModel(), long_only=True, **common)

    def test_short_profitability_mirrors_the_long_label(self) -> None:
        # Under the barrier-free design (barriers set beyond reach) the existing
        # short_success label collapses: every bar times out and it returns 0,
        # so it cannot train anything. profitability escapes that on the long
        # side by counting a timeout as a win when the horizon return clears the
        # threshold; the short side needs the same branch with the sign flipped.
        # Without it, shorts can only be inferred from the bottom of a
        # long-trained probability, which answers a different question -- a low
        # P(return > +thr) covers small POSITIVE returns too.
        from btcusdt_quant.dataset import (
            triple_barrier_label_short,
            triple_barrier_label_short_profitability,
        )
        far, thr = 0.5, 0.0004          # barriers beyond reach, 4 bps threshold
        down = _ohlc_candles([(100.0, 100.1, 99.9, 100.0)] + [(99.9, 100.0, 99.8, 99.9)] * 12)
        up = _ohlc_candles([(100.0, 100.1, 99.9, 100.0)] + [(100.1, 100.2, 100.0, 100.1)] * 12)
        for candles, label, expected in ((down, "falling", 1), (up, "rising", 0)):
            ret = candles[10].close / candles[0].close - 1.0
            old, old_reason = triple_barrier_label_short(0, candles, 10, far, far)
            new, new_reason = triple_barrier_label_short_profitability(0, candles, 10, thr, far, far, ret)
            # The old label is a constant 0 whichever way price went.
            self.assertEqual((old, old_reason), (0, "short_timeout"), label)
            self.assertEqual(new, expected, f"{label}: return {1e4*ret:+.1f} bps")
            self.assertEqual(new_reason, "short_timeout_return")
        # A reachable barrier still decides it, exactly as short_success does.
        crash = _ohlc_candles([(100.0, 100.1, 99.9, 100.0)] + [(99.0, 99.1, 97.0, 97.5)] * 3)
        self.assertEqual(
            triple_barrier_label_short_profitability(0, crash, 3, thr, 0.008, 0.004, -0.02)[1],
            "short_tp_first",
        )
        # And the payoff signer treats it as a short.
        from btcusdt_quant import training as _tr
        self.assertIn("short_profitability", _tr._TRAIN_TARGET_KEYS)

    def test_funding_alignment_carries_only_settled_information(self) -> None:
        # Funding is the one input that is not a transform of OHLCV, so it is
        # the one worth being strict about: filling a bar with the NEXT
        # settlement's rate would put tomorrow's number in today's features, and
        # it would look like signal because funding predicts the forward return.
        from datetime import datetime, timezone as _tz
        from btcusdt_quant import funding_source as fs
        settle = [
            fs.FundingRow(datetime(2026, 1, 1, 0, 0, tzinfo=_tz.utc), 0.0001),
            fs.FundingRow(datetime(2026, 1, 1, 8, 0, tzinfo=_tz.utc), -0.0002),
        ]
        minutes = [
            datetime(2025, 12, 31, 23, 59, tzinfo=_tz.utc),
            datetime(2026, 1, 1, 0, 0, tzinfo=_tz.utc),
            datetime(2026, 1, 1, 7, 59, tzinfo=_tz.utc),
            datetime(2026, 1, 1, 8, 0, tzinfo=_tz.utc),
        ]
        out = fs.funding_features_to_minutes(settle, minutes)
        # Before the first settlement nothing is known -- not even a zero, which
        # would be indistinguishable from a genuine zero rate.
        self.assertNotIn(minutes[0], out)
        # A bar carries the LAST SETTLED rate, never the one still to come.
        self.assertAlmostEqual(out[minutes[1]]["current_rate"], 0.0001)
        self.assertAlmostEqual(out[minutes[2]]["current_rate"], 0.0001)
        self.assertAlmostEqual(out[minutes[3]]["current_rate"], -0.0002)
        # The schedule is public, so counting down to it is causal.
        self.assertAlmostEqual(out[minutes[1]]["minutes_to_next"], 480.0)
        self.assertAlmostEqual(out[minutes[2]]["minutes_to_next"], 1.0)
        # next_rate repeats the SETTLED rate rather than being omitted. Leaving
        # it out does not get next_funding_rate dropped from training --
        # availability is decided per SOURCE, so the feature would train as the
        # constant 0.0 while a live feed publishing a predicted rate hands the
        # model a real number it never saw.
        self.assertAlmostEqual(out[minutes[1]]["next_rate"], out[minutes[1]]["current_rate"])
        # Past the last settlement the schedule is extrapolated, not clamped:
        # clamping pinned minutes_to_next at 0 forever, which reads as "funding
        # is imminent" and latched funding_blackout_active on permanently.
        far = datetime(2026, 1, 2, 12, 30, tzinfo=_tz.utc)   # 28.5h after the last settlement
        tail = fs.funding_features_to_minutes(settle, [far])
        self.assertGreater(tail[far]["minutes_to_next"], 0.0)
        self.assertLessEqual(tail[far]["minutes_to_next"], 480.0)
        # An unreadable archive is refused, not skipped: a dropped month carries
        # the previous rate across the gap and looks like a flat stretch.
        import tempfile
        from pathlib import Path as _P
        with tempfile.TemporaryDirectory() as tmp:
            (_P(tmp) / "BTCUSDT-fundingRate-2026-01.zip").write_bytes(b"not a zip")
            with self.assertRaises(fs.FundingDownloadError):
                fs.load_funding_dir(_P(tmp))
            self.assertEqual(fs.load_funding_dir(_P(tmp), strict=False), [])
        # Overlapping monthly files must not double-count a settlement.
        self.assertEqual(len(fs.dedup_funding_rows(settle + settle)), 2)
        # A header line is data-driven, not assumed.
        parsed = fs.parse_funding_csv_text(
            "calc_time,funding_interval_hours,last_funding_rate\n1767225600000,8,0.00010000\n"
        )
        self.assertEqual(len(parsed), 1)
        self.assertAlmostEqual(parsed[0].funding_rate, 0.0001)

    def test_execution_defaults_to_limit_only(self) -> None:
        # This account never crosses the spread, so a run that forgets the flags
        # must model the execution it actually performs. The defaults were the
        # opposite until 2026-08-04: instant taker entry and taker exits, priced
        # at 16 bps, while threshold selection charged 4 -- the same
        # selection-vs-execution split the cost-basis work keeps closing.
        specs = [(100.0, 100.2, 99.8, 100.0)]
        specs += [(100.0, 100.05, 99.5, 100.2)]
        specs += [(100.2, 100.4, 100.0, 100.3)] * 20
        common = dict(
            model=self._AlwaysLong(), position_size=0.1, label_horizon=10,
            cooldown_bars=0, long_threshold=0.6, short_threshold=0.01,
            fee_rate_per_side=0.0006, maker_fee_rate_per_side=0.0002,
            slippage_rate_per_side=0.0002,
        )
        default = run_backtest(self._candles(specs), **common)
        self.assertTrue(default.trades[0].entry_maker)
        self.assertAlmostEqual(default.trades[0].fee_pct, 0.0004)    # 2 + 2 bps
        self.assertAlmostEqual(default.trades[0].slippage_pct, 0.0)  # nothing crossed
        # The recorded round trip is what the run charged, not a fixed taker
        # figure -- and it matches the constant threshold selection uses.
        self.assertAlmostEqual(default.round_trip_cost_pct, 0.0004)
        self.assertAlmostEqual(default.round_trip_cost_pct,
                               backtest_module.DEFAULT_ROUND_TRIP_COST_PCT)
        # Crossing is still expressible, and then it costs the taker round trip.
        crossing = run_backtest(
            self._candles(specs), maker_fill_window=0, maker_exit_outcomes=[], **common
        )
        self.assertFalse(crossing.trades[0].entry_maker)
        self.assertAlmostEqual(crossing.round_trip_cost_pct, 2.0 * (0.0006 + 0.0002))

    def test_oos_trading_metrics_price_the_ranking_after_cost(self) -> None:
        # The fold loop recorded F1 and Brier and threw away the model and its
        # test-slice probabilities, so this project promoted candidates on a
        # model refit across its whole training span and only discovered the
        # overfit on the single unseen window it ever tried. These metrics turn
        # each fold's test slice into a verdict: does the ranking pay for cost?
        from btcusdt_quant.training import oos_trading_metrics
        # A perfectly informative ranking: probability tracks the return.
        probs = [i / 100.0 for i in range(100)]
        rets = [(i - 50) / 1e4 for i in range(100)]        # -50 bps .. +49 bps
        m = oos_trading_metrics(probs, rets, threshold=0.9, round_trip_cost=0.0004)
        self.assertEqual(m["long_trades"], 10)             # p >= 0.9
        self.assertAlmostEqual(m["long_gross_bps"], 44.5)  # mean of +40..+49
        self.assertAlmostEqual(m["long_net_bps"], 44.5 - 4.0)
        # The short book is the least-confident decile, and shorting losers pays.
        self.assertAlmostEqual(m["short_gross_bps"], 45.5)  # -(mean of -50..-41)
        self.assertAlmostEqual(m["short_net_bps"], 45.5 - 4.0)
        self.assertAlmostEqual(m["all_rows_mean_bps"], -0.5)
        # An uninformative ranking must not look profitable: reverse the returns
        # so high probability marks the WORST bars.
        bad = oos_trading_metrics(probs, list(reversed(rets)), threshold=0.9, round_trip_cost=0.0004)
        self.assertLess(bad["long_net_bps"], 0.0)
        self.assertLess(bad["short_net_bps"], 0.0)
        # Cost is subtracted, not decorative: a ranking whose edge is under the
        # round trip reports a negative net.
        thin = oos_trading_metrics(probs, [0.0002] * 100, threshold=0.5, round_trip_cost=0.0004)
        self.assertAlmostEqual(thin["long_gross_bps"], 2.0)
        self.assertAlmostEqual(thin["long_net_bps"], -2.0)
        self.assertEqual(oos_trading_metrics([], [], 0.5), {})

    def test_positions_never_overlap_in_time(self) -> None:
        # The suite is structurally blind to this class of defect: a backtest
        # can hold two positions at once, or size one with equity that already
        # includes a later bar's PnL, and every price/fee assertion still
        # passes. That is exactly how the removed `sl_fill="next_open"` mode
        # shipped a look-ahead -- it deferred the exit to bar i+1 while
        # cooldown_bars=0 let a new trade open on bar i. Assert the invariant
        # itself, not one mode's symptom.
        specs = [(100.0, 100.6, 99.4, 100.0)]
        specs += [(100.0 + 0.2 * (i % 7 - 3), 101.0, 99.0, 100.0 + 0.2 * (i % 5 - 2)) for i in range(120)]
        for cooldown in (0, 3):
            result = run_backtest(
                _ohlc_candles(specs), model=self._AlwaysLong(), position_size=0.1,
                label_horizon=8, cooldown_bars=cooldown,
                long_threshold=0.6, short_threshold=0.01,
                exec_tp_pct=0.004, exec_sl_pct=0.002,
                maker_fill_window=0, maker_exit_outcomes=[],
            )
            trades = result.trades
            self.assertGreater(len(trades), 1, f"cooldown={cooldown} produced too few trades to test")
            for earlier, later in zip(trades, trades[1:]):
                self.assertLessEqual(
                    earlier.exit_time, later.entry_time,
                    f"cooldown={cooldown}: trade entered at {later.entry_time} before the "
                    f"previous one exited at {earlier.exit_time}",
                )
            for t in trades:
                # OPEN_AT_END is the harness flattening at the window edge, so a
                # position opened on the final bar closes on that same bar. Every
                # other outcome must consume time.
                if t.outcome == "OPEN_AT_END":
                    self.assertLessEqual(t.entry_time, t.exit_time)
                else:
                    self.assertLess(t.entry_time, t.exit_time, "a trade exited at or before its entry")

    def test_entry_signal_picks_the_stronger_side_not_the_first_one(self) -> None:
        # evaluate_entry_signal was `if long ... elif short`, so a bar where the
        # long qualified never scored the short. Long won by source order, not
        # by being the better trade -- and with the long model's probabilities
        # running far above the short model's, that made every long+short bundle
        # effectively long-only.
        from btcusdt_quant.live import evaluate_entry_signal
        kw = dict(min_ev=0.0, long_threshold=0.30, short_threshold=0.30,
                  gross_tp_pct=0.008, gross_sl_pct=0.004,
                  cost_config={"fee_entry": 0.0, "fee_exit": 0.0, "slippage": 0.0,
                               "spread_cost": 0.0, "safety_margin": 0.0})
        # Both clear their thresholds and both have positive EV; the short is
        # the stronger. Under the old ordering this returned LONG.
        sig, lev, sev = evaluate_entry_signal(0.40, 0.60, **kw)
        self.assertGreater(sev, lev)
        self.assertEqual(sig, "SHORT")
        # Mirror case still picks long.
        sig, lev, sev = evaluate_entry_signal(0.60, 0.40, **kw)
        self.assertEqual(sig, "LONG")
        # One-sided cases are unchanged.
        self.assertEqual(evaluate_entry_signal(0.60, 0.10, **kw)[0], "LONG")
        self.assertEqual(evaluate_entry_signal(0.10, 0.60, **kw)[0], "SHORT")
        self.assertEqual(evaluate_entry_signal(0.10, 0.10, **kw)[0], "NO_TRADE")
        # An exact tie is a coin flip dressed as a signal -- stand aside.
        self.assertEqual(evaluate_entry_signal(0.50, 0.50, **kw)[0], "NO_TRADE")

    def test_range_gate_edge_is_one_knob_in_one_place(self) -> None:
        # The gate existed TWICE -- once in live.py and once in backtest.py --
        # with backtest.py already importing live. Two copies of the rule that
        # decides which bars are tradable is the train/serve skew this module
        # spends its comments guarding against, so backtest now re-exports.
        from btcusdt_quant import live as _live
        self.assertIs(backtest_module.apply_range_mean_reversion_gate,
                      _live.apply_range_mean_reversion_gate)
        gate = _live.apply_range_mean_reversion_gate
        both = {"LONG", "SHORT"}
        # The band is symmetric: widen the edge and a bar that was untradable
        # at 0.25 becomes long-only, and its mirror becomes short-only.
        self.assertEqual(gate("range", {"range_position_20": 0.30}, both, 0.25), set())
        self.assertEqual(gate("range", {"range_position_20": 0.30}, both, 0.35), {"LONG"})
        self.assertEqual(gate("range", {"range_position_20": 0.70}, both, 0.35), {"SHORT"})
        # Non-range regimes are untouched whatever the edge.
        self.assertEqual(gate("down", {"range_position_20": 0.01}, both, 0.40), both)
        # A missing feature must not silently become a tradable edge.
        self.assertEqual(gate("range", {}, both, 0.25), set())
        # Out-of-range edges are refused rather than clamped.
        for bad in (0.0, -0.1, 0.6, 1.0):
            with self.assertRaises(ValueError):
                run_backtest(_ohlc_candles([(100.0, 100.2, 99.8, 100.0)] * 5), range_gate_edge=bad)

    def test_feature_cache_returns_what_it_replaced(self) -> None:
        # A stale feature cache would silently feed a run features computed from
        # other data or other code -- the train/serve skew class that has already
        # invalidated result sets here. So the cached path must be
        # indistinguishable from the uncached one, and the key must move when
        # the inputs do.
        import tempfile
        from pathlib import Path as _P
        from btcusdt_quant import cli as _cli
        candles = _ohlc_candles([(100.0 + i * 0.1, 100.3 + i * 0.1, 99.7 + i * 0.1, 100.1 + i * 0.1)
                                 for i in range(60)])
        direct = backtest_module.dataset.build_feature_rows(candles)
        with tempfile.TemporaryDirectory() as tmp:
            miss = _cli.build_feature_rows_cached(candles, tmp)          # writes
            hit = _cli.build_feature_rows_cached(candles, tmp)           # reads
            self.assertEqual(len(direct), len(hit))
            for a, b in zip(direct, hit):
                self.assertEqual(a.open_time, b.open_time)
                self.assertEqual(dict(a.features), dict(b.features))
            for a, b in zip(miss, hit):
                self.assertEqual(dict(a.features), dict(b.features))
            # A different candle span must not reuse the same entry.
            k1 = _cli._feature_cache_key(None, candles, None, None)
            k2 = _cli._feature_cache_key(None, candles[:-1], None, None)
            self.assertNotEqual(k1, k2)
            # Entries are per-key directories, so both can coexist.
            _cli.build_feature_rows_cached(candles[:-1], tmp)
            self.assertEqual(len(list(_P(tmp).iterdir())), 2)
        # Without a cache directory it is a plain passthrough.
        plain = _cli.build_feature_rows_cached(candles, None)
        self.assertEqual(len(plain), len(direct))

    def test_directional_threshold_cannot_see_the_future(self) -> None:
        # fit_directional_threshold takes the percentile of the WHOLE series it
        # is handed, and the backtest hands it the whole file -- so a 2026 bar
        # was classified against a boundary computed with 2026 data. Live has no
        # future distribution to calibrate on, so that boundary is unreachable
        # in production. Pin the property that makes the causal version correct:
        # changing the future must not move a past threshold.
        import random
        from btcusdt_quant.features import RegimeDetector
        random.seed(0)
        detector = RegimeDetector()
        n, split = 8000, 5000
        slopes = [random.gauss(0.0, 1e-4) for _ in range(n)]
        blown = slopes[:split] + [random.gauss(0.0, 5e-3) for _ in range(n - split)]

        base = detector.fit_directional_threshold_expanding(slopes, refit_every=1440, min_rows=1440)
        alt = detector.fit_directional_threshold_expanding(blown, refit_every=1440, min_rows=1440)
        self.assertEqual(base[:split], alt[:split])
        # ...and the full-series fit DOES move, which is the bug being fixed.
        self.assertNotEqual(
            detector.fit_directional_threshold(slopes)["dir_threshold"],
            detector.fit_directional_threshold(blown)["dir_threshold"],
        )
        # Warmup rows have no history: fall back to the floor, not to a
        # percentile of data they cannot have seen.
        self.assertEqual(base[0], detector.config.min_trend_abs)
        regimes, thresholds = detector.detect_all_directional_causal([0.001] * n, slopes)
        self.assertEqual(len(regimes), n)
        self.assertEqual(thresholds, base)

    def test_auto_regime_records_counts_and_threshold(self) -> None:
        # --auto-regime routed every bar while leaving regime_routing_diagnostics
        # empty, so an artifact could not say how many bars went up vs range vs
        # down, nor at what slope the split was drawn. regime_coverage only
        # counts matched/no_model, which is why "down was 20.5% of a -33%
        # downtrend" had to be inferred from a no_model tally.
        from btcusdt_quant.features import RegimeDetector
        specs = [(100.0 + i * 0.1, 100.2 + i * 0.1, 99.8 + i * 0.1, 100.0 + i * 0.1) for i in range(80)]
        result = run_backtest(
            _ohlc_candles(specs), model=self._AlwaysLong(), position_size=0.1,
            label_horizon=10, cooldown_bars=0, long_threshold=0.6, short_threshold=0.01,
            exec_tp_pct=0.005, exec_sl_pct=0.005,
            regime_detector=RegimeDetector(),
        )
        diag = result.regime_routing_diagnostics
        self.assertEqual(diag["source"], "regime_detector.detect_all_directional")
        self.assertEqual(set(diag["regime_counts"]), {"up", "range", "down"})
        self.assertEqual(sum(diag["regime_counts"].values()), diag["window_rows"])
        self.assertAlmostEqual(sum(diag["regime_ratios"].values()), 1.0)
        # The boundary moves, so the run reports its range, not one number that
        # was never in force throughout.
        for key in ("dir_threshold_first", "dir_threshold_last", "dir_threshold_min", "dir_threshold_max"):
            self.assertIsInstance(diag[key], float)
        self.assertLessEqual(diag["dir_threshold_min"], diag["dir_threshold_max"])
        self.assertEqual(diag["dir_threshold_calibration"], "expanding-past-only (causal)")

    def test_compare_strategies_honours_position_size(self) -> None:
        # compare_strategies took no position_size at all, so every CLI backtest
        # silently ran at run_backtest's 0.1 default. That hid a deployment
        # constraint: an exchange's minimum order size puts a FLOOR on this
        # number (0.001 BTC on Binance USDT-M is ~0.5 of a $130 account), and
        # the size you can actually place was never the size being validated.
        specs = [(100.0, 100.2, 99.8, 100.0)]
        specs += [(100.0, 100.05, 99.5, 100.2)]
        specs += [(100.2, 100.4, 100.0, 100.3)] * 20
        common = dict(
            strategies=None, label_horizon=10,
            exec_tp_pct=0.002, exec_sl_pct=0.002,
            fee_rate_per_side=0.0006, maker_fee_rate_per_side=0.0002,
            slippage_rate_per_side=0.0,
        )
        small = backtest_module.compare_strategies(
            _ohlc_candles(specs), self._AlwaysLong(), position_size=0.1, **common
        )
        big = backtest_module.compare_strategies(
            _ohlc_candles(specs), self._AlwaysLong(), position_size=0.5, **common
        )
        # Same signals, five times the notional -> a different result, not the
        # default silently reused for both.
        self.assertNotEqual(small["best_total_return"], big["best_total_return"])

    def test_exit_cost_follows_the_outcome_not_a_flag(self) -> None:
        # Which exits rest is the whole verdict, not a trim: a TP limit really is
        # crossed by someone else (maker), an SL is a stop that crosses the book
        # (taker), and a TIMEOUT is a horizon market-close. On the 30m long the
        # mix is TP 13.4% / SL 29.8% / TIMEOUT 56.8% against a ~44% break-even,
        # so one flag covering all of them decided the answer by assumption.
        # Pin that the discount applies to the outcome that HAPPENED and to no
        # other, without hard-coding which outcome this fixture produces.
        specs = [(100.0, 100.2, 99.8, 100.0)]
        specs += [(100.0, 100.05, 99.5, 100.2)]
        specs += [(100.2, 100.4, 100.0, 100.3)] * 20
        common = dict(
            model=self._AlwaysLong(), position_size=0.1, label_horizon=10,
            cooldown_bars=0, long_threshold=0.6, short_threshold=0.01,
            fee_rate_per_side=0.0006, maker_fee_rate_per_side=0.0002,
            slippage_rate_per_side=0.0,
        )
        happened = run_backtest(self._candles(specs), maker_fill_window=5, **common).trades[0].outcome
        self.assertIn(happened, _ALL_EXITS)
        resting = run_backtest(
            self._candles(specs), maker_fill_window=5, maker_exit_outcomes=[happened], **common
        )
        crossing = run_backtest(
            self._candles(specs), maker_fill_window=5,
            maker_exit_outcomes=[o for o in _ALL_EXITS if o != happened], **common,
        )
        self.assertAlmostEqual(resting.trades[0].fee_pct, 0.0004)   # 2 + 2 bps
        self.assertAlmostEqual(crossing.trades[0].fee_pct, 0.0008)  # 2 + 6 bps
        # Case-insensitive, and the run records what it actually assumed.
        lower = run_backtest(
            self._candles(specs), maker_fill_window=5, maker_exit_outcomes=[happened.lower()], **common
        )
        self.assertAlmostEqual(lower.trades[0].fee_pct, 0.0004)
        self.assertEqual(lower.run_config["maker_exit_outcomes"], [happened])
        # A typo must not silently price everything taker.
        with self.assertRaises(ValueError):
            run_backtest(self._candles(specs), maker_exit_outcomes=["TAKE_PROFIT"], **common)

    def test_fill_bar_can_hit_the_stop(self) -> None:
        # A maker order fills part-way through its bar, so the REST of that bar
        # can hit a barrier. bar 0 signals BUY -> limit at 100. bar 1 dips to
        # the limit and keeps falling well past the stop (default sl_pct puts
        # the SL just under 100), so the trade must resolve SL on the FILL BAR
        # rather than surviving to bar 2. Opening the trade below the exit block
        # skipped this bar entirely -- and since a fill bar is by construction
        # one that moved against the entry, the skipped outcomes were the losses.
        specs = [(100.0, 100.2, 99.8, 100.0)]        # signal bar
        specs += [(100.0, 100.05, 90.0, 90.5)]       # bar1: fills at 100, craters
        # Ramp away afterwards so no re-placed limit is ever touched again --
        # the run then contains exactly the one trade under test.
        specs += [(95.5 + 5 * k, 96.5 + 5 * k, 94.5 + 5 * k, 95.5 + 5 * k) for k in range(20)]
        result = self._run(specs, window=5)
        self.assertEqual(result.trade_count, 1)
        first = result.trades[0]
        self.assertTrue(first.entry_maker)
        self.assertEqual(first.outcome, "SL")
        # Resolved ON the fill bar, not a later one.
        self.assertEqual(first.exit_time, first.entry_time)

    def test_penetration_blocks_a_bare_touch(self) -> None:
        # bar1 dips exactly to the limit (100.0) -- a bare touch. With a 5bps
        # penetration requirement the queue-priority proxy refuses the fill; a
        # touch (0 penetration) would take it. Same candles, both windows large
        # enough that only the fill rule differs.
        # Every bar: close 100.0, low exactly 100.0. So every (re-placed) limit
        # is 100.0 and later lows only ever TOUCH it, never trade through.
        specs = [(100.0, 100.2, 100.0, 100.0)] * 9
        touched = self._run(specs, window=5, penetration=0.0)
        blocked = self._run(specs, window=5, penetration=0.0005)  # 5 bps
        self.assertGreaterEqual(touched.maker_fill_diagnostics["orders_filled"], 1)
        self.assertEqual(blocked.maker_fill_diagnostics["orders_filled"], 0)


if __name__ == "__main__":
    unittest.main()
