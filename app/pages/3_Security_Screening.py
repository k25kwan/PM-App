"""
Security Screening
Filter universe based on user preferences (sectors, geography)
"""

import streamlit as st
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.utils_db import get_conn

st.set_page_config(page_title="Security Screening", layout="wide")

st.title("Security Universe Screening")
st.markdown("Define filters to narrow down your investable universe")

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

# Load existing preferences
existing_prefs = load_screening_prefs(user_id)

if 'screening_prefs' not in st.session_state:
    st.session_state.screening_prefs = existing_prefs.copy()

st.markdown("---")

# Sector Exclusions
st.subheader("Sector Exclusions")
st.markdown("Select sectors you want to EXCLUDE from your universe")

all_sectors = ["Technology", "Financials", "Healthcare", "Energy", "Utilities", 
               "Real Estate", "Consumer", "Industrial"]

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
    "Which geographic markets do you want to invest in?",
    options=["US only", "Canada only", "North America", "Global", "Emerging markets"],
    index=["US only", "Canada only", "North America", "Global", "Emerging markets"].index(st.session_state.screening_prefs.get(11, "North America")) if st.session_state.screening_prefs.get(11) in ["US only", "Canada only", "North America", "Global", "Emerging markets"] else 2,
    key="geography"
)
st.session_state.screening_prefs[11] = geography

st.markdown("---")

# Save Button
if st.button("Apply Filters and Generate Universe", type="primary"):
    if save_screening_pref(user_id, 10, "Sector exclusions", st.session_state.screening_prefs[10]):
        if save_screening_pref(user_id, 11, "Geographic preference", st.session_state.screening_prefs[11]):
            st.success("Screening preferences saved!")
            st.session_state.universe_generated = True

st.markdown("---")

# Display Filtered Universe
if st.session_state.get('universe_generated') or len(st.session_state.screening_prefs) >= 2:
    st.subheader("Your Filtered Investment Universe")
    
    # Get sector exclusions and geography
    excluded = st.session_state.screening_prefs.get(10, "").split(",")
    excluded = [s.strip() for s in excluded if s.strip()]
    geo = st.session_state.screening_prefs.get(11, "North America")
    
    st.markdown(f"**Geography:** {geo}")
    st.markdown(f"**Excluded Sectors:** {', '.join(excluded) if excluded else 'None'}")
    
    # Sample universe data (in production, this would query master_universe table)
    
    # ETFs Tab
    st.markdown("### Exchange-Traded Funds (ETFs)")
    etfs = []
    
    if "Technology" not in excluded:
        etfs.append(("XLK", "Technology Select Sector SPDR", "US", "Technology"))
        etfs.append(("QQQ", "Invesco QQQ Trust", "US", "Technology"))
    
    if "Financials" not in excluded:
        etfs.append(("XLF", "Financial Select Sector SPDR", "US", "Financials"))
        if geo in ["Canada only", "North America"]:
            etfs.append(("XFN.TO", "iShares S&P/TSX Financials", "Canada", "Financials"))
    
    if "Healthcare" not in excluded:
        etfs.append(("XLV", "Health Care Select Sector SPDR", "US", "Healthcare"))
    
    if "Energy" not in excluded:
        etfs.append(("XLE", "Energy Select Sector SPDR", "US", "Energy"))
    
    # Broad market ETFs
    if geo == "US only":
        etfs.append(("SPY", "SPDR S&P 500 ETF", "US", "Broad Market"))
        etfs.append(("IWM", "iShares Russell 2000", "US", "Broad Market"))
    elif geo in ["Canada only", "North America"]:
        etfs.append(("XIU.TO", "iShares S&P/TSX 60", "Canada", "Broad Market"))
        etfs.append(("VCN.TO", "Vanguard FTSE Canada", "Canada", "Broad Market"))
    
    if etfs:
        st.table({
            "Ticker": [e[0] for e in etfs],
            "Name": [e[1] for e in etfs],
            "Geography": [e[2] for e in etfs],
            "Category": [e[3] for e in etfs]
        })
    else:
        st.info("No ETFs match your criteria")
    
    # Equities Tab
    st.markdown("### Individual Equities")
    equities = []
    
    if "Technology" not in excluded:
        if geo in ["US only", "North America", "Global"]:
            equities.extend([
                ("AAPL", "Apple Inc.", "US", "Technology"),
                ("MSFT", "Microsoft Corp.", "US", "Technology"),
                ("NVDA", "NVIDIA Corp.", "US", "Technology")
            ])
        if geo in ["Canada only", "North America"]:
            equities.append(("SHOP.TO", "Shopify Inc.", "Canada", "Technology"))
    
    if "Financials" not in excluded:
        if geo in ["US only", "North America", "Global"]:
            equities.extend([
                ("JPM", "JPMorgan Chase", "US", "Financials"),
                ("BAC", "Bank of America", "US", "Financials")
            ])
        if geo in ["Canada only", "North America"]:
            equities.extend([
                ("TD.TO", "Toronto-Dominion Bank", "Canada", "Financials"),
                ("RY.TO", "Royal Bank of Canada", "Canada", "Financials"),
                ("BNS.TO", "Bank of Nova Scotia", "Canada", "Financials")
            ])
    
    if "Healthcare" not in excluded and geo in ["US only", "North America", "Global"]:
        equities.extend([
            ("JNJ", "Johnson & Johnson", "US", "Healthcare"),
            ("UNH", "UnitedHealth Group", "US", "Healthcare")
        ])
    
    if "Energy" not in excluded:
        if geo in ["US only", "North America", "Global"]:
            equities.append(("XOM", "Exxon Mobil", "US", "Energy"))
        if geo in ["Canada only", "North America"]:
            equities.extend([
                ("CNQ.TO", "Canadian Natural Resources", "Canada", "Energy"),
                ("SU.TO", "Suncor Energy", "Canada", "Energy")
            ])
    
    if equities:
        st.table({
            "Ticker": [e[0] for e in equities],
            "Name": [e[1] for e in equities],
            "Geography": [e[2] for e in equities],
            "Sector": [e[3] for e in equities]
        })
    else:
        st.info("No equities match your criteria")
    
    # Fixed Income Tab
    st.markdown("### Fixed Income")
    fixed_income = []
    
    if geo in ["US only", "North America", "Global"]:
        fixed_income.extend([
            ("AGG", "iShares Core US Aggregate Bond", "US", "Government Bonds"),
            ("LQD", "iShares Investment Grade Corp", "US", "Investment Grade Corp"),
            ("HYG", "iShares High Yield Corp", "US", "High Yield")
        ])
    
    if geo in ["Canada only", "North America"]:
        fixed_income.extend([
            ("XBB.TO", "iShares Core Canadian Bond", "Canada", "Government Bonds"),
            ("XCB.TO", "iShares Canadian Corporate Bond", "Canada", "Investment Grade Corp")
        ])
    
    if fixed_income:
        st.table({
            "Ticker": [f[0] for f in fixed_income],
            "Name": [f[1] for f in fixed_income],
            "Geography": [f[2] for f in fixed_income],
            "Type": [f[3] for f in fixed_income]
        })
    else:
        st.info("No fixed income securities match your criteria")
    
    st.markdown("---")
    st.info("**Next Step:** Use the Portfolio Dashboard to view your current holdings and risk metrics, or go to Trade Entry to buy/sell securities from this universe.")
else:
    st.info("Complete the screening questions above and click 'Apply Filters' to see your filtered universe.")
