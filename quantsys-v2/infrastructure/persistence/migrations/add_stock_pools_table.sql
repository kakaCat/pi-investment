-- Stock Pools table for screening → pool → validation pipeline
-- Supports static (manually curated) and dynamic (auto-refreshed) pools

CREATE TABLE IF NOT EXISTS quant.stock_pools (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    pool_type VARCHAR(10) NOT NULL CHECK (pool_type IN ('static', 'dynamic')),
    description TEXT,
    symbols TEXT[] NOT NULL DEFAULT '{}',
    filter_template JSONB,
    refresh_interval VARCHAR(20) CHECK (refresh_interval IN ('daily', 'weekly', NULL)),
    last_refreshed_at TIMESTAMP,
    last_validation JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_pools_pool_type ON quant.stock_pools(pool_type);
CREATE INDEX IF NOT EXISTS idx_stock_pools_name ON quant.stock_pools(name);

COMMENT ON TABLE quant.stock_pools IS '股票池管理表：支持静态池和动态池（定时刷新）';
COMMENT ON COLUMN quant.stock_pools.pool_type IS 'static=手动锁定, dynamic=按filter_template定时刷新';
COMMENT ON COLUMN quant.stock_pools.filter_template IS '动态池筛选条件模板（JSON），复用 /api/signals/scan 参数格式';
COMMENT ON COLUMN quant.stock_pools.last_validation IS '最近一次策略验证结果快照（JSON）';
