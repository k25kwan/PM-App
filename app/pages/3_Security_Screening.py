"""
Security Screening  
Filter universe using real yfinance data based on user preferences
Uses comprehensive ticker universe from external sources
Filters out "bad apples" using fundamental quality screens
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

st.set_page_config(page_title="Find Investments", layout="wide")

st.title("🔍 Find Great Investments for Your Portfolio")
st.markdown("""
**What does this tool do?** It helps you discover quality stocks and ETFs that match your interests and portfolio needs.

**How it works:** 
1. Choose what type of investment (stocks, ETFs, bonds)
2. Apply optional filters to narrow down the universe
3. Select sectors you're interested in
4. See all matching securities with their fundamentals
""")

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

def load_user_portfolios(user_id):
    """Load all portfolios for a user"""
    try:
        with get_conn() as cn:
            query = """
                SELECT id, portfolio_name
                FROM portfolios
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC
            """
            df = pd.read_sql(query, cn, params=[user_id])
            return df
    except Exception as e:
        st.error(f"Error loading portfolios: {e}")
        return pd.DataFrame()

def load_portfolio_holdings(portfolio_id):
    """Load current portfolio holdings"""
    try:
        with get_conn() as cn:
            query = """
                SELECT ticker, name, sector, market_value
                FROM f_positions
                WHERE portfolio_id = ?
                AND asof_date = (SELECT MAX(asof_date) FROM f_positions WHERE portfolio_id = ?)
            """
            # Convert to int to avoid numpy.int64 parameter type error
            portfolio_id_int = int(portfolio_id)
            df = pd.read_sql(query, cn, params=[portfolio_id_int, portfolio_id_int])
            return df
    except Exception as e:
        st.error(f"Error loading holdings: {e}")
        return pd.DataFrame()

def calculate_fundamental_score(row, metric_weights):
    """
    Calculate fundamental score based on selected metrics and weights
    Lower P/E, P/B, Debt/Equity = better
    Higher Dividend Yield, ROE, Profit Margin, Revenue Growth = better
    
    Returns None for ETFs (they should not be scored on fundamentals)
    """
    # Skip fundamental scoring for ETFs - they don't have company fundamentals
    asset_type = row.get('asset_type', 'Unknown')
    if asset_type == 'ETF':
        return None  # Will be handled separately
    
    score = 0
    count = 0
    
    # P/E Ratio (lower is better, normalize to 0-100 scale)
    if pd.notna(row.get('pe_ratio')) and 'P/E Ratio' in metric_weights:
        pe = row['pe_ratio']
        if 0 < pe < 50:  # Reasonable range
            # Score: 100 for PE=5, 0 for PE=50
            pe_score = max(0, min(100, 100 - (pe - 5) * 100 / 45))
            score += pe_score * metric_weights['P/E Ratio']
            count += metric_weights['P/E Ratio']
    
    # P/B Ratio (lower is better)
    if pd.notna(row.get('pb_ratio')) and 'P/B Ratio' in metric_weights:
        pb = row['pb_ratio']
        if 0 < pb < 10:  # Reasonable range
            # Adjusted scoring: 100 for PB=1.0, decreasing on either side
            # This avoids giving financial companies (PB<1) artificially high scores
            # Many banks trade at 0.8-1.2 PB which is normal, not "cheap"
            if pb <= 1.5:
                # For PB <= 1.5: Score peaks at PB=1.0
                pb_score = max(0, 100 - abs(pb - 1.0) * 40)  # -40 points per unit away from 1.0
            else:
                # For PB > 1.5: Lower is better
                pb_score = max(0, min(100, 100 - (pb - 1.5) * 15))  # -15 points per unit above 1.5
            score += pb_score * metric_weights['P/B Ratio']
            count += metric_weights['P/B Ratio']
    
    # Dividend Yield (higher is better)
    if pd.notna(row.get('dividend_yield')) and 'Dividend Yield' in metric_weights:
        div_yield = row['dividend_yield'] * 100  # Convert to percentage
        # Score: 0 for 0%, 100 for 5%+
        div_score = min(100, div_yield * 20)
        score += div_score * metric_weights['Dividend Yield']
        count += metric_weights['Dividend Yield']
    
    # ROE (higher is better)
    if pd.notna(row.get('roe')) and 'ROE' in metric_weights:
        roe = row['roe'] * 100  # Convert to percentage
        # Score: 0 for 0%, 100 for 25%+
        roe_score = min(100, max(0, roe * 4))
        score += roe_score * metric_weights['ROE']
        count += metric_weights['ROE']
    
    # Profit Margin (higher is better)
    if pd.notna(row.get('profit_margin')) and 'Profit Margin' in metric_weights:
        margin = row['profit_margin'] * 100
        # Score: 0 for 0%, 100 for 20%+
        margin_score = min(100, max(0, margin * 5))
        score += margin_score * metric_weights['Profit Margin']
        count += metric_weights['Profit Margin']
    
    # Revenue Growth (higher is better)
    if pd.notna(row.get('revenue_growth')) and 'Revenue Growth' in metric_weights:
        growth = row['revenue_growth'] * 100
        # Score: 50 for 0%, 100 for 20%+, 0 for -20%
        growth_score = min(100, max(0, 50 + growth * 2.5))
        score += growth_score * metric_weights['Revenue Growth']
        count += metric_weights['Revenue Growth']
    
    # Debt/Equity (lower is better)
    if pd.notna(row.get('debt_to_equity')) and 'Debt/Equity' in metric_weights:
        de = row['debt_to_equity']
        if de >= 0:  # Only positive debt ratios
            # Score: 100 for DE=0, 0 for DE=200
            de_score = max(0, min(100, 100 - de / 2))
            score += de_score * metric_weights['Debt/Equity']
            count += metric_weights['Debt/Equity']
    
    # EV/EBITDA (lower is better)
    if pd.notna(row.get('ev_ebitda')) and 'EV/EBITDA' in metric_weights:
        ev_ebitda = row['ev_ebitda']
        if 0 < ev_ebitda < 30:
            # Score: 100 for EV/EBITDA=5, 0 for EV/EBITDA=30
            ev_score = max(0, min(100, 100 - (ev_ebitda - 5) * 100 / 25))
            score += ev_score * metric_weights['EV/EBITDA']
            count += metric_weights['EV/EBITDA']
    
    return score / count if count > 0 else 0

def calculate_diversification_benefit(ticker, sector, portfolio_holdings):
    """
    Calculate diversification benefit of adding this security to portfolio
    Higher score = better diversification
    
    Returns:
    - Score from 0-100 based on sector diversity, ticker uniqueness, and HHI reduction
    - Returns None if no portfolio is selected (will be filtered out in combined score)
    """
    if portfolio_holdings.empty:
        return None  # Return None instead of 50 - signals "no portfolio selected"
    
    total_mv = portfolio_holdings['market_value'].sum()
    if total_mv == 0:
        return None
    
    score = 0
    
    # 1. Sector Diversification (40 points)
    # Check if sector is underrepresented in portfolio
    sector_mv = portfolio_holdings[portfolio_holdings['sector'] == sector]['market_value'].sum()
    sector_weight = sector_mv / total_mv
    
    # Conservative scoring with steep diminishing returns
    # 40 points if sector has 0% weight (completely new exposure)
    # 30 points at 5% weight (still underrepresented)
    # 20 points at 10% weight (moving toward neutral)
    # 10 points at 15% weight (neutral)
    # 0 points at 20%+ weight (already well-represented)
    if sector_weight == 0:
        sector_score = 40
    elif sector_weight < 0.20:
        # Steep curve: penalize even small existing positions more
        # score = 40 * (1 - (weight/0.20)^0.5)
        # This gives: 0% → 40, 5% → 31, 10% → 23, 15% → 15, 20% → 0
        sector_score = 40 * (1 - (sector_weight / 0.20) ** 0.5)
    else:
        sector_score = 0
    score += sector_score
    
    # 2. Ticker Uniqueness (20 points)
    # Penalize if ticker already exists in portfolio
    if ticker in portfolio_holdings['ticker'].values:
        ticker_score = 0  # Already own it - no diversification benefit
    else:
        ticker_score = 20  # New ticker - adds diversification
    score += ticker_score
    
    # 3. Concentration Benefit (40 points) - MOST IMPORTANT
    # Calculate HHI impact of adding this security at 10% weight
    n_holdings = len(portfolio_holdings)
    
    # Current portfolio weights
    current_weights = portfolio_holdings['market_value'] / total_mv
    current_hhi = (current_weights ** 2).sum()
    
    # Simulate adding new holding with 10% weight
    new_holding_weight = 0.10
    
    # Scale down existing holdings proportionally
    adjusted_existing_weights = current_weights * (1 - new_holding_weight)
    
    # New HHI with the new holding added
    new_hhi = (adjusted_existing_weights ** 2).sum() + new_holding_weight ** 2
    
    # HHI reduction in basis points
    hhi_reduction = (current_hhi - new_hhi) * 10000
    
    # MUCH more conservative scoring - require SIGNIFICANT HHI reduction
    # The issue: for concentrated portfolios, ANY addition gives big HHI reduction
    # Solution: Scale by portfolio concentration level
    
    # Expected HHI for equal-weight portfolio of this size
    equal_weight_hhi = 10000 / n_holdings  # in bps
    concentration_ratio = current_hhi / equal_weight_hhi  # >1 means concentrated
    
    # Adjust HHI benefit based on how concentrated the portfolio is
    # If portfolio is 2x as concentrated as equal-weight, discount the benefit by 50%
    if concentration_ratio > 1:
        adjusted_hhi_reduction = hhi_reduction / concentration_ratio
    else:
        adjusted_hhi_reduction = hhi_reduction
    
    # Now score based on adjusted HHI reduction
    # Need 200+ bps of ADJUSTED reduction for full 40 points
    concentration_score = min(40, adjusted_hhi_reduction * 0.2)
    
    score += concentration_score
    
    # DEBUG: Print breakdown for first few calculations
    import streamlit as st
    if not hasattr(calculate_diversification_benefit, '_debug_count'):
        calculate_diversification_benefit._debug_count = 0
    
    if calculate_diversification_benefit._debug_count < 3:
        equal_weight_hhi = 10000 / n_holdings
        concentration_ratio = current_hhi / equal_weight_hhi
        adjusted_hhi_reduction = hhi_reduction / concentration_ratio if concentration_ratio > 1 else hhi_reduction
        
        st.write(f"🔍 DEBUG {ticker} ({sector}):")
        st.write(f"  - Portfolio: {n_holdings} holdings, Total MV: ${total_mv:,.0f}")
        st.write(f"  - Sector weight: {sector_weight*100:.1f}% → Sector score: {sector_score:.1f}/40")
        st.write(f"  - Ticker score: {ticker_score:.1f}/20")
        st.write(f"  - Current HHI: {current_hhi*10000:.1f} bps (equal-weight would be {equal_weight_hhi:.1f} bps)")
        st.write(f"  - Concentration ratio: {concentration_ratio:.2f}x")
        st.write(f"  - Raw HHI reduction: {hhi_reduction:.1f} bps → Adjusted: {adjusted_hhi_reduction:.1f} bps")
        st.write(f"  - Concentration score: {concentration_score:.1f}/40")
        st.write(f"  - **TOTAL: {score:.1f}/100**")
        calculate_diversification_benefit._debug_count += 1
    
    return round(score, 1)  # Round to 1 decimal for cleaner display

# Investment Sleeves - Pre-curated, investable-grade securities
# Each sleeve has quality filters built-in (market cap, liquidity, financial health)
# Users select ONE sleeve at a time for focused screening
INVESTMENT_SLEEVES = {
    # US Equity Sleeves
    "US Large Cap Technology": {
        "description": "Mega-cap tech companies (>$100B market cap, strong balance sheets)",
        "tickers": ["AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA", "ORCL", "AVGO", 
                   "ADBE", "CRM", "CSCO", "INTC", "AMD", "QCOM", "TXN", "INTU", "NOW", "AMAT"],
        "min_market_cap": 100_000_000_000,  # $100B
        "max_debt_equity": 100,  # Low leverage for tech
    },
    
    "US Large Cap Financials": {
        "description": "Major banks and insurers (>$50B market cap, regulated institutions)",
        "tickers": ["JPM", "BAC", "WFC", "C", "GS", "MS", "BRK.B", "V", "MA", "AXP", 
                   "SCHW", "USB", "PNC", "TFC", "BK", "COF", "AIG", "MET", "PRU", "AFL"],
        "min_market_cap": 50_000_000_000,  # $50B
        "max_debt_equity": 500,  # Higher for banks (different business model)
    },
    
    "US Large Cap Healthcare": {
        "description": "Pharma, biotech, and medical devices (>$50B, established players)",
        "tickers": ["JNJ", "UNH", "LLY", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR", "AMGN",
                   "BMY", "CVS", "CI", "ELV", "GILD", "VRTX", "REGN", "ISRG", "SYK", "BSX"],
        "min_market_cap": 50_000_000_000,
        "max_debt_equity": 150,
    },
    
    "US Large Cap Consumer": {
        "description": "Consumer staples & discretionary (>$30B, brand leaders)",
        "tickers": ["WMT", "PG", "KO", "PEP", "COST", "HD", "MCD", "NKE", "SBUX", "TGT",
                   "LOW", "CL", "KMB", "GIS", "K", "HSY", "MDLZ", "PM", "MO", "STZ"],
        "min_market_cap": 30_000_000_000,
        "max_debt_equity": 200,
    },
    
    "US Large Cap Energy": {
        "description": "Oil & gas majors (>$30B, integrated or upstream leaders)",
        "tickers": ["XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "VLO", "OXY", "PXD",
                   "HAL", "BKR", "KMI", "WMB", "OKE", "HES", "DVN", "FANG"],
        "min_market_cap": 30_000_000_000,
        "max_debt_equity": 150,
    },
    
    "US Large Cap Industrials": {
        "description": "Manufacturing, aerospace, logistics (>$30B, blue chips)",
        "tickers": ["BA", "CAT", "GE", "HON", "UNP", "UPS", "RTX", "LMT", "DE", "MMM",
                   "ETN", "ITW", "EMR", "CSX", "NSC", "FDX", "NOC", "GD", "LHX", "TXT"],
        "min_market_cap": 30_000_000_000,
        "max_debt_equity": 200,
    },
    
    # Canadian Equity Sleeves
    "Canadian Banks": {
        "description": "Big 5 banks + major insurers (TSX blue chips)",
        "tickers": ["RY.TO", "TD.TO", "BNS.TO", "BMO.TO", "CM.TO", "MFC.TO", "SLF.TO", "GWO.TO", "POW.TO"],
        "min_market_cap": 20_000_000_000,  # $20B CAD
        "max_debt_equity": 500,  # Banks have higher leverage
    },
    
    "Canadian Energy": {
        "description": "Energy producers, pipelines, services (TSX leaders)",
        "tickers": ["CNQ.TO", "SU.TO", "ENB.TO", "TRP.TO", "CVE.TO", "IMO.TO", "PPL.TO", 
                   "WCP.TO", "ARX.TO", "TOU.TO", "SDE.TO", "KEL.TO"],
        "min_market_cap": 5_000_000_000,  # $5B CAD
        "max_debt_equity": 150,
    },
    
    "Canadian Materials & Resources": {
        "description": "Mining, metals, fertilizers (commodity producers)",
        "tickers": ["ABX.TO", "NTR.TO", "SHOP.TO", "FM.TO", "WPM.TO", "K.TO", "CCO.TO", 
                   "FNV.TO", "AEM.TO", "WDO.TO", "HBM.TO", "TKO.TO"],
        "min_market_cap": 5_000_000_000,
        "max_debt_equity": 200,
    },
    
    # ETF Sleeves
    "US Equity ETFs": {
        "description": "Broad market and sector ETFs (US equity exposure)",
        "tickers": ["SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "XLF", "XLE", "XLV", "XLK",
                   "XLU", "XLI", "XLY", "XLP", "XLRE", "XLB", "XLC"],
        "min_market_cap": 0,  # ETFs don't have market cap filter
        "max_debt_equity": 9999,  # Not applicable
    },
    
    "Fixed Income ETFs": {
        "description": "Bond ETFs across duration and credit quality",
        "tickers": ["AGG", "BND", "LQD", "HYG", "JNK", "TLT", "IEF", "SHY", "TIP", "MUB",
                   "EMB", "VCIT", "VCLT", "BNDX", "VWOB"],
        "min_market_cap": 0,
        "max_debt_equity": 9999,
    },
    
    "Canadian ETFs": {
        "description": "Canadian equity and fixed income ETFs",
        "tickers": ["XIU.TO", "XIC.TO", "VCN.TO", "ZCN.TO", "XBB.TO", "VAB.TO", "ZAG.TO",
                   "XEG.TO", "XFN.TO", "XIT.TO", "XRE.TO", "ZEB.TO", "ZEO.TO"],
        "min_market_cap": 0,
        "max_debt_equity": 9999,
    },
    
    "International ETFs": {
        "description": "Developed and emerging market ETFs",
        "tickers": ["EFA", "VEA", "IEFA", "EEM", "VWO", "IEMG", "FXI", "EWJ", "EWG", "EWU",
                   "INDA", "EWY", "EWZ", "EWT", "MCHI"],
        "min_market_cap": 0,
        "max_debt_equity": 9999,
    },
}

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


# Load existing preferences
existing_prefs = load_screening_prefs(user_id)

if 'screening_prefs' not in st.session_state:
    st.session_state.screening_prefs = existing_prefs.copy()

st.markdown("---")

# STEP 1: Asset Class Selection
st.subheader("📊 Step 1: What Type of Investment?")
st.markdown("Choose the asset class you want to screen:")

asset_class = st.radio(
    "Asset Class:",
    options=["Equities (Stocks)", "ETFs (Exchange-Traded Funds)", "Bonds", "All"],
    help="Equities = individual companies | ETFs = baskets of securities | Bonds = fixed income"
)

st.markdown("---")

# STEP 2: Optional Quality Filters
st.subheader("⚙️ Step 2: Optional Filters (Reduce Universe Size)")
st.markdown("""
**These filters help narrow down the universe** to make loading faster and focus on quality companies.

