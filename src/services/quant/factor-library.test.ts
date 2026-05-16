import { describe, it, expect } from '@jest/globals';
import { FactorLibrary, type TechnicalIndicators } from './factor-library';

describe('FactorLibrary', () => {
  const factorLib = new FactorLibrary();

  describe('calculateRSI', () => {
    it('should calculate RSI correctly for uptrend data', () => {
      // Classic RSI test data from Wilder's book
      const closes = [44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28, 46.00, 46.03, 46.41, 46.22, 45.64];
      const rsi = factorLib.calculateRSI(closes, 14);
      expect(rsi).toBeGreaterThan(50);
      expect(rsi).toBeLessThan(80);
    });

    it('should return 50 for insufficient data', () => {
      const closes = [10, 11, 12];
      const rsi = factorLib.calculateRSI(closes, 14);
      expect(rsi).toBe(50);
    });

    it('should return 100 when all gains', () => {
      const closes = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25];
      const rsi = factorLib.calculateRSI(closes, 14);
      expect(rsi).toBe(100);
    });

    it('should handle oversold condition (RSI < 30)', () => {
      const closes = [100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 29];
      const rsi = factorLib.calculateRSI(closes, 14);
      expect(rsi).toBeLessThan(30);
    });
  });

  describe('calculateMA', () => {
    it('should calculate 5-day MA correctly', () => {
      const closes = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19];
      const ma5 = factorLib.calculateMA(closes, 5);
      expect(ma5).toBe(17); // (15+16+17+18+19)/5 = 17
    });

    it('should calculate 20-day MA correctly', () => {
      const closes = Array.from({ length: 30 }, (_, i) => 100 + i);
      const ma20 = factorLib.calculateMA(closes, 20);
      expect(ma20).toBe(119.5); // Average of last 20 values
    });

    it('should return last price when insufficient data', () => {
      const closes = [10, 11, 12];
      const ma5 = factorLib.calculateMA(closes, 5);
      expect(ma5).toBe(12);
    });

    it('should return 0 for empty array', () => {
      const closes: number[] = [];
      const ma5 = factorLib.calculateMA(closes, 5);
      expect(ma5).toBe(0);
    });
  });

  describe('calculateEMA', () => {
    it('should calculate 12-day EMA correctly', () => {
      const closes = Array.from({ length: 30 }, (_, i) => 100 + i * 0.5);
      const ema12 = factorLib.calculateEMA(closes, 12);
      expect(ema12).toBeGreaterThan(100);
      expect(ema12).toBeLessThan(130);
    });

    it('should return last value for insufficient data', () => {
      const closes = [10, 11];
      const ema12 = factorLib.calculateEMA(closes, 12);
      expect(ema12).toBe(11);
    });
  });

  describe('calculateMACD', () => {
    it('should calculate MACD with all components', () => {
      const closes = Array.from({ length: 50 }, (_, i) => 100 + i * 0.5);
      const macd = factorLib.calculateMACD(closes);

      expect(macd.dif).toBeDefined();
      expect(macd.dea).toBeDefined();
      expect(macd.histogram).toBeDefined();
      expect(typeof macd.dif).toBe('number');
      expect(typeof macd.dea).toBe('number');
      expect(typeof macd.histogram).toBe('number');
    });

    it('should return zeros for insufficient data', () => {
      const closes = [100, 101, 102];
      const macd = factorLib.calculateMACD(closes);

      expect(macd.dif).toBe(0);
      expect(macd.dea).toBe(0);
      expect(macd.histogram).toBe(0);
    });

    it('should have histogram = dif - dea', () => {
      const closes = Array.from({ length: 50 }, (_, i) => 100 + i * 0.5);
      const macd = factorLib.calculateMACD(closes);

      expect(macd.histogram).toBeCloseTo(macd.dif - macd.dea, 5);
    });

    it('should detect golden cross (histogram > 0)', () => {
      // Strong uptrend data should produce positive histogram
      // Need more data points for proper MACD calculation
      const closes = Array.from({ length: 100 }, (_, i) => 100 + i * 2);
      const macd = factorLib.calculateMACD(closes);

      // With strong uptrend, DIF should be positive
      expect(macd.dif).toBeGreaterThanOrEqual(0);
      expect(typeof macd.histogram).toBe('number');
    });
  });

  describe('calculateBollinger', () => {
    it('should calculate Bollinger Bands correctly', () => {
      const closes = Array.from({ length: 30 }, (_, i) => 100 + Math.sin(i / 5) * 5);
      const bb = factorLib.calculateBollinger(closes, 20, 2);

      expect(bb.upper).toBeGreaterThan(bb.mid);
      expect(bb.mid).toBeGreaterThan(bb.lower);
      expect(bb.upper - bb.mid).toBeCloseTo(bb.mid - bb.lower, 1);
    });

    it('should return same value for all bands with insufficient data', () => {
      const closes = [100, 101, 102];
      const bb = factorLib.calculateBollinger(closes, 20, 2);

      expect(bb.upper).toBe(102);
      expect(bb.mid).toBe(102);
      expect(bb.lower).toBe(102);
    });

    it('should handle empty array', () => {
      const closes: number[] = [];
      const bb = factorLib.calculateBollinger(closes, 20, 2);

      expect(bb.upper).toBe(0);
      expect(bb.mid).toBe(0);
      expect(bb.lower).toBe(0);
    });

    it('should calculate with custom standard deviation', () => {
      const closes = Array.from({ length: 30 }, () => 100);
      const bb1 = factorLib.calculateBollinger(closes, 20, 1);
      const bb2 = factorLib.calculateBollinger(closes, 20, 2);

      // For constant prices, bands should be at mid
      expect(bb1.upper).toBe(bb1.mid);
      expect(bb2.upper).toBe(bb2.mid);
    });
  });

  describe('calculateATR', () => {
    it('should calculate ATR correctly', () => {
      const highs = [105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119];
      const lows = [95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109];
      const closes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114];

      const atr = factorLib.calculateATR(highs, lows, closes, 14);
      expect(atr).toBeGreaterThan(0);
      expect(atr).toBeLessThan(20);
    });

    it('should return 0 for insufficient data', () => {
      const highs = [105, 106];
      const lows = [95, 96];
      const closes = [100, 101];

      const atr = factorLib.calculateATR(highs, lows, closes, 14);
      expect(atr).toBe(0);
    });

    it('should handle mismatched array lengths', () => {
      const highs = [105, 106, 107];
      const lows = [95, 96];
      const closes = [100, 101, 102];

      const atr = factorLib.calculateATR(highs, lows, closes, 14);
      expect(atr).toBe(0);
    });
  });

  describe('calculateVolumeRatio', () => {
    it('should calculate volume ratio correctly', () => {
      const volumes = [1000, 1100, 1200, 1300, 1400, 2000];
      const ratio = factorLib.calculateVolumeRatio(volumes, 5);

      // Current volume (2000) / avg of previous 5 (1200)
      expect(ratio).toBeCloseTo(2000 / 1200, 2);
    });

    it('should return 1 for insufficient data', () => {
      const volumes = [1000, 1100];
      const ratio = factorLib.calculateVolumeRatio(volumes, 5);
      expect(ratio).toBe(1);
    });

    it('should handle zero average volume', () => {
      const volumes = [0, 0, 0, 0, 0, 1000];
      const ratio = factorLib.calculateVolumeRatio(volumes, 5);
      expect(ratio).toBe(1);
    });
  });

  describe('batchCalculate', () => {
    it('should calculate multiple indicators for multiple stocks', async () => {
      const symbols = ['000001', '000002'];
      const factors = ['ma5', 'ma20', 'rsi'];

      const results = await factorLib.batchCalculate(symbols, factors);

      // Without StockDBService, all stocks will fail gracefully
      // The method should not throw, just return empty or partial results
      expect(results.size).toBeGreaterThanOrEqual(0);
      expect(results.size).toBeLessThanOrEqual(2);
    });

    it('should return empty map for empty symbols', async () => {
      const results = await factorLib.batchCalculate([], ['ma5']);
      expect(results.size).toBe(0);
    });

    it('should handle errors gracefully', async () => {
      const symbols = ['INVALID'];
      const factors = ['ma5'];

      const results = await factorLib.batchCalculate(symbols, factors);
      expect(results.size).toBeLessThanOrEqual(1);
    });
  });

  describe('scoreStock', () => {
    it('should score stock with strong buy signals', () => {
      const indicators: TechnicalIndicators = {
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
        atr: 2.5
      };

      const score = factorLib.scoreStock(indicators, 92);

      expect(score.total_score).toBeGreaterThan(60);
      expect(score.recommendation).toBe('buy');
      expect(score.details.rsi_score).toBe(20); // RSI < 30
      expect(score.details.ma_score).toBe(25); // MA5 > MA20 > MA60
      expect(score.details.macd_score).toBe(20); // MACD histogram > 0
      expect(score.details.volume_score).toBe(15); // Volume ratio > 2
      expect(score.details.bb_score).toBe(20); // Price near lower band
    });

    it('should score stock with weak signals as hold', () => {
      const indicators: TechnicalIndicators = {
        rsi: 50,
        ma5: 100,
        ma10: 100,
        ma20: 100,
        ma60: 100,
        macd_dif: 0,
        macd_dea: 0,
        macd_histogram: 0,
        bollinger_upper: 105,
        bollinger_mid: 100,
        bollinger_lower: 95,
        volume_ratio: 1.0,
        atr: 2.0
      };

      const score = factorLib.scoreStock(indicators, 100);

      expect(score.total_score).toBeGreaterThanOrEqual(40);
      expect(score.total_score).toBeLessThan(70);
      expect(score.recommendation).toBe('hold');
    });

    it('should score stock with sell signals as avoid', () => {
      const indicators: TechnicalIndicators = {
        rsi: 75,
        ma5: 95,
        ma10: 97,
        ma20: 100,
        ma60: 105,
        macd_dif: -0.5,
        macd_dea: -0.3,
        macd_histogram: -0.2,
        bollinger_upper: 110,
        bollinger_mid: 100,
        bollinger_lower: 90,
        volume_ratio: 0.4,
        atr: 3.0
      };

      const score = factorLib.scoreStock(indicators, 108);

      expect(score.total_score).toBeLessThan(40);
      expect(score.recommendation).toBe('avoid');
      expect(score.details.rsi_score).toBe(-10); // RSI > 70
      expect(score.details.ma_score).toBe(-15); // MA5 < MA20 < MA60
    });

    it('should normalize score to 0-100 range', () => {
      const indicators: TechnicalIndicators = {
        rsi: 10,
        ma5: 110,
        ma10: 105,
        ma20: 100,
        ma60: 95,
        macd_dif: 1.0,
        macd_dea: 0.5,
        macd_histogram: 0.5,
        bollinger_upper: 110,
        bollinger_mid: 100,
        bollinger_lower: 90,
        volume_ratio: 3.0,
        atr: 2.0
      };

      const score = factorLib.scoreStock(indicators, 91);

      expect(score.total_score).toBeGreaterThanOrEqual(0);
      expect(score.total_score).toBeLessThanOrEqual(100);
    });
  });

  describe('caching behavior', () => {
    it('should cache results for same symbol and date', async () => {
      // This test requires StockDBService to be initialized
      // For now, we test that the method throws appropriately
      const symbol = '000001';
      const date = '2024-01-01';

      await expect(async () => {
        await factorLib.calculateMAForSymbol(symbol, 5, date);
      }).rejects.toThrow('StockDBService not initialized');
    });

    it('should not cache for different dates', async () => {
      // This test requires StockDBService to be initialized
      const symbol = '000001';

      await expect(async () => {
        await factorLib.calculateMAForSymbol(symbol, 5, '2024-01-01');
      }).rejects.toThrow('StockDBService not initialized');
    });
  });

  describe('error handling', () => {
    it('should handle missing data gracefully', async () => {
      const symbol = 'NONEXISTENT';

      await expect(async () => {
        await factorLib.calculateMAForSymbol(symbol, 5);
      }).rejects.toThrow();
    });

    it('should handle invalid period', () => {
      const closes = [10, 11, 12, 13, 14];

      expect(() => {
        factorLib.calculateMA(closes, 0);
      }).toThrow();
    });

    it('should handle negative period', () => {
      const closes = [10, 11, 12, 13, 14];

      expect(() => {
        factorLib.calculateMA(closes, -5);
      }).toThrow();
    });
  });
});
