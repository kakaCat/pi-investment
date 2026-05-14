import { describe, it, expect } from '@jest/globals';
import { calculateGap } from './comparator.js';

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
