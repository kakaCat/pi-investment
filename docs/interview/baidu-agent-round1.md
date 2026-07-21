# 百度 AI Agent 一面高频题整理

## 1. 代码Agent或自动补全的输出如果被决定怎么设计？什么是ICM？

**答案：**

### 问题理解
这个问题实际在问：**如何保证Agent输出的一致性和可控性**。

### ICM (Incremental Context Management)

**定义：** 增量上下文管理，是一种动态管理上下文的策略。

```typescript
class IncrementalContextManager {
  private context: Context[] = []
  private maxTokens = 8000
  
  // 增量添加上下文
  addContext(newContext: Context) {
    this.context.push(newContext)
    
    // 超出限制时，智能压缩
    if (this.getTotalTokens() > this.maxTokens) {
      this.compress()
    }
  }
  
  // 智能压缩：保留最重要的部分
  private compress() {
    // 1. 计算每个上下文的重要性
    const scored = this.context.map(ctx => ({
      context: ctx,
      score: this.calculateImportance(ctx)
    }))
    
    // 2. 按重要性排序
    scored.sort((a, b) => b.score - a.score)
    
    // 3. 保留高分上下文直到token预算用完
    let totalTokens = 0
    this.context = []
    
    for (const item of scored) {
      const tokens = this.countTokens(item.context)
      if (totalTokens + tokens <= this.maxTokens) {
        this.context.push(item.context)
        totalTokens += tokens
      }
    }
  }
  
  private calculateImportance(ctx: Context): number {
    let score = 0
    
    // 因子1：类型（系统消息 > 工具调用 > 普通对话）
    if (ctx.type === 'system') score += 10
    else if (ctx.type === 'tool_call') score += 8
    else if (ctx.type === 'user') score += 5
    
    // 因子2：新鲜度（越新越重要）
    const ageInMinutes = (Date.now() - ctx.timestamp) / 60000
    score += Math.max(0, 5 - ageInMinutes / 10)
    
    // 因子3：引用次数（被后续对话引用越多越重要）
    score += ctx.referenceCount * 2
    
    return score
  }
}
```

### 代码输出的确定性设计

**问题：** 同样的输入，每次生成的代码可能不同

**解决方案：**

#### 1. 温度参数控制
```python
# 代码生成时使用低温度
response = llm.generate(
    prompt=code_prompt,
    temperature=0.0,  # 完全确定性
    # temperature=0.2,  # 轻微随机性（推荐）
    top_p=0.95
)
```

#### 2. 结构化输出
```typescript
// 使用JSON Schema强制输出格式
const schema = {
  type: "object",
  properties: {
    code: { type: "string", description: "生成的代码" },
    explanation: { type: "string", description: "代码说明" },
    imports: { 
      type: "array", 
      items: { type: "string" },
      description: "需要导入的模块"
    }
  },
  required: ["code", "explanation", "imports"]
}

const response = await llm.generate(prompt, {
  response_format: { type: "json_schema", schema }
})
```

#### 3. Few-shot固定输出模式
```typescript
const prompt = `
你是代码生成助手，输出必须严格遵循以下格式：

示例1：
输入: 实现快速排序
输出:
\`\`\`typescript
function quickSort(arr: number[]): number[] {
  if (arr.length <= 1) return arr
  // 实现...
}
\`\`\`

示例2：
输入: 实现二分查找
输出:
\`\`\`typescript
function binarySearch(arr: number[], target: number): number {
  let left = 0, right = arr.length - 1
  // 实现...
}
\`\`\`

现在，请为以下需求生成代码：
输入: ${userRequest}
输出:
`
```

#### 4. 后处理标准化
```typescript
class CodeOutputStandardizer {
  standardize(rawCode: string): StandardizedCode {
    return {
      // 1. 格式化代码
      code: this.formatCode(rawCode),
      
      // 2. 提取导入语句
      imports: this.extractImports(rawCode),
      
      // 3. 提取函数签名
      signatures: this.extractSignatures(rawCode),
      
      // 4. 添加标准注释
      documented: this.addDocumentation(rawCode)
    }
  }
  
  private formatCode(code: string): string {
    // 使用prettier/black等格式化工具
    return prettier.format(code, {
      parser: "typescript",
      semi: true,
      singleQuote: true,
      trailingComma: "es5"
    })
  }
}
```

#### 5. 缓存机制
```typescript
class CodeGenerationCache {
  private cache = new Map<string, GeneratedCode>()
  
  async generate(prompt: string): Promise<GeneratedCode> {
    // 对prompt进行标准化（去除空格、统一大小写等）
    const normalizedPrompt = this.normalizePrompt(prompt)
    
    // 计算hash作为缓存key
    const cacheKey = this.hash(normalizedPrompt)
    
    // 检查缓存
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey)!
    }
    
    // 生成代码
    const code = await llm.generate(prompt, { temperature: 0 })
    
    // 存入缓存
    this.cache.set(cacheKey, code)
    
    return code
  }
  
  private normalizePrompt(prompt: string): string {
    return prompt
      .toLowerCase()
      .replace(/\s+/g, ' ')  // 多个空格合并为一个
      .trim()
  }
}
```

#### 6. 版本控制和回滚
```typescript
class CodeVersionControl {
  private versions: Map<string, CodeVersion[]> = new Map()
  
  async generateWithVersion(request: CodeRequest): Promise<CodeResult> {
    // 生成代码
    const code = await this.generate(request)
    
    // 保存版本
    const version: CodeVersion = {
      id: generateId(),
      code: code,
      prompt: request.prompt,
      timestamp: Date.now(),
      metadata: {
        model: "gpt-4",
        temperature: 0.2,
        hash: this.hash(code)
      }
    }
    
    this.saveVersion(request.contextId, version)
    
    return {
      code: code,
      versionId: version.id
    }
  }
  
  // 如果用户不满意，可以回滚到之前的版本
  async rollback(contextId: string, versionId: string) {
    const versions = this.versions.get(contextId) || []
    const targetVersion = versions.find(v => v.id === versionId)
    
    if (targetVersion) {
      return targetVersion.code
    }
    
    throw new Error('Version not found')
  }
}
```

### 实战建议

**场景1：自动补全（高频调用）**
```typescript
// 要求：快速、一致、精简
const config = {
  temperature: 0.1,      // 轻微随机性
  max_tokens: 50,        // 限制长度
  cache_enabled: true,   // 启用缓存
  model: "gpt-3.5-turbo" // 使用快速模型
}
```

**场景2：代码生成（复杂任务）**
```typescript
// 要求：准确、完整、可控
const config = {
  temperature: 0.2,      // 低随机性
  max_tokens: 2000,      // 允许完整代码
  cache_enabled: true,
  model: "gpt-4",        // 使用高质量模型
  response_format: "json_schema" // 结构化输出
}
```

## 2. 怎么判断一个提示词模板是真的更好了？有没有量化的评估标准？

**答案：**

### 评估框架

提示词优化需要建立**科学的评估体系**，而不是凭感觉。

### 1. 离线评估（Offline Evaluation）

#### A. 准确率指标
```python
class PromptEvaluator:
    def evaluate_accuracy(self, prompt_template: str, test_cases: List[TestCase]):
        results = []
        
        for case in test_cases:
            # 使用提示词生成输出
            output = llm.generate(prompt_template.format(**case.input))
            
            # 与期望输出对比
            is_correct = self.compare(output, case.expected_output)
            results.append(is_correct)
        
        accuracy = sum(results) / len(results)
        return {
            "accuracy": accuracy,
            "correct": sum(results),
            "total": len(results)
        }
    
    def compare(self, output: str, expected: str) -> bool:
        # 方法1：精确匹配
        if output.strip() == expected.strip():
            return True
        
        # 方法2：语义相似度（使用embedding）
        similarity = self.semantic_similarity(output, expected)
        return similarity > 0.85
        
        # 方法3：结构化匹配（对于JSON输出）
        try:
            output_json = json.loads(output)
            expected_json = json.loads(expected)
            return output_json == expected_json
        except:
            return False
```

#### B. 鲁棒性指标
```python
def evaluate_robustness(prompt_template: str):
    """评估提示词对输入变化的鲁棒性"""
    
    test_variations = [
        "写一个排序函数",
        "请写一个排序函数",
        "帮我写一个排序函数",
        "能否写一个排序函数？",
        "我需要一个排序函数",
    ]
    
    outputs = [llm.generate(prompt_template.format(input=v)) 
               for v in test_variations]
    
    # 计算输出的一致性
    # 期望：不同表述应该产生类似的输出
    consistency_score = calculate_output_consistency(outputs)
    
    return {
        "consistency": consistency_score,
        "message": "高分表示对输入变化不敏感（好）"
    }
```

#### C. 效率指标
```python
def evaluate_efficiency(prompt_template: str):
    """评估token消耗和响应时间"""
    
    test_cases = load_test_cases()
    
    total_input_tokens = 0
    total_output_tokens = 0
    total_time = 0
    
    for case in test_cases:
        start = time.time()
        
        prompt = prompt_template.format(**case.input)
        response = llm.generate(prompt)
        
        elapsed = time.time() - start
        
        total_input_tokens += count_tokens(prompt)
        total_output_tokens += count_tokens(response)
        total_time += elapsed
    
    return {
        "avg_input_tokens": total_input_tokens / len(test_cases),
        "avg_output_tokens": total_output_tokens / len(test_cases),
        "avg_latency_ms": (total_time / len(test_cases)) * 1000,
        "cost_per_request": calculate_cost(
            total_input_tokens, total_output_tokens
        ) / len(test_cases)
    }
```

### 2. A/B测试（Online Evaluation）

```python
class PromptABTest:
    def __init__(self):
        self.variant_a = "旧提示词模板"
        self.variant_b = "新提示词模板"
        self.traffic_split = 0.5  # 50%流量到新版本
    
    def run_experiment(self, duration_days=7):
        """运行A/B测试"""
        
        for user_request in self.get_production_traffic():
            # 随机分配到A或B组
            variant = self.assign_variant(user_request.user_id)
            
            prompt_template = (self.variant_a if variant == 'A' 
                             else self.variant_b)
            
            # 生成响应
            response = llm.generate(
                prompt_template.format(**user_request.params)
            )
            
            # 记录指标
            self.log_metrics(
                variant=variant,
                latency=response.latency,
                user_feedback=None  # 待收集
            )
    
    def analyze_results(self):
        """分析A/B测试结果"""
        
        metrics_a = self.get_metrics('A')
        metrics_b = self.get_metrics('B')
        
        return {
            "用户满意度": {
                "A": metrics_a.satisfaction,
                "B": metrics_b.satisfaction,
                "提升": (metrics_b.satisfaction - metrics_a.satisfaction) / metrics_a.satisfaction
            },
            "响应时间": {
                "A": metrics_a.latency,
                "B": metrics_b.latency,
                "改善": metrics_a.latency - metrics_b.latency
            },
            "成本": {
                "A": metrics_a.cost,
                "B": metrics_b.cost,
                "节省": (metrics_a.cost - metrics_b.cost) / metrics_a.cost
            },
            "统计显著性": self.statistical_significance(metrics_a, metrics_b)
        }
```

### 3. 综合评分卡

```python
class PromptScorecardEvaluator:
    """多维度综合评估"""
    
    def evaluate(self, prompt_template: str) -> dict:
        # 1. 准确性 (40%)
        accuracy = self.evaluate_accuracy(prompt_template)
        
        # 2. 鲁棒性 (20%)
        robustness = self.evaluate_robustness(prompt_template)
        
        # 3. 效率 (20%)
        efficiency = self.evaluate_efficiency(prompt_template)
        
        # 4. 可维护性 (10%)
        maintainability = self.evaluate_maintainability(prompt_template)
        
        # 5. 用户满意度 (10%)
        satisfaction = self.evaluate_satisfaction(prompt_template)
        
        # 加权总分
        total_score = (
            accuracy * 0.4 +
            robustness * 0.2 +
            efficiency * 0.2 +
            maintainability * 0.1 +
            satisfaction * 0.1
        )
        
        return {
            "total_score": total_score,
            "breakdown": {
                "accuracy": accuracy,
                "robustness": robustness,
                "efficiency": efficiency,
                "maintainability": maintainability,
                "satisfaction": satisfaction
            },
            "recommendation": self.get_recommendation(total_score)
        }
