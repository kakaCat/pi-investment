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
        this.fetchTodayTrades(v2BaseURL, accountName, timeout),
        this.fetchWatchRules(v2BaseURL, accountName, timeout),
      ]);

      // 提取结果，失败的用空数组/默认值
      const accountsData = accounts.status === 'fulfilled' ? accounts.value : [];
      const summaryData = summary.status === 'fulfilled' ? summary.value : this.getDefaultSummary();
      const positionsData = positions.status === 'fulfilled' ? positions.value : [];
      const tradesData = trades.status === 'fulfilled' ? trades.value : [];
      const watchRulesData = watchRules.status === 'fulfilled' ? watchRules.value : [];

      // 计算合规指标
      const compliance = this.calculateCompliance(summaryData, positionsData);

      return {
        accounts: accountsData,
        currentAccount: accountName,
        summary: summaryData,
        positions: positionsData,
        todayTrades: tradesData,
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

  private async fetchTodayTrades(
    baseURL: string,
    accountName: string,
    timeout: { timeoutMs: number }
  ): Promise<Trade[]> {
    const url = `${baseURL}/api/simulation/trades?account_name=${accountName}`;
    const resp = await fetchData<{ trades: Trade[] }>(url, timeout);
    const trades = resp.trades || [];

    // 过滤今天的交易
    const today = new Date().toISOString().split('T')[0];
    return trades.filter((t) => t.created_at && t.created_at.startsWith(today));
  }

  private async fetchWatchRules(baseURL: string, accountName: string, timeout: { timeoutMs: number }): Promise<WatchRule[]> {
    // account 过滤：后端返回该账户归属 + 通用观察（account IS NULL）的规则（2026-09-04 账户关联）
    const url = `${baseURL}/api/watch/rules?account=${encodeURIComponent(accountName)}`;
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
