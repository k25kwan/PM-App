import pandas as pd
import numpy as np
from datetime import date, timedelta
from src.core.utils_db import get_conn

# asset class mappings hard coded for now but can add in the future
EQUITY_SECTORS = ['Tech', 'Financials', 'US Broad', 'Canada Broad']
FIXED_INCOME_SECTORS = ['CAN Bonds', 'US Bonds']

# get sector data from portfolio
def load_portfolio_data(asof_date):
    with get_conn() as cn:
        query = """
        SELECT 
            sector,
            SUM(market_value) AS market_value,
            AVG(daily_return) AS daily_return  -- Sector return is market-value weighted average
        FROM historical_portfolio_info
        WHERE date = ?
            AND sector IS NOT NULL
            AND market_value IS NOT NULL
        GROUP BY sector
        """
        df = pd.read_sql(query, cn, params=[asof_date])
    
    if df.empty:
        return df
    
    # calculate sector weights
    total_mv = df['market_value'].sum()
    df['weight'] = df['market_value'] / total_mv if total_mv > 0 else 0
    
    # return df has columns sector, market_value, daily_return, weight
    return df

def load_benchmark_data(asof_date):
    with get_conn() as cn:
        # Get benchmark holdings with their sectors
        query = """
        SELECT 
            db.ticker,
            ds.sector,
            hbi.daily_return
        FROM historical_benchmark_info hbi
        JOIN dim_benchmarks db ON hbi.ticker = db.ticker
        LEFT JOIN dim_securities ds ON db.ticker = ds.ticker  -- Map to sector via securities table
        WHERE hbi.date = ?
            AND hbi.daily_return IS NOT NULL
        """
        df = pd.read_sql(query, cn, params=[asof_date])
    
    if df.empty:
        # columns are sector, weight, daily_return
        return df
    
    # map benchmark tickers to sectors manually (since not all benchmarks have sector in securities)
    # this is for the demo only. will need a more robust mapping in production (FLAG). or just add more to the map
    sector_mapping = {
        'XLK': 'Tech',
        'XFN.TO': 'Financials',
        'SPY': 'US Broad',
        'XIC.TO': 'Canada Broad',
        'XBB.TO': 'CAN Bonds',
        'AGG': 'US Bonds'
    }
    
    df['sector'] = df['ticker'].map(sector_mapping)
    
    # calculate equal-weighted sector returns (6 benchmarks, equal weight)
    sector_returns = df.groupby('sector')['daily_return'].mean().reset_index()
    
    # equal weight across 6 benchmarks means each sector's weight in total benchmark
    # CHANGE THIS (FLAG): this should match the portfolio weights
    sector_returns['weight'] = 1.0 / len(sector_mapping)
    
    return sector_returns[['sector', 'weight', 'daily_return']]

def calculate_attribution(portfolio_df, benchmark_df, attribution_type='TOTAL'):
    """
    calculate Brinson-Fachler attribution effects
    
    formula:
    - allocation Effect = (Wp - Wb) × (Rb - R_benchmark_total)
    - selection Effect = Wb × (Rp - Rb)
    - interaction Effect = (Wp - Wb) × (Rp - Rb)
    
    where:
    - Wp = portfolio weight in sector
    - Wb = benchmark weight in sector
    - Rp = portfolio return in sector
    - Rb = benchmark return in sector
    - R_benchmark_total = total benchmark return
    """
    
    # merge portfolio and benchmark data on sector
    # other columns: weight_portfolio, daily_return_portfolio, weight_benchmark, daily_return_benchmark
    merged = portfolio_df.merge(
        benchmark_df,
        on='sector',
        how='outer',
        suffixes=('_portfolio', '_benchmark')
    )
    
    # fill missing values with 0 (sector not present in portfolio or benchmark)
    merged['weight_portfolio'] = merged['weight_portfolio'].fillna(0)
    merged['weight_benchmark'] = merged['weight_benchmark'].fillna(0)
    merged['daily_return_portfolio'] = merged['daily_return_portfolio'].fillna(0)
    merged['daily_return_benchmark'] = merged['daily_return_benchmark'].fillna(0)
    
    # calculate total benchmark return (weighted average)
    total_benchmark_return = (merged['weight_benchmark'] * merged['daily_return_benchmark']).sum()
    
    # brinson attribution components
    merged['allocation_effect'] = (
        (merged['weight_portfolio'] - merged['weight_benchmark']) 
        * (merged['daily_return_benchmark'] - total_benchmark_return)
    )
    
    merged['selection_effect'] = (
        merged['weight_benchmark'] 
        * (merged['daily_return_portfolio'] - merged['daily_return_benchmark'])
    )
    
    merged['interaction_effect'] = (
        (merged['weight_portfolio'] - merged['weight_benchmark']) 
        * (merged['daily_return_portfolio'] - merged['daily_return_benchmark'])
    )
    
    merged['total_benchmark_return'] = total_benchmark_return
    merged['attribution_type'] = attribution_type
    
    result = merged.rename(columns={
        'weight_portfolio': 'portfolio_weight',
        'weight_benchmark': 'benchmark_weight',
        'daily_return_portfolio': 'portfolio_return',
        'daily_return_benchmark': 'benchmark_return'
    })
    
    return result[[
        'sector', 'attribution_type',
        'allocation_effect', 'selection_effect', 'interaction_effect',
        'portfolio_weight', 'benchmark_weight',
        'portfolio_return', 'benchmark_return', 'total_benchmark_return'
    ]]

