import { StockDBService } from '../data/stock-db-service.js';
import { callQuantSysDaemon } from '../../infrastructure/quant/quantsys-daemon-adapter.js';

export interface TechnicalIndicators {
  rsi: number;
  ma5: number;
  ma10: number;
  ma20: number;
  ma60: number;
  macd_dif: number;
  macd_dea: number;
  macd_histogram: number;
  bollinger_upper: number;
  bollinger_mid: number;
  bollinger_lower: number;
  volume_ratio: number;
  atr: number;
  /** 基本面因子 */
  pe: number;
  pb: number;
  roe: number;
  gross_margin: number;
  debt_ratio: number;
}

export interface StockScore {
  symbol: string;
  total_score: number;
  technical_score: number;
  fundamental_score: number;
  recommendation: 'buy' | 'hold' | 'avoid';
  details: {
    rsi_score: number;
    ma_score: number;
    macd_score: number;
    volume_score: number;
    bb_score: number;
  };
}

interface CacheEntry {
  value: any;
  timestamp: number;
}

export class FactorLibrary {
  private stockDBService?: StockDBService;
  private cache: Map<string, CacheEntry> = new Map();
  private readonly CACHE_TTL_REALTIME = 5 * 60 * 1000; // 5 minutes for real-time
  private readonly CACHE_TTL_HISTORICAL = 24 * 60 * 60 * 1000; // 1 day for historical

  constructor(stockDBService?: StockDBService) {
    this.stockDBService = stockDBService;
  }

  /**
   * Get K-line data with fallback to quant CLI
   * @param symbol Stock symbol
   * @param date Optional date
   * @returns K-line data arrays
   */
  private async getKlineData(
    symbol: string,
    date?: string
  ): Promise<{
    closes: number[];
    highs: number[];
    lows: number[];
    volumes: number[];
  }> {
    try {
      if (!this.stockDBService) throw new Error('StockDBService not initialized');

      const klines = this.stockDBService.getKlines(symbol, undefined, date);
      if (!klines || klines.length === 0) {
        throw new Error('No data from StockDBService');
      }

      return {
        closes: klines.map(k => k.close),
        highs: klines.map(k => k.high),
        lows: klines.map(k => k.low),
        volumes: klines.map(k => k.volume)
      };
    } catch (error) {
      // Fallback to quant CLI
      console.log(`[FactorLibrary] Falling back to quant CLI for ${symbol}, DB error: ${error}`);
      const historyJson = await callQuantSysDaemon("get_stock_history", {
        symbol,
        period: 'daily',
        end_date: date,
        limit: 60,
      });
      const historyData = JSON.parse(historyJson);

      // Support both legacy `data` field and new `recent_data` field
      let klineData = historyData.data || historyData.recent_data;
      
      // If recent_data has < 60 rows and full_data_file exists, try to read the full file
      if ((!klineData || klineData.length < 60) && historyData.full_data_file) {
        try {
          const { readFile } = await import('fs/promises');
          const fullJson = JSON.parse(await readFile(historyData.full_data_file, 'utf-8'));
          if (fullJson.data && fullJson.data.length > klineData?.length) {
            klineData = fullJson.data;
          }
        } catch (e) {
          console.warn(`[FactorLibrary] Failed to read full kline file for ${symbol}:`, e);
        }
      }

      if (historyData.error || !klineData || klineData.length === 0) {
        throw new Error(`No K-line data found for ${symbol}`);
      }

      return {
        closes: klineData.map((d: any) => d.close || d.收盘 || 0),
        highs: klineData.map((d: any) => d.high || d.最高 || 0),
        lows: klineData.map((d: any) => d.low || d.最低 || 0),
        volumes: klineData.map((d: any) => d.volume || d.成交量 || 0)
      };
    }
  }