```

### 4. 实战评估流程

```python
# Step 1: 准备测试集
test_cases = [
    {
        "input": {"task": "实现快速排序"},
        "expected_output": "包含quickSort函数的TypeScript代码",
        "evaluation_criteria": {
            "has_function": True,
            "is_valid_code": True,
            "time_complexity_mentioned": True
        }
    },
    # ... 更多测试用例
]

# Step 2: 评估旧提示词
old_prompt = """请生成{task}的代码。"""
old_score = evaluator.evaluate(old_prompt, test_cases)

# Step 3: 评估新提示词
new_prompt = """
你是专业的代码生成助手。

任务: {task}

要求:
1. 使用TypeScript
2. 包含类型注解
3. 添加注释说明
4. 考虑边界情况

输出格式:
\`\`\`typescript
// 你的代码
\`\`\`
"""
new_score = evaluator.evaluate(new_prompt, test_cases)

# Step 4: 对比分析
comparison = {
    "准确率": {
        "old": old_score['accuracy'],
        "new": new_score['accuracy'],
        "提升": new_score['accuracy'] - old_score['accuracy']
    },
    "平均tokens": {
        "old": old_score['avg_tokens'],
        "new": new_score['avg_tokens'],
        "差异": new_score['avg_tokens'] - old_score['avg_tokens']
    },
    "成本": {
        "old": old_score['cost'],
        "new": new_score['cost'],
        "差异": new_score['cost'] - old_score['cost']
    }
}

# Step 5: 做决策
if new_score['total_score'] > old_score['total_score'] * 1.05:  # 提升>5%
    print("✅ 新提示词更好，建议采用")
else:
    print("❌ 改进不明显，需要继续优化")
```

### 5. 关键指标定义

| 指标 | 定义 | 计算方法 | 目标值 |
|------|------|----------|--------|
| **准确率** | 输出符合期望的比例 | 正确数/总数 | >90% |
| **鲁棒性** | 对输入变化的稳定性 | 输出一致性得分 | >0.85 |
| **Token效率** | 单次请求平均token | 总tokens/请求数 | 越低越好 |
| **响应时间** | 平均生成时间 | 总时间/请求数 | <2s |
| **用户满意度** | 用户点赞率 | 点赞数/总数 | >80% |
| **任务完成率** | 一次性完成任务比例 | 无需修改的输出数/总数 | >75% |

### 最佳实践

```
1. ✅ 建立基准测试集（至少50个真实case）
2. ✅ 每次修改都跑回归测试
3. ✅ A/B测试验证实际效果
4. ✅ 收集用户反馈（满意度、修改次数）
5. ✅ 监控成本变化（token消耗）
6. ✅ 持续迭代优化
```


## 3. Agent是单Agent还是多Agent？为什么这么设计？有没有考虑过另一种方案？

**答案：**

### 单Agent vs 多Agent决策树

```
任务类型分析
  ↓
任务是否可以清晰分解为独立子任务？
  No → 单Agent（串行处理）
  Yes ↓
  
子任务之间需要频繁协作吗？
  Yes → 单Agent（协调成本高）
  No ↓
  
子任务的专业领域差异大吗？
  Yes → 多Agent（专业化优势）
  No ↓
  
需要并行提升效率吗？
  Yes → 多Agent（并行执行）
  No → 单Agent（简单直接）
```

### 单Agent架构

**适用场景：**
- ✅ 任务简单，步骤少
- ✅ 需要连贯的上下文
- ✅ 预算有限
- ✅ 开发资源紧张

**示例：个人编程助手**
```typescript
class SingleCodeAgent {
  async handleRequest(userInput: string): Promise<string> {
    // 一个Agent处理所有任务
    const intent = await this.understandIntent(userInput)
    
    switch (intent.type) {
      case 'code_generation':
        return await this.generateCode(intent)
      case 'code_review':
        return await this.reviewCode(intent)
      case 'bug_fix':
        return await this.fixBug(intent)
      case 'explain':
        return await this.explainCode(intent)
      default:
        return await this.generalResponse(intent)
    }
  }
}
```

**优点：**
- ✅ 架构简单，易于实现
- ✅ 上下文连贯（单一会话）
- ✅ 成本低（只调用一个模型）
- ✅ 调试容易（单一执行流程）

**缺点：**
- ❌ 能力有限（一个Agent难以精通所有领域）
- ❌ 扩展性差（新功能都堆在一起）
- ❌ 无法并行（串行执行）
- ❌ Prompt膨胀（所有能力都写在一个prompt里）

### 多Agent架构

**适用场景：**
- ✅ 任务复杂，需要多个专业领域
- ✅ 可以并行处理
- ✅ 需要高质量输出
- ✅ 有足够的预算

**示例1：协作式多Agent（软件开发团队）**
```typescript
class MultiAgentSystem {
  private agents = {
    architect: new ArchitectAgent(),    // 架构师
    developer: new DeveloperAgent(),    // 开发者
    reviewer: new ReviewerAgent(),      // 审查者
    tester: new TesterAgent()          // 测试员
  }
  
  async developFeature(requirement: string): Promise<Result> {
    // Step 1: 架构师设计方案
    const design = await this.agents.architect.design(requirement)
    
    // Step 2: 开发者实现代码（可以多个并行）
    const implementations = await Promise.all([
      this.agents.developer.implement(design.backend),
      this.agents.developer.implement(design.frontend)
    ])
    
    // Step 3: 审查者检查代码
    const review = await this.agents.reviewer.review(implementations)
    
    // Step 4: 测试员编写测试
    const tests = await this.agents.tester.generateTests(implementations)
    
    return {
      code: implementations,
      review: review,
      tests: tests
    }
  }
}
```

**示例2：竞争式多Agent（多角度分析）**
```typescript
class CompetitiveMultiAgent {
  async analyzeStock(symbol: string): Promise<Decision> {
    // 3个Agent独立分析，给出不同视角
    const analyses = await Promise.all([
      this.fundamentalAgent.analyze(symbol),  // 基本面分析
      this.technicalAgent.analyze(symbol),    // 技术面分析
      this.sentimentAgent.analyze(symbol)     // 情绪面分析
    ])
    
    // 聚合多个观点
    return this.aggregateDecisions(analyses)
  }
  
  aggregateDecisions(analyses: Analysis[]): Decision {
    // 投票机制
    const votes = analyses.map(a => a.recommendation)
    const majority = this.getMajorityVote(votes)
    
    // 加权平均
    const confidenceScore = analyses.reduce((sum, a) => 
      sum + a.confidence, 0
    ) / analyses.length
    
    return {
      recommendation: majority,
      confidence: confidenceScore,
      reasoning: analyses.map(a => a.reasoning)
    }
  }
}
```

**多Agent协作模式：**

#### 1. 串行协作（Pipeline）
```typescript
// Agent按顺序处理，前一个的输出是下一个的输入
const result = await pipe(
  researchAgent,
  planningAgent,
  executionAgent,
  reviewAgent
)(initialInput)
```

#### 2. 并行协作（Fan-out/Fan-in）
```typescript
// 多个Agent并行处理，最后汇总
const results = await Promise.all([
  agent1.process(input),
  agent2.process(input),
  agent3.process(input)
])
const final = await coordinatorAgent.aggregate(results)
```

#### 3. 层级协作（Hierarchical）
```typescript
class HierarchicalSystem {
  manager: ManagerAgent      // 管理者：分配任务
  workers: WorkerAgent[]     // 工作者：执行任务
  
  async execute(task: Task): Promise<Result> {
    // Manager分解任务
    const subtasks = await this.manager.decompose(task)
    
    // Workers并行执行
    const results = await Promise.all(
      subtasks.map(st => this.assignWorker(st).execute(st))
    )
    
    // Manager汇总结果
    return await this.manager.synthesize(results)
  }
}
```

#### 4. 辩论协作（Debate）
```typescript
class DebateSystem {
  async makeDecision(problem: string): Promise<Decision> {
    let round = 0
    let proposals = []
    
    // 多轮辩论
    while (round < MAX_ROUNDS) {
      // Agent1提出方案
      const proposal1 = await this.agent1.propose(problem, proposals)
      
      // Agent2批评并提出替代方案
      const critique = await this.agent2.critique(proposal1)
      const proposal2 = await this.agent2.propose(problem, [...proposals, critique])
      
      // Agent3作为裁判评估
      const evaluation = await this.judge.evaluate([proposal1, proposal2])
      
      if (evaluation.consensus) {
        return evaluation.decision
      }
      
      proposals.push(proposal1, proposal2)
      round++
    }
    
    // 最终由裁判决定
    return await this.judge.finalDecision(proposals)
  }
}
```

### 我的项目选择

**项目：投资Agent系统**

**选择：单Agent + 模块化设计**

**原因：**

```typescript
// 虽然是单Agent，但内部模块化设计
class InvestmentAgent {
  // 不同能力通过工具实现，而不是多个Agent
  private tools = {
    // 数据工具
    marketData: new MarketDataTool(),
    fundamentalAnalysis: new FundamentalTool(),
    technicalAnalysis: new TechnicalTool(),
    
    // 决策工具
    portfolioOptimization: new PortfolioTool(),
    riskAssessment: new RiskTool(),
    
    // 执行工具
    tradeExecution: new TradeTool(),
    positionManagement: new PositionTool()
  }
  
  async executeTask(task: Task): Promise<Result> {
    // 单个Agent，但可以灵活调用不同工具
    const plan = await this.plan(task)
    
    for (const step of plan.steps) {
      const tool = this.tools[step.toolName]
      const result = await tool.execute(step.params)
      
      // 根据结果调整后续步骤
      if (this.shouldAdjustPlan(result)) {
        plan = await this.replan(plan, result)
      }
    }
    
    return this.synthesizeResults(plan.results)
  }
}
```

**为什么不用多Agent？**

1. **任务连贯性要求高**
   - 投资决策需要综合考虑多个因素
   - 中间状态需要保持（不能切换Agent丢失上下文）

2. **成本考虑**
   - 每天自动运行多次
   - 多Agent会导致token消耗激增

3. **调试复杂度**
   - 单Agent更容易追踪决策过程
   - 多Agent的协调逻辑容易出bug

4. **实时性要求**
   - 需要快速响应市场变化
   - 多Agent通信会增加延迟

### 考虑过的替代方案

**方案A：多Agent专家系统（未采用）**
```typescript
// 考虑过用多个专家Agent
class ExpertSystem {
  fundamentalExpert: Agent  // 基本面专家
  technicalExpert: Agent    // 技术面专家
  riskExpert: Agent         // 风险管理专家
  coordinator: Agent        // 协调者
}

// 为什么没用？
// ❌ 成本高：每个决策需要调用4个Agent
// ❌ 延迟高：串行调用时间长
// ❌ 过度设计：实际上工具调用就能解决
```

**方案B：混合架构（考虑中）**
```typescript
// 未来可能采用的方案
class HybridSystem {
  // 主Agent：日常决策
  mainAgent: Agent
  
  // 辅助Agent：特殊场景
  deepResearchAgent: Agent    // 深度研究（低频）
  riskReviewAgent: Agent      // 风险审查（高风险交易时）
  performanceAnalyzer: Agent  // 业绩归因（定期）
  
  async makeDecision(context: Context): Promise<Decision> {
    // 95%的决策由主Agent处理
    const decision = await this.mainAgent.decide(context)
    
    // 高风险决策时，启用风险审查Agent
    if (decision.risk > THRESHOLD) {
      const review = await this.riskReviewAgent.review(decision)
      if (!review.approved) {
        return this.alternativeDecision(context)
      }
    }
    
    return decision
  }
}
```

### 决策建议

**选择单Agent如果：**
- 任务规模小-中等
- 预算有限
- 团队规模小
- 需要快速上线

**选择多Agent如果：**
- 任务高度复杂（如完整的软件开发流程）
- 需要专业领域知识（医疗、法律等）
- 可以并行提升效率
- 有足够预算

**最佳实践：**
```
开始：单Agent
成长：单Agent + 模块化工具
成熟：单Agent + 关键场景多Agent
极致：完全多Agent系统
```

## 4. Agent的任务是怎么拆分的？拆分粒度是怎么决定的？

**答案：**

### 任务拆分原则

#### 1. SMART原则
```
S - Specific (具体的)
M - Measurable (可衡量的)
A - Achievable (可实现的)
R - Relevant (相关的)
T - Time-bound (有时限的)
```

**示例：**
```typescript
// ❌ 拆分粒度过粗
const task = "开发用户系统"

