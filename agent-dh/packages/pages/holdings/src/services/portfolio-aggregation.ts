// 持仓数据聚合服务
// 职责：从 v2 各端点拉取数据，聚合为 HoldingsData 契约

import { fetchData, fetchJson } from './http.js';
import { getStockName } from './name-map.js';
import type {
  Account,
  AccountAutomation,
  HoldingsData,
  PortfolioSummary,
  Position,
  SchedulerTask,
  Trade,
  WatchRule,
} from '../types/index.js';

export interface AggregationOptions {
  v2BaseURL: string;
  requestTimeoutMs: number;
}

export class PortfolioAggregationService {
  constructor(private readonly options: AggregationOptions) {}

  /**
   * 聚合持仓数据
   * @param accountName - 账户名称，默认 agent_virtual
   */
  async aggregate(accountName: string = 'agent_virtual'): Promise<HoldingsData> {
    const { v2BaseURL, requestTimeoutMs } = this.options;
    const timeout = { timeoutMs: requestTimeoutMs };

    try {
      // 并发请求所有端点（单个失败不影响其他）
      const [accounts, summary, positions, trades, watchRules, schedulerTasks] = await Promise.allSettled([
        this.fetchAccounts(v2BaseURL, timeout),
        this.fetchSummary(v2BaseURL, accountName, timeout),
        this.fetchPositions(v2BaseURL, accountName, timeout),
        this.fetchTrades(v2BaseURL, accountName, timeout),
        this.fetchWatchRules(v2BaseURL, accountName, timeout),
        this.fetchSchedulerTasks(v2BaseURL, timeout),
      ]);

      // 提取结果，失败的用空数组/默认值
      const accountsData = accounts.status === 'fulfilled' ? accounts.value : [];
      const summaryData = summary.status === 'fulfilled' ? summary.value : this.getDefaultSummary();
      const positionsData = positions.status === 'fulfilled' ? positions.value : [];
      const tradesData = trades.status === 'fulfilled' ? trades.value : [];

      // 今日成交与历史交易同源（/api/simulation/trades 全量，v2 已倒序）；拆两视图用：
      //   todayTrades = 当日过滤（「今日自动交易」卡）；tradeHistory = 全量（「历史交易」分页卡）
      const tradeHistory = [...tradesData].sort((a, b) => String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')))
      // 「今日」按本地日期口径（toISOString 是 UTC，00:00–08:00 会把当日成交错归昨日）：
      // 优先 v2 自带的 trade_date（YYYY-MM-DD，本地），回退 created_at 前 10 位
      const nowD = new Date()
      const localToday = nowD.getFullYear() + '-' + String(nowD.getMonth() + 1).padStart(2, '0') + '-' + String(nowD.getDate()).padStart(2, '0')
      const todayTrades = tradeHistory.filter((t) => (t.trade_date ?? (t.created_at ? t.created_at.slice(0, 10) : '')) === localToday)
      const watchRulesData = watchRules.status === 'fulfilled' ? watchRules.value : [];
      const schedulerTasksData = schedulerTasks.status === 'fulfilled' ? schedulerTasks.value : [];

      // 自动化流程：找到当前账户 → 引擎策略账户才有关联任务；agent/user/legacy 无 v2 引擎任务
      const currentAccountMeta = accountsData.find((a) => a.account_name === accountName);
      const automation = this.buildAutomation(currentAccountMeta, schedulerTasksData, accountName);

      // 计算合规指标
      const compliance = this.calculateCompliance(summaryData, positionsData);

      return {
        accounts: accountsData,
        currentAccount: accountName,
        summary: summaryData,
        positions: positionsData,
        todayTrades,
        tradeHistory,
        watchRules: watchRulesData,
        automation,
        compliance,
      };
    } catch (error) {
      throw new Error(`持仓数据聚合失败: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async fetchAccounts(baseURL: string, timeout: { timeoutMs: number }): Promise<Account[]> {
    const url = `${baseURL}/api/simulation/accounts`;
    const resp = await fetchData<{ accounts: Account[] }>(url, timeout);
    return resp.accounts || [];
  }

  private async fetchSummary(
    baseURL: string,
    accountName: string,
    timeout: { timeoutMs: number }
  ): Promise<PortfolioSummary> {
    const url = `${baseURL}/api/portfolio/summary?account_name=${accountName}`;
    return await fetchData<PortfolioSummary>(url, timeout);
  }

  private async fetchPositions(
    baseURL: string,
    accountName: string,
    timeout: { timeoutMs: number }
  ): Promise<Position[]> {
    const url = `${baseURL}/api/portfolio/positions?account_name=${accountName}`;
    const resp = await fetchData<{ positions: Position[] }>(url, timeout);
    const positions = resp.positions || [];

    // 补全 name 字段（v2 返回的 name 为空）
    return positions.map((pos) => ({
      ...pos,
      name: pos.name || getStockName(pos.symbol),
    }));
  }

  private async fetchTrades(
    baseURL: string,
    accountName: string,
    timeout: { timeoutMs: number }
  ): Promise<Trade[]> {
    // v2 /api/simulation/trades 信封实测 {success, data: Trade[]}（成交明细，全历史倒序、无 status 字段）——
    // pluck 按 data 数组直取，勿按 {trades:[]} 假设（旧写法 unwrap 后取 .trades 恒为空）
    const url = `${baseURL}/api/simulation/trades?account_name=${accountName}`;
    const resp = await fetchData<Trade[]>(url, timeout);
    return Array.isArray(resp) ? resp : [];
  }
  private async fetchWatchRules(baseURL: string, accountName: string, timeout: { timeoutMs: number }): Promise<WatchRule[]> {
    // 全量拉取（不按 account 过滤）：盯盘中心按「账户归属 tab」展示，须带出全部账户规则；
    // 视图过滤（本账户=该账户归属 + 通用观察 account 为空）由 client 端完成（2026-09-05 盯盘 tab 化）
    const url = `${baseURL}/api/watch/rules`;
    const resp = await fetchData<{ rules: WatchRule[] }>(url, timeout);
    return resp.rules || [];
  }

  private async fetchSchedulerTasks(baseURL: string, timeout: { timeoutMs: number }): Promise<SchedulerTask[]> {
    // qv2 scheduler 端点是裸信封 {success, tasks, ...}（无 data 键）→ fetchJson 直取 .tasks
    const url = `${baseURL}/api/scheduler/tasks?pageSize=200`;
    const resp = await fetchJson<{ tasks?: unknown[] }>(url, timeout);
    return (Array.isArray(resp.tasks) ? resp.tasks : []).map((t) => this.normalizeTask(t));
  }

  /** 归一化调度任务：status 以「内层真实执行结果」为准（外层 lastRun.status 假成功陷阱） */
  private normalizeTask(raw: unknown): SchedulerTask {
    const t = (raw ?? {}) as Record<string, any>;
    const payload = (t.payload ?? {}) as Record<string, any>;
    const lastRun = t.lastRun;

    const { status, at, err } = resolveLastRun(lastRun);
    return {
      id: String(t.id ?? ''),
      name: String(t.name ?? ''),
      enabled: t.enabled === true || t.enabled === 'true' || t.enabled === 1,
      scheduleExpr: String(t.scheduleExpr ?? ''),
      command: String(payload.command ?? payload.action ?? ''),
      description: String(payload.description ?? payload.desc ?? ''),
      lastStatus: status,
      lastAt: at,
      lastError: err,
      nextRunAt: t.nextRunAt ? String(t.nextRunAt) : null,
      todayTriggered: Number(t.todayTriggered ?? 0) || 0,
      todaySuccess: Number(t.todaySuccess ?? 0) || 0,
      strategy: strategyOf(String(t.name ?? ''), String(payload.command ?? payload.action ?? ''), payload.strategy),
    };
  }

  /** 组装当前账户的自动化流程概览（仅 strategy 引擎账户有关联任务） */
  private buildAutomation(acct: Account | undefined, tasks: SchedulerTask[], accountName: string): AccountAutomation {
    if (!acct) {
      return { accountName, accountType: '', displayName: accountName, strategyName: '', engine: false, tasks: [] };
    }
    const isEngine = acct.account_type === 'strategy';
    const key = String(acct.strategy_name ?? '').trim();
    const bound = isEngine && key
      ? tasks.filter((t) => t.strategy === key)
      : [];
    return {
      accountName: acct.account_name ?? accountName,
      accountType: acct.account_type ?? '',
      displayName: acct.display_name || acct.account_name || accountName,
      strategyName: key,
      engine: isEngine,
      tasks: bound,
    };
  }

  private getDefaultSummary(): PortfolioSummary {
    return {
      totalValue: 0,
      totalCost: 0,
      totalMarketValue: 0,
      totalPnl: 0,
      totalPnlPct: 0,
      dailyChange: 0,
      positions: 0,
      cash: 0,
      liquidAssets: 0,
      profitCount: 0,
      lossCount: 0,
      lastUpdated: new Date().toISOString(),
    };
  }

  private calculateCompliance(summary: PortfolioSummary, positions: Position[]): {
    cashRatio: number;
    maxSingleStock: number;
    maxIndustry: number;
    maxDrawdown60d: number;
  } {
    const totalValue = summary.totalValue || 1; // 避免除零
    const cashRatio = (summary.cash / totalValue) * 100;

    // 计算单股最大占比
    let maxSingleStock = 0;
    for (const pos of positions) {
      const ratio = (pos.currentValue / totalValue) * 100;
      if (ratio > maxSingleStock) {
        maxSingleStock = ratio;
      }
    }

    // 行业占比（暂时简化，实际需要行业分类）
    const maxIndustry = 0; // TODO: 需要股票行业数据

    // 60日最大回撤（暂时从 summary 中获取，实际需要历史净值数据）
    const maxDrawdown60d = 0; // TODO: 需要净值时间序列

    return {
      cashRatio: Math.round(cashRatio * 100) / 100,
      maxSingleStock: Math.round(maxSingleStock * 100) / 100,
      maxIndustry: Math.round(maxIndustry * 100) / 100,
      maxDrawdown60d: Math.round(maxDrawdown60d * 100) / 100,
    };
  }
}


/* ---------------- 引擎任务辅助（模块级，2026-09-05） ---------------- */

/** 解析 lastRun → {status, at, err}。status 优先取内层 payload.details.details
 * （qv2 scheduler 外层 lastRun.status=success 但内层可能 failed/skipped——假成功陷阱）；
 * inner 缺失时回退外层 lastRun.status/error。 */
function resolveLastRun(lr: unknown): { status: string; at: string | null; err: string } {
  if (lr === null || lr === undefined) return { status: '', at: null, err: '' };
  if (typeof lr === 'string') {
    if (/^(success|failed|skipped|running|pending|unknown|completed|misfire)$/.test(lr)) {
      return { status: lr, at: null, err: '' };
    }
    return { status: '', at: lr, err: '' };
  }
  const o = lr as Record<string, any>;
  const at = o.triggeredAt ? String(o.triggeredAt) : null;
  // 内层详情：可能是 details.details（引擎动作执行）或 details（单层）
  const innerCandidates = [o.payload?.details?.details, o.payload?.details];
  for (const inner of innerCandidates) {
    if (inner && typeof inner === 'object') {
      const ist = String(inner.status ?? '');
      if (ist) {
        const errMsg = String(inner.error ?? inner.message ?? '');
        // completed 语义归 success（引擎内层用 completed 表示完成）
        const st = ist === 'completed' ? 'success' : ist;
        return { status: st, at, err: errMsg };
      }
    }
  }
  // 无内层详情：回退外层（含 misfire 等调度器自身状态）
  const outerErr = String(o.error ?? o.message ?? '');
  const outerSt = String(o.status ?? '');
  return { status: outerSt === 'completed' ? 'success' : outerSt, at, err: outerErr };
}

/** 任务 → 引擎策略 key：任务名/命令前缀 v13-/v13_/v14- 等；chip 任务归 chip_theme */
function strategyOf(name: string, command: string, innerStrategy?: unknown): string {
  const src = name + '|' + command;
  for (const k of ['v13', 'v14', 'v15']) {
    if (src.includes(k + '-') || src.includes(k + '_')) {
      // 前缀匹配避免误伤（如 v130 之类无真实策略，仅接受 -/_ 分隔）
      const idx = src.indexOf(k + '-');
      if (idx === 0 || src[idx - 1] === '|') return k;
      const idx2 = src.indexOf(k + '_');
      if (idx2 === 0 || src[idx2 - 1] === '|') return k;
      // 仅命令里以 vXX_ 开头
      if (command.startsWith(k + '_')) return k;
    }
  }
  if (name.startsWith('chip') || command.startsWith('chip_')) return 'chip_theme';
  if (typeof innerStrategy === 'string' && /^(v13|v14|v15|chip_theme)$/.test(innerStrategy)) return innerStrategy;
  return '';
}
