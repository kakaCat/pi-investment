-- ============================================================
-- Migration: 004_add_trades_pnl
-- Description: Add pnl / pnl_percent columns to quant.trades
--   for tracking profit & loss on each trade.
-- Created: 2026-05-24
-- ============================================================

ALTER TABLE quant.trades ADD COLUMN IF NOT EXISTS pnl         DOUBLE PRECISION;
ALTER TABLE quant.trades ADD COLUMN IF NOT EXISTS pnl_percent DOUBLE PRECISION;

COMMENT ON COLUMN quant.trades.pnl         IS '交易盈亏金额';
COMMENT ON COLUMN quant.trades.pnl_percent IS '交易盈亏百分比';

DO $$
BEGIN
    RAISE NOTICE 'Migration 004_add_trades_pnl completed successfully';
END $$;
