# ============================================================================
# Run Database Migration - Add Multi-User Support
# ============================================================================

param(
    [string]$Server = $env:DB_SERVER,
    [string]$Database = $env:DB_NAME
)

# Load .env file if exists
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*?)\s*=\s*(.*?)\s*$') {
            $key = $matches[1]
            $value = $matches[2]
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    $Server = $env:DB_SERVER
    $Database = $env:DB_NAME
}

Write-Host "=== Running Database Migration ===" -ForegroundColor Cyan
Write-Host "Server: $Server" -ForegroundColor Yellow
Write-Host "Database: $Database" -ForegroundColor Yellow
Write-Host ""

# Check if sqlcmd is available
$sqlcmdPath = Get-Command sqlcmd -ErrorAction SilentlyContinue
if (-not $sqlcmdPath) {
    Write-Host "ERROR: sqlcmd not found. Please install SQL Server Command Line Tools." -ForegroundColor Red
    Write-Host "Download: https://learn.microsoft.com/en-us/sql/tools/sqlcmd-utility" -ForegroundColor Yellow
    exit 1
}

# Run migration
$migrationFile = "migrations\01_add_multiuser_support.sql"

if (-not (Test-Path $migrationFile)) {
    Write-Host "ERROR: Migration file not found: $migrationFile" -ForegroundColor Red
    exit 1
}

Write-Host "Running migration: $migrationFile" -ForegroundColor Green

# Execute with Windows Authentication
sqlcmd -S $Server -d $Database -E -i $migrationFile

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Migration failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Migration Completed Successfully ===" -ForegroundColor Green
Write-Host ""
Write-Host "New capabilities enabled:" -ForegroundColor Cyan
Write-Host "  - Multi-user support with user_id columns" -ForegroundColor White
Write-Host "  - User authentication table (users)" -ForegroundColor White
Write-Host "  - IPS questionnaire responses (ips_responses)" -ForegroundColor White
Write-Host "  - Trade logging (trade_log)" -ForegroundColor White
Write-Host "  - Security screening scores (security_scores)" -ForegroundColor White
Write-Host "  - User-specific universe (user_universe)" -ForegroundColor White
Write-Host "  - Master securities universe (master_universe)" -ForegroundColor White
