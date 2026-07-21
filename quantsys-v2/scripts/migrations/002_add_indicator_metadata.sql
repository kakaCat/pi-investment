-- ============================================================
-- Migration: 002_add_indicator_metadata
-- Description: 扩展 quant.strategy_configs 表以支持指标社区功能
-- Created: 2026-05-24
-- ============================================================

-- 添加 is_public 字段（社区发布）
ALTER TABLE quant.strategy_configs
ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE;

-- 添加 category 字段（指标分类）
ALTER TABLE quant.strategy_configs
ADD COLUMN IF NOT EXISTS category VARCHAR(50);

-- 添加 favorite_count 字段（收藏数）
ALTER TABLE quant.strategy_configs
ADD COLUMN IF NOT EXISTS favorite_count INTEGER DEFAULT 0;

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_strategy_is_public ON quant.strategy_configs(is_public);
CREATE INDEX IF NOT EXISTS idx_strategy_category ON quant.strategy_configs(category);

COMMENT ON COLUMN quant.strategy_configs.is_public IS '是否发布到社区';
COMMENT ON COLUMN quant.strategy_configs.category IS '指标分类: trend, momentum, volatility, volume, custom';
COMMENT ON COLUMN quant.strategy_configs.favorite_count IS '收藏数';

-- 验证
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'quant'
        AND table_name = 'strategy_configs'
        AND column_name = 'is_public'
    ) THEN
        RAISE EXCEPTION 'Migration failed: is_public column not added';
    END IF;

    RAISE NOTICE 'Migration 002_add_indicator_metadata completed successfully';
END $$;