def calculate_and_store_attribution(asof_date=None, lookback_days=1):
    """
    calculate attribution for all three types (TOTAL, EQUITY, FIXED_INCOME)
    and store in portfolio_attribution table
    """
    if asof_date is None:
        asof_date = date.today()
    
    if isinstance(asof_date, str):
        asof_date = pd.to_datetime(asof_date).date()
    
    portfolio_df = load_portfolio_data(asof_date)
    benchmark_df = load_benchmark_data(asof_date)
    
    # portfolio_total_return = (portfolio_df['daily_return'] * portfolio_df['weight']).sum()
    # benchmark_total_return = (benchmark_df['daily_return'] * benchmark_df['weight']).sum()
    
    # if abs(portfolio_total_return) < 0.0001 and abs(benchmark_total_return) < 0.0001:
    #     print(f"Skipping {asof_date} - both portfolio and benchmark returns < 1bp (likely stale prices)")
    #     return
    
    attribution_results = []
    
    # 1. TOTAL Portfolio Attribution
    total_attribution = calculate_attribution(portfolio_df, benchmark_df, 'TOTAL')
    attribution_results.append(total_attribution)
    
    # 2. EQUITY Attribution
    portfolio_equity = portfolio_df[portfolio_df['sector'].isin(EQUITY_SECTORS)].copy()
    benchmark_equity = benchmark_df[benchmark_df['sector'].isin(EQUITY_SECTORS)].copy()
    
    if not portfolio_equity.empty and not benchmark_equity.empty:
        # renormalize weights for equity-only universe
        portfolio_equity['weight'] = portfolio_equity['weight'] / portfolio_equity['weight'].sum()
        benchmark_equity['weight'] = benchmark_equity['weight'] / benchmark_equity['weight'].sum()
        
        equity_attribution = calculate_attribution(portfolio_equity, benchmark_equity, 'EQUITY')
        attribution_results.append(equity_attribution)
    
    # # 3. FIXED INCOME Attribution
    # portfolio_fi = portfolio_df[portfolio_df['sector'].isin(FIXED_INCOME_SECTORS)].copy()
    # benchmark_fi = benchmark_df[benchmark_df['sector'].isin(FIXED_INCOME_SECTORS)].copy()
    
    # if not portfolio_fi.empty and not benchmark_fi.empty:
    #     # renormalize weights for fixed income-only universe
    #     portfolio_fi['weight'] = portfolio_fi['weight'] / portfolio_fi['weight'].sum()
    #     benchmark_fi['weight'] = benchmark_fi['weight'] / benchmark_fi['weight'].sum()
        
    #     fi_attribution = calculate_attribution(portfolio_fi, benchmark_fi, 'FIXED_INCOME')
    #     attribution_results.append(fi_attribution)
    
    # combine all results
    all_attribution = pd.concat(attribution_results, ignore_index=True)
    
    with get_conn() as cn:
        cursor = cn.cursor()
        
        # clear attribution records for this date and lookback_days
        cursor.execute(
            "DELETE FROM portfolio_attribution WHERE asof_date = ? AND lookback_days = ?",
            asof_date, lookback_days
        )
        
        insert_query = """
        INSERT INTO portfolio_attribution (
            asof_date, attribution_type, sector,
            allocation_effect, selection_effect, interaction_effect,
            portfolio_weight, benchmark_weight,
            portfolio_return, benchmark_return, total_benchmark_return,
            lookback_days
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        for _, row in all_attribution.iterrows():
            cursor.execute(insert_query,
                asof_date,
                row['attribution_type'],
                row['sector'],
                float(row['allocation_effect']) if pd.notna(row['allocation_effect']) else None,
                float(row['selection_effect']) if pd.notna(row['selection_effect']) else None,
                float(row['interaction_effect']) if pd.notna(row['interaction_effect']) else None,
                float(row['portfolio_weight']) if pd.notna(row['portfolio_weight']) else None,
                float(row['benchmark_weight']) if pd.notna(row['benchmark_weight']) else None,
                float(row['portfolio_return']) if pd.notna(row['portfolio_return']) else None,
                float(row['benchmark_return']) if pd.notna(row['benchmark_return']) else None,
                float(row['total_benchmark_return']) if pd.notna(row['total_benchmark_return']) else None,
                lookback_days
            )
        
        cn.commit()
    
    print(f"Stored {len(all_attribution)} attribution records for {asof_date}")
    
    summary = all_attribution.groupby('attribution_type').agg({
        'allocation_effect': 'sum',
        'selection_effect': 'sum',
        'interaction_effect': 'sum'
    })
    
    # (FLAG): this is not getting seen in the UI
    summary['total_active_return'] = summary.sum(axis=1)
    
    print("\nAttribution Summary:")
    print(summary)
    print()

# # (FLAG): can eventually be removed (select start date and end date)
# def load_portfolio_monthly_data(end_date, lookback_days=30):
#     start_date = (pd.to_datetime(end_date) - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    
#     with get_conn() as cn:
#         query = """
#         SELECT 
#             sector,
#             AVG(market_value) AS avg_market_value,
#             -- Calculate period return: (1 + r1) * (1 + r2) * ... - 1
#             EXP(SUM(LOG(1 + daily_return))) - 1 AS period_return
#         FROM historical_portfolio_info
#         WHERE date > ? AND date <= ?
#             AND sector IS NOT NULL
#             AND market_value IS NOT NULL
#             AND daily_return IS NOT NULL
#         GROUP BY sector
#         """
#         df = pd.read_sql(query, cn, params=[start_date, end_date])
    