  /**
   * Calculate RSI (Relative Strength Index) from array
   * @param closes Array of closing prices
   * @param period RSI period (default 14)
   * @returns RSI value (0-100)
   */
  private calculateRSIFromArray(closes: number[], period: number = 14): number {
    if (closes.length < period + 1) return 50;

    let gains = 0;
    let losses = 0;

    // Calculate initial average gain/loss
    for (let i = closes.length - period; i < closes.length; i++) {
      const change = closes[i] - closes[i - 1];
      if (change > 0) gains += change;
      else losses += Math.abs(change);
    }

    const avgGain = gains / period;
    const avgLoss = losses / period;

    if (avgLoss === 0) return 100;
    const rs = avgGain / avgLoss;
    return 100 - (100 / (1 + rs));
  }

  /**
   * Calculate Simple Moving Average from array
   * @param closes Array of closing prices
   * @param period MA period
   * @returns MA value
   */
  private calculateMAFromArray(closes: number[], period: number): number {
    if (period <= 0) throw new Error('Period must be positive');
    if (closes.length === 0) return 0;
    if (closes.length < period) return closes[closes.length - 1] || 0;

    const slice = closes.slice(-period);
    return slice.reduce((sum, val) => sum + val, 0) / period;
  }

  /**
   * Calculate Exponential Moving Average from array
   * @param values Array of values
   * @param period EMA period
   * @returns EMA value
   */
  private calculateEMAFromArray(values: number[], period: number): number {
    if (values.length === 0) return 0;
    if (values.length < period) return values[values.length - 1];

    const multiplier = 2 / (period + 1);
    let ema = values[0];

    for (let i = 1; i < values.length; i++) {
      ema = (values[i] - ema) * multiplier + ema;
    }

    return ema;
  }

  /**
   * Calculate MACD (Moving Average Convergence Divergence) from array
   * @param closes Array of closing prices
   * @returns MACD components (dif, dea, histogram)
   */
  private calculateMACDFromArray(closes: number[]): { dif: number; dea: number; histogram: number } {
    if (closes.length < 26) {
      return { dif: 0, dea: 0, histogram: 0 };
    }

    // Compute DIF series incrementally (rolling EMA-12 / EMA-26)
    const ema12Mult = 2 / (12 + 1);
    const ema26Mult = 2 / (26 + 1);

    let ema12 = closes[0];
    let ema26 = closes[0];
    const difSeries: number[] = [];

    for (let i = 0; i < closes.length; i++) {
      ema12 = (closes[i] - ema12) * ema12Mult + ema12;
      ema26 = (closes[i] - ema26) * ema26Mult + ema26;

      if (i >= 25) {
        difSeries.push(ema12 - ema26);
      }
    }

    const dif = difSeries[difSeries.length - 1];
    const dea = difSeries.length >= 9
      ? this.calculateEMAFromArray(difSeries, 9)
      : difSeries.reduce((s, v) => s + v, 0) / difSeries.length;
    const histogram = dif - dea;

    return { dif, dea, histogram };
  }

  // Public methods for tests (delegate to private methods)
  calculateRSI(closes: number[], period: number = 14): number {
    return this.calculateRSIFromArray(closes, period);
  }

  calculateMA(closes: number[], period: number): number {
    return this.calculateMAFromArray(closes, period);
  }

  calculateEMA(values: number[], period: number): number {
    return this.calculateEMAFromArray(values, period);
  }

  calculateMACD(closes: number[]): { dif: number; dea: number; histogram: number } {
    return this.calculateMACDFromArray(closes);
  }

