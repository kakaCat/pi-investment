// Client 侧数据形状（与 host 侧 types/index.ts 一致）

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
  name: string;
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
  /** 成交金额（v2 /api/simulation/trades 真实行带 amount；旧行可能缺失 → 前端回退 price*shares） */
  amount?: number;
  /** 卖出平仓实现盈亏（元）；BUY 行为 null/缺失 */
  realized_pnl?: number | null;
  /** 平仓盈亏率（%，SELL 行带）；BUY 行 null */
  realized_pnl_rate?: number | null;
  /** 委托类型（v2: market 等）；缺失兼容 */
  order_type?: string;
  trade_date?: string;
  trade_time?: string;
  reason?: string | null;
  created_at: string;
  status?: string;
}

export interface WatchCondition {
  /** 条件类型，如 price_break（价格突破/跌破） */
  type: string;
  /** 旧式字段（部分规则/宿主仍返回） */
  operator?: string;
  threshold?: number;
  field?: string;
  /** 新式触发参数（价格条件）：{ price, direction: 'above' | 'below' } */
  params?: { price?: number; direction?: string; [k: string]: unknown };
  cooldown_sec?: number;
}

export interface WatchRule {
  id: number;
  symbol: string;
  enabled: boolean;
  conditions: WatchCondition[];
  /** 监控理由（含中文名/策略摘要），真实形状为字符串 */
  context?: unknown;
  cost_price?: number | null;
  created_at: string;
  triggered_count?: number;
  /** 归属账户（account_name 全名）；undefined/null=通用观察（跨账户看板展示） */
  account?: string | null;
  /** 过期时间（ISO）；到点后引擎不再触发，等同停用 */
  expires_at?: string | null;
}

export interface HoldingsData {
  accounts: Account[];
  currentAccount: string;
  summary: PortfolioSummary;
  positions: Position[];
  todayTrades: Trade[];
  /** 历史成交全量（同源 /api/simulation/trades，倒序；供「历史交易」分页卡） */
  tradeHistory: Trade[];
  watchRules: WatchRule[];
  compliance: {
    cashRatio: number;
    maxSingleStock: number;
    maxIndustry: number;
    maxDrawdown60d: number;
  };
}