-- 010_create_chip_distribution_tables.sql
-- 筹码分布（成本分布）服务
-- 设计：docs/superpowers/specs/2026-08-11-chip-distribution-design.md

-- 每股票一行：增量计算的滚动状态（价位桶数组）
CREATE TABLE IF NOT EXISTS quant.chip_distribution_state (
    symbol          TEXT PRIMARY KEY REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    price_min       DOUBLE PRECISION NOT NULL,
    bin_width       DOUBLE PRECISION NOT NULL,
    counts          BYTEA NOT NULL,           -- numpy float64 数组序列化（N_BINS 个）
    last_trade_date DATE NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 每日摘要指标：全市场约 5270 行/日，供扫描/因子用
CREATE TABLE IF NOT EXISTS quant.chip_metrics (
    symbol        TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    trade_date    DATE NOT NULL,
    profit_ratio  DOUBLE PRECISION,   -- 获利盘比例：收盘价以下筹码占比
    avg_cost      DOUBLE PRECISION,   -- 平均持仓成本
    cost_90_low   DOUBLE PRECISION,
    cost_90_high  DOUBLE PRECISION,   -- 90% 成本区间
    cost_70_low   DOUBLE PRECISION,
    cost_70_high  DOUBLE PRECISION,   -- 70% 成本区间
    peak_price    DOUBLE PRECISION,   -- 最大密集峰价位
    concentration DOUBLE PRECISION,   -- (cost_70_high - cost_70_low) / 区间中位价
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_chip_metrics_date ON quant.chip_metrics (trade_date);
CREATE INDEX IF NOT EXISTS idx_chip_metrics_profit ON quant.chip_metrics (trade_date, profit_ratio);
