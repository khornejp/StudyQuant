# Implementation Gaps, Vulnerabilities, and Improvements

**Status**: Multiple critical code gaps remain. See `docs/V718_CRITICAL_GAPS.md` for full review.

## Remaining Code Gaps (Blocking)

| Gap | Status | File |
|-----|--------|------|
| F11/F12 real-time source integration | Pending | `feature_registry.py` |
| Live source parity enforcement | Missing | `live.py` |
| Production semantic approval | Missing | `exchange.py`, `governance.py` |
| Live order submission | Missing | `live.py` |
| Risk state wiring | Missing | `live.py` |
| Retry-After reset | Missing | `live.py`, `exchange.py` |

## Remaining Test Gaps (Critical)

| Gap | Status | File |
|-----|--------|------|
| Gap-contamination test | Ineffective | `tests/test_v718.py` |
| Champion/challenger metrics | Incomplete | `tests/test_core.py`, `cli.py` |
| Source parity blocking | Untested | Missing |
| Production approval validation | Untested | Missing |

## Vulnerabilities avoided (implemented)

1. **Credential exposure**: credentials loaded only from env vars; never logged.
2. **Accidental live order placement**: mock adapter default; explicit flags required.
3. **Rate-limit modeling**: `RateLimitManager` with deterministic actions.
4. **Gap-contaminated inference**: gap metrics block entries at 0.20 ratio.
5. **One-way position guard**: blocks entries when position open.
6. **Artifact drift**: SHA-256 hashes with path traversal rejection.
7. **Ghost-fill prevention**: cancel-confirm lock.
8. **Drawdown protocol**: 3-tier step-down.
9. **Calibration drift**: ECE/Brier/MCE tracking.
10. **Clock drift**: hard-kill at ≥1000ms.
11. **ADL risk**: block entries at rank ≥4.

## Production-only validation (operational, not code gaps)

1. **Testnet soak**: 7+ days real signed testnet
2. **Latency SLO**: real exchange measurement
3. **Credential rotation**: formal SOP
4. **Security audit**: third-party review
5. **Human approval**: LIVE_DEPLOYMENT sign-off
6. **MLflow/DVC server**: deployed tracking
7. **Long-running WS**: 24h+ validation
8. **Exchange drills**: maintenance window drills
9. **Funding/ADL validation**: real endpoint behavior
10. **Partial fill reconciliation**: real order lifecycle

See `docs/V718_CRITICAL_GAPS.md` for full checklist.
