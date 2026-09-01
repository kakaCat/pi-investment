-- sector 板块列表 DB 快照（2026-09-01，investor w-8366e526）
-- 目的：sector_analysis 数据源（Eastmoney 单一源）故障时，用最近一次成功快照兜底（stale-while-error）
-- 板块列表为每日低频静态数据（496 行业 + 504 概念），同日覆盖、跨日累积
CREATE TABLE IF NOT EXISTS quant.sector_snapshot (
    snapshot_date DATE PRIMARY KEY,              -- 抓取日（同日 UPSERT 覆盖）
    industries JSONB NOT NULL DEFAULT '[]'::jsonb,  -- 行业板块列表
    concepts JSONB NOT NULL DEFAULT '[]'::jsonb,    -- 概念板块列表
    total INT NOT NULL DEFAULT 0,               -- industries + concepts 总数
    source VARCHAR(32) NOT NULL DEFAULT 'eastmoney',  -- 数据源
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
COMMENT ON TABLE quant.sector_snapshot IS 'sector 板块列表 DB 快照——外部数据源故障时的兜底缓存（2026-09-01）';

CREATE INDEX IF NOT EXISTS idx_sector_snapshot_date ON quant.sector_snapshot (snapshot_date DESC);
