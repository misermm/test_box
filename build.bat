@echo off
cd /d "%~dp0"

echo ========================================
echo        Build Test Toolbox
echo ========================================
echo.

echo [1/3] Cleaning old files...
if exist build rmdir /s /q build
del /q *.spec 2>nul

echo [2/3] Building exe...
python -m PyInstaller --onefile --noconsole --name "TestToolbox" --collect-all PIL --collect-all cv2 --collect-all paddle --collect-all pyclipper --collect-all shapely --collect-all paddlex --add-data "C:\Users\X\AppData\Local\Programs\Python\Python313\Lib\site-packages\paddle\libs;paddle\libs" toolbox.py

if %ERRORLEVEL% ne 0 (
    echo Build failed!
    pause
    exit /b 1
)

echo [3/3] Cleaning temp files...
if exist build rmdir /s /q build
del /q *.spec 2>nul

echo.
echo ========================================
echo Build complete!
echo Output: dist\TestToolbox.exe
echo ========================================
echo.

explorer dist
pause