  /**
   * Calculate Bollinger Bands
   * @param closes Array of closing prices
   * @param period BB period (default 20)
   * @param stdDev Standard deviation multiplier (default 2)
   * @returns Bollinger Bands (upper, mid, lower)
   */
  calculateBollinger(
    closes: number[],
    period: number = 20,
    stdDev: number = 2
  ): { upper: number; mid: number; lower: number } {
    if (closes.length === 0) {
      return { upper: 0, mid: 0, lower: 0 };
    }

    if (closes.length < period) {
      const last = closes[closes.length - 1] || 0;
      return { upper: last, mid: last, lower: last };
    }

    const slice = closes.slice(-period);
    const mid = slice.reduce((sum, val) => sum + val, 0) / period;
    const variance = slice.reduce((sum, val) => sum + Math.pow(val - mid, 2), 0) / period;
    const std = Math.sqrt(variance);

    return {
      upper: mid + stdDev * std,
      mid,
      lower: mid - stdDev * std
    };
  }

  /**
   * Calculate ATR (Average True Range)
   * @param highs Array of high prices
   * @param lows Array of low prices
   * @param closes Array of closing prices
   * @param period ATR period (default 14)
   * @returns ATR value
   */
  calculateATR(highs: number[], lows: number[], closes: number[], period: number = 14): number {
    if (highs.length < period + 1 || lows.length < period + 1 || closes.length < period + 1) {
      return 0;
    }

    if (highs.length !== lows.length || highs.length !== closes.length) {
      return 0;
    }

    const trueRanges: number[] = [];

    for (let i = 1; i < highs.length; i++) {
      const high = highs[i];
      const low = lows[i];
      const prevClose = closes[i - 1];

      const tr = Math.max(
        high - low,
        Math.abs(high - prevClose),
        Math.abs(low - prevClose)
      );

      trueRanges.push(tr);
    }

    // Calculate average of last 'period' true ranges
    const slice = trueRanges.slice(-period);
    return slice.reduce((sum, val) => sum + val, 0) / period;
  }

  /**
   * Calculate Volume Ratio
   * @param volumes Array of volume values
   * @param period Period for average calculation (default 5)
   * @returns Volume ratio (current / average)
   */
  calculateVolumeRatio(volumes: number[], period: number = 5): number {
    if (volumes.length < period + 1) return 1;

    const currentVolume = volumes[volumes.length - 1];
    const avgVolume = this.calculateMA(volumes.slice(0, -1), period);

    return avgVolume > 0 ? currentVolume / avgVolume : 1;
  }

  /**
   * 🔥 获取指定股票在指定日期的真实收盘价
   * @param symbol Stock symbol
   * @param date Optional date (default: today)
   * @returns 收盘价，获取失败返回 0（含无数据）
   */
  async getLatestClosePrice(symbol: string, date?: string): Promise<number> {
    try {
      const { closes } = await this.getKlineData(symbol, date);
      if (closes.length === 0) return 0;
      return closes[closes.length - 1];
    } catch {
      return 0;
    }
  }

  /**
   * 🔥 仅查本地DB获取收盘价，不触发API回源（用于回测场景，可接受无数据=跳过）
   */
  async getLatestClosePriceLocal(symbol: string, date?: string): Promise<number> {
    try {
      if (!this.stockDBService) return 0;
      const klines = this.stockDBService.getKlines(symbol, undefined, date);
      if (!klines || klines.length === 0) return 0;
      const last = klines[klines.length - 1];
      return last.close || 0;
    } catch {
      return 0;
    }
  }

  /**
   * 获取 A 股基本面因子（PE/PB/ROE）——仅查本地DB，用于回测
   */
  async getFundamentals(symbol: string): Promise<{ pe: number; pb: number; roe: number; gross_margin: number; debt_ratio: number }> {
    const defaults = { pe: 0, pb: 0, roe: 0, gross_margin: 0, debt_ratio: 0 };
    try {
      if (!this.stockDBService) return defaults;
      const row = this.stockDBService.getStockBasics(symbol);
      if (!row) return defaults;
      return {
        pe: row.pe || 0,
        pb: row.pb || 0,
        roe: row.roe || 0,
        gross_margin: row.gross_margin || 0,
        debt_ratio: row.debt_ratio || 0,
      };
    } catch {
      return defaults;
    }
  }

