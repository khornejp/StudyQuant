# BTCUSDT Pipeline - Unified Feature Computation (Portable)
# Usage:
#   .\run_pipeline.ps1                           # Run full pipeline
#   .\run_pipeline.ps1 -VenvPath ".\venv_btcusdt" # Use custom venv
#   .\run_pipeline.ps1 -SkipDownload             # Skip archive download
#   .\run_pipeline.ps1 -SkipBuild                # Skip dataset build
#   .\run_pipeline.ps1 -OnlyBacktest             # Only run backtest
#
# Requirements:
#   - PowerShell 5.1+
#   - Python venv with btcusdt_quant dependencies installed
#   - pyarrow (for CSV to Parquet conversion)

[CmdletBinding()]
param(
    [string]$VenvPath = ".\venv_btcusdt",
    [string]$DataDir = "artifacts",
    [string]$StartDate = "2020-01-01",
    [string]$EndDate = "2025-12-31",
    [string]$TrainEnd = "2024-12-31",
    [string]$TestStart = "2025-01-01",
    [string]$TestEnd = "2025-06-30",
    [string]$BacktestStart = "2025-07-01",
    [switch]$SkipDownload,
    [switch]$SkipBuild,
    [switch]$OnlyBacktest,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# ─── Resolve paths ────────────────────────────────────────────────────────────
$RepoRoot = $PSScriptRoot
if (-not $RepoRoot) { $RepoRoot = $PWD.Path }
Set-Location $RepoRoot

$VenvPath = Resolve-Path $VenvPath -ErrorAction SilentlyContinue
if (-not $VenvPath) {
    $VenvPath = Join-Path $RepoRoot $VenvPath
}

$DataDir = Join-Path $RepoRoot $DataDir
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$VenvPip = Join-Path $VenvPath "Scripts\pip.exe"

# ─── Validate environment ─────────────────────────────────────────────────────
function Test-Prereqs {
    if (-not (Test-Path $VenvPython)) {
        Write-Host "ERROR: Python not found in venv: $VenvPython" -ForegroundColor Red
        Write-Host "Please create the venv first:" -ForegroundColor Yellow
        Write-Host "  python -m venv venv_btcusdt" -ForegroundColor Cyan
        Write-Host "  .\venv_btcusdt\Scripts\activate.bat" -ForegroundColor Cyan
        Write-Host "  pip install -e .`"[ml]`"" -ForegroundColor Cyan
        exit 1
    }

    # Check pyarrow (needed for CSV→Parquet conversion)
    $hasPyarrow = & $VenvPython -c "import pyarrow" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Installing pyarrow (required for CSV to Parquet conversion)..." -ForegroundColor Yellow
        & $VenvPip install pyarrow
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to install pyarrow" -ForegroundColor Red
            exit 1
        }
    }

    # Verify btcusdt_quant is importable
    $hasModule = & $VenvPython -c "import btcusdt_quant" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: btcusdt_quant module not found in venv" -ForegroundColor Red
        Write-Host "Please install the project in editable mode:" -ForegroundColor Yellow
        Write-Host "  $VenvPip install -e .`"[ml]`"" -ForegroundColor Cyan
        exit 1
    }

    Write-Host "Environment OK: $VenvPython" -ForegroundColor Green
}

# ─── Wrapper for venv python ──────────────────────────────────────────────────
function Invoke-VenvPython {
    param([string]$Arguments)
    if ($DryRun) {
        Write-Host "[DRY-RUN] $VenvPython $Arguments" -ForegroundColor Gray
        return
    }
    & $VenvPython @($Arguments -split ' ')
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $VenvPython $Arguments"
    }
}

