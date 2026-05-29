/**
 * QuantV2Client 类型定义
 */

// 财务数据类型
export interface FinancialData {
  success: boolean;
  symbol: string;
  name: string;
  report_date: string;
  income_statement?: {
    revenue: number;
    operating_cost: number;
    gross_profit: number;
    net_profit: number;
    net_profit_attr_parent: number;
    gross_margin: number;
    net_margin: number;
  };
  balance_sheet?: {
    total_assets: number;
    current_assets: number;
    total_liabilities: number;
    current_liabilities: number;
    total_equity: number;
    debt_ratio: number;
    current_ratio: number;
  };
  cash_flow?: {
    operating_cashflow: number;
    investing_cashflow: number;
    financing_cashflow: number;
    net_cashflow: number;
  };
  metrics?: {
    pe_ratio: number;
    pb_ratio: number;
    roe: number;
    roa: number;
    eps: number;
    bvps: number;
  };
}

// 因子计算类型
export interface FactorComputeParams {
  symbols: string[];
  factors?: string[];
  date?: string;
}

export interface FactorResultItem {
  symbol: string;
  date: string;
  factor_count: number;
  factors: Record<string, number | null>;
  error?: string;
}

export interface FactorResult {
  success: boolean;
  results: FactorResultItem[];
  count: number;
}

// 因子分析类型
export interface FactorAnalyzeParams {
  factors: string[];
  start_date: string;
  end_date: string;
  universe?: string[];
}

export interface FactorAnalysis {
  success: boolean;
  factors: FactorMetrics[];
  error?: string;
}

export interface FactorMetrics {
  name: string;
  ic_daily: number;
  ic_weekly: number;
  ic_monthly: number;
  coverage: number;
  stability: number;
  decay_curve: number[];
}

// 机会扫描类型
export interface OpportunityScanParams {
  symbols?: string[];
  conditions?: string[];
  limit?: number;
  sectorFilter?: {
    enabled: boolean;
    topN?: number;
    minSectorScore?: number;
    excludeSectors?: string[];
    market?: 'A' | 'HK';
  };
}

export interface Opportunity {
  symbol: string;
  name: string;
  score: number;
  technical_score: number;
  fundamental_score: number;
  capital_score: number;
  confidence: number;
  risk_level: string;
  signal_type: string;
  reasons?: string[];
  timestamp: string;
  industry?: string;
  sector_score?: number;
  sector_rank?: number;
}

// Alias for formatter compatibility
export type OpportunityResult = Opportunity;

// 算法交易类型
export interface AlgoExecuteParams {
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  algo: 'TWAP' | 'VWAP';
  duration_minutes?: number;
  start_time?: string;
}

export interface AlgoOrder {
  success: boolean;
  data: {
    orderId: string;
    symbol: string;
    side: 'buy' | 'sell';
    algo: 'TWAP' | 'VWAP';
    status: string;
    parentQuantity: number;
    childOrders: OrderSlice[];
    executionStats: {
      totalSlices: number;
      avgSliceSize: number;
      durationMinutes: number;
      intervalMinutes: number;
    };
  };
}

export interface OrderSlice {
  time: string;
  quantity: number;
}

// Extended algo order result for formatting
export interface AlgoOrderResult {
  order_id: string;
  symbol: string;
  name: string;
  side: 'buy' | 'sell';
  algo_type: string;
  status: string;
  target_quantity: number;
  filled_quantity: number;
  remaining_quantity: number;
  limit_price?: number;
  avg_price?: number;
  created_at: string;
  start_time: string;
  end_time: string;
  updated_at?: string;
  completed_at?: string;
  algo_params?: {
    participation_rate?: number;
    urgency?: string;
    price_limit?: number;
    time_limit?: number;
  };
  execution_stats?: {
    total_trades?: number;
    avg_trade_size?: number;
    total_commission?: number;
    slippage?: number;
    vwap?: number;
  };
  error_message?: string;
}

// 错误类型
export class QuantV2Error extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public endpoint?: string
  ) {
    super(message);
    this.name = 'QuantV2Error';
  }
}

// K线数据类型
/**
 * K线数据点
 *
 * 数据来源: quantsys-v2 API /api/stock/{symbol}/history
 * 字段映射: 数据库 trade_date → API date
 *
 * @property date - 交易日期，格式 YYYY-MM-DD (数据库字段: trade_date)
 * @property open - 开盘价
 * @property high - 最高价
 * @property low - 最低价
 * @property close - 收盘价
 * @property volume - 成交量
 * @property change_pct - 涨跌幅 (%)，由后端计算 (当日收盘价 - 前日收盘价) / 前日收盘价 * 100
 *
 * 注意: 数据库还有 amount 字段，但 API 不返回
 */
