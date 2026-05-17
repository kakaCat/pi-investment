/**
 * Performance Analyzer - 策略性能分析器
 *
 * 统计量化策略的历史表现，包括：
 * - 信号数量统计
 * - 胜率计算
 * - 平均收益率
 * - 最大回撤
 * - 夏普比率
 */

import { readFileSync, readdirSync, existsSync } from 'fs';
import { join } from 'path';
import type { Signal } from './types.js';

export interface PerformanceMetrics {
  strategy_id: string;
  strategy_name: string;
  period_days: number;

  // 信号统计
  total_signals: number;
  buy_signals: number;
  sell_signals: number;

  // 收益统计
  win_rate: number;              // 胜率 (%)
  avg_profit_pct: number;        // 平均收益率 (%)
  total_profit_pct: number;      // 总收益率 (%)

  // 风险指标
  max_drawdown_pct: number;      // 最大回撤 (%)
  sharpe_ratio: number | null;   // 夏普比率

  // 详细数据
  profitable_trades: number;
  losing_trades: number;
  avg_win_pct: number;
  avg_loss_pct: number;

  // 时间范围
  first_signal_date: string | null;
  last_signal_date: string | null;
}

export interface SignalPerformance {
  signal: Signal;
  profit_pct: number | null;
  is_profitable: boolean | null;
  days_held: number | null;
}

export class PerformanceAnalyzer {
  private signalsDir: string;

  constructor(signalsDir: string = '.pi-invest/quant/signals') {
    this.signalsDir = signalsDir;
  }

  /**
   * 分析策略性能
   */
  async analyzeStrategy(
    strategyId: string,
    strategyName: string,
    days: number = 30
  ): Promise<PerformanceMetrics> {
    // 加载历史信号
    const signals = this.loadSignals(strategyId, days);

    if (signals.length === 0) {
      return this.emptyMetrics(strategyId, strategyName, days);
    }

    // 计算每个信号的表现
    const performances = await this.calculateSignalPerformances(signals);

    // 统计指标
    return this.calculateMetrics(strategyId, strategyName, days, signals, performances);
  }

  /**
   * 加载历史信号
   */
  private loadSignals(strategyId: string, days: number): Signal[] {
    if (!existsSync(this.signalsDir)) {
      return [];
    }

    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - days);

    const allSignals: Signal[] = [];
    const files = readdirSync(this.signalsDir).filter(f => f.endsWith('.json'));

    for (const file of files) {
      try {
        const filePath = join(this.signalsDir, file);
        const content = readFileSync(filePath, 'utf-8');
        const data = JSON.parse(content);

        // 过滤该策略的信号
        const signals = (data.signals || []).filter((s: Signal) => {
          if (s.strategy_id !== strategyId) return false;

          const signalDate = new Date(s.date);
          return signalDate >= cutoffDate;
        });

        allSignals.push(...signals);
      } catch (e) {
        console.error(`[PerformanceAnalyzer] Failed to load ${file}:`, e);
      }
    }

