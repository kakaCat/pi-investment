import { describe, it, expect } from '@jest/globals';
import { calculateGap, checkTargetRealistic, evaluateAgentCapability, attributeGap } from './comparator.js';
import type { DecisionQualityMetrics } from '../../types/evolution.js';

describe('Comparator - calculateGap', () => {
  it('应该正确计算性能差距', () => {
    const result = calculateGap(12, 10, 8);

    expect(result.target).toBe(12);
    expect(result.actual).toBe(10);
    expect(result.gap).toBe(2);
    expect(result.market).toBe(8);
    expect(result.alpha).toBe(2);
  });

  it('应该处理负收益', () => {
    const result = calculateGap(5, -3, 2);

    expect(result.gap).toBe(8);
    expect(result.alpha).toBe(-5);
  });

  it('应该处理跑赢大盘的情况', () => {
    const result = calculateGap(10, 12, 8);

    expect(result.gap).toBe(-2); // 超额完成
    expect(result.alpha).toBe(4); // 跑赢大盘4%
  });
});

describe('Comparator - checkTargetRealistic', () => {
  it('应该判断合理的目标', () => {
    const result = checkTargetRealistic(
      10,  // 目标 10%
      8,   // 大盘 8%
      [9, 10, 11],  // 历史平均 10%
      5    // 波动率 5%
    );

    expect(result.realistic).toBe(true);
    expect(result.reasons).toHaveLength(0);
    expect(result.suggestedTarget).toBeUndefined();
  });

  it('应该识别目标超出大盘过多', () => {
    const result = checkTargetRealistic(
      20,  // 目标 20%
      8,   // 大盘 8%
      [9, 10, 11],
      5
    );

    expect(result.realistic).toBe(false);
    expect(result.reasons.some(r => r.includes('目标超出大盘'))).toBe(true);
    expect(result.suggestedTarget).toBeDefined();
  });

  it('应该识别目标超出历史平均过多', () => {
    const result = checkTargetRealistic(
      25,  // 目标 25%
      10,  // 大盘 10%
      [8, 9, 10],  // 历史平均 9%
      10
    );

    expect(result.realistic).toBe(false);
    expect(result.reasons.some(r => r.includes('历史平均'))).toBe(true);
  });

  it('应该识别目标超出波动率过多', () => {
    const result = checkTargetRealistic(
      15,  // 目标 15%
      10,  // 大盘 10%
      [10, 11, 12],
      2    // 波动率 2%
    );

    expect(result.realistic).toBe(false);
    expect(result.reasons.some(r => r.includes('波动率'))).toBe(true);
  });
});

describe('Comparator - evaluateAgentCapability', () => {
  it('应该判断能力正常', () => {
    const metrics: DecisionQualityMetrics = {
      recentReturns: [10, 11, 12],
      errorRate: 0.2,
      stopLossExecutionRate: 0.8
    };

    const result = evaluateAgentCapability(10, 8, 2, metrics);

    expect(result.capable).toBe(true);
    expect(result.reasons).toHaveLength(0);
    expect(result.weaknesses).toHaveLength(0);
  });

  it('应该识别跑输大盘', () => {
    const metrics: DecisionQualityMetrics = {
      recentReturns: [5, 6, 5],
      errorRate: 0.2,
      stopLossExecutionRate: 0.8
    };

    const result = evaluateAgentCapability(5, 8, -3, metrics);

    expect(result.capable).toBe(false);
    expect(result.reasons.some(r => r.includes('跑输大盘'))).toBe(true);
    expect(result.weaknesses).toContain('选股能力');
  });

  it('应该识别收益率下降趋势', () => {
    const metrics: DecisionQualityMetrics = {
      recentReturns: [12, 10, 8],  // 下降趋势
      errorRate: 0.2,
      stopLossExecutionRate: 0.8
    };

    const result = evaluateAgentCapability(8, 7, 1, metrics);

    expect(result.capable).toBe(false);
    expect(result.reasons.some(r => r.includes('持续下降'))).toBe(true);
    expect(result.weaknesses).toContain('整体策略');
  });

  it('应该识别决策错误率过高', () => {
    const metrics: DecisionQualityMetrics = {
      recentReturns: [10, 11, 12],
      errorRate: 0.5,  // 50% 错误率
      stopLossExecutionRate: 0.8
    };

    const result = evaluateAgentCapability(10, 8, 2, metrics);

    expect(result.capable).toBe(false);
    expect(result.reasons.some(r => r.includes('错误率'))).toBe(true);
    expect(result.weaknesses).toContain('决策准确性');
  });

  it('应该识别止损执行率不足', () => {
    const metrics: DecisionQualityMetrics = {
      recentReturns: [10, 11, 12],
      errorRate: 0.2,
      stopLossExecutionRate: 0.5  // 50% 执行率
    };

    const result = evaluateAgentCapability(10, 8, 2, metrics);

    expect(result.capable).toBe(false);
    expect(result.reasons.some(r => r.includes('止损执行率'))).toBe(true);
    expect(result.weaknesses).toContain('风控能力');
  });
});

describe('Comparator - attributeGap', () => {
  it('应该归因为目标不合理', () => {
    const gap = calculateGap(20, 10, 8);
    const metrics: DecisionQualityMetrics = {
      recentReturns: [10, 11, 12],
      errorRate: 0.2,
      stopLossExecutionRate: 0.8
    };

    const result = attributeGap(gap, [9, 10, 11], 3, metrics);

    expect(result.rootCause).toBe('target_unrealistic');
    expect(result.recommendation).toBe('adjust_target');
    expect(result.suggestedTarget).toBeDefined();
  });

  it('应该归因为能力不足', () => {
    const gap = calculateGap(10, 5, 8);
    const metrics: DecisionQualityMetrics = {
      recentReturns: [8, 6, 5],  // 下降趋势
      errorRate: 0.5,  // 高错误率
      stopLossExecutionRate: 0.5  // 低执行率
    };

    const result = attributeGap(gap, [9, 10, 11], 3, metrics);

    expect(result.rootCause).toBe('capability_insufficient');
    expect(result.recommendation).toBe('trigger_optimizer');
  });

  it('应该处理混合情况（目标略高+能力略弱）', () => {
    const gap = calculateGap(12, 9, 8);
    const metrics: DecisionQualityMetrics = {
      recentReturns: [10, 9.5, 9],  // 轻微下降
      errorRate: 0.35,  // 略高
      stopLossExecutionRate: 0.65  // 略低
    };

    const result = attributeGap(gap, [9, 10, 11], 3, metrics);

    expect(result.rootCause).toBe('capability_insufficient');
    expect(result.recommendation).toBe('trigger_optimizer');
    expect(result.confidence).toBeLessThan(0.8);
  });
});
