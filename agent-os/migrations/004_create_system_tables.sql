-- 系统日志表
CREATE TABLE IF NOT EXISTS system_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    level VARCHAR(20) NOT NULL CHECK (level IN ('debug', 'info', 'warning', 'error', 'critical')),
    source VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    details JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 命名空间表
CREATE TABLE IF NOT EXISTS namespaces (
    name VARCHAR(100) PRIMARY KEY,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'archived')),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 资源配额表
CREATE TABLE IF NOT EXISTS resource_quotas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    namespace VARCHAR(100) NOT NULL REFERENCES namespaces(name) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL,
    limit_value NUMERIC(10, 2) NOT NULL,
    used_value NUMERIC(10, 2) DEFAULT 0,
    unit VARCHAR(20),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(namespace, resource_type)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_system_logs_level ON system_logs(level);
CREATE INDEX IF NOT EXISTS idx_system_logs_timestamp ON system_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_system_logs_source ON system_logs(source);
CREATE INDEX IF NOT EXISTS idx_resource_quotas_namespace ON resource_quotas(namespace);

-- 插入测试数据
INSERT INTO namespaces (name, description, status) VALUES
('default', '默认命名空间', 'active'),
('scheduler', '任务调度器命名空间', 'active'),
('monitor', '监控服务命名空间', 'active')
ON CONFLICT DO NOTHING;

INSERT INTO resource_quotas (namespace, resource_type, limit_value, used_value, unit) VALUES
('default', 'CPU', 8, 4.5, '核'),
('default', 'Memory', 16, 10.2, 'GB'),
('default', 'Disk', 500, 235, 'GB'),
('scheduler', 'Tasks', 100, 27, '个')
ON CONFLICT DO NOTHING;

INSERT INTO system_logs (level, source, message, details, timestamp) VALUES
('info', 'scheduler', '任务调度器启动成功', '{"version": "1.0.0", "port": 8080}'::jsonb, NOW() - INTERVAL '2 hours'),
('warning', 'api', 'API 请求响应时间较慢', '{"endpoint": "/api/v1/tasks", "duration": "3.5s"}'::jsonb, NOW() - INTERVAL '1 hour'),
('error', 'database', '数据库连接池耗尽', '{"pool_size": 10, "active": 10, "waiting": 5}'::jsonb, NOW() - INTERVAL '30 minutes')
ON CONFLICT DO NOTHING;
