# BTCUSDT User-Regime Pipeline (Windows PowerShell)
# ---------------------------------------------------------------------------
# Intended flow:
#   1. Download 2020-01-01 ~ 2025-12-31 Binance archive (full 6-year span)
#   2. Combine into one Parquet file
#   3. Train regime-aware models using YOUR user-specified up/down/range
#      periods (regimes.json), with training data restricted to 2020-2024
#      (validated on 2025-01-01 ~ 2025-06-30)
#   4. Backtest the trained models on 2025-07-01 ~ 2025-12-31 (out-of-sample,
#      never seen during training or validation)
#
# Requirements:
#   - Python with pyarrow, catboost, numpy, pandas installed
#   - ~16GB RAM (5 years of 1m candles ~ 2.6M rows; features ~3GB in memory)
#   - regimes.json with your up/down/range period definitions
#   - Network access to data.binance.vision for archive downloads
#
# Usage:
#   # Edit the variables below to point at your regimes.json, then:
#   powershell -ExecutionPolicy Bypass -File run_full_pipeline.ps1
# ---------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

# ====== Configuration =====================================================
$RegimeFile      = "regimes.json"           # YOUR up/down/range periods
$DownloadStart   = "2020-01-01"             # earliest training data
$TrainingEnd     = "2024-12-31"             # last day used for model fitting
$ValidationStart = "2025-01-01"             # in-sample test window (no fitting)
$ValidationEnd   = "2025-06-30"
$BacktestStart   = "2025-07-01"             # final out-of-sample backtest
$BacktestEnd     = "2025-12-31"
$ArtifactsDir    = "artifacts"
# ==========================================================================

Write-Host "=== BTCUSDT User-Regime Pipeline ===" -ForegroundColor Cyan
Write-Host "Training span    : $DownloadStart -> $TrainingEnd"
Write-Host "Validation span  : $ValidationStart -> $ValidationEnd (held out)"
Write-Host "Backtest span    : $BacktestStart -> $BacktestEnd (out of sample)"
Write-Host "Regime file      : $RegimeFile"
Write-Host ""

# Validate regime file exists before doing anything expensive
if (-not (Test-Path $RegimeFile)) {
    Write-Host "ERROR: regime file not found: $RegimeFile" -ForegroundColor Red
    Write-Host ""
    Write-Host "Create $RegimeFile with this shape:" -ForegroundColor Yellow
    Write-Host '{'
    Write-Host '  "periods": ['
    Write-Host '    {"regime": "up",    "start": "2020-04-01", "end_exclusive": "2021-05-15"},'
    Write-Host '    {"regime": "down",  "start": "2021-05-15", "end_exclusive": "2021-08-01"},'
    Write-Host '    {"regime": "range", "start": "2021-08-01", "end_exclusive": "2021-10-15"},'
    Write-Host '    // ... cover the full 2020-01-01 -> 2024-12-31 range'
    Write-Host '  ]'
    Write-Host '}'
    Write-Host ""
    Write-Host "Allowed regime values: up, down, range"
    exit 1
}

if (-not (Test-Path $ArtifactsDir)) {
    New-Item -ItemType Directory -Path $ArtifactsDir | Out-Null
}

# ============================================================================
# PHASE 1: Download the full 2020-01-01 ~ 2025-12-31 archive in one shot
# ============================================================================

Write-Host "[Phase 1] Downloading Binance archive ($DownloadStart -> $BacktestEnd)..." -ForegroundColor Yellow

$ArchiveDir = Join-Path $ArtifactsDir "archive_full"
if (-not (Test-Path $ArchiveDir)) {
    New-Item -ItemType Directory -Path $ArchiveDir | Out-Null
}

