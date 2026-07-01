#!/usr/bin/env bash
# TP/SL Exact Sweep (Linux/macOS shell)
# ---------------------------------------------------------------------------
# For each (TP, SL) combination: re-train with that TP/SL as the label,
# re-backtest with the same TP/SL as the strategy floor, collect metrics.
#
# The goal is to MEASURE whether the model has a cost-surviving directional
# edge at ANY barrier width. Read the gross_* columns.
#
# Requirements: prepared full-history Parquet + regimes.json.
# Usage:  chmod +x tp_sl_sweep.sh && ./tp_sl_sweep.sh
# ---------------------------------------------------------------------------

set -euo pipefail

FULL_PARQUET="${FULL_PARQUET:-artifacts/btcusdt_2020_2025.parquet}"
REGIME_FILE="${REGIME_FILE:-regimes.json}"
DOWNLOAD_START="${DOWNLOAD_START:-2020-01-01}"
TRAINING_END="${TRAINING_END:-2024-12-31}"
VALIDATION_START="${VALIDATION_START:-2025-01-01}"
VALIDATION_END="${VALIDATION_END:-2025-06-30}"
BACKTEST_START="${BACKTEST_START:-2025-07-01}"
SWEEP_DIR="${SWEEP_DIR:-artifacts/tp_sl_sweep}"
OPTUNA_TRIALS="${OPTUNA_TRIALS:-15}"

if [[ ! -f "$FULL_PARQUET" ]]; then
    echo "ERROR: $FULL_PARQUET not found. Run run_full_pipeline.sh Phases 1-2 first." >&2
    exit 1
fi
if [[ ! -f "$REGIME_FILE" ]]; then
    echo "ERROR: $REGIME_FILE not found." >&2
    exit 1
fi
mkdir -p "$SWEEP_DIR"

RESULTS_CSV="$SWEEP_DIR/sweep_results.csv"
echo "label,tp_pct,sl_pct,trades,win_rate,gross_total_return,net_total_return,profit_factor,sharpe,max_drawdown,best_strategy" > "$RESULTS_CSV"

# (label tp sl) triples
COMBOS=(
    "tp0.20_sl0.10_2to1 0.002 0.001"
    "tp0.30_sl0.15_2to1 0.003 0.0015"
    "tp0.40_sl0.20_2to1 0.004 0.002"
    "tp0.50_sl0.25_2to1 0.005 0.0025"
    "tp0.30_sl0.10_3to1 0.003 0.001"
    "tp0.60_sl0.20_3to1 0.006 0.002"
)

for combo in "${COMBOS[@]}"; do
    read -r label tp sl <<< "$combo"
    echo ""
    echo "=================================================================="
    echo " Sweep cell: $label  (TP=$tp  SL=$sl)"
    echo "=================================================================="

    cell_dir="$SWEEP_DIR/$label"
    model_dir="$cell_dir/model"
    bt_dir="$cell_dir/backtest"
    mkdir -p "$cell_dir"

    echo "[$label] Training..."
    python -m btcusdt_quant train \
        --input "$FULL_PARQUET" \
        --use-user-regime \
        --user-regime-file "$REGIME_FILE" \
        --training-start "$DOWNLOAD_START" \
        --training-end "$TRAINING_END" \
        --test-start "$VALIDATION_START" \
        --test-end "$VALIDATION_END" \
        --tp-pct "$tp" \
        --sl-pct "$sl" \
        --optuna \
        --optuna-trials "$OPTUNA_TRIALS" \
        --output "$model_dir"

    echo "[$label] Backtesting..."
    python -m btcusdt_quant backtest \
        --input "$FULL_PARQUET" \
        --model-artifact "$model_dir" \
        --user-regime-file "$REGIME_FILE" \
        --backtest-start "$BACKTEST_START" \
        --tp-floor "$tp" \
        --sl-floor "$sl" \
        --fixed-tp-sl \
        --output "$bt_dir"

    summary="$bt_dir/backtest_summary.json"
    if [[ -f "$summary" ]]; then
        python - "$summary" "$label" "$tp" "$sl" "$RESULTS_CSV" <<'PY'
import json, sys
summary, label, tp, sl, csv = sys.argv[1:6]
with open(summary) as f:
    j = json.load(f)
b = j["backtest"]
best = j.get("strategy_comparison", {}).get("best_strategy", "")
row = f'{label},{tp},{sl},{b.get("trade_count")},{b.get("win_rate")},{b.get("gross_total_return")},{b.get("net_total_return")},{b.get("profit_factor")},{b.get("sharpe")},{b.get("max_drawdown")},{best}'
with open(csv, "a") as f:
    f.write(row + "\n")
print(f'[{label}] gross={b.get("gross_total_return")} net={b.get("net_total_return")} trades={b.get("trade_count")} win={b.get("win_rate")}')
PY
    else
        echo "[$label] WARNING: no backtest summary produced" >&2
    fi
done

echo ""
echo "=== Sweep complete ==="
echo "Results: $RESULTS_CSV"
echo ""
echo "How to read this:"
echo "  - gross_total_return ~0 across ALL rows -> fix the MODEL, not TP/SL."
echo "  - some row clearly positive gross -> edge exists at that width."
cat "$RESULTS_CSV"
