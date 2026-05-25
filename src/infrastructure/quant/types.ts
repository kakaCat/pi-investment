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
  risk_level: string;
  signals: string[];
}

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
  slices: OrderSlice[];
  status: string;
}

export interface OrderSlice {
  time: string;
  quantity: number;
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
