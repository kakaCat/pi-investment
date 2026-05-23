-- PostgreSQL Schema for pi-investment Quantitative Trading System
-- This schema supports agent operation logging, trading positions, orders, and approval workflow

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS quant_agent;

-- Table 1: Agent operation logs
CREATE TABLE IF NOT EXISTS quant_agent.agent_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN ('analysis', 'signal_generation', 'order_creation', 'position_update', 'risk_check')),
    symbol TEXT NOT NULL,
    details JSONB NOT NULL,  -- Action parameters and reasoning
    result JSONB NOT NULL,   -- Action result
    status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'partial')),
    duration_ms INTEGER,
    data_snapshot_id UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp ON quant_agent.agent_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_agent_logs_symbol ON quant_agent.agent_logs(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_logs_action_type ON quant_agent.agent_logs(action_type);
CREATE INDEX IF NOT EXISTS idx_agent_logs_status ON quant_agent.agent_logs(status);
CREATE INDEX IF NOT EXISTS idx_agent_logs_created_at ON quant_agent.agent_logs(created_at DESC);

-- Table 2: Trading positions
CREATE TABLE IF NOT EXISTS quant_agent.positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id TEXT NOT NULL DEFAULT 'default',
    symbol TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    cost_basis DOUBLE PRECISION NOT NULL,
    current_price DOUBLE PRECISION,
    market_value DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION,
    unrealized_pnl_pct DOUBLE PRECISION,
    stop_loss DOUBLE PRECISION,
    take_profit DOUBLE PRECISION,
    entry_date DATE NOT NULL,
    entry_reason TEXT,
    entry_log_id UUID,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(account_id, symbol, status)
);

CREATE INDEX IF NOT EXISTS idx_positions_account_symbol ON quant_agent.positions(account_id, symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON quant_agent.positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_entry_date ON quant_agent.positions(entry_date);
CREATE INDEX IF NOT EXISTS idx_positions_updated_at ON quant_agent.positions(updated_at DESC);

-- Table 3: Position history (audit trail)
CREATE TABLE IF NOT EXISTS quant_agent.position_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('buy', 'sell', 'adjust', 'stop_loss', 'take_profit')),
    quantity INTEGER,
    price DOUBLE PRECISION,
    amount DOUBLE PRECISION,
    stop_loss DOUBLE PRECISION,
    take_profit DOUBLE PRECISION,
    reason TEXT,
    log_id UUID,
    timestamp TIMESTAMPTZ DEFAULT now(),
    FOREIGN KEY (position_id) REFERENCES quant_agent.positions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_position_history_position_id ON quant_agent.position_history(position_id);
CREATE INDEX IF NOT EXISTS idx_position_history_timestamp ON quant_agent.position_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_position_history_action ON quant_agent.position_history(action);

-- Table 4: Orders
CREATE TABLE IF NOT EXISTS quant_agent.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id TEXT NOT NULL DEFAULT 'default',
    symbol TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('buy', 'sell')),
    quantity INTEGER NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    submitted_by TEXT NOT NULL CHECK (submitted_by IN ('agent', 'user')),
    submitted_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'executed', 'cancelled')),
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    rejection_reason TEXT,
    reason TEXT,
    confidence DOUBLE PRECISION CHECK (confidence >= 0 AND confidence <= 1),
    agent_decision_id UUID,
    log_id UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON quant_agent.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON quant_agent.orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_submitted_at ON quant_agent.orders(submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_account_id ON quant_agent.orders(account_id);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON quant_agent.orders(created_at DESC);

-- Table 5: Agent decisions (for learning and feedback)
CREATE TABLE IF NOT EXISTS quant_agent.agent_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    decision_type TEXT NOT NULL CHECK (decision_type IN ('buy', 'sell', 'hold')),
    reasoning TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    supporting_data JSONB,
    log_id UUID,
    created_at TIMESTAMPTZ DEFAULT now(),
    user_feedback TEXT CHECK (user_feedback IN ('correct', 'incorrect', 'partial', NULL)),
    actual_outcome JSONB,
    feedback_notes TEXT,
    feedback_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_symbol ON quant_agent.agent_decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_created_at ON quant_agent.agent_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_decision_type ON quant_agent.agent_decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_feedback ON quant_agent.agent_decisions(user_feedback);

-- Table 6: Data snapshots (for reproducibility)
CREATE TABLE IF NOT EXISTS quant_agent.data_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    data_type TEXT NOT NULL CHECK (data_type IN ('market_data', 'analysis_result', 'indicator_values', 'fundamentals')),
    data JSONB NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_data_snapshots_symbol ON quant_agent.data_snapshots(symbol);
CREATE INDEX IF NOT EXISTS idx_data_snapshots_timestamp ON quant_agent.data_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_data_snapshots_data_type ON quant_agent.data_snapshots(data_type);
CREATE INDEX IF NOT EXISTS idx_data_snapshots_created_at ON quant_agent.data_snapshots(created_at DESC);

-- Table 7: Approval rules
CREATE TABLE IF NOT EXISTS quant_agent.approval_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name TEXT NOT NULL UNIQUE,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('auto_approve', 'require_approval', 'auto_reject')),
    conditions JSONB NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_approval_rules_priority ON quant_agent.approval_rules(priority DESC);
CREATE INDEX IF NOT EXISTS idx_approval_rules_enabled ON quant_agent.approval_rules(enabled);

-- Table 8: Accounts
CREATE TABLE IF NOT EXISTS quant_agent.accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    account_type TEXT NOT NULL CHECK (account_type IN ('real', 'paper')),
    initial_capital DOUBLE PRECISION NOT NULL,
    current_capital DOUBLE PRECISION NOT NULL,
    total_pnl DOUBLE PRECISION DEFAULT 0,
    total_pnl_pct DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_accounts_account_type ON quant_agent.accounts(account_type);

-- Insert default account (using a fixed UUID for consistency)
INSERT INTO quant_agent.accounts (id, name, account_type, initial_capital, current_capital)
VALUES ('00000000-0000-0000-0000-000000000001'::uuid, 'Default Account', 'paper', 100000.0, 100000.0)
ON CONFLICT (name) DO NOTHING;
