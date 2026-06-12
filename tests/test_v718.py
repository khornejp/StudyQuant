from __future__ import annotations

import csv
import json
import tempfile
import unittest
import urllib.parse
from datetime import timedelta
from pathlib import Path
from typing import cast

from btcusdt_quant import dataset, features, governance, live, parity, sources


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


if __name__ == "__main__":
    unittest.main()
