# BTCUSDT User-Regime Pipeline (Windows PowerShell)
# ---------------------------------------------------------------------------
# Intended flow:
#   1.   Download 2020-01-01 ~ 2025-12-31 Binance archive (full 6-year span)
#   2.   Combine into one Parquet file
#   2.3  Data diagnostics: feature IC report with fold-stability and
#        look-ahead-leakage heuristics (ic_diagnostic.py) + OU half-life of
#        range regimes vs the fixed 20-bar mean-reversion window
#        (verify_range_halflife.py). Informational -- does not gate the run.
#   3.   Train regime-aware models with multi-feature RULE regime bucketing
#        (default $RegimeMode="rule"; regimes.json only needed for the legacy
#        "classifier" mode), training data restricted to 2020-2024.
#        Model quality is checked via a chronological holdout SPLIT OF THE
#        TRAINING DATA ITSELF (last 20% of each regime's own rows), not a
#        separate held-out calendar span -- see "Regime holdout" log lines.
#   3.5  Multi-horizon ensemble pilot: one entry model per label horizon
#        (default 30/60/90m), probabilities blended by validation accuracy
#        (G-Research 7th-place pattern). Regime-aware, mirroring Phase 3's
#        bucketing and direction policy (up->long, down->short, range->both)
#        with per-side long_success/short_success targets, so it is a
#        regime-aligned challenger. Saved to artifacts/multi_horizon_model.
#   4.   Backtest the regime models on the FULL 2025 year (out-of-sample),
#        with fractional-Kelly position sizing ($KellySizing, default on:
#        Half-Kelly from entry probability + executed TP/SL barriers +
#        trailing bar variance; position_size acts as the cap and
#        no-edge entries are skipped).
#   4.5  Backtest the multi-horizon pilot model on the same window with the
#        same cost/kelly settings, so the two model families can be compared
#        in artifacts/backtest_results vs artifacts/backtest_results_multi_horizon.
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

# $ErrorActionPreference="Stop" does NOT trap a native command's nonzero exit
# in Windows PowerShell 5.1 -- python failing here would otherwise fall
# through to the next phase and backtest a stale or missing model artifact,
# reporting the previous run's numbers as if they were current. Every phase
# that produces an artifact the next phase consumes must be gated explicitly.
function Assert-PhaseSucceeded {
    param([Parameter(Mandatory)][string]$Phase)
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERROR: $Phase failed (exit code $LASTEXITCODE). Pipeline stopped." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

# Informational phases: report the failure, keep going. Used only where the
# phase's output is not consumed downstream (diagnostics).
function Warn-IfPhaseFailed {
    param([Parameter(Mandatory)][string]$Phase)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARNING: $Phase failed (exit code $LASTEXITCODE); continuing (informational phase)." -ForegroundColor Yellow
    }
}

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
# The barriers must clear the round-trip cost by a wide margin or the reward:risk
# the labels advertise is not the one the account earns. At TP 0.30%/SL 0.15% the
# 0.08% round trip turns a nominal 2.0:1 into a net 0.96:1 (+0.22% vs -0.23%) and
# lifts break-even win rate from 33.3% to 51.1% -- unreachable, so every run lost.
# At 1.00%/0.50% the net is +0.92% vs -0.58% (1.59:1) and break-even is 38.7%.
if (-not $Horizon)    { $Horizon    = 60 }
if (-not $LabelTpPct) { $LabelTpPct = "0.010" }   # 1.00%
if (-not $LabelSlPct) { $LabelSlPct = "0.005" }   # 0.50%
# Hard lower bound on learned entry thresholds at backtest time (0 = off).
# Off by default: threshold selection already maximizes trading PnL net of
# RoundTripCost, so a floor above the learned value only vetoes it. The 0.45
# floor silently disabled the range regime (learned 0.348/0.358), which is ~91%
# of 2025 bars -- the backtest traded 9% of the data and reported it as a result.
if (-not $ThresholdFloor) { $ThresholdFloor = "0.0" }
# Cost basis SINGLE SOURCE: per-side fee/slippage fractions. The round-trip
# cost 2*(fee+slippage) is derived below and passed to train (threshold
# objective + holdout metrics) while the per-side values go to backtest
# execution -- so threshold selection and execution always share one basis.
if (-not $FeePerSide)      { $FeePerSide      = "0.0002" }  # 0.02%
if (-not $SlippagePerSide) { $SlippagePerSide = "0.0002" }  # 0.02%
$RoundTripCost = [string](2.0 * ([double]$FeePerSide + [double]$SlippagePerSide))
# Fractional-Kelly position sizing for the backtests (Phase 4 / 4.5).
# Half-Kelly (0.5) trades ~18.5% of growth for ~43% smaller max drawdown.
# The backtest's fixed position_size becomes the CAP on the per-trade
# fraction; entries whose Kelly edge is non-positive are skipped (see
# kelly_sizing.entries_skipped_no_edge in backtest_summary.json).
# NOTE: $null -eq checks (not -not) so a preset $KellySizing=$false survives.
if ($null -eq $KellySizing)  { $KellySizing = $true }
if (-not $KellyMultiplier)   { $KellyMultiplier = "0.5" }
if (-not $KellyLookbackBars) { $KellyLookbackBars = "1440" }   # 1 day of 1m bars
# Phase 2.3 data diagnostics (IC/leakage report + range half-life). Adds a
# few minutes on the full 6-year parquet; set $false to skip.
if ($null -eq $RunDiagnostics) { $RunDiagnostics = $true }
# Phase 3.5/4.5 multi-horizon ensemble pilot. Regime-aware: mirrors Phase 3's
# bucketing and direction policy, so it costs one CatBoost per regime x side x
# horizon (no Optuna). Set $false to skip.
if ($null -eq $MultiHorizonPilot) { $MultiHorizonPilot = $true }
if (-not $MhHorizons) { $MhHorizons = "30,60,90" }
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
Assert-PhaseSucceeded "Phase 1 (collect-archive)"

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
Assert-PhaseSucceeded "Phase 1.5 (collect-metrics)"

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
    Assert-PhaseSucceeded "Phase 2 (parquet build)"
} else {
    Write-Host "  (using cached $FullParquet)"
}

