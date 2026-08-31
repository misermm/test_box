# Build Test Toolbox
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       Build Test Toolbox" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] Checking models..." -ForegroundColor Yellow
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

Write-Host "[2/4] Cleaning old files..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
Get-ChildItem "*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host "[3/4] Building exe..." -ForegroundColor Yellow
& ".venv\Scripts\python.exe" -m PyInstaller --onefile --noconsole --name "TestToolbox" --icon icon.ico --version-file version.txt --collect-all PIL --collect-all cv2 --collect-all paddle --collect-all pyclipper --collect-all shapely --collect-all paddlex --add-data ".venv\Lib\site-packages\paddle\libs;paddle\libs" --add-data "models;models" toolbox.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[4/4] Cleaning temp files..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
Get-ChildItem "*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Build complete!" -ForegroundColor Green
Write-Host "Output: dist\TestToolbox.exe" -ForegroundColor Green
Write-Host "Note: 单文件可直接运行，模型已内置；启动时自动检查模型更新（失败则用内置模型）" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Explorer "dist"
Read-Host "Press Enter to exit"