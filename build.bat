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
.venv\Scripts\python.exe -m PyInstaller --onefile --noconsole --name "TestToolbox" --collect-all PIL --collect-all cv2 --collect-all paddle --collect-all pyclipper --collect-all shapely --collect-all paddlex --add-data ".venv\Lib\site-packages\paddle\libs;paddle\libs" toolbox.py

if %ERRORLEVEL% neq 0 (
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
echo Note: exe 需与 models\ 文件夹放在同一目录运行（表格识别本地模型）
echo ========================================
echo.

explorer dist
pause