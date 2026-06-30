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
    # Stream-concatenate to avoid loading all 6 years into memory at once.
    # Column renames match dataset.load_parquet_candles expectations:
    #   count               -> number_of_trades
    #   taker_buy_volume    -> taker_buy_base_volume
    # close_time and ignore are dropped (not used downstream).
    python -c @"
import glob, os, sys
import pyarrow.csv as pv
import pyarrow.parquet as pq
import pyarrow as pa

archive_dir = r'$ArchiveDir'
out_path    = r'$FullParquet'

files = sorted(glob.glob(os.path.join(archive_dir, 'BTCUSDT-1m-*.csv')))
if not files:
    print(f'no archive csv files in {archive_dir}', file=sys.stderr)
    sys.exit(1)
print(f'concatenating {len(files)} daily files...')

writer = None
total_rows = 0
batch = []
BATCH_SIZE = 30  # ~1 month at a time

def flush_batch(writer, batch):
    if not batch:
        return writer, 0
    tbl = pa.concat_tables(batch, promote=True)
    renamed = []
    for n in tbl.column_names:
        if n == 'count':                   renamed.append('number_of_trades')
        elif n == 'taker_buy_volume':       renamed.append('taker_buy_base_volume')
        else:                                renamed.append(n)
    tbl = tbl.rename_columns(renamed)
    keep = [n for n in renamed if n not in ('close_time', 'ignore')]
    tbl = tbl.select(keep)
    if writer is None:
        writer = pq.ParquetWriter(out_path, tbl.schema)
    writer.write_table(tbl)
    return writer, tbl.num_rows

for path in files:
    try:
        batch.append(pv.read_csv(path))
    except Exception as e:
        print(f'WARN: failed to read {path}: {e}', file=sys.stderr)
        continue
    if len(batch) >= BATCH_SIZE:
        writer, n = flush_batch(writer, batch)
        total_rows += n
        batch = []

writer, n = flush_batch(writer, batch)
total_rows += n
if writer is not None:
    writer.close()

print(f'  -> wrote {total_rows:,} rows to {out_path}')
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
Write-Host "  Expect 30-60 minutes depending on hardware." -ForegroundColor Gray
Write-Host ""

$ModelDir = Join-Path $ArtifactsDir "regime_stacking_model"

python -m btcusdt_quant train `
    --input $FullParquet `
    --use-user-regime `
    --user-regime-file $RegimeFile `
    --ensemble `
    --training-start $DownloadStart `
    --training-end $TrainingEnd `
    --test-start $ValidationStart `
    --test-end $ValidationEnd `
    --cv-mode combinatorial_purged `
    --n-groups 6 `
    --test-group-count 2 `
    --threshold-objective trading_pnl `
    --output $ModelDir

Write-Host ""
Write-Host "  Training complete." -ForegroundColor Green
Write-Host "  Model:        $ModelDir" -ForegroundColor Green
Write-Host "  Run summary:  $ModelDir\run_summary.json" -ForegroundColor Green

# ============================================================================
# PHASE 4: Backtest on 2025-07-01 ~ 2025-12-31 (truly unseen)
# ============================================================================

Write-Host ""
Write-Host "[Phase 4] Running backtest on $BacktestStart -> $BacktestEnd ..." -ForegroundColor Yellow

$BacktestDir = Join-Path $ArtifactsDir "backtest_results"

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
Write-Host "=== Pipeline Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Outputs:" -ForegroundColor Green
Write-Host "  Combined data : $FullParquet" -ForegroundColor Green
Write-Host "  Model         : $ModelDir" -ForegroundColor Green
Write-Host "  Backtest      : $BacktestDir" -ForegroundColor Green
Write-Host ""
Write-Host "To inspect the backtest summary:" -ForegroundColor Gray
Write-Host "  Get-Content $BacktestDir\backtest_summary.json | ConvertFrom-Json | ConvertTo-Json -Depth 10" -ForegroundColor Gray
