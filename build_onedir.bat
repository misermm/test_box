@echo off
cd /d "%~dp0"
echo ========================================
echo   Build Test Toolbox (onedir, instant start)
echo ========================================
echo.

echo [1/3] Checking models...
if not exist models (
    echo   models/ not found, downloading...
    mkdir models
    .venv\Scripts\python.exe download_models.py
    if errorlevel 1 (
        echo Model download failed!
        pause
        exit /b 1
    )
) else (
    if not exist models\official_models\SLANet_plus\inference.yml (
        echo   models incomplete, downloading...
        .venv\Scripts\python.exe download_models.py
        if errorlevel 1 (
            echo Model download failed!
            pause
            exit /b 1
        )
    ) else (
        echo   models OK
    )
)

echo [2/3] Stopping running TestToolbox.exe if any...
taskkill /F /IM TestToolbox.exe >nul 2>&1
timeout /t 2 /nobreak >nul
taskkill /F /IM TestToolbox.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [3/3] Building onedir (spec file + incremental cache)...
if exist build\TestToolbox\TestToolbox.pkg if not exist build\TestToolbox\PYZ-00.pyz (
    echo   Stale incremental cache detected, cleaning build/...
    rmdir /s /q build
)
.venv\Scripts\python.exe -m PyInstaller TestToolbox.spec --noconfirm --distpath dist_onedir
if errorlevel 1 (
    echo Build failed!
    pause
    exit /b 1
)
echo Build complete! Output: dist_onedir\TestToolbox\TestToolbox.exe
explorer dist_onedir\TestToolbox
pause
