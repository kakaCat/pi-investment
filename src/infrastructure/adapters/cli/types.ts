/**
 * CLI Adapter Types and Error Classes
 */

// ============================================================================
// Position Types
// ============================================================================

export interface Position {
  symbol: string;
  name: string;
  quantity: number;
  cost_basis: number;
  current_price?: number;
  entry_date: string;
  stop_loss?: number;
  take_profit?: number;
  status: 'open' | 'closed';
  account_id: string;
  notes?: string;
}

export interface PositionSummary {
  total_positions: number;
  total_quantity: number;
  total_cost: number;
  total_market_value: number;
  total_pnl: number;
  total_pnl_pct: number;
}

// ============================================================================
// Watchlist Types
// ============================================================================

export interface WatchlistItem {
  symbol: string;
  name: string;
  market: 'A' | 'HK';
  priority: number;
  pool: 'A' | 'B' | 'C';
  status: 'watching' | 'ready' | 'bought' | 'discarded';
  buy_range_low?: number;
  buy_range_high?: number;
  target_price?: number;
  stop_loss?: number;
  reason?: string;
  notes?: string;
}

// ============================================================================
// Trade Types
// ============================================================================

export interface Trade {
  id: string;
  symbol: string;
  name: string;
  action: 'buy' | 'sell';
  quantity: number;
  price: number;
  timestamp: string;
  realized_pnl?: number;
  notes?: string;
}

export interface TradeStats {
  total_trades: number;
  buy_count: number;
  sell_count: number;
  total_pnl: number;
  avg_pnl: number;
  win_count: number;
  loss_count: number;
  win_rate: number;
}

// ============================================================================
// Account Types
// ============================================================================

export interface Account {
  name: string;
  current_capital: number;
  currency: string;
  notes?: string;
}

// ============================================================================
// Error Classes
// ============================================================================

export class CliExecutionError extends Error {
  constructor(
    message: string,
    public readonly command: string,
    public readonly exitCode: number
  ) {
    super(message);
    this.name = 'CliExecutionError';
  }
}

export class CliParseError extends Error {
  constructor(
    message: string,
    public readonly output: string
  ) {
    super(message);
    this.name = 'CliParseError';
  }
}
