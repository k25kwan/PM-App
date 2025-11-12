"""
Security Screening  
Filter universe using real yfinance data based on user preferences
"""

import streamlit as st
import sys
from pathlib import Path
import yfinance as yf
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.utils_db import get_conn

st.set_page_config(page_title="Security Screening", layout="wide")

st.title("Security Universe Screening")
st.markdown("Filter investable securities using real market data from Yahoo Finance")

# Get user_id from session
user_id = st.session_state.get('user_id', 1)

def load_screening_prefs(user_id):
    """Load user's security screening preferences"""
    prefs = {}
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            # Question IDs 10+ are for screening
            cursor.execute("""
                SELECT question_id, response 
                FROM ips_responses 
                WHERE user_id = ? AND question_id >= 10
            """, (user_id,))
            
            for row in cursor.fetchall():
                prefs[row[0]] = row[1]
    except Exception as e:
        st.error(f"Error loading preferences: {e}")
    
    return prefs

def save_screening_pref(user_id, question_id, question_text, response):
    """Save screening preference"""
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            cursor.execute("""
                SELECT id FROM ips_responses 
                WHERE user_id = ? AND question_id = ?
            """, (user_id, question_id))
            
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE ips_responses 
                    SET response = ?, question_text = ?, updated_at = SYSDATETIME()
                    WHERE user_id = ? AND question_id = ?
                """, (response, question_text, user_id, question_id))
            else:
                cursor.execute("""
                    INSERT INTO ips_responses (user_id, question_id, question_text, response)
                    VALUES (?, ?, ?, ?)
                """, (user_id, question_id, question_text, response))
            
            cn.commit()
        return True
    except Exception as e:
        st.error(f"Error saving preference: {e}")
        return False

# Define base universe of tickers to screen
# This could be expanded or pulled from a database
BASE_UNIVERSE = {
    # Major ETFs by sector/asset class
    "ETF": [
        "SPY",    # S&P 500
        "QQQ",    # Nasdaq 100 (Tech-heavy)
        "IWM",    # Russell 2000 Small Cap
        "XLF",    # Financials
        "XLE",    # Energy
        "XLV",    # Healthcare
        "XLK",    # Technology
        "XLU",    # Utilities
        "XLI",    # Industrials
        "XLY",    # Consumer Discretionary
        "XLP",    # Consumer Staples
        "XLRE",   # Real Estate
        "AGG",    # Aggregate Bonds
        "LQD",    # Investment Grade Corp Bonds
        "HYG",    # High Yield Bonds
        "TLT",    # Long-term Treasury
    ],
    "Canada ETF": [
        "XIU.TO",   # S&P/TSX 60
        "XBB.TO",   # Canadian Aggregate Bond
        "XIC.TO",   # TSX Composite
        "ZCN.TO",   # Canadian Equity
    ],
    # Major US stocks by sector
    "US Tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
    "US Financials": ["JPM", "BAC", "WFC", "GS", "MS", "C"],
    "US Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "LLY"],
    "US Energy": ["XOM", "CVX", "COP", "SLB"],
    "US Utilities": ["NEE", "DUK", "SO", "D"],
    "US Consumer": ["WMT", "PG", "KO", "PEP", "COST"],
    "US Industrial": ["BA", "CAT", "GE", "HON", "UNP"],
    # Major Canadian stocks
    "Canada Financials": ["TD.TO", "RY.TO", "BNS.TO", "BMO.TO", "CM.TO"],
    "Canada Energy": ["CNQ.TO", "SU.TO", "ENB.TO", "TRP.TO"],
    "Canada Materials": ["ABX.TO", "SHOP.TO", "FM.TO"],
}

def get_ticker_info(ticker, include_fundamentals=False):
    """Fetch ticker info from yfinance"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        base_info = {
            'ticker': ticker,
            'name': info.get('longName', ticker),
            'sector': info.get('sector', 'Unknown'),
            'industry': info.get('industry', 'Unknown'),
            'market_cap': info.get('marketCap', 0),
            'country': info.get('country', 'Unknown'),
            'price': info.get('currentPrice', info.get('regularMarketPrice', 0))
        }
        
        if include_fundamentals:
            # Add fundamental metrics
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

# Load existing preferences
existing_prefs = load_screening_prefs(user_id)

if 'screening_prefs' not in st.session_state:
    st.session_state.screening_prefs = existing_prefs.copy()

st.markdown("---")

# Sector Exclusions
st.subheader("Sector Exclusions")
st.markdown("Select sectors you want to EXCLUDE from your universe")

all_sectors = ["Technology", "Financial Services", "Financials", "Healthcare", "Energy", 
               "Utilities", "Real Estate", "Consumer Cyclical", "Consumer Defensive",
               "Industrials", "Communication Services", "Basic Materials"]

existing_exclusions = st.session_state.screening_prefs.get(10, "").split(",") if st.session_state.screening_prefs.get(10) else []
excluded_sectors = st.multiselect(
    "Excluded Sectors",
    options=all_sectors,
    default=[s.strip() for s in existing_exclusions if s.strip() in all_sectors],
    key="excluded_sectors"
)
st.session_state.screening_prefs[10] = ",".join(excluded_sectors)

st.markdown("---")

# Geographic Preference
st.subheader("Geographic Preference")
geography = st.radio(
    "Select your geographic preference",
    options=["US only", "Canada only", "North America", "Global"],
    index=["US only", "Canada only", "North America", "Global"].index(
        st.session_state.screening_prefs.get(11, "North America")
    ) if st.session_state.screening_prefs.get(11) in ["US only", "Canada only", "North America", "Global"] else 2,
    key="geography"
)
st.session_state.screening_prefs[11] = geography