⚠️ **Load Time Warning:** Screening takes ~1 second per ticker (yfinance API calls).
- 100 tickers = ~2 minutes
- 500 tickers = ~8 minutes  
- 7,000+ tickers = impractical without filters
""")

col1, col2, col3 = st.columns(3)

with col1:
    enable_market_cap_filter = st.checkbox(
        "Filter by Market Cap (Company Size)",
        value=True,
        help="Recommended: Filters out very small companies that may be illiquid"
    )
    
    if enable_market_cap_filter:
        min_market_cap_billions = st.select_slider(
            "Minimum Market Cap:",
            options=[0.05, 0.1, 0.5, 1, 5, 10, 50, 100],
            value=1,
            format_func=lambda x: f"${x}B",
            help="Lower values = more companies, longer load time. $1B is a good starting point."
        )
        min_market_cap = min_market_cap_billions * 1_000_000_000
    else:
        min_market_cap = 0
        st.warning("⏱️ No market cap filter: Expect very long load times")

with col2:
    exclude_high_debt = st.checkbox(
        "Exclude High Debt Companies",
        value=False,
        help="Filter out companies with Debt/Equity > 100% (excludes banks/financials which naturally have high leverage)"
    )
    
    if exclude_high_debt:
        st.caption("✓ Will exclude companies with Debt/Equity > 100%")
        max_debt_equity = 100
    else:
        max_debt_equity = 9999  # No filter

with col3:
    st.markdown("**Sample Size Limit**")
    enable_sample_limit = st.checkbox(
        "Limit Universe Size",
        value=True,
        help="Randomly sample from full universe to speed up screening"
    )
    
    if enable_sample_limit:
        max_tickers = st.select_slider(
            "Max tickers to screen:",
            options=[50, 100, 200, 500, 1000, 2000],
            value=500,
            help="For testing, use 50-100. For comprehensive screening, use 1000+."
        )
        st.caption(f"Will screen up to {max_tickers} randomly selected tickers")
    else:
        max_tickers = None
        st.warning("⏱️ No limit: May take 30+ minutes for full universe")

st.markdown("---")
st.subheader("💼 Your Portfolio (Optional)")
st.markdown("Select a portfolio to get personalized sector recommendations")

portfolios_df = load_user_portfolios(user_id)
selected_portfolio = None
portfolio_holdings = pd.DataFrame()

if not portfolios_df.empty:
    portfolio_options = ["None"] + portfolios_df['portfolio_name'].tolist()
    selected_portfolio_name = st.selectbox(
        "Select Portfolio:",
        options=portfolio_options,
        key="portfolio_selector"
    )
    
    if selected_portfolio_name != "None":
        selected_portfolio = portfolios_df[portfolios_df['portfolio_name'] == selected_portfolio_name]['id'].iloc[0]
        portfolio_holdings = load_portfolio_holdings(selected_portfolio)
        
        if not portfolio_holdings.empty:
            st.success(f"✓ Loaded '{selected_portfolio_name}' with {len(portfolio_holdings)} holdings")
            with st.expander("View Current Holdings"):
                st.dataframe(portfolio_holdings[['ticker', 'sector', 'market_value']], use_container_width=True, hide_index=True)
        else:
            st.warning(f"Portfolio '{selected_portfolio_name}' has no holdings")
else:
    st.info("💡 Create a portfolio to get personalized sector recommendations")

st.markdown("---")

# STEP 3: Sector Selection (with diversification hints)
st.subheader("🎯 Step 3: Which Sectors Interest You?")
st.markdown("**Select sectors to INCLUDE** in your screening (not exclude):")

# Portfolio analysis for diversification hints
diversification_hints = {}
if not portfolio_holdings.empty:
    total_value = portfolio_holdings['market_value'].sum()
    # Group by actual sector names from portfolio
    sector_weights = portfolio_holdings.groupby('sector')['market_value'].sum() / total_value
    
    # Generate hints for ALL sectors in portfolio
    for sector, weight in sector_weights.items():
        if weight < 0.05:
            diversification_hints[sector] = f"💡 Low exposure ({weight*100:.1f}%) - good diversification opportunity"
        elif weight < 0.15:
            diversification_hints[sector] = f"📊 Moderate exposure ({weight*100:.1f}%)"
        else:
            diversification_hints[sector] = f"✓ Well represented ({weight*100:.1f}%)"

# Standard sector list (matches yfinance sector names)
all_sectors = [
    "Technology",
    "Financial Services",
    "Healthcare",
    "Energy",
    "Utilities",
    "Real Estate",
    "Consumer Cyclical",
    "Consumer Defensive",
    "Industrials",
    "Communication Services",
    "Basic Materials",
    "Unknown"
]

# Show sectors with hints
selected_sectors = st.multiselect(
    "Include these sectors:",
    options=all_sectors,
    default=all_sectors,  # Start with all selected
    help="Select one or more sectors. Deselect to exclude from screening."
)

# Show diversification hints if available
if diversification_hints:
    with st.expander("💡 Diversification Hints Based on Your Portfolio"):
        for sector in all_sectors:
            if sector in diversification_hints:
                st.markdown(f"**{sector}**: {diversification_hints[sector]}")
            elif sector in selected_sectors and not portfolio_holdings.empty:
                # Sector selected but not in portfolio
                st.markdown(f"**{sector}**: 💡 Not in your portfolio (0.0%) - good diversification opportunity")

if not selected_sectors:
    st.warning("⚠️ No sectors selected. Please select at least one sector to screen.")

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Filter by Industry** (optional)")
    filter_by_industry = st.checkbox("Enable industry filter", value=False, key="enable_industry_filter")
    if filter_by_industry:
        industry_filter_text = st.text_input(
            "Industry keywords (comma-separated)",
            placeholder="e.g., Software, Semiconductor, Banking",
            help="Case-insensitive search. Will include securities matching ANY keyword.",
            key="industry_filter"
        )

with col2:
    st.markdown("**Filter by Country** (optional)")
    filter_by_country = st.checkbox("Enable country filter", value=False, key="enable_country_filter")
    if filter_by_country:
        country_filter_text = st.text_input(
            "Country keywords (comma-separated)",
            placeholder="e.g., United States, Canada",
            help="Case-insensitive search. Will include securities matching ANY keyword.",
            key="country_filter"
        )

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

# STEP 3: Sector Selection (with diversification hints)
st.subheader("Step 4: Run the Screening")
st.markdown("""
**Ready to see the results?** Click below to:
1. Fetch live data from Yahoo Finance (30-60 seconds)
2. Apply quality filters (market cap, debt levels)
3. Rank companies by your chosen criteria
4. Show you the top opportunities
""")

if st.button("🔍 Load Universe and Screen", type="primary", use_container_width=True):
    
    if not selected_sectors:
        st.error("❌ Please select at least one sector to screen")
        st.stop()
    
    # Step 1: Load comprehensive ticker universe
    with st.spinner("📥 Loading ticker universe from external sources..."):
        # Map asset class selection to filter
        asset_filter = None
        if asset_class == "Equities (Stocks)":
            asset_filter = "Equity"
        elif asset_class == "ETFs (Exchange-Traded Funds)":
            asset_filter = "ETF"
        # "Bonds" and "All" get no filter (bonds detected via sector later)
        
        universe_df = load_ticker_universe(asset_class=asset_filter, force_refresh=False)
        
        if universe_df.empty:
            st.error("❌ Failed to load ticker universe. Please try again.")
            st.stop()
        
        stats = get_universe_stats()
        if stats:
            with st.expander("📊 Universe Statistics"):
                st.write(f"**Total Securities:** {stats.get('total_securities', 0):,}")
                st.write(f"**Last Updated:** {stats.get('updated_at', 'Unknown')}")
                st.write(f"- NASDAQ Stocks: {stats.get('nasdaq_stocks', 0):,}")
                st.write(f"- NYSE Stocks: {stats.get('nyse_stocks', 0):,}")
                st.write(f"- ETFs: {stats.get('etfs', 0):,}")
                st.write(f"- Canadian Stocks: {stats.get('canadian_stocks', 0):,}")
        
        all_tickers = universe_df['ticker'].tolist()
        
        # Apply sample limit if enabled - prioritize major exchanges and well-known tickers
        if enable_sample_limit and max_tickers and len(all_tickers) > max_tickers:
            st.info(f"📊 Selecting {max_tickers:,} tickers from universe of {len(universe_df):,} (prioritizing major exchanges)...")
            
            # Strategy: Prioritize by exchange (NYSE > NASDAQ > others)
            # NYSE/NASDAQ typically have larger companies than smaller exchanges
            # Also prioritize shorter ticker symbols (usually larger, older companies)
            exchange_priority = {'NYSE': 1, 'NASDAQ': 2, 'NYSE Arca': 3, 'TSX': 4, 'NYSE MKT': 5, 'BATS': 6, 'IEX': 7}
            
            # Add priority scoring
            universe_df['exchange_priority'] = universe_df['exchange'].map(exchange_priority).fillna(99)
            universe_df['ticker_length'] = universe_df['ticker'].str.len()
            
            # Sort by: 1) Exchange priority, 2) Ticker length (shorter = usually larger companies), 3) Alphabetical
            sorted_df = universe_df.sort_values(['exchange_priority', 'ticker_length', 'ticker']).head(max_tickers)
            all_tickers = sorted_df['ticker'].tolist()
            
            exchange_breakdown = sorted_df['exchange'].value_counts()
            st.success(f"✓ Selected {len(all_tickers):,} tickers prioritizing major exchanges: {', '.join([f'{ex} ({ct})' for ex, ct in exchange_breakdown.head(3).items()])}")
        else:
            st.success(f"✓ Loaded {len(all_tickers):,} tickers from universe")
    
    # Step 2: Screen with filters and bad apple elimination
    with st.spinner("🔍 Screening securities and filtering out bad apples..."):
        estimated_time = len(all_tickers) * 0.8 / 60  # ~0.8 seconds per ticker
        st.info(f"📊 Screening {len(all_tickers):,} securities (estimated time: {estimated_time:.1f} minutes)...")
        st.caption(f"Filters: {asset_class} | Market cap ≥ ${min_market_cap/1e9:.1f}B | D/E {'≤ 100%' if exclude_high_debt else 'Any'} | Sectors: {len(selected_sectors)} selected")
        
        # Always fetch fundamentals for quality scoring
        include_fundamentals = True
        
        # Track statistics
        screened_securities = []
        bad_apples = []
        filtered_count = {'market_cap': 0, 'debt': 0, 'asset_class': 0, 'sector': 0, 'bad_apple': 0}
        
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
            
            # Apply sector filter
            sector = info.get('sector', 'Unknown')
            if sector not in selected_sectors:
                filtered_count['sector'] += 1
                continue
            
            # BAD APPLE FILTER - eliminate obvious problems
            is_bad, reason = is_bad_apple(info, asset_class)
            if is_bad:
                filtered_count['bad_apple'] += 1
                bad_apples.append({'ticker': ticker, 'reason': reason})
                continue
            
            # Calculate quality score for ranking
            info['quality_score'] = calculate_quality_score(info)
            
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
            st.write(f"  - Sector not selected: {filtered_count['sector']:,}")
            st.write(f"  - ❌ **Bad apples** (red flags): {filtered_count['bad_apple']:,}")
            st.write(f"**Passed all filters:** {len(screened_securities):,}")
            
            if bad_apples and len(bad_apples) <= 20:
                st.markdown("**Examples of filtered 'bad apples':**")
                for ba in bad_apples[:10]:
                    st.caption(f"• {ba['reason']}")
        
        # Display results
        if screened_securities:
            df = pd.DataFrame(screened_securities)
            
            # Apply industry filter if enabled
            if filter_by_industry and 'industry_filter_text' in locals() and industry_filter_text:
                keywords = [k.strip().lower() for k in industry_filter_text.split(',') if k.strip()]
                if keywords:
                    df = df[df['industry'].str.lower().str.contains('|'.join(keywords), na=False)]
            
            # Apply country filter if enabled
            if filter_by_country and 'country_filter_text' in locals() and country_filter_text:
                keywords = [k.strip().lower() for k in country_filter_text.split(',') if k.strip()]
                if keywords:
                    df = df[df['country'].str.lower().str.contains('|'.join(keywords), na=False)]
            
            if df.empty:
                st.warning("No securities match your post-screening filters. Try adjusting your criteria.")
            else:
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
            
            # Build display columns - include quality score
            display_columns = ['rank', 'ticker', 'name', 'quality_score_formatted', 'asset_type', 'sector', 'market_cap_formatted', 'price_formatted']
            column_names = ['Rank', 'Ticker', 'Name', 'Quality', 'Type', 'Sector', 'Market Cap', 'Price']
            
            # Add selected fundamental metrics
            for metric_name in selected_metrics:
                metric_key = FUNDAMENTAL_METRICS[metric_name]
                formatted_key = f"{metric_key}_formatted"
                if formatted_key in df.columns:
                    display_columns.append(formatted_key)
                    column_names.append(metric_name)
            
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
            # Diversification Debug Info (only show if portfolio selected)
            if not portfolio_holdings.empty:
                with st.expander("Diversification Score Breakdown (Debug)"):
                    st.markdown("**How Diversification Scores are Calculated:**")
                    st.markdown("""
                    - **Sector Score (40 pts max)**: Higher for underrepresented sectors. 40 pts if new sector, declining steeply to 0 at 20% weight.
                    - **Ticker Uniqueness (20 pts)**: 20 pts if new ticker, 0 pts if already owned.
                    - **Concentration Benefit (40 pts)**: Based on HHI reduction adjusted for portfolio concentration. Requires 200+ bps of adjusted reduction for full points.
                    
                    **Key Insight**: If your portfolio is highly concentrated (HHI > equal-weight), the concentration benefit is discounted to avoid over-rewarding additions to poorly diversified portfolios.
                    """)
                    
                    # Show sector weights in current portfolio
                    sector_weights = portfolio_holdings.groupby('sector')['market_value'].sum() / portfolio_holdings['market_value'].sum()
                    sector_df = pd.DataFrame({
                        'Sector': sector_weights.index,
                        'Current Weight': (sector_weights.values * 100).round(1)
                    }).sort_values('Current Weight', ascending=False)
                    
                    # Show portfolio concentration metrics
                    n_holdings = len(portfolio_holdings)
                    current_weights = portfolio_holdings['market_value'] / portfolio_holdings['market_value'].sum()
                    current_hhi = (current_weights ** 2).sum() * 10000
                    equal_weight_hhi = 10000 / n_holdings
                    concentration_ratio = current_hhi / equal_weight_hhi
                    
                    st.markdown(f"**Current Portfolio:** {n_holdings} holdings")
                    st.markdown(f"**HHI:** {current_hhi:.1f} bps (equal-weight would be {equal_weight_hhi:.1f} bps)")
                    st.markdown(f"**Concentration Ratio:** {concentration_ratio:.2f}x ({'concentrated' if concentration_ratio > 1.2 else 'balanced' if concentration_ratio > 0.9 else 'well-diversified'})")
                    
                    st.dataframe(sector_df, hide_index=True, use_container_width=True)
                    
                    # Show sample calculation for top security
                    if len(df) > 0:
                        top_sec = df.iloc[0]
                        st.markdown(f"**Example: {top_sec['ticker']} ({top_sec['sector']})**")
                        
                        # Recalculate for display
                        sector = top_sec['sector']
                        ticker = top_sec['ticker']
                        
                        sector_mv = portfolio_holdings[portfolio_holdings['sector'] == sector]['market_value'].sum()
                        sector_weight = sector_mv / portfolio_holdings['market_value'].sum()
                        
                        if sector_weight == 0:
                            sector_score = 40
                        elif sector_weight < 0.20:
                            sector_score = 40 * (1 - (sector_weight / 0.20) ** 0.5)
                        else:
                            sector_score = 0
                        
                        ticker_score = 0 if ticker in portfolio_holdings['ticker'].values else 20
                        
                        st.markdown(f"""
                        - Sector Weight: {sector_weight*100:.1f}% → Sector Score: {sector_score:.1f}/40
                        - {'Already Owned' if ticker_score == 0 else 'New Ticker'} → Uniqueness Score: {ticker_score:.1f}/20
                        - Total Diversification: {top_sec['diversification_score']:.1f}/100
                        """)
            
            # Top 10 Recommendations
            st.markdown("---")
            st.subheader("Top 10 Recommended Securities")
            
            top_10 = df.head(10)[['rank', 'asset_type', 'ticker', 'name', 'sector', 'combined_score', 'fundamental_score', 'diversification_score']].copy()
            top_10.columns = ['Rank', 'Asset Type', 'Ticker', 'Name', 'Sector', 'Combined Score', 'Fundamental Score', 'Diversification Score']
            top_10['Combined Score'] = top_10['Combined Score'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
            top_10['Fundamental Score'] = top_10['Fundamental Score'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A (ETF)")
            top_10['Diversification Score'] = top_10['Diversification Score'].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "N/A")
            
            st.dataframe(top_10, use_container_width=True, hide_index=True)
            
            # Score distribution
            st.markdown("---")
            st.subheader("Score Distribution")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Combined Score Distribution**")
                st.bar_chart(df['combined_score'].value_counts().sort_index())
            
            with col2:
                st.markdown("**Sector Breakdown**")
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
