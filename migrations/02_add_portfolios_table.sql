-- Migration: Add portfolios table for multi-portfolio support
-- Each user can have multiple named portfolios

-- Create portfolios table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'portfolios')
BEGIN
    CREATE TABLE portfolios (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        user_id BIGINT NOT NULL,
        portfolio_name NVARCHAR(255) NOT NULL,
        description NVARCHAR(MAX),
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        updated_at DATETIME2 DEFAULT SYSDATETIME(),
        is_active BIT DEFAULT 1,
        CONSTRAINT UQ_user_portfolio_name UNIQUE (user_id, portfolio_name)
    );
    
    CREATE INDEX IX_portfolios_user_id ON portfolios(user_id);
    
    PRINT 'Created portfolios table';
END
ELSE
BEGIN
    PRINT 'portfolios table already exists';
END
GO

-- Add portfolio_id column to historical_portfolio_info
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('historical_portfolio_info') AND name = 'portfolio_id')
BEGIN
    ALTER TABLE historical_portfolio_info ADD portfolio_id BIGINT NULL;
    CREATE INDEX IX_historical_portfolio_info_portfolio_id ON historical_portfolio_info(portfolio_id);
    PRINT 'Added portfolio_id to historical_portfolio_info';
END
ELSE
BEGIN
    PRINT 'portfolio_id column already exists in historical_portfolio_info';
END
GO

-- Add portfolio_id column to f_positions
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('f_positions') AND name = 'portfolio_id')
BEGIN
    ALTER TABLE f_positions ADD portfolio_id BIGINT NULL;
    CREATE INDEX IX_f_positions_portfolio_id ON f_positions(portfolio_id);
    PRINT 'Added portfolio_id to f_positions';
END
ELSE
BEGIN
    PRINT 'portfolio_id column already exists in f_positions';
END
GO

-- Add portfolio_id column to portfolio_risk_metrics
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('portfolio_risk_metrics') AND name = 'portfolio_id')
BEGIN
    ALTER TABLE portfolio_risk_metrics ADD portfolio_id BIGINT NULL;
    CREATE INDEX IX_portfolio_risk_metrics_portfolio_id ON portfolio_risk_metrics(portfolio_id);
    PRINT 'Added portfolio_id to portfolio_risk_metrics';
END
ELSE
BEGIN
    PRINT 'portfolio_id column already exists in portfolio_risk_metrics';
END
GO

-- Add portfolio_id column to portfolio_attribution
IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('portfolio_attribution') AND name = 'portfolio_id')
BEGIN
    ALTER TABLE portfolio_attribution ADD portfolio_id BIGINT NULL;
    CREATE INDEX IX_portfolio_attribution_portfolio_id ON portfolio_attribution(portfolio_id);
    PRINT 'Added portfolio_id to portfolio_attribution';
END
ELSE
BEGIN
    PRINT 'portfolio_id column already exists in portfolio_attribution';
END
GO

PRINT 'Migration 02 complete: Multi-portfolio support added';
