@echo off
cd /d "%~dp0"
echo ========================================
echo   Build Test Toolbox (onedir, instant start)
echo ========================================
echo.
.venv\Scripts\python.exe -m PyInstaller ^
  --onedir --noconsole --noconfirm ^
  --name "TestToolbox" ^
  --distpath dist_onedir --workpath build --specpath . ^
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
echo Build complete! Output: dist_onedir\TestToolbox\TestToolbox.exe
explorer dist_onedir\TestToolbox
pause
