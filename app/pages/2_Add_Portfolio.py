"""
Add Portfolio - Manage multiple portfolios per user
List existing portfolios, create new ones, add holdings, delete portfolios
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

st.set_page_config(page_title="Add Portfolio", layout="wide")

st.title("Portfolio Management")

# Get user_id from session
user_id = st.session_state.get('user_id', 1)

def load_user_portfolios(user_id):
    """Load all portfolios for this user"""
    portfolios = []
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            cursor.execute("""
                SELECT id, portfolio_name, description, created_at, is_active
                FROM portfolios
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,))
            
            for row in cursor.fetchall():
                portfolios.append({
                    'id': row[0],
                    'name': row[1],
                    'description': row[2] or '',
                    'created_at': row[3],
                    'is_active': row[4]
                })
    except Exception as e:
        st.error(f"Error loading portfolios: {e}")
    
    return portfolios

def create_portfolio(user_id, portfolio_name, description):
    """Create a new portfolio"""
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            cursor.execute("""
                INSERT INTO portfolios (user_id, portfolio_name, description)
                VALUES (?, ?, ?)
            """, (user_id, portfolio_name, description))
            cn.commit()
            
            # Get the new portfolio_id
            cursor.execute("SELECT @@IDENTITY AS id")
            portfolio_id = cursor.fetchone()[0]
            return portfolio_id
    except Exception as e:
        st.error(f"Error creating portfolio: {e}")
        return None

def delete_portfolio(portfolio_id):
    """Delete a portfolio and all its holdings"""
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            # Delete holdings first
            cursor.execute("DELETE FROM f_positions WHERE portfolio_id = ?", (portfolio_id,))
            cursor.execute("DELETE FROM historical_portfolio_info WHERE portfolio_id = ?", (portfolio_id,))
            # Delete portfolio
            cursor.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
            cn.commit()
        return True
    except Exception as e:
        st.error(f"Error deleting portfolio: {e}")
        return False

def load_portfolio_holdings(portfolio_id):
    """Load holdings for a specific portfolio"""
    try:
        with get_conn() as cn:
            query = """
                SELECT DISTINCT 
                    h.ticker,
                    h.name,
                    h.sector,
                    h.market_value,
                    h.currency,
                    h.asof_date
                FROM historical_portfolio_info h
                WHERE h.portfolio_id = ?
                AND h.asof_date = (
                    SELECT MAX(asof_date) 
                    FROM historical_portfolio_info 
                    WHERE portfolio_id = ?
                )
                ORDER BY h.market_value DESC
            """
            df = pd.read_sql(query, cn, params=[portfolio_id, portfolio_id])
            return df
    except Exception as e:
        st.error(f"Error loading holdings: {e}")
        return pd.DataFrame()

def add_holding(portfolio_id, user_id, ticker, name, sector, market_value, currency, asof_date):
    """Add a holding to a portfolio"""
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            
            # Insert into historical_portfolio_info
            cursor.execute("""
                INSERT INTO historical_portfolio_info 
                (user_id, portfolio_id, ticker, name, sector, market_value, currency, asof_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, portfolio_id, ticker, name, sector, market_value, currency, asof_date))
            
            # Update f_positions (current snapshot)
            cursor.execute("""
                SELECT COUNT(*) FROM f_positions 
                WHERE user_id = ? AND portfolio_id = ? AND ticker = ?
            """, (user_id, portfolio_id, ticker))
            
            if cursor.fetchone()[0] > 0:
                # Update
                cursor.execute("""
                    UPDATE f_positions
                    SET name = ?, sector = ?, market_value = ?, currency = ?, asof_date = ?
                    WHERE user_id = ? AND portfolio_id = ? AND ticker = ?
                """, (name, sector, market_value, currency, asof_date, user_id, portfolio_id, ticker))
            else:
                # Insert
                cursor.execute("""
                    INSERT INTO f_positions (user_id, portfolio_id, ticker, name, sector, market_value, currency, asof_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, portfolio_id, ticker, name, sector, market_value, currency, asof_date))
            
            cn.commit()
        return True
    except Exception as e:
        st.error(f"Error adding holding: {e}")
        return False

# Load existing portfolios
portfolios = load_user_portfolios(user_id)

