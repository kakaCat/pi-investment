// 持仓看板数据契约
// GET /dashboard/api/holdings?account=agent_virtual (默认)
// 返回：{ success: true, data: HoldingsData } | { success: false, error: string }

export interface Account {
  account_name: string;
  display_name: string;
  /** 账户类型口径：strategy=引擎策略仓 / agent=AI自营仓 / user=用户主仓 / legacy=历史账户 */
  account_type?: string;
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
  /** 成交金额（v2 真实行带）；旧行缺失时前端回退 price*shares */
  amount?: number;
  /** 卖出平仓实现盈亏（元）；BUY 行 null */
  realized_pnl?: number | null;
  realized_pnl_rate?: number | null;
  order_type?: string;
  trade_date?: string;
  trade_time?: string;
  reason?: string | null;
  created_at: string;
  status?: string;
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

/** 引擎调度任务（归一化展示形状；lastStatus 已按「内层真实执行结果」归一——
 *  外层 scheduler lastRun.status 存在假成功：inner payload.details.details.status/error 才是真相）
 */
export interface SchedulerTask {
  id: string;
  name: string;
  enabled: boolean;
  /** 5 段 cron（如 "30 6 * * 1-5"） */
  scheduleExpr: string;
  /** payload.command（如 v13_daily_check） */
  command: string;
  description: string;
  /** success/failed/skipped/pending/unknown/''（''=从未运行） */
  lastStatus: string;
  lastAt: string | null;
  lastError: string;
  nextRunAt: string | null;
  todayTriggered: number;
  todaySuccess: number;
  /** 绑定的引擎策略 key（v13/v14/v15/...）；''=无策略绑定 */
  strategy: string;
}

/** 当前账户的自动化流程概览（host 聚合时按 strategy 绑定过滤任务） */
export interface AccountAutomation {
  accountName: string;
  accountType: string;
  displayName: string;
  strategyName: string;
  /** 是否为引擎策略账户（strategy 型）；false=agent/user/legacy 无引擎任务 */
  engine: boolean;
  tasks: SchedulerTask[];
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
  /** 当前账户的自动化流程（引擎调度任务；agent/user/legacy 账户无任务时 engine=false） */
  automation?: AccountAutomation;
  compliance: {
    cashRatio: number; // 现金占比
    maxSingleStock: number; // 最大单股占比
    maxIndustry: number; // 最大行业占比
    maxDrawdown60d: number; // 60日最大回撤
  };
}
