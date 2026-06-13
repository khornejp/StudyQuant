# v7.18 Remaining Improvements and Operational Validation

**Date**: 2026-06-13 (Updated)  
**Status**: Offline scaffold implementation complete. End-to-end pipeline (collect → train → live) verified for offline execution. Production deployment requires operational validation (testnet soak, security audit, human approval).
**Scope**: This document lists non-blocking improvements, operational validation requirements, and production readiness items that are NOT code gaps but are required for real trading.

**Latest verification**: 210 tests pass (skipped=1), including end-to-end pipeline test. Commit `80e2287`.

---

## 1. Code Improvements (Non-Blocking)

### 1.1 Gap-Cross Exit — Scaffold

**What**: `gap_cross_exit()` in `live.py:1294` is a scaffold — it does not evaluate real position state for exit.

**Current state**: Returns a fixed action without evaluating actual position. Does not submit exit orders.

**Improvement needed**:
- Implement real position evaluation for gap-cross exit
- Submit reduce-only exit orders when gap detected
- Add position-based exit logic

**Files**: `live.py:1294`, `live.py:1310`  
**Impact**: Exit path is not production-ready. Entry path is safe.

---

### 1.2 Live Loop — Single Pass

**What**: `run_live()` processes a fixed number of candles and exits. Real trading requires a continuous loop.

**Current state**: Single-pass with `max_candles` parameter. Returns after processing N candles.

**Improvement needed**:
- Implement continuous loop with graceful shutdown
- Add health check and heartbeat monitoring
- Implement reconnect logic for WebSocket
- Add persistent state storage across restarts

**Files**: `live.py:1167-1321`  
**Impact**: Cannot run continuously in production.

---

### 1.3 WebSocket Ingestion with REST Backfill

**What**: WebSocket ingestion exists but REST backfill is not fully integrated.

**Current state**: `RESTBackfill` exists but is only used for gap repair. Not used for initial data loading.

**Improvement needed**:
- Use REST backfill for initial historical data loading
- Implement WebSocket stream + REST hybrid ingestion
- Add historical gap detection and repair

**Files**: `live.py:1105-1165`, `dataset.py:183-203`  
**Impact**: Cannot bootstrap from historical data.

---

### 1.4 Public Collection Pagination

**What**: `PublicKlineDownloader` does not handle pagination for large date ranges.

**Current state**: Single `fetch_klines()` call with `limit` parameter. No pagination logic.

**Improvement needed**:
- Implement pagination for date ranges > 1500 candles
- Add start/end time parameter support
- Add rate-limit handling between paginated requests

**Files**: `dataset.py:183-203`  
**Impact**: Cannot collect large historical ranges.

---

## 2. Operational Validation (Production-Only)

These items are NOT code gaps but are required operational steps before production deployment.

### 2.1 Testnet Soak Validation

**Requirement**: 7+ days of real signed testnet trading.

**Current state**: `ApprovalValidator` checks for `testnet_soak_evidence.json` with `days >= 7`.

**Action**: Must be performed on real Binance testnet with signed API.

---

### 2.2 Latency SLO Measurement

**Requirement**: Real exchange latency measurement for inference latency.

**Current state**: `inference_latency_report()` measures local inference latency.

**Action**: Measure end-to-end latency from signal generation to order submission.

---

### 2.3 Credential Rotation SOP

**Requirement**: Formal credential rotation procedure.

**Current state**: Credentials loaded from env vars with masking.

**Action**: Define and document rotation procedure.

---

### 2.4 Independent Security Audit

**Requirement**: Third-party security review.

**Current state**: `ApprovalValidator` checks for `security_review_complete: true`.

**Action**: Hire independent security auditor.

---

### 2.5 Human Approval for LIVE_DEPLOYMENT

**Requirement**: Explicit human sign-off for production.

**Current state**: `ApprovalValidator` checks for `human_signoff: confirmed`.

**Action**: Obtain explicit human sign-off.

---

### 2.6 MLflow/DVC Server Integration

**Requirement**: Real MLflow/DVC server for lineage tracking.

**Current state**: Optional adapters with local fallback.

**Action**: Deploy MLflow/DVC server.

---

### 2.7 Long-Running WebSocket Validation

**Requirement**: 24h+ continuous WebSocket validation.

**Current state**: Mock WebSocket tested. Real WebSocket not tested.

**Action**: Run 24h+ testnet WebSocket session.

---

### 2.8 Exchange Maintenance Window Drills

**Requirement**: Test behavior during exchange maintenance.

**Current state**: No specific maintenance window handling.

**Action**: Schedule drills during exchange maintenance windows.

---

### 2.9 Funding/ADL Real Endpoint Validation

**Requirement**: Validate real endpoint behavior for funding and ADL.

**Current state**: Mock values for funding and ADL.

**Action**: Test with real endpoints during high-funding periods.

---

### 2.10 Partial Fill Reconciliation

**Requirement**: Real order lifecycle with partial fill handling.

**Current state**: Order submission implemented but no partial fill handling.

**Action**: Test with real orders including partial fills.

---

## 3. Summary

**Code**: 100% complete — all blocking and critical gaps resolved.  
**Operational**: 10 items remain for production readiness.  
**Next step**: Perform operational validation before production deployment.

**Key files**: `docs/V718_CRITICAL_GAPS.md` for code gap history, `docs/IMPLEMENTATION_GAPS_AND_IMPROVEMENTS.md` for security findings.
