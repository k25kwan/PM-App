# PM-App: Daily Portfolio Management System

A Python-based portfolio management system for tracking daily portfolio performance, risk metrics, and attribution analysis.

## Overview

PM-App is a **forward-filling** portfolio management system designed for single-user portfolio tracking and analysis. Unlike traditional systems that require historical data loading, PM-App builds your portfolio history incrementally - starting from today and growing forward each day.

### Core Philosophy: Forward-Filling Architecture

The system is built around a simple principle: **you start with your current portfolio positions, and the system automatically builds history going forward**. Each day adds one new data point to your metrics - no complex backfilling, no historical data imports.

### What PM-App Does

1. **Daily Price Tracking**: Automatically fetches latest prices from Yahoo Finance for your holdings
2. **Risk Analytics**: Calculates comprehensive rolling risk metrics (volatility, tracking error, beta, VaR, Sharpe ratio)
3. **Attribution Analysis**: Decomposes portfolio returns vs benchmark into allocation and selection effects using Brinson-Fachler methodology
4. **SQL Server Backend**: Structured relational database that preserves full history and supports complex queries

### Who This Is For

- Individual investors managing their own portfolios
- Portfolio managers tracking client accounts
- Finance students learning quantitative portfolio analysis
- Anyone who wants institutional-grade analytics for personal investing

## Features

- **Automated Price Updates**: Fetches daily prices from Yahoo Finance with intelligent ticker mapping (e.g., bond proxies via ETFs)
- **Comprehensive Risk Metrics**: 
  - Market Risk: VaR (95%, 99%), Expected Shortfall, Volatility, Max Drawdown, Sharpe Ratio
  - Relative Risk: Beta, Tracking Error, Information Ratio, Active Return
  - Concentration Risk: HHI (Herfindahl-Hirschman Index)
  - Duration Risk: DV01 (Dollar Value of a Basis Point)
- **Expanding Window Analysis**: All metrics calculated using entire history from earliest to latest data point (not fixed rolling windows)
- **Sector-Level Attribution**: Brinson-Fachler attribution by sector for equity and fixed income separately
- **Database-Driven**: All calculations flow through SQL Server views ensuring data consistency
- **PowerShell Automation**: One-command daily updates that handle the entire workflow

## Quick Start

### Prerequisites

- Python 3.10+
- SQL Server Express (or any SQL Server instance)
- Git

### Installation

1. **Clone the repository**
   ```powershell
   git clone https://github.com/k25kwan/PM-App.git
   cd PM-App
   ```

2. **Install Python dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   - Copy `.env.example` to `.env`
   - Update database connection details:
     ```
     DB_SERVER=your_server_name
     DB_NAME=RiskDemo
     DB_DRIVER=ODBC Driver 17 for SQL Server
     ```

4. **Initialize database**
   ```powershell
   # Run schemas in order
   sqlcmd -S your_server -d RiskDemo -i sql\schemas\01_core_portfolio.sql
   sqlcmd -S your_server -d RiskDemo -i sql\schemas\02_risk_metrics.sql
   sqlcmd -S your_server -d RiskDemo -i sql\schemas\03_attribution.sql
   
   # Load seed data (date dimensions only)
   sqlcmd -S your_server -d RiskDemo -i sql\seed_data\seed_dimensions.sql
   
   # Create views
   sqlcmd -S your_server -d RiskDemo -i sql\views\view_returns.sql
   sqlcmd -S your_server -d RiskDemo -i sql\views\view_risk_metrics_latest.sql
   ```

5. **Input initial portfolio holdings**
   - Manually insert holdings into `historical_portfolio_info` table
   - Specify `date`, `ticker`, `market_value`, `sector`, `name`, etc.
   - Example:
     ```sql
     INSERT INTO historical_portfolio_info (date, ticker, sector, name, market_value, currency)
     VALUES 
         ('2024-01-01', 'AAPL', 'Tech', 'Apple Inc.', 15000.00, 'USD'),
         ('2024-01-01', 'MSFT', 'Tech', 'Microsoft Corp.', 12000.00, 'USD'),
         ('2024-01-01', 'TD', 'Financials', 'Toronto-Dominion Bank', 8000.00, 'CAD');
     ```

**Important**: The system is designed to **start from today and build forward**. You don't need historical data - just input your current positions and let the system accumulate history naturally as you run daily updates.

### Daily Workflow

The system follows a three-stage pipeline that runs daily:

