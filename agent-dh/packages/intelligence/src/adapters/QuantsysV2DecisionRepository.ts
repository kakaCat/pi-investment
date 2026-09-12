/**
 * QuantsysV2DecisionRepository - IDecisionRepository 实现
 * 
 * 适配器模式：将 QuantsysV2Client 适配为领域层的 IDecisionRepository 接口
 */

import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import type {
  IDecisionRepository,
  DecisionRecord,
} from '../services/DecisionEvaluationService';
import type { Outcome } from '../domain/decision/Outcome';

export class QuantsysV2DecisionRepository implements IDecisionRepository {
  constructor(private readonly qv2Client: QuantsysV2Client) {}
  
  /**
   * 查询待评估的决策（创建时间 > minAge 天）
   */
  async findPendingEvaluations(minAge: number): Promise<DecisionRecord[]> {
    try {
      const response = await this.qv2Client.getPendingEvaluations(minAge);
      
      const decisions = response?.decisions ?? response?.data ?? [];
      
      return decisions.map((d: any) => this.mapToDecisionRecord(d));
    } catch (error: any) {
      console.error('查询待评估决策失败:', error);
      return [];
    }
  }
  
  /**
   * 根据 ID 查询决策
   */
  async findById(decisionId: string): Promise<DecisionRecord | null> {
    try {
      const response = await this.qv2Client.getDecision(decisionId);
      
      if (!response || !response.decision_id) {
        return null;
      }
      
      return this.mapToDecisionRecord(response);
    } catch (error: any) {
      console.error(`查询决策失败: ${decisionId}`, error);
      return null;
    }
  }
  
  /**
   * 保存评估结果
   */
  async saveEvaluation(decisionId: string, outcome: Outcome): Promise<void> {
    try {
      await this.qv2Client.updateEvaluation(decisionId, {
        success: outcome.success,
        score: outcome.score,
        metrics: outcome.metrics,
        lesson: outcome.lesson,
        confidence: outcome.confidence,
        evaluation_status: 'evaluated',
      });
    } catch (error: any) {
      console.error(`保存评估结果失败: ${decisionId}`, error);
      throw error;
    }
  }
  
  /**
   * 标记决策为已过期
   */
  async markAsExpired(decisionId: string): Promise<void> {
    try {
      await this.qv2Client.updateEvaluation(decisionId, {
        evaluation_status: 'expired',
      });
    } catch (error: any) {
      console.error(`标记决策过期失败: ${decisionId}`, error);
      throw error;
    }
  }
  
  /**
   * 映射后端数据到领域模型
   */
  private mapToDecisionRecord(data: any): DecisionRecord {
    return {
      decision_id: data.decision_id ?? data.decisionId ?? data.id,
      decision_type: data.decision_type ?? data.decisionType,
      decision_subtype: data.decision_subtype ?? data.decisionSubtype,
      reasoning: data.reasoning ?? '',
      context: data.context ?? {},
      parameters: data.parameters ?? {},
      created_at: data.created_at ?? data.createdAt ?? new Date().toISOString(),
      evaluation_status: data.evaluation_status ?? data.evaluationStatus ?? 'pending',
    };
  }
}