# The CLI's collect-archive supports resuming via checkpoint, so re-runs are
# cheap if you stop and restart.
python -m btcusdt_quant collect-archive `
    --start $DownloadStart --end $BacktestEnd `
    --output $ArchiveDir `
    --allow-public-network

# ============================================================================
# PHASE 2: Combine daily CSVs into a single Parquet
# ============================================================================

Write-Host ""
Write-Host "[Phase 2] Combining daily archive files into a single Parquet..." -ForegroundColor Yellow

$FullParquet = Join-Path $ArtifactsDir "btcusdt_2020_2025.parquet"

if (-not (Test-Path $FullParquet)) {
    # Reuse dataset.py's own archive parser (handles header/no-header
    # auto-detection, OHLCV validation, duplicate open_time dedup) instead of
    # re-implementing CSV parsing here. This guarantees the exact same
    # parsing rules used everywhere else in the codebase (training, backtest,
    # tests) are applied to the data that feeds the pipeline.
    python -c @"
import sys
from pathlib import Path
from btcusdt_quant import dataset

archive_dir = Path(r'$ArchiveDir')
out_path    = Path(r'$FullParquet')

print('loading archive candles (this auto-detects header/no-header CSVs, '
      'validates OHLCV, and de-duplicates by open_time)...')
candles = dataset.load_archive_candles(archive_dir)
print(f'  loaded {len(candles):,} raw candles')

print('writing Parquet...')
dataset.write_candles_parquet(out_path, candles)
print(f'  -> wrote {len(candles):,} rows to {out_path}')
"@
} else {
    Write-Host "  (using cached $FullParquet)"
}

# ============================================================================
# PHASE 3: Train regime-aware models on 2020 -> 2024 with validation on 2025 H1
# ============================================================================

Write-Host ""
Write-Host "[Phase 3] Training regime-aware ensemble..." -ForegroundColor Yellow
Write-Host "  Features are computed once over the full 2020-2025 series." -ForegroundColor Gray
Write-Host "  Training rows are restricted to $DownloadStart -> $TrainingEnd via --training-end." -ForegroundColor Gray
Write-Host "  Validation rows are $ValidationStart -> $ValidationEnd via --test-start/--test-end." -ForegroundColor Gray
Write-Host "  Regime labels come from $RegimeFile (--use-user-regime)." -ForegroundColor Gray
Write-Host ""
Write-Host "  Per-regime Optuna tuning (--optuna) IS applied: each long/short" -ForegroundColor DarkYellow
Write-Host "  CatBoost model gets its own small Optuna study to pick iterations," -ForegroundColor DarkYellow
Write-Host "  learning_rate, depth, and l2_leaf_reg on a chronological 80/20" -ForegroundColor DarkYellow
Write-Host "  holdout of that regime's rows. Other flags (--ensemble, --cv-mode," -ForegroundColor DarkYellow
Write-Host "  --threshold-objective, --feature-selection) are NOT applied on" -ForegroundColor DarkYellow
Write-Host "  this path." -ForegroundColor DarkYellow
Write-Host ""

$ModelDir = Join-Path $ArtifactsDir "regime_stacking_model"

python -m btcusdt_quant train `
    --input $FullParquet `
    --use-user-regime `
    --user-regime-file $RegimeFile `
    --training-start $DownloadStart `
    --training-end $TrainingEnd `
    --test-start $ValidationStart `
    --test-end $ValidationEnd `
    --optuna `
    --optuna-trials 30 `
    --output $ModelDir

Write-Host ""
Write-Host "  Training complete." -ForegroundColor Green
Write-Host "  Model:        $ModelDir" -ForegroundColor Green
Write-Host "  Run summary:  $ModelDir\run_summary.json" -ForegroundColor Green

# ============================================================================
# PHASE 4: Backtest on 2025-07-01 ~ 2025-12-31 (truly unseen)
#
# Two backtests are run so you can compare:
#   (4a) user-regime file  -> uses regimes.json. Because those 2025 regimes are
#        labeled in hindsight, this shows "how the model does WHEN regime
#        routing is perfect" (has look-ahead bias, NOT live performance).
#   (4b) auto-regime        -> RegimeDetector classifies up/down/range from the
#        trend slope in real time, exactly as a live deployment must. This is
#        the realistic, deployable estimate. Compare its gross return to 4a:
#        if 4b is far worse, the model leans on perfect foresight of regimes.
# ============================================================================

Write-Host ""
Write-Host "[Phase 4a] Backtest with hand-labeled regimes ($RegimeFile) ..." -ForegroundColor Yellow

$BacktestDir     = Join-Path $ArtifactsDir "backtest_results"
$BacktestAutoDir = Join-Path $ArtifactsDir "backtest_results_auto_regime"

# Feed the full 2020-2025 series so the backtest can reuse warmup history,
# and let --backtest-start skip everything before $BacktestStart for the
# actual trading simulation. Reuse the same regime file so backtest period
# regime labels align with how the models were trained.
python -m btcusdt_quant backtest `
    --input $FullParquet `
    --model-artifact $ModelDir `
    --user-regime-file $RegimeFile `
    --backtest-start $BacktestStart `
    --output $BacktestDir

Write-Host ""
Write-Host "[Phase 4b] Backtest with REAL-TIME regime detection (--auto-regime) ..." -ForegroundColor Yellow
Write-Host "  This is the live-deployable path: no hand-labeled regime file." -ForegroundColor Gray

python -m btcusdt_quant backtest `
    --input $FullParquet `
    --model-artifact $ModelDir `
    --auto-regime `
    --backtest-start $BacktestStart `
    --output $BacktestAutoDir

Write-Host ""
Write-Host "=== Pipeline Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Outputs:" -ForegroundColor Green
Write-Host "  Combined data      : $FullParquet" -ForegroundColor Green
Write-Host "  Model              : $ModelDir" -ForegroundColor Green
Write-Host "  Backtest (labeled) : $BacktestDir" -ForegroundColor Green
Write-Host "  Backtest (auto)    : $BacktestAutoDir" -ForegroundColor Green
Write-Host ""
Write-Host "Compare the two backtests (gross return is the cleaner edge signal):" -ForegroundColor Gray
Write-Host "  `$a = (Get-Content $BacktestDir\backtest_summary.json | ConvertFrom-Json).backtest" -ForegroundColor Gray
Write-Host "  `$b = (Get-Content $BacktestAutoDir\backtest_summary.json | ConvertFrom-Json).backtest" -ForegroundColor Gray
Write-Host "  Write-Host \"labeled : gross=`$(`$a.gross_total_return) net=`$(`$a.net_total_return) trades=`$(`$a.trade_count)\"" -ForegroundColor Gray
Write-Host "  Write-Host \"auto    : gross=`$(`$b.gross_total_return) net=`$(`$b.net_total_return) trades=`$(`$b.trade_count)\"" -ForegroundColor Gray
Write-Host ""
Write-Host "If 'auto' is much worse than 'labeled', the model depends on perfect" -ForegroundColor Gray
Write-Host "regime foresight and will underperform live. If they're close, the" -ForegroundColor Gray
Write-Host "real-time detector reproduces the regime structure well enough to deploy." -ForegroundColor Gray
