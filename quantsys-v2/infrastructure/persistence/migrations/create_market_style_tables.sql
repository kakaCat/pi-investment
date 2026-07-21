-- 市场风格检测系统数据库迁移
-- 创建日期: 2026-05-29
-- 用途: 支持市场风格自动检测和策略权重动态调整

-- 市场风格状态表
CREATE TABLE IF NOT EXISTS quant.market_style_state (
    id SERIAL PRIMARY KEY,
    trade_date DATE NOT NULL UNIQUE,
    style VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    metrics JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_market_style_date ON quant.market_style_state(trade_date DESC);

COMMENT ON TABLE quant.market_style_state IS '市场风格状态表';
COMMENT ON COLUMN quant.market_style_state.style IS '风格类型: momentum, oscillation, low_volatility, value';
COMMENT ON COLUMN quant.market_style_state.confidence IS '置信度 0.0-1.0';
COMMENT ON COLUMN quant.market_style_state.metrics IS '详细指标 JSON';

-- 策略权重配置表
CREATE TABLE IF NOT EXISTS quant.strategy_weight_config (
    id SERIAL PRIMARY KEY,
    strategy_type VARCHAR(50) NOT NULL,
    market_style VARCHAR(50) NOT NULL,
    static_weight FLOAT NOT NULL CHECK (static_weight >= -1.0 AND static_weight <= 1.0),
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(strategy_type, market_style)
);

CREATE INDEX idx_strategy_weight_lookup ON quant.strategy_weight_config(strategy_type, market_style);

COMMENT ON TABLE quant.strategy_weight_config IS '策略权重配置表';
COMMENT ON COLUMN quant.strategy_weight_config.static_weight IS '静态权重调整 -1.0 到 +1.0';

-- 插入初始静态权重数据
INSERT INTO quant.strategy_weight_config (strategy_type, market_style, static_weight) VALUES
    ('trend_following', 'momentum', 0.30),
    ('trend_following', 'oscillation', -0.40),
    ('mean_reversion', 'oscillation', 0.30),
    ('mean_reversion', 'momentum', -0.20),
    ('multi_factor', 'value', 0.20),
    ('multi_factor', 'low_volatility', 0.10)
ON CONFLICT (strategy_type, market_style) DO NOTHING;

-- 扩展 strategy_performance 表
ALTER TABLE quant.strategy_performance
ADD COLUMN IF NOT EXISTS market_style VARCHAR(50);

CREATE INDEX IF NOT EXISTS idx_strategy_performance_style
ON quant.strategy_performance(strategy_name, market_style);

COMMENT ON COLUMN quant.strategy_performance.market_style IS '交易时的市场风格';
