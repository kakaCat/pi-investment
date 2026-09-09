-- Feature: Agent OS 错误事件收集与处置系统
-- 2026-09-10: 错误事件从「看板 tail 日志快照」升级为「agent-os 结构化落库 + 状态机处置」。
-- 来源：① scheduler 任务执行失败（executor 挂钩，含 task_id/task_name）② 三端日志（v2/os/dsh）tail 采集器
-- 指纹去重：同 fingerprint 反复出现只 occurrence_count+1（last_seen_at 刷新），不刷屏；
--            resolved 后同指纹再出现自动复开（status 回 open）。
-- 状态机：open→processing(claim/dispatch)→resolved/ignored；resolved/ignored 为终态（复开除外）。

CREATE TABLE IF NOT EXISTS error_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source VARCHAR(20) NOT NULL,                  -- os/v2/dsh（产生端）
    task_id VARCHAR(100),                          -- 关联任务（scheduler 失败时有）
    task_name VARCHAR(255),
    level VARCHAR(20) NOT NULL DEFAULT 'error',    -- error/fatal/critical
    msg TEXT NOT NULL,                             -- 错误摘要（列表展示）
    detail TEXT,                                   -- 完整错误/堆栈/日志行
    fingerprint VARCHAR(64) NOT NULL,              -- 去重哈希（source+task+msg 归一）
    status VARCHAR(20) NOT NULL DEFAULT 'open',    -- open/processing/resolved/ignored
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    assignee VARCHAR(100),                         -- 处置窗口（w-xxx 或 agent id）
    dispatched_session VARCHAR(100),               -- 投递的窗口会话 id
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_note TEXT,                          -- resolve/ignore 说明
    metadata JSONB DEFAULT '{}'::jsonb,            -- 扩展（日志文件/行号/调用栈等）
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_error_events_fingerprint ON error_events(fingerprint);
CREATE INDEX IF NOT EXISTS idx_error_events_status ON error_events(status);
CREATE INDEX IF NOT EXISTS idx_error_events_source ON error_events(source);
CREATE INDEX IF NOT EXISTS idx_error_events_last_seen ON error_events(last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_events_task ON error_events(task_id) WHERE task_id IS NOT NULL;

COMMENT ON TABLE error_events IS 'Agent OS 错误事件收集与处置：scheduler 失败源头 + 三端日志 tail 采集，指纹去重 + 状态机';
COMMENT ON COLUMN error_events.fingerprint IS '去重哈希：source+task_id+归一 msg 的 sha256，同错误只增 occurrence_count';
COMMENT ON COLUMN error_events.status IS '状态机：open→processing(claim/dispatch)→resolved/ignored；resolved 后同指纹复现自动复开';
