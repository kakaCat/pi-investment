-- 创建分钟线数据表
CREATE TABLE IF NOT EXISTS quant.minute_klines (
    symbol TEXT NOT NULL,
    trade_datetime TIMESTAMP NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    PRIMARY KEY (symbol, trade_datetime),
    CONSTRAINT minute_klines_symbol_fkey
        FOREIGN KEY (symbol)
        REFERENCES quant.stocks(symbol)
        ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_minute_klines_datetime
    ON quant.minute_klines(trade_datetime);

CREATE INDEX IF NOT EXISTS idx_minute_klines_recent
    ON quant.minute_klines(symbol, trade_datetime DESC);

-- 添加注释
COMMENT ON TABLE quant.minute_klines IS '1分钟K线数据表，保留最近1年数据';
COMMENT ON COLUMN quant.minute_klines.symbol IS '股票代码';
COMMENT ON COLUMN quant.minute_klines.trade_datetime IS '交易时间（精确到分钟）';
COMMENT ON COLUMN quant.minute_klines.open IS '开盘价';
COMMENT ON COLUMN quant.minute_klines.high IS '最高价';
COMMENT ON COLUMN quant.minute_klines.low IS '最低价';
COMMENT ON COLUMN quant.minute_klines.close IS '收盘价';
COMMENT ON COLUMN quant.minute_klines.volume IS '成交量';
COMMENT ON COLUMN quant.minute_klines.amount IS '成交额';
