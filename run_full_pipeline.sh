#!/usr/bin/env bash
# BTCUSDT User-Regime Pipeline (Linux/macOS shell)
# ---------------------------------------------------------------------------
# Intended flow (kept in sync with run_full_pipeline.ps1):
#   1.   Download 2020-01-01 ~ 2025-12-31 Binance archive (full 6-year span)
#   2.   Combine into one Parquet file
#   2.3  Data diagnostics: feature IC with fold stability + look-ahead-leakage
#        heuristics, and the OU half-life of range regimes vs the fixed 20-bar
#        mean-reversion window. Informational: a failure here does not stop
#        the run (the `|| true` guards below opt out of `set -e`).
#   3.   Train regime-aware models with multi-feature RULE regime bucketing
#        (default REGIME_MODE=rule; no regimes.json needed), training
#        restricted to 2020-2024. Model quality is checked on a chronological
#        holdout split INSIDE training (last 20% of each regime's rows).
#   3.5  Multi-horizon ensemble pilot (one entry model per label horizon,
#        blended by validation accuracy). Regime-aware, mirroring Phase 3's
#        bucketing and direction policy (up->long, down->short, range->both)
#        with per-side long_success/short_success targets, so Phase 4.5 is a
#        regime-aligned challenger to Phase 4.
#   4.   Backtest on 2025-01-01 ~ 2025-12-31 (the full year, out-of-sample),
#        with fractional-Kelly sizing (KELLY_SIZING=1 by default).
#   4.5  Backtest the multi-horizon pilot on the same window/costs/kelly.
#
# `set -euo pipefail` already aborts the pipeline on any nonzero exit, so the
# artifact-producing phases are gated implicitly (the PowerShell twin needs
# explicit $LASTEXITCODE checks because native exits do not throw there).
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
# The barriers must clear the round-trip cost by a wide margin or the reward:risk
# the labels advertise is not the one the account earns. At TP 0.30%/SL 0.15% the
# 0.08% round trip turns a nominal 2.0:1 into a net 0.96:1 (+0.22% vs -0.23%) and
# lifts break-even win rate from 33.3% to 51.1% -- unreachable, so every run lost.
# At 1.00%/0.50% the net is +0.92% vs -0.58% (1.59:1) and break-even is 38.7%.
HORIZON="${HORIZON:-60}"
LABEL_TP_PCT="${LABEL_TP_PCT:-0.010}"
LABEL_SL_PCT="${LABEL_SL_PCT:-0.005}"
# Hard lower bound on learned entry thresholds at backtest time (0 = off).
# Off by default: threshold selection already maximizes trading PnL net of
# ROUND_TRIP_COST, so a floor above the learned value only vetoes it. The 0.45
# floor silently disabled the range regime (learned 0.348/0.358), which is ~91%
# of 2025 bars -- the backtest traded 9% of the data and reported it as a result.
THRESHOLD_FLOOR="${THRESHOLD_FLOOR:-0.0}"
# Cost basis SINGLE SOURCE: per-side fee/slippage fractions. Round-trip
# cost 2*(fee+slippage) is derived and passed to train (threshold objective
# + holdout metrics); per-side values go to backtest execution.
FEE_PER_SIDE="${FEE_PER_SIDE:-0.0002}"            # 0.02%
SLIPPAGE_PER_SIDE="${SLIPPAGE_PER_SIDE:-0.0002}"  # 0.02%
ROUND_TRIP_COST=$(python -c "print(2.0 * (${FEE_PER_SIDE} + ${SLIPPAGE_PER_SIDE}))")
# Fractional-Kelly position sizing for the backtests (Phase 4 / 4.5). Half-Kelly
# (0.5) trades ~18.5% of growth for ~43% smaller max drawdown. The backtest's
# fixed position_size becomes the CAP on the per-trade fraction; entries whose
# cost-adjusted Kelly edge is non-positive are skipped. Set KELLY_SIZING=0 off.
KELLY_SIZING="${KELLY_SIZING:-1}"
KELLY_MULTIPLIER="${KELLY_MULTIPLIER:-0.5}"
KELLY_LOOKBACK_BARS="${KELLY_LOOKBACK_BARS:-1440}"   # 1 day of 1m bars
# Phase 2.3 data diagnostics (IC/leakage report + range half-life). Adds a few
# minutes on the full 6-year parquet; set RUN_DIAGNOSTICS=0 to skip.
RUN_DIAGNOSTICS="${RUN_DIAGNOSTICS:-1}"
# Phase 3.5/4.5 multi-horizon ensemble pilot. Regime-aware: mirrors Phase 3's
# bucketing and direction policy, so it costs ~1 ensemble per regime/side.
# Set MULTI_HORIZON_PILOT=0 to skip.
MULTI_HORIZON_PILOT="${MULTI_HORIZON_PILOT:-1}"
MH_HORIZONS="${MH_HORIZONS:-30,60,90}"
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
# PHASE 2.3: Data diagnostics (informational; `|| true` opts out of `set -e`)
#   - ic_diagnostic.py: per-feature Spearman IC with chronological fold
#     mean/std (IC drift) plus look-ahead-leakage heuristics. Leak flags are
#     triage only -- confirm with a truncation-invariance test before acting.
#   - verify_range_halflife.py: OU half-life of range regimes. Fitted to the
#     drift-removed log z-score, not raw close: BTC's trend and changing
#     volatility make a raw-price OU fit measure the trend, not the reversion.
# ----------------------------------------------------------------------------
if [[ "$RUN_DIAGNOSTICS" != "0" ]]; then
    echo ""
    echo "[Phase 2.3] Data diagnostics (feature IC / leakage / range half-life) ..."

    IC_REPORT_DIR="$ARTIFACTS_DIR/ic_report"
    IC_ARGS=(--input "$FULL_PARQUET" --metrics-dir "$METRICS_DIR" --output "$IC_REPORT_DIR")
    if [[ -f "$REGIME_FILE" ]]; then
        IC_ARGS+=(--regime-file "$REGIME_FILE")
    fi
    python ic_diagnostic.py "${IC_ARGS[@]}" || echo "  WARNING: ic_diagnostic failed; continuing (informational phase)."
    echo "  IC/leakage report: $IC_REPORT_DIR/ic_report.csv"

    HL_ARGS=(--input "$FULL_PARQUET" --series log_zscore)
    if [[ -f "$REGIME_FILE" ]]; then
        HL_ARGS+=(--regime-file "$REGIME_FILE")
    else
        echo "  ($REGIME_FILE not found: half-life runs without per-regime breakdown)"
    fi
    python verify_range_halflife.py "${HL_ARGS[@]}" || echo "  WARNING: verify_range_halflife failed; continuing (informational phase)."
