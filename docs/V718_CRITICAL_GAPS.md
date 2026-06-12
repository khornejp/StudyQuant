# v7.18 Implementation Gaps — Critical Review

**Date**: 2026-06-12  
**Scope**: Full codebase review after Oracle verification failure  
**Status**: 40% implemented, 60% gaps remain  

---

## 1. Blocking Gaps (Production Unsafe)

### 1.1 F11/F12 Real-Time Features — Pending Data Sources

**What**: 15 microstructure (F11) and exchange-safety (F12) features are registered but require real-time data sources not yet integrated.

**Current state**: `feature_registry.py` marks these as `pending_data_source`. The `active_feature_names()` filter excludes them from training/live feature matrices.

**Required for 100%**:
- Depth snapshot WebSocket stream (best bid/ask, qty, microprice)
- ADL quantile endpoint polling
- Funding rate endpoint with next-funding announcement
- Mark price stream
- Premium index endpoint
- Leverage bracket endpoint

**Files**: `feature_registry.py:163-177`, `dataset.py:FEATURE_NAMES`  
**Impact**: Model cannot use microstructure or exchange-safety signals live.

---

### 1.2 Live Source Parity Not Enforced

**What**: `live.py` computes `train_live_feature_parity_report` but does **not** pass it to `safe_market_entry()`.

**Current state**: `source_parity_passed` defaults to `True` in `safe_market_entry()` (`live.py:298`). The computed report is only written to summary JSON.

**Required for 100%**:
- Pass `source_report["train_live_feature_parity_passed"]` to `safe_market_entry(..., source_parity_passed=...)`
- Block entries when required live sources (depth, funding, ADL) are unavailable
- Document Grade C fallback plan for each missing source

**Files**: `live.py:1211-1228`  
**Impact**: Live trading can proceed with missing critical data sources.

---

### 1.3 Production Approval Semantic Validation Missing

**What**: Production adapter only verifies artifact SHA-256 hashes, not actual readiness.

**Current state**: `verify_manifest()` checks path safety and hashes. No validation of:
- LIVE_DEPLOYMENT stage completion
- Human sign-off attestation
- Security review completion
- Testnet soak evidence
- Non-offline model artifacts

**Required for 100%**:
- Add `ApprovalValidator` with semantic checks
- Require explicit human sign-off record in manifest
- Verify testnet soak duration ≥ 7 days
- Verify security review artifact exists
- Reject offline/demo artifacts for production

**Files**: `exchange.py:390-400`, `governance.py:528-553`, `cli.py:192-203`  
**Impact**: Demo artifacts can pass production gates.

---

### 1.4 Live Execution Loop Does Not Submit Orders

**What**: `run_live()` calls `safe_market_entry()` without `submit=True`, and exit path is inert.

**Current state**:
- `safe_market_entry()` defaults to `submit=False` (`live.py:308`)
- `gap_cross_exit(0.0, False, ...)` does not evaluate real position state
- Position state is string `"BTCUSDT"`, not actual account position

**Required for 100%**:
- Read real position from exchange adapter before entry
- Pass `submit=True` after all gates pass
- Implement TP/SL bracket submission
- Implement gap-cross exit with actual position evaluation
- Add order reconciliation loop

**Files**: `live.py:1203-1229`  
**Impact**: No real orders are submitted; claimed order safety is untested.

---

### 1.5 Risk Gates Use Missing State as Allow

**What**: Live loop passes no account balance, leverage, drawdown, or real position state.

**Current state**: `safe_market_entry()` receives `None` for balance, leverage, drawdown. Missing state defaults to `allow` in gate logic.

**Required for 100%**:
- Fetch account balance from exchange adapter
- Fetch current position and leverage
- Maintain drawdown state across live loop iterations
- Reject entry when any required state is unavailable

**Files**: `live.py:1216-1228`, `live.py:727-743`, `live.py:708-710`  
**Impact**: Risk boundaries are bypassed when state is missing.

---

## 2. Critical Gaps (Test/Behavioral)

### 2.1 Gap-Contamination Test Is Ineffective

**What**: `test_gap_contamination_blocks_entry_when_gap_ratio_high` accepts both outcomes.

**Current state**: Assertion uses `assertIn(..., {"block_new_entries", "market_entry_allowed"})` — always passes.

**Required for 100%**:
- Assert `block_new_entries` when gap ratio ≥ 0.20
- Assert `market_entry_allowed` only when gap ratio < 0.20
- Test with actual gap-injected candles through live loop

