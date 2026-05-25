-- SQLite Schema for pi-investment Quantitative Trading System
-- This schema supports agent operation logging, trading positions, orders, and approval workflow

-- Table 1: Agent operation logs
CREATE TABLE IF NOT EXISTS agent_logs (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN ('analysis', 'signal_generation', 'order_creation', 'position_update', 'risk_check')),
    symbol TEXT NOT NULL,
    details TEXT NOT NULL,  -- JSON: Action parameters and reasoning
    result TEXT NOT NULL,   -- JSON: Action result
    status TEXT NOT NULL CHECK (status IN ('success', 'failed', 'partial')),
    duration_ms INTEGER,
    data_snapshot_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp ON agent_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_agent_logs_symbol ON agent_logs(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_logs_action_type ON agent_logs(action_type);
CREATE INDEX IF NOT EXISTS idx_agent_logs_status ON agent_logs(status);

-- Table 2: Trading positions
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL DEFAULT 'default',
    symbol TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    cost_basis REAL NOT NULL,
    current_price REAL,
    market_value REAL,
    unrealized_pnl REAL,
    unrealized_pnl_pct REAL,
    stop_loss REAL,
    take_profit REAL,
    entry_date DATE NOT NULL,
    entry_reason TEXT,
    entry_log_id TEXT,  -- Reference to agent_logs
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, symbol, status)
);

CREATE INDEX IF NOT EXISTS idx_positions_account_symbol ON positions(account_id, symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_entry_date ON positions(entry_date);

-- Table 3: Position history (audit trail)
CREATE TABLE IF NOT EXISTS position_history (
    id TEXT PRIMARY KEY,
    position_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('buy', 'sell', 'adjust', 'stop_loss', 'take_profit')),
    quantity INTEGER,
    price REAL,
    amount REAL,
    stop_loss REAL,
    take_profit REAL,
    reason TEXT,
    log_id TEXT,  -- Reference to agent_logs
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_position_history_position_id ON position_history(position_id);
CREATE INDEX IF NOT EXISTS idx_position_history_timestamp ON position_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_position_history_action ON position_history(action);

-- Table 4: Orders
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL DEFAULT 'default',
    symbol TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('buy', 'sell')),
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    amount REAL NOT NULL,
    submitted_by TEXT NOT NULL CHECK (submitted_by IN ('agent', 'user')),
    submitted_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'executed', 'cancelled')),
    approved_by TEXT,
    approved_at TIMESTAMP,
    executed_at TIMESTAMP,
    rejection_reason TEXT,
    reason TEXT,  -- Why this order was created
    confidence REAL CHECK (confidence >= 0 AND confidence <= 1),
    agent_decision_id TEXT,
    log_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_submitted_at ON orders(submitted_at);
CREATE INDEX IF NOT EXISTS idx_orders_account_id ON orders(account_id);

-- Table 5: Agent decisions (for learning and feedback)
CREATE TABLE IF NOT EXISTS agent_decisions (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    decision_type TEXT NOT NULL CHECK (decision_type IN ('buy', 'sell', 'hold')),
    reasoning TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    supporting_data TEXT,  -- JSON: Technical indicators, fundamentals, etc.
    log_id TEXT,  -- Reference to agent_logs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_feedback TEXT CHECK (user_feedback IN ('correct', 'incorrect', 'partial', NULL)),
    actual_outcome TEXT,  -- JSON: What actually happened
    feedback_notes TEXT,
    feedback_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_symbol ON agent_decisions(symbol);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_created_at ON agent_decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_decision_type ON agent_decisions(decision_type);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_feedback ON agent_decisions(user_feedback);

-- Table 6: Data snapshots (for reproducibility)
CREATE TABLE IF NOT EXISTS data_snapshots (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    data_type TEXT NOT NULL CHECK (data_type IN ('market_data', 'analysis_result', 'indicator_values', 'fundamentals')),
    data TEXT NOT NULL,  -- JSON: Snapshot data
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_data_snapshots_symbol ON data_snapshots(symbol);
CREATE INDEX IF NOT EXISTS idx_data_snapshots_timestamp ON data_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_data_snapshots_data_type ON data_snapshots(data_type);

-- Table 7: Approval rules
CREATE TABLE IF NOT EXISTS approval_rules (
    id TEXT PRIMARY KEY,
    rule_name TEXT NOT NULL UNIQUE,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('auto_approve', 'require_approval', 'auto_reject')),
    conditions TEXT NOT NULL,  -- JSON: Rule conditions (e.g., {"max_amount": 10000, "symbols": ["600000"]})
    priority INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_approval_rules_priority ON approval_rules(priority DESC);
CREATE INDEX IF NOT EXISTS idx_approval_rules_enabled ON approval_rules(enabled);

-- Table 8: Accounts
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    account_type TEXT NOT NULL CHECK (account_type IN ('real', 'paper')),
    initial_capital REAL NOT NULL,
    current_capital REAL NOT NULL,
    total_pnl REAL DEFAULT 0,
    total_pnl_pct REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_accounts_account_type ON accounts(account_type);

-- Insert default account
INSERT OR IGNORE INTO accounts (id, name, account_type, initial_capital, current_capital)
VALUES ('default', 'Default Account', 'paper', 100000.0, 100000.0);