  /**
   * Calculate MA for a specific symbol and date (with caching)
   * @param symbol Stock symbol
   * @param period MA period
   * @param date Optional date (default: today)
   * @returns MA value
   */
  async calculateMAForSymbol(symbol: string, period: number, date?: string): Promise<number> {
    const cacheKey = `ma_${symbol}_${period}_${date || 'today'}`;
    const cached = this.getFromCache(cacheKey, date);
    if (cached !== null) return cached;

    const { closes } = await this.getKlineData(symbol, date);
    const result = this.calculateMAFromArray(closes, period);

    this.setCache(cacheKey, result, date);
    return result;
  }

  /**
   * Calculate EMA for a specific symbol and date (with caching)
   */
  async calculateEMAForSymbol(symbol: string, period: number, date?: string): Promise<number> {
    const cacheKey = `ema_${symbol}_${period}_${date || 'today'}`;
    const cached = this.getFromCache(cacheKey, date);
    if (cached !== null) return cached;

    const { closes } = await this.getKlineData(symbol, date);
    const result = this.calculateEMAFromArray(closes, period);

    this.setCache(cacheKey, result, date);
    return result;
  }

  /**
   * Calculate RSI for a specific symbol and date (with caching)
   */
  async calculateRSIForSymbol(symbol: string, period: number, date?: string): Promise<number> {
    const cacheKey = `rsi_${symbol}_${period}_${date || 'today'}`;
    const cached = this.getFromCache(cacheKey, date);
    if (cached !== null) return cached;

    const { closes } = await this.getKlineData(symbol, date);
    const result = this.calculateRSIFromArray(closes, period);

    this.setCache(cacheKey, result, date);
    return result;
  }

  /**
   * Calculate MACD for a specific symbol and date (with caching)
   */
  async calculateMACDForSymbol(symbol: string, date?: string): Promise<{ dif: number; dea: number; macd: number }> {
    const cacheKey = `macd_${symbol}_${date || 'today'}`;
    const cached = this.getFromCache(cacheKey, date);
    if (cached !== null) return cached;

    const { closes } = await this.getKlineData(symbol, date);
    const { dif, dea, histogram } = this.calculateMACDFromArray(closes);
    const result = { dif, dea, macd: histogram };

    this.setCache(cacheKey, result, date);
    return result;
  }

  /**
   * Calculate Bollinger Bands for a specific symbol and date (with caching)
   */
  async calculateBollingerBands(
    symbol: string,
    period: number,
    stdDev: number,
    date?: string
  ): Promise<{ upper: number; middle: number; lower: number }> {
    const cacheKey = `bb_${symbol}_${period}_${stdDev}_${date || 'today'}`;
    const cached = this.getFromCache(cacheKey, date);
    if (cached !== null) return cached;

    const { closes } = await this.getKlineData(symbol, date);
    const { upper, mid, lower } = this.calculateBollinger(closes, period, stdDev);
    const result = { upper, middle: mid, lower };

    this.setCache(cacheKey, result, date);
    return result;
  }

  /**
   * Batch calculate indicators for multiple stocks
   * @param symbols Array of stock symbols
   * @param factors Array of factor names to calculate
   * @param date Optional date
   * @returns Map of symbol to calculated factors
   */
  async batchCalculate(
    symbols: string[],
    factors: string[],
    date?: string
  ): Promise<Map<string, any>> {
    const results = new Map<string, any>();

    for (const symbol of symbols) {
      try {
        const stockFactors: any = {};

        for (const factor of factors) {
          if (factor === 'ma5') {
            stockFactors.ma5 = await this.calculateMAForSymbol(symbol, 5, date);
          } else if (factor === 'ma20') {
            stockFactors.ma20 = await this.calculateMAForSymbol(symbol, 20, date);
          } else if (factor === 'ma60') {
            stockFactors.ma60 = await this.calculateMAForSymbol(symbol, 60, date);
          } else if (factor === 'rsi') {
            stockFactors.rsi = await this.calculateRSIForSymbol(symbol, 14, date);
          } else if (factor === 'macd') {
            stockFactors.macd = await this.calculateMACDForSymbol(symbol, date);
          }
        }

        results.set(symbol, stockFactors);
      } catch (error) {
        // Skip stocks with errors
        console.warn(`Failed to calculate factors for ${symbol}:`, error);
      }
    }

    return results;
  }

