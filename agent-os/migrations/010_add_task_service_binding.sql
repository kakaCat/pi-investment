-- Migration: Add service binding to tasks table
-- Date: 2026-08-20
-- Purpose: Allow a scheduled task to declare a required local service
--          (e.g. quantsys-v2). Before executing the task, Agent OS
--          health-checks the bound service and starts it if it is down.

ALTER TABLE tasks
  ADD COLUMN IF NOT EXISTS service_name VARCHAR(255) NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_tasks_service_name
  ON tasks(service_name) WHERE service_name != '';

COMMENT ON COLUMN tasks.service_name IS 'Name of the local service that must be running before the task executes (empty = no binding)';
