-- ============================================
-- Agent Session 审计表
-- 创建日期: 2026-07-22
-- 用途: session 事件流持久化（agent 工作质量诊断与 web 可视化）
-- ============================================

CREATE TABLE IF NOT EXISTS quant.agent_sessions (
  session_key      TEXT PRIMARY KEY,
  channel          VARCHAR(20) NOT NULL,
  peer_id          VARCHAR(200) NOT NULL,
  agent_id         VARCHAR(50) NOT NULL DEFAULT 'main',
  started_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_active_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status           VARCHAR(20) NOT NULL DEFAULT 'active',
  message_count    INT DEFAULT 0,
  tool_call_count  INT DEFAULT 0,
  error_count      INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quant.agent_session_events (
  id           BIGSERIAL PRIMARY KEY,
  session_key  TEXT NOT NULL REFERENCES quant.agent_sessions(session_key),
  seq          INT NOT NULL,
  event_type   VARCHAR(30) NOT NULL,
  payload      JSONB NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL,
  UNIQUE(session_key, seq)
);

CREATE INDEX IF NOT EXISTS idx_agent_session_events_type ON quant.agent_session_events(event_type);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_channel ON quant.agent_sessions(channel);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_active ON quant.agent_sessions(last_active_at DESC);

ALTER TABLE quant.agent_decisions ADD COLUMN IF NOT EXISTS session_key TEXT;
CREATE INDEX IF NOT EXISTS idx_agent_decisions_session ON quant.agent_decisions(session_key);

COMMENT ON TABLE quant.agent_sessions IS 'Agent 会话元数据：通道、计数器、活跃状态';
COMMENT ON TABLE quant.agent_session_events IS 'Agent 会话事件流：seq 幂等，支撑诊断与会话回放';
