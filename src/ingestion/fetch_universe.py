# (FLAG): is this file being used? this is the older code that does not just load from the s&p500

import pandas as pd
import requests
from pathlib import Path
from datetime import datetime, timedelta
import json

CACHE_DIR = Path(__file__).parent.parent.parent / "data"
CACHE_DIR.mkdir(exist_ok=True)

UNIVERSE_CACHE = CACHE_DIR / "ticker_universe.csv"
CACHE_METADATA = CACHE_DIR / "universe_metadata.json"


def is_cache_valid(max_age_days=7):
    if not UNIVERSE_CACHE.exists() or not CACHE_METADATA.exists():
        return False
    
    try:
        with open(CACHE_METADATA, 'r') as f:
            metadata = json.load(f)
        
        cache_date = datetime.fromisoformat(metadata['updated_at'])
        age = datetime.now() - cache_date
        
        return age.days < max_age_days
    except Exception:
        return False


def fetch_nasdaq_listed_stocks():
    url = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt"
    
    try:
        # NASDAQ provides pipe-delimited file
        df = pd.read_csv(url, sep='|')
        
        # Clean up - remove footer row and filter
        df = df[df['Symbol'] != 'File Creation Time']
        
        # Remove test symbols
        df = df[~df['Symbol'].str.contains(r'\^|\$|\.', na=False)]
        
        # Select relevant columns
        df = df[['Symbol', 'Security Name', 'Market Category', 'Test Issue', 'Financial Status']]
        df.columns = ['ticker', 'name', 'market', 'test_issue', 'financial_status']
        
        # Filter out test issues and bankrupt companies
        df = df[df['test_issue'] == 'N']
        df = df[df['financial_status'] == 'N']  # N = Normal (not deficient)
        
        df['exchange'] = 'NASDAQ'
        df['asset_class'] = 'Equity'
        
        return df[['ticker', 'name', 'exchange', 'asset_class']]
    
    except Exception as e:
        print(f"Error fetching NASDAQ stocks: {e}")
        return pd.DataFrame()


def fetch_nyse_listed_stocks():
    """
    Fetch all NYSE-listed stocks from NASDAQ FTP (yes, NASDAQ hosts NYSE data too)
    """
    url = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt"
    
    try:
        df = pd.read_csv(url, sep='|')
        
        # Clean up
        df = df[df['ACT Symbol'] != 'File Creation Time']
        
        # Remove test symbols and ETFs (ETFs handled separately)
        df = df[~df['ACT Symbol'].str.contains(r'\^|\$|\.', na=False)]
        df = df[df['ETF'] == 'N']  # N = Not an ETF
        df = df[df['Test Issue'] == 'N']
        
        # Select relevant columns
        df = df[['ACT Symbol', 'Security Name', 'Exchange']]
        df.columns = ['ticker', 'name', 'exchange']
        
        # Map exchange codes
        exchange_map = {'A': 'NYSE MKT', 'N': 'NYSE', 'P': 'NYSE Arca', 'Z': 'BATS', 'V': 'IEX'}
        df['exchange'] = df['exchange'].map(exchange_map)
        
        df['asset_class'] = 'Equity'
        
        return df[['ticker', 'name', 'exchange', 'asset_class']]
    
    except Exception as e:
        print(f"Error fetching NYSE stocks: {e}")
        return pd.DataFrame()


def fetch_etf_list():
    """
    Fetch comprehensive ETF list from NASDAQ FTP
    """
    url = "ftp://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt"
    
    try:
        df = pd.read_csv(url, sep='|')
        df = df[df['ACT Symbol'] != 'File Creation Time']
        
        # Filter for ETFs only
        df = df[df['ETF'] == 'Y']
        df = df[df['Test Issue'] == 'N']
        
        df = df[['ACT Symbol', 'Security Name', 'Exchange']]
        df.columns = ['ticker', 'name', 'exchange']
        
        exchange_map = {'A': 'NYSE MKT', 'N': 'NYSE', 'P': 'NYSE Arca', 'Z': 'BATS', 'V': 'IEX'}
        df['exchange'] = df['exchange'].map(exchange_map)
        
        df['asset_class'] = 'ETF'
        
        return df[['ticker', 'name', 'exchange', 'asset_class']]
    
    except Exception as e:
        print(f"Error fetching ETF list: {e}")
        return pd.DataFrame()


