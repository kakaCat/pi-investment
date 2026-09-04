-- 为定时任务表添加 executor_type 字段
-- 记录定时任务的执行主体：system=后端自动执行 / agent=交给AI agent处理 / both=系统与agent协同
--
-- 执行日期: 2026-09-03
-- 作者: PI 投资顾问·投资脑 (investor, w-8366e526)
-- 背景: 排查 v2(quant.scheduler_tasks) 与 Agent OS(public.tasks) 两套调度任务时，
--       需要区分"纯后端自动任务"与"交给 agent 的任务"。Agent OS 8080 实际读写
--       quant_investment 库的 public.tasks（见 agent-os/config.yaml dbname=quant_investment）。
--
-- 覆盖 3 张表：
--   1. quant.scheduler_tasks          (quant_investment 库, v2 进程内任务, 21 行)
--   2. public.tasks                   (quant_investment 库, Agent OS 8080 在用, 13 行)
--   3. agent_os 库 public.tasks       (旧遗留, fin-agent 任务, 9 行)
-- 幂等，可重复执行。

-- ============ 1. quant_investment.quant.scheduler_tasks ============
ALTER TABLE quant.scheduler_tasks
ADD COLUMN IF NOT EXISTS executor_type VARCHAR(20) DEFAULT 'system' NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='scheduler_tasks_executor_type_check') THEN
    ALTER TABLE quant.scheduler_tasks ADD CONSTRAINT scheduler_tasks_executor_type_check
      CHECK (executor_type IN ('system','agent','both'));
  END IF;
END $$;

COMMENT ON COLUMN quant.scheduler_tasks.executor_type
  IS '执行主体: system=后端自动执行, agent=交给AI agent处理, both=系统与agent协同';

-- 回填：v2 scheduler_tasks 全部由后端进程执行 → system
UPDATE quant.scheduler_tasks SET executor_type='system' WHERE executor_type = 'system' AND name NOT IN (
  -- 若未来某个 v2 任务实际唤起 agent，在此列出并改值
  '___none___'
);

-- ============ 2. quant_investment.public.tasks (Agent OS 8080 在用) ============
ALTER TABLE tasks
ADD COLUMN IF NOT EXISTS executor_type VARCHAR(20) DEFAULT 'system' NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='tasks_executor_type_check') THEN
    ALTER TABLE tasks ADD CONSTRAINT tasks_executor_type_check
      CHECK (executor_type IN ('system','agent','both'));
  END IF;
END $$;

COMMENT ON COLUMN tasks.executor_type
  IS '执行主体: system=后端自动执行, agent=交给AI agent处理, both=系统与agent协同';

-- 回填：Agent OS 中 investor/agent-dh 任务 = dsh-native 唤起 agent → agent
UPDATE tasks SET executor_type='agent'
WHERE owner IN ('investor','agent-dh') AND executor_type = 'system';

-- ============ 3. agent_os 库 public.tasks (旧遗留 fin-agent) ============
-- 注意：需在 agent_os 库单独执行（本脚本连接的是 quant_investment 库时跳过）
-- \connect agent_os
-- ALTER TABLE public.tasks ADD COLUMN IF NOT EXISTS executor_type VARCHAR(20) DEFAULT 'system' NOT NULL;
-- UPDATE public.tasks SET executor_type='agent' WHERE owner='fin-agent' AND executor_type='system';
-- DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='tasks_executor_type_check') THEN
--   ALTER TABLE public.tasks ADD CONSTRAINT tasks_executor_type_check CHECK (executor_type IN ('system','agent','both'));
-- END IF; END $$;
-- COMMENT ON COLUMN public.tasks.executor_type IS '执行主体: system=后端自动执行, agent=交给AI agent处理, both=系统与agent协同';

-- 回滚脚本（如需要）:
-- ALTER TABLE quant.scheduler_tasks DROP CONSTRAINT IF EXISTS scheduler_tasks_executor_type_check;
-- ALTER TABLE quant.scheduler_tasks DROP COLUMN IF EXISTS executor_type;
-- ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_executor_type_check;
-- ALTER TABLE tasks DROP COLUMN IF EXISTS executor_type;
