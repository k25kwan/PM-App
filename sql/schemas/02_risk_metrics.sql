-- Schema for portfolio risk metrics
USE RiskDemo;
GO

-- Table for storing calculated risk metrics over time
CREATE TABLE portfolio_risk_metrics (
    id BIGINT IDENTITY PRIMARY KEY,
    asof_date DATE NOT NULL,
    metric_name NVARCHAR(64) NOT NULL,
    metric_value DECIMAL(18,6),
    metric_category NVARCHAR(32), -- 'Market Risk', 'Relative Risk', 'Concentration', 'Duration'
    lookback_days INT, -- For rolling metrics (e.g., 252 days for 1-year VaR)
    created_at DATETIME2 DEFAULT SYSDATETIME(),
    CONSTRAINT UQ_risk_metric UNIQUE (asof_date, metric_name, lookback_days)
);
GO

CREATE INDEX IX_risk_metrics_date ON portfolio_risk_metrics(asof_date);
CREATE INDEX IX_risk_metrics_name ON portfolio_risk_metrics(metric_name);
GO
