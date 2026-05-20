/**
 * SignalArbiter - 信号裁决层
 *
 * 解决同一股票同时产生买入和卖出信号的冲突问题
 *
 * 裁决策略：
 * 1. 检测冲突：同一股票同一时间有买入+卖出信号
 * 2. 裁决规则：
 *    - 保留置信度高的信号
 *    - 如果置信度差距小于阈值，则都降级或丢弃
 *    - 考虑策略权重（可选）
 * 3. 记录冲突情况用于监控
 */

import { Signal, SignalActionType } from './types.js';

export interface ArbiterConfig {
  /**
   * 裁决模式
   * - keep_highest: 保留置信度最高的信号
   * - downgrade_both: 两个信号都降级（降低置信度）
   * - discard_both: 两个信号都丢弃
   * - weighted: 使用策略权重裁决
   */
  mode: 'keep_highest' | 'downgrade_both' | 'discard_both' | 'weighted';

  /**
   * 置信度差距阈值
   * 如果两个信号置信度差距小于此值，认为难以判断
   */
  confidenceGapThreshold: number;

  /**
   * 降级因子（用于 downgrade_both 模式）
   * 冲突信号的置信度会乘以此因子
   */
  downgradeFactor: number;

  /**
   * 策略权重（用于 weighted 模式）
   * key: strategy_id, value: weight
   */
  strategyWeights?: Record<string, number>;

  /**
   * 是否记录冲突日志
   */
  logConflicts: boolean;
}

export interface ConflictRecord {
  symbol: string;
  name: string;
  date: string;
  buySignals: Signal[];
  sellSignals: Signal[];
  resolution: 'kept_buy' | 'kept_sell' | 'downgraded_both' | 'discarded_both';
  reason: string;
}

export interface ArbiterResult {
  signals: Signal[];
  conflicts: ConflictRecord[];
  stats: {
    totalInput: number;
    totalOutput: number;
    conflictsDetected: number;
    signalsDiscarded: number;
    signalsDowngraded: number;
  };
}

export class SignalArbiter {
  private config: ArbiterConfig;
  private conflictHistory: ConflictRecord[] = [];

  constructor(config?: Partial<ArbiterConfig>) {
    this.config = {
      mode: config?.mode || 'keep_highest',
      confidenceGapThreshold: config?.confidenceGapThreshold ?? 0.15,
      downgradeFactor: config?.downgradeFactor ?? 0.5,
      strategyWeights: config?.strategyWeights || {},
      logConflicts: config?.logConflicts ?? true,
    };
  }

  /**
   * 裁决信号列表，解决冲突
   */
  arbitrate(signals: Signal[]): ArbiterResult {
    const stats = {
      totalInput: signals.length,
      totalOutput: 0,
      conflictsDetected: 0,
      signalsDiscarded: 0,
      signalsDowngraded: 0,
    };

    const conflicts: ConflictRecord[] = [];

    // Step 1: 按股票分组
    const signalsBySymbol = this.groupBySymbol(signals);

    // Step 2: 检测并解决冲突
    const resolvedSignals: Signal[] = [];

    for (const [symbol, symbolSignals] of signalsBySymbol.entries()) {
      const buySignals = symbolSignals.filter(s => s.action === 'buy');
      const sellSignals = symbolSignals.filter(s => s.action === 'sell');

      // 无冲突：只有买入或只有卖出
      if (buySignals.length === 0 || sellSignals.length === 0) {
        resolvedSignals.push(...symbolSignals);
        continue;
      }

      // 检测到冲突
      stats.conflictsDetected++;

      const conflict = this.resolveConflict(symbol, buySignals, sellSignals);
      conflicts.push(conflict);

      // 根据裁决结果添加信号
      if (conflict.resolution === 'kept_buy') {
        resolvedSignals.push(...conflict.buySignals);
        stats.signalsDiscarded += sellSignals.length;
      } else if (conflict.resolution === 'kept_sell') {
        resolvedSignals.push(...conflict.sellSignals);
        stats.signalsDiscarded += buySignals.length;
      } else if (conflict.resolution === 'downgraded_both') {
        resolvedSignals.push(...conflict.buySignals, ...conflict.sellSignals);
        stats.signalsDowngraded += conflict.buySignals.length + conflict.sellSignals.length;
      } else if (conflict.resolution === 'discarded_both') {
        stats.signalsDiscarded += buySignals.length + sellSignals.length;
      }
    }

    stats.totalOutput = resolvedSignals.length;

    // 记录冲突历史
    if (this.config.logConflicts && conflicts.length > 0) {
      this.conflictHistory.push(...conflicts);
    }

    return {
      signals: resolvedSignals,
      conflicts,
      stats,
    };
  }