```powershell
.\scripts\run_daily_update.ps1
```

This executes:

**Stage 1: Price Ingestion** (`fetch_prices.py`)
- Downloads latest prices from Yahoo Finance for all portfolio + benchmark tickers
- Applies ticker mapping (e.g., "US10Y" → "IEF" ETF proxy for bonds)
- Saves to `data/yf_prices_cache.csv` as intermediate cache
- Bulk inserts into `historical_portfolio_info` and `historical_benchmark_info` tables
- Reverse-maps ticker names back to portfolio conventions

**Stage 2: Risk Calculation** (`compute_risk_metrics.py`)  
- Loads portfolio and benchmark returns from database views
- Calculates comprehensive risk metrics for **today only** (incremental, not full recalculation):
  - Market Risk: VaR 95%, VaR 99%, Expected Shortfall, Volatility, Max Drawdown, Sharpe Ratio
  - Relative Risk: Beta, Tracking Error, Information Ratio, Active Return
  - Concentration: HHI (portfolio concentration index)
  - Duration: DV01 (interest rate sensitivity)
- Computes each metric across 30/90/180-day rolling windows
- Inserts results into `portfolio_risk_metrics` table

**Stage 3: Attribution Analysis** (`compute_attribution.py`)
- Loads portfolio sector weights and returns
- Loads benchmark sector weights and returns  
- Applies Brinson-Fachler attribution methodology:
  - **Allocation Effect**: Returns from sector weighting decisions
  - **Selection Effect**: Returns from security selection within sectors
  - **Interaction Effect**: Combined allocation + selection impact
- Calculates for Total Portfolio, Equity-Only, and Fixed Income-Only
- Inserts into `portfolio_attribution` table

**Key Design Principle**: Each stage is **incremental** - it adds today's data point without recalculating historical metrics. This makes the system fast and predictable.

You can also run individual stages:
```powershell
.\scripts\run_daily_update.ps1 -Step prices       # Only fetch prices
.\scripts\run_daily_update.ps1 -Step risk         # Only calculate risk
.\scripts\run_daily_update.ps1 -Step attribution  # Only calculate attribution
```

## Project Structure

```
PM-app/
├── src/
│   ├── core/                    # Core utilities
│   │   ├── utils_db.py          # Database connection
│   │   └── data_sanitizers.py   # Data cleaning functions
│   ├── ingestion/               # Data ingestion
│   │   └── fetch_prices.py      # Fetch Yahoo Finance prices
│   └── analytics/               # Analytics calculations
│       ├── compute_risk_metrics.py    # Risk metrics
│       └── compute_attribution.py     # Attribution analysis
├── sql/
│   ├── schemas/                 # Database schemas (MUST apply in order)
│   │   ├── 01_core_portfolio.sql      # Portfolio holdings, prices, benchmarks
│   │   ├── 02_risk_metrics.sql        # Risk metrics tables
│   │   └── 03_attribution.sql         # Attribution tables and views
│   ├── seed_data/               # Reference data
│   │   └── seed_dimensions.sql        # Date and security dimensions
│   └── views/                   # SQL views for reporting
│       ├── view_returns.sql           # Portfolio/benchmark returns (CRITICAL)
│       └── view_risk_metrics_latest.sql  # Latest risk metrics summary
├── scripts/
│   └── run_daily_update.ps1     # Daily update automation
├── data/                        # Price cache (JSON files)
├── docs/                        # Documentation
├── requirements.txt             # Python dependencies
└── .env.example                 # Environment variable template
```

## Database Schema

### Core Tables

**`historical_portfolio_info`**: Daily portfolio positions and returns
- Stores daily snapshots of each holding with market value, returns, sector classification
- Primary source for portfolio analysis
- Populated by price ingestion and manual position updates

**`f_positions`**: Current portfolio positions summary
- Snapshot view of latest positions
- Used for reporting current state

**`dim_securities`**: Securities master dimension
- Reference data for tickers, names, sectors, currencies
- Ensures consistent classification across the system

**`dim_dates`**: Date dimension
- Calendar with business day flags
- Supports date-based filtering and aggregations

**`historical_benchmark_info`**: Benchmark holdings and returns  
- Daily prices and returns for benchmark ETFs
- Parallel structure to portfolio for consistent comparison

**`dim_benchmarks`**: Benchmark securities master
- Reference data for benchmark components

### Risk Metrics Tables

