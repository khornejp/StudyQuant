# BTCUSDT USD-M Futures Data Collection - Detailed Regime Periods 2020-2024 (Windows PowerShell)
# Supports parallel downloads for speed

$ErrorActionPreference = "Stop"

$BASE_URL = "https://data.binance.vision/data/futures/um/daily/klines/BTCUSDT/1m"
$MAX_PARALLEL = 4  # 동시 다운로드 수

function Download-Period {
    param(
        [string]$Label,
        [string]$StartDate,
        [string]$EndDate,
        [string]$OutputDir
    )
    
    Write-Host "[$Label] Queueing $StartDate ~ $EndDate ..." -ForegroundColor Yellow
    
    # Start download in background job
    $job = Start-Job -ScriptBlock {
        param($BASE_URL, $StartDate, $EndDate, $OutputDir, $Label)
        
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
                $current = $current.AddDays(1)
                continue
            }
            
            try {
                if (-not (Test-Path $zipPath)) {
                    Invoke-WebRequest -Uri $url -OutFile $zipPath -TimeoutSec 30
                }
                Expand-Archive -Path $zipPath -DestinationPath $OutputDir -Force
                Remove-Item $zipPath
                $downloaded++
            }
            catch {
                $failed++
            }
            
            $current = $current.AddDays(1)
        }
        
        return @{Label=$Label; Downloaded=$downloaded; Failed=$failed}
    } -ArgumentList $BASE_URL, $StartDate, $EndDate, $OutputDir, $Label
    
    return $job
}

Write-Host "=== BTCUSDT USD-M Futures Detailed Regime Collection (2020-2024) ===" -ForegroundColor Cyan
Write-Host "Using parallel downloads (max $MAX_PARALLEL concurrent)" -ForegroundColor Gray
Write-Host ""

