# BTCUSDT User-Regime Pipeline (Windows PowerShell)
# ---------------------------------------------------------------------------
# Intended flow:
#   1. Download 2020-01-01 ~ 2025-12-31 Binance archive (full 6-year span)
#   2. Combine into one Parquet file
#   3. Train regime-aware models with multi-feature RULE regime bucketing
#      (default $RegimeMode="rule"; regimes.json only needed for the legacy
#      "classifier" mode), training data restricted to 2020-2024.
#      Model quality is checked via a chronological holdout SPLIT OF THE
#      TRAINING DATA ITSELF (last 20% of each regime's own rows), not a
#      separate held-out calendar span -- see "Regime holdout" log lines.
#   4. Backtest the trained models on the FULL 2025 year (out-of-sample,
#      never seen during training)
#
# Requirements:
#   - Python with pyarrow, catboost, numpy, pandas installed
#   - ~16GB RAM (5 years of 1m candles ~ 2.6M rows; features ~3GB in memory)
#   - regimes.json only if $RegimeMode="classifier" (rule mode needs none)
#   - Network access to data.binance.vision for archive downloads
#
# Usage:
#   # Review the configuration variables below (rule mode needs no
#   # regimes.json; set $RegimeMode="classifier" to use one), then:
#   powershell -ExecutionPolicy Bypass -File run_full_pipeline.ps1
# ---------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

# ====== Configuration =====================================================
$RegimeFile      = "regimes.json"           # only used when $RegimeMode="classifier"
$DownloadStart   = "2020-01-01"             # earliest training data
$TrainingEnd     = "2024-12-31"             # last day used for model fitting
$BacktestStart   = "2025-01-01"             # full-year out-of-sample backtest
$BacktestEnd     = "2025-12-31"
$ArtifactsDir    = "artifacts"
# How each regime/side model picks its decision threshold on its own holdout:
#   precision_recall (default) - precision with recall>=0.3 floor, F1 fallback
#   trading_pnl                - optimizes simulated calmar/sharpe/f1 from PnL,
#                                 usually the better fit for a trading model
#                                 since classification balance != profitability
# Threshold objective for per-side holdout threshold selection.
# "trading_pnl" ranks candidates by cost-aware simulated PnL (no-trade below
# threshold, asymmetric TP/SL, round-trip cost) -- the fixed _trading_pnl.
# The old "precision_recall" default drove thresholds down to ~0.32 and
# flooded the backtest with sub-cost entries.
$ThresholdObjective = "trading_pnl"
# Regime routing mode:
#   "rule"       (default) - multi-feature rule-based detector; no learned
#                            classifier and no regimes.json needed. The fitted
#                            detector is saved into the model artifact and
#                            reused by backtest/live (no train/serve skew).
#   "classifier"           - legacy learned-classifier routing (Phase 2.5 +
#                            --regime-classifier-dir). Requires regimes.json.
if (-not $RegimeMode) { $RegimeMode = "rule" }
# Optional: path to a MultiFeatureRegimeConfig JSON (rule mode only). Defaults to
# the conservative 1m-scalping preset (switch_confirm_bars=10,
# allow_direct_reversal=false, ...). Set to "" to use built-in code defaults.
if (-not $RuleRegimeConfig) { $RuleRegimeConfig = "configs/rule_regime.json" }
# Triple-barrier label geometry (also used as the FIXED execution barriers in
# Phase 4 so the backtest trades the SAME barrier the model was trained on).
# Timeout/horizon is in bars (=minutes for 1m data). Tune these together to
# reduce the TIMEOUT rate and align cost vs reward.
if (-not $Horizon)    { $Horizon    = 60 }
if (-not $LabelTpPct) { $LabelTpPct = "0.003" }   # 0.30%
if (-not $LabelSlPct) { $LabelSlPct = "0.0015" }  # 0.15%
# Hard lower bound on learned entry thresholds at backtest time (0 = off).
if (-not $ThresholdFloor) { $ThresholdFloor = "0.45" }
# Cost basis SINGLE SOURCE: per-side fee/slippage fractions. The round-trip
# cost 2*(fee+slippage) is derived below and passed to train (threshold
# objective + holdout metrics) while the per-side values go to backtest
# execution -- so threshold selection and execution always share one basis.
if (-not $FeePerSide)      { $FeePerSide      = "0.0002" }  # 0.02%
if (-not $SlippagePerSide) { $SlippagePerSide = "0.0002" }  # 0.02%
$RoundTripCost = [string](2.0 * ([double]$FeePerSide + [double]$SlippagePerSide))
# ==========================================================================

