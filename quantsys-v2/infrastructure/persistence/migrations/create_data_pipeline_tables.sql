-- Raw data table (preserves all source data)
CREATE TABLE IF NOT EXISTS quant.raw_klines (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(10,2) NOT NULL,
    high DECIMAL(10,2) NOT NULL,
    low DECIMAL(10,2) NOT NULL,
    close DECIMAL(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    amount DECIMAL(20,2),
    fetch_time TIMESTAMP DEFAULT NOW(),
    UNIQUE(source, symbol, trade_date),
    CHECK (high >= low),
    CHECK (high >= open),
    CHECK (high >= close),
    CHECK (low <= open),
    CHECK (low <= close),
    CHECK (volume >= 0)
);

-- Cleaned data table (merged and validated)
CREATE TABLE IF NOT EXISTS quant.daily_klines (
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(10,2) NOT NULL,
    high DECIMAL(10,2) NOT NULL,
    low DECIMAL(10,2) NOT NULL,
    close DECIMAL(10,2) NOT NULL,
    volume BIGINT NOT NULL,
    amount DECIMAL(20,2),
    adj_factor DECIMAL(10,6) DEFAULT 1.0,
    is_suspended BOOLEAN DEFAULT FALSE,
    quality_score DECIMAL(5,2),
    processed_time TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date),
    CHECK (high >= low),
    CHECK (high >= open),
    CHECK (high >= close),
    CHECK (low <= open),
    CHECK (low <= close),
    CHECK (volume >= 0),
    CHECK (quality_score >= 0 AND quality_score <= 100)
);

-- Factor data table (computed factors)
CREATE TABLE IF NOT EXISTS quant.factors (
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    factor_name VARCHAR(100) NOT NULL,
    factor_value DECIMAL(20,6),
    computed_time TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (symbol, trade_date, factor_name)
);

-- Indexes for performance
-- Composite indexes for common query patterns (symbol + date)
CREATE INDEX IF NOT EXISTS idx_raw_klines_symbol_date ON quant.raw_klines(symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_daily_klines_symbol_date ON quant.daily_klines(symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_factors_symbol_date ON quant.factors(symbol, trade_date);
CREATE INDEX IF NOT EXISTS idx_factors_name_date ON quant.factors(factor_name, trade_date);

-- Trading calendar table (if not exists)
CREATE TABLE IF NOT EXISTS quant.trading_calendar (
    trade_date DATE PRIMARY KEY,
    exchange VARCHAR(10) NOT NULL,
    is_trading_day BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_trading_calendar_exchange ON quant.trading_calendar(exchange);
