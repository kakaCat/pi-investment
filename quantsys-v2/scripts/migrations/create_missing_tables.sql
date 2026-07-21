-- ============================================================================
-- 创建缺失的8张表
-- ============================================================================

-- 7. portfolio_holdings - 持仓表
CREATE TABLE IF NOT EXISTS quant.portfolio_holdings (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    avg_cost DOUBLE PRECISION NOT NULL,
    original_cost DOUBLE PRECISION,
    total_invested DOUBLE PRECISION NOT NULL,
    market TEXT NOT NULL,
    sector TEXT,
    added_date DATE NOT NULL,
    stop_loss DOUBLE PRECISION,
    target_price DOUBLE PRECISION,
    buy_reason TEXT,
    notes TEXT,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(symbol)
);

CREATE INDEX IF NOT EXISTS idx_quant_portfolio_holdings_market
    ON quant.portfolio_holdings(market);
CREATE INDEX IF NOT EXISTS idx_quant_portfolio_holdings_sector
    ON quant.portfolio_holdings(sector);
CREATE INDEX IF NOT EXISTS idx_quant_portfolio_holdings_added_date
    ON quant.portfolio_holdings(added_date);

-- 8. trades - 交易记录表
CREATE TABLE IF NOT EXISTS quant.trades (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    name TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('buy', 'sell')),
    price DOUBLE PRECISION NOT NULL CHECK (price > 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    amount DOUBLE PRECISION NOT NULL,
    fee DOUBLE PRECISION DEFAULT 0,
    stamp_duty DOUBLE PRECISION DEFAULT 0,
    pnl DOUBLE PRECISION,
    pnl_percent DOUBLE PRECISION,
    trade_date DATE NOT NULL,
    reason TEXT,
    order_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quant_trades_symbol
    ON quant.trades(symbol);
CREATE INDEX IF NOT EXISTS idx_quant_trades_trade_date_desc
    ON quant.trades(trade_date DESC);
CREATE INDEX IF NOT EXISTS idx_quant_trades_action
    ON quant.trades(action);
CREATE INDEX IF NOT EXISTS idx_quant_trades_order_id
    ON quant.trades(order_id);

-- 9. orders - 订单表
CREATE TABLE IF NOT EXISTS quant.orders (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    name TEXT NOT NULL,
    order_type TEXT NOT NULL CHECK (order_type IN ('limit', 'market', 'stop')),
    action TEXT NOT NULL CHECK (action IN ('buy', 'sell')),
    price DOUBLE PRECISION,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    status TEXT NOT NULL CHECK (status IN ('pending', 'partial', 'filled', 'cancelled', 'expired')),
    filled_quantity INTEGER DEFAULT 0,
    avg_filled_price DOUBLE PRECISION,
    reason TEXT,
    signal_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_quant_orders_symbol
    ON quant.orders(symbol);
CREATE INDEX IF NOT EXISTS idx_quant_orders_status
    ON quant.orders(status);
CREATE INDEX IF NOT EXISTS idx_quant_orders_created_at_desc
    ON quant.orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quant_orders_signal_id
    ON quant.orders(signal_id);

-- 10. backtest_results - 回测结果表
CREATE TABLE IF NOT EXISTS quant.backtest_results (
    id BIGSERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    symbol TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DOUBLE PRECISION NOT NULL,
    final_capital DOUBLE PRECISION NOT NULL,
    total_return DOUBLE PRECISION,
    annual_return DOUBLE PRECISION,
    sharpe_ratio DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    win_rate DOUBLE PRECISION,
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    avg_win DOUBLE PRECISION,
    avg_loss DOUBLE PRECISION,
    profit_factor DOUBLE PRECISION,
    parameters JSONB,
    equity_curve JSONB,
    trade_details JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quant_backtest_results_strategy_name
    ON quant.backtest_results(strategy_name);
CREATE INDEX IF NOT EXISTS idx_quant_backtest_results_symbol
    ON quant.backtest_results(symbol);
CREATE INDEX IF NOT EXISTS idx_quant_backtest_results_created_at_desc
    ON quant.backtest_results(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quant_backtest_results_sharpe_ratio
    ON quant.backtest_results(sharpe_ratio DESC);

-- 11. strategy_configs - 策略配置表
CREATE TABLE IF NOT EXISTS quant.strategy_configs (
    id BIGSERIAL PRIMARY KEY,
    strategy_name TEXT NOT NULL UNIQUE,
    description TEXT,
    strategy_type TEXT NOT NULL,
    parameters JSONB NOT NULL,
    risk_params JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    version TEXT DEFAULT '1.0',
    author TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quant_strategy_configs_is_active
    ON quant.strategy_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_quant_strategy_configs_strategy_type
    ON quant.strategy_configs(strategy_type);

-- 12. account_balance - 账户资金表
CREATE TABLE IF NOT EXISTS quant.account_balance (
    id BIGSERIAL PRIMARY KEY,
    balance_date DATE NOT NULL UNIQUE,
    cash DOUBLE PRECISION NOT NULL,
    market_value DOUBLE PRECISION NOT NULL,
    total_assets DOUBLE PRECISION NOT NULL,
    daily_pnl DOUBLE PRECISION,
    daily_return DOUBLE PRECISION,
    total_pnl DOUBLE PRECISION,
    total_return DOUBLE PRECISION,
    position_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quant_account_balance_date_desc
    ON quant.account_balance(balance_date DESC);

-- 13. risk_metrics - 风险指标表
CREATE TABLE IF NOT EXISTS quant.risk_metrics (
    id BIGSERIAL PRIMARY KEY,
    metric_date DATE NOT NULL,
    symbol TEXT,
    volatility DOUBLE PRECISION,
    beta DOUBLE PRECISION,
    var_95 DOUBLE PRECISION,
    cvar_95 DOUBLE PRECISION,
    max_position_ratio DOUBLE PRECISION,
    concentration_risk DOUBLE PRECISION,
    sector_exposure JSONB,
    correlation_matrix JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(metric_date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_quant_risk_metrics_date_desc
    ON quant.risk_metrics(metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_quant_risk_metrics_symbol
    ON quant.risk_metrics(symbol);

-- 3. minute_klines - 分钟K线表
CREATE TABLE IF NOT EXISTS quant.minute_klines (
    symbol TEXT NOT NULL REFERENCES quant.stocks(symbol) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    PRIMARY KEY (symbol, ts)
);

CREATE INDEX IF NOT EXISTS idx_quant_minute_klines_symbol_ts_desc
    ON quant.minute_klines(symbol, ts DESC);
CREATE INDEX IF NOT EXISTS idx_quant_minute_klines_ts
    ON quant.minute_klines(ts);

-- 完成
SELECT 'All 8 missing tables created successfully!' as status;