if not portfolios:
    st.info("You don't have any portfolios yet. Create your first portfolio below!")
    
    # Create first portfolio
    st.markdown("### Create New Portfolio")
    with st.form("create_first_portfolio"):
        portfolio_name = st.text_input("Portfolio Name", value="My Portfolio")
        description = st.text_area("Description (optional)", value="")
        start_option = st.radio(
            "How would you like to start?",
            options=["Empty portfolio", "Input existing holdings"],
            index=0
        )
        
        submitted = st.form_submit_button("Create Portfolio")
        
        if submitted:
            portfolio_id = create_portfolio(user_id, portfolio_name, description)
            if portfolio_id:
                st.success(f"Portfolio '{portfolio_name}' created successfully!")
                st.session_state.selected_portfolio_id = portfolio_id
                st.session_state.start_option = start_option
                st.rerun()
else:
    # Show existing portfolios
    st.markdown("### Your Portfolios")
    
    for portfolio in portfolios:
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"**{portfolio['name']}**")
            if portfolio['description']:
                st.caption(portfolio['description'])
            st.caption(f"Created: {portfolio['created_at'].strftime('%Y-%m-%d')}")
        
        with col2:
            if st.button("View/Edit", key=f"view_{portfolio['id']}"):
                st.session_state.selected_portfolio_id = portfolio['id']
                st.rerun()
        
        with col3:
            if st.button("Delete", key=f"delete_{portfolio['id']}", type="secondary"):
                if delete_portfolio(portfolio['id']):
                    st.success(f"Portfolio '{portfolio['name']}' deleted!")
                    if 'selected_portfolio_id' in st.session_state and st.session_state.selected_portfolio_id == portfolio['id']:
                        del st.session_state.selected_portfolio_id
                    st.rerun()
        
        st.markdown("---")
    
    # Create new portfolio button
    if st.button("+ Create New Portfolio", type="primary"):
        st.session_state.show_create_form = True
        st.rerun()

# Show create form if requested
if st.session_state.get('show_create_form', False):
    st.markdown("### Create New Portfolio")
    with st.form("create_new_portfolio"):
        portfolio_name = st.text_input("Portfolio Name")
        description = st.text_area("Description (optional)")
        
        submitted = st.form_submit_button("Create Portfolio")
        cancel = st.form_submit_button("Cancel")
        
        if submitted and portfolio_name:
            portfolio_id = create_portfolio(user_id, portfolio_name, description)
            if portfolio_id:
                st.success(f"Portfolio '{portfolio_name}' created successfully!")
                st.session_state.selected_portfolio_id = portfolio_id
                st.session_state.show_create_form = False
                st.rerun()
        
        if cancel:
            st.session_state.show_create_form = False
            st.rerun()

# Show portfolio details if one is selected
if 'selected_portfolio_id' in st.session_state:
    portfolio_id = st.session_state.selected_portfolio_id
    
    # Get portfolio name
    portfolio_name = next((p['name'] for p in portfolios if p['id'] == portfolio_id), "Portfolio")
    
    st.markdown("---")
    st.markdown(f"## {portfolio_name}")
    
    # Load holdings
    holdings_df = load_portfolio_holdings(portfolio_id)
    
    if holdings_df.empty:
        st.info("This portfolio is empty. Add your first holding below.")
    else:
        st.markdown(f"### Current Holdings ({len(holdings_df)} positions)")
        # Format for display
        display_df = holdings_df.copy()
        display_df['market_value'] = display_df['market_value'].apply(lambda x: f"${x:,.2f}")
        display_df['asof_date'] = pd.to_datetime(display_df['asof_date']).dt.strftime('%Y-%m-%d')
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        total_value = holdings_df['market_value'].sum()
        st.metric("Total Portfolio Value", f"${total_value:,.2f}")
    
    # Add new holding
    st.markdown("### Add New Holding")
    with st.form(f"add_holding_{portfolio_id}"):
        col1, col2 = st.columns(2)
        
        with col1:
            ticker = st.text_input("Ticker Symbol", value="")
            name = st.text_input("Security Name", value="")
            sector = st.selectbox("Sector", options=[
                "Technology", "Financials", "Healthcare", "Energy", 
                "Utilities", "Real Estate", "Consumer", "Industrial",
                "Fixed Income", "Cash", "Other"
            ])
        
        with col2:
            market_value = st.number_input("Market Value", min_value=0.0, value=0.0, step=100.0)
            currency = st.selectbox("Currency", options=["USD", "CAD"])
            asof_date = st.date_input("As of Date", value=date.today())
        
        submitted = st.form_submit_button("Add Holding")
        
        if submitted and ticker and name:
            if add_holding(portfolio_id, user_id, ticker, name, sector, market_value, currency, asof_date):
                st.success(f"Added {ticker} to portfolio!")
                st.rerun()
    
    # Back button
    if st.button("Back to Portfolio List"):
        del st.session_state.selected_portfolio_id
        st.rerun()
