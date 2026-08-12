-- 012_create_memory_entries_table_no_vector.sql
-- 统一记忆存储：替代散落的 MEMORY.md/daily jsonl/experience-base.json/agent_knowledge
-- 设计：docs/superpowers/plans/2026-08-12-framework-evolution-roadmap.md W1.2
-- 临时版本：不使用 pgvector（embedding 使用 TEXT 存储 JSON）

-- 统一记忆条目表
CREATE TABLE IF NOT EXISTS quant.memory_entries (
    id                  BIGSERIAL PRIMARY KEY,
    kind                TEXT NOT NULL CHECK (kind IN ('rule', 'episode', 'experience', 'stock_note')),
    scope               TEXT NOT NULL DEFAULT 'global',  -- global | stock:600519 | strategy:v13 | sector:消费
    title               TEXT NOT NULL,
    content             TEXT NOT NULL,
    payload             JSONB,                          -- 结构化数据（experience 的条件/动作等）
    evidence            JSONB,                          -- 证据链：decision_id/trade_id/session_id 等
    status              TEXT NOT NULL DEFAULT 'testing' CHECK (status IN ('testing', 'active', 'deprecated', 'archived')),
    confidence          DOUBLE PRECISION DEFAULT 0.3,
    validation_count    INTEGER DEFAULT 0,
    success_count       INTEGER DEFAULT 0,
    provenance          JSONB NOT NULL,                 -- {session_kind, channel, session_id}
    last_recalled_at    TIMESTAMPTZ,
    source              TEXT,                           -- distiller | agent | manual | recall
    supersedes          BIGINT REFERENCES quant.memory_entries(id) ON DELETE SET NULL,
    embedding           TEXT,                           -- 临时用 TEXT 存储，W1.3 升级为 vector(1024)
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_memory_entries_scope ON quant.memory_entries (scope);
CREATE INDEX IF NOT EXISTS idx_memory_entries_kind ON quant.memory_entries (kind);
CREATE INDEX IF NOT EXISTS idx_memory_entries_status ON quant.memory_entries (status);
CREATE INDEX IF NOT EXISTS idx_memory_entries_kind_status ON quant.memory_entries (kind, status);
CREATE INDEX IF NOT EXISTS idx_memory_entries_scope_status ON quant.memory_entries (scope, status);
CREATE INDEX IF NOT EXISTS idx_memory_entries_created_at ON quant.memory_entries (created_at DESC);

-- 更新时间触发器
CREATE OR REPLACE FUNCTION update_memory_entries_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_memory_entries_updated_at
    BEFORE UPDATE ON quant.memory_entries
    FOR EACH ROW
    EXECUTE FUNCTION update_memory_entries_updated_at();