export interface KlineDataPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  change_pct: number;
}

/**
 * K线数据响应
 *
 * @property symbol - 股票代码
 * @property period - 周期类型 (daily/weekly/monthly)
 * @property count - 数据点数量
 * @property data - K线数据数组，按日期升序排列
 */
export interface KlineData {
  success?: boolean;
  symbol: string;
  period: 'daily' | 'weekly' | 'monthly';
  count: number;
  data: KlineDataPoint[];
  error?: string;
}

// 股票基础数据类型
/**
 * 股票基本信息
 *
 * @property symbol - 股票代码
 * @property name - 股票名称
 * @property market - 市场 (SH/SZ/BJ)
 * @property industry - 所属行业
 * @property sector - 所属板块
 * @property market_cap - 市值
 * @property pe_ratio - 市盈率
 * @property pb_ratio - 市净率
 */
export interface StockInfo {
  symbol: string;
  name: string;
  market?: string;
  industry?: string;
  sector?: string;
  market_cap?: number;
  pe_ratio?: number;
  pb_ratio?: number;
}

/**
 * 股票实时价格
 *
 * @property symbol - 股票代码
 * @property name - 股票名称
 * @property price - 当前价格
 * @property change_pct - 涨跌幅 (%)
 * @property high - 当日最高价
 * @property low - 当日最低价
 * @property open - 开盘价
 * @property volume - 成交量
 * @property source - 数据源
 */
export interface StockPrice {
  symbol: string;
  name?: string;
  price: number;
  change_pct: number;
  high: number;
  low: number;
  open: number;
  volume: number;
  source?: string;
}

/**
 * 股票新闻
 *
 * @property title - 新闻标题
 * @property date - 发布日期，格式 YYYY-MM-DD
 * @property source - 新闻来源
 * @property url - 新闻链接
 * @property summary - 新闻摘要
 */
export interface StockNews {
  title: string;
  date: string;
  source?: string;
  url?: string;
  summary?: string;
}

/**
 * 股票公告
 *
 * @property title - 公告标题
 * @property date - 发布日期，格式 YYYY-MM-DD
 * @property type - 公告类型
 * @property url - 公告链接
 */
export interface StockAnnouncement {
  title: string;
  date: string;
  type?: string;
  url?: string;
}

/**
 * 股票综合数据响应
 *
 * 支持部分成功：每个数据源独立查询，失败时对应字段为 null，错误信息记录在 *_error 字段
 *
 * @property success - 整体请求是否成功
 * @property info - 基本信息，失败时为 null
 * @property price - 实时价格，失败时为 null
 * @property news - 新闻列表，失败时为 null
 * @property announcements - 公告列表，失败时为 null
 * @property info_error - 基本信息查询错误
 * @property price_error - 价格查询错误
 * @property news_error - 新闻查询错误
 * @property announcements_error - 公告查询错误
 * @property error - 整体错误信息
 */
export interface StockData {
  success?: boolean;
  info?: StockInfo | null;
  price?: StockPrice | null;
  news?: StockNews[] | null;
  announcements?: StockAnnouncement[] | null;
  info_error?: string;
  price_error?: string;
  news_error?: string;
  announcements_error?: string;
  error?: string;
}

// 策略执行请求参数
export interface StrategyExecuteParams {
  symbol: string;           // 股票代码（如 "600519.SH"）
  strategy_name: string;    // 策略名称（如 "VolatilityBreakout"）
  date?: string;            // 可选：指定日期（默认最新）
}

// 止损配置
export interface StopLossConfig {
  type: 'atr' | 'percent' | 'trailing' | 'fixed';
  price: number;            // 止损价格
  params: {
    atr_value?: number;           // ATR 值
    atr_multiplier?: number;      // ATR 倍数
    percent?: number;             // 百分比
    trailing_percent?: number;    // 追踪百分比
  };
}

// 仓位管理配置
export interface PositionSizingConfig {
  method: 'kelly' | 'fixed_percent' | 'fixed_shares';
  value: number | null;     // 具体值（Kelly 返回 null，需要账户余额计算）
  params: {
    win_rate?: number;            // 胜率
    profit_loss_ratio?: number;   // 盈亏比
    kelly_fraction?: number;      // Kelly 系数
    percent?: number;             // 固定百分比
    shares?: number;              // 固定股数
  };
}

