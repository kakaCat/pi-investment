-- Add validation_status column to strategy_configs
ALTER TABLE quant.strategy_configs
ADD COLUMN IF NOT EXISTS validation_status VARCHAR(20) DEFAULT 'valid';

CREATE INDEX IF NOT EXISTS idx_strategy_configs_validation_status
ON quant.strategy_configs(validation_status);

-- Create strategy_validation_reports table
CREATE TABLE IF NOT EXISTS quant.strategy_validation_reports (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER NOT NULL REFERENCES quant.strategy_configs(id) ON DELETE CASCADE,
    validation_date TIMESTAMP NOT NULL DEFAULT NOW(),
    score DECIMAL(5, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    annual_return DECIMAL(10, 4),
    sharpe_ratio DECIMAL(10, 4),
    max_drawdown DECIMAL(10, 4),
    win_rate DECIMAL(10, 4),
    profit_factor DECIMAL(10, 4),
    backtest_count INTEGER,
    error_count INTEGER,
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_validation_reports_strategy
ON quant.strategy_validation_reports(strategy_id, validation_date DESC);

COMMENT ON TABLE quant.strategy_validation_reports IS '策略验证报告记录';
COMMENT ON COLUMN quant.strategy_validation_reports.score IS '综合评分 (0-100)';
COMMENT ON COLUMN quant.strategy_validation_reports.status IS 'passed | failed';