#     if df.empty:
#         return df
    
#     total_mv = df['avg_market_value'].sum()
#     df['weight'] = df['avg_market_value'] / total_mv if total_mv > 0 else 0
    
#     return df[['sector', 'weight', 'period_return']]

# # (FLAG): can eventually be removed (select start date and end date)
# def load_benchmark_monthly_data(end_date, lookback_days=30):
#     start_date = (pd.to_datetime(end_date) - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    
#     with get_conn() as cn:
#         query = """
#         SELECT 
#             db.ticker,
#             -- Calculate period return: (1 + r1) * (1 + r2) * ... - 1
#             EXP(SUM(LOG(1 + hbi.daily_return))) - 1 AS period_return
#         FROM historical_benchmark_info hbi
#         JOIN dim_benchmarks db ON hbi.ticker = db.ticker
#         WHERE hbi.date > ? AND hbi.date <= ?
#             AND hbi.daily_return IS NOT NULL
#         GROUP BY db.ticker
#         """
#         df = pd.read_sql(query, cn, params=[start_date, end_date])
    
#     if df.empty:
#         return df
    
#     sector_mapping = {
#         'XLK': 'Tech',  
#         'XFN.TO': 'Financials',
#         'SPY': 'US Broad',
#         'XIC.TO': 'Canada Broad',
#         'XBB.TO': 'CAN Bonds',
#         'AGG': 'US Bonds'
#     }
    
#     df['sector'] = df['ticker'].map(sector_mapping)
#     df['weight'] = 1.0 / len(sector_mapping)  # Equal weight
    
#     return df[['sector', 'weight', 'period_return']]

# def calculate_monthly_attribution(end_date, lookback_days=30):
#     print(f"\nCalculating MONTHLY attribution for period ending {end_date} ({lookback_days} days)...")
    
#     # Load monthly data
#     portfolio_df = load_portfolio_monthly_data(end_date, lookback_days)
#     benchmark_df = load_benchmark_monthly_data(end_date, lookback_days)
    
#     if portfolio_df.empty:
#         print(f"No portfolio data for period ending {end_date}, skipping...")
#         return
    
#     if benchmark_df.empty:
#         print(f"No benchmark data for period ending {end_date}, skipping...")
#         return
    
#     # Skip periods with near-zero returns
#     portfolio_total_return = (portfolio_df['period_return'] * portfolio_df['weight']).sum()
#     benchmark_total_return = (benchmark_df['period_return'] * benchmark_df['weight']).sum()
    