  /**
   * Score stock based on technical indicators
   * @param indicators Technical indicators
   * @param currentPrice Current stock price
   * @returns Stock score with recommendation
   */
  scoreStock(indicators: TechnicalIndicators, currentPrice: number): StockScore {
    let technicalScore = 0;
    const details = {
      rsi_score: 0,
      ma_score: 0,
      macd_score: 0,
      volume_score: 0,
      bb_score: 0
    };

    // RSI scoring (0-20 points)
    if (indicators.rsi < 30) {
      details.rsi_score = 20;
    } else if (indicators.rsi < 40) {
      details.rsi_score = 15;
    } else if (indicators.rsi > 70) {
      details.rsi_score = -10;
    }

    // MA scoring (0-25 points)
    if (indicators.ma5 > indicators.ma20 && indicators.ma20 > indicators.ma60) {
      details.ma_score = 25;
    } else if (indicators.ma5 > indicators.ma20) {
      details.ma_score = 15;
    } else if (indicators.ma5 < indicators.ma20 && indicators.ma20 < indicators.ma60) {
      details.ma_score = -15;
    }

    // MACD scoring (0-20 points)
    if (indicators.macd_histogram > 0) {
      details.macd_score = 20;
    } else if (indicators.macd_histogram > -0.1) {
      details.macd_score = 10;
    } else {
      details.macd_score = -10;
    }

    // Volume scoring (0-15 points)
    if (indicators.volume_ratio > 2) {
      details.volume_score = 15;
    } else if (indicators.volume_ratio > 1.5) {
      details.volume_score = 10;
    } else if (indicators.volume_ratio < 0.5) {
      details.volume_score = -5;
    }

    // Bollinger Bands scoring (0-20 points)
    const bbPosition = (currentPrice - indicators.bollinger_lower) /
                       (indicators.bollinger_upper - indicators.bollinger_lower);
    if (bbPosition < 0.2) {
      details.bb_score = 20;
    } else if (bbPosition < 0.4) {
      details.bb_score = 10;
    } else if (bbPosition > 0.8) {
      details.bb_score = -10;
    }

    technicalScore = details.rsi_score + details.ma_score + details.macd_score +
                     details.volume_score + details.bb_score;

    // Normalize to 0-100
    const normalizedScore = Math.max(0, Math.min(100, technicalScore + 50));

    let recommendation: 'buy' | 'hold' | 'avoid' = 'hold';
    if (normalizedScore >= 70) recommendation = 'buy';
    else if (normalizedScore < 40) recommendation = 'avoid';

    return {
      symbol: '',
      total_score: normalizedScore,
      technical_score: normalizedScore,
      fundamental_score: 0,
      recommendation,
      details
    };
  }

  /**
   * Get value from cache
   */
  private getFromCache(key: string, date?: string): any | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    const ttl = date ? this.CACHE_TTL_HISTORICAL : this.CACHE_TTL_REALTIME;
    const now = Date.now();

    if (now - entry.timestamp > ttl) {
      this.cache.delete(key);
      return null;
    }

    return entry.value;
  }

  /**
   * Set value in cache
   */
  private setCache(key: string, value: any, date?: string): void {
    this.cache.set(key, {
      value,
      timestamp: Date.now()
    });
  }

  /**
   * Clear cache
   */
  clearCache(): void {
    this.cache.clear();
  }
}