Write-Host "=== BTCUSDT User-Regime Pipeline ===" -ForegroundColor Cyan
Write-Host "Training span    : $DownloadStart -> $TrainingEnd"
Write-Host "Regime holdout   : last 20% of each regime's own training rows (in-training check)"
Write-Host "Backtest span    : $BacktestStart -> $BacktestEnd (full-year out of sample)"
Write-Host "Regime file      : $RegimeFile"
Write-Host "Regime mode      : $RegimeMode"
Write-Host ""

# Validate regime file exists before doing anything expensive
if (($RegimeMode -eq "classifier") -and (-not (Test-Path $RegimeFile))) {
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
# PHASE 1.5: Download the futures metrics archive (open interest, long/short
# ratios, taker buy/sell). Cached on disk so re-training reuses it. Feeds the
# F16 derivatives-metrics features. NOTE: live use needs the /futures/data/*
# REST endpoints wired into the live engine (not done yet).
# ============================================================================

Write-Host ""
Write-Host "[Phase 1.5] Downloading Binance futures metrics archive ..." -ForegroundColor Yellow

$MetricsDir = Join-Path $ArtifactsDir "metrics"
if (-not (Test-Path $MetricsDir)) {
    New-Item -ItemType Directory -Path $MetricsDir | Out-Null
}

python -m btcusdt_quant collect-metrics `
    --start $DownloadStart --end $BacktestEnd `
    --output $MetricsDir `
    --allow-public-network

# ============================================================================
# PHASE 2: Combine daily CSVs into a single Parquet
# ============================================================================

Write-Host ""
Write-Host "[Phase 2] Combining daily archive files into a single Parquet..." -ForegroundColor Yellow

$FullParquet = Join-Path $ArtifactsDir "btcusdt_2020_2025.parquet"

if (-not (Test-Path $FullParquet)) {
    # Reuse dataset.py's own archive parser (handles header/no-header
    # auto-detection, OHLCV validation, duplicate open_time dedup) instead of
    # re-implementing CSV parsing here. This guarantees the exact same
    # parsing rules used everywhere else in the codebase (training, backtest,
    # tests) are applied to the data that feeds the pipeline.
    python -c @"
import sys
from pathlib import Path
from btcusdt_quant import dataset

archive_dir = Path(r'$ArchiveDir')
out_path    = Path(r'$FullParquet')

print('loading archive candles (this auto-detects header/no-header CSVs, '
      'validates OHLCV, and de-duplicates by open_time)...')
candles = dataset.load_archive_candles(archive_dir)
print(f'  loaded {len(candles):,} raw candles')

print('writing Parquet...')
dataset.write_candles_parquet(out_path, candles)
print(f'  -> wrote {len(candles):,} rows to {out_path}')
"@
} else {
    Write-Host "  (using cached $FullParquet)"
}

# ============================================================================
# PHASE 2.5: Train the regime probability classifier (Method B, stage 2)
#
# Leakage-safe (walk-forward out-of-fold) up/range/down probability
# classifier on F17 multi-timeframe features, trained against the
# hand-labeled regimes.json. Writes regime_probabilities.json, which Phase 3
# feeds into --regime-classifier-dir so the entry (long/short) models can use
# F18 soft regime-probability features. See btcusdt_quant/regime_classifier.py
# for how leakage is prevented: no fold's classifier ever sees the label of a
# row it predicts.
# ============================================================================

Write-Host ""
$RegimeClassifierDir = Join-Path $ArtifactsDir "regime_classifier"

if ($RegimeMode -eq "classifier") {
    Write-Host "[Phase 2.5] Training regime probability classifier (leakage-safe OOF) ..." -ForegroundColor Yellow
    python -m btcusdt_quant train-regime-classifier `
        --input $FullParquet `
        --regime-file $RegimeFile `
        --output $RegimeClassifierDir
} else {
    Write-Host "[Phase 2.5] Skipped (RegimeMode=${RegimeMode}: multi-feature rule detector needs no learned classifier)." -ForegroundColor DarkYellow
}

