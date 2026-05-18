import fs from 'fs/promises';
import path from 'path';
import { Signal, QuantStrategy, EntryCondition } from './types.js';
import { FactorLibrary, TechnicalIndicators } from './factor-library.js';

export interface StockData {
  symbol: string;
  name: string;
  price: number;
  tech: TechnicalIndicators;
}

export class SignalGenerator {
  private signalsDir: string;
  private factorLib: FactorLibrary;
  private useML: boolean;

  constructor(signalsDir: string = '.pi-invest/quant/signals', factorLib?: FactorLibrary, useML: boolean = true) {
    this.signalsDir = signalsDir;
    this.factorLib = factorLib || new FactorLibrary();
    this.useML = useML;
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

      const signal: Signal = {
        date: new Date().toISOString().split('T')[0],
        symbol,
        name,
        action,
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
   * Calculate confidence score based on technical indicators
   */
  private calculateConfidence(indicators: TechnicalIndicators, signalType: 'buy' | 'sell'): number {
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
    const ind = signal.indicators as TechnicalIndicators;
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

    // Level 2: Rule-based fallback
    const ind = signal.indicators as TechnicalIndicators;
    return this.calculateConfidence(ind, signal.action);
  }

  /**
   * Sleep helper for retry logic
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Save signals to file
   */
  async saveSignals(date: string, signals: Signal[]): Promise<void> {
    await fs.mkdir(this.signalsDir, { recursive: true });
    const filePath = path.join(this.signalsDir, `${date}.json`);
    await fs.writeFile(filePath, JSON.stringify(signals, null, 2), 'utf-8');
  }

  /**
   * Load signals from file
   */
  async loadSignals(date: string): Promise<Signal[]> {
    try {
      const filePath = path.join(this.signalsDir, `${date}.json`);
      const content = await fs.readFile(filePath, 'utf-8');
      return JSON.parse(content);
    } catch {
      return [];
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
    try {
      // Import dynamically to avoid circular dependency
      const pythonCaller = await import('../../infrastructure/tools/shared/python-caller-resilient-adapter.js');
      const { callPythonResilient } = pythonCaller;

      // Convert TypeScript signals to Python format
      const pythonSignals = signals.map(s => ({
        timestamp: s.date + 'T00:00:00',  // Convert date string to ISO timestamp
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
      if (data.error) {
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
      const combinedSignals: Signal[] = data.combined_signals.map((s: any) => ({
        date: s.timestamp.split('T')[0],  // Extract date from ISO timestamp
        symbol: s.symbol,
        name: signals.find(sig => sig.symbol === s.symbol)?.name || s.symbol,
        action: s.action as 'buy' | 'sell',
        strategy_id: s.strategy_id,
        price: s.price,
        reason: s.reason,
        confidence: s.confidence,
        indicators: signals.find(sig => sig.strategy_id === s.strategy_id)?.indicators
      }));

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
    confidenceThreshold: number = 0.5
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

    return combinedSignals;
  }
}
