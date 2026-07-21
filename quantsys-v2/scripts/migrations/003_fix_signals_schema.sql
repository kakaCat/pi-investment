-- ============================================================
-- Migration: 003_fix_signals_schema
-- Description: Align quant.signals table with code expectations.
--   Code references action/confidence/name/strategy_id/price/reason/
--   indicators/action_type/reject_reason/error_description columns
--   that don't exist in the original schema (which used final_action/
--   final_confidence instead). This migration adds them all.
-- Created: 2026-05-24
-- ============================================================

-- Add missing columns (IF NOT EXISTS safe to re-run)
ALTER TABLE quant.signals ADD COLUMN IF NOT EXISTS name              TEXT;
ALTER TABLE quant.signals ADD COLUMN IF NOT EXISTS action            VARCHAR(10);
ALTER TABLE quant.signals ADD COLUMN IF NOT EXISTS action_type       VARCHAR(20);
ALTER TABLE quant.signals ADD COLUMN IF NOT EXISTS strategy_id       VARCHAR(50);
ALTER TABLE quant.signals ADD COLUMN IF NOT EXISTS confidence        DECIMAL(5,4);
ALTER TABLE quant.signals ADD COLUMN IF NOT EXISTS price             DECIMAL(10,2);
ALTER TABLE quant.signals ADD COLUMN IF NOT EXISTS reason            TEXT;
ALTER TABLE quant.signals ADD COLUMN IF NOT EXISTS indicators        JSONB;
ALTER TABLE quant.signals ADD COLUMN IF NOT EXISTS reject_reason     TEXT;
ALTER TABLE quant.signals ADD COLUMN IF NOT EXISTS error_description TEXT;

-- Fix unique constraint: drop old 2-column, add new 3-column
-- (symbol, signal_date, strategy_id) so multiple strategies can emit
-- signals for the same symbol+date.
ALTER TABLE quant.signals DROP CONSTRAINT IF EXISTS unique_symbol_date;

-- Dedup: keep only the newest row per (symbol, signal_date, strategy_id)
DELETE FROM quant.signals
WHERE id NOT IN (
    SELECT MAX(id)
    FROM quant.signals
    WHERE strategy_id IS NOT NULL
    GROUP BY symbol, signal_date, strategy_id
) AND strategy_id IS NOT NULL;

ALTER TABLE quant.signals ADD CONSTRAINT unique_symbol_date_strategy
    UNIQUE(symbol, signal_date, strategy_id);

-- Fix default status: code expects 'pending' not 'active'
ALTER TABLE quant.signals ALTER COLUMN status SET DEFAULT 'pending';

DO $$
BEGIN
    RAISE NOTICE 'Migration 003_fix_signals_schema completed successfully';
END $$;
