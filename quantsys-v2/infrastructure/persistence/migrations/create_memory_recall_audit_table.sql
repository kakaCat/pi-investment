-- 记忆召回审计表（P1-T4，2026-08-13）
-- ⚠️ 已作废（2026-10-05 · REQ-261004202231-bb99）：v2 记忆子系统已下线——
-- 15 个 /api/memory* 端点全 404，domain/memory 与记忆仓储已删，记忆能力归 agent 侧（agent-os）。
-- 本脚本**仅作历史与回滚依据保留，请勿再执行**；生产表已于同需求 t7 处置（先 pg_dump 再 DROP）。
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
