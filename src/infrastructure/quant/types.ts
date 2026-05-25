/**
 * QuantV2Client 类型定义
 */

// 财务数据类型
export interface FinancialData {
  success: boolean;
  symbol: string;
  data: {
    income_statement?: FinancialStatement[];
    balance_sheet?: BalanceSheet[];
    cash_flow?: CashFlow[];
  };
}

export interface FinancialStatement {
  period: string;
  revenue: number;
  net_profit: number;
  gross_profit?: number;
  operating_profit?: number;
}

export interface BalanceSheet {
  period: string;
  total_assets: number;
  total_liabilities: number;
  shareholders_equity: number;
}

export interface CashFlow {
  period: string;
  operating_cash_flow: number;
  investing_cash_flow: number;
  financing_cash_flow: number;
}

// 因子计算类型
export interface FactorComputeParams {
  symbols: string[];
  factors?: string[];
  date?: string;
}

export interface FactorResult {
  success: boolean;
  factors: Record<string, Record<string, number | null>>;
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
