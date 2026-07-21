-- 资金流数据表
CREATE TABLE IF NOT EXISTS quant.stock_fund_flow (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    close_price DECIMAL(10,2),
    change_pct DECIMAL(8,4),

    -- 主力资金
    main_net_inflow DECIMAL(18,2),
    main_net_inflow_rate DECIMAL(8,4),

    -- 超大单
    large_net_inflow DECIMAL(18,2),
    large_net_inflow_rate DECIMAL(8,4),

    -- 大单
    big_net_inflow DECIMAL(18,2),
    big_net_inflow_rate DECIMAL(8,4),

    -- 中单
    medium_net_inflow DECIMAL(18,2),
    medium_net_inflow_rate DECIMAL(8,4),

    -- 小单
    small_net_inflow DECIMAL(18,2),
    small_net_inflow_rate DECIMAL(8,4),

    -- 元数据
    source VARCHAR(50) DEFAULT 'eastmoney',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(symbol, trade_date)
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_fund_flow_symbol_date
    ON quant.stock_fund_flow(symbol, trade_date DESC);

CREATE INDEX IF NOT EXISTS idx_fund_flow_updated_at
    ON quant.stock_fund_flow(updated_at);

CREATE INDEX IF NOT EXISTS idx_fund_flow_trade_date
    ON quant.stock_fund_flow(trade_date DESC);

-- 添加注释
COMMENT ON TABLE quant.stock_fund_flow IS '股票资金流向数据（缓存表）';
COMMENT ON COLUMN quant.stock_fund_flow.symbol IS '股票代码（不带后缀）';
COMMENT ON COLUMN quant.stock_fund_flow.main_net_inflow IS '主力净流入（万元）';
COMMENT ON COLUMN quant.stock_fund_flow.updated_at IS '数据更新时间（用于判断缓存新鲜度）';
