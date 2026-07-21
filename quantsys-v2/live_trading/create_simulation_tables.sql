-- 模拟交易系统数据表
-- 用于存储模拟交易的持仓、交易记录、账户状态

-- 1. 模拟账户表
CREATE TABLE IF NOT EXISTS quant.simulation_account (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR(50) NOT NULL DEFAULT 'default',
    cash NUMERIC(15, 2) NOT NULL DEFAULT 0,
    total_value NUMERIC(15, 2) NOT NULL DEFAULT 0,
    peak_value NUMERIC(15, 2) NOT NULL DEFAULT 0,
    cumulative_return NUMERIC(10, 4) DEFAULT 0,
    max_drawdown NUMERIC(10, 4) DEFAULT 0,
    last_rebalance_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_name)
);

COMMENT ON TABLE quant.simulation_account IS '模拟账户表';
COMMENT ON COLUMN quant.simulation_account.account_name IS '账户名称';
COMMENT ON COLUMN quant.simulation_account.cash IS '现金余额';
COMMENT ON COLUMN quant.simulation_account.total_value IS '总资产';
COMMENT ON COLUMN quant.simulation_account.peak_value IS '历史最高净值';
COMMENT ON COLUMN quant.simulation_account.cumulative_return IS '累计收益率';
COMMENT ON COLUMN quant.simulation_account.max_drawdown IS '最大回撤';

-- 2. 模拟持仓表
CREATE TABLE IF NOT EXISTS quant.simulation_positions (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR(50) NOT NULL DEFAULT 'default',
    symbol VARCHAR(20) NOT NULL,
    shares INTEGER NOT NULL DEFAULT 0,
    avg_price NUMERIC(10, 2) NOT NULL,
    current_price NUMERIC(10, 2),
    market_value NUMERIC(15, 2),
    cost NUMERIC(15, 2),
    profit NUMERIC(15, 2),
    profit_rate NUMERIC(10, 4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_name, symbol)
);

COMMENT ON TABLE quant.simulation_positions IS '模拟持仓表';
COMMENT ON COLUMN quant.simulation_positions.account_name IS '账户名称';
COMMENT ON COLUMN quant.simulation_positions.symbol IS '股票代码';
COMMENT ON COLUMN quant.simulation_positions.shares IS '持仓股数';
COMMENT ON COLUMN quant.simulation_positions.avg_price IS '持仓均价';
COMMENT ON COLUMN quant.simulation_positions.current_price IS '当前价格';
COMMENT ON COLUMN quant.simulation_positions.market_value IS '市值';
COMMENT ON COLUMN quant.simulation_positions.cost IS '成本';
COMMENT ON COLUMN quant.simulation_positions.profit IS '盈亏';

-- 3. 模拟交易记录表
CREATE TABLE IF NOT EXISTS quant.simulation_trades (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR(50) NOT NULL DEFAULT 'default',
    symbol VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL,  -- BUY/SELL
    shares INTEGER NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    filled_price NUMERIC(10, 2) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    commission NUMERIC(10, 2) NOT NULL DEFAULT 0,
    stamp_duty NUMERIC(10, 2) DEFAULT 0,
    total_cost NUMERIC(15, 2),
    total_revenue NUMERIC(15, 2),
    order_type VARCHAR(20) DEFAULT 'market',
    trade_date DATE NOT NULL,
    trade_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_simulation_trades_account ON quant.simulation_trades(account_name);
CREATE INDEX idx_simulation_trades_symbol ON quant.simulation_trades(symbol);
CREATE INDEX idx_simulation_trades_date ON quant.simulation_trades(trade_date);

COMMENT ON TABLE quant.simulation_trades IS '模拟交易记录表';
COMMENT ON COLUMN quant.simulation_trades.account_name IS '账户名称';
COMMENT ON COLUMN quant.simulation_trades.symbol IS '股票代码';
COMMENT ON COLUMN quant.simulation_trades.action IS '交易方向';
COMMENT ON COLUMN quant.simulation_trades.shares IS '交易股数';
COMMENT ON COLUMN quant.simulation_trades.price IS '委托价格';
COMMENT ON COLUMN quant.simulation_trades.filled_price IS '成交价格';
COMMENT ON COLUMN quant.simulation_trades.commission IS '手续费';
COMMENT ON COLUMN quant.simulation_trades.stamp_duty IS '印花税';

-- 4. 模拟账户日报表
CREATE TABLE IF NOT EXISTS quant.simulation_daily_reports (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR(50) NOT NULL DEFAULT 'default',
    report_date DATE NOT NULL,
    cash NUMERIC(15, 2) NOT NULL,
    position_value NUMERIC(15, 2) NOT NULL,
    total_value NUMERIC(15, 2) NOT NULL,
    daily_return NUMERIC(10, 4),
    cumulative_return NUMERIC(10, 4),
    peak_value NUMERIC(15, 2),
    drawdown NUMERIC(10, 4),
    position_count INTEGER DEFAULT 0,
    trade_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_name, report_date)
);

CREATE INDEX idx_simulation_reports_account ON quant.simulation_daily_reports(account_name);
CREATE INDEX idx_simulation_reports_date ON quant.simulation_daily_reports(report_date);

COMMENT ON TABLE quant.simulation_daily_reports IS '模拟账户日报表';
COMMENT ON COLUMN quant.simulation_daily_reports.report_date IS '报告日期';
COMMENT ON COLUMN quant.simulation_daily_reports.cash IS '现金';
COMMENT ON COLUMN quant.simulation_daily_reports.position_value IS '持仓市值';
COMMENT ON COLUMN quant.simulation_daily_reports.total_value IS '总资产';
COMMENT ON COLUMN quant.simulation_daily_reports.daily_return IS '日收益率';
COMMENT ON COLUMN quant.simulation_daily_reports.cumulative_return IS '累计收益率';

-- 5. 初始化默认账户
INSERT INTO quant.simulation_account (account_name, cash, total_value, peak_value)
VALUES ('default', 100000, 100000, 100000)
ON CONFLICT (account_name) DO NOTHING;

-- 查询示例
-- 查看账户状态
-- SELECT * FROM quant.simulation_account WHERE account_name = 'default';

-- 查看当前持仓
-- SELECT * FROM quant.simulation_positions WHERE account_name = 'default' AND shares > 0;

-- 查看交易记录
-- SELECT * FROM quant.simulation_trades WHERE account_name = 'default' ORDER BY trade_time DESC LIMIT 20;

-- 查看每日报告
-- SELECT * FROM quant.simulation_daily_reports WHERE account_name = 'default' ORDER BY report_date DESC LIMIT 30;
