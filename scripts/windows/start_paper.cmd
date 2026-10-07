@echo off
rem Starts paper collector and dashboard hidden, each under a restart loop. Copy or link into shell:startup.
set ROOT=%~dp0..\..
start "" /min powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%ROOT%\scripts\windows\paper_supervisor.ps1" -Script scripts\paper_run.py -Log paper_run
start "" /min powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%ROOT%\scripts\windows\paper_supervisor.ps1" -Script scripts\paper_dashboard.py -Log dashboard
rem R2-48 catalog books and live PatchTST predictions (5-minute cycle, weekly retrain on GPU).
start "" /min powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%ROOT%\scripts\windows\paper_supervisor.ps1" -Script scripts\paper_catalog.py -Log catalog
rem Public Quick Tunnel for the dashboard; each new URL is sent to Telegram.
start "" /min powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "%ROOT%\scripts\windows\paper_supervisor.ps1" -Script scripts\paper_tunnel.py -Log tunnel
