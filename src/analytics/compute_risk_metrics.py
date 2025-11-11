"""
Portfolio Risk Metrics Calculator

Computes comprehensive risk metrics for portfolio monitoring:
- Market Risk: VaR, ES, Volatility, Max Drawdown, Sharpe Ratio
- Relative Risk: Beta, Tracking Error, Information Ratio, Active Return
- Concentration: HHI (Herfindahl-Hirschman Index)
- Duration: DV01 (Dollar Value of 01)
"""

import pandas as pd
import numpy as np
from src.core.utils_db import get_conn
from datetime import date, timedelta

# Risk-free rate (annualized)
RISK_FREE_RATE = 0.04  # 4% annual

def load_portfolio_returns(asof_date=None):
    """Load portfolio-weighted daily returns from database view up to asof_date"""
    with get_conn() as cn:
        if asof_date:
            query = """
            SELECT date, daily_return
            FROM v_portfolio_daily_returns
            WHERE date <= ?
            ORDER BY date
            """
            df = pd.read_sql(query, cn, params=[asof_date])
        else:
            query = """
            SELECT date, daily_return
            FROM v_portfolio_daily_returns
            ORDER BY date
            """
            df = pd.read_sql(query, cn)
    df['date'] = pd.to_datetime(df['date'])
    df = df.dropna(subset=['daily_return'])
    df = df.sort_values('date')
    return df

def load_benchmark_returns(asof_date=None):
    """Load benchmark composite daily returns from database view up to asof_date"""
    with get_conn() as cn:
        if asof_date:
            query = """
            SELECT date, daily_return
            FROM v_benchmark_daily_returns
            WHERE date <= ?
            ORDER BY date
            """
            df = pd.read_sql(query, cn, params=[asof_date])
        else:
            query = """
            SELECT date, daily_return
            FROM v_benchmark_daily_returns
            ORDER BY date
            """
            df = pd.read_sql(query, cn)
    df['date'] = pd.to_datetime(df['date'])
    df = df.dropna(subset=['daily_return'])
    df = df.sort_values('date')
    return df

def load_portfolio_holdings(asof_date=None):
    """Load portfolio holdings for concentration metrics as of specified date"""
    with get_conn() as cn:
        if asof_date:
            query = """
            SELECT ticker, market_value, sector
            FROM historical_portfolio_info
            WHERE date = ?
            """
            df = pd.read_sql(query, cn, params=[asof_date])
        else:
            query = """
            SELECT ticker, market_value, sector
            FROM historical_portfolio_info
            WHERE date = (SELECT MAX(date) FROM historical_portfolio_info)
            """
            df = pd.read_sql(query, cn)
    return df

def load_bond_durations(asof_date=None):
    """Load bond positions and their durations as of specified date"""
    with get_conn() as cn:
        if asof_date:
            query = """
            SELECT ticker, market_value, sector
            FROM historical_portfolio_info
            WHERE date = ?
            AND sector LIKE '%Bond%'
            """
            df = pd.read_sql(query, cn, params=[asof_date])
        else:
            query = """
            SELECT ticker, market_value, sector
            FROM historical_portfolio_info
            WHERE date = (SELECT MAX(date) FROM historical_portfolio_info)
            AND sector LIKE '%Bond%'
            """
            df = pd.read_sql(query, cn)
    return df

# ============================================================================
# MARKET RISK METRICS
# ============================================================================

def calculate_var_95(returns, lookback_days=252):
    """
    Calculate Value at Risk at 95% confidence level
    Returns the 5th percentile of returns (negative value = loss)
    """
    if len(returns) < lookback_days:
        lookback_days = len(returns)
    recent_returns = returns.tail(lookback_days)
    var_95 = np.percentile(recent_returns, 5)
    return var_95

def calculate_expected_shortfall(returns, lookback_days=252):
    """
    Calculate Expected Shortfall (Conditional VaR)
    Average of returns below the VaR threshold
    """
    if len(returns) < lookback_days:
        lookback_days = len(returns)
    recent_returns = returns.tail(lookback_days)
    var_95 = np.percentile(recent_returns, 5)
    es = recent_returns[recent_returns <= var_95].mean()
    return es

def calculate_volatility(returns, lookback_days=252):
    """
    Calculate annualized volatility
    """
    if len(returns) < lookback_days:
        lookback_days = len(returns)
    recent_returns = returns.tail(lookback_days)
    daily_vol = recent_returns.std()
    annualized_vol = daily_vol * np.sqrt(252)
    return annualized_vol

