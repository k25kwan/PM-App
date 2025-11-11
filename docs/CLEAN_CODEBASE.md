# Clean Codebase Documentation

This document provides a comprehensive explanation of every file in the PM-App codebase. Read this to understand what each component does and how they work together.

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Core Utilities](#core-utilities)
3. [Data Ingestion](#data-ingestion)
4. [Analytics](#analytics)
5. [Database Schema](#database-schema)
6. [Scripts](#scripts)
7. [Data Flow](#data-flow)

---

## System Architecture

PM-App is a **forward-filling** portfolio management system. This means:
- You manually input your initial portfolio holdings
- The system automatically fetches daily prices
- Risk metrics and attribution are calculated daily using rolling windows
- **No historical backfilling** - it builds history going forward from today

### Technology Stack
- **Language**: Python 3.10+
- **Database**: SQL Server Express
- **Data Source**: Yahoo Finance (via yfinance library)
- **Key Libraries**: pandas, numpy, sqlalchemy, pyodbc

### Design Philosophy
- **Simple and Clean**: Every file has one clear purpose
- **Forward-Only**: No complex historical data population
- **Incremental Updates**: Each day adds one new row to metrics tables
- **Minimal Dependencies**: Only essential libraries

---

## Core Utilities

### `src/core/utils_db.py`
**Purpose**: Database connection management

**What it does**:
- Creates SQLAlchemy database connections
- Loads connection parameters from `.env` file
- Provides reusable `get_conn()` function for all scripts

**Key Functions**:
```python
get_conn() -> sqlalchemy.engine.Connection
```
Returns a database connection using environment variables:
- `DB_SERVER`: Your SQL Server instance name
- `DB_NAME`: Database name (default: RiskDemo)
- `DB_DRIVER`: ODBC driver name

**How it's used**:
```python
from src.core.utils_db import get_conn

with get_conn() as conn:
    df = pd.read_sql("SELECT * FROM core.Prices", conn)
```

**Important Notes**:
- Uses `pyodbc` for Windows authentication
- Connection string format: `mssql+pyodbc://server/database?driver=...`
- `.env` file must exist in project root

---

### `src/core/data_sanitizers.py`
**Purpose**: Clean and validate data before database insertion

**What it does**:
- Handles NULL values in DataFrames
- Converts Python None to SQL NULL
- Ensures data types match SQL schema

**Key Functions**:
```python
sanitize_for_sql(df: pd.DataFrame) -> pd.DataFrame
```
Cleans a DataFrame for SQL insertion:
- Replaces NaN with None (SQL NULL)
- Converts datetime objects to proper format
- Strips whitespace from strings

**How it's used**:
```python
from src.core.data_sanitizers import sanitize_for_sql

df = sanitize_for_sql(prices_df)
df.to_sql('Prices', conn, schema='core', if_exists='append', index=False)
```

**Why this matters**:
- Prevents SQL type errors
- Ensures consistent NULL handling
- Avoids duplicate key violations

---

## Data Ingestion

### `src/ingestion/fetch_prices.py`
**Purpose**: Fetch latest prices from Yahoo Finance and save to database

**What it does**:
1. Queries database for all unique tickers in `core.PortfolioHoldings`
2. Fetches latest prices from Yahoo Finance using `yfinance`
3. Caches prices to `data/` folder as JSON (for faster re-runs)
4. Inserts new prices into `core.Prices` table

**Workflow**:
```
1. Get unique tickers from PortfolioHoldings
2. Check cache for recent prices (within 24 hours)
3. If cache miss, fetch from Yahoo Finance
4. Save to cache as JSON
5. Insert into core.Prices (skipping duplicates)
```

**Key Parameters**:
```python
start_date: Date to fetch prices from (default: 1 year ago)
end_date: Date to fetch prices until (default: today)
```

**Cache Structure**:
```
data/
  ├── AAPL_prices.json
  ├── MSFT_prices.json
  └── ...
```

**Error Handling**:
- Skips invalid tickers (prints warning)
- Continues if one ticker fails
- Logs failed tickers for manual review

**How to run**:
```powershell
python src\ingestion\fetch_prices.py
```

**Expected Output**:
```
Fetching prices for 10 tickers...
✓ AAPL: 252 prices
✓ MSFT: 252 prices
Inserted 504 new price records
```

---

## Analytics

### `src/analytics/compute_risk_metrics.py`
**Purpose**: Calculate rolling risk metrics for portfolio and benchmark

**What it does**:
1. Fetches daily returns from `view_returns` SQL view
2. Calculates rolling volatility (30/90/180-day windows)
3. Calculates tracking error (portfolio vs benchmark)
4. Calculates beta (portfolio sensitivity to benchmark)
5. Inserts results into risk metrics tables

**Metrics Calculated**:

| Metric | Formula | Interpretation |
|--------|---------|---------------|
| **Volatility** | StdDev(Returns) * √252 | Annualized return variability |
| **Tracking Error** | StdDev(Active Returns) * √252 | Deviation from benchmark |
| **Beta** | Cov(Portfolio, Benchmark) / Var(Benchmark) | Market sensitivity |

**Rolling Windows**:
- **30-day**: Recent volatility (captures short-term moves)
- **90-day**: Quarterly trends (used for risk reporting)
- **180-day**: Half-year patterns (smooths out noise)

**Database Tables Updated**:
- `risk.RollingVolatility`: Daily volatility for each window
- `risk.TrackingError`: Daily tracking error
- `risk.Beta`: Daily beta coefficient

**Data Flow**:
```
view_returns → Calculate Returns → Rolling Windows → Insert to Tables
```

**Key Code Snippet**:
```python
# 30-day rolling volatility
df['VOL_030D'] = df['Return'].rolling(30).std() * np.sqrt(252)

# Tracking error
df['TrackingError_30D'] = (df['Portfolio_Return'] - df['Benchmark_Return']).rolling(30).std() * np.sqrt(252)

# Beta
df['Beta_30D'] = df['Portfolio_Return'].rolling(30).cov(df['Benchmark_Return']) / df['Benchmark_Return'].rolling(30).var()
```

**How to run**:
```powershell
python src\analytics\compute_risk_metrics.py
```

**Expected Output**:
```
Calculating risk metrics...
Date range: 2024-01-01 to 2024-11-11
Inserted 314 volatility records
Inserted 314 tracking error records
Inserted 314 beta records
```

---

### `src/analytics/compute_attribution.py`
**Purpose**: Analyze portfolio returns vs benchmark (attribution analysis)

**What it does**:
1. Fetches portfolio holdings and benchmark weights
2. Calculates daily returns for portfolio and benchmark
3. Decomposes returns into allocation and selection effects
4. Inserts results into `attribution.DailyAttribution`

**Attribution Effects Explained**:

| Effect | Formula | What It Measures |
|--------|---------|-----------------|
| **Asset Allocation** | (Portfolio Weight - Benchmark Weight) × Benchmark Return | Returns from over/underweighting asset classes |
| **Security Selection** | Benchmark Weight × (Portfolio Return - Benchmark Return) | Returns from stock picking within asset classes |
| **Interaction** | (Portfolio Weight - Benchmark Weight) × (Portfolio Return - Benchmark Return) | Combined effect of allocation and selection |

**Example**:
If you overweight Tech stocks (allocation) AND pick good Tech stocks (selection):
- **Allocation Effect**: +0.5% (Tech outperformed, you had more)
- **Selection Effect**: +0.3% (Your Tech stocks beat Tech benchmark)
- **Interaction Effect**: +0.1% (Bonus from doing both right)
- **Total Alpha**: +0.9%

**Asset Class Mapping**:
The script maps tickers to asset classes:
```python
asset_class_map = {
    'AAPL': 'US Equity',
    'MSFT': 'US Equity',
    'TLT': 'Fixed Income',
    'GLD': 'Commodities'
}
```

**Database Tables Updated**:
- `attribution.DailyAttribution`: Daily attribution by asset class
- `attribution.MonthlyAttribution`: Month-end aggregated attribution

**Data Flow**:
```
PortfolioHoldings + BenchmarkWeights → Calculate Returns → Attribution Effects → Insert to Tables
```

**How to run**:
```powershell
python src\analytics\compute_attribution.py
```

**Expected Output**:
```
Calculating attribution...
Date range: 2024-01-01 to 2024-11-11
Inserted 942 daily attribution records (3 asset classes × 314 days)
```

---

## Database Schema

### Schema 1: Core Portfolio (`sql/schemas/01_core_portfolio.sql`)

**Purpose**: Store portfolio holdings, prices, and benchmark data

**Tables**:

#### `core.PortfolioHoldings`
Stores daily portfolio positions:
```sql
AsOfDate DATE          -- Position date
Ticker VARCHAR(20)     -- Stock ticker
Shares DECIMAL(18,4)   -- Number of shares held
CostBasis DECIMAL(18,4) -- Average cost per share
```

**How to use**: Manually insert your holdings at start, then update daily if positions change.

Example:
```sql
INSERT INTO core.PortfolioHoldings VALUES
('2024-01-01', 'AAPL', 100, 150.00),
('2024-01-01', 'MSFT', 50, 350.00);
```

#### `core.Prices`
Stores historical prices:
```sql
AsOfDate DATE          -- Price date
Ticker VARCHAR(20)     -- Stock ticker
ClosePrice DECIMAL(18,6) -- Closing price
AdjClose DECIMAL(18,6)   -- Adjusted close (splits/dividends)
Volume BIGINT           -- Trading volume
```

**How it's populated**: Automatically by `fetch_prices.py`

#### `core.BenchmarkWeights`
Stores benchmark composition:
```sql
AsOfDate DATE          -- Rebalance date
Ticker VARCHAR(20)     -- Benchmark constituent
Weight DECIMAL(10,6)   -- Target weight (0-1)
```

**How to use**: Define your benchmark (e.g., S&P 500 weights) manually.

---

### Schema 2: Risk Metrics (`sql/schemas/02_risk_metrics.sql`)

**Purpose**: Store calculated risk metrics

**Tables**:

#### `risk.RollingVolatility`
```sql
AsOfDate DATE
Ticker VARCHAR(20)     -- 'PORTFOLIO' or individual ticker
Window INT            -- Days in rolling window (30/90/180)
Volatility DECIMAL(10,6) -- Annualized volatility
```

#### `risk.TrackingError`
```sql
AsOfDate DATE
Window INT
TrackingError DECIMAL(10,6) -- Annualized tracking error
```

#### `risk.Beta`
```sql
AsOfDate DATE
Window INT
Beta DECIMAL(10,6)    -- Portfolio beta vs benchmark
```

**How it's populated**: Automatically by `compute_risk_metrics.py`

---

### Schema 3: Attribution (`sql/schemas/03_attribution.sql`)

**Purpose**: Store attribution analysis results

**Tables**:

#### `attribution.DailyAttribution`
```sql
AsOfDate DATE
AssetClass VARCHAR(50)         -- e.g., 'US Equity'
AllocationEffect DECIMAL(10,6)  -- Allocation return
SelectionEffect DECIMAL(10,6)   -- Selection return
InteractionEffect DECIMAL(10,6) -- Interaction return
TotalEffect DECIMAL(10,6)      -- Sum of above
```

#### `attribution.MonthlyAttribution`
Same structure as daily, but aggregated to month-end.

**How it's populated**: Automatically by `compute_attribution.py`

---

### Seed Data

#### `sql/seed_data/seed_dimensions.sql`
Creates reference tables:
- `dim.Calendar`: Date dimension (2020-2030)
- `dim.AssetClass`: List of asset classes (Equity, Fixed Income, etc.)

**Why this matters**: Ensures consistent date handling and asset class names.

#### `sql/seed_data/seed_ips_policy.sql`
Defines Investment Policy Statement targets:
```sql
INSERT INTO core.IPSPolicy VALUES
('US Equity', 0.60, 0.05),  -- 60% target, ±5% tolerance
('Fixed Income', 0.30, 0.05),
('Commodities', 0.10, 0.03);
```

**How to use**: Update these values to match your IPS document.

---

### SQL Views

#### `sql/views/view_returns.sql`
**Purpose**: Calculate daily returns for portfolio and benchmark

**What it returns**:
```sql
AsOfDate | Portfolio_Return | Benchmark_Return | Active_Return
---------|-----------------|------------------|---------------
2024-01-02 | 0.0125 | 0.0100 | 0.0025
```

**Used by**: `compute_risk_metrics.py`, `compute_attribution.py`

#### `sql/views/view_ips_monitoring.sql`
**Purpose**: Show portfolio drift from IPS targets

**What it returns**:
```sql
AsOfDate | AssetClass | Actual_Weight | Policy_Weight | Drift | Alert
---------|-----------|--------------|---------------|------|-------
2024-11-11 | US Equity | 0.65 | 0.60 | 0.05 | AT_LIMIT
```

**Used for**: Compliance reporting

#### `sql/views/view_risk_metrics_latest.sql`
**Purpose**: Show most recent risk metrics

**What it returns**:
```sql
Metric | 30D_Value | 90D_Value | 180D_Value
-------|----------|----------|------------
Volatility | 0.15 | 0.18 | 0.20
Tracking Error | 0.02 | 0.03 | 0.03
Beta | 0.95 | 1.00 | 1.05
```

**Used for**: Quick dashboard view

---

## Scripts

### `scripts/run_daily_update.ps1`
**Purpose**: Orchestrate daily workflow

**What it does**:
```
Step 1: Fetch Prices → fetch_prices.py
Step 2: Calculate Risk → compute_risk_metrics.py
Step 3: Calculate Attribution → compute_attribution.py
```

**How to run**:
```powershell
# Run all steps
.\scripts\run_daily_update.ps1

# Run specific step
.\scripts\run_daily_update.ps1 -Step prices
.\scripts\run_daily_update.ps1 -Step risk
.\scripts\run_daily_update.ps1 -Step attribution
```

**Error Handling**:
- Stops on first error (doesn't continue to next step)
- Sets `PYTHONPATH` environment variable
- Shows colored output (Green=success, Red=error)

**Typical Run Time**:
- Fetch Prices: 30-60 seconds (depends on # of tickers)
- Risk Metrics: 5-10 seconds
- Attribution: 5-10 seconds
- **Total: ~1 minute**

---

## Data Flow

### End-to-End Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. MANUAL SETUP (One-time)                                 │
├─────────────────────────────────────────────────────────────┤
│ • Run SQL schemas (01, 02, 03)                             │
│ • Load seed data (dimensions, IPS policy)                  │
│ • Insert initial portfolio holdings                        │
│ • Define benchmark weights                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. DAILY INGESTION (Automated)                             │
├─────────────────────────────────────────────────────────────┤
│ fetch_prices.py                                            │
│ • Get tickers from PortfolioHoldings                       │
│ • Fetch prices from Yahoo Finance                          │
│ • Cache to data/*.json                                     │
│ • Insert to core.Prices                                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. RISK CALCULATION (Automated)                            │
├─────────────────────────────────────────────────────────────┤
│ compute_risk_metrics.py                                    │
│ • Read from view_returns                                   │
│ • Calculate rolling volatility (30/90/180D)                │
│ • Calculate tracking error                                 │
│ • Calculate beta                                           │
│ • Insert to risk.* tables                                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. ATTRIBUTION CALCULATION (Automated)                     │
├─────────────────────────────────────────────────────────────┤
│ compute_attribution.py                                     │
│ • Read holdings & benchmark weights                        │
│ • Calculate returns by asset class                         │
│ • Decompose into allocation/selection effects              │
│ • Insert to attribution.* tables                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. REPORTING (SQL Views)                                   │
├─────────────────────────────────────────────────────────────┤
│ • view_returns: Daily portfolio vs benchmark returns       │
│ • view_risk_metrics_latest: Current risk profile           │
│ • view_ips_monitoring: IPS compliance status               │
└─────────────────────────────────────────────────────────────┘
```

### Typical Daily Workflow

**Morning (Before Market Open)**:
1. Update portfolio holdings if positions changed overnight
2. Run `.\scripts\run_daily_update.ps1`
3. Review risk metrics and IPS compliance

**End of Day (After Market Close)**:
1. Re-run `.\scripts\run_daily_update.ps1` to get final prices
2. Generate reports from SQL views
3. Review attribution to understand daily performance

---

## Common Operations

### Adding a New Stock to Portfolio

**Step 1**: Insert into PortfolioHoldings
```sql
INSERT INTO core.PortfolioHoldings (AsOfDate, Ticker, Shares, CostBasis)
VALUES ('2024-11-11', 'GOOGL', 25, 140.50);
```

**Step 2**: Run daily update
```powershell
.\scripts\run_daily_update.ps1
```

The system will automatically:
- Fetch GOOGL prices from Yahoo Finance
- Include GOOGL in risk calculations
- Update attribution with new position

---

### Checking Risk Metrics

**Quick View** (Latest metrics):
```sql
SELECT * FROM view_risk_metrics_latest;
```

**Historical Trend** (30-day volatility over time):
```sql
SELECT AsOfDate, Volatility
FROM risk.RollingVolatility
WHERE Ticker = 'PORTFOLIO' AND Window = 30
ORDER BY AsOfDate DESC;
```

---

### Reviewing Attribution

**Today's Attribution**:
```sql
SELECT * FROM attribution.DailyAttribution
WHERE AsOfDate = '2024-11-11'
ORDER BY AssetClass;
```

**Month-to-Date Attribution**:
```sql
SELECT AssetClass,
       SUM(AllocationEffect) AS MTD_Allocation,
       SUM(SelectionEffect) AS MTD_Selection,
       SUM(TotalEffect) AS MTD_Total
FROM attribution.DailyAttribution
WHERE AsOfDate >= '2024-11-01'
GROUP BY AssetClass;
```

---

### Checking IPS Compliance

```sql
SELECT * FROM view_ips_monitoring
WHERE Alert != 'OK'
ORDER BY ABS(Drift) DESC;
```

Shows asset classes outside tolerance bands, ordered by severity.

---

## Troubleshooting Guide

### Problem: "No prices found for ticker XYZ"

**Cause**: Invalid ticker symbol or delisted stock

**Solution**:
1. Verify ticker on Yahoo Finance: https://finance.yahoo.com/quote/XYZ
2. Update ticker in PortfolioHoldings if symbol changed
3. Remove from holdings if delisted

---

### Problem: "Connection to database failed"

**Cause**: SQL Server not running or firewall blocking

**Solution**:
1. Check SQL Server status: `services.msc` → Look for "SQL Server (SQLEXPRESS)"
2. Verify server name in `.env` file matches SQL Server instance
3. Test connection: `sqlcmd -S your_server -Q "SELECT @@VERSION"`

---

### Problem: "Risk metrics not updating"

**Cause**: Insufficient data for rolling window

**Solution**:
Risk metrics require minimum data points:
- 30-day window: Need 30 days of prices
- 90-day window: Need 90 days of prices
- 180-day window: Need 180 days of prices

**Fix**: Wait for more data to accumulate, or reduce window size temporarily.

---

### Problem: "Attribution shows NULL values"

**Cause**: Missing benchmark weights

**Solution**:
1. Check `core.BenchmarkWeights` has data for today's date
2. Ensure asset class mappings exist in `compute_attribution.py`
3. Verify benchmark tickers have prices in `core.Prices`

---

## Best Practices

### 1. Daily Routine
- Run update script at consistent time (e.g., 5 PM after market close)
- Review IPS compliance weekly
- Archive old cache files monthly (`data/*.json`)

### 2. Data Hygiene
- Don't manually edit `core.Prices` (let `fetch_prices.py` handle it)
- Keep PortfolioHoldings current (delete old positions)
- Update benchmark weights quarterly (when index rebalances)

### 3. Performance
- Cache files speed up re-runs (keep them unless debugging)
- Risk calculations are fast (< 10 seconds for 1 year of data)
- Attribution is slowest (but still < 30 seconds)

### 4. Backups
- Backup database weekly: `BACKUP DATABASE RiskDemo TO DISK = 'C:\Backups\RiskDemo.bak'`
- Version control code changes with git
- Keep copy of IPS policy document alongside `seed_ips_policy.sql`

---

## Next Steps

Now that you understand the codebase:

1. **Set up your environment** (see README.md Quick Start)
2. **Input your portfolio** (manually insert holdings)
3. **Run first update** (`.\scripts\run_daily_update.ps1`)
4. **Review results** (query SQL views)
5. **Automate** (schedule daily task in Windows Task Scheduler)

For questions or issues, review this document first, then check code comments in individual files.

---

**Last Updated**: 2024-11-11  
**Codebase Version**: 1.0  
**Maintained By**: PM-App Team
