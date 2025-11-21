USE RiskDemo;
GO

IF OBJECT_ID('v_portfolio_daily_returns', 'V') IS NOT NULL
    DROP VIEW v_portfolio_daily_returns;
GO

CREATE VIEW v_portfolio_daily_returns AS
SELECT 
    date,
    SUM(daily_return * market_value) / NULLIF(SUM(market_value), 0) as daily_return,
    SUM(market_value) as total_market_value,
    COUNT(*) as num_securities
FROM historical_portfolio_info
GROUP BY date;
GO

IF OBJECT_ID('v_portfolio_cumulative_returns', 'V') IS NOT NULL
    DROP VIEW v_portfolio_cumulative_returns;
GO

CREATE VIEW v_portfolio_cumulative_returns AS
WITH daily_portfolio_returns AS (
    SELECT 
        date,
        SUM(daily_return * market_value) / NULLIF(SUM(market_value), 0) as daily_return,
        SUM(market_value) as total_market_value
    FROM historical_portfolio_info
    WHERE daily_return IS NOT NULL
    GROUP BY date
),
cumulative_calc AS (
    SELECT 
        date,
        daily_return,
        total_market_value,
        EXP(SUM(LOG(1 + daily_return)) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) - 1 as cumulative_return
    FROM daily_portfolio_returns
    WHERE daily_return IS NOT NULL AND daily_return > -1  -- Avoid LOG of negative numbers
)
SELECT 
    date,
    daily_return,
    cumulative_return,
    total_market_value,
    cumulative_return * 100 as cumulative_return_pct,
    daily_return * 100 as daily_return_pct
FROM cumulative_calc;
GO

IF OBJECT_ID('v_benchmark_daily_returns', 'V') IS NOT NULL
    DROP VIEW v_benchmark_daily_returns;
GO

CREATE VIEW v_benchmark_daily_returns AS
SELECT 
    h.date,

    AVG(h.daily_return) as daily_return,
    COUNT(*) as num_components
FROM historical_benchmark_info h
JOIN dim_benchmarks b ON h.ticker = b.ticker
GROUP BY h.date;
GO

IF OBJECT_ID('v_benchmark_cumulative_returns', 'V') IS NOT NULL
    DROP VIEW v_benchmark_cumulative_returns;
GO

CREATE VIEW v_benchmark_cumulative_returns AS
WITH daily_benchmark_returns AS (
    SELECT 
        h.date,
        AVG(h.daily_return) as daily_return,
        COUNT(*) as num_components
    FROM historical_benchmark_info h
    JOIN dim_benchmarks b ON h.ticker = b.ticker
    WHERE h.daily_return IS NOT NULL
    GROUP BY h.date
),
cumulative_calc AS (
    SELECT 
        date,
        daily_return,
        num_components,
        EXP(SUM(LOG(1 + daily_return)) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) - 1 as cumulative_return
    FROM daily_benchmark_returns
    WHERE daily_return IS NOT NULL AND daily_return > -1
)
SELECT 
    date,
    daily_return,
    cumulative_return,
    num_components,
    cumulative_return * 100 as cumulative_return_pct,
    daily_return * 100 as daily_return_pct
FROM cumulative_calc;
GO

PRINT 'Portfolio and benchmark returns views created successfully.';
PRINT 'Views: v_portfolio_daily_returns, v_portfolio_cumulative_returns, v_benchmark_daily_returns, v_benchmark_cumulative_returns';
GO
