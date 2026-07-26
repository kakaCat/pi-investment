-- Agent Session AI 诊断缓存（2026-07-26）
ALTER TABLE quant.agent_sessions ADD COLUMN IF NOT EXISTS ai_diagnosis JSONB;
ALTER TABLE quant.agent_sessions ADD COLUMN IF NOT EXISTS ai_diagnosis_at TIMESTAMPTZ;
