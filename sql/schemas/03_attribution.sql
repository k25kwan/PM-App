-- Portfolio Attribution Schema
-- Stores Brinson-Fachler attribution analysis results
-- Supports total portfolio, equity-only, and fixed income-only attribution

USE RiskDemo;
GO

-- Drop existing table if it exists
IF OBJECT_ID('portfolio_attribution', 'U') IS NOT NULL
    DROP TABLE portfolio_attribution;
GO

-- Portfolio Attribution Table
CREATE TABLE portfolio_attribution (
    id BIGINT IDENTITY(1,1) PRIMARY KEY,
    asof_date DATE NOT NULL,
    attribution_type NVARCHAR(20) NOT NULL,  -- 'TOTAL', 'EQUITY', 'FIXED_INCOME'
    sector NVARCHAR(64) NOT NULL,
    
    -- Brinson Attribution Components (all in decimal format, e.g., 0.0015 = 15 bps)
    allocation_effect NUMERIC(18,6),         -- Sector timing/weighting decisions
    selection_effect NUMERIC(18,6),          -- Security selection within sectors
    interaction_effect NUMERIC(18,6),        -- Combined allocation + selection effect
    
    -- Supporting Data
    portfolio_weight NUMERIC(18,6),          -- Portfolio sector weight
    benchmark_weight NUMERIC(18,6),          -- Benchmark sector weight
    portfolio_return NUMERIC(18,6),          -- Portfolio sector return for the period
    benchmark_return NUMERIC(18,6),          -- Benchmark sector return for the period
    total_benchmark_return NUMERIC(18,6),    -- Total benchmark return for the period
    
    -- Metadata
    lookback_days INT DEFAULT 1,             -- Period for return calculation (1 = daily)
    created_at DATETIME2 DEFAULT SYSDATETIME(),
    
    -- Constraints
    CONSTRAINT UQ_attribution UNIQUE (asof_date, attribution_type, sector, lookback_days),
    CONSTRAINT CHK_attribution_type CHECK (attribution_type IN ('TOTAL', 'EQUITY', 'FIXED_INCOME'))
);
GO

-- Indexes for performance
CREATE INDEX IX_portfolio_attribution_date ON portfolio_attribution(asof_date);
CREATE INDEX IX_portfolio_attribution_type ON portfolio_attribution(attribution_type);
CREATE INDEX IX_portfolio_attribution_date_type ON portfolio_attribution(asof_date, attribution_type);
GO

-- View: Latest Attribution Summary (aggregated across sectors)
CREATE OR ALTER VIEW v_attribution_summary AS
SELECT 
    asof_date,
    attribution_type,
    SUM(allocation_effect) AS total_allocation_effect,
    SUM(selection_effect) AS total_selection_effect,
    SUM(interaction_effect) AS total_interaction_effect,
    SUM(allocation_effect) + SUM(selection_effect) + SUM(interaction_effect) AS total_active_return,
    COUNT(sector) AS num_sectors,
    created_at
FROM portfolio_attribution
WHERE lookback_days = 1  -- Daily attribution
GROUP BY asof_date, attribution_type, created_at;
GO

-- View: Latest Attribution by Sector (Monthly by default)
CREATE OR ALTER VIEW v_attribution_latest AS
SELECT 
    a.asof_date,
    a.attribution_type,
    a.sector,
    a.lookback_days,
    a.allocation_effect,
    a.selection_effect,
    a.interaction_effect,
    (a.allocation_effect + a.selection_effect + a.interaction_effect) AS total_effect,
    a.portfolio_weight,
    a.benchmark_weight,
    (a.portfolio_weight - a.benchmark_weight) AS weight_difference,
    a.portfolio_return,
    a.benchmark_return,
    (a.portfolio_return - a.benchmark_return) AS return_difference,
    -- Format effects in basis points for display
    CAST(a.allocation_effect * 10000 AS DECIMAL(10,2)) AS allocation_effect_bps,
    CAST(a.selection_effect * 10000 AS DECIMAL(10,2)) AS selection_effect_bps,
    CAST(a.interaction_effect * 10000 AS DECIMAL(10,2)) AS interaction_effect_bps,
    CAST((a.allocation_effect + a.selection_effect + a.interaction_effect) * 10000 AS DECIMAL(10,2)) AS total_effect_bps,
    -- Status coloring
    CASE 
        WHEN (a.allocation_effect + a.selection_effect + a.interaction_effect) > 0.0005 THEN 'Green'
        WHEN (a.allocation_effect + a.selection_effect + a.interaction_effect) < -0.0005 THEN 'Red'
        ELSE 'Yellow'
    END AS status_color
FROM portfolio_attribution a
WHERE a.asof_date = (SELECT MAX(asof_date) FROM portfolio_attribution WHERE attribution_type = a.attribution_type AND lookback_days = a.lookback_days)
    AND a.lookback_days = 30;  -- Default to monthly (30-day) attribution
GO

PRINT 'Portfolio attribution schema created successfully.';
PRINT 'Tables: portfolio_attribution';
PRINT 'Views: v_attribution_summary, v_attribution_latest';
GO
