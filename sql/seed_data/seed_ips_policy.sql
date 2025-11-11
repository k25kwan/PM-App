-- Investment Policy Statement (IPS) Rules and Targets
-- Defines portfolio constraints: sector bands, single name caps, and target weights
USE RiskDemo;
GO

-- ============================================================================
-- IPS SECTOR BANDS
-- Max/min overweight/underweight vs benchmark (in basis points)
-- Format: (warning buffer = near_buffer_bp, hard stop = max_over_bp/min_under_bp)
-- Tighter limits to trigger more frequent rebalancing actions
-- Rebalancing logic triggers at WARNING level (near_buffer_bp)
-- ============================================================================
INSERT INTO ips_sector_bands (sector, max_over_bp, min_under_bp, near_buffer_bp) VALUES
('Tech', 1000, -1000, 300),           -- Warning: ±3%, Hard Stop: ±10%
('Financials', 600, -600, 200),       -- Warning: ±2%, Hard Stop: ±6%
('US Broad', 800, -800, 250),         -- Warning: ±2.5%, Hard Stop: ±8%
('Canada Broad', 400, -400, 150),     -- Warning: ±1.5%, Hard Stop: ±4%
('US Bonds', 300, -300, 100),         -- Warning: ±1%, Hard Stop: ±3%
('CAN Bonds', 300, -300, 100);        -- Warning: ±1%, Hard Stop: ±3%
GO

-- ============================================================================
-- IPS SINGLE NAME CAP
-- Maximum weight for any individual security (in basis points)
-- ============================================================================
INSERT INTO ips_single_name_cap (max_weight_bp, near_buffer_bp) VALUES (2000, 200);
GO

-- ============================================================================
-- IPS SECTOR TARGET WEIGHTS
-- Strategic target allocations matching benchmark composition
-- ============================================================================

-- Create sector targets table if it doesn't exist
IF OBJECT_ID('dbo.ips_sector_targets', 'U') IS NULL
BEGIN
    CREATE TABLE ips_sector_targets (
        sector NVARCHAR(64) PRIMARY KEY,
        target_weight_pct DECIMAL(5,2) NOT NULL
    );
END
GO

-- Clear existing targets
DELETE FROM ips_sector_targets;
GO

-- Insert sector target weights (matching benchmark allocation)
INSERT INTO ips_sector_targets (sector, target_weight_pct) VALUES
('Tech', 40.00),
('Financials', 16.00),
('US Broad', 20.00),
('Canada Broad', 9.00),
('CAN Bonds', 7.00),
('US Bonds', 8.00);
GO

PRINT 'IPS policy rules and targets seeded successfully.';
GO
