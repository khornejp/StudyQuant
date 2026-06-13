# BTCUSDT 1m Quant Trading System v7.18 — Scaffold Implementation

**Status**: Core scaffold implementation complete. Data collection and training pipeline operational. Live execution framework ready with model artifact loading and TP/SL bracket order wiring.  
**Active features**: 107 of 107 (F01–F12). F11–F12 compute from real-time exchange sources when available (depth, funding, ADL, mark price).  
**See**: `docs/V718_CRITICAL_GAPS.md` for the complete critical review.

**⚠️ SAFETY WARNING**: Do not use for live trading. Mock exchange is default. Production requires human approval, security audit, and testnet soak.

## What is implemented

### Data Pipeline (Core Complete)
- **Canonical 1-minute timeline** with gap repair, gap metrics, and gap ratio tracking
- **107 active computed features** across F01–F12 (price/return, trend, volatility, volume, candle structure, gap quality, regime normalization, volatility-adjusted returns/trend/flow, microstructure, exchange-safety)
- **F11–F12 real-time features**: Compute from live exchange data when available (depth, funding, ADL, mark price, premium index, leverage bracket). Fall back to safe mock defaults when sources are offline.
- **Feature governance**: finite-value enforcement, clipping (z-score ±10, ratio ±100, return ±0.20, vol_adj ±10), NaN source classification (outage, warmup, structural, isolated)
- **Source contracts**: availability grading (A/B/C/D), train/live feature parity gates, column data contracts, retention contracts

### ML Pipeline (Core Complete)
- **Model adapters**: stdlib centroid linear classifier (default), optional LightGBM/CatBoost with graceful fallback chain
- **Walk-forward validation**: standard purged splits + combinatorial purged CV (CPCV) with sample uniqueness weighting (O(N+T))
- **Calibration**: Platt/Beta/Isotonic calibration with sample gates, ECE/Brier drift monitoring
- **Feature selection**: 6-stage pipeline (Spearman clustering, gain filtering, permutation importance, SHAP stability, ablation testing, core feature set)
- **Bootstrap confidence intervals**: score-bin CI for net return and win rate
- **Optuna integration**: budget profiles (research/practical/full) with MDD(p90) objective
- **Champion-challenger workflow**: shadow → canary 5/20/50 → full promotion with rollback gates

### Live Execution (Framework Ready)
- **Exchange adapters**: Mock (default), Binance USD-M Futures Testnet (signed), Production (hard-gated with semantic approval)
- **Rate limiting**: token bucket with emergency reserve (20%), 429/418/503 handling, retry-after respect with auto-reset
- **Position management**: one-way position guard, position sizing (fixed notional, Kelly placeholder), leverage cap, real position/account fetched from adapter
- **Order safety**: TP/SL bracket orders (reduce-only), clientOrderId reconciliation, gap-cross exit, submitted with `submit=True` when gates pass
- **Drawdown protocol**: 3-tier step-down (warn → reduce size → block entries → hard kill) with drawdown state tracked across live loop iterations
- **Ghost-fill prevention**: cancel-confirm lock, safe market exit
- **Emergency close**: priority-based execution, retry capped, hard kill on max retries
- **F11/F12 real-time sources**: Depth, funding, ADL, mark price fetched from exchange adapter and passed to feature computation
- **Source parity**: Train/live feature parity enforced in entry gates — blocks entries when parity fails
- **Model artifact loading**: `run_live()` accepts `--model-artifact` path; loads `LinearClassifier` from JSON and uses `probability()` for signal generation
- **TP/SL bracket wiring**: `submit_take_profit_stop_loss()` called after successful `safe_market_entry()` with 1% TP / 0.5% SL prices; atomic submission with cancel-on-failure for partial success protection

### Operational Monitoring (Scaffold Complete)
- **Clock drift**: NTP-style monitoring, thresholds at 100ms/500ms/1000ms
- **ADL monitoring**: rank-based actions (≥3 reduce size, ≥4 block entries, ≥5 hard kill)
- **Funding monitoring**: rate tracking, blackout detection, cost estimation
- **Calibration drift**: ECE, MCE, Brier, Brier skill score with rolling window

### Governance & Artifacts (Scaffold Complete)
- **13-stage pipeline**: strict stage ordering with enforcement
- **7-tier fallback chain**: allow → warn → raise_threshold → reduce_size → block_new_entries → rollback → hard_kill
- **Approval package**: dataset/model cards, feature registry, dependency graph, source contracts, calibration config, bootstrap CI, monitoring SLO, lineage manifest, security signoff
- **SHA-256 manifest**: artifact verification with path traversal rejection
- **Lineage**: MLflow/DVC optional adapters with local fallback

