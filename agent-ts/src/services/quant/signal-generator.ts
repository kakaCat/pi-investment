import fs from 'fs/promises';
import path from 'path';
import Database from 'better-sqlite3';
import { Signal, QuantStrategy, EntryCondition, SignalActionType } from './types.js';
// @ts-ignore - Module stub needed
import { FactorLibrary, TechnicalIndicators } from './factor-library.js';
import { SignalArbiter, ArbiterConfig } from './signal-arbiter.js';

export interface StockData {
  symbol: string;
  name: string;
  price: number;
  tech: TechnicalIndicators;
}

// ═══════════════════════════════════════════════════════════════
// Confidence Config Types (from calibration)
// ═══════════════════════════════════════════════════════════════

interface FactorBinConfig {
  range: [number, number];
  mean_return: number;
  hit_rate: number;
  score_bonus: number;
  samples: number;
  neutral: boolean;
}

interface FactorConfig {
  type: 'range' | 'boolean';
  rank_ic: number;
  weight: number;
  direction?: 'buy' | 'sell';
  bins?: FactorBinConfig[];
  // boolean-specific
  mean_return?: number;
  hit_rate?: number;
  samples?: number;
  excess_return?: number;
  // meta
  column?: string;
  condition?: string;
}

interface ConfidenceConfig {
  version: string;
  generated_at: string;
  forward_return_days: number;
  return_threshold: number;
  total_samples: number;
  factors: Record<string, FactorConfig>;
  meta: {
    calibration_method: string;
    data_range: { start: string; end: string };
    symbols_count: number;
  };
}

export class SignalGenerator {
  private signalsDir: string;
  private factorLib: FactorLibrary;
  private useML: boolean;
  private dbPath: string;
  private arbiter: SignalArbiter;
  private confidenceConfig: ConfidenceConfig | null = null;
  private configPath: string;

  // 是否已尝试加载配置（避免每次重复读取文件）
  private configLoaded = false;

  constructor(
    signalsDir: string = '.pi-invest/quant/signals',
    factorLib?: FactorLibrary,
    useML: boolean = true,
    dbPath?: string,
    arbiterConfig?: Partial<ArbiterConfig>
  ) {
    this.signalsDir = signalsDir;
    this.factorLib = factorLib || new FactorLibrary();
    this.useML = useML;
    this.dbPath = dbPath || '.pi-invest/stock-db/stocks.db';
    this.arbiter = new SignalArbiter(arbiterConfig);
    this.configPath = path.join(path.dirname(this.signalsDir), 'confidence_config.json');
  }

  /**
   * 加载校准配置。首次调用时读取 JSON，后续返回缓存。
   */
  loadConfidenceConfig(): ConfidenceConfig | null {
    if (this.configLoaded) {
      return this.confidenceConfig;
    }
    this.configLoaded = true;

    try {
      // 使用同步读取（与项目其他位置一致）
      const { readFileSync } = require('fs');
      const raw = readFileSync(this.configPath, 'utf-8');
      const config = JSON.parse(raw) as ConfidenceConfig;

      // 基本校验
      if (!config.version || !config.factors || typeof config.factors !== 'object') {
        console.warn('[SignalGenerator] 校准配置格式无效，使用硬编码 fallback');
        return null;
      }

      const factorCount = Object.keys(config.factors).length;
      console.log(
        `[SignalGenerator] ✅ 已加载校准配置 v${config.version} ` +
        `(${config.generated_at?.slice(0, 10)}, ${factorCount} 个因子, ` +
        `${config.total_samples?.toLocaleString()} 样本)`
      );
      this.confidenceConfig = config;
      return config;
    } catch (err: any) {
      if (err.code === 'ENOENT') {
        console.log('[SignalGenerator] 校准配置不存在，使用硬编码 fallback。运行 calibrate.run 生成。');
      } else {
        console.warn('[SignalGenerator] 校准配置读取失败:', err.message, '，使用硬编码 fallback');
      }
      return null;
    }
  }

