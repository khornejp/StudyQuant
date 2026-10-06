@echo off
rem Starts paper collector and dashboard hidden, each under a restart loop. Copy or link into shell:startup.
set ROOT=%~dp0..\..
start "" /min powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%ROOT%\scripts\windows\paper_supervisor.ps1" -Script scripts\paper_run.py -Log paper_run
start "" /min powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%ROOT%\scripts\windows\paper_supervisor.ps1" -Script scripts\paper_dashboard.py -Log dashboard