**Files**: `tests/test_v718.py:732-754`  
**Impact**: Test does not prove the claimed behavior.

---

### 2.2 Champion/Challenger Promotion Gates Incomplete

**What**: `can_promote()` is called with only 4 metrics; missing 6 required metrics.

**Current state**: CLI calls `can_promote(30, 100, -0.01, 0.01)` without Sharpe, MDD, Calmar, CI, latency, PSI.

**Required for 100%**:
- Pass all required metrics: Sharpe, MDD(p90), Calmar, CI, latency, PSI
- Fail promotion if any metric is missing
- Validate metric thresholds against policy

**Files**: `cli.py:40`, `features.py:844-893`, `tests/test_core.py:995-998`  
**Impact**: Promotion can proceed with incomplete validation.

---

### 2.3 Rate-Limit Retry-After Not Respected

**What**: Rate limit manager sets permanent backoff on 429 but never resets based on Retry-After.

**Current state**: `backoff_active=True` on 429 permanently. `exchange.py` parses Retry-After header but live rate limiting does not consume it.

**Required for 100%**:
- Parse Retry-After duration in `RateLimitManager`
- Schedule reset after duration expires
- Test with simulated 429 + Retry-After: 60

**Files**: `live.py:82-89`, `exchange.py:403-407`  
**Impact**: Can remain in backoff state longer than required.

---

## 3. Documentation Gaps

### 3.1 README Contradicts Implementation

**What**: README claims ~85% complete with 92 active features, but F11/F12 are excluded from active set.

**Current state**: README says "15 features pending" but also lists them as "implemented" in some sections.

**Required for 100%**:
- State exact count: 92 active, 15 pending
- Clarify which features are mock-only vs real
- Add explicit "not for live trading" warnings

**Files**: `README.md`  

---

### 3.2 IMPLEMENTATION_GAPS_AND_IMPROVEMENTS.md Overclaims

**What**: Claims "All original v7.18 gaps have been addressed" but multiple code gaps remain.

**Current state**: Line 3 says "All items from original v7.18 scaffold have been addressed."

**Required for 100%**:
- Remove "ALL RESOLVED" claim
- List remaining code gaps explicitly
- Distinguish code gaps from operational validation

**Files**: `docs/IMPLEMENTATION_GAPS_AND_IMPROVEMENTS.md`  

---

### 3.3 OFFLINE_TRAINING_PIPELINE.md Lists Resolved Gaps as Remaining

**What**: Lists items as "remaining" that are already implemented.

**Required for 100%**:
- Update to reflect actual implementation status
- Move implemented items to "Implemented" section
- Keep only genuine remaining gaps

**Files**: `docs/OFFLINE_TRAINING_PIPELINE.md`  

---

### 3.4 TRACEABILITY_MATRIX References Missing Test

**What**: References `test_gap_policy_blocks_trade_flow_contamination` which does not exist.

**Required for 100%**:
- Add the missing test or remove reference
- Verify all referenced tests exist

**Files**: `docs/TRACEABILITY_MATRIX.md`  

---

## 4. Warning Gaps

### 4.1 collect-archive CLI Missing Network Boundary

**What**: `collect-archive` command does not require `--allow-public-network` flag.

**Current state**: Archive collection proceeds without explicit network opt-in.

**Required for 100%**:
- Add `--allow-public-network` flag
- Default to offline fixture when flag absent

**Files**: `cli.py:158-171`  

---

## 5. Action Plan

### Priority 1: Safety (Blocking)
1. Revert F11/F12 to `pending_data_source` — **DONE**
2. Wire source parity into entry gates
3. Implement semantic production approval
4. Add real position/account state to live loop
5. Add `submit=True` and order lifecycle

### Priority 2: Tests (Critical)
6. Fix gap-contamination test to assert actual behavior
7. Complete champion/challenger metrics
8. Implement Retry-After respect
9. Add test for source parity blocking

### Priority 3: Documentation
10. Rewrite README with accurate percentages
11. Update IMPLEMENTATION_GAPS with honest status
12. Fix OFFLINE_TRAINING_PIPELINE accuracy
13. Add TRACEABILITY_MATRIX missing test
14. Create this document: `docs/V718_CRITICAL_GAPS.md`

---

**Verification**: All items must be addressed before claiming 100% implementation.
