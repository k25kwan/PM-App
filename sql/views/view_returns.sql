-- Portfolio and Benchmark Returns Views
-- Daily and cumulative return calculations for performance analysis
USE RiskDemo;
GO

-- ============================================================================
-- PORTFOLIO RETURNS
-- ============================================================================

-- =============================================
-- View: v_portfolio_daily_returns
-- Description: Portfolio-weighted daily returns
-- 
-- Calculates the portfolio-level daily return by 
-- weighting each security's return by its market value.
-- This provides the actual portfolio performance,
-- not individual ticker performance.
-- =============================================

IF OBJECT_ID('v_portfolio_daily_returns', 'V') IS NOT NULL
    DROP VIEW v_portfolio_daily_returns;
GO

CREATE VIEW v_portfolio_daily_returns AS
SELECT 
    date,
    -- Weighted average return: Σ(return_i × weight_i)
    SUM(daily_return * market_value) / NULLIF(SUM(market_value), 0) as daily_return,
    SUM(market_value) as total_market_value,
    COUNT(*) as num_securities
FROM historical_portfolio_info
GROUP BY date;
GO

-- =============================================
-- View: v_portfolio_cumulative_returns
-- Description: Portfolio cumulative returns over time
-- 
-- Calculates the portfolio-level cumulative return by:
-- 1. Computing daily value-weighted portfolio returns
-- 2. Compounding those returns geometrically from inception
-- 
-- This is the CORRECT portfolio performance metric,
-- not an average of individual ticker cumulative returns.
-- =============================================

IF OBJECT_ID('v_portfolio_cumulative_returns', 'V') IS NOT NULL
    DROP VIEW v_portfolio_cumulative_returns;
GO

CREATE VIEW v_portfolio_cumulative_returns AS
WITH daily_portfolio_returns AS (
    -- Calculate daily value-weighted portfolio returns
    SELECT 
        date,
        SUM(daily_return * market_value) / NULLIF(SUM(market_value), 0) as daily_return,
        SUM(market_value) as total_market_value
    FROM historical_portfolio_info
    WHERE daily_return IS NOT NULL
    GROUP BY date
),
cumulative_calc AS (
    -- Calculate cumulative returns using geometric compounding
    -- Formula: cumulative_return = PRODUCT(1 + daily_return) - 1
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
    -- Additional metrics
    cumulative_return * 100 as cumulative_return_pct,
    daily_return * 100 as daily_return_pct
FROM cumulative_calc;
GO

-- ============================================================================
-- BENCHMARK RETURNS
-- ============================================================================

-- =============================================
-- View: v_benchmark_daily_returns
-- Description: Benchmark composite daily returns
-- 
-- Calculates the benchmark composite return by 
-- weighting each benchmark ETF's return by its 
-- strategic allocation weight from dim_benchmarks.
-- =============================================

IF OBJECT_ID('v_benchmark_daily_returns', 'V') IS NOT NULL
    DROP VIEW v_benchmark_daily_returns;
GO

CREATE VIEW v_benchmark_daily_returns AS
SELECT 
    h.date,
    -- Equal-weighted composite return (each benchmark gets 1/N weight)
    -- To use custom weights, add weight_pct column to dim_benchmarks
    AVG(h.daily_return) as daily_return,
    COUNT(*) as num_components
FROM historical_benchmark_info h
JOIN dim_benchmarks b ON h.ticker = b.ticker
GROUP BY h.date;
GO

-- =============================================
-- View: v_benchmark_cumulative_returns
-- Description: Benchmark cumulative returns over time
-- 
-- Calculates the benchmark composite cumulative return by:
-- 1. Computing daily equal-weighted benchmark returns
--    (or use custom weights if added to dim_benchmarks)
-- 2. Compounding those returns geometrically from inception
-- 
-- This is the CORRECT benchmark performance metric,
-- not an average of individual ETF cumulative returns.
-- =============================================

IF OBJECT_ID('v_benchmark_cumulative_returns', 'V') IS NOT NULL
    DROP VIEW v_benchmark_cumulative_returns;
GO

CREATE VIEW v_benchmark_cumulative_returns AS
WITH daily_benchmark_returns AS (
    -- Calculate daily equal-weighted benchmark returns
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
    -- Calculate cumulative returns using geometric compounding
    -- Formula: cumulative_return = PRODUCT(1 + daily_return) - 1
    SELECT 
        date,
        daily_return,
        num_components,
        EXP(SUM(LOG(1 + daily_return)) OVER (ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) - 1 as cumulative_return
    FROM daily_benchmark_returns
    WHERE daily_return IS NOT NULL AND daily_return > -1  -- Avoid LOG of negative numbers
)
SELECT 
    date,
    daily_return,
    cumulative_return,
    num_components,
    -- Additional metrics
    cumulative_return * 100 as cumulative_return_pct,
    daily_return * 100 as daily_return_pct
FROM cumulative_calc;
GO

PRINT 'Portfolio and benchmark returns views created successfully.';
PRINT 'Views: v_portfolio_daily_returns, v_portfolio_cumulative_returns, v_benchmark_daily_returns, v_benchmark_cumulative_returns';
GO
