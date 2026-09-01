-- 添加 task_type 字段到 scheduler_tasks 表
-- 用于区分定时任务(cron)、延迟任务(delay)、间隔任务(interval)、一次性任务(once)
--
-- 执行日期: 2026-09-01
-- 作者: System

BEGIN;

-- 1. 添加 task_type 字段
ALTER TABLE quant.scheduler_tasks
ADD COLUMN task_type VARCHAR(20) DEFAULT 'cron' NOT NULL;

-- 2. 添加检查约束
ALTER TABLE quant.scheduler_tasks
ADD CONSTRAINT scheduler_tasks_task_type_check
CHECK (task_type IN ('cron', 'delay', 'interval', 'once'));

-- 3. 添加注释
COMMENT ON COLUMN quant.scheduler_tasks.task_type IS '任务类型: cron=定时任务, delay=延迟任务, interval=间隔任务, once=一次性任务';

-- 4. 根据现有 cron_expression 推断任务类型（数据迁移）
UPDATE quant.scheduler_tasks
SET task_type = CASE
    WHEN cron_expression LIKE 'DELAY:%' THEN 'delay'
    WHEN cron_expression LIKE 'INTERVAL:%' THEN 'interval'
    WHEN cron_expression ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' THEN 'once'  -- ISO格式日期开头
    ELSE 'cron'
END;

-- 5. 创建索引（可选，用于快速查询不同类型的任务）
CREATE INDEX idx_scheduler_tasks_task_type ON quant.scheduler_tasks(task_type);

COMMIT;

-- 回滚脚本（如需要）
-- BEGIN;
-- DROP INDEX IF EXISTS quant.idx_scheduler_tasks_task_type;
-- ALTER TABLE quant.scheduler_tasks DROP CONSTRAINT IF EXISTS scheduler_tasks_task_type_check;
-- ALTER TABLE quant.scheduler_tasks DROP COLUMN IF EXISTS task_type;
-- COMMIT;
