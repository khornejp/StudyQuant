# BTCUSDT 1m Quant Trading System v7.18 — Local Scaffold (40% Implemented, 60% Gaps Remain)

**Status**: This is a local scaffold with significant implementation gaps. It is NOT a production-ready system.  
**Active features**: 92 of 107 (F01–F10 only). 15 features (F11–F12) require real-time data sources.  
**See**: `docs/V718_CRITICAL_GAPS.md` for the complete critical review.

**⚠️ SAFETY WARNING**: Do not use for live trading. Mock exchange is default. Production requires human approval, security audit, and testnet soak.

## What is implemented

### Data Pipeline (100%)
- **Canonical 1-minute timeline** with gap repair, gap metrics, and gap ratio tracking
- **92 active computed features** across F01–F10 (price/return, trend, volatility, volume, candle structure, gap quality, regime normalization, volatility-adjusted returns/trend/flow)
- 15 additional features registered (F11–F12) but pending real-time data sources (depth, funding, ADL, mark price)
- **Feature governance**: finite-value enforcement, clipping (z-score ±10, ratio ±100, return ±0.20, vol_adj ±10), NaN source classification (outage, warmup, structural, isolated)
- **Source contracts**: availability grading (A/B/C/D), train/live feature parity gates, column data contracts, retention contracts

### ML Pipeline (100% of local scope)
- **Model adapters**: stdlib centroid linear classifier (default), optional LightGBM/CatBoost with graceful fallback chain
- **Walk-forward validation**: standard purged splits + combinatorial purged CV (CPCV) with sample uniqueness weighting (O(N+T))
- **Calibration**: Platt/Beta/Isotonic calibration with sample gates, ECE/Brier drift monitoring
- **Feature selection**: 6-stage pipeline (Spearman clustering, gain filtering, permutation importance, SHAP stability, ablation testing, core feature set)
- **Bootstrap confidence intervals**: score-bin CI for net return and win rate
- **Optuna integration**: budget profiles (research/practical/full) with MDD(p90) objective
- **Champion-challenger workflow**: shadow → canary 5/20/50 → full promotion with rollback gates

### Live Execution (Scaffold — 40% Implemented)
- **Exchange adapters**: Mock (default), Binance USD-M Futures Testnet (signed), Production (hard-gated)
- **Rate limiting**: token bucket with emergency reserve (20%), 429/418/503 handling, retry-after respect *(partial — Retry-After reset not implemented)*
- **Position management**: one-way position guard, position sizing (fixed notional, Kelly placeholder), leverage cap *(position state not wired into live loop)*
- **Order safety**: TP/SL bracket orders (reduce-only), clientOrderId reconciliation, gap-cross exit *(not actually submitted in live loop)*
- **Drawdown protocol**: 3-tier step-down (warn → reduce size → block entries → hard kill) *(drawdown state not passed in live loop)*
- **Ghost-fill prevention**: cancel-confirm lock, safe market exit
- **Emergency close**: priority-based execution, retry capped, hard kill on max retries
- **⚠️ Known gaps**: Live loop does not submit orders; source parity not enforced; risk state not fetched; real order lifecycle untested

### Operational Monitoring (100% of scaffold)
- **Clock drift**: NTP-style monitoring, thresholds at 100ms/500ms/1000ms
- **ADL monitoring**: rank-based actions (≥3 reduce size, ≥4 block entries, ≥5 hard kill)
- **Funding monitoring**: rate tracking, blackout detection, cost estimation
- **Calibration drift**: ECE, MCE, Brier, Brier skill score with rolling window

### Governance & Artifacts (100%)
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
    ├── test_core.py     # 120+ original tests
    └── test_v718.py     # 60+ v7.18 regression tests
```

## Verification

All tests pass:
```
Ran 182 tests in 60.889s
OK (skipped=1)
```
