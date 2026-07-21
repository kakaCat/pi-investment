-- quantsys-v2/migrations/add_signal_execution_tables.sql
-- Migration for signal execution pipeline infrastructure
-- Creates: signal_execution_logs, risk_config tables and helper function

-- 1. Create signal execution logs table
CREATE TABLE IF NOT EXISTS quant.signal_execution_logs (
    id SERIAL PRIMARY KEY,
    execution_date DATE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_ms INTEGER,

    strategies_run INTEGER DEFAULT 0,
    signals_generated INTEGER DEFAULT 0,
    signals_approved INTEGER DEFAULT 0,
    signals_rejected INTEGER DEFAULT 0,
    orders_created INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,

    execution_details JSONB,
    status VARCHAR(20) DEFAULT 'running',
    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_signal_execution_logs_date ON quant.signal_execution_logs(execution_date);
CREATE INDEX IF NOT EXISTS idx_signal_execution_logs_status ON quant.signal_execution_logs(status);

COMMENT ON TABLE quant.signal_execution_logs IS '信号执行日志表';
COMMENT ON COLUMN quant.signal_execution_logs.execution_details IS 'JSONB格式：strategies, risk_check_summary, orders_summary';

-- 2. Create risk config table
CREATE TABLE IF NOT EXISTS quant.risk_config (
    id SERIAL PRIMARY KEY,
    config_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT true,

    max_single_order_percent DECIMAL(5,2) DEFAULT 20.00,
    max_daily_trade_amount DECIMAL(15,2),
    min_cash_reserve_percent DECIMAL(5,2) DEFAULT 10.00,

    max_position_percent DECIMAL(5,2) DEFAULT 30.00,
    max_sector_percent DECIMAL(5,2) DEFAULT 40.00,
    max_total_position_percent DECIMAL(5,2) DEFAULT 95.00,

    max_daily_trades INTEGER DEFAULT 50,
    max_single_stock_trades INTEGER DEFAULT 5,

    require_stop_loss BOOLEAN DEFAULT true,
    min_stop_loss_percent DECIMAL(5,2) DEFAULT 3.00,
    max_stop_loss_percent DECIMAL(5,2) DEFAULT 15.00,

    config_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE quant.risk_config IS '风控配置表';

-- Insert default config
INSERT INTO quant.risk_config (config_name) VALUES ('default')
ON CONFLICT (config_name) DO NOTHING;

-- 3. Extend signals table (skip if column already exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'quant'
        AND table_name = 'signals'
        AND column_name = 'reject_reason'
    ) THEN
        ALTER TABLE quant.signals ADD COLUMN reject_reason TEXT;
        COMMENT ON COLUMN quant.signals.reject_reason IS '风控拒绝原因';
    END IF;
END $$;

-- 4. Add helper function for querying trades by date and symbol
CREATE OR REPLACE FUNCTION quant.get_trades_by_date_and_symbol(
    p_date DATE,
    p_symbol VARCHAR
)
RETURNS TABLE (
    id BIGINT,
    symbol TEXT,
    action TEXT,
    quantity INTEGER,
    price DOUBLE PRECISION,
    trade_date DATE,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        t.id,
        t.symbol,
        t.action,
        t.quantity,
        t.price,
        t.trade_date,
        t.created_at
    FROM quant.trades t
    WHERE t.trade_date = p_date
    AND t.symbol = p_symbol
    ORDER BY t.created_at DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION quant.get_trades_by_date_and_symbol IS '查询指定日期和股票的交易记录';