**`portfolio_risk_metrics`**: Calculated risk metrics over time
- Stores all risk metrics with their calculation date, window period, and values
- Each metric stored as separate row with category classification
- Unique constraint on (asof_date, metric_name, lookback_days)

Example metrics stored:
- VOL_030D, VOL_090D, VOL_180D (volatility)
- TE_030D, TE_090D, TE_180D (tracking error)
- BETA_030D, BETA_090D, BETA_180D
- VAR_95, VAR_99 (Value at Risk)
- ES_95, ES_99 (Expected Shortfall)
- SHARPE_RATIO, INFO_RATIO
- MAX_DD (Maximum Drawdown)
- HHI (Herfindahl-Hirschman Index - concentration)
- DV01 (Duration risk)

### Attribution Tables

**`portfolio_attribution`**: Brinson-Fachler attribution analysis
- Daily decomposition of returns into allocation, selection, and interaction effects
- Calculated at sector level
- Supports multiple attribution types: TOTAL, EQUITY, FIXED_INCOME
- Each row represents one sector's attribution for one day

**Key Fields**:
- `allocation_effect`: Returns from sector weighting decisions
- `selection_effect`: Returns from security selection within sectors  
- `interaction_effect`: Combined effect
- `portfolio_weight`, `benchmark_weight`: Sector weights for comparison
- `portfolio_return`, `benchmark_return`: Sector returns for the period

### Critical SQL Views

**`v_portfolio_daily_returns`**: Portfolio-level daily returns
- Calculates value-weighted portfolio return each day
- **This is THE source of truth for portfolio performance**
- Used by all downstream risk and attribution calculations

**`v_benchmark_daily_returns`**: Benchmark composite daily returns
- Aggregates benchmark component returns
- Weighted by benchmark holdings
- Parallel calculation to portfolio for consistent comparison

**`v_attribution_summary`**: Latest attribution aggregated across sectors
- Quick view of total allocation, selection, and interaction effects
- Summarized by attribution type (TOTAL/EQUITY/FIXED_INCOME)

**`v_attribution_latest`**: Latest attribution by sector
- Detailed sector-level breakdown
- Includes basis point conversions for easy interpretation
- Color-coded status indicators

**`v_risk_metrics_latest`**: Most recent risk metrics
- Latest value for each risk metric across all time windows
- Used for dashboard/reporting views

## Key Concepts

### Forward-Filling vs. Backfilling

**Traditional Systems** (Backfilling):
- Import years of historical data upfront
- Complex data alignment and cleaning
- Requires complete historical holdings records
- Prone to survivorship bias

**PM-App** (Forward-Filling):
- Start with today's portfolio
- Each day adds one new data point
- History builds naturally over time
- No historical data migration needed
- Clean, incremental growth

**Example Timeline**:
```
Day 1:  Input current holdings → Run update → 1 day of data
Day 2:  Run update → 2 days of data → Minimal metrics calculated
Day 30: Run update → 30 days of data → More robust metrics
Day 90: Run update → 90 days of data → Increasingly stable metrics
Day 180+: Run update → Extensive history → Highly reliable metrics
```

### Expanding Window Approach

Unlike traditional rolling windows (e.g., "last 30 days", "last 90 days"), PM-App uses an **expanding window from inception**:

**How it works:**
- Day 1: Calculate metrics using 1 day of data
- Day 30: Calculate metrics using all 30 days of data
- Day 100: Calculate metrics using all 100 days of data
- Day 365: Calculate metrics using all 365 days of data

**Why expanding windows?**
- **More data = better estimates**: As history accumulates, metrics become more statistically reliable
- **Consistent baseline**: Always comparing against your entire track record, not arbitrary time slices
- **True performance**: Captures your full investment experience, not just recent periods
- **Simpler logic**: No arbitrary decisions about "is 30 days enough?" or "should we use 60 vs 90?"

**Trade-off**: Recent market changes are weighted equally with older data. For risk management focused on current conditions, you may want to supplement with manual short-term analysis.

**Practical implications:**
- Volatility stabilizes over time (less noisy with more data)
- Sharpe ratio becomes more meaningful after 6-12 months
- Max drawdown captures worst period across entire history
- Beta/tracking error reflect long-term relationship with benchmark

### Attribution Methodology

PM-App uses the **Brinson-Fachler attribution model**, the industry standard for performance attribution:

**Three Attribution Effects**:

