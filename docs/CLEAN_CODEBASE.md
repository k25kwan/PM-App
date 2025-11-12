# Clean Codebase Documentation

This document provides a comprehensive explanation of every file in the PM-App codebase, the architecture, data flows, and design decisions. Read this to fully understand how the system works.

## Table of Contents
1. [System Architecture](#system-architecture)
2. [Core Utilities](#core-utilities)
3. [Data Ingestion](#data-ingestion)
4. [Analytics](#analytics)
5. [Database Schema](#database-schema)
6. [Scripts](#scripts)
7. [Data Flow](#data-flow)
8. [Design Decisions](#design-decisions)

---

## System Architecture

### The Big Picture: Forward-Filling Philosophy

PM-App is fundamentally different from traditional portfolio management systems. Instead of requiring you to import years of historical data, it builds your portfolio history **incrementally from today forward**.

**Why this approach?**
- **No historical data migration**: Don't need to hunt down old holdings records
- **Clean data**: Each day's data captured when it's fresh, not reconstructed later
- **No survivorship bias**: You capture what you actually owned, not what survived
- **Predictable**: Each day adds exactly one data point - no complex backfilling logic
- **Fast**: Incremental calculations are faster than full recalculations

**The Trade-off**: You can't analyze historical performance from before you started using the system. But for ongoing portfolio management, this is usually fine - you care more about forward-looking risk monitoring than backward-looking performance measurement.

### Technology Stack

- **Database**: SQL Server Express (free edition, production-ready)
  - Why SQL Server? Strong for financial data, excellent performance, free tier available, works great on Windows
  - Stores: Portfolio holdings, prices, risk metrics, attribution results
  - All calculations flow through database views (ensures data consistency)
  
- **Data Source**: Yahoo Finance via `yfinance` library
  - Why yfinance? Free, reliable, comprehensive coverage of stocks/ETFs, historical data
  - Limitations: Some bonds don't have direct tickers (we use ETF proxies)
  
- **Key Libraries**: 
  - `pandas`: DataFrames for financial time series manipulation
  - `numpy`: Numerical calculations (volatility, correlations, etc.)
  - `pyodbc`: SQL Server connection (native Windows ODBC integration)
  - `python-dotenv`: Environment variable management (.env file)

### Design Philosophy

**1. Simplicity Over Features**
- Each file has one clear purpose
- No over-engineering or premature optimization
- Readable code that your friend can understand in 15 minutes

**2. Database-Centric Architecture**
- Database is the "source of truth"
- Python scripts are stateless (no in-memory caching between runs)
- All calculations flow through SQL views
- This makes the system deterministic and debuggable

**3. Incremental > Batch**
- Each daily run adds one new day's worth of metrics
- Never recalculate full history (only today's values)
- Fast, predictable runtimes (~1 minute total)

**4. Separation of Concerns**
- **Ingestion** (`src/ingestion/`): Get external data (Yahoo Finance)
- **Core** (`src/core/`): Utilities used by everything (DB connection, sanitization)
- **Analytics** (`src/analytics/`): Calculate metrics (risk, attribution)
- **Database** (`sql/`): Store and structure data (schemas, views)
- **Automation** (`scripts/`): Orchestrate workflows (PowerShell)

Each layer has a clear boundary. Ingestion doesn't know about analytics. Analytics doesn't know about ingestion. They communicate only through the database.

---

## Core Utilities

### `src/core/utils_db.py`
**Purpose**: Centralized database connection management

**What it does**:
This file provides a single function that every other Python script uses to connect to SQL Server. It handles all the messy details of connection strings, authentication, and driver configuration.

**Key Function**:
```python
def get_conn():
    """Returns a pyodbc connection to SQL Server"""
    # Reads from .env file:
    # - DB_SERVER (e.g., "localhost\SQLEXPRESS")
    # - DB_NAME (e.g., "RiskDemo")
    # - AUTH_MODE (e.g., "windows" for Windows Auth, or set DB_USER/DB_PASS)
    # - DB_DRIVER (e.g., "ODBC Driver 17 for SQL Server")
```

**Authentication Modes**:
1. **Windows Authentication** (recommended for local development):
   ```
   AUTH_MODE=windows
   ```
   Uses your Windows login credentials. No password needed.

2. **SQL Authentication** (for username/password):
   ```
   AUTH_MODE=sql
   DB_USER=sa
   DB_PASS=your_password
   ```

**Connection Settings**:
- `autocommit = True`: Every SQL statement commits immediately (no manual commit needed)
- `Encrypt=yes; TrustServerCertificate=yes`: Required for modern SQL Server security

**Why centralized?**
- If you need to change database server, update .env file once (not in 10 different scripts)
- Consistent connection handling across all scripts
- Easy to switch between Windows Auth and SQL Auth
- Handles driver differences automatically

**Usage Pattern** (used everywhere):
```python
from src.core.utils_db import get_conn

with get_conn() as cn:
    df = pd.read_sql("SELECT * FROM historical_portfolio_info", cn)
    # Connection automatically closes when 'with' block ends
```

**Helper Function**:
```python
def run_sql_file(path: str):
    """Execute a .sql file (useful for running schema scripts)"""
```

---

### `src/core/data_sanitizers.py`
**Purpose**: Clean data before SQL Server inserts

**The Problem**: 
Pandas calculations often produce `NaN`, `None`, or `infinity` values. SQL Server **rejects** these:
```python
# This will crash SQL Server insert:
value = np.sqrt(-1)  # NaN
cursor.execute("INSERT INTO table VALUES (?)", value)  # ERROR!
```

**The Solution**: 
Sanitize every value before inserting:

**Function 1: `sanitize_decimal(val, default=0)`**
```python
def sanitize_decimal(val, default=0):
    """
    Sanitize numeric values for SQL DECIMAL columns
    
    Handles:
    - None → default
    - NaN → default
    - Infinity → default  
    - Valid numbers → Decimal(value) with precision
    
    Returns: Decimal object or default value
    """
```

**Example Usage**:
```python
from src.core.data_sanitizers import sanitize_decimal

# Calculate volatility (might be NaN if insufficient data)
volatility = returns.std()  # Could be NaN

# Sanitize before insert
clean_vol = sanitize_decimal(volatility, default=0.0)

# Safe to insert
cursor.execute(
    "INSERT INTO portfolio_risk_metrics (metric_value) VALUES (?)",
    clean_vol
)
```

**Function 2: `sanitize_string(val, default='')`**
```python
def sanitize_string(val, default=''):
    """
    Sanitize string/text values for SQL NVARCHAR columns
    
    Handles:
    - None → default
    - NaN (float) → default
    - Empty string → default
    - Valid strings → str(val)
    
    Returns: String or default value
    """
```

**Example Usage**:
```python
from src.core.data_sanitizers import sanitize_string

# Ticker might be None in some data sources
ticker = stock_data.get('ticker')  # Could be None

# Sanitize before insert
clean_ticker = sanitize_string(ticker, default='UNKNOWN')

cursor.execute(
    "INSERT INTO historical_portfolio_info (ticker) VALUES (?)",
    clean_ticker
)
```

**Why This Matters**:
Without sanitization, your daily updates will crash randomly when:
- Not enough data exists to calculate a metric (volatility with 1 day of returns = NaN)
- Division by zero occurs (Sharpe ratio with zero volatility = infinity)
- External data source returns incomplete records (ticker missing = None)

**Best Practice**: 
**Always sanitize before any SQL insert**. It takes 2 seconds and prevents hours of debugging.

---
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
**Purpose**: Download latest stock/ETF prices from Yahoo Finance and prepare for database loading

**This is Stage 1 of the daily workflow** - provides the raw price data everything else depends on.

**Step-by-Step Process**:

**1. Ticker Mapping (Portfolio Conventions → Yahoo Finance Tickers)**

Some portfolio instruments don't have direct Yahoo Finance tickers. We use ETF proxies:

```python
TICKER_MAPPING = {
    # Bonds → Bond ETF Proxies  
    "US10Y": "IEF",       # US 10Y Treasury → iShares 7-10 Year Treasury ETF
    "CAN10Y": "XBB.TO",   # Canadian bonds → iShares Canadian Bond ETF
    "CORP5": "LQD",       # Corporate bonds → Investment Grade Corp ETF
    
    # Stocks map to themselves
    "AAPL": "AAPL",
    "MSFT": "MSFT",
}
```

**Why ETF proxies for bonds?**
- Bonds trade infrequently (illiquid) → irregular, unreliable pricing
- Bond ETFs trade continuously → daily prices always available
- ETFs track bond indices with 99%+ correlation → excellent proxy
- Example: IEF provides daily-updated 10-year Treasury exposure

**2. Bulk Price Download**

Downloads prices for all portfolio AND benchmark tickers in one efficient API call:

```python
import yfinance as yf

# Get all unique tickers (portfolio + benchmark)
YF_TICKERS = [TICKER_MAPPING.get(t, t) for t in PORTFOLIO_TICKERS] + BENCHMARK_TICKERS

# Bulk download (much faster than individual downloads)
yf_data = yf.download(
    list(set(YF_TICKERS)),  # Deduplicated list
    start="2023-10-22",     # Hard-coded start date
    end="2025-10-22",       # Hard-coded end date
    group_by='ticker',       # Organize by ticker
    auto_adjust=True         # Adjust for splits/dividends
)
```

**What `auto_adjust=True` does**:
- **Stock splits**: Adjusts historical prices so charts don't show fake jumps
  - Example: 2-for-1 split → old prices divided by 2
- **Dividends**: Adjusts prices for dividend payments
- **Result**: "Total return" price series (what you actually earned)

**Why this matters**: Without adjustments, a 2-for-1 split looks like a 50% crash!

**3. Reverse Mapping (Yahoo Finance → Portfolio Conventions)**

After downloading, map tickers BACK to portfolio conventions for storage:

```python
# Create reverse lookup dictionary
REVERSE_MAPPING = {v: k for k, v in TICKER_MAPPING.items()}
# {"IEF": "US10Y", "XBB.TO": "CAN10Y", "LQD": "CORP5"}

# When processing downloaded data:
for yf_ticker in downloaded_tickers:
    portfolio_ticker = REVERSE_MAPPING.get(yf_ticker, yf_ticker)
    # "IEF" becomes "US10Y" for database storage
```

**Why reverse map?**
- Database stores data with YOUR conventions ("US10Y" not "IEF")
- Reports show familiar names
- Easy to understand what you actually own

**4. Cache to CSV File**

Saves downloaded prices to intermediate CSV file:

```python
prices_df.to_csv('data/yf_prices_cache.csv', index=False)
```

**Cache file format**:
```csv
date,ticker,trade_price
2024-11-01,AAPL,225.50
2024-11-01,MSFT,412.80
2024-11-01,US10Y,95.32
2024-11-02,AAPL,227.10
```

**Why cache?**
- **Debugging**: Inspect what was downloaded before it hits database
- **Recovery**: If database insert fails, data isn't lost
- **Audit trail**: Know exactly what prices were used
- **Re-runs**: Can re-insert without re-downloading (saves time/API calls)

**5. Data Validation**

Script validates downloaded data:
- Checks for empty dataframes (invalid ticker)
- Handles single-ticker vs multi-ticker response formats
- Converts dates to consistent format ('YYYY-MM-DD')
- Filters out rows with missing prices

**Ticker Lists**:

```python
PORTFOLIO_TICKERS = [
    "AAPL", "MSFT", "NVDA",      # US Tech
    "SHOP", "TD", "RY", "BNS",   # Canadian  
    "SPY", "XIC.TO",             # Index ETFs
    "US10Y", "CAN10Y", "CORP5"   # Bonds (will be mapped to ETFs)
]

BENCHMARK_TICKERS = [
    "XLK",      # Tech sector ETF
    "XFN.TO",   # Canadian Financials ETF
    "SPY",      # S&P 500
    "XIC.TO",   # TSX Composite
    "XBB.TO",   # Canadian Bonds
    "AGG"       # US Aggregate Bonds
]
```

**Ticker Conventions**:
- **US stocks/ETFs**: Plain ticker ("AAPL", "SPY")
- **Canadian stocks/ETFs**: Add ".TO" suffix ("TD.TO", "XIC.TO")
- **Bonds**: Use portfolio convention ("US10Y") → mapped to ETF

**How to Run**:
```powershell
python src\ingestion\fetch_prices.py
```

**Expected Output**:
```
Downloading yfinance prices for 18 unique tickers...
[*********************100%***********************]  18 of 18 completed
Saved 3420 rows to data\yf_prices_cache.csv
```

**Error Handling**:
- **Invalid ticker**: yfinance returns empty → skipped with warning
- **Network error**: Script fails → retry manually
- **Delisted stock**: yfinance returns empty → remove from ticker lists
- **API rate limits**: Yahoo Finance limits ~2000 requests/hour (we use ~1)

**Performance**:
- 18 tickers × 2 years = ~720 trading days × 18 = ~13,000 data points
- Download time: 30-60 seconds (network dependent)
- Cache write: <1 second

**Important Notes**:
- **No database insert**: This script only downloads and caches
- **Hard-coded dates**: START_DATE and END_DATE are fixed in code
- **To add tickers**: Just add to PORTFOLIO_TICKERS or BENCHMARK_TICKERS lists
- **To add mapping**: Add entry to TICKER_MAPPING dictionary

**Next Step**: Bulk insert from cache CSV to database tables (done separately)

---

## Analytics

### `src/analytics/compute_risk_metrics.py`
**Purpose**: Calculate rolling risk metrics for portfolio and benchmark

**What it does**:
1. Fetches daily returns from `view_returns` SQL view
2. Calculates rolling volatility
3. Calculates tracking error (portfolio vs benchmark)
4. Calculates beta (portfolio sensitivity to benchmark)
5. Inserts results into risk metrics tables

**Metrics Calculated**:

| Metric | Formula | Interpretation |
|--------|---------|---------------|
| **Volatility** | StdDev(Returns) * √252 | Annualized return variability |
| **Tracking Error** | StdDev(Active Returns) * √252 | Deviation from benchmark |
| **Beta** | Cov(Portfolio, Benchmark) / Var(Benchmark) | Market sensitivity |

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
Creates reference tables for dates and securities:
- `dim_dates`: Date dimension with business day flags (used for date-based queries)
- `dim_securities`: Securities master with ticker, name, sector, currency
- `dim_benchmarks`: Benchmark securities master

**Why this matters**: Provides consistent dimension tables for joins and ensures data quality.

---

### SQL Views

#### `sql/views/view_returns.sql`
**Purpose**: Calculate daily returns for portfolio and benchmark

**Critical Views Created**:

**1. `v_portfolio_daily_returns`**: Portfolio-weighted daily returns
```sql
SELECT 
    date,
    SUM(daily_return * market_value) / SUM(market_value) as daily_return,
    SUM(market_value) as total_market_value
FROM historical_portfolio_info
GROUP BY date
```

**This is THE source of truth for portfolio performance**. All risk and attribution calculations use this view.

**2. `v_benchmark_daily_returns`**: Benchmark composite daily returns
```sql
-- Aggregates benchmark component returns weighted by holdings
```

**Why views matter**: 
- Single calculation logic used everywhere (no duplicate code)
- Database optimizes view queries automatically
- Easy to update calculation methodology (change view, affects all downstream)

**Used by**: `compute_risk_metrics.py`, `compute_attribution.py`

#### `sql/views/view_risk_metrics_latest.sql`
**Purpose**: Show most recent risk metrics across all windows

**What it returns**:
```sql
metric_name    | value_30d | value_90d | value_180d
---------------|-----------|-----------|------------
Volatility     | 0.15      | 0.18      | 0.20
Tracking Error | 0.02      | 0.03      | 0.03
Beta           | 0.95      | 1.00      | 1.05
```

**Used for**: Dashboard queries, quick risk snapshots

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
