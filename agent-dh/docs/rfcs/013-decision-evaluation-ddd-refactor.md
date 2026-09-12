# P1-3: 判断结果自动对账系统 DDD 重构设计

## 当前系统分析

### 已有实现
- ✅ **工具层**: DecisionAuditTool (record + evaluate)
- ✅ **后端服务**: DecisionEvaluator (批量评估 + 单个评估)
- ✅ **数据库**: agent_decisions 表
- ✅ **API**: POST /api/decisions/record, POST /api/decisions/evaluate

### 当前问题
1. **只评估执行过的决策**（create_pool/add_stock），不评估"观察/不交易"
2. **评估逻辑简化**：只看池子是否删除、持有天数，没有真实收益计算
3. **缺少 missed_opportunity 检测**：说"不追"但后来涨了，没有自动对账
4. **领域模型不清晰**：决策类型混杂，评估逻辑耦合在服务层

---

## DDD 领域模型设计

### 1. 核心领域概念

#### 1.1 Decision（决策）聚合根

```typescript
// 决策实体
interface Decision {
  // 标识
  decisionId: DecisionId;        // 值对象
  agentId: AgentId;
  timestamp: DateTime;
  
  // 决策内容（多态）
  type: DecisionType;            // 值对象：TradeDecision | ObservationDecision | SkipDecision
  reasoning: Reasoning;          // 值对象：规则 + 数据依据
  context: DecisionContext;      // 值对象：市场环境、regime
  
  // 评估状态
  evaluationStatus: EvaluationStatus;  // Pending | Evaluated | Expired
  outcome?: Outcome;             // 值对象：评估结果
  
  // 领域行为
  evaluate(evaluator: DecisionEvaluator): void;
  markAsExpired(): void;
  extractLesson(): Lesson;
}
```

#### 1.2 DecisionType（决策类型）值对象族

```typescript
// 基类
abstract class DecisionType {
  abstract canEvaluate(): boolean;
  abstract getEvaluationStrategy(): EvaluationStrategy;
}

// 交易决策（可直接对账）
class TradeDecision extends DecisionType {
  symbol: string;
  action: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  
  canEvaluate(): boolean { return true; }
  getEvaluationStrategy(): EvaluationStrategy { 
    return new TradeEvaluationStrategy(); 
  }
}

// 观察决策（T+N 天后对账）
class ObservationDecision extends DecisionType {
  symbol: string;
  reason: string;          // "等待回调"、"观察突破"
  targetPrice?: number;    // 期望价格
  watchDays: number;       // 观察期（默认 5 天）
  
  canEvaluate(): boolean { return true; }
  getEvaluationStrategy(): EvaluationStrategy { 
    return new ObservationEvaluationStrategy(); 
  }
}

// 跳过决策（T+N 天后检查是否错过机会）
class SkipDecision extends DecisionType {
  symbol: string;
  reason: string;          // "估值过高"、"技术面走坏"
  checkDays: number;       // 检查期（默认 10 天）
  
  canEvaluate(): boolean { return true; }
  getEvaluationStrategy(): EvaluationStrategy { 
    return new MissedOpportunityStrategy(); 
  }
}

// 池子管理决策（已有，保持兼容）
class PoolManagementDecision extends DecisionType {
  poolId: string;
  action: 'create' | 'update' | 'delete';
  
  canEvaluate(): boolean { return true; }
  getEvaluationStrategy(): EvaluationStrategy { 
    return new PoolEvaluationStrategy(); 
  }
}
```

#### 1.3 Outcome（评估结果）值对象

```typescript
interface Outcome {
  success: boolean;
  score: number;          // 0-100，综合评分
  metrics: OutcomeMetrics;
  lesson: string;
  confidence: number;     // 0-1，评估置信度
}

interface OutcomeMetrics {
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
  opportunityCost?: number;           // 机会成本
}
```

### 2. 评估策略（Strategy Pattern）