    return allSignals.sort((a, b) =>
      new Date(a.date).getTime() - new Date(b.date).getTime()
    );
  }

  /**
   * 计算每个信号的表现
   */
  private async calculateSignalPerformances(signals: Signal[]): Promise<SignalPerformance[]> {
    const performances: SignalPerformance[] = [];

    for (const signal of signals) {
      // 简化版：使用信号的置信度作为预期收益的代理
      // 实际应该查询真实的价格数据计算实际收益
      const performance = await this.calculateSingleSignalPerformance(signal);
      performances.push(performance);
    }

    return performances;
  }

  /**
   * 计算单个信号的表现
   */
  private async calculateSingleSignalPerformance(signal: Signal): Promise<SignalPerformance> {
    // TODO: 实际应该查询历史价格数据
    // 这里使用简化逻辑：基于置信度模拟收益

    const baseProfit = signal.action === 'buy' ? 1 : -1;
    const confidenceFactor = (signal.confidence - 0.5) * 2; // 将0.5-1映射到0-1

    // 模拟收益：置信度越高，收益越好（或亏损越小）
    const profit_pct = baseProfit * confidenceFactor * 5 + (Math.random() - 0.5) * 3;

    return {
      signal,
      profit_pct,
      is_profitable: profit_pct > 0,
      days_held: Math.floor(Math.random() * 10) + 1 // 模拟持有天数
    };
  }

  /**
   * 计算性能指标
   */
  private calculateMetrics(
    strategyId: string,
    strategyName: string,
    days: number,
    signals: Signal[],
    performances: SignalPerformance[]
  ): PerformanceMetrics {
    const buySignals = signals.filter(s => s.action === 'buy').length;
    const sellSignals = signals.filter(s => s.action === 'sell').length;

    const profitablePerfs = performances.filter(p => p.is_profitable === true);
    const losingPerfs = performances.filter(p => p.is_profitable === false);

    const totalProfit = performances.reduce((sum, p) => sum + (p.profit_pct || 0), 0);
    const avgProfit = performances.length > 0 ? totalProfit / performances.length : 0;

    const avgWin = profitablePerfs.length > 0
      ? profitablePerfs.reduce((sum, p) => sum + (p.profit_pct || 0), 0) / profitablePerfs.length
      : 0;

    const avgLoss = losingPerfs.length > 0
      ? losingPerfs.reduce((sum, p) => sum + (p.profit_pct || 0), 0) / losingPerfs.length
      : 0;

    const winRate = performances.length > 0
      ? (profitablePerfs.length / performances.length) * 100
      : 0;

    // 计算最大回撤
    const maxDrawdown = this.calculateMaxDrawdown(performances);

    // 计算夏普比率
    const sharpeRatio = this.calculateSharpeRatio(performances);

    // 时间范围
    const firstSignal = signals.length > 0 ? signals[0].date : null;
    const lastSignal = signals.length > 0 ? signals[signals.length - 1].date : null;

    return {
      strategy_id: strategyId,
      strategy_name: strategyName,
      period_days: days,
      total_signals: signals.length,
      buy_signals: buySignals,
      sell_signals: sellSignals,
      win_rate: Math.round(winRate * 100) / 100,
      avg_profit_pct: Math.round(avgProfit * 100) / 100,
      total_profit_pct: Math.round(totalProfit * 100) / 100,
      max_drawdown_pct: Math.round(maxDrawdown * 100) / 100,
      sharpe_ratio: sharpeRatio,
      profitable_trades: profitablePerfs.length,
      losing_trades: losingPerfs.length,
      avg_win_pct: Math.round(avgWin * 100) / 100,
      avg_loss_pct: Math.round(avgLoss * 100) / 100,
      first_signal_date: firstSignal,
      last_signal_date: lastSignal
    };
  }

  /**
   * 计算最大回撤
   */
  private calculateMaxDrawdown(performances: SignalPerformance[]): number {
    if (performances.length === 0) return 0;

    let peak = 0;
    let maxDrawdown = 0;
    let cumulative = 0;

    for (const perf of performances) {
      cumulative += perf.profit_pct || 0;

      if (cumulative > peak) {
        peak = cumulative;
      }

      const drawdown = peak - cumulative;
      if (drawdown > maxDrawdown) {
        maxDrawdown = drawdown;
      }
    }

    return maxDrawdown;
  }

  /**
   * 计算夏普比率
   */
  private calculateSharpeRatio(performances: SignalPerformance[]): number | null {
    if (performances.length < 2) return null;

    const returns = performances.map(p => p.profit_pct || 0);
    const avgReturn = returns.reduce((sum, r) => sum + r, 0) / returns.length;

    // 计算标准差
    const variance = returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length;
    const stdDev = Math.sqrt(variance);

    if (stdDev === 0) return null;

    // 假设无风险利率为0
    const sharpe = avgReturn / stdDev;
    return Math.round(sharpe * 100) / 100;
  }

  /**
   * 空指标（无信号时）
   */
  private emptyMetrics(strategyId: string, strategyName: string, days: number): PerformanceMetrics {
    return {
      strategy_id: strategyId,
      strategy_name: strategyName,
      period_days: days,
      total_signals: 0,
      buy_signals: 0,
      sell_signals: 0,
      win_rate: 0,
      avg_profit_pct: 0,
      total_profit_pct: 0,
      max_drawdown_pct: 0,
      sharpe_ratio: null,
      profitable_trades: 0,
      losing_trades: 0,
      avg_win_pct: 0,
      avg_loss_pct: 0,
      first_signal_date: null,
      last_signal_date: null
    };
  }
}
