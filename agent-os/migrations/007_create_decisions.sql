-- Migration: 007_create_decisions
-- Description: Create decisions table for WP-7 Decision System
-- Created: 2026-08-14

-- ============================================================================
-- UP Migration
-- ============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing decisions table if it exists (from schema.sql)
DROP TABLE IF EXISTS decisions CASCADE;

-- Create new decisions table matching WP-7 specification
CREATE TABLE decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(64) NOT NULL,
    action VARCHAR(32) NOT NULL,  -- watch, buy, sell, hold
    targets TEXT[],               -- Stock symbols array
    reason TEXT,                  -- Decision rationale
    confidence FLOAT,             -- Confidence [0, 1]
    context JSONB,                -- Decision context
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    executed_at TIMESTAMP WITH TIME ZONE,  -- Execution time
    outcome JSONB                 -- Execution result
);

-- Create indexes for efficient querying
CREATE INDEX idx_decisions_agent_id ON decisions(agent_id);
CREATE INDEX idx_decisions_action ON decisions(action);
CREATE INDEX idx_decisions_created_at ON decisions(created_at DESC);
CREATE INDEX idx_decisions_executed_at ON decisions(executed_at) WHERE executed_at IS NOT NULL;

-- Add constraint to validate action values
ALTER TABLE decisions ADD CONSTRAINT check_action
    CHECK (action IN ('watch', 'buy', 'sell', 'hold'));

-- Add constraint to validate confidence range
ALTER TABLE decisions ADD CONSTRAINT check_confidence
    CHECK (confidence >= 0 AND confidence <= 1);

-- Add constraint to ensure targets is not empty
ALTER TABLE decisions ADD CONSTRAINT check_targets_not_empty
    CHECK (array_length(targets, 1) > 0);

-- ============================================================================
-- DOWN Migration
-- ============================================================================

-- To rollback this migration:
-- DROP TABLE IF EXISTS decisions CASCADE;
--
-- Then restore the old schema from schema.sql if needed:
-- CREATE TABLE IF NOT EXISTS decisions (
--     id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
--     namespace_id UUID NOT NULL REFERENCES namespaces(id) ON DELETE CASCADE,
--     decision_type VARCHAR(50) NOT NULL,
--     action TEXT NOT NULL,
--     reasoning TEXT,
--     confidence FLOAT,
--     status VARCHAR(20) DEFAULT 'pending',
--     created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
--     executed_at TIMESTAMP WITH TIME ZONE,
--     result JSONB,
--     metadata JSONB DEFAULT '{}'::jsonb
-- );
