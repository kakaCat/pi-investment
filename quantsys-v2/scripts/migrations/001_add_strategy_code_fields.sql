-- ============================================================
-- Migration: 001_add_strategy_code_fields
-- Description: 扩展 quant.strategy_configs 表以支持用户自定义策略代码
-- Created: 2026-05-22
-- Reference: quantsys-v2/docs/superpowers/specs/strategy-code-execution-engine.md (Chapter 5)
-- ============================================================

-- 添加新字段支持用户自定义策略
ALTER TABLE quant.strategy_configs
ADD COLUMN IF NOT EXISTS code_content TEXT,
ADD COLUMN IF NOT EXISTS code_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS parsed_params JSONB,
ADD COLUMN IF NOT EXISTS risk_config JSONB,
ADD COLUMN IF NOT EXISTS metadata JSONB,
ADD COLUMN IF NOT EXISTS validation_status VARCHAR(50),
ADD COLUMN IF NOT EXISTS validation_errors TEXT,
ADD COLUMN IF NOT EXISTS last_executed_at TIMESTAMP;

-- 添加索引以提升查询性能
CREATE INDEX IF NOT EXISTS idx_strategy_code_type ON quant.strategy_configs(code_type);
CREATE INDEX IF NOT EXISTS idx_strategy_validation_status ON quant.strategy_configs(validation_status);

-- 添加字段注释
COMMENT ON COLUMN quant.strategy_configs.code_content IS '用户自定义策略代码';
COMMENT ON COLUMN quant.strategy_configs.code_type IS '策略类型: builtin(内置), indicator(信号驱动), script(事件驱动)';
COMMENT ON COLUMN quant.strategy_configs.parsed_params IS '从代码中解析的参数定义 @param';
COMMENT ON COLUMN quant.strategy_configs.risk_config IS '从代码中解析的风控配置 @strategy';
COMMENT ON COLUMN quant.strategy_configs.metadata IS '策略元数据(名称、描述等)';
COMMENT ON COLUMN quant.strategy_configs.validation_status IS '验证状态: pending(待验证), valid(有效), invalid(无效)';
COMMENT ON COLUMN quant.strategy_configs.validation_errors IS '验证错误信息';
COMMENT ON COLUMN quant.strategy_configs.last_executed_at IS '最后执行时间';

-- 验证表结构
DO $$
BEGIN
    -- 检查所有字段是否成功添加
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'quant'
        AND table_name = 'strategy_configs'
        AND column_name = 'code_content'
    ) THEN
        RAISE EXCEPTION 'Migration failed: code_content column not added';
    END IF;

    RAISE NOTICE 'Migration 001_add_strategy_code_fields completed successfully';
END $$;
