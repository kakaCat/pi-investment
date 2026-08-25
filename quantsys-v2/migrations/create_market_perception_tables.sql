-- M1 市场感知三表（RFC 007）
-- 已于 2026-08-21 应用到生产 PG，本文件存档用

-- 1. market_regime: 每日 regime 判定（trend_up/trend_down/range/panic/euphoria）
CREATE TABLE IF NOT EXISTS quant.market_regime (
    trade_date DATE PRIMARY KEY,
    regime VARCHAR(20) NOT NULL,  -- trend_up/trend_down/range/panic/euphoria
    index_trend_score NUMERIC(5,2),  -- 指数趋势得分 [-1,1]
    sentiment_score NUMERIC(5,2),  -- 情绪分 [0,100]
    volume_ratio NUMERIC(8,2),  -- 量能比
    ad_ratio NUMERIC(8,2),  -- 涨跌家数比
    reason TEXT NOT NULL,  -- 判定依据（含全部指标值）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE quant.market_regime IS 'M1-1 每日市场 regime 判定（RFC 007）';

-- 2. market_sentiment_daily: 涨跌家数/新高新低/量能/波动率时间序列
CREATE TABLE IF NOT EXISTS quant.market_sentiment_daily (
    trade_date DATE PRIMARY KEY,
    up_count INTEGER,
    down_count INTEGER,
    flat_count INTEGER,
    ad_ratio NUMERIC(8,4),  -- 涨跌家数比
    new_high_count INTEGER,
    new_low_count INTEGER,
    volume_ratio NUMERIC(8,2),  -- 量能比（近5日 vs 近20日）
    total_turnover NUMERIC(20,2),  -- 总成交额
    volatility NUMERIC(8,4),  -- 波动率
    fear_greed_index NUMERIC(5,2),  -- 恐慌贪婪指数 [0,100]
    coverage INTEGER,  -- 样本覆盖数（自查：up+down+flat）
    partial BOOLEAN DEFAULT FALSE,  -- coverage < 4000 时为 true（K线同步未完成）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE quant.market_sentiment_daily IS 'M1-3 每日情绪时间序列（RFC 007）';

-- 3. market_theme: 每日涨停聚类主线识别（Top3）
CREATE TABLE IF NOT EXISTS quant.market_theme (
    id SERIAL PRIMARY KEY,
    trade_date DATE NOT NULL,
    rank INTEGER NOT NULL,  -- 1/2/3
    theme VARCHAR(100),  -- 主题名（初始=sector，LLM 回写优化）
    sector VARCHAR(100) NOT NULL,  -- 所属行业（聚类依据）
    limit_up_count INTEGER NOT NULL,  -- 涨停只数
    stocks JSONB NOT NULL,  -- 成分股列表 [{symbol,name,change_pct}]
    fund_flow NUMERIC(12,2),  -- 封板资金合计（亿）
    catalyst TEXT,  -- 催化剂（盘后例程 LLM 回写）
    confidence NUMERIC(3,2) DEFAULT 0.5,  -- 置信度 [0,1]
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(trade_date, rank)
);
CREATE INDEX IF NOT EXISTS idx_market_theme_date ON quant.market_theme(trade_date);
COMMENT ON TABLE quant.market_theme IS 'M1-2 每日涨停聚类主线识别（RFC 007）';
