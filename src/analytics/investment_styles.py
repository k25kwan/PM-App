"""
Investment style definitions and style-specific scoring

Defines 4 investment styles (growth, value, quality, balanced)
with different factor weights and minimum thresholds.

Focuses on fundamentals only - no technical analysis or sentiment.

Usage:
    from src.analytics.investment_styles import get_top_stocks_by_style, rank_stocks_by_style_cached
    
    # Original (fetches data):
    top_growth = get_top_stocks_by_style(clean_stocks, style='growth', top_n=10)
    
    # New (uses pre-computed factor scores):
    top_growth = rank_stocks_by_style_cached(factor_scores_dict, style='growth', top_n=10)
"""

import pandas as pd
from typing import List, Dict
from src.analytics.factor_scoring import score_stock_all_factors


# Investment Style Configurations (FUNDAMENTALS ONLY)
INVESTMENT_STYLES = {
    
    'growth': {
        'name': 'High Growth',
        'description': 'Fast-growing companies with strong revenue/earnings expansion',
        'ideal_for': 'Bull markets, tech-heavy portfolios, risk-tolerant investors',
        
        'weights': {
            'revenue_growth_pct': 0.35,      # Primary focus on revenue growth
            'earnings_growth_pct': 0.25,     # And earnings expansion
            'profit_margin_pct': 0.20,       # With improving margins
            'roe_pct': 0.20                  # Some profitability
        },
        
        'min_thresholds': {
            'revenue_growth_pct': 50         # Top half in revenue growth (REQUIRED)
        },
        
        'examples': ['Nvidia (2015-2020)', 'Tesla (2019-2021)', 'Shopify', 'CrowdStrike']
    },
    
    'value': {
        'name': 'Deep Value',
        'description': 'Undervalued stocks with strong fundamentals trading below intrinsic value',
        'ideal_for': 'Bear markets, defensive portfolios, value investors',
        
        'weights': {
            'pe_pct': 0.30,                  # Low P/E (already inverted - higher = cheaper)
            'pb_pct': 0.25,                  # Low P/B
            'fcf_yield_pct': 0.25,           # High FCF yield
            'roe_pct': 0.10,                 # Still profitable
            'current_ratio_pct': 0.10        # Financial safety
        },
        
        'min_thresholds': {
            'roe_pct': 40,                   # Must be profitable (top 60%)
            'pe_pct': 40,                    # Must be cheaper than median
            'current_ratio_pct': 30          # Basic liquidity
        },
        
        'examples': ['Berkshire Hathaway picks', 'Coca-Cola', 'Johnson & Johnson', 'Procter & Gamble']
    },
    
    'quality': {
        'name': 'Quality Compounders',
        'description': 'High ROE, strong margins, low debt, sustainable competitive advantages',
        'ideal_for': 'Long-term hold, core portfolio positions, low-turnover strategies',
        
        'weights': {
            'roe_pct': 0.35,                 # High returns on equity (PRIMARY)
            'roic_pct': 0.25,                # High ROIC (capital efficiency)
            'profit_margin_pct': 0.25,       # Strong margins
            'debt_equity_pct': 0.15          # Low leverage
        },
        
        'min_thresholds': {
            'roe_pct': 70,                   # Top 30% in returns (REQUIRED)
            'debt_equity_pct': 50,           # Bottom half of leverage
            'profit_margin_pct': 60          # Strong margins
        },
        
        'examples': ['Microsoft', 'Apple', 'Visa', 'Mastercard', 'Adobe', "Moody's"]
    },
    
    'balanced': {
        'name': 'Balanced (GARP - Growth At Reasonable Price)',
        'description': 'Mix of growth, value, quality - Peter Lynch style',
        'ideal_for': 'Most investors, diversified portfolios, all market conditions',
        
        'weights': {
            'revenue_growth_pct': 0.20,      # Moderate growth
            'roe_pct': 0.20,                 # Profitability
            'pe_pct': 0.20,                  # Reasonable valuation
            'profit_margin_pct': 0.20,       # Quality
            'fcf_yield_pct': 0.10,           # Cash generation
            'debt_equity_pct': 0.10          # Financial safety
        },
        
        'min_thresholds': {
            'revenue_growth_pct': 40,        # Some growth
            'roe_pct': 40                    # Some profitability
        },
        
        'examples': ['S&P 500 core holdings', 'Diversified portfolios', 'Index-beating strategies']
    }
}


