-- ============================================================================
-- Scheduler Tables - cron-based task scheduling
-- ============================================================================

CREATE TABLE IF NOT EXISTS quant.scheduler_tasks (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    cron_expression TEXT NOT NULL,  -- standard 5-field: "0 9 * * 1-5"
    command TEXT NOT NULL,          -- e.g. "data_update", "signal_generate", "risk_check"
    params JSONB DEFAULT '{}',
    is_enabled BOOLEAN DEFAULT true,
    last_run_at TIMESTAMPTZ,
    last_status TEXT,               -- 'success', 'failed', 'running'
    last_error TEXT,
    next_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quant_scheduler_tasks_name
    ON quant.scheduler_tasks(name);
CREATE INDEX IF NOT EXISTS idx_quant_scheduler_tasks_is_enabled
    ON quant.scheduler_tasks(is_enabled);
CREATE INDEX IF NOT EXISTS idx_quant_scheduler_tasks_next_run_at
    ON quant.scheduler_tasks(next_run_at);

CREATE TABLE IF NOT EXISTS quant.scheduler_runs (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT REFERENCES quant.scheduler_tasks(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'running',  -- 'running', 'success', 'failed'
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    result JSONB,
    error TEXT,
    duration_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_quant_scheduler_runs_task_id
    ON quant.scheduler_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_quant_scheduler_runs_started_at_desc
    ON quant.scheduler_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_quant_scheduler_runs_status
    ON quant.scheduler_runs(status);

SELECT 'Scheduler tables created successfully!' as status;
