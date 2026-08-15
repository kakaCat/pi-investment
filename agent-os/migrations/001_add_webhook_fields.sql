-- Migration: Add webhook and scheduling fields to tasks table
-- Date: 2026-08-15
-- Purpose: Support webhook-based task execution and Agent OS scheduler

-- Add new columns
ALTER TABLE tasks
  ADD COLUMN IF NOT EXISTS owner VARCHAR(255),
  ADD COLUMN IF NOT EXISTS cron VARCHAR(100),
  ADD COLUMN IF NOT EXISTS webhook_url TEXT,
  ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS timeout INT DEFAULT 3600,
  ADD COLUMN IF NOT EXISTS retry_count INT DEFAULT 0;

-- Make command nullable (for webhook-based tasks)
ALTER TABLE tasks ALTER COLUMN command DROP NOT NULL;

-- Update existing tasks to have owner
UPDATE tasks SET owner = created_by WHERE owner IS NULL;

-- Copy schedule to cron for backward compatibility
UPDATE tasks SET cron = schedule WHERE cron IS NULL AND schedule IS NOT NULL;

-- Create index on webhook_url
CREATE INDEX IF NOT EXISTS idx_tasks_webhook_url ON tasks(webhook_url) WHERE webhook_url IS NOT NULL;

-- Create index on owner
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner);

COMMENT ON COLUMN tasks.owner IS 'Agent owner ID';
COMMENT ON COLUMN tasks.cron IS 'Cron expression for scheduling';
COMMENT ON COLUMN tasks.webhook_url IS 'HTTP webhook URL to trigger';
COMMENT ON COLUMN tasks.payload IS 'Task payload sent to webhook';
COMMENT ON COLUMN tasks.timeout IS 'Timeout in seconds';
COMMENT ON COLUMN tasks.retry_count IS 'Max retry count on failure';
