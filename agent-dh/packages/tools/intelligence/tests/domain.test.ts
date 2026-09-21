/**
 * 领域模型单元测试
 */

import { describe, it, expect } from 'vitest';
import {
  TradeDecision,
  ObservationDecision,
  SkipDecision,
  DecisionTypeFactory,
} from '../src/domain/decision/DecisionType';
import { Outcome } from '../src/domain/decision/Outcome';

describe('DecisionType', () => {
  describe('TradeDecision', () => {
    it('should create trade decision correctly', () => {
      const decision = new TradeDecision('600519', 'BUY', 100, 1850.0);
      
      expect(decision.typeName).toBe('trade');
      expect(decision.symbol).toBe('600519');
      expect(decision.action).toBe('BUY');
      expect(decision.canEvaluate()).toBe(true);
      expect(decision.getEvaluationStrategyName()).toBe('TradeEvaluationStrategy');
    });
    
    it('should serialize and deserialize correctly', () => {
      const original = new TradeDecision('600519', 'SELL', 200, 1900.0, 'order-123');
      const json = original.toJSON();
      const restored = TradeDecision.fromJSON(json);
      
      expect(restored.symbol).toBe(original.symbol);
      expect(restored.action).toBe(original.action);
      expect(restored.quantity).toBe(original.quantity);
      expect(restored.price).toBe(original.price);
      expect(restored.orderId).toBe(original.orderId);
    });
  });
  
  describe('ObservationDecision', () => {
    it('should create observation decision correctly', () => {
      const decision = new ObservationDecision('600519', '等待回调', 1800.0, 5);
      
      expect(decision.typeName).toBe('observation');
      expect(decision.symbol).toBe('600519');
      expect(decision.reason).toBe('等待回调');
      expect(decision.targetPrice).toBe(1800.0);
      expect(decision.watchDays).toBe(5);
      expect(decision.canEvaluate()).toBe(true);
      expect(decision.getEvaluationStrategyName()).toBe('ObservationEvaluationStrategy');
    });
    
    it('should use default watch days', () => {
      const decision = new ObservationDecision('600519', '观察突破');
      expect(decision.watchDays).toBe(5);
    });
  });
  
  describe('SkipDecision', () => {
    it('should create skip decision correctly', () => {
      const decision = new SkipDecision('600519', '估值过高', 10);
      
      expect(decision.typeName).toBe('skip');
      expect(decision.symbol).toBe('600519');
      expect(decision.reason).toBe('估值过高');
      expect(decision.checkDays).toBe(10);
      expect(decision.canEvaluate()).toBe(true);
      expect(decision.getEvaluationStrategyName()).toBe('MissedOpportunityStrategy');
    });
  });
  
  describe('DecisionTypeFactory', () => {
    it('should deserialize trade decision', () => {
      const json = {
        typeName: 'trade',
        symbol: '600519',
        action: 'BUY',
        quantity: 100,
        price: 1850.0,
      };
      
      const decision = DecisionTypeFactory.fromJSON(json);
      expect(decision).toBeInstanceOf(TradeDecision);
      expect((decision as TradeDecision).symbol).toBe('600519');
    });
    
    it('should deserialize observation decision', () => {
      const json = {
        typeName: 'observation',
        symbol: '600519',
        reason: '等待回调',
        watchDays: 5,
      };
      
      const decision = DecisionTypeFactory.fromJSON(json);
      expect(decision).toBeInstanceOf(ObservationDecision);
    });
    
    it('should throw error for unknown type', () => {
      const json = { typeName: 'unknown' };
      
      expect(() => DecisionTypeFactory.fromJSON(json)).toThrow('Unknown decision type');
    });
  });
});

describe('Outcome', () => {
  it('should create outcome correctly', () => {
    const outcome = new Outcome(
      true,
      85,
      { actualReturn: 10.5, holdingDays: 7 },
      '买入决策正确，持仓7天盈利10.5%',
      0.95
    );
    
    expect(outcome.success).toBe(true);
    expect(outcome.score).toBe(85);
    expect(outcome.metrics.actualReturn).toBe(10.5);
    expect(outcome.lesson).toContain('盈利10.5%');
    expect(outcome.confidence).toBe(0.95);
  });
  
  it('should validate score range', () => {
    expect(() => new Outcome(true, 150, {}, 'test', 0.8)).toThrow('Score must be between 0-100');
    expect(() => new Outcome(true, -10, {}, 'test', 0.8)).toThrow('Score must be between 0-100');
  });
  
  it('should validate confidence range', () => {
    expect(() => new Outcome(true, 80, {}, 'test', 1.5)).toThrow('Confidence must be between 0-1');
    expect(() => new Outcome(true, 80, {}, 'test', -0.1)).toThrow('Confidence must be between 0-1');
  });
  
  it('should identify high quality decision', () => {
    const outcome = new Outcome(true, 85, {}, 'test', 0.9);
    expect(outcome.isHighQuality()).toBe(true);
    
    const lowScore = new Outcome(true, 70, {}, 'test', 0.9);
    expect(lowScore.isHighQuality()).toBe(false);
  });
  
  it('should identify low quality decision', () => {
    const outcome = new Outcome(false, 40, {}, 'test', 0.8);
    expect(outcome.isLowQuality()).toBe(true);
    
    const highScore = new Outcome(true, 80, {}, 'test', 0.8);
    expect(highScore.isLowQuality()).toBe(false);
  });
  
  it('should identify major missed opportunity', () => {
    const outcome = new Outcome(
      false,
      30,
      { missedOpportunity: true, opportunityCost: 20 },
      'test',
      0.85
    );
    expect(outcome.isMajorMissedOpportunity()).toBe(true);
    
    const minor = new Outcome(
      false,
      60,
      { missedOpportunity: true, opportunityCost: 10 },
      'test',
      0.85
    );
    expect(minor.isMajorMissedOpportunity()).toBe(false);
  });
  
  it('should serialize and deserialize correctly', () => {
    const original = new Outcome(
      true,
      85,
      { actualReturn: 10.5 },
      'test lesson',
      0.95
    );
    
    const json = original.toJSON();
    const restored = Outcome.fromJSON(json);
    
    expect(restored.success).toBe(original.success);
    expect(restored.score).toBe(original.score);
    expect(restored.lesson).toBe(original.lesson);
    expect(restored.confidence).toBe(original.confidence);
  });
});
