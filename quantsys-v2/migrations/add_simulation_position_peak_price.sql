-- quant.simulation_positions.peak_price（2026-10-26 止损链路修复）
--
-- 背景：IntradayRiskService 已声明移动止损规则，但持仓表/ORM/仓储均未提供
-- peak_price，导致该规则实际永远不会触发。本迁移为移动止损补齐持久化峰值，
-- 并用 max(avg_cost, current_price) 回填存量持仓的初始峰值。
--
-- 幂等：可重复执行；表不存在时跳过该段并输出 NOTICE。
DO $$
BEGIN
    IF to_regclass('quant.simulation_positions') IS NULL THEN
        RAISE NOTICE 'quant.simulation_positions 不存在 → 跳过 peak_price 迁移';
    ELSE
        ALTER TABLE quant.simulation_positions
            ADD COLUMN IF NOT EXISTS peak_price NUMERIC(10, 2);

        UPDATE quant.simulation_positions
        SET peak_price = GREATEST(avg_cost, COALESCE(current_price, avg_cost))
        WHERE peak_price IS NULL;

        COMMENT ON COLUMN quant.simulation_positions.peak_price IS
            '持仓后历史最高价（移动止损基准）';
    END IF;
END $$;
