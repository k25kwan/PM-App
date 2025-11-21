import pandas as pd
import numpy as np
from src.core.utils_db import get_conn
from datetime import date, timedelta

# risk-free rate (annualized)
RISK_FREE_RATE = 0.04 

def load_portfolio_returns(asof_date=None):

    # (FLAG): is v_portfolio_daily_returns the best place to pull these returns from?
    # this view was used before in powerbi but now i am using streamlit so im not sure if i still need this view
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

# (FLAG): can this be combined with load_portfolio_returns function?
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

# implement bond stuff later
# def load_bond_durations(asof_date=None):
#     """Load bond positions and their durations as of specified date"""
#     with get_conn() as cn:
#         if asof_date:
#             query = """
#             SELECT ticker, market_value, sector
#             FROM historical_portfolio_info
#             WHERE date = ?
#             AND sector LIKE '%Bond%'
#             """
#             df = pd.read_sql(query, cn, params=[asof_date])
#         else:
#             query = """
#             SELECT ticker, market_value, sector
#             FROM historical_portfolio_info
#             WHERE date = (SELECT MAX(date) FROM historical_portfolio_info)
#             AND sector LIKE '%Bond%'
#             """
#             df = pd.read_sql(query, cn)
#     return df

# ============================================================================
# MARKET RISK METRICS
# ============================================================================

def calculate_var_95(returns):
    var_95 = np.percentile(returns, 5)
    return var_95

def calculate_expected_shortfall(returns):
    var_95 = np.percentile(returns, 5)
    es = returns[returns <= var_95].mean()
    return es

def calculate_volatility(returns):
    daily_vol = returns.std()
    annualized_vol = daily_vol * np.sqrt(252)
    return annualized_vol

def calculate_sharpe_ratio(returns):    
    # annualized return
    cumulative_return = (1 + returns).prod() - 1
    annualized_return = (1 + cumulative_return) ** (252 / len(returns)) - 1
    
    # annualized volatility
    annualized_vol = returns.std() * np.sqrt(252)
    
    if annualized_vol == 0:
        return 0
    
    sharpe = (annualized_return - RISK_FREE_RATE) / annualized_vol
    return sharpe

def calculate_max_drawdown(returns):
    # calculate cumulative returns
    # (FLAG): step through this and make sure the calculation makes sense
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_dd = drawdown.min()
    return max_dd

# ============================================================================
# RELATIVE RISK METRICS (vs Benchmark)
# ============================================================================

def calculate_beta(portfolio_returns, benchmark_returns):
    # align dates
    merged = pd.merge(portfolio_returns, benchmark_returns, on='date', suffixes=('_port', '_bench'))
    
    covariance = merged['daily_return_port'].cov(merged['daily_return_bench'])
    benchmark_variance = merged['daily_return_bench'].var()
    
    if benchmark_variance == 0:
        return 0
    
    beta = covariance / benchmark_variance
    return beta

def calculate_tracking_error(portfolio_returns, benchmark_returns):
    merged = pd.merge(portfolio_returns, benchmark_returns, on='date', suffixes=('_port', '_bench'))
    
    # (FLAG): does this need to be an absolute value?
    active_returns = merged['daily_return_port'] - merged['daily_return_bench']
    tracking_error = active_returns.std() * np.sqrt(252)
    return tracking_error

# (FLAG): check this calculation
def calculate_information_ratio(portfolio_returns, benchmark_returns):
    merged = pd.merge(portfolio_returns, benchmark_returns, on='date', suffixes=('_port', '_bench'))
    
    active_returns = merged['daily_return_port'] - merged['daily_return_bench']
    cumulative_active = (1 + active_returns).prod() - 1
    annualized_active_return = (1 + cumulative_active) ** (252 / len(active_returns)) - 1

    tracking_error = active_returns.std() * np.sqrt(252)
    
    if tracking_error == 0:
        return 0
    
    info_ratio = annualized_active_return / tracking_error
    return info_ratio

def calculate_active_return(portfolio_returns, benchmark_returns):
    merged = pd.merge(portfolio_returns, benchmark_returns, on='date', suffixes=('_port', '_bench'))
    
    active_returns = merged['daily_return_port'] - merged['daily_return_bench']
    cumulative_active = (1 + active_returns).prod() - 1
    annualized_active_return = (1 + cumulative_active) ** (252 / len(active_returns)) - 1
    
    return annualized_active_return

# ============================================================================
# CONCENTRATION METRICS
# ============================================================================

def calculate_hhi(holdings_df):
    total_mv = holdings_df['market_value'].sum()
    if total_mv == 0:
        return 0
    
    weights = holdings_df['market_value'] / total_mv
    hhi = (weights ** 2).sum() * 10000
    return hhi

