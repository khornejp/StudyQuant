from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from btcusdt_quant import data, features, governance, live
from btcusdt_quant.cli import run_demo


class DataPipelineTests(unittest.TestCase):
    def test_canonical_timeline_repairs_gaps(self) -> None:
        candles = data.CanonicalTimelineBuilder().build(data.local_fixture())
        self.assertEqual(len(candles), 8)
        self.assertEqual(sum(candle.gap_flag for candle in candles), 2)
        self.assertEqual(candles[3].gap_length, 1)
        self.assertEqual(candles[4].gap_length, 2)
        self.assertEqual(data.max_gap_run([candle.gap_flag for candle in candles], 120), 2)

    def test_gap_policy_blocks_trade_flow_contamination(self) -> None:
        decision = data.GapContaminationGovernance().decide("volume_trade_flow_features", 0.03, 1, live=True)
        self.assertEqual(decision.action, "block_new_entries")


class FeatureGovernanceTests(unittest.TestCase):
    def test_feature_clipper_bounds_and_inf_to_nan(self) -> None:
        result = features.FeatureClipper().clip({"return_1": 0.5, "return_5_vol_adj": 11.0, "close_zscore_60": 12.0, "volume_ratio": float("inf")})
        self.assertEqual(result.values["return_1"], 0.2)
        self.assertEqual(result.values["return_5_vol_adj"], 10.0)
        self.assertEqual(result.values["close_zscore_60"], 10.0)
        self.assertIsNone(result.values["volume_ratio"])

    def test_nan_source_classifier_distinguishes_outage(self) -> None:
        classifier = features.NaNSourceClassifier(optional_noncritical_features={"optional_feature"})
        self.assertEqual(classifier.classify({"gap_flag": 1}, "volume"), "outage_nan")
        self.assertEqual(classifier.classify({"warmup_invalid": 1}, "return_120"), "warmup_nan")
        self.assertEqual(classifier.classify({}, "optional_feature"), "structural_nan")


class LiveSafetyTests(unittest.TestCase):
    def test_rate_limit_budget_and_status_actions(self) -> None:
        manager = live.RateLimitManager(limit_per_minute=10)
        manager.acquire("GET /fapi/v1/klines", 8)
        with self.assertRaises(live.RateLimitBudgetExceeded):
            manager.acquire("GET /fapi/v1/klines", 1)
        self.assertEqual(manager.observe_status(429), "block_new_entries")
        self.assertEqual(manager.observe_status(418), "hard_kill")

    def test_one_way_position_guard_blocks_existing_position(self) -> None:
        allowed, reason = live.OneWayPositionGuard().can_enter(live.PositionState("BTCUSDT", 0.1), "BUY")
        self.assertFalse(allowed)
        self.assertIn("blocks new entry", reason)

    def test_position_sizer_enforces_notional_fraction(self) -> None:
        result = live.PositionSizer().fixed_notional(100000.0, 10000.0, 0.5, 1.0, 0.001, 0.001, 0.1)
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "max_notional_fraction breached")

    def test_mock_exchange_never_uses_network(self) -> None:
        adapter = live.MockExchangeAdapter()
        order = adapter.submit_order("BTCUSDT", "BUY", "LIMIT", 0.001)
        self.assertEqual(order.status, "MOCK_ACCEPTED")
        self.assertFalse(adapter.network_enabled)


class GovernanceTests(unittest.TestCase):
    def test_pipeline_stage_enforcer_rejects_skips(self) -> None:
        enforcer = governance.PipelineStageEnforcer()
        with self.assertRaises(governance.PipelineStageError):
            enforcer.complete("SCHEMA_VALIDATION")
        for stage in governance.PIPELINE_STAGES:
            enforcer.complete(stage)
        self.assertEqual(len(enforcer.completed), 13)

    def test_fallback_policy_is_deterministic(self) -> None:
        self.assertEqual(governance.fallback_action("gap_ratio_20", 0.20), "block_new_entries")
        self.assertEqual(governance.fallback_action("dataset_card_hash_mismatch", True), "hard_kill")
        self.assertEqual(governance.fallback_action("unknown", 0), "allow")

    def test_demo_generates_verifiable_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            summary = run_demo(output)
            self.assertFalse(summary["network_used"])
            ok, errors = governance.verify_manifest(output)
            self.assertTrue(ok, errors)
            manifest = json.loads((output / "artifact_manifest.json").read_text(encoding="utf-8"))
            paths = {artifact["path"] for artifact in manifest["artifacts"]}
            self.assertIn("dataset_card.json", paths)
            self.assertIn("dataset_card.yaml", paths)
            self.assertIn("model_card.json", paths)
            self.assertIn("model_card.yaml", paths)
            self.assertIn("column_data_contract.csv", paths)
            self.assertIn("monitoring_slo_report.csv", paths)
            self.assertIn("lineage_manifest.json", paths)

    def test_manifest_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / "artifact_manifest.json").write_text(
                '{"artifacts":[{"path":"../README.md","sha256":"bad"}]}',
                encoding="utf-8",
            )
            ok, errors = governance.verify_manifest(output)
            self.assertFalse(ok)
            self.assertIn("unsafe artifact path: ../README.md", errors)

    def test_ml_and_ops_scaffold_modules(self) -> None:
        self.assertEqual(features.RollingFeatureEngine().rolling_mean([1.0, 2.0, 3.0], 2), [None, 1.5, 2.5])
        self.assertEqual(features.CalibrationModule().select_method(40), "platt")
        self.assertEqual(len(features.PurgedWalkForwardSplit().split(20, 5, 3, 3, 1)), 3)
        self.assertEqual(features.FeatureSelectionPipeline().core_features([["a", "b"], ["a"], ["a", "c"]]), ["a"])
        self.assertEqual(features.BootstrapCIEngine().ci95([-0.1, 0.0, 0.1]), (-0.1, 0.0))
        self.assertEqual(features.OptunaBudgetProfiles().get("practical_start")["trials"], 200)
        self.assertTrue(features.ChampionChallengerManager().can_promote(30, 100, -0.01, 0.01)[0])
        self.assertEqual(governance.DataQualityGate().evaluate(1, 0.0, False).action, "block_new_entries")
        self.assertTrue(governance.SourceGradeManager().grade("klines_1m", True, True)["train_live_feature_parity_passed"])
        self.assertEqual(governance.MonitoringSLOEngine().evaluate({"gap_ratio_20": 0.20})["gap_ratio_20"], "block_new_entries")
        self.assertEqual(governance.ClockDriftMonitor().action(1000), "hard_kill")
        self.assertEqual(governance.ADLMonitor().action(4), "block_new_entries")

    def test_execution_safety_modules(self) -> None:
        self.assertTrue(live.FundingEventManager().blackout_active(3))
        self.assertEqual(live.GhostFillPrevention().safe_market_exit(1, 0.1, False), "hard_kill")
        self.assertEqual(live.EmergencyCloseExecutor().close(0, 0), "emergency_close_submitted")


if __name__ == "__main__":
    unittest.main()