else
    echo ""
    echo "[Phase 2.3] Skipped (RUN_DIAGNOSTICS=$RUN_DIAGNOSTICS)."
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
# PHASE 3.5: Multi-horizon ensemble pilot (challenger to the regime model)
#
# One entry model per label horizon on the SAME features, blended by
# validation-accuracy weights. Trained regime-aware, sharing Phase 3's rule
# bucketing, direction policy, per-side triple-barrier targets, threshold
# horizon, and (via the final refit) the full per-regime training set.
#
# This is a CHALLENGER comparison, not a clean horizon-blend A/B: Phase 3 tunes
# with Optuna (100 trials) while the horizon models use default parameters, so
# a Phase 4.5 win or loss reflects the blend AND the tuning difference.
#
# A short model must learn short_success -- 1-P(long_success) is not a short
# probability (a long that times out is not a short win).
# ----------------------------------------------------------------------------
echo ""
MH_MODEL_DIR="$ARTIFACTS_DIR/multi_horizon_model"

if [[ "$MULTI_HORIZON_PILOT" != "0" ]]; then
    echo "[Phase 3.5] Training multi-horizon ensemble pilot (horizons: $MH_HORIZONS) ..."
    echo "  Regime-aware: one horizon-blended ensemble per regime AND side (up->long,"
    echo "  down->short, range->both), each on its own long_success/short_success target,"
    echo "  with a per-regime/side holdout threshold. Same artifact layout and direction"
    echo "  policy as Phase 3. Phase 4.5 is a regime-aligned multi-horizon challenger:"
    echo "  it shares execution and routing with Phase 4, but still differs in horizon"
    echo "  blending, base-model tuning (Optuna vs defaults) and probability calibration."
    # --threshold-horizon "$HORIZON": pick each regime/side cutoff against the
    # SAME time barrier Phase 4.5 executes on. Without it the thresholds would
    # be scored on max(horizons)=90-bar labels while the backtest times out at
    # $HORIZON, adding a second axis of difference vs Phase 4.
    MH_TRAIN_FLAGS=(--regime-aware --threshold-horizon "$HORIZON" --threshold-objective "$THRESHOLD_OBJECTIVE" --round-trip-cost "$ROUND_TRIP_COST")
    if [[ -n "$RULE_REGIME_CONFIG" && -f "$RULE_REGIME_CONFIG" ]]; then
        MH_TRAIN_FLAGS+=(--rule-regime-config "$RULE_REGIME_CONFIG")
    fi
    # NON-FATAL (|| ...): the multi-horizon pilot is a challenger, not the
    # deliverable. Its regime-aware training fails closed (exit 1) on a
    # one-sided data quirk -- correct for the pilot, but under `set -e` it would
    # abort the primary Phase 4 backtest that follows. On failure, skip Phase
    # 4.5 rather than shipping/comparing a partial pilot artifact.
    if python -m btcusdt_quant train-multi-horizon \
        --input "$FULL_PARQUET" \
        --training-start "$DOWNLOAD_START" \
        --training-end "$TRAINING_END" \
        --horizons "$MH_HORIZONS" \
        --tp-pct "$LABEL_TP_PCT" \
        --sl-pct "$LABEL_SL_PCT" \
        --weighting validation \
        --metrics-dir "$METRICS_DIR" \
        "${MH_TRAIN_FLAGS[@]}" \
        --output "$MH_MODEL_DIR"; then
        echo "  Multi-horizon model: $MH_MODEL_DIR"
    else
        echo "  WARNING: Phase 3.5 (multi-horizon pilot) failed; skipping Phase 4.5. Phase 4 continues."
        MULTI_HORIZON_PILOT=0
    fi
