/**
 * SignalArbiter 单元测试
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { SignalArbiter, ArbiterConfig } from './signal-arbiter.js';
import { Signal, SignalActionType } from './types.js';

describe('SignalArbiter', () => {
  let arbiter: SignalArbiter;

  beforeEach(() => {
    arbiter = new SignalArbiter();
  });

  // 辅助函数：创建测试信号
  const createSignal = (
    symbol: string,
    action: 'buy' | 'sell',
    confidence: number,
    strategyId: string = 'test_strategy'
  ): Signal => ({
    date: '2026-05-19',
    symbol,
    name: `股票${symbol}`,
    action,
    action_type: action === 'buy' ? SignalActionType.BUY : SignalActionType.SELL,
    strategy_id: strategyId,
    price: 100,
    reason: `${action} signal`,
    confidence,
  });

  describe('无冲突场景', () => {
    it('应该保留所有买入信号（无卖出信号）', () => {
      const signals = [
        createSignal('000001', 'buy', 0.8),
        createSignal('000002', 'buy', 0.7),
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(2);
      expect(result.conflicts).toHaveLength(0);
      expect(result.stats.conflictsDetected).toBe(0);
      expect(result.stats.totalOutput).toBe(2);
    });

    it('应该保留所有卖出信号（无买入信号）', () => {
      const signals = [
        createSignal('000001', 'sell', 0.8),
        createSignal('000002', 'sell', 0.7),
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(2);
      expect(result.conflicts).toHaveLength(0);
      expect(result.stats.conflictsDetected).toBe(0);
    });

    it('应该保留不同股票的买入和卖出信号', () => {
      const signals = [
        createSignal('000001', 'buy', 0.8),
        createSignal('000002', 'sell', 0.7),
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(2);
      expect(result.conflicts).toHaveLength(0);
      expect(result.stats.conflictsDetected).toBe(0);
    });
  });

  describe('冲突场景 - keep_highest 模式', () => {
    beforeEach(() => {
      arbiter = new SignalArbiter({ mode: 'keep_highest', confidenceGapThreshold: 0.15 });
    });

    it('应该保留置信度更高的买入信号', () => {
      const signals = [
        createSignal('000001', 'buy', 0.8, 'strategy_a'),
        createSignal('000001', 'sell', 0.5, 'strategy_b'),
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(1);
      expect(result.signals[0].action).toBe('buy');
      expect(result.conflicts).toHaveLength(1);
      expect(result.conflicts[0].resolution).toBe('kept_buy');
      expect(result.stats.conflictsDetected).toBe(1);
      expect(result.stats.signalsDiscarded).toBe(1);
    });

    it('应该保留置信度更高的卖出信号', () => {
      const signals = [
        createSignal('000001', 'buy', 0.5, 'strategy_a'),
        createSignal('000001', 'sell', 0.8, 'strategy_b'),
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(1);
      expect(result.signals[0].action).toBe('sell');
      expect(result.conflicts[0].resolution).toBe('kept_sell');
    });

    it('应该丢弃置信度差距过小的信号', () => {
      const signals = [
        createSignal('000001', 'buy', 0.65, 'strategy_a'),
        createSignal('000001', 'sell', 0.60, 'strategy_b'),
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(0);
      expect(result.conflicts[0].resolution).toBe('discarded_both');
      expect(result.stats.signalsDiscarded).toBe(2);
    });

    it('应该处理多个策略产生的冲突信号', () => {
      const signals = [
        createSignal('000001', 'buy', 0.7, 'strategy_a'),
        createSignal('000001', 'buy', 0.6, 'strategy_b'),
        createSignal('000001', 'sell', 0.5, 'strategy_c'),
      ];

      const result = arbiter.arbitrate(signals);

      // 应该保留最高置信度的买入信号
      expect(result.signals).toHaveLength(1);
      expect(result.signals[0].action).toBe('buy');
      expect(result.signals[0].confidence).toBe(0.7);
    });
  });

  describe('冲突场景 - downgrade_both 模式', () => {
    beforeEach(() => {
      arbiter = new SignalArbiter({ mode: 'downgrade_both', downgradeFactor: 0.5 });
    });

    it('应该降低所有冲突信号的置信度', () => {
      const signals = [
        createSignal('000001', 'buy', 0.8, 'strategy_a'),
        createSignal('000001', 'sell', 0.7, 'strategy_b'),
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(2);
      expect(result.signals[0].confidence).toBe(0.4); // 0.8 * 0.5
      expect(result.signals[1].confidence).toBe(0.35); // 0.7 * 0.5
      expect(result.conflicts[0].resolution).toBe('downgraded_both');
      expect(result.stats.signalsDowngraded).toBe(2);
    });

    it('应该在原因中标注降级', () => {
      const signals = [
        createSignal('000001', 'buy', 0.8, 'strategy_a'),
        createSignal('000001', 'sell', 0.7, 'strategy_b'),
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals[0].reason).toContain('[冲突降级]');
      expect(result.signals[1].reason).toContain('[冲突降级]');
    });
  });

  describe('冲突场景 - discard_both 模式', () => {
    beforeEach(() => {
      arbiter = new SignalArbiter({ mode: 'discard_both' });
    });

    it('应该丢弃所有冲突信号', () => {
      const signals = [
        createSignal('000001', 'buy', 0.8, 'strategy_a'),
        createSignal('000001', 'sell', 0.7, 'strategy_b'),
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(0);
      expect(result.conflicts[0].resolution).toBe('discarded_both');
      expect(result.stats.signalsDiscarded).toBe(2);
    });
  });

  describe('冲突场景 - weighted 模式', () => {
    beforeEach(() => {
      arbiter = new SignalArbiter({
        mode: 'weighted',
        strategyWeights: {
          strategy_high: 2.0,
          strategy_medium: 1.0,
          strategy_low: 0.5,
        },
        confidenceGapThreshold: 0.15,
      });
    });

    it('应该根据策略权重裁决', () => {
      const signals = [
        createSignal('000001', 'buy', 0.6, 'strategy_high'), // 加权得分: 0.6 * 2.0 = 1.2
        createSignal('000001', 'sell', 0.8, 'strategy_low'), // 加权得分: 0.8 * 0.5 = 0.4
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(1);
      expect(result.signals[0].action).toBe('buy');
      expect(result.conflicts[0].resolution).toBe('kept_buy');
    });

    it('应该累加同方向多个策略的权重', () => {
      const signals = [
        createSignal('000001', 'buy', 0.5, 'strategy_medium'), // 0.5 * 1.0 = 0.5
        createSignal('000001', 'buy', 0.5, 'strategy_low'),    // 0.5 * 0.5 = 0.25
        // 买入总分: 0.75
        createSignal('000001', 'sell', 0.6, 'strategy_medium'), // 0.6 * 1.0 = 0.6
        // 卖出总分: 0.6
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(2);
      expect(result.signals.every(s => s.action === 'buy')).toBe(true);
      expect(result.conflicts[0].resolution).toBe('kept_buy');
    });

    it('应该丢弃加权得分差距过小的信号', () => {
      const signals = [
        createSignal('000001', 'buy', 0.6, 'strategy_medium'),  // 0.6 * 1.0 = 0.6
        createSignal('000001', 'sell', 0.55, 'strategy_medium'), // 0.55 * 1.0 = 0.55
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(0);
      expect(result.conflicts[0].resolution).toBe('discarded_both');
    });
  });

  describe('多股票混合场景', () => {
    it('应该正确处理多个股票的混合信号', () => {
      const signals = [
        // 000001: 冲突，买入置信度高
        createSignal('000001', 'buy', 0.8),
        createSignal('000001', 'sell', 0.5),
        // 000002: 无冲突，只有买入
        createSignal('000002', 'buy', 0.7),
        // 000003: 冲突，卖出置信度高
        createSignal('000003', 'buy', 0.4),
        createSignal('000003', 'sell', 0.9),
        // 000004: 无冲突，只有卖出
        createSignal('000004', 'sell', 0.6),
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(4);
      expect(result.conflicts).toHaveLength(2);
      expect(result.stats.conflictsDetected).toBe(2);
      expect(result.stats.signalsDiscarded).toBe(2);

      // 验证每个股票的结果
      const signal000001 = result.signals.find(s => s.symbol === '000001');
      expect(signal000001?.action).toBe('buy');

      const signal000002 = result.signals.find(s => s.symbol === '000002');
      expect(signal000002?.action).toBe('buy');

      const signal000003 = result.signals.find(s => s.symbol === '000003');
      expect(signal000003?.action).toBe('sell');

      const signal000004 = result.signals.find(s => s.symbol === '000004');
      expect(signal000004?.action).toBe('sell');
    });
  });

  describe('冲突历史和统计', () => {
    it('应该记录冲突历史', () => {
      const signals = [
        createSignal('000001', 'buy', 0.8),
        createSignal('000001', 'sell', 0.5),
      ];

      arbiter.arbitrate(signals);

      const history = arbiter.getConflictHistory();
      expect(history).toHaveLength(1);
      expect(history[0].symbol).toBe('000001');
    });

    it('应该累积多次裁决的冲突历史', () => {
      const signals1 = [
        createSignal('000001', 'buy', 0.8),
        createSignal('000001', 'sell', 0.5),
      ];

      const signals2 = [
        createSignal('000002', 'buy', 0.6),
        createSignal('000002', 'sell', 0.7),
      ];

      arbiter.arbitrate(signals1);
      arbiter.arbitrate(signals2);

      const history = arbiter.getConflictHistory();
      expect(history).toHaveLength(2);
    });

    it('应该提供冲突统计', () => {
      const signals = [
        createSignal('000001', 'buy', 0.8),
        createSignal('000001', 'sell', 0.5),
        createSignal('000002', 'buy', 0.4),
        createSignal('000002', 'sell', 0.8),
      ];

      arbiter.arbitrate(signals);

      const stats = arbiter.getConflictStats();
      expect(stats.totalConflicts).toBe(2);
      expect(stats.resolutionBreakdown.kept_buy).toBe(1);
      expect(stats.resolutionBreakdown.kept_sell).toBe(1);
      expect(stats.topConflictSymbols).toHaveLength(2);
    });

    it('应该能清空冲突历史', () => {
      const signals = [
        createSignal('000001', 'buy', 0.8),
        createSignal('000001', 'sell', 0.5),
      ];

      arbiter.arbitrate(signals);
      expect(arbiter.getConflictHistory()).toHaveLength(1);

      arbiter.clearConflictHistory();
      expect(arbiter.getConflictHistory()).toHaveLength(0);
    });
  });

  describe('边界情况', () => {
    it('应该处理空信号列表', () => {
      const result = arbiter.arbitrate([]);

      expect(result.signals).toHaveLength(0);
      expect(result.conflicts).toHaveLength(0);
      expect(result.stats.totalInput).toBe(0);
      expect(result.stats.totalOutput).toBe(0);
    });

    it('应该处理置信度为0的信号', () => {
      const signals = [
        createSignal('000001', 'buy', 0),
        createSignal('000001', 'sell', 0.5),
      ];

      const result = arbiter.arbitrate(signals);

      expect(result.signals).toHaveLength(1);
      expect(result.signals[0].action).toBe('sell');
    });

    it('应该处理置信度相等的信号', () => {
      arbiter = new SignalArbiter({ mode: 'keep_highest', confidenceGapThreshold: 0.01 });

      const signals = [
        createSignal('000001', 'buy', 0.7),
        createSignal('000001', 'sell', 0.7),
      ];

      const result = arbiter.arbitrate(signals);

      // 置信度相等，差距为0，小于阈值，应该丢弃
      expect(result.signals).toHaveLength(0);
      expect(result.conflicts[0].resolution).toBe('discarded_both');
    });
  });
});
