import yfinance
import pandas as pd
import os

# Ticker mapping: portfolio ticker -> yfinance ticker
# Some portfolio tickers (like bonds) don't have direct yfinance equivalents,
# so we use ETF proxies that closely track the instrument
TICKER_MAPPING = {
    # Direct mappings (same ticker)
    "AAPL": "AAPL",
    "MSFT": "MSFT", 
    "NVDA": "NVDA",
    "SHOP": "SHOP",
    "TD": "TD",
    "RY": "RY",
    "BNS": "BNS",
    "SPY": "SPY",        # S&P 500 ETF
    "XIC.TO": "XIC.TO",  # iShares Core S&P/TSX Capped Composite Index ETF
    # Bond proxies
    "US10Y": "IEF",      # iShares 7-10 Year Treasury Bond ETF (US 10Y proxy)
    "CAN10Y": "XBB.TO",  # iShares Core Canadian Universe Bond Index ETF (CAN 10Y proxy)
    "CORP5": "LQD",      # iShares iBoxx Investment Grade Corporate Bond ETF (US Corp proxy)
}

# List all tickers needed for both portfolio and benchmark
PORTFOLIO_TICKERS = ["AAPL", "MSFT", "NVDA", "SHOP", "TD", "RY", "BNS", "SPY", "XIC.TO", "US10Y", "CAN10Y", "CORP5"]
BENCHMARK_TICKERS = ["XLK", "XFN.TO", "SPY", "XIC.TO", "XBB.TO", "AGG"]

# Get yfinance tickers (map portfolio tickers, keep benchmark tickers as-is)
YF_TICKERS = [TICKER_MAPPING.get(t, t) for t in PORTFOLIO_TICKERS] + BENCHMARK_TICKERS

START_DATE = "2023-10-22"
END_DATE = "2025-10-22"
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
CACHE_PATH = os.path.join(CACHE_DIR, 'yf_prices_cache.csv')

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

print(f"Downloading yfinance prices for {len(set(YF_TICKERS))} unique tickers...")
yf_data = yfinance.download(list(set(YF_TICKERS)), start=START_DATE, end=END_DATE, group_by='ticker', auto_adjust=True)

# Create reverse mapping (yfinance ticker -> portfolio ticker)
REVERSE_MAPPING = {v: k for k, v in TICKER_MAPPING.items()}

price_records = []
for yf_tkr in set(YF_TICKERS):
    if yf_tkr in yf_data or len(set(YF_TICKERS)) == 1:
        # Handle single ticker case
        if len(set(YF_TICKERS)) == 1:
            df = yf_data.reset_index()
        else:
            df = yf_data[yf_tkr].reset_index()
        
        # Map back to portfolio ticker if it was mapped
        portfolio_tkr = REVERSE_MAPPING.get(yf_tkr, yf_tkr)
        df['ticker'] = portfolio_tkr
        df = df[['Date', 'ticker', 'Close']].rename(columns={'Date': 'date', 'Close': 'trade_price'})
        price_records.append(df)
        
if price_records:
    prices_df = pd.concat(price_records, ignore_index=True)
    prices_df['date'] = pd.to_datetime(prices_df['date']).dt.strftime('%Y-%m-%d')
    prices_df.to_csv(CACHE_PATH, index=False)
    print(f"Saved {len(prices_df)} rows to {CACHE_PATH}")
else:
    print("No price data downloaded from yfinance.")
