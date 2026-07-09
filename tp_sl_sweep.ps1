# TP/SL Exact Sweep (Windows PowerShell)
# ---------------------------------------------------------------------------
# For each (TP, SL) combination this script:
#   1. Re-trains the regime models with that TP/SL as the triple-barrier
#      label (so labels match what the backtest will trade), using the SAME
#      structure as run_full_pipeline.ps1: multi-feature RULE regime
#      bucketing, trading_pnl threshold objective, explicit horizon.
#   2. Re-runs the backtest EXECUTING exactly those label barriers
#      (--exec-tp-pct/--exec-sl-pct) over a pinned 2025 window, with the
#      fitted rule detector auto-loaded from the model artifact.
#   3. Collects gross/net metrics into a comparison CSV.
#
# The point is NOT to find a profitable setting by luck, but to MEASURE
# whether the model has a real directional edge that survives cost at ANY
# barrier width. Read the gross_* columns: if gross expectancy stays ~0
# across all rows, the model — not the TP/SL — is the bottleneck.
#
# Regimes are routed with the multi-feature RULE detector fitted at training
# time and embedded in each cell's model artifact (auto-loaded by the
# backtest) -- the same path run_full_pipeline.ps1 uses. The detector's
# regime assignment doesn't depend on TP/SL, so cell-to-cell differences
# here still isolate only the TP/SL change.
#
# Requirements: a prepared full-history Parquet (produced by
# run_full_pipeline.ps1 Phases 1-2). This script re-runs training + a single
# controlled backtest per TP/SL cell.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File tp_sl_sweep.ps1
# ---------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

# ====== Configuration (match run_full_pipeline.ps1) ========================
$FullParquet      = "artifacts/btcusdt_2020_2025.parquet"
$DownloadStart    = "2020-01-01"
$TrainingEnd      = "2024-12-31"
$BacktestStart    = "2025-01-01"
$BacktestEnd      = "2025-12-31"   # date-only = inclusive of the whole day
$SweepDir         = "artifacts/tp_sl_sweep"
$OptunaTrials     = 15   # fewer trials per cell to keep the sweep tractable
$Horizon          = 60   # bars (=minutes). SAME value goes to train AND backtest.
$ThresholdFloor   = "0.45"
$RuleRegimeConfig = "configs/rule_regime.json"  # "" -> built-in defaults
$FeePerSide       = "0.0002"  # 0.02%
$SlippagePerSide  = "0.0002"  # 0.02%
$RoundTripCost    = [string](2.0 * ([double]$FeePerSide + [double]$SlippagePerSide))  # -> train
# Same F16 derivatives-metrics archive the main pipeline collects. If the
# directory has data, it is passed to BOTH train and backtest of every cell
# (training with metrics and backtesting without them is a train/serve
# feature skew). Leave the directory absent/empty to sweep without metrics.
$MetricsDir       = "artifacts/metrics"
# ==========================================================================

# (TP, SL) pairs to sweep. Expressed as fractions of price.
# Covers 2:1 and 3:1 reward:risk at several absolute widths vs the 0.08% cost.
$Combos = @(
    @{ tp = 0.002;  sl = 0.001  ; label = "tp0.20_sl0.10_2to1" },
    @{ tp = 0.003;  sl = 0.0015 ; label = "tp0.30_sl0.15_2to1" },
    @{ tp = 0.004;  sl = 0.002  ; label = "tp0.40_sl0.20_2to1" },
    @{ tp = 0.005;  sl = 0.0025 ; label = "tp0.50_sl0.25_2to1" },
    @{ tp = 0.003;  sl = 0.001  ; label = "tp0.30_sl0.10_3to1" },
    @{ tp = 0.006;  sl = 0.002  ; label = "tp0.60_sl0.20_3to1" }
)

if (-not (Test-Path $FullParquet)) {
    Write-Host "ERROR: $FullParquet not found. Run run_full_pipeline.ps1 Phases 1-2 first." -ForegroundColor Red
    exit 1
}
New-Item -ItemType Directory -Force -Path $SweepDir | Out-Null

$ResultsCsv = Join-Path $SweepDir "sweep_results.csv"
"label,tp_pct,sl_pct,trades,win_rate,gross_total_return,net_total_return,profit_factor,sharpe,max_drawdown,best_strategy" | Out-File -FilePath $ResultsCsv -Encoding utf8

