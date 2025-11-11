"""
Portfolio Attribution Analysis

Implements Brinson-Fachler attribution model to decompose active returns into:
- Allocation Effect: Sector timing/weighting decisions
- Selection Effect: Security selection within sectors
- Interaction Effect: Combined allocation + selection

Calculates attribution for:
- Total Portfolio vs Blended Benchmark
- Equity-Only vs Equity Benchmark
- Fixed Income-Only vs Bond Benchmark
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
from src.core.utils_db import get_conn

# Asset class mappings
EQUITY_SECTORS = ['Tech', 'Financials', 'US Broad', 'Canada Broad']  # Changed 'Technology' to 'Tech'
FIXED_INCOME_SECTORS = ['CAN Bonds', 'US Bonds']

def load_portfolio_data(asof_date):
    """
    Load portfolio positions with sector weights and returns for attribution calculation
    
    Returns DataFrame with columns:
    - sector, market_value, weight, daily_return
    """
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
    
    # Calculate sector weights
    total_mv = df['market_value'].sum()
    df['weight'] = df['market_value'] / total_mv if total_mv > 0 else 0
    
    return df

def load_benchmark_data(asof_date):
    """
    Load benchmark composite returns by sector
    
    Returns DataFrame with columns:
    - sector, weight, daily_return
    """
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
        return df
    
    # Map benchmark tickers to sectors manually (since not all benchmarks have sector in securities)
    sector_mapping = {
        'XLK': 'Tech',  # Changed from 'Technology' to match portfolio sector naming
        'XFN.TO': 'Financials',
        'SPY': 'US Broad',
        'XIC.TO': 'Canada Broad',
        'XBB.TO': 'CAN Bonds',
        'AGG': 'US Bonds'
    }
    
    df['sector'] = df['ticker'].map(sector_mapping)
    
    # Calculate equal-weighted sector returns (6 benchmarks, equal weight)
    # Group by sector and average returns
    sector_returns = df.groupby('sector')['daily_return'].mean().reset_index()
    
    # Equal weight across 6 benchmarks means each sector's weight in total benchmark
    sector_returns['weight'] = 1.0 / len(sector_mapping)  # 1/6 each
    
    return sector_returns[['sector', 'weight', 'daily_return']]

def calculate_attribution(portfolio_df, benchmark_df, attribution_type='TOTAL'):
    """
    Calculate Brinson-Fachler attribution effects
    
    Formula:
    - Allocation Effect = (Wp - Wb) × (Rb - R_benchmark_total)
    - Selection Effect = Wb × (Rp - Rb)
    - Interaction Effect = (Wp - Wb) × (Rp - Rb)
    
    Where:
    - Wp = Portfolio weight in sector
    - Wb = Benchmark weight in sector
    - Rp = Portfolio return in sector
    - Rb = Benchmark return in sector
    - R_benchmark_total = Total benchmark return
    """
    
    # Merge portfolio and benchmark data on sector
    merged = portfolio_df.merge(
        benchmark_df,
        on='sector',
        how='outer',
        suffixes=('_portfolio', '_benchmark')
    )
    
    # Fill missing values with 0 (sector not present in portfolio or benchmark)
    merged['weight_portfolio'] = merged['weight_portfolio'].fillna(0)
    merged['weight_benchmark'] = merged['weight_benchmark'].fillna(0)
    merged['daily_return_portfolio'] = merged['daily_return_portfolio'].fillna(0)
    merged['daily_return_benchmark'] = merged['daily_return_benchmark'].fillna(0)
    
    # Calculate total benchmark return (weighted average)
    total_benchmark_return = (merged['weight_benchmark'] * merged['daily_return_benchmark']).sum()
    
    # Brinson Attribution Components
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
    
    # Add metadata
    merged['total_benchmark_return'] = total_benchmark_return
    merged['attribution_type'] = attribution_type
    
    # Rename columns for clarity
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
    Calculate attribution for all three types (TOTAL, EQUITY, FIXED_INCOME)
    and store in portfolio_attribution table
    """
    if asof_date is None:
        asof_date = date.today()
    
    if isinstance(asof_date, str):
        asof_date = pd.to_datetime(asof_date).date()
    
    print(f"Calculating attribution as of {asof_date}...")
    
    # Load data
    portfolio_df = load_portfolio_data(asof_date)
    benchmark_df = load_benchmark_data(asof_date)
    
    if portfolio_df.empty:
        print(f"No portfolio data for {asof_date}, skipping...")
        return
    
    if benchmark_df.empty:
        print(f"No benchmark data for {asof_date}, skipping...")
        return
    
    # Skip days with near-zero returns (stale prices)
    # Calculate portfolio and benchmark total returns
    portfolio_total_return = (portfolio_df['daily_return'] * portfolio_df['weight']).sum()
    benchmark_total_return = (benchmark_df['daily_return'] * benchmark_df['weight']).sum()
    
    # Skip if both returns are < 1 bp (0.0001 in decimal)
    if abs(portfolio_total_return) < 0.0001 and abs(benchmark_total_return) < 0.0001:
        print(f"Skipping {asof_date} - both portfolio and benchmark returns < 1bp (likely stale prices)")
        return
    
    attribution_results = []
    
    # 1. TOTAL Portfolio Attribution
    total_attribution = calculate_attribution(portfolio_df, benchmark_df, 'TOTAL')
    attribution_results.append(total_attribution)
    
    # 2. EQUITY Attribution
    portfolio_equity = portfolio_df[portfolio_df['sector'].isin(EQUITY_SECTORS)].copy()
    benchmark_equity = benchmark_df[benchmark_df['sector'].isin(EQUITY_SECTORS)].copy()
    
    if not portfolio_equity.empty and not benchmark_equity.empty:
        # Renormalize weights for equity-only universe
        portfolio_equity['weight'] = portfolio_equity['weight'] / portfolio_equity['weight'].sum()
        benchmark_equity['weight'] = benchmark_equity['weight'] / benchmark_equity['weight'].sum()
        
        equity_attribution = calculate_attribution(portfolio_equity, benchmark_equity, 'EQUITY')
        attribution_results.append(equity_attribution)
    
    # 3. FIXED INCOME Attribution
    portfolio_fi = portfolio_df[portfolio_df['sector'].isin(FIXED_INCOME_SECTORS)].copy()
    benchmark_fi = benchmark_df[benchmark_df['sector'].isin(FIXED_INCOME_SECTORS)].copy()
    
    if not portfolio_fi.empty and not benchmark_fi.empty:
        # Renormalize weights for fixed income-only universe
        portfolio_fi['weight'] = portfolio_fi['weight'] / portfolio_fi['weight'].sum()
        benchmark_fi['weight'] = benchmark_fi['weight'] / benchmark_fi['weight'].sum()
        
        fi_attribution = calculate_attribution(portfolio_fi, benchmark_fi, 'FIXED_INCOME')
        attribution_results.append(fi_attribution)
    
    # Combine all results
    all_attribution = pd.concat(attribution_results, ignore_index=True)
    
    # Store in database
    with get_conn() as cn:
        cursor = cn.cursor()
        
        # Delete existing records for this date
        cursor.execute(
            "DELETE FROM portfolio_attribution WHERE asof_date = ? AND lookback_days = ?",
            asof_date, lookback_days
        )
        
        # Insert new records
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
    
    # Print summary
    summary = all_attribution.groupby('attribution_type').agg({
        'allocation_effect': 'sum',
        'selection_effect': 'sum',
        'interaction_effect': 'sum'
    })
    summary['total_active_return'] = summary.sum(axis=1)
    
    print("\nAttribution Summary:")
    print(summary)
    print()

