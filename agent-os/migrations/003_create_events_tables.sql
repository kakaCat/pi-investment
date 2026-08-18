-- 事件表
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    agent_id VARCHAR(100),
    data JSONB,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 告警规则表
CREATE TABLE IF NOT EXISTS alert_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    condition TEXT NOT NULL,
    level VARCHAR(20) NOT NULL CHECK (level IN ('info', 'warning', 'error', 'critical')),
    channels TEXT[],
    enabled BOOLEAN DEFAULT true,
    triggered_count INT DEFAULT 0,
    last_triggered_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_agent_id ON events(agent_id);
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_alert_rules_event_type ON alert_rules(event_type);

-- 插入测试数据
INSERT INTO events (type, message, agent_id, data, timestamp) VALUES
('task', '任务 kline_update_daily 执行成功', 'agent-001', '{"task_id": "task-001", "duration": "45.2s", "status": "success"}'::jsonb, NOW() - INTERVAL '1 hour'),
('decision', '生成买入决策：600519 贵州茅台', 'agent-002', '{"action": "buy", "target": "600519", "confidence": 0.85}'::jsonb, NOW() - INTERVAL '30 minutes'),
('system', '系统健康检查通过', NULL, '{"cpu": 45, "memory": 68, "disk": 52}'::jsonb, NOW() - INTERVAL '15 minutes'),
('task', '任务 signal_generate_buy 执行失败', 'agent-001', '{"task_id": "task-002", "error": "database connection timeout"}'::jsonb, NOW() - INTERVAL '10 minutes'),
('decision', '生成卖出决策：000001 平安银行', 'agent-002', '{"action": "sell", "target": "000001", "confidence": 0.72}'::jsonb, NOW() - INTERVAL '5 minutes')
ON CONFLICT DO NOTHING;

INSERT INTO alert_rules (name, event_type, condition, level, channels, enabled, triggered_count, last_triggered_at) VALUES
('任务执行失败告警', 'task', 'status == "failed"', 'error', ARRAY['feishu', 'email'], true, 15, NOW() - INTERVAL '2 hours'),
('系统负载过高告警', 'system', 'cpu > 80 || memory > 90', 'warning', ARRAY['feishu'], true, 8, NOW() - INTERVAL '1 day'),
('决策置信度过低告警', 'decision', 'confidence < 0.6', 'warning', ARRAY['feishu'], false, 0, NULL)
ON CONFLICT DO NOTHING;
