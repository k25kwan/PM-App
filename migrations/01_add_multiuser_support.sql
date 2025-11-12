-- ============================================================================
-- Migration: Add Multi-User Support to PM-App
-- Date: 2025-11-11
-- Description: Adds user_id columns to existing tables and creates new tables
--              for multi-user functionality (IPS, trades, screening)
-- ============================================================================

-- Step 1: Create users table
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'users')
BEGIN
    CREATE TABLE users (
        id BIGINT IDENTITY PRIMARY KEY,
        clerk_user_id NVARCHAR(255) UNIQUE NOT NULL,  -- From Clerk auth
        email NVARCHAR(255) UNIQUE NOT NULL,
        display_name NVARCHAR(255),
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        last_login_at DATETIME2
    );
    
    CREATE INDEX IX_users_clerk_id ON users(clerk_user_id);
    CREATE INDEX IX_users_email ON users(email);
    
    PRINT 'Created users table';
END
ELSE
BEGIN
    PRINT 'users table already exists';
END
GO

-- Step 2: Add user_id to existing tables
-- ============================================================================

-- Add user_id to historical_portfolio_info
IF NOT EXISTS (SELECT * FROM sys.columns 
               WHERE object_id = OBJECT_ID('historical_portfolio_info') 
               AND name = 'user_id')
BEGIN
    ALTER TABLE historical_portfolio_info 
    ADD user_id BIGINT NOT NULL DEFAULT 0;
    
    CREATE INDEX IX_portfolio_user_date ON historical_portfolio_info(user_id, date);
    
    PRINT 'Added user_id to historical_portfolio_info';
END
ELSE
BEGIN
    PRINT 'user_id already exists in historical_portfolio_info';
END
GO

-- Add user_id to portfolio_risk_metrics
IF NOT EXISTS (SELECT * FROM sys.columns 
               WHERE object_id = OBJECT_ID('portfolio_risk_metrics') 
               AND name = 'user_id')
BEGIN
    ALTER TABLE portfolio_risk_metrics 
    ADD user_id BIGINT NOT NULL DEFAULT 0;
    
    CREATE INDEX IX_risk_user_date ON portfolio_risk_metrics(user_id, asof_date);
    
    PRINT 'Added user_id to portfolio_risk_metrics';
END
ELSE
BEGIN
    PRINT 'user_id already exists in portfolio_risk_metrics';
END
GO

-- Add user_id to portfolio_attribution
IF NOT EXISTS (SELECT * FROM sys.columns 
               WHERE object_id = OBJECT_ID('portfolio_attribution') 
               AND name = 'user_id')
BEGIN
    ALTER TABLE portfolio_attribution 
    ADD user_id BIGINT NOT NULL DEFAULT 0;
    
    CREATE INDEX IX_attribution_user_date ON portfolio_attribution(user_id, asof_date);
    
    PRINT 'Added user_id to portfolio_attribution';
END
ELSE
BEGIN
    PRINT 'user_id already exists in portfolio_attribution';
END
GO

-- Add user_id to f_positions (if exists)
IF EXISTS (SELECT * FROM sys.tables WHERE name = 'f_positions')
BEGIN
    IF NOT EXISTS (SELECT * FROM sys.columns 
                   WHERE object_id = OBJECT_ID('f_positions') 
                   AND name = 'user_id')
    BEGIN
        ALTER TABLE f_positions 
        ADD user_id BIGINT NOT NULL DEFAULT 0;
        
        CREATE INDEX IX_positions_user ON f_positions(user_id);
        
        PRINT 'Added user_id to f_positions';
    END
    ELSE
    BEGIN
        PRINT 'user_id already exists in f_positions';
    END
END
GO

-- Step 3: Create IPS responses table
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ips_responses')
BEGIN
    CREATE TABLE ips_responses (
        id BIGINT IDENTITY PRIMARY KEY,
        user_id BIGINT NOT NULL,
        question_id INT NOT NULL,
        question_text NVARCHAR(500),
        response NVARCHAR(MAX),  -- JSON or plain text
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        updated_at DATETIME2 DEFAULT SYSDATETIME(),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT UQ_user_question UNIQUE (user_id, question_id)
    );
    
    CREATE INDEX IX_ips_user ON ips_responses(user_id);
    
    PRINT 'Created ips_responses table';
END
ELSE
BEGIN
    PRINT 'ips_responses table already exists';
END
GO

