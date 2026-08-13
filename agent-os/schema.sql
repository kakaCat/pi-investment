-- Agent OS Database Schema
-- Version: 0.1.0
-- Created: 2026-08-13

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- SCHEDULER MODULE
-- ============================================================================

-- Tasks table: stores task definitions
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    schedule VARCHAR(100), -- cron expression
    command TEXT NOT NULL, -- CLI command to execute
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(100), -- agent ID
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_tasks_name ON tasks(name);
CREATE INDEX idx_tasks_enabled ON tasks(enabled);
CREATE INDEX idx_tasks_schedule ON tasks(schedule) WHERE schedule IS NOT NULL;

-- Task runs table: stores execution history
CREATE TABLE IF NOT EXISTS task_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL, -- pending, running, success, failed, timeout
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    finished_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    output TEXT,
    error TEXT,
    triggered_by VARCHAR(100), -- scheduler, manual, webhook
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_task_runs_task_id ON task_runs(task_id);
CREATE INDEX idx_task_runs_status ON task_runs(status);
CREATE INDEX idx_task_runs_started_at ON task_runs(started_at DESC);

-- Task dependencies table: DAG dependencies
CREATE TABLE IF NOT EXISTS task_dependencies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on_task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(task_id, depends_on_task_id),
    CHECK(task_id != depends_on_task_id)
);

CREATE INDEX idx_task_deps_task_id ON task_dependencies(task_id);
CREATE INDEX idx_task_deps_depends_on ON task_dependencies(depends_on_task_id);

-- ============================================================================
-- RESOURCE MANAGEMENT MODULE
-- ============================================================================

-- Namespaces table: agent namespaces
CREATE TABLE IF NOT EXISTS namespaces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE, -- e.g., fin-agent, memory-agent
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_namespaces_name ON namespaces(name);

-- Resource quotas table: quota limits per namespace
CREATE TABLE IF NOT EXISTS resource_quotas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    namespace_id UUID NOT NULL REFERENCES namespaces(id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL, -- cpu, memory, api_calls, tokens
    limit_value BIGINT NOT NULL,
    used_value BIGINT DEFAULT 0,
    unit VARCHAR(20), -- cores, mb, count, tokens
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(namespace_id, resource_type)
);

CREATE INDEX idx_quotas_namespace ON resource_quotas(namespace_id);
CREATE INDEX idx_quotas_resource_type ON resource_quotas(resource_type);