# ============================================================================
# PHASE 2.3: Data diagnostics (informational; failures do not stop the run)
#   - ic_diagnostic.py: Spearman IC per feature/horizon with chronological
#     fold mean/std (IC drift) and look-ahead-leakage heuristics (a feature
#     that predicts the future better than it remembers the past, or whose
#     IC collapses when used one bar late, is flagged for triage).
#   - verify_range_halflife.py: measures the OU half-life of mean reversion
#     inside range regimes and compares it against the fixed 20-bar window
#     used by range_position_20 / the mean-reversion gate.
# ============================================================================

if ($RunDiagnostics) {
    Write-Host ""
    Write-Host "[Phase 2.3] Data diagnostics (feature IC / leakage / range half-life) ..." -ForegroundColor Yellow

    $IcReportDir = Join-Path $ArtifactsDir "ic_report"
    $IcArgs = @("--input", $FullParquet, "--metrics-dir", $MetricsDir, "--output", $IcReportDir)
    if (Test-Path $RegimeFile) { $IcArgs += @("--regime-file", $RegimeFile) }
    python ic_diagnostic.py @IcArgs
    Warn-IfPhaseFailed "Phase 2.3 (ic_diagnostic)"
    Write-Host "  IC/leakage report: $IcReportDir\ic_report.csv (leak flags are heuristics -- confirm with a truncation-invariance test before deleting a feature)" -ForegroundColor Gray

    if (Test-Path $RegimeFile) {
        python verify_range_halflife.py --input $FullParquet --regime-file $RegimeFile --series log_zscore
        Warn-IfPhaseFailed "Phase 2.3 (verify_range_halflife)"
    } else {
        Write-Host "  ($RegimeFile not found: half-life runs without per-regime breakdown)" -ForegroundColor DarkYellow
        python verify_range_halflife.py --input $FullParquet --series log_zscore
        Warn-IfPhaseFailed "Phase 2.3 (verify_range_halflife)"
    }
} else {
    Write-Host ""
    Write-Host "[Phase 2.3] Skipped (RunDiagnostics=$RunDiagnostics)." -ForegroundColor DarkYellow
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
    Assert-PhaseSucceeded "Phase 2.5 (train-regime-classifier)"
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
Assert-PhaseSucceeded "Phase 3 (train)"

Write-Host ""
Write-Host "  Training complete." -ForegroundColor Green
Write-Host "  Model: $ModelDir" -ForegroundColor Green

# ============================================================================
# PHASE 3.5: Multi-horizon ensemble pilot (challenger to the regime model)
#
# One entry model per label horizon on the SAME features, probabilities blended
# by validation-accuracy weights (chronological tail split with a max(horizons)
# purge gap). Trained regime-aware, so it shares Phase 3's rule bucketing,
# direction policy, per-side triple-barrier targets, threshold objective,
# threshold horizon, and (via the final refit) the full per-regime training set.
#
# This is a CHALLENGER comparison, not a clean horizon-blend A/B: Phase 3 tunes
# each model with Optuna (100 trials) while the horizon models here use default
# parameters. A Phase 4.5 win or loss therefore reflects the horizon blend AND
# the tuning difference. Read the two together.
#
# A short model must learn short_success -- 1-P(long_success) is not a short
# probability (a long that times out is not a short win), and a model that
# cannot price shorts would be silently long-only under Kelly.
# ============================================================================

Write-Host ""
$MhModelDir = Join-Path $ArtifactsDir "multi_horizon_model"

if ($MultiHorizonPilot) {
    Write-Host "[Phase 3.5] Training multi-horizon ensemble pilot (horizons: $MhHorizons) ..." -ForegroundColor Yellow
    Write-Host "  Regime-aware: one horizon-blended ensemble per regime AND side (up->long," -ForegroundColor Gray
    Write-Host "  down->short, range->both), each on its own long_success/short_success target," -ForegroundColor Gray
    Write-Host "  with a per-regime/side holdout threshold. Same artifact layout and direction" -ForegroundColor Gray
    Write-Host "  policy as Phase 3. Phase 4.5 is a regime-aligned multi-horizon challenger:" -ForegroundColor Gray
    Write-Host "  it shares execution and routing with Phase 4, but still differs in horizon" -ForegroundColor Gray
    Write-Host "  blending, base-model tuning (Optuna vs defaults) and probability calibration." -ForegroundColor Gray
    # --threshold-horizon $Horizon: pick each regime/side cutoff against the
    # SAME time barrier Phase 4.5 executes on. Without it the thresholds would
    # be scored on max(horizons)=90-bar labels while the backtest times out at
    # $Horizon, adding a second axis of difference vs Phase 4.
    $MhTrainFlags = @("--regime-aware", "--threshold-horizon", $Horizon, "--threshold-objective", $ThresholdObjective, "--round-trip-cost", $RoundTripCost)
    if ($RuleRegimeConfig -ne "" -and (Test-Path $RuleRegimeConfig)) {
        $MhTrainFlags += @("--rule-regime-config", $RuleRegimeConfig)
    }
    python -m btcusdt_quant train-multi-horizon `
        --input $FullParquet `
        --training-start $DownloadStart `
        --training-end $TrainingEnd `
        --horizons $MhHorizons `
        --tp-pct $LabelTpPct `
        --sl-pct $LabelSlPct `
        --weighting validation `
        --metrics-dir $MetricsDir `
        @MhTrainFlags `
        --output $MhModelDir
    # NON-FATAL: the multi-horizon pilot is a challenger, not the deliverable.
    # Its regime-aware training fails closed (exit 1) on a one-sided data quirk
    # -- correct for the pilot, but it must not abort the primary Phase 4
    # regime-model backtest that follows. On failure, skip Phase 4.5 rather
    # than shipping/comparing a partial pilot artifact.
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARNING: Phase 3.5 (multi-horizon pilot) failed (exit $LASTEXITCODE); skipping Phase 4.5. Phase 4 continues." -ForegroundColor Yellow
        $MultiHorizonPilot = $false
    } else {
        Write-Host "  Multi-horizon model: $MhModelDir" -ForegroundColor Green
    }
} else {
    Write-Host "[Phase 3.5] Skipped (MultiHorizonPilot=$MultiHorizonPilot)." -ForegroundColor DarkYellow
}

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
# Fractional-Kelly sizing flags shared by Phase 4 and Phase 4.5. The main
# backtest is Kelly-sized while the strategy_comparison block inside the
# summary stays fixed-size (marked "sizing": "fixed_position_size") -- do
# not compare the two directly.
$KellyFlags = @()
if ($KellySizing) {
    $KellyFlags = @("--kelly-sizing", "--kelly-multiplier", $KellyMultiplier, "--kelly-lookback-bars", $KellyLookbackBars)
    Write-Host "  Kelly sizing ON: Half-Kelly=$KellyMultiplier, variance lookback=$KellyLookbackBars bars, holding=--horizon ($Horizon bars), cap=position_size" -ForegroundColor Gray
}
python -m btcusdt_quant backtest `
    --input $FullParquet `
    --model-artifact $ModelDir `
    @RegimeBtFlags `
    @KellyFlags `
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
Assert-PhaseSucceeded "Phase 4 (backtest)"

# ============================================================================
# PHASE 4.5: Backtest the multi-horizon pilot on the same window/costs
# ============================================================================

$MhBacktestDir = Join-Path $ArtifactsDir "backtest_results_multi_horizon"

if ($MultiHorizonPilot) {
    Write-Host ""
    Write-Host "[Phase 4.5] Backtest multi-horizon pilot (same window, costs and kelly settings) ..." -ForegroundColor Yellow
    # Directory artifact (not model.json): regime_run_summary.json rides the
    # fitted rule detector, so routing and the direction policy match Phase 4.
    python -m btcusdt_quant backtest `
        --input $FullParquet `
        --model-artifact $MhModelDir `
        @KellyFlags `
        --exec-tp-pct $LabelTpPct `
        --exec-sl-pct $LabelSlPct `
        --metrics-dir $MetricsDir `
        --fee-rate-per-side $FeePerSide `
        --slippage-rate-per-side $SlippagePerSide `
        --horizon $Horizon `
        --threshold-floor $ThresholdFloor `
        --backtest-start $BacktestStart `
        --backtest-end $BacktestEnd `
        --output $MhBacktestDir
    Assert-PhaseSucceeded "Phase 4.5 (multi-horizon backtest)"
}

