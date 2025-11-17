# Portfolio Dashboard Page Documentation

## Overview
The Portfolio Dashboard (`app/pages/4_Portfolio_Dashboard.py`) provides comprehensive visualization and analysis of portfolio composition, performance, risk metrics, and attribution analysis against sector-specific benchmarks.

## Current Implementation

### Purpose
- Visualize portfolio composition (sectors, holdings, concentration)
- Track performance vs sector-weighted benchmarks
- Calculate comprehensive risk metrics (market, relative, concentration)
- Perform Brinson-Fachler attribution analysis

### Workflow

**Step 1: Portfolio Selection**
- Dropdown menu of all user portfolios
- Sidebar filter for easy switching

**Step 2: Date Range Selection**
- Pre-configured ranges: Last 30/90 Days, YTD, All Time
- Custom date picker for specific periods

**Step 3: View Analysis**
Four main sections:
1. Composition charts and tables
2. Performance vs benchmark
3. Risk metrics (market, relative, concentration)
4. Attribution analysis (allocation, selection, interaction)

### Composition Analysis

**Visualizations:**

1. **Sector Allocation Pie Chart**
   - Shows portfolio breakdown by sector
   - Donut chart with percentages
   - Hover shows: Sector name, $ value, % weight

2. **Ticker Allocation Pie Chart**
   - Top 10 holdings by market value
   - Identifies concentration in specific securities
   - Useful for detecting single-stock risk

3. **Portfolio Metrics Summary**
   - Total Value: Sum of all holdings
   - Number of Holdings: Count of unique positions
   - Number of Sectors: Diversification across sectors
   - Concentration (HHI): Herfindahl-Hirschman Index (lower = more diversified)

**Holdings Detail Table:**
- Sortable, searchable table of all positions
- Columns: Ticker, Name, Sector, Market Value, Weight (%)
- Formatted for readability ($1,234,567 | 12.34%)

### Performance Analysis

**Portfolio Cumulative Returns by Ticker**
- Line chart showing each holding's cumulative return over time
- Multi-colored lines for visual differentiation
- Hover shows: Ticker, Date, Return %, Company Name, Sector
- Unified hover mode (vertical line across all tickers)

**Portfolio vs Benchmark Performance**
- Dual-line chart comparing portfolio to sector-weighted benchmark
- Portfolio: Blue solid line
- Benchmark: Gray dashed line
- Automatically calculates sector-weighted benchmark using custom logic

**Benchmark Composition (Expandable)**
- Shows which benchmark indices are used for each sector
- Displays sector → benchmark mapping table
- Aggregated benchmark weights across all sectors
- Example:
  - Technology (30% of portfolio) → QQQ (Nasdaq 100)
  - Financials (20%) → XLF (Financial Select Sector)
  - Energy (15%) → XLE (Energy Select Sector)

**Performance Statistics:**
- **Cumulative Return**: Total return over selected period
- **Annualized Volatility**: Standard deviation × √252
- **Sharpe Ratio**: (Mean return / Std dev) × √252
- **Alpha vs Benchmark**: Excess return vs sector-weighted benchmark
- **Max Drawdown**: Largest peak-to-trough decline

### Risk Metrics

#### Market Risk (Absolute)

1. **VaR 95% (Value at Risk)**
   - Formula: 5th percentile of daily returns
   - Interpretation: Max expected loss with 95% confidence
   - Example: -1.2% means worst daily loss likely -1.2% or better
   - Color coding: Green (>-1%), Yellow (-1% to -2%), Red (<-2%)

2. **Expected Shortfall (CVaR)**
   - Formula: Average of all losses beyond VaR threshold
   - Interpretation: Average loss in worst 5% of days
   - More conservative than VaR (captures tail risk)
   - Color coding: Green (>-1.5%), Yellow (-1.5% to -3%), Red (<-3%)

3. **Volatility (Annualized)**
   - Formula: Daily std dev × √252
   - Interpretation: Expected annual fluctuation range
   - Example: 15% means returns typically ±15% from average
   - Color coding: Green (<15%), Yellow (15-25%), Red (>25%)