```typescript
// 评估策略接口
interface EvaluationStrategy {
  evaluate(decision: Decision, marketData: MarketDataProvider): Outcome;
  getRequiredDataWindow(): number;  // 需要多少天数据
}

// 交易决策评估策略
class TradeEvaluationStrategy implements EvaluationStrategy {
  evaluate(decision: Decision, marketData: MarketDataProvider): Outcome {
    const trade = decision.type as TradeDecision;
    
    // 1. 获取实际成交记录
    const execution = this.getTradeExecution(trade);
    
    // 2. 计算持仓收益（如果已卖出）或浮动盈亏
    const returns = this.calculateReturns(execution, marketData);
    
    // 3. 计算风险指标
    const riskMetrics = this.calculateRiskMetrics(execution, marketData);
    
    // 4. 综合评分
    const score = this.calculateScore(returns, riskMetrics);
    
    return {
      success: returns.pnlPct > 0,
      score: score,
      metrics: {
        actualReturn: returns.pnlPct,
        holdingDays: returns.holdingDays,
        sharpeRatio: riskMetrics.sharpe,
        maxDrawdown: riskMetrics.maxDrawdown,
      },
      lesson: this.generateLesson(decision, returns),
      confidence: 0.95, // 交易数据可靠
    };
  }
  
  getRequiredDataWindow(): number { return 30; }
}

// 观察决策评估策略
class ObservationEvaluationStrategy implements EvaluationStrategy {
  evaluate(decision: Decision, marketData: MarketDataProvider): Outcome {
    const observation = decision.type as ObservationDecision;
    
    // 1. 获取观察期内的价格走势
    const priceData = marketData.getPriceHistory(
      observation.symbol,
      decision.timestamp,
      observation.watchDays
    );
    
    // 2. 判断观察结果
    const priceChange = this.calculatePriceChange(priceData);
    const didTrigger = this.checkTriggerCondition(observation, priceData);
    
    // 3. 评估决策质量
    let success = false;
    let lesson = '';
    
    if (observation.reason.includes('等待回调') && priceChange < -3) {
      success = true;
      lesson = `等待策略有效，${observation.watchDays}天内回调${Math.abs(priceChange).toFixed(1)}%`;
    } else if (observation.reason.includes('观察突破') && didTrigger) {
      success = true;
      lesson = `突破观察有效，触发条件已满足`;
    } else if (priceChange > 10) {
      success = false;
      lesson = `观察期错过机会，${observation.watchDays}天内上涨${priceChange.toFixed(1)}%`;
    } else {
      success = true;
      lesson = `观察决策合理，${observation.watchDays}天内波动${priceChange.toFixed(1)}%`;
    }
    
    return {
      success: success,
      score: this.calculateScore(priceChange, didTrigger, observation.reason),
      metrics: {
        priceChangeAfterDecision: priceChange,
        missedOpportunity: !success && priceChange > 10,
        opportunityCost: !success ? priceChange : 0,
      },
      lesson: lesson,
      confidence: 0.8, // 观察决策评估有一定主观性
    };
  }
  
  getRequiredDataWindow(): number { return 10; }
}

// 错过机会检测策略
class MissedOpportunityStrategy implements EvaluationStrategy {
  evaluate(decision: Decision, marketData: MarketDataProvider): Outcome {
    const skip = decision.type as SkipDecision;
    
    // 1. 获取决策后的价格表现
    const priceData = marketData.getPriceHistory(
      skip.symbol,
      decision.timestamp,
      skip.checkDays
    );
    
    const priceChange = this.calculatePriceChange(priceData);
    const maxGain = this.calculateMaxGain(priceData);
    
    // 2. 判断是否错过机会
    const missedOpportunity = priceChange > 15 || maxGain > 20;
    
    // 3. 分析跳过理由是否成立
    const reasonValid = this.validateSkipReason(skip.reason, priceData, marketData);
    
    let success = !missedOpportunity && reasonValid;
    let lesson = '';
    
    if (missedOpportunity) {
      success = false;
      lesson = `"${skip.reason}"判断失误，${skip.checkDays}天内上涨${priceChange.toFixed(1)}%（最高${maxGain.toFixed(1)}%），错过机会`;
    } else if (!reasonValid) {
      success = false;
      lesson = `"${skip.reason}"理由不充分，但幸运未错过（${skip.checkDays}天涨幅${priceChange.toFixed(1)}%）`;
    } else {
      success = true;
      lesson = `"${skip.reason}"判断正确，${skip.checkDays}天内涨幅仅${priceChange.toFixed(1)}%，跳过决策合理`;
    }
    
    return {
      success: success,
      score: missedOpportunity ? Math.max(0, 100 - priceChange) : 80,
      metrics: {
        priceChangeAfterDecision: priceChange,
        missedOpportunity: missedOpportunity,
        opportunityCost: missedOpportunity ? priceChange : 0,
      },
      lesson: lesson,
      confidence: 0.85,
    };
  }
  
  getRequiredDataWindow(): number { return 20; }
}
```