def calculate_sector_hhi(holdings_df):
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

# def calculate_dv01(bond_holdings_df):
#     """
#     Calculate DV01 (Dollar Value of 01 basis point)
#     Approximation using bond duration estimates
    
#     For simplicity, using approximate durations:
#     - US10Y (10-year treasury): ~9 years duration
#     - CORP5 (5-year corporate): ~4.5 years duration
#     - CAN10Y (10-year Canada): ~9 years duration
#     """
#     # Approximate modified durations
#     duration_map = {
#         'US10Y': 9.0,
#         'CORP5': 4.5,
#         'CAN10Y': 9.0
#     }
    
#     total_dv01 = 0
#     for _, row in bond_holdings_df.iterrows():
#         ticker = row['ticker']
#         mv = row['market_value']
        
#         if ticker in duration_map:
#             duration = duration_map[ticker]
#             # DV01 = Market Value * Modified Duration * 0.0001
#             dv01 = mv * duration * 0.0001
#             total_dv01 += dv01
    
#     return total_dv01

# ============================================================================
# MAIN CALCULATION AND STORAGE
# ============================================================================

def calculate_and_store_all_metrics(asof_date=None):
    if asof_date is None:
        asof_date = date.today()
    
    print(f"Calculating risk metrics as of {asof_date}...")
    
    # Load data up to asof_date for point-in-time calculations
    port_returns = load_portfolio_returns(asof_date)
    bench_returns = load_benchmark_returns(asof_date)
    holdings = load_portfolio_holdings(asof_date)
    # bond_holdings = load_bond_durations(asof_date)
    
    if len(port_returns) == 0:
        print(f"No portfolio returns data available as of {asof_date}")
        return []
    
    print(f"Using {len(port_returns)} days of return data (from {port_returns['date'].min()} to {port_returns['date'].max()})")
    
    metrics = []
    # uses all available days right now but this can be changed
    lookback_days = len(port_returns)
    
    # market risk
    returns_series = port_returns['daily_return']
    metrics.append(('VaR_95', calculate_var_95(returns_series), 'Market Risk', lookback_days))
    metrics.append(('Expected_Shortfall', calculate_expected_shortfall(returns_series), 'Market Risk', lookback_days))
    metrics.append(('Volatility_Ann', calculate_volatility(returns_series), 'Market Risk', lookback_days))
    metrics.append(('Sharpe_Ratio', calculate_sharpe_ratio(returns_series), 'Market Risk', lookback_days))
    metrics.append(('Max_Drawdown', calculate_max_drawdown(returns_series), 'Market Risk', lookback_days))
    
    # relative risk
    metrics.append(('Beta', calculate_beta(port_returns, bench_returns), 'Relative Risk', lookback_days))
    metrics.append(('Tracking_Error', calculate_tracking_error(port_returns, bench_returns), 'Relative Risk', lookback_days))
    metrics.append(('Information_Ratio', calculate_information_ratio(port_returns, bench_returns), 'Relative Risk', lookback_days))
    metrics.append(('Active_Return', calculate_active_return(port_returns, bench_returns), 'Relative Risk', lookback_days))
    
    # concentration metrics
    metrics.append(('HHI_Security', calculate_hhi(holdings), 'Concentration', None))
    metrics.append(('HHI_Sector', calculate_sector_hhi(holdings), 'Concentration', None))
    
    # # Duration Metrics (not time-dependent)
    # metrics.append(('DV01', calculate_dv01(bond_holdings), 'Duration', None))
    
    # Store in database
    with get_conn() as cn:
        cursor = cn.cursor()
        
        # Delete existing metrics for this date
        cursor.execute("DELETE FROM portfolio_risk_metrics WHERE asof_date = ?", (asof_date,))
        cn.commit()
        
        # Insert new metrics
        for metric_name, metric_value, category, lookback in metrics:
            cursor.execute(
                """
                INSERT INTO portfolio_risk_metrics 
                (asof_date, metric_name, metric_value, metric_category, lookback_days)
                VALUES (?, ?, ?, ?, ?)
                """,
                (asof_date, metric_name, float(metric_value) if metric_value is not None else None, 
                category, lookback)
            )
        cn.commit()
        
        #(FLAG): what is this for?
        # try:
        #     cursor.execute("EXEC sp_refresh_risk_metrics_latest")
        #     cn.commit()
        # except:
        #     pass 
    
    print(f"Stored {len(metrics)} risk metrics for {asof_date}")
    return metrics

def main():
    metrics = calculate_and_store_all_metrics()
    
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
