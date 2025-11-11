# PM-App: Daily Portfolio Management System

A Python-based portfolio management system for tracking daily portfolio performance, risk metrics, and attribution analysis.

## Overview

PM-App is designed for portfolio managers to:
- Track daily portfolio holdings and prices
- Calculate rolling risk metrics (volatility, tracking error, beta)
- Analyze portfolio attribution vs benchmark
- Monitor IPS (Investment Policy Statement) compliance

## Features

- **Daily Price Updates**: Automatically fetch latest prices from Yahoo Finance
- **Risk Metrics**: Calculate 30/90/180-day rolling volatility, tracking error, and beta
- **Attribution Analysis**: Decompose portfolio returns into asset allocation and selection effects
- **IPS Monitoring**: Track portfolio drift from policy targets
- **SQL Server Backend**: Structured database with historical tracking

## Quick Start

### Prerequisites

- Python 3.10+
- SQL Server Express (or any SQL Server instance)
- Git

### Installation

1. **Clone the repository**
   ```powershell
   git clone https://github.com/k25kwan/PM-App.git
   cd PM-App
   ```

2. **Install Python dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   - Copy `.env.example` to `.env`
   - Update database connection details:
     ```
     DB_SERVER=your_server_name
     DB_NAME=RiskDemo
     DB_DRIVER=ODBC Driver 17 for SQL Server
     ```

4. **Initialize database**
   ```powershell
   # Run schemas in order
   sqlcmd -S your_server -d RiskDemo -i sql\schemas\01_core_portfolio.sql
   sqlcmd -S your_server -d RiskDemo -i sql\schemas\02_risk_metrics.sql
   sqlcmd -S your_server -d RiskDemo -i sql\schemas\03_attribution.sql
   
   # Load seed data
   sqlcmd -S your_server -d RiskDemo -i sql\seed_data\seed_dimensions.sql
   sqlcmd -S your_server -d RiskDemo -i sql\seed_data\seed_ips_policy.sql
   
   # Create views
   sqlcmd -S your_server -d RiskDemo -i sql\views\view_returns.sql
   sqlcmd -S your_server -d RiskDemo -i sql\views\view_ips_monitoring.sql
   sqlcmd -S your_server -d RiskDemo -i sql\views\view_risk_metrics_latest.sql
   ```

5. **Input initial portfolio holdings**
   - Manually insert holdings into `core.PortfolioHoldings` table
   - Specify `AsOfDate`, `Ticker`, `Shares`, `CostBasis`
   - Example:
     ```sql
     INSERT INTO core.PortfolioHoldings (AsOfDate, Ticker, Shares, CostBasis)
     VALUES 
         ('2024-01-01', 'AAPL', 100, 150.00),
         ('2024-01-01', 'MSFT', 50, 350.00);
     ```

### Daily Workflow

Run the daily update script to fetch prices and calculate metrics:

```powershell
.\scripts\run_daily_update.ps1
```

This will:
1. Fetch latest prices for all tickers in your portfolio
2. Calculate rolling risk metrics (volatility, tracking error, beta)
3. Calculate attribution vs benchmark

You can also run individual steps:
```powershell
.\scripts\run_daily_update.ps1 -Step prices       # Only fetch prices
.\scripts\run_daily_update.ps1 -Step risk         # Only calculate risk
.\scripts\run_daily_update.ps1 -Step attribution  # Only calculate attribution
```

## Project Structure

```
PM-app/
├── src/
│   ├── core/                    # Core utilities
│   │   ├── utils_db.py          # Database connection
│   │   └── data_sanitizers.py   # Data cleaning functions
│   ├── ingestion/               # Data ingestion
│   │   └── fetch_prices.py      # Fetch Yahoo Finance prices
│   └── analytics/               # Analytics calculations
│       ├── compute_risk_metrics.py    # Risk metrics
│       └── compute_attribution.py     # Attribution analysis
├── sql/
│   ├── schemas/                 # Database schemas
│   │   ├── 01_core_portfolio.sql      # Portfolio holdings & prices
│   │   ├── 02_risk_metrics.sql        # Risk metrics tables
│   │   └── 03_attribution.sql         # Attribution tables
│   ├── seed_data/               # Reference data
│   │   ├── seed_dimensions.sql        # Date, asset class dimensions
│   │   └── seed_ips_policy.sql        # IPS policy targets
│   └── views/                   # SQL views for reporting
│       ├── view_returns.sql           # Portfolio/benchmark returns
│       ├── view_ips_monitoring.sql    # IPS compliance tracking
│       └── view_risk_metrics_latest.sql  # Latest risk metrics
├── scripts/
│   └── run_daily_update.ps1     # Daily update automation
├── data/                        # Price cache (JSON files)
├── docs/                        # Documentation
├── requirements.txt             # Python dependencies
└── .env.example                 # Environment variable template
```

## Database Schema

### Core Tables
- `core.PortfolioHoldings`: Daily portfolio positions
- `core.Prices`: Historical price data (portfolio + benchmark)
- `core.BenchmarkWeights`: Benchmark composition over time

### Risk Metrics Tables
- `risk.RollingVolatility`: 30/90/180-day volatility
- `risk.TrackingError`: Tracking error vs benchmark
- `risk.Beta`: Portfolio beta

### Attribution Tables
- `attribution.DailyAttribution`: Daily attribution effects
- `attribution.MonthlyAttribution`: Monthly aggregated attribution

## Key Concepts

### Rolling Windows
All risk metrics are calculated using rolling windows:
- **30-day**: Short-term volatility and tracking
- **90-day**: Medium-term trends
- **180-day**: Long-term patterns

### Attribution Effects
Attribution decomposes portfolio returns into:
- **Asset Allocation**: Returns from over/underweighting asset classes
- **Security Selection**: Returns from stock picking within asset classes
- **Interaction**: Combined effect of allocation and selection

### IPS Monitoring
The system tracks portfolio drift from policy targets:
- Policy weights defined in `seed_ips_policy.sql`
- Actual weights calculated from current holdings
- Drift alerts when positions exceed tolerance bands

## Development

### Adding New Tickers
Simply add holdings to `core.PortfolioHoldings` - prices will be fetched automatically on next run.

### Modifying Risk Windows
Edit window sizes in `compute_risk_metrics.py`:
```python
windows = {
    'VOL_030D': 30,
    'VOL_090D': 90,
    'VOL_180D': 180
}
```

### Customizing Attribution
Edit asset class mappings in `compute_attribution.py`:
```python
asset_class_map = {
    'AAPL': 'US Equity',
    'TLT': 'Fixed Income'
}
```

## Troubleshooting

### Database Connection Issues
- Verify SQL Server is running
- Check firewall allows connections on port 1433
- Confirm ODBC driver is installed: `ODBC Driver 17 for SQL Server`

### Missing Prices
- Check ticker symbols are valid on Yahoo Finance
- Verify internet connection
- Review `data/` folder for cached price files

### Import Errors
- Ensure `PYTHONPATH` includes project root
- Verify all `__init__.py` files exist in src folders
- Check Python version is 3.10+

## Contributing

This project is maintained for personal portfolio management. For questions or suggestions, please contact the repository owner.

## License

Private project - not for redistribution.