  /**
   * 运行置信度校准（异步，调用 Python 校准器）。
   */
  async runCalibration(
    forwardDays: number = 5,
    returnThreshold: number = 0.02
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const pythonCaller = await import(
        '../../infrastructure/tools/shared/python-caller-resilient-adapter.js'
      );
      const { callPythonResilient } = pythonCaller;

      const resultJson = await callPythonResilient('run_confidence_calibration', {
        forward_days: forwardDays,
        return_threshold: returnThreshold,
        output_path: this.configPath,
      });
      const result = JSON.parse(resultJson);

      if (result.success) {
        // 重新加载
        this.configLoaded = false;
        this.loadConfidenceConfig();
        return { success: true };
      }
      return { success: false, error: result.error || '校准失败' };
    } catch (err: any) {
      return { success: false, error: err.message };
    }
  }

  /**
   * Generate signal for a single stock
   */
  async generateSignal(
    symbol: string,
    name: string,
    strategy: QuantStrategy,
    tech: TechnicalIndicators,
    price: number
  ): Promise<Signal | null> {
    // Determine if this is a sell-oriented strategy (RSI > 70, overbought conditions)
    const isSellStrategy = this.isSellStrategy(strategy);

    // Check entry conditions
    const conditionsMatch = this.matchConditions(tech, strategy.entry.conditions, strategy.entry.logic);

    if (conditionsMatch) {
      const action = isSellStrategy ? 'sell' : 'buy';
      const action_type = isSellStrategy ? SignalActionType.SELL : SignalActionType.BUY;

      const signal: Signal = {
        date: new Date().toISOString().split('T')[0],
        symbol,
        name,
        action,
        action_type,
        strategy_id: strategy.id,
        price,
        reason: this.buildReason(tech, strategy.entry.conditions),
        confidence: 0.5,
        indicators: tech as any,
      };

      // Use ML prediction if enabled, otherwise use rule-based
      if (this.useML) {
        signal.confidence = await this.predictConfidence(signal);
      } else {
        signal.confidence = this.calculateConfidence(tech, signal.action);
      }

      return signal;
    }

    return null;
  }

  /**
   * Scan multiple stocks and return matching signals
   */
  async scanMarket(
    strategy: QuantStrategy,
    stockData: StockData[],
    confidenceThreshold: number = 0.5
  ): Promise<Signal[]> {
    const signals: Signal[] = [];

    for (const stock of stockData) {
      const signal = await this.generateSignal(
        stock.symbol,
        stock.name,
        strategy,
        stock.tech,
        stock.price
      );

      if (signal && signal.confidence >= confidenceThreshold) {
        signals.push(signal);
      }
    }

    return signals;
  }

  /**
   * Match a single condition against technical indicators
   */
  private matchCondition(tech: any, condition: EntryCondition): boolean {
    const { indicator, operator, value } = condition;
    const op = operator as string; // Use string for extended operators

    // RSI conditions
    if (indicator === 'rsi') {
      const rsi = tech.rsi || 50;
      if (op === '<') return rsi < (value as number);
      if (op === '>') return rsi > (value as number);
      if (op === '<=') return rsi <= (value as number);
      if (op === '>=') return rsi >= (value as number);
      if (op === '==') return rsi === (value as number);
    }

    // MA cross conditions
    if (indicator === 'ma_cross') {
      const ma5 = tech.ma5 || 0;
      const ma20 = tech.ma20 || 0;
      if (op === 'cross_above') return ma5 > ma20;
      if (op === 'cross_below') return ma5 < ma20;
    }

    // MACD conditions
    if (indicator === 'macd') {
      const hist = tech.macd_histogram || 0;
      if (op === '>') return hist > (value as number);
      if (op === '<') return hist < (value as number);
      if (op === '>=') return hist >= (value as number);
      if (op === '<=') return hist <= (value as number);
      if (op === 'golden_cross') return hist > 0;
      if (op === 'death_cross') return hist < 0;
    }

    // Bollinger Bands conditions
    if (indicator === 'bollinger') {
      const price = tech.close || 0;
      const upper = tech.bollinger_upper || 0;
      const lower = tech.bollinger_lower || 0;
      if (op === 'touch_lower') return price <= lower * 1.01;
      if (op === 'touch_upper') return price >= upper * 0.99;
      if (op === 'break_upper') return price > upper;
      if (op === 'break_lower') return price < lower;
    }

    // Volume conditions
    if (indicator === 'volume') {
      const volumeRatio = tech.volume_ratio || 1;
      if (op === '>') return volumeRatio > (value as number);
      if (op === '<') return volumeRatio < (value as number);
      if (op === '>=') return volumeRatio >= (value as number);
      if (op === '<=') return volumeRatio <= (value as number);
    }

    // PE conditions (基本面因子)
    if (indicator === 'pe') {
      const pe = tech.pe || 0;
      if (op === '>') return pe > (value as number);
      if (op === '<') return pe < (value as number);
      if (op === '>=') return pe >= (value as number);
      if (op === '<=') return pe <= (value as number);
      if (op === '==') return Math.abs(pe - (value as number)) < 0.01;
    }

    // PB conditions
    if (indicator === 'pb') {
      const pb = tech.pb || 0;
      if (op === '>') return pb > (value as number);
      if (op === '<') return pb < (value as number);
      if (op === '>=') return pb >= (value as number);
      if (op === '<=') return pb <= (value as number);
    }

    // ROE conditions
    if (indicator === 'roe') {
      const roe = tech.roe || 0;
      if (op === '>') return roe > (value as number);
      if (op === '<') return roe < (value as number);
      if (op === '>=') return roe >= (value as number);
      if (op === '<=') return roe <= (value as number);
    }

    // Debt ratio conditions
    if (indicator === 'debt_ratio') {
      const dr = tech.debt_ratio || 0;
      if (op === '>') return dr > (value as number);
      if (op === '<') return dr < (value as number);
      if (op === '>=') return dr >= (value as number);
      if (op === '<=') return dr <= (value as number);
    }

    return false;
  }

  /**
   * Match multiple conditions with AND/OR logic
   */
  private matchConditions(tech: any, conditions: EntryCondition[], logic: 'AND' | 'OR'): boolean {
    if (conditions.length === 0) return false;

    const results = conditions.map(cond => this.matchCondition(tech, cond));

    if (logic === 'AND') {
      return results.every(r => r);
    } else {
      return results.some(r => r);
    }
  }

  /**
   * Check if sell conditions are met (for strategies that look for overbought)
   */
  private isSellStrategy(strategy: QuantStrategy): boolean {
    // Check if entry conditions indicate a sell signal (e.g., RSI > 70)
    for (const condition of strategy.entry.conditions) {
      if (condition.indicator === 'rsi' && condition.operator === '>' && (condition.value as number) >= 70) {
        return true;
      }
      // MA death cross
      if (condition.indicator === 'ma_cross' && condition.operator === 'cross_below') {
        return true;
      }
      // MACD death cross
      const op = condition.operator as string;
      if (condition.indicator === 'macd' && op === 'death_cross') {
        return true;
      }
      // Bollinger upper band breakout
      if (condition.indicator === 'bollinger' && (op === 'break_upper' || op === 'touch_upper')) {
        return true;
      }
    }
    return false;
  }

  /**
   * Build human-readable reason string
   */
  private buildReason(tech: any, conditions: EntryCondition[]): string {
    const reasons: string[] = [];

    for (const c of conditions) {
      if (c.indicator === 'rsi') {
        reasons.push(`RSI=${tech.rsi?.toFixed(2) || 'N/A'}`);
      } else if (c.indicator === 'ma_cross') {
        reasons.push(`MA5=${tech.ma5?.toFixed(2) || 'N/A'} MA20=${tech.ma20?.toFixed(2) || 'N/A'}`);
      } else if (c.indicator === 'macd') {
        reasons.push(`MACD柱=${tech.macd_histogram?.toFixed(4) || 'N/A'}`);
      } else if (c.indicator === 'bollinger') {
        reasons.push(`价格=${tech.close?.toFixed(2) || 'N/A'} 下轨=${tech.bollinger_lower?.toFixed(2) || 'N/A'}`);
      } else if (c.indicator === 'volume') {
        reasons.push(`量比=${tech.volume_ratio?.toFixed(2) || 'N/A'}`);
      } else if (c.indicator === 'pe') {
        reasons.push(`PE=${tech.pe?.toFixed(2) || 'N/A'}`);
      } else if (c.indicator === 'pb') {
        reasons.push(`PB=${tech.pb?.toFixed(2) || 'N/A'}`);
      } else if (c.indicator === 'roe') {
        reasons.push(`ROE=${tech.roe?.toFixed(2) || 'N/A'}%`);
      } else if (c.indicator === 'debt_ratio') {
        reasons.push(`负债率=${tech.debt_ratio?.toFixed(1) || 'N/A'}%`);
      }
    }

    return reasons.filter(r => r).join(', ');
  }

  /**
   * Calculate confidence score — data-driven when calibration config exists,
   * falls back to hardcoded thresholds otherwise.
   */
  private calculateConfidence(indicators: TechnicalIndicators, signalType: 'buy' | 'sell'): number {
    const config = this.loadConfidenceConfig();
    if (config && config.factors && Object.keys(config.factors).length > 0) {
      return this.calculateConfidenceFromConfig(indicators, signalType, config);
    }
    return this.calculateConfidenceFallback(indicators, signalType);
  }

  /**
   * Data-driven confidence calculation using calibration config.
   */
  private calculateConfidenceFromConfig(
    indicators: TechnicalIndicators,
    signalType: 'buy' | 'sell',
    config: ConfidenceConfig
  ): number {
    let score = 0.5;
    let totalWeight = 0;
    const factors = config.factors;

    // RSI (range factor)
    const rsiCfg = factors.rsi;
    if (rsiCfg && rsiCfg.type === 'range' && rsiCfg.bins && indicators.rsi != null) {
      const rsi = indicators.rsi;
      for (const bin of rsiCfg.bins) {
        if (rsi >= bin.range[0] && rsi < bin.range[1]) {
          if (!bin.neutral) {
            // score_bonus is signed: positive = good for buy, negative = good for sell
            const bonus = bin.score_bonus;
            if (signalType === 'buy') {
              score += bonus * (rsiCfg.weight || 0.1) * 10;
            } else {
              score -= bonus * (rsiCfg.weight || 0.1) * 10; // mirror for sell
            }
          }
          break;
        }
      }
      totalWeight += Math.abs(rsiCfg.weight || 0);
    }

    // MA Bullish (boolean, buy direction)
    const maBullCfg = factors.ma_bullish;
    if (maBullCfg && maBullCfg.type === 'boolean' && maBullCfg.direction === 'buy') {
      const isBullish = (indicators.ma5 ?? 0) > (indicators.ma20 ?? 0) &&
                        (indicators.ma20 ?? 0) > (indicators.ma60 ?? 0);
      if (isBullish) {
        // Scale excess_return: ±2.5% → ±0.125 bonus, bounded ±0.2 per factor
        const rawBonus = Math.max(-0.2, Math.min(0.2, (maBullCfg.excess_return ?? 0) * 5));
        score += signalType === 'buy' ? rawBonus : -rawBonus * 0.3;
      }
      totalWeight += Math.abs(maBullCfg.weight || 0);
    }

    // MA Bearish (boolean, sell direction)
    const maBearCfg = factors.ma_bearish;
    if (maBearCfg && maBearCfg.type === 'boolean' && maBearCfg.direction === 'sell') {
      const isBearish = (indicators.ma5 ?? 0) < (indicators.ma20 ?? 0) &&
                        (indicators.ma20 ?? 0) < (indicators.ma60 ?? 0);
      if (isBearish) {
        const rawBonus = Math.max(-0.2, Math.min(0.2, (maBearCfg.excess_return ?? 0) * 5));
        score += signalType === 'sell' ? rawBonus : -rawBonus * 0.3;
      }
      totalWeight += Math.abs(maBearCfg.weight || 0);
    }

    // MA5 > MA20 (simple bullish)
    const ma5Cfg = factors.ma5_cross;
    if (ma5Cfg && ma5Cfg.type === 'boolean') {
      const isAbove = (indicators.ma5 ?? 0) > (indicators.ma20 ?? 0);
      if (isAbove) {
        const rawBonus = Math.max(-0.15, Math.min(0.15, (ma5Cfg.excess_return ?? 0) * 5));
        if (signalType === 'buy') {
          score += rawBonus;
        } else {
          score -= rawBonus * 0.3;
        }
      }
      totalWeight += Math.abs(ma5Cfg.weight || 0);
    }

    // MACD Positive (boolean, buy direction)
    const macdCfg = factors.macd_positive;
    if (macdCfg && macdCfg.type === 'boolean') {
      const macdPositive = (indicators.macd_histogram ?? 0) > 0;
      if (macdPositive) {
        const rawBonus = Math.max(-0.15, Math.min(0.15, (macdCfg.excess_return ?? 0) * 5));
        score += signalType === 'buy' ? rawBonus : -rawBonus * 0.3;
      }
      totalWeight += Math.abs(macdCfg.weight || 0);
    }

    // Volume Ratio (range factor)
    const vrCfg = factors.volume_ratio;
    if (vrCfg && vrCfg.type === 'range' && vrCfg.bins && indicators.volume_ratio != null) {
      const vr = indicators.volume_ratio;
      for (const bin of vrCfg.bins) {
        if (vr >= bin.range[0] && vr < bin.range[1]) {
          if (!bin.neutral) {
            const bonus = bin.score_bonus;
            score += bonus * (vrCfg.weight || 0.05) * 10;
          }
          break;
        }
      }
      totalWeight += Math.abs(vrCfg.weight || 0);
    }

    // Bollinger Band Position (range factor)
    const bbCfg = factors.bb_position;
    if (bbCfg && bbCfg.type === 'range' && bbCfg.bins) {
      const bbPos = this.calculateBBPosition(indicators);
      for (const bin of bbCfg.bins) {
        if (bbPos >= bin.range[0] && bbPos < bin.range[1]) {
          if (!bin.neutral) {
            const bonus = bin.score_bonus;
            if (signalType === 'buy') {
              // Low BB position = good for buy (oversold)
              score += bonus * (bbCfg.weight || 0.05) * 10;
            } else {
              // High BB position = good for sell (overbought)
              score -= bonus * (bbCfg.weight || 0.05) * 10;
            }
          }
          break;
        }
      }
      totalWeight += Math.abs(bbCfg.weight || 0);
    }

    // Clamp to [0.1, 0.95]
    return Math.max(0.1, Math.min(0.95, score));
  }

  /**
   * Hardcoded fallback — maintains backward compatibility.
   * This is the original hand-tuned logic, preserved for when no calibration
   * config exists.
   */
  private calculateConfidenceFallback(indicators: TechnicalIndicators, signalType: 'buy' | 'sell'): number {
    let score = 0.5; // Base score

    if (signalType === 'buy') {
      // RSI oversold bonus
      if (indicators.rsi < 30) {
        score += 0.2;
      } else if (indicators.rsi < 40) {
        score += 0.1;
      }

      // MA bullish alignment bonus
      if (indicators.ma5 > indicators.ma20 && indicators.ma20 > indicators.ma60) {
        score += 0.15;
      } else if (indicators.ma5 > indicators.ma20) {
        score += 0.08;
      }

      // MACD golden cross bonus
      if (indicators.macd_histogram > 0) {
        score += 0.1;
      } else if (indicators.macd_histogram > -0.1) {
        score += 0.05;
      }

      // Volume surge bonus
      if (indicators.volume_ratio > 2) {
        score += 0.1;
      } else if (indicators.volume_ratio > 1.5) {
        score += 0.05;
      }

      // Bollinger lower band bonus
      const bbPosition = this.calculateBBPosition(indicators);
      if (bbPosition < 0.2) {
        score += 0.1;
      } else if (bbPosition < 0.4) {
        score += 0.05;
      }

    } else if (signalType === 'sell') {
      // RSI overbought bonus
      if (indicators.rsi > 70) {
        score += 0.2;
      } else if (indicators.rsi > 60) {
        score += 0.1;
      }

      // MA bearish alignment bonus
      if (indicators.ma5 < indicators.ma20 && indicators.ma20 < indicators.ma60) {
        score += 0.15;
      } else if (indicators.ma5 < indicators.ma20) {
        score += 0.08;
      }

      // MACD death cross bonus
      if (indicators.macd_histogram < 0) {
        score += 0.1;
      } else if (indicators.macd_histogram < 0.1) {
        score += 0.05;
      }

      // Volume decline penalty
      if (indicators.volume_ratio < 0.5) {
        score += 0.05;
      }

      // Bollinger upper band bonus
      const bbPosition = this.calculateBBPosition(indicators);
      if (bbPosition > 0.8) {
        score += 0.1;
      } else if (bbPosition > 0.6) {
        score += 0.05;
      }
    }

    // Clamp to [0.1, 0.9]
    return Math.max(0.1, Math.min(0.9, score));
  }

  /**
   * Calculate Bollinger Band position (0-1)
   */
  private calculateBBPosition(indicators: TechnicalIndicators): number {
    const upper = indicators.bollinger_upper;
    const lower = indicators.bollinger_lower;
    const mid = indicators.bollinger_mid;

    if (!upper || !lower || upper === lower) {
      return 0.5;
    }

    // Use mid as proxy for current price if close not available
    const price = mid || (upper + lower) / 2;
    return (price - lower) / (upper - lower);
  }

  /**
   * Extract features from signal for ML prediction
   */
  private extractFeatures(signal: Signal): any {
    const ind = signal.indicators as unknown as TechnicalIndicators;
    return {
      rsi: ind.rsi || 50,
      ma5_ma20_ratio: ind.ma5 && ind.ma20 ? ind.ma5 / ind.ma20 : 1,
      ma20_ma60_ratio: ind.ma20 && ind.ma60 ? ind.ma20 / ind.ma60 : 1,
      macd_histogram: ind.macd_histogram || 0,
      bb_position: this.calculateBBPosition(ind),
      volume_ratio: ind.volume_ratio || 1,
      conditions_matched_ratio: this.calculateConditionsRatio(signal.reason),
      action: signal.action === 'buy' ? 0 : 1
    };
  }

  /**
   * Calculate conditions matched ratio from reason string
   */
  private calculateConditionsRatio(reason: string): number {
    if (!reason) return 0.5;
    const count = reason.split(',').length;
    return Math.min(count / 3, 1.0);
  }

  /**
   * Predict confidence using ML model with fallback to rule-based
   */
  async predictConfidence(signal: Signal, retries: number = 2): Promise<number> {
    // Import callPythonResilient dynamically
    try {
// @ts-ignore - Module stub needed
      const pythonCaller = await import('../../infrastructure/tools/shared/python-caller-resilient-adapter.js');
      const { callPythonResilient } = pythonCaller;

      // Level 1: Try XGBoost ML model
      for (let i = 0; i < retries; i++) {
        try {
          const features = this.extractFeatures(signal);
          const result = await callPythonResilient('predict_signal_confidence', { features });
          const data = JSON.parse(result);

          if (data.confidence !== null && data.confidence !== undefined) {
            return data.confidence;
          }
        } catch (error) {
          if (i === retries - 1) {
            // All retries failed, fall back to rule-based
            break;
          }
          await this.sleep(1000 * (i + 1));
        }
      }
    } catch (importError) {
      // python-caller not available, use rule-based
    }

    // Level 2: Data-driven or rule-based fallback
    const ind = signal.indicators as unknown as TechnicalIndicators;
    return this.calculateConfidence(ind, signal.action as 'buy' | 'sell');
  }

  /**
   * Sleep helper for retry logic
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Save signals to database
   */
  async saveSignals(date: string, signals: Signal[]): Promise<void> {
    const db = new Database(this.dbPath);

    try {
      const stmt = db.prepare(`
        INSERT INTO signals (date, symbol, name, action, action_type, strategy_id, price, reason, confidence, indicators)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);

      const insertMany = db.transaction((signals: Signal[]) => {
        for (const signal of signals) {
          stmt.run(
            signal.date,
            signal.symbol,
            signal.name,
            signal.action,
            signal.action_type,
            signal.strategy_id,
            signal.price,
            signal.reason,
            signal.confidence,
            JSON.stringify(signal.indicators)
          );
        }
      });

      insertMany(signals);
    } finally {
      db.close();
    }
  }

  /**
   * Load signals from database
   */
  async loadSignals(date: string): Promise<Signal[]> {
    const db = new Database(this.dbPath, { readonly: true });

    try {
      const stmt = db.prepare(`
        SELECT * FROM signals WHERE date = ? ORDER BY created_at DESC
      `);

      const rows = stmt.all(date) as any[];

      return rows.map(row => ({
        date: row.date,
        symbol: row.symbol,
        name: row.name,
        action: row.action,
        action_type: row.action_type,
        strategy_id: row.strategy_id,
        price: row.price,
        reason: row.reason,
        confidence: row.confidence,
        indicators: row.indicators ? JSON.parse(row.indicators) : undefined
      }));
    } finally {
      db.close();
    }
  }

  /**
   * Combine multiple signals using Python combiner
   */
  async combineSignals(
    signals: Signal[],
    mode: 'or' | 'and' | 'vote' = 'vote',
    weights?: Record<string, number>,
    confidenceThreshold: number = 0.5
  ): Promise<{ signals: Signal[], metadata: any }> {
    // Validate empty input
    if (signals.length === 0) {
      return { signals: [], metadata: { empty: true } };
    }

    try {
      // Import dynamically to avoid circular dependency
// @ts-ignore - Module stub needed
      const pythonCaller = await import('../../infrastructure/tools/shared/python-caller-resilient-adapter.js');
      const { callPythonResilient } = pythonCaller;

      // Convert TypeScript signals to Python format
      const pythonSignals = signals.map(s => ({
        timestamp: new Date(s.date).toISOString().split('.')[0],  // Convert date string to ISO timestamp
        symbol: s.symbol,
        action: s.action,
        price: s.price,
        quantity: 0,
        strategy_id: s.strategy_id,
        confidence: s.confidence,
        reason: s.reason
      }));

      // Call Python combiner
      const result = await callPythonResilient('combine_strategy_signals', {
        signals: pythonSignals,
        mode,
        weights: weights || {},
        confidence_threshold: confidenceThreshold
      });

      const data = JSON.parse(result);

      // Check for errors
      if ((data as any).error) {
        console.warn('Python combiner error, falling back to OR mode:', data.error);
        return {
          signals: signals,  // Return all signals (OR mode fallback)
          metadata: {
            fallback: true,
            reason: 'python_error',
            error: data.error
          }
        };
      }

      // Convert Python signals back to TypeScript format
      const combinedSignals: Signal[] = data.combined_signals.map((s: any) => {
        // Extract date from ISO timestamp with validation
        const date = s.timestamp.includes('T') ? s.timestamp.split('T')[0] : s.timestamp;

        // Find matching signal by symbol for name lookup
        const matchingSignal = signals.find(sig => sig.symbol === s.symbol);
        if (!matchingSignal) {
          console.warn(`No matching signal found for symbol ${s.symbol}, using symbol as name`);
        }

        // Find indicators by matching both symbol AND strategy_id
        const indicatorsSource = signals.find(sig =>
          sig.symbol === s.symbol && sig.strategy_id === s.strategy_id
        );

        // Determine action_type from action string
        const action_type = s.action === 'sell' ? SignalActionType.SELL : SignalActionType.BUY;

        return {
          date,
          symbol: s.symbol,
          name: matchingSignal?.name || s.symbol,
          action: s.action as 'buy' | 'sell',
          action_type,
          strategy_id: s.strategy_id,
          price: s.price,
          reason: s.reason,
          confidence: s.confidence,
          indicators: indicatorsSource?.indicators
        };
      });

      return {
        signals: combinedSignals,
        metadata: data.metadata
      };

    } catch (error) {
      console.error('combineSignals error:', error);
      // Fallback: return all signals (OR mode)
      return {
        signals: signals,
        metadata: {
          fallback: true,
          reason: 'exception',
          error: error instanceof Error ? error.message : String(error)
        }
      };
    }
  }

  /**
   * Scan market with multiple strategies and combine signals
   */
  async scanMarketMultiStrategy(
    strategies: QuantStrategy[],
    stockData: StockData[],
    mode: 'or' | 'and' | 'vote' = 'vote',
    weights?: Record<string, number>,
    confidenceThreshold: number = 0.5,
    useArbiter: boolean = true
  ): Promise<Signal[]> {
    // Step 1: Generate signals for each strategy
    const allSignals: Signal[] = [];

    for (const strategy of strategies) {
      const strategySignals = await this.scanMarket(strategy, stockData, confidenceThreshold);
      allSignals.push(...strategySignals);
    }

    // Step 2: Group signals by symbol
    const signalsBySymbol = new Map<string, Signal[]>();
    for (const signal of allSignals) {
      const existing = signalsBySymbol.get(signal.symbol) || [];
      existing.push(signal);
      signalsBySymbol.set(signal.symbol, existing);
    }

    // Step 3: Combine signals for each symbol
    const combinedSignals: Signal[] = [];

    for (const [symbol, signals] of signalsBySymbol.entries()) {
      // Only combine if multiple strategies generated signals for this symbol
      if (signals.length > 1) {
        const { signals: combined } = await this.combineSignals(
          signals,
          mode,
          weights,
          confidenceThreshold
        );
        combinedSignals.push(...combined);
      } else {
        // Single signal, keep as-is
        combinedSignals.push(signals[0]);
      }
    }

    // Step 4: Apply signal arbiter to resolve conflicts
    if (useArbiter) {
      const arbiterResult = this.arbiter.arbitrate(combinedSignals);

      // Log conflicts if any
      if (arbiterResult.conflicts.length > 0) {
        console.log(`\n⚠️  检测到 ${arbiterResult.conflicts.length} 个信号冲突:`);
        for (const conflict of arbiterResult.conflicts) {
          console.log(`  - ${conflict.symbol} (${conflict.name}): ${conflict.resolution} - ${conflict.reason}`);
        }
        console.log(`\n📊 裁决统计:`);
        console.log(`  输入信号: ${arbiterResult.stats.totalInput}`);
        console.log(`  输出信号: ${arbiterResult.stats.totalOutput}`);
        console.log(`  丢弃信号: ${arbiterResult.stats.signalsDiscarded}`);
        console.log(`  降级信号: ${arbiterResult.stats.signalsDowngraded}`);
      }

      return arbiterResult.signals;
    }

    return combinedSignals;
  }

  /**
   * Get signal arbiter instance for advanced usage
   */
  getArbiter(): SignalArbiter {
    return this.arbiter;
  }

  /**
   * Get conflict statistics from arbiter
   */
  getConflictStats() {
    return this.arbiter.getConflictStats();
  }
}
