// 持仓数据聚合服务
// 职责：从 v2 各端点拉取数据，聚合为 HoldingsData 契约

import { fetchData, fetchJson } from './http.js';
import { ALL_PARTS } from './parts.js';
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
  /** Agent OS 调度器地址（agent 类账户执行者任务数据源） */
  agentOsBaseURL: string;
  requestTimeoutMs: number;
}

// 冷块（盯盘规则 / 成交明细）服务端 TTL 缓存：这几块变化慢、体积大，短时间内的重复轮询
// 不必回源；用 HOLDINGS_COLD_CACHE_MS 覆盖（默认 30 秒），设 0 关闭。
const COLD_TTL_MS = Number(process.env.HOLDINGS_COLD_CACHE_MS ?? 30000);
const _coldCache = new Map<string, { value: any; ts: number }>();

async function coldCached<T>(key: string, fn: () => Promise<T>): Promise<T> {
  if (COLD_TTL_MS > 0) {
    const hit = _coldCache.get(key);
    if (hit !== undefined && (Date.now() - hit.ts) <= COLD_TTL_MS) return hit.value as T;
  }
  const value = await fn();
  if (COLD_TTL_MS > 0) _coldCache.set(key, { value, ts: Date.now() });
  return value;
}

export class PortfolioAggregationService {
  constructor(private readonly options: AggregationOptions) {}