1. **Allocation Effect** = (Portfolio Weight - Benchmark Weight) × Benchmark Return
   - Measures returns from sector timing decisions
   - Positive: You overweighted sectors that outperformed
   - Example: Overweight Tech by 5%, Tech returns +2% → Allocation = +0.10%

2. **Selection Effect** = Benchmark Weight × (Portfolio Return - Benchmark Return)  
   - Measures returns from security selection within sectors
   - Positive: Your stocks outperformed their sector benchmark
   - Example: Your Tech stocks return +3% vs Tech benchmark +2%, Tech weight 40% → Selection = +0.40%

3. **Interaction Effect** = (Portfolio Weight - Benchmark Weight) × (Portfolio Return - Benchmark Return)
   - Measures combined effect of allocation + selection
   - Positive: You overweighted sectors where you also picked good stocks
   - Example: Overweight Tech by 5%, your Tech beats benchmark by 1% → Interaction = +0.05%

**Total Active Return** = Allocation + Selection + Interaction

**Why this matters**: 
- Attribution tells you **where** your returns came from
- Separate skill (selection) from luck (allocation)
- Identify which sectors/decisions added value
- Guide future portfolio decisions

### Ticker Mapping Strategy

Some portfolio instruments (especially bonds) don't have direct ticker symbols on Yahoo Finance. PM-App uses **ETF proxies**:

**Bond Proxies**:
- `US10Y` → `IEF` (iShares 7-10 Year Treasury Bond ETF)
- `CAN10Y` → `XBB.TO` (iShares Core Canadian Universe Bond Index ETF)  
- `CORP5` → `LQD` (iShares iBoxx Investment Grade Corporate Bond ETF)

**How it works**:
1. `fetch_prices.py` maps portfolio tickers → yfinance tickers
2. Downloads prices using yfinance tickers
3. **Reverse maps** back to portfolio tickers before database insert
4. Database stores data with original portfolio ticker names

**Why this approach?**:
- Portfolio conventions remain consistent
- Bond exposure tracked via highly liquid ETFs
- ETFs provide continuous pricing (bonds can be illiquid)
- Easy to extend with new mappings

## Development

### Data Flow Architecture

**The database is the system's backbone**. All calculations flow through SQL views:

```
Raw Data (Tables)           Views (Calculations)              Analytics (Python)
─────────────────          ────────────────────             ──────────────────
historical_portfolio_info                                   
                    ─────> v_portfolio_daily_returns ────> compute_risk_metrics.py
historical_benchmark_info                                   compute_attribution.py
                    ─────> v_benchmark_daily_returns ───>   
```

**Critical Design Principle**: Python scripts are **stateless**. They:
1. Query views for data (views do the heavy lifting)
2. Perform calculations
3. Insert results back to tables
4. Exit

No in-memory state persists between runs. This makes the system predictable and debuggable.

### Adding New Tickers

**For Portfolio Holdings**:
```sql
-- Just insert new holding with sector/name metadata
INSERT INTO historical_portfolio_info (date, ticker, sector, name, market_value, currency)
VALUES ('2024-11-11', 'GOOGL', 'Tech', 'Alphabet Inc.', 10000.00, 'USD');
```

Prices will be fetched automatically on next run.

**If ticker needs mapping** (e.g., a bond):
Edit `src/ingestion/fetch_prices.py`:
```python
TICKER_MAPPING = {
    "US10Y": "IEF",      # Existing
    "EU10Y": "IEAG",     # Add new mapping
}
```

**For Benchmark Components**:
```sql
-- Add to dim_benchmarks
INSERT INTO dim_benchmarks (benchmark_id, ticker, name, sector, base_ccy)
VALUES (7, 'QQQ', 'Invesco QQQ Trust', 'Tech', 'USD');

-- Add to benchmark history (prices fetched automatically)
```

### Modifying Risk Windows

Edit `src/analytics/compute_risk_metrics.py`:
```python
# Current windows
windows = [30, 90, 180]

# Add 252-day (1-year) window
windows = [30, 90, 180, 252]
```

Risk metrics will automatically calculate for new windows on next run.

### Customizing Attribution Sectors

Attribution uses sector mappings from the database. To add/modify sectors:

1. Update sector in `historical_portfolio_info`:
```sql
UPDATE historical_portfolio_info 
SET sector = 'New Sector Name'
WHERE ticker = 'XYZ';
```

2. Ensure benchmark has same sector mapping in `dim_benchmarks`

3. Run attribution - it will automatically group by the new sectors

### Database Connection Patterns

