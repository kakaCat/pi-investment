// 持仓看板数据契约
// GET /dashboard/api/holdings?account=agent_virtual (默认)
// 返回：{ success: true, data: HoldingsData } | { success: false, error: string }

export interface Account {
  account_name: string;
  display_name: string;
  strategy_name: string;
  status: string;
  cash_available: number;
  position_value: number;
  total_value: number;
  cumulative_return: number;
  positions_count: number;
}

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

export interface Position {
  symbol: string;
  name: string; // 可能为空，host 侧会补全
  quantity: number;
  sharesAvailable: number;
  avgCost: number;
  currentPrice: number;
  currentValue: number;
  profitLoss: number;
  profitLossPct: number;
  profitToday: number;
}

export interface Trade {
  order_id: string;
  symbol: string;
  action: string;
  shares: number;
  price: number;
  filled_price: number;
  realized_pnl: number;
  reason: string;
  created_at: string;
  status: string;
}

export interface WatchCondition {
  type: string;
  operator: string;
  threshold: number;
  field?: string;
}

export interface WatchRule {
  id: number;
  symbol: string;
  enabled: boolean;
  conditions: WatchCondition[];
  context: Record<string, any>;
  created_at: string;
  triggered_count: number;
  /** 归属账户（account_name 全名，如 agent_virtual）；null=通用观察（跨账户看板展示） */
  account?: string | null;
}

export interface HoldingsData {
  accounts: Account[];
  currentAccount: string;
  summary: PortfolioSummary;
  positions: Position[];
  todayTrades: Trade[];
  watchRules: WatchRule[];
  compliance: {
    cashRatio: number; // 现金占比
    maxSingleStock: number; // 最大单股占比
    maxIndustry: number; // 最大行业占比
    maxDrawdown60d: number; // 60日最大回撤
  };
}
