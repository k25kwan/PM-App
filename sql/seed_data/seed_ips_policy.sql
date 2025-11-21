USE RiskDemo;
GO

INSERT INTO ips_sector_bands (sector, max_over_bp, min_under_bp, near_buffer_bp) VALUES
('Tech', 1000, -1000, 300),           
('Financials', 600, -600, 200),       
('US Broad', 800, -800, 250),         
('Canada Broad', 400, -400, 150),     
('US Bonds', 300, -300, 100),         
('CAN Bonds', 300, -300, 100);        
GO

INSERT INTO ips_single_name_cap (max_weight_bp, near_buffer_bp) VALUES (2000, 200);
GO

IF OBJECT_ID('dbo.ips_sector_targets', 'U') IS NULL
BEGIN
    CREATE TABLE ips_sector_targets (
        sector NVARCHAR(64) PRIMARY KEY,
        target_weight_pct DECIMAL(5,2) NOT NULL
    );
END
GO

DELETE FROM ips_sector_targets;
GO

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
