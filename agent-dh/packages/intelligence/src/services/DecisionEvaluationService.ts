/**
 * DecisionEvaluationService - 决策评估领域服务
 * 
 * 职责：
 * 1. 批量评估待评估的决策
 * 2. 评估单个决策
 * 3. 协调领域模型和评估策略
 */

import type { MarketDataProvider, DecisionContext } from '../domain/evaluation/EvaluationStrategy';
import { StrategyFactory } from '../domain/evaluation/StrategyFactory';
import type { Outcome } from '../domain/decision/Outcome';
import { DecisionTypeFactory } from '../domain/decision/DecisionType';

/**
 * 决策记录（从仓库获取）
 */
export interface DecisionRecord {
  decision_id: string;
  decision_type: string;           // 旧格式：trade_buy, pool_create 等
  decision_subtype?: string;        // 新格式：trade, observation, skip
  reasoning: string;
  context?: Record<string, any>;
  parameters?: Record<string, any>;
  created_at: string;
  evaluation_status?: string;       // pending, evaluated, expired
}

/**
 * 决策仓库接口（端口）
 */
export interface IDecisionRepository {
  /**
   * 查询待评估的决策（创建时间 > minAge 天）
   */
  findPendingEvaluations(minAge: number): Promise<DecisionRecord[]>;
  
  /**
   * 根据 ID 查询决策
   */
  findById(decisionId: string): Promise<DecisionRecord | null>;
  
  /**
   * 保存评估结果
   */
  saveEvaluation(decisionId: string, outcome: Outcome): Promise<void>;
  
  /**
   * 标记决策为已过期
   */
  markAsExpired(decisionId: string): Promise<void>;
}

/**
 * 评估批次结果
 */
export interface EvaluationBatchResult {
  totalEvaluated: number;
  successCount: number;
  failureCount: number;
  expiredCount: number;
  averageScore: number;
  results: Array<{
    decisionId: string;
    outcome: Outcome;
  }>;
}

/**
 * 决策评估服务
 */
export class DecisionEvaluationService {
  constructor(
    private readonly marketDataProvider: MarketDataProvider,
    private readonly decisionRepository: IDecisionRepository
  ) {}
  
  /**
   * 批量评估待评估的决策
   */
  async evaluatePendingDecisions(minAge: number = 5): Promise<EvaluationBatchResult> {
    console.log(`📊 开始批量评估决策（创建 >${minAge} 天）`);
    
    // 1. 获取待评估决策
    const pendingDecisions = await this.decisionRepository.findPendingEvaluations(minAge);
    
    if (pendingDecisions.length === 0) {
      console.log('✅ 无待评估决策');
      return {
        totalEvaluated: 0,
        successCount: 0,
        failureCount: 0,
        expiredCount: 0,
        averageScore: 0,
        results: [],
      };
    }
    
    console.log(`📋 找到 ${pendingDecisions.length} 条待评估决策`);
    
    const results: Array<{ decisionId: string; outcome: Outcome }> = [];
    let expiredCount = 0;
    
    // 2. 逐个评估
    for (const record of pendingDecisions) {
      try {
        // 转换为领域模型
        const context = this.convertToDecisionContext(record);
        
        // 检查是否可评估
        if (!context.decisionType.canEvaluate()) {
          await this.decisionRepository.markAsExpired(record.decision_id);
          expiredCount++;
          continue;
        }
        
        // 获取评估策略
        const strategyName = context.decisionType.getEvaluationStrategyName();
        const strategy = StrategyFactory.getStrategy(strategyName);
        
        // 检查数据窗口是否足够
        if (!strategy.canEvaluateNow(context.timestamp)) {
          console.log(`⏳ 决策 ${record.decision_id} 数据窗口不足，跳过`);
          continue;
        }
        
        // 执行评估
        const outcome = await strategy.evaluate(context, this.marketDataProvider);
        
        // 保存结果
        await this.decisionRepository.saveEvaluation(record.decision_id, outcome);
        
        results.push({
          decisionId: record.decision_id,
          outcome: outcome,
        });
        
        console.log(
          `${outcome.success ? '✅' : '❌'} 决策 ${record.decision_id}: ${outcome.score}分 - ${outcome.lesson}`
        );
      } catch (error: any) {
        console.error(`❌ 评估决策失败: ${record.decision_id}`, error.message);
      }
    }
    
    // 3. 计算统计
    const successCount = results.filter(r => r.outcome.success).length;
    const failureCount = results.filter(r => !r.outcome.success).length;
    const averageScore = results.length > 0
      ? results.reduce((sum, r) => sum + r.outcome.score, 0) / results.length
      : 0;
    
    console.log(`✅ 批量评估完成: ${results.length}条评估，${successCount}条成功，${failureCount}条失败`);
    
    return {
      totalEvaluated: results.length,
      successCount: successCount,
      failureCount: failureCount,
      expiredCount: expiredCount,
      averageScore: averageScore,
      results: results,
    };
  }
  
