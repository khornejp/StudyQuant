#!/usr/bin/env bash
# BTCUSDT User-Regime Pipeline (Linux/macOS shell)
# ---------------------------------------------------------------------------
# Intended flow (same as run_full_pipeline.ps1):
#   1. Download 2020-01-01 ~ 2025-12-31 Binance archive (full 6-year span)
#   2. Combine into one Parquet file
#   3. Train regime-aware models on YOUR user-specified up/down/range
#      periods (regimes.json), with training restricted to 2020-2024 and
#      validation on 2025-01-01 ~ 2025-06-30
#   4. Backtest on 2025-07-01 ~ 2025-12-31 (out-of-sample)
#
# Requirements:
#   - Python with pyarrow, catboost, numpy, pandas installed
#   - ~16GB RAM
#   - regimes.json with your up/down/range period definitions
#   - Network access to data.binance.vision
#
# Usage:
#   chmod +x run_full_pipeline.sh
#   ./run_full_pipeline.sh
# ---------------------------------------------------------------------------

set -euo pipefail

# ====== Configuration =====================================================
REGIME_FILE="${REGIME_FILE:-regimes.json}"
DOWNLOAD_START="${DOWNLOAD_START:-2020-01-01}"
TRAINING_END="${TRAINING_END:-2024-12-31}"
VALIDATION_START="${VALIDATION_START:-2025-01-01}"
VALIDATION_END="${VALIDATION_END:-2025-06-30}"
BACKTEST_START="${BACKTEST_START:-2025-07-01}"
BACKTEST_END="${BACKTEST_END:-2025-12-31}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-artifacts}"
# ==========================================================================

echo "=== BTCUSDT User-Regime Pipeline ==="
echo "Training span    : $DOWNLOAD_START -> $TRAINING_END"
echo "Validation span  : $VALIDATION_START -> $VALIDATION_END (held out)"
echo "Backtest span    : $BACKTEST_START -> $BACKTEST_END (out of sample)"
echo "Regime file      : $REGIME_FILE"
echo ""

if [[ ! -f "$REGIME_FILE" ]]; then
    echo "ERROR: regime file not found: $REGIME_FILE" >&2
    echo ""
    echo "Create $REGIME_FILE with this shape:" >&2
    cat >&2 <<'JSON_EOF'
{
  "periods": [
    {"regime": "up",    "start": "2020-04-01", "end_exclusive": "2021-05-15"},
    {"regime": "down",  "start": "2021-05-15", "end_exclusive": "2021-08-01"},
    {"regime": "range", "start": "2021-08-01", "end_exclusive": "2021-10-15"}
    // ... cover the full 2020-01-01 -> 2024-12-31 range
  ]
}
JSON_EOF
    echo "Allowed regime values: up, down, range" >&2
    exit 1
fi

mkdir -p "$ARTIFACTS_DIR"

# ----------------------------------------------------------------------------
# PHASE 1: Download the full 2020-01-01 ~ 2025-12-31 archive
# ----------------------------------------------------------------------------
echo "[Phase 1] Downloading Binance archive ($DOWNLOAD_START -> $BACKTEST_END)..."

ARCHIVE_DIR="$ARTIFACTS_DIR/archive_full"
mkdir -p "$ARCHIVE_DIR"

python -m btcusdt_quant collect-archive \
    --start "$DOWNLOAD_START" --end "$BACKTEST_END" \
    --output "$ARCHIVE_DIR" \
    --allow-public-network

# ----------------------------------------------------------------------------
# PHASE 2: Combine daily CSVs into a single Parquet
# ----------------------------------------------------------------------------
echo ""
echo "[Phase 2] Combining daily archive files into a single Parquet..."

FULL_PARQUET="$ARTIFACTS_DIR/btcusdt_2020_2025.parquet"

if [[ ! -f "$FULL_PARQUET" ]]; then
    python - <<PY
import glob, os, sys
import pyarrow.csv as pv
import pyarrow.parquet as pq
import pyarrow as pa

archive_dir = "$ARCHIVE_DIR"
out_path    = "$FULL_PARQUET"

files = sorted(glob.glob(os.path.join(archive_dir, 'BTCUSDT-1m-*.csv')))
if not files:
    print(f'no archive csv files in {archive_dir}', file=sys.stderr)
    sys.exit(1)
print(f'concatenating {len(files)} daily files...')

writer = None
total_rows = 0
batch = []
BATCH_SIZE = 30

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
PY
else
    echo "  (using cached $FULL_PARQUET)"
fi

# ----------------------------------------------------------------------------
# PHASE 3: Train on 2020 -> 2024, validate on 2025 H1
# ----------------------------------------------------------------------------
echo ""
echo "[Phase 3] Training regime-aware ensemble..."
echo "  Features are computed once over the full 2020-2025 series."
echo "  Training rows: $DOWNLOAD_START -> $TRAINING_END"
echo "  Validation rows: $VALIDATION_START -> $VALIDATION_END"
echo "  Regime labels from: $REGIME_FILE"
echo ""

MODEL_DIR="$ARTIFACTS_DIR/regime_stacking_model"

python -m btcusdt_quant train \
    --input "$FULL_PARQUET" \
    --use-user-regime \
    --user-regime-file "$REGIME_FILE" \
    --ensemble \
    --training-start "$DOWNLOAD_START" \
    --training-end "$TRAINING_END" \
    --test-start "$VALIDATION_START" \
    --test-end "$VALIDATION_END" \
    --cv-mode combinatorial_purged \
    --n-groups 6 \
    --test-group-count 2 \
    --threshold-objective trading_pnl \
    --output "$MODEL_DIR"

echo ""
echo "  Training complete."
echo "  Model:        $MODEL_DIR"

# ----------------------------------------------------------------------------
# PHASE 4: Backtest on 2025 H2 (out-of-sample)
# ----------------------------------------------------------------------------
echo ""
echo "[Phase 4] Running backtest on $BACKTEST_START -> $BACKTEST_END ..."

BACKTEST_DIR="$ARTIFACTS_DIR/backtest_results"

python -m btcusdt_quant backtest \
    --input "$FULL_PARQUET" \
    --model-artifact "$MODEL_DIR" \
    --user-regime-file "$REGIME_FILE" \
    --backtest-start "$BACKTEST_START" \
    --output "$BACKTEST_DIR"

echo ""
echo "=== Pipeline Complete ==="
echo ""
echo "Outputs:"
echo "  Combined data : $FULL_PARQUET"
echo "  Model         : $MODEL_DIR"
echo "  Backtest      : $BACKTEST_DIR"
