-- 007_add_stock_fund_flow_table.sql
-- 资金流数据表（个股日度资金流向，单位：万元）
-- 来源：infrastructure/persistence/migrations/add_stock_fund_flow_table.sql（设计后从未应用）
-- 用途：opponent_behavior 对手行为分析、个股资金流缓存
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

COMMENT ON TABLE quant.stock_fund_flow IS '股票资金流向数据（单位：万元，由 scripts/update_fund_flows.py 每日采集）';
COMMENT ON COLUMN quant.stock_fund_flow.symbol IS '股票代码（不带后缀）';
COMMENT ON COLUMN quant.stock_fund_flow.main_net_inflow IS '主力净流入（万元）';
COMMENT ON COLUMN quant.stock_fund_flow.updated_at IS '数据更新时间（用于判断缓存新鲜度）';

-- 每日采集任务（scheduler_daemon 从该表加载）
INSERT INTO quant.scheduler_task_configs
    (task_name, description, cron_expression, command, params, is_enabled,
     executor, max_instances, misfire_grace_time, coalesce, created_by)
VALUES
    ('fund_flow_update', '全市场资金流向每日采集（东财clist，落库stock_fund_flow）',
     '30 15 * * 1-5', 'infrastructure.jobs.fund_flow_update_job.execute',
     '{}'::jsonb, true, 'default', 1, 43200, true, 'migration-007')
ON CONFLICT (task_name) DO NOTHING;
