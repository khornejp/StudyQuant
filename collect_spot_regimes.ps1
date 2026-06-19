# BTCUSDT Spot Data Collection - Selective Regime Periods (Windows PowerShell)
# Downloads ONLY key regime periods from 2017-2024 to reduce volume

$ErrorActionPreference = "Stop"

$BASE_URL = "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m"

function Download-Period {
    param(
        [string]$Label,
        [string]$StartDate,  # YYYY-MM-DD
        [string]$EndDate,    # YYYY-MM-DD
        [string]$OutputDir
    )
    
    Write-Host "[$Label] Downloading $StartDate ~ $EndDate ..." -ForegroundColor Yellow
    
    $start = [DateTime]::ParseExact($StartDate, "yyyy-MM-dd", $null)
    $end = [DateTime]::ParseExact($EndDate, "yyyy-MM-dd", $null)
    $current = $start
    
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    
    $downloaded = 0
    $failed = 0
    
    while ($current -le $end) {
        $dateStr = $current.ToString("yyyy-MM-dd")
        $zipName = "BTCUSDT-1m-$dateStr.zip"
        $csvName = "BTCUSDT-1m-$dateStr.csv"
        $url = "$BASE_URL/$zipName"
        $zipPath = "$OutputDir/$zipName"
        $csvPath = "$OutputDir/$csvName"
        
        if (Test-Path $csvPath) {
            # Already extracted
            $current = $current.AddDays(1)
            continue
        }
        
        try {
            # Download
            if (-not (Test-Path $zipPath)) {
                Invoke-WebRequest -Uri $url -OutFile $zipPath -TimeoutSec 30
            }
            # Extract
            Expand-Archive -Path $zipPath -DestinationPath $OutputDir -Force
            Remove-Item $zipPath
            $downloaded++
        }
        catch {
            $failed++
            Write-Host "  Failed: $dateStr" -ForegroundColor Red
        }
        
        $current = $current.AddDays(1)
        
        # Progress every 30 days
        if ($downloaded % 30 -eq 0 -and $downloaded -gt 0) {
            Write-Host "  Progress: $downloaded days downloaded, $failed failed" -ForegroundColor Gray
        }
    }
    
    Write-Host "  Complete: $downloaded days, $failed failed" -ForegroundColor Green
}

# ============================================================================
# REGIME PERIODS (User-specified trend periods)
# ============================================================================

Write-Host "=== BTCUSDT Spot 2020+ Regime Collection ===" -ForegroundColor Cyan
Write-Host "Collecting regime periods from 2020-2024 only" -ForegroundColor Gray
Write-Host ""

# UPTREND periods (2020+)
Download-Period -Label "UPTREND 2020" -StartDate "2020-03-01" -EndDate "2021-04-30" -OutputDir "artifacts/spot_up_2020"
Download-Period -Label "UPTREND 2021" -StartDate "2021-07-01" -EndDate "2021-11-30" -OutputDir "artifacts/spot_up_2021"
Download-Period -Label "UPTREND 2023" -StartDate "2023-03-01" -EndDate "2024-03-31" -OutputDir "artifacts/spot_up_2023"
Download-Period -Label "UPTREND 2024" -StartDate "2024-10-01" -EndDate "2024-12-31" -OutputDir "artifacts/spot_up_2024"

# DOWNTREND periods (2020+)
Download-Period -Label "DOWNTREND 2021" -StartDate "2021-05-01" -EndDate "2021-07-31" -OutputDir "artifacts/spot_down_2021"
Download-Period -Label "DOWNTREND 2022" -StartDate "2021-11-01" -EndDate "2022-11-30" -OutputDir "artifacts/spot_down_2022"

# RANGING periods (2020+)
Download-Period -Label "RANGE 2022-23" -StartDate "2022-12-01" -EndDate "2023-02-28" -OutputDir "artifacts/spot_range_2023"
Download-Period -Label "RANGE 2024" -StartDate "2024-04-01" -EndDate "2024-09-30" -OutputDir "artifacts/spot_range_2024"

# 2025 BACKTEST (unseen data)
Download-Period -Label "BACKTEST 2025" -StartDate "2025-01-01" -EndDate "2025-06-30" -OutputDir "artifacts/spot_backtest_2025"

Write-Host ""
Write-Host "=== Download Complete ===" -ForegroundColor Cyan
Write-Host "Next: Convert CSVs to Parquet" -ForegroundColor Green
