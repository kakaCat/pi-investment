/**
 * ObservationEvaluationStrategy - 观察决策评估策略
 * 
 * 评估逻辑：
 * 1. 获取观察期内的价格走势
 * 2. 判断观察理由是否成立（如"等回调"看是否真的回调了）
 * 3. 评估观察决策的质量
 */

import { BaseEvaluationStrategy, type DecisionContext, type MarketDataProvider } from './EvaluationStrategy';
import { Outcome } from '../decision/Outcome';
import { ObservationDecision } from '../decision/DecisionType';

export class ObservationEvaluationStrategy extends BaseEvaluationStrategy {
  readonly name = 'ObservationEvaluationStrategy';
  
  async evaluate(
    context: DecisionContext,
    marketData: MarketDataProvider
  ): Promise<Outcome> {
    const observation = context.decisionType as ObservationDecision;
    
    // 1. 获取观察期内的价格走势
    const priceData = await marketData.getPriceHistory(
      observation.symbol,
      context.timestamp,
      observation.watchDays
    );
    
    if (priceData.length === 0) {
      return new Outcome(
        false,
        50,
        { priceChangeAfterDecision: 0 },
        '无法获取价格数据',
        0.1
      );
    }
    
    // 2. 计算价格变化
    const priceChange = this.calculatePriceChange(priceData);
    const maxGain = this.calculateMaxGain(priceData);
    
    // 3. 根据观察理由判断决策质量
    let success = false;
    let score = 50;
    let lesson = '';
    
    const reason = observation.reason.toLowerCase();
    
    // 情况1：等待回调
    if (reason.includes('回调') || reason.includes('等待')) {
      if (priceChange < -3) {
        // 确实回调了，观察决策正确
        success = true;
        score = 80 + Math.min(20, Math.abs(priceChange));
        lesson = `等待策略有效，${observation.watchDays}天内回调${Math.abs(priceChange).toFixed(1)}%，耐心等待是正确的`;
      } else if (priceChange > 10) {
        // 等了个寂寞，直接起飞了
        success = false;
        score = Math.max(0, 50 - priceChange);
        lesson = `等待失误，${observation.watchDays}天内上涨${priceChange.toFixed(1)}%，错过机会成本${priceChange.toFixed(1)}%`;
      } else {
        // 横盘或小幅波动，观察决策合理
        success = true;
        score = 70;
        lesson = `等待决策合理，${observation.watchDays}天内波动${priceChange.toFixed(1)}%，未出现明显机会`;
      }
    }
    
    // 情况2：观察突破
    else if (reason.includes('突破') || reason.includes('观察')) {
      const didBreak = maxGain > 5;
      
      if (didBreak && priceChange > 5) {
        // 突破且持续，观察有效
        success = true;
        score = 80;
        lesson = `突破观察有效，${observation.watchDays}天内最高涨${maxGain.toFixed(1)}%，可以考虑介入`;
      } else if (priceChange < -5) {
        // 没突破反而跌了，观察避免了损失
        success = true;
        score = 85;
        lesson = `突破观察避免损失，${observation.watchDays}天内下跌${Math.abs(priceChange).toFixed(1)}%，未突破是对的`;
      } else {
        // 横盘或假突破
        success = true;
        score = 70;
        lesson = `突破观察合理，${observation.watchDays}天内波动${priceChange.toFixed(1)}%，未见明显突破`;
      }
    }
    
    // 情况3：其他观察理由（通用评估）
    else {
      if (priceChange > 15) {
        // 观察期错过大机会
        success = false;
        score = Math.max(20, 100 - priceChange * 2);
        lesson = `观察期错过机会，${observation.watchDays}天内上涨${priceChange.toFixed(1)}%，机会成本${priceChange.toFixed(1)}%`;
      } else if (priceChange < -10) {
        // 观察避免了损失
        success = true;
        score = 85;
        lesson = `观察决策避免损失，${observation.watchDays}天内下跌${Math.abs(priceChange).toFixed(1)}%`;
      } else {
        // 正常波动
        success = true;
        score = 70;
        lesson = `观察决策合理，${observation.watchDays}天内涨跌${priceChange.toFixed(1)}%`;
      }
    }
    
    return new Outcome(
      success,
      score,
      {
        priceChangeAfterDecision: priceChange,
        missedOpportunity: !success && priceChange > 10,
        opportunityCost: !success ? priceChange : 0,
      },
      lesson,
      0.8  // 观察决策评估有一定主观性
    );
  }
  
  getRequiredDataWindow(): number {
    return 5;  // 默认观察 5 天后评估
  }
}