**Always use `get_conn()` from `utils_db.py`**:
```python
from src.core.utils_db import get_conn

with get_conn() as cn:
    df = pd.read_sql("SELECT * FROM v_portfolio_daily_returns", cn)
```

**Why?**:
- Centralizes connection logic
- Handles autocommit automatically  
- Loads credentials from `.env`
- Supports both Windows Auth and SQL Auth

### Data Sanitization

**Always sanitize before SQL inserts** to handle NaN, infinity, None:

```python
from src.core.data_sanitizers import sanitize_decimal, sanitize_string

# Sanitize financial values
clean_value = sanitize_decimal(possibly_nan_value, default=0)

# Sanitize text fields  
clean_text = sanitize_string(possibly_none_text, default='')
```

**Why?**: SQL Server rejects NaN and infinity. Pandas often produces these in calculations. Sanitizers ensure clean inserts.

## Troubleshooting

### Database Connection Issues
**Symptoms**: "Login failed", "Cannot connect to server"

**Solutions**:
- Verify SQL Server is running: Open Services → Find "SQL Server (instance_name)"
- Check firewall: Allow port 1433 for SQL Server
- Confirm ODBC driver installed: Run `odbcad32.exe` → Drivers tab → Look for "ODBC Driver 17 for SQL Server"
- Test connection: `sqlcmd -S your_server -d RiskDemo -Q "SELECT @@VERSION"`
- Verify `.env` settings:
  ```
  DB_SERVER=localhost\SQLEXPRESS  # or your server name
  DB_NAME=RiskDemo
  AUTH_MODE=windows  # or provide DB_USER/DB_PASS
  ```

### Missing Prices
**Symptoms**: "No price data for ticker XYZ", empty `yf_prices_cache.csv`

**Solutions**:
- Check ticker exists on Yahoo Finance: Visit `https://finance.yahoo.com/quote/XYZ`
- For Canadian stocks: Add `.TO` suffix (e.g., `TD.TO` not `TD`)
- For bonds: Ensure ticker mapping exists in `fetch_prices.py`
- Check internet connection
- Review `data/yf_prices_cache.csv` to see what was downloaded
- Try downloading single ticker manually:
  ```python
  import yfinance as yf
  yf.download("AAPL", start="2024-01-01", end="2024-11-11")
  ```

### Import Errors
**Symptoms**: "ModuleNotFoundError: No module named 'src'"

**Solutions**:
- Ensure all `src/` subdirectories have `__init__.py` files:
  ```
  src/__init__.py
  src/core/__init__.py
  src/ingestion/__init__.py  
  src/analytics/__init__.py
  ```
- Set PYTHONPATH to project root:
  ```powershell
  $env:PYTHONPATH = "C:\Users\Kevin Kwan\PM-app"
  ```
- The `run_daily_update.ps1` script sets this automatically
- If running Python scripts directly, set PYTHONPATH first

### Risk Calculation Failures
**Symptoms**: "Insufficient data for 90-day window", metrics show NULL

**Root Cause**: Risk metrics require minimum data points:
- 30-day window → Need 30 days of returns
- 90-day window → Need 90 days of returns  
- 180-day window → Need 180 days of returns

**Solutions**:
- Wait for more data to accumulate (system builds forward)
- Check `v_portfolio_daily_returns` view has enough rows:
  ```sql
  SELECT COUNT(*) FROM v_portfolio_daily_returns;
  ```
- Temporarily reduce window size for testing
- Verify returns are not NULL in view (check price data exists)

### Attribution Shows NULL
**Symptoms**: Attribution results empty or NULL values

**Solutions**:
- Verify benchmark data exists:
  ```sql
  SELECT * FROM historical_benchmark_info WHERE date = '2024-11-11';
  ```
- Check sector mappings in `compute_attribution.py` match database sectors
- Ensure portfolio has sector classifications:
  ```sql
  SELECT DISTINCT sector FROM historical_portfolio_info WHERE sector IS NULL;
  ```
- Verify both portfolio and benchmark have returns for same dates:
  ```sql
  SELECT p.date, p.daily_return, b.daily_return
  FROM v_portfolio_daily_returns p
  FULL OUTER JOIN v_benchmark_daily_returns b ON p.date = b.date
  WHERE p.daily_return IS NULL OR b.daily_return IS NULL;
  ```

## Contributing

This project is maintained for personal portfolio management. For questions or suggestions, please contact the repository owner.

## License

Private project - not for redistribution.
