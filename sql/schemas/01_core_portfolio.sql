-- Core Portfolio and Benchmark Schema
-- Historical price, position, and return tracking for portfolio and benchmark
USE RiskDemo;
GO

-- ============================================================================
-- PORTFOLIO TABLES
-- ============================================================================

-- Historical portfolio positions and returns
CREATE TABLE historical_portfolio_info (
  id BIGINT IDENTITY PRIMARY KEY,
  ticker NVARCHAR(32),
  date DATE,
  -- Pipeline columns used by rebalancing logic
  trade_quantity DECIMAL(18,4) NULL,
  quantity_change DECIMAL(18,4) NULL,
  trade_action NVARCHAR(32) NULL,
  trade_price DECIMAL(18,4) NULL,
  sector NVARCHAR(64) NULL,
  name NVARCHAR(128) NULL,
  sleeve NVARCHAR(64) NULL,
  currency CHAR(3) NULL,
  market_value DECIMAL(18,2) NULL,
  daily_return DECIMAL(9,6) NULL,
  cumulative_return DECIMAL(10,6) NULL
);
GO

-- Current portfolio positions snapshot
CREATE TABLE f_positions (
  asof_date DATE,
  security_id INT,
  ticker NVARCHAR(32),
  name NVARCHAR(128),
  sector NVARCHAR(64),
  sleeve NVARCHAR(64),
  base_ccy CHAR(3),
  quantity DECIMAL(18,4),
  market_value DECIMAL(18,2),
  local_price DECIMAL(18,4),
  change_from_prev_mv DECIMAL(18,2) NULL,
  PRIMARY KEY (asof_date, security_id)
);
GO

-- Securities master dimension
CREATE TABLE dim_securities (
  security_id INT PRIMARY KEY,
  ticker NVARCHAR(32),
  name NVARCHAR(128),
  sleeve NVARCHAR(64),
  sector NVARCHAR(64),
  base_ccy CHAR(3)
);
GO

-- Date dimension for calendar and business day tracking
CREATE TABLE dim_dates (
  date DATE PRIMARY KEY,
  year INT,
  quarter INT,
  month INT,
  day INT,
  day_of_week INT,
  is_weekend BIT,
  is_holiday BIT,
  week_of_year INT
);
GO

-- ============================================================================
-- BENCHMARK TABLES
-- ============================================================================

-- Benchmark securities master dimension
CREATE TABLE dim_benchmarks (
  benchmark_id INT PRIMARY KEY,
  ticker NVARCHAR(32),
  name NVARCHAR(128),
  sector NVARCHAR(64),
  sleeve NVARCHAR(64),
  base_ccy CHAR(3)
);
GO

-- Historical benchmark prices and returns
CREATE TABLE historical_benchmark_info (
    id BIGINT IDENTITY PRIMARY KEY,
    ticker NVARCHAR(32),
    date DATE,
    [close] DECIMAL(18,4),
    [daily_return] DECIMAL(9,6),
    [cumulative_return] DECIMAL(10,6),
    sector NVARCHAR(64) NULL,
    name NVARCHAR(128) NULL,
    sleeve NVARCHAR(64) NULL,
    currency CHAR(3) NULL
);
GO

PRINT 'Core portfolio and benchmark schema created successfully.';
PRINT 'Tables: historical_portfolio_info, f_positions, dim_securities, dim_dates, dim_benchmarks, historical_benchmark_info';
GO
