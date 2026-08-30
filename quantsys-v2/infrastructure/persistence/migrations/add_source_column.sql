-- Add source column to track data provider origin
-- Created: 2026-08-30
-- Purpose: Enable data source tracking for multi-data-source consolidation

-- DailyKline: track which provider supplied each K-line record
ALTER TABLE quant.daily_klines 
ADD COLUMN IF NOT EXISTS source VARCHAR(50);

COMMENT ON COLUMN quant.daily_klines.source IS 
    'Data source provider: sina, tencent, eastmoney, akshare, baostock, database';

-- IncomeStatement: track which provider supplied financial data
ALTER TABLE quant.income_statements 
ADD COLUMN IF NOT EXISTS source VARCHAR(50);

COMMENT ON COLUMN quant.income_statements.source IS 
    'Data source provider: sina, eastmoney, akshare';

-- BalanceSheet: track which provider supplied financial data
ALTER TABLE quant.balance_sheets 
ADD COLUMN IF NOT EXISTS source VARCHAR(50);

COMMENT ON COLUMN quant.balance_sheets.source IS 
    'Data source provider: sina, eastmoney, akshare';
