param([switch]$Background, [switch]$Worker)

$ErrorActionPreference = "Stop"
$workspace = "D:\StudyQuant"
$python = Join-Path $workspace "venv_btcusdt\Scripts\python.exe"
$runRoot = Join-Path $workspace "artifacts\short_sequence_experiment_20260826"

if ($Background -and -not $Worker) {
    if (Test-Path -LiteralPath $runRoot) { throw "Refusing to overwrite $runRoot" }
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PSCommandPath, "-Worker"
    ) -WorkingDirectory $workspace -WindowStyle Hidden -PassThru
    Write-Output "started_pid=$($process.Id)"
    Write-Output "status=$runRoot\status.json"
    exit 0
}

Set-Location -LiteralPath $workspace
& $python -m btcusdt_quant.short_sequence *> (Join-Path $workspace "short_sequence_experiment.log")
exit $LASTEXITCODE