// ✅ 拆分为具体的子任务
const subtasks = [
  "设计用户数据模型（User, Profile表）",
  "实现用户注册API（POST /api/users/register）",
  "实现用户登录API（POST /api/users/login）",
  "实现JWT认证中间件",
  "编写用户API的单元测试"
]
```

#### 2. 单一职责原则
```typescript
// 每个子任务只做一件事

// ❌ 职责不清
"实现用户注册并发送欢迎邮件并记录日志"

// ✅ 拆分为独立职责
[
  "实现用户注册逻辑",
  "发送欢迎邮件",
  "记录注册日志"
]
```

#### 3. 原子性原则
```typescript
// 原子任务：不可再分且能独立执行

class TaskDecomposer {
  isAtomic(task: Task): boolean {
    // 判断标准：
    // 1. 估计时间 < 1小时
    // 2. 输入输出明确
    // 3. 不依赖其他未完成的任务
    // 4. 可以独立验证完成
    
    return (
      task.estimatedTime < 60 &&
      task.hasCanClearInputOutput() &&
      task.dependencies.length === 0 &&
      task.isVerifiable()
    )
  }
  
  async decompose(task: Task): Promise<Task[]> {
    if (this.isAtomic(task)) {
      return [task]
    }
    
    // 递归分解
    const subtasks = await this.breakdown(task)
    const atomicTasks = []
    
    for (const subtask of subtasks) {
      const atoms = await this.decompose(subtask)
      atomicTasks.push(...atoms)
    }
    
    return atomicTasks
  }
}
```

### 拆分粒度决策

#### 粒度对比表

| 粒度 | 特点 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| **粗粒度** | 大任务，少量步骤 | 上下文连贯、协调简单 | 难以并行、错误影响大 | 简单任务 |
| **中粒度** | 合理拆分，平衡 | 灵活性好、可控性强 | 需要协调 | 大部分场景 |
| **细粒度** | 小任务，多步骤 | 高度并行、精确控制 | 协调复杂、开销大 | 复杂系统 |

#### 动态粒度调整
```typescript
class AdaptiveTaskDecomposer {
  async decompose(task: Task, context: Context): Promise<Task[]> {
    // 因素1：任务复杂度
    const complexity = this.assessComplexity(task)
    
    // 因素2：可用资源
    const resources = context.availableResources
    
    // 因素3：时间压力
    const urgency = context.deadline ? 
      (context.deadline - Date.now()) : Infinity
    
    // 因素4：错误容忍度
    const errorTolerance = context.criticalLevel
    
    // 决定粒度
    let granularity: 'coarse' | 'medium' | 'fine'
    
    if (complexity === 'low' && urgency < HOUR) {
      // 简单且紧急 → 粗粒度（快速完成）
      granularity = 'coarse'
    } else if (complexity === 'high' || errorTolerance === 'low') {
      // 复杂或关键 → 细粒度（精确控制）
      granularity = 'fine'
    } else {
      // 一般情况 → 中粒度
      granularity = 'medium'
    }
    
    return this.decomposeWithGranularity(task, granularity)
  }
  
  assessComplexity(task: Task): 'low' | 'medium' | 'high' {
    let score = 0
    
    // 指标1：描述长度
    if (task.description.length > 500) score += 2
    else if (task.description.length > 200) score += 1
    
    // 指标2：依赖数量
    score += Math.min(task.dependencies.length, 3)
    
    // 指标3：领域知识要求
    if (task.requiresDomainKnowledge) score += 2
    
    // 指标4：是否有现成模板
    if (!task.hasTemplate) score += 1
    
    if (score >= 6) return 'high'
    if (score >= 3) return 'medium'
    return 'low'
  }
}
```

### 实战拆分示例

#### 示例1：开发一个Todo API

**粗粒度拆分（不推荐）：**
```typescript
const tasks = [
  "实现Todo CRUD功能"  // 太粗，不知道从何下手
]
```

**中粒度拆分（推荐）：**
```typescript
const tasks = [
  "设计Todo数据模型",
  "实现创建Todo接口",
  "实现查询Todo列表接口",
  "实现更新Todo接口",
  "实现删除Todo接口",
  "编写API测试"
]
```

**细粒度拆分（过度设计）：**
```typescript
const tasks = [
  "定义Todo接口类型",
  "创建Todo数据库表",
  "编写Todo Model类",
  "实现Todo创建的数据验证",
  "实现Todo创建的业务逻辑",
  "实现Todo创建的数据库操作",
  "实现Todo创建的错误处理",
  "实现Todo创建的API路由",
  // ... 太细，协调成本高
]
```

#### 示例2：Agent自动拆分

```typescript
class SmartTaskDecomposer {
  async decompose(userRequest: string): Promise<Task[]> {
    const prompt = `
    用户请求: ${userRequest}
    
    请将此任务拆分为可执行的子任务。
    
    拆分原则:
    1. 每个子任务估计时间30-60分钟
    2. 子任务之间依赖关系清晰
    3. 每个子任务有明确的完成标准
    
    输出格式:
    {
      "tasks": [
        {
          "id": "task-1",
          "description": "具体任务描述",
          "estimatedTime": 45,
          "dependencies": [],
          "acceptanceCriteria": "完成标准"
        }
      ]
    }
    `
    
    const response = await llm.generate(prompt, {
      response_format: "json"
    })
    
    return JSON.parse(response).tasks
  }
}

// 使用示例
const decomposer = new SmartTaskDecomposer()
const tasks = await decomposer.decompose(
  "实现一个带认证的博客系统"
)

// 输出示例:
// [
//   { id: "1", description: "设计数据库schema（User、Post、Comment表）", time: 30, deps: [] },
//   { id: "2", description: "实现JWT认证中间件", time: 45, deps: [] },
//   { id: "3", description: "实现用户注册/登录API", time: 60, deps: ["2"] },
//   { id: "4", description: "实现文章CRUD API", time: 60, deps: ["1", "2"] },
//   { id: "5", description: "实现评论功能API", time: 45, deps: ["1", "4"] }
// ]
```

### 拆分后的执行策略

```typescript
class TaskExecutor {
  async execute(tasks: Task[]): Promise<Result> {
    // 1. 构建依赖图
    const graph = this.buildDependencyGraph(tasks)
    
    // 2. 拓扑排序（确定执行顺序）
    const sortedTasks = this.topologicalSort(graph)
    
    // 3. 识别可并行的任务
    const layers = this.identifyParallelLayers(sortedTasks)
    
    // 4. 分层执行
    const results = []
    for (const layer of layers) {
      // 同一层的任务可以并行执行
      const layerResults = await Promise.all(
        layer.map(task => this.executeTask(task))
      )
      results.push(...layerResults)
    }
    
    return this.aggregateResults(results)
  }
  
  identifyParallelLayers(tasks: Task[]): Task[][] {
    const layers: Task[][] = []
    const completed = new Set<string>()
    
    while (completed.size < tasks.length) {
      const currentLayer = tasks.filter(task => 
        // 依赖都已完成的任务可以并行执行
        !completed.has(task.id) &&
        task.dependencies.every(dep => completed.has(dep))
      )
      
      layers.push(currentLayer)
      currentLayer.forEach(task => completed.add(task.id))
    }
    
    return layers
  }
}
```

### 最佳实践

**1. 使用估算时间判断**
```
粗粒度：2-4小时/任务
中粒度：30-60分钟/任务 ✅ 推荐
细粒度：5-15分钟/任务
```

**2. 考虑Agent的能力边界**
```typescript
// 不要拆分成Agent无法理解的任务
// ❌ "优化算法的时间复杂度" （太抽象）
// ✅ "将嵌套循环改为哈希表查找" （具体）
```

**3. 保留必要的上下文**
```typescript
interface Task {
  id: string
  description: string
  context: {
    projectName: string
    relatedFiles: string[]
    previousSteps: string[]
  }
  // 每个任务携带必要上下文，避免信息丢失
}
```

**4. 动态调整**
```typescript
// 执行过程中根据实际情况调整

if (task.failed && task.complexity === 'high') {
  // 失败了 → 拆分得更细
  const subtasks = await decomposer.decomposeMore(task)
  await execute(subtasks)
}

if (task.succeededQuickly && task.siblings.length > 0) {
  // 完成太快 → 合并相似任务
  const merged = await merger.mergeSimilarTasks(task.siblings)
  await execute(merged)
}
```


## 5. 上下文是怎么构建的？怎么避免上下文过长或者信息污染？

**答案：**

### 上下文构建策略

上下文构建的核心是：**在token预算内提供最相关的信息**。

#### 1. 分层上下文架构

```typescript
interface Context {
  // Layer 0: 系统级（永久保留）
  systemPrompt: string        // 角色定义、行为准则
  
  // Layer 1: 项目级（会话内保留）
  projectContext: {
    name: string
    techStack: string[]
    codeStyle: StyleGuide
    architecture: string
  }
  
  // Layer 2: 对话级（定期压缩）
  conversationHistory: Message[]
  
  // Layer 3: 任务级（动态召回）
  relevantMemories: Memory[]
  relevantFiles: File[]
  relevantDocs: Document[]
}
```

#### 2. 上下文构建流程

```typescript
class ContextBuilder {
  private maxTokens = 32000      // 总预算
  private reservedForOutput = 4000  // 为输出预留
  
  async buildContext(userInput: string, session: Session): Promise<Context> {
    let availableTokens = this.maxTokens - this.reservedForOutput
    const context: Context = {}
    
    // Step 1: 系统Prompt（必须，P0）
    context.system = this.getSystemPrompt()
    availableTokens -= this.countTokens(context.system)
    
    // Step 2: 用户输入（必须，P0）
    context.userInput = userInput
    availableTokens -= this.countTokens(userInput)
    
    // Step 3: 最近N条对话（重要，P1）
    context.recentMessages = this.getRecentMessages(session, 5)
    availableTokens -= this.countTokens(context.recentMessages)
    
    // Step 4: 相关文件/文档（按需，P2）
    if (availableTokens > 5000) {
      const relevantFiles = await this.retrieveRelevantFiles(
        userInput, 
        session,
        maxTokens: Math.min(availableTokens * 0.4, 8000)
      )
      context.files = relevantFiles
      availableTokens -= this.countTokens(relevantFiles)
    }
    
    // Step 5: 历史记忆（可选，P3）
    if (availableTokens > 3000) {
      const memories = await this.recallMemories(
        userInput,
        maxTokens: Math.min(availableTokens * 0.3, 5000)
      )
      context.memories = memories
      availableTokens -= this.countTokens(memories)
    }
    
    // Step 6: 项目上下文（可选，P4）
    if (availableTokens > 2000) {
      context.project = this.getProjectContext(session.projectId)
      availableTokens -= this.countTokens(context.project)
    }
    
    console.log(`Context built: ${this.maxTokens - availableTokens}/${this.maxTokens} tokens used`)
    
    return context
  }
  
  // 智能检索相关文件
  async retrieveRelevantFiles(
    query: string, 
    session: Session,
    maxTokens: number
  ): Promise<File[]> {
    // 1. 语义检索
    const semanticResults = await this.vectorDB.search(query, topK: 10)
    
    // 2. 关键词检索
    const keywords = this.extractKeywords(query)
    const keywordResults = await this.bm25Search(keywords)
    
    // 3. 文件依赖关系
    const currentFile = session.currentFile
    const dependencyResults = currentFile ? 
      await this.getDependencies(currentFile) : []
    
    // 4. 合并去重
    const allResults = this.mergeAndDedupe([
      semanticResults,
      keywordResults,
      dependencyResults
    ])
    
    // 5. 重排序
    const reranked = this.rerank(query, allResults)
    
    // 6. 截断到token预算
    return this.truncateToTokenLimit(reranked, maxTokens)
  }
}
```

### 避免上下文过长

#### 策略1：滚动窗口
```typescript
class RollingWindowContext {
  private maxMessages = 20
  
