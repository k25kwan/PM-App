# Testing & Demo Scripts

## ⚠️ These scripts are for DEVELOPMENT/TESTING ONLY

The scripts in this directory are **optional** and only used for testing the dashboard with sample data. They are **NOT** required for production use.

---

## Testing Scripts Overview

### 1. `create_sample_portfolio.py`
**Purpose**: Creates a sample portfolio for testing dashboard visualizations

**What it does**:
- Creates a portfolio named "My Growth Portfolio"
- Adds 10 holdings with realistic market values
- Fetches historical prices from 1 year ago
- Populates `f_positions` and `historical_portfolio_info` tables

**How to use**:
```powershell
python scripts/create_sample_portfolio.py
```

**How to disable**: Simply don't run this script. The dashboard works with portfolios created through the UI.

**How to remove sample data**:
```sql
DELETE FROM historical_portfolio_info WHERE portfolio_id = (SELECT id FROM portfolios WHERE portfolio_name = 'My Growth Portfolio');
DELETE FROM f_positions WHERE portfolio_id = (SELECT id FROM portfolios WHERE portfolio_name = 'My Growth Portfolio');
DELETE FROM portfolios WHERE portfolio_name = 'My Growth Portfolio';
```

---

### 2. `backfill_portfolio_prices.py`
**Purpose**: Backfills 1 year of historical price data for testing performance charts

**What it does**:
- Downloads daily prices from yfinance for all portfolio holdings
- Forward-fills weekends/holidays for continuous time series
- Calculates daily returns and cumulative returns
- Populates `historical_portfolio_info` table with historical data

**How to use**:
```powershell
python scripts/backfill_portfolio_prices.py
```

**How to disable**: Simply don't run this script. The dashboard works with forward-filled data from portfolio creation date.

**How to remove backfilled data**:
```sql
DELETE FROM historical_portfolio_info WHERE portfolio_id = [your_portfolio_id];
```

---

## Production Workflow (Without Testing Scripts)

In production, the system works **forward-filling only**:

1. **User creates portfolio** through Streamlit UI (`2_Add_Portfolio.py`)
   - Portfolio is created with current date
   - Holdings are added with today's prices

2. **Daily price ingestion** runs via scheduled task
   - `fetch_prices.py` downloads latest prices from yfinance
   - Inserts into `historical_portfolio_info` for **today only**
   - Each day adds one new row per ticker

3. **Dashboard displays data** from creation date forward
   - Composition charts show current holdings
   - Performance charts show cumulative returns from creation date
   - Risk metrics calculated from available history
   - Attribution analysis based on available data

**No historical backfilling is performed in production.**

---

## When to Use Testing Scripts

✅ **Use these scripts when**:
- Developing new dashboard features
- Testing performance/risk calculations with realistic data
- Demonstrating the system to stakeholders
- Need to see charts with 1 year of history immediately

❌ **Don't use these scripts when**:
- Deploying to production
- Managing real user portfolios
- The system has been running for weeks/months (real history exists)

---

## Other Production Scripts

### `run_daily_update.ps1`
**Status**: ✅ **PRODUCTION SCRIPT**

This is the **main production workflow** that should run daily:

```powershell
.\scripts\run_daily_update.ps1          # Run all steps
.\scripts\run_daily_update.ps1 -Step prices      # Just fetch prices
.\scripts\run_daily_update.ps1 -Step risk        # Just compute risk metrics
.\scripts\run_daily_update.ps1 -Step attribution # Just compute attribution
```

**What it does**:
1. **Prices**: Fetches today's prices from yfinance → `data/yf_prices_cache.csv` → bulk insert to database
2. **Risk**: Calculates rolling risk metrics for today only
3. **Attribution**: Calculates today's attribution effects

**This is the only script needed for production daily operations.**

---

## Summary

| Script | Purpose | Production Use | Can Be Removed |
|--------|---------|----------------|----------------|
| `create_sample_portfolio.py` | Create test portfolio | ❌ Testing only | ✅ Yes |
| `backfill_portfolio_prices.py` | Backfill historical data | ❌ Testing only | ✅ Yes |
| `run_daily_update.ps1` | Daily price/risk/attribution update | ✅ Required | ❌ No |

---

## Questions?

- **"Do I need historical data?"** → No, the system is designed for forward-filling
- **"How do I test the dashboard?"** → Run the testing scripts to create sample data
- **"How do I clean up test data?"** → Use the SQL DELETE commands above
- **"What runs in production?"** → Only `run_daily_update.ps1` (scheduled daily)
