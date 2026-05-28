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