  addMessage(message: Message) {
    this.messages.push(message)
    
    // 超过限制，移除最旧的（保留系统消息）
    if (this.messages.length > this.maxMessages) {
      const systemMessages = this.messages.filter(m => m.role === 'system')
      const nonSystemMessages = this.messages.filter(m => m.role !== 'system')
      
      // 保留系统消息 + 最近的非系统消息
      this.messages = [
        ...systemMessages,
        ...nonSystemMessages.slice(-this.maxMessages + systemMessages.length)
      ]
    }
  }
}
```

#### 策略2：智能摘要
```typescript
class SmartSummarizer {
  async compress(messages: Message[]): Promise<Message[]> {
    // 1. 识别重要消息
    const important = this.filterImportant(messages)
    
    // 2. 对不重要的消息进行摘要
    const unimportant = messages.filter(m => !important.includes(m))
    const summary = await this.summarize(unimportant)
    
    // 3. 构造压缩后的上下文
    return [
      ...important,
      {
        role: 'system',
        content: `[对话摘要]\n${summary}`
      }
    ]
  }
  
  filterImportant(messages: Message[]): Message[] {
    return messages.filter(m => 
      // 系统消息
      m.role === 'system' ||
      // 包含工具调用
      m.tool_calls?.length > 0 ||
      // 用户明确标记
      m.metadata?.important === true ||
      // 最近5条
      messages.indexOf(m) >= messages.length - 5
    )
  }
  
  async summarize(messages: Message[]): Promise<string> {
    const prompt = `
    请总结以下对话的关键信息：
    
    ${this.formatMessages(messages)}
    
    要求：
    1. 保留所有重要决策和结论
    2. 保留未完成的任务
    3. 保留用户偏好和设置
    4. 忽略闲聊和重复内容
    5. 精简到500字以内
    `
    
    return await llm.generate(prompt, { maxTokens: 1000 })
  }
}
```

#### 策略3：分层缓存
```typescript
class TieredContextCache {
  // 热数据：当前会话，完整保留
  private hotCache: Message[] = []
  
  // 温数据：最近会话，摘要保留
  private warmCache: Map<string, Summary> = new Map()
  
  // 冷数据：历史会话，向量检索
  private coldStorage: VectorDB
  
  async getContext(sessionId: string, query: string): Promise<Context> {
    return {
      // 热数据：直接返回
      recent: this.hotCache,
      
      // 温数据：加载摘要
      recentSessions: Array.from(this.warmCache.values()),
      
      // 冷数据：按需检索
      historical: await this.coldStorage.search(query, topK: 3)
    }
  }
  
  async archiveSession(sessionId: string) {
    // 将热数据归档到温数据
    const summary = await this.summarize(this.hotCache)
    this.warmCache.set(sessionId, summary)
    
    // 清理热缓存
    this.hotCache = []
    
    // 定期将温数据归档到冷存储
    if (this.warmCache.size > 10) {
      const oldest = Array.from(this.warmCache.entries())[0]
      await this.coldStorage.insert(oldest[1])
      this.warmCache.delete(oldest[0])
    }
  }
}
```

### 避免信息污染

#### 问题1：无关信息混入

```typescript
class ContextFilter {
  // 过滤与当前任务无关的信息
  filterRelevant(context: Context, currentTask: Task): Context {
    return {
      ...context,
      files: context.files.filter(f => 
        this.isRelevantToTask(f, currentTask)
      ),
      memories: context.memories.filter(m => 
        this.calculateRelevance(m, currentTask) > 0.7
      )
    }
  }
  
  isRelevantToTask(file: File, task: Task): boolean {
    // 方法1：文件路径匹配
    if (task.affectedFiles?.includes(file.path)) {
      return true
    }
    
    // 方法2：语义相似度
    const similarity = this.semanticSimilarity(
      file.content, 
      task.description
    )
    if (similarity > 0.75) {
      return true
    }
    
    // 方法3：依赖关系
    if (task.currentFile && this.hasDependency(file, task.currentFile)) {
      return true
    }
    
    return false
  }
}
```

#### 问题2：过时信息残留

```typescript
class ContextFreshness {
  // 检查信息新鲜度
  isFresh(item: ContextItem): boolean {
    const age = Date.now() - item.timestamp
    const maxAge = this.getMaxAge(item.type)
    
    return age < maxAge
  }
  
  getMaxAge(type: string): number {
    const maxAges = {
      'file_content': 5 * 60 * 1000,      // 5分钟
      'api_response': 10 * 60 * 1000,     // 10分钟
      'user_preference': 7 * 24 * 60 * 60 * 1000,  // 7天
      'project_config': 24 * 60 * 60 * 1000       // 1天
    }
    
    return maxAges[type] || 60 * 60 * 1000  // 默认1小时
  }
  
  // 自动刷新过时信息
  async refreshStaleContext(context: Context): Promise<Context> {
    const refreshed = { ...context }
    
    // 刷新过时的文件内容
    refreshed.files = await Promise.all(
      context.files.map(async f => {
        if (!this.isFresh(f)) {
          return await this.readFile(f.path)  // 重新读取
        }
        return f
      })
    )
    
    return refreshed
  }
}
```

#### 问题3：冲突信息共存

```typescript
class ConflictResolver {
  // 检测并解决冲突信息
  async resolveConflicts(context: Context): Promise<Context> {
    // 例子：代码文件的不同版本
    const fileVersions = this.groupByPath(context.files)
    
    for (const [path, versions] of fileVersions.entries()) {
      if (versions.length > 1) {
        // 保留最新版本
        const latest = versions.reduce((a, b) => 
          a.timestamp > b.timestamp ? a : b
        )
        
        context.files = context.files.filter(f => 
          f.path !== path || f === latest
        )
      }
    }
    
    return context
  }
  
  // 检测语义冲突
  async detectSemanticConflicts(statements: string[]): Promise<Conflict[]> {
    const conflicts = []
    
    for (let i = 0; i < statements.length; i++) {
      for (let j = i + 1; j < statements.length; j++) {
        const isConflict = await this.checkConflict(
          statements[i], 
          statements[j]
        )
        
        if (isConflict) {
          conflicts.push({
            statement1: statements[i],
            statement2: statements[j],
            resolution: await this.resolveConflict(
              statements[i], 
              statements[j]
            )
          })
        }
      }
    }
    
    return conflicts
  }
  
  async checkConflict(s1: string, s2: string): Promise<boolean> {
    const prompt = `
    判断以下两个陈述是否冲突：
    陈述1: ${s1}
    陈述2: ${s2}
    
    如果冲突，回答"是"，否则回答"否"。
    `
    
    const response = await llm.generate(prompt, { maxTokens: 10 })
    return response.includes('是')
  }
}
```

### 上下文隔离

```typescript
class ContextIsolation {
  // 不同任务使用独立的上下文命名空间
  private contexts: Map<string, Context> = new Map()
  
  getContext(taskId: string): Context {
    if (!this.contexts.has(taskId)) {
      this.contexts.set(taskId, this.createCleanContext())
    }
    return this.contexts.get(taskId)!
  }
  
  // 防止任务间污染
  isolate(taskA: Task, taskB: Task): void {
    // 确保两个任务使用不同的上下文
    const contextA = this.getContext(taskA.id)
    const contextB = this.getContext(taskB.id)
    
    // 上下文不共享
    assert(contextA !== contextB)
  }
  
  // 清理完成任务的上下文
  cleanup(taskId: string): void {
    this.contexts.delete(taskId)
  }
}
```

### 最佳实践总结

**上下文构建：**
```
1. ✅ 分层构建（系统→项目→对话→任务）
2. ✅ 按需加载（只加载相关信息）
3. ✅ Token预算（严格控制总量）
4. ✅ 优先级排序（重要信息优先）
```

**避免过长：**
```
1. ✅ 滚动窗口（保留最近N条）
2. ✅ 智能摘要（压缩历史对话）
3. ✅ 分层缓存（热温冷数据分离）
4. ✅ 动态裁剪（超限时删除低优先级）
```

**避免污染：**
```
1. ✅ 相关性过滤（只保留相关信息）
2. ✅ 新鲜度检查（刷新过时信息）
3. ✅ 冲突检测（解决矛盾信息）
4. ✅ 上下文隔离（任务间独立）
```

## 6. 如果上下文窗口不够，优先保留哪些信息？为什么？

**答案：**

### 信息优先级矩阵

| 优先级 | 信息类型 | 保留率 | 理由 |
|--------|---------|--------|------|
| **P0** | 系统Prompt | 100% | 定义Agent行为，必须保留 |
| **P0** | 用户当前输入 | 100% | 任务起点，必须保留 |
| **P0** | 工具调用历史 | 100% | 决策依据，丢失会导致逻辑混乱 |
| **P1** | 最近3-5轮对话 | 90% | 保持上下文连贯性 |
| **P1** | 当前编辑的文件 | 90% | 操作对象，几乎必须保留 |
| **P2** | 相关代码文件 | 70% | 重要但可截断 |
| **P2** | 项目配置信息 | 60% | 可以缓存或重新加载 |
| **P3** | 历史记忆 | 40% | 有帮助但非必需 |
| **P3** | 文档和注释 | 30% | 可以按需检索 |
| **P4** | 示例代码 | 20% | 最先牺牲 |

### 优先级决策算法

```typescript
class PriorityBasedContextManager {
  private tokenBudget = 32000
  
  async buildContext(request: ContextRequest): Promise<Context> {
    const candidates: ContextItem[] = []
    
    // 收集所有候选信息
    candidates.push(...await this.collectP0Items(request))
    candidates.push(...await this.collectP1Items(request))
    candidates.push(...await this.collectP2Items(request))
    candidates.push(...await this.collectP3Items(request))
    candidates.push(...await this.collectP4Items(request))
    
    // 按优先级和相关性排序
    const scored = candidates.map(item => ({
      item,
      score: this.calculateScore(item, request)
    }))
    
    scored.sort((a, b) => b.score - a.score)
    
    // 贪心选择，直到预算用完
    const selected: ContextItem[] = []
    let usedTokens = 0
    
    for (const { item } of scored) {
      const itemTokens = this.countTokens(item)
      
      if (usedTokens + itemTokens <= this.tokenBudget) {
        selected.push(item)
        usedTokens += itemTokens
      } else if (item.priority === 'P0') {
        // P0级别信息必须保留，即使超预算也要强制加入
        // 这种情况下需要压缩其他内容
        await this.makSpaceFor(item, selected)
        selected.push(item)
      }
    }
    
    return this.assembleContext(selected)
  }
  
  calculateScore(item: ContextItem, request: ContextRequest): number {
    let score = 0
    
    // 因子1：优先级（最重要）
    const priorityScores = {
      'P0': 1000,
      'P1': 100,
      'P2': 10,
      'P3': 1,
      'P4': 0.1
    }
    score += priorityScores[item.priority]
    
    // 因子2：相关性
    const relevance = this.semanticSimilarity(item.content, request.query)
    score += relevance * 50
    
    // 因子3：新鲜度
    const age = Date.now() - item.timestamp
    const recency = Math.exp(-age / (24 * 60 * 60 * 1000))  // 24小时衰减
    score += recency * 20
    
    // 因子4：信息密度（信息量/token数）
    const density = this.calculateInformationDensity(item)
    score += density * 10
    
    // 因子5：是否被引用
    score += item.referenceCount * 5
    
    return score
  }
  
