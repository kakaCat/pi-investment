/**
 * Outcome - 评估结果值对象
 * 
 * DDD 设计：不可变值对象，封装评估结果的所有信息
 */

export interface OutcomeMetrics {
  // 通用指标
  actualReturn?: number;        // 实际收益率 %
  expectedReturn?: number;      // 预期收益率 %
  deviationFromExpected?: number;
  
  // 交易决策指标
  holdingDays?: number;
  sharpeRatio?: number;
  maxDrawdown?: number;
  
  // 观察/跳过决策指标
  priceChangeAfterDecision?: number;  // 决策后价格变化 %
  missedOpportunity?: boolean;        // 是否错过机会
  opportunityCost?: number;           // 机会成本 %
}

export class Outcome {
  constructor(
    public readonly success: boolean,
    public readonly score: number,          // 0-100，综合评分
    public readonly metrics: OutcomeMetrics,
    public readonly lesson: string,
    public readonly confidence: number      // 0-1，评估置信度
  ) {
    // 值对象校验
    if (score < 0 || score > 100) {
      throw new Error(`Score must be between 0-100, got ${score}`);
    }
    if (confidence < 0 || confidence > 1) {
      throw new Error(`Confidence must be between 0-1, got ${confidence}`);
    }
  }
  
  /**
   * 是否为高质量决策（成功且高分）
   */
  isHighQuality(): boolean {
    return this.success && this.score >= 80;
  }
  
  /**
   * 是否为低质量决策（失败或低分）
   */
  isLowQuality(): boolean {
    return !this.success || this.score < 50;
  }
  
  /**
   * 是否错过重大机会（机会成本 > 15%）
   */
  isMajorMissedOpportunity(): boolean {
    return this.metrics.missedOpportunity === true && 
           (this.metrics.opportunityCost ?? 0) > 15;
  }
  
  /**
   * 序列化
   */
  toJSON() {
    return {
      success: this.success,
      score: this.score,
      metrics: this.metrics,
      lesson: this.lesson,
      confidence: this.confidence,
    };
  }
  
  static fromJSON(data: any): Outcome {
    return new Outcome(
      data.success,
      data.score,
      data.metrics,
      data.lesson,
      data.confidence
    );
  }
}