# ============================================================================
# PHASE 3: Train regime-aware models on 2020 -> 2024 (real-time directional
# detection -- the old --use-user-regime hand-labeled path was removed: it
# depended on regimes.json, which requires knowing the regime in hindsight
# and therefore can never be reproduced live. regimes.json remains useful as
# GROUND-TRUTH LABELS for Phase 2.5's regime probability classifier (which
# IS fully causal at inference time), just not for hard-routing entry models.
# ============================================================================

Write-Host ""
Write-Host "[Phase 3] Training regime-aware ensemble..." -ForegroundColor Yellow
Write-Host "  Features are computed once over the full 2020-2025 series." -ForegroundColor Gray
Write-Host "  Training rows are restricted to $DownloadStart -> $TrainingEnd via --training-end." -ForegroundColor Gray
if ($RegimeMode -eq "classifier") {
    Write-Host "  Regimes are detected by the learned classifier (Phase 2.5 .cbm)." -ForegroundColor Gray
} else {
    Write-Host "  Regimes are detected by MultiFeatureRegimeDetector (rule-based, 1h/4h/24h)." -ForegroundColor Gray
}
Write-Host ""
Write-Host "  Per-regime Optuna tuning (--optuna) IS applied: each long/short" -ForegroundColor DarkYellow
Write-Host "  CatBoost model gets its own Optuna study (100 trials) over 8" -ForegroundColor DarkYellow
Write-Host "  hyperparameters (iterations, learning_rate, depth, l2_leaf_reg," -ForegroundColor DarkYellow
Write-Host "  random_strength, bagging_temperature, min_data_in_leaf," -ForegroundColor DarkYellow
Write-Host "  border_count) on a chronological 80/20 holdout of that regime's" -ForegroundColor DarkYellow
Write-Host "  rows, with eval_set-based early stopping (use_best_model=True)." -ForegroundColor DarkYellow
Write-Host "  The FINAL model per regime is then ALSO evaluated on that same" -ForegroundColor DarkYellow
Write-Host "  regime's own chronological holdout tail (never mixed with other" -ForegroundColor DarkYellow
Write-Host "  regimes) -- see 'Regime holdout' log lines. Each regime/side model" -ForegroundColor DarkYellow
Write-Host "  also picks its decision threshold on that same holdout via" -ForegroundColor DarkYellow
Write-Host "  --threshold-objective ($ThresholdObjective) instead of a fixed 0.5" -ForegroundColor DarkYellow
Write-Host "  cutoff -- see 'threshold=' in the holdout log lines. Other flags" -ForegroundColor DarkYellow
Write-Host "  (--ensemble, --cv-mode, --feature-selection) are NOT applied on" -ForegroundColor DarkYellow
Write-Host "  this path." -ForegroundColor DarkYellow
Write-Host ""

$ModelDir = Join-Path $ArtifactsDir "regime_stacking_model"

