-- ============================================================================
-- 策略追溯体系 - 8张表
-- 设计日期: 2026-05-21
-- ============================================================================

-- ============================================================================
-- 1. strategy_metadata - 策略元数据注册表
-- ============================================================================
CREATE TABLE IF NOT EXISTS quant.strategy_metadata (
    id              BIGSERIAL PRIMARY KEY,
    strategy_type   TEXT NOT NULL UNIQUE,
    class_name      TEXT NOT NULL,
    category        TEXT NOT NULL,
    description     TEXT,
    default_params  JSONB NOT NULL DEFAULT '{}',
    param_schema    JSONB NOT NULL DEFAULT '{}',
    required_libs   JSONB DEFAULT '[]',
    is_available    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE  quant.strategy_metadata IS '策略元数据注册表 - 从代码自动发现并同步';
COMMENT ON COLUMN quant.strategy_metadata.strategy_type  IS '策略类型标识（snake_case）';
COMMENT ON COLUMN quant.strategy_metadata.class_name     IS '策略类名';
COMMENT ON COLUMN quant.strategy_metadata.category       IS 'trend_following|mean_reversion|arbitrage|machine_learning|multi_factor|volatility';
COMMENT ON COLUMN quant.strategy_metadata.default_params IS '默认参数({key:value})';
COMMENT ON COLUMN quant.strategy_metadata.param_schema   IS '参数schema({key:{type,min,max,description}})';
COMMENT ON COLUMN quant.strategy_metadata.required_libs  IS '依赖库列表';
COMMENT ON COLUMN quant.strategy_metadata.is_available   IS '依赖库是否满足';

CREATE INDEX IF NOT EXISTS idx_strategy_metadata_category   ON quant.strategy_metadata(category);
CREATE INDEX IF NOT EXISTS idx_strategy_metadata_available  ON quant.strategy_metadata(is_available);


-- ============================================================================
-- 2. strategy_executions - 策略执行追溯表
-- ============================================================================
CREATE TABLE IF NOT EXISTS quant.strategy_executions (
    id                  BIGSERIAL PRIMARY KEY,
    execution_id        UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    strategy_config_id  INTEGER,
    strategy_type       TEXT NOT NULL,
    strategy_name       TEXT NOT NULL,

    symbol              TEXT NOT NULL,
    market              TEXT,
    execution_time      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- 输入快照
    klines_count        INTEGER,
    klines_date_range   JSONB,
    params_snapshot     JSONB NOT NULL DEFAULT '{}',

    -- 输出信号
    signal_action       TEXT,
    signal_confidence   DOUBLE PRECISION,
    signal_reason       TEXT,

    -- 多策略投票（组合器场景）
    strategy_votes      JSONB DEFAULT '[]',

    -- 性能指标
    execution_duration_ms INTEGER,

    created_at          TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE  quant.strategy_executions IS '策略执行追溯表 - 每次调用的完整记录';
COMMENT ON COLUMN quant.strategy_executions.execution_id       IS '全局唯一执行ID UUID';
COMMENT ON COLUMN quant.strategy_executions.strategy_config_id IS '引用的策略配置ID';
COMMENT ON COLUMN quant.strategy_executions.params_snapshot    IS '本次执行的参数快照(JSON)';
COMMENT ON COLUMN quant.strategy_executions.signal_action      IS '买卖持有信号';
COMMENT ON COLUMN quant.strategy_executions.strategy_votes     IS '多策略投票明细';

CREATE INDEX IF NOT EXISTS idx_strategy_executions_exec_id   ON quant.strategy_executions(execution_id);
CREATE INDEX IF NOT EXISTS idx_strategy_executions_symbol    ON quant.strategy_executions(symbol);
CREATE INDEX IF NOT EXISTS idx_strategy_executions_time      ON quant.strategy_executions(execution_time DESC);
CREATE INDEX IF NOT EXISTS idx_strategy_executions_strategy  ON quant.strategy_executions(strategy_type);
CREATE INDEX IF NOT EXISTS idx_strategy_executions_signal    ON quant.strategy_executions(signal_action);
CREATE INDEX IF NOT EXISTS idx_strategy_executions_config    ON quant.strategy_executions(strategy_config_id);


-- ============================================================================
-- 3. factor_calculations - 因子计算追溯表
-- ============================================================================
CREATE TABLE IF NOT EXISTS quant.factor_calculations (
    id              BIGSERIAL PRIMARY KEY,
    execution_id    UUID NOT NULL,
    symbol          TEXT NOT NULL,
    calculation_time TIMESTAMPTZ NOT NULL DEFAULT now(),

    factor_name     TEXT NOT NULL,
    factor_category TEXT NOT NULL,
    factor_value    DOUBLE PRECISION,
    factor_rank     DOUBLE PRECISION,

    klines_count    INTEGER,
    calculation_duration_ms INTEGER,

    created_at      TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE  quant.factor_calculations IS '因子计算追溯表 - 每次因子计算的记录';
COMMENT ON COLUMN quant.factor_calculations.execution_id  IS '关联的策略执行ID';
COMMENT ON COLUMN quant.factor_calculations.factor_name   IS '因子名称';
COMMENT ON COLUMN quant.factor_calculations.factor_value  IS '因子计算值';
COMMENT ON COLUMN quant.factor_calculations.factor_rank   IS '因子标准化排名(0~1)';

CREATE INDEX IF NOT EXISTS idx_factor_calculations_execution ON quant.factor_calculations(execution_id);
CREATE INDEX IF NOT EXISTS idx_factor_calculations_factor    ON quant.factor_calculations(factor_name);
CREATE INDEX IF NOT EXISTS idx_factor_calculations_symbol    ON quant.factor_calculations(symbol);
CREATE INDEX IF NOT EXISTS idx_factor_calculations_time      ON quant.factor_calculations(calculation_time DESC);


-- ============================================================================
-- 4. signal_generations - 信号生成追溯表
-- ============================================================================
CREATE TABLE IF NOT EXISTS quant.signal_generations (
    id              BIGSERIAL PRIMARY KEY,
    signal_id       UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    execution_id    UUID,

    symbol          TEXT NOT NULL,
    signal_time     TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- 信号内容
    action          TEXT NOT NULL CHECK (action IN ('buy', 'sell', 'hold')),
    confidence      DOUBLE PRECISION NOT NULL,
    reason          TEXT,

    -- 价格快照
    price_at_signal DOUBLE PRECISION,

    -- 多策略投票明细
    strategy_votes  JSONB DEFAULT '[]',

    -- 状态追踪
    is_executed     BOOLEAN DEFAULT FALSE,
    execution_price DOUBLE PRECISION,
    execution_time  TIMESTAMPTZ,
    order_id        BIGINT,

    -- 生命周期
    expires_at      TIMESTAMPTZ,
    cancelled_at    TIMESTAMPTZ,
    cancel_reason   TEXT,

    created_at      TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE  quant.signal_generations IS '信号生成追溯表 - 每个交易信号的完整生命周期';
COMMENT ON COLUMN quant.signal_generations.signal_id       IS '全局唯一信号ID UUID';
COMMENT ON COLUMN quant.signal_generations.execution_id    IS '关联的策略执行ID';
COMMENT ON COLUMN quant.signal_generations.strategy_votes  IS '多策略投票明细';
COMMENT ON COLUMN quant.signal_generations.is_executed     IS '是否已转化为实际交易';
COMMENT ON COLUMN quant.signal_generations.order_id        IS '关联的订单ID';

CREATE INDEX IF NOT EXISTS idx_signal_gen_signal_id    ON quant.signal_generations(signal_id);
CREATE INDEX IF NOT EXISTS idx_signal_gen_execution    ON quant.signal_generations(execution_id);
CREATE INDEX IF NOT EXISTS idx_signal_gen_symbol       ON quant.signal_generations(symbol);
CREATE INDEX IF NOT EXISTS idx_signal_gen_time         ON quant.signal_generations(signal_time DESC);
CREATE INDEX IF NOT EXISTS idx_signal_gen_action       ON quant.signal_generations(action);
CREATE INDEX IF NOT EXISTS idx_signal_gen_executed     ON quant.signal_generations(is_executed);
CREATE INDEX IF NOT EXISTS idx_signal_gen_order        ON quant.signal_generations(order_id);


-- ============================================================================
-- 5. ml_predictions - ML预测追溯表
-- ============================================================================
CREATE TABLE IF NOT EXISTS quant.ml_predictions (
    id              BIGSERIAL PRIMARY KEY,
    execution_id    UUID,

    symbol          TEXT NOT NULL,
    prediction_time TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- 模型信息
    model_type      TEXT NOT NULL,
    model_version   TEXT NOT NULL,

    -- 特征
    feature_names   JSONB NOT NULL DEFAULT '[]',
    feature_values  JSONB NOT NULL DEFAULT '{}',
    feature_count   INTEGER,

    -- 预测结果
    prediction      INTEGER NOT NULL,
    confidence      DOUBLE PRECISION,
    prob_down       DOUBLE PRECISION,
    prob_up         DOUBLE PRECISION,

    -- 性能
    prediction_duration_ms INTEGER,

    created_at      TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE  quant.ml_predictions IS 'ML预测追溯表 - 每次模型预测的完整记录';
COMMENT ON COLUMN quant.ml_predictions.execution_id   IS '关联的策略执行ID';
COMMENT ON COLUMN quant.ml_predictions.model_type     IS '模型类型 xgboost/lightgbm';
COMMENT ON COLUMN quant.ml_predictions.feature_names  IS '使用的特征名称列表';
COMMENT ON COLUMN quant.ml_predictions.feature_values IS '特征值快照';
COMMENT ON COLUMN quant.ml_predictions.prediction     IS '0=HOLD 1=BUY';
COMMENT ON COLUMN quant.ml_predictions.prob_down      IS '预测下跌的概率';
COMMENT ON COLUMN quant.ml_predictions.prob_up        IS '预测上涨的概率';

CREATE INDEX IF NOT EXISTS idx_ml_predictions_execution ON quant.ml_predictions(execution_id);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_symbol    ON quant.ml_predictions(symbol);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_time      ON quant.ml_predictions(prediction_time DESC);
CREATE INDEX IF NOT EXISTS idx_ml_predictions_model     ON quant.ml_predictions(model_type, model_version);


-- ============================================================================
-- 6. backtest_executions - 回测执行追溯表
-- ============================================================================
CREATE TABLE IF NOT EXISTS quant.backtest_executions (
    id                  BIGSERIAL PRIMARY KEY,
    backtest_id         UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    backtest_name       TEXT NOT NULL,

    -- 对象
    symbol              TEXT,
    symbols             JSONB DEFAULT '[]',

    -- 参数
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    initial_capital     DOUBLE PRECISION NOT NULL,
    commission_rate     DOUBLE PRECISION DEFAULT 0.0003,
    slippage            DOUBLE PRECISION DEFAULT 0.001,
    benchmark           TEXT DEFAULT '000300.SH',

    -- 使用的策略
    strategy_config_ids JSONB DEFAULT '[]',
    strategy_types      JSONB DEFAULT '[]',

    -- 结果汇总
    final_capital       DOUBLE PRECISION,
    total_return        DOUBLE PRECISION,
    annual_return       DOUBLE PRECISION,
    sharpe_ratio        DOUBLE PRECISION,
    max_drawdown        DOUBLE PRECISION,
    calmar_ratio        DOUBLE PRECISION,

    -- 交易统计
    total_trades        INTEGER DEFAULT 0,
    winning_trades      INTEGER DEFAULT 0,
    losing_trades       INTEGER DEFAULT 0,
    win_rate            DOUBLE PRECISION,
    avg_win             DOUBLE PRECISION,
    avg_loss            DOUBLE PRECISION,
    profit_factor       DOUBLE PRECISION,
    max_consecutive_losses INTEGER,

    -- 执行信息
    total_duration_ms   INTEGER,
    status              TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    error_message       TEXT,

    created_at          TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE quant.backtest_executions IS '回测执行追溯表 - 每次回测的完整记录';
COMMENT ON COLUMN quant.backtest_executions.symbols            IS '组合回测的股票列表';
COMMENT ON COLUMN quant.backtest_executions.strategy_config_ids IS '使用的策略配置ID列表';
COMMENT ON COLUMN quant.backtest_executions.calmar_ratio       IS '卡玛比率(年化收益/最大回撤)';

CREATE INDEX IF NOT EXISTS idx_backtest_exec_backtest_id ON quant.backtest_executions(backtest_id);
CREATE INDEX IF NOT EXISTS idx_backtest_exec_symbol      ON quant.backtest_executions(symbol);
CREATE INDEX IF NOT EXISTS idx_backtest_exec_time        ON quant.backtest_executions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backtest_exec_status      ON quant.backtest_executions(status);


-- ============================================================================
-- 7. backtest_trades - 回测逐笔交易追溯表
-- ============================================================================
CREATE TABLE IF NOT EXISTS quant.backtest_trades (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     UUID NOT NULL,
    trade_no        INTEGER NOT NULL,

    symbol          TEXT NOT NULL,
    action          TEXT NOT NULL CHECK (action IN ('buy', 'sell')),

    -- 价格与数量
    price           DOUBLE PRECISION NOT NULL,
    quantity        INTEGER NOT NULL,
    amount          DOUBLE PRECISION NOT NULL,
    fee             DOUBLE PRECISION DEFAULT 0,
    slippage_cost   DOUBLE PRECISION DEFAULT 0,

    -- 时间
    entry_date      DATE,
    exit_date       DATE,
    holding_days    INTEGER,

    -- 盈亏
    pnl             DOUBLE PRECISION,
    pnl_pct         DOUBLE PRECISION,
    cumulative_pnl  DOUBLE PRECISION,

    -- 追溯
    signal_id       UUID,
    strategy_type   TEXT,
    exit_reason     TEXT CHECK (exit_reason IN ('stop_loss', 'target', 'signal', 'end_of_period', 'manual')),

    -- 持仓状态快照
    capital_before  DOUBLE PRECISION,
    capital_after   DOUBLE PRECISION,
    position_ratio  DOUBLE PRECISION,

    created_at      TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE quant.backtest_trades IS '回测逐笔交易追溯表';
COMMENT ON COLUMN quant.backtest_trades.trade_no       IS '交易序号';
COMMENT ON COLUMN quant.backtest_trades.holding_days   IS '持仓天数';
COMMENT ON COLUMN quant.backtest_trades.signal_id      IS '触发信号ID（可追溯到信号生成）';
COMMENT ON COLUMN quant.backtest_trades.exit_reason    IS '离场原因';
COMMENT ON COLUMN quant.backtest_trades.position_ratio IS '仓位占比';

CREATE INDEX IF NOT EXISTS idx_backtest_trades_backtest ON quant.backtest_trades(backtest_id);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_symbol   ON quant.backtest_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_strategy ON quant.backtest_trades(strategy_type);
CREATE INDEX IF NOT EXISTS idx_backtest_trades_signal   ON quant.backtest_trades(signal_id);


-- ============================================================================
-- 8. backtest_daily_snapshots - 回测每日快照表
-- ============================================================================
CREATE TABLE IF NOT EXISTS quant.backtest_daily_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    backtest_id     UUID NOT NULL,
    snapshot_date   DATE NOT NULL,

    -- 资金
    cash            DOUBLE PRECISION,
    market_value    DOUBLE PRECISION,
    total_assets    DOUBLE PRECISION,

    -- 收益
    daily_pnl       DOUBLE PRECISION,
    daily_return    DOUBLE PRECISION,
    cumulative_return DOUBLE PRECISION,

    -- 持仓
    positions       JSONB DEFAULT '[]',
    position_count  INTEGER DEFAULT 0,

    -- 回撤
    drawdown        DOUBLE PRECISION,
    drawdown_pct    DOUBLE PRECISION,

    -- 基准对比
    benchmark_value  DOUBLE PRECISION,
    benchmark_return DOUBLE PRECISION,

    created_at      TIMESTAMPTZ DEFAULT now(),

    UNIQUE(backtest_id, snapshot_date)
);

COMMENT ON TABLE quant.backtest_daily_snapshots IS '回测每日快照表 - 绘制净值曲线';
COMMENT ON COLUMN quant.backtest_daily_snapshots.positions       IS '当日持仓明细';
COMMENT ON COLUMN quant.backtest_daily_snapshots.drawdown        IS '当日回撤金额';
COMMENT ON COLUMN quant.backtest_daily_snapshots.drawdown_pct    IS '当日回撤百分比';
COMMENT ON COLUMN quant.backtest_daily_snapshots.benchmark_value IS '基准指数净值';

CREATE INDEX IF NOT EXISTS idx_backtest_daily_snaps_backtest ON quant.backtest_daily_snapshots(backtest_id);
CREATE INDEX IF NOT EXISTS idx_backtest_daily_snaps_date     ON quant.backtest_daily_snapshots(snapshot_date);


-- ============================================================================
-- 完成
-- ============================================================================
SELECT 'Strategy traceability system: 8 tables created successfully!' as status;
