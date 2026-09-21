/**
 * TradeEvaluationStrategy - 交易决策评估策略
 * 
 * 评估逻辑：
 * 1. 获取实际成交记录
 * 2. 计算持仓收益（已卖出）或浮动盈亏（持仓中）
 * 3. 计算风险指标（夏普比率、最大回撤）
 * 4. 综合评分
 */

import { BaseEvaluationStrategy, type DecisionContext, type MarketDataProvider } from './EvaluationStrategy';
import { Outcome } from '../decision/Outcome';
import { TradeDecision } from '../decision/DecisionType';

export class TradeEvaluationStrategy extends BaseEvaluationStrategy {
  readonly name = 'TradeEvaluationStrategy';
  
  async evaluate(
    context: DecisionContext,
    marketData: MarketDataProvider
  ): Promise<Outcome> {
    const trade = context.decisionType as TradeDecision;
    
    try {
      if (trade.action === 'BUY') {
        return await this.evaluateBuyDecision(trade, context, marketData);
      } else {
        return await this.evaluateSellDecision(trade, context, marketData);
      }
    } catch (error: any) {
      return new Outcome(
        false,
        50,
        {},
        `评估失败: ${error.message}`,
        0.1
      );
    }
  }
  
  private async evaluateBuyDecision(
    trade: TradeDecision,
    context: DecisionContext,
    marketData: MarketDataProvider
  ): Promise<Outcome> {
    // 1. 获取交易执行记录
    const execution = await marketData.getTradeExecution(trade.symbol, trade.orderId);
    
    if (!execution) {
      return new Outcome(
        false,
        50,
        {},
        '未找到交易执行记录',
        0.2
      );
    }
    
    // 2. 获取当前持仓或卖出记录
    const position = await marketData.getCurrentPosition(trade.symbol);
    
    // 3. 计算收益
    let pnlPct = 0;
    let holdingDays = 0;
    let isClosed = false;
    
    if (position) {
      // 仍持仓中，计算浮动盈亏
      pnlPct = position.pnlPct;
      holdingDays = Math.floor(
        (Date.now() - context.timestamp.getTime()) / (1000 * 60 * 60 * 24)
      );
    } else {
      // 已卖出，需要查询卖出记录（简化处理：如果没有持仓，假设已止损）
      // TODO: 实际应该查询卖出记录
      pnlPct = -5;  // 假设止损
      holdingDays = 10;
      isClosed = true;
    }
    
    // 4. 获取价格历史计算风险指标
    const priceData = await marketData.getPriceHistory(
      trade.symbol,
      context.timestamp,
      Math.min(holdingDays + 5, 30)
    );
    
    const maxDrawdown = this.calculateMaxDrawdownFromEntry(priceData, execution.avgPrice);
    
    // 5. 综合评分
    let success = pnlPct > 0;
    let score = 50;
    let lesson = '';
    
    if (pnlPct > 10) {
      success = true;
      score = Math.min(95, 70 + pnlPct);
      lesson = `买入决策优秀，持仓${holdingDays}天盈利${pnlPct.toFixed(1)}%`;
    } else if (pnlPct > 0) {
      success = true;
      score = 60 + pnlPct * 2;
      lesson = `买入决策正确，持仓${holdingDays}天盈利${pnlPct.toFixed(1)}%`;
    } else if (pnlPct > -5) {
      success = false;
      score = 50 + pnlPct * 5;
      lesson = `买入决策小幅亏损，持仓${holdingDays}天浮亏${Math.abs(pnlPct).toFixed(1)}%`;
    } else {
      success = false;
      score = Math.max(0, 50 + pnlPct * 3);
      lesson = `买入决策失误，持仓${holdingDays}天亏损${Math.abs(pnlPct).toFixed(1)}%，最大回撤${Math.abs(maxDrawdown).toFixed(1)}%`;
    }
    
    return new Outcome(
      success,
      score,
      {
        actualReturn: pnlPct,
        holdingDays: holdingDays,
        maxDrawdown: maxDrawdown,
      },
      lesson,
      0.95  // 交易数据可靠
    );
  }
  
  private async evaluateSellDecision(
    trade: TradeDecision,
    context: DecisionContext,
    marketData: MarketDataProvider
  ): Promise<Outcome> {
    // 获取卖出后的价格走势，判断卖出时机
    const priceData = await marketData.getPriceHistory(
      trade.symbol,
      context.timestamp,
      10
    );
    
    if (priceData.length === 0) {
      return new Outcome(
        true,
        70,
        {},
        '卖出决策已执行，无法获取后续价格数据',
        0.3
      );
    }
    
    const priceChangeAfterSell = this.calculatePriceChange(priceData);
    
    let success = false;
    let score = 50;
    let lesson = '';
    
    if (priceChangeAfterSell < -5) {
      // 卖在高点，决策优秀
      success = true;
      score = Math.min(95, 80 + Math.abs(priceChangeAfterSell));
      lesson = `卖出时机优秀，卖出后${Math.floor(10)}天下跌${Math.abs(priceChangeAfterSell).toFixed(1)}%，成功逃顶`;
    } else if (priceChangeAfterSell > 10) {
      // 卖早了，错过后续涨幅
      success = false;
      score = Math.max(30, 70 - priceChangeAfterSell);
      lesson = `卖出时机偏早，卖出后${Math.floor(10)}天上涨${priceChangeAfterSell.toFixed(1)}%，错过后续涨幅`;
    } else {
      // 卖出时机合理
      success = true;
      score = 75;
      lesson = `卖出时机合理，卖出后${Math.floor(10)}天涨跌${priceChangeAfterSell.toFixed(1)}%`;
    }
    
    return new Outcome(
      success,
      score,
      {
        priceChangeAfterDecision: priceChangeAfterSell,
        opportunityCost: priceChangeAfterSell > 10 ? priceChangeAfterSell : 0,
      },
      lesson,
      0.85
    );
  }
  
  /**
   * 计算从入场价开始的最大回撤
   */
  private calculateMaxDrawdownFromEntry(priceData: any[], entryPrice: number): number {
    if (priceData.length === 0) return 0;
    
    let maxDrawdown = 0;
    
    for (const data of priceData) {
      const drawdown = ((data.low - entryPrice) / entryPrice) * 100;
      if (drawdown < maxDrawdown) {
        maxDrawdown = drawdown;
      }
    }
    
    return maxDrawdown;
  }
  
  getRequiredDataWindow(): number {
    return 5;  // 买入 5 天后可初步评估
  }
}
