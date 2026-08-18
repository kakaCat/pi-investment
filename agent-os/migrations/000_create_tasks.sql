-- Migration: Create tasks and related tables
-- Date: 2026-08-16
-- Purpose: Create base tables for Agent OS scheduler

-- Create tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    owner VARCHAR(255) NOT NULL,
    description TEXT,
    schedule VARCHAR(100),
    cron VARCHAR(100),
    command TEXT,
    webhook_url TEXT,
    payload JSONB DEFAULT '{}'::jsonb,
    timeout INT DEFAULT 3600,
    retry_count INT DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create task_runs table
CREATE TABLE IF NOT EXISTS task_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP WITH TIME ZONE,
    duration_ms BIGINT,
    output TEXT,
    error TEXT,
    triggered_by VARCHAR(20) NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create task_dependencies table
CREATE TABLE IF NOT EXISTS task_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on_task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(task_id, depends_on_task_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_tasks_enabled ON tasks(enabled);
CREATE INDEX IF NOT EXISTS idx_tasks_schedule ON tasks(schedule) WHERE schedule IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_cron ON tasks(cron) WHERE cron IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_webhook_url ON tasks(webhook_url) WHERE webhook_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner);

CREATE INDEX IF NOT EXISTS idx_task_runs_task_id ON task_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_status ON task_runs(status);
CREATE INDEX IF NOT EXISTS idx_task_runs_started_at ON task_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_task_dependencies_task_id ON task_dependencies(task_id);
CREATE INDEX IF NOT EXISTS idx_task_dependencies_depends_on ON task_dependencies(depends_on_task_id);

-- Add comments
COMMENT ON TABLE tasks IS 'Task definitions for Agent OS scheduler';
COMMENT ON TABLE task_runs IS 'Task execution history';
COMMENT ON TABLE task_dependencies IS 'Task dependencies for DAG execution';

COMMENT ON COLUMN tasks.owner IS 'Agent owner ID';
COMMENT ON COLUMN tasks.cron IS 'Cron expression for scheduling';
COMMENT ON COLUMN tasks.webhook_url IS 'HTTP webhook URL to trigger';
COMMENT ON COLUMN tasks.payload IS 'Task payload sent to webhook';
COMMENT ON COLUMN tasks.timeout IS 'Timeout in seconds';
COMMENT ON COLUMN tasks.retry_count IS 'Max retry count on failure';