foreach ($combo in $Combos) {
    $tp = $combo.tp
    $sl = $combo.sl
    $label = $combo.label
    Write-Host ""
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host " Sweep cell: $label  (TP=$($tp*100)%  SL=$($sl*100)%)" -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Cyan

    $cellDir   = Join-Path $SweepDir $label
    $modelDir  = Join-Path $cellDir "model"
    $btDir     = Join-Path $cellDir "backtest"
    New-Item -ItemType Directory -Force -Path $cellDir | Out-Null

    # --- Phase 3: re-train with this TP/SL as the label ---
    # Mirrors run_full_pipeline.ps1 Phase 3: multi-feature RULE regime
    # bucketing (fitted detector saved in the artifact, auto-loaded by the
    # backtest), trading_pnl threshold objective, and an explicit horizon so
    # every cell shares the pipeline's label geometry except TP/SL.
    $RegimeTrainFlags = @("--multi-feature-regime")
    if ($RuleRegimeConfig -ne "" -and (Test-Path $RuleRegimeConfig)) {
        $RegimeTrainFlags += @("--rule-regime-config", $RuleRegimeConfig)
    }
    $MetricsFlags = @()
    if ($MetricsDir -ne "" -and (Test-Path $MetricsDir) -and (Get-ChildItem $MetricsDir -Filter *.zip -ErrorAction SilentlyContinue)) {
        $MetricsFlags = @("--metrics-dir", $MetricsDir)
    }
    Write-Host "[$label] Training (tp=$tp sl=$sl horizon=$Horizon)..." -ForegroundColor Yellow
    python -m btcusdt_quant train `
        --input $FullParquet `
        --regime-aware `
        @RegimeTrainFlags `
        @MetricsFlags `
        --threshold-objective trading_pnl `
        --round-trip-cost $RoundTripCost `
        --horizon $Horizon `
        --training-start $DownloadStart `
        --training-end $TrainingEnd `
        --tp-pct $tp `
        --sl-pct $sl `
        --optuna `
        --optuna-trials $OptunaTrials `
        --output $modelDir

    # --- Phase 4: backtest executing EXACTLY the label barriers ---
    # Rule routing auto-loads from the model artifact (no --auto-regime:
    # that would route with the legacy slope-only detector, a skew vs the
    # rule buckets the models trained on). --exec-tp/sl-pct forces the
    # executed barriers to the label TP/SL; --horizon matches the label
    # timeout; --backtest-end pins the traded window; --threshold-floor and
    # learned per-regime thresholds mirror run_full_pipeline.ps1.
    Write-Host "[$label] Backtesting (exec-tp=$tp exec-sl=$sl horizon=$Horizon)..." -ForegroundColor Yellow
    python -m btcusdt_quant backtest `
        --input $FullParquet `
        --model-artifact $modelDir `
        --exec-tp-pct $tp `
        --exec-sl-pct $sl `
        @MetricsFlags `
        --fee-rate-per-side $FeePerSide `
        --slippage-rate-per-side $SlippagePerSide `
        --horizon $Horizon `
        --threshold-floor $ThresholdFloor `
        --backtest-start $BacktestStart `
        --backtest-end $BacktestEnd `
        --output $btDir

    # --- Collect metrics from backtest_summary.json ---
    $summaryPath = Join-Path $btDir "backtest_summary.json"
    if (Test-Path $summaryPath) {
        $j = Get-Content $summaryPath -Raw | ConvertFrom-Json
        $b = $j.backtest
        $row = "$label,$tp,$sl,$($b.trade_count),$($b.win_rate),$($b.gross_total_return),$($b.net_total_return),$($b.profit_factor),$($b.sharpe),$($b.max_drawdown),$($j.strategy_comparison.best_strategy)"
        $row | Out-File -FilePath $ResultsCsv -Append -Encoding utf8
        Write-Host "[$label] gross=$($b.gross_total_return)  net=$($b.net_total_return)  trades=$($b.trade_count)  win=$($b.win_rate)" -ForegroundColor Green
    } else {
        Write-Host "[$label] WARNING: no backtest summary produced" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Sweep complete ===" -ForegroundColor Cyan
Write-Host "Results: $ResultsCsv" -ForegroundColor Green
Write-Host ""
Write-Host "How to read this:" -ForegroundColor Gray
Write-Host "  - If gross_total_return stays near 0 (or negative) across ALL rows," -ForegroundColor Gray
Write-Host "    the model has no cost-surviving edge -> fix the MODEL, not TP/SL." -ForegroundColor Gray
Write-Host "  - If some row shows clearly positive gross_total_return, the model" -ForegroundColor Gray
Write-Host "    has an edge at that barrier width -> TP/SL tuning is worthwhile." -ForegroundColor Gray
Write-Host "  - net_total_return is after cost; gross is the cleaner edge signal." -ForegroundColor Gray
Get-Content $ResultsCsv | ForEach-Object { Write-Host $_ }
