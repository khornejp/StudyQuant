$ErrorActionPreference = "Stop"

$runRoot = "D:\StudyQuant\artifacts\short_quantile_sweep_20260826"
$runStatusPath = Join-Path $runRoot "status.json"
$monitorStatusPath = Join-Path $runRoot "monitor_status.json"
$monitorHistoryPath = Join-Path $runRoot "monitor_history.jsonl"
while ($true) {
    $runStatus = if (Test-Path -LiteralPath $runStatusPath) {
        Get-Content -Raw -LiteralPath $runStatusPath | ConvertFrom-Json
    } else {
        [pscustomobject]@{ state = "unknown"; stage = "unknown"; message = "status.json is missing" }
    }
    $supervisorPid = [int]$runStatus.pid
    $supervisor = Get-Process -Id $supervisorPid -ErrorAction SilentlyContinue
    $logs = @(Get-ChildItem -LiteralPath $runRoot -File -Filter "*.log" -ErrorAction SilentlyContinue)
    $latest = Get-ChildItem -LiteralPath $runRoot -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $monitorState = if ($runStatus.state -in @("complete", "failed")) {
        [string]$runStatus.state
    } elseif ($null -eq $supervisor) {
        "orphaned"
    } else {
        "monitoring"
    }
    $snapshot = [ordered]@{
        monitor_state = $monitorState
        run_state = [string]$runStatus.state
        run_stage = [string]$runStatus.stage
        run_message = [string]$runStatus.message
        supervisor_pid = $supervisorPid
        supervisor_alive = ($null -ne $supervisor)
        log_bytes = [long](($logs | Measure-Object Length -Sum).Sum)
        latest_file = if ($null -eq $latest) { $null } else { $latest.FullName }
        latest_write_at = if ($null -eq $latest) { $null } else { $latest.LastWriteTime.ToString("o") }
        checked_at = (Get-Date).ToString("o")
    }
    $snapshot | ConvertTo-Json | Set-Content -LiteralPath $monitorStatusPath -Encoding UTF8
    ($snapshot | ConvertTo-Json -Compress) | Add-Content -LiteralPath $monitorHistoryPath -Encoding UTF8
    if ($monitorState -in @("complete", "failed", "orphaned")) { break }
    Start-Sleep -Seconds 60
}
