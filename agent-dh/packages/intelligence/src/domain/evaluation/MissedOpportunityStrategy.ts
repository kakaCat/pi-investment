/**
 * MissedOpportunityStrategy - 错过机会检测策略
 * 
 * 评估逻辑：
 * 1. 获取决策后的价格表现
 * 2. 判断是否错过重大机会（涨幅 > 15%）
 * 3. 分析跳过理由是否成立
 */

import { BaseEvaluationStrategy, type DecisionContext, type MarketDataProvider } from './EvaluationStrategy';
import { Outcome } from '../decision/Outcome';
import { SkipDecision } from '../decision/DecisionType';

export class MissedOpportunityStrategy extends BaseEvaluationStrategy {
  readonly name = 'MissedOpportunityStrategy';
  
  async evaluate(
    context: DecisionContext,
    marketData: MarketDataProvider
  ): Promise<Outcome> {
    const skip = context.decisionType as SkipDecision;
    
    // 1. 获取决策后的价格表现
    const priceData = await marketData.getPriceHistory(
      skip.symbol,
      context.timestamp,
      skip.checkDays
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
    
    // 2. 计算价格变化和最大涨幅
    const priceChange = this.calculatePriceChange(priceData);
    const maxGain = this.calculateMaxGain(priceData);
    
    // 3. 判断是否错过重大机会
    const missedOpportunity = priceChange > 15 || maxGain > 20;
    
    // 4. 分析跳过理由
    const reason = skip.reason.toLowerCase();
    let reasonCategory = 'other';
    
    if (reason.includes('估值') || reason.includes('贵') || reason.includes('高')) {
      reasonCategory = 'valuation';
    } else if (reason.includes('技术') || reason.includes('走坏') || reason.includes('破位')) {
      reasonCategory = 'technical';
    } else if (reason.includes('基本面') || reason.includes('业绩') || reason.includes('风险')) {
      reasonCategory = 'fundamental';
    }
    
    // 5. 综合评估
    let success = false;
    let score = 50;
    let lesson = '';
    
    if (missedOpportunity) {
      // 确实错过机会
      success = false;
      score = Math.max(0, 100 - priceChange * 1.5);
      
      if (reasonCategory === 'valuation') {
        lesson = `"${skip.reason}"估值判断失误，${skip.checkDays}天内上涨${priceChange.toFixed(1)}%（最高${maxGain.toFixed(1)}%），市场不理会估值短期炒作，错过机会成本${priceChange.toFixed(1)}%`;
      } else if (reasonCategory === 'technical') {
        lesson = `"${skip.reason}"技术判断失误，${skip.checkDays}天内上涨${priceChange.toFixed(1)}%（最高${maxGain.toFixed(1)}%），技术破位后反转，错过机会成本${priceChange.toFixed(1)}%`;
      } else {
        lesson = `"${skip.reason}"判断失误，${skip.checkDays}天内上涨${priceChange.toFixed(1)}%（最高${maxGain.toFixed(1)}%），错过重大机会`;
      }
    } else if (priceChange > 5 && priceChange <= 15) {
      // 小幅上涨，跳过合理但略显保守
      success = true;
      score = 70 - priceChange;
      lesson = `"${skip.reason}"判断偏保守，${skip.checkDays}天内涨${priceChange.toFixed(1)}%，虽未错过重大机会但略显谨慎`;
    } else if (priceChange < -5) {
      // 跳过避免了损失，决策正确
      success = true;
      score = 90 + Math.min(10, Math.abs(priceChange) / 2);
      lesson = `"${skip.reason}"判断正确，${skip.checkDays}天内下跌${Math.abs(priceChange).toFixed(1)}%，成功避免损失`;
    } else {
      // 横盘或小幅波动，跳过合理
      success = true;
      score = 80;
      lesson = `"${skip.reason}"判断合理，${skip.checkDays}天内涨跌${priceChange.toFixed(1)}%，跳过决策适当`;
    }
    
    return new Outcome(
      success,
      score,
      {
        priceChangeAfterDecision: priceChange,
        missedOpportunity: missedOpportunity,
        opportunityCost: missedOpportunity ? priceChange : 0,
      },
      lesson,
      0.85  // 跳过决策评估置信度较高（价格是客观的）
    );
  }
  
  getRequiredDataWindow(): number {
    return 10;  // 默认 10 天后评估是否错过机会
  }
}
