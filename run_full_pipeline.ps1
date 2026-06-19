# BTCUSDT Regime-Aware Stacking Ensemble - Complete Pipeline (Windows PowerShell)
# Run this on a machine with sufficient RAM (16GB+) and CPU cores

$ErrorActionPreference = "Stop"

Write-Host "=== BTCUSDT Regime-Aware Stacking Pipeline ===" -ForegroundColor Cyan
Write-Host "This script will:"
Write-Host "  1. Collect training data from multiple market regimes"
Write-Host "  2. Convert to Parquet format"
Write-Host "  3. Train regime-aware stacking ensemble"
Write-Host "  4. Collect 2025 backtest data"
Write-Host "  5. Run backtest with regime-aware inference"
Write-Host ""

# ============================================================================
# PHASE 1: Data Collection (Training)
# ============================================================================

Write-Host "[Phase 1] Collecting training data from multiple regimes..." -ForegroundColor Yellow

# Uptrend periods
if (-not (Test-Path "artifacts/regime_up.parquet")) {
    Write-Host "  [1/3] Collecting uptrend data (2024-10~12)..." -ForegroundColor Gray
    python -m btcusdt_quant collect-archive `
        --start 2024-10-01 --end 2024-12-31 `
        --output artifacts/archive_up_2024 `
        --allow-public-network

    python -c "
import glob, pyarrow.csv as pv, pyarrow.parquet as pq, pyarrow as pa
files = sorted(glob.glob('artifacts/archive_up_2024/BTCUSDT-1m-*.csv'))
tables = [pv.read_csv(f) for f in files]
combined = pa.concat_tables(tables)
old_names = combined.column_names
new_names = []
for name in old_names:
    if name == 'count': new_names.append('number_of_trades')
    elif name == 'taker_buy_volume': new_names.append('taker_buy_base_volume')
    else: new_names.append(name)
combined = combined.rename_columns(new_names)
keep = [n for n in new_names if n not in ('close_time', 'ignore')]
combined = combined.select(keep)
pq.write_table(combined, 'artifacts/regime_up.parquet')
print(f'  Saved {combined.num_rows} rows')
"
}

# Downtrend periods
if (-not (Test-Path "artifacts/regime_down.parquet")) {
    Write-Host "  [2/3] Collecting downtrend data (2024-08~09)..." -ForegroundColor Gray
    python -m btcusdt_quant collect-archive `
        --start 2024-08-01 --end 2024-09-30 `
        --output artifacts/archive_down_2024 `
        --allow-public-network

    python -c "
import glob, pyarrow.csv as pv, pyarrow.parquet as pq, pyarrow as pa
files = sorted(glob.glob('artifacts/archive_down_2024/BTCUSDT-1m-*.csv'))
tables = [pv.read_csv(f) for f in files]
combined = pa.concat_tables(tables)
old_names = combined.column_names
new_names = []
for name in old_names:
    if name == 'count': new_names.append('number_of_trades')
    elif name == 'taker_buy_volume': new_names.append('taker_buy_base_volume')
    else: new_names.append(name)
combined = combined.rename_columns(new_names)
keep = [n for n in new_names if n not in ('close_time', 'ignore')]
combined = combined.select(keep)
pq.write_table(combined, 'artifacts/regime_down.parquet')
print(f'  Saved {combined.num_rows} rows')
"
}

