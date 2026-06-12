# ProjectMD Traceability Matrix

This matrix maps the ProjectMD BTCUSDT v7.18 requirements to the local scaffold implementation. Items marked as **local scaffold** enforce deterministic behavior without live Binance connectivity.

| ProjectMD requirement | Local implementation | Verification |
|---|---|---|
| Canonical 1m timeline and gap metrics | `CanonicalTimelineBuilder`, `gap_ratio`, `max_gap_run` | `test_canonical_timeline_repairs_gaps` |
| Feature-group gap contamination policy | `GapContaminationGovernance` | `test_gap_policy_blocks_trade_flow_contamination` |
| Strict rolling warm-up/no partial windows | `RollingFeatureEngine` | `test_ml_and_ops_scaffold_modules` |
| Feature clipping incl. vol-adjusted limit | `FeatureClipper` | `test_feature_clipper_bounds_and_inf_to_nan` |
| Live NaN source classification | `NaNSourceClassifier` | `test_nan_source_classifier_distinguishes_outage` |
| Data quality deterministic gate | `DataQualityGate` | `test_ml_and_ops_scaffold_modules` |
| Source availability grading | `SourceGradeManager` | `test_ml_and_ops_scaffold_modules` |
| Calibration sample gate | `CalibrationModule` | `test_ml_and_ops_scaffold_modules` |
| Purged walk-forward split contract | `PurgedWalkForwardSplit` | `test_ml_and_ops_scaffold_modules` |
| Feature core-set survival rule | `FeatureSelectionPipeline` | `test_ml_and_ops_scaffold_modules` |
| Bootstrap CI scaffold | `BootstrapCIEngine` | `test_ml_and_ops_scaffold_modules` |
| Optuna budget profiles | `OptunaBudgetProfiles` | `test_ml_and_ops_scaffold_modules` |
| RateLimitManager and 429/418 actions | `RateLimitManager` | `test_rate_limit_budget_and_status_actions` |
| One-way position guard | `OneWayPositionGuard` | `test_one_way_position_guard_blocks_existing_position` |
| Position sizing cap | `PositionSizer` | `test_position_sizer_enforces_notional_fraction` |
| Mock-only exchange boundary | `MockExchangeAdapter` | `test_mock_exchange_never_uses_network`, CLI `network_used=False` |
| Funding blackout scaffold | `FundingEventManager` | `test_execution_safety_modules` |
| Ghost-fill safe-exit scaffold | `GhostFillPrevention` | `test_execution_safety_modules` |
| Emergency close scaffold | `EmergencyCloseExecutor` | `test_execution_safety_modules` |
| Monitoring SLO fallback chain | `MonitoringSLOEngine`, `ClockDriftMonitor`, `ADLMonitor` | `test_ml_and_ops_scaffold_modules` |
| 13-stage pipeline contract | `PipelineStageEnforcer` | `test_pipeline_stage_enforcer_rejects_skips` |
| Approval artifacts and SHA-256 manifest | `ArtifactWriter`, `verify_manifest` | `test_demo_generates_verifiable_artifacts`, CLI artifacts command |
| Vulnerability/improvement MD | `docs/IMPLEMENTATION_GAPS_AND_IMPROVEMENTS.md` | File exists and reviewed |

## Explicit non-production boundary

The scaffold implements deterministic local contracts and mocks. It does not claim live production readiness, and the remaining production-only gaps are documented in `IMPLEMENTATION_GAPS_AND_IMPROVEMENTS.md`.
