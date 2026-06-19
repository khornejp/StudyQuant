#!/bin/bash
# Regime-aware Stacking Ensemble - Full Pipeline
# Run this on a machine with sufficient RAM and CPU

set -e

echo "=== BTCUSDT Regime-Aware Stacking Pipeline ==="

# 1. 데이터 수집 (이미 완료된 경우 스킵)
if [ ! -d "artifacts/archive_up_2024" ]; then
    echo "[1/6] Collecting uptrend data (2024-10~12)..."
    python -m btcusdt_quant collect-archive --start 2024-10-01 --end 2024-12-31 --output artifacts/archive_up_2024 --allow-public-network
fi

if [ ! -d "artifacts/archive_down_2024" ]; then
    echo "[2/6] Collecting downtrend data (2024-08~09)..."
    python -m btcusdt_quant collect-archive --start 2024-08-01 --end 2024-09-30 --output artifacts/archive_down_2024 --allow-public-network
fi

if [ ! -d "artifacts/archive_2months" ]; then
    echo "[3/6] Collecting ranging data (2024-03~04)..."
    python -m btcusdt_quant collect-archive --start 2024-03-01 --end 2024-04-30 --output artifacts/archive_2months --allow-public-network
fi

# 2. Parquet 변환
echo "[4/6] Converting to Parquet..."
python convertparquet.py

# 3. 학습 데이터 결합
echo "[5/6] Combining training data..."
python -c "
import pyarrow.parquet as pq
import pyarrow as pa

up = pq.read_table('artifacts/regime_up.parquet')
down = pq.read_table('artifacts/regime_down.parquet')
range_data = pq.read_table('artifacts/regime_range.parquet')
combined = pa.concat_tables([up, down, range_data])
pq.write_table(combined, 'artifacts/training_combined.parquet')
print(f'Combined: {combined.num_rows} rows')
"

# 4. Regime-aware Stacking 학습 (시간 소요 큼: 약 30~60분)
echo "[6/6] Training Regime-Aware Stacking Ensemble..."
python -m btcusdt_quant train \
    --input artifacts/training_combined.parquet \
    --ensemble \
    --regime-aware \
    --output artifacts/regime_stacking_model

echo "=== Training Complete ==="
echo "Model saved to: artifacts/regime_stacking_model/"
echo ""
echo "To backtest on 2025 data:"
echo "  python -m btcusdt_quant backtest \\"
echo "    --input artifacts/backtest_2025.parquet \\"
echo "    --model-artifact artifacts/regime_stacking_model \\"
echo "    --output artifacts/backtest_results"
