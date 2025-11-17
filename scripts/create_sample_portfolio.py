"""
===================================================================================
TESTING/DEMO SCRIPT - NOT REQUIRED FOR PRODUCTION
===================================================================================
Create Sample Portfolio for Testing Dashboard
Creates a portfolio with realistic holdings dated 1 year ago

⚠️ THIS SCRIPT IS FOR TESTING ONLY ⚠️
To disable sample portfolio creation:
1. Simply don't run this script
2. The dashboard works with any portfolios created through the UI

This script:
- Creates a portfolio named "My Growth Portfolio"
- Adds 10 holdings with historical prices from 1 year ago
- Populates both f_positions and historical_portfolio_info tables
- Used to test dashboard visualizations during development

To remove sample portfolio:
DELETE FROM historical_portfolio_info WHERE portfolio_id = (SELECT id FROM portfolios WHERE portfolio_name = 'My Growth Portfolio');
DELETE FROM f_positions WHERE portfolio_id = (SELECT id FROM portfolios WHERE portfolio_name = 'My Growth Portfolio');
DELETE FROM portfolios WHERE portfolio_name = 'My Growth Portfolio';
===================================================================================
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import yfinance as yf

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.utils_db import get_conn

# Sample portfolio holdings (user's actual portfolio)
# Total shares add up to 155, we'll calculate market value based on historical prices
SAMPLE_HOLDINGS = [
    # Consumer (40% weight)
    {"ticker": "LULU", "name": "Lululemon Athletica", "sector": "Consumer", "shares": 15},
    {"ticker": "COST", "name": "Costco Wholesale", "sector": "Consumer", "shares": 2},
    
    # US Broad (40% weight)
    {"ticker": "VOO", "name": "Vanguard S&P 500 ETF", "sector": "US Broad", "shares": 6},
    {"ticker": "SSO", "name": "ProShares Ultra S&P 500", "sector": "US Broad", "shares": 30},
    
    # Financials (10% weight)
    {"ticker": "XLF", "name": "Financial Select Sector SPDR", "sector": "Financials", "shares": 10},
    {"ticker": "MA", "name": "Mastercard Inc", "sector": "Financials", "shares": 6},
    
    # Tech (5% weight)
    {"ticker": "AAPL", "name": "Apple Inc", "sector": "Tech", "shares": 6},
    {"ticker": "NVDA", "name": "NVIDIA Corp", "sector": "Tech", "shares": 10},
    
    # Crypto (5% weight)
    {"ticker": "IBIT", "name": "iShares Bitcoin Trust ETF", "sector": "Crypto", "shares": 10},
    
    # Canada (historical - 0% current weight)
    {"ticker": "CGLO.TO", "name": "CIBC Global Growth ETF", "sector": "Canada", "shares": 60},
]

# Benchmark mapping for sector-matched benchmarks
BENCHMARK_MAPPING = {
    "Tech": "QQQ",           # Invesco QQQ Trust (Nasdaq-100)
    "Consumer": "XLY",       # Consumer Discretionary Select Sector
    "Financials": "XLF",     # Financial Select Sector
    "US Broad": "SPY",       # SPDR S&P 500 ETF Trust
    "Crypto": "BTC-USD",     # Bitcoin USD
    "Canada": "XIC.TO"       # iShares Core S&P/TSX Capped Composite
}

# Benchmark weights to match portfolio allocation
BENCHMARK_WEIGHTS = {
    "Consumer": 0.40,    # LULU + COST
    "US Broad": 0.40,    # VOO + SSO
    "Financials": 0.10,  # XLF + MA
    "Tech": 0.05,        # AAPL + NVDA
    "Crypto": 0.05,      # IBIT
    "Canada": 0.00       # CGLO historical only
}

def get_historical_price(ticker, date):
    """Get historical closing price for a ticker on a specific date"""
    try:
        stock = yf.Ticker(ticker)
        # Get data for a week around the target date to handle weekends/holidays
        start = date - timedelta(days=7)
        end = date + timedelta(days=1)
        hist = stock.history(start=start, end=end)
        
        if not hist.empty:
            # Get closest available price
            return hist['Close'].iloc[-1]
        else:
            print(f"Warning: No price data for {ticker}, using default $100")
            return 100.0
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
        return 100.0

def create_sample_portfolio():
    """Create sample portfolio with historical holdings"""
    
    user_id = 1  # Test user
    portfolio_name = "My Growth Portfolio"
    description = "Diversified growth portfolio with tech, consumer, and broad market exposure"
    
    # Portfolio start date: 1 year ago
    start_date = datetime.now() - timedelta(days=365)
    start_date_str = start_date.strftime('%Y-%m-%d')
    
    print(f"Creating sample portfolio: {portfolio_name}")
    print(f"Start date: {start_date_str}")
    print("-" * 60)
    
    try:
        with get_conn() as cn:
            cursor = cn.cursor()
            
            # 1. Create portfolio
            cursor.execute("""
                INSERT INTO portfolios (user_id, portfolio_name, description, is_active)
                VALUES (?, ?, ?, 1)
            """, (user_id, portfolio_name, description))
            
            cursor.execute("SELECT @@IDENTITY")
            portfolio_id = cursor.fetchone()[0]
            print(f"Created portfolio with ID: {portfolio_id}")
            
            total_value = 0
            
            # 2. Add holdings
            for holding in SAMPLE_HOLDINGS:
                ticker = holding['ticker']
                name = holding['name']
                sector = holding['sector']
                shares = holding['shares']
                
                print(f"\nAdding {ticker} ({name})...")
                print(f"  Sector: {sector}")
                print(f"  Shares: {shares}")
                
                # Get historical price from 1 year ago
                price = get_historical_price(ticker, start_date)
                market_value = price * shares
                total_value += market_value
                
                print(f"  Historical Price: ${price:.2f}")
                print(f"  Market Value: ${market_value:,.2f}")
                
                # Determine currency
                currency = "CAD" if ".TO" in ticker else "USD"
                
                # Check if security exists in dim_securities
                cursor.execute("""
                    SELECT security_id FROM dim_securities WHERE ticker = ?
                """, (ticker,))
                result = cursor.fetchone()
                
                if result:
                    security_id = result[0]
                    print(f"  Using existing security_id: {security_id}")
                else:
                    # Get next available security_id
                    cursor.execute("SELECT ISNULL(MAX(security_id), 0) + 1 FROM dim_securities")
                    security_id = cursor.fetchone()[0]
                    
                    # Insert new security with explicit ID
                    cursor.execute("""
                        INSERT INTO dim_securities (security_id, ticker, name, sector, sleeve, base_ccy)
                        VALUES (?, ?, ?, ?, NULL, ?)
                    """, (security_id, ticker, name, sector, currency))
                    print(f"  Created new security_id: {security_id}")
                
                # Insert into historical_portfolio_info
                cursor.execute("""
                    INSERT INTO historical_portfolio_info 
                    (user_id, portfolio_id, ticker, name, sector, market_value, currency, date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, portfolio_id, ticker, name, sector, market_value, currency, start_date_str))
                
                # Insert into f_positions (current snapshot)
                cursor.execute("""
                    INSERT INTO f_positions 
                    (security_id, user_id, portfolio_id, ticker, name, sector, market_value, base_ccy, asof_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (security_id, user_id, portfolio_id, ticker, name, sector, market_value, currency, start_date_str))
                
                print(f"  ✓ Added to database")
            
            cn.commit()
            print("\n" + "=" * 60)
            print("✓ Sample portfolio created successfully!")
            print(f"Portfolio ID: {portfolio_id}")
            print(f"Total Holdings: {len(SAMPLE_HOLDINGS)}")
            print(f"Total Portfolio Value: ${total_value:,.2f}")
            print("\nBenchmark Mapping:")
            for sector, benchmark in BENCHMARK_MAPPING.items():
                weight = BENCHMARK_WEIGHTS.get(sector, 0) * 100
                print(f"  {sector}: {benchmark} ({weight:.0f}%)")
            
    except Exception as e:
        print(f"\n✗ Error creating sample portfolio: {e}")
        raise

if __name__ == "__main__":
    create_sample_portfolio()
