/**
 * DecisionType - 决策类型值对象族
 * 
 * DDD 设计：每种决策类型是一个值对象，包含自己的评估策略
 */

export abstract class DecisionType {
  /**
   * 决策类型名称
   */
  abstract readonly typeName: string;
  
  /**
   * 是否可以评估
   */
  abstract canEvaluate(): boolean;
  
  /**
   * 获取评估策略名称（用于服务层动态创建策略）
   */
  abstract getEvaluationStrategyName(): string;
  
  /**
   * 序列化为 JSON（用于存储）
   */
  abstract toJSON(): Record<string, any>;
}

/**
 * 交易决策（买入/卖出）
 */
export class TradeDecision extends DecisionType {
  readonly typeName = 'trade';
  
  constructor(
    public readonly symbol: string,
    public readonly action: 'BUY' | 'SELL',
    public readonly quantity: number,
    public readonly price: number,
    public readonly orderId?: string
  ) {
    super();
  }
  
  canEvaluate(): boolean {
    return true;
  }
  
  getEvaluationStrategyName(): string {
    return 'TradeEvaluationStrategy';
  }
  
  toJSON() {
    return {
      typeName: this.typeName,
      symbol: this.symbol,
      action: this.action,
      quantity: this.quantity,
      price: this.price,
      orderId: this.orderId,
    };
  }
  
  static fromJSON(data: any): TradeDecision {
    return new TradeDecision(
      data.symbol,
      data.action,
      data.quantity,
      data.price,
      data.orderId
    );
  }
}

/**
 * 观察决策（等待回调、观察突破等）
 */
export class ObservationDecision extends DecisionType {
  readonly typeName = 'observation';
  
  constructor(
    public readonly symbol: string,
    public readonly reason: string,
    public readonly targetPrice?: number,
    public readonly watchDays: number = 5
  ) {
    super();
  }
  
  canEvaluate(): boolean {
    return true;
  }
  
  getEvaluationStrategyName(): string {
    return 'ObservationEvaluationStrategy';
  }
  
  toJSON() {
    return {
      typeName: this.typeName,
      symbol: this.symbol,
      reason: this.reason,
      targetPrice: this.targetPrice,
      watchDays: this.watchDays,
    };
  }
  
  static fromJSON(data: any): ObservationDecision {
    return new ObservationDecision(
      data.symbol,
      data.reason,
      data.targetPrice,
      data.watchDays ?? 5
    );
  }
}

/**
 * 跳过决策（不追、估值高等）
 */
export class SkipDecision extends DecisionType {
  readonly typeName = 'skip';
  
  constructor(
    public readonly symbol: string,
    public readonly reason: string,
    public readonly checkDays: number = 10
  ) {
    super();
  }
  
  canEvaluate(): boolean {
    return true;
  }
  
  getEvaluationStrategyName(): string {
    return 'MissedOpportunityStrategy';
  }
  
  toJSON() {
    return {
      typeName: this.typeName,
      symbol: this.symbol,
      reason: this.reason,
      checkDays: this.checkDays,
    };
  }
  
  static fromJSON(data: any): SkipDecision {
    return new SkipDecision(
      data.symbol,
      data.reason,
      data.checkDays ?? 10
    );
  }
}

/**
 * 池子管理决策（现有，保持兼容）
 */
export class PoolManagementDecision extends DecisionType {
  readonly typeName = 'pool_management';
  
  constructor(
    public readonly poolId: string,
    public readonly action: 'create' | 'update' | 'delete' | 'add_members' | 'remove_members'
  ) {
    super();
  }
  
  canEvaluate(): boolean {
    return this.action === 'create' || this.action === 'add_members';
  }
  
  getEvaluationStrategyName(): string {
    return 'PoolEvaluationStrategy';
  }
  
  toJSON() {
    return {
      typeName: this.typeName,
      poolId: this.poolId,
      action: this.action,
    };
  }
  
  static fromJSON(data: any): PoolManagementDecision {
    return new PoolManagementDecision(
      data.poolId,
      data.action
    );
  }
}

/**
 * DecisionType 工厂
 */
export class DecisionTypeFactory {
  static fromJSON(data: any): DecisionType {
    switch (data.typeName) {
      case 'trade':
        return TradeDecision.fromJSON(data);
      case 'observation':
        return ObservationDecision.fromJSON(data);
      case 'skip':
        return SkipDecision.fromJSON(data);
      case 'pool_management':
        return PoolManagementDecision.fromJSON(data);
      default:
        throw new Error(`Unknown decision type: ${data.typeName}`);
    }
  }
}