# ─── User-defined regime periods (2020-2024 only, used for training) ──────────
$regimePeriods = @(
    # 2020
    @{Regime="up";     Start="2020-01-01"; End="2020-02-13"},
    @{Regime="down";   Start="2020-02-13"; End="2020-03-13"},
    @{Regime="up";     Start="2020-03-13"; End="2020-05-11"},
    @{Regime="range";  Start="2020-05-11"; End="2020-07-20"},
    @{Regime="up";     Start="2020-07-20"; End="2020-09-01"},
    @{Regime="range";  Start="2020-09-01"; End="2020-10-08"},
    @{Regime="up";     Start="2020-10-08"; End="2021-01-08"},
    # 2021
    @{Regime="down";   Start="2021-01-08"; End="2021-01-27"},
    @{Regime="up";     Start="2021-01-27"; End="2021-04-14"},
    @{Regime="down";   Start="2021-04-14"; End="2021-07-20"},
    @{Regime="up";     Start="2021-07-20"; End="2021-09-07"},
    @{Regime="down";   Start="2021-09-07"; End="2021-09-29"},
    @{Regime="up";     Start="2021-09-29"; End="2021-11-10"},
    @{Regime="down";   Start="2021-11-10"; End="2022-01-24"},
    # 2022
    @{Regime="up";     Start="2022-01-24"; End="2022-03-28"},
    @{Regime="down";   Start="2022-03-28"; End="2022-05-12"},
    @{Regime="down";   Start="2022-05-12"; End="2022-06-18"},
    @{Regime="range";  Start="2022-06-18"; End="2022-08-15"},
    @{Regime="down";   Start="2022-08-15"; End="2022-09-21"},
    @{Regime="range";  Start="2022-09-21"; End="2022-11-05"},
    @{Regime="down";   Start="2022-11-05"; End="2022-11-21"},
    @{Regime="range";  Start="2022-11-21"; End="2022-12-31"},
    # 2023
    @{Regime="up";     Start="2023-01-01"; End="2023-02-16"},
    @{Regime="down";   Start="2023-02-16"; End="2023-03-10"},
    @{Regime="up";     Start="2023-03-10"; End="2023-04-14"},
    @{Regime="range";  Start="2023-04-14"; End="2023-06-15"},
    @{Regime="up";     Start="2023-06-15"; End="2023-07-13"},
    @{Regime="down";   Start="2023-07-13"; End="2023-09-11"},
    @{Regime="range";  Start="2023-09-11"; End="2023-10-16"},
    @{Regime="up";     Start="2023-10-16"; End="2023-12-08"},
    @{Regime="range";  Start="2023-12-08"; End="2023-12-31"},
    # 2024
    @{Regime="down";   Start="2024-01-01"; End="2024-01-23"},
    @{Regime="up";     Start="2024-01-23"; End="2024-03-14"},
    @{Regime="down";   Start="2024-03-14"; End="2024-05-01"},
    @{Regime="up";     Start="2024-05-01"; End="2024-06-07"},
    @{Regime="down";   Start="2024-06-07"; End="2024-08-05"},
    @{Regime="range";  Start="2024-08-05"; End="2024-09-06"},
    @{Regime="up";     Start="2024-09-06"; End="2024-10-29"},
    @{Regime="up";     Start="2024-11-05"; End="2024-12-17"},
    @{Regime="down";   Start="2024-12-17"; End="2024-12-31"}
)

# Standard Binance kline columns
$BINANCE_COLS = @(
    'open_time', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'count', 'taker_buy_volume',
    'taker_buy_quote_volume', 'ignore'
)

