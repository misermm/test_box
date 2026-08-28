# Setup Venv & Install Deps
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "    Create Venv & Install Deps" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Creating virtual environment..." -ForegroundColor Yellow
& python -m venv .venv

Write-Host "[2/3] Upgrading pip..." -ForegroundColor Yellow
& ".venv\Scripts\python.exe" -m pip install --upgrade pip

Write-Host "[3/3] Installing dependencies..." -ForegroundColor Yellow
& ".venv\Scripts\pip.exe" install -r requirements.txt

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "Use: .venv\Scripts\python.exe toolbox.py" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Read-Host "Press Enter to exit"
