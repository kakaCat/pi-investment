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
  symbol?: string;
  symbols?: string[];
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
  /** 行情刷新时间戳（ISO），来自 simulation 账户接口的 price_updated_at */
  priceUpdatedAt?: string | null;
  /** 账户级行情陈旧标记：true=本次行情拉取失败，价格为旧值 */
  priceStale?: boolean;
}

/**
 * Portfolio summary
 */
export interface PortfolioSummary {
  accountName: string;
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
  /** 行情陈旧标记（透传自 simulation 账户接口） */
  priceStale?: boolean;
}

/**
 * Simulation 账户接口（GET /api/simulation/accounts/{account}）原始 snake_case 结构
 */
export interface SimulationPositionItem {
  symbol?: string;
  name?: string;
  shares_total?: number;
  shares_available?: number;
  avg_cost?: number;
  current_price?: number;
  market_value?: number;
  cost?: number;
  profit_total?: number;
  profit_total_rate?: number;
  profit_today?: number;
  created_at?: string;
  price_updated_at?: string;
  days_held?: number;
}

export interface SimulationAccountStatus {
  account_name?: string;
  display_name?: string | null;
  strategy_name?: string | null;
  cash_available?: number;
  cash_frozen?: number;
  position_value?: number;
  total_value?: number;
  initial_capital?: number;
  cumulative_return?: number;
  last_rebalance_date?: string | null;
  last_updated?: string;
  price_stale?: boolean;
  positions_count?: number;
  positions?: SimulationPositionItem[];
  benchmark?: unknown;
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
 * Macroeconomic data (GDP/CPI/PMI)
 * Real endpoint: GET /api/market/macro
 * Note: row keys are Chinese (e.g. "季度", "国内生产总值-同比增长")
 */
export interface MacroData {
  gdp: Array<Record<string, string | number>>;
  cpi: Array<Record<string, string | number>>;
  pmi: Array<Record<string, string | number>>;
  updateTime: string;
}

/**
 * North-bound capital flow (single trading day)
 * Real endpoint: GET /api/market/north-flow
 */
export interface NorthFlowDay {
  tradeDate: string;
  /** 净流入（元） */
  netFlow: number;
  /** 沪股通净流入（元） */
  shNetFlow: number;
  /** 深股通净流入（元） */
  szNetFlow: number;
}

/**
 * Market sentiment
 * Real endpoint: GET /api/market/sentiment
 */
export interface MarketSentiment {
  sentimentScore: number;
  sentimentLevel: string;
  fearGreedIndex: number;
  indicators: {
    advanceDecline?: {
      dataDate: string;
      upCount: number;
      downCount: number;
      flatCount: number;
      ratio: number;
      upPercentage: number;
      strength: string;
    };
    volume?: {
      dataDate: string;
      recentAvgVolume: number;
      baseAvgVolume: number;
      volumeRatio: number;
      status: string;
    };
    indexPerformance?: {
      dataDate: string;
      positiveCount: number;
      totalCount: number;
      avgReturn5DPct: number;
      marketTrend: string;
    };
    volatility?: {
      volatility: number;
      level: string;
    };
    newHighLow?: {
      dataDate: string;
      newHighCount: number;
      newLowCount: number;
      ratio: number;
      signal: string;
    };
  };
  degradedDimensions: string[];
  degraded: boolean;
  marketPhase: string;
  recommendation: string;
  timestamp: string;
}

/**
 * Client configuration
 */
export interface QuantsysV2ClientConfig {
  baseURL: string;
  timeout?: number;
  headers?: Record<string, string>;
}

// ==================== Missing Method Types (P0) ====================

/**
 * Trade execution request
 */
export interface TradeRequest {
  action: 'buy' | 'sell';
  symbol: string;
  quantity: number;
  price?: number;
  account_name?: string;
  /** 订单类型：market=市价 / limit=限价（2026-08-25 起后端必填，simulation 端点不使用） */
  order_type?: 'market' | 'limit';
  /** 交易理由（simulation 端点要求 ≥10 字，R-005 纪律） */
  reason?: string;
  /** 决策时基因组版本（RFC 005 决策打标，如 'g17'） */
  genome_version?: string;
}

/**
 * Trade execution response
 */
export interface TradeResponse {
  order_id: string;
  action: string;
  symbol: string;
  quantity: number;
  price: number;
  amount: number;
  status: string;
  timestamp: string;
}

/**
 * Algorithmic order execution request
 */
export interface AlgoExecuteRequest {
  side: 'buy' | 'sell';
  symbol: string;
  quantity: number;
  algo: 'TWAP' | 'VWAP';
  /** 执行时长（分钟）。2026-08-30 起透传为后端 duration_minutes */
  duration?: number;
  /** 后端契约参数名（duration 的别名，二选一） */
  duration_minutes?: number;
  account_name?: string;
}

/**
 * Algorithmic order execution response
 */
export interface AlgoExecuteResponse {
  algo_order_id: string;
  algo: string;
  symbol: string;
  total_quantity: number;
  filled_quantity: number;
  avg_price: number;
  slices: any[];
  status: string;
}

/**
 * Trade history / monitor response
 */
export interface TradeHistoryResponse {
  orders: any[];
  pendingCount: number;
  filledCount: number;
  total?: number;
  page?: number;
  pageSize?: number;
}

/**
 * Trade verification response
 */
export interface TradeVerifyResponse {
  date: string;
  total_orders: number;
  matched: number;
  mismatched: number;
  anomalies: any[];
}

/**
 * Market alert
 */
export interface Alert {
  id: string;
  level: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  symbol?: string;
  triggered_at: string;
}

/**
 * Watch rule management request
 */
export interface WatchRuleManageRequest {
  action: 'create' | 'enable' | 'disable' | 'delete';
  rule_id?: number;
  name?: string;
  symbol?: string;
  condition?: string;
}

/**
 * Sector analysis data
 */
export interface SectorInfo {
  name: string;
  change_pct: number;
  volume_ratio: number;
  leading_stocks?: string[];
}

/**
 * Sector analysis response
 */
export interface SectorAnalysisResponse {
  sectors: SectorInfo[];
  top_performers: SectorInfo[];
  worst_performers: SectorInfo[];
  rotation_signal?: string;
}

/**
 * Risk metrics
 */
export interface RiskMetrics {
  volatility: number;
  max_drawdown: number;
  sharpe_ratio: number;
  beta: number;
  alpha: number;
  var_95: number;
  sortino_ratio: number;
}

/**
 * Risk control request
 */
export interface RiskControlRequest {
  command: 'position_size' | 'stop_loss' | 'portfolio_risk';
  symbol?: string;
  account_name?: string;
  risk_level?: 'large_cap' | 'growth' | 'small_cap_theme';
  price?: number;
  entry_price?: number;
}

/**
 * Barra risk decomposition response
 */
export interface BarraDecompositionResponse {
  total_risk: number;
  factor_risks: any[];
  idiosyncratic_risk: number;
  industry_concentration: number;
  style_exposure: Record<string, any>;
}

/**
 * Signal generation request
 */
export interface SignalGenerateRequest {
  strategy_id: number;
  symbols?: string[];
  date?: string;
}

/**
 * Opportunity scan request
 */
export interface OpportunityScanRequest {
  // New fields for Strategy Package tools
  scan_type?: 'technical' | 'fundamental' | 'hybrid';
  pool_id?: number;
  symbols?: string[];
  min_score?: number;
  // Legacy fields (keep for backward compatibility)
  conditions?: string[];
  limit?: number;
}

/**
 * Opportunity scan result
 */
export interface Opportunity {
  symbol: string;
  name: string;
  score: number;
  reasons: string[];
  price: number;
  change_pct: number;
}

/**
 * Stock screening request
 */
export interface ScreenRequest {
  // New fields for Strategy Package tools
  criteria?: Record<string, any>;
  sort_by?: string;
  // Legacy fields (keep for backward compatibility)
  filters?: Record<string, any>;
  limit?: number;
}

/**
 * Stock screening response
 */
export interface ScreenResponse {
  total: number;
  stocks: any[];
}

/**
 * Rotation proposal request
 */
export interface RotationProposalRequest {
  // New fields for Strategy Package tools
  account_name?: string;
  mode?: 'conservative' | 'balanced' | 'aggressive';
  max_positions?: number;
  // Legacy fields (keep for backward compatibility)
  portfolio_id?: string;
}

/**
 * Rotation proposal response
 */
export interface RotationProposal {
  proposal_id: string;
  current_allocation: any[];
  proposed_allocation: any[];
  sell_list: any[];
  buy_list: any[];
  reasoning: string;
}

/**
 * Rotation simulate request
 */
export interface RotationSimulateRequest {
  // New fields for Strategy Package tools
  proposals?: Array<{
    // 2026-09-01：与后端 strategy_rotation_engine 对齐（原 buy/sell 交易语义不匹配会被静默忽略）
    action: 'activate' | 'deactivate' | 'adjust_weight';
    strategy_id?: number;
    strategy_name?: string;
    symbol?: string;
    weight?: number;
  }>;
  account_name?: string;
  check_constraints?: boolean;
  // Legacy fields (keep for backward compatibility)
  proposal_id?: string;
}

/**
 * Rotation simulate response
 */
export interface RotationSimulateResponse {
  proposal_id: string;
  current_return: number;
  proposed_return: number;
  improvement: number;
  risk_change: number;
  simulation_details: Record<string, any>;
}

/**
 * Rotation execute request
 */
export interface RotationExecuteRequest {
  // New fields for Strategy Package tools
  proposals?: Array<{
    // 2026-09-01：与后端 strategy_rotation_engine 对齐（activate/deactivate/adjust_weight）
    action: 'activate' | 'deactivate' | 'adjust_weight';
    strategy_id?: number;
    strategy_name?: string;
    symbol?: string;
    weight?: number;
  }>;
  account_name?: string;
  // Legacy fields (keep for backward compatibility)
  proposal_id?: string;
  dry_run?: boolean;
}

/**
 * Rotation execute response
 */
export interface RotationExecuteResponse {
  proposal_id: string;
  dry_run: boolean;
  executed: boolean;
  orders: any[];
  summary: string;
}

/**
 * Factor calculation request
 */
export interface FactorCalculateRequest {
  symbol: string;
  factors?: string[];
}

/**
 * Factor calculation response
 */
export interface FactorData {
  symbol: string;
  date: string;
  factors: Record<string, number>;
}

/**
 * Factor analysis request
 */
export interface FactorAnalyzeRequest {
  factor_name: string;
  start_date?: string;
  end_date?: string;
}

/**
 * Factor analysis response
 */
export interface FactorAnalysisResponse {
  factor_name: string;
  ic_mean: number;
  ic_std: number;
  ir: number;
  coverage: number;
  monotonicity: number;
  turnover: number;
  conclusion: string;
}

/**
 * Model prediction request
 */
export interface ModelPredictRequest {
  symbol: string;
  model_id?: string;
  horizon?: number;
}

/**
 * Model prediction response
 */
export interface ModelPrediction {
  symbol: string;
  model_id: string;
  up_probability: number;
  down_probability: number;
  expected_return: number;
  confidence: number;
  top_features: string[];
}

/**
 * Data quality report request
 */
export interface DataQualityReportRequest {
  data_type?: 'quote' | 'kline' | 'financial' | 'all';
  days?: number;
}

/**
 * Data quality report response
 */
export interface DataQualityReportResponse {
  data_type: string;
  check_date: string;
  overall_score: number;
  missing_data: any[];
  delayed_data: any[];
  anomalies: any[];
  summary: string;
}

/**
 * Data manager request
 */
export interface DataManagerRequest {
  command: 'status' | 'refresh' | 'cleanup' | 'backup';
  data_type?: string;
  symbol?: string;
}

/**
 * Data manager response
 */
export interface DataManagerResponse {
  command: string;
  status: string;
  details: Record<string, any>;
  message: string;
}

/**
 * Competition analysis response
 */
export interface CompetitionAnalysis {
  symbol: string;
  company_name: string;
  industry: {
    level1: string;
    level2: string;
  };
  market_size: {
    total_market_cap: number;
    industry_rank: number;
    market_share: number;
  };
  competitors: Array<{
    symbol: string;
    name: string;
    market_cap: number;
    market_share: number;
    competitive_position: 'leader' | 'second_tier' | 'follower';
  }>;
  financial_comparison?: {
    metrics: string[];
    data: Array<{
      symbol: string;
      name: string;
      [key: string]: any;
    }>;
  };
  competitive_advantages: string[];
  competitive_disadvantages: string[];
  summary: string;
}

/**
 * 事件日历条目（E1 特殊日子：宏观发布/央行议息/财报/交割）
 */
export interface CalendarEvent {
  id: number;
  event_type: string;        // cpi/ppi/pmi/gdp/nbs/lpr/fomc/us_cpi/nfp/earnings/futures_delivery/policy/other
  event_date: string;        // YYYY-MM-DD
  event_time?: string;       // HH:MM
  title: string;
  description?: string;
  symbol?: string;
  market?: string;           // CN/US
  importance?: number;       // 1低 2中 3高
  status?: string;           // pending/notified/collected/reviewed/skipped
  source?: string;
  meta?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

/**
 * 事件查询参数
 */
export interface EventListRequest {
  start?: string;            // YYYY-MM-DD
  end?: string;
  event_type?: string;
  status?: string;
  symbol?: string;
  limit?: number;
}

/**
 * 事件创建/更新请求
 */
export interface EventUpsertRequest {
  event_type: string;
  event_date: string;
  title: string;
  event_time?: string;
  description?: string;
  symbol?: string;
  market?: string;
  importance?: number;
  status?: string;
  source?: string;
  meta?: Record<string, any>;
}

export interface EventListResponse {
  success: boolean;
  count?: number;
  days?: number;
  events: CalendarEvent[];
}

/**
 * 通用数据源响应（data_provider 多数据源层）
 * 数据源失败时 success=false + error + attempted_sources，工具须降级友好处理
 */
export interface ProviderResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  attempted_sources?: string[];
  provider_errors?: Record<string, string>;
  source?: string;
}

/** 个股资金流单日记录 */
export interface FundFlowDay {
  date: string;
  closePrice?: number;
  changePct?: number;
  mainNetInflow?: number;      // 主力净流入（万）
  mainNetInflowRate?: number;
  largeNetInflow?: number;
  bigNetInflow?: number;
  mediumNetInflow?: number;
  smallNetInflow?: number;
  [key: string]: any;
}

/** 两融单日记录 */
export interface MarginDay {
  date: string;
  financingBalance?: number;   // 融资余额
  financingBuy?: number;
  financingRepay?: number;
  marginBalance?: number;      // 融券余额
  marginSell?: number;
  marginRepay?: number;
  totalBalance?: number;       // 两融总余额
  [key: string]: any;
}

/** 涨停池记录 */
export interface LimitUpRecord {
  代码?: string;
  名称?: string;
  涨跌幅?: number;
  最新价?: number;
  成交额?: number;
  流通市值?: number;
  换手率?: number;
  封板资金?: number;
  首次封板时间?: string;
  炸板次数?: number;
  连板数?: number;
  所属行业?: string;
  [key: string]: any;
}

/** 个股新闻记录 */
export interface StockNewsItem {
  新闻标题?: string;
  新闻内容?: string;
  发布时间?: string;
  文章来源?: string;
  新闻链接?: string;
  [key: string]: any;
}