st.markdown("---")

# Fundamental Metrics Selection
st.subheader("Fundamental Metrics to Display")
st.markdown("Select which fundamental metrics you want to see in the filtered universe")

FUNDAMENTAL_METRICS = {
    "P/E Ratio": "pe_ratio",
    "P/B Ratio": "pb_ratio", 
    "Dividend Yield": "dividend_yield",
    "Profit Margin": "profit_margin",
    "Revenue Growth": "revenue_growth",
    "ROE": "roe",
    "Debt/Equity": "debt_to_equity",
    "EV/EBITDA": "ev_ebitda"
}

existing_metrics = st.session_state.screening_prefs.get(12, "P/E Ratio,Dividend Yield,Profit Margin").split(",") if st.session_state.screening_prefs.get(12) else ["P/E Ratio", "Dividend Yield", "Profit Margin"]
selected_metrics = st.multiselect(
    "Select Fundamental Metrics",
    options=list(FUNDAMENTAL_METRICS.keys()),
    default=[m.strip() for m in existing_metrics if m.strip() in FUNDAMENTAL_METRICS],
    key="selected_fundamentals",
    help="Choose which fundamental metrics to display for each security"
)
st.session_state.screening_prefs[12] = ",".join(selected_metrics)

st.markdown("---")

# Save preferences
if st.button("Save Screening Preferences", type="primary"):
    success = True
    if save_screening_pref(user_id, 10, "Sector exclusions", st.session_state.screening_prefs[10]):
        pass
    else:
        success = False
    
    if save_screening_pref(user_id, 11, "Geographic preference", st.session_state.screening_prefs[11]):
        pass
    else:
        success = False
    
    if save_screening_pref(user_id, 12, "Fundamental metrics", st.session_state.screening_prefs[12]):
        pass
    else:
        success = False
    
    if success:
        st.success("Preferences saved successfully!")
    else:
        st.warning("Some preferences failed to save")

st.markdown("---")

# Filter and display universe
st.subheader("Filtered Universe")

if st.button("Apply Filters and Screen Securities", type="primary"):
    with st.spinner("Fetching data from Yahoo Finance..."):
        # Build ticker list based on geography
        tickers_to_screen = []
        
        if geography == "US only":
            for category, ticker_list in BASE_UNIVERSE.items():
                if "Canada" not in category:
                    tickers_to_screen.extend(ticker_list)
        elif geography == "Canada only":
            for category, ticker_list in BASE_UNIVERSE.items():
                if "Canada" in category:
                    tickers_to_screen.extend(ticker_list)
        else:  # North America or Global
            for category, ticker_list in BASE_UNIVERSE.items():
                tickers_to_screen.extend(ticker_list)
        
        # Determine if we need to fetch fundamentals
        include_fundamentals = len(selected_metrics) > 0
        
        # Fetch ticker info
        screened_securities = []
        progress_bar = st.progress(0)
        
        for i, ticker in enumerate(tickers_to_screen):
            info = get_ticker_info(ticker, include_fundamentals=include_fundamentals)
            
            # Apply sector filter
            if excluded_sectors and info['sector'] in excluded_sectors:
                continue
            
            screened_securities.append(info)
            progress_bar.progress((i + 1) / len(tickers_to_screen))
        
        progress_bar.empty()
        
        # Display results
        if screened_securities:
            df = pd.DataFrame(screened_securities)
            
            # Format market cap
            df['market_cap_formatted'] = df['market_cap'].apply(
                lambda x: f"${x/1e9:.2f}B" if x > 0 else "N/A"
            )
            
            # Format price
            df['price_formatted'] = df['price'].apply(
                lambda x: f"${x:.2f}" if x > 0 else "N/A"
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
            
            # Build display columns
            display_columns = ['ticker', 'name', 'sector', 'industry', 'country', 'market_cap_formatted', 'price_formatted']
            column_names = ['Ticker', 'Name', 'Sector', 'Industry', 'Country', 'Market Cap', 'Price']
            
            # Add selected fundamental metrics
            for metric_name in selected_metrics:
                metric_key = FUNDAMENTAL_METRICS[metric_name]
                formatted_key = f"{metric_key}_formatted"
                if formatted_key in df.columns:
                    display_columns.append(formatted_key)
                    column_names.append(metric_name)
            
            # Display table
            display_df = df[display_columns]
            display_df.columns = column_names
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            st.success(f"Found {len(screened_securities)} securities matching your criteria")
            
            # Summary stats
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Securities", len(screened_securities))
            
            with col2:
                unique_sectors = df['sector'].nunique()
                st.metric("Unique Sectors", unique_sectors)
            
            with col3:
                unique_countries = df['country'].nunique()
                st.metric("Countries", unique_countries)
            
            # Sector breakdown
            st.markdown("### Sector Breakdown")
            sector_counts = df['sector'].value_counts()
            st.bar_chart(sector_counts)
        
        else:
            st.warning("No securities match your filters. Try adjusting your exclusions.")

st.markdown("---")

st.info("""
**Note**: This screener uses Yahoo Finance data. The base universe includes:
- Major US/Canadian ETFs (sector, broad market, fixed income)
- Large-cap US stocks across all sectors
- Major Canadian stocks (banks, energy, materials)

For a complete institutional-grade screener, integrate with Bloomberg or FactSet APIs.
""")
