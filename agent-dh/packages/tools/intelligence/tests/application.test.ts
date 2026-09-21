/**
 * 应用层服务测试
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { DecisionTrackingApplicationService } from '../src/services/DecisionTrackingApplicationService';
import type { DecisionEvaluationService } from '../src/services/DecisionEvaluationService';
import type { IKnowledgeService, INotificationService } from '../src/services/DecisionTrackingApplicationService';
import { Outcome } from '../src/domain/decision/Outcome';

describe('DecisionTrackingApplicationService', () => {
  let appService: DecisionTrackingApplicationService;
  let mockEvaluationService: any;
  let mockKnowledgeService: any;
  let mockNotificationService: any;
  
  beforeEach(() => {
    // Mock 领域服务
    mockEvaluationService = {
      evaluatePendingDecisions: vi.fn(),
      evaluateDecision: vi.fn(),
    };
    
    // Mock 知识服务
    mockKnowledgeService = {
      saveLesson: vi.fn().mockResolvedValue(undefined),
    };
    
    // Mock 通知服务
    mockNotificationService = {
      sendEvaluationReport: vi.fn().mockResolvedValue(undefined),
    };
    
    appService = new DecisionTrackingApplicationService(
      mockEvaluationService as any,
      mockKnowledgeService,
      mockNotificationService
    );
  });
  
  describe('runDailyEvaluation', () => {
    it('should evaluate decisions, extract lessons, and send report', async () => {
      // 模拟评估结果
      const mockResult = {
        totalEvaluated: 3,
        successCount: 2,
        failureCount: 1,
        expiredCount: 0,
        averageScore: 75,
        results: [
          {
            decisionId: 'dec-001',
            outcome: new Outcome(true, 85, { actualReturn: 10 }, '买入决策优秀', 0.95),
          },
          {
            decisionId: 'dec-002',
            outcome: new Outcome(false, 30, { missedOpportunity: true, opportunityCost: 20 }, '错过重大机会', 0.85),
          },
          {
            decisionId: 'dec-003',
            outcome: new Outcome(true, 70, {}, '决策合理', 0.8),
          },
        ],
      };
      
      mockEvaluationService.evaluatePendingDecisions.mockResolvedValue(mockResult);
      
      // 执行每日评估
      await appService.runDailyEvaluation(5);
      
      // 验证调用
      expect(mockEvaluationService.evaluatePendingDecisions).toHaveBeenCalledWith(5);
      expect(mockKnowledgeService.saveLesson).toHaveBeenCalled();
      expect(mockNotificationService.sendEvaluationReport).toHaveBeenCalled();
      
      // 验证保存的教训数量（高质量 + 低质量）
      const lessonCalls = mockKnowledgeService.saveLesson.mock.calls;
      expect(lessonCalls.length).toBeGreaterThan(0);
      
      // 验证报告内容
      const reportCall = mockNotificationService.sendEvaluationReport.mock.calls[0][0];
      expect(reportCall.totalEvaluated).toBe(3);
      expect(reportCall.successCount).toBe(2);
      expect(reportCall.failureCount).toBe(1);
      expect(reportCall.averageScore).toBe(75);
    });
    
    it('should skip evaluation when no pending decisions', async () => {
      mockEvaluationService.evaluatePendingDecisions.mockResolvedValue({
        totalEvaluated: 0,
        successCount: 0,
        failureCount: 0,
        expiredCount: 0,
        averageScore: 0,
        results: [],
      });
      
      await appService.runDailyEvaluation(5);
      
      // 不应该调用知识服务和通知服务
      expect(mockKnowledgeService.saveLesson).not.toHaveBeenCalled();
      expect(mockNotificationService.sendEvaluationReport).not.toHaveBeenCalled();
    });
  });
  
  describe('evaluateSingleDecision', () => {
    it('should evaluate and save lesson for low quality decision', async () => {
      const mockOutcome = new Outcome(
        false,
        30,
        { missedOpportunity: true, opportunityCost: 20 },
        '判断失误，错过重大机会',
        0.85
      );
      
      mockEvaluationService.evaluateDecision.mockResolvedValue(mockOutcome);
      
      const outcome = await appService.evaluateSingleDecision('dec-001');
      
      expect(outcome).toBe(mockOutcome);
      expect(mockKnowledgeService.saveLesson).toHaveBeenCalled();
      
      // 验证保存的教训重要性较高（失败案例）
      const lessonCall = mockKnowledgeService.saveLesson.mock.calls[0][0];
      expect(lessonCall.importance).toBeGreaterThan(0.7);
    });
    
    it('should not save lesson for medium quality decision', async () => {
      const mockOutcome = new Outcome(
        true,
        70,
        {},
        '决策合理',
        0.8
      );
      
      mockEvaluationService.evaluateDecision.mockResolvedValue(mockOutcome);
      
      await appService.evaluateSingleDecision('dec-001');
      
      // 普通决策不保存教训
      expect(mockKnowledgeService.saveLesson).not.toHaveBeenCalled();
    });
  });
});