else
    echo "[Phase 3.5] Skipped (MULTI_HORIZON_PILOT=$MULTI_HORIZON_PILOT)."
fi

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
# Kelly sizing flags shared by Phase 4 and 4.5. The main backtest is
# Kelly-sized; the strategy_comparison block inside the summary stays
# fixed-size (marked "sizing": "fixed_position_size") -- not comparable.
KELLY_FLAGS=()
if [[ "$KELLY_SIZING" != "0" ]]; then
    KELLY_FLAGS=(--kelly-sizing --kelly-multiplier "$KELLY_MULTIPLIER" --kelly-lookback-bars "$KELLY_LOOKBACK_BARS")
    echo "  Kelly sizing ON: Half-Kelly=$KELLY_MULTIPLIER, variance lookback=$KELLY_LOOKBACK_BARS bars, holding=$HORIZON bars, cap=position_size"
fi
python -m btcusdt_quant backtest \
    --input "$FULL_PARQUET" \
    --model-artifact "$MODEL_DIR" \
    ${REGIME_BT_FLAGS[@]+"${REGIME_BT_FLAGS[@]}"} \
    ${KELLY_FLAGS[@]+"${KELLY_FLAGS[@]}"} \
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

# ----------------------------------------------------------------------------
# PHASE 4.5: Backtest the multi-horizon pilot on the same window/costs
# ----------------------------------------------------------------------------
MH_BACKTEST_DIR="$ARTIFACTS_DIR/backtest_results_multi_horizon"

if [[ "$MULTI_HORIZON_PILOT" != "0" ]]; then
    echo ""
    echo "[Phase 4.5] Backtest multi-horizon pilot (same window, costs and kelly settings) ..."
    # Directory artifact (not model.json): regime_run_summary.json rides the
    # fitted rule detector, so routing and the direction policy match Phase 4.
    python -m btcusdt_quant backtest \
        --input "$FULL_PARQUET" \
        --model-artifact "$MH_MODEL_DIR" \
        ${KELLY_FLAGS[@]+"${KELLY_FLAGS[@]}"} \
        --exec-tp-pct "$LABEL_TP_PCT" \
        --exec-sl-pct "$LABEL_SL_PCT" \
        --metrics-dir "$METRICS_DIR" \
        --threshold-floor "$THRESHOLD_FLOOR" \
        --fee-rate-per-side "$FEE_PER_SIDE" \
        --slippage-rate-per-side "$SLIPPAGE_PER_SIDE" \
        --horizon "$HORIZON" \
        --backtest-start "$BACKTEST_START" \
        --backtest-end "$BACKTEST_END" \
        --output "$MH_BACKTEST_DIR"
