import fs from 'fs/promises';
import path from 'path';
import { Signal, QuantStrategy } from './types';
import { TS_FUNCTIONS } from '../../infrastructure/akshare-ts/index.js';
import { StockDBService } from '../stock-db/index.js';

export class SignalGenerator {
  private signalsDir = '.pi-invest/quant/signals';
  private stockDB: StockDBService;

  constructor() {
    this.stockDB = new StockDBService('.pi-invest');
  }

  async scan(strategy: QuantStrategy): Promise<Signal[]> {
    const signals: Signal[] = [];
    const date = new Date().toISOString().split('T')[0];

    // 1. 获取股票池
    const symbols = await this.getStockPool(strategy);

    // 2. 检查每只股票
    for (const symbol of symbols) {
      try {
        const signal = await this.checkStock(symbol, strategy, date);
        if (signal) signals.push(signal);
      } catch (err) {
        console.error(`检查 ${symbol} 失败:`, err);
      }
    }

    // 3. 保存信号
    if (signals.length > 0) {
      await this.saveSignals(date, signals);
    }

    return signals;
  }

  private async checkStock(symbol: string, strategy: QuantStrategy, date: string): Promise<Signal | null> {
    // 获取实时价格
    const priceJson = await TS_FUNCTIONS['get_stock_realtime_price']({ symbol });
    const priceData = JSON.parse(priceJson);
    const price = priceData.current || priceData.price || 0;
    const name = priceData.name || symbol;

    // 获取技术指标
    const indicators = ['ma', 'rsi', 'macd'];
    const techJson = await TS_FUNCTIONS['calculate_technical_indicators']({ symbol, indicators });
    const tech = JSON.parse(techJson);

    // 检查买入条件
    const buySignal = this.matchConditions(tech, strategy.entry.conditions, strategy.entry.logic);
    if (buySignal) {
      const { confidence, model } = await this.calculateConfidence(symbol, tech, strategy.entry.conditions, 'buy');
      return {
        date,
        symbol,
        name,
        action: 'buy',
        strategy_id: strategy.id,
        price,
        reason: this.buildReason(tech, strategy.entry.conditions),
        confidence,
        indicators: tech,
      };
    }

    // 检查卖出条件
    if (strategy.exit.conditions?.length) {
      const sellSignal = this.matchConditions(tech, strategy.exit.conditions, 'OR');
      if (sellSignal) {
        const { confidence, model } = await this.calculateConfidence(symbol, tech, strategy.exit.conditions, 'sell');
        return {
          date,
          symbol,
          name,
          action: 'sell',
          strategy_id: strategy.id,
          price,
          reason: this.buildReason(tech, strategy.exit.conditions),
          confidence,
          indicators: tech,
        };
      }
    }

    return null;
  }

  private matchConditions(tech: any, conditions: any[], logic: 'AND' | 'OR'): boolean {
    const results = conditions.map(cond => this.matchCondition(tech, cond));
    return logic === 'AND' ? results.every(r => r) : results.some(r => r);
  }

  private matchCondition(tech: any, condition: any): boolean {
    const { indicator, operator, value } = condition;

    // RSI
    if (indicator === 'rsi') {
      const rsi = tech.rsi;
      if (operator === '<') return rsi < value;
      if (operator === '>') return rsi > value;
      if (operator === '<=') return rsi <= value;
      if (operator === '>=') return rsi >= value;
    }

    // 均线交叉
    if (indicator === 'ma_cross') {
      const ma5 = tech.ma5;
      const ma20 = tech.ma20;
      if (operator === 'cross_above') return ma5 > ma20;
      if (operator === 'cross_below') return ma5 < ma20;
    }

    // MACD
    if (indicator === 'macd') {
      const hist = tech.macd_histogram || 0;
      if (operator === '>') return hist > value;
      if (operator === '<') return hist < value;
      if (operator === 'golden_cross') return hist > 0;
      if (operator === 'death_cross') return hist < 0;
    }

    // 布林带
    if (indicator === 'bollinger') {
      const price = tech.close || 0;
      const upper = tech.bollinger_upper || 0;
      const lower = tech.bollinger_lower || 0;
      if (operator === 'touch_lower') return price <= lower * 1.01;
      if (operator === 'touch_upper') return price >= upper * 0.99;
      if (operator === 'break_upper') return price > upper;
      if (operator === 'break_lower') return price < lower;
    }

    return false;
  }

