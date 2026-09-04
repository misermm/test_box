@echo off
cd /d "%~dp0"

echo ========================================
echo        Build Test Toolbox
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

echo   Stopping running TestToolbox.exe if any...
taskkill /F /IM TestToolbox.exe >nul 2>&1
timeout /t 2 /nobreak >nul
taskkill /F /IM TestToolbox.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo [2/3] Building exe (spec file + incremental cache)...
if exist build\TestToolbox\TestToolbox.pkg if not exist build\TestToolbox\PYZ-00.pyz (
    echo   Stale incremental cache detected, cleaning build/...
    rmdir /s /q build
)
.venv\Scripts\python.exe -m PyInstaller TestToolbox.spec --noconfirm
if errorlevel 1 (
    echo Build failed!
    pause
    exit /b 1
)

echo [3/3] Done!
echo.
echo ========================================
echo Build complete!
echo Output: dist\TestToolbox.exe
echo Note: single-file exe, models bundled, extract to .\cache at runtime, keep build/ for faster rebuilds
echo ========================================
echo.

explorer dist
pause