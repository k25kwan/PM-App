# Sleeve-Based Security Screening

## Overview

The Security Screening page now uses a **sleeve-based approach** for faster, more focused screening. Instead of screening 1500+ random securities, users select one investment category at a time.

## Key Changes

### Before (Multi-Sleeve)
- Hardcoded `BASE_UNIVERSE` with 400+ tickers across all categories
- Geography filters (US/Canada/Global)
- Sector exclusion lists
- 5-10 minute load times for comprehensive screening

### After (Single-Sleeve)
- **13 investment sleeves** with 15-25 securities each
- **Pre-filtered for quality**: Market cap, debt/equity, liquidity
- **30 seconds to 1 minute** load time per sleeve
- No need for geography/sector filters (built into sleeve selection)

## Investment Sleeves

### US Equity Sleeves (Large Cap Focus)
1. **US Large Cap Technology** - 20 tickers, >$100B cap, <100% D/E
2. **US Large Cap Financials** - 20 tickers, >$50B cap, <500% D/E
3. **US Large Cap Healthcare** - 20 tickers, >$50B cap, <150% D/E
4. **US Large Cap Consumer** - 20 tickers, >$30B cap, <200% D/E
5. **US Large Cap Energy** - 18 tickers, >$30B cap, <150% D/E
6. **US Large Cap Industrials** - 20 tickers, >$30B cap, <200% D/E

### Canadian Equity Sleeves
7. **Canadian Banks** - 9 tickers, >$20B CAD cap, <500% D/E
8. **Canadian Energy** - 12 tickers, >$5B CAD cap, <150% D/E
9. **Canadian Materials & Resources** - 12 tickers, >$5B CAD cap, <200% D/E

### ETF Sleeves
10. **US Equity ETFs** - 17 tickers (broad market + sector ETFs)
11. **Fixed Income ETFs** - 15 tickers (bonds across duration/credit)
12. **Canadian ETFs** - 13 tickers (equity + fixed income)
13. **International ETFs** - 15 tickers (developed + emerging markets)

## Quality Filters Built Into Each Sleeve

### Market Cap Thresholds
- **Mega Cap Tech**: >$100B (institutional-grade only)
- **Large Cap US**: >$30-50B (blue chips)
- **Canadian**: >$5-20B CAD (TSX leaders)
- **ETFs**: No market cap filter (N/A)

### Debt/Equity Limits
- **Technology**: <100% (low leverage business model)
- **Healthcare/Energy**: <150% (moderate leverage)
- **Consumer/Industrials**: <200% (industry standard)
- **Banks/Financials**: <500% (higher leverage is normal)
- **ETFs**: Not applicable

### Liquidity
- Only includes actively traded securities
- No micro-caps, penny stocks, or illiquid names
- Excludes companies with questionable financial health

## User Workflow

### 1. Select Sleeve
User picks one category from dropdown:
```
Choose an investment sleeve:
[ US Large Cap Technology ▼ ]
```

### 2. View Sleeve Details
System shows:
- Description: "Mega-cap tech companies (>$100B market cap, strong balance sheets)"
- Ticker count: 20 securities
- Min Market Cap: $100B
- Max D/E: 100%

### 3. Apply Optional Filters
- Include/exclude ETFs
- Include/exclude Equities
- Industry keyword filter (post-fetch)
- Country keyword filter (post-fetch)

### 4. Fetch & Rank
- Pulls fresh data from Yahoo Finance for 15-25 tickers
- **30-60 seconds** total time
- Applies sleeve-specific quality filters
- Ranks by fundamental score + diversification benefit

## Benefits

### Speed
- **Before**: 5-10 minutes for 1500+ tickers
- **After**: 30-60 seconds for 20 tickers
- 10x faster screening

### Focus
- Users screen one coherent category at a time
- No mixing of Canadian banks with US tech stocks
- Easier to compare apples-to-apples

### Quality
- Every sleeve has built-in quality standards
- No need to manually filter out junk securities
- Saves time and improves results

### No API Rate Limits
- Small batches (20 tickers) avoid yfinance throttling
- Can screen multiple sleeves sequentially without issues
- Reliable data fetch success rate

## Technical Implementation

### Sleeve Definition Structure
```python
INVESTMENT_SLEEVES = {
    "Sleeve Name": {
        "description": "Human-readable description",
        "tickers": ["AAPL", "MSFT", ...],  # 15-25 tickers
        "min_market_cap": 100_000_000_000,  # $100B
        "max_debt_equity": 100,  # 100% D/E ratio
    },
    ...
}
```

### Runtime Filtering Logic
```python
# 1. Get tickers from selected sleeve
tickers = sleeve_info['tickers']

# 2. Fetch yfinance data
for ticker in tickers:
    info = get_ticker_info(ticker)
    
    # 3. Apply sleeve filters
    if info['market_cap'] < sleeve_info['min_market_cap']:
        skip
    if info['debt_equity'] > sleeve_info['max_debt_equity']:
        skip
    
    # 4. Keep if passes
    screened.append(info)
```

## Future Enhancements

Potential additions:
- [ ] User-defined custom sleeves (save ticker lists)
- [ ] Mid-cap and small-cap sleeves
- [ ] International equity sleeves (Europe, Asia)
- [ ] Sector-specific sleeves (Software, Semiconductors, Oil & Gas)
- [ ] Factor-based sleeves (Value, Growth, Momentum)
- [ ] ESG-focused sleeves
- [ ] Dividend aristocrats sleeve

## Maintenance

### Updating Sleeve Tickers
To add/remove tickers from a sleeve:

1. Open `app/pages/3_Security_Screening.py`
2. Find `INVESTMENT_SLEEVES` dictionary (around line 320)
3. Edit the ticker list for the sleeve
4. Save and restart Streamlit

### Adding New Sleeves
```python
"New Sleeve Name": {
    "description": "Brief description of the sleeve",
    "tickers": ["TICK1", "TICK2", "TICK3"],
    "min_market_cap": 10_000_000_000,  # $10B
    "max_debt_equity": 200,  # 200%
},
```

### Quality Check
Periodically verify:
- Tickers still exist on Yahoo Finance
- No delisted/merged companies
- Market cap thresholds still appropriate
- Debt/equity limits reasonable for sector

Recommended frequency: **Quarterly**
