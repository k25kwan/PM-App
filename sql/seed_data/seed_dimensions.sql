USE RiskDemo;
GO

"(FLAG): not needed for now"
INSERT INTO dim_securities (security_id, ticker, name, sleeve, sector, base_ccy) VALUES
(1, 'AAPL', 'Apple Inc', 'Equity', 'Tech', 'USD'),
(2, 'MSFT', 'Microsoft Corp', 'Equity', 'Tech', 'USD'),
(3, 'NVDA', 'NVIDIA Corp', 'Equity', 'Tech', 'USD'),
(4, 'RY', 'Royal Bank', 'Equity', 'Financials', 'CAD'),
(5, 'TD', 'Toronto-Dominion', 'Equity', 'Financials', 'CAD'),
(6, 'SHOP', 'Shopify', 'Equity', 'Tech', 'CAD'),
(7, 'BNS', 'Bank of Nova Scotia', 'Equity', 'Financials', 'CAD'),
(8, 'SPY', 'S&P 500 ETF', 'Equity', 'US Broad', 'USD'),
(9, 'XIC.TO', 'iShares Core S&P/TSX', 'Equity', 'Canada Broad', 'CAD'),
(10, 'CAN10Y', 'Canada 10Y Bond', 'Bond', 'CAN Bonds', 'CAD'),
(11, 'US10Y', 'US 10Y Bond', 'Bond', 'US Bonds', 'USD'),
(12, 'CORP5', 'US Corp 5Y', 'Bond', 'US Bonds', 'USD');
GO

CREATE TABLE dim_benchmarks (
    benchmark_id INT PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    sleeve VARCHAR(50) NOT NULL,
    sector VARCHAR(50) NOT NULL,
    base_ccy VARCHAR(10) NOT NULL
);
GO

INSERT INTO dim_benchmarks (benchmark_id, ticker, name, sleeve, sector, base_ccy) VALUES
(1, 'XLK', 'Technology Select Sector SPDR Fund', 'Equity', 'US Technology', 'USD'),
(2, 'XFN.TO', 'iShares S&P/TSX Capped Financials Index ETF', 'Equity', 'Canadian Financials', 'CAD'),
(3, 'SPY', 'S&P 500 ETF', 'Equity', 'US Broad', 'USD'),
(4, 'XIC.TO', 'iShares S&P/TSX Capped Composite Index ETF', 'Equity', 'Canadian Broad', 'CAD'),
(5, 'XBB.TO', 'iShares Core Canadian Bond Universe ETF', 'Fixed Income', 'Canadian Bonds', 'CAD'),
(6, 'AGG', 'iShares Core US Aggregate Bond ETF', 'Fixed Income', 'US Aggregate Bonds', 'USD');
GO

PRINT 'Dimension tables seeded successfully.';
GO
