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
    # Reuse dataset.py's own archive parser (handles header/no-header
    # auto-detection, OHLCV validation, duplicate open_time dedup) instead of
    # re-implementing CSV parsing here.
    python - <<PY
import sys
from pathlib import Path
from btcusdt_quant import dataset

archive_dir = Path("$ARCHIVE_DIR")
out_path    = Path("$FULL_PARQUET")

print('loading archive candles (this auto-detects header/no-header CSVs, '
      'validates OHLCV, and de-duplicates by open_time)...')
candles = dataset.load_archive_candles(archive_dir)
print(f'  loaded {len(candles):,} raw candles')

print('writing Parquet...')
dataset.write_candles_parquet(out_path, candles)
print(f'  -> wrote {len(candles):,} rows to {out_path}')
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
echo "  Per-regime Optuna tuning (--optuna) IS applied: each long/short"
echo "  CatBoost model gets its own small Optuna study to pick iterations,"
echo "  learning_rate, depth, and l2_leaf_reg on a chronological 80/20"
echo "  holdout. Other flags (--ensemble, --cv-mode, --threshold-objective,"
echo "  --feature-selection) are NOT applied on this path."
echo ""

MODEL_DIR="$ARTIFACTS_DIR/regime_stacking_model"

python -m btcusdt_quant train \
    --input "$FULL_PARQUET" \
    --use-user-regime \
    --user-regime-file "$REGIME_FILE" \
    --training-start "$DOWNLOAD_START" \
    --training-end "$TRAINING_END" \
    --test-start "$VALIDATION_START" \
    --test-end "$VALIDATION_END" \
    --optuna \
    --optuna-trials 30 \
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
