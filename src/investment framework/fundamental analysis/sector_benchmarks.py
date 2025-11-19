"""
Sector Benchmark System - Calculate percentile distributions from S&P 1500

Fetches all S&P 1500 stocks, groups by sector, and calculates distributions
for all fundamental metrics. Caches to disk for fast reuse.

Usage:
    from src.analytics.sector_benchmarks import SectorBenchmarks
    
    benchmarks = SectorBenchmarks()
    benchmarks.build_from_universe()  # Fetches S&P 1500, takes ~10 minutes
    
    # Use in scoring
    scores = score_stock_all_factors('AAPL', sector_benchmarks=benchmarks.data)
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from typing import Dict, List
from datetime import datetime


class SectorBenchmarks:
    """
    Calculate and cache sector-specific percentile distributions
    from S&P 1500 universe for accurate peer comparisons
    """
    
    def __init__(self, cache_file: str = 'data/sector_benchmarks_cache.json'):
        """
        Initialize sector benchmarks system
        
        Args:
            cache_file: Path to cache file for storing distributions
        """
        self.cache_file = cache_file
        self.data = None
        self.sp1500_tickers = None
        
    def get_sp1500_tickers(self) -> List[str]:
        """
        Get S&P 500 ticker list from Wikipedia (best available free source)
        
        S&P 500 provides ~500 large-cap stocks with good sector distribution:
        - Technology: 70-80 stocks
        - Healthcare: 60-70 stocks
        - Financials: 60-70 stocks
        - Consumer: 50-60 stocks
        - Industrials: 70-80 stocks
        - Energy: 20-30 stocks
        - Utilities: 30-40 stocks
        - Real Estate: 30-40 stocks
        - Materials: 25-30 stocks
        - Communication Services: 20-25 stocks
        
        All sectors have 20+ stocks = statistically valid benchmarks
        
        Returns:
            List of ticker symbols from S&P 500
        """
        
        print("\nFetching S&P 500 ticker list from Wikipedia...")
        
        try:
            # Fetch S&P 500 list from Wikipedia
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            
            # Add User-Agent header to avoid 403 Forbidden
            # We need to use urllib to set headers since storage_options doesn't work in all pandas versions
            import urllib.request
            
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            # Read tables with proper headers
            with urllib.request.urlopen(req) as response:
                tables = pd.read_html(response.read())
            
            print(f"Found {len(tables)} tables on Wikipedia")
            
            # Find the table with Symbol column (usually table index 1)
            sp500_table = None
            for i, table in enumerate(tables):
                if 'Symbol' in table.columns:
                    sp500_table = table
                    print(f"Found S&P 500 table at index {i} with {len(table)} stocks")
                    break
            
            if sp500_table is None:
                raise ValueError("Could not find Symbol column in Wikipedia tables")
            
            # Extract tickers
            tickers = sp500_table['Symbol'].tolist()
            
            # Clean tickers (remove any dots - yfinance uses dashes)
            tickers = [ticker.replace('.', '-') for ticker in tickers]
            
            print(f"Successfully fetched {len(tickers)} S&P 500 tickers from Wikipedia")
            
            return tickers
            
        except Exception as e:
            print(f"Error fetching S&P 500 list from Wikipedia: {e}")
            print("   Falling back to hardcoded sample...")
            
            # Fallback to expanded sample if Wikipedia fails
            fallback_tickers = [
                # Technology (expanded)
                'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'META', 'NVDA', 'AVGO', 'CSCO', 'ORCL', 'CRM',
                'ADBE', 'AMD', 'INTC', 'IBM', 'NOW', 'INTU', 'QCOM', 'TXN', 'AMAT', 'MU',
                'PANW', 'PLTR', 'SNOW', 'TEAM', 'DDOG', 'CRWD', 'ZS', 'NET', 'OKTA', 'FTNT',
                'DELL', 'HPQ', 'ACN', 'ACIW', 'ADSK', 'AEIS', 'AKAM', 'ALRM',
                
                # Healthcare (expanded)
                'UNH', 'JNJ', 'LLY', 'ABBV', 'MRK', 'PFE', 'TMO', 'ABT', 'DHR', 'CVS',
                'AMGN', 'GILD', 'BMY', 'ISRG', 'VRTX', 'CI', 'HUM', 'ELV', 'MCK', 'CAH',
                'REGN', 'BSX', 'MDT', 'SYK', 'BIIB', 'ZTS', 'EW', 'BDX', 'A', 'IQV',
                
                # Financial Services (expanded)
                'BRK-B', 'JPM', 'V', 'MA', 'BAC', 'WFC', 'MS', 'GS', 'BLK', 'SPGI',
                'C', 'AXP', 'SCHW', 'CB', 'MMC', 'PGR', 'AON', 'AFL', 'MET', 'ALL',
                'TFC', 'USB', 'PNC', 'COF', 'AIG', 'CME', 'ICE', 'MCO', 'TRV', 'AJG',
                
                # Consumer Cyclical (expanded)
                'AMZN', 'TSLA', 'HD', 'MCD', 'NKE', 'LOW', 'SBUX', 'TGT', 'TJX', 'CMG',
                'BKNG', 'MAR', 'ABNB', 'GM', 'F', 'YUM', 'DRI', 'ULTA', 'ROST', 'DHI',
                'LEN', 'POOL', 'RL', 'TPR', 'VFC', 'HAS', 'WHR', 'LULU', 'RCL', 'CCL',
                
                # Consumer Defensive (expanded)
                'WMT', 'PG', 'KO', 'PEP', 'COST', 'PM', 'MO', 'CL', 'MDLZ', 'GIS',
                'KHC', 'K', 'HSY', 'SYY', 'TSN', 'CAG', 'CPB', 'CHD', 'CLX', 'MKC',
                'KMB', 'KR', 'SJM', 'HRL', 'TAP', 'BF-B', 'EL', 'ADM', 'BG',
                
                # Industrials (expanded)
                'CAT', 'BA', 'HON', 'UNP', 'RTX', 'UPS', 'LMT', 'DE', 'GE', 'MMM',
                'FDX', 'NSC', 'EMR', 'ETN', 'ITW', 'PH', 'CSX', 'WM', 'RSG', 'PCAR',
                'NOC', 'GD', 'LHX', 'TDG', 'CARR', 'OTIS', 'ROK', 'AME', 'DOV', 'IR',
                
                # Energy (expanded)
                'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'PXD',
                'KMI', 'WMB', 'HAL', 'BKR', 'DVN', 'FANG', 'MRO', 'APA', 'CTRA', 'OVV',
                'OKE', 'TRGP', 'ET', 'EPD', 'LNG', 'CHRD', 'PR', 'EQT', 'CNX',
                
                # Utilities (expanded)
                'NEE', 'DUK', 'SO', 'D', 'AEP', 'EXC', 'SRE', 'XEL', 'ED', 'PEG',
                'ES', 'WEC', 'DTE', 'ETR', 'FE', 'CNP', 'AEE', 'CMS', 'NI', 'LNT',
                'ATO', 'AWK', 'PPL', 'VST', 'EVRG', 'PNW', 'IDA', 'NWE', 'OGE', 'SWX',
                
                # Real Estate (expanded)
                'PLD', 'AMT', 'EQIX', 'SPG', 'WELL', 'PSA', 'O', 'DLR', 'VICI', 'AVB',
                'EQR', 'SBAC', 'VTR', 'ARE', 'INVH', 'EXR', 'MAA', 'KIM', 'UDR', 'HST',
                'REG', 'BXP', 'FRT', 'ESS', 'CPT', 'AIV', 'ACC', 'BRX', 'SKT', 'ROIC',
                
                # Basic Materials (expanded)
                'LIN', 'APD', 'SHW', 'ECL', 'NEM', 'FCX', 'CTVA', 'DD', 'DOW', 'NUE',
                'VMC', 'MLM', 'ALB', 'BALL', 'AVY', 'IP', 'PKG', 'AMCR', 'SEE', 'MOS',
                'CF', 'FMC', 'EMN', 'CE', 'IFF', 'PPG', 'RPM', 'AXTA', 'HUN', 'OLN',
                
                # Communication Services (expanded)
                'META', 'GOOGL', 'GOOG', 'NFLX', 'DIS', 'CMCSA', 'VZ', 'T', 'TMUS', 'CHTR',
                'EA', 'TTWO', 'WBD', 'MTCH', 'NWSA', 'FOX', 'FOXA', 'OMC', 'IPG',
                'PINS', 'SNAP', 'ROKU', 'ZM', 'TWLO', 'SPOT', 'LYFT', 'UBER', 'DASH', 'ABNB'
            ]
            
            return list(set(fallback_tickers))
    
    def fetch_stock_fundamentals(self, ticker: str) -> Dict:
        """
        Fetch fundamental metrics for a single stock
        
        Args:
            ticker: Stock symbol
        
        Returns:
            Dictionary with fundamental metrics (or None if error)
        """
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Extract fundamentals
            market_cap = info.get('marketCap', 0)
            fcf = info.get('freeCashflow', 0)
            fcf_yield = (fcf / market_cap * 100) if market_cap > 0 else None
            
            fundamentals = {
                'ticker': ticker,
                'sector': info.get('sector', 'Unknown'),
                'industry': info.get('industry', 'Unknown'),
                
                # Profitability
                'roe': info.get('returnOnEquity'),
                'profit_margin': info.get('profitMargins'),
                'roic': info.get('returnOnAssets'),  # Proxy for ROIC
                
                # Growth
                'revenue_growth': info.get('revenueGrowth'),
                'earnings_growth': info.get('earningsGrowth'),
                
                # Value
                'pe': info.get('trailingPE'),
                'pb': info.get('priceToBook'),
                'fcf_yield': fcf_yield,
                
                # Safety
                'debt_equity': info.get('debtToEquity'),
                'current_ratio': info.get('currentRatio'),
                
                # Metadata
                'market_cap': market_cap
            }
            
            return fundamentals
            
        except Exception as e:
            print(f"  ⚠️  Error fetching {ticker}: {e}")
            return None
    
    def build_from_universe(self, max_stocks: int = None, min_sector_size: int = 20):
        """
        Build sector benchmarks from S&P 500 universe
        
        Args:
            max_stocks: Optional limit for testing (e.g., 50 stocks). 
                       If None, uses full S&P 500 (~500 stocks)
            min_sector_size: Minimum stocks per sector for valid benchmark (default: 20)
                            Sectors with fewer stocks will be flagged in output
        """
        
        print("\n" + "="*80)
        print("BUILDING SECTOR BENCHMARKS FROM S&P 500 UNIVERSE")
        print("="*80)
        
        # Get ticker list
        all_tickers = self.get_sp1500_tickers()
        
        if max_stocks:
            all_tickers = all_tickers[:max_stocks]
            print(f"⚠️  Limited to {max_stocks} stocks for testing")
        
        print(f"\nFetching fundamentals for {len(all_tickers)} stocks...")
        print(f"Estimated time: {len(all_tickers) * 0.5 / 60:.1f} minutes")
        print(f"Minimum sector size for valid benchmark: {min_sector_size} stocks\n")
        
        # Fetch all stocks
        stocks_data = []
        errors = 0
        
        for i, ticker in enumerate(all_tickers, 1):
            if i % 25 == 0 or i == len(all_tickers):
                print(f"  Progress: {i}/{len(all_tickers)} ({i/len(all_tickers)*100:.0f}%) - {len(stocks_data)} successful, {errors} errors")
            
            fundamentals = self.fetch_stock_fundamentals(ticker)
            
            if fundamentals and fundamentals['sector'] != 'Unknown':
                stocks_data.append(fundamentals)
            else:
                errors += 1
        
        print(f"\n✅ Successfully fetched {len(stocks_data)} stocks ({errors} errors/unknown sectors)")
        
        # Convert to DataFrame
        df = pd.DataFrame(stocks_data)
        
        # Show sector distribution
        print(f"\n{'='*80}")
        print("SECTOR DISTRIBUTION")
        print(f"{'='*80}")
        
        sector_counts = df['sector'].value_counts().sort_values(ascending=False)
        
        valid_sectors = 0
        warning_sectors = 0
        
        for sector, count in sector_counts.items():
            status = "✅" if count >= min_sector_size else "⚠️ "
            print(f"  {status} {sector:30s}: {count:3d} stocks")
            
            if count >= min_sector_size:
                valid_sectors += 1
            else:
                warning_sectors += 1
        
        print(f"\n  Valid sectors (≥{min_sector_size} stocks): {valid_sectors}")
        if warning_sectors > 0:
            print(f"  ⚠️  Warning: {warning_sectors} sectors with <{min_sector_size} stocks (less reliable benchmarks)")
        
        # Build sector distributions
        print(f"\n{'='*80}")
        print("CALCULATING SECTOR BENCHMARKS")
        print(f"{'='*80}\n")
        
        distributions = {}
        
        for sector in df['sector'].unique():
            sector_df = df[df['sector'] == sector]
            
            # Calculate how many stocks have each metric available
            metric_counts = {
                'roe': sector_df['roe'].notna().sum(),
                'profit_margin': sector_df['profit_margin'].notna().sum(),
                'roic': sector_df['roic'].notna().sum(),
                'revenue_growth': sector_df['revenue_growth'].notna().sum(),
                'earnings_growth': sector_df['earnings_growth'].notna().sum(),
                'pe': sector_df['pe'].notna().sum(),
                'pb': sector_df['pb'].notna().sum(),
                'fcf_yield': sector_df['fcf_yield'].notna().sum(),
                'debt_equity': sector_df['debt_equity'].notna().sum(),
                'current_ratio': sector_df['current_ratio'].notna().sum()
            }
            
            distributions[sector] = {
                'count': len(sector_df),
                'metric_counts': metric_counts,  # Track data availability
                'metrics': {
                    # Store arrays for percentile calculations
                    'roe': sector_df['roe'].dropna().tolist(),
                    'profit_margin': sector_df['profit_margin'].dropna().tolist(),
                    'roic': sector_df['roic'].dropna().tolist(),
                    'revenue_growth': sector_df['revenue_growth'].dropna().tolist(),
                    'earnings_growth': sector_df['earnings_growth'].dropna().tolist(),
                    'pe': sector_df['pe'].dropna().tolist(),
                    'pb': sector_df['pb'].dropna().tolist(),
                    'fcf_yield': sector_df['fcf_yield'].dropna().tolist(),
                    'debt_equity': sector_df['debt_equity'].dropna().tolist(),
                    'current_ratio': sector_df['current_ratio'].dropna().tolist()
                }
            }
            
            print(f"  {sector}: {len(sector_df)} stocks, avg {sum(metric_counts.values())/len(metric_counts):.0f} metrics per stock")
        
        # Build cross-sector distributions (all stocks combined for z-score normalization)
        print(f"\n{'='*80}")
        print("CALCULATING CROSS-SECTOR DISTRIBUTIONS (for normalized comparison)")
        print(f"{'='*80}\n")
        
        all_sectors = {
            'roe': df['roe'].dropna().tolist(),
            'profit_margin': df['profit_margin'].dropna().tolist(),
            'roic': df['roic'].dropna().tolist(),
            'revenue_growth': df['revenue_growth'].dropna().tolist(),
            'earnings_growth': df['earnings_growth'].dropna().tolist(),
            'pe': df['pe'].dropna().tolist(),
            'pb': df['pb'].dropna().tolist(),
            'fcf_yield': df['fcf_yield'].dropna().tolist(),
            'debt_equity': df['debt_equity'].dropna().tolist(),
            'current_ratio': df['current_ratio'].dropna().tolist()
        }
        
        print(f"  Cross-sector stats:")
        for metric, values in all_sectors.items():
            if values:
                print(f"    {metric:20s}: {len(values):3d} stocks, mean={np.mean(values):.3f}, std={np.std(values):.3f}")
        
        # Store in data attribute
        self.data = {
            'distributions': distributions,
            'all_sectors': all_sectors,  # NEW: Cross-sector distributions for z-score
            'metadata': {
                'total_stocks': len(stocks_data),
                'total_fetched': len(all_tickers),
                'errors': errors,
                'sectors': list(distributions.keys()),
                'created_at': datetime.now().isoformat(),
                'universe': 'S&P 500 (Wikipedia)' if not max_stocks else f'S&P 500 (limited to {max_stocks})',
                'min_sector_size': min_sector_size,
                'valid_sectors': valid_sectors,
                'warning_sectors': warning_sectors
            }
        }
        
        print(f"\n{'='*80}")
        print("✅ SECTOR BENCHMARKS BUILT SUCCESSFULLY")
        print(f"{'='*80}")
        print(f"   Total stocks: {len(stocks_data)} (from {len(all_tickers)} fetched)")
        print(f"   Sectors: {len(distributions)}")
        print(f"   Valid sectors (≥{min_sector_size} stocks): {valid_sectors}")
        if warning_sectors > 0:
            print(f"   ⚠️  Sectors with <{min_sector_size} stocks: {warning_sectors}")
        
        return self.data
    
    def save_to_cache(self):
        """Save distributions to cache file"""
        
        if not self.data:
            print("⚠️  No data to save. Run build_from_universe() first.")
            return
        
        # Create data directory if needed
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        
        # Convert numpy types to Python native types for JSON serialization
        def convert_to_native(obj):
            """Recursively convert numpy types to Python native types"""
            if isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(item) for item in obj]
            elif isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64)):
                return float(obj)
            else:
                return obj
        
        clean_data = convert_to_native(self.data)
        
        with open(self.cache_file, 'w') as f:
            json.dump(clean_data, f, indent=2)
        
        print(f"\n✅ Saved to cache: {self.cache_file}")
    
    def load_from_cache(self) -> bool:
        """
        Load distributions from cache file
        
        Returns:
            True if loaded successfully, False if cache doesn't exist
        """
        
        if not os.path.exists(self.cache_file):
            print(f"⚠️  Cache file not found: {self.cache_file}")
            return False
        
        with open(self.cache_file, 'r') as f:
            self.data = json.load(f)
        
        metadata = self.data.get('metadata', {})
        print(f"\nLoaded sector benchmarks from cache")
        print(f"   Created: {metadata.get('created_at', 'Unknown')}")
        print(f"   Total stocks: {metadata.get('total_stocks', 0)}")
        print(f"   Sectors: {len(metadata.get('sectors', []))}")
        
        return True
    
    def get_sector_distributions(self, sector: str) -> Dict:
        """
        Get metric distributions for a specific sector
        
        Args:
            sector: Sector name (e.g., 'Technology')
        
        Returns:
            Dictionary with metric arrays for percentile calculations
        """
        
        if not self.data:
            return {}
        
        distributions = self.data.get('distributions', {})
        sector_data = distributions.get(sector, {})
        
        return sector_data.get('metrics', {})
    
    def print_summary(self):
        """Print summary of benchmark data"""
        
        if not self.data:
            print("⚠️  No benchmark data loaded")
            return
        
        metadata = self.data.get('metadata', {})
        distributions = self.data.get('distributions', {})
        
        print("\n" + "="*80)
        print("SECTOR BENCHMARKS SUMMARY")
        print("="*80)
        
        print(f"\nMetadata:")
        print(f"  Created: {metadata.get('created_at', 'Unknown')}")
        print(f"  Universe: {metadata.get('universe', 'Unknown')}")
        print(f"  Total stocks: {metadata.get('total_stocks', 0)}")
        print(f"  Sectors: {len(distributions)}")
        
        print(f"\nSector Breakdown:")
        for sector, data in distributions.items():
            print(f"  {sector:30s}: {data['count']:3d} stocks")


if __name__ == "__main__":
    # Build sector benchmarks
    benchmarks = SectorBenchmarks()
    
    # Try to load from cache first
    if not benchmarks.load_from_cache():
        print("\nCache not found. Building from scratch...\n")
        
        # Build from FULL S&P 500 universe (~500 stocks, 4-5 minutes)
        # Set max_stocks=100 for quick testing, or None for full universe
        benchmarks.build_from_universe(max_stocks=None, min_sector_size=20)
        
        # Save to cache
        benchmarks.save_to_cache()
    
    # Print summary
    benchmarks.print_summary()
    
    # Test: Get Technology sector distributions
    print("\n" + "="*80)
    print("SAMPLE: Technology Sector Distributions")
    print("="*80)
    
    tech_dist = benchmarks.get_sector_distributions('Technology')
    
    if tech_dist:
        print(f"\nROE distribution (n={len(tech_dist.get('roe', []))}):")
        roe_values = tech_dist.get('roe', [])
        if roe_values:
            print(f"  Min:    {min(roe_values):.2%}")
            print(f"  25th:   {np.percentile(roe_values, 25):.2%}")
            print(f"  Median: {np.percentile(roe_values, 50):.2%}")
            print(f"  75th:   {np.percentile(roe_values, 75):.2%}")
            print(f"  Max:    {max(roe_values):.2%}")
        
        print(f"\nRevenue Growth distribution (n={len(tech_dist.get('revenue_growth', []))}):")
        growth_values = tech_dist.get('revenue_growth', [])
        if growth_values:
            print(f"  Min:    {min(growth_values):.2%}")
            print(f"  25th:   {np.percentile(growth_values, 25):.2%}")
            print(f"  Median: {np.percentile(growth_values, 50):.2%}")
            print(f"  75th:   {np.percentile(growth_values, 75):.2%}")
            print(f"  Max:    {max(growth_values):.2%}")