Write-Host ""
Write-Host "=== Pipeline Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Outputs:" -ForegroundColor Green
Write-Host "  Combined data : $FullParquet" -ForegroundColor Green
Write-Host "  Model         : $ModelDir" -ForegroundColor Green
Write-Host "  Backtest      : $BacktestDir" -ForegroundColor Green
if ($MultiHorizonPilot) {
    Write-Host "  MH model      : $MhModelDir" -ForegroundColor Green
    Write-Host "  MH backtest   : $MhBacktestDir" -ForegroundColor Green
}
Write-Host ""

# A risk metric is null in the summary when it is UNDEFINED: fewer trades than
# risk_metrics_min_trades, or zero return dispersion. PowerShell formats $null
# as an empty string, which reads as a rendering glitch rather than a verdict,
# so say so explicitly.
function Format-Metric {
    param($Value, [string]$Format = "N3")
    if ($null -eq $Value) { return "n/a" }
    return ("{0:$Format}" -f $Value)
}

function Show-BacktestSummary {
    param([string]$Label, [string]$SummaryPath)
    if (-not (Test-Path $SummaryPath)) {
        Write-Host "  ${Label}: (backtest summary not found)" -ForegroundColor Yellow
        return
    }
    $b = (Get-Content $SummaryPath -Raw | ConvertFrom-Json).backtest
    Write-Host ("  {0}: gross={1}  net={2}  trades={3}  win={4}" -f `
        $Label, (Format-Metric $b.gross_total_return "P3"), (Format-Metric $b.net_total_return "P3"), `
        $b.trade_count, (Format-Metric $b.win_rate "P1")) -ForegroundColor Green
    # Gross vs net Sharpe side by side: the gap is the cost drag. A strategy
    # whose Sharpe is only positive gross must not ship (Chan ch.3).
    Write-Host ("    sharpe: net={0}  gross={1}  cost_impact={2}" -f `
        (Format-Metric $b.net_sharpe), (Format-Metric $b.gross_sharpe), (Format-Metric $b.cost_impact_sharpe)) -ForegroundColor Green
    if ($b.kelly_sizing -and $b.kelly_sizing.enabled) {
        $k = $b.kelly_sizing
        Write-Host ("    kelly: avg_frac={0:N4}  min={1:N4}  max={2:N4}  (cap={3})  skipped_no_edge={4}" -f `
            $k.avg_fraction, $k.min_fraction, $k.max_fraction, $k.cap, $k.entries_skipped_no_edge) -ForegroundColor Gray
        if ($k.shorts_skipped_no_short_model -gt 0) {
            Write-Host ("    kelly: {0} SELL signals refused (no short-success model) -- this run was LONG-ONLY" -f `
                $k.shorts_skipped_no_short_model) -ForegroundColor Yellow
        }
    }
    if ($b.regime_coverage) {
        $cov = $b.regime_coverage
        Write-Host ("    regime coverage: matched={0} default_fallback={1} no_model={2}" -f `
            $cov.matched, $cov.default_fallback, $cov.no_model) -ForegroundColor Gray
    }
}

Show-BacktestSummary -Label "regime model " -SummaryPath (Join-Path $BacktestDir "backtest_summary.json")
if ($MultiHorizonPilot) {
    Show-BacktestSummary -Label "multi-horizon" -SummaryPath (Join-Path $MhBacktestDir "backtest_summary.json")
    # Regime x side x month breakdown -- the axes that actually explain a
    # difference between the two models. Informational; never gates the run.
    $BtA = Join-Path $BacktestDir "backtest_summary.json"
    $BtB = Join-Path $MhBacktestDir "backtest_summary.json"
    if ((Test-Path $BtA) -and (Test-Path $BtB)) {
        Write-Host ""
        python compare_backtests.py $BtA $BtB
        Warn-IfPhaseFailed "compare_backtests"
    }
    Write-Host "  (multi-horizon pilot shares Phase 4's regimes and direction policy -- judge it on net sharpe/MDD, not raw return)" -ForegroundColor Gray
}
if ($RunDiagnostics) {
    Write-Host "  IC/leakage report: $(Join-Path $ArtifactsDir 'ic_report')\ic_report.csv" -ForegroundColor Gray
}