# Ranging periods
if (-not (Test-Path "artifacts/regime_range.parquet")) {
    Write-Host "  [3/3] Collecting ranging data (2024-03~04)..." -ForegroundColor Gray
    python -m btcusdt_quant collect-archive `
        --start 2024-03-01 --end 2024-04-30 `
        --output artifacts/archive_range_2024 `
        --allow-public-network

    python -c "
import glob, pyarrow.csv as pv, pyarrow.parquet as pq, pyarrow as pa
files = sorted(glob.glob('artifacts/archive_range_2024/BTCUSDT-1m-*.csv'))
tables = [pv.read_csv(f) for f in files]
combined = pa.concat_tables(tables)
old_names = combined.column_names
new_names = []
for name in old_names:
    if name == 'count': new_names.append('number_of_trades')
    elif name == 'taker_buy_volume': new_names.append('taker_buy_base_volume')
    else: new_names.append(name)
combined = combined.rename_columns(new_names)
keep = [n for n in new_names if n not in ('close_time', 'ignore')]
combined = combined.select(keep)
pq.write_table(combined, 'artifacts/regime_range.parquet')
print(f'  Saved {combined.num_rows} rows')
"
}

# ============================================================================
# PHASE 2: Combine Training Data
# ============================================================================

Write-Host ""
Write-Host "[Phase 2] Combining training data..." -ForegroundColor Yellow
python -c "
import pyarrow.parquet as pq
import pyarrow as pa

up = pq.read_table('artifacts/regime_up.parquet')
down = pq.read_table('artifacts/regime_down.parquet')
range_data = pq.read_table('artifacts/regime_range.parquet')
combined = pa.concat_tables([up, down, range_data])
pq.write_table(combined, 'artifacts/training_combined.parquet')
print(f'Combined: {combined.num_rows} rows')
print(f'  Uptrend: {up.num_rows}')
print(f'  Downtrend: {down.num_rows}')
print(f'  Ranging: {range_data.num_rows}')
"

# ============================================================================
# PHASE 3: Train Regime-Aware Stacking Ensemble
# ============================================================================

Write-Host ""
Write-Host "[Phase 3] Training Regime-Aware Stacking Ensemble..." -ForegroundColor Yellow
Write-Host "  This will take 30-60 minutes depending on your hardware..." -ForegroundColor Gray
Write-Host ""

python -m btcusdt_quant train `
    --input artifacts/training_combined.parquet `
    --ensemble `
    --regime-aware `
    --output artifacts/regime_stacking_model

Write-Host ""
Write-Host "  Training complete!" -ForegroundColor Green
Write-Host "  Model saved to: artifacts/regime_stacking_model/" -ForegroundColor Green

# ============================================================================
# PHASE 4: Collect 2025 Backtest Data
# ============================================================================

Write-Host ""
Write-Host "[Phase 4] Collecting 2025 backtest data (unseen)..." -ForegroundColor Yellow

if (-not (Test-Path "artifacts/backtest_2025.parquet")) {
    python -m btcusdt_quant collect-archive `
        --start 2025-01-01 --end 2025-06-30 `
        --output artifacts/archive_2025 `
        --allow-public-network

    python -c "
import glob, pyarrow.csv as pv, pyarrow.parquet as pq, pyarrow as pa
files = sorted(glob.glob('artifacts/archive_2025/BTCUSDT-1m-*.csv'))
tables = [pv.read_csv(f) for f in files]
combined = pa.concat_tables(tables)
old_names = combined.column_names
new_names = []
for name in old_names:
    if name == 'count': new_names.append('number_of_trades')
    elif name == 'taker_buy_volume': new_names.append('taker_buy_base_volume')
    else: new_names.append(name)
combined = combined.rename_columns(new_names)
keep = [n for n in new_names if n not in ('close_time', 'ignore')]
combined = combined.select(keep)
pq.write_table(combined, 'artifacts/backtest_2025.parquet')
print(f'  Saved {combined.num_rows} rows')
"
}

# ============================================================================
# PHASE 5: Backtest on 2025 Data
# ============================================================================

Write-Host ""
Write-Host "[Phase 5] Running backtest on 2025 data..." -ForegroundColor Yellow

python -m btcusdt_quant backtest `
    --input artifacts/backtest_2025.parquet `
    --model-artifact artifacts/regime_stacking_model `
    --output artifacts/backtest_results

Write-Host ""
Write-Host "=== Pipeline Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Results:" -ForegroundColor Green
Write-Host "  Model: artifacts/regime_stacking_model/" -ForegroundColor Green
Write-Host "  Backtest: artifacts/backtest_results/" -ForegroundColor Green
Write-Host ""
Write-Host "To view results:" -ForegroundColor Gray
Write-Host "  Get-Content artifacts/backtest_results/run_summary.json | Write-Host" -ForegroundColor Gray
