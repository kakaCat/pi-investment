-- 基本面因子模块 - 财务报表历史数据表
-- 创建日期: 2026-05-26

-- 1. 利润表历史数据表
CREATE TABLE IF NOT EXISTS quant.income_statements (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    period_type TEXT NOT NULL,  -- 'Q' (季度) 或 'Y' (年度)

    -- 收入相关
    revenue DOUBLE PRECISION,
    operating_revenue DOUBLE PRECISION,

    -- 成本相关
    operating_cost DOUBLE PRECISION,
    gross_profit DOUBLE PRECISION,
    gross_margin DOUBLE PRECISION,

    -- 利润相关
    operating_profit DOUBLE PRECISION,
    total_profit DOUBLE PRECISION,
    net_profit DOUBLE PRECISION,
    net_profit_parent DOUBLE PRECISION,

    -- 每股指标
    eps DOUBLE PRECISION,
    eps_diluted DOUBLE PRECISION,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(symbol, report_date, period_type)
);

CREATE INDEX IF NOT EXISTS idx_income_statements_symbol ON quant.income_statements(symbol);
CREATE INDEX IF NOT EXISTS idx_income_statements_report_date ON quant.income_statements(report_date);
CREATE INDEX IF NOT EXISTS idx_income_statements_period_type ON quant.income_statements(period_type);

-- 2. 资产负债表历史数据表
CREATE TABLE IF NOT EXISTS quant.balance_sheets (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    period_type TEXT NOT NULL,

    -- 资产
    total_assets DOUBLE PRECISION,
    current_assets DOUBLE PRECISION,
    non_current_assets DOUBLE PRECISION,

    -- 负债
    total_liabilities DOUBLE PRECISION,
    current_liabilities DOUBLE PRECISION,
    non_current_liabilities DOUBLE PRECISION,

    -- 权益
    total_equity DOUBLE PRECISION,
    parent_equity DOUBLE PRECISION,

    -- 比率
    debt_ratio DOUBLE PRECISION,
    current_ratio DOUBLE PRECISION,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(symbol, report_date, period_type)
);

CREATE INDEX IF NOT EXISTS idx_balance_sheets_symbol ON quant.balance_sheets(symbol);
CREATE INDEX IF NOT EXISTS idx_balance_sheets_report_date ON quant.balance_sheets(report_date);
CREATE INDEX IF NOT EXISTS idx_balance_sheets_period_type ON quant.balance_sheets(period_type);

-- 3. 现金流量表历史数据表
CREATE TABLE IF NOT EXISTS quant.cash_flows (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    period_type TEXT NOT NULL,

    -- 经营活动现金流
    operating_cash_flow DOUBLE PRECISION,

    -- 投资活动现金流
    investing_cash_flow DOUBLE PRECISION,
    capex DOUBLE PRECISION,

    -- 筹资活动现金流
    financing_cash_flow DOUBLE PRECISION,
    dividends_paid DOUBLE PRECISION,

    -- 自由现金流
    free_cash_flow DOUBLE PRECISION,

    -- 现金及现金等价物
    cash_end DOUBLE PRECISION,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(symbol, report_date, period_type)
);

CREATE INDEX IF NOT EXISTS idx_cash_flows_symbol ON quant.cash_flows(symbol);
CREATE INDEX IF NOT EXISTS idx_cash_flows_report_date ON quant.cash_flows(report_date);
CREATE INDEX IF NOT EXISTS idx_cash_flows_period_type ON quant.cash_flows(period_type);