  /**
   * 按股票代码分组
   */
  private groupBySymbol(signals: Signal[]): Map<string, Signal[]> {
    const grouped = new Map<string, Signal[]>();

    for (const signal of signals) {
      const existing = grouped.get(signal.symbol) || [];
      existing.push(signal);
      grouped.set(signal.symbol, existing);
    }

    return grouped;
  }

  /**
   * 解决单个股票的信号冲突
   */
  private resolveConflict(
    symbol: string,
    buySignals: Signal[],
    sellSignals: Signal[]
  ): ConflictRecord {
    const name = buySignals[0]?.name || sellSignals[0]?.name || symbol;
    const date = buySignals[0]?.date || sellSignals[0]?.date || new Date().toISOString().split('T')[0];

    switch (this.config.mode) {
      case 'keep_highest':
        return this.resolveByHighestConfidence(symbol, name, date, buySignals, sellSignals);

      case 'downgrade_both':
        return this.resolveByDowngrade(symbol, name, date, buySignals, sellSignals);

      case 'discard_both':
        return this.resolveByDiscard(symbol, name, date, buySignals, sellSignals);

      case 'weighted':
        return this.resolveByWeight(symbol, name, date, buySignals, sellSignals);

      default:
        return this.resolveByHighestConfidence(symbol, name, date, buySignals, sellSignals);
    }
  }

  /**
   * 策略1: 保留置信度最高的信号
   */
  private resolveByHighestConfidence(
    symbol: string,
    name: string,
    date: string,
    buySignals: Signal[],
    sellSignals: Signal[]
  ): ConflictRecord {
    const maxBuyConfidence = Math.max(...buySignals.map(s => s.confidence));
    const maxSellConfidence = Math.max(...sellSignals.map(s => s.confidence));

    const confidenceGap = Math.abs(maxBuyConfidence - maxSellConfidence);

    // 如果置信度差距太小，难以判断，丢弃所有信号
    if (confidenceGap < this.config.confidenceGapThreshold) {
      return {
        symbol,
        name,
        date,
        buySignals: [],
        sellSignals: [],
        resolution: 'discarded_both',
        reason: `置信度差距过小 (${confidenceGap.toFixed(3)} < ${this.config.confidenceGapThreshold})，无法判断`,
      };
    }

    // 保留置信度高的一方
    if (maxBuyConfidence > maxSellConfidence) {
      return {
        symbol,
        name,
        date,
        buySignals: buySignals.filter(s => s.confidence === maxBuyConfidence),
        sellSignals: [],
        resolution: 'kept_buy',
        reason: `买入信号置信度更高 (${maxBuyConfidence.toFixed(3)} > ${maxSellConfidence.toFixed(3)})`,
      };
    } else {
      return {
        symbol,
        name,
        date,
        buySignals: [],
        sellSignals: sellSignals.filter(s => s.confidence === maxSellConfidence),
        resolution: 'kept_sell',
        reason: `卖出信号置信度更高 (${maxSellConfidence.toFixed(3)} > ${maxBuyConfidence.toFixed(3)})`,
      };
    }
  }

