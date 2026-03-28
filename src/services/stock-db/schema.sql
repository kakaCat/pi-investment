-- 股票基础信息表
CREATE TABLE IF NOT EXISTS stocks (
  symbol TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  market TEXT NOT NULL,        -- 'A' or 'HK'
  industry TEXT,                -- 行业
  market_cap REAL,              -- 市值（亿元）
  pe REAL,                      -- 市盈率
  pb REAL,                      -- 市净率
  total_mv REAL,                -- 总市值
  circulating_mv REAL,          -- 流通市值
  is_st INTEGER DEFAULT 0,      -- 是否ST
  is_suspended INTEGER DEFAULT 0, -- 是否停牌
  list_date TEXT,               -- 上市日期
  updated_at TEXT NOT NULL      -- 更新时间
);

-- 日行情快照（用于流动性筛选）
CREATE TABLE IF NOT EXISTS daily_quotes (
  symbol TEXT NOT NULL,
  date TEXT NOT NULL,
  close REAL,
  volume REAL,                  -- 成交量
  amount REAL,                  -- 成交额（万元）
  turnover_rate REAL,           -- 换手率
  PRIMARY KEY (symbol, date)
);

-- 财务指标（季度更新）
CREATE TABLE IF NOT EXISTS financials (
  symbol TEXT NOT NULL,
  report_date TEXT NOT NULL,    -- 报告期
  revenue REAL,                 -- 营收（亿元）
  net_profit REAL,              -- 净利润
  roe REAL,                     -- ROE
  debt_ratio REAL,              -- 资产负债率
  gross_margin REAL,            -- 毛利率
  PRIMARY KEY (symbol, report_date)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_market ON stocks(market);
CREATE INDEX IF NOT EXISTS idx_industry ON stocks(industry);
CREATE INDEX IF NOT EXISTS idx_market_cap ON stocks(market_cap);
CREATE INDEX IF NOT EXISTS idx_pe ON stocks(pe);
CREATE INDEX IF NOT EXISTS idx_updated ON stocks(updated_at);
CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_quotes(date);