  async makeSpaceFor(item: ContextItem, selected: ContextItem[]): Promise<void> {
    const needed = this.countTokens(item)
    let freed = 0
    
    // 从低优先级开始删除
    for (let i = selected.length - 1; i >= 0 && freed < needed; i--) {
      if (selected[i].priority !== 'P0') {
        freed += this.countTokens(selected[i])
        selected.splice(i, 1)
      }
    }
    
    // 如果还不够，压缩P1/P2信息
    if (freed < needed) {
      for (const item of selected) {
        if (item.priority === 'P1' || item.priority === 'P2') {
          const compressed = await this.compress(item)
          const savedTokens = this.countTokens(item) - this.countTokens(compressed)
          freed += savedTokens
          item.content = compressed.content
          
          if (freed >= needed) break
        }
      }
    }
  }
}
```

### 具体保留策略

#### P0: 必须保留（核心上下文）

```typescript
class P0ContextCollector {
  async collect(request: ContextRequest): Promise<ContextItem[]> {
    return [
      // 1. 系统Prompt
      {
        type: 'system_prompt',
        priority: 'P0',
        content: this.getSystemPrompt(),
        reason: '定义Agent角色和行为规则，缺失会导致行为异常'
      },
      
      // 2. 用户当前输入
      {
        type: 'user_input',
        priority: 'P0',
        content: request.userInput,
        reason: '当前任务的起点，必须完整保留'
      },
      
      // 3. 工具调用历史（本次会话）
      {
        type: 'tool_calls',
        priority: 'P0',
        content: request.session.toolCalls,
        reason: '记录已执行的操作，丢失会导致重复执行或逻辑错误'
      },
      
      // 4. 未完成的任务状态
      {
        type: 'pending_tasks',
        priority: 'P0',
        content: request.session.pendingTasks,
        reason: '跟踪进度，避免任务丢失'
      }
    ]
  }
}
```

#### P1: 高优先级（上下文连贯性）

```typescript
class P1ContextCollector {
  async collect(request: ContextRequest): Promise<ContextItem[]> {
    return [
      // 1. 最近的对话（3-5轮）
      {
        type: 'recent_messages',
        priority: 'P1',
        content: request.session.messages.slice(-5),
        reason: '保持对话连贯性，理解用户意图'
      },
      
      // 2. 当前操作的文件
      {
        type: 'current_file',
        priority: 'P1',
        content: await this.readFile(request.session.currentFile),
        reason: '正在编辑的文件，大概率需要引用'
      },
      
      // 3. 重要的用户偏好
      {
        type: 'user_preferences',
        priority: 'P1',
        content: request.session.user.preferences,
        reason: '影响输出质量（代码风格、语言等）'
      }
    ]
  }
}
```

#### P2: 中优先级（辅助信息）

```typescript
class P2ContextCollector {
  async collect(request: ContextRequest): Promise<ContextItem[]> {
    // 这一层可以根据token预算动态调整
    const items = []
    
    // 1. 相关代码文件（语义检索）
    const relatedFiles = await this.retrieveRelatedFiles(
      request.userInput,
      maxFiles: 5
    )
    items.push({
      type: 'related_files',
      priority: 'P2',
      content: relatedFiles,
      reason: '提供代码上下文，但可以截断或摘要'
    })
    
    // 2. 项目配置
    items.push({
      type: 'project_config',
      priority: 'P2',
      content: await this.getProjectConfig(),
      reason: '技术栈、依赖等信息，可以缓存'
    })
    
    // 3. API文档（按需）
    if (this.needsApiDocs(request.userInput)) {
      items.push({
        type: 'api_docs',
        priority: 'P2',
        content: await this.retrieveDocs(request.userInput),
        reason: '帮助理解API使用，但非必需'
      })
    }
    
    return items
  }
}
```

### 动态调整策略

```typescript
class AdaptiveContextManager {
  async adjustPriorities(context: Context, feedback: Feedback): Promise<void> {
    // 根据反馈动态调整优先级
    
    if (feedback.type === 'missing_context') {
      // 如果Agent反馈缺少上下文，提升相关信息优先级
      const missingType = feedback.missingType
      this.promotePriority(missingType, 'P1')
    }
    
    if (feedback.type === 'irrelevant_context') {
      // 如果包含无关信息，降低优先级
      const irrelevantItems = feedback.irrelevantItems
      irrelevantItems.forEach(item => {
        this.demotePriority(item, 'P3')
      })
    }
    
    // 学习用户的使用模式
    await this.learnFromUsage(context, feedback)
  }
  
  async learnFromUsage(context: Context, feedback: Feedback): Promise<void> {
    // 记录哪些上下文实际被使用了
    const usedItems = feedback.usedContextItems
    
    for (const item of context.items) {
      if (usedItems.includes(item.id)) {
        item.usageCount++
      }
    }
    
    // 使用频率高的信息提升优先级
    const highUsageItems = context.items.filter(i => i.usageCount > 10)
    highUsageItems.forEach(item => {
      if (item.priority === 'P2') {
        item.priority = 'P1'
      }
    })
  }
}
```

### 实战案例

```typescript
// 场景：上下文窗口只剩8K tokens，但有20K tokens的候选信息

const candidates = {
  systemPrompt: 2000,        // P0
  userInput: 500,            // P0
  toolCalls: 1500,           // P0
  recentMessages: 3000,      // P1
  currentFile: 4000,         // P1
  relatedFiles: 8000,        // P2
  projectConfig: 1000,       // P2
  apiDocs: 3000,             // P2
  examples: 2000             // P4
}

// 决策过程：
// 1. P0必选：2000 + 500 + 1500 = 4000 tokens
// 2. 剩余：8000 - 4000 = 4000 tokens
// 3. P1选择：recentMessages(3000) → 剩余1000
// 4. P1选择：currentFile(4000) → 超限，压缩到1000
// 5. 最终上下文：P0全部 + recentMessages + currentFile(压缩版)

const finalContext = {
  systemPrompt: full,              // 2000
  userInput: full,                 // 500
  toolCalls: full,                 // 1500
  recentMessages: full,            // 3000
  currentFile: compressed,         // 1000（压缩后）
  // 其他全部舍弃
}
```

### 总结

**保留原则：**
```
1. 行为定义 > 数据内容
2. 最近信息 > 历史信息
3. 操作对象 > 参考资料
4. 已执行动作 > 计划动作
5. 结构化信息 > 自然语言描述
```

**压缩而非删除：**
```
当必须保留的信息超出预算时：
- P0: 绝不删除，如果太大则是设计问题
- P1: 压缩（摘要/截断）
- P2: 大幅压缩或删除
- P3/P4: 直接删除
```


## 7. 做代码理解的时候，AST、调用关系这些信息是怎么用起来的？

**答案：**

### AST（抽象语法树）在代码理解中的应用

AST是代码的结构化表示，对于Agent理解代码至关重要。

#### 1. AST基础

```typescript
// 原始代码
function add(a: number, b: number): number {
  return a + b;
}

// AST表示（简化）
{
  type: "FunctionDeclaration",
  name: "add",
  parameters: [
    { name: "a", type: "number" },
    { name: "b", type: "number" }
  ],
  returnType: "number",
  body: {
    type: "ReturnStatement",
    expression: {
      type: "BinaryExpression",
      operator: "+",
      left: { type: "Identifier", name: "a" },
      right: { type: "Identifier", name: "b" }
    }
  }
}
```

#### 2. AST实战应用

**应用1：函数签名提取**
```typescript
import * as ts from 'typescript';

class ASTAnalyzer {
  extractFunctionSignatures(sourceCode: string): FunctionSignature[] {
    const sourceFile = ts.createSourceFile(
      'temp.ts',
      sourceCode,
      ts.ScriptTarget.Latest,
      true
    );
    
    const signatures: FunctionSignature[] = [];
    
    const visit = (node: ts.Node) => {
      if (ts.isFunctionDeclaration(node)) {
        signatures.push({
          name: node.name?.text || 'anonymous',
          parameters: node.parameters.map(p => ({
            name: p.name.getText(),
            type: p.type?.getText() || 'any'
          })),
          returnType: node.type?.getText() || 'void',
          location: {
            line: sourceFile.getLineAndCharacterOfPosition(node.pos).line,
            file: 'temp.ts'
          }
        });
      }
      
      ts.forEachChild(node, visit);
    };
    
    visit(sourceFile);
    return signatures;
  }
}

// 使用场景：生成函数文档、理解API接口
const analyzer = new ASTAnalyzer();
const signatures = analyzer.extractFunctionSignatures(code);

// 注入到Agent上下文
const prompt = `
当前文件的函数签名：
${signatures.map(s => `- ${s.name}(${s.parameters.map(p => `${p.name}: ${p.type}`).join(', ')}): ${s.returnType}`).join('\n')}

用户请求：${userRequest}
`;
```

**应用2：变量依赖分析**
```typescript
class DependencyAnalyzer {
  analyzeDependencies(functionNode: ts.FunctionDeclaration): VariableDependency {
    const dependencies = {
      parameters: [],
      localVariables: [],
      externalReferences: [],
      functionCalls: []
    };
    
    const visit = (node: ts.Node) => {
      // 识别函数调用
      if (ts.isCallExpression(node)) {
        const funcName = node.expression.getText();
        dependencies.functionCalls.push({
          name: funcName,
          arguments: node.arguments.map(arg => arg.getText())
        });
      }
      
      // 识别变量声明
      if (ts.isVariableDeclaration(node)) {
        dependencies.localVariables.push({
          name: node.name.getText(),
          type: node.type?.getText(),
          initializer: node.initializer?.getText()
        });
      }
      
      // 识别外部引用
      if (ts.isIdentifier(node)) {
        const name = node.text;
        if (!this.isLocalVariable(name, dependencies)) {
          dependencies.externalReferences.push(name);
        }
      }
      
      ts.forEachChild(node, visit);
    };
    
    visit(functionNode);
    return dependencies;
  }
  
  // 使用场景：生成单元测试时识别需要Mock的依赖
  async generateTestWithDependencies(functionName: string): Promise<string> {
    const func = this.findFunction(functionName);
    const deps = this.analyzeDependencies(func);
    
    const prompt = `
    为函数 ${functionName} 生成单元测试。
    
    依赖信息：
    - 参数：${deps.parameters.join(', ')}
    - 调用的函数：${deps.functionCalls.map(c => c.name).join(', ')}
    - 外部引用：${deps.externalReferences.join(', ')}
    
    请为所有外部依赖创建Mock。
    `;
    
    return await llm.generate(prompt);
  }
}
```

**应用3：代码复杂度计算**
```typescript
class ComplexityAnalyzer {
  calculateCyclomaticComplexity(node: ts.FunctionDeclaration): number {
    let complexity = 1; // 基础复杂度
    
    const visit = (node: ts.Node) => {
      // 条件语句增加复杂度
      if (ts.isIfStatement(node)) complexity++;
      if (ts.isConditionalExpression(node)) complexity++;
      
      // 循环语句增加复杂度
      if (ts.isForStatement(node)) complexity++;
      if (ts.isWhileStatement(node)) complexity++;
      if (ts.isDoStatement(node)) complexity++;
      
      // 逻辑运算符增加复杂度
      if (ts.isBinaryExpression(node)) {
        if (node.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken ||
            node.operatorToken.kind === ts.SyntaxKind.BarBarToken) {
          complexity++;
        }
      }
      
      // case语句增加复杂度
      if (ts.isCaseClause(node)) complexity++;
      
      ts.forEachChild(node, visit);
    };
    
    visit(node);
    return complexity;
  }
  
  // 使用场景：判断是否需要重构
  async suggestRefactoring(code: string): Promise<string> {
    const functions = this.extractFunctions(code);
    const complexFunctions = functions.filter(f => 
      this.calculateCyclomaticComplexity(f) > 10
    );
    
    if (complexFunctions.length > 0) {
      const prompt = `
      以下函数复杂度过高，需要重构：
      ${complexFunctions.map(f => `- ${f.name}: 复杂度${this.calculateCyclomaticComplexity(f)}`).join('\n')}
      
      请提供重构建议。
      `;
      
      return await llm.generate(prompt);
    }
    
    return "代码复杂度合理，无需重构。";
  }
}
```

### 调用关系图（Call Graph）

#### 1. 构建调用关系图

```typescript
class CallGraphBuilder {
  buildCallGraph(project: ts.Program): CallGraph {
    const graph = new Map<string, string[]>(); // 函数名 -> 调用的函数列表
    
    const sourceFiles = project.getSourceFiles();
    
    for (const sourceFile of sourceFiles) {
      if (sourceFile.isDeclarationFile) continue;
      
      const visit = (node: ts.Node, currentFunction?: string) => {
        // 记录函数定义
        if (ts.isFunctionDeclaration(node)) {
          const funcName = node.name?.text;
          if (funcName) {
            if (!graph.has(funcName)) {
              graph.set(funcName, []);
            }
            currentFunction = funcName;
          }
        }
        
        // 记录函数调用
        if (ts.isCallExpression(node) && currentFunction) {
          const calledFunc = node.expression.getText();
          graph.get(currentFunction)!.push(calledFunc);
        }
        
        ts.forEachChild(node, child => visit(child, currentFunction));
      };
      
      visit(sourceFile);
    }
    
    return graph;
  }
  
