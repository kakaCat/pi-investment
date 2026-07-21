-- 策略风控管理系统 - 数据库迁移
-- 添加风控字段到 orders 表

-- 1. 添加新字段
ALTER TABLE quant.orders ADD COLUMN IF NOT EXISTS stop_loss_price DECIMAL(10, 2);
ALTER TABLE quant.orders ADD COLUMN IF NOT EXISTS take_profit_price DECIMAL(10, 2);
ALTER TABLE quant.orders ADD COLUMN IF NOT EXISTS parent_order_id BIGINT;
ALTER TABLE quant.orders ADD COLUMN IF NOT EXISTS order_group VARCHAR(50);
ALTER TABLE quant.orders ADD COLUMN IF NOT EXISTS risk_params JSONB;

-- 2. 添加索引
CREATE INDEX IF NOT EXISTS idx_orders_parent_order_id ON quant.orders(parent_order_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_group ON quant.orders(order_group);

-- 3. 添加外键约束
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_parent_order'
    ) THEN
        ALTER TABLE quant.orders
        ADD CONSTRAINT fk_parent_order
        FOREIGN KEY (parent_order_id)
        REFERENCES quant.orders(id)
        ON DELETE SET NULL;
    END IF;
END $$;

-- 4. 添加注释
COMMENT ON COLUMN quant.orders.stop_loss_price IS '止损价格';
COMMENT ON COLUMN quant.orders.take_profit_price IS '止盈价格';
COMMENT ON COLUMN quant.orders.parent_order_id IS '关联的主订单ID（用于止损单、止盈单）';
COMMENT ON COLUMN quant.orders.order_group IS '订单组标识（UUID）';
COMMENT ON COLUMN quant.orders.risk_params IS '完整的风控参数（JSON格式）';
