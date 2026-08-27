# Build Test Toolbox
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       Build Test Toolbox" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Cleaning old files..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
Get-ChildItem "*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host "[2/3] Building exe..." -ForegroundColor Yellow
& python -m PyInstaller --onefile --noconsole --name "TestToolbox" --collect-all PIL --collect-all cv2 --collect-all paddle --collect-all pyclipper --collect-all shapely --collect-all paddlex --add-data "C:\Users\X\AppData\Local\Programs\Python\Python313\Lib\site-packages\paddle\libs;paddle\libs" toolbox.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[3/3] Cleaning temp files..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
Get-ChildItem "*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Build complete!" -ForegroundColor Green
Write-Host "Output: dist\TestToolbox.exe" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Explorer "dist"
Read-Host "Press Enter to exit"