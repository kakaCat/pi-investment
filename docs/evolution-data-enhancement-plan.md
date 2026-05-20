# 进化系统数据增强计划

## 📋 概述

当前进化系统的效果器（Effector）缺少关键数据源，特别是 **agent 日志内容**和**市场环境数据**。本计划分5个优先级实施数据增强。

---

## 🎯 优先级 1: 补充市场环境数据（最重要）

### 目标
将硬编码的市场参考值（`market: 5`）替换为真实的大盘指数、板块表现和市场情绪数据。

### 数据结构

```typescript
interface MarketContext {
  // 大盘指数
  indices: {
    sh000001: { 
      return: number;        // 收益率
      volatility: number;    // 波动率
      trend: 'up' | 'down' | 'sideways';
    };
    sz399001: { return: number; volatility: number; trend: string };
    hsi: { return: number; volatility: number; trend: string };
  };
  
  // 板块表现
  sectorPerformance: {
    [sector: string]: {
      return: number;        // 板块收益率
      rank: number;          // 排名（1-N）
      momentum: number;      // 动量指标
    };
  };
  
  // 市场情绪
  sentiment: {
    advanceDeclineRatio: number;  // 涨跌家数比
    volumeRatio: number;          // 成交量比（今日/5日均）
    volatilityIndex: number;      // 波动率指数
    marketBreadth: number;        // 市场广度（上涨股票占比）
  };
  
  // 时间窗口
  period: {
    start: string;
    end: string;
    days: number;
  };
}
```

### 实施步骤

1. **创建市场数据收集器** (`src/services/intelligence/market-data-collector.ts`)
   - 从 akshare 获取大盘指数历史数据
   - 计算收益率和波动率
   - 获取板块资金流向和排名
   - 计算市场情绪指标

2. **集成到进化服务**
   - 在 `evolution-service.ts` 中调用市场数据收集器
   - 将市场数据传递给归因分析器
   - 在报告中展示市场环境对比

3. **更新归因算法**
   - 使用真实大盘收益率替代硬编码值
   - 考虑板块轮动因素
   - 根据市场情绪调整归因权重

### 预期效果
- 归因分析更准确（区分市场因素 vs 能力因素）
- 可以识别"赚了指数的钱"vs"赚了 alpha"
- 板块轮动分析（持仓板块是否踏准节奏）

---

## 🎯 优先级 2: 增强 Session 分析（解析 agent 日志）

### 目标
从 session 日志中提取更深层的决策信息，包括推理过程、错误原因、决策路径。

### Session 日志结构

```
.pi-invest/sessions/{session-id}/
├── conversation.json    # 完整对话历史
├── events.jsonl        # 事件流（工具调用、错误、状态变化）
└── metadata.json       # 会话元数据（token、耗时、工具调用数）
```

### 数据结构

```typescript
interface SessionAnalysisEnhanced {
  // 基础信息（已有）
  sessionId: string;
  timestamp: string;
  decision: 'buy' | 'sell' | 'hold';
  
  // 新增：决策路径
  decisionPath: {
    toolSequence: string[];           // 工具调用序列
    totalTools: number;               // 总工具数
    parallelCalls: number;            // 并行调用次数
    avgResponseTime: number;          // 平均响应时间
    failedTools: Array<{              // 失败的工具
      name: string;
      reason: string;
      retried: boolean;
    }>;
  };
  
  // 新增：推理质量
  reasoning: {
    hasExplicitReasoning: boolean;    // 是否有明确推理
    reasoningLength: number;          // 推理文本长度
    dataSourcesCited: string[];       // 引用的数据源
    contradictions: number;           // 矛盾次数（前后不一致）
  };
  
  // 新增：用户交互
  interaction: {
    userMessages: number;             // 用户消息数
    agentMessages: number;            // Agent 消息数
    clarificationAsked: number;       // 澄清问题次数
    userCorrected: number;            // 用户纠正次数
  };
  
  // 新增：决策时间分布
  timing: {
    dataGatheringTime: number;        // 数据收集耗时
    analysisTime: number;             // 分析耗时
    totalTime: number;                // 总耗时
    timeOfDay: 'morning' | 'afternoon' | 'afterHours';
  };
  
  // 新增：错误分析
  errors: {
    dataErrors: number;               // 数据获取失败
    logicErrors: number;              // 逻辑错误（如类型错误）
    timeoutErrors: number;            // 超时
    recoveryAttempts: number;         // 恢复尝试次数
  };
}
```

### 实施步骤

1. **创建 Session 日志解析器** (`src/services/intelligence/session-log-parser.ts`)
   - 解析 `conversation.json` 提取对话内容
   - 解析 `events.jsonl` 提取工具调用和错误
   - 提取决策路径和推理过程
   - 统计错误类型和恢复情况