$allPeriods = @(
    # UPTREND
    @{Label="UP 2020-01"; Start="2020-01-01"; End="2020-02-13"; Dir="artifacts/futures_up_2020_01"},
    @{Label="UP 2020-03"; Start="2020-03-13"; End="2020-05-11"; Dir="artifacts/futures_up_2020_03"},
    @{Label="UP 2020-07"; Start="2020-07-20"; End="2020-09-01"; Dir="artifacts/futures_up_2020_07"},
    @{Label="UP 2020-10"; Start="2020-10-08"; End="2021-01-08"; Dir="artifacts/futures_up_2020_10"},
    @{Label="UP 2021-01"; Start="2021-01-27"; End="2021-04-14"; Dir="artifacts/futures_up_2021_01"},
    @{Label="UP 2021-07"; Start="2021-07-20"; End="2021-09-07"; Dir="artifacts/futures_up_2021_07"},
    @{Label="UP 2021-09"; Start="2021-09-29"; End="2021-11-10"; Dir="artifacts/futures_up_2021_09"},
    @{Label="UP 2022-01"; Start="2022-01-24"; End="2022-03-28"; Dir="artifacts/futures_up_2022_01"},
    @{Label="UP 2023-01"; Start="2023-01-01"; End="2023-02-16"; Dir="artifacts/futures_up_2023_01"},
    @{Label="UP 2023-03"; Start="2023-03-10"; End="2023-04-14"; Dir="artifacts/futures_up_2023_03"},
    @{Label="UP 2023-06"; Start="2023-06-15"; End="2023-07-13"; Dir="artifacts/futures_up_2023_06"},
    @{Label="UP 2023-10"; Start="2023-10-16"; End="2023-12-08"; Dir="artifacts/futures_up_2023_10"},
    @{Label="UP 2024-01"; Start="2024-01-23"; End="2024-03-14"; Dir="artifacts/futures_up_2024_01"},
    @{Label="UP 2024-05"; Start="2024-05-01"; End="2024-06-07"; Dir="artifacts/futures_up_2024_05"},
    @{Label="UP 2024-09"; Start="2024-09-06"; End="2024-10-29"; Dir="artifacts/futures_up_2024_09"},
    @{Label="UP 2024-11"; Start="2024-11-05"; End="2024-12-17"; Dir="artifacts/futures_up_2024_11"},
    
    # DOWNTREND
    @{Label="DN 2020-02"; Start="2020-02-13"; End="2020-03-13"; Dir="artifacts/futures_down_2020_02"},
    @{Label="DN 2021-01"; Start="2021-01-08"; End="2021-01-27"; Dir="artifacts/futures_down_2021_01"},
    @{Label="DN 2021-04"; Start="2021-04-14"; End="2021-07-20"; Dir="artifacts/futures_down_2021_04"},
    @{Label="DN 2021-09"; Start="2021-09-07"; End="2021-09-29"; Dir="artifacts/futures_down_2021_09"},
    @{Label="DN 2021-11"; Start="2021-11-10"; End="2022-01-24"; Dir="artifacts/futures_down_2021_11"},
    @{Label="DN 2022-03"; Start="2022-03-28"; End="2022-05-12"; Dir="artifacts/futures_down_2022_03"},
    @{Label="DN 2022-05"; Start="2022-05-12"; End="2022-06-18"; Dir="artifacts/futures_down_2022_05"},
    @{Label="DN 2022-08"; Start="2022-08-15"; End="2022-09-21"; Dir="artifacts/futures_down_2022_08"},
    @{Label="DN 2022-11"; Start="2022-11-05"; End="2022-11-21"; Dir="artifacts/futures_down_2022_11"},
    @{Label="DN 2023-02"; Start="2023-02-16"; End="2023-03-10"; Dir="artifacts/futures_down_2023_02"},
    @{Label="DN 2023-07"; Start="2023-07-13"; End="2023-09-11"; Dir="artifacts/futures_down_2023_07"},
    @{Label="DN 2024-01"; Start="2024-01-01"; End="2024-01-23"; Dir="artifacts/futures_down_2024_01"},
    @{Label="DN 2024-03"; Start="2024-03-14"; End="2024-05-01"; Dir="artifacts/futures_down_2024_03"},
    @{Label="DN 2024-06"; Start="2024-06-07"; End="2024-08-05"; Dir="artifacts/futures_down_2024_06"},
    @{Label="DN 2024-12"; Start="2024-12-17"; End="2024-12-31"; Dir="artifacts/futures_down_2024_12"},
    
    # RANGING
    @{Label="RG 2020-05"; Start="2020-05-11"; End="2020-07-20"; Dir="artifacts/futures_range_2020_05"},
    @{Label="RG 2020-09"; Start="2020-09-01"; End="2020-10-08"; Dir="artifacts/futures_range_2020_09"},
    @{Label="RG 2022-06"; Start="2022-06-18"; End="2022-08-15"; Dir="artifacts/futures_range_2022_06"},
    @{Label="RG 2022-09"; Start="2022-09-21"; End="2022-11-05"; Dir="artifacts/futures_range_2022_09"},
    @{Label="RG 2022-11"; Start="2022-11-21"; End="2022-12-31"; Dir="artifacts/futures_range_2022_11"},
    @{Label="RG 2023-04"; Start="2023-04-14"; End="2023-06-15"; Dir="artifacts/futures_range_2023_04"},
    @{Label="RG 2023-09"; Start="2023-09-11"; End="2023-10-16"; Dir="artifacts/futures_range_2023_09"},
    @{Label="RG 2023-12"; Start="2023-12-08"; End="2023-12-31"; Dir="artifacts/futures_range_2023_12"},
    @{Label="RG 2024-08"; Start="2024-08-05"; End="2024-09-06"; Dir="artifacts/futures_range_2024_08"}
)

# Queue all downloads
$jobs = @()
$running = @()
$completed = @()

foreach ($period in $allPeriods) {
    $job = Download-Period -Label $period.Label -StartDate $period.Start -EndDate $period.End -OutputDir $period.Dir
    $jobs += @{Job=$job; Label=$period.Label; Start=$period.Start; End=$period.End}
    $running += $job
    
    # Limit concurrency
    while ($running.Count -ge $MAX_PARALLEL) {
        $finished = $running | Where-Object { $_.State -ne 'Running' }
        foreach ($f in $finished) {
            $result = Receive-Job -Job $f
            Write-Host "  [$($result.Label)] Complete: $($result.Downloaded) days, $($result.Failed) failed" -ForegroundColor Green
            $running = $running | Where-Object { $_ -ne $f }
            $completed += $f
        }
        Start-Sleep -Seconds 1
    }
}

# Wait for remaining
while ($running.Count -gt 0) {
    $finished = $running | Where-Object { $_.State -ne 'Running' }
    foreach ($f in $finished) {
        $result = Receive-Job -Job $f
        Write-Host "  [$($result.Label)] Complete: $($result.Downloaded) days, $($result.Failed) failed" -ForegroundColor Green
        $running = $running | Where-Object { $_ -ne $f }
        $completed += $f
    }
    Start-Sleep -Seconds 1
}

# Cleanup
Get-Job | Remove-Job

Write-Host ""
Write-Host "=== All Downloads Complete ===" -ForegroundColor Cyan
Write-Host "Total periods: $($allPeriods.Count)" -ForegroundColor Green
Write-Host "Next: Convert CSVs to Parquet" -ForegroundColor Gray
