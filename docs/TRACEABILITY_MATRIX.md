# ProjectMD Traceability Matrix

This matrix maps the ProjectMD BTCUSDT v7.18 requirements to the local scaffold implementation. Items marked as **local scaffold** enforce deterministic behavior without live Binance connectivity.

| ProjectMD requirement | Local implementation | Verification |
|---|---|---|
| Canonical 1m timeline and gap metrics | `CanonicalTimelineBuilder`, `gap_ratio`, `max_gap_run` | `test_canonical_timeline_repairs_gaps` |
| Feature-group gap contamination policy | `GapContaminationGovernance` | `test_gap_contamination_blocks_entry_when_gap_ratio_high` |
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
| Offline fixture/local CSV data collection | `dataset.collect_candles`, CLI `collect` | `test_collect_writes_offline_fixture_csv`, CLI `collect --rows` |
| Local CSV candle ingestion | `dataset.load_csv_candles`, `dataset.build_dataset` | `test_local_csv_dataset_builds_canonical_timeline` |
| Offline feature matrix and forward-return labels | `dataset.build_feature_rows`, `dataset.attach_labels`, `dataset.feature_matrix` | `test_offline_fixture_dataset_builds_features_and_labels` |
| Purged offline training/validation run | `training.run_training`, `training.default_splits`, CLI `train` | `test_purged_default_splits_have_no_overlap`, `test_training_run_generates_verifiable_offline_artifacts` |
| Offline dataset/model cards and training manifest | `training.write_training_artifacts`, `training.write_manifest` | `test_training_run_generates_verifiable_offline_artifacts`, CLI artifact verification |
| Public data collection safety opt-in | `dataset.PublicKlineDownloader` | `test_public_downloader_requires_explicit_network_opt_in` |
| Collection input validation | `dataset.collect_candles` | `test_collect_rejects_non_positive_rows` |
| Vulnerability/improvement MD | `docs/IMPLEMENTATION_GAPS_AND_IMPROVEMENTS.md` | File exists and reviewed |

## Missing Implementations

| ProjectMD requirement | Status | Gap |
|---|---|---|
| Live source parity enforcement | Missing | `live.py` does not block entries on missing sources |
| Production semantic approval | Missing | Only hash verification, no human signoff |
| Real order submission | Missing | `submit=True` not called in live loop |
| Risk state wiring | Missing | Balance, leverage, drawdown not fetched |
| Retry-After respect | Partial | Header parsed but not consumed by rate limiter |
| F11/F12 real-time sources | Pending | 15 features require depth/funding/ADL/mark-price |

## Explicit non-production boundary

The scaffold implements deterministic local contracts and mocks. It does not claim live production readiness. See `docs/V718_CRITICAL_GAPS.md` for remaining code gaps.
