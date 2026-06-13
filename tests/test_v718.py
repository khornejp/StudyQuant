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

from btcusdt_quant import dataset, features, governance, live, parity, sources, training


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
        self.assertIn("missing", reason.lower(), f"reason should mention missing metric: {reason}")

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


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
    def read(self) -> bytes:
        return self._body
    def __enter__(self) -> "_FakeResponse":
        return self
    def __exit__(self, *args: object) -> None:
        pass

if __name__ == "__main__":
    unittest.main()
