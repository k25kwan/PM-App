"""
Fundamental Analysis  
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

# Add project root and investment framework to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src" / "investment framework" / "fundamental analysis"))

from src.core.utils_db import get_conn
from sector_benchmarks import SectorBenchmarks
from factor_scoring import score_stock_all_factors, score_stock_from_info
from investment_styles import get_top_stocks_by_style, rank_stocks_by_style_cached, rank_stocks_by_style_normalized, INVESTMENT_STYLES

st.set_page_config(page_title="Fundamental Analysis", layout="wide")

# Initialize sector benchmarks (cache in session state)
if 'benchmarks' not in st.session_state:
    try:
        benchmarks = SectorBenchmarks()
        if benchmarks.load_from_cache():
            st.session_state.benchmarks = benchmarks
            st.session_state.benchmarks_available = True
            # Fetch fresh S&P 500 tickers from Wikipedia (not from cache)
            fresh_tickers = benchmarks.get_sp1500_tickers()
            st.session_state.sp500_tickers = fresh_tickers
            print(f"DEBUG: Fetched {len(fresh_tickers)} tickers from Wikipedia")
        else:
            st.session_state.benchmarks_available = False
            st.session_state.sp500_tickers = []
    except Exception as e:
        st.session_state.benchmarks_available = False
        st.session_state.sp500_tickers = []

st.title("Fundamental Analysis")
st.markdown("Discover quality stocks from the S&P 500 using fundamental factor analysis")

# Show ticker count for debugging
if st.session_state.get('sp500_tickers'):
    st.caption(f"S&P 500 Universe: {len(st.session_state.sp500_tickers)} tickers available")

# Add cache clearing button
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🔄 Clear Cache & Reload", help="Clear all cached data and reload benchmarks"):
        # Clear all screening-related cache
        keys_to_clear = ['factor_scores_cache', 'style_screening_results', 'score_type', 
                        'benchmarks', 'benchmarks_available', 'sp500_tickers']
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.success("Cache cleared! Page will reload with fresh data.")
        st.rerun()

def get_ticker_info(ticker, include_fundamentals=False):
    """Fetch ticker info from yfinance for equities"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if include_fundamentals:
            # Return the FULL yfinance info dict for factor scoring
            # score_stock_from_info() needs all the raw yfinance fields
            # Add ticker field since yfinance info doesn't include it
            full_info = info.copy()
            full_info['ticker'] = ticker
            return full_info
        
        # Get sector from yfinance
        sector = info.get('sector', 'Unknown')
        
        base_info = {
            'ticker': ticker,
            'name': info.get('longName', ticker),
            'sector': sector,
            'industry': info.get('industry', 'Unknown'),
            'market_cap': info.get('marketCap', 0),
            'country': info.get('country', 'Unknown'),
            'price': info.get('currentPrice', info.get('regularMarketPrice', 0))
        }
        
        return base_info
    except Exception as e:
        # Return minimal info if yfinance fails
        base_info = {
            'ticker': ticker,
            'name': ticker,
            'sector': 'Unknown',
            'industry': 'Unknown',
            'market_cap': 0,
            'country': 'US',
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

def is_bad_apple(info):
    """
    Filter out obvious "bad apples" - companies with red flags
    This is NOT scoring, just eliminating clear problems
    
    For S&P 500 stocks, filters should be VERY lenient - only catch data errors
    and truly distressed companies, not just expensive/leveraged ones.
    
    Returns: (is_bad: bool, reason: str)
    """
    
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
    # Relaxed from 300% to 1000% - S&P 500 companies can handle leverage
    debt_equity = safe_float(info.get('debt_to_equity'))
    sector = info.get('sector', '')
    if debt_equity is not None and sector not in ['Financial Services', 'Financials', 'Real Estate']:
        if debt_equity > 1000:  # 1000% D/E is truly excessive
            return True, f"Excessive debt ({ticker} D/E = {debt_equity:.0f}%)"
    
    # Rule 3: Extremely low ROE (return on equity) = inefficient capital use
    # Only filter truly terrible cases (losing >50% on equity)
    roe = safe_float(info.get('roe'))
    if roe is not None and roe < -0.50:  # Losing >50% on equity
        return True, f"Poor returns ({ticker} ROE = {roe*100:.1f}%)"
    
    # Rule 4: Absurd valuations - removed P/E filter entirely
    # S&P 500 can have high P/E stocks (growth, momentum)
    # Keep P/B filter but make it more lenient
    pb_ratio = safe_float(info.get('pb_ratio'))
    if pb_ratio is not None and pb_ratio > 100 and sector not in ['Technology', 'Communication Services']:
        return True, f"Extreme P/B ratio ({ticker} P/B = {pb_ratio:.1f})"
    
    # Rule 5: Negative profit margins (unless growth/startup)
    # Only filter if losing >50% on revenue (truly unsustainable)
    profit_margin = safe_float(info.get('profit_margin'))
    if profit_margin is not None and profit_margin < -0.50:  # Losing >50% on revenue
        if sector not in ['Technology', 'Healthcare', 'Communication Services']:
            return True, f"Unsustainable losses ({ticker} margin = {profit_margin*100:.1f}%)"
    
    # Passed all checks
    return False, None


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

# Check if we already have cached data for today
if st.session_state.universe_cache is not None:
    st.success(f"Universe already loaded today! Showing {len(st.session_state.universe_cache)} cached securities.")
    st.info("The universe is cached for the day. It will auto-refresh tomorrow. You can now use the Advanced Factor Analysis below.")

# Only show button if cache is empty
if st.session_state.universe_cache is None and st.button("Load S&P 500 Universe and Screen", type="primary", use_container_width=True):
    
    # Load S&P 500 ticker universe
    with st.spinner("Loading S&P 500 ticker universe..."):
        # Use S&P 500 tickers from benchmarks
        if not st.session_state.sp500_tickers:
            st.error("S&P 500 tickers not available. Please ensure sector benchmarks are loaded.")
            st.stop()
        
        all_tickers = st.session_state.sp500_tickers
    
    # Screen with bad apple elimination
    estimated_time = len(all_tickers) * 0.8 / 60  # ~0.8 seconds per ticker
    
    # Always fetch fundamentals for factor scoring
    include_fundamentals = True
    
    # Track statistics
    screened_securities = []
    bad_apples = []
    filtered_count = {'bad_apple': 0}
    
    # Cache for factor scores (for fast style ranking later)
    factor_scores_cache = {}
    
    # Get benchmarks if available for factor scoring
    benchmarks_data = None
    if st.session_state.get('benchmarks_available', False):
        benchmarks_data = st.session_state.benchmarks.data
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, ticker in enumerate(all_tickers):
        # Update progress
        progress = (i + 1) / len(all_tickers)
        progress_bar.progress(progress)
        
        # Calculate time remaining
        elapsed_tickers = i + 1
        remaining_tickers = len(all_tickers) - elapsed_tickers
        time_remaining = remaining_tickers * 0.8 / 60  # minutes
        
        status_text.text(f"Screening {elapsed_tickers}/{len(all_tickers)} stocks... ({time_remaining:.1f} min remaining)")
        
        info = get_ticker_info(ticker, include_fundamentals=include_fundamentals)
        
        # BAD APPLE FILTER - eliminate obvious problems
        is_bad, reason = is_bad_apple(info)
        if is_bad:
            filtered_count['bad_apple'] += 1
            bad_apples.append({'ticker': ticker, 'reason': reason})
            continue
        
        # Calculate factor scores for advanced analysis (uses already-fetched info)
        if benchmarks_data:
            try:
                # Use the yfinance info we already fetched - no additional API call
                factor_scores = score_stock_from_info(ticker, info, benchmarks_data)
                if factor_scores:
                    factor_scores_cache[ticker] = factor_scores
            except Exception as e:
                pass  # Skip if factor scoring fails
        
        screened_securities.append(info)
    
    progress_bar.empty()
    status_text.empty()
    
    # Show final result
    st.success(f"✓ Screening complete! Found {len(screened_securities)} quality stocks, filtered out {len(bad_apples)} bad apples")
    
    # Display results
    if screened_securities:
        df = pd.DataFrame(screened_securities)
        
        # Save to cache
        st.session_state.universe_cache = df
        
        # Save bad apples to session state for persistent display
        st.session_state.bad_apples = bad_apples
        
        # Save factor scores cache for fast style ranking
        if factor_scores_cache:
            st.session_state.factor_scores_cache = factor_scores_cache
        
        else:
            st.warning("No securities passed the bad apple filter.")

# ============================================================================
# DISPLAY RESULTS (outside button block - uses cache)
# ============================================================================
st.markdown("---")

# Show bad apples if available (persists across interactions)
if st.session_state.get('bad_apples'):
    bad_apples = st.session_state.bad_apples
    with st.expander(f"⚠️ View {len(bad_apples)} filtered stocks (Bad Apples)", expanded=False):
        bad_apple_df = pd.DataFrame(bad_apples)
        st.dataframe(bad_apple_df, use_container_width=True, hide_index=True)
        st.caption("These stocks were filtered out during screening. Review the reasons to ensure quality companies aren't incorrectly excluded.")

if st.session_state.universe_cache is not None:
    df = st.session_state.universe_cache
    
    # ========================================
    # FACTOR-BASED ANALYSIS SECTION
    # ========================================
    if st.session_state.get('benchmarks_available', False):
        st.markdown("---")
        st.subheader("Advanced Factor Analysis")
        st.markdown(f"Rank and filter {len(df)} S&P 500 stocks")
        
        # Create tabs for style-based screening and individual analysis
        factor_tab1, factor_tab2 = st.tabs(["Style-Based Ranking", "Individual Stock Analysis"])
        
        with factor_tab1:
            # Get list of stocks from current screening results
            available_tickers = df['ticker'].tolist()
            
            # Add helpful prompting
            st.info("**How to use:** Select a sector to view fundamentals, or select both a sector AND a style to see style-based rankings with scores.")
            
            # Simplified filter interface
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                style_choice = st.selectbox(
                    "Investment Style (Required for Rankings)",
                    options=['None'] + ['growth', 'value', 'quality', 'balanced'],
                    format_func=lambda x: 'Select a style for rankings...' if x == 'None' else INVESTMENT_STYLES[x]['name'],
                    help="Style-based ranking requires selecting a style. Growth prioritizes revenue/earnings growth, Value prioritizes low P/E and P/B, Quality prioritizes high ROE and margins, Balanced uses equal weights."
                )
            
            with col2:
                # Sector filter option - convert to strings and filter out NaN/None
                sectors = df['sector'].dropna().astype(str).unique().tolist()
                all_sectors = sorted([s for s in sectors if s and s != 'nan'])
                sector_filter = st.selectbox(
                    "Sector (Optional)",
                    options=['All Sectors'] + all_sectors,
                    help="Filter to specific sector or view across all sectors. When no style is selected, fundamentals will still be shown."
                )
            
            with col3:
                style_top_n = st.slider("Top N", 5, 20, 10, key="style_top_n")
            
            if st.button("Apply Filters", type="primary"):
                # Apply sector filter if specified
                sector_to_filter = None if sector_filter == 'All Sectors' else sector_filter
                use_style = style_choice != 'None'
                
                # Determine if we should use normalized scoring (cross-sector comparison)
                use_normalized = (sector_to_filter is None) and use_style
                
                if use_style:
                    # Style-based ranking with style scores
                    style_info = INVESTMENT_STYLES[style_choice]
                    
                    # Use cached factor scores if available
                    if 'factor_scores_cache' in st.session_state and st.session_state.factor_scores_cache:
                        if use_normalized:
                            # Cross-sector comparison - use normalized z-scores
                            with st.spinner(f"Ranking stocks by {style_info['name']} style (normalized across all sectors)..."):
                                style_results = rank_stocks_by_style_normalized(
                                    factor_scores_dict=st.session_state.factor_scores_cache,
                                    style=style_choice,
                                    sector=sector_to_filter,
                                    top_n=style_top_n,
                                    use_z_scores=True
                                )
                                st.session_state.style_screening_results = style_results
                                st.session_state.score_type = 'normalized'
                        else:
                            # Within-sector comparison - use percentiles
                            with st.spinner(f"Ranking stocks by {style_info['name']} style..."):
                                style_results = rank_stocks_by_style_cached(
                                    factor_scores_dict=st.session_state.factor_scores_cache,
                                    style=style_choice,
                                    sector=sector_to_filter,
                                    top_n=style_top_n
                                )
                                st.session_state.style_screening_results = style_results
                                st.session_state.score_type = 'percentile'
                    else:
                        # Fallback to fetching data (slower) - only supports percentile scoring
                        st.warning("Factor scores not cached - fetching fresh data (this will be slow)")
                        with st.spinner(f"Ranking {len(available_tickers)} stocks by {style_info['name']} style..."):
                            benchmarks = st.session_state.benchmarks
                            
                            style_results = get_top_stocks_by_style(
                                screened_stocks=available_tickers,
                                style=style_choice,
                                sector=sector_to_filter,
                                top_n=style_top_n,
                                sector_benchmarks=benchmarks.data
                            )
                            st.session_state.style_screening_results = style_results
                            st.session_state.score_type = 'percentile'
                    
                    if style_results.empty:
                        filter_msg = f" in {sector_filter}" if sector_to_filter else ""
                        st.warning(f"No stocks passed minimum thresholds for {style_info['name']} style{filter_msg}")
                    else:
                        filter_msg = f" in {sector_filter}" if sector_to_filter else ""
                        st.success(f"Found {len(style_results)} stocks matching {style_info['name']} criteria{filter_msg}")
                
                else:
                    # No style selected - show fundamentals only (no style scores)
                    st.info("Showing fundamentals without style ranking. Select a style above to see style-based scores and rankings.")
                    
                    # Get stocks to analyze
                    tickers_to_analyze = available_tickers.copy()
                    if sector_to_filter:
                        sector_stocks = df[df['sector'] == sector_to_filter]['ticker'].tolist()
                        tickers_to_analyze = sector_stocks
                    
                    # Limit to top_n
                    tickers_to_analyze = tickers_to_analyze[:style_top_n]
                    
                    # Fetch fundamentals for these stocks
                    benchmarks = st.session_state.benchmarks
                    fundamental_results = []
                    
                    with st.spinner(f"Fetching fundamentals for {len(tickers_to_analyze)} stocks..."):
                        for ticker in tickers_to_analyze:
                            scores = score_stock_all_factors(ticker, sector_benchmarks=benchmarks.data)
                            if scores:
                                fundamental_results.append(scores)
                    
                    if fundamental_results:
                        style_results = pd.DataFrame(fundamental_results)
                        st.session_state.style_screening_results = style_results
                        
                        filter_msg = f" in {sector_filter}" if sector_to_filter else ""
                        st.success(f"Loaded fundamentals for {len(style_results)} stocks{filter_msg}")
                    else:
                        style_results = pd.DataFrame()
                        st.warning("No fundamental data available for selected stocks")
                        st.session_state.style_screening_results = style_results
                
                if not style_results.empty:
                    # Display results - show appropriate columns based on whether style is used
                    available_cols = style_results.columns.tolist()
                    
                    # Determine which score column to use
                    score_type = st.session_state.get('score_type', 'percentile')
                    score_col = 'style_score_normalized' if score_type == 'normalized' else 'style_score'
                    
                    if use_style:
                        # Show style scores and relevant percentiles
                        if style_choice == 'growth':
                            desired_cols = ['ticker', 'sector', score_col, 
                                          'revenue_growth_pct', 'earnings_growth_pct',
                                          'profit_margin_pct', 'roe_pct',
                                          'raw_revenue_growth', 'raw_earnings_growth']
                        elif style_choice == 'value':
                            desired_cols = ['ticker', 'sector', score_col, 
                                          'pe_pct', 'pb_pct', 'fcf_yield_pct', 'roe_pct',
                                          'raw_pe', 'raw_pb', 'raw_fcf_yield']
                        elif style_choice == 'quality':
                            desired_cols = ['ticker', 'sector', score_col, 
                                          'roe_pct', 'roic_pct', 'profit_margin_pct', 'debt_equity_pct',
                                          'raw_roe', 'raw_roic', 'raw_profit_margin']
                        elif style_choice == 'balanced':
                            desired_cols = ['ticker', 'sector', score_col, 
                                          'revenue_growth_pct', 'roe_pct', 'pe_pct', 'profit_margin_pct',
                                          'raw_revenue_growth', 'raw_roe', 'raw_pe']
                        else:
                            desired_cols = ['ticker', 'sector', score_col]
                    else:
                        # No style - show fundamentals without style score
                        desired_cols = ['ticker', 'sector', 
                                      'roe_pct', 'revenue_growth_pct', 'earnings_growth_pct', 'profit_margin_pct',
                                      'pe_pct', 'pb_pct', 'debt_equity_pct',
                                      'raw_roe', 'raw_revenue_growth', 'raw_earnings_growth', 'raw_profit_margin',
                                      'raw_pe', 'raw_pb', 'raw_debt_equity']
                    
                    display_cols = [col for col in desired_cols if col in available_cols]
                    display_df = style_results[display_cols].copy()
                    
                    # Rename columns for display
                    col_rename = {
                        'ticker': 'Ticker',
                        'sector': 'Sector',
                        'style_score': 'Style Score',
                        'style_score_normalized': 'Style Score (Normalized)',
                        'revenue_growth_pct': 'Rev Growth %ile',
                        'earnings_growth_pct': 'EPS Growth %ile',
                        'profit_margin_pct': 'Margin %ile',
                        'roe_pct': 'ROE %ile',
                        'roic_pct': 'ROIC %ile',
                        'pe_pct': 'P/E %ile (Low=Good)',
                        'pb_pct': 'P/B %ile (Low=Good)',
                        'fcf_yield_pct': 'FCF Yield %ile',
                        'debt_equity_pct': 'Debt %ile (Low=Good)',
                        'raw_revenue_growth': 'Rev Growth %',
                        'raw_earnings_growth': 'EPS Growth %',
                        'raw_profit_margin': 'Margin %',
                        'raw_roe': 'ROE',
                        'raw_roic': 'ROIC',
                        'raw_pe': 'P/E Ratio',
                        'raw_pb': 'P/B Ratio',
                        'raw_fcf_yield': 'FCF Yield %',
                        'raw_debt_equity': 'Debt/Equity'
                    }
                    display_df.columns = [col_rename.get(col, col) for col in display_df.columns]
                    
                    # Round numerics
                    numeric_cols = display_df.select_dtypes(include=['float64', 'float32']).columns
                    display_df[numeric_cols] = display_df[numeric_cols].round(1)
                    
                    # Display table
                    st.dataframe(display_df, use_container_width=True)
                    
                    # Add explanatory caption based on score type
                    if use_style:
                        score_type = st.session_state.get('score_type', 'percentile')
                        if score_type == 'normalized':
                            st.caption("**Normalized Style Score:** Uses z-scores to compare stocks across all sectors on a common scale. Higher scores = better fit for the style regardless of sector.")
                        else:
                            st.caption("**Style Score:** Weighted composite of factor percentiles based on selected investment style. Higher scores = better fit for the style within the selected sector.")
                    else:
                        st.caption("**Percentiles:** Show how each stock ranks within its sector (e.g., 75th percentile ROE = better than 75% of sector peers). Raw values show actual fundamentals.")
        
        with factor_tab2:
            st.markdown("**Deep-dive analysis showing percentile rankings vs sector peers**")
            
            # Stock selector
            if 'style_screening_results' in st.session_state and not st.session_state.style_screening_results.empty:
                analysis_tickers = st.session_state.style_screening_results['ticker'].tolist()
                st.info(f" Showing top stocks from style ranking ({len(analysis_tickers)} available)")
            else:
                analysis_tickers = available_tickers[:20]  # Limit to top 20 from screening
            
            selected_analysis_ticker = st.selectbox(
                "Select stock for detailed analysis",
                options=analysis_tickers,
                key="analysis_ticker_select"
            )
            
            if st.button(" Analyze Stock", type="primary", key="analyze_btn"):
                with st.spinner(f"Analyzing {selected_analysis_ticker}..."):
                    benchmarks = st.session_state.benchmarks
                    scores = score_stock_all_factors(
                        selected_analysis_ticker,
                        sector_benchmarks=benchmarks.data
                    )
                    
                    if not scores:
                        st.error(f" Unable to fetch data for {selected_analysis_ticker}")
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
                            st.markdown("** Profitability**")
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
                            st.markdown("** Growth**")
                            st.metric("Revenue Growth",
                                     f"{scores['raw_revenue_growth']:.1%}" if scores['raw_revenue_growth'] else "N/A",
                                     f"{scores['revenue_growth_pct']:.0f}th %ile")
                            st.metric("Earnings Growth",
                                     f"{scores['raw_earnings_growth']:.1%}" if scores['raw_earnings_growth'] else "N/A",
                                     f"{scores['earnings_growth_pct']:.0f}th %ile")
                        
                        with col3:
                            st.markdown("** Value**")
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
                            st.markdown("** Safety**")
                            st.metric("Debt/Equity",
                                     f"{scores['raw_debt_equity']:.1f}" if scores['raw_debt_equity'] else "N/A",
                                     f"{scores['debt_equity_pct']:.0f}th %ile")
                            st.metric("Current Ratio",
                                     f"{scores['raw_current_ratio']:.2f}" if scores['raw_current_ratio'] else "N/A",
                                     f"{scores['current_ratio_pct']:.0f}th %ile")
                        
                        st.markdown("---")
                        st.caption(f"Compared to {scores['sector']} sector peers from S&P 500 ({benchmarks.data['metadata']['total_stocks']} stocks)")

st.markdown("---")
