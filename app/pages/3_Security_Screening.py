"""
Security Screening  
Filter universe using real yfinance data based on user preferences
Uses comprehensive ticker universe from external sources
Filters out "bad apples" using fundamental quality screens
Includes factor-based analysis using S&P 500 sector benchmarks
"""

import streamlit as st
import sys
from pathlib import Path
import yfinance as yf
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.utils_db import get_conn
from src.ingestion.fetch_universe import load_ticker_universe, get_universe_stats
from src.analytics.sector_benchmarks import SectorBenchmarks
from src.analytics.factor_scoring import score_stock_all_factors, score_stock_from_info
from src.analytics.investment_styles import get_top_stocks_by_style, rank_stocks_by_style_cached, INVESTMENT_STYLES

st.set_page_config(page_title="Find Investments", layout="wide")

# Initialize sector benchmarks (cache in session state)
if 'benchmarks' not in st.session_state:
    try:
        benchmarks = SectorBenchmarks()
        if benchmarks.load_from_cache():
            st.session_state.benchmarks = benchmarks
            st.session_state.benchmarks_available = True
            # Also store S&P 500 tickers for screening
            st.session_state.sp500_tickers = benchmarks.get_sp1500_tickers()
        else:
            st.session_state.benchmarks_available = False
            st.session_state.sp500_tickers = []
    except Exception as e:
        st.session_state.benchmarks_available = False
        st.session_state.sp500_tickers = []

st.title("🔍 Find Great Investments for Your Portfolio")
st.markdown("""
**What does this tool do?** It helps you discover quality stocks from the S&P 500.

**How it works:** 
1. Choose what type of investment (stocks, ETFs, bonds)
2. Load and screen the S&P 500 universe with quality filters
3. Review results and use advanced factor analysis for ranking
""")

# ETF Sector Mapping - since yfinance doesn't provide sector for ETFs
# Map ETF tickers to their primary sector/asset class exposure
ETF_SECTOR_MAP = {
    # Broad Market
    "SPY": "Broad Market Equity",
    "QQQ": "Technology",
    "IWM": "Small Cap Equity",
    "VTI": "Broad Market Equity",
    "VOO": "Broad Market Equity",
    
    # US Sector ETFs
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLK": "Technology",
    "XLU": "Utilities",
    "XLI": "Industrials",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLRE": "Real Estate",
    "XLB": "Materials",
    "XLC": "Communication Services",
    
    # Fixed Income
    "AGG": "Fixed Income - Investment Grade",
    "LQD": "Fixed Income - Corporate",
    "HYG": "Fixed Income - High Yield",
    "TLT": "Fixed Income - Treasury",
    "BND": "Fixed Income - Investment Grade",
    "TIP": "Fixed Income - TIPS",
    "MUB": "Fixed Income - Municipal",
    
    # Canadian ETFs
    "XIU.TO": "Canadian Equity",
    "XBB.TO": "Canadian Fixed Income",
    "XIC.TO": "Canadian Equity",
    "ZCN.TO": "Canadian Equity",
    "XEG.TO": "Canadian Energy",
    "XFN.TO": "Canadian Financials",
    
    # International
    "EFA": "International Equity",
    "VEA": "International Equity",
    "EEM": "Emerging Markets",
    "VWO": "Emerging Markets",
    "IEFA": "International Equity",
}

