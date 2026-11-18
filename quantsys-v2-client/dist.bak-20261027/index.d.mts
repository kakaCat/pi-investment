//#region src/types.d.ts
/**
 * Stock information
 */
interface Stock {
  symbol: string;
  name: string;
  market?: string;
}
/**
 * K-line data
 */
interface KlineData {
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
interface Strategy {
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
interface BacktestRequest {
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
interface BacktestResult {
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
interface Trade {
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
interface EquityPoint {
  date: string;
  equity: number;
}
/**
 * Pool information
 */
interface Pool {
  id: number;
  name: string;
  pool_type: string;
  /** 业务分类（板块共振/主题/策略/观察…），与 pool_type(static/dynamic) 正交 */
  category?: string | null;
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
interface PoolMember {
  symbol: string;
  name: string;
  added_at: string;
  score?: number;
  metadata?: Record<string, any>;
}
/**
 * Signal information
 */
interface Signal {
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
interface FinancialData {
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
interface WatchRule {
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
  /** 归属账户（account_name 全名，如 agent_virtual）；null=通用观察（跨账户看板展示） */
  account?: string | null;
}
/**
 * ZigZag 波段分析结果（POST /api/analysis/swing-points，响应 camelCase）
 */
interface SwingPoint {
  date: string;
  price: number;
  type: 'high' | 'low';
  changePct: number;
}
interface SwingTrade {
  buyDate: string;
  buyPrice: number;
  sellDate: string;
  sellPrice: number;
  profitPct: number;
  holdingDays: number;
}
interface SwingPointSummary {
  totalTrades: number;
  winCount: number;
  lossCount: number;
  winRate: number;
  totalReturn: number;
  avgReturn: number;
  maxReturn: number;
  maxLoss: number;
  avgHoldingDays: number;
}
interface SwingPointAnalysis {
  symbol: string;
  period: {
    start: string;
    end: string;
  };
  minChange: number;
  klineCount?: number;
  swingPoints: SwingPoint[];
  trades: SwingTrade[];
  summary: SwingPointSummary;
  message?: string;
  error?: string;
  suggestions?: string[];
}
/**
 * Portfolio position
 */
interface Position {
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
  /** 持仓后历史最高价（移动止盈峰值基准；无数据时为 0） */
  peakPrice?: number;
  /** 行情刷新时间戳（ISO），来自 simulation 账户接口的 price_updated_at */
  priceUpdatedAt?: string | null;
  /** 账户级行情陈旧标记：true=本次行情拉取失败，价格为旧值 */
  priceStale?: boolean;
}
/**
 * Portfolio summary
 */
interface PortfolioSummary {
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
interface SimulationPositionItem {
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
interface SimulationAccountStatus {
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
interface QuoteData {
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
interface StrategyListResponse {
  total: number;
  page: number;
  pageSize: number;
  items: Strategy[];
}
/**
 * Evolution leaderboard entry
 */
interface EvolutionLeaderboardEntry {
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
interface EvolutionLeaderboard {
  windowEnd: string;
  windowDays: number;
  ranking: EvolutionLeaderboardEntry[];
}
/**
 * Evolution decision score entry
 */
interface EvolutionDecisionScore {
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
interface EvolutionDecisionScores {
  total: number;
  items: EvolutionDecisionScore[];
}
/**
 * Macroeconomic data (GDP/CPI/PMI)
 * Real endpoint: GET /api/market/macro
 * Note: row keys are Chinese (e.g. "季度", "国内生产总值-同比增长")
 */
interface MacroData {
  gdp: Array<Record<string, string | number>>;
  cpi: Array<Record<string, string | number>>;
  pmi: Array<Record<string, string | number>>;
  updateTime: string;
}
/**
 * North-bound capital flow (single trading day)
 * Real endpoint: GET /api/market/north-flow
 */
interface NorthFlowDay {
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
interface MarketSentiment {
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
interface QuantsysV2ClientConfig {
  baseURL: string;
  timeout?: number;
  headers?: Record<string, string>;
}
/**
 * Trade execution request
 */
interface TradeRequest {
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
  /** 执行时机：'market_open'=盘前挂单（非交易时段提交，开盘 9:31 起自动撮合） */
  execute_at?: 'market_open';
  /** 重复挂单确认（2026-09-03）：同标的同方向已有 pending 单时后端 409 拦截，确认后设 true 放行 */
  allow_duplicate?: boolean;
}
/**
 * Trade execution response
 */
interface TradeResponse {
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
interface AlgoExecuteRequest {
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
interface AlgoExecuteResponse {
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
interface TradeHistoryResponse {
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
interface TradeVerifyResponse {
  date: string;
  total_orders: number;
  matched: number;
  mismatched: number;
  anomalies: any[];
}
/**
 * Market alert
 */
interface Alert {
  id: string;
  level: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  symbol?: string;
  triggered_at: string;
}
/**
 * 盯盘待办（quant.watch_todos，2026-10-16）
 *
 * 为什么需要：规则自愈/元评审/补全指引会派「修规则工单」（watch_todos），而 wake
 * 只负责通知——agent 此前**没有任何工具能读/认领/关闭待办**，工单只能靠人，
 * 且处置结论回执全库仅 1 条（闭环从未跑通）。
 */
interface WatchTodo {
  id: number;
  /** 触发来源（规则自愈/元评审派出的工单为 null） */
  trigger_id?: number | null;
  rule_id?: number | null;
  symbol: string;
  account?: string | null;
  /** P0..P3 */
  level: string;
  /** L1 / L2 / L3（P0/P1 建出来即 L3） */
  flow_state: string;
  owner_kind?: 'agent' | 'user' | null;
  owner_ref?: string | null;
  autonomy?: string | null;
  sla_seconds?: number | null;
  due_at?: string | null;
  terminal?: 'handled' | 'ignored' | 'expired' | null;
  close_reason?: string | null;
  next_condition?: string | null;
  action_kind?: 'trade' | 'rule_change' | null;
  decision_audit_id?: string | null;
  escalate_count?: number;
  claimed_at?: string | null;
  closed_at?: string | null;
  created_at?: string | null;
}
/** 待办列表查询参数（GET /api/watch/todos） */
interface WatchTodoListParams {
  level?: string;
  flow_state?: string;
  account?: string;
  /** 不传=只返回未收敛；'*'=全部；其余按终态精确过滤 */
  terminal?: string;
  /** 默认 100，上限 500 */
  limit?: number;
}
/**
 * 待办收敛请求（POST /api/watch/todos/{id}/close）
 *
 * 服务端硬约束（缺一即 400）：
 *   · terminal=ignored 必须给 next_condition（下次什么条件下才动）；
 *   · flow_state=L3 且 action_kind ∈ (trade, rule_change) 必须给 decision_audit_id。
 */
interface WatchTodoCloseRequest {
  terminal: 'handled' | 'ignored' | 'expired';
  /** 处置结论（写清做了什么 / 为什么不动） */
  close_reason?: string;
  /** terminal=ignored 必填 */
  next_condition?: string;
  action_kind?: 'trade' | 'rule_change';
  /** 决策审计 ID（L3 + trade/rule_change 必填） */
  decision_audit_id?: string;
  closed_by?: string;
}
/**
 * Watch rule management request
 */
interface WatchRuleManageRequest {
  action: 'create' | 'enable' | 'disable' | 'delete';
  rule_id?: number;
  name?: string;
  symbol?: string;
  condition?: string;
  /** 结构化条件数组（高级用法，与 condition 二选一；同一条规则多条件=OR 语义） */
  conditions?: Array<{
    type: string;
    params: Record<string, any>;
  }>;
  /** 监视理由（触发时随通知带出，供决策回溯） */
  context?: string;
  /** 成本价（pnl_pct 条件必填；不传时工具层可自动取持仓成本） */
  cost_price?: number;
  /** 生效时段，如 "09:30-11:30,13:00-15:00" */
  active_window?: string;
  /** 过期时间 ISO 格式，如 2026-09-30T15:00:00 */
  expires_at?: string;
  created_by?: string;
  /** 归属账户（account_name 全名，如 agent_virtual）。持仓止损/止盈等账户内规则必传；
   *  不传=通用观察（无主候选，各账户看板均可见） */
  account?: string;
}
/**
 * Sector analysis data
 */
interface SectorInfo {
  name: string;
  change_pct: number;
  volume_ratio: number;
  leading_stocks?: string[];
}
/**
 * Sector analysis response
 */
interface SectorAnalysisResponse {
  sectors: SectorInfo[];
  top_performers: SectorInfo[];
  worst_performers: SectorInfo[];
  rotation_signal?: string;
}
/**
 * Risk metrics
 */
interface RiskMetrics {
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
interface RiskControlRequest {
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
interface BarraDecompositionResponse {
  total_risk: number;
  factor_risks: any[];
  idiosyncratic_risk: number;
  industry_concentration: number;
  style_exposure: Record<string, any>;
}
/**
 * Signal generation request
 */
interface SignalGenerateRequest {
  strategy_id: number;
  symbols?: string[];
  date?: string;
}
/**
 * Opportunity scan request
 */
interface OpportunityScanRequest {
  scan_type?: 'technical' | 'fundamental' | 'hybrid';
  pool_id?: number;
  symbols?: string[];
  min_score?: number;
  conditions?: string[];
  limit?: number;
}
/**
 * Opportunity scan result
 */
interface Opportunity {
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
interface ScreenRequest {
  criteria?: Record<string, any>;
  sort_by?: string;
  filters?: Record<string, any>;
  limit?: number;
}
/**
 * Stock screening response
 */
interface ScreenResponse {
  total: number;
  stocks: any[];
}
/**
 * Rotation proposal request
 */
interface RotationProposalRequest {
  account_name?: string;
  mode?: 'conservative' | 'balanced' | 'aggressive';
  max_positions?: number;
  portfolio_id?: string;
}
/**
 * Rotation proposal response
 */
interface RotationProposal {
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
interface RotationSimulateRequest {
  proposals?: Array<{
    action: 'activate' | 'deactivate' | 'adjust_weight';
    strategy_id?: number;
    strategy_name?: string;
    symbol?: string;
    weight?: number;
  }>;
  account_name?: string;
  check_constraints?: boolean;
  proposal_id?: string;
}
/**
 * Rotation simulate response
 */
interface RotationSimulateResponse {
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
interface RotationExecuteRequest {
  proposals?: Array<{
    action: 'activate' | 'deactivate' | 'adjust_weight';
    strategy_id?: number;
    strategy_name?: string;
    symbol?: string;
    weight?: number;
  }>;
  account_name?: string;
  proposal_id?: string;
  dry_run?: boolean;
}
/**
 * Rotation execute response
 */
interface RotationExecuteResponse {
  proposal_id: string;
  dry_run: boolean;
  executed: boolean;
  orders: any[];
  summary: string;
}
/**
 * Factor calculation request
 */
interface FactorCalculateRequest {
  symbol: string;
  factors?: string[];
}
/**
 * Factor calculation response
 */
interface FactorData {
  symbol: string;
  date: string;
  factors: Record<string, number>;
}
/**
 * Factor analysis request
 */
interface FactorAnalyzeRequest {
  factor_name: string;
  start_date?: string;
  end_date?: string;
}
/**
 * Factor analysis response
 */
interface FactorAnalysisResponse {
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
interface ModelPredictRequest {
  symbol: string;
  model_id?: string;
  horizon?: number;
}
/**
 * Model prediction response
 */
interface ModelPrediction {
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
interface DataQualityReportRequest {
  data_type?: 'quote' | 'kline' | 'financial' | 'all';
  days?: number;
}
/**
 * Data quality report response
 */
interface DataQualityReportResponse {
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
interface DataManagerRequest {
  command: 'status' | 'refresh' | 'cleanup' | 'backup';
  data_type?: string;
  symbol?: string;
}
/**
 * Data manager response
 */
interface DataManagerResponse {
  command: string;
  status: string;
  details: Record<string, any>;
  message: string;
}
/**
 * Competition analysis response
 */
interface CompetitionAnalysis {
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
interface CalendarEvent {
  id: number;
  event_type: string;
  event_date: string;
  event_time?: string;
  title: string;
  description?: string;
  symbol?: string;
  market?: string;
  importance?: number;
  status?: string;
  source?: string;
  meta?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}
/**
 * 事件查询参数
 */
interface EventListRequest {
  start?: string;
  end?: string;
  event_type?: string;
  status?: string;
  symbol?: string;
  limit?: number;
}
/**
 * 事件创建/更新请求
 */
interface EventUpsertRequest {
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
interface EventListResponse {
  success: boolean;
  count?: number;
  days?: number;
  events: CalendarEvent[];
}
/**
 * 通用数据源响应（data_provider 多数据源层）
 * 数据源失败时 success=false + error + attempted_sources，工具须降级友好处理
 */
interface ProviderResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  attempted_sources?: string[];
  provider_errors?: Record<string, string>;
  source?: string;
}
/** 个股资金流单日记录 */
interface FundFlowDay {
  date: string;
  closePrice?: number;
  changePct?: number;
  mainNetInflow?: number;
  mainNetInflowRate?: number;
  largeNetInflow?: number;
  bigNetInflow?: number;
  mediumNetInflow?: number;
  smallNetInflow?: number;
  [key: string]: any;
}
/** 两融单日记录 */
interface MarginDay {
  date: string;
  financingBalance?: number;
  financingBuy?: number;
  financingRepay?: number;
  marginBalance?: number;
  marginSell?: number;
  marginRepay?: number;
  totalBalance?: number;
  [key: string]: any;
}
/** 涨停池记录 */
interface LimitUpRecord {
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
interface StockNewsItem {
  新闻标题?: string;
  新闻内容?: string;
  发布时间?: string;
  文章来源?: string;
  新闻链接?: string;
  [key: string]: any;
}
/** 策略进化引擎请求（RFC 012 P1；POST /api/evolution/engine/run） */
interface EvolutionEngineRunRequest {
  strategyId: number;
  symbol: string;
  startDate: string;
  endDate: string;
  mode?: 'full' | 'propose';
  generations?: number;
  initialCash?: number;
}
/** 进化结果中的单个变体提案（proposals[]） */
interface EvolutionEngineProposal {
  variant?: number;
  params?: Record<string, any>;
  estimatedFitness?: number | null;
  metrics?: Record<string, any> | null;
  rationale?: string | null;
  [key: string]: any;
}
/** 一轮进化 run 的结果（dataSource=qv2_real 真回测 / degraded 诚实降级） */
interface EvolutionEngineRunResult {
  success?: boolean;
  runId?: string;
  strategyId?: number;
  symbol?: string;
  mode?: string;
  klineWindow?: string;
  /** qv2_real=qv2 真实回测进化 / degraded=诚实降级（无占位数字） */
  dataSource: 'qv2_real' | 'degraded';
  degradedReason?: string | null;
  totalVariants?: number;
  successVariants?: number;
  degradedVariants?: number;
  bestParams?: Record<string, any> | null;
  bestMetrics?: Record<string, any> | null;
  fitness?: number | null;
  fitnessImprovement?: number | null;
  proposals?: EvolutionEngineProposal[];
  runAt?: string;
  [key: string]: any;
}
/** 单条进化结果行（每 run 一条 = fitness 最优变体行；GET /api/evolution/engine/runs） */
interface EvolutionEngineRunRow {
  runId: string;
  strategyId: number;
  variant?: number;
  variantKey?: string;
  params?: Record<string, any>;
  fitness?: number | null;
  metrics?: Record<string, any> | null;
  degradedReason?: string | null;
  computedAt?: string;
  [key: string]: any;
}
/** GET /api/evolution/engine/runs 响应（data 部分） */
interface EvolutionEngineRunsResponse {
  runs: EvolutionEngineRunRow[];
}
/** 计划新鲜度（机械判定 + 理由） */
interface CorePlanFreshness {
  generated_at: string | null;
  data_date: string | null;
  deadline_hhmm: string;
  age_hours: number | null;
  generated_today: boolean;
  generated_after_deadline: boolean;
  is_stale: boolean;
  stale_reason: string | null;
  [key: string]: any;
}
/** 目标 vs 现状的一行机械差额 */
interface CorePlanDeltaRow {
  symbol: string;
  /** core | growth_sleeve | held_only */
  bucket: string;
  in_plan: boolean;
  plan_close: number | null;
  target_lots: number | null;
  target_shares: number | null;
  held_shares: number;
  shares_available: number;
  delta_shares: number | null;
  /** BUY | SELL | NONE | REVIEW（REVIEW=持仓但不在计划内，**不是**卖出建议） */
  action: string;
  est_amount: number | null;
  [key: string]: any;
}
interface CorePlanDelta {
  account: string;
  cash_available: number | null;
  rows: CorePlanDeltaRow[];
  summary: {
    buy_count: number;
    sell_count: number;
    hold_count: number;
    review_count: number;
    est_buy_amount: number;
    cash_after_full_delta: number | null;
    cash_sufficient: boolean;
    [key: string]: any;
  };
  caveats: string[];
  [key: string]: any;
}
/** GET /api/core-plan 的 data 部分 */
interface CorePlanSnapshot {
  plan_file: string;
  available: boolean;
  unavailable_reason: string | null;
  account: string | null;
  requested_account: string | null;
  account_mismatch: boolean;
  freshness: CorePlanFreshness | null;
  plan: Record<string, any> | null;
  delta: CorePlanDelta | null;
  [key: string]: any;
}
//#endregion
//#region src/client.d.ts
/**
 * QuantsysV2 API Client
 */
declare class QuantsysV2Client {
  private client;
  constructor(config: QuantsysV2ClientConfig);
  /**
   * Parse condition string to conditions array for watch rules (backend schema)
   * Examples:
   *   "price>100" -> [{type: "price_break", params: {direction: "above", price: 100}}]
   *   "price<90" -> [{type: "price_break", params: {direction: "below", price: 90}}]
   *   "change_pct>5" -> [{type: "pct_change", params: {direction: "above", pct: 5}}]
   *   "change_pct<-3" -> [{type: "pct_change", params: {direction: "below", pct: -3}}]
   *
   * Supports:
   *   - price > N / price < N  → price_break (突破/跌破价格)
   *   - change_pct > N / change_pct < N  → pct_change (涨跌幅)
   *   - Operators: >, <, >=, <=
   */
  private parseCondition;
  /**
   * Unwrap response envelope based on endpoint-specific patterns
   */
  private unwrap;
  /**
   * Search stocks
   */
  searchStocks(query: string): Promise<Stock[]>;
  /**
   * Get K-line data
   * Real endpoint: GET /api/stock/{symbol}/klines
   * Response: {symbol, count, klines: [...]} - no success envelope
   */
  getKlines(symbol: string, startDate: string, endDate: string, period?: 'daily' | 'weekly' | 'monthly', limit?: number): Promise<KlineData[]>;
  /**
   * Get K-line data with full envelope（含解析元数据）。
   * 2026-09-11（REQ-733c5e, w-348bf585）：后端 /api/stock/{symbol}/klines 自本日起在响应里附带
   * resolved_kind / resolved_symbol / resolved_name / ambiguity_warning，用于杜绝"指数/股票同码"
   * 静默错配（000905→厦门港务 vs 中证500）。getKlines 只取 klines 数组、会丢这些字段；
   * 需要歧义判定时用本方法拿完整 envelope。
   */
  getKlinesEnvelope(symbol: string, startDate: string, endDate: string, period?: 'daily' | 'weekly' | 'monthly', limit?: number): Promise<any>;
  /**
   * List strategies
   * Real endpoint: GET /api/strategies/list
   * Response: {success, data: {total, page, pageSize, items: [...]}}
   */
  listStrategies(params?: {
    source?: 'builtin' | 'user';
    code_type?: string;
    page?: number;
    pageSize?: number;
  }): Promise<StrategyListResponse>;
  /**
   * Get strategy by ID
   */
  getStrategy(id: number): Promise<Strategy>;
  /**
   * Create strategy
   */
  createStrategy(strategy: Omit<Strategy, 'id'>): Promise<Strategy>;
  /**
   * Update strategy
   */
  updateStrategy(id: number, updates: Partial<Strategy>): Promise<Strategy>;
  /**
   * Delete strategy
   */
  deleteStrategy(id: number): Promise<void>;
  /**
   * Backtest strategy
   */
  backtestStrategy(request: BacktestRequest): Promise<BacktestResult>;
  /**
   * Optimize strategy parameters (backtest matrix)
   * Real endpoint: POST /api/strategies/optimize
   */
  optimizeStrategy(params: {
    strategy_id: number;
    symbol: string;
    start_date: string;
    end_date: string;
    param_ranges: Record<string, number[]>;
    initial_cash?: number;
    sort_by?: 'sharpe_ratio' | 'total_return' | 'max_drawdown' | 'win_rate';
  }): Promise<{
    success: boolean;
    results: Array<{
      params: Record<string, any>;
      sharpeRatio?: number;
      totalReturn?: number;
      maxDrawdown?: number;
      winRate?: number;
      totalTrades?: number;
    }>;
    totalCombinations: number;
    successfulCombinations: number;
  }>;
  /**
   * List pools
   * Real endpoint: GET /api/pools
   * Response: {success, data: [...]}
   */
  listPools(): Promise<Pool[]>;
  /**
   * Get pool by ID
   */
  getPool(id: number): Promise<Pool>;
  /**
   * Create pool（对齐后端 POST /api/pools 契约：pool_type 必填）
   * pool_type: static（手工成员）/ dynamic（filter_template 驱动，refresh 时重算）
   * category: 业务分类（如 板块共振），与 pool_type 正交
   * filter_template: 动态池筛选规则 {conditions:[...], top_n?, sort_by?, min_score?...}（经 validate_filter 校验）
   */
  createPool(pool: {
    name: string;
    pool_type: string;
    category?: string | null;
    description?: string;
    symbols?: string[];
    filter_template?: Record<string, any>;
    refresh_interval?: string | null;
  }): Promise<Pool>;
  /**
   * Update pool（name/symbols/description 覆盖更新——symbols 为整表替换，增删成员请用 addPoolMembers/removePoolMembers）
   */
  updatePool(id: number, updates: Partial<Pool>): Promise<Pool>;
  /**
   * Delete pool
   */
  deletePool(id: number): Promise<void>;
  /**
   * Get pool members —— 后端无 GET /api/pools/{id}/members 路由（2026-09-05 核对，仅
   * PUT/POST/DELETE members 三种），成员明细随池对象（getPool/create/update 响应）的
   * symbols/members 字段返回，故该方法移除，勿再调用。
   */
  /**
   * Add members to pool（批量，对齐后端 POST /api/pools/{id}/members：body.symbols 数组）
   */
  addPoolMembers(poolId: number, params: {
    symbols: string[];
    description?: string;
    buy_point?: number;
    sell_point?: number;
    tags?: string[];
  }): Promise<any>;
  /**
   * Remove members from pool（批量，对齐后端 DELETE /api/pools/{id}/members：body.symbols 数组）
   */
  removePoolMembers(poolId: number, symbols: string[]): Promise<any>;
  /**
   * Update member metadata（对齐后端 PUT /api/pools/{id}/members/{symbol}：description/buy_point/sell_point/tags）
   */
  updatePoolMember(poolId: number, symbol: string, meta: {
    description?: string;
    buy_point?: number;
    sell_point?: number;
    tags?: string[];
  }): Promise<any>;
  /**
   * Refresh pool（重算动态池成员 / 同步静态池展示计数）
   */
  refreshPool(poolId: number): Promise<Pool>;
  /**
   * Sync stock names（把池内符号补充为 {symbol, name} 展示形态）
   */
  syncStockNames(poolId: number): Promise<Pool>;
  /**
   * Validate pool（对池成员跑策略回测校验，需 strategy_ids）
   */
  validatePool(poolId: number, params: {
    strategy_ids?: number[];
    start_date?: string;
    end_date?: string;
  }): Promise<any>;
  /**
   * Scan-and-create pool（扫描筛选后自动建池，对齐后端 POST /api/pools/scan-and-create）
   */
  scanAndCreatePool(params: {
    name: string;
    pool_type: string;
    filter_template: Record<string, any>;
    refresh_interval?: string | null;
    description?: string;
    category?: string | null;
  }): Promise<Pool>;
  /**
   * List signals
   */
  listSignals(params?: {
    symbol?: string;
    signal_type?: 'buy' | 'sell';
    start_date?: string;
    end_date?: string;
  }): Promise<Signal[]>;
  /**
   * Get real-time quote
   * Real endpoint: GET /api/stock/{symbol}/quote?source=auto
   * Response: {success, data: {symbol, name, price, open, high, low, prevClose, volume, amount, change, changePct, source, timestamp}}
   */
  getQuote(symbol: string, source?: 'realtime' | 'db' | 'auto'): Promise<QuoteData>;
  /**
   * Get market style
   * Real endpoint: GET /api/market/style
   * Real response data: {style, confidence, scores, indicators, recommendedFactors, detectionDate}
   */
  getMarketStyle(): Promise<{
    style: string;
    confidence: number;
    scores: Record<string, number>;
    indicators: Record<string, number>;
    recommendedFactors: string[];
    detectionDate: string;
  }>;
  /**
   * Get macroeconomic data (GDP/CPI/PMI)
   * Real endpoint: GET /api/market/macro
   * Response: {success, data: {gdp: [...], cpi: [...], pmi: [...], updateTime}}
   */
  getMacroData(): Promise<MacroData>;
  /**
   * Get north-bound capital flow
   * Real endpoint: GET /api/market/north-flow?start_date=&end_date=
   * Response: {success, data: [{tradeDate, netFlow, shNetFlow, szNetFlow}]}
   * Note: upstream data source is slow (~50s cold); uses an extended timeout.
   */
  getNorthFlow(startDate?: string, endDate?: string): Promise<NorthFlowDay[]>;
  /**
   * Get market sentiment
   * Real endpoint: GET /api/market/sentiment
   * Response: {success, data: {sentimentScore, sentimentLevel, fearGreedIndex, indicators, marketPhase, recommendation, ...}}
   */
  getMarketSentiment(): Promise<MarketSentiment>;
  /**
   * Get platform status (for quantsys_v2_status tool)
   */
  getPlatformStatus(): Promise<{
    status: string;
    holdings_count: number;
    balance: any;
    recent_signals: number;
    db_connected: boolean;
    model_loaded: boolean;
    recent_report: boolean;
    timestamp: string;
  }>;
  /**
   * Get chip distribution
   */
  getChipDistribution(symbol: string): Promise<{
    symbol: string;
    date: string;
    profit_ratio: number;
    avg_cost: number;
    peak_price: number;
    concentration: number;
    cost_ranges: {
      p70_low: number;
      p70_high: number;
      p90_low: number;
      p90_high: number;
    };
  }>;
  /**
   * ZigZag 波段分析（买卖点识别）
   * Real endpoint: POST /api/analysis/swing-points
   * Body: { symbol, start_date?, end_date?, min_change? }
   * 响应为 camelCase（后端 convert_keys_to_camel）。
   * 2026-09-01 新增：后端路由原未注入 kline_repo 必 500，已修复。
   */
  analyzeSwingPoints(params: {
    symbol: string;
    startDate?: string;
    endDate?: string;
    minChange?: number;
  }): Promise<SwingPointAnalysis>;
  /**
   * PE 历史分位
   * Real endpoint: GET /api/stock/{symbol}/pe-percentile
   * 响应 camelCase：currentPe/percentile/minPe/maxPe/meanPe/medianPe/dataPoints/years/interpretation
   */
  getPePercentile(symbol: string): Promise<{
    symbol: string;
    name?: string;
    currentPe: number;
    currentPrice?: number;
    percentile: number;
    minPe?: number;
    maxPe?: number;
    meanPe?: number;
    medianPe?: number;
    dataPoints?: number;
    years?: number;
    interpretation?: string;
  }>;
  /**
   * 个股分红历史
   * Real endpoint: GET /api/provider/dividend/{symbol}?years=N
   * ⚠️ 依赖 akshare，夜间/维护时段可能 All providers failed（调用方需容忍）
   */
  getDividends(symbol: string, years?: number): Promise<any>;
  /**
   * 高股息筛选
   * Real endpoint: GET /api/provider/screen-high-dividend?min_yield=3&min_years=5
   * ⚠️ 同样依赖 akshare，夜间可能不可用
   */
  screenHighDividend(params?: {
    minYield?: number;
    minYears?: number;
  }): Promise<any>;
  /**
   * Get competition analysis
   */
  getCompetitionAnalysis(symbol: string, includeFinancial?: boolean): Promise<CompetitionAnalysis>;
  /**
   * Get financial data
   * Response: existing .data.data || .data fallback works
   */
  getFinancialData(symbol: string, params?: {
    statement_type?: 'income' | 'balance' | 'cash_flow' | 'all';
    periods?: number;
    source?: 'auto' | 'fresh' | 'cache_only';
  }): Promise<FinancialData>;
  /**
   * Get financial statements (provider sina-statements, 真实报表数据)
   * Real endpoint: GET /api/provider/financial/{symbol}/sina-statements
   * 2026-08-30 新增：/api/v2/stock/{symbol}/financials 的 sina-web 指标源已失效
   * （全部返回 null），改用 DataProviderManager 的原始报表接口兜底。
   * 返回 { data_type, data: { income, balance, cashflow } }
   */
  getFinancialStatements(symbol: string): Promise<any>;
  /**
   * List watch rules
   * Real endpoint: GET /api/watch/rules
   * Response: {success, rules: [...]} - key is 'rules' not 'data'
   */
  listWatchRules(account?: string): Promise<WatchRule[]>;
  /**
   * 盯盘触发记录（2026-09-11，w-c8cae280）
   *
   * 为什么需要：后端 /api/watch/rules 不返回 triggered_count，watch_list 工具层
   * 曾用 `?? 0` 兜底 → 53 条规则全部显示「从未触发」，而同一时刻 watch_triggers
   * 里规则 #135 当日已触发 4 次。这个假 0 直接造成「盯盘引擎失效」的误判。
   * 本方法提供真实计数的数据来源。
   * Response: {success, data: {triggers: [...]}}
   */
  listWatchTriggers(symbol?: string, limit?: number): Promise<any[]>;
  /**
   * 待办列表
   * Real endpoint: GET /api/watch/todos
   * Response: {success, data: {items: [...], total: n}}
   * terminal 不传 = 只返回未收敛（闭环工作队列的默认视图）
   */
  listWatchTodos(params?: WatchTodoListParams): Promise<WatchTodo[]>;
  /**
   * 认领待办（L1→L2；仅未终态行生效）
   * Real endpoint: POST /api/watch/todos/{id}/claim
   * 失败：404 watch_todo_not_found / 409 watch_todo_already_closed
   */
  claimWatchTodo(todoId: number, ownerRef: string): Promise<WatchTodo>;
  /**
   * 收敛待办（终态校验在服务端）
   * Real endpoint: POST /api/watch/todos/{id}/close
   * Response: {success, data: {todo, receipt}}
   * 失败：400 watch_todo_invalid_terminal / watch_todo_missing_next_condition /
   *       watch_todo_missing_audit（L3 + trade|rule_change 缺 decision_audit_id）
   */
  closeWatchTodo(todoId: number, request: WatchTodoCloseRequest): Promise<any>;
  /**
   * Get portfolio positions
   * 2026-08-31 修复：改调 /api/simulation/accounts/{account}（get_account_status），
   * 该接口每次请求实时拉行情刷新持仓价格并返回 price_stale / price_updated_at；
   * 原 /api/portfolio/positions 直读数据库 current_price 快照（陈旧价，曾导致 8/28 旧价）。
   * 响应为 snake_case，映射为工具层期望的 camelCase Position[]。
   */
  getPositions(accountName?: string): Promise<Position[]>;
  /**
   * Get portfolio summary
   * 2026-08-31 修复：同样改调 /api/simulation/accounts/{account}（实时刷新），
   * 原 /api/portfolio/summary 直读数据库快照（account.lastUpdated 曾停更在 8/28）。
   */
  getPortfolioSummary(accountName?: string): Promise<PortfolioSummary>;
  /**
   * 将 simulation 账户接口的 snake_case 持仓项映射为 Position（camelCase）
   */
  private mapPosition;
  /**
   * 读取投资脑 core 建仓计划（**只读**）。
   *
   * 返回 {available, unavailable_reason, freshness, plan, delta}：
   *   · plan      计划全文（与 config/core_plan.json 结构一致，**蛇形 key 原样返回**）
   *   · freshness 新鲜度（generated_at/data_date/is_stale/stale_reason）——
   *               直读文件时**看不出**计划陈不陈，周五的计划周一读出来一模一样
   *   · delta     目标组合 vs 当前持仓的机械差额（含 shares_available 供 T+1 校验）
   *
   * ⚠️ delta 不是委托清单：价格是计划时收盘价、未做 regime/止损复检、未做分批节奏。
   *    下单前仍须走 R-001/R-002。详见返回的 delta.caveats。
   * ⚠️ 不触发重新生成（生成参数集已审批）；补跑用 POST /api/scheduler/tasks/337/trigger。
   */
  getCorePlan(account?: string): Promise<CorePlanSnapshot>;
  listPlans(account?: string, status?: string): Promise<any>;
  getPlan(planId: number): Promise<any>;
  createPlan(payload: Record<string, any>): Promise<any>;
  patchPlan(planId: number, payload: Record<string, any>): Promise<any>;
  applyPlan(planId: number, payload: Record<string, any>): Promise<any>;
  activatePlan(planId: number, payload?: Record<string, any>): Promise<any>;
  pausePlan(planId: number, payload?: Record<string, any>): Promise<any>;
  resumePlan(planId: number, payload?: Record<string, any>): Promise<any>;
  closePlan(planId: number, payload?: Record<string, any>): Promise<any>;
  compilePlanPreview(planId: number): Promise<any>;
  plansToday(account?: string): Promise<any>;
  planStats(planId: number): Promise<any>;
  recordPlanReflection(planId: number, payload: Record<string, any>): Promise<any>;
  listPlanReflections(planId: number): Promise<any>;
  blockedSignalStats(sinceDays?: number, horizon?: number): Promise<any>;
  /**
   * Get evolution leaderboard
   * Real endpoint: GET /api/evolution/leaderboard
   * Response: {success, data: {windowEnd, windowDays, ranking: [...]}}
   */
  getEvolutionLeaderboard(): Promise<EvolutionLeaderboard>;
  /**
   * Get evolution decision scores
   * Real endpoint: GET /api/evolution/decision-scores
   * Response: {success, data: {total, items: [...]}}
   */
  getEvolutionDecisionScores(): Promise<EvolutionDecisionScores>;
  /**
   * Execute a trade (virtual account)
   * Real endpoint: POST /api/orders/create
   */
  /**
   * Execute a trade（虚拟账户立即成交）
   * 2026-08-25 修复：改走 simulation 交易端点（/api/orders/create 属于订单管理系统，
   * 只建单不成交、不动虚拟账户持仓——卖出校验也查的是废弃 holdings 表）。
   * 正确端点：POST /api/simulation/accounts/{account}/trade（立即成交并更新持仓）。
   */
  executeTrade(params: TradeRequest): Promise<TradeResponse>;
  /**
   * 挂单列表（盘前挂单）
   * Real endpoint: GET /api/simulation/accounts/{account}/pending-orders?status=pending|all
   */
  /**
   * 账户发现（2026-09-13 w-c8cae280）：列出账户 + 摘要。
   * 后端 GET /api/simulation/accounts?status=active → {accounts:[{account_name, display_name,
   * strategy_name, account_type, status, cash_available, cash_frozen, position_value,
   * total_value, cumulative_return, positions_count}], total}
   * 用途：让 agent **不必记住/写死账户名**——先查有哪些账户、哪个是本实例账户。
   */
  listAccounts(status?: 'active' | 'all'): Promise<any[]>;
  listPendingOrders(accountName?: string, status?: 'pending' | 'all'): Promise<any[]>;
  /**
   * 取消挂单（仅 pending 状态可取消）
   * Real endpoint: POST /api/simulation/accounts/{account}/pending-orders/{orderId}/cancel
   */
  cancelPendingOrder(accountName: string, orderId: number): Promise<any>;
  /**
   * 记录决策
   * Real endpoint: POST /api/decisions/record
   * Body: { decision_type, reasoning, context?, parameters?, related_entity_type?, related_entity_id?, session_key? }
   */
  recordDecision(params: {
    decision_type: string;
    reasoning: string;
    context?: Record<string, any>;
    parameters?: Record<string, any>;
    related_entity_type?: string;
    related_entity_id?: string;
    session_key?: string;
  }): Promise<any>;
  /**
   * 决策历史
   * Real endpoint: GET /api/decisions/history
   */
  getDecisionHistory(params?: {
    entity_type?: string;
    entity_id?: string;
    decision_type?: string;
    limit?: number;
  }): Promise<any[]>;
  /**
   * 待评估决策（创建超过 days 天仍 pending）
   * Real endpoint: GET /api/decisions/pending
   */
  getPendingDecisions(days?: number): Promise<any[]>;
  /**
   * 触发决策评估（单笔或批量）
   * Real endpoint: POST /api/decisions/evaluate
   * Body: { decision_id? } 或 { days? }（批量）
   */
  evaluateDecisions(params?: {
    decision_id?: string;
    days?: number;
  }): Promise<any>;
  /**
   * 决策报告（按关联实体聚合统计）
   * Real endpoint: GET /api/decisions/report
   */
  getDecisionReport(entityType: string, entityId: string): Promise<any>;
  /**
   * ML 模型批量预测（上涨概率）
   * Real endpoint: POST /api/ml/predict  Body: { symbols: string[], model_type?, version? }
   * 注意：后端带上线门禁（test_accuracy<0.50 拒服，0.50~0.55 degraded 警告）；
   * 已知问题：DB 因子覆盖不足时输出恒等概率 0.4659（缺失补零），须关注 model_gate.level。
   */
  mlPredict(params: {
    symbols: string[];
    model_type?: string;
    version?: string;
  }): Promise<{
    predictions: Array<{
      symbol: string;
      date: string;
      predicted_class: number;
      probability: number;
      confidence: string;
    }>;
    model_gate?: {
      passed: boolean;
      level: string;
      test_accuracy?: number;
      warning?: string;
    };
  }>;
  /**
   * Get trade history
   * Real endpoint: GET /api/trades/list
   */
  getTradeHistory(params?: {
    account_name?: string;
    order_id?: string;
    symbol?: string;
    direction?: string;
    page?: number;
    pageSize?: number;
  }): Promise<TradeHistoryResponse>;
  /**
   * Execute algorithmic order (TWAP/VWAP)
   * Real endpoint: POST /api/orders/algo-execute
   */
  executeAlgo(params: AlgoExecuteRequest): Promise<AlgoExecuteResponse>;
  /**
   * Verify trades (reconciliation)
   * Real endpoint: POST /api/risk/trade-verify
   */
  verifyTrades(params?: {
    account_name?: string;
    date?: string;
  }): Promise<TradeVerifyResponse>;
  /**
   * Manage watch rules (create/enable/disable/delete)
   * Real endpoints:
   *   POST   /api/watch/rules           (create)
   *   PATCH  /api/watch/rules/{id}      (enable/disable - update enabled field)
   *   DELETE /api/watch/rules/{id}      (delete)
   */
  manageWatchRule(params: WatchRuleManageRequest): Promise<any>;
  /**
   * Get market alerts
   * Real endpoint: GET /api/alerts/check
   */
  getAlerts(params?: {
    level?: string;
    limit?: number;
  }): Promise<Alert[]>;
  /**
   * Get sector analysis
   * Real endpoint: GET /api/market/sectors
   */
  getSectorAnalysis(params?: {
    sector?: string;
    days?: number;
    date?: string;
    window?: number;
    limit?: number;
  }): Promise<SectorAnalysisResponse>;
  /**
   * Get sector constituent stocks（板块成分股，M2-1 主线→标的映射数据源）
   * Real endpoint: GET /api/market/sector/{sector:path}（sector 传中文板块名，如"白银"）
   * Response data: {sector, sectorCode, stocks: [{symbol, name, pe, marketCapBillion}], count}
   */
  getSectorStocks(sector: string): Promise<{
    sector: string;
    sectorCode?: string;
    stocks: Array<{
      symbol: string;
      name: string;
      pe?: number;
      marketCapBillion?: number;
    }>;
    count: number;
  }>;
  /**
   * Risk control: position_size / stop_loss / portfolio_risk
   * Dispatches to different endpoints based on command.
   */
  riskControl(params: RiskControlRequest): Promise<any>;
  /**
   * Calculate risk metrics
   * Real endpoint: POST /api/risk/metrics
   */
  getRiskMetrics(params?: {
    account_name?: string;
    days?: number;
    returns?: number[];
    benchmark_returns?: number[];
    risk_free_rate?: number;
  }): Promise<RiskMetrics>;
  /**
   * 组合级回撤熔断状态读写（M4 硬拦截数据源，2026-09-10）
   * Real endpoints: GET/POST /api/risk/circuit-breaker
   */
  getCircuitBreaker(account_name?: string): Promise<any>;
  setCircuitBreaker(params: {
    account_name?: string;
    active: boolean;
    triggered_drawdown?: number;
    actions_taken?: string[];
    unblock_condition?: string;
    note?: string;
  }): Promise<any>;
  /**
   * Barra risk decomposition
   * Real endpoint: POST /api/factor-models/barra/calculate
   */
  getBarraDecomposition(params?: {
    symbols?: string[];
    start_date?: string;
    end_date?: string;
    weights?: number[];
    account_name?: string;
  }): Promise<BarraDecompositionResponse>;
  /**
   * Generate trading signals
   * Real endpoint: POST /api/signals/scan
   */
  generateSignals(params: SignalGenerateRequest): Promise<Signal[]>;
  /**
   * Scan market opportunities
   * Real endpoint: POST /api/signals/scan
   */
  scanOpportunities(params?: OpportunityScanRequest): Promise<Opportunity[]>;
  /**
   * Screen stocks by filters
   * Real endpoint: GET /api/stocks/screen
   */
  screenStocks(params?: ScreenRequest): Promise<ScreenResponse>;
  /**
   * Generate rotation proposal
   * Real endpoint: GET /api/agent/rotation/proposal
   */
  generateRotationProposal(params?: RotationProposalRequest): Promise<RotationProposal>;
  /**
   * Simulate rotation proposal
   * Real endpoint: POST /api/agent/rotation/simulate
   */
  simulateRotation(params: RotationSimulateRequest): Promise<RotationSimulateResponse>;
  /**
   * Execute rotation proposal
   * Real endpoint: POST /api/agent/rotation/execute
   */
  executeRotation(params: RotationExecuteRequest): Promise<RotationExecuteResponse>;
  /**
   * Calculate stock factors
   * Real endpoint: GET /api/stock/{symbol}/factors
   */
  calculateFactors(params: FactorCalculateRequest): Promise<FactorData>;
  /**
   * Analyze factor effectiveness
   * Real endpoint: POST /api/portfolio/factor-analyze
   */
  analyzeFactor(params: FactorAnalyzeRequest): Promise<FactorAnalysisResponse>;
  /**
   * 解析 agent 侧 model_id（如 "lightgbm_20260820_195134"）为后端所需的
   * model_type + version。裸类型名（如 "lightgbm"、"lgbm"）视为 latest。
   * 无法识别时抛错——禁止静默回退默认模型（RFC003-P3 验收发现）。
   */
  private parseModelId;
  /**
   * 列出已注册模型
   * Real endpoint: GET /api/ml/models
   */
  listModels(params?: {
    model_type?: string;
    status?: string;
    limit?: number;
  }): Promise<any>;
  /**
   * 选择默认模型：最新一个通过上线门禁（roc_auc >= 0.55, status=ready）的模型。
   * 无达标模型时返回 null，由后端默认路径兜底（RFC003-P3 门禁规则）。
   */
  private resolveGatedDefaultModel;
  /**
   * Predict with ML model
   * Real endpoint: POST /api/ml/predict
   */
  predictWithModel(params: ModelPredictRequest): Promise<ModelPrediction>;
  /**
   * Get data quality report
   * Real endpoint: GET /api/data/quality-report
   */
  getDataQualityReport(params?: DataQualityReportRequest): Promise<DataQualityReportResponse>;
  /**
   * Data manager operations (status/refresh/cleanup/backup)
   * Real endpoint: POST /api/data/update
   */
  dataManager(params: DataManagerRequest): Promise<DataManagerResponse>;
  /**
   * Sync daily K-line data
   * Real endpoint: POST /api/data/sync-daily-klines
   */
  syncDailyKlines(params?: {
    date?: string;
    symbols?: string[];
    force?: boolean;
  }): Promise<{
    success: boolean;
    sync_date: string;
    success_count: number;
    failed_count: number;
    total_stocks: number;
    total_rows: number;
    elapsed_time: number;
    message: string;
    failed_symbols?: string[];
  }>;
  /**
   * Get data sync status
   * Real endpoint: GET /api/data/sync-status
   */
  getDataSyncStatus(): Promise<{
    status: string;
    latest_date: string | null;
    latest_count?: number;
    active_stocks_count?: number;
    coverage?: string;
    message: string;
  }>;
  /**
   * Train ML model
   * Real endpoint: POST /api/ml/train
   */
  trainModel(params: {
    model_type: string;
    name?: string;
    symbols?: string[];
    features?: string[];
    target?: string;
  }): Promise<any>;
  /**
   * Evaluate ML model
   * Real endpoint: GET /api/ml/model/evaluate（后端参数为 model_type + version）
   * 注意：后端不支持按 test_period 重估，返回的是训练时落库的指标；
   * 未知 model_id 会明确报错（success=false），不再静默回退默认模型。
   */
  evaluateModel(params: {
    model_id: string;
    test_period?: string;
  }): Promise<any>;
  /**
   * Opponent behavior analysis
   * Real endpoint: GET /api/game/market/opponent-behavior
   */
  getOpponentBehavior(params?: {
    symbol?: string;
    focus?: string;
  }): Promise<any>;
  /**
   * Pool battlefield assessment
   * Real endpoint: GET /api/game/pools/{pool_id}/battlefield-assessment
   */
  getPoolBattlefield(params: {
    pool_id: number;
  }): Promise<any>;
  /**
   * Manipulation detection
   * Real endpoint: GET /api/game/market/manipulation-detect
   */
  detectManipulation(params: {
    symbol: string;
    days?: number;
  }): Promise<any>;
  /**
   * Retail panic index (M7-2)
   * Real endpoint: GET /api/market/perception/panic-index
   */
  getRetailPanicIndex(params?: {
    trade_date?: string;
    days?: number;
  }): Promise<any>;
  /**
   * Record a buy signal
   * Real endpoint: POST /api/signals/track
   * Body: {signal_date, symbol, grade, source, price, reason?}
   */
  recordSignal(params: {
    signal_date: string;
    symbol: string;
    grade: 'A' | 'B' | 'C';
    source: string;
    price: number;
    reason?: string;
  }): Promise<{
    signalId: number;
    message: string;
  }>;
  /**
   * Update signal performance (backfill 5/10/20-day returns)
   * Real endpoint: PUT /api/signals/track/update
   * Body: {signal_date?, lookback_days?}
   */
  updateSignalPerformance(params?: {
    signal_date?: string;
    lookback_days?: number;
  }): Promise<{
    updated: number;
    details: Record<string, number>;
  }>;
  /**
   * Get signal statistics report
   * Real endpoint: GET /api/signals/track/report?start_date=&end_date=&grade=&source=
   */
  getSignalReport(params?: {
    start_date?: string;
    end_date?: string;
    grade?: 'A' | 'B' | 'C';
    source?: string;
  }): Promise<{
    total: number;
    dateRange: {
      start: string;
      end: string;
    };
    byGrade: Record<string, any>;
    bySource: Record<string, any>;
    recentSignals: any[];
  }>;
  /**
   * 生成周报并推送到飞书（M6-2）
   */
  pushWeeklyReport(params?: {
    week_start?: string;
    week_end?: string;
    feishu_webhook?: string;
  }): Promise<{
    success: boolean;
    report: any;
    markdown: string;
    push_result: {
      success: boolean;
      message?: string;
      error?: string;
    } | null;
  }>;
  /**
   * 获取最新周报（M6-2）
   */
  getLatestWeeklyReport(format?: 'json' | 'markdown'): Promise<any>;
  /**
   * 查未来 N 天待处理事件（每日检查任务核心调用）
   */
  getUpcomingEvents(days?: number): Promise<EventListResponse>;
  /**
   * 范围查询事件日历（按日期区间/类型/状态/标的过滤）
   */
  listEvents(params?: EventListRequest): Promise<EventListResponse>;
  /**
   * 按 ID 查单个事件
   */
  getEvent(id: number): Promise<CalendarEvent>;
  /**
   * 创建/更新事件（幂等 upsert：按类型+日期+标题去重）
   */
  upsertEvent(event: EventUpsertRequest): Promise<CalendarEvent>;
  /**
   * 更新事件（状态/结果/影响评估）
   */
  updateEvent(id: number, updates: Partial<EventUpsertRequest>): Promise<CalendarEvent>;
  /**
   * 标记事件状态（状态机：pending→notified→collected→reviewed/skipped）
   */
  markEventStatus(id: number, status: string, metaPatch?: Record<string, any>): Promise<CalendarEvent>;
  /**
   * 删除事件
   */
  deleteEvent(id: number): Promise<{
    success: boolean;
    deleted: number;
  }>;
  /** 事件流（按 scope/type/日期过滤） */
  getEventsFeed(params?: {
    scope?: string;
    type?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
  }): Promise<ProviderResponse>;
  /** 执行质量报表：决策价 vs 成交价的滑点（2026-09-13 w-a9ec14d7，M5 闭环） */
  getSlippageReport(accountName?: string, params?: {
    days?: number;
    symbol?: string;
  }): Promise<ProviderResponse>;
  /** 事件 → 盯盘规则建议（前瞻日历；2026-09-13 w-a9ec14d7 补上消费端） */
  getEventWatchSuggestions(params?: {
    symbols?: string;
    days?: number;
  }): Promise<ProviderResponse>;
  /** 把任务派给处置 agent（2026-10-20）：统一信封 + 交付要求 + 留痕；返回 wake 状态 */
  dispatchAgentTask(params: {
    title: string;
    instruction: string;
    event?: string;
    target?: string;
    requires_report?: boolean;
    urgency?: 'normal' | 'high' | 'critical';
  }): Promise<ProviderResponse>;
  /** 条件入参契约（2026-10-20 框架适配）：全部条件类型参数说明/单位/示例 + market_gate 规格 */
  getWatchConditionSchema(): Promise<ProviderResponse>;
  /** 单标的盯盘简报（2026-10-20）：行情+成本+规则距离+未决触发+近48h消息命中，一张卡 */
  getWatchBrief(symbol: string): Promise<ProviderResponse>;
  /** 盯盘触发增量查询（2026-10-20）：since 之后的新触发（agent 轮询「有什么新信号」） */
  getWatchTriggers(params?: {
    symbol?: string;
    disposition?: string;
    since?: string;
    limit?: number;
  }): Promise<ProviderResponse>;
  /** 处置触发（2026-10-20 框架适配）：handled/ignored 收敛未决触发——agent 的处置动作 */
  resolveWatchTrigger(triggerId: number, body: {
    disposition: string;
    reason?: string;
  }): Promise<ProviderResponse>;
  /** 个股事件（公告/解禁/财报/股东会/减持…）——买入前排雷 */
  getSymbolEvents(symbol: string, params?: {
    days?: number;
  }): Promise<ProviderResponse>;
  /** 分钟线（多源故障转移：腾讯/东财/新浪 + 本地 DB 兜底） */
  getMinuteKlines(symbol: string, params?: {
    period?: string;
    date?: string;
    limit?: number;
  }): Promise<ProviderResponse>;
  /** 交易状态（ST/停牌/涨跌停/可交易性——下单前硬校验） */
  getTradingStatus(symbol: string): Promise<ProviderResponse>;
  /** 执行预估（参与率/滑点/冲击成本，供 R-003 拆单参考） */
  estimateExecution(payload: {
    symbol: string;
    side: 'BUY' | 'SELL';
    quantity: number;
    price?: number;
  }): Promise<ProviderResponse>;
  /** 个股资金流（主力/大单/中单/小单净流入） */
  getStockFundFlow(symbol: string, days?: number): Promise<ProviderResponse>;
  /** 板块资金流 */
  getSectorFlow(): Promise<ProviderResponse>;
  /** 个股融资融券（杠杆资金） */
  getStockMargin(symbol: string, days?: number): Promise<ProviderResponse>;
  /** 产业链清单 */
  getIndustryChains(): Promise<ProviderResponse>;
  /** 单条产业链全貌（按环节分组的成员 + evidence/confidence） */
  getIndustryChain(name: string): Promise<ProviderResponse>;
  /** 个股所属产业链与环节（链式扫描的关键查询） */
  getStockChain(symbol: string): Promise<ProviderResponse>;
  /** 链式扫描：按环节分组 + 可选挂实时行情 */
  scanIndustryChain(name: string, params?: {
    include_quotes?: boolean;
  }): Promise<ProviderResponse>;
  /** 指数成分股（如 000300 → 沪深300 成分代码列表） */
  getIndexConstituents(symbol: string): Promise<ProviderResponse>;
  /**
   * 记忆召回审计统计（quantsys-v2 /api/memory/recall-audit/stats）
   * 注意：该端点返回**裸 JSON**（非 {success,data} 包裹），此处不做 unwrap。
   */
  getRecallAuditStats(params?: {
    date_from?: string;
    date_to?: string;
  }): Promise<any>;
  /**
   * 记忆召回审计明细（quantsys-v2 /api/memory/recall-audit）
   * 返回 { items: [...], ... }，同样为裸 JSON。
   */
  getRecallAudit(params?: {
    flow?: string;
    gate_result?: string;
    suppressed_only?: boolean;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  }): Promise<any>;
  /** 龙虎榜：某日上榜记录 */
  getLhbDaily(date: string): Promise<ProviderResponse>;
  /** 龙虎榜：个股上榜明细 */
  getLhbDetail(symbol: string): Promise<ProviderResponse>;
  /** 涨停池（某日涨停股+连板/封单） */
  getLimitUpPool(date: string): Promise<ProviderResponse>;
  /** 个股公告 */
  getStockAnnouncements(symbol: string): Promise<ProviderResponse>;
  /** 个股新闻 */
  getStockNews(symbol: string): Promise<ProviderResponse>;
  /** 内部人交易（高管增减持） */
  getInsiderTrades(symbol: string): Promise<ProviderResponse>;
  /** 交易日历
   *
   * 2026-09-10 修复（investor / w-8f2c4cc5）：必须传日期窗口——不传时后端 Provider
   * 收到空区间返回 data:[]，调用方（trading_calendar 工具）会静默降级成"周末排除法"，
   * 实测把 2026-10-01 国庆误判为交易日。缺省时后端已给 ±1 年窗口，显式传更可控。
   */
  getTradingCalendar(startDate?: string, endDate?: string): Promise<ProviderResponse>;
  /**
   * 跑一轮真实回测进化（参数网格 → 逐变体回测 → 同批 fitness 归一 → 落库）
   * Real endpoint: POST /api/evolution/engine/run
   * 请求/响应均为 camelCase；dataSource=qv2_real（真回测）| degraded（诚实降级，无占位数字）
   */
  evolutionRunStrategy(request: EvolutionEngineRunRequest): Promise<EvolutionEngineRunResult>;
  /**
   * 策略最近进化结果行（每 run 一条 = fitness 最优变体行；leaderboard 数据源）
   * Real endpoint: GET /api/evolution/engine/runs?strategy_id=&limit=
   */
  getStrategyEvolutionRuns(strategyId: number, limit?: number): Promise<EvolutionEngineRunsResponse>;
}
//#endregion
//#region src/manipulation.d.ts
interface ManipulationDetectResult {
  symbol: string;
  manipulation_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'unknown';
  recommendation: 'normal' | 'watch' | 'avoid' | 'opportunity';
  detected_patterns: string[];
  evidence: string[];
  window_days: number;
  note?: string;
}
/**
 * 检测个股操纵嫌疑（拉高出货、对倒交易、诱多诱空等）
 *
 * 基于 K 线行为特征计算嫌疑评分（0-100），越高嫌疑越大。
 *
 * @param qv2 - QuantsysV2Client 实例
 * @param symbol - 股票代码（如 600519）
 * @param days - 分析窗口（默认 30 天）
 * @returns 嫌疑评分、检测模式、证据列表、操作建议
 */
declare function detectManipulation(qv2: QuantsysV2Client, symbol: string, days?: number): Promise<ManipulationDetectResult>;
//#endregion
export { Alert, AlgoExecuteRequest, AlgoExecuteResponse, BacktestRequest, BacktestResult, BarraDecompositionResponse, CalendarEvent, CompetitionAnalysis, CorePlanDelta, CorePlanDeltaRow, CorePlanFreshness, CorePlanSnapshot, DataManagerRequest, DataManagerResponse, DataQualityReportRequest, DataQualityReportResponse, EquityPoint, EventListRequest, EventListResponse, EventUpsertRequest, EvolutionDecisionScore, EvolutionDecisionScores, EvolutionEngineProposal, EvolutionEngineRunRequest, EvolutionEngineRunResult, EvolutionEngineRunRow, EvolutionEngineRunsResponse, EvolutionLeaderboard, EvolutionLeaderboardEntry, FactorAnalysisResponse, FactorAnalyzeRequest, FactorCalculateRequest, FactorData, FinancialData, FundFlowDay, KlineData, LimitUpRecord, MacroData, ManipulationDetectResult, MarginDay, MarketSentiment, ModelPredictRequest, ModelPrediction, NorthFlowDay, Opportunity, OpportunityScanRequest, Pool, PoolMember, PortfolioSummary, Position, ProviderResponse, QuantsysV2Client, QuantsysV2ClientConfig, QuoteData, RiskControlRequest, RiskMetrics, RotationExecuteRequest, RotationExecuteResponse, RotationProposal, RotationProposalRequest, RotationSimulateRequest, RotationSimulateResponse, ScreenRequest, ScreenResponse, SectorAnalysisResponse, SectorInfo, Signal, SignalGenerateRequest, SimulationAccountStatus, SimulationPositionItem, Stock, StockNewsItem, Strategy, StrategyListResponse, SwingPoint, SwingPointAnalysis, SwingPointSummary, SwingTrade, Trade, TradeHistoryResponse, TradeRequest, TradeResponse, TradeVerifyResponse, WatchRule, WatchRuleManageRequest, WatchTodo, WatchTodoCloseRequest, WatchTodoListParams, detectManipulation };