2. **增强 Session 分析器** (`src/services/intelligence/session-analyzer.ts`)
   - 集成日志解析器
   - 分析决策路径模式
   - 识别成功/失败路径
   - 计算决策效率指标

3. **决策路径模式识别**
   - 提取高胜率的工具序列
   - 识别导致失败的工具组合
   - 分析工具调用时机（早盘 vs 尾盘）

### 预期效果
- 识别最优决策路径（哪些工具序列效果好）
- 发现常见错误模式（数据源不稳定、超时频发）
- 优化工具调用策略（减少冗余调用）
- 改进错误恢复机制

---

## 🎯 优先级 3: 增强工具效能分析

### 目标
从基础的"调用次数+胜率"扩展到多维度的工具效能评估。

### 数据结构

```typescript
interface EnhancedToolEfficiency extends ToolEfficiency {
  // 基础指标（保留）
  tool_name: string;
  call_count: number;
  win_rate: number;
  avg_return: number;
  
  // 新增：时间分布
  timeDistribution: {
    morning: number;      // 9:30-11:30 调用次数
    afternoon: number;    // 13:00-15:00
    afterHours: number;   // 15:00+
    morningWinRate: number;
    afternoonWinRate: number;
  };
  
  // 新增：组合效果
  frequentCombinations: Array<{
    tools: string[];      // 常见组合
    count: number;        // 出现次数
    winRate: number;      // 组合胜率
    avgReturn: number;    // 组合平均收益
  }>;
  
  // 新增：失败分析
  failures: {
    total: number;
    dataError: number;        // 数据获取失败
    logicError: number;       // 逻辑错误
    timeoutError: number;     // 超时
    retrySuccess: number;     // 重试成功次数
  };
  
  // 新增：性能指标
  performance: {
    avgResponseTime: number;  // 平均响应时间（ms）
    p50ResponseTime: number;  // 中位数
    p95ResponseTime: number;  // 95分位
    errorRate: number;        // 错误率
    timeoutRate: number;      // 超时率
  };
  
  // 新增：参数分析（如果工具有参数）
  parameterImpact?: {
    parameter: string;
    values: Array<{
      value: any;
      count: number;
      winRate: number;
    }>;
  };
}
```

### 实施步骤

1. **扩展工具调用记录**
   - 在 session-context.json 中记录调用时间戳
   - 记录响应时间和错误类型
   - 记录工具参数

2. **创建工具组合分析器**
   - 识别常见工具序列（N-gram）
   - 计算组合的联合胜率
   - 发现协同效应（1+1>2）

3. **性能监控**
   - 统计响应时间分布
   - 识别慢查询工具
   - 监控错误率趋势

### 预期效果
- 发现最佳工具组合（协同效应）
- 识别性能瓶颈工具（优化目标）
- 优化工具调用时机（早盘 vs 尾盘）
- 改进错误处理策略

---

## 🎯 优先级 4: 添加持仓维度分析

### 目标
从总体指标深入到行业、市场、个股维度的细粒度分析。

### 数据结构

```typescript
interface PortfolioAnalysis {
  // 按行业分析
  bySector: {
    [sector: string]: {
      count: number;              // 持仓数量
      totalValue: number;         // 总市值
      weight: number;             // 占比
      return: number;             // 收益率
      winRate: number;            // 胜率
      contribution: number;       // 对总收益的贡献
    };
  };
  
  // 按市场分析
  byMarket: {
    A: { count: number; value: number; return: number; winRate: number };
    HK: { count: number; value: number; return: number; winRate: number };
    US: { count: number; value: number; return: number; winRate: number };
  };
  
  // 风险指标
  risk: {
    concentration: number;        // HHI 集中度指数（0-1）
    topHoldingWeight: number;     // 最大持仓占比
    turnoverRate: number;         // 换手率（月度）
    avgHoldingDays: number;       // 平均持仓天数
    sectorConcentration: number;  // 行业集中度
  };
  
  // 个股表现排名
  topPerformers: Array<{
    symbol: string;
    name: string;
    return: number;
    contribution: number;
  }>;
  
  worstPerformers: Array<{
    symbol: string;
    name: string;
    return: number;
    contribution: number;
  }>;
}
```

### 实施步骤

1. **创建持仓分析器** (`src/services/intelligence/portfolio-analyzer.ts`)
   - 按行业/市场分组统计
   - 计算集中度指标（HHI）
   - 计算换手率和持仓天数

2. **集成到进化报告**
   - 在报告中展示持仓结构
   - 对比行业表现 vs 大盘
   - 识别过度集中风险

