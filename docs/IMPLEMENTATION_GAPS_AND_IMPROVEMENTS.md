# Implementation Gaps, Vulnerabilities, and Improvements

This file records the security and completeness findings discovered while turning the `ProjectMD/` BTCUSDT v7.18 documents into a safe local scaffold.

## Safety boundary decisions

- Live Binance REST calls, WebSocket streams, account-state reads, and order submission are intentionally absent.
- `MockExchangeAdapter` is the only exchange path in the demo and tests.
- Generated artifacts state `forbidden_use: live trading or real order submission`.

## Vulnerabilities avoided in this scaffold

1. **Credential exposure**: no API key fields, `.env` files, or signing configuration are required.
2. **Accidental live order placement**: the mock adapter raises if network access is enabled and only returns deterministic mock order IDs.
3. **Rate-limit ban risk**: the local `RateLimitManager` models 429 and 418 responses as deterministic safety actions.
4. **Gap-contaminated inference**: gap metrics and feature-group policies can block new entries when contamination thresholds are breached.
5. **One-way position race risk**: `OneWayPositionGuard` blocks new entries when a BTCUSDT position is already open.
6. **Artifact drift**: `artifact_manifest.json` records SHA-256 hashes and can be verified locally.

## Remaining implementation gaps before any real trading use

- Binance API integration must remain testnet-only until signed requests, listenKey refresh, order reconciliation, unknown 503 retry semantics, and rate-limit headers are validated.
- `wait_until_exit_orders_resolved` and ghost-fill cancellation timing require exchange-level failure-injection tests.
- Funding blackout duration, shadow-mode minimum duration, MDD warning/hard limits, and Grade C promotion thresholds need operator-approved numeric policies.
- ML model training is represented as governance scaffolding only; no production LightGBM/CatBoost model is trained in this local scaffold.
- Feature formulas are represented by safety mechanisms and artifact templates; the full 70+ feature registry should be expanded before production research runs.
- NTP/clock drift monitoring and ADL indicator monitoring are noted by ProjectMD as high-risk items and are not implemented in the local-only scaffold.

## Recommended next hardening steps

1. Add a testnet-only exchange adapter behind an explicit `--testnet` flag, still disabled by default.
2. Expand `feature_formula_registry` into a complete generated artifact from ProjectMD feature definitions.
3. Add virtual-time failure injection for 429 storms, 418 hard bans, WebSocket disconnects, and ghost-fill races.
4. Add real ML pipeline adapters only after deterministic data contracts and lockbox governance are complete.
