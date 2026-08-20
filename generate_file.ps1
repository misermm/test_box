# Generate File Tool
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       Generate File Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataDir = Join-Path $ScriptDir "data"

# Ensure data directory exists
if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
}

# Preset options
Write-Host "Preset options:" -ForegroundColor Yellow
Write-Host "  1. Generate 101MB ZIP file" -ForegroundColor Gray
Write-Host "  2. Generate 50MB ZIP file" -ForegroundColor Gray
Write-Host "  3. Generate 25MB ZIP file" -ForegroundColor Gray
Write-Host "  4. Custom size" -ForegroundColor Gray
Write-Host ""

$choice = Read-Host "Select (1-4)"

if ($choice -eq "1") {
    $size = 101
    $fileType = "zip"
    $ext = "zip"
    $filename = "101mb_file"
} elseif ($choice -eq "2") {
    $size = 50
    $fileType = "zip"
    $ext = "zip"
    $filename = "50mb_file"
} elseif ($choice -eq "3") {
    $size = 25
    $fileType = "zip"
    $ext = "zip"
    $filename = "25mb_file"
} elseif ($choice -eq "4") {
    $size = Read-Host "Enter file size (MB)"
    $filename = Read-Host "Enter filename (without extension)"
    
    Write-Host ""
    Write-Host "Select file type:" -ForegroundColor Gray
    Write-Host "  1. ZIP file" -ForegroundColor Gray
    Write-Host "  2. Plain file" -ForegroundColor Gray
    $typeChoice = Read-Host "Select (1 or 2)"
    
    if ($typeChoice -eq "2") {
        $fileType = "plain"
        $ext = "bin"
    } else {
        $fileType = "zip"
        $ext = "zip"
    }
} else {
    Write-Host "Invalid selection" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Build output path
$outputFile = Join-Path $DataDir "$filename.$ext"

Write-Host ""
Write-Host "Generating ${size}MB $ext file..." -ForegroundColor Yellow

# Execute generation
& python (Join-Path $ScriptDir "generate_file.py") -s $size -o $outputFile -t $fileType

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Success!" -ForegroundColor Green
    Write-Host "File: $outputFile" -ForegroundColor White
    
    # Open output directory
    Explorer $DataDir
}

Write-Host ""
Read-Host "Press Enter to exit"