  // 使用场景：影响分析
  analyzeImpact(funcName: string, graph: CallGraph): ImpactAnalysis {
    // 找出所有调用该函数的地方
    const callers = [];
    for (const [caller, callees] of graph.entries()) {
      if (callees.includes(funcName)) {
        callers.push(caller);
      }
    }
    
    // 找出该函数调用的所有函数
    const callees = graph.get(funcName) || [];
    
    return {
      directCallers: callers,
      directCallees: callees,
      impactScope: this.calculateImpactScope(funcName, graph)
    };
  }
  
  // 递归计算影响范围
  calculateImpactScope(funcName: string, graph: CallGraph): string[] {
    const visited = new Set<string>();
    const stack = [funcName];
    
    while (stack.length > 0) {
      const current = stack.pop()!;
      if (visited.has(current)) continue;
      visited.add(current);
      
      // 找出所有调用者
      for (const [caller, callees] of graph.entries()) {
        if (callees.includes(current) && !visited.has(caller)) {
          stack.push(caller);
        }
      }
    }
    
    return Array.from(visited);
  }
}
```

#### 2. 调用关系的实战应用

**应用1：生成修改建议**
```typescript
async function generateModificationAdvice(
  funcName: string,
  modification: string
): Promise<string> {
  const callGraph = buildCallGraph(project);
  const impact = analyzeImpact(funcName, callGraph);
  
  const prompt = `
  计划修改函数：${funcName}
  修改内容：${modification}
  
  影响分析：
  - 直接调用者：${impact.directCallers.join(', ')}
  - 总影响范围：${impact.impactScope.length}个函数
  
  请评估：
  1. 这个修改是否会破坏现有功能？
  2. 需要同步修改哪些调用者？
  3. 需要补充哪些测试用例？
  `;
  
  return await llm.generate(prompt);
}
```

**应用2：生成集成测试**
```typescript
async function generateIntegrationTest(entryFunc: string): Promise<string> {
  const callGraph = buildCallGraph(project);
  const callChain = getCallChain(entryFunc, callGraph);
  
  const prompt = `
  为入口函数 ${entryFunc} 生成集成测试。
  
  调用链：
  ${callChain.map((chain, i) => `${i + 1}. ${chain.join(' -> ')}`).join('\n')}
  
  请生成测试用例覆盖主要调用路径。
  `;
  
  return await llm.generate(prompt);
}
```

**应用3：死代码检测**
```typescript
class DeadCodeDetector {
  findDeadCode(entryPoints: string[], callGraph: CallGraph): string[] {
    // 从入口点开始，找出所有可达的函数
    const reachable = new Set<string>();
    const stack = [...entryPoints];
    
    while (stack.length > 0) {
      const current = stack.pop()!;
      if (reachable.has(current)) continue;
      reachable.add(current);
      
      const callees = callGraph.get(current) || [];
      stack.push(...callees);
    }
    
    // 所有函数 - 可达函数 = 死代码
    const allFunctions = Array.from(callGraph.keys());
    const deadCode = allFunctions.filter(f => !reachable.has(f));
    
    return deadCode;
  }
  
  async reportDeadCode(deadCode: string[]): Promise<string> {
    if (deadCode.length === 0) {
      return "没有发现死代码。";
    }
    
    const prompt = `
    发现以下未使用的函数：
    ${deadCode.join('\n')}
    
    请确认：
    1. 这些函数是否可以安全删除？
    2. 是否有特殊用途（如导出给外部使用）？
    `;
    
    return await llm.generate(prompt);
  }
}
```

### 结合AST和调用关系的高级应用

#### 应用1：智能代码补全

```typescript
class IntelligentCodeCompletion {
  async suggest(
    cursorPosition: Position,
    sourceCode: string
  ): Promise<Suggestion[]> {
    // 1. 解析当前位置的AST节点
    const currentNode = this.getNodeAtPosition(sourceCode, cursorPosition);
    
    // 2. 分析上下文
    const context = this.analyzeContext(currentNode);
    
    // 3. 获取可用的函数和变量
    const availableSymbols = this.getAvailableSymbols(currentNode);
    
    // 4. 基于调用关系推荐
    if (context.type === 'function_call') {
      const similarContexts = this.findSimilarContexts(context);
      const commonlyUsedFuncs = this.getCommonlyCalledFunctions(similarContexts);
      
      return commonlyUsedFuncs.map(f => ({
        text: f.name,
        type: 'function',
        confidence: f.frequency,
        documentation: f.doc
      }));
    }
    
    return [];
  }
  
  analyzeContext(node: ts.Node): Context {
    // 当前在函数内部？循环内部？条件语句内？
    const ancestors = this.getAncestors(node);
    
    return {
      type: this.determineContextType(node),
      scope: this.determineScope(ancestors),
      expectedType: this.inferExpectedType(node)
    };
  }
  
  findSimilarContexts(context: Context): Context[] {
    // 在代码库中查找类似的代码模式
    // 例如：都在处理用户数据的函数中
    return this.codebaseIndex.searchSimilarContexts(context);
  }
}
```

#### 应用2：自动重构

```typescript
class AutoRefactoring {
  async extractFunction(
    selection: CodeRange,
    sourceCode: string
  ): Promise<RefactoringResult> {
    // 1. 解析选中代码的AST
    const selectedNodes = this.parseSelection(selection, sourceCode);
    
    // 2. 分析依赖
    const dependencies = this.analyzeDependencies(selectedNodes);
    
    // 3. 生成新函数
    const newFunctionName = await this.suggestFunctionName(selectedNodes);
    const parameters = dependencies.externalReferences;
    const returnValue = dependencies.returnedValues;
    
    const newFunction = `
    function ${newFunctionName}(${parameters.join(', ')}) {
      ${this.formatCode(selectedNodes)}
      return ${returnValue};
    }
    `;
    
    // 4. 替换原代码
    const replacement = `const result = ${newFunctionName}(${parameters.join(', ')});`;
    
    // 5. 更新调用关系图
    this.updateCallGraph(newFunctionName, dependencies);
    
    return {
      newFunction,
      replacement,
      affectedFiles: this.findAffectedFiles(dependencies)
    };
  }
  
  async suggestFunctionName(nodes: ts.Node[]): Promise<string> {
    // 使用LLM基于代码语义生成函数名
    const codeSnippet = nodes.map(n => n.getText()).join('\n');
    
    const prompt = `
    分析以下代码片段，建议一个合适的函数名：
    
    ${codeSnippet}
    
    函数名应该：
    1. 清晰描述功能
    2. 遵循驼峰命名法
    3. 动词开头
    
    只返回函数名，不要解释。
    `;
    
    return await llm.generate(prompt, { maxTokens: 20 });
  }
}
```

#### 应用3：Bug定位

```typescript
class BugLocator {
  async locateBug(
    errorMessage: string,
    stackTrace: string[]
  ): Promise<BugReport> {
    // 1. 从堆栈跟踪提取函数调用链
    const callChain = this.parseStackTrace(stackTrace);
    
    // 2. 在调用关系图中定位
    const suspiciousFunctions = [];
    
    for (const func of callChain) {
      // 分析该函数的AST
      const ast = this.getFunctionAST(func);
      
      // 检查常见bug模式
      const issues = this.detectIssuePatterns(ast);
      
      if (issues.length > 0) {
        suspiciousFunctions.push({
          function: func,
          issues: issues,
          confidence: this.calculateConfidence(issues, errorMessage)
        });
      }
    }
    
    // 3. 使用LLM分析
    const prompt = `
    错误信息：${errorMessage}
    
    调用链：${callChain.join(' -> ')}
    
    可疑函数：
    ${suspiciousFunctions.map(f => 
      `- ${f.function}: ${f.issues.join(', ')}`
    ).join('\n')}
    
    请分析最可能的bug原因和修复建议。
    `;
    
    const analysis = await llm.generate(prompt);
    
    return {
      suspiciousFunctions,
      analysis,
      suggestedFixes: this.generateFixes(suspiciousFunctions)
    };
  }
  
  detectIssuePatterns(ast: ts.Node): string[] {
    const issues = [];
    
    const visit = (node: ts.Node) => {
      // 检查空指针访问
      if (this.isNullableAccess(node)) {
        issues.push('可能的空指针访问');
      }
      
      // 检查数组越界
      if (this.isPotentialArrayOutOfBounds(node)) {
        issues.push('可能的数组越界');
      }
      
      // 检查类型不匹配
      if (this.isTypeMismatch(node)) {
        issues.push('类型不匹配');
      }
      
      ts.forEachChild(node, visit);
    };
    
    visit(ast);
    return issues;
  }
}
```

### 总结

**AST的价值：**
- ✅ 结构化理解代码（不是字符串匹配）
- ✅ 精确提取信息（函数签名、变量依赖）
- ✅ 检测代码模式（复杂度、坏味道）

**调用关系的价值：**
- ✅ 影响分析（修改影响范围）
- ✅ 死代码检测
- ✅ 测试用例生成（覆盖调用路径）

**结合使用的效果：**
- 🚀 智能代码补全
- 🚀 自动重构
- 🚀 精准Bug定位
- 🚀 代码质量分析


## 8. 单测生成时，哪些代码不适合生成单测？怎么识别并过滤？

**答案：**

### 不适合生成单测的代码类型

#### 1. 简单的Getter/Setter

```typescript
// ❌ 不值得测试
class User {
  private name: string;
  
  getName(): string {
    return this.name;
  }
  
  setName(name: string): void {
    this.name = name;
  }
}

// 原因：
// - 无业务逻辑
// - 测试成本 > 测试价值
// - 如果出错，其他测试会发现
```

#### 2. 纯UI渲染组件

```typescript
// ❌ 不适合单测（适合E2E测试）
function ProfileCard({ user }: Props) {
  return (
    <div className="profile-card">
      <img src={user.avatar} />
      <h2>{user.name}</h2>
      <p>{user.bio}</p>
    </div>
  );
}

// 原因：
// - 无逻辑，只有布局
// - 视觉效果难以单测验证
// - 应该用快照测试或E2E
```

#### 3. 纯配置/常量

```typescript
// ❌ 不需要测试
export const API_ENDPOINTS = {
  users: '/api/users',
  posts: '/api/posts'
};

export const MAX_FILE_SIZE = 10 * 1024 * 1024;
```

#### 4. 第三方库的简单封装

```typescript
// ❌ 不值得测试
export function formatDate(date: Date): string {
  return dayjs(date).format('YYYY-MM-DD');
}

// 原因：
// - dayjs已经测试过
// - 无自定义逻辑
// - 信任第三方库
```

#### 5. 纯粹的类型定义

```typescript
// ❌ TypeScript编译器已验证
interface User {
  id: string;
  name: string;
  email: string;
}

type UserRole = 'admin' | 'user' | 'guest';
```

### 识别和过滤策略

#### 策略1：复杂度评分

```typescript
class TestWorthinessAnalyzer {
  shouldGenerateTest(functionNode: ts.FunctionDeclaration): boolean {
    let score = 0;
    
    // 因子1：圈复杂度
    const complexity = this.calculateComplexity(functionNode);
    if (complexity <= 1) score -= 5;  // 太简单
    else if (complexity <= 5) score += 3;  // 适中
    else score += 5;  // 复杂，值得测试
    
    // 因子2：代码行数
    const lines = this.countLines(functionNode);
    if (lines <= 3) score -= 3;  // 太短
    else if (lines <= 20) score += 2;
    else score += 4;
    
    // 因子3：是否有业务逻辑
    const hasLogic = this.hasBusinessLogic(functionNode);
    if (hasLogic) score += 10;
    else score -= 5;
    
    // 因子4：是否有外部依赖
    const hasDependencies = this.hasExternalDependencies(functionNode);
    if (hasDependencies) score += 3;
    
    // 因子5：是否是纯函数
    const isPure = this.isPureFunction(functionNode);
    if (isPure) score += 2;  // 纯函数容易测试
    
    // 因子6：是否是公开API
    const isPublic = this.isPublicAPI(functionNode);
    if (isPublic) score += 5;
    
    // 因子7：是否是Getter/Setter
    const isAccessor = this.isGetterOrSetter(functionNode);
    if (isAccessor) score -= 10;
    
    // 决策阈值
    return score >= 5;
  }
  
