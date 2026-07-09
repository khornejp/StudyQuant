#!/usr/bin/env bash
# BTCUSDT User-Regime Pipeline (Linux/macOS shell)
# ---------------------------------------------------------------------------
# Intended flow (same as run_full_pipeline.ps1):
#   1. Download 2020-01-01 ~ 2025-12-31 Binance archive (full 6-year span)
#   2. Combine into one Parquet file
#   3. Train regime-aware models with multi-feature RULE regime bucketing
#      (default REGIME_MODE=rule; no regimes.json needed), training
#      restricted to 2020-2024. Model quality is checked on a chronological
#      holdout split INSIDE training (last 20% of each regime's rows).
#   4. Backtest on 2025-01-01 ~ 2025-12-31 (the full year, out-of-sample)
#
# Requirements:
#   - Python with pyarrow, catboost, numpy, pandas installed
#   - ~16GB RAM
#   - regimes.json only if REGIME_MODE=classifier (rule mode needs none)
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
# No more held-out 2025 H1 "validation" span: regime model quality is now
# checked via a chronological holdout SPLIT OF THE TRAINING DATA itself
# (last 20% of each regime's own rows, done inside training -- see
# "Regime holdout" log lines). That frees up all of 2025 to be a genuine,
# single, out-of-sample backtest window instead of splitting it into a
# held-out half and a backtest half.
BACKTEST_START="${BACKTEST_START:-2025-01-01}"
BACKTEST_END="${BACKTEST_END:-2025-12-31}"
ARTIFACTS_DIR="${ARTIFACTS_DIR:-artifacts}"
# How each regime/side model picks its decision threshold on its own holdout:
#   precision_recall (default) - precision with recall>=0.3 floor, F1 fallback
#   trading_pnl                - optimizes simulated calmar/sharpe/f1 from PnL,
#                                 usually the better fit for a trading model
#                                 since classification balance != profitability
# trading_pnl ranks threshold candidates by cost-aware simulated PnL
# (no-trade below threshold, asymmetric TP/SL, round-trip cost). The old
# precision_recall default drove thresholds down to ~0.32.
THRESHOLD_OBJECTIVE="${THRESHOLD_OBJECTIVE:-trading_pnl}"
# Regime routing mode:
#   rule       (default) - multi-feature rule-based detector
#                          (regime_rules.MultiFeatureRegimeDetector). No learned
#                          classifier and no regimes.json needed: the detector
#                          derives up/down/range from F17 features directly, and
#                          the SAME fitted detector is saved into the model
#                          artifact and reused by backtest/live (no train/serve
#                          skew). This is the current recommended path.
#   classifier          - legacy learned-classifier routing (Phase 2.5 trains a
#                          walk-forward OOF classifier from regimes.json; entry
#                          models bucket by its argmax; backtest routes with the
#                          saved .cbm). Requires regimes.json + catboost.
REGIME_MODE="${REGIME_MODE:-rule}"
# Optional: path to a MultiFeatureRegimeConfig JSON (rule mode only). Defaults to
# the conservative preset (switch_confirm_bars=10, allow_direct_reversal=false,
# ...). Set RULE_REGIME_CONFIG="" to use built-in code defaults.
RULE_REGIME_CONFIG="${RULE_REGIME_CONFIG:-configs/rule_regime.json}"
# Triple-barrier label geometry (also used as FIXED execution barriers in
# Phase 4 so backtest trades the SAME barrier the model was trained on).
# HORIZON is in bars (=minutes for 1m data). Tune together.
HORIZON="${HORIZON:-60}"
LABEL_TP_PCT="${LABEL_TP_PCT:-0.003}"
LABEL_SL_PCT="${LABEL_SL_PCT:-0.0015}"
# Hard lower bound on learned entry thresholds at backtest time (0 = off).
THRESHOLD_FLOOR="${THRESHOLD_FLOOR:-0.45}"
# Cost basis SINGLE SOURCE: per-side fee/slippage fractions. Round-trip
# cost 2*(fee+slippage) is derived and passed to train (threshold objective
# + holdout metrics); per-side values go to backtest execution.
FEE_PER_SIDE="${FEE_PER_SIDE:-0.0002}"            # 0.02%
SLIPPAGE_PER_SIDE="${SLIPPAGE_PER_SIDE:-0.0002}"  # 0.02%
ROUND_TRIP_COST=$(python -c "print(2.0 * (${FEE_PER_SIDE} + ${SLIPPAGE_PER_SIDE}))")
# ==========================================================================

