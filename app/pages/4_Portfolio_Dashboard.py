"""
Portfolio Dashboard
Visualize portfolio composition, performance, risk metrics, and attribution analysis
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.utils_db import get_conn

st.set_page_config(page_title="Portfolio Dashboard", layout="wide")

st.title("📊 Portfolio Dashboard")

# Get user_id from session
user_id = st.session_state.get('user_id', 1)

def load_user_portfolios(user_id):
    """Load all portfolios for a user"""
    try:
        with get_conn() as cn:
            query = """
                SELECT id, portfolio_name, description, created_at, is_active
                FROM portfolios
                WHERE user_id = ?
                ORDER BY created_at DESC
            """
            df = pd.read_sql(query, cn, params=[user_id])
            return df
    except Exception as e:
        st.error(f"Error loading portfolios: {e}")
        return pd.DataFrame()

def load_portfolio_composition(portfolio_id, as_of_date=None):
    """Load current portfolio holdings for composition analysis"""
    try:
        with get_conn() as cn:
            if as_of_date is None:
                # Get latest date
                query = """
                    SELECT 
                        ticker,
                        name,
                        sector,
                        market_value,
                        base_ccy,
                        asof_date
                    FROM f_positions
                    WHERE portfolio_id = ?
                    AND asof_date = (SELECT MAX(asof_date) FROM f_positions WHERE portfolio_id = ?)
                """
                df = pd.read_sql(query, cn, params=[portfolio_id, portfolio_id])
            else:
                query = """
                    SELECT 
                        ticker,
                        name,
                        sector,
                        market_value,
                        base_ccy,
                        asof_date
                    FROM f_positions
                    WHERE portfolio_id = ?
                    AND asof_date = ?
                """
                df = pd.read_sql(query, cn, params=[portfolio_id, as_of_date])
            
            return df
    except Exception as e:
        st.error(f"Error loading composition: {e}")
        return pd.DataFrame()

def load_performance_data(portfolio_id, start_date=None, end_date=None):
    """Load portfolio performance (cumulative returns by ticker)"""
    try:
        with get_conn() as cn:
            query = """
                SELECT 
                    date,
                    ticker,
                    name,
                    sector,
                    cumulative_return,
                    daily_return,
                    market_value
                FROM historical_portfolio_info
                WHERE portfolio_id = ?
            """
            params = [portfolio_id]
            
            if start_date:
                query += " AND date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND date <= ?"
                params.append(end_date)
            
            query += " ORDER BY date, ticker"
            
            df = pd.read_sql(query, cn, params=params)
            df['date'] = pd.to_datetime(df['date'])
            return df
    except Exception as e:
        st.error(f"Error loading performance: {e}")
        return pd.DataFrame()

# Portfolio Selection
portfolios = load_user_portfolios(user_id)

if portfolios.empty:
    st.warning("No portfolios found. Please create a portfolio first in the 'Add Portfolio' page.")
    st.stop()

# Sidebar filters
st.sidebar.header("Dashboard Filters")

selected_portfolio = st.sidebar.selectbox(
    "Select Portfolio",
    options=portfolios['id'].tolist(),
    format_func=lambda x: portfolios[portfolios['id'] == x]['portfolio_name'].values[0]
)

# Date range selector
st.sidebar.subheader("Date Range")
date_range_option = st.sidebar.radio(
    "Select Range",
    options=["Last 30 Days", "Last 90 Days", "Year to Date", "All Time", "Custom"],
    index=3
)

if date_range_option == "Custom":
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=365))
    with col2:
        end_date = st.date_input("End Date", value=datetime.now())
else:
    end_date = datetime.now()
    if date_range_option == "Last 30 Days":
        start_date = end_date - timedelta(days=30)
    elif date_range_option == "Last 90 Days":
        start_date = end_date - timedelta(days=90)
    elif date_range_option == "Year to Date":
        start_date = datetime(end_date.year, 1, 1)
    else:  # All Time
        start_date = None
        end_date = None

# Load data for selected portfolio
composition_df = load_portfolio_composition(selected_portfolio)
performance_df = load_performance_data(selected_portfolio, start_date, end_date)

# ============================================================================
# COMPOSITION CHARTS
# ============================================================================

st.header("Portfolio Composition")

if not composition_df.empty:
    # Calculate total portfolio value
    total_value = composition_df['market_value'].sum()
    
    # Add weight column
    composition_df['weight'] = composition_df['market_value'] / total_value * 100
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Sector Allocation")
        sector_allocation = composition_df.groupby('sector')['market_value'].sum().reset_index()
        sector_allocation['weight'] = sector_allocation['market_value'] / total_value * 100
        
        fig_sector = px.pie(
            sector_allocation,
            values='market_value',
            names='sector',
            title='Portfolio by Sector',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig_sector.update_traces(
            textposition='inside',
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>Value: $%{value:,.0f}<br>Weight: %{percent}<extra></extra>'
        )
        st.plotly_chart(fig_sector, use_container_width=True)
    
    with col2:
        st.subheader("Ticker Allocation")
        ticker_allocation = composition_df.groupby('ticker')['market_value'].sum().reset_index()
        ticker_allocation = ticker_allocation.nlargest(10, 'market_value')  # Top 10
        
        fig_ticker = px.pie(
            ticker_allocation,
            values='market_value',
            names='ticker',
            title='Top 10 Holdings',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_ticker.update_traces(
            textposition='inside',
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>Value: $%{value:,.0f}<br>Weight: %{percent}<extra></extra>'
        )
        st.plotly_chart(fig_ticker, use_container_width=True)
    
    with col3:
        st.subheader("Portfolio Metrics")
        st.metric("Total Value", f"${total_value:,.0f}")
        st.metric("Number of Holdings", len(composition_df))
        st.metric("Number of Sectors", composition_df['sector'].nunique())
        
        # Concentration metrics
        hhi = (composition_df['weight'] ** 2).sum()
        st.metric("Concentration (HHI)", f"{hhi:.2f}")
    
    # Detailed holdings table
    st.subheader("Holdings Detail")
    holdings_display = composition_df[['ticker', 'name', 'sector', 'market_value', 'weight']].copy()
    holdings_display['market_value'] = holdings_display['market_value'].apply(lambda x: f"${x:,.0f}")
    holdings_display['weight'] = holdings_display['weight'].apply(lambda x: f"{x:.2f}%")
    holdings_display.columns = ['Ticker', 'Name', 'Sector', 'Market Value', 'Weight (%)']
    holdings_display = holdings_display.sort_values('Weight (%)', ascending=False)
    
    st.dataframe(holdings_display, use_container_width=True, hide_index=True)

else:
    st.info("No holdings data available for this portfolio.")

st.markdown("---")

# ============================================================================
# PERFORMANCE CHARTS
# ============================================================================

st.header("Performance Analysis")

if not performance_df.empty:
    
    # Portfolio Cumulative Returns by Ticker
    st.subheader("Portfolio Cumulative Returns by Ticker")
    
    fig_portfolio_returns = px.line(
        performance_df,
        x='date',
        y='cumulative_return',
        color='ticker',
        title='Cumulative Returns by Holding',
        labels={'cumulative_return': 'Cumulative Return (%)', 'date': 'Date'},
        hover_data=['name', 'sector']
    )
    fig_portfolio_returns.update_traces(
        hovertemplate='<b>%{fullData.name}</b><br>Date: %{x}<br>Return: %{y:.2%}<extra></extra>'
    )
    fig_portfolio_returns.update_layout(
        hovermode='x unified',
        yaxis_tickformat='.1%',
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_portfolio_returns, use_container_width=True)
    
    # Portfolio-level aggregate performance
    st.subheader("Portfolio Aggregate Performance")
    
    # Calculate value-weighted portfolio return
    portfolio_agg = performance_df.groupby('date').apply(
        lambda x: pd.Series({
            'daily_return': (x['daily_return'] * x['market_value']).sum() / x['market_value'].sum(),
            'total_value': x['market_value'].sum()
        })
    ).reset_index()
    
    # Calculate cumulative return
    portfolio_agg['cumulative_return'] = (1 + portfolio_agg['daily_return']).cumprod() - 1
    
    fig_agg = go.Figure()
    fig_agg.add_trace(go.Scatter(
        x=portfolio_agg['date'],
        y=portfolio_agg['cumulative_return'] * 100,
        mode='lines',
        name='Portfolio',
        line=dict(color='blue', width=3),
        hovertemplate='<b>Portfolio</b><br>Date: %{x}<br>Return: %{y:.2f}%<extra></extra>'
    ))
    
    fig_agg.update_layout(
        title='Portfolio Cumulative Return',
        xaxis_title='Date',
        yaxis_title='Cumulative Return (%)',
        hovermode='x unified',
        showlegend=True
    )
    st.plotly_chart(fig_agg, use_container_width=True)
    
    # Performance statistics
    col1, col2, col3, col4 = st.columns(4)
    
    latest_return = portfolio_agg['cumulative_return'].iloc[-1] * 100
    daily_volatility = portfolio_agg['daily_return'].std() * 100
    annualized_volatility = daily_volatility * (252 ** 0.5)
    sharpe_ratio = (portfolio_agg['daily_return'].mean() / portfolio_agg['daily_return'].std()) * (252 ** 0.5) if portfolio_agg['daily_return'].std() > 0 else 0
    
    with col1:
        st.metric("Cumulative Return", f"{latest_return:.2f}%")
    with col2:
        st.metric("Annualized Volatility", f"{annualized_volatility:.2f}%")
    with col3:
        st.metric("Sharpe Ratio", f"{sharpe_ratio:.2f}")
    with col4:
        max_drawdown = (portfolio_agg['cumulative_return'].cummax() - portfolio_agg['cumulative_return']).max() * 100
        st.metric("Max Drawdown", f"-{max_drawdown:.2f}%")

else:
    st.info("No performance data available for the selected date range.")

st.markdown("---")

# ============================================================================
# RISK METRICS (Placeholder - to be implemented next)
# ============================================================================

st.header("Risk Metrics")
st.info("Risk metrics visualization coming soon. Will display VaR, Expected Shortfall, Beta, Tracking Error, etc.")

st.markdown("---")

# ============================================================================
# ATTRIBUTION ANALYSIS (Placeholder - to be implemented last)
# ============================================================================

st.header("Attribution Analysis")
st.info("Attribution analysis visualization coming soon. Will display allocation, selection, and interaction effects by sector.")
