# 生成指定大小文件工具
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       生成指定大小文件工具" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 获取脚本目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataDir = Join-Path $ScriptDir "data"

# 确保data目录存在
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
}

# 预设选项
Write-Host "预设选项:" -ForegroundColor Yellow
Write-Host "  1. 生成101MB的ZIP文件" -ForegroundColor Gray
Write-Host "  2. 生成50MB的ZIP文件" -ForegroundColor Gray
Write-Host "  3. 生成25MB的ZIP文件" -ForegroundColor Gray
Write-Host "  4. 自定义大小" -ForegroundColor Gray
Write-Host ""

$choice = Read-Host "请选择(1-4)"

switch ($choice) {
    "1" {
        $size = 101
        $fileType = "zip"
        $ext = "zip"
        $filename = "101mb_file"
    }
    "2" {
        $size = 50
        $fileType = "zip"
        $ext = "zip"
        $filename = "50mb_file"
    }
    "3" {
        $size = 25
        $fileType = "zip"
        $ext = "zip"
        $filename = "25mb_file"
    }
    "4" {
        $size = Read-Host "请输入文件大小(MB)"
        $filename = Read-Host "请输入文件名(不含扩展名)"
        
        Write-Host ""
        Write-Host "选择文件类型:" -ForegroundColor Gray
        Write-Host "  1. ZIP文件" -ForegroundColor Gray
        Write-Host "  2. 普通文件" -ForegroundColor Gray
        $typeChoice = Read-Host "请选择(1或2)"
        
        if ($typeChoice -eq "2") {
            $fileType = "plain"
            $ext = "bin"
        } else {
            $fileType = "zip"
            $ext = "zip"
        }
    }
    default {
        Write-Host "无效选择" -ForegroundColor Red
        Read-Host "按Enter键退出"
        exit 1
    }
}

# 构建输出路径
$outputFile = Join-Path $DataDir "$filename.$ext"

Write-Host ""
Write-Host "正在生成 ${size}MB 的 $ext 文件..." -ForegroundColor Yellow

# 执行生成
& python (Join-Path $ScriptDir "generate_file.py") -s $size -o $outputFile -t $fileType

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "生成成功!" -ForegroundColor Green
    Write-Host "文件: $outputFile" -ForegroundColor White
    
    # 打开文件所在目录
    Explorer $DataDir
}

Write-Host ""
Read-Host "按Enter键退出"