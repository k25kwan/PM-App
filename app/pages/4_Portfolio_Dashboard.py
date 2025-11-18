"""
Portfolio Dashboard
Visualize portfolio composition, performance, risk metrics, and attribution analysis
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.utils_db import get_conn
from src.core.benchmark_utils import get_portfolio_benchmark_composition, get_benchmark_name
import yfinance as yf

st.set_page_config(page_title="Portfolio Dashboard", layout="wide")

st.title("Portfolio Dashboard")

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

def load_benchmark_data(benchmark_weights, start_date, end_date):
    """Fetch benchmark returns based on sector weights"""
    try:
        all_benchmark_data = []
        
        for benchmark_ticker, weight in benchmark_weights.items():
            stock = yf.Ticker(benchmark_ticker)
            hist = stock.history(start=start_date, end=end_date)
            
            if not hist.empty:
                hist.reset_index(inplace=True)
                hist['ticker'] = benchmark_ticker
                hist['weight'] = weight
                hist['Date'] = pd.to_datetime(hist['Date']).dt.tz_localize(None)
                all_benchmark_data.append(hist[['Date', 'ticker', 'Close', 'weight']])
        
        if all_benchmark_data:
            combined = pd.concat(all_benchmark_data, ignore_index=True)
            combined.rename(columns={'Date': 'date', 'Close': 'price'}, inplace=True)
            
            # Calculate weighted benchmark return
            combined = combined.sort_values(['date', 'ticker'])
            combined['daily_return'] = combined.groupby('ticker')['price'].pct_change()
            combined['daily_return'] = combined['daily_return'].fillna(0)
            
            # Aggregate weighted returns by date
            weighted_returns = combined.groupby('date').apply(
                lambda x: (x['daily_return'] * x['weight']).sum(),
                include_groups=False
            ).reset_index()
            weighted_returns.columns = ['date', 'daily_return']
            
            # Calculate cumulative return
            weighted_returns['cumulative_return'] = (1 + weighted_returns['daily_return']).cumprod() - 1
            
            return weighted_returns
        else:
            return pd.DataFrame()
    
    except Exception as e:
        st.warning(f"Could not load benchmark data: {e}")
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
    st.subheader("Portfolio vs Benchmark Performance")
    
    # Calculate value-weighted portfolio return
    portfolio_agg = performance_df.groupby('date').apply(
        lambda x: pd.Series({
            'daily_return': (x['daily_return'] * x['market_value']).sum() / x['market_value'].sum(),
            'total_value': x['market_value'].sum()
        }), include_groups=False
    ).reset_index()
    
    # Calculate cumulative return
    portfolio_agg['cumulative_return'] = (1 + portfolio_agg['daily_return']).cumprod() - 1
    
    # Get benchmark weights and data
    benchmark_weights = get_portfolio_benchmark_composition(composition_df)
    benchmark_data = load_benchmark_data(
        benchmark_weights, 
        portfolio_agg['date'].min(), 
        portfolio_agg['date'].max()
    )
    
    fig_agg = go.Figure()
    
    # Add portfolio line
    fig_agg.add_trace(go.Scatter(
        x=portfolio_agg['date'],
        y=portfolio_agg['cumulative_return'] * 100,
        mode='lines',
        name='Portfolio',
        line=dict(color='blue', width=3),
        hovertemplate='<b>Portfolio</b><br>Date: %{x}<br>Return: %{y:.2f}%<extra></extra>'
    ))
    
    # Add benchmark line if data available
    if not benchmark_data.empty:
        fig_agg.add_trace(go.Scatter(
            x=benchmark_data['date'],
            y=benchmark_data['cumulative_return'] * 100,
            mode='lines',
            name='Benchmark',
            line=dict(color='gray', width=2, dash='dash'),
            hovertemplate='<b>Benchmark</b><br>Date: %{x}<br>Return: %{y:.2f}%<extra></extra>'
        ))
    
    fig_agg.update_layout(
        title='Portfolio vs Benchmark Cumulative Returns',
        xaxis_title='Date',
        yaxis_title='Cumulative Return (%)',
        hovermode='x unified',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_agg, use_container_width=True)
    
    # Show benchmark composition
    if benchmark_weights:
        with st.expander("Benchmark Composition & Sector Mapping"):
            st.markdown("**Sector-to-Benchmark Mapping:**")
            
            # Create detailed mapping showing sectors → benchmarks
            from src.core.benchmark_utils import get_benchmark_for_sector
            
            sector_mapping = []
            sector_weights = composition_df.groupby('sector')['market_value'].sum() / composition_df['market_value'].sum()
            
            for sector, weight in sector_weights.items():
                benchmark_ticker = get_benchmark_for_sector(sector)
                sector_mapping.append({
                    'Portfolio Sector': sector,
                    'Sector Weight': f"{weight*100:.1f}%",
                    'Benchmark Index': get_benchmark_name(benchmark_ticker),
                    'Ticker': benchmark_ticker
                })
            
            st.table(pd.DataFrame(sector_mapping))
            
            st.markdown("**Aggregated Benchmark Weights:**")
            bench_display = []
            for ticker, weight in sorted(benchmark_weights.items(), key=lambda x: x[1], reverse=True):
                bench_display.append({
                    'Benchmark Index': get_benchmark_name(ticker),
                    'Ticker': ticker,
                    'Total Weight': f"{weight*100:.1f}%"
                })
            st.table(pd.DataFrame(bench_display))
    
    # Performance statistics
    col1, col2, col3, col4 = st.columns(4)
    
    latest_return = portfolio_agg['cumulative_return'].iloc[-1] * 100
    daily_volatility = portfolio_agg['daily_return'].std() * 100
    annualized_volatility = daily_volatility * (252 ** 0.5)
    sharpe_ratio = (portfolio_agg['daily_return'].mean() / portfolio_agg['daily_return'].std()) * (252 ** 0.5) if portfolio_agg['daily_return'].std() > 0 else 0
    
    # Calculate alpha vs benchmark if available
    if not benchmark_data.empty:
        # Merge portfolio and benchmark by date
        merged = portfolio_agg.merge(benchmark_data[['date', 'cumulative_return']], on='date', suffixes=('_port', '_bench'))
        if not merged.empty:
            port_final = merged['cumulative_return_port'].iloc[-1] * 100
            bench_final = merged['cumulative_return_bench'].iloc[-1] * 100
            alpha = port_final - bench_final
        else:
            alpha = None
    else:
        alpha = None
    
    with col1:
        st.metric("Cumulative Return", f"{latest_return:.2f}%")
    with col2:
        st.metric("Annualized Volatility", f"{annualized_volatility:.2f}%")
    with col3:
        st.metric("Sharpe Ratio", f"{sharpe_ratio:.2f}")
    with col4:
        if alpha is not None:
            st.metric("Alpha vs Benchmark", f"{alpha:+.2f}%", delta=f"{alpha:.2f}%")
        else:
            max_drawdown = (portfolio_agg['cumulative_return'].cummax() - portfolio_agg['cumulative_return']).max() * 100
            st.metric("Max Drawdown", f"-{max_drawdown:.2f}%")

else:
    st.info("No performance data available for the selected date range.")

st.markdown("---")

# ============================================================================
# RISK METRICS
# ============================================================================

st.header("Risk Metrics")

def get_risk_color(metric_name, value):
    """Return background color based on metric thresholds (good/warning/bad)"""
    # Green = good, Yellow = warning, Red = bad
    
    if metric_name == "VaR 95%":
        # VaR is negative, closer to 0 is better
        if value > -1: return "#d4edda"  # Green
        elif value > -2: return "#fff3cd"  # Yellow
        else: return "#f8d7da"  # Red
    
    elif metric_name == "Expected Shortfall":
        # ES is negative, closer to 0 is better
        if value > -1.5: return "#d4edda"
        elif value > -3: return "#fff3cd"
        else: return "#f8d7da"
    
    elif metric_name == "Volatility (Ann.)":
        # Lower volatility is better
        if value < 15: return "#d4edda"
        elif value < 25: return "#fff3cd"
        else: return "#f8d7da"
    
    elif metric_name == "Max Drawdown":
        # Drawdown is negative, closer to 0 is better
        if value > -10: return "#d4edda"
        elif value > -20: return "#fff3cd"
        else: return "#f8d7da"
    
    elif metric_name == "Beta":
        # Beta close to 1 is neutral, <1 is defensive, >1 is aggressive
        if 0.8 <= value <= 1.2: return "#d4edda"
        elif 0.6 <= value <= 1.5: return "#fff3cd"
        else: return "#f8d7da"
    
    elif metric_name == "Tracking Error":
        # Lower tracking error is better for index-like portfolios
        if value < 5: return "#d4edda"
        elif value < 10: return "#fff3cd"
        else: return "#f8d7da"
    
    elif metric_name == "Information Ratio":
        # Higher is better
        if value > 0.5: return "#d4edda"
        elif value > 0: return "#fff3cd"
        else: return "#f8d7da"
    
    elif metric_name == "Active Return (Ann.)":
        # Positive is better
        if value > 2: return "#d4edda"
        elif value > -2: return "#fff3cd"
        else: return "#f8d7da"
    
    elif metric_name == "Security HHI (bps)":
        # Lower is more diversified (better)
        if value < 1500: return "#d4edda"
        elif value < 2500: return "#fff3cd"
        else: return "#f8d7da"
    
    elif metric_name == "Sector HHI (bps)":
        # Lower is more diversified (better)
        if value < 2500: return "#d4edda"
        elif value < 4000: return "#fff3cd"
        else: return "#f8d7da"
    
    elif metric_name == "Sharpe Ratio":
        # Higher is better
        if value > 1: return "#d4edda"
        elif value > 0: return "#fff3cd"
        else: return "#f8d7da"
    
    return "#ffffff"  # Default white

if not performance_df.empty and not portfolio_agg.empty:
    
    # Calculate risk metrics from portfolio data
    returns = portfolio_agg['daily_return'].values
    cum_returns = portfolio_agg['cumulative_return'].values
    
    # Market Risk Metrics
    st.subheader("Market Risk")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # VaR 95% (parametric)
        var_95 = np.percentile(returns, 5) * 100
        color = get_risk_color("VaR 95%", var_95)
        st.markdown(f"""
        <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
            <p style="margin: 0; font-size: 14px; color: #666;">VaR 95%</p>
            <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{var_95:.2f}%</p>
            <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Max expected loss (95% conf.)</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Expected Shortfall (CVaR) - average of losses beyond VaR
        var_threshold = np.percentile(returns, 5)
        cvar = returns[returns <= var_threshold].mean() * 100
        color = get_risk_color("Expected Shortfall", cvar)
        st.markdown(f"""
        <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
            <p style="margin: 0; font-size: 14px; color: #666;">Expected Shortfall</p>
            <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{cvar:.2f}%</p>
            <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Avg loss beyond VaR</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Annualized Volatility
        ann_vol = returns.std() * np.sqrt(252) * 100
        color = get_risk_color("Volatility (Ann.)", ann_vol)
        st.markdown(f"""
        <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
            <p style="margin: 0; font-size: 14px; color: #666;">Volatility (Ann.)</p>
            <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{ann_vol:.2f}%</p>
            <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Annualized std dev</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        # Maximum Drawdown
        cummax = pd.Series(cum_returns).cummax()
        drawdown = (pd.Series(cum_returns) - cummax) * 100
        max_dd = drawdown.min()
        color = get_risk_color("Max Drawdown", max_dd)
        st.markdown(f"""
        <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
            <p style="margin: 0; font-size: 14px; color: #666;">Max Drawdown</p>
            <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{max_dd:.2f}%</p>
            <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Largest decline</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Relative Risk Metrics (vs Benchmark)
    if not benchmark_data.empty:
        st.subheader("Relative Risk")
        
        # Merge portfolio and benchmark for regression
        merged = portfolio_agg.merge(
            benchmark_data[['date', 'daily_return']], 
            on='date', 
            suffixes=('_port', '_bench')
        )
        
        if len(merged) > 30:  # Need sufficient data for stats
            port_returns = merged['daily_return_port'].values
            bench_returns = merged['daily_return_bench'].values
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                # Beta (covariance / benchmark variance)
                covariance = np.cov(port_returns, bench_returns)[0, 1]
                bench_variance = np.var(bench_returns)
                beta = covariance / bench_variance if bench_variance > 0 else 0
                color = get_risk_color("Beta", beta)
                st.markdown(f"""
                <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
                    <p style="margin: 0; font-size: 14px; color: #666;">Beta</p>
                    <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{beta:.2f}</p>
                    <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Benchmark sensitivity</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                # Tracking Error (volatility of active returns)
                active_returns = port_returns - bench_returns
                tracking_error = active_returns.std() * np.sqrt(252) * 100
                color = get_risk_color("Tracking Error", tracking_error)
                st.markdown(f"""
                <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
                    <p style="margin: 0; font-size: 14px; color: #666;">Tracking Error</p>
                    <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{tracking_error:.2f}%</p>
                    <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Active return volatility</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                # Information Ratio (active return / tracking error)
                active_return_ann = active_returns.mean() * 252 * 100
                info_ratio = (active_return_ann / tracking_error) if tracking_error > 0 else 0
                color = get_risk_color("Information Ratio", info_ratio)
                st.markdown(f"""
                <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
                    <p style="margin: 0; font-size: 14px; color: #666;">Information Ratio</p>
                    <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{info_ratio:.2f}</p>
                    <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Risk-adj. excess return</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                # Active Return (annualized)
                color = get_risk_color("Active Return (Ann.)", active_return_ann)
                st.markdown(f"""
                <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
                    <p style="margin: 0; font-size: 14px; color: #666;">Active Return (Ann.)</p>
                    <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{active_return_ann:+.2f}%</p>
                    <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Ann. return vs benchmark</p>
                </div>
                """, unsafe_allow_html=True)
    
    # Concentration & Duration Metrics
    st.subheader("Concentration & Duration")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Security HHI (Herfindahl-Hirschman Index)
        weights = composition_df['market_value'] / composition_df['market_value'].sum()
        security_hhi = (weights ** 2).sum() * 10000  # Convert to bps
        color = get_risk_color("Security HHI (bps)", security_hhi)
        st.markdown(f"""
        <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
            <p style="margin: 0; font-size: 14px; color: #666;">Security HHI (bps)</p>
            <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{security_hhi:.0f}</p>
            <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Security concentration</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Sector HHI
        sector_weights = composition_df.groupby('sector')['market_value'].sum() / composition_df['market_value'].sum()
        sector_hhi = (sector_weights ** 2).sum() * 10000
        color = get_risk_color("Sector HHI (bps)", sector_hhi)
        st.markdown(f"""
        <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
            <p style="margin: 0; font-size: 14px; color: #666;">Sector HHI (bps)</p>
            <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{sector_hhi:.0f}</p>
            <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Sector concentration</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Sharpe Ratio (already calculated above)
        sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        color = get_risk_color("Sharpe Ratio", sharpe)
        st.markdown(f"""
        <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
            <p style="margin: 0; font-size: 14px; color: #666;">Sharpe Ratio</p>
            <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{sharpe:.2f}</p>
            <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Return per unit of risk</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        # DV01 placeholder (would need bond duration data)
        st.markdown(f"""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
            <p style="margin: 0; font-size: 14px; color: #666;">DV01 ($)</p>
            <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">N/A</p>
            <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Requires bond data</p>
        </div>
        """, unsafe_allow_html=True)

else:
    st.info("No data available for risk calculations.")

st.markdown("---")

# ============================================================================
# ATTRIBUTION ANALYSIS
# ============================================================================

st.header("Attribution Analysis")

if not performance_df.empty and not benchmark_data.empty and not composition_df.empty:
    
    # Calculate sector-level attribution (Brinson-Fachler model)
    # Attribution = Allocation Effect + Selection Effect + Interaction Effect
    
    # Get latest date for weights
    latest_date = performance_df['date'].max()
    
    # Calculate portfolio sector weights and returns for the entire period
    # Group by sector and calculate average daily returns over the selected period
    portfolio_sector = performance_df.groupby('sector').agg({
        'market_value': 'last',  # Use last market value
        'daily_return': 'mean'  # Average daily return over period
    }).reset_index()
    
    # Filter out any null sectors
    portfolio_sector = portfolio_sector[portfolio_sector['sector'].notna()]
    
    # Check if we have valid data
    if len(portfolio_sector) == 0:
        st.warning("No sector data available for attribution analysis.")
    else:
        portfolio_total = portfolio_sector['market_value'].sum()
        portfolio_sector['weight'] = portfolio_sector['market_value'] / portfolio_total
        portfolio_sector.rename(columns={'daily_return': 'return'}, inplace=True)
        
        # Calculate benchmark sector composition based on portfolio sectors
        from src.core.benchmark_utils import get_benchmark_for_sector
        
        # Create benchmark weights based on portfolio sector allocation
        benchmark_sector = portfolio_sector[['sector', 'weight']].copy()
        benchmark_sector['benchmark_ticker'] = benchmark_sector['sector'].apply(get_benchmark_for_sector)
        
        # Calculate average benchmark return over the period
        benchmark_return_avg = benchmark_data['daily_return'].mean() if len(benchmark_data) > 0 else 0
        
        # For attribution, use the average benchmark return for all sectors
        # In production, you would fetch sector-specific benchmark returns
        sector_bench_returns = {}
        for sector in portfolio_sector['sector'].unique():
            bench_ticker = get_benchmark_for_sector(sector)
            # Use the overall benchmark return as approximation
            sector_bench_returns[sector] = benchmark_return_avg
        
        benchmark_sector['return'] = benchmark_sector['sector'].map(sector_bench_returns)
    
        benchmark_sector['return'] = benchmark_sector['sector'].map(sector_bench_returns)
        
        # Merge portfolio and benchmark data
        attribution_df = portfolio_sector.merge(
            benchmark_sector[['sector', 'return']], 
            on='sector', 
            suffixes=('_port', '_bench')
        )
        
        # Calculate attribution effects (in basis points)
        # Allocation Effect = (w_p - w_b) * (R_b - R_B)
        # Selection Effect = w_b * (R_p - R_b)
        # Interaction Effect = (w_p - w_b) * (R_p - R_b)
        
        # Since we're matching weights, w_b = w_p for each sector
        # So allocation effect is driven by sector weight differences vs equal weight
        n_sectors = len(attribution_df)
        equal_weight = 1.0 / n_sectors if n_sectors > 0 else 0
        
        benchmark_total_return = attribution_df['return_bench'].mean()  # Equal-weighted benchmark
        portfolio_total_return = (attribution_df['weight'] * attribution_df['return_port']).sum()
        
        attribution_df['allocation_effect'] = (attribution_df['weight'] - equal_weight) * (attribution_df['return_bench'] - benchmark_total_return) * 10000
        attribution_df['selection_effect'] = attribution_df['weight'] * (attribution_df['return_port'] - attribution_df['return_bench']) * 10000
        attribution_df['interaction_effect'] = (attribution_df['weight'] - equal_weight) * (attribution_df['return_port'] - attribution_df['return_bench']) * 10000
        attribution_df['total_effect'] = attribution_df['allocation_effect'] + attribution_df['selection_effect'] + attribution_df['interaction_effect']
        
        # Display summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        total_allocation = attribution_df['allocation_effect'].sum()
        total_selection = attribution_df['selection_effect'].sum()
        total_interaction = attribution_df['interaction_effect'].sum()
        total_active = attribution_df['total_effect'].sum()
        
        with col1:
            color = "#d4edda" if total_allocation > 0 else "#f8d7da"
            st.markdown(f"""
            <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
                <p style="margin: 0; font-size: 14px; color: #666;">Total Allocation</p>
                <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{total_allocation:+.1f} bps</p>
                <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Sector weighting impact</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            color = "#d4edda" if total_selection > 0 else "#f8d7da"
            st.markdown(f"""
            <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
                <p style="margin: 0; font-size: 14px; color: #666;">Total Selection</p>
                <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{total_selection:+.1f} bps</p>
                <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Security selection impact</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            color = "#d4edda" if total_interaction > 0 else "#f8d7da"
            st.markdown(f"""
            <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
                <p style="margin: 0; font-size: 14px; color: #666;">Total Interaction</p>
                <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{total_interaction:+.1f} bps</p>
                <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Combined effect</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            color = "#d4edda" if total_active > 0 else "#f8d7da"
            st.markdown(f"""
            <div style="background-color: {color}; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
                <p style="margin: 0; font-size: 14px; color: #666;">Total Active Return</p>
                <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; color: #333;">{total_active:+.1f} bps</p>
                <p style="margin: 5px 0 0 0; font-size: 11px; color: #888;">Total attribution</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Bar chart showing attribution by sector
        st.subheader("Attribution by Sector")
        
        fig_attribution = go.Figure()
        
        # Add bars for each effect type
        fig_attribution.add_trace(go.Bar(
            name='Allocation',
            x=attribution_df['sector'],
            y=attribution_df['allocation_effect'],
            marker_color='#4472C4'
        ))
        
        fig_attribution.add_trace(go.Bar(
            name='Selection',
            x=attribution_df['sector'],
            y=attribution_df['selection_effect'],
            marker_color='#70AD47'
        ))
        
        fig_attribution.add_trace(go.Bar(
            name='Interaction',
            x=attribution_df['sector'],
            y=attribution_df['interaction_effect'],
            marker_color='#FFC000'
        ))
        
        fig_attribution.update_layout(
            barmode='group',
            xaxis_title='Sector',
            yaxis_title='Attribution (bps)',
            height=400,
            hovermode='x unified',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        
        st.plotly_chart(fig_attribution, use_container_width=True)
        
        # Detailed attribution table
        with st.expander("Detailed Attribution Breakdown"):
            display_df = attribution_df[['sector', 'weight', 'return_port', 'return_bench', 
                                         'allocation_effect', 'selection_effect', 
                                         'interaction_effect', 'total_effect']].copy()
            
            display_df.columns = ['Sector', 'Portfolio Weight', 'Portfolio Return', 'Benchmark Return',
                                 'Allocation (bps)', 'Selection (bps)', 'Interaction (bps)', 'Total (bps)']
            
            # Format percentages and basis points
            display_df['Portfolio Weight'] = display_df['Portfolio Weight'].apply(lambda x: f"{x*100:.2f}%")
            display_df['Portfolio Return'] = display_df['Portfolio Return'].apply(lambda x: f"{x*100:.2f}%")
            display_df['Benchmark Return'] = display_df['Benchmark Return'].apply(lambda x: f"{x*100:.2f}%")
            display_df['Allocation (bps)'] = display_df['Allocation (bps)'].apply(lambda x: f"{x:+.1f}")
            display_df['Selection (bps)'] = display_df['Selection (bps)'].apply(lambda x: f"{x:+.1f}")
            display_df['Interaction (bps)'] = display_df['Interaction (bps)'].apply(lambda x: f"{x:+.1f}")
            display_df['Total (bps)'] = display_df['Total (bps)'].apply(lambda x: f"{x:+.1f}")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    st.info("No data available for attribution analysis. Requires portfolio performance and benchmark data.")
