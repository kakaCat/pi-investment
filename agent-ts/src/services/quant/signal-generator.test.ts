import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { SignalGenerator } from './signal-generator.js';
import { QuantStrategy, SignalActionType } from './types.js';
// @ts-ignore - Module stub needed
import { FactorLibrary } from './factor-library.js';
// @ts-ignore - Module stub needed
import type { TechnicalIndicators } from './factor-library.js';
import fs from 'fs/promises';

function tech(overrides: Partial<TechnicalIndicators> = {}): TechnicalIndicators {
  return {
    rsi: 50,
    ma5: 100,
    ma10: 100,
    ma20: 100,
    ma60: 100,
    macd_dif: 0,
    macd_dea: 0,
    macd_histogram: 0,
    bollinger_upper: 110,
    bollinger_mid: 100,
    bollinger_lower: 90,
    volume_ratio: 1,
    atr: 1,
    pe: 15,
    pb: 1.5,
    roe: 0.12,
    gross_margin: 0.35,
    debt_ratio: 0.45,
    ...overrides,
  };
}

describe('SignalGenerator', () => {
  const testDir = '.pi-invest-test/quant/signals';
  let generator: SignalGenerator;
  let factorLib: FactorLibrary;

  beforeEach(async () => {
    factorLib = new FactorLibrary();
    generator = new SignalGenerator(testDir, factorLib);
    await fs.mkdir(testDir, { recursive: true });
  });

  afterEach(async () => {
    await fs.rm('.pi-invest-test', { recursive: true, force: true });
  });

  describe('Condition Matching', () => {
    it('should match RSI < 30 condition (oversold)', () => {
      const tech = { rsi: 25, ma5: 100, ma20: 95, ma60: 90, macd_histogram: 0.1 };
      const condition = { indicator: 'rsi' as const, operator: '<' as const, value: 30, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(true);
    });

    it('should not match RSI < 30 when RSI is 50', () => {
      const tech = { rsi: 50, ma5: 100, ma20: 95, ma60: 90, macd_histogram: 0.1 };
      const condition = { indicator: 'rsi' as const, operator: '<' as const, value: 30, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(false);
    });

    it('should match RSI > 70 condition (overbought)', () => {
      const tech = { rsi: 75, ma5: 100, ma20: 95, ma60: 90, macd_histogram: 0.1 };
      const condition = { indicator: 'rsi' as const, operator: '>' as const, value: 70, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(true);
    });

    it('should match MA golden cross (MA5 > MA20)', () => {
      const tech = { rsi: 50, ma5: 105, ma20: 100, ma60: 95, macd_histogram: 0 };
      const condition = { indicator: 'ma_cross' as const, operator: 'cross_above' as const, value: 0, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(true);
    });

    it('should match MA death cross (MA5 < MA20)', () => {
      const tech = { rsi: 50, ma5: 95, ma20: 100, ma60: 105, macd_histogram: 0 };
      const condition = { indicator: 'ma_cross' as const, operator: 'cross_below' as const, value: 0, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(true);
    });

    it('should match MACD golden cross (histogram > 0)', () => {
      const tech = { rsi: 50, ma5: 100, ma20: 100, ma60: 100, macd_histogram: 0.5 };
      const condition = { indicator: 'macd' as const, operator: 'golden_cross' as const, value: 0, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(true);
    });

    it('should match MACD death cross (histogram < 0)', () => {
      const tech = { rsi: 50, ma5: 100, ma20: 100, ma60: 100, macd_histogram: -0.5 };
      const condition = { indicator: 'macd' as const, operator: 'death_cross' as const, value: 0, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(true);
    });

    it('should match Bollinger lower band touch', () => {
      const tech = {
        rsi: 50,
        ma5: 100,
        ma20: 100,
        ma60: 100,
        macd_histogram: 0,
        close: 90.5,
        bollinger_upper: 110,
        bollinger_lower: 90
      };
      const condition = { indicator: 'bollinger' as const, operator: 'touch_lower' as const, value: 0, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(true);
    });

    it('should match Bollinger upper band breakout', () => {
      const tech = {
        rsi: 50,
        ma5: 100,
        ma20: 100,
        ma60: 100,
        macd_histogram: 0,
        close: 111,
        bollinger_upper: 110,
        bollinger_lower: 90
      };
      const condition = { indicator: 'bollinger' as const, operator: 'break_upper' as const, value: 0, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(true);
    });

    it('should match volume surge condition', () => {
      const tech = {
        rsi: 50,
        ma5: 100,
        ma20: 100,
        ma60: 100,
        macd_histogram: 0,
        volume_ratio: 2.5
      };
      const condition = { indicator: 'volume' as const, operator: '>' as const, value: 2, params: {} };
      const result = (generator as any).matchCondition(tech, condition);
      expect(result).toBe(true);
    });
  });

  describe('Multiple Conditions Logic', () => {
    it('should match AND logic when all conditions are true', () => {
      const tech = {
        rsi: 25,
        ma5: 105,
        ma20: 100,
        ma60: 95,
        macd_histogram: 0.5,
        volume_ratio: 2.0
      };
      const conditions = [
        { indicator: 'rsi' as const, operator: '<' as const, value: 30, params: {} },
        { indicator: 'ma_cross' as const, operator: 'cross_above' as const, value: 0, params: {} },
        { indicator: 'macd' as const, operator: 'golden_cross' as const, value: 0, params: {} }
      ];
      const result = (generator as any).matchConditions(tech, conditions, 'AND');
      expect(result).toBe(true);
    });

    it('should not match AND logic when one condition is false', () => {
      const tech = {
        rsi: 50, // This fails the RSI < 30 condition
        ma5: 105,
        ma20: 100,
        ma60: 95,
        macd_histogram: 0.5
      };
      const conditions = [
        { indicator: 'rsi' as const, operator: '<' as const, value: 30, params: {} },
        { indicator: 'ma_cross' as const, operator: 'cross_above' as const, value: 0, params: {} }
      ];
      const result = (generator as any).matchConditions(tech, conditions, 'AND');
      expect(result).toBe(false);
    });

    it('should match OR logic when at least one condition is true', () => {
      const tech = {
        rsi: 50, // Fails RSI condition
        ma5: 105, // Passes MA cross condition
        ma20: 100,
        ma60: 95,
        macd_histogram: 0.5
      };
      const conditions = [
        { indicator: 'rsi' as const, operator: '<' as const, value: 30, params: {} },
        { indicator: 'ma_cross' as const, operator: 'cross_above' as const, value: 0, params: {} }
      ];
      const result = (generator as any).matchConditions(tech, conditions, 'OR');
      expect(result).toBe(true);
    });

    it('should not match OR logic when all conditions are false', () => {
      const tech = {
        rsi: 50,
        ma5: 95, // MA5 < MA20 (no golden cross)
        ma20: 100,
        ma60: 105,
        macd_histogram: -0.5
      };
      const conditions = [
        { indicator: 'rsi' as const, operator: '<' as const, value: 30, params: {} },
        { indicator: 'ma_cross' as const, operator: 'cross_above' as const, value: 0, params: {} }
      ];
      const result = (generator as any).matchConditions(tech, conditions, 'OR');
      expect(result).toBe(false);
    });
  });

  describe('Signal Generation', () => {
    it('should generate buy signal when conditions match', async () => {
      const strategy: QuantStrategy = {
        id: 'test_strategy',
        name: 'RSI Oversold Strategy',
        description: 'Buy when RSI < 30 and MA golden cross',
        enabled: true,
        created_at: new Date().toISOString(),
        screening: { market: 'A', filters: {} },
        entry: {
          conditions: [
            { indicator: 'rsi', operator: '<', value: 30, params: {} },
            { indicator: 'ma_cross', operator: 'cross_above', value: 0, params: {} }
          ],
          logic: 'AND'
        },
        exit: {
          stop_loss: 0.05,
          take_profit: 0.15,
          conditions: []
        },
        position: {
          max_position_pct: 0.2,
          max_stocks: 10
        }
      };

      const tech = {
        rsi: 25,
        ma5: 105,
        ma10: 103,
        ma20: 100,
        ma60: 95,
        macd_dif: 0.5,
        macd_dea: 0.3,
        macd_histogram: 0.2,
        bollinger_upper: 110,
        bollinger_mid: 100,
        bollinger_lower: 90,
        volume_ratio: 2.0,
        atr: 1.5,
      pe: 0,
      pb: 0,
      roe: 0,
      gross_margin: 0,
        debt_ratio: 0
      };

      const signal = await generator.generateSignal('000001', '平安银行', strategy, tech, 102);

      expect(signal).not.toBeNull();
      expect(signal!.action).toBe('buy');
      expect(signal!.symbol).toBe('000001');
      expect(signal!.name).toBe('平安银行');
      expect(signal!.price).toBe(102);
      expect(signal!.strategy_id).toBe('test_strategy');
      expect(signal!.confidence).toBeGreaterThan(0);
      expect(signal!.confidence).toBeLessThanOrEqual(1);
      expect(signal!.reason).toContain('RSI');
      expect(signal!.indicators).toEqual(tech);
    });

    it('should return null when conditions do not match', async () => {
      const strategy: QuantStrategy = {
        id: 'test_strategy',
        name: 'RSI Oversold Strategy',
        description: 'Buy when RSI < 30',
        enabled: true,
        created_at: new Date().toISOString(),
        screening: { market: 'A', filters: {} },
        entry: {
          conditions: [
            { indicator: 'rsi', operator: '<', value: 30, params: {} }
          ],
          logic: 'AND'
        },
        exit: {
          stop_loss: 0.05,
          take_profit: 0.1,
          conditions: []
        },
        position: {
          max_position_pct: 0.2,
          max_stocks: 10
        }
      };

      const tech = {
        rsi: 65, // Does not meet RSI < 30
        ma5: 100,
        ma10: 100,
        ma20: 95,
        ma60: 90,
        macd_dif: 0.5,
        macd_dea: 0.3,
        macd_histogram: 0.1,
        bollinger_upper: 110,
        bollinger_mid: 100,
        bollinger_lower: 90,
        volume_ratio: 1.0,
        atr: 1.5,
      pe: 0,
      pb: 0,
      roe: 0,
      gross_margin: 0,
        debt_ratio: 0
      };

      const signal = await generator.generateSignal('000001', '平安银行', strategy, tech, 102);
      expect(signal).toBeNull();
    });

    it('should generate sell signal when exit conditions match', async () => {
      const strategy: QuantStrategy = {
        id: 'test_strategy',
        name: 'RSI Overbought Strategy',
        description: 'Sell when RSI > 70',
        enabled: true,
        created_at: new Date().toISOString(),
        screening: { market: 'A', filters: {} },
        entry: {
          conditions: [
            { indicator: 'rsi', operator: '>', value: 70, params: {} }
          ],
          logic: 'AND'
        },
        exit: {
          stop_loss: 0.05,
          take_profit: 0.1,
          conditions: []
        },
        position: {
          max_position_pct: 0.2,
          max_stocks: 10
        }
      };

      const tech = {
        rsi: 75,
        ma5: 100,
        ma10: 100,
        ma20: 95,
        ma60: 90,
        macd_dif: 0.5,
        macd_dea: 0.3,
        macd_histogram: 0.1,
        bollinger_upper: 110,
        bollinger_mid: 100,
        bollinger_lower: 90,
        volume_ratio: 1.0,
        atr: 1.5,
      pe: 0,
      pb: 0,
      roe: 0,
      gross_margin: 0,
        debt_ratio: 0
      };

      const signal = await generator.generateSignal('000001', '平安银行', strategy, tech, 102);

      expect(signal).not.toBeNull();
      expect(signal!.action).toBe('sell');
    });
  });

  describe('Confidence Scoring', () => {
    it('should calculate high confidence for strong buy signals', () => {
      const signal = {
        date: '2024-01-01',
        symbol: '000001',
        name: '平安银行',
        action: 'buy' as const,
        strategy_id: 'test',
        price: 100,
        reason: 'RSI=25, MA5>MA20, MACD>0',
        confidence: 0.5,
        indicators: {
          rsi: 25,
          ma5: 105,
          ma10: 103,
          ma20: 100,
          ma60: 95,
          macd_dif: 0.5,
          macd_dea: 0.3,
          macd_histogram: 0.5,
          bollinger_upper: 110,
          bollinger_mid: 100,
          bollinger_lower: 90,
          volume_ratio: 2.5,
          atr: 1.5
        }
      };

      const confidence = (generator as any).calculateConfidence(signal.indicators, signal.action);
      expect(confidence).toBeGreaterThan(0.7); // Strong signal
    });

    it('should calculate medium confidence for moderate signals', () => {
      const signal = {
        date: '2024-01-01',
        symbol: '000001',
        name: '平安银行',
        action: 'buy' as const,
        strategy_id: 'test',
        price: 100,
        reason: 'RSI=45',
        confidence: 0.5,
        indicators: {
          rsi: 45,
          ma5: 100,
          ma10: 100,
          ma20: 100,
          ma60: 100,
          macd_dif: 0,
          macd_dea: 0,
          macd_histogram: 0,
          bollinger_upper: 110,
          bollinger_mid: 100,
          bollinger_lower: 90,
          volume_ratio: 1.0,
          atr: 1.5
        }
      };

      const confidence = (generator as any).calculateConfidence(signal.indicators, signal.action);
      expect(confidence).toBeGreaterThan(0.3);
      expect(confidence).toBeLessThan(0.7);
    });

    it('should calculate high confidence for strong sell signals', () => {
      const signal = {
        date: '2024-01-01',
        symbol: '000001',
        name: '平安银行',
        action: 'sell' as const,
        strategy_id: 'test',
        price: 100,
        reason: 'RSI=75',
        confidence: 0.5,
        indicators: {
          rsi: 75,
          ma5: 95,
          ma10: 97,
          ma20: 100,
          ma60: 105,
          macd_dif: -0.5,
          macd_dea: -0.3,
          macd_histogram: -0.5,
          bollinger_upper: 110,
          bollinger_mid: 100,
          bollinger_lower: 90,
          volume_ratio: 0.5,
          atr: 1.5
        }
      };

      const confidence = (generator as any).calculateConfidence(signal.indicators, signal.action);
      expect(confidence).toBeGreaterThan(0.7);
    });
  });

  describe('Batch Signal Generation', () => {
    it('should scan multiple stocks and return matching signals', async () => {
      const strategy: QuantStrategy = {
        id: 'test_strategy',
        name: 'RSI Strategy',
        description: 'Buy when RSI < 30',
        enabled: true,
        created_at: new Date().toISOString(),
        screening: { market: 'A', filters: {} },
        entry: {
          conditions: [
            { indicator: 'rsi', operator: '<', value: 30, params: {} }
          ],
          logic: 'AND'
        },
        exit: {
          stop_loss: 0.05,
          take_profit: 0.1,
          conditions: []
        },
        position: {
          max_position_pct: 0.2,
          max_stocks: 10
        }
      };

      const stockData = [
        {
          symbol: '000001',
          name: '平安银行',
          price: 10.5,
          tech: tech({
            rsi: 25,
            ma5: 105,
            ma10: 103,
            ma20: 100,
            ma60: 95,
            macd_dif: 0.5,
            macd_dea: 0.3,
            macd_histogram: 0.2,
            bollinger_upper: 110,
            bollinger_mid: 100,
            bollinger_lower: 90,
            volume_ratio: 2.0,
            atr: 1.5
          })
        },
        {
          symbol: '000002',
          name: '万科A',
          price: 8.5,
          tech: tech({
            rsi: 65, // Does not match
            ma5: 100,
            ma10: 100,
            ma20: 95,
            ma60: 90,
            macd_dif: 0.5,
            macd_dea: 0.3,
            macd_histogram: 0.1,
            bollinger_upper: 110,
            bollinger_mid: 100,
            bollinger_lower: 90,
            volume_ratio: 1.0,
            atr: 1.5
          })
        },
        {
          symbol: '600000',
          name: '浦发银行',
          price: 7.8,
          tech: tech({
            rsi: 28,
            ma5: 102,
            ma10: 100,
            ma20: 98,
            ma60: 95,
            macd_dif: 0.3,
            macd_dea: 0.2,
            macd_histogram: 0.1,
            bollinger_upper: 105,
            bollinger_mid: 98,
            bollinger_lower: 91,
            volume_ratio: 1.5,
            atr: 1.2
          })
        }
      ];

      const signals = await generator.scanMarket(strategy, stockData);

      expect(signals).toHaveLength(2); // Only 000001 and 600000 match
      expect(signals[0].symbol).toBe('000001');
      expect(signals[1].symbol).toBe('600000');
      expect(signals.every((s: any) => s.action === 'buy')).toBe(true);
    });

    it('should filter signals by confidence threshold', async () => {
      const strategy: QuantStrategy = {
        id: 'test_strategy',
        name: 'High Confidence Strategy',
        description: 'Only high confidence signals',
        enabled: true,
        created_at: new Date().toISOString(),
        screening: { market: 'A', filters: {} },
        entry: {
          conditions: [
            { indicator: 'rsi', operator: '<', value: 50, params: {} }
          ],
          logic: 'AND'
        },
        exit: {
          stop_loss: 0.05,
          take_profit: 0.1,
          conditions: []
        },
        position: {
          max_position_pct: 0.2,
          max_stocks: 10
        }
      };

      const stockData = [
        {
          symbol: '000001',
          name: '平安银行',
          price: 10.5,
          tech: tech({
            rsi: 25, // Strong signal
            ma5: 105,
            ma10: 103,
            ma20: 100,
            ma60: 95,
            macd_dif: 0.5,
            macd_dea: 0.3,
            macd_histogram: 0.5,
            bollinger_upper: 110,
            bollinger_mid: 100,
            bollinger_lower: 90,
            volume_ratio: 2.5,
            atr: 1.5
          })
        },
        {
          symbol: '000002',
          name: '万科A',
          price: 8.5,
          tech: tech({
            rsi: 48, // Weak signal
            ma5: 100,
            ma10: 100,
            ma20: 100,
            ma60: 100,
            macd_dif: 0,
            macd_dea: 0,
            macd_histogram: 0,
            bollinger_upper: 110,
            bollinger_mid: 100,
            bollinger_lower: 90,
            volume_ratio: 1.0,
            atr: 1.5
          })
        }
      ];

      const signals = await generator.scanMarket(strategy, stockData, 0.6);

      expect(signals.length).toBeLessThanOrEqual(1); // Only strong signals pass
      if (signals.length > 0) {
        expect(signals[0].confidence).toBeGreaterThanOrEqual(0.6);
      }
    });
  });

  describe('Signal Persistence', () => {
    it('should save signals to file', async () => {
      const signals = [
        {
          date: '2024-01-01',
          symbol: '000001',
          name: '平安银行',
          action: 'buy' as const,
          action_type: SignalActionType.BUY,
          strategy_id: 'test',
          price: 10.5,
          reason: 'RSI < 30',
          confidence: 0.75,
          indicators: {}
        }
      ];

      await generator.saveSignals('2024-01-01', signals);

      const loaded = await generator.loadSignals('2024-01-01');
      expect(loaded).toHaveLength(1);
      expect(loaded[0].symbol).toBe('000001');
      expect(loaded[0].confidence).toBe(0.75);
    });

    it('should return empty array for non-existent date', async () => {
      const loaded = await generator.loadSignals('2099-12-31');
      expect(loaded).toEqual([]);
    });
  });
});
