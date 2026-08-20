# Image to PDF Converter with File Splitting
# Merges all images in data directory into PDF, then optionally splits into ZIP files

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       Image to PDF Tool" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataDir = Join-Path $ScriptDir "data"

# Check if data directory exists
if (-not (Test-Path $DataDir)) {
    Write-Host "Error: data directory not found" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Supported image formats
$ImageExtensions = @("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tiff", "*.tif", "*.gif")

# Find all image files
$Images = @()
foreach ($Ext in $ImageExtensions) {
    $Images += Get-ChildItem -Path $DataDir -Filter $Ext -File
}

if ($Images.Count -eq 0) {
    Write-Host "Error: No image files found in data directory" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Found $($Images.Count) images:" -ForegroundColor Green
foreach ($Img in $Images) {
    Write-Host "  - $($Img.Name)" -ForegroundColor Gray
}
Write-Host ""

# Generate PDF
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$PdfFile = Join-Path $DataDir "merged_$Timestamp.pdf"

Write-Host "Step 1: Merging images to PDF..." -ForegroundColor Yellow
$ImagePaths = $Images | ForEach-Object { $_.FullName }
& python (Join-Path $ScriptDir "image_to_pdf.py") @ImagePaths -o $PdfFile

if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: PDF creation failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$PdfSize = (Get-Item $PdfFile).Length / 1MB
Write-Host "PDF created: $PdfFile ($([math]::Round($PdfSize, 2)) MB)" -ForegroundColor Green
Write-Host ""

# Ask user if they want to split the file
Write-Host "Step 2: Do you want to split the PDF into ZIP files?" -ForegroundColor Yellow
Write-Host "  1. No, keep as single PDF" -ForegroundColor Gray
Write-Host "  2. Yes, split into custom size ZIP files" -ForegroundColor Gray
Write-Host "  3. Yes, split into 101MB ZIP files" -ForegroundColor Gray
Write-Host "  4. Yes, split into 50MB ZIP files" -ForegroundColor Gray
Write-Host "  5. Yes, split into 25MB ZIP files" -ForegroundColor Gray
Write-Host ""

$choice = Read-Host "Enter your choice (1-5)"

if ($choice -eq "2") {
    # Custom size
    $sizeInput = Read-Host "Enter ZIP file size in MB (e.g., 101)"
    $zipSize = [float]$sizeInput
    
    if ($zipSize -le 0) {
        Write-Host "Invalid size" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    $outputDir = Join-Path $DataDir "zip_parts"
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
    
    Write-Host "Splitting PDF into ${zipSize}MB ZIP files..." -ForegroundColor Yellow
    & python (Join-Path $ScriptDir "file_splitter.py") split $PdfFile -s $zipSize -o $outputDir
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Split completed! Files saved to: $outputDir" -ForegroundColor Green
        Explorer $outputDir
    }
}
elseif ($choice -eq "3") {
    # 101MB
    $outputDir = Join-Path $DataDir "zip_101mb"
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
    
    Write-Host "Splitting PDF into 101MB ZIP files..." -ForegroundColor Yellow
    & python (Join-Path $ScriptDir "file_splitter.py") split $PdfFile -s 101 -o $outputDir
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Split completed! Files saved to: $outputDir" -ForegroundColor Green
        Explorer $outputDir
    }
}
elseif ($choice -eq "4") {
    # 50MB
    $outputDir = Join-Path $DataDir "zip_50mb"
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
    
    Write-Host "Splitting PDF into 50MB ZIP files..." -ForegroundColor Yellow
    & python (Join-Path $ScriptDir "file_splitter.py") split $PdfFile -s 50 -o $outputDir
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Split completed! Files saved to: $outputDir" -ForegroundColor Green
        Explorer $outputDir
    }
}
elseif ($choice -eq "5") {
    # 25MB
    $outputDir = Join-Path $DataDir "zip_25mb"
    New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
    
    Write-Host "Splitting PDF into 25MB ZIP files..." -ForegroundColor Yellow
    & python (Join-Path $ScriptDir "file_splitter.py") split $PdfFile -s 25 -o $outputDir
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "Split completed! Files saved to: $outputDir" -ForegroundColor Green
        Explorer $outputDir
    }
}
else {
    # Keep as single PDF
    Write-Host "Keeping as single PDF file" -ForegroundColor Green
    Write-Host "File: $PdfFile" -ForegroundColor White
    Explorer $DataDir
}

Write-Host ""
Read-Host "Press Enter to exit"