---

## 3. 领域服务

### 3.1 DecisionEvaluationService（领域服务）

```typescript
class DecisionEvaluationService {
  constructor(
    private readonly marketDataProvider: MarketDataProvider,
    private readonly decisionRepository: IDecisionRepository
  ) {}
  
  /**
   * 批量评估待评估的决策
   */
  async evaluatePendingDecisions(minAge: number = 5): Promise<EvaluationBatchResult> {
    // 1. 获取待评估决策（创建时间 > minAge 天）
    const pendingDecisions = await this.decisionRepository.findPendingEvaluations(minAge);
    
    const results: EvaluationResult[] = [];
    
    for (const decision of pendingDecisions) {
      try {
        // 2. 判断是否可评估
        if (!decision.type.canEvaluate()) {
          decision.markAsExpired();
          continue;
        }
        
        // 3. 获取评估策略
        const strategy = decision.type.getEvaluationStrategy();
        
        // 4. 检查数据窗口
        const requiredDays = strategy.getRequiredDataWindow();
        const daysSinceDecision = DateTime.now().diff(decision.timestamp, 'days').days;
        
        if (daysSinceDecision < requiredDays) {
          continue; // 数据窗口不足，等待
        }
        
        // 5. 执行评估
        const outcome = strategy.evaluate(decision, this.marketDataProvider);
        
        // 6. 更新决策
        decision.evaluate(outcome);
        await this.decisionRepository.save(decision);
        
        results.push({
          decisionId: decision.decisionId,
          outcome: outcome,
        });
        
      } catch (error) {
        logger.error(`评估决策失败: ${decision.decisionId}`, error);
      }
    }
    
    return {
      totalEvaluated: results.length,
      successCount: results.filter(r => r.outcome.success).length,
      failureCount: results.filter(r => !r.outcome.success).length,
      averageScore: this.calculateAverageScore(results),
      results: results,
    };
  }
  
  /**
   * 评估单个决策
   */
  async evaluateDecision(decisionId: DecisionId): Promise<Outcome> {
    const decision = await this.decisionRepository.findById(decisionId);
    
    if (!decision) {
      throw new DecisionNotFoundError(decisionId);
    }
    
    if (!decision.type.canEvaluate()) {
      throw new DecisionNotEvaluableError(decisionId);
    }
    
    const strategy = decision.type.getEvaluationStrategy();
    const outcome = strategy.evaluate(decision, this.marketDataProvider);
    
    decision.evaluate(outcome);
    await this.decisionRepository.save(decision);
    
    return outcome;
  }
}
```

---

## 4. 应用层服务

### 4.1 DecisionTrackingApplicationService

