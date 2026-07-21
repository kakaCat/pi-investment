-- 为 stock_pools 表添加 members 字段
-- 将现有的 symbols 数组迁移到 members jsonb

-- 1. 添加 members 字段
ALTER TABLE quant.stock_pools
ADD COLUMN IF NOT EXISTS members jsonb DEFAULT '[]'::jsonb;

-- 2. 将现有 symbols 迁移到 members（保留 symbols 字段用于向后兼容）
UPDATE quant.stock_pools
SET members = (
    SELECT jsonb_agg(
        jsonb_build_object(
            'symbol', unnest,
            'name', NULL,
            'description', NULL,
            'buy_point', NULL,
            'sell_point', NULL,
            'tags', '[]'::jsonb
        )
    )
    FROM unnest(symbols)
)
WHERE members = '[]'::jsonb AND array_length(symbols, 1) > 0;

-- 3. 创建索引加速查询
CREATE INDEX IF NOT EXISTS idx_stock_pools_members_gin ON quant.stock_pools USING gin(members);

-- 4. 添加注释
COMMENT ON COLUMN quant.stock_pools.members IS '池子成员详细信息，包含 symbol, name, description, buy_point, sell_point, tags';