4. **Max Drawdown**
   - Formula: Max(Cumulative Return Peak - Current Level)
   - Interpretation: Largest decline from peak during period
   - Example: -12% means worst decline was 12% from previous high
   - Color coding: Green (>-10%), Yellow (-10% to -20%), Red (<-20%)

#### Relative Risk (vs Benchmark)

**Only displayed if benchmark data available**

1. **Beta**
   - Formula: Covariance(Portfolio, Benchmark) / Variance(Benchmark)
   - Interpretation: Sensitivity to benchmark movements
   - Examples:
     - Beta = 1.0 → Moves in line with benchmark
     - Beta = 1.2 → 20% more volatile than benchmark
     - Beta = 0.8 → 20% less volatile (defensive)
   - Color coding: Green (0.8-1.2), Yellow (0.6-1.5), Red (outside range)

2. **Tracking Error**
   - Formula: Std dev of (Portfolio Return - Benchmark Return) × √252
   - Interpretation: Volatility of excess returns
   - Example: 5% means active returns fluctuate ±5% annually
   - Color coding: Green (<5%), Yellow (5-10%), Red (>10%)

3. **Information Ratio**
   - Formula: Active Return / Tracking Error
   - Interpretation: Risk-adjusted excess return
   - Examples:
     - IR = 0.5 → Generating 0.5% excess return per 1% tracking error
     - IR > 1.0 → Excellent active management
     - IR < 0 → Underperforming benchmark
   - Color coding: Green (>0.5), Yellow (0 to 0.5), Red (<0)

4. **Active Return (Annualized)**
   - Formula: (Avg Portfolio Return - Avg Benchmark Return) × 252
   - Interpretation: Annual excess return vs benchmark
   - Example: +2.5% means outperforming by 2.5% annually
   - Color coding: Green (>+2%), Yellow (-2% to +2%), Red (<-2%)

#### Concentration & Duration

1. **Security HHI (Herfindahl-Hirschman Index)**
   - Formula: Σ(weight²) × 10,000 (in basis points)
   - Interpretation: Concentration across individual securities
   - Thresholds:
     - <1500 bps: Well diversified (e.g., 20+ equal-weight stocks)
     - 1500-2500 bps: Moderate concentration
     - >2500 bps: High concentration (e.g., 10-stock portfolio)
   - Color coding: Green (<1500), Yellow (1500-2500), Red (>2500)

2. **Sector HHI**
   - Formula: Σ(sector_weight²) × 10,000
   - Interpretation: Concentration across sectors
   - Thresholds:
     - <2500 bps: Well diversified across sectors
     - 2500-4000 bps: Moderate sector concentration
     - >4000 bps: High sector concentration
   - Color coding: Green (<2500), Yellow (2500-4000), Red (>4000)

3. **Sharpe Ratio**
   - (Duplicate from performance section for convenience)
   - Quick reference for risk-adjusted returns

4. **DV01** (Placeholder)
   - Dollar value of 1 basis point rate change
   - Currently N/A (requires bond duration data)
   - Future enhancement for fixed income portfolios

### Attribution Analysis

**Brinson-Fachler Model Implementation**

Attribution breaks down portfolio vs benchmark excess return into three components:

#### Three Attribution Effects

1. **Allocation Effect**
   - Formula: (w_p - w_equal) × (R_b - R_B_avg)
   - Interpretation: Return from overweighting/underweighting sectors
   - Example: Overweighting Technology by 10% when Tech outperforms → Positive allocation
   - Measures: Sector timing skill

2. **Selection Effect**
   - Formula: w_p × (R_p - R_b)
   - Interpretation: Return from picking better securities within sectors
   - Example: Tech stocks in portfolio return 15% vs QQQ benchmark 12% → Positive selection
   - Measures: Security picking skill

3. **Interaction Effect**
   - Formula: (w_p - w_equal) × (R_p - R_b)
   - Interpretation: Combined effect of allocation + selection
   - Example: Overweighting a sector AND picking outperformers → Amplified positive return
   - Measures: Compounding effect of two decisions

**Total Active Return = Allocation + Selection + Interaction**

