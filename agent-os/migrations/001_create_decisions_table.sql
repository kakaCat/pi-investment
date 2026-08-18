-- 决策表
CREATE TABLE IF NOT EXISTS decisions (
    id VARCHAR(36) PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    target VARCHAR(200) NOT NULL,
    confidence DECIMAL(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    status VARCHAR(50) NOT NULL CHECK (status IN ('pending', 'executed', 'cancelled', 'failed')),
    reason TEXT,
    pnl DECIMAL(10,2),
    timeline JSONB,
    data JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    executed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_created_at ON decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_action ON decisions(action);

-- 插入测试数据
INSERT INTO decisions (id, action, target, confidence, status, reason, pnl, timeline, created_at, executed_at) VALUES
('dec-001', '买入', '600519 贵州茅台', 0.85, 'executed', '技术面突破关键阻力位，成交量放大，MACD金叉，RSI进入强势区', 12.50, 
 '[{"timestamp":"2024-08-18T09:30:00Z","type":"created","description":"系统生成买入决策"},{"timestamp":"2024-08-18T09:35:00Z","type":"executed","description":"决策已执行，买入成功"}]'::jsonb,
 '2024-08-18 09:30:00', '2024-08-18 09:35:00'),
 
('dec-002', '卖出', '000001 平安银行', 0.72, 'executed', '股价接近前期高点，出现顶背离信号，建议止盈', 8.30,
 '[{"timestamp":"2024-08-17T14:00:00Z","type":"created","description":"系统生成卖出决策"},{"timestamp":"2024-08-17T14:05:00Z","type":"executed","description":"决策已执行，卖出成功"}]'::jsonb,
 '2024-08-17 14:00:00', '2024-08-17 14:05:00'),
 
('dec-003', '持有', '600036 招商银行', 0.68, 'pending', '当前处于震荡区间，等待明确突破信号', NULL,
 '[{"timestamp":"2024-08-18T10:00:00Z","type":"created","description":"系统生成持有决策"}]'::jsonb,
 '2024-08-18 10:00:00', NULL),
 
('dec-004', '买入', '300750 宁德时代', 0.91, 'cancelled', '新能源板块整体走强，龙头股有望突破', NULL,
 '[{"timestamp":"2024-08-16T10:30:00Z","type":"created","description":"系统生成买入决策"},{"timestamp":"2024-08-16T10:35:00Z","type":"cancelled","description":"市场环境变化，决策取消"}]'::jsonb,
 '2024-08-16 10:30:00', NULL),
 
('dec-005', '卖出', '002594 比亚迪', 0.78, 'executed', '短期涨幅过大，技术指标超买，建议获利了结', -3.20,
 '[{"timestamp":"2024-08-15T13:00:00Z","type":"created","description":"系统生成卖出决策"},{"timestamp":"2024-08-15T13:10:00Z","type":"executed","description":"决策已执行，卖出成功"}]'::jsonb,
 '2024-08-15 13:00:00', '2024-08-15 13:10:00');
