-- 为stock_pools表添加last_signal_scan字段，用于存储实时信号扫描结果

ALTER TABLE quant.stock_pools
ADD COLUMN IF NOT EXISTS last_signal_scan JSONB;

COMMENT ON COLUMN quant.stock_pools.last_signal_scan IS '最近一次信号扫描结果（买入/卖出信号）';
