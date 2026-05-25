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
  order_id: string;
  child_orders: OrderSlice[];
  status: string;
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