  /**
   * 评估单个决策
   */
  async evaluateDecision(decisionId: string): Promise<Outcome> {
    console.log(`📊 评估决策: ${decisionId}`);
    
    // 1. 获取决策记录
    const record = await this.decisionRepository.findById(decisionId);
    
    if (!record) {
      throw new Error(`决策不存在: ${decisionId}`);
    }
    
    // 2. 转换为领域模型
    const context = this.convertToDecisionContext(record);
    
    // 3. 检查是否可评估
    if (!context.decisionType.canEvaluate()) {
      throw new Error(`决策类型不支持评估: ${record.decision_type}`);
    }
    
    // 4. 获取评估策略
    const strategyName = context.decisionType.getEvaluationStrategyName();
    const strategy = StrategyFactory.getStrategy(strategyName);
    
    // 5. 执行评估
    const outcome = await strategy.evaluate(context, this.marketDataProvider);
    
    // 6. 保存结果
    await this.decisionRepository.saveEvaluation(decisionId, outcome);
    
    console.log(`${outcome.success ? '✅' : '❌'} 评估完成: ${outcome.score}分 - ${outcome.lesson}`);
    
    return outcome;
  }
  
  /**
   * 将决策记录转换为决策上下文（领域模型）
   */
  private convertToDecisionContext(record: DecisionRecord): DecisionContext {
    // 1. 解析决策类型
    let decisionType;
    
    if (record.decision_subtype) {
      // 新格式：使用 decision_subtype + parameters
      decisionType = DecisionTypeFactory.fromJSON({
        typeName: record.decision_subtype,
        ...record.parameters,
      });
    } else {
      // 旧格式：从 decision_type 推断
      decisionType = this.inferDecisionTypeFromLegacy(record);
    }
    
    // 2. 构造决策上下文
    return {
      decisionId: record.decision_id,
      decisionType: decisionType,
      timestamp: new Date(record.created_at),
      reasoning: record.reasoning,
      marketContext: record.context,
    };
  }
  
  /**
   * 从旧格式推断决策类型（向后兼容）
   */
  private inferDecisionTypeFromLegacy(record: DecisionRecord): any {
    const { DecisionTypeFactory } = require('../domain/decision/DecisionType');
    const params = record.parameters || {};
    
    // 根据旧的 decision_type 推断新的决策类型
    if (record.decision_type === 'trade_buy' || record.decision_type === 'trade_sell') {
      return DecisionTypeFactory.fromJSON({
        typeName: 'trade',
        symbol: params.symbol,
        action: record.decision_type === 'trade_buy' ? 'BUY' : 'SELL',
        quantity: params.quantity || 0,
        price: params.price || 0,
        orderId: params.order_id,
      });
    }
    
    if (record.decision_type === 'pool_create' || record.decision_type === 'pool_update') {
      return DecisionTypeFactory.fromJSON({
        typeName: 'pool_management',
        poolId: params.pool_id || params.related_entity_id,
        action: record.decision_type === 'pool_create' ? 'create' : 'update',
      });
    }
    
    // 默认：pool_management
    return DecisionTypeFactory.fromJSON({
      typeName: 'pool_management',
      poolId: params.pool_id || 'unknown',
      action: 'update',
    });
  }
}
