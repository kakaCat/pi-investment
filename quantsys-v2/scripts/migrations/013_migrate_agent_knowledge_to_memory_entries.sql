-- 013_migrate_agent_knowledge_to_memory_entries.sql
-- ⚠️ 已作废（2026-10-05 · REQ-261004202231-bb99）：v2 记忆子系统已下线——
-- 15 个 /api/memory* 端点全 404，domain/memory 与记忆仓储已删，记忆能力归 agent 侧（agent-os）。
-- 本脚本**仅作历史与回滚依据保留，请勿再执行**；生产表已于同需求 t7 处置（先 pg_dump 再 DROP）。
-- 数据迁移：quant.agent_knowledge 现有 8 条缠论知识 → memory_entries
-- 迁移策略：kind=experience, source=distiller, provenance 标记 chan_weekly
-- 原表保留不动（向后兼容）

INSERT INTO quant.memory_entries (
    kind,
    scope,
    title,
    content,
    payload,
    evidence,
    status,
    confidence,
    validation_count,
    success_count,
    provenance,
    source,
    created_at
)
SELECT
    'experience' AS kind,
    'global' AS scope,
    knowledge_id AS title,
    content::text AS content,
    content AS payload,
    COALESCE(evidence, '{}'::jsonb) AS evidence,
    status,
    COALESCE(confidence, 0.5) AS confidence,
    COALESCE(validation_count, 0) AS validation_count,
    COALESCE(success_count, 0) AS success_count,
    jsonb_build_object(
        'session_kind', 'distiller',
        'channel', 'chan_weekly',
        'migrated_from', 'agent_knowledge'
    ) AS provenance,
    'distiller' AS source,
    learned_at AS created_at
FROM quant.agent_knowledge
WHERE NOT EXISTS (
    SELECT 1 FROM quant.memory_entries
    WHERE title = agent_knowledge.knowledge_id
      AND source = 'distiller'
);

-- 验证迁移结果（注释掉，仅供手动验证时使用）
-- SELECT COUNT(*) AS migrated_count FROM quant.memory_entries WHERE source = 'distiller' AND provenance->>'migrated_from' = 'agent_knowledge';