-- Resource usage log: historical usage tracking
CREATE TABLE IF NOT EXISTS resource_usage_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    namespace_id UUID NOT NULL REFERENCES namespaces(id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL,
    amount BIGINT NOT NULL,
    operation VARCHAR(20) NOT NULL, -- allocate, release
    task_run_id UUID REFERENCES task_runs(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_usage_log_namespace ON resource_usage_log(namespace_id);
CREATE INDEX idx_usage_log_created_at ON resource_usage_log(created_at DESC);

-- ============================================================================
-- MEMORY MODULE
-- ============================================================================

-- Memories table: agent memory storage
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    namespace_id UUID NOT NULL REFERENCES namespaces(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    category VARCHAR(50), -- user, feedback, project, reference
    importance FLOAT DEFAULT 0.5, -- 0.0 to 1.0
    embedding TEXT, -- TODO: change to vector(768) in WP-3 when pgvector is installed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    accessed_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_memories_namespace ON memories(namespace_id);
CREATE INDEX idx_memories_category ON memories(category);
CREATE INDEX idx_memories_importance ON memories(importance DESC);
CREATE INDEX idx_memories_created_at ON memories(created_at DESC);
CREATE INDEX idx_memories_accessed_count ON memories(accessed_count DESC);

-- Memory tags table: tagging system
CREATE TABLE IF NOT EXISTS memory_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    tag VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(memory_id, tag)
);

CREATE INDEX idx_memory_tags_memory_id ON memory_tags(memory_id);
CREATE INDEX idx_memory_tags_tag ON memory_tags(tag);

-- ============================================================================
-- DECISION SYSTEM MODULE
-- ============================================================================

-- Decisions table: stores agent decisions
CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    namespace_id UUID NOT NULL REFERENCES namespaces(id) ON DELETE CASCADE,
    decision_type VARCHAR(50) NOT NULL, -- watch, buy, sell, adjust
    action TEXT NOT NULL,
    reasoning TEXT,
    confidence FLOAT, -- 0.0 to 1.0
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected, executed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    executed_at TIMESTAMP WITH TIME ZONE,
    result JSONB,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_decisions_namespace ON decisions(namespace_id);
CREATE INDEX idx_decisions_type ON decisions(decision_type);
CREATE INDEX idx_decisions_status ON decisions(status);
CREATE INDEX idx_decisions_created_at ON decisions(created_at DESC);

-- ============================================================================
-- PERMISSIONS MODULE
-- ============================================================================

-- Permissions table: defines what actions each namespace can perform
CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    namespace_id UUID NOT NULL REFERENCES namespaces(id) ON DELETE CASCADE,
    resource VARCHAR(100) NOT NULL, -- e.g., trading, memory, data
    action VARCHAR(50) NOT NULL, -- e.g., read, write, execute
    allowed BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(namespace_id, resource, action)
);

CREATE INDEX idx_permissions_namespace ON permissions(namespace_id);
CREATE INDEX idx_permissions_resource ON permissions(resource);

-- ============================================================================
-- EVENT BUS MODULE
-- ============================================================================

-- Events table: event log for system-wide events
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL, -- task.completed, decision.made, quota.exceeded
    source VARCHAR(100), -- namespace or system component
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_source ON events(source);
CREATE INDEX idx_events_created_at ON events(created_at DESC);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Active tasks view
CREATE OR REPLACE VIEW active_tasks AS
SELECT
    t.id,
    t.name,
    t.description,
    t.schedule,
    t.enabled,
    COUNT(tr.id) as total_runs,
    MAX(tr.started_at) as last_run_at,
    CASE
        WHEN MAX(tr.started_at) IS NULL THEN NULL
        ELSE (SELECT status FROM task_runs WHERE task_id = t.id ORDER BY started_at DESC LIMIT 1)
    END as last_run_status
FROM tasks t
LEFT JOIN task_runs tr ON t.id = tr.task_id
WHERE t.enabled = true
GROUP BY t.id, t.name, t.description, t.schedule, t.enabled;

-- Resource quota usage view
CREATE OR REPLACE VIEW quota_usage AS
SELECT
    n.name as namespace,
    rq.resource_type,
    rq.limit_value,
    rq.used_value,
    ROUND((rq.used_value::float / NULLIF(rq.limit_value, 0) * 100)::numeric, 2) as usage_percent,
    rq.unit
FROM resource_quotas rq
JOIN namespaces n ON rq.namespace_id = n.id
ORDER BY usage_percent DESC NULLS LAST;

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to relevant tables
CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_quotas_updated_at BEFORE UPDATE ON resource_quotas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_memories_updated_at BEFORE UPDATE ON memories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SEED DATA
-- ============================================================================

-- Insert default namespaces
INSERT INTO namespaces (name, description, metadata) VALUES
    ('fin-agent', 'Financial Agent - Full trading permissions', '{"role": "trading"}'),
    ('memory-agent', 'Memory Agent - Read-only memory access', '{"role": "memory"}'),
    ('research-agent', 'Research Agent - Market data access', '{"role": "research"}'),
    ('system', 'System namespace for internal operations', '{"role": "system"}')
ON CONFLICT (name) DO NOTHING;

-- Insert default permissions
WITH ns AS (SELECT id, name FROM namespaces)
INSERT INTO permissions (namespace_id, resource, action, allowed)
SELECT
    ns.id,
    perm.resource,
    perm.action,
    perm.allowed
FROM ns
CROSS JOIN LATERAL (
    VALUES
        -- fin-agent: full permissions
        ('trading', 'read', true),
        ('trading', 'write', true),
        ('trading', 'execute', true),
        ('memory', 'read', true),
        ('memory', 'write', true),
        ('data', 'read', true),
        ('scheduler', 'read', true),
        ('scheduler', 'write', true)
) AS perm(resource, action, allowed)
WHERE ns.name = 'fin-agent'

UNION ALL

SELECT
    ns.id,
    perm.resource,
    perm.action,
    perm.allowed
FROM ns
CROSS JOIN LATERAL (
    VALUES
        -- memory-agent: memory-only permissions
        ('memory', 'read', true),
        ('memory', 'write', true),
        ('trading', 'read', false),
        ('trading', 'write', false),
        ('trading', 'execute', false)
) AS perm(resource, action, allowed)
WHERE ns.name = 'memory-agent'

UNION ALL

SELECT
    ns.id,
    perm.resource,
    perm.action,
    perm.allowed
FROM ns
CROSS JOIN LATERAL (
    VALUES
        -- research-agent: read-only permissions
        ('data', 'read', true),
        ('memory', 'read', true),
        ('trading', 'read', true),
        ('trading', 'write', false),
        ('trading', 'execute', false)
) AS perm(resource, action, allowed)
WHERE ns.name = 'research-agent'

ON CONFLICT (namespace_id, resource, action) DO NOTHING;

-- Insert default quotas
WITH ns AS (SELECT id, name FROM namespaces)
INSERT INTO resource_quotas (namespace_id, resource_type, limit_value, unit)
SELECT
    ns.id,
    quota.resource_type,
    quota.limit_value,
    quota.unit
FROM ns
CROSS JOIN LATERAL (
    VALUES
        ('api_calls', 10000, 'count'),
        ('tokens', 1000000, 'tokens'),
        ('memory', 512, 'mb')
) AS quota(resource_type, limit_value, unit)
WHERE ns.name IN ('fin-agent', 'memory-agent', 'research-agent')
ON CONFLICT (namespace_id, resource_type) DO NOTHING;
