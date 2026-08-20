@echo off
chcp 65001 >nul

echo ========================================
echo        Generate File Tool
echo ========================================
echo.

set /p size="Enter file size (MB): "
set /p ext="Enter file type (zip/bin): "

if "%ext%"=="bin" (
    set typ=plain
) else (
    set typ=zip
)

echo.
echo Generating %size%MB %ext% file...
python "%~dp0generate_file.py" -s %size% -o "%~dp0data\file_%size%.%ext%" -t %typ%

echo.
pause