  /**
   * 策略2: 降级所有冲突信号
   */
  private resolveByDowngrade(
    symbol: string,
    name: string,
    date: string,
    buySignals: Signal[],
    sellSignals: Signal[]
  ): ConflictRecord {
    // 降低所有信号的置信度
    const downgradedBuy = buySignals.map(s => ({
      ...s,
      confidence: s.confidence * this.config.downgradeFactor,
      reason: `${s.reason} [冲突降级]`,
    }));

    const downgradedSell = sellSignals.map(s => ({
      ...s,
      confidence: s.confidence * this.config.downgradeFactor,
      reason: `${s.reason} [冲突降级]`,
    }));

    return {
      symbol,
      name,
      date,
      buySignals: downgradedBuy,
      sellSignals: downgradedSell,
      resolution: 'downgraded_both',
      reason: `检测到冲突，所有信号置信度降低至 ${(this.config.downgradeFactor * 100).toFixed(0)}%`,
    };
  }

  /**
   * 策略3: 丢弃所有冲突信号
   */
  private resolveByDiscard(
    symbol: string,
    name: string,
    date: string,
    buySignals: Signal[],
    sellSignals: Signal[]
  ): ConflictRecord {
    return {
      symbol,
      name,
      date,
      buySignals: [],
      sellSignals: [],
      resolution: 'discarded_both',
      reason: '检测到冲突，丢弃所有信号',
    };
  }

  /**
   * 策略4: 使用策略权重裁决
   */
  private resolveByWeight(
    symbol: string,
    name: string,
    date: string,
    buySignals: Signal[],
    sellSignals: Signal[]
  ): ConflictRecord {
    // 计算加权得分
    const buyScore = this.calculateWeightedScore(buySignals);
    const sellScore = this.calculateWeightedScore(sellSignals);

    const scoreGap = Math.abs(buyScore - sellScore);
    const avgScore = (buyScore + sellScore) / 2;
    const relativeGap = avgScore > 0 ? scoreGap / avgScore : 0;

    // 如果得分差距太小，丢弃
    if (relativeGap < this.config.confidenceGapThreshold) {
      return {
        symbol,
        name,
        date,
        buySignals: [],
        sellSignals: [],
        resolution: 'discarded_both',
        reason: `加权得分差距过小 (买入=${buyScore.toFixed(3)}, 卖出=${sellScore.toFixed(3)})`,
      };
    }

    // 保留得分高的一方
    if (buyScore > sellScore) {
      return {
        symbol,
        name,
        date,
        buySignals,
        sellSignals: [],
        resolution: 'kept_buy',
        reason: `买入加权得分更高 (${buyScore.toFixed(3)} > ${sellScore.toFixed(3)})`,
      };
    } else {
      return {
        symbol,
        name,
        date,
        buySignals: [],
        sellSignals,
        resolution: 'kept_sell',
        reason: `卖出加权得分更高 (${sellScore.toFixed(3)} > ${buyScore.toFixed(3)})`,
      };
    }
  }

  /**
   * 计算加权得分
   */
  private calculateWeightedScore(signals: Signal[]): number {
    let totalScore = 0;

    for (const signal of signals) {
      const weight = this.config.strategyWeights?.[signal.strategy_id] || 1.0;
      totalScore += signal.confidence * weight;
    }

    return totalScore;
  }

  /**
   * 获取冲突历史
   */
  getConflictHistory(): ConflictRecord[] {
    return [...this.conflictHistory];
  }

  /**
   * 清空冲突历史
   */
  clearConflictHistory(): void {
    this.conflictHistory = [];
  }

  /**
   * 获取冲突统计
   */
  getConflictStats(): {
    totalConflicts: number;
    resolutionBreakdown: Record<string, number>;
    topConflictSymbols: Array<{ symbol: string; count: number }>;
  } {
    const resolutionBreakdown: Record<string, number> = {};
    const symbolCounts: Record<string, number> = {};

    for (const conflict of this.conflictHistory) {
      resolutionBreakdown[conflict.resolution] = (resolutionBreakdown[conflict.resolution] || 0) + 1;
      symbolCounts[conflict.symbol] = (symbolCounts[conflict.symbol] || 0) + 1;
    }

    const topConflictSymbols = Object.entries(symbolCounts)
      .map(([symbol, count]) => ({ symbol, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    return {
      totalConflicts: this.conflictHistory.length,
      resolutionBreakdown,
      topConflictSymbols,
    };
  }
}
