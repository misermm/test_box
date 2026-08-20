# 打包测试工具箱为exe文件
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       打包测试工具箱" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "[1/3] 清理旧文件..." -ForegroundColor Yellow
if (Test-Path "$ScriptDir\build") { Remove-Item -Recurse -Force "$ScriptDir\build" }
Get-ChildItem "$ScriptDir\*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host "[2/3] 开始打包..." -ForegroundColor Yellow
& python -m PyInstaller --onefile --noconsole --name "测试工具箱" --collect-all PIL "$ScriptDir\toolbox.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "打包失败！" -ForegroundColor Red
    Read-Host "按Enter键退出"
    exit 1
}

Write-Host "[3/3] 清理临时文件..." -ForegroundColor Yellow
if (Test-Path "$ScriptDir\build") { Remove-Item -Recurse -Force "$ScriptDir\build" }
Get-ChildItem "$ScriptDir\*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "打包完成！" -ForegroundColor Green
Write-Host "输出文件: dist\测试工具箱.exe" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Explorer "$ScriptDir\dist"
Read-Host "按Enter键退出"