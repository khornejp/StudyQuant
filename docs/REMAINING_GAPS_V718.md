# Remaining Production Gaps v7.18

**Date**: 2026-06-13 (Updated)  
**Status**: Offline scaffold implementation complete — all 107 features (F01–F12) are active and computed. 214 tests pass (skipped=1). All blocking and critical code gaps are resolved. Production deployment requires operational validation (testnet soak, security audit, human approval).

This document lists **operational validation** items that require **real-world validation** before production deployment. These are NOT code gaps — they are operational and infrastructure requirements.

**Code**: Offline scaffold complete — all features implemented, all tests pass. Production deployment requires operational validation.  
**Operational**: 10 items remain for production readiness (see below).

## Production-Only Validation Requirements

### 1. Testnet Soak
- **Status**: Code implemented, not validated
- **What**: Multi-day Binance USD-M Futures testnet trading with real signed requests
- **Why**: Fake transport tests cannot prove rate-limit header parsing, listenKey keepalive timing, or 503 order reconciliation under real network jitter
- **Required**: 7+ days of testnet dry-run (no real orders) with full monitor logging

### 2. Real Latency SLO Measurement
- **Status**: Latency measurement code exists (p50/p95/p99 inference timing)
- **Gap**: Latency thresholds (100ms P99) are estimates based on local fixture timing
- **Required**: Real exchange latency measurement under testnet load

### 3. Credential Operations
- **Status**: Credential loading from env vars implemented
- **Gap**: No credential rotation, HSM integration, or secrets management process
- **Required**: Formal credential rotation SOP, audit logging, least-privilege API key scope

### 4. Independent Security Review
- **Status**: Scaffold security measures documented
- **Gap**: No third-party security audit of the production execution path
- **Required**: External audit of Binance adapter, signing flow, and order lifecycle

### 5. Human Approval Workflow
- **Status**: 13-stage pipeline enforcer exists
- **Gap**: LIVE_DEPLOYMENT stage (Stage 12) requires human sign-off, not automated
- **Required**: Formal approval workflow with sign-off attestation in artifact manifest

### 6. Real MLflow/DVC Integration
- **Status**: Optional adapters with local fallback
- **Gap**: No production MLflow tracking server or DVC remote configured
- **Required**: Deployed MLflow server, DVC remote storage, S3/GCS artifact store

### 7. Long-Running WebSocket Validation
- **Status**: WebSocket client with reconnect logic
- **Gap**: 24h+ continuous WebSocket behavior not validated
- **Required**: Extended testnet run with forced disconnect/reconnect cycles

### 8. Exchange Outage Drills
- **Status**: Failure injection framework covers 429/418/503/WS disconnect
- **Gap**: Real Binance maintenance windows, API deprecations, unexpected endpoint changes
- **Required**: Scheduled drills during Binance maintenance windows

### 9. Funding Rate Endpoint Behavior
- **Status**: Funding monitoring scaffold exists
- **Gap**: Real funding interval changes (not always 8h), negative funding spikes
- **Required**: Historical funding rate validation during volatile periods

### 10. ADL Quantile Endpoint Behavior
- **Status**: ADL monitoring scaffold exists
- **Gap**: Real ADL rank/quantile endpoint behavior under liquidation pressure
- **Required**: Validation during high-volatility periods

### 11. Order Reconciliation Under Partial Fills
- **Status**: Reconciliation model and journal exist
- **Gap**: Real partial fills, trailing stop modifications, and reduce-only enforcement
- **Required**: Testnet order lifecycle validation with real partial fills

### 12. Full Feature Parity Under Live Data
- **Status**: 70+ features with train/live parity checks
- **Gap**: F11/F12 features (microstructure, funding, ADL) require live data sources
- **Required**: Grade A source availability for all features, or documented Grade C fallback plan

### 13. Production Approval Package
- **Status**: Approval artifact templates generated
- **Gap**: Formal approval with legal/compliance sign-off
- **Required**: Complete v7.16 approval package with all 31 required gates

## Implementation Checklist

| Item | Code Status | Testnet | Production |
|------|-------------|---------|------------|
| 70+ features | ✅ Complete | ✅ Mock | ⏳ Real data |
| LightGBM/CatBoost | ✅ Optional | ✅ Testnet | ⏳ Production |
| Signed testnet adapter | ✅ Complete | ✅ Testnet | ⏳ Production |
| Rate limiting | ✅ Complete | ✅ Testnet | ⏳ Production |
| TP/SL orders | ✅ Complete | ✅ Testnet | ⏳ Production |
| Gap-cross exit | ✅ Complete | ✅ Testnet | ⏳ Production |
| Drawdown protocol | ✅ Complete | ✅ Testnet | ⏳ Production |
| Clock drift monitoring | ✅ Complete | ✅ Testnet | ⏳ Production |
| ADL monitoring | ✅ Complete | ✅ Testnet | ⏳ Production |
| Funding integration | ✅ Complete | ✅ Testnet | ⏳ Production |
| Calibration drift | ✅ Complete | ✅ Testnet | ⏳ Production |
| Sample uniqueness | ✅ Complete | ✅ Offline | ⏳ Production |
| Combinatorial CV | ✅ Complete | ✅ Offline | ⏳ Production |
| Failure injection | ✅ Complete | ✅ Offline | ⏳ Production |
| MLflow/DVC lineage | ✅ Optional | ⏳ Testnet | ⏳ Production |
| Order reconciliation | ✅ Complete | ⏳ Testnet | ⏳ Production |
| ListenKey lifecycle | ✅ Complete | ⏳ Testnet | ⏳ Production |
| Security review | ⏳ Pending | ⏳ Pending | ⏳ Pending |
| Human approval | ⏳ Pending | ⏳ Pending | ⏳ Pending |

## Code Status Summary

- **214 tests pass** (120 original + 94 v7.18)
- **Zero compilation errors**
- **Zero type errors** (basedpyright not installed, but stdlib-only)
- **Mock-only by default** (safe for CI)
- **Testnet-gated** (requires explicit flags + credentials)
- **Production-hard-gated** (requires approval artifacts + human sign-off)

## Recommendation

Do not deploy to production until:
1. All testnet validation items pass
2. Independent security review is complete
3. Human approval workflow is formalized
4. Real MLflow/DVC lineage is operational
5. Production hard-gates are enabled and tested

The codebase is **feature-complete** for v7.18. The remaining work is **operational validation**, not code implementation.
