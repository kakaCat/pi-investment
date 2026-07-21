-- quantsys-v2/migrations/add_strategy_performance_table.sql
-- Migration for strategy performance tracking
-- Creates: strategy_performance table for tracking strategy execution results

-- Create strategy performance table
CREATE TABLE IF NOT EXISTS quant.strategy_performance (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    signal_date DATE NOT NULL,

    entry_price DECIMAL(15,4) NOT NULL,
    exit_price DECIMAL(15,4),
    pnl_pct DECIMAL(10,4),
    holding_days INTEGER DEFAULT 0,

    scenario_tags JSONB,
    params_snapshot JSONB,
    source VARCHAR(20) DEFAULT 'paper',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_strategy_performance_strategy ON quant.strategy_performance(strategy_name);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_symbol ON quant.strategy_performance(symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_date ON quant.strategy_performance(signal_date);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_source ON quant.strategy_performance(source);
CREATE INDEX IF NOT EXISTS idx_strategy_performance_strategy_symbol ON quant.strategy_performance(strategy_name, symbol);

-- Create GIN index for JSONB scenario_tags
CREATE INDEX IF NOT EXISTS idx_strategy_performance_scenario_tags ON quant.strategy_performance USING GIN (scenario_tags);

-- Add comments
COMMENT ON TABLE quant.strategy_performance IS '策略表现追踪表 - 记录策略执行的盈亏结果';
COMMENT ON COLUMN quant.strategy_performance.strategy_name IS '策略名称';
COMMENT ON COLUMN quant.strategy_performance.symbol IS '标的代码';
COMMENT ON COLUMN quant.strategy_performance.signal_date IS '信号产生日期';
COMMENT ON COLUMN quant.strategy_performance.entry_price IS '入场价格';
COMMENT ON COLUMN quant.strategy_performance.exit_price IS '出场价格';
COMMENT ON COLUMN quant.strategy_performance.pnl_pct IS '盈亏百分比';
COMMENT ON COLUMN quant.strategy_performance.holding_days IS '持仓天数';
COMMENT ON COLUMN quant.strategy_performance.scenario_tags IS '场景标签（如 rsi_oversold, bull_market）';
COMMENT ON COLUMN quant.strategy_performance.params_snapshot IS '参数快照（JSON）';
COMMENT ON COLUMN quant.strategy_performance.source IS '来源：paper（纸面测试）或 live（实盘）';

-- Add trigger to update updated_at
CREATE OR REPLACE FUNCTION quant.update_strategy_performance_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_strategy_performance_updated_at
    BEFORE UPDATE ON quant.strategy_performance
    FOR EACH ROW
    EXECUTE FUNCTION quant.update_strategy_performance_updated_at();

COMMENT ON FUNCTION quant.update_strategy_performance_updated_at IS '自动更新 updated_at 字段';
