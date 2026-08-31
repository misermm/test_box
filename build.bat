@echo off
cd /d "%~dp0"

echo ========================================
echo        Build Test Toolbox
echo ========================================
echo.

echo [1/4] Checking models...
if not exist models (
    echo   models/ not found, downloading...
    mkdir models
    .venv\Scripts\python.exe download_models.py
    if %ERRORLEVEL% neq 0 (
        echo Model download failed!
        pause
        exit /b 1
    )
) else (
    if not exist models\official_models\SLANet_plus\inference.yml (
        echo   models incomplete, downloading...
        .venv\Scripts\python.exe download_models.py
        if %ERRORLEVEL% neq 0 (
            echo Model download failed!
            pause
            exit /b 1
        )
    ) else (
        echo   models OK
    )
)

echo [2/4] Cleaning old files...
if exist build rmdir /s /q build
del /q *.spec 2>nul

echo [3/4] Building exe...
.venv\Scripts\python.exe -m PyInstaller --onefile --noconsole --name "TestToolbox" --icon icon.ico --version-file version.txt --collect-all PIL --collect-all cv2 --collect-all paddle --collect-all pyclipper --collect-all shapely --collect-all paddlex --add-data ".venv\Lib\site-packages\paddle\libs;paddle\libs" --add-data "models;models" toolbox.py

if %ERRORLEVEL% neq 0 (
    echo Build failed!
    pause
    exit /b 1
)

echo [4/4] Cleaning temp files...
if exist build rmdir /s /q build
del /q *.spec 2>nul

echo.
echo ========================================
echo Build complete!
echo Output: dist\TestToolbox.exe
echo Note: 单文件可直接运行，模型已内置；启动时自动检查模型更新（失败则用内置模型）
echo ========================================
echo.

explorer dist
pause