-- quantsys-v2/migrations/create_watch_tables.sql
-- WatchEngine 实时盯盘表
-- 创建时间: 2026-07-21

CREATE TABLE IF NOT EXISTS quant.watch_rules (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    conditions JSONB NOT NULL,          -- [{"type": "...", "params": {...}, "cooldown_sec": 300}]
    context TEXT,                        -- Agent 创建时填的监视理由，触发时回传
    cost_price NUMERIC(12,4),            -- pnl_pct 条件的成本基准
    active_window JSONB,                 -- ["09:30-10:30","14:30-15:00"]，NULL = 全交易时段
    expires_at TIMESTAMP,                -- 过期自动停用，NULL = 永不过期
    created_by VARCHAR(50) DEFAULT 'agent',
    account VARCHAR(50),               -- 归属账户（account_name 全名）；NULL=通用观察
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watch_rules_enabled ON quant.watch_rules(enabled) WHERE enabled = true;
CREATE INDEX IF NOT EXISTS idx_watch_rules_symbol ON quant.watch_rules(symbol);

COMMENT ON TABLE quant.watch_rules IS 'WatchEngine 盯盘监视规则（Agent 动态注册）';
COMMENT ON COLUMN quant.watch_rules.conditions IS '条件数组，type: price_break/pct_change/pnl_pct/velocity/volume_surge';

CREATE TABLE IF NOT EXISTS quant.watch_triggers (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES quant.watch_rules(id) ON DELETE SET NULL,
    symbol VARCHAR(20) NOT NULL,
    condition JSONB NOT NULL,            -- 触发时命中的条件快照
    trigger_price NUMERIC(12,4),
    detail JSONB,                        -- 评估详情（value、message、涨跌幅等）
    agent_response JSONB,                -- Agent 决策回填（后续）
    notified BOOLEAN DEFAULT false,      -- 是否成功唤醒 Agent
    triggered_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watch_triggers_symbol_time ON quant.watch_triggers(symbol, triggered_at DESC);

COMMENT ON TABLE quant.watch_triggers IS 'WatchEngine 触发审计记录（供 Agent 学习）';
