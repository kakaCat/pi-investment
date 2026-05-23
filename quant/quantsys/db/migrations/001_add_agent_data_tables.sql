-- Migration: Add agent data tables and extend existing tables
-- Date: 2026-05-23
-- Description: Create watchlist table and extend positions, position_history, accounts tables

-- 1. Create watchlist table
CREATE TABLE IF NOT EXISTS quant_agent.watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('A', 'HK', 'US')),
    buy_range_low DOUBLE PRECISION,
    buy_range_high DOUBLE PRECISION,
    target_price DOUBLE PRECISION,
    stop_loss DOUBLE PRECISION,
    priority INTEGER DEFAULT 3,
    pool TEXT CHECK (pool IN ('A', 'B', 'C')),
    status TEXT DEFAULT 'watching' CHECK (status IN ('watching', 'paused', 'removed')),
    reason TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_watchlist_symbol ON quant_agent.watchlist(symbol);
CREATE INDEX IF NOT EXISTS idx_watchlist_priority ON quant_agent.watchlist(priority);
CREATE INDEX IF NOT EXISTS idx_watchlist_pool ON quant_agent.watchlist(pool);
CREATE INDEX IF NOT EXISTS idx_watchlist_status ON quant_agent.watchlist(status);

-- 2. Extend positions table
ALTER TABLE quant_agent.positions
ADD COLUMN IF NOT EXISTS name TEXT,
ADD COLUMN IF NOT EXISTS market TEXT CHECK (market IN ('A', 'HK', 'US')),
ADD COLUMN IF NOT EXISTS sector TEXT,
ADD COLUMN IF NOT EXISTS notes TEXT,
ADD COLUMN IF NOT EXISTS original_cost DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS total_invested DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS batch_plan TEXT;

-- 3. Extend position_history table
ALTER TABLE quant_agent.position_history
ADD COLUMN IF NOT EXISTS name TEXT,
ADD COLUMN IF NOT EXISTS fee DOUBLE PRECISION DEFAULT 0,
ADD COLUMN IF NOT EXISTS realized_pnl DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS realized_pnl_pct DOUBLE PRECISION,
ADD COLUMN IF NOT EXISTS notes TEXT;

-- 4. Extend accounts table
ALTER TABLE quant_agent.accounts
ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'CNY',
ADD COLUMN IF NOT EXISTS notes TEXT;
