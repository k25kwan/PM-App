# ============================================================================
# Run Streamlit Multi-User App (IPS Prototype)
# ============================================================================

Write-Host "=== Starting PM-App Multi-User Prototype ===" -ForegroundColor Cyan
Write-Host ""

# Set PYTHONPATH
$rootDir = $PSScriptRoot | Split-Path
$env:PYTHONPATH = $rootDir

Write-Host "PYTHONPATH set to: $rootDir" -ForegroundColor Yellow
Write-Host ""

# Activate virtual environment
$venvPath = Join-Path $rootDir ".venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    Write-Host "Activating virtual environment..." -ForegroundColor Green
    & $venvPath
} else {
    Write-Host "Warning: Virtual environment not found at $venvPath" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Starting Streamlit app..." -ForegroundColor Green
Write-Host "Access the app at: http://localhost:8501" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Run Streamlit
$appPath = Join-Path $rootDir "app\Home.py"
& "C:/Users/Kevin Kwan/PM-app/.venv/Scripts/python.exe" -m streamlit run $appPath
