# Keeps one paper process alive: restarts it 60 s after any exit. Usage: -Script scripts\paper_run.py -Log paper_run
param([string]$Script, [string]$Log)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$py = Join-Path $root 'venv_btcusdt\Scripts\python.exe'
while ($true) {
    "$(Get-Date -Format o) start $Script" | Out-File -Encoding utf8 -Append "artifacts\live\logs\$Log.supervisor.log"
    & $py $Script --config config\paper.toml *>> "artifacts\live\logs\$Log.task.log"
    "$(Get-Date -Format o) exit $LASTEXITCODE" | Out-File -Encoding utf8 -Append "artifacts\live\logs\$Log.supervisor.log"
    Start-Sleep 60
}
