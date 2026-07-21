-- QuantSys V2 自动化系统数据库表
-- 创建时间: 2026-06-24

-- 1. 自动化任务表
CREATE TABLE IF NOT EXISTS quant.automation_tasks (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL UNIQUE,
    task_type VARCHAR(20) NOT NULL CHECK (task_type IN ('scheduled', 'event', 'condition')),
    schedule_config JSONB,              -- Cron 表达式或事件配置
    condition_rules JSONB,              -- 条件触发规则
    agent_tool VARCHAR(50),             -- 对应的 agent 工具名
    api_endpoint VARCHAR(200),          -- API 端点
    params JSONB DEFAULT '{}',          -- 任务参数
    priority INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    is_enabled BOOLEAN DEFAULT true,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(50),
    description TEXT
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_automation_tasks_type ON quant.automation_tasks(task_type);
CREATE INDEX IF NOT EXISTS idx_automation_tasks_enabled ON quant.automation_tasks(is_enabled);
CREATE INDEX IF NOT EXISTS idx_automation_tasks_next_run ON quant.automation_tasks(next_run_at) WHERE is_enabled = true;

-- 注释
COMMENT ON TABLE quant.automation_tasks IS '自动化任务定义表';
COMMENT ON COLUMN quant.automation_tasks.task_type IS '任务类型: scheduled(定时), event(事件), condition(条件)';
COMMENT ON COLUMN quant.automation_tasks.schedule_config IS 'Cron表达式 {"cron": "0 9 * * 1-5"} 或事件配置';
COMMENT ON COLUMN quant.automation_tasks.condition_rules IS '条件规则 {"metric": "sh_index_change", "operator": "<", "threshold": -0.03}';
COMMENT ON COLUMN quant.automation_tasks.priority IS '优先级 1-10，数字越大优先级越高';

-- 2. 任务执行历史表
CREATE TABLE IF NOT EXISTS quant.automation_runs (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES quant.automation_tasks(id) ON DELETE CASCADE,
    run_id VARCHAR(50) NOT NULL UNIQUE,
    trigger_type VARCHAR(20) NOT NULL CHECK (trigger_type IN ('scheduled', 'manual', 'condition', 'event')),
    trigger_by VARCHAR(50),              -- 'system', 'agent', 'user:{id}'
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'success', 'failed', 'timeout', 'cancelled')),
    result JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,
    retry_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_automation_runs_task ON quant.automation_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_automation_runs_status ON quant.automation_runs(status);
CREATE INDEX IF NOT EXISTS idx_automation_runs_started ON quant.automation_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_automation_runs_run_id ON quant.automation_runs(run_id);

-- 注释
COMMENT ON TABLE quant.automation_runs IS '自动化任务执行历史';
COMMENT ON COLUMN quant.automation_runs.trigger_type IS '触发方式: scheduled(定时), manual(手动), condition(条件), event(事件)';
COMMENT ON COLUMN quant.automation_runs.status IS '执行状态: pending, running, success, failed, timeout, cancelled';

-- 3. 条件监控表
CREATE TABLE IF NOT EXISTS quant.condition_monitors (
    id SERIAL PRIMARY KEY,
    monitor_name VARCHAR(100) NOT NULL UNIQUE,
    condition_type VARCHAR(50) NOT NULL CHECK (condition_type IN ('market', 'position', 'strategy', 'custom')),
    condition_expression TEXT NOT NULL,  -- 条件表达式
    check_interval INTEGER DEFAULT 60,   -- 检查间隔（秒）
    triggered_task_id INTEGER REFERENCES quant.automation_tasks(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT true,
    last_check_at TIMESTAMP,
    last_check_result BOOLEAN,
    last_triggered_at TIMESTAMP,
    trigger_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    description TEXT,
    metadata JSONB DEFAULT '{}'
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_condition_monitors_active ON quant.condition_monitors(is_active);
CREATE INDEX IF NOT EXISTS idx_condition_monitors_type ON quant.condition_monitors(condition_type);
CREATE INDEX IF NOT EXISTS idx_condition_monitors_next_check ON quant.condition_monitors(last_check_at, check_interval) WHERE is_active = true;

-- 注释
COMMENT ON TABLE quant.condition_monitors IS '条件监控器配置';
COMMENT ON COLUMN quant.condition_monitors.condition_type IS '条件类型: market(市场), position(持仓), strategy(策略), custom(自定义)';
COMMENT ON COLUMN quant.condition_monitors.check_interval IS '检查间隔，单位秒';

-- 4. 任务依赖关系表
CREATE TABLE IF NOT EXISTS quant.task_dependencies (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES quant.automation_tasks(id) ON DELETE CASCADE,
    depends_on_task_id INTEGER NOT NULL REFERENCES quant.automation_tasks(id) ON DELETE CASCADE,
    dependency_type VARCHAR(20) DEFAULT 'success' CHECK (dependency_type IN ('success', 'completion', 'always')),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(task_id, depends_on_task_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_task_dependencies_task ON quant.task_dependencies(task_id);
CREATE INDEX IF NOT EXISTS idx_task_dependencies_depends ON quant.task_dependencies(depends_on_task_id);

-- 注释
COMMENT ON TABLE quant.task_dependencies IS '任务依赖关系';
COMMENT ON COLUMN quant.task_dependencies.dependency_type IS '依赖类型: success(成功后), completion(完成后), always(总是)';

-- 5. 自动化日志表
CREATE TABLE IF NOT EXISTS quant.automation_logs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50) REFERENCES quant.automation_runs(run_id) ON DELETE CASCADE,
    log_level VARCHAR(10) NOT NULL CHECK (log_level IN ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_automation_logs_run ON quant.automation_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_automation_logs_level ON quant.automation_logs(log_level);
CREATE INDEX IF NOT EXISTS idx_automation_logs_created ON quant.automation_logs(created_at DESC);

-- 注释
COMMENT ON TABLE quant.automation_logs IS '自动化任务执行日志';

-- 6. 创建更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为需要的表添加触发器
DROP TRIGGER IF EXISTS update_automation_tasks_updated_at ON quant.automation_tasks;
CREATE TRIGGER update_automation_tasks_updated_at
    BEFORE UPDATE ON quant.automation_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_condition_monitors_updated_at ON quant.condition_monitors;
CREATE TRIGGER update_condition_monitors_updated_at
    BEFORE UPDATE ON quant.condition_monitors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 7. 插入默认数据
-- 这里可以插入一些预定义的自动化任务

-- 完成提示
DO $$
BEGIN
    RAISE NOTICE '✓ Automation tables created successfully';
    RAISE NOTICE '  - automation_tasks';
    RAISE NOTICE '  - automation_runs';
    RAISE NOTICE '  - condition_monitors';
    RAISE NOTICE '  - task_dependencies';
    RAISE NOTICE '  - automation_logs';
END $$;
