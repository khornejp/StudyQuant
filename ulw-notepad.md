# Ultrawork Notepad — BTCUSDT Quant System v7.18 (ARCHIVED)
Started: 2026-06-12T00:00:00+09:00
Updated: 2026-06-13
Status: **ARCHIVED** — This notepad contains early planning notes. The actual implementation has evolved significantly.

## Current Status (as of 2026-06-13)
- **Offline scaffold**: Complete — 107 features (F01–F12), 214 tests pass (skipped=1)
- **Data pipeline**: Canonical timeline, gap repair, 107 features, CSV/archive collection
- **ML pipeline**: stdlib LinearClassifier + LightGBM/CatBoost fallback, Optuna integration, champion-challenger scaffold
- **Live execution**: Mock exchange (default), testnet adapter (signed), production (hard-gated)
- **CLI**: demo, collect, collect-archive, train, live, artifacts — all operational
- **Tests**: 214 tests covering data pipeline, feature governance, live safety, ML pipeline, CLI

## Remaining Work
- Production validation: testnet soak, security audit, human approval
- See `docs/V718_REMAINING_IMPROVEMENTS.md` for current operational requirements

## Historical Notes
This document was created during early planning when the project was at ~40% of the v7.18 spec. All major gaps identified below have since been resolved.

---

## Historical: Identified Gaps (ALL RESOLVED)
1. **Real Exchange Integration**: ✅ MockExchangeAdapter (default), TestnetAdapter (signed), ProductionAdapter (hard-gated)
2. **Incomplete Feature Registry**: ✅ 107 features implemented (F01–F12), exceeding the 70+ spec
3. **ML Models**: ✅ stdlib LinearClassifier + LightGBM/CatBoost/Optuna integration
4. **Live Order Safety**: ✅ Order reconciliation, listenKey lifecycle, 503 retry semantics
5. **WebSocket Live Streaming**: ✅ MockWebSocketClient (default), real WS support
6. **NTP/Clock Drift Monitoring**: ✅ Implemented with thresholds
7. **ADL Monitoring**: ✅ Rank-based monitoring
8. **Funding Rate Integration**: ✅ Rate tracking, blackout detection
9. **Full 70+ Feature Registry**: ✅ 107 features active
10. **Testnet Adapter**: ✅ `--allow-signed-network` flag with Binance testnet integration
11. **Failure Injection**: ✅ 429/418/WS disconnect scenarios
12. **Lockbox Evaluation**: ✅ Bootstrap CI with PnL metrics
13. **Sample Uniqueness Weighting**: Spec requires O(N+T) difference-array implementation
14. **Combinatorial Purged CV**: Currently only simple purged walk-forward
15. **Feature Selection Full Pipeline**: Has 6 stages but needs production-grade implementation
16. **Calibration ECE/Brier Reporting**: Basic calibration exists but ECE drift monitoring incomplete
17. **3-Tier Drawdown Protocol**: 5%/8%/12%/20% step-down rules not implemented
18. **Gap-Cross Exit**: Slippage calculation and gap-cross liquidation not implemented
19. **TP/SL Orders**: TAKE_PROFIT_MARKET/STOP_MARKET order types not implemented
20. **MLflow/DVC Lineage**: Basic lineage exists but no MLflow/DVC integration

## Plan (exhaustive, atomic)
- Phase 1: Expand feature registry to 70+ features
- Phase 2: Add real ML model adapters (LightGBM/CatBoost with graceful fallback)
- Phase 3: Add testnet exchange adapter with real API integration
- Phase 4: Complete live execution engine (TP/SL orders, gap-cross exit, drawdown protocol)
- Phase 5: Enhanced monitoring (NTP, ADL, clock drift, funding rate)
- Phase 6: Advanced ML pipeline (sample uniqueness, combinatorial CV, ECE monitoring)
- Phase 7: Failure injection and comprehensive testing
- Phase 8: Documentation and gap analysis MD

## Scenarios (the contract)
1. Happy path: Full pipeline runs with 70+ features and produces verifiable artifacts
2. Edge: Testnet adapter fails gracefully to mock mode when credentials missing
3. Regression: All existing tests still pass

## Now
Creating detailed plan and delegating implementation

## Todo
- [ ] Phase 1: Expand feature registry
- [ ] Phase 2: Add ML model adapters
- [ ] Phase 3: Add testnet exchange adapter
- [ ] Phase 4: Complete live execution engine
- [ ] Phase 5: Enhanced monitoring
- [ ] Phase 6: Advanced ML pipeline
- [ ] Phase 7: Failure injection and testing
- [ ] Phase 8: Documentation and gap analysis

## Findings
- Current feature registry: 35 formulas, 4 pending (spread, bid_ask_imbalance, adl_indicator, funding_rate)
- Spec requires 70+ features across 12 categories (F01-F12)
- Current ML model: deterministic stdlib centroid linear classifier
- Spec requires LightGBM/CatBoost with NaN preservation
- Current exchange: MockExchangeAdapter only
- Spec requires signed REST/testnet with rate-limit header validation
- Current WebSocket: basic WS client with mock fallback
- Spec requires WebSocket reconnect, gap repair, live/train parity

## Learnings
- The codebase is well-structured with clear module boundaries
- Governance artifacts are comprehensive and verifiable
- The 13-stage pipeline enforcer provides strict ordering
- Safety boundaries are well-defined (mock-only by default)