def rank_stocks_by_style_cached(
    factor_scores_dict: Dict[str, Dict],
    style: str = 'balanced',
    sector: str = None,
    top_n: int = 10
) -> pd.DataFrame:
    """
    Rank stocks using pre-computed factor scores (NO yfinance calls)
    
    This is the FAST version - uses factor scores already calculated
    during screening. Much faster than get_top_stocks_by_style().
    
    Args:
        factor_scores_dict: Dict mapping ticker -> factor_scores
                           e.g., {'AAPL': {...scores...}, 'MSFT': {...scores...}}
        style: 'growth', 'value', 'quality', or 'balanced'
        sector: Optional - filter to single sector
        top_n: Number of stocks to return
    
    Returns:
        DataFrame with top N stocks sorted by style score
        
    Example:
        >>> # After screening, you have factor_scores for all stocks
        >>> factor_scores = {ticker: scores for ticker, scores in ...}
        >>> top_growth = rank_stocks_by_style_cached(factor_scores, style='growth', top_n=10)
    """
    
    # Validate style
    if style not in INVESTMENT_STYLES:
        raise ValueError(f"Invalid style '{style}'. Choose from: {list(INVESTMENT_STYLES.keys())}")
    
    # Get style configuration
    style_config = INVESTMENT_STYLES[style]
    weights = style_config['weights']
    min_thresholds = style_config['min_thresholds']
    
    results = []
    
    for ticker, factor_scores in factor_scores_dict.items():
        if not factor_scores:
            continue
        
        # Filter by sector if specified
        if sector and factor_scores.get('sector') != sector:
            continue
        
        # Apply minimum thresholds
        passes_threshold = all(
            factor_scores.get(metric, 0) >= min_val 
            for metric, min_val in min_thresholds.items()
        )
        
        if not passes_threshold:
            continue
        
        # Calculate weighted score for this style
        style_score = sum(
            factor_scores.get(metric, 50) * weight 
            for metric, weight in weights.items()
        )
        
        # Store result
        results.append({
            'ticker': ticker,
            'sector': factor_scores.get('sector'),
            'market_cap': factor_scores.get('market_cap'),
            'style_score': round(style_score, 2),
            
            # Include key percentiles for review
            'roe_pct': factor_scores.get('roe_pct'),
            'revenue_growth_pct': factor_scores.get('revenue_growth_pct'),
            'pe_pct': factor_scores.get('pe_pct'),
            'profit_margin_pct': factor_scores.get('profit_margin_pct'),
            'debt_equity_pct': factor_scores.get('debt_equity_pct'),
            
            # Raw values
            'raw_roe': factor_scores.get('raw_roe'),
            'raw_revenue_growth': factor_scores.get('raw_revenue_growth'),
            'raw_pe': factor_scores.get('raw_pe'),
        })
    
    # Sort by style score
    df = pd.DataFrame(results)
    
    if df.empty:
        return pd.DataFrame()
    
    df_sorted = df.sort_values('style_score', ascending=False)
    
    return df_sorted.head(top_n)


def get_top_stocks_by_style(
    screened_stocks: List[str],
    style: str = 'balanced',
    sector: str = None,
    top_n: int = 10,
    sector_benchmarks: Dict = None
) -> pd.DataFrame:
    """
    Rank stocks using style-specific weights (fundamentals only)
    
    Args:
        screened_stocks: List of tickers that passed red flags
        style: 'growth', 'value', 'quality', or 'balanced'
        sector: Optional - filter to single sector (e.g., 'Technology')
        top_n: Number of stocks to return
        sector_benchmarks: Optional pre-loaded sector benchmark data
    
    Returns:
        DataFrame with top N stocks sorted by style score
        
    Example:
        >>> clean_stocks = screen_red_flags(sp1500_tickers)
        >>> top_growth = get_top_stocks_by_style(clean_stocks, style='growth', top_n=10)
        >>> print(top_growth[['ticker', 'sector', 'style_score', 'revenue_growth_pct']])
    """
    
    # Validate style
    if style not in INVESTMENT_STYLES:
        raise ValueError(f"Invalid style '{style}'. Choose from: {list(INVESTMENT_STYLES.keys())}")
    
    # Get style configuration
    style_config = INVESTMENT_STYLES[style]
    weights = style_config['weights']
    min_thresholds = style_config['min_thresholds']
    
    results = []
    
    print(f"\nScoring {len(screened_stocks)} stocks using '{style}' style...")
    print(f"Minimum thresholds: {min_thresholds}")
    
    for i, ticker in enumerate(screened_stocks):
        if (i + 1) % 100 == 0:
            print(f"  Processed {i+1}/{len(screened_stocks)} stocks...")
        
        try:
            # Calculate all factor percentiles
            factor_scores = score_stock_all_factors(ticker, sector_benchmarks)
            
            if not factor_scores:
                continue
            
            # Filter by sector if specified
            if sector and factor_scores['sector'] != sector:
                continue
            
            # Apply minimum thresholds
            passes_threshold = all(
                factor_scores.get(metric, 0) >= min_val 
                for metric, min_val in min_thresholds.items()
            )
            
            if not passes_threshold:
                continue  # Skip stocks that don't meet minimums
            
            # Calculate weighted score for this style
            style_score = sum(
                factor_scores.get(metric, 50) * weight 
                for metric, weight in weights.items()
            )
            
            # Store result
            results.append({
                'ticker': ticker,
                'sector': factor_scores['sector'],
                'market_cap': factor_scores['market_cap'],
                'style_score': round(style_score, 2),
                
                # Include key percentiles for review
                'roe_pct': factor_scores.get('roe_pct'),
                'revenue_growth_pct': factor_scores.get('revenue_growth_pct'),
                'pe_pct': factor_scores.get('pe_pct'),
                'return_6m_pct': factor_scores.get('return_6m_pct'),
                'news_sentiment_pct': factor_scores.get('news_sentiment_pct'),
                
                # Raw values
                'raw_roe': factor_scores.get('raw_roe'),
                'raw_revenue_growth': factor_scores.get('raw_revenue_growth'),
                'raw_pe': factor_scores.get('raw_pe'),
                'raw_return_6m': factor_scores.get('raw_return_6m'),
                
                # All percentiles (for detailed analysis)
                'all_percentiles': factor_scores
            })
        
        except Exception as e:
            print(f"  Error scoring {ticker}: {e}")
            continue
    
    # Sort by style score
    df = pd.DataFrame(results)
    
    if df.empty:
        print(f"\n⚠️  No stocks passed thresholds for '{style}' style")
        if sector:
            print(f"   (filtered to sector: {sector})")
        return pd.DataFrame()
    
    df_sorted = df.sort_values('style_score', ascending=False)
    
    print(f"\n✅ {len(df_sorted)} stocks passed thresholds")
    print(f"   Returning top {min(top_n, len(df_sorted))} stocks\n")
    
    return df_sorted.head(top_n)


