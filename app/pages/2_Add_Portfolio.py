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
from src.core.benchmark_utils import get_portfolio_benchmark_composition, get_benchmark_name
import src.core.auth as auth

st.set_page_config(page_title="Add Portfolio", layout="wide")

st.title("Portfolio Management")

_rl = getattr(auth, 'require_login', None)
if not callable(_rl):
    st.error("Authentication helper not available. Please restart the app.")
    st.stop()
_rl(st)
user_id = st.session_state.get('user_id')

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

def update_portfolio_name(portfolio_id, new_name, new_description):
    """Update portfolio name and description"""
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            cursor.execute("""
                UPDATE portfolios
                SET portfolio_name = ?, description = ?
                WHERE id = ?
            """, (new_name, new_description, portfolio_id))
            cn.commit()
        return True
    except Exception as e:
        st.error(f"Error updating portfolio: {e}")
        return False

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

def delete_holding(portfolio_id, ticker, holding_date):
    """Delete a specific holding from a portfolio"""
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            # Delete from historical_portfolio_info
            cursor.execute("""
                DELETE FROM historical_portfolio_info 
                WHERE portfolio_id = ? AND ticker = ? AND date = ?
            """, (portfolio_id, ticker, holding_date))
            
            # Delete from f_positions if it's the current position
            cursor.execute("""
                DELETE FROM f_positions 
                WHERE portfolio_id = ? AND ticker = ?
            """, (portfolio_id, ticker))
            
            cn.commit()
        return True
    except Exception as e:
        st.error(f"Error deleting holding: {e}")
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
                    h.date
                FROM historical_portfolio_info h
                WHERE h.portfolio_id = ?
                AND h.date = (
                    SELECT MAX(date) 
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

def add_holding(portfolio_id, user_id, ticker, name, sector, market_value, currency, holding_date):
    """Add a holding to a portfolio"""
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            
            # Step 1: Ensure security exists in dim_securities (required for f_positions FK)
            cursor.execute("""
                SELECT security_id FROM dim_securities WHERE ticker = ?
            """, (ticker,))
            result = cursor.fetchone()
            
            if result:
                security_id = result[0]
            else:
                # Insert new security into dim_securities
                # sleeve defaults to NULL (will be determined by IPS allocation later)
                cursor.execute("""
                    INSERT INTO dim_securities (ticker, name, sector, sleeve, base_ccy)
                    VALUES (?, ?, ?, NULL, ?)
                """, (ticker, name, sector, currency))
                cursor.execute("SELECT @@IDENTITY")
                security_id = cursor.fetchone()[0]
            
            # Step 2: Insert into historical_portfolio_info (uses 'date' column)
            cursor.execute("""
                INSERT INTO historical_portfolio_info 
                (user_id, portfolio_id, ticker, name, sector, market_value, currency, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, portfolio_id, ticker, name, sector, market_value, currency, holding_date))
            
            # Step 3: Update f_positions (current snapshot - uses 'asof_date' and 'security_id' columns)
            cursor.execute("""
                SELECT COUNT(*) FROM f_positions 
                WHERE user_id = ? AND portfolio_id = ? AND ticker = ?
            """, (user_id, portfolio_id, ticker))
            
            if cursor.fetchone()[0] > 0:
                # Update
                cursor.execute("""
                    UPDATE f_positions
                    SET security_id = ?, name = ?, sector = ?, market_value = ?, base_ccy = ?, asof_date = ?
                    WHERE user_id = ? AND portfolio_id = ? AND ticker = ?
                """, (security_id, name, sector, market_value, currency, holding_date, user_id, portfolio_id, ticker))
            else:
                # Insert
                cursor.execute("""
                    INSERT INTO f_positions (security_id, user_id, portfolio_id, ticker, name, sector, market_value, base_ccy, asof_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (security_id, user_id, portfolio_id, ticker, name, sector, market_value, currency, holding_date))
            
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
    
    # Get portfolio details
    portfolio = next((p for p in portfolios if p['id'] == portfolio_id), None)
    if not portfolio:
        st.error("Portfolio not found")
        del st.session_state.selected_portfolio_id
        st.rerun()
    
    portfolio_name = portfolio['name']
    portfolio_description = portfolio.get('description', '')
    
    st.markdown("---")
    
    # Portfolio header with edit option
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"## {portfolio_name}")
        if portfolio_description:
            st.caption(portfolio_description)
    with col2:
        if st.button("Edit Name", key="edit_portfolio_name"):
            st.session_state.show_edit_portfolio = True
            st.rerun()
    
    # Show edit form if requested
    if st.session_state.get('show_edit_portfolio', False):
        st.markdown("### Edit Portfolio Details")
        with st.form("edit_portfolio_form"):
            new_name = st.text_input("Portfolio Name", value=portfolio_name)
            new_description = st.text_area("Description", value=portfolio_description)
            
            col1, col2 = st.columns(2)
            with col1:
                submitted = st.form_submit_button("Save Changes", type="primary")
            with col2:
                cancel = st.form_submit_button("Cancel")
            
            if submitted and new_name:
                if update_portfolio_name(portfolio_id, new_name, new_description):
                    st.success(f"Portfolio updated to '{new_name}'")
                    st.session_state.show_edit_portfolio = False
                    st.rerun()
            
            if cancel:
                st.session_state.show_edit_portfolio = False
                st.rerun()
        
        st.markdown("---")
    
    # Load holdings
    holdings_df = load_portfolio_holdings(portfolio_id)
    
    if holdings_df.empty:
        st.info("This portfolio is empty. Add your first holding below.")
    else:
        st.markdown(f"### Current Holdings ({len(holdings_df)} positions)")
        
        # Display holdings with delete option
        for idx, row in holdings_df.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 1, 1])
            
            with col1:
                st.markdown(f"**{row['ticker']}**")
            with col2:
                st.text(row['name'])
            with col3:
                st.text(row['sector'])
            with col4:
                st.text(f"${row['market_value']:,.2f}")
            with col5:
                st.text(row['currency'])
            with col6:
                if st.button("X", key=f"delete_{row['ticker']}_{idx}", help="Delete holding"):
                    if delete_holding(portfolio_id, row['ticker'], row['date']):
                        st.success(f"Deleted {row['ticker']}")
                        st.rerun()
        
        st.markdown("---")
        
        total_value = holdings_df['market_value'].sum()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Total Portfolio Value", f"${total_value:,.2f}")
        
        with col2:
            # Show benchmark composition
            benchmark_weights = get_portfolio_benchmark_composition(holdings_df)
            if benchmark_weights:
                st.markdown("**Benchmark Composition:**")
                bench_text = []
                for ticker, weight in sorted(benchmark_weights.items(), key=lambda x: x[1], reverse=True):
                    bench_text.append(f"{get_benchmark_name(ticker)} ({ticker}): {weight*100:.1f}%")
                st.caption(" | ".join(bench_text))
    
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
            holding_date = st.date_input("As of Date", value=date.today())
        
        submitted = st.form_submit_button("Add Holding")
        
        if submitted and ticker and name:
            if add_holding(portfolio_id, user_id, ticker, name, sector, market_value, currency, holding_date):
                st.success(f"Added {ticker} to portfolio!")
                st.rerun()
    
    # Back button
    if st.button("Back to Portfolio List"):
        del st.session_state.selected_portfolio_id
        st.rerun()
