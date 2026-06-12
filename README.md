# BTCUSDT 1m Quant Trading System v7.18 Local Scaffold

This project is a safe local implementation scaffold derived from the Markdown documents in `ProjectMD/`.

It intentionally does **not** connect to Binance, open WebSockets, read account state, or submit orders. All exchange behavior is modeled through deterministic local mocks so the ProjectMD safety invariants can be tested without credentials or network access.

## What is implemented

- Data pipeline: canonical 1-minute timeline, gap metrics, gap repair, feature-group gap policy.
- Feature governance: finite-value enforcement, clipping, NaN source classification.
- Live safety scaffold: token-bucket rate limiting, one-way position guard, position sizing, mock exchange adapter.
- Operational governance: 13-stage pipeline transition enforcement, deterministic fallback policy, artifact manifest/hash generation, approval artifact templates.
- ML/ops/execution scaffolds: strict rolling warm-up, calibration sample gates, purged split contracts, bootstrap CI, Optuna budget profiles, monitoring SLO actions, funding blackout, ghost-fill safe-exit, and emergency close behavior.
- Offline research pipeline: fixture/local CSV collection, optional explicit public-kline CSV collection, canonical timeline, gap report, stdlib feature matrix, forward labels, purged walk-forward training, validation/test metrics, calibration/threshold reports, and verifiable training artifacts.
- CLI: local dry-run demo, candle collection, offline training, and artifact verification.
- Tests: core safety invariants and smoke coverage.
- Documentation: implementation gaps, vulnerabilities, and improvement notes in `docs/IMPLEMENTATION_GAPS_AND_IMPROVEMENTS.md`.
- Traceability: ProjectMD requirement mapping in `docs/TRACEABILITY_MATRIX.md`.

## Run locally

```powershell
python -m btcusdt_quant --help
python -m btcusdt_quant demo --output artifacts/demo
python -m btcusdt_quant collect --output artifacts/collected/btcusdt_1m.csv
python -m btcusdt_quant train --output artifacts/training
python -m btcusdt_quant train --input path\to\local_candles.csv --output artifacts/training_csv
python -m btcusdt_quant artifacts --path artifacts/demo
python -m unittest discover -s tests
python -m compileall btcusdt_quant tests
```

The demo writes local approval-style artifacts under `artifacts/demo/` and prints a summary proving the mock exchange path was used.
The collection command defaults to deterministic fixture candles; unsigned public Binance kline download requires explicit `--allow-public-network`. The training command writes offline-only dataset/model cards, split manifests, fold metrics, calibration/threshold reports, and an artifact manifest. See `docs/OFFLINE_TRAINING_PIPELINE.md` for implemented scope and production-only gaps.

## Safety boundary

The scaffold is for local engineering validation only. It is not a live trading bot and must not be connected to production credentials without replacing mocks, adding integration testnet gates, and completing the unresolved items documented in `docs/IMPLEMENTATION_GAPS_AND_IMPROVEMENTS.md`.
