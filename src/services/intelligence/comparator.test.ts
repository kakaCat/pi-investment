import { describe, it, expect } from '@jest/globals';
import { calculateGap, checkTargetRealistic } from './comparator.js';

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
