-- Add retry_count and updated_at to notification_logs for retry mechanism
-- Migration: 011_add_notification_retry.sql
-- Date: 2026-08-26
-- Purpose: 支持通知投递重试机制，防止 pending 状态永久挂起

-- Add retry_count column (default 0)
ALTER TABLE notification_logs 
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

-- Add updated_at column for tracking retry updates
ALTER TABLE notification_logs 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- Create index on pending status + created_at for efficient stuck log queries
CREATE INDEX IF NOT EXISTS idx_notification_logs_pending_created 
ON notification_logs(status, created_at) 
WHERE status = 'pending';

-- Add comment
COMMENT ON COLUMN notification_logs.retry_count IS '重试次数，0=首次投递，>=1表示已重试';
COMMENT ON COLUMN notification_logs.updated_at IS '最后更新时间，用于追踪重试';
