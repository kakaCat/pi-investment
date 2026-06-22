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
  costBasis: number;
  currentPrice?: number;
  entryDate: string;
  stopLoss?: number;
  takeProfit?: number;
  status: 'open' | 'closed';
  accountId: string;
  notes?: string;
}

export interface PositionSummary {
  totalPositions: number;
  totalQuantity: number;
  totalCost: number;
  totalMarketValue: number;
  totalPnl: number;
  totalPnlPct: number;
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
  buyRangeLow?: number;
  buyRangeHigh?: number;
  targetPrice?: number;
  stopLoss?: number;
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
  realizedPnl?: number;
  notes?: string;
}

export interface TradeStats {
  totalTrades: number;
  buyCount: number;
  sellCount: number;
  totalPnl: number;
  avgPnl: number;
  winCount: number;
  lossCount: number;
  winRate: number;
}

// ============================================================================
// Account Types
// ============================================================================

export interface Account {
  name: string;
  currentCapital: number;
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
