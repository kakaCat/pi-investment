-- 2026-09-04 盯盘规则归属账户（看板按账户分组展示）
-- 历史规则由回填脚本（context/持仓启发式）赋 account；无法归属者保持 NULL=通用观察。
ALTER TABLE quant.watch_rules
    ADD COLUMN IF NOT EXISTS account VARCHAR(50);
COMMENT ON COLUMN quant.watch_rules.account IS
    '规则归属账户（account_name 全名）；NULL=通用观察（无主/跨账户候选，各账户看板均展示）';
CREATE INDEX IF NOT EXISTS idx_watch_rules_account ON quant.watch_rules(account) WHERE account IS NOT NULL;
