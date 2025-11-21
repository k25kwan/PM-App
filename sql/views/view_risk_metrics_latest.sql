USE RiskDemo;
GO

IF OBJECT_ID('dbo.v_risk_metrics_latest', 'V') IS NOT NULL
    DROP VIEW dbo.v_risk_metrics_latest;
GO

CREATE VIEW dbo.v_risk_metrics_latest AS
SELECT 
    metric_name,
    metric_value,
    metric_category,
    asof_date,
    lookback_days,

    CASE metric_name
        WHEN 'VaR_95' THEN 'VaR 95%'
        WHEN 'Expected_Shortfall' THEN 'Expected Shortfall'
        WHEN 'Volatility_Ann' THEN 'Volatility (Ann.)'
        WHEN 'Sharpe_Ratio' THEN 'Sharpe Ratio'
        WHEN 'Max_Drawdown' THEN 'Max Drawdown'
        WHEN 'Beta' THEN 'Beta'
        WHEN 'Tracking_Error' THEN 'Tracking Error'
        WHEN 'Information_Ratio' THEN 'Information Ratio'
        WHEN 'Active_Return' THEN 'Active Return'
        WHEN 'HHI_Security' THEN 'HHI (Security)'
        WHEN 'HHI_Sector' THEN 'HHI (Sector)'
        WHEN 'DV01' THEN 'DV01'
        ELSE metric_name
    END as display_name,

    CASE 
        WHEN metric_name IN ('VaR_95', 'Expected_Shortfall', 'Volatility_Ann', 'Max_Drawdown', 
                              'Tracking_Error', 'Active_Return') 
        THEN metric_value * 100 
        ELSE metric_value
    END as display_value,

    CASE 
        WHEN metric_name IN ('VaR_95', 'Expected_Shortfall', 'Volatility_Ann', 'Max_Drawdown', 
                              'Tracking_Error', 'Active_Return') 
        THEN '%'
        WHEN metric_name IN ('HHI_Security', 'HHI_Sector')
        THEN 'pts'
        WHEN metric_name = 'DV01'
        THEN '$'
        ELSE 'ratio'
    END as unit,
    CASE 
        WHEN metric_name = 'VaR_95' AND metric_value > -0.02 THEN 'Green'
        WHEN metric_name = 'VaR_95' AND metric_value > -0.04 THEN 'Yellow'
        WHEN metric_name = 'VaR_95' THEN 'Red'
        
        WHEN metric_name = 'Sharpe_Ratio' AND metric_value > 1.0 THEN 'Green'
        WHEN metric_name = 'Sharpe_Ratio' AND metric_value > 0.5 THEN 'Yellow'
        WHEN metric_name = 'Sharpe_Ratio' THEN 'Red'
        
        WHEN metric_name = 'Tracking_Error' AND metric_value < 0.05 THEN 'Green'
        WHEN metric_name = 'Tracking_Error' AND metric_value < 0.10 THEN 'Yellow'
        WHEN metric_name = 'Tracking_Error' THEN 'Red'
        
        WHEN metric_name LIKE 'HHI%' AND metric_value < 1500 THEN 'Green'
        WHEN metric_name LIKE 'HHI%' AND metric_value < 2500 THEN 'Yellow'
        WHEN metric_name LIKE 'HHI%' THEN 'Red'
        
        ELSE 'Neutral'
    END as status_color
FROM portfolio_risk_metrics
WHERE asof_date = (SELECT MAX(asof_date) FROM portfolio_risk_metrics);
GO