#### Summary Metrics

**Four color-coded cards:**
1. Total Allocation (bps): Sum of all sector allocation effects
2. Total Selection (bps): Sum of all security selection effects
3. Total Interaction (bps): Sum of all interaction effects
4. Total Active Return (bps): Sum of above three

**Color Coding:**
- Green background: Positive contribution
- Red background: Negative contribution

#### Attribution by Sector Chart

**Grouped bar chart:**
- X-axis: Sectors
- Y-axis: Attribution (basis points)
- Three bars per sector:
  - Blue: Allocation effect
  - Green: Selection effect
  - Yellow: Interaction effect
- Quickly identifies which sectors drove outperformance/underperformance

#### Detailed Attribution Table (Expandable)

**Columns:**
- Sector
- Portfolio Weight (%)
- Portfolio Return (%)
- Benchmark Return (%)
- Allocation (bps)
- Selection (bps)
- Interaction (bps)
- Total (bps)

**Use Cases:**
- Diagnose why portfolio over/underperformed
- Identify strongest/weakest sector bets
- Validate investment thesis
- Report to clients on value-add

## Technical Details

### Key Functions

1. **`load_user_portfolios(user_id)`**
   - Queries: `portfolios` table
   - Returns: DataFrame with id, name, description, created_at, is_active
   - Used for: Portfolio selection dropdown

2. **`load_portfolio_composition(portfolio_id, as_of_date=None)`**
   - Queries: `f_positions` table
   - Returns: Current holdings (ticker, name, sector, market_value, base_ccy, asof_date)
   - Default: Latest date
   - Used for: Composition charts, concentration metrics

3. **`load_performance_data(portfolio_id, start_date=None, end_date=None)`**
   - Queries: `historical_portfolio_info` table
   - Returns: Time series (date, ticker, name, sector, cumulative_return, daily_return, market_value)
   - Filters by date range
   - Used for: Performance charts, risk calculations

4. **`load_benchmark_data(benchmark_weights, start_date, end_date)`**
   - Fetches: yfinance historical prices for benchmark ETFs
   - Calculates: Weighted benchmark return using sector composition
   - Returns: Daily and cumulative returns
   - Used for: Benchmark comparison, relative risk metrics