def load_portfolio_monthly_data(end_date, lookback_days=30):
    """
    Load portfolio positions with sector weights and PERIOD returns for monthly attribution
    
    Returns DataFrame with columns:
    - sector, avg_market_value, weight, period_return
    """
    start_date = (pd.to_datetime(end_date) - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    
    with get_conn() as cn:
        query = """
        SELECT 
            sector,
            AVG(market_value) AS avg_market_value,
            -- Calculate period return: (1 + r1) * (1 + r2) * ... - 1
            EXP(SUM(LOG(1 + daily_return))) - 1 AS period_return
        FROM historical_portfolio_info
        WHERE date > ? AND date <= ?
            AND sector IS NOT NULL
            AND market_value IS NOT NULL
            AND daily_return IS NOT NULL
        GROUP BY sector
        """
        df = pd.read_sql(query, cn, params=[start_date, end_date])
    
    if df.empty:
        return df
    
    # Calculate sector weights based on average market value over period
    total_mv = df['avg_market_value'].sum()
    df['weight'] = df['avg_market_value'] / total_mv if total_mv > 0 else 0
    
    return df[['sector', 'weight', 'period_return']]

def load_benchmark_monthly_data(end_date, lookback_days=30):
    """
    Load benchmark composite PERIOD returns by sector
    
    Returns DataFrame with columns:
    - sector, weight, period_return
    """
    start_date = (pd.to_datetime(end_date) - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    
    with get_conn() as cn:
        query = """
        SELECT 
            db.ticker,
            -- Calculate period return: (1 + r1) * (1 + r2) * ... - 1
            EXP(SUM(LOG(1 + hbi.daily_return))) - 1 AS period_return
        FROM historical_benchmark_info hbi
        JOIN dim_benchmarks db ON hbi.ticker = db.ticker
        WHERE hbi.date > ? AND hbi.date <= ?
            AND hbi.daily_return IS NOT NULL
        GROUP BY db.ticker
        """
        df = pd.read_sql(query, cn, params=[start_date, end_date])
    
    if df.empty:
        return df
    
    # Map benchmark tickers to sectors
    sector_mapping = {
        'XLK': 'Tech',  # Changed from 'Technology' to match portfolio sector naming
        'XFN.TO': 'Financials',
        'SPY': 'US Broad',
        'XIC.TO': 'Canada Broad',
        'XBB.TO': 'CAN Bonds',
        'AGG': 'US Bonds'
    }
    
    df['sector'] = df['ticker'].map(sector_mapping)
    df['weight'] = 1.0 / len(sector_mapping)  # Equal weight
    
    return df[['sector', 'weight', 'period_return']]

def calculate_monthly_attribution(end_date, lookback_days=30):
    """
    Calculate monthly (or period-based) attribution using period returns
    Similar to daily attribution but uses compounded returns over the period
    """
    print(f"\nCalculating MONTHLY attribution for period ending {end_date} ({lookback_days} days)...")
    
    # Load monthly data
    portfolio_df = load_portfolio_monthly_data(end_date, lookback_days)
    benchmark_df = load_benchmark_monthly_data(end_date, lookback_days)
    
    if portfolio_df.empty:
        print(f"No portfolio data for period ending {end_date}, skipping...")
        return
    
    if benchmark_df.empty:
        print(f"No benchmark data for period ending {end_date}, skipping...")
        return
    
    # Skip periods with near-zero returns
    portfolio_total_return = (portfolio_df['period_return'] * portfolio_df['weight']).sum()
    benchmark_total_return = (benchmark_df['period_return'] * benchmark_df['weight']).sum()
    
    if abs(portfolio_total_return) < 0.0001 and abs(benchmark_total_return) < 0.0001:
        print(f"Skipping period ending {end_date} - both portfolio and benchmark returns < 1bp")
        return
    
    attribution_results = []
    
    # Rename columns to match daily attribution function expectations
    portfolio_df = portfolio_df.rename(columns={'period_return': 'daily_return'})
    benchmark_df = benchmark_df.rename(columns={'period_return': 'daily_return'})
    
    # 1. TOTAL Portfolio Attribution
    total_attribution = calculate_attribution(portfolio_df, benchmark_df, 'TOTAL')
    attribution_results.append(total_attribution)
    
    # 2. EQUITY Attribution
    portfolio_equity = portfolio_df[portfolio_df['sector'].isin(EQUITY_SECTORS)].copy()
    benchmark_equity = benchmark_df[benchmark_df['sector'].isin(EQUITY_SECTORS)].copy()
    
    if not portfolio_equity.empty and not benchmark_equity.empty:
        portfolio_equity['weight'] = portfolio_equity['weight'] / portfolio_equity['weight'].sum()
        benchmark_equity['weight'] = benchmark_equity['weight'] / benchmark_equity['weight'].sum()
        
        equity_attribution = calculate_attribution(portfolio_equity, benchmark_equity, 'EQUITY')
        attribution_results.append(equity_attribution)
    
    # 3. FIXED INCOME Attribution
    portfolio_fi = portfolio_df[portfolio_df['sector'].isin(FIXED_INCOME_SECTORS)].copy()
    benchmark_fi = benchmark_df[benchmark_df['sector'].isin(FIXED_INCOME_SECTORS)].copy()
    
    if not portfolio_fi.empty and not benchmark_fi.empty:
        portfolio_fi['weight'] = portfolio_fi['weight'] / portfolio_fi['weight'].sum()
        benchmark_fi['weight'] = benchmark_fi['weight'] / benchmark_fi['weight'].sum()
        
        fi_attribution = calculate_attribution(portfolio_fi, benchmark_fi, 'FIXED_INCOME')
        attribution_results.append(fi_attribution)
    
    # Combine all results
    all_attribution = pd.concat(attribution_results, ignore_index=True)
    
    # Store in database
    with get_conn() as cn:
        cursor = cn.cursor()
        
        # Delete existing monthly records for this date
        cursor.execute(
            "DELETE FROM portfolio_attribution WHERE asof_date = ? AND lookback_days = ?",
            end_date, lookback_days
        )
        
        # Insert new records
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
                end_date,
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
    
    print(f"Stored {len(all_attribution)} MONTHLY attribution records for period ending {end_date}")
    
    # Print summary
    summary = all_attribution.groupby('attribution_type').agg({
        'allocation_effect': 'sum',
        'selection_effect': 'sum',
        'interaction_effect': 'sum'
    })
    summary['total_active_return'] = summary.sum(axis=1)
    
    print("\nMonthly Attribution Summary:")
    print(summary)
    print()

if __name__ == '__main__':
    # Calculate attribution for today
    calculate_and_store_attribution()