#     if abs(portfolio_total_return) < 0.0001 and abs(benchmark_total_return) < 0.0001:
#         print(f"Skipping period ending {end_date} - both portfolio and benchmark returns < 1bp")
#         return
    
#     attribution_results = []
    
#     # Rename columns to match daily attribution function expectations
#     portfolio_df = portfolio_df.rename(columns={'period_return': 'daily_return'})
#     benchmark_df = benchmark_df.rename(columns={'period_return': 'daily_return'})
    
#     # 1. TOTAL Portfolio Attribution
#     total_attribution = calculate_attribution(portfolio_df, benchmark_df, 'TOTAL')
#     attribution_results.append(total_attribution)
    
#     # 2. EQUITY Attribution
#     portfolio_equity = portfolio_df[portfolio_df['sector'].isin(EQUITY_SECTORS)].copy()
#     benchmark_equity = benchmark_df[benchmark_df['sector'].isin(EQUITY_SECTORS)].copy()
    
#     if not portfolio_equity.empty and not benchmark_equity.empty:
#         portfolio_equity['weight'] = portfolio_equity['weight'] / portfolio_equity['weight'].sum()
#         benchmark_equity['weight'] = benchmark_equity['weight'] / benchmark_equity['weight'].sum()
        
#         equity_attribution = calculate_attribution(portfolio_equity, benchmark_equity, 'EQUITY')
#         attribution_results.append(equity_attribution)
    
#     # 3. FIXED INCOME Attribution
#     portfolio_fi = portfolio_df[portfolio_df['sector'].isin(FIXED_INCOME_SECTORS)].copy()
#     benchmark_fi = benchmark_df[benchmark_df['sector'].isin(FIXED_INCOME_SECTORS)].copy()
    
#     if not portfolio_fi.empty and not benchmark_fi.empty:
#         portfolio_fi['weight'] = portfolio_fi['weight'] / portfolio_fi['weight'].sum()
#         benchmark_fi['weight'] = benchmark_fi['weight'] / benchmark_fi['weight'].sum()
        
#         fi_attribution = calculate_attribution(portfolio_fi, benchmark_fi, 'FIXED_INCOME')
#         attribution_results.append(fi_attribution)
    
#     # Combine all results
#     all_attribution = pd.concat(attribution_results, ignore_index=True)
    
#     # Store in database
#     with get_conn() as cn:
#         cursor = cn.cursor()
        
#         # Delete existing monthly records for this date
#         cursor.execute(
#             "DELETE FROM portfolio_attribution WHERE asof_date = ? AND lookback_days = ?",
#             end_date, lookback_days
#         )
        
#         # Insert new records
#         insert_query = """
#         INSERT INTO portfolio_attribution (
#             asof_date, attribution_type, sector,
#             allocation_effect, selection_effect, interaction_effect,
#             portfolio_weight, benchmark_weight,
#             portfolio_return, benchmark_return, total_benchmark_return,
#             lookback_days
#         ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#         """
        
#         for _, row in all_attribution.iterrows():
#             cursor.execute(insert_query,
#                 end_date,
#                 row['attribution_type'],
#                 row['sector'],
#                 float(row['allocation_effect']) if pd.notna(row['allocation_effect']) else None,
#                 float(row['selection_effect']) if pd.notna(row['selection_effect']) else None,
#                 float(row['interaction_effect']) if pd.notna(row['interaction_effect']) else None,
#                 float(row['portfolio_weight']) if pd.notna(row['portfolio_weight']) else None,
#                 float(row['benchmark_weight']) if pd.notna(row['benchmark_weight']) else None,
#                 float(row['portfolio_return']) if pd.notna(row['portfolio_return']) else None,
#                 float(row['benchmark_return']) if pd.notna(row['benchmark_return']) else None,
#                 float(row['total_benchmark_return']) if pd.notna(row['total_benchmark_return']) else None,
#                 lookback_days
#             )
        
#         cn.commit()
    
#     print(f"Stored {len(all_attribution)} MONTHLY attribution records for period ending {end_date}")
    
#     # Print summary
#     summary = all_attribution.groupby('attribution_type').agg({
#         'allocation_effect': 'sum',
#         'selection_effect': 'sum',
#         'interaction_effect': 'sum'
#     })
#     summary['total_active_return'] = summary.sum(axis=1)
    
#     print("\nMonthly Attribution Summary:")
#     print(summary)
#     print()

if __name__ == '__main__':
    # Calculate attribution for today
    calculate_and_store_attribution()