5. **`get_risk_color(metric_name, value)`**
   - Logic: Thresholds for each metric type
   - Returns: Hex color code (#d4edda green, #fff3cd yellow, #f8d7da red)
   - Used for: Color-coding risk metric cards

### Database Schema

**Tables Used:**

1. **`portfolios`**
   - `id`: Primary key
   - `user_id`: Foreign key to users
   - `portfolio_name`: Portfolio name
   - `description`: Optional description
   - `created_at`: Timestamp
   - `is_active`: Boolean flag

2. **`f_positions`**
   - `portfolio_id`: Foreign key to portfolios
   - `ticker`: Stock/ETF ticker
   - `name`: Company name
   - `sector`: GICS sector
   - `market_value`: Dollar value of holding
   - `base_ccy`: Currency (USD/CAD)
   - `asof_date`: Position date

3. **`historical_portfolio_info`**
   - `portfolio_id`: Foreign key to portfolios
   - `date`: Date of observation
   - `ticker`: Stock ticker
   - `name`: Company name
   - `sector`: GICS sector
   - `cumulative_return`: Cumulative return from start
   - `daily_return`: Daily return
   - `market_value`: Dollar value on date

### Benchmark Mapping Logic

**Custom Sector-to-ETF Mapping:**

Uses `src.core.benchmark_utils`:
- `get_benchmark_for_sector(sector)` → Returns benchmark ETF ticker
- `get_benchmark_name(ticker)` → Returns human-readable name
- `get_portfolio_benchmark_composition(composition_df)` → Calculates weighted benchmark

**Example Mappings:**
- Technology → QQQ (Invesco QQQ Trust)
- Financials → XLF (Financial Select Sector SPDR)
- Energy → XLE (Energy Select Sector SPDR)
- Healthcare → XLV (Health Care Select Sector SPDR)
- Consumer Discretionary → XLY (Consumer Discretionary Select Sector)
- Industrials → XLI (Industrial Select Sector)
- Utilities → XLU (Utilities Select Sector)
- Real Estate → XLRE (Real Estate Select Sector)
- Materials → XLB (Materials Select Sector)
- Consumer Staples → XLP (Consumer Staples Select Sector)
- Communication Services → XLC (Communication Services Select Sector)

**Weighted Benchmark Calculation:**
1. Calculate portfolio sector weights (e.g., 30% Tech, 20% Financials)
2. Map each sector to benchmark ETF
3. Fetch historical prices for all benchmark ETFs
4. Calculate weighted average return: Σ(sector_weight × benchmark_return)

### Data Flow

```
User Selects Portfolio & Date Range
        ↓
Load Composition (f_positions) → Sector/Ticker Charts
        ↓
Load Performance (historical_portfolio_info) → Time Series
        ↓
Map Sectors to Benchmarks (benchmark_utils)
        ↓
Fetch Benchmark Data (yfinance)
        ↓
Calculate:
  - Portfolio Metrics (returns, volatility, Sharpe)
  - Risk Metrics (VaR, ES, Beta, Tracking Error)
  - Attribution (Brinson-Fachler model)
        ↓
Display Charts & Tables
```

### Performance Optimizations

1. **Date Filtering**
   - Queries filter at database level (not in-memory)
   - Reduces data transfer for large portfolios

2. **Benchmark Caching** (Potential Enhancement)
   - Currently fetches benchmark data every time
   - Could cache daily benchmark prices to reduce yfinance calls

3. **Plotly Charts**
   - Interactive but lightweight
   - Client-side rendering reduces server load

### Color Coding System

**Risk Metric Thresholds:**

All metrics use 3-tier color system:
- **Green (#d4edda)**: Good/Low Risk
- **Yellow (#fff3cd)**: Warning/Moderate Risk
- **Red (#f8d7da)**: Bad/High Risk

See `get_risk_color()` function for specific thresholds per metric.

## Next Steps

### Discussed Improvements

1. **Enhanced Risk Metrics** (Discussed)
   - Add Sortino Ratio (downside deviation)
   - Add Calmar Ratio (return / max drawdown)
   - Add Omega Ratio (probability-weighted gains/losses)
   - Add tail risk metrics (skewness, kurtosis)
   - Stress testing scenarios (2008, 2020 market crashes)

2. **Factor Exposure Analysis** (Discussed)
   - Calculate factor loadings (size, value, momentum, quality)
   - Compare factor tilts vs benchmark
   - Factor contribution to returns
   - Style drift detection

3. **Advanced Attribution** (Discussed)
   - Multi-period attribution (show trends over time)
   - Currency attribution for international portfolios
   - Asset allocation attribution (stocks/bonds/cash)
   - Factor-based attribution (complement Brinson)

4. **Real-Time Updates** (Discussed)
   - Auto-refresh prices during market hours
   - Live P&L tracking
   - Intraday return charts
   - Price alerts for holdings

### Planned Future Enhancements

1. **Interactive Scenario Analysis**
   - What-if analysis: "What if Tech drops 10%?"
   - Monte Carlo simulation for future returns
   - Portfolio optimization suggestions
   - Rebalancing recommendations

2. **Custom Benchmark Selection**
   - Allow user to choose custom benchmark (S&P 500, 60/40, etc.)
   - Create composite benchmarks
   - Compare multiple benchmarks simultaneously
   - Upload custom benchmark data

3. **Export & Reporting**
   - PDF report generation (all charts + commentary)
   - Excel export with formulas intact
   - Schedule automated monthly reports
   - White-label client reports

4. **Tax Analytics**
   - Tax lot tracking (FIFO, LIFO, Specific ID)
   - Unrealized gain/loss reporting
   - Tax-loss harvesting opportunities
   - Qualified dividend income tracking

5. **ESG Integration**
   - ESG scores at portfolio level
   - Controversy screening
   - Carbon footprint analysis
   - Alignment with UN SDGs

6. **Mobile Optimization**
   - Responsive design for tablets/phones
   - Touch-friendly chart interactions
   - Simplified mobile view
   - Progressive Web App (PWA) support

7. **Collaboration Features**
   - Share portfolios with team members
   - Comments on specific holdings
   - Approval workflows for trades
   - Audit trail of changes

### Technical Debt

1. **Hardcoded User ID**
   - Currently: `user_id = 1` (hardcoded)
   - Risk: Multi-user scenarios not supported
   - Fix: Implement authentication, use session-based user_id

2. **No Error Handling for Missing Data**
   - Currently: Assumes data exists in all tables
   - Risk: Page crashes if portfolio has no positions or history
   - Fix: Add checks for empty DataFrames, show meaningful messages

3. **yfinance Dependency**
   - Currently: Free API, no SLA
   - Risk: Rate limits, downtime, data quality issues
   - Fix: Consider Bloomberg, FactSet, or Alpha Vantage for production

4. **Attribution Approximation**
   - Currently: Uses equal-weight benchmark for sectors (not true sector indices)
   - Risk: Attribution may not reflect true benchmark performance
   - Fix: Fetch actual sector index returns (e.g., S&P sector indices)

5. **No Caching of Benchmark Data**
   - Currently: Fetches yfinance data every page load
   - Risk: Slow performance, API rate limits
   - Fix: Cache daily benchmark prices in database

6. **Generic Error Messages**
   - Currently: "Error loading composition: {e}"
   - Risk: User doesn't know how to fix
   - Fix: Specific error messages with actionable guidance

7. **No Unit Tests**
   - Currently: No automated testing
   - Risk: Breaking changes undetected
   - Fix: Add tests for risk calculations, attribution logic

### Known Limitations

1. **Daily Data Only**
   - Intraday returns not supported
   - Can't analyze intraday volatility

2. **USD/CAD Only**
   - No FX conversion for international holdings
   - Mixed currency portfolios show incorrect totals

3. **Equity-Focused**
   - Bond analytics limited (no duration, convexity, YTM)
   - Options not supported
   - Futures/commodities not supported

4. **Single Benchmark**
   - Can't compare multiple benchmarks simultaneously
   - Fixed benchmark logic (sector-weighted)

5. **No Rebalancing Suggestions**
   - Shows current state, not optimal state
   - User must manually determine trades

6. **Limited Historical Depth**
   - Performance depends on `historical_portfolio_info` data
   - If data incomplete, charts show gaps

7. **No Drawdown Chart**
   - Only shows max drawdown (single number)
   - Underwater chart would show duration/magnitude visually

## Dependencies

- `streamlit`: UI framework
- `pandas`: Data manipulation
- `numpy`: Numerical calculations
- `plotly.express` & `plotly.graph_objects`: Interactive charts
- `datetime`: Date handling
- `yfinance`: Benchmark price data
- `src.core.utils_db`: Database connections
- `src.core.benchmark_utils`: Benchmark mapping logic

## File Location
`c:\Users\Kevin Kwan\PM-app\app\pages\4_Portfolio_Dashboard.py`

## Related Files
- `src/core/utils_db.py` - Database connection utilities
- `src/core/benchmark_utils.py` - Sector-to-benchmark mapping
- `sql/schemas/01_core_portfolio.sql` - Portfolio and positions tables
- `sql/schemas/02_risk_metrics.sql` - Risk metrics schema (if applicable)
- `sql/schemas/03_attribution.sql` - Attribution schema (if applicable)

## Usage Notes

**For Best Results:**
1. Ensure `historical_portfolio_info` table is populated (run daily update script)
2. Select appropriate date range (longer periods = more stable risk metrics)
3. Review attribution by sector to understand drivers
4. Compare Sharpe vs Information Ratio (absolute vs relative performance)
5. Monitor HHI metrics for concentration risk
6. Use expandable sections to drill into details

**Common Issues:**
- "No data available": Portfolio has no holdings or history
- Benchmark data missing: yfinance API issue or incorrect ticker mapping
- Attribution shows zeros: Insufficient data for calculation (need >30 days)
- Charts empty: Date range filter excludes all data
