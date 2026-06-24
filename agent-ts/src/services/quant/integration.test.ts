import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
// @ts-ignore - Module stub needed
import { QuantService } from './quant-service.js';
import { SignalGenerator } from './signal-generator.js';
// @ts-ignore - Module stub needed
import { FactorLibrary } from './factor-library.js';
import fs from 'fs/promises';

describe('Quant System Integration', () => {
  const testDir = '.pi-invest-test';
  let quantService: QuantService;
  let signalGenerator: SignalGenerator;
  let factorLib: FactorLibrary;

  beforeEach(async () => {
    quantService = new QuantService(`${testDir}/quant/strategies`);
    signalGenerator = new SignalGenerator(`${testDir}/quant/signals`, undefined, false); // Disable ML for tests
    factorLib = new FactorLibrary();
    await fs.mkdir(testDir, { recursive: true });
  });

  afterEach(async () => {
    await fs.rm(testDir, { recursive: true, force: true });
  });

  it('should complete full workflow: create strategy -> generate signal -> score stock', async () => {
    // Step 1: Create strategy
    const strategy = await quantService.createStrategy({
      name: 'Integration Test Strategy',
      description: 'RSI超卖策略',
      enabled: true,
      screening: {
        market: 'A',
        filters: { pe_range: [0, 30] }
      },
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
    });

    expect(strategy.id).toBeDefined();
    expect(strategy.enabled).toBe(true);

    // Step 2: Generate signal
    const tech = {
      rsi: 28,
      ma5: 105,
      ma10: 103,
      ma20: 100,
      ma60: 98,
      macd_dif: 0.2,
      macd_dea: 0.1,
      macd_histogram: 0.1,
      bollinger_upper: 110,
      bollinger_mid: 102,
      bollinger_lower: 95,
      volume_ratio: 2.0,
      atr: 1.5,
      pe: 0,
      pb: 0,
      roe: 0,
    gross_margin: 0,
      debt_ratio: 0
    };

    const signal = await signalGenerator.generateSignal(
      '000001',
      '平安银行',
      strategy,
      tech,
      102
    );

    expect(signal).not.toBeNull();
    expect(signal!.action).toBe('buy');
    expect(signal!.confidence).toBeGreaterThan(0);
    expect(signal!.confidence).toBeLessThan(1);

    // Step 3: Score stock
    const score = factorLib.scoreStock(tech, 102);
    expect(score.total_score).toBeGreaterThan(50);
    expect(score.recommendation).toBe('buy');

    // Step 4: List strategies
    const strategies: any[] = await quantService.listStrategies();
    expect(strategies).toHaveLength(1);
    expect(strategies[0].id).toBe(strategy.id);
  });

  it('should handle strategy lifecycle: create -> update -> disable -> enable -> delete', async () => {
    // Create
    const strategy = await quantService.createStrategy({
      name: 'Lifecycle Test',
      description: 'Test strategy lifecycle',
      enabled: true,
      screening: { market: 'A', filters: {} },
      entry: { conditions: [], logic: 'AND' },
      exit: { stop_loss: 0.05, take_profit: 0.1, conditions: [] },
      position: { max_position_pct: 0.15, max_stocks: 5 }
    });

    expect(strategy.enabled).toBe(true);

    // Update
    const updated = await quantService.updateStrategy(strategy.id, {
      description: 'Updated description'
    });
    expect(updated!.description).toBe('Updated description');

    // Disable
    const disabled = await quantService.disableStrategy(strategy.id);
    expect(disabled!.enabled).toBe(false);

    // Enable
    const enabled = await quantService.enableStrategy(strategy.id);
    expect(enabled!.enabled).toBe(true);

    // Delete
    const deleted = await quantService.deleteStrategy(strategy.id);
    expect(deleted).toBe(true);

    // Verify deletion
    const retrieved = await quantService.getStrategy(strategy.id);
    expect(retrieved).toBeNull();
  });

  it('should generate multiple signals for different stocks', async () => {
    const strategy = await quantService.createStrategy({
      name: 'Multi-Stock Test',
      description: 'Test multiple signals',
      enabled: true,
      screening: { market: 'A', filters: {} },
      entry: {
        conditions: [{ indicator: 'rsi', operator: '<', value: 40, params: {} }],
        logic: 'AND'
      },
      exit: { stop_loss: 0.05, take_profit: 0.1, conditions: [] },
      position: { max_position_pct: 0.1, max_stocks: 20 }
    });

    const stocks = [
      { symbol: '000001', name: '平安银行', rsi: 35, price: 10.5 },
      { symbol: '000002', name: '万科A', rsi: 38, price: 8.2 },
      { symbol: '600519', name: '贵州茅台', rsi: 65, price: 1680 }
    ];

    const signals = [];
    for (const stock of stocks) {
      const tech = {
        rsi: stock.rsi,
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
        atr: 1.0,
      pe: 0,
      pb: 0,
      roe: 0,
      gross_margin: 0,
        debt_ratio: 0
      };

      const signal = await signalGenerator.generateSignal(
        stock.symbol,
        stock.name,
        strategy,
        tech,
        stock.price
      );

      if (signal) signals.push(signal);
    }

    // Should generate signals for stocks with RSI < 40
    expect(signals.length).toBe(2);
    expect(signals.map(s => s.symbol)).toEqual(['000001', '000002']);
  });

  it('should calculate technical indicators correctly', () => {
    // Test RSI calculation
    const closes = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64];
    const rsi = factorLib.calculateRSI(closes, 14);
    expect(rsi).toBeGreaterThan(50);
    expect(rsi).toBeLessThan(80);

    // Test MA calculation
    const ma5 = factorLib.calculateMA([10, 11, 12, 13, 14, 15, 16, 17, 18, 19], 5);
    expect(ma5).toBe(17); // (15+16+17+18+19)/5

    // Test MACD calculation
    const longCloses = Array.from({ length: 50 }, (_, i) => 100 + i * 0.5);
    const macd = factorLib.calculateMACD(longCloses);
    expect(macd.dif).toBeDefined();
    expect(macd.dea).toBeDefined();
    expect(macd.histogram).toBeDefined();

    // Test Bollinger Bands
    const bb = factorLib.calculateBollinger([95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114], 20, 2);
    expect(bb.upper).toBeGreaterThan(bb.mid);
    expect(bb.mid).toBeGreaterThan(bb.lower);
  });

  it('should score stocks with different technical patterns', () => {
    // Bullish pattern
    const bullishTech = {
      rsi: 28,
      ma5: 105,
      ma10: 103,
      ma20: 100,
      ma60: 98,
      macd_dif: 0.5,
      macd_dea: 0.3,
      macd_histogram: 0.2,
      bollinger_upper: 110,
      bollinger_mid: 100,
      bollinger_lower: 90,
      volume_ratio: 2.5,
      atr: 1.5,
      pe: 0,
      pb: 0,
      roe: 0,
    gross_margin: 0,
      debt_ratio: 0
    };

    const bullishScore = factorLib.scoreStock(bullishTech, 92);
    expect(bullishScore.total_score).toBeGreaterThan(60);
    expect(bullishScore.recommendation).toBe('buy');

    // Bearish pattern
    const bearishTech = {
      rsi: 75,
      ma5: 95,
      ma10: 97,
      ma20: 100,
      ma60: 102,
      macd_dif: -0.5,
      macd_dea: -0.3,
      macd_histogram: -0.2,
      bollinger_upper: 110,
      bollinger_mid: 100,
      bollinger_lower: 90,
      volume_ratio: 0.5,
      atr: 1.5,
      pe: 0,
      pb: 0,
      roe: 0,
    gross_margin: 0,
      debt_ratio: 0
    };

    const bearishScore = factorLib.scoreStock(bearishTech, 108);
    expect(bearishScore.total_score).toBeLessThan(50);
    expect(bearishScore.recommendation).toBe('avoid');
  });
});
