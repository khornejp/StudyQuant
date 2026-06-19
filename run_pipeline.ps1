# BTCUSDT USD-M Futures Complete Pipeline (Windows PowerShell)
# Step 1: Collect → Step 2: Convert → Step 3: Combine → Step 4: Train → Step 5: Backtest

$ErrorActionPreference = "Stop"

# ============================================================================
# CONFIGURATION
# ============================================================================

$BASE_URL = "https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1m"
$MAX_PARALLEL = 4

# Regime periods (user-specified)
$UP_PERIODS = @(
    @{Start="2020-01-01"; End="2020-02-13"; Dir="artifacts/futures_up_2020_01"},
    @{Start="2020-03-13"; End="2020-05-11"; Dir="artifacts/futures_up_2020_03"},
    @{Start="2020-07-20"; End="2020-09-01"; Dir="artifacts/futures_up_2020_07"},
    @{Start="2020-10-08"; End="2021-01-08"; Dir="artifacts/futures_up_2020_10"},
    @{Start="2021-01-27"; End="2021-04-14"; Dir="artifacts/futures_up_2021_01"},
    @{Start="2021-07-20"; End="2021-09-07"; Dir="artifacts/futures_up_2021_07"},
    @{Start="2021-09-29"; End="2021-11-10"; Dir="artifacts/futures_up_2021_09"},
    @{Start="2022-01-24"; End="2022-03-28"; Dir="artifacts/futures_up_2022_01"},
    @{Start="2023-01-01"; End="2023-02-16"; Dir="artifacts/futures_up_2023_01"},
    @{Start="2023-03-10"; End="2023-04-14"; Dir="artifacts/futures_up_2023_03"},
    @{Start="2023-06-15"; End="2023-07-13"; Dir="artifacts/futures_up_2023_06"},
    @{Start="2023-10-16"; End="2023-12-08"; Dir="artifacts/futures_up_2023_10"},
    @{Start="2024-01-23"; End="2024-03-14"; Dir="artifacts/futures_up_2024_01"},
    @{Start="2024-05-01"; End="2024-06-07"; Dir="artifacts/futures_up_2024_05"},
    @{Start="2024-09-06"; End="2024-10-29"; Dir="artifacts/futures_up_2024_09"},
    @{Start="2024-11-05"; End="2024-12-17"; Dir="artifacts/futures_up_2024_11"}
)

$DOWN_PERIODS = @(
    @{Start="2020-02-13"; End="2020-03-13"; Dir="artifacts/futures_down_2020_02"},
    @{Start="2021-01-08"; End="2021-01-27"; Dir="artifacts/futures_down_2021_01"},
    @{Start="2021-04-14"; End="2021-07-20"; Dir="artifacts/futures_down_2021_04"},
    @{Start="2021-09-07"; End="2021-09-29"; Dir="artifacts/futures_down_2021_09"},
    @{Start="2021-11-10"; End="2022-01-24"; Dir="artifacts/futures_down_2021_11"},
    @{Start="2022-03-28"; End="2022-05-12"; Dir="artifacts/futures_down_2022_03"},
    @{Start="2022-05-12"; End="2022-06-18"; Dir="artifacts/futures_down_2022_05"},
    @{Start="2022-08-15"; End="2022-09-21"; Dir="artifacts/futures_down_2022_08"},
    @{Start="2022-11-05"; End="2022-11-21"; Dir="artifacts/futures_down_2022_11"},
    @{Start="2023-02-16"; End="2023-03-10"; Dir="artifacts/futures_down_2023_02"},
    @{Start="2023-07-13"; End="2023-09-11"; Dir="artifacts/futures_down_2023_07"},
    @{Start="2024-01-01"; End="2024-01-23"; Dir="artifacts/futures_down_2024_01"},
    @{Start="2024-03-14"; End="2024-05-01"; Dir="artifacts/futures_down_2024_03"},
    @{Start="2024-06-07"; End="2024-08-05"; Dir="artifacts/futures_down_2024_06"},
    @{Start="2024-12-17"; End="2024-12-31"; Dir="artifacts/futures_down_2024_12"}
)

$RANGE_PERIODS = @(
    @{Start="2020-05-11"; End="2020-07-20"; Dir="artifacts/futures_range_2020_05"},
    @{Start="2020-09-01"; End="2020-10-08"; Dir="artifacts/futures_range_2020_09"},
    @{Start="2022-06-18"; End="2022-08-15"; Dir="artifacts/futures_range_2022_06"},
    @{Start="2022-09-21"; End="2022-11-05"; Dir="artifacts/futures_range_2022_09"},
    @{Start="2022-11-21"; End="2022-12-31"; Dir="artifacts/futures_range_2022_11"},
    @{Start="2023-04-14"; End="2023-06-15"; Dir="artifacts/futures_range_2023_04"},
    @{Start="2023-09-11"; End="2023-10-16"; Dir="artifacts/futures_range_2023_09"},
    @{Start="2023-12-08"; End="2023-12-31"; Dir="artifacts/futures_range_2023_12"},
    @{Start="2024-08-05"; End="2024-09-06"; Dir="artifacts/futures_range_2024_08"}
)

