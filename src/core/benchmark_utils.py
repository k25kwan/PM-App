# each sector is matched to a representative index/ETF
SECTOR_BENCHMARK_MAPPING = {
    "Tech": "QQQ",           # Invesco QQQ Trust (Nasdaq-100)
    "Technology": "QQQ",     # Alternative naming
    
    "Consumer": "XLY",       # Consumer Discretionary Select Sector SPDR
    "Consumer Discretionary": "XLY",
    "Consumer Cyclical": "XLY",
    
    "Consumer Defensive": "XLP",  # Consumer Staples Select Sector SPDR
    "Consumer Staples": "XLP",
    
    "Financials": "XLF",     # Financial Select Sector SPDR
    "Financial Services": "XLF",
    
    "US Broad": "SPY",       # SPDR S&P 500 ETF Trust
    "Broad Market": "SPY",
    
    "Crypto": "BTC-USD",     # Bitcoin USD
    "Cryptocurrency": "BTC-USD",
    
    "Canada": "XIC.TO",      # iShares Core S&P/TSX Capped Composite
    "Canada Broad": "XIC.TO",
    
    "US Bonds": "AGG",       # iShares Core U.S. Aggregate Bond ETF
    "Bonds": "AGG",
    "Fixed Income": "AGG",
    
    "CAN Bonds": "XBB.TO",   # iShares Core Canadian Universe Bond Index ETF
    "Canada Bonds": "XBB.TO",
    
    "Healthcare": "XLV",     # Health Care Select Sector SPDR
    "Health Care": "XLV",
    
    "Energy": "XLE",         # Energy Select Sector SPDR
    
    "Utilities": "XLU",      # Utilities Select Sector SPDR
    
    "Industrials": "XLI",    # Industrial Select Sector SPDR
    
    "Materials": "XLB",      # Materials Select Sector SPDR
    "Basic Materials": "XLB",
    
    "Real Estate": "XLRE",   # Real Estate Select Sector SPDR
    
    "Communication Services": "XLC",  # Communication Services Select Sector SPDR
}

def get_benchmark_for_sector(sector):
# get benchmark ticker for a given sector, SPY is default
    return SECTOR_BENCHMARK_MAPPING.get(sector, "SPY")

def get_portfolio_benchmark_composition(portfolio_holdings):
    # calculate sector weights
    total_value = portfolio_holdings['market_value'].sum()
    sector_weights = portfolio_holdings.groupby('sector')['market_value'].sum() / total_value
    
    # map sectors to benchmarks
    benchmark_weights = {}
    for sector, weight in sector_weights.items():
        benchmark = get_benchmark_for_sector(sector)
        if benchmark in benchmark_weights:
            benchmark_weights[benchmark] += weight
        else:
            benchmark_weights[benchmark] = weight
    
    return benchmark_weights

def get_benchmark_name(ticker):
    benchmark_names = {
        "QQQ": "Nasdaq-100",
        "XLY": "Consumer Discretionary",
        "XLP": "Consumer Staples",
        "XLF": "Financials",
        "SPY": "S&P 500",
        "BTC-USD": "Bitcoin",
        "XIC.TO": "TSX Composite",
        "AGG": "US Aggregate Bonds",
        "XBB.TO": "Canadian Bonds",
        "XLV": "Healthcare",
        "XLE": "Energy",
        "XLU": "Utilities",
        "XLI": "Industrials",
        "XLB": "Materials",
        "XLRE": "Real Estate",
        "XLC": "Communication Services"
    }
    return benchmark_names.get(ticker, ticker)
