# Security Screening Page Documentation

## Overview
The Security Screening page (`app/pages/3_Security_Screening.py`) helps users discover quality stocks from the S&P 500 by applying quality filters and performing advanced factor-based analysis.

## Current Implementation (November 2025)

### Purpose
- Screen S&P 500 stocks for quality investments
- Apply automated "bad apple" filters to eliminate problematic stocks
- Rank securities by investment style using factor analysis
- Compare stocks to S&P 500 sector benchmarks
- Cache results for fast re-access within the same day

### Workflow

**Step 1: Asset Class Selection**
- Choose what to screen: Equities, ETFs, Bonds, or All
- Radio button selection
- **Note**: Currently only Equities (stocks) are supported from S&P 500

**Step 2: Load and Screen Universe (Once Per Day)**
- Click "Load Universe and Screen" button
- Button only appears if cache is empty
- Loads S&P 500 tickers from Wikipedia (~500 stocks)
- Applies hardcoded quality filters (detailed below)
- Calculates factor scores for advanced analysis
- Shows progress bar during screening (~3-5 minutes for 500 stocks)
- Results cached for remainder of day
- Cache auto-refreshes at midnight

**Post-Load:**
- Universe remains loaded for the day
- Access Advanced Factor Analysis without reloading
- Click "Rank by Style" → Instant results (uses cached factor scores)
- Click "Analyze Stock" → Instant results (uses cached data)

### Quality Filters (Always Applied)

**1. Market Cap ≥ $1B**
- Filters out micro-cap stocks
- Reduces illiquidity risk
- Focuses on investable universe

**2. Bad Apple Elimination**
Five automated red flag checks:

**Rule 1: Negative Earnings (non-growth sectors)**
- Rejects: Negative P/E unless in Technology, Healthcare, or Communication Services
- Rationale: Unprofitable companies in mature sectors are distressed

**Rule 2: Extreme Debt (non-financials)**
- Rejects: Debt/Equity > 300% for non-financial companies
- Exception: Banks, Real Estate (naturally leverage-intensive)
- Rationale: Excessive leverage increases bankruptcy risk

**Rule 3: Extremely Low ROE**
- Rejects: ROE < -20%
- Rationale: Destroying shareholder value

**Rule 4: Absurd Valuations**
- Rejects: P/E > 500 (likely data error or extreme bubble)
- Rejects: P/B > 50 for non-tech sectors
- Rationale: Unrealistic pricing

**Rule 5: Unsustainable Losses**
- Rejects: Profit Margin < -30% for non-growth sectors
- Exception: Technology, Healthcare, Communication Services
- Rationale: Burning cash too fast

**3. Quality Score (Internal Ranking Only)**
- Simple 0-100 ranking for sorting
- Based on: Profitability (30%), Value (25%), Financial Health (25%), Growth (20%)
- **Not displayed to users** - used only for internal ordering
- Factor analysis is the primary ranking method shown to users

### Daily Caching System

**Implementation:**
```python
# Session state variables:
- universe_cache_date: Stores today's date
- universe_cache: Stores screened DataFrame

# Logic:
if cache_date != today:
    Clear cache
    Set cache_date = today
```

**Benefits:**
- Click off page and return without reloading
- One fetch per day (not per visit)
- Faster user experience
- Reduces API calls to yfinance

### Advanced Factor Analysis

**Only appears if S&P 500 benchmarks loaded**

#### Tab 1: Style-Based Ranking
**Investment Styles (Fundamentals Only):**

1. **Growth Style**
   - Weights: 35% rev growth, 25% earnings growth, 20% margins, 20% ROE
   - Threshold: Revenue growth ≥50th percentile
   - Examples: High-growth tech, emerging sectors

2. **Value Style**
   - Weights: 30% P/E, 25% P/B, 25% FCF yield, 10% ROE, 10% current ratio
   - Thresholds: ROE ≥40%ile, P/E ≥40%ile, Current ratio ≥30%ile
   - Examples: Undervalued quality, dividend value

3. **Quality Style**
   - Weights: 35% ROE, 25% ROIC, 25% margins, 15% debt/equity
   - Thresholds: ROE ≥70%ile, Debt/equity ≥50%ile, Margins ≥60%ile
   - Examples: Wide-moat compounders, blue chips

4. **Balanced (GARP - Growth At Reasonable Price)**
   - Weights: 20% each (rev growth, ROE, P/E, margins, FCF yield, debt/equity)
   - Thresholds: Rev growth ≥40%ile, ROE ≥40%ile
   - Examples: Quality growth at fair valuations

**Process:**
1. Select style from dropdown
2. Choose top N stocks (5-20)
3. Click "Rank by Style"
4. View percentile scores vs sector peers
5. Color-coded gradient on Style Score column

#### Tab 2: Individual Stock Analysis
**Deep-dive for single stock:**
- 4-column layout: Profitability | Growth | Value | Safety
- Each metric shows: Raw value + Percentile rank
- Bar chart of all 10 percentile rankings
- Comparison: "{Sector} sector peers from S&P 500"

