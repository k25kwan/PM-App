"""
===================================================================================
TESTING/DEMO SCRIPT - NOT REQUIRED FOR PRODUCTION
===================================================================================
Backfill Historical Price Data for Portfolio Holdings
Downloads daily prices from yfinance and calculates returns for cumulative performance charts
Forward-fills weekends and holidays to match ai-risk-demo behavior

⚠️ THIS SCRIPT IS FOR TESTING ONLY ⚠️
To disable historical backfilling:
1. Simply don't run this script
2. The dashboard works with current portfolio data without historical backfill
3. Performance charts will show data from the date portfolios are created forward

This script:
- Downloads 1 year of historical prices from yfinance
- Forward-fills weekends/holidays for continuous time series
- Calculates daily returns and cumulative returns
- Populates historical_portfolio_info table for testing
- Used to test performance charts during development

Production Approach:
- Users create portfolios through the UI
- historical_portfolio_info gets populated via daily price ingestion (fetch_prices.py)
- Performance charts show data from creation date forward (not backward)
- No need for historical backfilling in live system

To clear backfilled data:
DELETE FROM historical_portfolio_info WHERE portfolio_id = [portfolio_id];
===================================================================================
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.utils_db import get_conn

def get_portfolio_holdings(portfolio_id):
    """Get all holdings for a portfolio"""
    try:
        with get_conn() as cn:
            query = """
                SELECT DISTINCT ticker, name, sector, base_ccy, asof_date
                FROM f_positions
                WHERE portfolio_id = ?
            """
            df = pd.read_sql(query, cn, params=[portfolio_id])
            return df
    except Exception as e:
        print(f"Error loading holdings: {e}")
        return pd.DataFrame()

def fetch_historical_prices(tickers, start_date, end_date):
    """Fetch historical prices from yfinance for all tickers"""
    print(f"\nFetching historical prices from {start_date} to {end_date}...")
    
    all_data = []
    
    for ticker in tickers:
        try:
            print(f"  Downloading {ticker}...")
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            
            if not hist.empty:
                hist['ticker'] = ticker
                hist.reset_index(inplace=True)
                all_data.append(hist[['Date', 'ticker', 'Close']])
                print(f"    ✓ Got {len(hist)} days")
            else:
                print(f"    ✗ No data available")
        
        except Exception as e:
            print(f"    ✗ Error: {e}")
    
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined.rename(columns={'Date': 'date', 'Close': 'price'}, inplace=True)
        return combined
    else:
        return pd.DataFrame()

def forward_fill_prices(price_df, start_date, end_date):
    """Forward-fill prices for weekends and holidays"""
    print("\nForward-filling prices for weekends/holidays...")
    
    # Create complete date range (every calendar day)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # Get unique tickers
    tickers = price_df['ticker'].unique()
    
    filled_data = []
    
    for ticker in tickers:
        ticker_prices = price_df[price_df['ticker'] == ticker].copy()
        ticker_prices['date'] = pd.to_datetime(ticker_prices['date']).dt.tz_localize(None)  # Remove timezone
        ticker_prices = ticker_prices.set_index('date')
        
        # Reindex to full date range and forward-fill
        ticker_filled = ticker_prices.reindex(date_range, method='ffill')
        ticker_filled['ticker'] = ticker
        ticker_filled.reset_index(inplace=True)
        ticker_filled.rename(columns={'index': 'date'}, inplace=True)
        
        filled_data.append(ticker_filled)
    
    result = pd.concat(filled_data, ignore_index=True)
    print(f"  ✓ Filled {len(result)} total rows ({len(tickers)} tickers × {len(date_range)} days)")
    
    return result

def calculate_daily_returns(price_df):
    """Calculate daily returns for each ticker"""
    print("\nCalculating daily returns...")
    
    price_df = price_df.sort_values(['ticker', 'date']).reset_index(drop=True)
    price_df['daily_return'] = price_df.groupby('ticker')['price'].pct_change()
    
    # First day has no return, set to 0
    price_df['daily_return'] = price_df['daily_return'].fillna(0)
    
    # Calculate cumulative return per ticker
    cumulative_returns = []
    for ticker in price_df['ticker'].unique():
        ticker_data = price_df[price_df['ticker'] == ticker].copy()
        ticker_data['cumulative_return'] = (1 + ticker_data['daily_return']).cumprod() - 1
        cumulative_returns.append(ticker_data)
    
    price_df = pd.concat(cumulative_returns, ignore_index=True)
    
    print(f"  ✓ Calculated returns for {price_df['ticker'].nunique()} tickers")
    
    return price_df

def backfill_portfolio_data(portfolio_id, start_date, end_date):
    """Backfill historical price and return data for portfolio"""
    
    print("=" * 60)
    print(f"Backfilling Portfolio Data")
    print(f"Portfolio ID: {portfolio_id}")
    print(f"Date Range: {start_date} to {end_date}")
    print("=" * 60)
    
    # 1. Get portfolio holdings
    holdings = get_portfolio_holdings(portfolio_id)
    
    if holdings.empty:
        print("No holdings found for this portfolio!")
        return
    
    print(f"\nFound {len(holdings)} holdings:")
    for _, row in holdings.iterrows():
        print(f"  - {row['ticker']} ({row['name']})")
    
    # 2. Fetch historical prices
    tickers = holdings['ticker'].tolist()
    price_data = fetch_historical_prices(tickers, start_date, end_date)
    
    if price_data.empty:
        print("No price data fetched!")
        return
    
    # 3. Forward-fill for weekends/holidays
    filled_prices = forward_fill_prices(price_data, start_date, end_date)
    
    # 4. Calculate daily returns
    filled_prices = calculate_daily_returns(filled_prices)
    
    # 5. Merge with holdings to get sector, name, currency
    filled_prices = filled_prices.merge(
        holdings[['ticker', 'name', 'sector', 'base_ccy']],
        on='ticker',
        how='left'
    )
    
    # 6. Calculate market value based on initial position
    # Get initial shares from f_positions
    print("\nCalculating market values...")
    
    with get_conn() as cn:
        cursor = cn.cursor()
        
        for ticker in tickers:
            # Get initial market value and price
            cursor.execute("""
                SELECT market_value, asof_date 
                FROM f_positions 
                WHERE portfolio_id = ? AND ticker = ?
            """, (portfolio_id, ticker))
            
            result = cursor.fetchone()
            if result:
                initial_value = float(result[0])  # Convert Decimal to float
                initial_date = result[1]
                
                # Get initial price
                ticker_data = filled_prices[filled_prices['ticker'] == ticker].copy()
                initial_price = ticker_data[ticker_data['date'] == pd.to_datetime(initial_date)]['price'].values
                
                if len(initial_price) > 0:
                    initial_price = initial_price[0]
                    shares = initial_value / initial_price
                    
                    # Calculate market value for all dates
                    filled_prices.loc[filled_prices['ticker'] == ticker, 'market_value'] = \
                        filled_prices.loc[filled_prices['ticker'] == ticker, 'price'] * shares
                    
                    print(f"  {ticker}: {shares:.2f} shares @ ${initial_price:.2f} = ${initial_value:,.2f}")
    
    # 7. Insert into historical_portfolio_info
    print("\nInserting data into historical_portfolio_info...")
    
    user_id = 1  # Hardcoded for now
    
    with get_conn() as cn:
        cursor = cn.cursor()
        
        # Delete existing data for this portfolio in the date range
        cursor.execute("""
            DELETE FROM historical_portfolio_info
            WHERE portfolio_id = ? AND date >= ? AND date <= ?
        """, (portfolio_id, start_date, end_date))
        
        deleted_count = cursor.rowcount
        print(f"  Deleted {deleted_count} existing rows")
        
        # Batch insert new data
        insert_count = 0
        for _, row in filled_prices.iterrows():
            cursor.execute("""
                INSERT INTO historical_portfolio_info 
                (user_id, portfolio_id, ticker, name, sector, market_value, currency, date, daily_return, cumulative_return)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                portfolio_id,
                row['ticker'],
                row['name'],
                row['sector'],
                row['market_value'],
                row['base_ccy'],
                row['date'],
                row['daily_return'],
                row['cumulative_return']
            ))
            insert_count += 1
            
            if insert_count % 100 == 0:
                print(f"    Inserted {insert_count} rows...")
        
        cn.commit()
        print(f"  ✓ Inserted {insert_count} total rows")
    
    print("\n" + "=" * 60)
    print("✓ Backfill complete!")
    print(f"Total rows inserted: {insert_count}")
    print(f"Date range: {filled_prices['date'].min()} to {filled_prices['date'].max()}")
    print("=" * 60)

if __name__ == "__main__":
    # Configuration
    portfolio_id = 7  # "My Growth Portfolio"
    start_date = "2024-11-12"  # 1 year ago
    end_date = datetime.now().strftime("%Y-%m-%d")
    
    backfill_portfolio_data(portfolio_id, start_date, end_date)
