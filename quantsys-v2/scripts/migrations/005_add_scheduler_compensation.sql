-- ============================================================
-- Migration: 005_add_scheduler_compensation
-- Description: Add compensation fields to quant.scheduler_tasks
--   for missed-schedule recovery support.
-- Created: 2026-05-24
-- ============================================================

ALTER TABLE quant.scheduler_tasks ADD COLUMN IF NOT EXISTS compensation_enabled       BOOLEAN DEFAULT FALSE;
ALTER TABLE quant.scheduler_tasks ADD COLUMN IF NOT EXISTS compensation_check_after   TIME;
ALTER TABLE quant.scheduler_tasks ADD COLUMN IF NOT EXISTS compensation_max_attempts  INTEGER DEFAULT 1;

COMMENT ON COLUMN quant.scheduler_tasks.compensation_enabled       IS '是否启用补偿检查';
COMMENT ON COLUMN quant.scheduler_tasks.compensation_check_after   IS '补偿检查等待时间';
COMMENT ON COLUMN quant.scheduler_tasks.compensation_max_attempts  IS '补偿最大重试次数';

DO $$
BEGIN
    RAISE NOTICE 'Migration 005_add_scheduler_compensation completed successfully';
END $$;
