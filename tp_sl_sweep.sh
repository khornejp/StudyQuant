#!/usr/bin/env bash
# TP/SL Exact Sweep (Linux/macOS shell)
# ---------------------------------------------------------------------------
# For each (TP, SL) combination: re-train with that TP/SL as the label
# (SAME structure as run_full_pipeline.sh: multi-feature RULE regime
# bucketing, trading_pnl threshold objective, explicit horizon), then
# re-backtest EXECUTING exactly those label barriers
# (--exec-tp-pct/--exec-sl-pct) over a pinned 2025 window, and collect
# gross/net metrics.
#
# The goal is to MEASURE whether the model has a cost-surviving directional
# edge at ANY barrier width. Read the gross_* columns.
#
# Regimes are routed with the multi-feature RULE detector fitted at training
# time and embedded in each cell's model artifact (auto-loaded by the
# backtest) -- the same path run_full_pipeline.sh uses. The detector's
# regime assignment doesn't depend on TP/SL, so cell-to-cell differences
# here still isolate only the TP/SL change.
#
# Requirements: prepared full-history Parquet (run_full_pipeline.sh
# Phases 1-2). regimes.json is NOT required in rule mode.
# Usage:  chmod +x tp_sl_sweep.sh && ./tp_sl_sweep.sh
# ---------------------------------------------------------------------------

set -euo pipefail

FULL_PARQUET="${FULL_PARQUET:-artifacts/btcusdt_2020_2025.parquet}"
DOWNLOAD_START="${DOWNLOAD_START:-2020-01-01}"
TRAINING_END="${TRAINING_END:-2024-12-31}"
BACKTEST_START="${BACKTEST_START:-2025-01-01}"
BACKTEST_END="${BACKTEST_END:-2025-12-31}"   # date-only = inclusive of the whole day
SWEEP_DIR="${SWEEP_DIR:-artifacts/tp_sl_sweep}"
OPTUNA_TRIALS="${OPTUNA_TRIALS:-15}"
HORIZON="${HORIZON:-60}"                     # bars; SAME value to train AND backtest
THRESHOLD_FLOOR="${THRESHOLD_FLOOR:-0.45}"
RULE_REGIME_CONFIG="${RULE_REGIME_CONFIG:-configs/rule_regime.json}"  # "" -> defaults
FEE_PER_SIDE="${FEE_PER_SIDE:-0.0002}"            # 0.02%
SLIPPAGE_PER_SIDE="${SLIPPAGE_PER_SIDE:-0.0002}"  # 0.02%
ROUND_TRIP_COST=$(python -c "print(2.0 * (${FEE_PER_SIDE} + ${SLIPPAGE_PER_SIDE}))")  # -> train
# Same F16 derivatives-metrics archive the main pipeline collects. When the
# directory has zips, it goes to BOTH train and backtest of every cell
# (training with metrics but backtesting without is a train/serve skew).
METRICS_DIR="${METRICS_DIR:-artifacts/metrics}"

if [[ ! -f "$FULL_PARQUET" ]]; then
    echo "ERROR: $FULL_PARQUET not found. Run run_full_pipeline.sh Phases 1-2 first." >&2
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

    # Mirrors run_full_pipeline.sh Phase 3: multi-feature RULE regime
    # bucketing + trading_pnl objective + explicit horizon, so every cell
    # shares the pipeline's structure except TP/SL.
    regime_flags=(--multi-feature-regime)
    if [[ -n "$RULE_REGIME_CONFIG" && -f "$RULE_REGIME_CONFIG" ]]; then
        regime_flags+=(--rule-regime-config "$RULE_REGIME_CONFIG")
    fi
    metrics_flags=()
    if [[ -n "$METRICS_DIR" && -d "$METRICS_DIR" ]] && compgen -G "$METRICS_DIR/*.zip" > /dev/null; then
        metrics_flags=(--metrics-dir "$METRICS_DIR")
    fi
    echo "[$label] Training (horizon=$HORIZON)..."
    python -m btcusdt_quant train \
        --input "$FULL_PARQUET" \
        --regime-aware \
        "${regime_flags[@]}" \
        ${metrics_flags[@]+"${metrics_flags[@]}"} \
        --threshold-objective trading_pnl \
        --round-trip-cost "$ROUND_TRIP_COST" \
        --horizon "$HORIZON" \
        --training-start "$DOWNLOAD_START" \
        --training-end "$TRAINING_END" \
        --tp-pct "$tp" \
        --sl-pct "$sl" \
        --optuna \
        --optuna-trials "$OPTUNA_TRIALS" \
        --output "$model_dir"

    # Rule routing auto-loads from the model artifact (NOT --auto-regime,
    # which would route with the legacy slope-only detector -- a skew vs the
    # rule buckets the models trained on). --exec-tp/sl-pct executes exactly
    # the label barriers; --horizon matches the label timeout.
    echo "[$label] Backtesting (exec barriers, horizon=$HORIZON)..."
    python -m btcusdt_quant backtest \
        --input "$FULL_PARQUET" \
        --model-artifact "$model_dir" \
        --exec-tp-pct "$tp" \
        --exec-sl-pct "$sl" \
        ${metrics_flags[@]+"${metrics_flags[@]}"} \
        --fee-rate-per-side "$FEE_PER_SIDE" \
        --slippage-rate-per-side "$SLIPPAGE_PER_SIDE" \
        --horizon "$HORIZON" \
        --threshold-floor "$THRESHOLD_FLOOR" \
        --backtest-start "$BACKTEST_START" \
        --backtest-end "$BACKTEST_END" \
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