  hasBusinessLogic(node: ts.FunctionDeclaration): boolean {
    let hasLogic = false;
    
    const visit = (n: ts.Node) => {
      // 包含条件判断
      if (ts.isIfStatement(n) || ts.isConditionalExpression(n)) {
        hasLogic = true;
      }
      
      // 包含循环
      if (ts.isForStatement(n) || ts.isWhileStatement(n)) {
        hasLogic = true;
      }
      
      // 包含复杂运算
      if (ts.isBinaryExpression(n)) {
        const operator = n.operatorToken.kind;
        if (operator !== ts.SyntaxKind.PlusToken && 
            operator !== ts.SyntaxKind.MinusToken) {
          hasLogic = true;
        }
      }
      
      // 包含函数调用（排除简单赋值）
      if (ts.isCallExpression(n)) {
        const callName = n.expression.getText();
        if (!['console.log', 'this.setState'].includes(callName)) {
          hasLogic = true;
        }
      }
      
      ts.forEachChild(n, visit);
    };
    
    visit(node);
    return hasLogic;
  }
  
  isGetterOrSetter(node: ts.FunctionDeclaration): boolean {
    const name = node.name?.text || '';
    
    // 检查命名模式
    if (name.startsWith('get') || name.startsWith('set')) {
      // 检查函数体
      const statements = node.body?.statements || [];
      
      // Getter: 只有一个return语句
      if (name.startsWith('get') && statements.length === 1) {
        const stmt = statements[0];
        if (ts.isReturnStatement(stmt)) {
          return true;
        }
      }
      
      // Setter: 只有一个赋值语句
      if (name.startsWith('set') && statements.length === 1) {
        const stmt = statements[0];
        if (ts.isExpressionStatement(stmt)) {
          return true;
        }
      }
    }
    
    return false;
  }
  
  isPureFunction(node: ts.FunctionDeclaration): boolean {
    let isPure = true;
    
    const visit = (n: ts.Node) => {
      // 有副作用的操作
      if (ts.isCallExpression(n)) {
        const callName = n.expression.getText();
        // 检查是否调用有副作用的函数
        if (this.hasSideEffects(callName)) {
          isPure = false;
        }
      }
      
      // 修改外部状态
      if (ts.isBinaryExpression(n) && 
          n.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
        const left = n.left.getText();
        if (left.startsWith('this.') || left.startsWith('global.')) {
          isPure = false;
        }
      }
      
      ts.forEachChild(n, visit);
    };
    
    visit(node);
    return isPure;
  }
}
```

#### 策略2：模式匹配

```typescript
class TestFilterPatterns {
  private skipPatterns = [
    // 1. 简单返回
    {
      name: 'simple-return',
      detect: (node: ts.Node) => {
        if (!ts.isFunctionDeclaration(node)) return false;
        const statements = node.body?.statements || [];
        return statements.length === 1 && 
               ts.isReturnStatement(statements[0]);
      }
    },
    
    // 2. 纯赋值
    {
      name: 'pure-assignment',
      detect: (node: ts.Node) => {
        if (!ts.isFunctionDeclaration(node)) return false;
        const statements = node.body?.statements || [];
        return statements.length === 1 && 
               ts.isExpressionStatement(statements[0]) &&
               this.isSimpleAssignment(statements[0]);
      }
    },
    
    // 3. 仅调用父类方法
    {
      name: 'super-call-only',
      detect: (node: ts.Node) => {
        const body = this.getFunctionBody(node);
        return body?.includes('super.') && 
               body.split('\n').length <= 3;
      }
    },
    
    // 4. 仅返回常量
    {
      name: 'constant-return',
      detect: (node: ts.Node) => {
        if (!ts.isFunctionDeclaration(node)) return false;
        const statements = node.body?.statements || [];
        if (statements.length !== 1) return false;
        
        const returnStmt = statements[0];
        if (!ts.isReturnStatement(returnStmt)) return false;
        
        const expr = returnStmt.expression;
        return expr && (
          ts.isStringLiteral(expr) ||
          ts.isNumericLiteral(expr) ||
          ts.isTrueLiteral(expr) ||
          ts.isFalseLiteral(expr)
        );
      }
    }
  ];
  
  shouldSkip(node: ts.FunctionDeclaration): { skip: boolean, reason: string } {
    for (const pattern of this.skipPatterns) {
      if (pattern.detect(node)) {
        return {
          skip: true,
          reason: `匹配模式: ${pattern.name}`
        };
      }
    }
    
    return { skip: false, reason: '' };
  }
}
```

#### 策略3：结合LLM判断

```typescript
class LLMBasedFilter {
  async shouldGenerateTest(
    functionCode: string,
    context: string
  ): Promise<{ should: boolean, reason: string }> {
    const prompt = `
    判断以下函数是否值得生成单元测试：
    
    函数代码：
    \`\`\`typescript
    ${functionCode}
    \`\`\`
    
    上下文：${context}
    
    评判标准：
    1. 是否包含业务逻辑？
    2. 复杂度是否足够？
    3. 是否容易出错？
    4. 测试成本是否合理？
    
    回答格式：
    {
      "should": true/false,
      "reason": "原因说明",
      "confidence": 0-1
    }
    `;
    
    const response = await llm.generate(prompt, {
      response_format: 'json'
    });
    
    return JSON.parse(response);
  }
}
```

#### 策略4：基于代码覆盖率

```typescript
class CoverageBasedFilter {
  async filterByExistingCoverage(
    functions: ts.FunctionDeclaration[],
    coverageReport: CoverageReport
  ): Promise<ts.FunctionDeclaration[]> {
    return functions.filter(func => {
      const funcName = func.name?.text;
      if (!funcName) return false;
      
      const coverage = coverageReport.functions[funcName];
      
      // 如果已有测试且覆盖率高，跳过
      if (coverage && coverage.coverage > 0.8) {
        return false;
      }
      
      // 如果未覆盖且复杂度高，优先生成
      if (!coverage && this.isComplex(func)) {
        return true;
      }
      
      // 如果覆盖率低但很重要，生成测试
      if (coverage && coverage.coverage < 0.5 && this.isCritical(func)) {
        return true;
      }
      
      return true;
    });
  }
  
  isCritical(func: ts.FunctionDeclaration): boolean {
    const name = func.name?.text || '';
    
    // 关键函数名模式
    const criticalPatterns = [
      /^validate/,
      /^auth/,
      /^encrypt/,
      /^decrypt/,
      /^calculate/,
      /^process/,
      /Payment$/,
      /Security$/
    ];
    
    return criticalPatterns.some(pattern => pattern.test(name));
  }
}
```

### 实战示例

```typescript
class SmartTestGenerator {
  async generateTests(sourceCode: string): Promise<GeneratedTest[]> {
    // 1. 解析代码
    const functions = this.extractFunctions(sourceCode);
    
    // 2. 过滤不值得测试的函数
    const worthyFunctions = [];
    
    for (const func of functions) {
      // 检查1：复杂度评分
      const worthinessScore = this.analyzer.shouldGenerateTest(func);
      if (!worthinessScore) {
        console.log(`跳过 ${func.name?.text}: 复杂度过低`);
        continue;
      }
      
      // 检查2：模式匹配
      const patternCheck = this.filter.shouldSkip(func);
      if (patternCheck.skip) {
        console.log(`跳过 ${func.name?.text}: ${patternCheck.reason}`);
        continue;
      }
      
      // 检查3：现有覆盖率
      const coverage = await this.getCoverage(func);
      if (coverage > 0.8) {
        console.log(`跳过 ${func.name?.text}: 已有充分测试`);
        continue;
      }
      
      // 检查4：LLM最终判断（可选，用于边界情况）
      if (this.useAIFilter) {
        const aiDecision = await this.llmFilter.shouldGenerateTest(
          func.getText(),
          this.getContext(func)
        );
        
        if (!aiDecision.should) {
          console.log(`跳过 ${func.name?.text}: AI判断 - ${aiDecision.reason}`);
          continue;
        }
      }
      
      worthyFunctions.push(func);
    }
    
    // 3. 为筛选后的函数生成测试
    const tests = [];
    for (const func of worthyFunctions) {
      console.log(`✓ 生成测试: ${func.name?.text}`);
      const test = await this.generateTest(func);
      tests.push(test);
    }
    
    return tests;
  }
}
```

### 白名单和黑名单

```typescript
class TestGenerationConfig {
  // 黑名单：永远不生成测试
  private blacklist = {
    functionNames: [
      /^get[A-Z]/,  // getXxx
      /^set[A-Z]/,  // setXxx
      /^_private/,  // 私有函数（某些情况）
    ],
    
    filePatterns: [
      /\.config\.ts$/,
      /\.constants\.ts$/,
      /\.types\.ts$/,
      /\.d\.ts$/
    ],
    
    functionTypes: [
      'constructor',
      'getter',
      'setter',
      'simple-return'
    ]
  };
  
  // 白名单：强制生成测试
  private whitelist = {
    functionNames: [
      /^validate/,
      /^auth/,
      /^encrypt/,
      /^calculate/,
      /Payment$/,
      /Security$/
    ],
    
    annotations: [
      '@critical',
      '@security',
      '@testRequired'
    ]
  };
  
  shouldGenerateTest(func: ts.FunctionDeclaration): boolean {
    // 1. 检查白名单（最高优先级）
    if (this.isInWhitelist(func)) {
      return true;
    }
    
    // 2. 检查黑名单
    if (this.isInBlacklist(func)) {
      return false;
    }
    
    // 3. 使用其他策略判断
    return this.defaultStrategy(func);
  }
}
```

### 总结

**不适合生成单测的代码：**
1. ❌ 简单Getter/Setter
2. ❌ 纯UI组件
3. ❌ 常量和配置
4. ❌ 第三方库简单封装
5. ❌ 纯类型定义

**识别策略：**
1. ✅ 复杂度评分（圈复杂度、代码行数）
2. ✅ 模式匹配（识别常见模式）
3. ✅ LLM判断（边界情况）
4. ✅ 覆盖率分析（避免重复）
5. ✅ 白名单/黑名单（关键函数）

**最佳实践：**
```
优先级排序：
P0: 关键业务逻辑（支付、认证、加密）
P1: 复杂算法（复杂度 > 5）
P2: 公开API
P3: 一般业务逻辑
跳过: 简单函数、配置、UI组件
```


## 9. 覆盖率高但测试质量很差的情况怎么解决？

**答案：**

### 问题分析

**覆盖率高≠测试质量好**

```typescript
// 示例：100%覆盖率但测试质量差
function divide(a: number, b: number): number {
  if (b === 0) {
    throw new Error('Division by zero');
  }
  return a / b;
}

// ❌ 差测试：覆盖率100%但没测试边界情况
test('divide function', () => {
  const result = divide(10, 2);
  expect(result).toBe(5);
  
  try {
    divide(10, 0);
  } catch (e) {
    // 捕获了异常，覆盖率达到100%
  }
});

// ✅ 好测试：真正验证行为
describe('divide function', () => {
  it('should divide two positive numbers', () => {
    expect(divide(10, 2)).toBe(5);
  });
  
  it('should handle negative numbers', () => {
    expect(divide(-10, 2)).toBe(-5);
  });
  
  it('should throw error for division by zero', () => {
    expect(() => divide(10, 0)).toThrow('Division by zero');
  });
  
  it('should handle decimal numbers', () => {
    expect(divide(10, 3)).toBeCloseTo(3.33, 2);
  });
});
```

### 测试质量问题类型

#### 1. 空断言测试

```typescript
// ❌ 问题：只执行代码，不验证结果
test('process user data', () => {
  processUserData({ name: 'Alice', age: 30 });
  // 没有任何断言！
});

// ✅ 解决：添加有意义的断言
test('process user data', () => {
  const result = processUserData({ name: 'Alice', age: 30 });
  
  expect(result.processed).toBe(true);
  expect(result.data.name).toBe('Alice');
  expect(result.data.age).toBe(30);
});
```

#### 2. 断言永远成功

```typescript
// ❌ 问题：断言逻辑错误
test('validate email', () => {
  const isValid = validateEmail('invalid-email');
  expect(isValid || !isValid).toBe(true); // 永远为true！
});

