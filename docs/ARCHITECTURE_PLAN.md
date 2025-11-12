# PM-App Multi-User Architecture Plan

## Executive Summary

Transform PM-App from single-user desktop system to multi-user web application supporting 1000+ users. MVP focuses on: IPS screening, security universe filtering, fundamental analysis, manual trade input, and portfolio analytics.

---

## 1. Technology Stack Recommendations

### Option A: Modern Python Full-Stack (RECOMMENDED)

**Frontend:**
- **Framework**: Streamlit or Dash
- **Why**: 
  - Pure Python (leverage existing codebase)
  - Built-in components for financial dashboards
  - Rapid development (weeks not months)
  - Great for data-heavy applications
- **Cons**: Less customizable UI than React

**Backend:**
- **Framework**: FastAPI
- **Why**:
  - Modern async Python framework
  - Automatic API documentation
  - Easy integration with pandas/numpy
  - Can reuse 100% of existing analytics code
- **Cons**: None significant for this use case

**Database:**
- **Primary**: SQL Server (keep existing)
- **Cache**: Redis (for session data, API rate limiting)
- **Why**: Already have SQL Server expertise, minimal migration

**Auth:**
- **Provider**: Clerk.com or Auth0
- **Why**:
  - Managed service (don't build auth yourself)
  - Free tier supports 5000-10000 users
  - Social login (Google, Microsoft) built-in
  - JWT tokens work seamlessly with FastAPI
- **Cost**: Free up to 5000 MAU (monthly active users)

**Hosting:**
- **Option 1**: Azure App Service
  - **Pros**: SQL Server native integration, Python support, scales to 1000+ users
  - **Cons**: More expensive than AWS
  - **Cost**: ~$50-200/month for small scale
  
- **Option 2**: Railway.app or Render.com
  - **Pros**: Dead simple deployment, generous free tier
  - **Cons**: Less scalable long-term
  - **Cost**: Free tier, then $20-50/month

**Total Monthly Cost (MVP)**: $0-100

---

### Option B: Enterprise React Stack

**Frontend:**
- **Framework**: Next.js (React)
- **Why**: Most flexible UI, best user experience
- **Cons**: Learning curve, slower development

**Backend:**
- **Framework**: FastAPI (Python) for analytics + Next.js API routes for CRUD
- **Why**: Hybrid approach - Python for number crunching, JavaScript for data operations

**Database/Auth/Hosting:** Same as Option A

**Total Monthly Cost (MVP)**: $50-150

**Recommendation**: Only choose if you have React expertise or plan to hire frontend developer

---

### Option C: Django Full-Stack

**Framework**: Django + Django REST Framework
**Why**: Mature, batteries-included, admin panel
**Cons**: Slower development than FastAPI/Streamlit, older architecture

**Recommendation**: Skip this - FastAPI is better for new projects

---

## 2. Recommended Stack (Final Choice)

**Frontend**: Streamlit  
**Backend**: FastAPI  
**Database**: SQL Server + Redis  
**Auth**: Clerk.com  
**Hosting**: Railway.app (MVP) → Azure (scale-up)  
**Data Sources**: yfinance (free)

**Why this combination:**
1. **Fastest time-to-market**: 4-6 weeks to MVP
2. **Leverage existing code**: Reuse 90% of analytics Python code
3. **Cost-effective**: Free for MVP, $50-100/month for 100+ users
4. **Scalable**: Can handle 1000+ users with Azure migration
5. **Python-native**: No context switching between languages

---

## 3. Database Multi-Tenancy Strategy

### Recommended: Row-Level Security (Single Database with user_id)

**Schema Changes:**
```sql
-- Add to ALL existing tables
ALTER TABLE historical_portfolio_info ADD user_id BIGINT NOT NULL DEFAULT 0;
ALTER TABLE portfolio_risk_metrics ADD user_id BIGINT NOT NULL DEFAULT 0;
ALTER TABLE portfolio_attribution ADD user_id BIGINT NOT NULL DEFAULT 0;

-- Create index for performance
CREATE INDEX IX_user_holdings ON historical_portfolio_info(user_id, date);
CREATE INDEX IX_user_metrics ON portfolio_risk_metrics(user_id, asof_date);
```

**New Tables Needed:**
```sql
-- Users table
CREATE TABLE users (
    id BIGINT IDENTITY PRIMARY KEY,
    clerk_user_id NVARCHAR(255) UNIQUE NOT NULL,  -- From Clerk auth
    email NVARCHAR(255) UNIQUE NOT NULL,
    display_name NVARCHAR(255),
    created_at DATETIME2 DEFAULT SYSDATETIME(),
    last_login_at DATETIME2
);

-- IPS Responses
CREATE TABLE ips_responses (
    id BIGINT IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    question_id INT NOT NULL,
    response NVARCHAR(MAX),  -- JSON or plain text
    created_at DATETIME2 DEFAULT SYSDATETIME(),
    updated_at DATETIME2 DEFAULT SYSDATETIME(),
    FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT UQ_user_question UNIQUE (user_id, question_id)
);

-- Trade Log
CREATE TABLE trade_log (
    id BIGINT IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    trade_date DATE NOT NULL,
    ticker NVARCHAR(32) NOT NULL,
    action NVARCHAR(10) NOT NULL,  -- BUY or SELL
    quantity DECIMAL(18,4) NOT NULL,
    price DECIMAL(18,4) NOT NULL,
    total_value AS (quantity * price),
    sector NVARCHAR(64),
    notes NVARCHAR(MAX),
    created_at DATETIME2 DEFAULT SYSDATETIME(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Security Scores (for screener)
CREATE TABLE security_scores (
    id BIGINT IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    ticker NVARCHAR(32) NOT NULL,
    score_date DATE NOT NULL,
    fundamental_score DECIMAL(5,2),
    technical_score DECIMAL(5,2),
    ips_fit_score DECIMAL(5,2),
    composite_score DECIMAL(5,2),
    rank INT,
    created_at DATETIME2 DEFAULT SYSDATETIME(),
    FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT UQ_user_ticker_date UNIQUE (user_id, ticker, score_date)
);

-- Filtered Universe (per user based on IPS)
CREATE TABLE user_universe (
    id BIGINT IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    ticker NVARCHAR(32) NOT NULL,
    name NVARCHAR(255),
    sector NVARCHAR(64),
    market_cap DECIMAL(18,2),
    included BIT DEFAULT 1,  -- Allow manual exclusions
    created_at DATETIME2 DEFAULT SYSDATETIME(),
    FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT UQ_user_universe UNIQUE (user_id, ticker)
);
```

**Pros:**
- Simpler management (one database to backup)
- Shared reference data (tickers, sectors)
- Easier queries across users (admin analytics)
- Lower cost (one SQL Server instance)

**Cons:**
- Must be careful with WHERE user_id = ? in every query
- One security mistake exposes all user data
- Slightly more complex queries

**Security Mitigation:**
- Use ORM with automatic user_id filtering
- Database row-level security policies
- Audit logging on user tables

---

## 4. IPS Screening Questionnaire Design

### Questions (10 total):

**Risk Tolerance (1-2)**
1. "What is your investment time horizon?"
   - < 1 year, 1-3 years, 3-5 years, 5-10 years, 10+ years
   
2. "How much volatility can you tolerate?"
   - Low (0-5% annual swings)
   - Moderate (5-15% annual swings)
   - High (15%+ annual swings)

**Investment Goals (3-4)**
3. "What is your primary investment objective?"
   - Capital preservation, Income generation, Balanced growth, Aggressive growth

4. "What is your target annual return?"
   - 0-3%, 3-5%, 5-8%, 8-12%, 12%+

**Sector Preferences (5-7)**
5. "Which sectors do you want to EXCLUDE?" (multi-select)
   - Technology, Financials, Healthcare, Energy, Utilities, Real Estate, Consumer, Industrial

6. "Geographic preference?"
   - US only, Canada only, North America, Global, Emerging markets

7. "Asset class allocation?"
   - Equities (%), Bonds (%), Cash (%)

**Constraints (8-10)**
8. "Maximum single position size?"
   - 2%, 5%, 10%, 20%, No limit

9. "ESG preferences?"
   - None, Exclude tobacco/weapons, Exclude fossil fuels, Full ESG screening

10. "Dividend requirements?"
    - No preference, Dividend payers only, High yield (4%+)

### Universe Filtering Logic:

```python
def filter_universe(ips_responses, full_universe):
    """
    Filter universe based on IPS responses
    Returns list of ticker symbols that pass all filters
    """
    filtered = full_universe.copy()
    
    # Hard filters (must pass)
    excluded_sectors = ips_responses.get('excluded_sectors', [])
    filtered = filtered[~filtered['sector'].isin(excluded_sectors)]
    
    geography = ips_responses.get('geography', 'North America')
    if geography == 'US only':
        filtered = filtered[filtered['country'] == 'US']
    elif geography == 'Canada only':
        filtered = filtered[filtered['country'] == 'CA']
    
    # ESG filter
    esg_pref = ips_responses.get('esg', 'None')
    if esg_pref == 'Exclude tobacco/weapons':
        filtered = filtered[~filtered['sector'].isin(['Tobacco', 'Defense'])]
    
    # Dividend filter
    div_req = ips_responses.get('dividend', 'No preference')
    if div_req == 'Dividend payers only':
        filtered = filtered[filtered['dividend_yield'] > 0]
    elif div_req == 'High yield (4%+)':
        filtered = filtered[filtered['dividend_yield'] >= 0.04]
    
    return filtered
```

---

## 5. Data Sources & Fundamentals

### Primary Data Source: yfinance (Free)

**What yfinance provides:**
```python
import yfinance as yf

ticker = yf.Ticker("AAPL")

# Fundamentals
info = ticker.info
# Available data:
# - marketCap, trailingPE, forwardPE, priceToBook
# - dividendYield, payoutRatio
# - profitMargins, operatingMargins
# - revenueGrowth, earningsGrowth
# - debtToEquity, currentRatio, quickRatio
# - returnOnEquity, returnOnAssets
# - 52WeekHigh, 52WeekLow, beta

# Financials
ticker.financials          # Income statement
ticker.balance_sheet       # Balance sheet
ticker.cashflow           # Cash flow statement

# Recommendations
ticker.recommendations    # Analyst ratings

# Important dates
ticker.calendar           # Earnings dates, ex-dividend dates
```

### Key Fundamental Metrics to Display:

**Valuation (Red Flags)**
- P/E Ratio > 50: Overvalued warning
- P/B Ratio > 10: Growth stock premium
- Market Cap < $1B: Small cap risk

**Financial Health (Red Flags)**
- Debt/Equity > 2: High leverage warning
- Current Ratio < 1: Liquidity concern
- Negative profit margin: Unprofitable

**Growth**
- Revenue Growth (YoY)
- Earnings Growth (YoY)
- Dividend Growth (if applicable)

**Quality**
- ROE (Return on Equity)
- Operating Margin
- Free Cash Flow positive/negative

### Red Flag System:

```python
def calculate_red_flags(ticker_info):
    """Returns list of warnings"""
    flags = []
    
    if ticker_info.get('trailingPE', 0) > 50:
        flags.append("⚠️ High P/E Ratio - potentially overvalued")
    
    if ticker_info.get('debtToEquity', 0) > 2:
        flags.append("🔴 High debt levels")
    
    if ticker_info.get('currentRatio', 0) < 1:
        flags.append("🔴 Liquidity concerns")
    
    if ticker_info.get('profitMargins', 0) < 0:
        flags.append("⚠️ Currently unprofitable")
    
    return flags
```

---

## 6. Scoring System (Basic MVP)

### Composite Score = Weighted Average

**Weights:**
- Fundamental Score: 50%
- IPS Fit Score: 30%
- Technical/Momentum: 20%

### 1. Fundamental Score (0-100)

```python
def calculate_fundamental_score(ticker_info):
    """
    Score based on value, quality, growth metrics
    Higher = better fundamentals
    """
    score = 50  # Start at neutral
    
    # Value component (0-30 points)
    pe_ratio = ticker_info.get('trailingPE', 999)
    if pe_ratio < 15:
        score += 30
    elif pe_ratio < 25:
        score += 20
    elif pe_ratio < 35:
        score += 10
    else:
        score += 0  # Expensive
    
    # Quality component (0-40 points)
    roe = ticker_info.get('returnOnEquity', 0)
    if roe > 0.20:
        score += 20
    elif roe > 0.15:
        score += 15
    elif roe > 0.10:
        score += 10
    
    profit_margin = ticker_info.get('profitMargins', 0)
    if profit_margin > 0.20:
        score += 20
    elif profit_margin > 0.10:
        score += 15
    elif profit_margin > 0.05:
        score += 10
    
    # Growth component (0-30 points)
    earnings_growth = ticker_info.get('earningsGrowth', 0)
    if earnings_growth > 0.25:
        score += 30
    elif earnings_growth > 0.15:
        score += 20
    elif earnings_growth > 0.05:
        score += 10
    
    return min(score, 100)  # Cap at 100
```

### 2. IPS Fit Score (0-100)

```python
def calculate_ips_fit_score(ticker_info, ips_responses):
    """
    How well does security match user's IPS preferences
    """
    score = 50  # Start neutral
    
    # Risk tolerance match
    beta = ticker_info.get('beta', 1.0)
    risk_tolerance = ips_responses.get('volatility_tolerance', 'Moderate')
    
    if risk_tolerance == 'Low' and beta < 0.8:
        score += 25
    elif risk_tolerance == 'Moderate' and 0.8 <= beta <= 1.2:
        score += 25
    elif risk_tolerance == 'High' and beta > 1.2:
        score += 25
    else:
        score -= 10  # Mismatch
    
    # Dividend requirement match
    div_yield = ticker_info.get('dividendYield', 0) or 0
    div_req = ips_responses.get('dividend', 'No preference')
    
    if div_req == 'High yield (4%+)' and div_yield >= 0.04:
        score += 25
    elif div_req == 'Dividend payers only' and div_yield > 0:
        score += 25
    elif div_req == 'No preference':
        score += 10  # Neutral
    
    return min(max(score, 0), 100)
```

### 3. Technical/Momentum Score (0-100)

```python
def calculate_momentum_score(price_history):
    """
    Simple momentum based on recent price trends
    """
    if len(price_history) < 60:
        return 50  # Neutral if insufficient data
    
    # 1-month return
    month_return = (price_history[-1] / price_history[-20]) - 1
    
    # 3-month return
    quarter_return = (price_history[-1] / price_history[-60]) - 1
    
    score = 50
    
    if month_return > 0.10:
        score += 25
    elif month_return > 0.05:
        score += 15
    elif month_return > 0:
        score += 5
    else:
        score -= 10
    
    if quarter_return > 0.15:
        score += 25
    elif quarter_return > 0.10:
        score += 15
    elif quarter_return > 0:
        score += 5
    else:
        score -= 10
    
    return min(max(score, 0), 100)
```

### Final Composite Score:

```python
composite_score = (
    0.50 * fundamental_score +
    0.30 * ips_fit_score +
    0.20 * momentum_score
)

# Rank all securities in universe by composite score
```

---

## 7. Trade Window & Portfolio Impact

### Trade Preview Calculation:

```python
def calculate_trade_impact(current_holdings, proposed_trade, risk_metrics):
    """
    Show before/after comparison for a proposed trade
    """
    # Create hypothetical portfolio after trade
    new_holdings = current_holdings.copy()
    
    if proposed_trade['action'] == 'BUY':
        # Add to holdings
        new_holdings = add_position(new_holdings, proposed_trade)
    else:  # SELL
        # Remove from holdings
        new_holdings = remove_position(new_holdings, proposed_trade)
    
    # Recalculate metrics
    current_metrics = {
        'total_value': current_holdings['market_value'].sum(),
        'sector_weights': calculate_sector_weights(current_holdings),
        'volatility': risk_metrics.get('Volatility_Ann'),
        'beta': risk_metrics.get('Beta'),
        'sharpe': risk_metrics.get('Sharpe_Ratio'),
        'concentration': risk_metrics.get('HHI_Security')
    }
    
    new_metrics = {
        'total_value': new_holdings['market_value'].sum(),
        'sector_weights': calculate_sector_weights(new_holdings),
        'volatility': estimate_new_volatility(new_holdings),  # Simplified
        'beta': estimate_new_beta(new_holdings),
        'sharpe': None,  # Can't estimate reliably
        'concentration': calculate_hhi(new_holdings)
    }
    
    return {
        'current': current_metrics,
        'proposed': new_metrics,
        'changes': calculate_changes(current_metrics, new_metrics),
        'warnings': generate_warnings(current_metrics, new_metrics)
    }
```

### UI Display:

```
┌──────────────────────────────────────────────────────┐
│ Trade Preview: BUY 50 shares AAPL @ $225.50         │
├──────────────────────────────────────────────────────┤
│                      Current    After Trade   Change │
│ Total Value:         $150,000   $161,275      +7.5% │
│ # of Positions:      12         13            +1    │
│                                                       │
│ Sector Weights:                                      │
│   Technology:        35.0%      42.5%         +7.5% │
│   Financials:        25.0%      23.2%         -1.8% │
│   Healthcare:        15.0%      13.9%         -1.1% │
│   ... (others)                                       │
│                                                       │
│ Risk Metrics:                                        │
│   Volatility (ann.): 18.5%      19.2%         +0.7% │
│   Beta:              0.98       1.02          +0.04 │
│   Concentration:     1,250      1,380         +130  │
│                                                       │
│ ⚠️  WARNINGS:                                        │
│   • Technology allocation exceeds 40% target        │
│   • Concentration increasing (HHI +130)             │
│                                                       │
│ 📊 Expected Return Impact: +0.8% annualized         │
│    ⚠️  DISCLAIMER: This is an estimate based on    │
│    historical data and is NOT guaranteed. Actual    │
│    returns may differ significantly.                │
└──────────────────────────────────────────────────────┘

[Cancel]  [Confirm Trade]
```

---

## 8. Data Update Strategy

### Daily EOD Process (Automated):

**Scheduled Task (runs at 6 PM ET daily):**

```python
# Daily batch job (runs on server)
def daily_eod_update():
    """
    Update all user portfolios with end-of-day prices
    """
    # 1. Fetch EOD prices for all unique tickers across all users
    all_tickers = get_all_user_tickers()
    prices = fetch_yfinance_prices(all_tickers)
    
    # 2. For each user's trade log, update portfolio
    for user_id in get_active_users():
        # Apply any trades made today at user-specified price
        apply_trades_to_portfolio(user_id, date.today())
        
        # Update market values with EOD prices
        update_portfolio_with_eod_prices(user_id, prices)
        
        # Calculate risk metrics (using expanding window)
        calculate_risk_metrics(user_id)
        
        # Calculate attribution
        calculate_attribution(user_id)
    
    print(f"Updated {len(get_active_users())} user portfolios")
```

**Trade Price Handling:**
```python
# When user enters trade
trade = {
    'user_id': 123,
    'date': '2025-11-11',
    'ticker': 'AAPL',
    'action': 'BUY',
    'quantity': 50,
    'price': 225.50,  # User's actual execution price
    'time': '10:30 AM'
}

# Store in trade_log table with user's price

# At EOD, when updating historical_portfolio_info:
# - Trade executes at user's price (225.50)
# - Market value calculated with EOD price (e.g., 227.00)
# - Daily return reflects EOD-to-EOD change, not intraday
```

### On-Demand Fundamentals (Real-Time):

**When user clicks on a security:**
```python
@app.route('/security/<ticker>')
def get_security_details(ticker):
    """
    Fetch real-time fundamental data when user views security
    """
    # Cache for 1 hour to avoid rate limiting
    cached = redis.get(f'fundamentals:{ticker}')
    if cached:
        return json.loads(cached)
    
    # Fetch fresh data from yfinance
    ticker_obj = yf.Ticker(ticker)
    fundamentals = {
        'info': ticker_obj.info,
        'financials': ticker_obj.financials.to_dict(),
        'calendar': ticker_obj.calendar,
        'recommendations': ticker_obj.recommendations.to_dict()
    }
    
    # Cache for 1 hour
    redis.setex(f'fundamentals:{ticker}', 3600, json.dumps(fundamentals))
    
    return fundamentals
```

---

## 9. MVP Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

**Database Migration:**
- [ ] Add user_id to all existing tables
- [ ] Create new tables (users, ips_responses, trade_log, etc.)
- [ ] Write migration script to preserve existing data

**Authentication Setup:**
- [ ] Set up Clerk.com account
- [ ] Implement login/signup flow
- [ ] Create user session management

**Hosting Setup:**
- [ ] Deploy to Railway.app (free tier)
- [ ] Set up SQL Server connection (Azure SQL or Railway DB)
- [ ] Configure environment variables

### Phase 2: IPS & Screening (Weeks 3-4)

**IPS Questionnaire:**
- [ ] Build 10-question form (Streamlit)
- [ ] Store responses in database
- [ ] Allow editing responses

**Universe Filtering:**
- [ ] Create master ticker list (~500-1000 securities)
- [ ] Implement filtering logic based on IPS
- [ ] Display filtered universe to user

**Fundamentals Display:**
- [ ] Fetch yfinance data for securities
- [ ] Display key metrics in table
- [ ] Show red flags/warnings
- [ ] Add sorting/filtering

### Phase 3: Scoring & Ranking (Week 5)

**Scoring System:**
- [ ] Implement fundamental scoring
- [ ] Implement IPS fit scoring
- [ ] Implement momentum scoring
- [ ] Calculate composite scores
- [ ] Rank securities

### Phase 4: Trading & Portfolio (Week 6)

**Trade Entry:**
- [ ] Build trade input form
- [ ] Calculate portfolio impact preview
- [ ] Show before/after comparison
- [ ] Confirm and store trade

**Portfolio Display:**
- [ ] Show current holdings
- [ ] Display risk metrics (from existing code)
- [ ] Display attribution (from existing code)
- [ ] Trade history log

### Phase 5: Testing & Launch (Week 7-8)

**Testing:**
- [ ] Test with 5-10 beta users
- [ ] Fix bugs
- [ ] Performance optimization
- [ ] Documentation

**Launch:**
- [ ] Migrate to production
- [ ] Monitor for issues
- [ ] Gather feedback

---

## 10. Cost Breakdown & Scalability

### MVP (0-100 users):
- **Hosting**: Railway.app (Free tier)
- **Auth**: Clerk.com (Free tier - 5000 MAU)
- **Database**: Railway.app included PostgreSQL OR Azure SQL ($5-10/mo)
- **Data**: yfinance (Free)
- **Total**: $0-10/month

### Growth (100-500 users):
- **Hosting**: Railway.app Pro ($20/mo) or Azure App Service ($50/mo)
- **Auth**: Clerk.com (Still free < 5000 MAU)
- **Database**: Azure SQL Standard ($15-30/mo)
- **Redis**: Azure Cache ($10/mo)
- **Total**: $50-100/month

### Scale (500-1000+ users):
- **Hosting**: Azure App Service ($100-200/mo)
- **Auth**: Clerk.com (Still free < 5000 MAU)
- **Database**: Azure SQL Standard ($50-100/mo)
- **Redis**: Azure Cache ($20/mo)
- **CDN**: Azure CDN ($10/mo)
- **Total**: $180-330/month

---

## 11. Next Steps

1. **Review this document** - Approve technology choices
2. **Set up development environment** - Install Streamlit, FastAPI, Clerk
3. **Database migration** - Add user_id columns, create new tables
4. **Build IPS questionnaire** - First user-facing feature
5. **Iterate** - Get feedback, refine

**Questions? Let me know which sections need more detail!**
