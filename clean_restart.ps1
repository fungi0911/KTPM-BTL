#!/usr/bin/env pwsh
# Clean Python cache and restart

Write-Host "Cleaning Python cache..." -ForegroundColor Yellow

# Remove __pycache__ directories
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | ForEach-Object {
    Write-Host "  Removing $($_.FullName)" -ForegroundColor Gray
    Remove-Item -Path $_.FullName -Recurse -Force
}

# Remove .pyc files
Get-ChildItem -Path . -Recurse -File -Filter "*.pyc" | ForEach-Object {
    Write-Host "  Removing $($_.FullName)" -ForegroundColor Gray
    Remove-Item -Path $_.FullName -Force
}

Write-Host "`n✓ Cache cleaned" -ForegroundColor Green
Write-Host "`nRestarting server...`n" -ForegroundColor Yellow

# Restart server
& "$PSScriptRoot\restart_server.ps1"
