"""
Factor-based scoring system for equity screening

Calculates percentile ranks for all fundamental factors independently 
(no blending into composite score).

Focuses on fundamentals only:
- Profitability: ROE, Profit Margin, ROIC
- Growth: Revenue Growth, Earnings Growth
- Value: P/E, P/B, FCF Yield
- Safety: Debt/Equity, Current Ratio

Usage:
    from src.analytics.factor_scoring import score_stock_all_factors
    
    scores = score_stock_all_factors('AAPL')
    print(scores['roe_pct'])  # 85 = better than 85% of sector in ROE
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List


def calculate_z_score(
    value: float,
    all_values: List[float]
) -> float:
    """
    Calculate z-score (standard deviations from mean)
    
    Z-score normalizes values across different distributions:
    - z = 0: average
    - z = 1: one standard deviation above average
    - z = -1: one standard deviation below average
    
    This allows comparing stocks across sectors with different scales.
    
    Args:
        value: The stock's metric value
        all_values: All values across ALL sectors (not just one sector)
    
    Returns:
        Z-score (typically between -3 and +3)
    """
    if pd.isna(value) or not all_values or len(all_values) < 2:
        return 0.0
    
    clean_values = [v for v in all_values if not pd.isna(v)]
    
    if not clean_values or len(clean_values) < 2:
        return 0.0
    
    mean = np.mean(clean_values)
    std = np.std(clean_values)
    
    if std == 0:
        return 0.0
    
    z = (value - mean) / std
    return round(z, 3)


def calculate_percentile_rank(
    ticker_value: float,
    sector_values: List[float],
    lower_is_better: bool = False
) -> float:
    """
    Calculate percentile rank (0-100) for a metric vs sector peers
    
    Args:
        ticker_value: The stock's metric value
        sector_values: List of all sector peers' values
        lower_is_better: True for P/E, Debt/Equity (cheaper = better)
    
    Returns:
        0-100 percentile rank
        - 90 = better than 90% of sector
        - 50 = median
        - 10 = worse than 90% of sector
    
    Examples:
        >>> calculate_percentile_rank(15.5, [10, 12, 14, 16, 18, 20])
        >>> 66.67  # Better than 4 out of 6 stocks (66.67%)
        
        >>> calculate_percentile_rank(25, [10, 15, 20, 25, 30], lower_is_better=True)
        >>> 40  # Cheaper than 2 out of 5 (40% inverted from 60%)
    """
    
    if pd.isna(ticker_value) or not sector_values or len(sector_values) == 0:
        return 50.0  # Neutral if data missing
    
    # Remove NaN values from sector_values
    clean_sector_values = [v for v in sector_values if not pd.isna(v)]
    
    if not clean_sector_values:
        return 50.0
    
    # Calculate percentile (what % of sector is this stock better than)
    percentile = (np.array(clean_sector_values) < ticker_value).sum() / len(clean_sector_values) * 100
    
    # Invert if lower is better (e.g., P/E ratio - cheaper = better)
    if lower_is_better:
        percentile = 100 - percentile
    
    return round(percentile, 2)


def score_stock_from_info(
    ticker: str,
    info: Dict,
    sector_benchmarks: Dict = None
) -> Dict:
    """
    Calculate percentile ranks using pre-fetched yfinance info
    
    This version DOES NOT call yfinance - uses already-fetched data.
    Use this to avoid redundant API calls when you already have the data.
    
    Args:
        ticker: Stock symbol
        info: Pre-fetched yfinance info dict (from stock.info)
        sector_benchmarks: Optional pre-loaded sector benchmark data
    
    Returns:
        Dictionary with percentile rank (0-100) for every metric
        Returns None if data unavailable
    """
    
    try:
        sector = info.get('sector', 'Unknown')
        
        # Get sector distributions for percentile calculations
        sector_dist = {}
        all_sectors_dist = {}
        
        if sector_benchmarks:
            distributions = sector_benchmarks.get('distributions', {})
            sector_data = distributions.get(sector, {})
            sector_dist = sector_data.get('metrics', {})
            
            # Get cross-sector distributions (all stocks across all sectors)
            all_sectors_dist = sector_benchmarks.get('all_sectors', {})
        
        # === FUNDAMENTAL METRICS ===
        
        # Profitability
        roe = info.get('returnOnEquity')
        profit_margin = info.get('profitMargins')
        roic = info.get('returnOnAssets')  # Proxy for ROIC
        
        # Growth
        revenue_growth = info.get('revenueGrowth')
        earnings_growth = info.get('earningsGrowth')
        
        # Value
        pe = info.get('trailingPE')
        pb = info.get('priceToBook')
        market_cap = info.get('marketCap', 1)
        fcf = info.get('freeCashflow', 0)
        fcf_yield = (fcf / market_cap * 100) if market_cap > 0 else 0
        
        # Safety
        debt_equity = info.get('debtToEquity')
        current_ratio = info.get('currentRatio')
        
        # === CALCULATE PERCENTILES (vs sector peers) ===
        
        percentiles = {
            'ticker': ticker,
            'sector': sector,
            'market_cap': market_cap,
            
            # Profitability percentiles (higher = better)
            'roe_pct': calculate_percentile_rank(roe, sector_dist.get('roe', [])),
            'profit_margin_pct': calculate_percentile_rank(
                profit_margin, sector_dist.get('profit_margin', [])
            ),
            'roic_pct': calculate_percentile_rank(roic, sector_dist.get('roic', [])),
            
            # Growth percentiles (higher = better)
            'revenue_growth_pct': calculate_percentile_rank(
                revenue_growth, sector_dist.get('revenue_growth', [])
            ),
            'earnings_growth_pct': calculate_percentile_rank(
                earnings_growth, sector_dist.get('earnings_growth', [])
            ),
            
            # Value percentiles (LOWER is better - inverted)
            'pe_pct': calculate_percentile_rank(
                pe, sector_dist.get('pe', []), lower_is_better=True
            ),
            'pb_pct': calculate_percentile_rank(
                pb, sector_dist.get('pb', []), lower_is_better=True
            ),
            'fcf_yield_pct': calculate_percentile_rank(
                fcf_yield, sector_dist.get('fcf_yield', [])
            ),
            
            # Safety percentiles (lower debt = better, higher current ratio = better)
            'debt_equity_pct': calculate_percentile_rank(
                debt_equity, sector_dist.get('debt_equity', []), lower_is_better=True
            ),
            'current_ratio_pct': calculate_percentile_rank(
                current_ratio, sector_dist.get('current_ratio', [])
            ),
            
            # === CROSS-SECTOR Z-SCORES (for normalized comparison across all sectors) ===
            # Z-score = (value - mean) / std_dev across ALL S&P 500 stocks
            # Allows comparing stocks across sectors with different scales
            # Higher z-score = further above average (better for most metrics)
            
            'roe_zscore': calculate_z_score(roe, all_sectors_dist.get('roe', [])),
            'profit_margin_zscore': calculate_z_score(
                profit_margin, all_sectors_dist.get('profit_margin', [])
            ),
            'roic_zscore': calculate_z_score(roic, all_sectors_dist.get('roic', [])),
            'revenue_growth_zscore': calculate_z_score(
                revenue_growth, all_sectors_dist.get('revenue_growth', [])
            ),
            'earnings_growth_zscore': calculate_z_score(
                earnings_growth, all_sectors_dist.get('earnings_growth', [])
            ),
            # For P/E and debt: negate z-score since lower is better
            'pe_zscore': -1 * calculate_z_score(pe, all_sectors_dist.get('pe', [])),
            'pb_zscore': -1 * calculate_z_score(pb, all_sectors_dist.get('pb', [])),
            'fcf_yield_zscore': calculate_z_score(fcf_yield, all_sectors_dist.get('fcf_yield', [])),
            'debt_equity_zscore': -1 * calculate_z_score(
                debt_equity, all_sectors_dist.get('debt_equity', [])
            ),
            'current_ratio_zscore': calculate_z_score(
                current_ratio, all_sectors_dist.get('current_ratio', [])
            ),
            
            # Raw values (for reference)
            'raw_roe': roe,
            'raw_profit_margin': profit_margin,
            'raw_roic': roic,
            'raw_revenue_growth': revenue_growth,
            'raw_earnings_growth': earnings_growth,
            'raw_pe': pe,
            'raw_pb': pb,
            'raw_fcf_yield': fcf_yield,
            'raw_debt_equity': debt_equity,
            'raw_current_ratio': current_ratio
        }
        
        return percentiles
    
    except Exception as e:
        print(f"Error scoring {ticker}: {e}")
        return None


def score_stock_all_factors(
    ticker: str,
    sector_benchmarks: Dict = None
) -> Dict:
    """
    Calculate percentile ranks for ALL fundamental factors separately
    
    Focuses on fundamentals only:
    - Profitability: ROE, Profit Margin, ROIC
    - Growth: Revenue Growth, Earnings Growth
    - Value: P/E, P/B, FCF Yield
    - Safety: Debt/Equity, Current Ratio
    
    Args:
        ticker: Stock symbol
        sector_benchmarks: Optional pre-loaded sector benchmark data
                          (from DynamicSectorBenchmarks class)
    
    Returns:
        Dictionary with percentile rank (0-100) for every metric
        Returns None if data unavailable
        
    Note:
        NO blended composite score - keep factors independent for
        style-specific weighting later
    """
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        sector = info.get('sector', 'Unknown')
        
        # Get sector distributions for percentile calculations
        sector_dist = {}
        
        if sector_benchmarks:
            distributions = sector_benchmarks.get('distributions', {})
            sector_data = distributions.get(sector, {})
            sector_dist = sector_data.get('metrics', {})
        
        # If no benchmarks or sector not found, will use empty arrays (returns 50th percentile)
        
        # === FUNDAMENTAL METRICS ===
        
        # Profitability
        roe = info.get('returnOnEquity')
        profit_margin = info.get('profitMargins')
        roic = info.get('returnOnAssets')  # Proxy for ROIC
        
        # Growth
        revenue_growth = info.get('revenueGrowth')
        earnings_growth = info.get('earningsGrowth')
        
        # Value
        pe = info.get('trailingPE')
        pb = info.get('priceToBook')
        market_cap = info.get('marketCap', 1)
        fcf = info.get('freeCashflow', 0)
        fcf_yield = (fcf / market_cap * 100) if market_cap > 0 else 0
        
        # Safety
        debt_equity = info.get('debtToEquity')
        current_ratio = info.get('currentRatio')
        
        # === CALCULATE PERCENTILES (vs sector peers) ===
        
        percentiles = {
            'ticker': ticker,
            'sector': sector,
            'market_cap': market_cap,
            
            # Profitability percentiles (higher = better)
            'roe_pct': calculate_percentile_rank(roe, sector_dist.get('roe', [])),
            'profit_margin_pct': calculate_percentile_rank(
                profit_margin, sector_dist.get('profit_margin', [])
            ),
            'roic_pct': calculate_percentile_rank(roic, sector_dist.get('roic', [])),
            
            # Growth percentiles (higher = better)
            'revenue_growth_pct': calculate_percentile_rank(
                revenue_growth, sector_dist.get('revenue_growth', [])
            ),
            'earnings_growth_pct': calculate_percentile_rank(
                earnings_growth, sector_dist.get('earnings_growth', [])
            ),
            
            # Value percentiles (LOWER is better - inverted)
            'pe_pct': calculate_percentile_rank(
                pe, sector_dist.get('pe', []), lower_is_better=True
            ),
            'pb_pct': calculate_percentile_rank(
                pb, sector_dist.get('pb', []), lower_is_better=True
            ),
            'fcf_yield_pct': calculate_percentile_rank(
                fcf_yield, sector_dist.get('fcf_yield', [])
            ),
            
            # Safety percentiles (lower debt = better, higher current ratio = better)
            'debt_equity_pct': calculate_percentile_rank(
                debt_equity, sector_dist.get('debt_equity', []), lower_is_better=True
            ),
            'current_ratio_pct': calculate_percentile_rank(
                current_ratio, sector_dist.get('current_ratio', [])
            ),
            
            # Raw values (for reference)
            'raw_roe': roe,
            'raw_profit_margin': profit_margin,
            'raw_roic': roic,
            'raw_revenue_growth': revenue_growth,
            'raw_earnings_growth': earnings_growth,
            'raw_pe': pe,
            'raw_pb': pb,
            'raw_fcf_yield': fcf_yield,
            'raw_debt_equity': debt_equity,
            'raw_current_ratio': current_ratio
        }
        
        return percentiles
    
    except Exception as e:
        print(f"Error scoring {ticker}: {e}")
        return None


if __name__ == "__main__":
    # Test with a few stocks
    test_tickers = ['AAPL', 'MSFT', 'GOOGL']
    
    for ticker in test_tickers:
        print(f"\n{'='*60}")
        print(f"Scoring {ticker}")
        print(f"{'='*60}")
        
        scores = score_stock_all_factors(ticker)
        
        if scores:
            print(f"\nSector: {scores['sector']}")
            print(f"Market Cap: ${scores['market_cap']/1e9:.1f}B")
            print(f"\n--- Profitability ---")
            print(f"  ROE: {scores['raw_roe']:.2%} (Percentile: {scores['roe_pct']:.0f})")
            print(f"  Profit Margin: {scores['raw_profit_margin']:.2%} (Percentile: {scores['profit_margin_pct']:.0f})")
            print(f"  ROIC: {scores['raw_roic']:.2%} (Percentile: {scores['roic_pct']:.0f})")
            print(f"\n--- Growth ---")
            print(f"  Revenue Growth: {scores['raw_revenue_growth']:.2%} (Percentile: {scores['revenue_growth_pct']:.0f})")
            print(f"  Earnings Growth: {scores['raw_earnings_growth']:.2%} (Percentile: {scores['earnings_growth_pct']:.0f})")
            print(f"\n--- Value ---")
            print(f"  P/E: {scores['raw_pe']:.1f} (Percentile: {scores['pe_pct']:.0f})")
            print(f"  P/B: {scores['raw_pb']:.2f} (Percentile: {scores['pb_pct']:.0f})")
            print(f"  FCF Yield: {scores['raw_fcf_yield']:.2f}% (Percentile: {scores['fcf_yield_pct']:.0f})")
            print(f"\n--- Safety ---")
            print(f"  Debt/Equity: {scores['raw_debt_equity']:.1f} (Percentile: {scores['debt_equity_pct']:.0f})")
            print(f"  Current Ratio: {scores['raw_current_ratio']:.2f} (Percentile: {scores['current_ratio_pct']:.0f})")
