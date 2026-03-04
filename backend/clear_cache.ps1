# Clear Python Cache and Restart Server
# Run this script to fix the "settings is not defined" error

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Clearing Python Cache and Restarting" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Stop any running Python processes
Write-Host "[1/4] Stopping any running server..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Clear __pycache__ directories
Write-Host "[2/4] Clearing __pycache__ directories..." -ForegroundColor Yellow
$pycacheDirs = Get-ChildItem -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue
$pycacheCount = $pycacheDirs.Count
foreach ($dir in $pycacheDirs) {
    Write-Host "  Removing: $($dir.FullName)" -ForegroundColor Gray
    Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host "  Removed $pycacheCount __pycache__ directories" -ForegroundColor Green

# Clear .pyc files
Write-Host "[3/4] Clearing .pyc files..." -ForegroundColor Yellow
$pycFiles = Get-ChildItem -Recurse -Filter '*.pyc' -ErrorAction SilentlyContinue
$pycCount = $pycFiles.Count
foreach ($file in $pycFiles) {
    Write-Host "  Removing: $($file.FullName)" -ForegroundColor Gray
    Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
}
Write-Host "  Removed $pycCount .pyc files" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Cache Cleared Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Start server
Write-Host "[4/4] Starting server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Server starting on http://localhost:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Activate virtual environment and start server
& .\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