fi

echo ""
echo "=== Pipeline Complete ==="
echo ""
echo "Outputs:"
echo "  Combined data : $FULL_PARQUET"
echo "  Model         : $MODEL_DIR"
echo "  Backtest      : $BACKTEST_DIR"
if [[ "$MULTI_HORIZON_PILOT" != "0" ]]; then
    echo "  MH model      : $MH_MODEL_DIR"
    echo "  MH backtest   : $MH_BACKTEST_DIR"
fi
echo ""
# `python`, not `python3`: every other phase in this script invokes `python`,
# and on a venv/conda host where only `python` resolves, a `python3` here would
# fail the whole run at the last step after every artifact was already written.
python - "$BACKTEST_DIR/backtest_summary.json" "$MH_BACKTEST_DIR/backtest_summary.json" <<'PY'
import json, sys, os

def num(value, spec):
    """Format a metric that may be null.

    A risk metric is null when it is undefined -- fewer trades than
    risk_metrics_min_trades, or zero return dispersion. Printing 0.000 there
    would read as "flat performance" instead of "no answer", and formatting
    None with a numeric spec is a TypeError.
    """
    if value is None:
        return "n/a"
    return format(value, spec)

def show(label, path):
    if not os.path.exists(path):
        print(f"  {label}: (backtest summary not found)")
        return
    with open(path) as f:
        b = json.load(f)["backtest"]
    print(f"  {label}: gross={num(b.get('gross_total_return'),'+.4%')} net={num(b.get('net_total_return'),'+.4%')} "
          f"trades={b.get('trade_count',0)} win={num(b.get('win_rate'),'.1%')}")
    # Gross vs net Sharpe side by side: the gap is the cost drag. A strategy
    # whose Sharpe is only positive gross must not ship.
    print(f"    sharpe: net={num(b.get('net_sharpe'),'.3f')} gross={num(b.get('gross_sharpe'),'.3f')} "
          f"cost_impact={num(b.get('cost_impact_sharpe'),'.3f')}")
    k = b.get("kelly_sizing") or {}
    if k.get("enabled"):
        print(f"    kelly: avg_frac={k.get('avg_fraction',0):.4f} min={k.get('min_fraction',0):.4f} "
              f"max={k.get('max_fraction',0):.4f} (cap={k.get('cap')}) "
              f"skipped_no_edge={k.get('entries_skipped_no_edge',0)}")
        shorts = k.get("shorts_skipped_no_short_model", 0)
        if shorts:
            print(f"    kelly: {shorts} SELL signals refused (no short-success model) -- this run was LONG-ONLY")
    cov = b.get("regime_coverage")
    if cov:
        print(f"    regime coverage: matched={cov.get('matched',0)} "
              f"default_fallback={cov.get('default_fallback',0)} no_model={cov.get('no_model',0)}")

show("regime model ", sys.argv[1])
if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
    show("multi-horizon", sys.argv[2])
    print("  (multi-horizon pilot shares Phase 4's regimes/sides -- judge it on net sharpe/MDD, not raw return)")
PY

# Regime x side x month breakdown -- the axes that actually explain a
# difference between the two models. Informational; never gates the run.
if [[ "$MULTI_HORIZON_PILOT" != "0" && -f "$BACKTEST_DIR/backtest_summary.json" && -f "$MH_BACKTEST_DIR/backtest_summary.json" ]]; then
    echo ""
    python compare_backtests.py \
        "$BACKTEST_DIR/backtest_summary.json" \
        "$MH_BACKTEST_DIR/backtest_summary.json" \
        || echo "  WARNING: compare_backtests failed; continuing (informational)."
fi
