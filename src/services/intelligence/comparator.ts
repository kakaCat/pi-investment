/**
 * Comparator - 减法器（比较器）
 *
 * 计算目标与实际的差距，产生误差信号
 */

import type { PerformanceGap, TargetRealisticCheck, CapabilityCheck, DecisionQualityMetrics, AttributionResult } from '../../types/evolution.js';

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

  // 检查2：对比历史平均（仅当历史收益为正时有意义）
  const avgHistorical = historicalReturns.reduce((a, b) => a + b, 0) / historicalReturns.length;
  if (avgHistorical > 0 && target > avgHistorical * 2) {
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

/**
 * 计算趋势
 */
function calculateTrend(returns: number[]): 'rising' | 'stable' | 'declining' {
  if (returns.length < 2) return 'stable';

  let ups = 0;
  let downs = 0;

  for (let i = 1; i < returns.length; i++) {
    if (returns[i] > returns[i - 1]) ups++;
    else if (returns[i] < returns[i - 1]) downs++;
  }

  if (downs > ups) return 'declining';
  if (ups > downs) return 'rising';
  return 'stable';
}

/**
 * 评估 Agent 能力
 */
export function evaluateAgentCapability(
  actual: number,
  market: number,
  alpha: number,
  decisionQuality: DecisionQualityMetrics
): CapabilityCheck {
  const reasons: string[] = [];
  const weaknesses: string[] = [];
  let capable = true;

  // 检查1：对比大盘
  if (alpha < -2) {
    capable = false;
    reasons.push(`跑输大盘${Math.abs(alpha).toFixed(1)}%`);
    weaknesses.push('选股能力');
  }

  // 检查2：趋势分析
  const trend = calculateTrend(decisionQuality.recentReturns);
  if (trend === 'declining') {
    capable = false;
    reasons.push('收益率持续下降');
    weaknesses.push('整体策略');
  }

  // 检查3：决策质量
  if (decisionQuality.errorRate > 0.4) {
    capable = false;
    reasons.push(`决策错误率${(decisionQuality.errorRate * 100).toFixed(0)}%过高`);
    weaknesses.push('决策准确性');
  }

  // 检查4：止损执行
  if (decisionQuality.stopLossExecutionRate < 0.6) {
    capable = false;
    reasons.push('止损执行率不足60%');
    weaknesses.push('风控能力');
  }

  return { capable, reasons, weaknesses };
}

/**
 * 归因分析：判断差距的根本原因
 */
export function attributeGap(
  gap: PerformanceGap,
  historicalReturns: number[],
  marketVolatility: number,
  decisionQuality: DecisionQualityMetrics
): AttributionResult {
  // 1. 目标合理性检查
  const targetCheck = checkTargetRealistic(
    gap.target,
    gap.market,
    historicalReturns,
    marketVolatility
  );

  // 2. Agent 能力评估
  const capabilityCheck = evaluateAgentCapability(
    gap.actual,
    gap.market,
    gap.alpha,
    decisionQuality
  );

  // 3. 综合判断
  if (!targetCheck.realistic && capabilityCheck.capable) {
    // 目标不合理，但能力正常
    return {
      rootCause: 'target_unrealistic',
      confidence: 0.85,
      reasons: targetCheck.reasons,
      recommendation: 'adjust_target',
      suggestedTarget: targetCheck.suggestedTarget
    };
  }

  if (targetCheck.realistic && !capabilityCheck.capable) {
    // 目标合理，但能力不足
    return {
      rootCause: 'capability_insufficient',
      confidence: 0.90,
      reasons: capabilityCheck.reasons,
      recommendation: 'trigger_optimizer'
    };
  }

  // 4. 混合情况：目标略高 + 能力略弱
  // 优先归因为能力问题，因为提升能力比调整目标更有价值
  return {
    rootCause: 'capability_insufficient',
    confidence: 0.60,
    reasons: [...targetCheck.reasons, ...capabilityCheck.reasons],
    recommendation: 'trigger_optimizer'
  };
}
