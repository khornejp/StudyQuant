# TP/SL Exact Sweep (Windows PowerShell)
# ---------------------------------------------------------------------------
# For each (TP, SL) combination this script:
#   1. Re-trains the regime models with that TP/SL as the triple-barrier
#      label (so labels match what the backtest will trade).
#   2. Re-runs the backtest with the SAME TP/SL as the strategy floor.
#   3. Collects gross/net metrics into a comparison CSV.
#
# The point is NOT to find a profitable setting by luck, but to MEASURE
# whether the model has a real directional edge that survives cost at ANY
# barrier width. Read the gross_* columns: if gross expectancy stays ~0
# across all rows, the model — not the TP/SL — is the bottleneck.
#
# Requirements: a prepared full-history Parquet + regimes.json (produced by
# run_full_pipeline.ps1 Phases 1-2). This script only re-runs Phases 3-4.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File tp_sl_sweep.ps1
# ---------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

# ====== Configuration (match run_full_pipeline.ps1) ========================
$FullParquet     = "artifacts/btcusdt_2020_2025.parquet"
$RegimeFile      = "regimes.json"
$DownloadStart   = "2020-01-01"
$TrainingEnd     = "2024-12-31"
$ValidationStart = "2025-01-01"
$ValidationEnd   = "2025-06-30"
$BacktestStart   = "2025-07-01"
$SweepDir        = "artifacts/tp_sl_sweep"
$OptunaTrials    = 15   # fewer trials per cell to keep the sweep tractable
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
if (-not (Test-Path $RegimeFile)) {
    Write-Host "ERROR: $RegimeFile not found." -ForegroundColor Red
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
    Write-Host "[$label] Training (tp=$tp sl=$sl)..." -ForegroundColor Yellow
    python -m btcusdt_quant train `
        --input $FullParquet `
        --use-user-regime `
        --user-regime-file $RegimeFile `
        --training-start $DownloadStart `
        --training-end $TrainingEnd `
        --test-start $ValidationStart `
        --test-end $ValidationEnd `
        --tp-pct $tp `
        --sl-pct $sl `
        --optuna `
        --optuna-trials $OptunaTrials `
        --output $modelDir

    # --- Phase 4: backtest with the SAME TP/SL as the strategy floor ---
    Write-Host "[$label] Backtesting (tp-floor=$tp sl-floor=$sl)..." -ForegroundColor Yellow
    python -m btcusdt_quant backtest `
        --input $FullParquet `
        --model-artifact $modelDir `
        --user-regime-file $RegimeFile `
        --backtest-start $BacktestStart `
        --tp-floor $tp `
        --sl-floor $sl `
        --fixed-tp-sl `
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