def get_sector_balanced_top_10(
    screened_stocks: List[str],
    style: str = 'balanced',
    sectors: List[str] = None,
    sector_benchmarks: Dict = None
) -> pd.DataFrame:
    """
    Get top 2 stocks from each sector (for diversification)
    
    Args:
        screened_stocks: List of tickers that passed red flags
        style: Investment style to use for scoring
        sectors: List of sectors (default: top 5 sectors)
        sector_benchmarks: Optional pre-loaded sector benchmark data
    
    Returns:
        DataFrame with 10 stocks (2 per sector)
        
    Example:
        >>> clean_stocks = screen_red_flags(sp1500_tickers)
        >>> top_diversified = get_sector_balanced_top_10(clean_stocks, style='balanced')
        >>> print(top_diversified[['ticker', 'sector', 'style_score']])
    """
    
    if not sectors:
        # Default: Technology, Healthcare, Financials, Consumer, Industrials
        sectors = [
            'Technology',
            'Healthcare',
            'Financial Services',
            'Consumer Cyclical',
            'Industrials'
        ]
    
    all_picks = []
    
    print(f"\nBuilding sector-balanced portfolio ({len(sectors)} sectors, 2 stocks each)...\n")
    
    for sector in sectors:
        print(f"  Sector: {sector}")
        
        # Get top 2 stocks for this sector
        sector_top = get_top_stocks_by_style(
            screened_stocks,
            style=style,
            sector=sector,
            top_n=2,
            sector_benchmarks=sector_benchmarks
        )
        
        if not sector_top.empty:
            all_picks.append(sector_top)
            print(f"    ✅ Found {len(sector_top)} stocks")
        else:
            print(f"    ⚠️  No stocks found")
    
    # Combine all sectors
    if all_picks:
        result = pd.concat(all_picks, ignore_index=True)
        result = result.sort_values('style_score', ascending=False)
        
        print(f"\n✅ Total portfolio: {len(result)} stocks across {len(all_picks)} sectors\n")
        
        return result
    else:
        print(f"\n⚠️  No stocks found across any sector\n")
        return pd.DataFrame()


def print_style_summary():
    """Print summary of all available investment styles"""
    
    print("\n" + "="*80)
    print("AVAILABLE INVESTMENT STYLES")
    print("="*80)
    
    for style_key, style_config in INVESTMENT_STYLES.items():
        print(f"\n{style_key.upper()}: {style_config['name']}")
        print(f"  {style_config['description']}")
        print(f"  Ideal for: {style_config['ideal_for']}")
        
        print(f"\n  Factor Weights:")
        for factor, weight in style_config['weights'].items():
            print(f"    {factor:25s}: {weight*100:5.1f}%")
        
        print(f"\n  Minimum Thresholds:")
        for metric, threshold in style_config['min_thresholds'].items():
            print(f"    {metric:25s}: {threshold:5.0f}th percentile")
        
        print(f"\n  Examples: {', '.join(style_config['examples'])}")
        print(f"  {'-'*78}")


if __name__ == "__main__":
    # Print style summary
    print_style_summary()
    
    # Test with a few stocks
    test_tickers = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'META', 'TSLA', 'AMZN', 'PFE', 'JNJ', 'KO']
    
    print(f"\n\n{'='*80}")
    print(f"TESTING STYLE SCORING (FUNDAMENTALS ONLY)")
    print(f"{'='*80}")
    
    # Test each style
    for style in ['growth', 'value', 'quality', 'balanced']:
        print(f"\n\nTesting '{style}' style:")
        print(f"{'-'*80}")
        
        top_stocks = get_top_stocks_by_style(test_tickers, style=style, top_n=3)
        
        if not top_stocks.empty:
            print(f"\nTop 3 {style} stocks:")
            print(top_stocks[['ticker', 'sector', 'style_score', 
                            'revenue_growth_pct', 'roe_pct', 'pe_pct']].to_string(index=False))
