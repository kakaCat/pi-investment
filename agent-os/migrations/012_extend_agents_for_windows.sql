-- RFC 010: 扩展 agents 表以支持 Window Registry
-- 2026-08-21: 添加 name, instance, offline_at 字段

-- 添加窗口名称（如 "PI投资脑"）
ALTER TABLE agents ADD COLUMN IF NOT EXISTS name VARCHAR(255);

-- 添加实例名（如 "investment"，区分多实例部署）
ALTER TABLE agents ADD COLUMN IF NOT EXISTS instance VARCHAR(64);

-- 添加离线时间（用于超时检测与统计）
ALTER TABLE agents ADD COLUMN IF NOT EXISTS offline_at TIMESTAMP;

-- 添加索引：按 agent_type (role) 查询
CREATE INDEX IF NOT EXISTS idx_agents_type_status ON agents(agent_type, status);

-- 添加索引：按 instance 查询
CREATE INDEX IF NOT EXISTS idx_agents_instance ON agents(instance);

-- 注释说明字段映射（RFC 010 术语）
COMMENT ON COLUMN agents.agent_id IS 'Window ID (e.g., w-29882338)';
COMMENT ON COLUMN agents.agent_type IS 'Role (e.g., investor, market_analyst)';
COMMENT ON COLUMN agents.name IS 'Window name (e.g., PI投资脑)';
COMMENT ON COLUMN agents.instance IS 'Instance name (e.g., investment)';
COMMENT ON COLUMN agents.status IS 'online, offline, timeout, idle, active';
COMMENT ON COLUMN agents.offline_at IS 'Timestamp when status changed to offline/timeout';

-- 更新现有记录的 instance（默认 investment）
UPDATE agents SET instance = 'investment' WHERE instance IS NULL;
