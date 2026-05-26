-- 创建分钟线数据表（如果不存在）
CREATE TABLE IF NOT EXISTS quant.minute_klines (
    symbol TEXT NOT NULL,
    ts TIMESTAMP WITH TIME ZONE NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    PRIMARY KEY (symbol, ts),
    CONSTRAINT minute_klines_symbol_fkey
        FOREIGN KEY (symbol)
        REFERENCES quant.stocks(symbol)
        ON DELETE CASCADE
);

-- 重命名列以匹配规范（如果表已存在且使用旧列名）
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'quant'
        AND table_name = 'minute_klines'
        AND column_name = 'ts'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'quant'
        AND table_name = 'minute_klines'
        AND column_name = 'trade_datetime'
    ) THEN
        ALTER TABLE quant.minute_klines RENAME COLUMN ts TO trade_datetime;
    END IF;
END $$;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_minute_klines_symbol
    ON quant.minute_klines(symbol);

CREATE INDEX IF NOT EXISTS idx_minute_klines_datetime
    ON quant.minute_klines(trade_datetime);

CREATE INDEX IF NOT EXISTS idx_minute_klines_recent
    ON quant.minute_klines(symbol, trade_datetime DESC);

-- 添加注释
COMMENT ON TABLE quant.minute_klines IS '1分钟K线数据表，保留最近1年数据';
COMMENT ON COLUMN quant.minute_klines.symbol IS '股票代码';
COMMENT ON COLUMN quant.minute_klines.trade_datetime IS '交易时间（精确到分钟）';