// 风险管理配置
export interface RiskManagement {
  stop_loss?: StopLossConfig;
  position_sizing?: PositionSizingConfig;
  take_profit?: StopLossConfig;  // 可选：止盈（结构同止损）
}

// 策略信号
export interface StrategySignal {
  success: boolean;
  symbol: string;
  name: string;              // 股票名称
  strategy: string;          // 策略名称
  action: 'buy' | 'sell' | 'hold';
  confidence: number;        // 0-1
  reason: string;
  risk_management?: RiskManagement;
  indicators?: Record<string, number>;  // 技术指标
  timestamp: string;
  error?: string;
}

// 批量回测类型
export interface BatchBacktestJob {
  strategy_id: number;
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital?: number;
}

export interface BatchBacktestRequest {
  jobs: BatchBacktestJob[];
  initial_capital?: number;
}

export interface BacktestResult {
  strategy_id: number;
  symbol: string;
  total_return: number;
  annual_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  start_date: string;
  end_date: string;
}

export interface BatchBacktestResponse {
  success: boolean;
  summary: {
    total: number;
    success: number;
    errors: number;
    profitable: number;
    best: BacktestResult | null;
    worst: BacktestResult | null;
  };
  results: BacktestResult[];
  errors: Array<{
    strategy_id?: number;
    symbol?: string;
    error: string;
  }>;
}

// 参数优化类型
export interface StrategyOptimizeRequest {
  strategy_id: number;
  symbol: string;
  start_date: string;
  end_date: string;
  metric: "sharpe" | "return" | "win_rate" | "calmar";
  param_grid: Record<string, Array<number | string>>;
  initial_capital?: number;
  max_combinations?: number;
}

export interface OptimizedParams {
  params: Record<string, number | string>;
  score: number;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
}

export interface StrategyOptimizeResponse {
  success: boolean;
  data: {
    strategy_id: number;
    symbol: string;
    metric: string;
    total_runs: number;
    best: OptimizedParams;
    top10: OptimizedParams[];
  };
}

// 信号生成类型
export interface SignalGenerateRequest {
  symbols?: string[];
  date?: string;
  strategy_ids?: number[];
  async?: boolean;
}

export interface SignalGenerateResponse {
  success: boolean;
  run_id: string;
  status: "running";
  symbol_count: number;
  message: string;
}

// 策略批量验证类型
export interface StrategyBatchValidateParams {
  startDate: string;
  endDate: string;
  threshold?: number;
  dryRun?: boolean;
}

export interface StrategyValidationDetail {
  strategyId: number;
  strategyName: string;
  score: number;
  status: 'passed' | 'failed';
  metrics: {
    annualReturn: number;
    sharpeRatio: number;
    maxDrawdown: number;
    winRate: number;
    profitFactor: number;
  };
  backtestCount: number;
  errorCount: number;
}

export interface StrategyBatchValidateResponse {
  success: boolean;
  data: {
    total: number;
    passed: number;
    failed: number;
    duration: number;
    details: StrategyValidationDetail[];
  };
  error?: string;
}

// Dividend data types
export interface DividendRecord {
  symbol: string;
  name: string;
  fiscal_year: string;
  dividend_type: string;
  cash_dividend: number;
  cash_per_share: number;
  stock_dividend: number;
  bonus_shares: number;
  dividend_yield: number;
  payout_ratio: number;
  announce_date: string;
  shareholder_meeting_date: string;
  ex_dividend_date: string;
  record_date: string;
  pay_date: string;
  status: string;
  total_dividend: number;
  is_implemented: boolean;
}

export interface DividendSummary {
  consecutive_years: number;
  avg_yield: number;
  total_cash_dividend: number;
}

export interface DividendResponse {
  success: boolean;
  error?: string;

  // single mode
  symbol?: string;
  name?: string;
  total_records?: number;
  dividends?: DividendRecord[];
  summary?: DividendSummary;

  // screen mode
  total?: number;
  stocks?: Array<{
    symbol: string;
    name: string;
    latest_yield: number;
    consecutive_years: number;
    avg_payout_ratio: number;
  }>;

  // calendar mode
  period?: string;
  event_type?: string;
  events?: Array<{
    date: string;
    symbol: string;
    name: string;
    cash_per_share: number;
    dividend_yield: number;
  }>;
}
