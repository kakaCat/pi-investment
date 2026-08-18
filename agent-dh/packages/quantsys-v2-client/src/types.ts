/**
 * Stock information
 */
export interface Stock {
  symbol: string;
  name: string;
  market?: string;
}

/**
 * K-line data
 */
export interface KlineData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount?: number;
}

/**
 * Strategy information
 */
export interface Strategy {
  id: number;
  name: string;
  code: string;
  code_type: 'indicator' | 'script' | 'trend_following' | 'mean_reversion' | 'multi_factor';
  description?: string;
  parameters?: Record<string, any>;
  source?: 'builtin' | 'user';
}

/**
 * Backtest request
 */
export interface BacktestRequest {
  strategy_id?: number;
  strategy_code?: string;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
  parameters?: Record<string, any>;
}

/**
 * Backtest result
 */
export interface BacktestResult {
  total_return: number;
  annual_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  trades?: Trade[];
  equity_curve?: EquityPoint[];
}

/**
 * Trade record
 */
export interface Trade {
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  shares: number;
  profit: number;
  return: number;
}

/**
 * Equity curve point
 */
export interface EquityPoint {
  date: string;
  equity: number;
}

/**
 * Pool information
 */
export interface Pool {
  id: number;
  name: string;
  pool_type: string;
  description?: string;
  symbol_count: number;
  refresh_interval?: string | null;
  last_refreshed_at?: string | null;
  has_validation: boolean;
  created_at: string;
}

/**
 * Pool member
 */
export interface PoolMember {
  symbol: string;
  name: string;
  added_at: string;
  score?: number;
  metadata?: Record<string, any>;
}

/**
 * Signal information
 */
export interface Signal {
  id: number;
  symbol: string;
  signal_type: 'buy' | 'sell';
  strategy_id: number;
  generated_at: string;
  price: number;
  confidence?: number;
  metadata?: Record<string, any>;
}

/**
 * Financial data
 */
export interface FinancialData {
  symbol: string;
  report_date: string;
  revenue?: number;
  net_profit?: number;
  total_assets?: number;
  total_liabilities?: number;
  roe?: number;
  eps?: number;
  [key: string]: any;
}

/**
 * Watch rule
 */
export interface WatchRule {
  id: number;
  symbol: string;
  enabled: boolean;
  conditions: Array<{
    type: string;
    params: Record<string, any>;
  }>;
  context: string;
  cost_price?: number | null;
  active_window?: string | null;
  expires_at?: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

/**
 * Portfolio position
 */
export interface Position {
  symbol: string;
  name: string;
  quantity: number;
  sharesAvailable: number;
  avgCost: number;
  currentPrice: number;
  totalCost: number;
  currentValue: number;
  profitLoss: number;
  profitLossPct: number;
  profitToday: number;
}

/**
 * Portfolio summary
 */
export interface PortfolioSummary {
  totalValue: number;
  totalCost: number;
  totalMarketValue: number;
  totalPnl: number;
  totalPnlPct: number;
  dailyChange: number;
  positions: number;
  cash: number;
  liquidAssets: number;
  profitCount: number;
  lossCount: number;
  lastUpdated: string;
}

/**
 * Quote data (real-time market quote)
 */
export interface QuoteData {
  symbol: string;
  name: string;
  price: number;
  open: number;
  high: number;
  low: number;
  prevClose: number;
  volume: number;
  amount: number;
  change: number;
  changePct: number;
  source: string;
  timestamp: string;
}

/**
 * Strategy list response (paginated)
 */
export interface StrategyListResponse {
  total: number;
  page: number;
  pageSize: number;
  items: Strategy[];
}

/**
 * Evolution leaderboard entry
 */
export interface EvolutionLeaderboardEntry {
  accountName: string;
  windowEnd: string;
  upCapture: number;
  downCapture: number;
  fitness: number;
  upDays: number;
  downDays: number;
  status: string;
  rank: number;
}

/**
 * Evolution leaderboard
 */
export interface EvolutionLeaderboard {
  windowEnd: string;
  windowDays: number;
  ranking: EvolutionLeaderboardEntry[];
}

/**
 * Evolution decision score entry
 */
export interface EvolutionDecisionScore {
  id: number;
  decisionId: string;
  decisionType: string;
  context: Record<string, any>;
  parameters: Record<string, any>;
  reasoning: string;
  createdAt: string;
  createdBy: string;
  evaluationStatus: string;
  evaluationResult?: {
    band: string;
    score: number;
    scorer: string;
    refDate: string;
    benchmark: string;
    refPrice: number;
    tradeDate: string;
    tradePrice: number;
    excessReturn: number;
    benchmarkMissing: boolean;
    windowTradingDays: number;
  };
  evaluationDate?: string;
  learnedLesson?: string | null;
  confidenceScore?: number | null;
}

/**
 * Evolution decision scores response
 */
export interface EvolutionDecisionScores {
  total: number;
  items: EvolutionDecisionScore[];
}

/**
 * Client configuration
 */
export interface QuantsysV2ClientConfig {
  baseURL: string;
  timeout?: number;
  headers?: Record<string, string>;
}
