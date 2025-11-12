"""
Initial Holdings Input
Option to input existing portfolio holdings or start fresh
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import date

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.utils_db import get_conn

st.set_page_config(page_title="Initial Holdings", layout="wide")

st.title("Initial Portfolio Holdings")

# Get user_id from session
user_id = st.session_state.get('user_id', 1)

st.markdown("---")

# Choice: New or Existing Portfolio
choice = st.radio(
    "Do you have existing holdings to input?",
    options=["Start with empty portfolio", "Input existing holdings"],
    index=0
)

if choice == "Start with empty portfolio":
    st.info("You've chosen to start with an empty portfolio. Proceed to Security Screening to build your portfolio.")
    
    if st.button("Clear any existing holdings and continue"):
        try:
            with get_conn() as cn:
                cursor = cn.cursor()
                cursor.execute("DELETE FROM historical_portfolio_info WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM f_positions WHERE user_id = ?", (user_id,))
                cn.commit()
            st.success("Portfolio cleared. Proceed to Security Screening.")
        except Exception as e:
            st.error(f"Error clearing portfolio: {e}")

else:
    st.markdown("### Input Your Current Holdings")
    st.markdown("Enter each position below. You can add multiple positions.")
    
    # Check for existing holdings
    def load_existing_holdings(user_id):
        try:
            with get_conn() as cn:
                query = """
                    SELECT ticker, name, sector, market_value, currency
                    FROM historical_portfolio_info
                    WHERE user_id = ? AND date = (
                        SELECT MAX(date) FROM historical_portfolio_info WHERE user_id = ?
                    )
                """
                df = pd.read_sql(query, cn, params=[user_id, user_id])
                return df
        except Exception as e:
            st.error(f"Error loading holdings: {e}")
            return pd.DataFrame()
    
    existing_holdings = load_existing_holdings(user_id)
    
    if not existing_holdings.empty:
        st.markdown("#### Current Holdings")
        st.dataframe(existing_holdings, use_container_width=True)
        
        if st.button("Clear all holdings"):
            try:
                with get_conn() as cn:
                    cursor = cn.cursor()
                    cursor.execute("DELETE FROM historical_portfolio_info WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM f_positions WHERE user_id = ?", (user_id,))
                    cn.commit()
                st.success("All holdings cleared. Refresh page to add new holdings.")
                st.rerun()
            except Exception as e:
                st.error(f"Error clearing holdings: {e}")
    
    st.markdown("#### Add New Position")
    
    col1, col2 = st.columns(2)
    
    with col1:
        ticker = st.text_input("Ticker Symbol", placeholder="AAPL", help="Stock ticker (e.g., AAPL, MSFT, TD.TO)")
        name = st.text_input("Security Name", placeholder="Apple Inc.", help="Full company/security name")
        sector = st.selectbox(
            "Sector",
            options=["Technology", "Financials", "Healthcare", "Energy", "Utilities", 
                    "Real Estate", "Consumer", "Industrial", "Government Bonds", 
                    "Investment Grade Corp", "High Yield"]
        )
    
    with col2:
        market_value = st.number_input("Current Market Value ($)", min_value=0.0, step=100.0, help="Total dollar value of this position")
        currency = st.selectbox("Currency", options=["USD", "CAD"])
        holding_date = st.date_input("As of Date", value=date.today())
    
    if st.button("Add Position", type="primary"):
        if not ticker or not name:
            st.error("Please provide both ticker and name")
        elif market_value <= 0:
            st.error("Market value must be greater than 0")
        else:
            try:
                with get_conn() as cn:
                    cursor = cn.cursor()
                    
                    # Insert into historical_portfolio_info
                    cursor.execute("""
                        INSERT INTO historical_portfolio_info 
                        (user_id, date, ticker, name, sector, market_value, currency, daily_return)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """, (user_id, holding_date, ticker.upper(), name, sector, market_value, currency))
                    
                    # Also insert into f_positions for current snapshot
                    cursor.execute("""
                        MERGE INTO f_positions AS target
                        USING (SELECT ? AS user_id, ? AS ticker) AS source
                        ON target.user_id = source.user_id AND target.ticker = source.ticker
                        WHEN MATCHED THEN
                            UPDATE SET market_value = ?, name = ?, sector = ?, currency = ?, date = ?
                        WHEN NOT MATCHED THEN
                            INSERT (user_id, ticker, name, sector, market_value, currency, date)
                            VALUES (?, ?, ?, ?, ?, ?, ?);
                    """, (user_id, ticker.upper(), market_value, name, sector, currency, holding_date,
                          user_id, ticker.upper(), name, sector, market_value, currency, holding_date))
                    
                    cn.commit()
                
                st.success(f"Added {ticker.upper()} to your portfolio!")
                st.rerun()
                
            except Exception as e:
                st.error(f"Error adding position: {e}")
    
    st.markdown("---")
    st.markdown("**Tip:** You can use Yahoo Finance ticker symbols. For Canadian stocks, add .TO suffix (e.g., TD.TO)")