```typescript
class DecisionTrackingApplicationService {
  constructor(
    private readonly evaluationService: DecisionEvaluationService,
    private readonly knowledgeService: KnowledgeService,
    private readonly notificationService: NotificationService
  ) {}
  
  /**
   * 应用层编排：评估 + 提取知识 + 通知
   */
  async runDailyEvaluation(): Promise<void> {
    logger.info('开始每日决策评估');
    
    // 1. 批量评估
    const result = await this.evaluationService.evaluatePendingDecisions(5);
    
    // 2. 提取知识
    const lessons = await this.extractLessonsFromResults(result.results);
    
    // 3. 保存到知识库
    for (const lesson of lessons) {
      await this.knowledgeService.saveLesson(lesson);
    }
    
    // 4. 生成报告并通知
    const report = this.generateEvaluationReport(result, lessons);
    await this.notificationService.sendReport(report);
    
    logger.info(`每日评估完成：${result.totalEvaluated}条决策`);
  }
  
  /**
   * 从评估结果中提取经验教训
   */
  private async extractLessonsFromResults(results: EvaluationResult[]): Promise<Lesson[]> {
    const lessons: Lesson[] = [];
    
    for (const result of results) {
      // 只从失败和重要成功中提取教训
      if (!result.outcome.success || result.outcome.score > 90) {
        const lesson = {
          content: result.outcome.lesson,
          importance: !result.outcome.success ? 0.8 : 0.6,
          tags: this.extractTags(result),
          namespace: 'experience',
        };
        
        lessons.push(lesson);
      }
    }
    
    return lessons;
  }
}
```

---

## 5. 实施计划

### Phase 1: 领域模型重构（2h）
1. ✅ 定义 DecisionType 值对象族（TradeDecision/ObservationDecision/SkipDecision）
2. ✅ 实现 EvaluationStrategy 接口和三个具体策略
3. ✅ 定义 Outcome 值对象
4. ✅ 单元测试

### Phase 2: 领域服务实现（1.5h）
1. ✅ 实现 DecisionEvaluationService
2. ✅ 实现 MarketDataProvider 适配器
3. ✅ 集成测试

### Phase 3: 应用层编排（1h）
1. ✅ 实现 DecisionTrackingApplicationService
2. ✅ 接入 KnowledgeService
3. ✅ 实现通知功能

### Phase 4: 前端工具更新（0.5h）
1. ✅ DecisionAuditTool 支持新的决策类型
2. ✅ 更新工具 prompt 和示例
3. ✅ E2E 测试

---

## 6. 数据库设计（兼容扩展）

### 现有表保持不变
```sql
-- agent_decisions 表（已有）
-- 添加新字段兼容新决策类型
ALTER TABLE agent_decisions 
ADD COLUMN decision_subtype VARCHAR(50),  -- 'trade' | 'observation' | 'skip'
ADD COLUMN evaluation_metrics JSONB,      -- OutcomeMetrics
ADD COLUMN evaluation_confidence FLOAT;   -- 0-1
```

---

## 7. 关键收益

### DDD 原则体现
1. **领域模型清晰**：DecisionType 多态体现真实业务
2. **策略模式**：评估逻辑按决策类型分离，易扩展
3. **值对象不变性**：Outcome/Reasoning 值语义明确
4. **领域服务聚焦**：评估逻辑在领域层，应用层只编排

### 业务价值
1. **覆盖观察/跳过决策**：不再遗漏"不交易"的判断
2. **自动 missed_opportunity 检测**：说"不追"但涨了会被抓出来
3. **精确评估指标**：不再简单看"池子是否删除"，有真实收益计算
4. **知识自动提取**：失败案例自动沉淀到经验库

### 技术优势
1. **可测试性**：策略模式易 mock，单元测试覆盖度高
2. **可扩展性**：新增决策类型只需实现新策略，不改主流程
3. **可维护性**：领域逻辑集中在领域层，不散落在 API/Service

---

## 8. 迁移策略

### 向后兼容
- 现有 DecisionAuditTool 继续工作
- 现有 agent_decisions 数据自动兼容
- 新增字段可空，渐进式迁移

### 灰度发布
1. Phase 1-2：后端实现，不影响前端
2. Phase 3：应用层编排，定时任务开始使用新逻辑
3. Phase 4：前端工具升级，agent 开始记录新类型决策

---

**总工作量**: 5 小时（3h 后端 + 1h 应用层 + 1h 前端）
**优先级**: P1（进化自动化的关键环节）
**依赖**: 无（独立可实施）