def fetch_canadian_stocks():
    """
    Fetch major Canadian stocks (TSX)
    Uses a curated list since TSX doesn't have free FTP access
    """
    # Top 100 TSX stocks by market cap (manually curated - this could be expanded)
    tickers = [
        "RY.TO", "TD.TO", "SHOP.TO", "ENB.TO", "CNR.TO", "BNS.TO", "BMO.TO", "CM.TO", 
        "CNQ.TO", "TRP.TO", "ABX.TO", "CP.TO", "SU.TO", "MFC.TO", "BCE.TO", "BAM.TO",
        "CVE.TO", "NTR.TO", "WCN.TO", "SLF.TO", "FNV.TO", "IMO.TO", "QSR.TO", "ATD.TO",
        "WPM.TO", "PPL.TO", "GWO.TO", "TOU.TO", "CCL-B.TO", "FM.TO", "AEM.TO", "CCO.TO",
        "DOL.TO", "POW.TO", "MGA.TO", "AQN.TO", "TIH.TO", "FTS.TO", "EMA.TO", "TRI.TO",
        "WCN.TO", "SJR-B.TO", "T.TO", "CSU.TO", "IFC.TO", "SNC.TO", "KEY.TO", "KL.TO"
    ]
    
    df = pd.DataFrame({
        'ticker': tickers,
        'name': tickers,  # Would need lookup for actual names
        'exchange': 'TSX',
        'asset_class': 'Equity'
    })
    
    return df


def load_ticker_universe(asset_class=None, force_refresh=False):
    """
    Load comprehensive ticker universe from cached file or fetch from source
    
    Args:
        asset_class: Filter by 'Equity', 'ETF', or None for all
        force_refresh: Force re-download even if cache is valid
    
    Returns:
        DataFrame with columns: ticker, name, exchange, asset_class
    """
    
    # Use cache if valid
    if not force_refresh and is_cache_valid():
        print("Loading ticker universe from cache...")
        df = pd.read_csv(UNIVERSE_CACHE)
    else:
        print("Fetching fresh ticker universe from external sources...")
        
        # Fetch from all sources
        nasdaq_stocks = fetch_nasdaq_listed_stocks()
        nyse_stocks = fetch_nyse_listed_stocks()
        etfs = fetch_etf_list()
        canadian = fetch_canadian_stocks()
        
        # Combine all
        df = pd.concat([nasdaq_stocks, nyse_stocks, etfs, canadian], ignore_index=True)
        
        # Remove duplicates
        df = df.drop_duplicates(subset=['ticker'])
        
        # Save cache
        df.to_csv(UNIVERSE_CACHE, index=False)
        
        # Save metadata
        metadata = {
            'updated_at': datetime.now().isoformat(),
            'total_securities': len(df),
            'nasdaq_stocks': len(nasdaq_stocks),
            'nyse_stocks': len(nyse_stocks),
            'etfs': len(etfs),
            'canadian_stocks': len(canadian)
        }
        
        with open(CACHE_METADATA, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Cached {len(df)} securities")
    
    # Filter by asset class if requested
    if asset_class:
        df = df[df['asset_class'] == asset_class]
    
    return df


def get_universe_stats():
    """Get statistics about cached universe"""
    if not CACHE_METADATA.exists():
        return None
    
    with open(CACHE_METADATA, 'r') as f:
        metadata = json.load(f)
    
    return metadata


if __name__ == "__main__":
    # Test the module
    print("Fetching ticker universe...")
    df = load_ticker_universe(force_refresh=True)
    
    print(f"\nTotal securities: {len(df)}")
    print(f"\nBreakdown by asset class:")
    print(df['asset_class'].value_counts())
    
    print(f"\nBreakdown by exchange:")
    print(df['exchange'].value_counts())
    
    print(f"\nSample securities:")
    print(df.head(10))
    
    stats = get_universe_stats()
    print(f"\nCache metadata:")
    print(json.dumps(stats, indent=2))
