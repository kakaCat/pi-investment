-- 修改 decisions 表以支持 Web 前端需求

-- 添加缺失的列
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS target VARCHAR(200);
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS status VARCHAR(50);
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS pnl DECIMAL(10,2);
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS timeline JSONB;
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS data JSONB;
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

-- 更新现有数据
UPDATE decisions SET target = targets[1] WHERE target IS NULL AND array_length(targets, 1) > 0;
UPDATE decisions SET status = 'executed' WHERE status IS NULL AND executed_at IS NOT NULL;
UPDATE decisions SET status = 'pending' WHERE status IS NULL AND executed_at IS NULL;
UPDATE decisions SET updated_at = created_at WHERE updated_at IS NULL;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_target ON decisions(target);

-- 插入测试数据（如果不存在）
INSERT INTO decisions (id, agent_id, action, targets, target, confidence, status, reason, pnl, timeline, created_at, executed_at)
SELECT 'dec-001', 'web-test', 'buy', ARRAY['600519'], '600519 贵州茅台', 0.85, 'executed', 
       '技术面突破关键阻力位，成交量放大，MACD金叉，RSI进入强势区', 12.50,
       '[{"timestamp":"2024-08-18T09:30:00Z","type":"created","description":"系统生成买入决策"},{"timestamp":"2024-08-18T09:35:00Z","type":"executed","description":"决策已执行，买入成功"}]'::jsonb,
       '2024-08-18 09:30:00', '2024-08-18 09:35:00'
WHERE NOT EXISTS (SELECT 1 FROM decisions WHERE id = 'dec-001');

INSERT INTO decisions (id, agent_id, action, targets, target, confidence, status, reason, pnl, timeline, created_at, executed_at)
SELECT 'dec-002', 'web-test', 'sell', ARRAY['000001'], '000001 平安银行', 0.72, 'executed',
       '股价接近前期高点，出现顶背离信号，建议止盈', 8.30,
       '[{"timestamp":"2024-08-17T14:00:00Z","type":"created","description":"系统生成卖出决策"},{"timestamp":"2024-08-17T14:05:00Z","type":"executed","description":"决策已执行，卖出成功"}]'::jsonb,
       '2024-08-17 14:00:00', '2024-08-17 14:05:00'
WHERE NOT EXISTS (SELECT 1 FROM decisions WHERE id = 'dec-002');

INSERT INTO decisions (id, agent_id, action, targets, target, confidence, status, reason, timeline, created_at, executed_at)
SELECT 'dec-003', 'web-test', 'hold', ARRAY['600036'], '600036 招商银行', 0.68, 'pending',
       '当前处于震荡区间，等待明确突破信号',
       '[{"timestamp":"2024-08-18T10:00:00Z","type":"created","description":"系统生成持有决策"}]'::jsonb,
       '2024-08-18 10:00:00', NULL
WHERE NOT EXISTS (SELECT 1 FROM decisions WHERE id = 'dec-003');

INSERT INTO decisions (id, agent_id, action, targets, target, confidence, status, reason, timeline, created_at, executed_at)
SELECT 'dec-004', 'web-test', 'buy', ARRAY['300750'], '300750 宁德时代', 0.91, 'cancelled',
       '新能源板块整体走强，龙头股有望突破',
       '[{"timestamp":"2024-08-16T10:30:00Z","type":"created","description":"系统生成买入决策"},{"timestamp":"2024-08-16T10:35:00Z","type":"cancelled","description":"市场环境变化，决策取消"}]'::jsonb,
       '2024-08-16 10:30:00', NULL
WHERE NOT EXISTS (SELECT 1 FROM decisions WHERE id = 'dec-004');

INSERT INTO decisions (id, agent_id, action, targets, target, confidence, status, reason, pnl, timeline, created_at, executed_at)
SELECT 'dec-005', 'web-test', 'sell', ARRAY['002594'], '002594 比亚迪', 0.78, 'executed',
       '短期涨幅过大，技术指标超买，建议获利了结', -3.20,
       '[{"timestamp":"2024-08-15T13:00:00Z","type":"created","description":"系统生成卖出决策"},{"timestamp":"2024-08-15T13:10:00Z","type":"executed","description":"决策已执行，卖出成功"}]'::jsonb,
       '2024-08-15 13:00:00', '2024-08-15 13:10:00'
WHERE NOT EXISTS (SELECT 1 FROM decisions WHERE id = 'dec-005');
