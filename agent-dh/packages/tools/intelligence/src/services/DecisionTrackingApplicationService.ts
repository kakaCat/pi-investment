/**
 * DecisionTrackingApplicationService - 决策追踪应用服务
 * 
 * 应用层职责：
 * 1. 编排领域服务和基础设施服务
 * 2. 实现业务用例（如每日评估）
 * 3. 处理事务和错误
 */

import { DecisionEvaluationService } from './DecisionEvaluationService';
import type { EvaluationBatchResult } from './DecisionEvaluationService';
import type { Outcome } from '../domain/decision/Outcome';

/**
 * 知识服务接口（端口）
 */
export interface IKnowledgeService {
  /**
   * 保存经验教训
   */
  saveLesson(lesson: Lesson): Promise<void>;
}

export interface Lesson {
  content: string;
  importance: number;  // 0-1
  tags: string[];
  namespace: string;
}

/**
 * 通知服务接口（端口）
 */
export interface INotificationService {
  /**
   * 发送评估报告
   */
  sendEvaluationReport(report: EvaluationReport): Promise<void>;
}

export interface EvaluationReport {
  title: string;
  summary: string;
  totalEvaluated: number;
  successCount: number;
  failureCount: number;
  averageScore: number;
  highlights: string[];
  recommendations: string[];
}

/**
 * 决策追踪应用服务
 */
export class DecisionTrackingApplicationService {
  constructor(
    private readonly evaluationService: DecisionEvaluationService,
    private readonly knowledgeService: IKnowledgeService,
    private readonly notificationService: INotificationService
  ) {}
  
  /**
   * 每日评估任务（定时任务入口）
   */
  async runDailyEvaluation(minAge: number = 5): Promise<void> {
    console.log('📊 开始每日决策评估');
    
    try {
      // 1. 批量评估决策
      const result = await this.evaluationService.evaluatePendingDecisions(minAge);
      
      if (result.totalEvaluated === 0) {
        console.log('✅ 无待评估决策');
        return;
      }
      
      // 2. 提取经验教训
      const lessons = await this.extractLessonsFromResults(result);
      
      // 3. 保存到知识库
      for (const lesson of lessons) {
        await this.knowledgeService.saveLesson(lesson);
      }
      
      console.log(`📚 提取 ${lessons.length} 条经验教训`);
      
      // 4. 生成并发送报告
      const report = this.generateEvaluationReport(result, lessons);
      await this.notificationService.sendEvaluationReport(report);
      
      console.log(`✅ 每日评估完成：${result.totalEvaluated}条决策，${result.successCount}条成功，${result.failureCount}条失败`);
    } catch (error: any) {
      console.error('❌ 每日评估失败:', error);
      throw error;
    }
  }
  
  /**
   * 评估单个决策（手动触发）
   */
  async evaluateSingleDecision(decisionId: string): Promise<Outcome> {
    console.log(`📊 评估单个决策: ${decisionId}`);
    
    try {
      // 1. 执行评估
      const outcome = await this.evaluationService.evaluateDecision(decisionId);
      
      // 2. 如果是重要的失败或成功，提取教训
      if (outcome.isLowQuality() || outcome.isHighQuality()) {
        const lesson = this.extractLessonFromOutcome(decisionId, outcome);
        await this.knowledgeService.saveLesson(lesson);
      }
      
      return outcome;
    } catch (error: any) {
      console.error(`❌ 评估决策失败: ${decisionId}`, error);
      throw error;
    }
  }
  
  /**
   * 从评估结果中提取经验教训
   */
  private async extractLessonsFromResults(result: EvaluationBatchResult): Promise<Lesson[]> {
    const lessons: Lesson[] = [];
    
    for (const { decisionId, outcome } of result.results) {
      // 只从失败和优秀成功中提取教训
      if (outcome.isLowQuality() || outcome.isHighQuality()) {
        const lesson = this.extractLessonFromOutcome(decisionId, outcome);
        lessons.push(lesson);
      }
    }
    
    return lessons;
  }
  
  /**
   * 从单个评估结果提取教训
   */
  private extractLessonFromOutcome(decisionId: string, outcome: Outcome): Lesson {
    // 重要性：失败 > 优秀成功 > 普通成功
    let importance = 0.5;
    
    if (outcome.isLowQuality()) {
      importance = 0.8;  // 失败更重要
    } else if (outcome.isHighQuality()) {
      importance = 0.6;  // 优秀成功也重要
    }
    
    // 重大错过机会：最高重要性
    if (outcome.isMajorMissedOpportunity()) {
      importance = 0.9;
    }
    
    // 提取标签
    const tags: string[] = ['decision-evaluation'];
    
    if (outcome.metrics.missedOpportunity) {
      tags.push('missed-opportunity');
    }
    
    if (outcome.success) {
      tags.push('success');
    } else {
      tags.push('failure');
    }
    
    return {
      content: `[${decisionId}] ${outcome.lesson}`,
      importance: importance,
      tags: tags,
      namespace: 'experience',
    };
  }
  
  /**
   * 生成评估报告
   */
  private generateEvaluationReport(
    result: EvaluationBatchResult,
    lessons: Lesson[]
  ): EvaluationReport {
    // 统计
    const totalEvaluated = result.totalEvaluated;
    const successCount = result.successCount;
    const failureCount = result.failureCount;
    const averageScore = result.averageScore;
    const successRate = totalEvaluated > 0 
      ? Math.round((successCount / totalEvaluated) * 100) 
      : 0;
    
    // 找出重大错过机会
    const majorMissed = result.results
      .filter(r => r.outcome.isMajorMissedOpportunity())
      .map(r => `${r.decisionId}: ${r.outcome.lesson}`);
    
    // 找出优秀决策
    const highQuality = result.results
      .filter(r => r.outcome.isHighQuality())
      .map(r => `${r.decisionId}: ${r.outcome.lesson}`);
    
    // 生成亮点
    const highlights: string[] = [];
    
    if (highQuality.length > 0) {
      highlights.push(`✅ ${highQuality.length} 条优秀决策（>80分）`);
    }
    
    if (majorMissed.length > 0) {
      highlights.push(`⚠️ ${majorMissed.length} 条重大错过机会（>15%）`);
    }
    
    highlights.push(`📚 提取 ${lessons.length} 条经验教训`);
    
    // 生成建议
    const recommendations: string[] = [];
    
    if (successRate < 50) {
      recommendations.push('决策胜率偏低，建议审视决策标准');
    }
    
    if (majorMissed.length > 3) {
      recommendations.push('频繁错过机会，建议降低跳过决策的门槛');
    }
    
    if (averageScore < 60) {
      recommendations.push('决策质量偏低，建议加强决策前的分析');
    }
    
    if (recommendations.length === 0) {
      recommendations.push('决策质量良好，继续保持');
    }
    
    // 生成摘要
    const summary = [
      `评估了 ${totalEvaluated} 条决策`,
      `成功 ${successCount} 条 (${successRate}%)`,
      `失败 ${failureCount} 条`,
      `平均分 ${averageScore.toFixed(1)}`,
    ].join('，');
    
    return {
      title: '📊 每日决策评估报告',
      summary: summary,
      totalEvaluated: totalEvaluated,
      successCount: successCount,
      failureCount: failureCount,
      averageScore: averageScore,
      highlights: highlights,
      recommendations: recommendations,
    };
  }
}
