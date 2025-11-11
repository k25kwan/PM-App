# ============================================================================
# Daily Portfolio Update Script
# ============================================================================
# This script runs the daily update workflow for portfolio management:
# 1. Fetches latest prices from Yahoo Finance
# 2. Calculates rolling risk metrics
# 3. Calculates rolling attribution
# ============================================================================

param(
    [string]$Step = "all"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptDir

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Daily Portfolio Update" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Run-PythonScript {
    param(
        [string]$ScriptPath,
        [string]$Description
    )
    
    Write-Host "[$Description]" -ForegroundColor Yellow
    Write-Host "Running: $ScriptPath" -ForegroundColor Gray
    
    $env:PYTHONPATH = $rootDir
    python $ScriptPath
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: $Description failed" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✓ Completed: $Description" -ForegroundColor Green
    Write-Host ""
}

# Step 1: Fetch Latest Prices
if ($Step -eq "all" -or $Step -eq "prices") {
    Run-PythonScript `
        -ScriptPath "$rootDir\src\ingestion\fetch_prices.py" `
        -Description "Fetch Latest Prices"
}

# Step 2: Calculate Risk Metrics
if ($Step -eq "all" -or $Step -eq "risk") {
    Run-PythonScript `
        -ScriptPath "$rootDir\src\analytics\compute_risk_metrics.py" `
        -Description "Calculate Risk Metrics"
}

# Step 3: Calculate Attribution
if ($Step -eq "all" -or $Step -eq "attribution") {
    Run-PythonScript `
        -ScriptPath "$rootDir\src\analytics\compute_attribution.py" `
        -Description "Calculate Attribution"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Daily Update Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
