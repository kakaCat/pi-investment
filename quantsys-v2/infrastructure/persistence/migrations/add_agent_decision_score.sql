-- 决策打分列（文本参数进化 P0a，2026-08-07）
-- score: 基准调整后归一化分数 [-1,1]；score_band: big_win/small_win/neutral/small_loss/big_loss
ALTER TABLE quant.agent_decisions ADD COLUMN IF NOT EXISTS score REAL;
ALTER TABLE quant.agent_decisions ADD COLUMN IF NOT EXISTS score_band TEXT;
CREATE INDEX IF NOT EXISTS idx_agent_decisions_score ON quant.agent_decisions(score) WHERE score IS NOT NULL;
