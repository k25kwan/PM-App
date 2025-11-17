# Add Portfolio Page Documentation

## Overview
The Add Portfolio page (`app/pages/2_Add_Portfolio.py`) enables users to create and manage multiple portfolios, add holdings, and view current positions.

## Current Implementation

### Purpose
- Create new portfolios with names and descriptions
- View list of existing portfolios
- Add/edit holdings for each portfolio
- Delete portfolios
- Manual position entry (ticker, shares, price)

### Key Features

#### 1. Portfolio List View
- Displays all portfolios for the logged-in user
- Shows: Name, Description, Created Date, Status (Active/Inactive)
- Ordered by creation date (newest first)
- Click to expand and view holdings

#### 2. Create New Portfolio
**Form Fields:**
- Portfolio Name (required, text input)
- Description (optional, text area)
- Submit button creates portfolio in database

**Process:**
1. User enters portfolio details
2. System validates name is not empty
3. Creates record in `portfolios` table
4. Returns new portfolio ID
5. Success message displayed

#### 3. Add Holdings
**Manual Entry:**
- Ticker symbol (e.g., AAPL, MSFT)
- Number of shares (quantity)
- Purchase price per share
- Date of purchase
- System auto-fetches:
  - Company name
  - Sector
  - Current price
  - Currency

**Validation:**
- Ticker must exist in yfinance
- Shares must be > 0
- Price must be > 0
- Date cannot be in future

#### 4. View Holdings
**Display Columns:**
- Ticker
- Name
- Sector
- Market Value
- Currency
- Date (as of date)

**Features:**
- Sortable by any column
- Searchable table
- Total portfolio value calculated
- Grouped by sector

#### 5. Delete Portfolio
- Confirmation dialog required
- Deletes portfolio AND all holdings (cascade)
- Updates `f_positions` and `historical_portfolio_info` tables

### Database Schema

**Table: `portfolios`**
```sql
id (PK)
user_id (FK)
portfolio_name
description
created_at
updated_at
is_active
```

**Table: `f_positions`**
```sql
id (PK)
portfolio_id (FK)
ticker
name
sector
shares
price
market_value
currency
asof_date
created_at
```

**Table: `historical_portfolio_info`**
```sql
id (PK)
portfolio_id (FK)
ticker
name
sector
market_value
currency
date
created_at
```

### Technical Details

#### Key Functions

1. **`load_user_portfolios(user_id)`**
   - Fetches all portfolios for user
   - Returns list of portfolio dicts
   - Includes metadata (name, description, dates)

2. **`create_portfolio(user_id, portfolio_name, description)`**
   - Inserts new portfolio record
   - Returns new portfolio_id
   - Handles database errors gracefully

3. **`delete_portfolio(portfolio_id)`**
   - Cascading delete (holdings → portfolio)
   - Transaction-safe
   - Returns success boolean

4. **`load_portfolio_holdings(portfolio_id)`**
   - Gets current positions for portfolio
   - Queries most recent date in historical_portfolio_info
   - Returns DataFrame

5. **`add_holding(portfolio_id, ticker, shares, price, date)`**
   - Fetches ticker data from yfinance
   - Inserts into both f_positions and historical_portfolio_info
   - Calculates market value (shares * price)
   - Handles data validation

6. **`get_portfolio_benchmark_composition(portfolio_id)`**
   - Determines appropriate benchmark based on holdings
   - Used for performance comparison
   - Returns benchmark ticker and weights

### Data Flow
```
User creates portfolio → Add holdings manually → View positions → 
Optional: Edit/Delete → Data stored in database → 
Used by Portfolio Dashboard for analytics
```

### UI Components
- **Tabs**: Separate tabs for "Create Portfolio" and "Manage Portfolios"
- **Expanders**: Collapse/expand portfolio details
- **Forms**: Streamlit forms for data entry
- **Dataframes**: Interactive tables for holdings
- **Buttons**: Create, Add, Delete actions

## Next Steps

### Discussed Improvements

1. **Bulk Import**
   - CSV upload for holdings
   - Support for broker statements (CSV, PDF parsing)
   - Template download for proper format
   - Validation and error reporting

2. **Holdings Management**
   - Edit existing positions (change shares/price)
   - Partial sells (reduce position size)
   - Corporate actions (splits, dividends, mergers)
   - Historical position tracking (time series)

3. **Portfolio Templates**
   - Pre-built portfolio suggestions
   - One-click clone from IPS allocations
   - Industry standard portfolios (60/40, All Weather, etc.)
   - Lazy portfolios (Bogleheads 3-fund, etc.)

4. **Data Enrichment**
   - Real-time price updates
   - Auto-refresh market values
   - Cost basis tracking (FIFO/LIFO)
   - Realized/unrealized gains

5. **Validation Enhancements**
   - Check for duplicate tickers
   - Warn on over-concentration (>10% in single position)
   - Flag when portfolio drifts from IPS targets
   - Suggest rebalancing opportunities

6. **Benchmark Assignment**
   - Auto-suggest benchmark based on portfolio composition
   - Custom benchmark creation (weighted blend)
   - Compare portfolio to benchmark on creation

### Technical Debt

1. **Data Model Redundancy**
   - `f_positions` and `historical_portfolio_info` have overlapping data
   - Should consolidate into single time-series table
   - Add effective_date ranges for proper temporal queries

2. **Hardcoded User**
   - `user_id = 1` hardcoded - needs authentication
   - No session management
   - Multi-user support exists in DB but not UI

3. **Error Handling**
   - Generic error messages
   - No rollback on partial failures
   - yfinance failures not handled gracefully

4. **Performance**
   - N+1 query problem when loading holdings for multiple portfolios
   - Should batch fetch ticker data
   - No caching of yfinance responses

### Known Limitations

- **No Edit Functionality**: Can't modify existing holdings (must delete and re-add)
- **No Lot Tracking**: Can't track multiple purchases of same ticker separately
- **Date Handling**: Assumes all holdings added on same date
- **Currency**: Supports multiple currencies but no FX conversion
- **Benchmarking**: Benchmark assignment is basic (could be more sophisticated)

## Dependencies
- `streamlit`: UI framework
- `pandas`: Data manipulation
- `yfinance`: Ticker data fetching
- `src.core.utils_db`: Database utilities
- `src.core.benchmark_utils`: Benchmark assignment logic

## File Location
`c:\Users\Kevin Kwan\PM-app\app\pages\2_Add_Portfolio.py`

## Related Files
- `sql/schemas/01_core_portfolio.sql` - Database schema
- `app/pages/1_IPS_Questionnaire.py` - Previous step (defines allocation)
- `app/pages/4_Portfolio_Dashboard.py` - Next step (view analytics)
- `src/core/benchmark_utils.py` - Benchmark selection logic
