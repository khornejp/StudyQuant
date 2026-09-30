$ErrorActionPreference = "Stop"
$runRoot = "D:\StudyQuant\artifacts\short_sequence_experiment_20260826"
$statusPath = Join-Path $runRoot "status.json"

while ($true) {
    if (Test-Path -LiteralPath $statusPath) {
        $status = Get-Content -Raw -LiteralPath $statusPath | ConvertFrom-Json
        $status | ConvertTo-Json -Depth 8
        if ($status.state -in @("complete", "stopped_no_edge", "failed")) {
            $log = "D:\StudyQuant\short_sequence_experiment.log"
            if (-not (Test-Path -LiteralPath $log)) { throw "terminal status has no log: $log" }
            exit $(if ($status.state -eq "failed") { 1 } else { 0 })
        }
    } else {
        Write-Output "waiting_for_status=$statusPath"
    }
    Start-Sleep -Seconds 60
}
