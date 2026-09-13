-- 迁移脚本：合并 scheduler_task_configs 到 scheduler_tasks
-- 执行前请备份数据库！
-- psql -U mac -d quant_investment -f scripts/migrate_scheduler_tables.sql

BEGIN;

-- 1. 给 scheduler_tasks 添加缺失的字段（如果不存在）
ALTER TABLE quant.scheduler_tasks 
ADD COLUMN IF NOT EXISTS compensation_enabled BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS compensation_check_after TIME,
ADD COLUMN IF NOT EXISTS compensation_max_attempts INTEGER DEFAULT 1,
ADD COLUMN IF NOT EXISTS misfire_grace_time_seconds INTEGER;

-- 2. 从 scheduler_task_configs 迁移数据到 scheduler_tasks（如果 configs 表有数据）
-- 注意：生产环境如果有数据需要先确认迁移逻辑
INSERT INTO quant.scheduler_tasks (name, description, cron_expression, command, params, is_enabled, created_at, updated_at)
SELECT task_name, description, cron_expression, command, params, is_enabled, created_at, updated_at
FROM quant.scheduler_task_configs
ON CONFLICT (name) DO NOTHING;

-- 3. 删除 scheduler_task_configs 表
DROP TABLE IF EXISTS quant.scheduler_task_configs;

-- 4. 删除关联的序列（如果存在）
DROP SEQUENCE IF EXISTS quant.scheduler_task_configs_config_id_seq;

COMMIT;

-- 验证
SELECT 'scheduler_tasks' as table_name, count(*) as row_count FROM quant.scheduler_tasks
UNION ALL
SELECT 'scheduler_runs' as table_name, count(*) as row_count FROM quant.scheduler_runs;
