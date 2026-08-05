-- 双侧捕获适应度表（agent 行为进化 Phase 1，2026-08-05）
CREATE TABLE IF NOT EXISTS quant.evolution_fitness (
    id SERIAL PRIMARY KEY,
    account_name VARCHAR(50) NOT NULL,
    window_end DATE NOT NULL,
    window_days INTEGER NOT NULL DEFAULT 20,
    up_capture NUMERIC(10, 4),
    down_capture NUMERIC(10, 4),
    fitness NUMERIC(10, 4),
    up_days INTEGER NOT NULL DEFAULT 0,
    down_days INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'ok',  -- ok / insufficient_sample / no_trades / data_gap
    computed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT evolution_fitness_account_date_key UNIQUE (account_name, window_end, window_days)
);
CREATE INDEX IF NOT EXISTS idx_evolution_fitness_window_end ON quant.evolution_fitness (window_end);
