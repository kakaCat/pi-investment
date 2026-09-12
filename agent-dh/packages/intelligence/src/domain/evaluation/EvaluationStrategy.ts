/**
 * EvaluationStrategy - 评估策略接口
 * 
 * DDD 设计：策略模式，每种决策类型有对应的评估策略
 */

import type { Outcome } from '../decision/Outcome';
import type { DecisionType } from '../decision/DecisionType';

/**
 * 市场数据提供者接口（端口）
 */
export interface MarketDataProvider {
  /**
   * 获取价格历史数据
   */
  getPriceHistory(
    symbol: string,
    startDate: Date,
    days: number
  ): Promise<PriceData[]>;
  
  /**
   * 获取交易执行记录
   */
  getTradeExecution(
    symbol: string,
    orderId?: string
  ): Promise<TradeExecution | null>;
  
  /**
   * 获取当前持仓
   */
  getCurrentPosition(
    symbol: string,
    accountName?: string
  ): Promise<Position | null>;
}

export interface PriceData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TradeExecution {
  symbol: string;
  action: 'BUY' | 'SELL';
  quantity: number;
  avgPrice: number;
  fillTime: Date;
}

export interface Position {
  symbol: string;
  quantity: number;
  avgCost: number;
  currentPrice: number;
  pnl: number;
  pnlPct: number;
}

/**
 * 决策评估上下文
 */
export interface DecisionContext {
  decisionId: string;
  decisionType: DecisionType;
  timestamp: Date;
  reasoning: string;
  marketContext?: Record<string, any>;
}

/**
 * 评估策略接口
 */
export interface EvaluationStrategy {
  /**
   * 策略名称
   */
  readonly name: string;
  
  /**
   * 评估决策
   */
  evaluate(
    context: DecisionContext,
    marketData: MarketDataProvider
  ): Promise<Outcome>;
  
  /**
   * 获取所需的数据窗口（天数）
   */
  getRequiredDataWindow(): number;
  
  /**
   * 检查是否可以评估（数据窗口是否足够）
   */
  canEvaluateNow(decisionTimestamp: Date): boolean;
}

/**
 * 评估策略基类
 */
export abstract class BaseEvaluationStrategy implements EvaluationStrategy {
  abstract readonly name: string;
  
  abstract evaluate(
    context: DecisionContext,
    marketData: MarketDataProvider
  ): Promise<Outcome>;
  
  abstract getRequiredDataWindow(): number;
  
  canEvaluateNow(decisionTimestamp: Date): boolean {
    const requiredDays = this.getRequiredDataWindow();
    const daysSinceDecision = Math.floor(
      (Date.now() - decisionTimestamp.getTime()) / (1000 * 60 * 60 * 24)
    );
    return daysSinceDecision >= requiredDays;
  }
  
  /**
   * 计算价格变化百分比
   */
  protected calculatePriceChange(priceData: PriceData[]): number {
    if (priceData.length < 2) return 0;
    const firstPrice = priceData[0].close;
    const lastPrice = priceData[priceData.length - 1].close;
    return ((lastPrice - firstPrice) / firstPrice) * 100;
  }
  
  /**
   * 计算最大涨幅
   */
  protected calculateMaxGain(priceData: PriceData[]): number {
    if (priceData.length === 0) return 0;
    const firstPrice = priceData[0].close;
    const maxPrice = Math.max(...priceData.map(p => p.high));
    return ((maxPrice - firstPrice) / firstPrice) * 100;
  }
}