echo "=== BTCUSDT User-Regime Pipeline ==="
echo "Training span    : $DOWNLOAD_START -> $TRAINING_END"
echo "Regime holdout   : last 20% of each regime's own training rows (in-training check)"
echo "Backtest span    : $BACKTEST_START -> $BACKTEST_END (full-year out of sample)"
echo "Regime file      : $REGIME_FILE"
echo "Regime mode      : $REGIME_MODE"
echo ""

if [[ "$REGIME_MODE" == "classifier" && ! -f "$REGIME_FILE" ]]; then
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
# PHASE 1.5: Download the futures metrics archive (open interest, long/short
# ratios, taker buy/sell). Cached on disk so re-training reuses it. These feed
# the F16 derivatives-metrics features. NOTE: live use of these features needs
# the /futures/data/* REST endpoints wired into the live engine (not done yet).
# ----------------------------------------------------------------------------
echo ""
echo "[Phase 1.5] Downloading Binance futures metrics archive ..."

METRICS_DIR="$ARTIFACTS_DIR/metrics"
mkdir -p "$METRICS_DIR"

python -m btcusdt_quant collect-metrics \
    --start "$DOWNLOAD_START" --end "$BACKTEST_END" \
    --output "$METRICS_DIR" \
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
# PHASE 2.5: Train the regime probability classifier (Method B, stage 2)
#
# Leakage-safe (walk-forward out-of-fold) up/range/down probability
# classifier on F17 multi-timeframe features, trained against the
# hand-labeled regimes.json. Writes regime_probabilities.json, which Phase 3
# feeds into --regime-classifier-dir so the entry (long/short) models can use
# F18 soft regime-probability features instead of (or alongside) the hard
# regime bucket routing. See btcusdt_quant/regime_classifier.py for how
# leakage is prevented: no fold's classifier ever sees the label of a row it
# predicts.
# ----------------------------------------------------------------------------
echo ""
REGIME_CLASSIFIER_DIR="$ARTIFACTS_DIR/regime_classifier"
if [[ "$REGIME_MODE" == "classifier" ]]; then
    echo "[Phase 2.5] Training regime probability classifier (leakage-safe OOF) ..."
    python -m btcusdt_quant train-regime-classifier \
        --input "$FULL_PARQUET" \
        --regime-file "$REGIME_FILE" \
        --output "$REGIME_CLASSIFIER_DIR"
else
    echo "[Phase 2.5] Skipped (REGIME_MODE=$REGIME_MODE: multi-feature rule detector needs no learned classifier)."
fi

# ----------------------------------------------------------------------------
# PHASE 3: Train on 2020 -> 2024
# ----------------------------------------------------------------------------
echo ""
echo "[Phase 3] Training regime-aware ensemble..."
echo "  Features are computed once over the full 2020-2025 series."
echo "  Training rows: $DOWNLOAD_START -> $TRAINING_END"
echo "  Regime labels from: $REGIME_FILE"
echo ""
echo "  Per-regime Optuna tuning (--optuna) IS applied: each long/short"
echo "  CatBoost model gets its own Optuna study (100 trials) over 8"
echo "  hyperparameters (iterations, learning_rate, depth, l2_leaf_reg,"
echo "  random_strength, bagging_temperature, min_data_in_leaf,"
echo "  border_count) on a chronological 80/20 holdout, with eval_set-based"
echo "  early stopping (use_best_model=True). The FINAL model per regime is"
echo "  then also evaluated on that same regime's own chronological holdout"
echo "  tail (never mixed with other regimes' rows) -- see 'Regime holdout'"
echo "  log lines below. Each regime/side model also picks its decision"
echo "  threshold on that same holdout via --threshold-objective"
echo "  ($THRESHOLD_OBJECTIVE) instead of a fixed 0.5 cutoff -- see 'threshold='"
echo "  in the holdout log lines. Other flags (--ensemble, --cv-mode,"
echo "  --feature-selection) are NOT applied on this path."
echo ""

MODEL_DIR="$ARTIFACTS_DIR/regime_stacking_model"

if [[ "$REGIME_MODE" == "classifier" ]]; then
    REGIME_TRAIN_FLAGS=(--regime-classifier-dir "$REGIME_CLASSIFIER_DIR")
    echo "[Phase 3] Training with LEARNED-CLASSIFIER regime bucketing ..."
