-- quantsys-v2/migrations/create_pending_orders.sql
-- 条件委托（挂单）表：盘前（非交易时段）可下 execute_at='market_open' 的挂单，
-- 开盘后 9:31 起由 daily_orchestrator MARKET_OPEN tick 自动撮合。
-- 创建时间: 2026-07-29

CREATE TABLE IF NOT EXISTS quant.simulation_pending_orders (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    action VARCHAR(10) NOT NULL,
    shares INTEGER,
    amount NUMERIC(15, 2),
    price_limit NUMERIC(10, 2),
    reason TEXT,
    execute_at VARCHAR(20) NOT NULL DEFAULT 'market_open',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    fail_reason TEXT,
    executed_trade_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_simulation_pending_orders_account
    ON quant.simulation_pending_orders (account_name);
CREATE INDEX IF NOT EXISTS idx_simulation_pending_orders_status
    ON quant.simulation_pending_orders (status);

COMMENT ON TABLE quant.simulation_pending_orders IS '条件委托：非交易时段挂单，execute_at=market_open 时开盘后 9:31 起自动撮合';
COMMENT ON COLUMN quant.simulation_pending_orders.action IS 'buy/sell';
COMMENT ON COLUMN quant.simulation_pending_orders.status IS 'pending/executed/failed/cancelled';
COMMENT ON COLUMN quant.simulation_pending_orders.executed_trade_id IS '撮合成功后关联的 simulation_trades.id';
