-- 记忆召回审计表（P1-T4，2026-08-13）
-- 记录每次记忆召回的门禁结果与命中明细，支撑注入率统计与人工/agent 标注回流
CREATE TABLE IF NOT EXISTS quant.memory_recall_audit (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL,
  session_id TEXT,
  flow TEXT NOT NULL,
  query_text TEXT,
  strategy TEXT,
  degraded BOOLEAN DEFAULT FALSE,
  gate_result TEXT NOT NULL,
  suppress_reason TEXT,
  hits JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_recall_audit_ts ON quant.memory_recall_audit (ts DESC);
CREATE INDEX IF NOT EXISTS idx_recall_audit_flow ON quant.memory_recall_audit (flow);
