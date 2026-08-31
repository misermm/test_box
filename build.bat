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
    if not exist models\official_models\SLANet_plus_infer\inference.yml (
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

echo [2/3] Building exe (onefile + incremental cache)...
.venv\Scripts\python.exe -m PyInstaller ^
  --onefile --noconsole --noconfirm --runtime-tmpdir "cache" ^
  --name "TestToolbox" ^
  --distpath dist --workpath build --specpath . ^
  --icon icon.ico --version-file version.txt ^
  --collect-all PIL --collect-all cv2 ^
  --collect-all paddle --collect-all pyclipper ^
  --collect-all shapely --collect-all paddlex ^
  --add-data ".venv\Lib\site-packages\paddle\libs;paddle\libs" ^
  --add-data "models;models" ^
  toolbox.py

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