// ✅ 解决：正确的断言
test('validate email', () => {
  expect(validateEmail('test@example.com')).toBe(true);
  expect(validateEmail('invalid-email')).toBe(false);
});
```

#### 3. 过度Mock

```typescript
// ❌ 问题：Mock了所有依赖，实际没测试任何逻辑
test('calculate total price', () => {
  const mockGetPrice = jest.fn().mockReturnValue(100);
  const mockGetDiscount = jest.fn().mockReturnValue(0.1);
  const mockCalculate = jest.fn().mockReturnValue(90);
  
  const result = calculateTotalPrice(mockGetPrice, mockGetDiscount, mockCalculate);
  expect(result).toBe(90); // 只是返回了mock的值
});

// ✅ 解决：只Mock外部依赖
test('calculate total price', () => {
  // 只mock外部API
  const mockGetPrice = jest.fn().mockReturnValue(100);
  
  // 真实测试计算逻辑
  const result = calculateTotalPrice(mockGetPrice);
  expect(result).toBe(90); // 真正验证了10%折扣计算
});
```

#### 4. 测试实现而非行为

```typescript
// ❌ 问题：测试内部实现细节
test('sort users', () => {
  const users = [{ name: 'Bob' }, { name: 'Alice' }];
  const sorted = sortUsers(users);
  
  // 测试使用了哪种排序算法
  expect(sorted.algorithm).toBe('quicksort');
});

// ✅ 解决：测试外部行为
test('sort users', () => {
  const users = [{ name: 'Bob' }, { name: 'Alice' }];
  const sorted = sortUsers(users);
  
  // 只关心结果是否正确
  expect(sorted[0].name).toBe('Alice');
  expect(sorted[1].name).toBe('Bob');
});
```

### 解决方案

#### 方案1：变异测试（Mutation Testing）

```typescript
// 使用Stryker等工具进行变异测试
// 配置文件：stryker.config.js
module.exports = {
  mutator: 'typescript',
  testRunner: 'jest',
  mutate: ['src/**/*.ts', '!src/**/*.spec.ts'],
  thresholds: { high: 80, low: 60, break: 50 }
};

// 运行变异测试
// npx stryker run

// 变异测试会修改源代码（如 + 改为 -）
// 如果测试仍然通过，说明测试质量差

// 示例：
function calculateDiscount(price: number, rate: number): number {
  return price * rate; // 变异：改为 price - rate
}

// 如果这个变异没被测试发现，说明测试不够
```

#### 方案2：断言质量检查

```typescript
class AssertionQualityChecker {
  checkTestQuality(testCode: string): QualityReport {
    const ast = parse(testCode);
    const issues: Issue[] = [];
    
    // 检查1：是否有断言
    const assertions = this.findAssertions(ast);
    if (assertions.length === 0) {
      issues.push({
        type: 'no-assertions',
        severity: 'high',
        message: '测试中没有任何断言'
      });
    }
    
    // 检查2：断言是否有意义
    for (const assertion of assertions) {
      if (this.isTrivialAssertion(assertion)) {
        issues.push({
          type: 'trivial-assertion',
          severity: 'medium',
          message: `无意义的断言: ${assertion.code}`,
          line: assertion.line
        });
      }
    }
    
    // 检查3：是否过度Mock
    const mocks = this.findMocks(ast);
    const functions = this.findFunctionCalls(ast);
    const mockRatio = mocks.length / functions.length;
    
    if (mockRatio > 0.8) {
      issues.push({
        type: 'excessive-mocking',
        severity: 'medium',
        message: `Mock比例过高(${Math.round(mockRatio * 100)}%)，可能没有测试真实逻辑`
      });
    }
    
    // 检查4：是否测试边界情况
    const hasEdgeCases = this.hasEdgeCaseTests(ast);
    if (!hasEdgeCases) {
      issues.push({
        type: 'missing-edge-cases',
        severity: 'low',
        message: '缺少边界情况测试'
      });
    }
    
    return {
      score: this.calculateScore(issues),
      issues,
      recommendations: this.generateRecommendations(issues)
    };
  }
  
  isTrivialAssertion(assertion: Assertion): boolean {
    const trivialPatterns = [
      /expect\(.*\)\.toBeTruthy\(\)/,  // expect(true).toBeTruthy()
      /expect\(.*\)\.toBeDefined\(\)/,  // expect(x).toBeDefined() 但x肯定存在
      /expect\(true\)\.toBe\(true\)/,   // 字面量比较
      /expect\(.*\|\|.*\)\.toBe\(true\)/, // 永远为true的表达式
    ];
    
    return trivialPatterns.some(p => p.test(assertion.code));
  }
}
```

#### 方案3：测试用例生成优化

```typescript
class QualityAwareTestGenerator {
  async generateQualityTests(
    functionCode: string
  ): Promise<string> {
    // 1. 分析函数
    const analysis = await this.analyzeFunction(functionCode);
    
    // 2. 识别测试维度
    const testDimensions = [
      // 正常情况
      {
        name: 'happy-path',
        cases: this.generateHappyPathCases(analysis)
      },
      
      // 边界情况
      {
        name: 'edge-cases',
        cases: this.generateEdgeCases(analysis)
      },
      
      // 异常情况
      {
        name: 'error-cases',
        cases: this.generateErrorCases(analysis)
      },
      
      // 性能测试
      {
        name: 'performance',
        cases: this.generatePerformanceCases(analysis)
      }
    ];
    
    // 3. 为每个维度生成测试
    const testCode = this.assembleTests(testDimensions);
    
    // 4. 质量检查
    const quality = await this.checkQuality(testCode);
    
    // 5. 如果质量不够，迭代改进
    if (quality.score < 0.8) {
      return await this.improveTests(testCode, quality.issues);
    }
    
    return testCode;
  }
  
  generateEdgeCases(analysis: FunctionAnalysis): TestCase[] {
    const cases: TestCase[] = [];
    
    for (const param of analysis.parameters) {
      // 数字类型边界
      if (param.type === 'number') {
        cases.push(
          { name: `${param.name} is zero`, value: 0 },
          { name: `${param.name} is negative`, value: -1 },
          { name: `${param.name} is MAX_VALUE`, value: Number.MAX_VALUE },
          { name: `${param.name} is MIN_VALUE`, value: Number.MIN_VALUE }
        );
      }
      
      // 字符串类型边界
      if (param.type === 'string') {
        cases.push(
          { name: `${param.name} is empty`, value: '' },
          { name: `${param.name} is very long`, value: 'x'.repeat(10000) },
          { name: `${param.name} contains special chars`, value: '!@#$%' }
        );
      }
      
      // 数组类型边界
      if (param.type.includes('[]')) {
        cases.push(
          { name: `${param.name} is empty array`, value: [] },
          { name: `${param.name} has one element`, value: [1] },
          { name: `${param.name} is large array`, value: Array(10000).fill(1) }
        );
      }
      
      // null/undefined
      if (param.optional) {
        cases.push(
          { name: `${param.name} is null`, value: null },
          { name: `${param.name} is undefined`, value: undefined }
        );
      }
    }
    
    return cases;
  }
}
```

#### 方案4：引入测试评审

```typescript
class TestReviewer {
  async reviewTest(testCode: string): Promise<ReviewReport> {
    const prompt = `
    请评审以下测试代码的质量：
    
    \`\`\`typescript
    ${testCode}
    \`\`\`
    
    评审维度：
    1. 断言完整性：是否验证了所有重要的输出？
    2. 边界情况：是否覆盖了边界值？
    3. 异常处理：是否测试了错误情况？
    4. 独立性：测试之间是否相互独立？
    5. 可读性：测试意图是否清晰？
    
    对每个维度打分(0-10)，并给出改进建议。
    
    输出格式：
    {
      "scores": {
        "completeness": 8,
        "edge_cases": 6,
        "error_handling": 7,
        "independence": 9,
        "readability": 8
      },
      "overall_score": 7.6,
      "issues": [
        { "type": "...", "description": "...", "suggestion": "..." }
      ],
      "improved_code": "..."
    }
    `;
    
    const response = await llm.generate(prompt, {
      response_format: 'json'
    });
    
    return JSON.parse(response);
  }
}
```

#### 方案5：集成质量度量

```typescript
class TestQualityMetrics {
  calculateQualityScore(
    coverageData: Coverage,
    testCode: string
  ): QualityScore {
    let score = 0;
    const weights = {
      coverage: 0.3,
      assertion: 0.2,
      edgeCases: 0.2,
      mutation: 0.2,
      maintainability: 0.1
    };
    
    // 指标1：代码覆盖率（30%）
    const coverageScore = coverageData.line / 100;
    score += coverageScore * weights.coverage;
    
    // 指标2：断言质量（20%）
    const assertions = this.analyzeAssertions(testCode);
    const assertionScore = assertions.meaningful / assertions.total;
    score += assertionScore * weights.assertion;
    
    // 指标3：边界情况覆盖（20%）
    const edgeCases = this.detectEdgeCases(testCode);
    const edgeScore = edgeCases.covered / edgeCases.total;
    score += edgeScore * weights.edgeCases;
    
    // 指标4：变异测试得分（20%）
    const mutationScore = this.getMutationScore();
    score += mutationScore * weights.mutation;
    
    // 指标5：可维护性（10%）
    const maintainability = this.assessMaintainability(testCode);
    score += maintainability * weights.maintainability;
    
    return {
      overall: score,
      breakdown: {
        coverage: coverageScore,
        assertion: assertionScore,
        edgeCases: edgeScore,
        mutation: mutationScore,
        maintainability
      },
      grade: this.getGrade(score)
    };
  }
  
  getGrade(score: number): string {
    if (score >= 0.9) return 'A';
    if (score >= 0.8) return 'B';
    if (score >= 0.7) return 'C';
    if (score >= 0.6) return 'D';
    return 'F';
  }
}
```

### 实战工作流

```typescript
class TestQualityWorkflow {
  async improveTestQuality(sourceFile: string): Promise<void> {
    // 步骤1：生成初始测试
    console.log('📝 生成测试用例...');
    let testCode = await this.generateTests(sourceFile);
    
    // 步骤2：运行测试获取覆盖率
    console.log('🧪 运行测试...');
    const coverage = await this.runTests(testCode);
    console.log(`覆盖率: ${coverage.line}%`);
    
    // 步骤3：质量检查
    console.log('🔍 质量检查...');
    const quality = await this.checkQuality(testCode);
    console.log(`质量得分: ${quality.overall}`);
    
    // 步骤4：如果质量不够，迭代改进
    let iteration = 0;
    while (quality.overall < 0.8 && iteration < 3) {
      console.log(`🔄 改进迭代 ${++iteration}...`);
      
      // 分析问题
      const issues = quality.issues;
      console.log(`发现 ${issues.length} 个问题`);
      
      // 针对性改进
      for (const issue of issues) {
        testCode = await this.fixIssue(testCode, issue);
      }
      
      // 重新评估
      quality = await this.checkQuality(testCode);
      console.log(`新质量得分: ${quality.overall}`);
    }
    
    // 步骤5：变异测试验证
    console.log('🧬 运行变异测试...');
    const mutationScore = await this.runMutationTests(testCode);
    console.log(`变异测试得分: ${mutationScore}%`);
    
    // 步骤6：生成报告
    const report = {
      coverage: coverage.line,
      qualityScore: quality.overall,
      mutationScore: mutationScore,
      finalGrade: quality.grade
    };
    
    console.log('\n📊 最终报告:');
    console.log(JSON.stringify(report, null, 2));
    
    // 步骤7：保存改进后的测试
    await this.saveTests(testCode);
  }
}
```

### 最佳实践

**检测指标：**
```
1. 断言密度：平均每个测试至少3个断言
2. Mock比例：不超过50%的函数调用被Mock
3. 边界覆盖：至少覆盖2个边界情况
4. 变异得分：至少80%的变异被杀死
5. 独立性：测试可以任意顺序运行
```

**改进策略：**
```
1. ✅ 使用变异测试验证测试有效性
2. ✅ 自动检测无意义断言
3. ✅ 生成时包含边界情况
4. ✅ LLM评审测试代码
5. ✅ 持续监控质量指标
```

**避免陷阱：**
```
❌ 只追求覆盖率数字
❌ 过度Mock导致不测试真实逻辑
❌ 测试实现细节而非行为
❌ 缺少边界和异常情况
❌ 断言永远成功的表达式
```