def get_ticker_info(ticker, include_fundamentals=False):
    """Fetch ticker info from yfinance"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Determine asset type
        quote_type = info.get('quoteType', '')
        if quote_type == 'ETF' or 'ETF' in info.get('longName', '').upper():
            asset_type = 'ETF'
        elif quote_type == 'EQUITY':
            asset_type = 'Equity'
        elif quote_type == 'MUTUALFUND':
            asset_type = 'Mutual Fund'
        else:
            asset_type = 'Other'
        
        # Get sector - use custom mapping for ETFs
        if asset_type == 'ETF' and ticker in ETF_SECTOR_MAP:
            sector = ETF_SECTOR_MAP[ticker]
        else:
            sector = info.get('sector', 'Unknown')
        
        base_info = {
            'ticker': ticker,
            'name': info.get('longName', ticker),
            'asset_type': asset_type,
            'sector': sector,
            'industry': info.get('industry', 'Unknown'),
            'market_cap': info.get('marketCap', 0),
            'country': info.get('country', 'Unknown'),
            'price': info.get('currentPrice', info.get('regularMarketPrice', 0))
        }
        
        if include_fundamentals:
            # Add fundamental metrics (only meaningful for equities)
            base_info.update({
                'pe_ratio': info.get('trailingPE'),
                'pb_ratio': info.get('priceToBook'),
                'dividend_yield': info.get('dividendYield'),
                'profit_margin': info.get('profitMargins'),
                'revenue_growth': info.get('revenueGrowth'),
                'roe': info.get('returnOnEquity'),
                'debt_to_equity': info.get('debtToEquity'),
                'ev_ebitda': info.get('enterpriseToEbitda')
            })
        
        return base_info
    except Exception as e:
        # Return minimal info if yfinance fails
        base_info = {
            'ticker': ticker,
            'name': ticker,
            'asset_type': 'Unknown',
            'sector': 'Unknown',
            'industry': 'Unknown',
            'market_cap': 0,
            'country': 'US' if '.TO' not in ticker else 'Canada',
            'price': 0
        }
        
        if include_fundamentals:
            base_info.update({
                'pe_ratio': None,
                'pb_ratio': None,
                'dividend_yield': None,
                'profit_margin': None,
                'revenue_growth': None,
                'roe': None,
                'debt_to_equity': None,
                'ev_ebitda': None
            })
        
        return base_info

def is_bad_apple(info, asset_class_filter):
    """
    Filter out obvious "bad apples" - companies with red flags
    This is NOT scoring, just eliminating clear problems
    
    Returns: (is_bad: bool, reason: str)
    """
    
    # ETFs skip fundamental checks
    if info.get('asset_type') == 'ETF':
        return False, None
    
    ticker = info.get('ticker', 'Unknown')
    
    # Helper to safely convert to float
    def safe_float(value):
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    # Rule 1: Negative or missing earnings for non-growth stocks
    pe_ratio = safe_float(info.get('pe_ratio'))
    if pe_ratio is not None and pe_ratio < 0:
        # Negative P/E = losing money
        # Allow if it's a known growth sector, else reject
        sector = info.get('sector', '')
        if sector not in ['Technology', 'Healthcare', 'Communication Services']:
            return True, f"Unprofitable ({ticker} has negative earnings)"
    
    # Rule 2: Extreme debt levels (non-financials)
    debt_equity = safe_float(info.get('debt_to_equity'))
    sector = info.get('sector', '')
    if debt_equity is not None and sector not in ['Financial Services', 'Financials', 'Real Estate']:
        if debt_equity > 300:  # 300% D/E is danger zone for non-financials
            return True, f"Excessive debt ({ticker} D/E = {debt_equity:.0f}%)"
    
    # Rule 3: Extremely low ROE (return on equity) = inefficient capital use
    roe = safe_float(info.get('roe'))
    if roe is not None and roe < -0.20:  # Losing >20% on equity
        return True, f"Poor returns ({ticker} ROE = {roe*100:.1f}%)"
    
    # Rule 4: Absurd valuations (likely data error or bubble stock)
    if pe_ratio is not None and pe_ratio > 500:
        return True, f"Unrealistic valuation ({ticker} P/E = {pe_ratio:.0f})"
    
    pb_ratio = safe_float(info.get('pb_ratio'))
    if pb_ratio is not None and pb_ratio > 50 and sector not in ['Technology', 'Communication Services']:
        return True, f"Extreme P/B ratio ({ticker} P/B = {pb_ratio:.1f})"
    
    # Rule 5: Negative profit margins (unless growth/startup)
    profit_margin = safe_float(info.get('profit_margin'))
    if profit_margin is not None and profit_margin < -0.30:  # Losing >30% on revenue
        if sector not in ['Technology', 'Healthcare', 'Communication Services']:
            return True, f"Unsustainable losses ({ticker} margin = {profit_margin*100:.1f}%)"
    
    # Passed all checks
    return False, None


def calculate_quality_score(info):
    """
    Calculate a simple quality score (0-100) based on fundamentals
    This is NOT a "buy" score - just helps rank the filtered universe
    Higher = better quality metrics
    
    Components:
    - Profitability (30 pts): Positive earnings, good margins
    - Value (25 pts): Reasonable P/E, P/B
    - Financial Health (25 pts): Low debt, high ROE  
    - Growth (20 pts): Revenue growth, margin expansion
    """
    
    # ETFs get neutral score (we don't rank them on fundamentals)
    if info.get('asset_type') == 'ETF':
        return 50
    
    # Helper to safely convert to float
    def safe_float(value):
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    score = 0
    sector = info.get('sector', 'Unknown')
    
    # --- PROFITABILITY (30 points) ---
    profit_margin = safe_float(info.get('profit_margin'))
    if profit_margin is not None:
        if profit_margin > 0.20:  # >20% is excellent
            score += 30
        elif profit_margin > 0.10:  # 10-20% is good
            score += 20
        elif profit_margin > 0:  # Positive is acceptable
            score += 10
        # Negative = 0 points
    
    # --- VALUE (25 points) ---
    pe_ratio = safe_float(info.get('pe_ratio'))
    if pe_ratio is not None and pe_ratio > 0:
        # Lower P/E is better (but not too low = distressed)
        if 8 < pe_ratio < 15:  # Sweet spot for value
            score += 15
        elif 5 < pe_ratio < 25:  # Reasonable range
            score += 10
        elif pe_ratio < 30:  # Growth premium acceptable
            score += 5
    
    pb_ratio = safe_float(info.get('pb_ratio'))
    if pb_ratio is not None and pb_ratio > 0:
        if sector in ['Financial Services', 'Financials', 'Real Estate']:
            # Asset-heavy industries: P/B < 1.5 is good
            if pb_ratio < 1.5:
                score += 10
            elif pb_ratio < 2.5:
                score += 5
        else:
            # Asset-light: P/B < 3 is reasonable
            if pb_ratio < 3:
                score += 10
            elif pb_ratio < 6:
                score += 5
    
    # --- FINANCIAL HEALTH (25 points) ---
    roe = safe_float(info.get('roe'))
    if roe is not None:
        if roe > 0.20:  # >20% ROE is excellent
            score += 15
        elif roe > 0.10:  # 10-20% is good
            score += 10
        elif roe > 0:  # Positive is acceptable
            score += 5
    
    debt_equity = safe_float(info.get('debt_to_equity'))
    if debt_equity is not None:
        if sector in ['Financial Services', 'Financials']:
            # Banks have high leverage - don't penalize
            score += 10
        else:
            # Non-financials: lower debt is better
            if debt_equity < 50:  # <50% is conservative
                score += 10
            elif debt_equity < 100:  # <100% is healthy
                score += 7
            elif debt_equity < 200:  # <200% is acceptable
                score += 3
    
    # --- GROWTH (20 points) ---
    revenue_growth = safe_float(info.get('revenue_growth'))
    if revenue_growth is not None:
        if revenue_growth > 0.20:  # >20% growth is strong
            score += 20
        elif revenue_growth > 0.10:  # 10-20% is good
            score += 15
        elif revenue_growth > 0.05:  # 5-10% is moderate
            score += 10
        elif revenue_growth > 0:  # Positive growth
            score += 5
    
    return min(100, score)  # Cap at 100


# Initialize daily cache in session state
from datetime import datetime
today = datetime.now().date()

if 'universe_cache_date' not in st.session_state:
    st.session_state.universe_cache_date = None
if 'universe_cache' not in st.session_state:
    st.session_state.universe_cache = None

# Clear cache if it's a new day
if st.session_state.universe_cache_date != today:
    st.session_state.universe_cache = None
    st.session_state.universe_cache_date = today

# STEP 1: Asset Class Selection
st.subheader("📊 Step 1: What Type of Investment?")
st.markdown("Choose the asset class you want to screen:")

asset_class = st.radio(
    "Asset Class:",
    options=["Equities (Stocks)", "ETFs (Exchange-Traded Funds)", "Bonds", "All"],
    help="Equities = individual companies | ETFs = baskets of securities | Bonds = fixed income"
)

st.markdown("---")

# STEP 2: Run the Screening
st.subheader("🔍 Step 2: Load and Screen Universe")

# Check if we already have cached data for today
if st.session_state.universe_cache is not None:
    st.success(f"✅ Universe already loaded today! Showing {len(st.session_state.universe_cache)} cached securities.")
    st.info("💡 The universe is cached for the day. It will auto-refresh tomorrow. You can now use the Advanced Factor Analysis below.")
else:
    st.markdown("""
    **Ready to load?** Click below to fetch the universe and apply quality filters:
    - Market cap ≥ $1B (filters out micro-caps)
    - Bad apple elimination (unprofitable, excessive debt, etc.)
    - Results are cached for the day (click off/back won't require reload)
    """)

# Only show button if cache is empty
if st.session_state.universe_cache is None and st.button("🔍 Load Universe and Screen", type="primary", use_container_width=True):
    
    # Set default filters (simplified - always applied)
    min_market_cap = 1_000_000_000  # $1B minimum
    max_debt_equity = 9999  # No debt filter
    max_tickers = 500  # Sample limit for performance
    
    # Step 1: Load S&P 500 ticker universe
    with st.spinner("📥 Loading S&P 500 ticker universe..."):
        # Use S&P 500 tickers from benchmarks
        if not st.session_state.sp500_tickers:
            st.error("❌ S&P 500 tickers not available. Please ensure sector benchmarks are loaded.")
            st.stop()
        
        all_tickers = st.session_state.sp500_tickers
        
        st.success(f"✓ Loaded {len(all_tickers):,} tickers from S&P 500")
    
    # Step 2: Screen with filters and bad apple elimination
    with st.spinner("🔍 Screening securities and filtering out bad apples..."):
        estimated_time = len(all_tickers) * 0.8 / 60  # ~0.8 seconds per ticker
        st.info(f"📊 Screening {len(all_tickers):,} securities (estimated time: {estimated_time:.1f} minutes)...")
        st.caption(f"Filters: {asset_class} | Market cap ≥ $1B | Bad apple elimination active")
        
        # Always fetch fundamentals for quality scoring
        include_fundamentals = True
        
        # Track statistics
        screened_securities = []
        bad_apples = []
        filtered_count = {'market_cap': 0, 'debt': 0, 'asset_class': 0, 'bad_apple': 0}
        
        # Cache for factor scores (for fast style ranking later)
        factor_scores_cache = {}
        
        # Get benchmarks if available for factor scoring
        benchmarks_data = None
        if st.session_state.get('benchmarks_available', False):
            benchmarks_data = st.session_state.benchmarks.data
        
        progress_bar = st.progress(0)
        progress_text = st.empty()
        
        for i, ticker in enumerate(all_tickers):
            if i % 10 == 0:  # Update every 10 tickers to avoid UI lag
                progress_text.text(f"Analyzing {ticker}... ({i+1}/{len(all_tickers):,})")
                progress_bar.progress((i + 1) / len(all_tickers))
            
            info = get_ticker_info(ticker, include_fundamentals=include_fundamentals)
            
            # Apply market cap filter
            if min_market_cap > 0:
                if info.get('market_cap', 0) < min_market_cap:
                    filtered_count['market_cap'] += 1
                    continue
            
            # Apply debt/equity filter
            if max_debt_equity < 9999:
                debt_equity = info.get('debt_to_equity')
                if debt_equity and debt_equity > max_debt_equity:
                    filtered_count['debt'] += 1
                    continue
            
            # Apply asset class filter (double-check yfinance data)
            asset_type = info.get('asset_type', 'Unknown')
            if asset_class == "Equities (Stocks)" and asset_type != 'Equity':
                filtered_count['asset_class'] += 1
                continue
            elif asset_class == "ETFs (Exchange-Traded Funds)" and asset_type != 'ETF':
                filtered_count['asset_class'] += 1
                continue
            elif asset_class == "Bonds" and 'Bond' not in asset_type and 'Fixed Income' not in info.get('sector', ''):
                filtered_count['asset_class'] += 1
                continue
            # "All" = no filter
            
            # BAD APPLE FILTER - eliminate obvious problems
            is_bad, reason = is_bad_apple(info, asset_class)
            if is_bad:
                filtered_count['bad_apple'] += 1
                bad_apples.append({'ticker': ticker, 'reason': reason})
                continue
            
            # Calculate quality score for ranking
            info['quality_score'] = calculate_quality_score(info)
            
            # Calculate factor scores for advanced analysis (if benchmarks available)
            # This uses the already-fetched yfinance info, no additional API call
            if benchmarks_data and asset_type == 'Equity':
                try:
                    # Get the full yfinance info for factor scoring
                    stock = yf.Ticker(ticker)
                    full_info = stock.info
                    
                    factor_scores = score_stock_from_info(ticker, full_info, benchmarks_data)
                    if factor_scores:
                        factor_scores_cache[ticker] = factor_scores
                except Exception as e:
                    pass  # Skip if factor scoring fails
            
            screened_securities.append(info)
        
        progress_bar.empty()
        progress_text.empty()
        
        # Show filtering statistics
        st.success(f"✅ Screening complete! Found **{len(screened_securities)}** quality securities")
        
        with st.expander("📊 Filtering Statistics"):
            st.write(f"**Started with:** {len(all_tickers):,} tickers")
            st.write(f"**Filtered out:**")
            st.write(f"  - Market cap too small: {filtered_count['market_cap']:,}")
            st.write(f"  - Debt too high: {filtered_count['debt']:,}")
            st.write(f"  - Wrong asset class: {filtered_count['asset_class']:,}")
            st.write(f"  - ❌ **Bad apples** (red flags): {filtered_count['bad_apple']:,}")
            st.write(f"**Passed all filters:** {len(screened_securities):,}")
            
            if bad_apples and len(bad_apples) <= 20:
                st.markdown("**Examples of filtered 'bad apples':**")
                for ba in bad_apples[:10]:
                    st.caption(f"• {ba['reason']}")
        
        # Display results
        if screened_securities:
            df = pd.DataFrame(screened_securities)
            
            # Sort by quality score (high to low)
            df = df.sort_values('quality_score', ascending=False)
            df['rank'] = range(1, len(df) + 1)
            
            st.info(f"📊 Displaying {len(df)} securities ranked by quality score")
            st.caption("**Quality Score:** Simple 0-100 ranking based on profitability, valuation, financial health, and growth. Higher = better fundamentals.")
            
            # Format market cap
            df['market_cap_formatted'] = df['market_cap'].apply(
                lambda x: f"${x/1e9:.2f}B" if x > 0 else "N/A"
            )
            
            # Format price
            df['price_formatted'] = df['price'].apply(
                lambda x: f"${x:.2f}" if x > 0 else "N/A"
            )
            
            # Format quality score
            df['quality_score_formatted'] = df['quality_score'].apply(
                lambda x: f"{x:.0f}/100" if pd.notna(x) else "N/A"
            )
            
            # Format fundamental metrics
            if include_fundamentals:
                # P/E Ratio
                if 'pe_ratio' in df.columns:
                    df['pe_ratio_formatted'] = df['pe_ratio'].apply(
                        lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
                    )
                
                # P/B Ratio
                if 'pb_ratio' in df.columns:
                    df['pb_ratio_formatted'] = df['pb_ratio'].apply(
                        lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
                    )
                
                # Dividend Yield
                if 'dividend_yield' in df.columns:
                    df['dividend_yield_formatted'] = df['dividend_yield'].apply(
                        lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A"
                    )
                
                # Profit Margin
                if 'profit_margin' in df.columns:
                    df['profit_margin_formatted'] = df['profit_margin'].apply(
                        lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A"
                    )
                
                # Revenue Growth
                if 'revenue_growth' in df.columns:
                    df['revenue_growth_formatted'] = df['revenue_growth'].apply(
                        lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A"
                    )
                
                # ROE
                if 'roe' in df.columns:
                    df['roe_formatted'] = df['roe'].apply(
                        lambda x: f"{x*100:.2f}%" if pd.notna(x) else "N/A"
                    )
                
                # Debt to Equity
                if 'debt_to_equity' in df.columns:
                    df['debt_to_equity_formatted'] = df['debt_to_equity'].apply(
                        lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
                    )
                
                # EV/EBITDA
                if 'ev_ebitda' in df.columns:
                    df['ev_ebitda_formatted'] = df['ev_ebitda'].apply(
                        lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
                    )
            
            # Build display columns - include quality score and all fundamentals
            display_columns = ['rank', 'ticker', 'name', 'quality_score_formatted', 'asset_type', 'sector', 'market_cap_formatted', 'price_formatted']
            column_names = ['Rank', 'Ticker', 'Name', 'Quality', 'Type', 'Sector', 'Market Cap', 'Price']
            
            # Add all fundamental metrics
            fundamental_cols = {
                'pe_ratio_formatted': 'P/E',
                'pb_ratio_formatted': 'P/B',
                'dividend_yield_formatted': 'Div Yield',
                'profit_margin_formatted': 'Margin',
                'revenue_growth_formatted': 'Rev Growth',
                'roe_formatted': 'ROE',
                'debt_to_equity_formatted': 'D/E',
                'ev_ebitda_formatted': 'EV/EBITDA'
            }
            
            for col_key, col_name in fundamental_cols.items():
                if col_key in df.columns:
                    display_columns.append(col_key)
                    column_names.append(col_name)
            
            # Display table
            display_df = df[display_columns].copy()
            display_df.columns = column_names
            
            st.markdown("### 📋 Top Quality Securities")
            st.markdown(f"**Showing {len(df)} securities** ranked by fundamental quality (highest first)")
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Summary stats
            st.markdown("#### Quick Summary")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Securities Found", len(screened_securities), help="Total companies/ETFs passing all filters")
            
            with col2:
                unique_sectors = df['sector'].nunique()
                st.metric("Sectors", unique_sectors, help="Number of different sectors")
            
            with col3:
                avg_quality = df['quality_score'].mean()
                st.metric("Avg Quality", f"{avg_quality:.0f}/100", help="Average quality score")
            
            with col4:
                high_quality = len(df[df['quality_score'] >= 70])
                st.metric("High Quality (≥70)", high_quality, help="Securities scoring 70+")
            
            # Show top performers
            st.markdown("#### 🏆 Top 10 by Quality Score")
            top_10 = df.head(10)
            for idx, (_, row) in enumerate(top_10.iterrows(), 1):
                ticker = row['ticker']
                name = row['name']
                score = row['quality_score']
                sector = row['sector']
                mcap = row['market_cap_formatted']
                
                # Color code by score
                if score >= 70:
                    st.success(f"**#{idx} - {ticker}** ({score:.0f}/100) | {name} | {sector} | {mcap}")
                elif score >= 50:
                    st.info(f"**#{idx} - {ticker}** ({score:.0f}/100) | {name} | {sector} | {mcap}")
                else:
                    st.warning(f"**#{idx} - {ticker}** ({score:.0f}/100) | {name} | {sector} | {mcap}")
            
            # Save to cache
            st.session_state.universe_cache = df
            
            # Save factor scores cache for fast style ranking
            if factor_scores_cache:
                st.session_state.factor_scores_cache = factor_scores_cache
                st.success(f"✅ Cached factor scores for {len(factor_scores_cache)} stocks (enables instant style ranking)")
        
        else:
            st.warning("No securities match your filters. Try adjusting your exclusions.")

# ============================================================================
# DISPLAY RESULTS (outside button block - uses cache)
# ============================================================================
st.markdown("---")

if st.session_state.universe_cache is not None:
    df = st.session_state.universe_cache
    
    # ========================================
    # FACTOR-BASED ANALYSIS SECTION
    # ========================================
    if st.session_state.get('benchmarks_available', False):
        st.markdown("---")
        st.subheader("🔬 Advanced Factor Analysis")
        st.markdown(f"**Rank {len(df)} S&P 500 stocks by investment style**")
        
        # Create tabs for style-based screening and individual analysis
        factor_tab1, factor_tab2 = st.tabs(["📊 Style-Based Ranking", "🔍 Individual Stock Analysis"])
        
        with factor_tab1:
            # Get list of stocks from current screening results
            available_tickers = df['ticker'].tolist()
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                style_choice = st.selectbox(
                    "Investment Style",
                    options=['growth', 'value', 'quality', 'balanced'],
                    format_func=lambda x: INVESTMENT_STYLES[x]['name'],
                    help="Select investment style for ranking"
                )
            
            with col2:
                style_top_n = st.slider("Top N stocks", 5, 20, 10, key="style_top_n")
            
            # Show style info
            style_info = INVESTMENT_STYLES[style_choice]
            with st.expander("ℹ️ Style Details"):
                st.markdown(f"**{style_info['name']}**: {style_info['description']}")
                st.markdown(f"*Best for:* {style_info['ideal_for']}")
                st.markdown(f"*Examples:* {', '.join(style_info['examples'])}")
            
            # Warning about performance
            if 'factor_scores_cache' in st.session_state:
                st.success(f"♻️ Using cached factor scores for {len(st.session_state.factor_scores_cache)} stocks - this will be instant!")
            else:
                st.info(f"💡 This will fetch detailed fundamental data for {len(available_tickers)} stocks. May take 2-5 minutes.")
            
            if st.button("🎯 Rank by Style", type="primary"):
                # Use cached factor scores if available
                if 'factor_scores_cache' in st.session_state and st.session_state.factor_scores_cache:
                    with st.spinner(f"Ranking stocks by {style_info['name']} style..."):
                        style_results = rank_stocks_by_style_cached(
                            factor_scores_dict=st.session_state.factor_scores_cache,
                            style=style_choice,
                            top_n=style_top_n
                        )
                        st.session_state.style_screening_results = style_results
                else:
                    # Fallback to fetching data (slower)
                    st.warning("⚠️ Factor scores not cached - fetching fresh data (this will be slow)")
                    with st.spinner(f"Ranking {len(available_tickers)} stocks by {style_info['name']} style..."):
                        benchmarks = st.session_state.benchmarks
                        
                        style_results = get_top_stocks_by_style(
                            screened_stocks=available_tickers,
                            style=style_choice,
                            top_n=style_top_n,
                            sector_benchmarks=benchmarks.data
                        )
                        st.session_state.style_screening_results = style_results
                
                if style_results.empty:
                    st.warning(f"⚠️ No stocks passed minimum thresholds for {style_info['name']} style")
                else:
                    st.success(f"✅ Found {len(style_results)} stocks matching {style_info['name']} criteria")
                    
                    # Display results - use only columns that exist
                    available_cols = style_results.columns.tolist()
                    
                    # Core columns we want to show (if they exist)
                    desired_cols = ['ticker', 'sector', 'style_score', 
                                  'revenue_growth_pct', 'roe_pct', 'pe_pct']
                    
                    display_cols = [col for col in desired_cols if col in available_cols]
                    
                    display_df = style_results[display_cols].copy()
                    
                    # Rename columns for display
                    col_rename = {
                        'ticker': 'Ticker',
                        'sector': 'Sector',
                        'style_score': 'Style Score',
                        'revenue_growth_pct': 'Rev Growth %ile',
                        'roe_pct': 'ROE %ile',
                        'pe_pct': 'P/E %ile'
                    }
                    display_df.columns = [col_rename.get(col, col) for col in display_df.columns]
                    
                    # Round numerics
                    numeric_cols = display_df.select_dtypes(include=['float64', 'float32']).columns
                    display_df[numeric_cols] = display_df[numeric_cols].round(1)
                    
                    # Display without background gradient (requires matplotlib)
                    st.dataframe(display_df, use_container_width=True)
        
        with factor_tab2:
            st.markdown("**Deep-dive analysis showing percentile rankings vs sector peers**")
            
            # Stock selector
            if 'style_screening_results' in st.session_state and not st.session_state.style_screening_results.empty:
                analysis_tickers = st.session_state.style_screening_results['ticker'].tolist()
                st.info(f"💡 Showing top stocks from style ranking ({len(analysis_tickers)} available)")
            else:
                analysis_tickers = available_tickers[:20]  # Limit to top 20 from screening
            
            selected_analysis_ticker = st.selectbox(
                "Select stock for detailed analysis",
                options=analysis_tickers,
                key="analysis_ticker_select"
            )
            
            if st.button("📊 Analyze Stock", type="primary", key="analyze_btn"):
                with st.spinner(f"Analyzing {selected_analysis_ticker}..."):
                    benchmarks = st.session_state.benchmarks
                    scores = score_stock_all_factors(
                        selected_analysis_ticker,
                        sector_benchmarks=benchmarks.data
                    )
                    
                    if not scores:
                        st.error(f"❌ Unable to fetch data for {selected_analysis_ticker}")
                    else:
                        # Header
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Ticker", scores['ticker'])
                        with col2:
                            st.metric("Sector", scores['sector'])
                        with col3:
                            mcap_b = scores['market_cap'] / 1e9
                            st.metric("Market Cap", f"${mcap_b:.1f}B")
                        
                        st.markdown("---")
                        
                        # Four factor categories
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.markdown("**💰 Profitability**")
                            st.metric("ROE", 
                                     f"{scores['raw_roe']:.1%}" if scores['raw_roe'] else "N/A",
                                     f"{scores['roe_pct']:.0f}th %ile")
                            st.metric("Profit Margin",
                                     f"{scores['raw_profit_margin']:.1%}" if scores['raw_profit_margin'] else "N/A",
                                     f"{scores['profit_margin_pct']:.0f}th %ile")
                            st.metric("ROIC",
                                     f"{scores['raw_roic']:.1%}" if scores['raw_roic'] else "N/A",
                                     f"{scores['roic_pct']:.0f}th %ile")
                        
                        with col2:
                            st.markdown("**📈 Growth**")
                            st.metric("Revenue Growth",
                                     f"{scores['raw_revenue_growth']:.1%}" if scores['raw_revenue_growth'] else "N/A",
                                     f"{scores['revenue_growth_pct']:.0f}th %ile")
                            st.metric("Earnings Growth",
                                     f"{scores['raw_earnings_growth']:.1%}" if scores['raw_earnings_growth'] else "N/A",
                                     f"{scores['earnings_growth_pct']:.0f}th %ile")
                        
                        with col3:
                            st.markdown("**💵 Value**")
                            st.metric("P/E Ratio",
                                     f"{scores['raw_pe']:.1f}" if scores['raw_pe'] else "N/A",
                                     f"{scores['pe_pct']:.0f}th %ile")
                            st.metric("P/B Ratio",
                                     f"{scores['raw_pb']:.2f}" if scores['raw_pb'] else "N/A",
                                     f"{scores['pb_pct']:.0f}th %ile")
                            st.metric("FCF Yield",
                                     f"{scores['raw_fcf_yield']:.2f}%" if scores['raw_fcf_yield'] else "N/A",
                                     f"{scores['fcf_yield_pct']:.0f}th %ile")
                        
                        with col4:
                            st.markdown("**🛡️ Safety**")
                            st.metric("Debt/Equity",
                                     f"{scores['raw_debt_equity']:.1f}" if scores['raw_debt_equity'] else "N/A",
                                     f"{scores['debt_equity_pct']:.0f}th %ile")
                            st.metric("Current Ratio",
                                     f"{scores['raw_current_ratio']:.2f}" if scores['raw_current_ratio'] else "N/A",
                                     f"{scores['current_ratio_pct']:.0f}th %ile")
                        
                        # Percentile chart
                        st.markdown("---")
                        st.markdown("**📊 Percentile Rankings vs Sector Peers**")
                        
                        percentile_data = pd.DataFrame({
                            'Factor': ['ROE', 'Margin', 'ROIC', 'Rev Growth', 'Earn Growth',
                                      'P/E', 'P/B', 'FCF Yield', 'Debt/Eq', 'Current Ratio'],
                            'Percentile': [
                                scores['roe_pct'], scores['profit_margin_pct'], scores['roic_pct'],
                                scores['revenue_growth_pct'], scores['earnings_growth_pct'],
                                scores['pe_pct'], scores['pb_pct'], scores['fcf_yield_pct'],
                                scores['debt_equity_pct'], scores['current_ratio_pct']
                            ]
                        })
                        
                        st.bar_chart(percentile_data.set_index('Factor')['Percentile'])
                        
                        st.caption(f"Compared to {scores['sector']} sector peers from S&P 500 ({benchmarks.data['metadata']['total_stocks']} stocks)")

st.markdown("---")

st.info("""
**Note**: This screener uses S&P 500 stocks fetched from Wikipedia (~500 large-cap US stocks).
Factor analysis compares each stock to its sector peers within the S&P 500.

For institutional-grade screening with broader coverage, integrate with Bloomberg or FactSet APIs.
""")
