@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo        打包测试工具箱
echo ========================================
echo.

echo [1/3] 清理旧文件...
if exist build rmdir /s /q build
if exist *.spec del /q *.spec

echo [2/3] 开始打包...
python -m PyInstaller --onefile --noconsole --name "测试工具箱" --collect-all PIL toolbox.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo 打包失败！请检查错误信息。
    pause
    exit /b 1
)

echo [3/3] 清理临时文件...
if exist build rmdir /s /q build
if exist *.spec del /q *.spec

echo.
echo ========================================
echo 打包完成！
echo 输出文件: dist\测试工具箱.exe
echo ========================================
echo.

explorer dist
pause