$BACKTEST_PERIOD = @{Start="2025-01-01"; End="2025-06-30"; Dir="artifacts/futures_backtest_2025"}

# ============================================================================
# STEP 1: DOWNLOAD DATA
# ============================================================================

function Download-Period {
    param([string]$Label, [string]$StartDate, [string]$EndDate, [string]$OutputDir)
    
    Write-Host "[$Label] $StartDate ~ $EndDate" -ForegroundColor Yellow
    
    $job = Start-Job -ScriptBlock {
        param($BASE_URL, $StartDate, $EndDate, $OutputDir)
        $start = [DateTime]::ParseExact($StartDate, "yyyy-MM-dd", $null)
        $end = [DateTime]::ParseExact($EndDate, "yyyy-MM-dd", $null)
        $current = $start
        New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
        $downloaded = 0; $failed = 0
        
        while ($current -le $end) {
            $dateStr = $current.ToString("yyyy-MM-dd")
            $zipName = "BTCUSDT-1m-$dateStr.zip"
            $csvName = "BTCUSDT-1m-$dateStr.csv"
            $url = "$BASE_URL/$zipName"
            $zipPath = "$OutputDir/$zipName"
            $csvPath = "$OutputDir/$csvName"
            
            if (Test-Path $csvPath) { $current = $current.AddDays(1); continue }
            
            try {
                if (-not (Test-Path $zipPath)) {
                    Invoke-WebRequest -Uri $url -OutFile $zipPath -TimeoutSec 30
                }
                Expand-Archive -Path $zipPath -DestinationPath $OutputDir -Force
                Remove-Item $zipPath
                $downloaded++
            } catch { $failed++ }
            $current = $current.AddDays(1)
        }
        return @{Downloaded=$downloaded; Failed=$failed}
    } -ArgumentList $BASE_URL, $StartDate, $EndDate, $OutputDir
    
    return $job
}

function Wait-Jobs {
    param([array]$Jobs, [int]$MaxParallel)
    $running = $Jobs
    while ($running.Count -gt 0) {
        $finished = $running | Where-Object { $_.State -ne 'Running' }
        foreach ($f in $finished) {
            $result = Receive-Job -Job $f
            Write-Host "  Complete: $($result.Downloaded) days, $($result.Failed) failed" -ForegroundColor Green
            $running = $running | Where-Object { $_ -ne $f }
        }
        if ($running.Count -ge $MaxParallel) { Start-Sleep -Seconds 1 }
    }
    Get-Job | Remove-Job
}

Write-Host ""
Write-Host "=== STEP 1: Downloading Futures Data ===" -ForegroundColor Cyan
Write-Host ""

$allJobs = @()
foreach ($p in $UP_PERIODS) { $allJobs += Download-Period -Label "UP" -StartDate $p.Start -EndDate $p.End -OutputDir $p.Dir }
foreach ($p in $DOWN_PERIODS) { $allJobs += Download-Period -Label "DN" -StartDate $p.Start -EndDate $p.End -OutputDir $p.Dir }
foreach ($p in $RANGE_PERIODS) { $allJobs += Download-Period -Label "RG" -StartDate $p.Start -EndDate $p.End -OutputDir $p.Dir }
$allJobs += Download-Period -Label "BT" -StartDate $BACKTEST_PERIOD.Start -EndDate $BACKTEST_PERIOD.End -OutputDir $BACKTEST_PERIOD.Dir

Wait-Jobs -Jobs $allJobs -MaxParallel $MAX_PARALLEL

# ============================================================================
# STEP 2: CONVERT CSV → PARQUET
# ============================================================================

Write-Host ""
Write-Host "=== STEP 2: Converting CSV to Parquet ===" -ForegroundColor Cyan
Write-Host ""

$convertScript = @"
import glob, pyarrow.csv as pv, pyarrow.parquet as pq, pyarrow as pa, sys, os

def convert_dir(csv_dir, parquet_path):
    files = sorted(glob.glob(f'{csv_dir}/*.csv'))
    if not files:
        print(f'  Skip (no CSV): {csv_dir}')
        return
    tables = [pv.read_csv(f) for f in files]
    combined = pa.concat_tables(tables)
    
    # Rename columns
    old_names = combined.column_names
    new_names = []
    for name in old_names:
        if name == 'count': new_names.append('number_of_trades')
        elif name == 'taker_buy_volume': new_names.append('taker_buy_base_volume')
        else: new_names.append(name)
    combined = combined.rename_columns(new_names)
    
    # Drop close_time and ignore
    keep = [n for n in new_names if n not in ('close_time', 'ignore')]
    combined = combined.select(keep)
    
    pq.write_table(combined, parquet_path)
    print(f'  {combined.num_rows} rows -> {parquet_path}')

