// 持仓数据聚合服务
// 职责：从 v2 各端点拉取数据，聚合为 HoldingsData 契约

import { fetchData } from './http.js';
import { getStockName } from './name-map.js';
import type {
  Account,
  HoldingsData,
  PortfolioSummary,
  Position,
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
      const [accounts, summary, positions, trades, watchRules] = await Promise.allSettled([
        this.fetchAccounts(v2BaseURL, timeout),
        this.fetchSummary(v2BaseURL, accountName, timeout),
        this.fetchPositions(v2BaseURL, accountName, timeout),
        this.fetchTrades(v2BaseURL, accountName, timeout),
        this.fetchWatchRules(v2BaseURL, accountName, timeout),
      ]);

      // 提取结果，失败的用空数组/默认值
      const accountsData = accounts.status === 'fulfilled' ? accounts.value : [];
      const summaryData = summary.status === 'fulfilled' ? summary.value : this.getDefaultSummary();
      const positionsData = positions.status === 'fulfilled' ? positions.value : [];
      const tradesData = trades.status === 'fulfilled' ? trades.value : [];

      // 今日成交与历史交易同源（/api/simulation/trades 全量，v2 已倒序）；拆两视图用：
      //   todayTrades = 当日过滤（「今日自动交易」卡）；tradeHistory = 全量（「历史交易」分页卡）
      const tradeHistory = [...tradesData].sort((a, b) => String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')))
      const today = new Date().toISOString().split('T')[0]
      const todayTrades = tradeHistory.filter((t) => t.created_at && t.created_at.startsWith(today))
      const watchRulesData = watchRules.status === 'fulfilled' ? watchRules.value : [];

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
