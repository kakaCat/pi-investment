/**
 * Comparator - 减法器（比较器）
 *
 * 计算目标与实际的差距，产生误差信号
 */

import type { PerformanceGap } from '../../types/evolution.js';

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