**10 Fundamental Metrics:**
- **Profitability**: ROE, Profit Margin, ROIC
- **Growth**: Revenue Growth, Earnings Growth
- **Value**: P/E, P/B, FCF Yield (inverted percentiles - lower is better)
- **Safety**: Debt/Equity (inverted), Current Ratio

### Data Sources

**Ticker Universe:**
- **S&P 500 Stocks Only** (~500 large-cap US companies)
- Source: `src.core.benchmarks.get_sp1500_tickers()` (Wikipedia S&P 500 table)
- Excludes: Mid-cap, small-cap, international stocks, ETFs
- Refreshed: Each screening run (live data from Wikipedia)
- Stored: `st.session_state.sp500_tickers`

**Fundamental Data:**
- **yfinance** `.info` endpoint
- Real-time pricing and fundamentals
- ~0.8 seconds per ticker fetch
- Estimated time: 500 tickers = ~3-5 minutes (initial load only)

**Sector Benchmarks:**
- Pre-built from S&P 500 constituent data
- Used for percentile comparisons in factor analysis
- Cached in `data/sector_benchmarks_cache.json`
- 11 sectors, all ≥20 stocks (statistically valid)
- **Note**: Screening universe = benchmark universe (both S&P 500)

### Results Display

**Main Table Columns:**
1. Rank (by quality score)
2. Ticker
3. Name
4. Quality Score (0-100, internal ranking only)
5. Type (Equity)
6. Sector
7. Market Cap
8. Price
9. P/E Ratio
10. P/B Ratio
11. Dividend Yield
12. Profit Margin
13. Revenue Growth
14. ROE
15. Debt/Equity
16. EV/EBITDA

**Interactive Features:**
- Sortable columns (click header)
- Searchable (Ctrl+F in table)
- Copy to clipboard
- Download as CSV

**Display Notes:**
- No quality summary metrics (removed for simplicity)
- No sector distribution chart (removed for simplicity)
- Direct access to Advanced Factor Analysis tabs

## Technical Details

### Key Functions

1. **`get_ticker_info(ticker, include_fundamentals=False)`**
   - Fetches data from yfinance
   - Determines asset type (Equity only for S&P 500)
   - Returns standardized dict with fundamental metrics

2. **`is_bad_apple(info, asset_class_filter)`**
   - Applies 5 red flag rules
   - Returns (is_bad: bool, reason: str)
   - Sector-aware exceptions

3. **`calculate_quality_score(info)`**
   - Internal ranking algorithm (not displayed to users)
   - 4-component scoring system (Profitability, Value, Financial Health, Growth)
   - Sector-adjusted for P/B (financials vs others)
   - Returns 0-100 score for sorting only

4. **`score_stock_from_info(ticker, info, sector_benchmarks)`**
   - **Performance-optimized function** (no yfinance calls)
   - Calculates all 10 factor percentiles from pre-fetched data
   - Used during initial screening to cache factor scores
   - Returns: Dict with percentile scores for all factors

5. **`rank_stocks_by_style_cached(factor_scores_dict, style, ...)`**
   - **Instant ranking function** (uses cached factor scores)
   - Applies style-specific weights and thresholds
   - No data fetching - pure computation
   - Returns: Ranked DataFrame with style scores

### Database Integration
**None currently** - This page is stateless:
- No saving of screening results
- No user preferences stored
- Pure read-only data fetching
- Cache exists only in session state (memory)

### Performance Optimizations

1. **Factor Score Caching**
   - **Implementation**: During screening, calculate and store all factor percentiles
   - **Storage**: `st.session_state.factor_scores_cache` (dict of {ticker: scores})
   - **Benefit**: Style ranking becomes instant (<1 second vs 5 minutes)
   - **Cache invalidation**: Cleared when new screening run initiated

2. **Two-Path Architecture**
   - **Fast Path**: Check cache → Use `rank_stocks_by_style_cached()` → Instant results
   - **Slow Path**: No cache → Fetch data → Use `get_top_stocks_by_style()` → 2-5 min
   - **Preference**: Always try fast path first

3. **Progress Updates**
   - Every 10 tickers (not every ticker)
   - Reduces UI lag from too many redraws

4. **S&P 500 Only**
   - Limits universe to ~500 stocks (vs 7,000+)
   - Reduces total screening time: 3-5 minutes (down from 7+ minutes)
   - More focused, investable universe
   - Prevents 30+ minute screenings
   - Still covers major investable universe

4. **Daily Caching**
   - Stores entire DataFrame in session_state
   - Date check on page load
   - Clears at midnight automatically

## Next Steps

### Completed Improvements

1. **Remove Optional Filters** ✅ COMPLETED
   - Removed: sample size slider, debt filter, industry filter, country filter, metrics selector
   - Removed: portfolio integration, sector pre-selection
   - Simplified to: Asset class → Load → Results

