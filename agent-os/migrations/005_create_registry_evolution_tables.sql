-- Agent 注册表 + 进化记录表（registry & evolution APIs）

-- Agent 注册表
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(100) NOT NULL UNIQUE,
    session_id VARCHAR(100),
    agent_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'idle',
    host VARCHAR(255),
    port INT,
    pid INT,
    version VARCHAR(50),
    capabilities TEXT[] DEFAULT '{}',
    metadata JSONB,
    registered_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_heartbeat_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_last_heartbeat ON agents(last_heartbeat_at DESC);

-- 策略进化记录
CREATE TABLE IF NOT EXISTS evolution_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id VARCHAR(50) NOT NULL,
    mode VARCHAR(20) NOT NULL DEFAULT 'propose',
    generations INT NOT NULL DEFAULT 3,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    fitness DOUBLE PRECISION NOT NULL DEFAULT 0,
    fitness_improvement DOUBLE PRECISION NOT NULL DEFAULT 0,
    proposals JSONB,
    best_params JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_evolution_runs_strategy ON evolution_runs(strategy_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_evolution_runs_status ON evolution_runs(status);
