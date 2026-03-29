import { SignalGenerator } from './signal-generator';
import { QuantStrategy } from './types';

describe('SignalGenerator', () => {
  let generator: SignalGenerator;

  beforeEach(() => {
    generator = new SignalGenerator();
  });

  describe('卖出信号检测', () => {
    it('应该在 RSI > 70 时触发卖出信号', async () => {
      const strategy: QuantStrategy = {
        id: 'test',
        name: 'Test',
        description: 'Test',
        enabled: true,
        created_at: '2026-03-30',
        screening: { filters: {} },
        entry: { conditions: [], logic: 'AND' },
        exit: {
          conditions: [
            { indicator: 'rsi', operator: '>', value: 70, params: {} }
          ]
        },
        position: { max_position_pct: 0.1, max_stocks: 5 }
      };

      const tech = { rsi: 75, ma5: 100, ma20: 95, macd_histogram: 0.1 };
      const result = (generator as any).matchConditions(tech, strategy.exit.conditions, 'OR');

      expect(result).toBe(true);
    });

    it('应该在 RSI < 70 时不触发卖出信号', async () => {
      const strategy: QuantStrategy = {
        id: 'test',
        name: 'Test',
        description: 'Test',
        enabled: true,
        created_at: '2026-03-30',
        screening: { filters: {} },
        entry: { conditions: [], logic: 'AND' },
        exit: {
          conditions: [
            { indicator: 'rsi', operator: '>', value: 70, params: {} }
          ]
        },
        position: { max_position_pct: 0.1, max_stocks: 5 }
      };

      const tech = { rsi: 65, ma5: 100, ma20: 95, macd_histogram: 0.1 };
      const result = (generator as any).matchConditions(tech, strategy.exit.conditions, 'OR');

      expect(result).toBe(false);
    });
  });

  describe('冷启动置信度计算', () => {
    it('应该在 RSI < 30 时给予 bonus', () => {
      const tech = { rsi: 25, close: 100, bollinger_lower: 95, bollinger_upper: 105 };
      const conditions = [{ indicator: 'rsi', operator: '<', value: 30, params: {} }];
      const confidence = (generator as any).calculateRuleConfidence(tech, conditions, 'buy');
      expect(confidence).toBeGreaterThanOrEqual(1.0);
    });

    it('应该正确计算匹配条件比例', () => {
      const tech = { rsi: 50, ma5: 100, ma20: 95, macd_histogram: 0.1 };
      const conditions = [
        { indicator: 'rsi', operator: '<', value: 30, params: {} },
        { indicator: 'ma_cross', operator: 'cross_above', value: 0, params: {} },
        { indicator: 'macd', operator: '>', value: 0, params: {} }
      ];
      const confidence = (generator as any).calculateRuleConfidence(tech, conditions, 'buy');
      expect(confidence).toBeCloseTo(0.67, 2);
    });
  });

  describe('边界条件处理', () => {
    it('应该处理 RSI 为 null', () => {
      const tech = { rsi: null };
      const condition = { indicator: 'rsi', operator: '<', value: 30, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(false);
    });

    it('应该处理布林带为 0', () => {
      const tech = { close: 100, bollinger_lower: 0, bollinger_upper: 0 };
      const condition = { indicator: 'bollinger', operator: 'touch_lower', value: 0, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(false);
    });
  });
});