  private buildReason(tech: any, conditions: any[]): string {
    const reasons = conditions.map(c => {
      if (c.indicator === 'rsi') return `RSI=${tech.rsi?.toFixed(2)}`;
      if (c.indicator === 'ma_cross') return `MA5=${tech.ma5?.toFixed(2)} MA20=${tech.ma20?.toFixed(2)}`;
      if (c.indicator === 'macd') return `MACD柱=${tech.macd_histogram?.toFixed(4)}`;
      if (c.indicator === 'bollinger') return `价格=${tech.close?.toFixed(2)} 下轨=${tech.bollinger_lower?.toFixed(2)}`;
      return '';
    });
    return reasons.filter(r => r).join(', ');
  }

  private calculateRuleConfidence(tech: any, conditions: any[], action: 'buy' | 'sell'): number {
    if (conditions.length === 0) return 0.5;

    // 基础分：匹配条件数 / 总条件数
    const matchedCount = conditions.filter(c => this.matchCondition(tech, c)).length;
    let confidence = matchedCount / conditions.length;

    // 强信号 bonus
    const rsi = tech.rsi || 50;
    const price = tech.close || 0;
    const bbLower = tech.bollinger_lower || 0;
    const bbUpper = tech.bollinger_upper || 0;

    if (action === 'buy') {
      if (rsi < 30) confidence += 0.1;
      if (bbLower > 0 && price <= bbLower * 1.01) confidence += 0.1;
    } else {
      if (rsi > 70) confidence += 0.1;
      if (bbUpper > 0 && price >= bbUpper * 0.99) confidence += 0.1;
    }

    return Math.min(confidence, 1.0);
  }

  private async calculateConfidence(symbol: string, tech: any, conditions: any[], action: 'buy' | 'sell'): Promise<{ confidence: number; model: string }> {
    // 尝试 ML 预测
    try {
      const matchedCount = conditions.filter(c => this.matchCondition(tech, c)).length;
      tech.conditions_matched_ratio = conditions.length > 0 ? matchedCount / conditions.length : 0;

      const mlJson = await TS_FUNCTIONS['predict_signal_confidence']({ symbol, indicators: tech, action });
      const mlResult = JSON.parse(mlJson);

      if (mlResult.model === 'xgboost' && mlResult.confidence != null) {
        return { confidence: mlResult.confidence, model: 'xgboost' };
      }
    } catch (err) {
      // ML 失败，回退到规则
    }

    // 回退到规则
    return { confidence: this.calculateRuleConfidence(tech, conditions, action), model: 'rule' };
  }

  private async getStockPool(strategy: QuantStrategy): Promise<string[]> {
    // 使用数据库筛选
    const filters = strategy.screening?.filters || {};

    const stocks = this.stockDB.filter({
      market: strategy.screening?.market || 'A',
      min_market_cap: 50,
      max_pe: filters.pe_range?.[1],
      max_pb: filters.pb_range?.[1],
      exclude_st: true,
      exclude_suspended: true,
      list_days: 365
    });

    return stocks.slice(0, 100).map(s => s.symbol); // 限制100只
  }

  private async saveSignals(date: string, signals: Signal[]): Promise<void> {
    await fs.mkdir(this.signalsDir, { recursive: true });
    await fs.writeFile(
      path.join(this.signalsDir, `${date}.json`),
      JSON.stringify(signals, null, 2)
    );
  }

  async getSignals(date?: string): Promise<Signal[]> {
    const targetDate = date || new Date().toISOString().split('T')[0];
    try {
      const content = await fs.readFile(
        path.join(this.signalsDir, `${targetDate}.json`),
        'utf-8'
      );
      return JSON.parse(content);
    } catch {
      return [];
    }
  }
}