### CLI Commands
```powershell
# Dry-run demo (default: mock exchange, no network)
python -m btcusdt_quant demo --output artifacts/demo

# Candle collection (fixture or public klines)
python -m btcusdt_quant collect --output artifacts/collected/btcusdt_1m.csv --rows 240
python -m btcusdt_quant collect --output artifacts/collected/btcusdt_1m.csv --allow-public-network

# Archive collection (Binance daily kline archives)
python -m btcusdt_quant collect-archive --start 2024-01-01 --end 2024-01-31 --output artifacts/archive

# Offline training (fixture or local CSV)
python -m btcusdt_quant train --output artifacts/training
python -m btcusdt_quant train --input path\to\local_candles.csv --output artifacts/training_csv
python -m btcusdt_quant train --model-family auto --output artifacts/training_ml

# Live execution (mock WebSocket, gap repair, backfill)
python -m btcusdt_quant live --dry-run --output artifacts/live
python -m btcusdt_quant live --dry-run --output artifacts/live --model-artifact artifacts/training/model.json

# Artifact verification
python -m btcusdt_quant artifacts --path artifacts/demo

# Run tests
python -m unittest discover -s tests
python -m compileall btcusdt_quant tests
```

## Optional Dependencies
```powershell
# ML model stack
pip install -e ".[ml]"

# Lineage tracking
pip install -e ".[lineage]"

# WebSocket client (for real network)
pip install -e ".[exchange]"
```

## Safety Boundary

The scaffold is **testnet-ready** but **production-gated**:
- **Default mode**: mock exchange, no network, no credentials — safe for CI/local
- **Testnet mode**: signed Binance API, requires `BINANCE_API_KEY` and `BINANCE_API_SECRET` env vars, explicit `--allow-signed-network`
- **Production mode**: hard-gated behind `--allow-prod`, valid approval artifacts, and explicit confirmation

Never connect to production without:
1. Testnet soak validation
2. Independent security review
3. Human approval for LIVE_DEPLOYMENT stage
4. Real MLflow/DVC server integration

## Documentation
- `docs/TRACEABILITY_MATRIX.md` — ProjectMD requirement mapping
- `docs/OFFLINE_TRAINING_PIPELINE.md` — Training pipeline scope
- `docs/IMPLEMENTATION_GAPS_AND_IMPROVEMENTS.md` — Security findings
- `docs/REMAINING_GAPS_V718.md` — Production-only validation requirements

## Architecture

```
btcusdt_quant/
├── data.py              # Candle structures, canonical timeline, gap repair
├── dataset.py           # Feature engineering (70+ features), labeling, CSV/archive
├── feature_registry.py  # Feature definitions, dependency graph, categories
├── features.py          # Feature selection, calibration, bootstrap CI, Optuna
├── cv.py                # Purged CV, combinatorial CV, sample uniqueness
├── training.py          # Offline training, model adapters, artifact generation
├── models.py            # Model adapter protocol, stdlib/LightGBM/CatBoost
├── live.py              # Live execution engine, WebSocket, gap repair
├── exchange.py          # Exchange adapter protocol, Binance testnet/prod
├── risk.py              # Drawdown protocol, risk policy, sizing
├── monitoring.py        # Clock drift, ADL, funding, calibration drift
├── governance.py        # Pipeline stages, fallback chain, artifact writer
├── sources.py           # Source contracts, availability grades, parity
├── parity.py            # Train/live feature parity verification
├── lineage.py           # MLflow/DVC optional adapters, local fallback
├── failure_injection.py # Deterministic fault scenarios for testing
├── secrets.py           # Credential loading, masking
├── cli.py               # CLI entry point
    └── tests/
    ├── test_core.py     # 120 original tests
    └── test_v718.py     # 78 v7.18 regression tests
```

## Verification

Core tests pass:
```
Ran 213 tests in ~55s
OK (skipped=1)
```

## Remaining Gaps & Next Steps

1. **Production validation**: Testnet soak with real credentials and signed order submission
2. **ML model integration end-to-end**: Train → save artifact → live inference with real model (scaffold is ready, needs real data)
3. **TP/SL price optimization**: Currently fixed at 1% / 0.5% — needs dynamic ATR-based or model-predicted levels
4. **Security audit**: Credential handling, network hardening, production gating
5. **Performance benchmarking**: Latency under load, memory profiling, GC optimization

See `README_FULL.md` for detailed gap analysis.
