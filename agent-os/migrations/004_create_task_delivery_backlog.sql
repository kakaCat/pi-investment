-- Migration: Task delivery backlog (durable retry for scheduler webhook deliveries)
-- Date: 2026-09-11
-- Author: w-f4aa1f6a (投资脑)
--
-- 背景（实测事故）：agent-os 把定时任务投递给 DSH(:13080) 只有**内存内重试**
-- （MaxRetries=2 + 连接失败递增退避 ≈90s 窗口）。2026-09-11 09:27-11:02 DSH 因内存压力
-- 长时间不可达（>90s），重试耗尽后任务被**直接丢弃**（含 09-10 19:00 的晚间例行），
-- 且没有任何持久化记录可供补投——账面只剩一条 error_event。
--
-- 本表把"投递不进去的任务"持久化，由 TaskDeliveryRetryWorker 在 DSH 恢复后自动补投，
-- 使"任务必达"不再依赖对端在 90 秒内恢复。

CREATE TABLE IF NOT EXISTS task_delivery_backlog (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID,
    task_name       VARCHAR(255),
    webhook_url     TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    attempts        INT NOT NULL DEFAULT 0,
    max_attempts    INT NOT NULL DEFAULT 10,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at    TIMESTAMPTZ
);

-- 只为待投递行建部分索引（热路径：WHERE status='pending' AND next_attempt_at <= now()）
CREATE INDEX IF NOT EXISTS idx_task_delivery_backlog_due
    ON task_delivery_backlog (next_attempt_at)
    WHERE status = 'pending';

COMMENT ON TABLE task_delivery_backlog IS
    '定时任务投递积压队列（2026-09-11 w-f4aa1f6a）：webhook 投递重试耗尽后落库，由 worker 补投';
COMMENT ON COLUMN task_delivery_backlog.status IS 'pending=待补投 / delivered=已投递 / failed=超过最大尝试次数';
