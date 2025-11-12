# PM-App AI Coding Instructions

## System Overview
PM-App is a **forward-filling** portfolio management system that builds risk metrics and attribution data incrementally from "today forward" - no historical backfilling. It follows a three-stage daily workflow: price ingestion → risk calculation → attribution analysis.

## Architecture Patterns

### Database-Centric Design
- **SQL Server backend** with structured schemas (`sql/schemas/01_*.sql` - order matters!)
- All data flows through database views (e.g., `v_portfolio_daily_returns`, `v_benchmark_daily_returns`)
- Use `src/core/utils_db.py::get_conn()` for all database connections
- Connection uses `.env` file with `AUTH_MODE=windows` or username/password

### Ticker Mapping Strategy
Portfolio tickers map to yfinance equivalents in `src/ingestion/fetch_prices.py`:
```python
TICKER_MAPPING = {
    "US10Y": "IEF",      # Bond proxy using ETF
    "CAN10Y": "XBB.TO",  # Canadian bond proxy
}
```
Always use **reverse mapping** when storing data back to database (yfinance → portfolio ticker).

### Rolling Window Calculations
Risk metrics use expanding windows (earliest to latest data point):
- All metrics calculated using FULL available history
- As more data accumulates, metrics become more statistically robust
- No arbitrary 30/90/180-day cutoffs

All calculations are **incremental** - each run adds one day's metrics, not recalculating entire history (though the calculation uses all history up to that point).

## Critical Workflows

### Daily Update Process
Run via `scripts/run_daily_update.ps1` (PowerShell):
1. **Prices**: `fetch_prices.py` → downloads to `data/yf_prices_cache.csv` → bulk insert to database
2. **Risk**: `compute_risk_metrics.py` → calculates rolling metrics for today only
3. **Attribution**: `compute_attribution.py` → calculates today's attribution effects

Can run individual steps: `.\scripts\run_daily_update.ps1 -Step prices|risk|attribution`

### Database Schema Order
Schemas **must** be applied in sequence:
```powershell
sqlcmd -S server -d RiskDemo -i sql\schemas\01_core_portfolio.sql
sqlcmd -S server -d RiskDemo -i sql\schemas\02_risk_metrics.sql  
sqlcmd -S server -d RiskDemo -i sql\schemas\03_attribution.sql
```

## Data Sanitization Patterns
Use `src/core/data_sanitizers.py` for SQL inserts:
- `sanitize_decimal()` for financial values (handles NaN, infinity)
- `sanitize_string()` for text fields
- Always sanitize before database inserts to prevent SQL errors

## Key Conventions

### Python Path Setup
Scripts set `$env:PYTHONPATH = $rootDir` before execution. All imports use absolute paths: `from src.core.utils_db import get_conn`

### Environment Variables
Required `.env` variables:
```
DB_SERVER=your_server
DB_NAME=RiskDemo  
DB_DRIVER=ODBC Driver 17 for SQL Server
AUTH_MODE=windows  # or provide DB_USER/DB_PASS
```

### Error Handling Pattern
Scripts use "fail fast" approach:
```powershell
if $LASTEXITCODE -ne 0:
    Write-Host "ERROR: failed" -ForegroundColor Red
    exit 1
```

### Data Validation
- Portfolio data flows through database views for consistency
- Risk metrics validate data availability before calculation
- Attribution requires both portfolio and benchmark returns

## File Organization Logic

- `src/core/`: Database utilities and data sanitization
- `src/ingestion/`: External data fetching (Yahoo Finance only)
- `src/analytics/`: Risk and attribution calculations
- `sql/schemas/`: Database structure (numbered for dependency order)
- `sql/views/`: Calculated views for portfolio/benchmark returns
- `sql/seed_data/`: Reference data (dimensions only - IPS features removed)

## Common Debugging Points

### Missing Prices
Check `data/yf_prices_cache.csv` for downloaded data. Verify ticker symbols exist on Yahoo Finance. Canadian tickers need `.TO` suffix.

### Database Connection Issues  
Verify SQL Server running, ODBC driver installed, and firewall allows port 1433. Check `.env` authentication mode.

### Import Errors
Ensure all `src/` subdirectories have `__init__.py` files. Set `PYTHONPATH` to project root before running scripts.

### Risk Calculation Failures
Risk metrics require sufficient return history (minimum 30 days for shortest window). Check `v_portfolio_daily_returns` view has data.

## Important Notes

- System is designed for **incremental daily updates**, not batch historical processing
- Each component assumes "calculate today's metrics using available history"
- Old IPS (Investment Policy Statement) monitoring features have been removed - references to `seed_ips_policy.sql` or `view_ips_monitoring.sql` are outdated