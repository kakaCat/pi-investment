-- 策略进化引擎结果表（RFC 012 P1，2026-09-03 w-8366e526）
-- 每次 evolution run 的每个变体一行（含 base 对照组 variant=0），
-- fitness 为同批窗口内相对百分位合成（0.5·收益 + 0.3·夏普 + 0.2·胜率，RFC 012 §4），
-- metrics 保留原始标量指标供审计；大数组（equity_curve/trades）不入库。
CREATE TABLE IF NOT EXISTS quant.evolution_strategy_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,               -- 一次 run 的批次 ID（uuid hex 前 12）
    strategy_id INTEGER NOT NULL,              -- strategies 表主键
    symbol VARCHAR(20),                        -- 回测标的（6 位代码）
    variant INTEGER NOT NULL DEFAULT 0,        -- 变体序号（0 = base 对照组）
    variant_key TEXT NOT NULL,                 -- params 稳定指纹（去重/归一键）
    params JSONB NOT NULL DEFAULT '{}',        -- 该变体完整参数
    genome_run_id TEXT,                        -- 可选：与 L4-B genome 变异关联（本版留空）
    code_diff TEXT,                            -- 代码文本变异 diff（RFC 012 P1 不做代码变异，留空）
    fitness DOUBLE PRECISION,                  -- 真实回测同批归一适应度（NULL=degraded）
    metrics JSONB,                             -- 裁剪后的标量回测指标（total_return/sharpe 等）
    kline_window VARCHAR(40),                  -- 回测窗口 'YYYY-MM-DD~YYYY-MM-DD'
    mode VARCHAR(20) NOT NULL DEFAULT 'full',  -- full / propose
    initial_cash DOUBLE PRECISION,
    status VARCHAR(20) NOT NULL DEFAULT 'ok',  -- ok / degraded
    degraded_reason TEXT,                      -- degraded 原因（零交易/回测异常/参数面缺失等）
    computed_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evorun_strategy_run ON quant.evolution_strategy_runs (strategy_id, run_id);
CREATE INDEX IF NOT EXISTS idx_evorun_run ON quant.evolution_strategy_runs (run_id);
CREATE INDEX IF NOT EXISTS idx_evorun_strategy_status ON quant.evolution_strategy_runs (strategy_id, status, computed_at);
