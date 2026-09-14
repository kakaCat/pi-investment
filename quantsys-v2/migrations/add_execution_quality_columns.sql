-- quantsys-v2/migrations/add_execution_quality_columns.sql
-- 执行质量闭环（M5，cedfb4ed）的 DDL 补账 + 同类漂移补齐。
-- 创建时间: 2026-09-14（w-2129d492）；同日按独立审查 w-0f022172 的建议重构（见"执行约束"）。
--
-- 背景（为什么会有这个文件）：
--   cedfb4ed 给"决策价/成交价/滑点"这 5 列**只**在 quant.simulation_pending_orders 上
--   做了物理变更（当时的 DDL 未入库、无留痕），ORM 与埋点却写歪了：
--     · ORM 把 5 列定义在 SimulationOrder（→ quant.simulation_order）上 → 该表没有这些列，
--       SQLAlchemy flush 会把全列带上 ⇒ 交易时段内任何立即买卖单都在 INSERT 阶段 500
--       （实测 2026-09-14 09:45:24-09:45:28，601857，事务已回滚、无脏数据）；
--     · 真正需要这 5 列的 SimulationPendingOrder（→ quant.simulation_pending_orders）
--       反而没定义 ⇒ create_pending_order 构造即 TypeError。
--   本文件把两张表的列口径对齐，使模型与数据库在**两侧都不再漂移**。
--
-- 执行约束（独立审查 B1 的修正，必须保留）：
--   1) **全文件不得用 BEGIN…COMMIT 包住多段**。原版把 3 段塞进一个事务，而
--      quant.simulation_order 在本仓**没有任何 CREATE TABLE 迁移**（新库/重建库没有这张表），
--      第一段必然 42P01 → 整文件回滚 → 连带丢掉真正必需的挂单 5 列，
--      使新环境"挂单模型要列、库没有"，比修复前更糟。
--      现在：每段独立事务（psql/psycopg2 逐语句自动提交；失败只影响该段）。
--   2) 段的执行顺序不得依赖其它迁移文件，且**必须幂等**（ADD COLUMN IF NOT EXISTS）。
--   3) 表可能不存在的段用 DO 块吃掉缺表情形并打印 NOTICE —— 缺表时该段无意义，
--      但绝不能拖垮其它段。
--   执行：/opt/homebrew/opt/postgresql@14/bin/psql -d <db> -f <本文件>（可重复执行）

-- ── 段 1/3：立即单表 quant.simulation_order 补齐 5 列 ────────────────────────────
-- 注意：本表**没有**对应的 CREATE TABLE 迁移（历史遗留，见上"执行约束"）；新库若缺此表，
-- 本段跳过（NOTICE），不影响其它段。ORM 侧**不声明**这 5 列（声明就会让立即单 INSERT
-- 带上它们 → 09-14 的 500 复现）；此处的目的是让两张订单表口径一致，供后续
-- "立即单执行质量"设计使用。
DO $$
BEGIN
    IF to_regclass('quant.simulation_order') IS NULL THEN
        RAISE NOTICE 'quant.simulation_order 不存在（本仓无其建表迁移）→ 跳过段 1';
    ELSE
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
    END IF;
END $$;

-- ── 段 2/3：挂单表 quant.simulation_pending_orders 5 列（本文件存在的**主因**）─────
-- 这段才是必须成功的：SimulationPendingOrder 已映射这 5 列，任何缺列环境 SELECT 挂单
-- 即 UndefinedColumn。cedfb4ed 已物理加过，此处为幂等兜底 + 新库自愈。
DO $$
BEGIN
    IF to_regclass('quant.simulation_pending_orders') IS NULL THEN
        RAISE NOTICE 'quant.simulation_pending_orders 不存在（应由 create_pending_orders.sql 建）→ 跳过段 2';
    ELSE
        ALTER TABLE quant.simulation_pending_orders
            ADD COLUMN IF NOT EXISTS decision_price NUMERIC(10, 2),
            ADD COLUMN IF NOT EXISTS decision_at    TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS price_source   TEXT,
            ADD COLUMN IF NOT EXISTS fill_price     NUMERIC(10, 2),
            ADD COLUMN IF NOT EXISTS slippage_bps   NUMERIC(10, 2);
    END IF;
END $$;

-- ── 段 3/3：同类漂移 quant.signal_executions（ORM 4 列在模型里、表里没有）────────
-- 现状：0 行、无生产写入方（SignalExecutionORMRepository 目前无人调用）→ 未爆但必然踩。
-- 列类型对齐 ORM 声明（signal.py）：executed_at DateTime / execution_amount Numeric(15,2) /
-- execution_volume Integer / error_message Text；均无 NOT NULL（模型侧亦然）。
DO $$
BEGIN
    IF to_regclass('quant.signal_executions') IS NULL THEN
        RAISE NOTICE 'quant.signal_executions 不存在 → 跳过段 3';
    ELSE
        ALTER TABLE quant.signal_executions
            ADD COLUMN IF NOT EXISTS executed_at      TIMESTAMP,
            ADD COLUMN IF NOT EXISTS execution_amount NUMERIC(15, 2),
            ADD COLUMN IF NOT EXISTS execution_volume INTEGER,
            ADD COLUMN IF NOT EXISTS error_message    TEXT;
    END IF;
END $$;