def calculate_sharpe_ratio(returns, lookback_days=252):
    """
    Calculate Sharpe Ratio
    (Annualized Return - Risk Free Rate) / Annualized Volatility
    """
    if len(returns) < lookback_days:
        lookback_days = len(returns)
    recent_returns = returns.tail(lookback_days)
    
    # Annualized return
    cumulative_return = (1 + recent_returns).prod() - 1
    annualized_return = (1 + cumulative_return) ** (252 / len(recent_returns)) - 1
    
    # Annualized volatility
    annualized_vol = recent_returns.std() * np.sqrt(252)
    
    if annualized_vol == 0:
        return 0
    
    sharpe = (annualized_return - RISK_FREE_RATE) / annualized_vol
    return sharpe

def calculate_max_drawdown(returns, lookback_days=252):
    """
    Calculate Maximum Drawdown
    Largest peak-to-trough decline
    """
    if len(returns) < lookback_days:
        lookback_days = len(returns)
    recent_returns = returns.tail(lookback_days)
    
    # Calculate cumulative returns
    cumulative = (1 + recent_returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_dd = drawdown.min()
    return max_dd

# ============================================================================
# RELATIVE RISK METRICS (vs Benchmark)
# ============================================================================

def calculate_beta(portfolio_returns, benchmark_returns, lookback_days=252):
    """
    Calculate Beta (sensitivity to benchmark)
    Covariance(Portfolio, Benchmark) / Variance(Benchmark)
    """
    # Align dates
    merged = pd.merge(portfolio_returns, benchmark_returns, on='date', suffixes=('_port', '_bench'))
    
    if len(merged) < lookback_days:
        lookback_days = len(merged)
    
    recent = merged.tail(lookback_days)
    
    covariance = recent['daily_return_port'].cov(recent['daily_return_bench'])
    benchmark_variance = recent['daily_return_bench'].var()
    
    if benchmark_variance == 0:
        return 0
    
    beta = covariance / benchmark_variance
    return beta

def calculate_tracking_error(portfolio_returns, benchmark_returns, lookback_days=252):
    """
    Calculate Tracking Error (annualized)
    Standard deviation of active returns (portfolio - benchmark)
    """
    # Align dates
    merged = pd.merge(portfolio_returns, benchmark_returns, on='date', suffixes=('_port', '_bench'))
    
    if len(merged) < lookback_days:
        lookback_days = len(merged)
    
    recent = merged.tail(lookback_days)
    
    active_returns = recent['daily_return_port'] - recent['daily_return_bench']
    tracking_error = active_returns.std() * np.sqrt(252)
    return tracking_error

def calculate_information_ratio(portfolio_returns, benchmark_returns, lookback_days=252):
    """
    Calculate Information Ratio
    Active Return / Tracking Error
    """
    # Align dates
    merged = pd.merge(portfolio_returns, benchmark_returns, on='date', suffixes=('_port', '_bench'))
    
    if len(merged) < lookback_days:
        lookback_days = len(merged)
    
    recent = merged.tail(lookback_days)
    
    active_returns = recent['daily_return_port'] - recent['daily_return_bench']
    
    # Annualized active return
    cumulative_active = (1 + active_returns).prod() - 1
    annualized_active_return = (1 + cumulative_active) ** (252 / len(active_returns)) - 1
    
    # Tracking error
    tracking_error = active_returns.std() * np.sqrt(252)
    
    if tracking_error == 0:
        return 0
    
    info_ratio = annualized_active_return / tracking_error
    return info_ratio

def calculate_active_return(portfolio_returns, benchmark_returns, lookback_days=252):
    """
    Calculate Annualized Active Return
    Portfolio Return - Benchmark Return
    """
    # Align dates
    merged = pd.merge(portfolio_returns, benchmark_returns, on='date', suffixes=('_port', '_bench'))
    
    if len(merged) < lookback_days:
        lookback_days = len(merged)
    
    recent = merged.tail(lookback_days)
    
    active_returns = recent['daily_return_port'] - recent['daily_return_bench']
    cumulative_active = (1 + active_returns).prod() - 1
    annualized_active_return = (1 + cumulative_active) ** (252 / len(active_returns)) - 1
    
    return annualized_active_return

# ============================================================================
# CONCENTRATION METRICS
# ============================================================================

def calculate_hhi(holdings_df):
    """
    Calculate Herfindahl-Hirschman Index (HHI)
    Sum of squared weights (0-10000, higher = more concentrated)
    """
    total_mv = holdings_df['market_value'].sum()
    if total_mv == 0:
        return 0
    
    weights = holdings_df['market_value'] / total_mv
    hhi = (weights ** 2).sum() * 10000  # Scale to 0-10000
    return hhi

def calculate_sector_hhi(holdings_df):
    """
    Calculate HHI at sector level
    """
    sector_mv = holdings_df.groupby('sector')['market_value'].sum()
    total_mv = sector_mv.sum()
    
    if total_mv == 0:
        return 0
    
    weights = sector_mv / total_mv
    hhi = (weights ** 2).sum() * 10000
    return hhi

# ============================================================================
# DURATION METRICS
# ============================================================================

def calculate_dv01(bond_holdings_df):
    """
    Calculate DV01 (Dollar Value of 01 basis point)
    Approximation using bond duration estimates
    
    For simplicity, using approximate durations:
    - US10Y (10-year treasury): ~9 years duration
    - CORP5 (5-year corporate): ~4.5 years duration
    - CAN10Y (10-year Canada): ~9 years duration
    """
    # Approximate modified durations
    duration_map = {
        'US10Y': 9.0,
        'CORP5': 4.5,
        'CAN10Y': 9.0
    }
    
    total_dv01 = 0
    for _, row in bond_holdings_df.iterrows():
        ticker = row['ticker']
        mv = row['market_value']
        
        if ticker in duration_map:
            duration = duration_map[ticker]
            # DV01 = Market Value * Modified Duration * 0.0001
            dv01 = mv * duration * 0.0001
            total_dv01 += dv01
    
    return total_dv01

# ============================================================================
# MAIN CALCULATION AND STORAGE
# ============================================================================

def calculate_and_store_all_metrics(asof_date=None):
    """
    Calculate all risk metrics and store in database
    """
    if asof_date is None:
        asof_date = date.today()
    
    print(f"Calculating risk metrics as of {asof_date}...")
    
    # Load data up to asof_date for point-in-time calculations
    port_returns = load_portfolio_returns(asof_date)
    bench_returns = load_benchmark_returns(asof_date)
    holdings = load_portfolio_holdings(asof_date)
    bond_holdings = load_bond_durations(asof_date)
    
    # Prepare metrics list
    metrics = []
    lookback = 252  # 1 year rolling window
    
    # Market Risk Metrics
    returns_series = port_returns['daily_return']
    metrics.append(('VaR_95', calculate_var_95(returns_series, lookback), 'Market Risk', lookback))
    metrics.append(('Expected_Shortfall', calculate_expected_shortfall(returns_series, lookback), 'Market Risk', lookback))
    metrics.append(('Volatility_Ann', calculate_volatility(returns_series, lookback), 'Market Risk', lookback))
    metrics.append(('Sharpe_Ratio', calculate_sharpe_ratio(returns_series, lookback), 'Market Risk', lookback))
    metrics.append(('Max_Drawdown', calculate_max_drawdown(returns_series, lookback), 'Market Risk', lookback))
    
    # Relative Risk Metrics
    metrics.append(('Beta', calculate_beta(port_returns, bench_returns, lookback), 'Relative Risk', lookback))
    metrics.append(('Tracking_Error', calculate_tracking_error(port_returns, bench_returns, lookback), 'Relative Risk', lookback))
    metrics.append(('Information_Ratio', calculate_information_ratio(port_returns, bench_returns, lookback), 'Relative Risk', lookback))
    metrics.append(('Active_Return', calculate_active_return(port_returns, bench_returns, lookback), 'Relative Risk', lookback))
    
    # Concentration Metrics
    metrics.append(('HHI_Security', calculate_hhi(holdings), 'Concentration', None))
    metrics.append(('HHI_Sector', calculate_sector_hhi(holdings), 'Concentration', None))
    
    # Duration Metrics
    metrics.append(('DV01', calculate_dv01(bond_holdings), 'Duration', None))
    
    # Store in database
    with get_conn() as cn:
        cursor = cn.cursor()
        
        # Delete existing metrics for this date
        cursor.execute("DELETE FROM portfolio_risk_metrics WHERE asof_date = ?", (asof_date,))
        cn.commit()
        
        # Insert new metrics
        for metric_name, metric_value, category, lookback_days in metrics:
            cursor.execute(
                """
                INSERT INTO portfolio_risk_metrics 
                (asof_date, metric_name, metric_value, metric_category, lookback_days)
                VALUES (?, ?, ?, ?, ?)
                """,
                (asof_date, metric_name, float(metric_value) if metric_value is not None else None, 
                category, lookback_days)
            )
        cn.commit()
        
        # Refresh the Power BI table (risk_metrics_latest)
        cursor.execute("EXEC sp_refresh_risk_metrics_latest")
        cn.commit()
    
    print(f"Stored {len(metrics)} risk metrics for {asof_date}")
    return metrics

def main():
    """Calculate metrics for latest date"""
    metrics = calculate_and_store_all_metrics()
    
    # Print summary
    print("\n=== Risk Metrics Summary ===")
    for name, value, category, lookback in metrics:
        if value is not None:
            if 'Ratio' in name or 'Beta' in name:
                print(f"{name:25s}: {value:8.3f} ({category})")
            elif 'HHI' in name:
                print(f"{name:25s}: {value:8.0f} ({category})")
            else:
                print(f"{name:25s}: {value:8.4f} ({category})")

if __name__ == "__main__":
    main()
