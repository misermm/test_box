@echo off
cd /d "%~dp0"

echo ========================================
echo     Create Venv ^& Install Deps
echo ========================================
echo.

echo [1/3] Creating virtual environment...
python -m venv .venv
if %ERRORLEVEL% ne 0 (
    echo Failed to create venv!
    pause
    exit /b 1
)

echo [2/3] Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip

echo [3/3] Installing dependencies...
.venv\Scripts\pip.exe install -r requirements.txt

if %ERRORLEVEL% ne 0 (
    echo Failed to install dependencies!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup complete!
echo Use: .venv\Scripts\python.exe toolbox.py
echo ========================================
echo.
pause
