/**
 * 决策评估集成测试
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { DecisionEvaluationService } from '../src/services/DecisionEvaluationService';
import type { MarketDataProvider } from '../src/domain/evaluation/EvaluationStrategy';
import type { IDecisionRepository, DecisionRecord } from '../src/services/DecisionEvaluationService';
import { Outcome } from '../src/domain/decision/Outcome';

// Mock MarketDataProvider
class MockMarketDataProvider implements MarketDataProvider {
  async getPriceHistory(symbol: string, startDate: Date, days: number) {
    // 模拟价格上涨 10%
    return [
      { date: '2024-01-01', open: 100, high: 105, low: 99, close: 102, volume: 1000000 },
      { date: '2024-01-02', open: 102, high: 108, low: 101, close: 105, volume: 1200000 },
      { date: '2024-01-03', open: 105, high: 112, low: 104, close: 110, volume: 1500000 },
    ];
  }
  
  async getTradeExecution(symbol: string, orderId?: string) {
    return {
      symbol: symbol,
      action: 'BUY' as const,
      quantity: 100,
      avgPrice: 100,
      fillTime: new Date('2024-01-01'),
    };
  }
  
  async getCurrentPosition(symbol: string, accountName?: string) {
    return {
      symbol: symbol,
      quantity: 100,
      avgCost: 100,
      currentPrice: 110,
      pnl: 1000,
      pnlPct: 10,
    };
  }
}

// Mock DecisionRepository
class MockDecisionRepository implements IDecisionRepository {
  private decisions: Map<string, DecisionRecord> = new Map();
  
  async findPendingEvaluations(minAge: number): Promise<DecisionRecord[]> {
    const now = new Date();
    const cutoff = new Date(now.getTime() - minAge * 24 * 60 * 60 * 1000);
    
    return Array.from(this.decisions.values()).filter(d => {
      const createdAt = new Date(d.created_at);
      return createdAt < cutoff && d.evaluation_status === 'pending';
    });
  }
  
  async findById(decisionId: string): Promise<DecisionRecord | null> {
    return this.decisions.get(decisionId) || null;
  }
  
  async saveEvaluation(decisionId: string, outcome: Outcome): Promise<void> {
    const decision = this.decisions.get(decisionId);
    if (decision) {
      decision.evaluation_status = 'evaluated';
      // 实际应该保存 outcome，这里简化
    }
  }
  
  async markAsExpired(decisionId: string): Promise<void> {
    const decision = this.decisions.get(decisionId);
    if (decision) {
      decision.evaluation_status = 'expired';
    }
  }
  
  // 测试辅助方法
  addDecision(decision: DecisionRecord) {
    this.decisions.set(decision.decision_id, decision);
  }
}

describe('DecisionEvaluationService Integration', () => {
  let service: DecisionEvaluationService;
  let marketData: MockMarketDataProvider;
  let repository: MockDecisionRepository;
  
  beforeEach(() => {
    marketData = new MockMarketDataProvider();
    repository = new MockDecisionRepository();
    service = new DecisionEvaluationService(marketData, repository);
  });
  
  describe('evaluateDecision', () => {
    it('should evaluate trade decision successfully', async () => {
      // 添加一个交易决策（10天前）
      const tenDaysAgo = new Date();
      tenDaysAgo.setDate(tenDaysAgo.getDate() - 10);
      
      repository.addDecision({
        decision_id: 'dec-001',
        decision_type: 'trade_buy',
        decision_subtype: 'trade',
        reasoning: '突破买入',
        parameters: {
          symbol: '600519',
          action: 'BUY',
          quantity: 100,
          price: 100,
        },
        created_at: tenDaysAgo.toISOString(),
        evaluation_status: 'pending',
      });
      
      const outcome = await service.evaluateDecision('dec-001');
      
      expect(outcome).toBeDefined();
      expect(outcome.success).toBe(true);  // 盈利 10%
      expect(outcome.score).toBeGreaterThan(60);
      expect(outcome.metrics.actualReturn).toBe(10);
      expect(outcome.lesson).toContain('盈利');
    });
    
    it('should evaluate observation decision', async () => {
      const fiveDaysAgo = new Date();
      fiveDaysAgo.setDate(fiveDaysAgo.getDate() - 5);
      
      repository.addDecision({
        decision_id: 'dec-002',
        decision_type: 'observation',
        decision_subtype: 'observation',
        reasoning: '等待回调',
        parameters: {
          symbol: '600519',
          reason: '等待回调',
          watchDays: 5,
        },
        created_at: fiveDaysAgo.toISOString(),
        evaluation_status: 'pending',
      });
      
      const outcome = await service.evaluateDecision('dec-002');
      
      expect(outcome).toBeDefined();
      // 价格上涨 10%，等待回调失败
      expect(outcome.success).toBe(false);
      expect(outcome.metrics.missedOpportunity).toBe(true);
      expect(outcome.lesson).toContain('错过机会');
    });
    
    it('should evaluate skip decision', async () => {
      const tenDaysAgo = new Date();
      tenDaysAgo.setDate(tenDaysAgo.getDate() - 10);
      
      repository.addDecision({
        decision_id: 'dec-003',
        decision_type: 'skip',
        decision_subtype: 'skip',
        reasoning: '估值过高',
        parameters: {
          symbol: '600519',
          reason: '估值过高',
          checkDays: 10,
        },
        created_at: tenDaysAgo.toISOString(),
        evaluation_status: 'pending',
      });
      
      const outcome = await service.evaluateDecision('dec-003');
      
      expect(outcome).toBeDefined();
      // 价格上涨 10%，跳过但错过机会（但未达 15% 重大机会阈值）
      expect(outcome.metrics.priceChangeAfterDecision).toBeGreaterThan(0);
    });
  });
  
  describe('evaluatePendingDecisions', () => {
    it('should evaluate multiple pending decisions', async () => {
      const tenDaysAgo = new Date();
      tenDaysAgo.setDate(tenDaysAgo.getDate() - 10);
      
      // 添加 3 个待评估决策
      repository.addDecision({
        decision_id: 'dec-101',
        decision_type: 'trade_buy',
        decision_subtype: 'trade',
        reasoning: '买入',
        parameters: { symbol: '600519', action: 'BUY', quantity: 100, price: 100 },
        created_at: tenDaysAgo.toISOString(),
        evaluation_status: 'pending',
      });
      
      repository.addDecision({
        decision_id: 'dec-102',
        decision_type: 'observation',
        decision_subtype: 'observation',
        reasoning: '观察',
        parameters: { symbol: '600519', reason: '等待回调', watchDays: 5 },
        created_at: tenDaysAgo.toISOString(),
        evaluation_status: 'pending',
      });
      
      repository.addDecision({
        decision_id: 'dec-103',
        decision_type: 'skip',
        decision_subtype: 'skip',
        reasoning: '跳过',
        parameters: { symbol: '600519', reason: '估值高', checkDays: 10 },
        created_at: tenDaysAgo.toISOString(),
        evaluation_status: 'pending',
      });
      
      const result = await service.evaluatePendingDecisions(5);
      
      expect(result.totalEvaluated).toBe(3);
      expect(result.results).toHaveLength(3);
      expect(result.averageScore).toBeGreaterThan(0);
    });
    
    it('should skip decisions with insufficient data window', async () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      
      repository.addDecision({
        decision_id: 'dec-201',
        decision_type: 'trade_buy',
        decision_subtype: 'trade',
        reasoning: '买入',
        parameters: { symbol: '600519', action: 'BUY', quantity: 100, price: 100 },
        created_at: yesterday.toISOString(),
        evaluation_status: 'pending',
      });
      
      // 交易决策需要 5 天数据窗口，1 天不够
      const result = await service.evaluatePendingDecisions(0);
      
      expect(result.totalEvaluated).toBe(0);  // 被跳过
    });
  });
});