-- Step 4: Create trade log table
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'trade_log')
BEGIN
    CREATE TABLE trade_log (
        id BIGINT IDENTITY PRIMARY KEY,
        user_id BIGINT NOT NULL,
        trade_date DATE NOT NULL,
        ticker NVARCHAR(32) NOT NULL,
        action NVARCHAR(10) NOT NULL,  -- BUY or SELL
        quantity DECIMAL(18,4) NOT NULL,
        price DECIMAL(18,4) NOT NULL,
        total_value AS (quantity * price) PERSISTED,
        sector NVARCHAR(64),
        notes NVARCHAR(MAX),
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    
    CREATE INDEX IX_trade_user_date ON trade_log(user_id, trade_date);
    CREATE INDEX IX_trade_ticker ON trade_log(ticker);
    
    PRINT 'Created trade_log table';
END
ELSE
BEGIN
    PRINT 'trade_log table already exists';
END
GO

-- Step 5: Create security scores table (for screener)
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'security_scores')
BEGIN
    CREATE TABLE security_scores (
        id BIGINT IDENTITY PRIMARY KEY,
        user_id BIGINT NOT NULL,
        ticker NVARCHAR(32) NOT NULL,
        score_date DATE NOT NULL,
        fundamental_score DECIMAL(5,2),
        technical_score DECIMAL(5,2),
        ips_fit_score DECIMAL(5,2),
        composite_score DECIMAL(5,2),
        rank INT,
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT UQ_user_ticker_date UNIQUE (user_id, ticker, score_date)
    );
    
    CREATE INDEX IX_scores_user_date ON security_scores(user_id, score_date);
    CREATE INDEX IX_scores_ticker ON security_scores(ticker);
    
    PRINT 'Created security_scores table';
END
ELSE
BEGIN
    PRINT 'security_scores table already exists';
END
GO

-- Step 6: Create filtered universe table (per user based on IPS)
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'user_universe')
BEGIN
    CREATE TABLE user_universe (
        id BIGINT IDENTITY PRIMARY KEY,
        user_id BIGINT NOT NULL,
        ticker NVARCHAR(32) NOT NULL,
        name NVARCHAR(255),
        sector NVARCHAR(64),
        market_cap DECIMAL(18,2),
        country NVARCHAR(64),
        included BIT DEFAULT 1,  -- Allow manual exclusions
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        updated_at DATETIME2 DEFAULT SYSDATETIME(),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT UQ_user_universe UNIQUE (user_id, ticker)
    );
    
    CREATE INDEX IX_universe_user ON user_universe(user_id);
    CREATE INDEX IX_universe_ticker ON user_universe(ticker);
    
    PRINT 'Created user_universe table';
END
ELSE
BEGIN
    PRINT 'user_universe table already exists';
END
GO

-- Step 7: Create master securities universe (shared across all users)
-- ============================================================================
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'master_universe')
BEGIN
    CREATE TABLE master_universe (
        id BIGINT IDENTITY PRIMARY KEY,
        ticker NVARCHAR(32) UNIQUE NOT NULL,
        name NVARCHAR(255),
        sector NVARCHAR(64),
        industry NVARCHAR(128),
        market_cap DECIMAL(18,2),
        country NVARCHAR(64),
        exchange NVARCHAR(32),
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT SYSDATETIME(),
        updated_at DATETIME2 DEFAULT SYSDATETIME()
    );
    
    CREATE INDEX IX_master_ticker ON master_universe(ticker);
    CREATE INDEX IX_master_sector ON master_universe(sector);
    CREATE INDEX IX_master_country ON master_universe(country);
    
    PRINT 'Created master_universe table';
END
ELSE
BEGIN
    PRINT 'master_universe table already exists';
END
GO

-- Step 8: Verification - Show new tables
-- ============================================================================
PRINT '';
PRINT '=== Migration Complete ===';
PRINT 'New tables created:';
SELECT 
    name as TableName,
    create_date as CreatedDate
FROM sys.tables 
WHERE name IN ('users', 'ips_responses', 'trade_log', 'security_scores', 'user_universe', 'master_universe')
ORDER BY name;

PRINT '';
PRINT 'Tables with user_id added:';
SELECT 
    t.name as TableName,
    c.name as ColumnName
FROM sys.tables t
INNER JOIN sys.columns c ON t.object_id = c.object_id
WHERE c.name = 'user_id'
AND t.name IN ('historical_portfolio_info', 'portfolio_risk_metrics', 'portfolio_attribution', 'f_positions')
ORDER BY t.name;
