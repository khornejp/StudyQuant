# Implementation Gaps, Vulnerabilities, and Improvements

This file records the security and completeness findings. **All items from the original v7.18 scaffold have been addressed.** Remaining items are production-only validation, not missing code.

## Safety boundary decisions

- Credentialed/live Binance REST calls, WebSocket streams, account-state reads, and order submission are **gated**, not absent.
- `MockExchangeAdapter` remains the **default** path in demo and tests.
- `BinanceUsdMFuturesTestnetAdapter` is available behind `--exchange binance-testnet --allow-signed-network`.
- `BinanceUsdMFuturesProdAdapter` is **hard-gated** behind `--allow-prod` + valid approval artifacts.
- Generated artifacts state `forbidden_use: live trading or real order submission` until approval.

## Vulnerabilities avoided (original + v7.18)

1. **Credential exposure**: credentials loaded only from `BINANCE_API_KEY` / `BINANCE_API_SECRET` env vars; never logged or stored in files.
2. **Accidental live order placement**: mock adapter is default; testnet requires explicit flags; prod requires approval artifacts.
3. **Rate-limit ban risk**: `RateLimitManager` models 429/418 with deterministic actions; retry-after respected; capped retries.
4. **Gap-contaminated inference**: gap metrics and feature-group policies block entries at 0.20 ratio.
5. **One-way position race risk**: `OneWayPositionGuard` blocks entries when position open.
6. **Artifact drift**: `artifact_manifest.json` records SHA-256 hashes with path traversal rejection.
7. **Ghost-fill race**: `GhostFillPrevention` with cancel-confirm lock and safe exit.
8. **Drawdown cascade**: `DrawdownProtocol` with 3-tier step-down (warn → reduce → block → kill).
9. **Calibration drift**: `CalibrationDriftMonitor` tracks ECE/Brier/MCE with rolling windows.
10. **Clock drift**: `ClockDriftService` hard-kills at ≥1000ms.
11. **ADL risk**: `ADLMonitorService` blocks entries at rank ≥4, kills at ≥5.

## Original gaps — ALL RESOLVED

| Gap | Resolution | File |
|-----|-----------|------|
| Binance signed/testnet API | ✅ Implemented | `exchange.py`, `secrets.py` |
| listenKey refresh | ✅ Implemented | `exchange.py` |
| Order reconciliation | ✅ Implemented | `live.py`, `exchange.py` |
| 503 retry semantics | ✅ Implemented | `exchange.py` (query-by-clientOrderId) |
| Rate-limit headers | ✅ Implemented | `exchange.py` (X-MBX-USED-WEIGHT, Retry-After) |
| Ghost-fill timing | ✅ Implemented | `live.py`, `risk.py` |
| Funding blackout | ✅ Implemented | `monitoring.py` |
| MDD limits | ✅ Implemented | `risk.py` |
| LightGBM/CatBoost/Optuna | ✅ Implemented | `models.py` (optional) |
| 70+ feature registry | ✅ Implemented | `feature_registry.py` (107 features, 92 active) |
| NTP/clock drift | ✅ Implemented | `monitoring.py` |
| ADL monitoring | ✅ Implemented | `monitoring.py` |
| Public backfill | ✅ Implemented | `dataset.py` (pagination, checkpointing) |
| WebSocket live | ✅ Implemented | `live.py` |
| Train/live parity | ✅ Implemented | `parity.py`, `sources.py` |
| Failure injection | ✅ Implemented | `failure_injection.py` |
| MLflow/DVC lineage | ✅ Implemented | `lineage.py` (optional fallback) |

## Production-only validation (NOT code gaps)

These are operational items requiring real-world testing:

1. **Testnet soak**: 7+ days of real signed testnet trading
2. **Latency SLO**: real exchange latency measurement
3. **Credential rotation**: formal SOP for API key rotation
4. **Security audit**: third-party review of production path
5. **Human approval**: formal sign-off for LIVE_DEPLOYMENT stage
6. **MLflow/DVC server**: deployed tracking server and remote storage
7. **Long-running WS**: 24h+ continuous WebSocket validation
8. **Exchange drills**: real outage/maintenance window drills
9. **Funding/ADL validation**: real endpoint behavior under volatility
10. **Partial fill reconciliation**: real order lifecycle validation

See `docs/REMAINING_GAPS_V718.md` for full checklist.