3. **归因到行业/个股**
   - 哪些行业贡献了收益
   - 哪些个股拖累了业绩
   - 行业配置是否合理

### 预期效果
- 识别行业配置问题（过度集中/分散）
- 发现拖累业绩的板块
- 优化持仓结构建议
- 改进选股策略（哪些行业选股能力强）

---

## 🎯 优先级 5: 优化评分算法

### 目标
结合新增数据调整进化评分权重，增加市场环境因素。

### 当前评分算法

```typescript
// 当前权重
returnScore * 0.4 +      // 收益率改善
winRateScore * 0.3 +     // 胜率改善
drawdownScore * 0.2 +    // 回撤控制
toolQualityScore * 0.1   // 工具质量
```

### 优化后的评分算法

```typescript
interface EvolutionScore {
  // 基础分（60%）
  baseScore: {
    returnImprovement: number;      // 收益率改善（25%）
    winRateImprovement: number;     // 胜率改善（20%）
    drawdownControl: number;        // 回撤控制（15%）
  };
  
  // 市场调整分（20%）
  marketAdjustedScore: {
    alphaGeneration: number;        // Alpha 生成能力（10%）
    sectorTiming: number;           // 板块轮动踏准度（5%）
    marketAdaptation: number;       // 市场适应性（5%）
  };
  
  // 能力提升分（20%）
  capabilityScore: {
    toolEfficiency: number;         // 工具效能提升（10%）
    decisionQuality: number;        // 决策质量提升（5%）
    errorReduction: number;         // 错误率降低（5%）
  };
  
  // 总分
  totalScore: number;  // 0-100
}
```

### 实施步骤

1. **重构评分函数** (`src/services/intelligence/evolution-history.ts`)
   - 拆分为多个子评分函数
   - 计算 Alpha（实际收益 - 市场收益）
   - 计算板块踏准度（持仓板块 vs 强势板块）

2. **动态权重调整**
   - 牛市：降低收益率权重，提高 Alpha 权重
   - 熊市：提高回撤控制权重
   - 震荡市：提高胜率权重

3. **增加归因细节**
   - 收益来源分解（市场 beta + 行业 + 个股 alpha）
   - 识别运气成分 vs 能力成分

### 预期效果
- 评分更公平（考虑市场环境）
- 识别真实能力提升（排除市场因素）
- 动态适应不同市场环境

---

## 📅 实施时间表

| 优先级 | 任务 | 预计工时 | 依赖 |
|:-----:|:-----|:--------:|:-----|
| P1 | 市场环境数据收集 | 4h | 无 |
| P2 | Session 日志解析 | 6h | 无 |
| P3 | 工具效能增强 | 4h | P2 |
| P4 | 持仓维度分析 | 3h | 无 |
| P5 | 评分算法优化 | 3h | P1, P2, P3, P4 |
| **总计** | | **20h** | |

---

## 🎯 成功指标

### 数据完整性
- ✅ 市场环境数据覆盖率 > 95%
- ✅ Session 日志解析成功率 > 90%
- ✅ 工具调用记录完整性 > 95%

### 分析准确性
- ✅ 归因分析准确率提升 > 30%
- ✅ 工具效能评估误差 < 10%
- ✅ 持仓风险识别准确率 > 80%

### 系统性能
- ✅ 数据收集耗时 < 30s
- ✅ 分析报告生成耗时 < 60s
- ✅ 内存占用增加 < 100MB

---

## 🚀 快速开始

### 第一步：市场环境数据（最重要）

```bash
# 1. 创建市场数据收集器
npx tsx src/services/intelligence/market-data-collector.ts

# 2. 测试数据收集
npm run test:market-data

# 3. 集成到进化服务
# 修改 evolution-service.ts
```

### 第二步：Session 日志解析

```bash
# 1. 创建日志解析器
npx tsx src/services/intelligence/session-log-parser.ts

# 2. 测试解析
npm run test:session-parser

# 3. 集成到 session-analyzer
```

### 第三步：逐步完成其他优先级

按照优先级顺序，逐个实施并测试。

---

## 📝 注意事项

1. **向后兼容**：新增字段使用可选类型，不破坏现有代码
2. **性能优化**：大量 session 日志解析可能耗时，考虑增量解析
3. **数据缓存**：市场数据可以缓存（按日期），避免重复获取
4. **错误处理**：数据获取失败时使用降级策略，不阻塞进化流程
5. **测试覆盖**：每个新增模块都要有单元测试

---

## 🔗 相关文档

- [进化系统设计文档](./superpowers/specs/2026-05-14-automated-evolution-system.md)
- [Session 分析器](../src/services/intelligence/session-analyzer.ts)
- [进化历史管理](../src/services/intelligence/evolution-history.ts)