periods = sys.argv[1:]
for period_str in periods:
    parts = period_str.split('|')
    csv_dir = parts[0]
    parquet_path = parts[1]
    convert_dir(csv_dir, parquet_path)
"@

$convertScript | Out-File -FilePath "_convert.py" -Encoding utf8

$allPeriodsStr = @()
foreach ($p in $UP_PERIODS) { $allPeriodsStr += "$($p.Dir)|$($p.Dir).parquet" }
foreach ($p in $DOWN_PERIODS) { $allPeriodsStr += "$($p.Dir)|$($p.Dir).parquet" }
foreach ($p in $RANGE_PERIODS) { $allPeriodsStr += "$($p.Dir)|$($p.Dir).parquet" }
$allPeriodsStr += "$($BACKTEST_PERIOD.Dir)|$($BACKTEST_PERIOD.Dir).parquet"

python _convert.py @allPeriodsStr
Remove-Item "_convert.py"

# ============================================================================
# STEP 3: COMBINE BY REGIME
# ============================================================================

Write-Host ""
Write-Host "=== STEP 3: Combining by Regime ===" -ForegroundColor Cyan
Write-Host ""

$combineScript = @"
import pyarrow.parquet as pq
import pyarrow as pa
import glob
import sys

def combine_parquet_files(pattern, output_path):
    files = sorted(glob.glob(pattern))
    if not files:
        print(f'No files found: {pattern}')
        return
    tables = [pq.read_table(f) for f in files]
    combined = pa.concat_tables(tables)
    pq.write_table(combined, output_path)
    print(f'Combined {len(files)} files -> {combined.num_rows} rows -> {output_path}')

# Combine by regime type
combine_parquet_files('artifacts/futures_up_*.parquet', 'artifacts/training_up.parquet')
combine_parquet_files('artifacts/futures_down_*.parquet', 'artifacts/training_down.parquet')
combine_parquet_files('artifacts/futures_range_*.parquet', 'artifacts/training_range.parquet')

# Combine all for training
all_train_files = sorted(glob.glob('artifacts/training_up.parquet') + 
                          glob.glob('artifacts/training_down.parquet') + 
                          glob.glob('artifacts/training_range.parquet'))
if all_train_files:
    tables = [pq.read_table(f) for f in all_train_files]
    combined = pa.concat_tables(tables)
    pq.write_table(combined, 'artifacts/training_combined.parquet')
    print(f'Final training set: {combined.num_rows} rows')
"@

$combineScript | Out-File -FilePath "_combine.py" -Encoding utf8
python _combine.py
Remove-Item "_combine.py"

# ============================================================================
# STEP 4: TRAIN REGIME-AWARE STACKING ENSEMBLE
# ============================================================================

Write-Host ""
Write-Host "=== STEP 4: Training Regime-Aware Stacking Ensemble ===" -ForegroundColor Cyan
Write-Host "  This will take 30-60 minutes..." -ForegroundColor Gray
Write-Host ""

python -m btcusdt_quant train `
    --input artifacts/training_combined.parquet `
    --ensemble `
    --regime-aware `
    --output artifacts/regime_stacking_model

Write-Host ""
Write-Host "  Training complete!" -ForegroundColor Green

# ============================================================================
# STEP 5: BACKTEST ON 2025 DATA
# ============================================================================

Write-Host ""
Write-Host "=== STEP 5: Backtesting on 2025 Data ===" -ForegroundColor Cyan
Write-Host ""

python -m btcusdt_quant backtest `
    --input artifacts/futures_backtest_2025.parquet `
    --model-artifact artifacts/regime_stacking_model `
    --output artifacts/backtest_results

# ============================================================================
# COMPLETE
# ============================================================================

Write-Host ""
Write-Host "=== Pipeline Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Artifacts:" -ForegroundColor Green
Write-Host "  Model: artifacts/regime_stacking_model/" -ForegroundColor Green
Write-Host "  Backtest: artifacts/backtest_results/" -ForegroundColor Green
Write-Host "  Training Data: artifacts/training_combined.parquet" -ForegroundColor Green
Write-Host ""
Write-Host "View results:" -ForegroundColor Gray
Write-Host "  Get-Content artifacts/backtest_results/run_summary.json" -ForegroundColor Gray
Write-Host "  Get-Content artifacts/regime_stacking_model/run_summary.json" -ForegroundColor Gray
