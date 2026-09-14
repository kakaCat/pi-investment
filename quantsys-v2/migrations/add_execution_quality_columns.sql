-- quantsys-v2/migrations/add_execution_quality_columns.sql
-- 执行质量闭环（M5，cedfb4ed）的 DDL 补账 + 同类漂移补齐。
-- 创建时间: 2026-09-14（w-2129d492）
--
-- 背景（为什么会有这个文件）：
--   cedfb4ed 给"决策价/成交价/滑点"这 5 列**只**在 quant.simulation_pending_orders 上
--   做了物理变更（当时的 DDL 未入库、无留痕），ORM 与埋点却写歪了：
--     · ORM 把 5 列定义在 SimulationOrder（→ quant.simulation_order）上 → 该表没有这些列，
--       SQLAlchemy flush 会把全列带上 ⇒ 交易时段内任何立即买卖单都在 INSERT 阶段
--       500（实测 2026-09-14 09:45:24-09:45:28，601857，事务已回滚、无脏数据）；
--     · 真正需要这 5 列的 SimulationPendingOrder（→ quant.simulation_pending_orders）
--       反而没定义 ⇒ create_pending_order 构造即 TypeError。
--   本文件做两件事：①把 ORM 侧回归到"埋点所在的那张表"；②把两张表的列口径对齐，
--   使模型与数据库在**两侧都不再漂移**（交付 M5 本意：挂单全生命周期可追溯）。
--
-- 幂等：全部 ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS，可重复执行。
-- 执行：/opt/homebrew/opt/postgresql@14/bin/psql -d quant_investment -f <本文件>

BEGIN;

-- ── 1. 立即单表：补齐 5 列（ORM 已在 SimulationPendingOrder 上定义，本表不定义）──────
-- 说明：本表当前**不**由 ORM 写入这 5 列，此处的目的是让"想要立即单也带执行质量"
-- 时有列可落，且两张订单表口径一致；不改变既有写入路径。
ALTER TABLE quant.simulation_order
    ADD COLUMN IF NOT EXISTS decision_price NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS decision_at    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS price_source   TEXT,
    ADD COLUMN IF NOT EXISTS fill_price     NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS slippage_bps   NUMERIC(10, 2);

COMMENT ON COLUMN quant.simulation_order.decision_price IS '决策时价（滑点基准）';
COMMENT ON COLUMN quant.simulation_order.decision_at    IS '决策时刻';
COMMENT ON COLUMN quant.simulation_order.price_source   IS '决策价来源（R-013 可追溯）';
COMMENT ON COLUMN quant.simulation_order.fill_price     IS '实际成交价';
COMMENT ON COLUMN quant.simulation_order.slippage_bps   IS '滑点基点（正=买贵/卖便宜=成本）';

-- ── 2. 挂单表：确保 5 列在位（cedfb4ed 已物理加过，此处只做幂等兜底）──────────────
ALTER TABLE quant.simulation_pending_orders
    ADD COLUMN IF NOT EXISTS decision_price NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS decision_at    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS price_source   TEXT,
    ADD COLUMN IF NOT EXISTS fill_price     NUMERIC(10, 2),
    ADD COLUMN IF NOT EXISTS slippage_bps   NUMERIC(10, 2);

-- ── 3. 同类漂移：quant.signal_executions（ORM 4 列在模型里、表里没有）─────────────
-- 现状：0 行、无生产写入方（SignalExecutionORMRepository 目前无人调用）→ 未爆但必然踩。
-- 与其删模型列留下"能力被静默移除"，不如把表补齐（表在 ORM 里已有同名模型）。
-- 列类型对齐 ORM 声明：executed_at DateTime / execution_amount Numeric / execution_volume Integer /
-- error_message Text；均无 NOT NULL 约束（模型侧亦然）。
ALTER TABLE quant.signal_executions
    ADD COLUMN IF NOT EXISTS executed_at      TIMESTAMP,
    ADD COLUMN IF NOT EXISTS execution_amount NUMERIC(15, 2),
    ADD COLUMN IF NOT EXISTS execution_volume INTEGER,
    ADD COLUMN IF NOT EXISTS error_message    TEXT;

COMMIT;