function Convert-CsvToParquet($csvDir, $outputParquet) {
    Write-Host "  Converting CSVs to Parquet: $outputParquet" -ForegroundColor Yellow
    $script = @"
import glob, pyarrow.csv as pv, pyarrow.parquet as pq, pyarrow as pa

BINANCE_COLS = [
    'open_time', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'count', 'taker_buy_volume',
    'taker_buy_quote_volume', 'ignore'
]

def read_csv_safe(path):
    with open(path, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
    first_field = first_line.split(',')[0] if first_line else ''
    is_header = not (first_field.replace('.', '').replace('-', '').isdigit())
    if is_header:
        return pv.read_csv(path)
    else:
        return pv.read_csv(path, read_options=pv.ReadOptions(column_names=BINANCE_COLS))

files = sorted(glob.glob('$csvDir/BTCUSDT-1m-*.csv'))
if not files:
    print('ERROR: No CSV files found in $csvDir')
    exit(1)
tables = [read_csv_safe(f) for f in files]
t = pa.concat_tables(tables)
names = []
for c in t.column_names:
    if c=='count': names.append('number_of_trades')
    elif c=='taker_buy_volume': names.append('taker_buy_base_volume')
    else: names.append(c)
t = t.rename_columns(names)
t = t.select([n for n in names if n not in ('close_time','ignore')])
pq.write_table(t, '$outputParquet')
print(f'  {t.num_rows:,} rows ({t.num_rows/60/24:.0f} days)')
"@
    if ($DryRun) {
        Write-Host "[DRY-RUN] Convert CSV to Parquet" -ForegroundColor Gray
        return
    }
    & $VenvPython -c $script
    if ($LASTEXITCODE -ne 0) { throw "CSV to Parquet conversion failed" }
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

Test-Prereqs

$fullDir = Join-Path $DataDir "full_2020_2025"
$fullParquet = Join-Path $DataDir "full_2020_2025.parquet"
$regimeJson = Join-Path $DataDir "user_regime_periods.json"
$cachePath = Join-Path $DataDir "full_dataset_cache.pkl"
$modelDir = Join-Path $DataDir "regime_model"
$backtestDir = Join-Path $DataDir "backtest_results"

New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path $fullDir | Out-Null

# ─── STEP 1: Download 2020-2025 Full Dataset ──────────────────────────────────
if (-not $OnlyBacktest -and -not $SkipDownload) {
    Write-Host "`n=== STEP 1: Download $StartDate ~ $EndDate Full Dataset ===" -ForegroundColor Cyan
    if (Test-Path "$fullDir\BTCUSDT-1m-*.csv") {
        Write-Host "Full dataset already downloaded, skipping..." -ForegroundColor Gray
    } else {
        Write-Host "Downloading (this may take a while)..." -ForegroundColor Yellow
        & $VenvPython -m btcusdt_quant collect-archive --start $StartDate --end $EndDate --output $fullDir --allow-public-network --min-rows 2000000
        if (-not (Test-Path "$fullDir\BTCUSDT-1m-*.csv")) {
            Write-Host "ERROR: Failed to download full dataset" -ForegroundColor Red
            exit 1
        }
    }
} else {
    Write-Host "`n=== STEP 1: SKIPPED (download) ===" -ForegroundColor Gray
}

# ─── STEP 1b: Convert CSV to Parquet ──────────────────────────────────────────
if (-not $OnlyBacktest -and -not $SkipBuild) {
    if (-not (Test-Path $fullParquet)) {
        Convert-CsvToParquet $fullDir $fullParquet
    } else {
        Write-Host "Full Parquet already exists, skipping conversion..." -ForegroundColor Gray
    }
} else {
    Write-Host "Parquet build skipped..." -ForegroundColor Gray
}

# ─── STEP 2: Generate user_regime_periods.json ────────────────────────────────
if (-not $OnlyBacktest) {
    Write-Host "`n=== STEP 2: Generate user_regime_periods.json ===" -ForegroundColor Cyan
    $jsonPeriods = @()
    foreach ($p in $regimePeriods) {
        $jsonPeriods += @{
            regime = $p.Regime
            start = $p.Start
            end_exclusive = $p.End
        }
    }
    $jsonContent = @{
        periods = $jsonPeriods
    } | ConvertTo-Json -Depth 3
    [System.IO.File]::WriteAllText($regimeJson, $jsonContent, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Generated $regimeJson with $($jsonPeriods.Count) periods" -ForegroundColor Green
}

# ─── STEP 3: Compute Features (one-time build with cache) ─────────────────────
if (-not $OnlyBacktest -and -not $SkipBuild) {
    Write-Host "`n=== STEP 3: Compute Features ($StartDate ~ $EndDate, one-time) ===" -ForegroundColor Cyan
    Write-Host "  This computes all features for the entire period and caches the result." -ForegroundColor Yellow
    $env:PYTHONUNBUFFERED = 1
    & $VenvPython -u -m btcusdt_quant train `
        --input $fullParquet `
        --use-user-regime `
        --user-regime-file $regimeJson `
        --output $modelDir `
        --cache-path $cachePath `
        --training-start $StartDate `
        --only-build
    $env:PYTHONUNBUFFERED = 0
    if ($LASTEXITCODE -ne 0) { throw "Feature build failed" }
}

# ─── STEP 4: Train on FULL dataset with Regimes ───────────────────────────────
if (-not $OnlyBacktest -and -not $SkipBuild) {
    Write-Host "`n=== STEP 4: Train on FULL dataset ($StartDate ~ $EndDate) with Regimes ===" -ForegroundColor Cyan
    Write-Host "  Full-period training (50-week warmup auto-excluded)" -ForegroundColor Yellow
    $env:PYTHONUNBUFFERED = 1
    & $VenvPython -u -m btcusdt_quant train `
        --input $fullParquet `
        --use-user-regime `
        --user-regime-file $regimeJson `
        --output $modelDir `
        --cache-path $cachePath `
        --training-start $StartDate
    $env:PYTHONUNBUFFERED = 0
    if ($LASTEXITCODE -ne 0) { throw "Training failed" }
}

# ─── STEP 5: Backtest on 2025 H2 (Jul-Dec) ────────────────────────────────────
Write-Host "`n=== STEP 5: Backtest on $BacktestStart ~ $EndDate ===" -ForegroundColor Cyan
Write-Host "  Backtest period: $BacktestStart ~ $EndDate" -ForegroundColor Yellow
& $VenvPython -m btcusdt_quant backtest `
    --input $fullParquet `
    --model-artifact $modelDir `
    --user-regime-file $regimeJson `
    --backtest-start $BacktestStart `
    --cache-path $cachePath `
    --output $backtestDir
if ($LASTEXITCODE -ne 0) { throw "Backtest failed" }

Write-Host "`n=== DONE ===" -ForegroundColor Cyan
Write-Host "Training model: $modelDir" -ForegroundColor Green
Write-Host "Backtest results: $backtestDir" -ForegroundColor Green
Write-Host "Dataset cache: $cachePath" -ForegroundColor Green
Write-Host "Regime config: $regimeJson" -ForegroundColor Green
