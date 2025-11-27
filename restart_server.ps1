#!/usr/bin/env pwsh
# Restart Flask server

Write-Host "Stopping Flask server..." -ForegroundColor Yellow

# Kill any running Python processes with run.py
Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*KTPM-BTL*" -or $_.CommandLine -like "*run.py*"
} | ForEach-Object {
    Write-Host "  Stopping process $($_.Id)..." -ForegroundColor Gray
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1

Write-Host "`nStarting Flask server..." -ForegroundColor Green
Write-Host "  URL: http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host "  Swagger: http://127.0.0.1:5000/apidocs" -ForegroundColor Cyan
Write-Host "`nPress Ctrl+C to stop`n" -ForegroundColor Yellow

# Activate venv and run
& "$PSScriptRoot\venv\Scripts\Activate.ps1"
python run.py