if ($RegimeMode -eq "classifier") {
    $RegimeTrainFlags = @("--regime-classifier-dir", $RegimeClassifierDir)
    Write-Host "[Phase 3] Training with LEARNED-CLASSIFIER regime bucketing ..." -ForegroundColor Yellow
} else {
    $RegimeTrainFlags = @("--multi-feature-regime")
    if ($RuleRegimeConfig -ne "" -and (Test-Path $RuleRegimeConfig)) {
        $RegimeTrainFlags += @("--rule-regime-config", $RuleRegimeConfig)
        Write-Host "[Phase 3] Training with MULTI-FEATURE RULE regime bucketing (config: $RuleRegimeConfig) ..." -ForegroundColor Yellow
    } else {
        Write-Host "[Phase 3] Training with MULTI-FEATURE RULE regime bucketing (default config) ..." -ForegroundColor Yellow
    }
}
python -m btcusdt_quant train `
    --input $FullParquet `
    --regime-aware `
    --training-start $DownloadStart `
    --training-end $TrainingEnd `
    --metrics-dir $MetricsDir `
    --threshold-objective $ThresholdObjective `
    --round-trip-cost $RoundTripCost `
    --horizon $Horizon `
    --tp-pct $LabelTpPct `
    --sl-pct $LabelSlPct `
    @RegimeTrainFlags `
    --optuna `
    --optuna-trials 100 `
    --output $ModelDir

Write-Host ""
Write-Host "  Training complete." -ForegroundColor Green
Write-Host "  Model: $ModelDir" -ForegroundColor Green

# ============================================================================
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
# ============================================================================

Write-Host ""

$BacktestDir = Join-Path $ArtifactsDir "backtest_results"

if ($RegimeMode -eq "classifier") {
    $RegimeBtFlags = @("--regime-classifier-dir", $RegimeClassifierDir)
    Write-Host "[Phase 4] Backtest with learned-classifier routing (same model as Phase 3) ..." -ForegroundColor Yellow
} else {
    # Rule mode: the fitted detector is saved inside the model artifact and
    # auto-loaded here, so routing matches training with no extra flag.
    $RegimeBtFlags = @()
    Write-Host "[Phase 4] Backtest with multi-feature rule routing (auto-loaded from artifact) ..." -ForegroundColor Yellow
}
python -m btcusdt_quant backtest `
    --input $FullParquet `
    --model-artifact $ModelDir `
    @RegimeBtFlags `
    --exec-tp-pct $LabelTpPct `
    --exec-sl-pct $LabelSlPct `
    --metrics-dir $MetricsDir `
    --fee-rate-per-side $FeePerSide `
    --slippage-rate-per-side $SlippagePerSide `
    --horizon $Horizon `
    --threshold-floor $ThresholdFloor `
    --backtest-start $BacktestStart `
    --backtest-end $BacktestEnd `
    --output $BacktestDir

Write-Host ""
Write-Host "=== Pipeline Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Outputs:" -ForegroundColor Green
Write-Host "  Combined data : $FullParquet" -ForegroundColor Green
Write-Host "  Model         : $ModelDir" -ForegroundColor Green
Write-Host "  Backtest      : $BacktestDir" -ForegroundColor Green
Write-Host ""

$summaryPath = Join-Path $BacktestDir "backtest_summary.json"
if (Test-Path $summaryPath) {
    $b = (Get-Content $summaryPath -Raw | ConvertFrom-Json).backtest
    Write-Host ("  gross={0:P3}  net={1:P3}  trades={2}  win={3:P1}" -f `
        $b.gross_total_return, $b.net_total_return, $b.trade_count, $b.win_rate) -ForegroundColor Green
    if ($b.regime_coverage) {
        $cov = $b.regime_coverage
        Write-Host ("  regime coverage: matched={0} default_fallback={1} no_model={2}" -f `
            $cov.matched, $cov.default_fallback, $cov.no_model) -ForegroundColor Gray
    }
} else {
    Write-Host "  (backtest summary not found)" -ForegroundColor Yellow
}
