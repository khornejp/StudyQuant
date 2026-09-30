param([switch]$ResumeBacktests)

$ErrorActionPreference = "Stop"

$workspace = "D:\StudyQuant"
$python = Join-Path $workspace "venv_btcusdt\Scripts\python.exe"
$runRoot = Join-Path $workspace "artifacts\short_quantile_sweep_20260826"
$modelDir = Join-Path $runRoot "model_oos"
$statusPath = Join-Path $runRoot "status.json"
$startedAt = (Get-Date).ToString("o")

function Write-RunStatus([string]$state, [string]$stage, [string]$message) {
    [ordered]@{
        state = $state
        stage = $stage
        message = $message
        pid = $PID
        started_at = $startedAt
        updated_at = (Get-Date).ToString("o")
    } | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding UTF8
}

function Invoke-Logged([string[]]$arguments, [string]$logPath) {
    $previousPreference = $ErrorActionPreference
    try {
        # Windows PowerShell wraps a native program's stderr as ErrorRecord.
        # Warnings belong in the log; only the process exit code decides failure.
        $ErrorActionPreference = "Continue"
        & $python @arguments *> $logPath
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

if ((Test-Path -LiteralPath $runRoot) -and -not $ResumeBacktests) {
    throw "Refusing to mix results with an existing run: $runRoot"
}
if (-not (Test-Path -LiteralPath $runRoot)) {
    New-Item -ItemType Directory -Path $runRoot | Out-Null
}
if ($ResumeBacktests -and -not (Test-Path -LiteralPath (Join-Path $modelDir "model.json"))) {
    throw "Cannot resume: trained model is missing from $modelDir"
}

try {
    if (-not $ResumeBacktests) {
        Write-RunStatus "running" "training" "Regenerating features, training the short model, and producing walk-forward OOS predictions."
        $trainArgs = @(
        "-m", "btcusdt_quant", "train",
        "--input", "artifacts/btcusdt_2020_2026h1.parquet",
        "--metrics-dir", "artifacts/metrics",
        "--funding-dir", "artifacts/funding_2020_2026h1",
        "--premium-index-dir", "artifacts/premium_index_2020_2026h1",
        "--training-start", "2020-01-01",
        "--training-end", "2025-12-31",
        "--output", $modelDir,
        "--cv-mode", "walk_forward",
        "--walk-forward-test-gap", "45",
        "--walk-forward-train-size", "10080",
        "--walk-forward-validation-size", "10080",
        "--walk-forward-test-size", "10080",
        "--shared-prior-threshold",
        "--target", "short_profitability",
        "--round-trip-cost", "0.0004",
        "--horizon", "45",
        "--label-threshold", "0.0004",
        "--long-label-tp-pct", "0.004",
        "--long-label-sl-pct", "0.002",
        "--short-label-tp-pct", "0.006",
        "--short-label-sl-pct", "0.012",
        "--vol-gate-feature", "rv_60",
        "--vol-gate-train-quantile", "0.8"
        )
        $trainExit = Invoke-Logged $trainArgs (Join-Path $runRoot "training.log")
        if ($trainExit -ne 0) { throw "Training failed with exit code $trainExit" }
    }

    $summary = Get-Content -Raw -LiteralPath (Join-Path $modelDir "run_summary.json") | ConvertFrom-Json
    $gate = $summary.shared_threshold_rule.volatility_gate.cutoff
    if ($null -eq $gate) { throw "Training summary has no shared-prior volatility gate cutoff" }
    $gateText = [Convert]::ToString([double]$gate, [Globalization.CultureInfo]::InvariantCulture)

    $fractions = [ordered]@{
        q45 = "0.55"
        q60 = "0.40"
        q75 = "0.25"
        q99 = "0.01"
    }
    foreach ($arm in $fractions.GetEnumerator()) {
        $name = [string]$arm.Key
        $output = Join-Path $runRoot "backtest_$name"
        if (Test-Path -LiteralPath (Join-Path $output "backtest_summary.json")) {
            continue
        }
        Write-RunStatus "running" "backtest_$name" "Running 2026 H1 OOS with rolling $name."
        $backtestArgs = @(
            "-m", "btcusdt_quant", "backtest",
            "--input", "artifacts/btcusdt_2020_2026h1.parquet",
            "--output", $output,
            "--model-artifact", $modelDir,
            "--metrics-dir", "artifacts/metrics",
            "--funding-dir", "artifacts/funding_2020_2026h1",
            "--premium-index-dir", "artifacts/premium_index_2020_2026h1",
            "--backtest-start", "2026-01-01",
            "--backtest-end", "2026-06-30",
            "--side", "short",
            "--horizon", "45",
            "--exec-tp-pct", "0.006",
            "--exec-sl-pct", "0.012",
            "--entry-quantile", [string]$arm.Value,
            "--entry-quantile-window", "43200",
            "--entry-quantile-warmup", "1000",
            "--vol-gate-feature", "rv_60",
            "--vol-gate-min", $gateText,
            "--disable-range-gate"
        )
        $backtestExit = Invoke-Logged $backtestArgs (Join-Path $runRoot "$name.log")
        if ($backtestExit -ne 0) { throw "$name backtest failed with exit code $backtestExit" }
    }

    Write-RunStatus "complete" "complete" "Training and all four OOS quantile backtests completed."
}
catch {
    $_ | Out-String | Set-Content -LiteralPath (Join-Path $runRoot "supervisor_error.log") -Encoding UTF8
    Write-RunStatus "failed" "failed" $_.Exception.Message
    exit 1
}
