# Offline BTCUSDT Data and Training Pipeline

**Status**: Implemented for offline training. Live integration gaps remain.

## Implemented

- `btcusdt_quant.dataset` loads local CSV candles or deterministic offline fixture.
- `python -m btcusdt_quant collect --output artifacts/collected/btcusdt_1m.csv` writes fixture candles.
- Unsigned public kline download requires explicit `--allow-public-network` flag.
- Canonical 1-minute timeline with gap repair and gap report.
- Strict warm-up handling and forward-return labels.
- Deterministic purged walk-forward training with stdlib centroid linear classifier.
- Verifiable artifacts: dataset_card, model_card, feature_formula_registry, split_manifest, fold_metrics, calibration_report, threshold_report, run_summary, artifact_manifest.

## Remaining Gaps (Operational, Not Code)

### Data Pipeline
- [x] Robust public collection pagination with retry/429 handling — **Done**
- [ ] WebSocket ingestion with REST backfill — production validation only
- [x] Live/train feature parity enforcement — **Done**
- [x] F11/F12 microstructure source integration (depth, funding, ADL, mark price) — **Done**

### ML Pipeline
- [x] LightGBM/CatBoost/Optuna lazy imports with graceful fallback — **Done**
- [x] Bootstrap confidence intervals around trading PnL — **Done**
- [x] Champion/challenger promotion with full metrics (Sharpe, MDD, Calmar, CI, latency, PSI) — **Done**

### Live Integration
- [x] Account reconciliation and listenKey lifecycle — **Done**
- [x] Rate-limit header validation with Retry-After reset — **Done**
- [x] Live order safety tests with failure injection — **Done**
- [ ] Human approval gates for production — requires human sign-off

The default training command is offline and safe for CI/local tests. Not a live trading system.

See `docs/V718_CRITICAL_GAPS.md` for full details.
