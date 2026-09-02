-- Migration: Add is_active column to strategy_configs
-- Part 4.3 of the strategy refactoring
-- Purpose: Allow enabling/disabling strategies dynamically

-- Add is_active column with default TRUE for existing rows.
-- NOT NULL DEFAULT TRUE ensures all existing strategies remain active
-- and application code can rely on the column always having a value.
ALTER TABLE quant.strategy_configs
ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- Ensure legacy V13/V14 strategies are explicitly marked active.
-- These strategy names are the canonical identifiers for the legacy
-- simulation-trading strategies in the system.
UPDATE quant.strategy_configs
SET is_active = TRUE
WHERE strategy_name IN ('v13', 'v14');

-- Add index for fast filtering of active/inactive strategies.
CREATE INDEX IF NOT EXISTS idx_strategy_configs_is_active
ON quant.strategy_configs(is_active);
