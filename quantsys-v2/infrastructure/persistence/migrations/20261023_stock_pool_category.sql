-- 2026-10-23（w-575d7ed5）：股票池新增「业务分类」字段 category
--
-- 背景：quant.stock_pools 原有 pool_type（static/dynamic）表示**存储/刷新形态**，
-- 且有 CHECK 约束并被动态池刷新/调度逻辑依赖，无法表达「板块共振 / 主题 / 策略 / 观察」
-- 这类业务分类。故新增独立字段，与 pool_type 正交（互不覆盖）。
--
-- 口径：自由文本（建议值：板块共振 / 主题 / 策略 / 观察 / 高股息 / 因子），可空；
-- 不加 CHECK 约束，便于后续扩展分类而无需迁移。

ALTER TABLE quant.stock_pools
    ADD COLUMN IF NOT EXISTS category VARCHAR(50);

COMMENT ON COLUMN quant.stock_pools.category IS
    '股票池业务分类（如：板块共振/主题/策略/观察），与 pool_type(static/dynamic 存储形态) 正交';

CREATE INDEX IF NOT EXISTS idx_stock_pools_category
    ON quant.stock_pools (category);
