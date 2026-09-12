/**
 * StrategyFactory - 评估策略工厂
 * 
 * 根据决策类型创建对应的评估策略实例
 */

import type { EvaluationStrategy } from './EvaluationStrategy';
import { ObservationEvaluationStrategy } from './ObservationEvaluationStrategy';
import { MissedOpportunityStrategy } from './MissedOpportunityStrategy';
import { TradeEvaluationStrategy } from './TradeEvaluationStrategy';

export class StrategyFactory {
  private static strategies = new Map<string, EvaluationStrategy>([
    ['ObservationEvaluationStrategy', new ObservationEvaluationStrategy()],
    ['MissedOpportunityStrategy', new MissedOpportunityStrategy()],
    ['TradeEvaluationStrategy', new TradeEvaluationStrategy()],
    // PoolEvaluationStrategy 暂时保持现有实现，不在此处实现
  ]);
  
  static getStrategy(strategyName: string): EvaluationStrategy {
    const strategy = this.strategies.get(strategyName);
    
    if (!strategy) {
      throw new Error(`Unknown evaluation strategy: ${strategyName}`);
    }
    
    return strategy;
  }
  
  /**
   * 注册新策略（用于扩展）
   */
  static registerStrategy(name: string, strategy: EvaluationStrategy): void {
    this.strategies.set(name, strategy);
  }
}
