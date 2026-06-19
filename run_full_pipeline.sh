#!/bin/bash
# BTCUSDT Regime-Aware Stacking Ensemble - Complete Pipeline
# Run this on a machine with sufficient RAM (16GB+) and CPU cores

set -e

echo "=== BTCUSDT Regime-Aware Stacking Pipeline ==="
echo "This script will:"
echo "  1. Collect training data from multiple market regimes"
echo "  2. Convert to Parquet format"
echo "  3. Train regime-aware stacking ensemble"
echo "  4. Collect 2025 backtest data"
echo "  5. Run backtest with regime-aware inference"
echo ""

# Configuration
TRAINING_DIR="artifacts/training"
BACKTEST_DIR="artifacts/backtest"

# ============================================================================
# PHASE 1: Data Collection (Training)
# ============================================================================

echo "[Phase 1] Collecting training data from multiple regimes..."

# Uptrend periods
if [ ! -f "artifacts/regime_up.parquet" ]; then
    echo "  [1/3] Collecting uptrend data (2024-10~12)..."
    python -m btcusdt_quant collect-archive \
        --start 2024-10-01 --end 2024-12-31 \
        --output artifacts/archive_up_2024 \
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
fi

# Downtrend periods
if [ ! -f "artifacts/regime_down.parquet" ]; then
    echo "  [2/3] Collecting downtrend data (2024-08~09)..."
    python -m btcusdt_quant collect-archive \
        --start 2024-08-01 --end 2024-09-30 \
        --output artifacts/archive_down_2024 \
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
fi

# Ranging periods
if [ ! -f "artifacts/regime_range.parquet" ]; then
    echo "  [3/3] Collecting ranging data (2024-03~04)..."
    python -m btcusdt_quant collect-archive \
        --start 2024-03-01 --end 2024-04-30 \
        --output artifacts/archive_2months \
        --allow-public-network
    
    python -c "
import glob, pyarrow.csv as pv, pyarrow.parquet as pq, pyarrow as pa
files = sorted(glob.glob('artifacts/archive_2months/BTCUSDT-1m-*.csv'))
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
fi

# ============================================================================
# PHASE 2: Combine Training Data
# ============================================================================

echo ""
echo "[Phase 2] Combining training data..."
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

echo ""
echo "[Phase 3] Training Regime-Aware Stacking Ensemble..."
echo "  This will take 30-60 minutes depending on your hardware..."
echo ""

python -m btcusdt_quant train \
    --input artifacts/training_combined.parquet \
    --ensemble \
    --regime-aware \
    --output artifacts/regime_stacking_model

echo ""
echo "  Training complete!"
echo "  Model saved to: artifacts/regime_stacking_model/"

# ============================================================================
# PHASE 4: Collect 2025 Backtest Data
# ============================================================================

echo ""
echo "[Phase 4] Collecting 2025 backtest data (unseen)..."

if [ ! -f "artifacts/backtest_2025.parquet" ]; then
    python -m btcusdt_quant collect-archive \
        --start 2025-01-01 --end 2025-06-30 \
        --output artifacts/archive_2025 \
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
fi

# ============================================================================
# PHASE 5: Backtest on 2025 Data
# ============================================================================

echo ""
echo "[Phase 5] Running backtest on 2025 data..."

python -m btcusdt_quant backtest \
    --input artifacts/backtest_2025.parquet \
    --model-artifact artifacts/regime_stacking_model \
    --output artifacts/backtest_results

echo ""
echo "=== Pipeline Complete ==="
echo ""
echo "Results:"
echo "  Model: artifacts/regime_stacking_model/"
echo "  Backtest: artifacts/backtest_results/"
echo ""
echo "To view results:"
echo "  cat artifacts/backtest_results/run_summary.json"