2. **Daily Caching** ✅ COMPLETED
   - Implemented session state caching
   - Date-based cache invalidation
   - Click off/back without reload

3. **Post-Load Filtering** ✅ COMPLETED
   - Users can filter by sector after loading
   - All fundamentals displayed in table
   - Native Streamlit dataframe filtering

4. **Sector Benchmarks** ✅ COMPLETED
   - S&P 500 as benchmark universe
   - All 11 sectors validated (≥20 stocks each)
   - Factor analysis fully functional

5. **S&P 500 Universe Only** ✅ COMPLETED
   - Restricted to ~500 S&P 500 stocks (from Wikipedia)
   - Removed mid-cap, small-cap, international, ETFs
   - More focused, investable universe

6. **Performance Optimization** ✅ COMPLETED
   - Factor score caching during initial load
   - Instant style ranking (<1 sec vs 5 min)
   - Two-path architecture (fast/slow)
   - Total time reduced: 7 min → 3-5 min

7. **UI Cleanup** ✅ COMPLETED
   - Removed quality summary metrics (4 metrics)
   - Removed sector distribution chart
   - Simplified results display
   - Removed matplotlib dependency

### Planned Future Enhancements

1. **Expand Universe Options**
   - Add toggle for S&P 400 (Mid-cap)
   - Add toggle for S&P 600 (Small-cap)
   - Full S&P 1500 coverage
   - International markets (optional)

2. **Smart Screening**
   - Save custom screening criteria
   - Named screens ("High Quality Dividend Payers")
   - Alert system when new stocks pass criteria
   - Schedule automatic re-screens

3. **Enhanced Factor Analysis**
   - Add technical analysis (momentum, trend, volume)
   - Add sentiment analysis (news, social media)
   - Machine learning stock similarity
   - Predict quality score direction (improving/deteriorating)

4. **Watchlist Integration**
   - Save interesting stocks to watchlist
   - Track price movements
   - Set price alerts
   - One-click add to portfolio

5. **Comparison Tools**
   - Side-by-side stock comparison
   - Peer group analysis (automatic comp selection)
   - Historical factor evolution
   - What-if scenarios

6. **Export & Sharing**
   - Export screening results to Excel
   - Share screens via link
   - PDF report generation
   - Email alerts for new matches

### Technical Debt

1. **No Authentication**
   - Currently no user context (stateless)
   - Can't save preferences or screens
   - When auth added, migrate to user-specific caching

2. **yfinance Dependency**
   - Free but rate-limited
   - Occasional data quality issues
   - No SLA or support
   - Consider: Bloomberg, FactSet, Alpha Vantage for production

3. **Error Handling**
   - Generic error messages
   - Failed tickers silently skipped
   - Should log failures and show summary
   - Retry logic for transient errors

4. **No Unit Tests**
   - Quality score calculation not tested
   - Bad apple logic not validated
   - Factor scoring functions not tested
   - Regression risk when modifying

5. **Hardcoded Constants**
   - Market cap threshold ($1B)
   - Bad apple thresholds (300% D/E, -20% ROE, etc.)
   - Should be configurable

### Known Limitations

- **S&P 500 Only**: Limited to large-cap US stocks (no mid-cap, small-cap, international)
- **Data Lag**: yfinance can be 15-20 minutes delayed
- **No Backtesting**: Can't see how screens performed historically
- **Static Criteria**: Filters don't adapt to market conditions
- **No FX Conversion**: All data in USD (no currency adjustments)

## Dependencies
- `streamlit`: UI framework
- `pandas`: Data manipulation
- `numpy`: Numerical operations
- `yfinance`: Market data
- `datetime`: Date handling
- `src.core.benchmarks`: S&P 500 ticker loading (Wikipedia)
- `src.analytics.sector_benchmarks`: Sector benchmark calculations
- `src.analytics.factor_scoring`: Factor percentile calculations (including `score_stock_from_info`)
- `src.analytics.investment_styles`: Style ranking logic (including `rank_stocks_by_style_cached`)

## File Location
`c:\Users\Kevin Kwan\PM-app\app\pages\3_Security_Screening.py`

## Related Files
- `src/core/benchmarks.py` - S&P 500 ticker loading (Wikipedia source)
- `src/analytics/sector_benchmarks.py` - Benchmark building and caching
- `src/analytics/factor_scoring.py` - Factor percentile calculations (original + cached versions)
- `src/analytics/investment_styles.py` - Style ranking (original + cached versions)
- `src/analytics/investment_styles.py` - Style definitions and ranking
- `data/sector_benchmarks_cache.json` - Pre-built S&P 500 benchmarks

## Recent Changes (November 17, 2025)

**Major Cleanup:**
- Removed 412 lines of unused code (32% reduction)
- Deleted 7 unused functions
- Simplified from Step 1-4 to Step 1-2
- Removed portfolio integration complexity
- Streamlined to fundamentals-only approach

**Current State:**
- 862 lines (down from 1,274)
- Clean, focused codebase
- All remaining code actively used
- No technical debt in page logic
