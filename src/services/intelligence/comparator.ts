/**
 * Comparator - 减法器（比较器）
 *
 * 计算目标与实际的差距，产生误差信号
 */

import type { PerformanceGap, TargetRealisticCheck } from '../../types/evolution.js';

/**
 * 计算性能差距
 */
export function calculateGap(
  target: number,
  actual: number,
  market: number
): PerformanceGap {
  return {
    target,
    actual,
    gap: target - actual,
    market,
    alpha: actual - market
  };
}

/**
 * 检查目标是否合理
 */
export function checkTargetRealistic(
  target: number,
  market: number,
  historicalReturns: number[],
  marketVolatility: number
): TargetRealisticCheck {
  const reasons: string[] = [];
  let realistic = true;

  // 检查1：对比大盘
  const vsMarket = target - market;
  if (vsMarket > 10) {
    realistic = false;
    reasons.push(`目标超出大盘${vsMarket.toFixed(1)}%，过于激进`);
  }

  // 检查2：对比历史平均
  const avgHistorical = historicalReturns.reduce((a, b) => a + b, 0) / historicalReturns.length;
  if (target > avgHistorical * 2) {
    realistic = false;
    reasons.push(`目标是历史平均的${(target / avgHistorical).toFixed(1)}倍，不现实`);
  }

  // 检查3：对比市场波动率
  if (target > marketVolatility * 3) {
    realistic = false;
    reasons.push(`目标超出市场波动率的3倍，风险过高`);
  }

  // 建议目标
  const suggestedTarget = realistic ? undefined : market + 1.5;

  return { realistic, reasons, suggestedTarget };
}
