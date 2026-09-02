# Build Test Toolbox
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       Build Test Toolbox" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Checking models..." -ForegroundColor Yellow
if (-not (Test-Path "models")) {
    Write-Host "  models/ not found, downloading..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "models" -Force | Out-Null
    & ".venv\Scripts\python.exe" download_models.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Model download failed!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
} elseif (-not (Test-Path "models\official_models\SLANet_plus\inference.yml")) {
    Write-Host "  models incomplete, downloading..." -ForegroundColor Yellow
    & ".venv\Scripts\python.exe" download_models.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Model download failed!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "  models OK" -ForegroundColor Green
}

Write-Host "[2/3] Stopping running exe..." -ForegroundColor Yellow
$null = taskkill /F /IM TestToolbox.exe 2>$null
Start-Sleep -Seconds 2

Write-Host "[3/3] Building exe (spec file + incremental cache)..." -ForegroundColor Yellow
if (Test-Path "build\TestToolbox\TestToolbox.pkg") {
    if (-not (Test-Path "build\TestToolbox\PYZ-00.pyz")) {
        Write-Host "  Stale incremental cache detected, cleaning build/..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue
    }
}
& ".venv\Scripts\python.exe" -m PyInstaller TestToolbox.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Build complete!" -ForegroundColor Green
Write-Host "Output: dist\TestToolbox.exe" -ForegroundColor Green
Write-Host "Note: single-file exe, models bundled, extract to .\cache at runtime, keep build/ for faster rebuilds" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Explorer "dist"
Read-Host "Press Enter to exit"