else
    REGIME_TRAIN_FLAGS=(--multi-feature-regime)
    if [[ -n "$RULE_REGIME_CONFIG" && -f "$RULE_REGIME_CONFIG" ]]; then
        REGIME_TRAIN_FLAGS+=(--rule-regime-config "$RULE_REGIME_CONFIG")
        echo "[Phase 3] Training with MULTI-FEATURE RULE regime bucketing (config: $RULE_REGIME_CONFIG) ..."
    else
        echo "[Phase 3] Training with MULTI-FEATURE RULE regime bucketing (default config) ..."
    fi
fi
python -m btcusdt_quant train \
    --input "$FULL_PARQUET" \
    --regime-aware \
    --training-start "$DOWNLOAD_START" \
    --training-end "$TRAINING_END" \
    --metrics-dir "$METRICS_DIR" \
    --threshold-objective "$THRESHOLD_OBJECTIVE" \
    --round-trip-cost "$ROUND_TRIP_COST" \
    --horizon "$HORIZON" \
    --tp-pct "$LABEL_TP_PCT" \
    --sl-pct "$LABEL_SL_PCT" \
    "${REGIME_TRAIN_FLAGS[@]}" \
    --optuna \
    --optuna-trials 100 \
    --output "$MODEL_DIR"

echo ""
echo "  Training complete."
echo "  Model: $MODEL_DIR"

# ----------------------------------------------------------------------------
# PHASE 4: Backtest on 2025 (out-of-sample)
#
# --regime-classifier-dir uses the SAME saved classifier (Phase 2.5's
# regime_classifier_model.cbm) that Phase 3 used to assign each training
# row's regime bucket -- required for consistency: if backtest routed with a
# DIFFERENT signal than training used to bucket rows, the up/down/range
# models would be invoked on regimes they never trained on (train/serve
# skew). This is fully causal at inference time (F17 multi-timeframe
# features only), exactly as a live deployment must be -- the old
# --user-regime-file hard-routed backtest, which depended on hindsight
# regime labels with no live counterpart, was removed.
# ----------------------------------------------------------------------------
echo ""

BACKTEST_DIR="$ARTIFACTS_DIR/backtest_results"

if [[ "$REGIME_MODE" == "classifier" ]]; then
    REGIME_BT_FLAGS=(--regime-classifier-dir "$REGIME_CLASSIFIER_DIR")
    echo "[Phase 4] Backtest with learned-classifier routing (same model as Phase 3) ..."
else
    # Rule mode: the fitted multi-feature detector is saved inside the model
    # artifact (regime_run_summary.json) and auto-loaded here, so routing
    # matches training bucketing with no extra flag.
    REGIME_BT_FLAGS=()
    echo "[Phase 4] Backtest with multi-feature rule routing (auto-loaded from artifact) ..."
fi
python -m btcusdt_quant backtest \
    --input "$FULL_PARQUET" \
    --model-artifact "$MODEL_DIR" \
    ${REGIME_BT_FLAGS[@]+"${REGIME_BT_FLAGS[@]}"} \
    --exec-tp-pct "$LABEL_TP_PCT" \
    --exec-sl-pct "$LABEL_SL_PCT" \
    --metrics-dir "$METRICS_DIR" \
    --threshold-floor "$THRESHOLD_FLOOR" \
    --fee-rate-per-side "$FEE_PER_SIDE" \
    --slippage-rate-per-side "$SLIPPAGE_PER_SIDE" \
    --horizon "$HORIZON" \
    --backtest-start "$BACKTEST_START" \
    --backtest-end "$BACKTEST_END" \
    --output "$BACKTEST_DIR"

echo ""
echo "=== Pipeline Complete ==="
echo ""
echo "Outputs:"
echo "  Combined data : $FULL_PARQUET"
echo "  Model         : $MODEL_DIR"
echo "  Backtest      : $BACKTEST_DIR"
echo ""
python3 - "$BACKTEST_DIR/backtest_summary.json" <<'PY'
import json, sys, os
path = sys.argv[1]
if os.path.exists(path):
    with open(path) as f:
        b = json.load(f)["backtest"]
    print(f"gross={b.get('gross_total_return',0):+.4%} net={b.get('net_total_return',0):+.4%} "
          f"trades={b.get('trade_count',0)} win={b.get('win_rate',0):.1%}")
    cov = b.get("regime_coverage")
    if cov:
        print(f"regime coverage: matched={cov.get('matched',0)} "
              f"default_fallback={cov.get('default_fallback',0)} no_model={cov.get('no_model',0)}")
else:
    print("(backtest summary not found)")
PY