  /**
   * 聚合持仓数据
   * @param accountName - 账户名称，默认 agent_virtual
   */
  async aggregate(accountName: string = 'agent_virtual', opts?: { parts?: string[] }): Promise<HoldingsData> {
    const { v2BaseURL, requestTimeoutMs, agentOsBaseURL } = this.options;
    const timeout = { timeoutMs: requestTimeoutMs };
    // 2026-09-13（w-adb088f2）：按分块取数。轮询只带 hot（约 4 KB），冷块（盯盘规则 79.5 KB /
    // 成交明细）不进高频轮询 —— 整包 82 KB 里 94.8% 是盯盘规则，却每 15 秒重传一次，这就是
    // 页面"卡住"的主因。缺省＝全量，向后兼容。
    const parts: string[] = opts?.parts ?? [...ALL_PARTS];
    const want = new Set(parts);

    try {
      // 并发请求所有端点（单个失败不影响其他）；agentOsTasks 仅 agent 类账户展示用到，
      // 失败容忍为空（8080 若不可用，agent 账户 automation 退化为不渲染块，strategy 账户不受影响）
      const needTrades = want.has('tradeHistory') || want.has('todayTrades');
      const needRules = want.has('watchRules');
      const [accounts, accountStatus, trades, watchRules, schedulerTasks, agentOsTasks] = await Promise.allSettled([
        this.fetchAccounts(v2BaseURL, timeout),
        this.fetchAccountStatus(v2BaseURL, accountName, timeout),
        needTrades ? coldCached('trades:' + accountName, () => this.fetchTrades(v2BaseURL, accountName, timeout)) : Promise.resolve([] as any[]),
        needRules ? coldCached('rules:' + accountName, () => this.fetchWatchRules(v2BaseURL, accountName, timeout)) : Promise.resolve([] as any[]),
        this.fetchSchedulerTasks(v2BaseURL, timeout),
        this.fetchAgentOsTasks(agentOsBaseURL, timeout),
      ]);

      // 提取结果，失败的用空数组/默认值
      const accountsData = accounts.status === 'fulfilled' ? accounts.value : [];
      const summaryData = accountStatus.status === 'fulfilled' ? accountStatus.value.summary : this.getDefaultSummary();
      const positionsData = accountStatus.status === 'fulfilled' ? accountStatus.value.positions : [];
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
      const agentOsTasksData = agentOsTasks.status === 'fulfilled' ? agentOsTasks.value : [];

      // 自动化流程：strategy 账户 ← qv2 引擎任务；agent 账户（agent_virtual/agent_brain）← Agent OS 执行者例行任务
      const currentAccountMeta = accountsData.find((a) => a.account_name === accountName);
      const automation = this.buildAutomation(currentAccountMeta, schedulerTasksData, agentOsTasksData, accountName);

      // 计算合规指标
      const compliance = this.calculateCompliance(summaryData, positionsData);

      return {
        accounts: accountsData,
        currentAccount: accountName,
        parts,
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

  /** 账户状态（持仓+汇总，同一端点一次请求）。
   *  2026-09-10 起改调 /api/simulation/accounts/{account}（get_account_status，与 position_list 工具同源）：
   *  旧 /api/portfolio/positions|summary 直读 DB 快照——name 恒空（看板名称列退化为裸代码，
   *  靠两份静态字典兜底永远追不上新持仓）且价格曾陈旧（8/28 旧价事故后客户端已弃用该端点）；
   *  新端点每次请求实时拉行情刷新价格并回填真实股票名称。 */
  private async fetchAccountStatus(
    baseURL: string,
    accountName: string,
    timeout: { timeoutMs: number }
  ): Promise<{ summary: PortfolioSummary; positions: Position[] }> {
    const url = `${baseURL}/api/simulation/accounts/${encodeURIComponent(accountName)}`;
    const data = await fetchData<Record<string, any>>(url, timeout);
    const rawPositions = Array.isArray(data.positions) ? data.positions : [];

    // snake_case → camelCase（口径同 quantsys-v2-client mapPosition）
    const positions: Position[] = rawPositions.map((p: Record<string, any>) => {
      const symbol = String(p.symbol ?? '');
      const quantity = Number(p.shares_total) || 0;
      const avgCost = Number(p.avg_cost) || 0;
      const currentPrice = Number(p.current_price) || avgCost;
      const currentValue = Number(p.market_value) || quantity * currentPrice;
      const totalCost = quantity * avgCost;
      const profitLoss = Number(p.profit_total) ?? (currentValue - totalCost);
      const rate = Number(p.profit_total_rate);
      return {
        symbol,
        // 新端点回填真实名称；空时退化为静态映射兜底
        name: String(p.name ?? '') || getStockName(symbol),
        quantity,
        sharesAvailable: Number(p.shares_available) ?? quantity,
        avgCost,
        currentPrice,
        currentValue,
        profitLoss,
        profitLossPct: Number.isFinite(rate)
          ? +(rate * 100).toFixed(2)
          : totalCost > 0 ? +((profitLoss / totalCost) * 100).toFixed(2) : 0,
        profitToday: Number(p.profit_today) || 0,
      };
    });

    const totalCost = positions.reduce((s, p) => s + p.avgCost * p.quantity, 0);
    const totalMarketValue = Number(data.position_value) || positions.reduce((s, p) => s + p.currentValue, 0);
    const totalPnl = totalMarketValue - totalCost;
    const cash = (Number(data.cash_available) || 0) + (Number(data.cash_frozen) || 0);
    const summary: PortfolioSummary = {
      totalValue: Number(data.total_value) || totalMarketValue + cash,
      totalCost,
      totalMarketValue,
      totalPnl,
      totalPnlPct: totalCost > 0 ? +((totalPnl / totalCost) * 100).toFixed(2) : 0,
      dailyChange: positions.reduce((s, p) => s + p.profitToday, 0),
      positions: positions.length,
      cash,
      liquidAssets: cash,
      profitCount: positions.filter((p) => p.profitLoss > 0).length,
      lossCount: positions.filter((p) => p.profitLoss < 0).length,
      lastUpdated: String(data.last_updated ?? new Date().toISOString()),
    };
    return { summary, positions };
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
    const trades = Array.isArray(resp) ? resp : [];
    return this.enrichTradeNames(baseURL, trades, timeout);
  }

  /** 交易记录补名（2026-09-10）：/api/simulation/trades 成交行无 name 字段，
   *  按代码经 /api/stocks/search 批量补全（每代码一次、并发、失败容忍——
   *  补不到时 client 端回退静态字典/裸代码，与持仓行同口径）。 */
  private async enrichTradeNames(
    baseURL: string,
    trades: Trade[],
    timeout: { timeoutMs: number }
  ): Promise<Trade[]> {
    // 后端 2026-09-10 起 trades 路由已联查填充 name——只补仍缺名的代码，避免重复请求
    const codes = [...new Set(
      trades
        .filter((t) => !String(t.name ?? '').trim())
        .map((t) => String(t.symbol ?? '').replace(/\D/g, '').slice(-6))
        .filter((c) => /^\d{6}$/.test(c))
    )].slice(0, 40);
    if (codes.length === 0) return trades;

    const results = await Promise.allSettled(
      codes.map(async (code) => {
        // search 端点为裸信封 {query,total,stocks[]}（无 success/data 包装）→ fetchJson 直取
        const resp = await fetchJson<{ stocks?: Array<Record<string, any>> }>(
          `${baseURL}/api/stocks/search?q=${code}`,
          timeout
        );
        const stocks = Array.isArray(resp?.stocks) ? resp.stocks : [];
        const hit = stocks.find((s) => String(s.symbol ?? '').replace(/\D/g, '').slice(-6) === code) ?? stocks[0];
        return String(hit?.name ?? '');
      })
    );
    const names: Record<string, string> = {};
    results.forEach((r, i) => {
      if (r.status === 'fulfilled' && r.value) names[codes[i]] = r.value;
    });
    return trades.map((t) => {
      if (String(t.name ?? '').trim()) return t; // 后端已填真名的行不动
      const code = String(t.symbol ?? '').replace(/\D/g, '').slice(-6);
      return { ...t, name: names[code] ?? '' };
    });
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

  /** 拉取 Agent OS 调度任务（agent 类账户执行者任务数据源）。
   * 双端点合并（2026-09-08 实证）：/api/v1/scheduler/tasks（list）含 owner 但无运行统计；
   * /api/v1/scheduler/tasks/stats 含运行统计但 owner 恒为空串 → 按 name 合并，owner 取 list。
   * cron 为 6 段（含前导秒）→ 归一化为 5 段 scheduleExpr。 */
  private async fetchAgentOsTasks(baseURL: string, timeout: { timeoutMs: number }): Promise<SchedulerTask[]> {
    if (!baseURL) return [];
    const t = { timeoutMs: Math.min(timeout.timeoutMs, 2500) }; // Agent OS 数据源辅助展示，超时收紧防拖慢看板
    const [listR, statsR] = await Promise.allSettled([
      fetchJson<{ tasks?: unknown[] }>(`${baseURL}/api/v1/scheduler/tasks`, t),
      fetchJson<{ tasks?: unknown[] }>(`${baseURL}/api/v1/scheduler/tasks/stats`, t),
    ]);
    const listTasks = (listR.status === 'fulfilled' ? listR.value.tasks : undefined) ?? [];
    const statsTasks = (statsR.status === 'fulfilled' ? statsR.value.tasks : undefined) ?? [];
    if (listTasks.length === 0 && statsTasks.length === 0) return [];

    const byName = new Map<string, Record<string, any>>();
    for (const raw of listTasks) {
      const o = raw as Record<string, any>;
      const name = String(o.name ?? '');
      if (!name) continue;
      const merged = byName.get(name) ?? {};
      byName.set(name, { ...o, ...merged, _owner: String(o.owner ?? '') });
    }
    for (const raw of statsTasks) {
      const o = raw as Record<string, any>;
      const name = String(o.name ?? '');
      if (!name) continue;
      const merged = byName.get(name) ?? {};
      // stats owner 为空串，勿覆盖 list 的 owner
      const owner = String((merged as any)._owner ?? o.owner ?? '');
      byName.set(name, { ...merged, ...o, _owner: owner });
    }
    const out: SchedulerTask[] = [];
    for (const o of byName.values()) {
      const task = this.normalizeAgentOsTask(o);
      if (task.name) out.push(task);
    }
    return out;
  }

  /** 归一化 Agent OS 任务 → SchedulerTask 形状。cron 6 段（秒 分 时 日 月 周）剥前导秒 → 5 段；
   * 运行态取自 stats 的 last_run_at/last_run_status；owner 暂存扩展字段供 buildAutomation 白名单校验。 */
  private normalizeAgentOsTask(raw: Record<string, any>): SchedulerTask & { owner?: string } {
    const cron = String(raw.cron ?? raw.schedule ?? '').trim();
    const parts = cron.split(/\s+/).filter(Boolean);
    const cron5 = parts.length === 6 ? parts.slice(1).join(' ') : cron;
    const ls = String(raw.last_run_status ?? '');
    const known = ['success', 'failed', 'skipped', 'running', 'pending', 'unknown'];
    const status = known.includes(ls) ? ls : ls === 'completed' ? 'success' : ls ? ls : '';
    return {
      id: String(raw.id ?? raw.name ?? ''),
      name: String(raw.name ?? ''),
      enabled: raw.enabled === true || raw.enabled === 'true' || raw.enabled === 1,
      scheduleExpr: cron5,
      command: '', // Agent OS 无 payload.command；展示中文名走 AUTO_ZH[name]
      description: String(raw.description ?? ''),
      lastStatus: status,
      lastAt: raw.last_run_at ? String(raw.last_run_at) : null,
      lastError: '',
      nextRunAt: null,
      todayTriggered: 0,
      todaySuccess: 0,
      strategy: '',
      owner: String(raw._owner ?? raw.owner ?? ''),
    };
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

  /** 组装当前账户的自动化流程概览（双轨：strategy 引擎账户 ← qv2 引擎任务；agent 账户 ← Agent OS 执行者例行任务）。
   * agent 分支映射实证（2026-09-08 Agent OS owner 分布）：
   *  - agent_virtual ← fin-agent（TS@3002 交易/复盘链，任务模板实证 account: agent_virtual）；
   *  - agent_brain ← investor（@13080 agent-dh 窗口账户例行：盘前/午后/盘后/熔断/周报——诚实口径：
   *    这些是系统例行巡检性质、实际作用于默认账户 agent_virtual，非 agent_brain 专属买卖任务，配 note 说明）。 */
  private buildAutomation(acct: Account | undefined, tasks: SchedulerTask[], agentOsTasks: SchedulerTask[], accountName: string): AccountAutomation {
    if (!acct) {
      return { accountName, accountType: '', displayName: accountName, strategyName: '', engine: false, tasks: [], executor: '', note: '' };
    }
    const key = String(acct.strategy_name ?? '').trim();
    if (acct.account_type === 'strategy') {
      const bound = key ? tasks.filter((t) => t.strategy === key) : [];
      return {
        accountName: acct.account_name ?? accountName,
        accountType: acct.account_type ?? '',
        displayName: acct.display_name || acct.account_name || accountName,
        strategyName: key,
        engine: true,
        tasks: sortBySchedule(bound),
        executorCode: 'v2',
      };
    }
    if (acct.account_type === 'agent') {
      const map = AGENT_EXECUTOR_BY_ACCOUNT[acct.account_name ?? ''];
      if (map) {
        const bound = agentOsTasks.filter((t) => {
          const own = String((t as SchedulerTask & { owner?: string }).owner ?? '');
          const names = map.tasks[own];
          return Array.isArray(names) && names.includes(t.name);
        });
        // 诚实口径：白名单命中的 disabled 任务（如 agent_brain 曾 disabled 的巡检）不展示；
        // 但保留以标注「已停用」让用户看到例行曾经存在 → 此处展示全部命中项，autoRow 已有 enabled=false → 「未启用」标注
        return {
          accountName: acct.account_name ?? accountName,
          accountType: acct.account_type ?? '',
          displayName: acct.display_name || acct.account_name || accountName,
          strategyName: key,
          engine: false,
          tasks: sortBySchedule(bound),
          executor: map.executor,
          executorCode: map.code,
          note: map.note,
        };
      }
      return {
        accountName: acct.account_name ?? accountName,
        accountType: acct.account_type ?? '',
        displayName: acct.display_name || acct.account_name || accountName,
        strategyName: key,
        engine: false,
        tasks: [],
        executor: '',
        note: '',
      };
    }
    // user/legacy：无自动化展示
    return {
      accountName: acct.account_name ?? accountName,
      accountType: acct.account_type ?? '',
      displayName: acct.display_name || acct.account_name || accountName,
      strategyName: key,
      engine: false,
      tasks: [],
      executor: '',
      note: '',
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

/** cron 5 段（分 时 日 月 周）→ 当日首触发时刻分钟数(0-1439)，供自动化流程按时间排序。
 * 仅用分钟/小时字段：范围(9-14)→9、列表(1,2)→1、步进 cron（每30分）→0、通配 →0；解析失败 → null（排序尾置）。
 * 注：注释内不得含「星斜杠30」形态字面量，会提前终止块注释。 */
function scheduleMinuteOfDay(expr: string): number | null {
  const parts = String(expr ?? '').trim().split(/\s+/).filter(Boolean);
  if (parts.length < 2) return null;
  const first = (f: string): number | null => {
    if (!f || f === '*' || f === '?') return 0;
    if (f.startsWith('*/')) return 0;
    const base = f.split('-')[0].split(',')[0];
    if (!base || base === '*' || base === '?') return 0;
    const n = Number(base);
    return Number.isFinite(n) ? n : null;
  };
  const h = first(parts[1]);
  const m = first(parts[0]);
  if (h === null || m === null) return null;
  return h * 60 + m;
}

/** 自动化任务按「当日计划时刻」升序排列（账户自动化流程时间线；engine/agent 两轨统一）。
 * 解析失败（无 cron/空）尾置并保持原相对序（Array.sort 稳定）。 */
function sortBySchedule<T extends { scheduleExpr?: string | null }>(tasks: T[]): T[] {
  const arr = tasks.slice();
  arr.sort((a, b) => {
    const ka = scheduleMinuteOfDay(String(a.scheduleExpr ?? ''));
    const kb = scheduleMinuteOfDay(String(b.scheduleExpr ?? ''));
    if (ka === null && kb === null) return 0;
    if (ka === null) return 1;
    if (kb === null) return -1;
    return ka - kb;
  });
  return arr;
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

/* ---------------- Agent 账户执行者例行任务白名单（2026-09-08 实证） ---------------- */
/** agent 类账户 → Agent OS owner + 任务名白名单。仅白名单命中项展示为「自动化流程」，
 * 其余 Agent OS 任务（agent-dh 引擎进化/股票池治理、quantsys-v2 内部任务、一次性核验、
 * script 巡检等）不映射到任何账户——避免把与账户执行链无关的任务伪装成账户例行。 */
interface AgentExecutorMap {
  /** 执行载体短码（徽标）：ts=fin-agent(agent-ts) / dh=agent-dh·investor */
  code: string;
  executor: string;
  note: string;
  tasks: Record<string, string[]>;
}
const AGENT_EXECUTOR_BY_ACCOUNT: Record<string, AgentExecutorMap> = {
  // agent_virtual：执行载体 fin-agent（agent-ts @3002），7 个交易/复盘链任务（实证任务模板 account: agent_virtual）
  agent_virtual: {
    code: 'ts',
    executor: 'fin-agent（AI 执行者 · agent-ts）',
    note: 'fin-agent 专属交易/复盘链任务（agent_virtual 账户决策与执行）',
    tasks: {
      'fin-agent': [
        'morning_ai_analysis',
        'realtime_quick_check',
        'daily_ai_review',
        'daily_recall_audit',
        'weekly_evolution',
        'weekly_memory_distill',
        'weekly_tool_roi_review',
      ],
    },
  },
  // agent_brain：执行载体 agent-dh investor 窗口（@13080）。7 条 agent-brain-* 专属例行
  // （2026-09-08 上线，镜像 fin-agent 作息，owner=investor、webhook :13080/agent-os-trigger、
  // 全部工具显式 account='agent_brain'）为账户自己的买卖/复盘/进化链；另 5 条系统巡检
  // （pre-market 等）作用于默认账户 agent_virtual，诚实保留展示。
  agent_brain: {
    code: 'dh',
    executor: 'agent-dh · investor 例行',
    note: 'agent_brain 专属例行 7 条（agent-brain-* 前缀，2026-09-08 上线，交易日 9:00 起跑）+ 系统巡检 5 条（作用于默认账户 agent_virtual）',
    tasks: {
      investor: [
        // agent_brain 专属买卖/复盘/进化链
        'agent-brain-morning-analysis',
        'agent-brain-realtime-check',
        'agent-brain-daily-review',
        'agent-brain-daily-audit',
        'agent-brain-weekly-roi',
        'agent-brain-weekly-evolution',
        'agent-brain-weekly-distill',
        // 系统巡检（作用于默认账户 agent_virtual，诚实保留）
        'pre-market-routine',
        'afternoon-open-check-live',
        'post-market-routine-live',
        'm4-circuit-breaker-live',
        'weekly-report-m6',
      ],
    },
  },
};

