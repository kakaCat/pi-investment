-- quantsys-v2/migrations/create_orchestrator_tables.sql
-- DailyOrchestrator 每日投资循环状态机表
-- 创建时间: 2026-07-23
-- 背景: ORM 模型 infrastructure/persistence/orm/models/orchestrator.py 已存在，
--       但迁移一直未写，导致 scheduler_daemon 注册 daily_orchestrator_tick 后
--       每分钟 tick 报 UndefinedTable/PendingRollbackError（2026-07-22 code review 发现）

CREATE TABLE IF NOT EXISTS quant.daily_orchestrator_state (
    id SERIAL PRIMARY KEY,
    orchestrator_name VARCHAR(50) NOT NULL DEFAULT 'main',
    trade_date DATE NOT NULL,
    current_phase VARCHAR(30) NOT NULL DEFAULT 'IDLE',
    phases_completed JSONB NOT NULL DEFAULT '{}'::jsonb,
    context JSONB,
    last_error VARCHAR(500),
    error_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 唯一约束：(orchestrator_name, trade_date)，与 ORM 模型的 Index(unique=True) 对应
CREATE UNIQUE INDEX IF NOT EXISTS orchestrator_state_name_date_key
    ON quant.daily_orchestrator_state (orchestrator_name, trade_date);

COMMENT ON TABLE quant.daily_orchestrator_state IS '日常编排器状态机：每交易日一行，追踪各阶段完成情况，支持断点续跑';
COMMENT ON COLUMN quant.daily_orchestrator_state.current_phase IS 'IDLE/PRE_MARKET/MARKET_OPEN/INTRADAY/MARKET_CLOSE/POST_MARKET/REVIEW';
COMMENT ON COLUMN quant.daily_orchestrator_state.phases_completed IS '{phase: {status, started_at, finished_at, result}}';
