-- 用户配置表
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255),
    avatar_url TEXT,
    display_name VARCHAR(200),
    bio TEXT,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- API 密钥表
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    permissions TEXT[],
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 操作日志表
CREATE TABLE IF NOT EXISTS user_activity_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(200),
    details JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON api_keys(expires_at);
CREATE INDEX IF NOT EXISTS idx_activity_logs_user_id ON user_activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_timestamp ON user_activity_logs(timestamp DESC);

-- 插入测试数据
INSERT INTO user_profiles (username, email, display_name, bio, preferences) VALUES
('admin', 'admin@agent-os.local', 'Administrator', 'System administrator', '{"theme": "dark", "language": "zh-CN", "notifications": true}'::jsonb)
ON CONFLICT DO NOTHING;

-- 获取用户 ID 并插入 API 密钥
DO $$
DECLARE
    user_uuid UUID;
BEGIN
    SELECT id INTO user_uuid FROM user_profiles WHERE username = 'admin';
    
    INSERT INTO api_keys (name, key_hash, key_prefix, user_id, permissions, expires_at) VALUES
    ('开发环境密钥', 'dev_key_hash_12345678', 'dev_', user_uuid, ARRAY['read', 'write'], NOW() + INTERVAL '1 year'),
    ('生产环境密钥', 'prod_key_hash_87654321', 'prod_', user_uuid, ARRAY['read'], NOW() + INTERVAL '6 months')
    ON CONFLICT DO NOTHING;
    
    INSERT INTO user_activity_logs (user_id, action, resource, details) VALUES
    (user_uuid, 'login', 'web', '{"ip": "127.0.0.1", "browser": "Chrome"}'::jsonb),
    (user_uuid, 'create_decision', 'decisions/123', '{"action": "buy", "target": "600519"}'::jsonb),
    (user_uuid, 'view_memory', 'memory/list', '{"category": "knowledge"}'::jsonb)
    ON CONFLICT DO NOTHING;
END $$;
