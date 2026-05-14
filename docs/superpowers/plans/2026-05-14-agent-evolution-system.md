# Agent 自我进化功能 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于控制论的 Agent 自我进化功能，通过分析历史决策数据和盈利反馈持续优化投资决策能力

**Architecture:** 采用控制论负反馈系统设计，包含减法器（差距计算与归因）、补偿器（能力调整）、Session分析器、经验库系统、进化报告生成器和每周自动触发流程

**Tech Stack:** TypeScript, Jest, 现有的 observable-logger 和 daily-review-service

---

## 文件结构规划

本功能将创建以下文件：

### 核心服务层
- `src/services/intelligence/evolution-service.ts` - 进化服务主入口
- `src/services/intelligence/comparator.ts` - 减法器（差距计算与归因）
- `src/services/intelligence/compensator.ts` - 补偿器（能力调整策略）
- `src/services/intelligence/session-analyzer.ts` - Session 分析器
- `src/services/intelligence/experience-manager.ts` - 经验库管理器
- `src/services/intelligence/evolution-reporter.ts` - 进化报告生成器

### 测试文件
- `src/services/intelligence/comparator.test.ts`
- `src/services/intelligence/compensator.test.ts`
- `src/services/intelligence/session-analyzer.test.ts`
- `src/services/intelligence/experience-manager.test.ts`
- `src/services/intelligence/evolution-reporter.test.ts`
- `src/services/intelligence/evolution-service.test.ts`

### 类型定义
- `src/types/evolution.ts` - 进化功能相关类型定义

### 工具层
- `src/infrastructure/tools/experience-tool.ts` - 经验库查询工具（供 Agent 调用）

### 数据目录
- `.pi-invest/evolution/` - 进化报告目录
- `.pi-invest/experience/` - 经验库目录

---

## Task 1: 类型定义

**Files:**
- Create: `src/types/evolution.ts`

- [ ] **Step 1: 创建类型定义文件**

```typescript
/**
 * 进化功能类型定义
 */

// 性能差距
export interface PerformanceGap {
  target: number;           // 目标收益率
  actual: number;           // 实际收益率
  gap: number;              // 差距 = target - actual
  market: number;           // 大盘收益率
  alpha: number;            // 超额收益 = actual - market
}

// 归因结果
export interface AttributionResult {
  rootCause: 'target_unrealistic' | 'capability_insufficient';
  confidence: number;
  reasons: string[];
  recommendation: 'adjust_target' | 'trigger_optimizer';
  suggestedTarget?: number;
}

// 目标合理性检查
export interface TargetRealisticCheck {
  realistic: boolean;
  reasons: string[];
  suggestedTarget?: number;
}

// 能力评估
export interface CapabilityCheck {
  capable: boolean;
  reasons: string[];
  weaknesses: string[];
}

// 决策质量指标
export interface DecisionQualityMetrics {
  recentReturns: number[];
  errorRate: number;
  stopLossExecutionRate: number;
}

// 优化策略
export interface OptimizerStrategy {
  level: 'minor' | 'moderate' | 'major';
  actions: OptimizerAction[];
}

export type OptimizerAction = 
  | 'adjust_parameters' 
  | 'update_experience'
  | 'add_tools'
  | 'remove_tools'
  | 'update_algorithms'
  | 'redesign_strategy';

// 工具调整
export interface ToolAddition {
  name: string;
  description: string;
  reason: string;
  expectedImpact: string;
}

export interface ToolRemoval {
  name: string;
  reason: string;
  evidence: {
    callCount: number;
    winRate: number;
    avgReturn: number;
  };
}

// 经验库
export interface Experience {
  id: string;
  scenario: string;
  pattern: {
    conditions: string[];
    action: 'buy' | 'sell' | 'hold';
  };
  outcomes: {
    total_cases: number;
    win_rate: number;
    avg_return: number;
    max_gain?: number;
    max_loss?: number;
  };
  recommendation: 'aggressive' | 'moderate' | 'cautious' | 'avoid';
  reason: string;
  examples: Array<{
    date: string;
    symbol: string;
    session_id: string;
    result: number;
  }>;
  confidence: number;
  last_updated: string;
}

export interface ExperienceBase {
  version: string;
  last_updated: string;
  experiences: Experience[];
}

// 决策链路
export interface ToolCall {
  tool_name: string;
  arguments: Record<string, any>;
  result?: any;
  timestamp: string;
}

export interface DecisionChain {
  session_id: string;
  timestamp: string;
  user_query: string;
  tool_calls: ToolCall[];
  reasoning?: string;
  decision: {
    action: string;
    symbol: string;
    reason: string;
  };
  resources: {
    tokens: number;
    cost: number;
    duration_ms: number;
  };
}

// 工具效能
export interface ToolEfficiency {
  tool_name: string;
  call_count: number;
  decisions_after_call: number;
  win_rate: number;
  avg_return: number;
  avg_tokens: number;
  cost_per_call: number;
  roi: number;
  rating: 1 | 2 | 3 | 4 | 5;
}

// 优化建议
export interface OptimizationSuggestion {
  id: string;
  type: 'add_tool' | 'remove_tool' | 'update_experience' | 'adjust_parameter';
  priority: 'high' | 'medium' | 'low';
  description: string;
  reason: string;
  expectedImpact: string;
  data?: any;
}

// 进化报告
export interface EvolutionReport {
  period: string;
  performance: {
    target: number;
    actual: number;
    gap: number;
    market: number;
    winRate: number;
    maxDrawdown: number;
    sharpeRatio: number;
  };
  attribution: AttributionResult;
  sessionAnalysis: {
    totalSessions: number;
    successPatterns: Array<{
      pattern: string;
      count: number;
      winRate: number;
      avgReturn: number;
    }>;
    failurePatterns: Array<{
      pattern: string;
      count: number;
      winRate: number;
      avgLoss: number;
    }>;
  };
  toolEfficiency: ToolEfficiency[];
  suggestions: OptimizationSuggestion[];
  appliedChanges?: Array<{
    suggestionId: string;
    appliedAt: string;
    version: number;
  }>;
}
```

- [ ] **Step 2: 提交类型定义**

```bash
git add src/types/evolution.ts
git commit -m "feat(evolution): 添加进化功能类型定义"
```

---

## Task 2: 减法器 - 差距计算

**Files:**
- Create: `src/services/intelligence/comparator.ts`
- Create: `src/services/intelligence/comparator.test.ts`

- [ ] **Step 1: 编写差距计算测试**

```typescript
import { describe, it, expect } from '@jest/globals';
import { calculateGap } from './comparator.js';

describe('Comparator - calculateGap', () => {
  it('应该正确计算性能差距', () => {
    const result = calculateGap(12, 10, 8);
    
    expect(result.target).toBe(12);
    expect(result.actual).toBe(10);
    expect(result.gap).toBe(2);
    expect(result.market).toBe(8);
    expect(result.alpha).toBe(2);
  });

  it('应该处理负收益', () => {
    const result = calculateGap(5, -3, 2);
    
    expect(result.gap).toBe(8);
    expect(result.alpha).toBe(-5);
  });

  it('应该处理跑赢大盘的情况', () => {
    const result = calculateGap(10, 12, 8);
    
    expect(result.gap).toBe(-2); // 超额完成
    expect(result.alpha).toBe(4); // 跑赢大盘4%
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- comparator.test.ts
```

Expected: FAIL with "Cannot find module './comparator.js'"

- [ ] **Step 3: 实现差距计算函数**

```typescript
/**
 * Comparator - 减法器（比较器）
 * 
 * 计算目标与实际的差距，产生误差信号
 */

import type { PerformanceGap } from '../../types/evolution.js';

/**
 * 计算性能差距
 */
export function calculateGap(
  target: number,
  actual: number,
  market: number
): PerformanceGap {
  return {
    target,
    actual,
    gap: target - actual,
    market,
    alpha: actual - market
  };
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- comparator.test.ts
```

Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/comparator.ts src/services/intelligence/comparator.test.ts
git commit -m "feat(evolution): 实现减法器差距计算"
```

---

## Task 3: 减法器 - 目标合理性检查

**Files:**
- Modify: `src/services/intelligence/comparator.ts`
- Modify: `src/services/intelligence/comparator.test.ts`

- [ ] **Step 1: 编写目标合理性检查测试**

```typescript
import { checkTargetRealistic } from './comparator.js';

describe('Comparator - checkTargetRealistic', () => {
  it('应该判断合理的目标', () => {
    const result = checkTargetRealistic(
      10,  // 目标 10%
      8,   // 大盘 8%
      [9, 10, 11],  // 历史平均 10%
      3    // 波动率 3%
    );
    
    expect(result.realistic).toBe(true);
    expect(result.reasons).toHaveLength(0);
    expect(result.suggestedTarget).toBeUndefined();
  });

  it('应该识别目标超出大盘过多', () => {
    const result = checkTargetRealistic(
      20,  // 目标 20%
      8,   // 大盘 8%
      [9, 10, 11],
      3
    );
    
    expect(result.realistic).toBe(false);
    expect(result.reasons).toContain(expect.stringContaining('目标超出大盘'));
    expect(result.suggestedTarget).toBeDefined();
  });

  it('应该识别目标超出历史平均过多', () => {
    const result = checkTargetRealistic(
      25,  // 目标 25%
      10,  // 大盘 10%
      [8, 9, 10],  // 历史平均 9%
      3
    );
    
    expect(result.realistic).toBe(false);
    expect(result.reasons).toContain(expect.stringContaining('历史平均'));
  });

  it('应该识别目标超出波动率过多', () => {
    const result = checkTargetRealistic(
      15,  // 目标 15%
      10,  // 大盘 10%
      [10, 11, 12],
      2    // 波动率 2%
    );
    
    expect(result.realistic).toBe(false);
    expect(result.reasons).toContain(expect.stringContaining('波动率'));
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- comparator.test.ts
```

Expected: FAIL with "checkTargetRealistic is not a function"

- [ ] **Step 3: 实现目标合理性检查**

```typescript
import type { TargetRealisticCheck } from '../../types/evolution.js';

/**
 * 检查目标是否合理
 */
export function checkTargetRealistic(
  target: number,
  market: number,
  historicalReturns: number[],
  marketVolatility: number
): TargetRealisticCheck {
  const reasons: string[] = [];
  let realistic = true;
  
  // 检查1：对比大盘
  const vsMarket = target - market;
  if (vsMarket > 10) {
    realistic = false;
    reasons.push(`目标超出大盘${vsMarket.toFixed(1)}%，过于激进`);
  }
  
  // 检查2：对比历史平均
  const avgHistorical = historicalReturns.reduce((a, b) => a + b, 0) / historicalReturns.length;
  if (target > avgHistorical * 2) {
    realistic = false;
    reasons.push(`目标是历史平均的${(target / avgHistorical).toFixed(1)}倍，不现实`);
  }
  
  // 检查3：对比市场波动率
  if (target > marketVolatility * 3) {
    realistic = false;
    reasons.push(`目标超出市场波动率的3倍，风险过高`);
  }
  
  // 建议目标
  const suggestedTarget = realistic ? undefined : market + 1.5;
  
  return { realistic, reasons, suggestedTarget };
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- comparator.test.ts
```

Expected: PASS (7 tests)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/comparator.ts src/services/intelligence/comparator.test.ts
git commit -m "feat(evolution): 实现目标合理性检查"
```

---

## Task 4: 减法器 - Agent 能力评估

**Files:**
- Modify: `src/services/intelligence/comparator.ts`
- Modify: `src/services/intelligence/comparator.test.ts`

- [ ] **Step 1: 编写能力评估测试**

```typescript
import { evaluateAgentCapability } from './comparator.js';
import type { DecisionQualityMetrics } from '../../types/evolution.js';

describe('Comparator - evaluateAgentCapability', () => {
  it('应该判断能力正常', () => {
    const metrics: DecisionQualityMetrics = {
      recentReturns: [10, 11, 12],
      errorRate: 0.2,
      stopLossExecutionRate: 0.8
    };
    
    const result = evaluateAgentCapability(10, 8, 2, metrics);
    
    expect(result.capable).toBe(true);
    expect(result.reasons).toHaveLength(0);
    expect(result.weaknesses).toHaveLength(0);
  });

  it('应该识别跑输大盘', () => {
    const metrics: DecisionQualityMetrics = {
      recentReturns: [5, 6, 5],
      errorRate: 0.2,
      stopLossExecutionRate: 0.8
    };
    
    const result = evaluateAgentCapability(5, 8, -3, metrics);
    
    expect(result.capable).toBe(false);
    expect(result.reasons).toContain(expect.stringContaining('跑输大盘'));
    expect(result.weaknesses).toContain('选股能力');
  });

  it('应该识别收益率下降趋势', () => {
    const metrics: DecisionQualityMetrics = {
      recentReturns: [12, 10, 8],  // 下降趋势
      errorRate: 0.2,
      stopLossExecutionRate: 0.8
    };
    
    const result = evaluateAgentCapability(8, 7, 1, metrics);
    
    expect(result.capable).toBe(false);
    expect(result.reasons).toContain(expect.stringContaining('持续下降'));
    expect(result.weaknesses).toContain('整体策略');
  });

  it('应该识别决策错误率过高', () => {
    const metrics: DecisionQualityMetrics = {
      recentReturns: [10, 11, 12],
      errorRate: 0.5,  // 50% 错误率
      stopLossExecutionRate: 0.8
    };
    
    const result = evaluateAgentCapability(10, 8, 2, metrics);
    
    expect(result.capable).toBe(false);
    expect(result.reasons).toContain(expect.stringContaining('错误率'));
    expect(result.weaknesses).toContain('决策准确性');
  });

  it('应该识别止损执行率不足', () => {
    const metrics: DecisionQualityMetrics = {
      recentReturns: [10, 11, 12],
      errorRate: 0.2,
      stopLossExecutionRate: 0.5  // 50% 执行率
    };
    
    const result = evaluateAgentCapability(10, 8, 2, metrics);
    
    expect(result.capable).toBe(false);
    expect(result.reasons).toContain(expect.stringContaining('止损执行率'));
    expect(result.weaknesses).toContain('风控能力');
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- comparator.test.ts
```

Expected: FAIL with "evaluateAgentCapability is not a function"

- [ ] **Step 3: 实现能力评估函数**

```typescript
import type { CapabilityCheck, DecisionQualityMetrics } from '../../types/evolution.js';

/**
 * 计算趋势
 */
function calculateTrend(returns: number[]): 'rising' | 'stable' | 'declining' {
  if (returns.length < 2) return 'stable';
  
  let ups = 0;
  let downs = 0;
  
  for (let i = 1; i < returns.length; i++) {
    if (returns[i] > returns[i - 1]) ups++;
    else if (returns[i] < returns[i - 1]) downs++;
  }
  
  if (downs > ups) return 'declining';
  if (ups > downs) return 'rising';
  return 'stable';
}

/**
 * 评估 Agent 能力
 */
export function evaluateAgentCapability(
  actual: number,
  market: number,
  alpha: number,
  decisionQuality: DecisionQualityMetrics
): CapabilityCheck {
  const reasons: string[] = [];
  const weaknesses: string[] = [];
  let capable = true;
  
  // 检查1：对比大盘
  if (alpha < -2) {
    capable = false;
    reasons.push(`跑输大盘${Math.abs(alpha).toFixed(1)}%`);
    weaknesses.push('选股能力');
  }
  
  // 检查2：趋势分析
  const trend = calculateTrend(decisionQuality.recentReturns);
  if (trend === 'declining') {
    capable = false;
    reasons.push('收益率持续下降');
    weaknesses.push('整体策略');
  }
  
  // 检查3：决策质量
  if (decisionQuality.errorRate > 0.4) {
    capable = false;
    reasons.push(`决策错误率${(decisionQuality.errorRate * 100).toFixed(0)}%过高`);
    weaknesses.push('决策准确性');
  }
  
  // 检查4：止损执行
  if (decisionQuality.stopLossExecutionRate < 0.6) {
    capable = false;
    reasons.push('止损执行率不足60%');
    weaknesses.push('风控能力');
  }
  
  return { capable, reasons, weaknesses };
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- comparator.test.ts
```

Expected: PASS (12 tests)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/comparator.ts src/services/intelligence/comparator.test.ts
git commit -m "feat(evolution): 实现 Agent 能力评估"
```

---

## Task 5: 减法器 - 归因分析

**Files:**
- Modify: `src/services/intelligence/comparator.ts`
- Modify: `src/services/intelligence/comparator.test.ts`

- [ ] **Step 1: 编写归因分析测试**

```typescript
import { attributeGap } from './comparator.js';

describe('Comparator - attributeGap', () => {
  it('应该归因为目标不合理', () => {
    const gap = calculateGap(20, 10, 8);
    const metrics: DecisionQualityMetrics = {
      recentReturns: [10, 11, 12],
      errorRate: 0.2,
      stopLossExecutionRate: 0.8
    };
    
    const result = attributeGap(gap, [9, 10, 11], 3, metrics);
    
    expect(result.rootCause).toBe('target_unrealistic');
    expect(result.recommendation).toBe('adjust_target');
    expect(result.suggestedTarget).toBeDefined();
  });

  it('应该归因为能力不足', () => {
    const gap = calculateGap(10, 5, 8);
    const metrics: DecisionQualityMetrics = {
      recentReturns: [8, 6, 5],  // 下降趋势
      errorRate: 0.5,  // 高错误率
      stopLossExecutionRate: 0.5  // 低执行率
    };
    
    const result = attributeGap(gap, [9, 10, 11], 3, metrics);
    
    expect(result.rootCause).toBe('capability_insufficient');
    expect(result.recommendation).toBe('trigger_optimizer');
  });

  it('应该处理混合情况（目标略高+能力略弱）', () => {
    const gap = calculateGap(12, 9, 8);
    const metrics: DecisionQualityMetrics = {
      recentReturns: [10, 9.5, 9],  // 轻微下降
      errorRate: 0.35,  // 略高
      stopLossExecutionRate: 0.65  // 略低
    };
    
    const result = attributeGap(gap, [9, 10, 11], 3, metrics);
    
    expect(result.rootCause).toBe('capability_insufficient');
    expect(result.recommendation).toBe('trigger_optimizer');
    expect(result.confidence).toBeLessThan(0.8);
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- comparator.test.ts
```

Expected: FAIL with "attributeGap is not a function"

- [ ] **Step 3: 实现归因分析函数**

```typescript
import type { AttributionResult } from '../../types/evolution.js';

/**
 * 归因分析：判断差距的根本原因
 */
export function attributeGap(
  gap: PerformanceGap,
  historicalReturns: number[],
  marketVolatility: number,
  decisionQuality: DecisionQualityMetrics
): AttributionResult {
  // 1. 目标合理性检查
  const targetCheck = checkTargetRealistic(
    gap.target,
    gap.market,
    historicalReturns,
    marketVolatility
  );
  
  // 2. Agent 能力评估
  const capabilityCheck = evaluateAgentCapability(
    gap.actual,
    gap.market,
    gap.alpha,
    decisionQuality
  );
  
  // 3. 综合判断
  if (!targetCheck.realistic && capabilityCheck.capable) {
    return {
      rootCause: 'target_unrealistic',
      confidence: 0.85,
      reasons: targetCheck.reasons,
      recommendation: 'adjust_target',
      suggestedTarget: targetCheck.suggestedTarget
    };
  }
  
  if (targetCheck.realistic && !capabilityCheck.capable) {
    return {
      rootCause: 'capability_insufficient',
      confidence: 0.90,
      reasons: capabilityCheck.reasons,
      recommendation: 'trigger_optimizer'
    };
  }
  
  // 4. 混合情况：目标略高 + 能力略弱
  return {
    rootCause: 'capability_insufficient',
    confidence: 0.60,
    reasons: [...targetCheck.reasons, ...capabilityCheck.reasons],
    recommendation: 'trigger_optimizer'
  };
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- comparator.test.ts
```

Expected: PASS (15 tests)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/comparator.ts src/services/intelligence/comparator.test.ts
git commit -m "feat(evolution): 实现归因分析"
```

---

## Task 6: Session 分析器 - 基础结构

**Files:**
- Create: `src/services/intelligence/session-analyzer.ts`
- Create: `src/services/intelligence/session-analyzer.test.ts`

- [ ] **Step 1: 编写 Session 解析测试**

```typescript
import { describe, it, expect } from '@jest/globals';
import { parseSessionEvents } from './session-analyzer.js';

describe('SessionAnalyzer - parseSessionEvents', () => {
  it('应该解析 session events 文件', () => {
    const events = [
      { ts: 1000, event: 'user_message', data: { content: '分析招商银行' } },
      { ts: 1001, event: 'tool_call', data: { tool: 'get_stock_realtime_price', args: { symbol: '600036' } } },
      { ts: 1002, event: 'tool_result', data: { result: { price: 45.2 } } },
      { ts: 1003, event: 'assistant_message', data: { content: '建议买入' } }
    ];
    
    const result = parseSessionEvents('20260511T02554_bd095f2b', events);
    
    expect(result.session_id).toBe('20260511T02554_bd095f2b');
    expect(result.user_query).toBe('分析招商银行');
    expect(result.tool_calls).toHaveLength(1);
    expect(result.tool_calls[0].tool_name).toBe('get_stock_realtime_price');
    expect(result.decision.action).toContain('买入');
  });

  it('应该处理多个工具调用', () => {
    const events = [
      { ts: 1000, event: 'user_message', data: { content: '分析紫金矿业' } },
      { ts: 1001, event: 'tool_call', data: { tool: 'get_stock_realtime_price', args: { symbol: '601899' } } },
      { ts: 1002, event: 'tool_call', data: { tool: 'calculate_technical_indicators', args: { symbol: '601899' } } },
      { ts: 1003, event: 'tool_call', data: { tool: 'get_financial_data', args: { symbol: '601899' } } },
      { ts: 1004, event: 'assistant_message', data: { content: '建议持有' } }
    ];
    
    const result = parseSessionEvents('test_session', events);
    
    expect(result.tool_calls).toHaveLength(3);
    expect(result.tool_calls.map(t => t.tool_name)).toEqual([
      'get_stock_realtime_price',
      'calculate_technical_indicators',
      'get_financial_data'
    ]);
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- session-analyzer.test.ts
```

Expected: FAIL with "Cannot find module './session-analyzer.js'"

- [ ] **Step 3: 实现 Session 解析函数**

```typescript
/**
 * Session Analyzer - Session 分析器
 * 
 * 解析 session 日志，提取决策链路和工具调用信息
 */

import type { DecisionChain, ToolCall } from '../../types/evolution.js';

interface SessionEvent {
  ts: number;
  event: string;
  data?: any;
}

/**
 * 解析 session events
 */
export function parseSessionEvents(
  sessionId: string,
  events: SessionEvent[]
): DecisionChain {
  let userQuery = '';
  const toolCalls: ToolCall[] = [];
  let decision = { action: '', symbol: '', reason: '' };
  let totalTokens = 0;
  let totalCost = 0;
  
  const startTime = events[0]?.ts || 0;
  const endTime = events[events.length - 1]?.ts || 0;
  
  for (const event of events) {
    switch (event.event) {
      case 'user_message':
        if (!userQuery) {
          userQuery = event.data?.content || '';
        }
        break;
        
      case 'tool_call':
        toolCalls.push({
          tool_name: event.data?.tool || '',
          arguments: event.data?.args || {},
          timestamp: new Date(event.ts * 1000).toISOString()
        });
        break;
        
      case 'assistant_message':
        const content = event.data?.content || '';
        if (content.includes('买入')) {
          decision.action = 'buy';
        } else if (content.includes('卖出')) {
          decision.action = 'sell';
        } else if (content.includes('持有')) {
          decision.action = 'hold';
        }
        decision.reason = content;
        break;
        
      case 'llm_call':
        totalTokens += event.data?.tokens || 0;
        totalCost += event.data?.cost || 0;
        break;
    }
  }
  
  return {
    session_id: sessionId,
    timestamp: new Date(startTime * 1000).toISOString(),
    user_query: userQuery,
    tool_calls: toolCalls,
    decision,
    resources: {
      tokens: totalTokens,
      cost: totalCost,
      duration_ms: (endTime - startTime) * 1000
    }
  };
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- session-analyzer.test.ts
```

Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/session-analyzer.ts src/services/intelligence/session-analyzer.test.ts
git commit -m "feat(evolution): 实现 Session 解析器"
```

---

## Task 7: Session 分析器 - 工具效能评估

**Files:**
- Modify: `src/services/intelligence/session-analyzer.ts`
- Modify: `src/services/intelligence/session-analyzer.test.ts`

- [ ] **Step 1: 编写工具效能评估测试**

```typescript
import { evaluateToolEfficiency } from './session-analyzer.js';
import type { DecisionChain } from '../../types/evolution.js';

describe('SessionAnalyzer - evaluateToolEfficiency', () => {
  it('应该计算工具效能指标', () => {
    const sessions: DecisionChain[] = [
      {
        session_id: 's1',
        timestamp: '2026-05-10T10:00:00Z',
        user_query: '分析股票',
        tool_calls: [
          { tool_name: 'get_stock_realtime_price', arguments: {}, timestamp: '2026-05-10T10:00:00Z' },
          { tool_name: 'calculate_technical_indicators', arguments: {}, timestamp: '2026-05-10T10:00:01Z' }
        ],
        decision: { action: 'buy', symbol: '600036', reason: '买入' },
        resources: { tokens: 1000, cost: 0.01, duration_ms: 2000 }
      },
      {
        session_id: 's2',
        timestamp: '2026-05-11T10:00:00Z',
        user_query: '分析股票',
        tool_calls: [
          { tool_name: 'get_stock_realtime_price', arguments: {}, timestamp: '2026-05-11T10:00:00Z' }
        ],
        decision: { action: 'sell', symbol: '600036', reason: '卖出' },
        resources: { tokens: 800, cost: 0.008, duration_ms: 1500 }
      }
    ];
    
    const trades = [
      { session_id: 's1', symbol: '600036', return: 0.05 },  // 5% 收益
      { session_id: 's2', symbol: '600036', return: -0.02 }  // -2% 亏损
    ];
    
    const result = evaluateToolEfficiency(sessions, trades);
    
    expect(result).toHaveLength(2);
    
    const priceToolStats = result.find(t => t.tool_name === 'get_stock_realtime_price');
    expect(priceToolStats).toBeDefined();
    expect(priceToolStats!.call_count).toBe(2);
    expect(priceToolStats!.decisions_after_call).toBe(2);
    expect(priceToolStats!.win_rate).toBe(0.5);
    
    const techToolStats = result.find(t => t.tool_name === 'calculate_technical_indicators');
    expect(techToolStats).toBeDefined();
    expect(techToolStats!.call_count).toBe(1);
    expect(techToolStats!.win_rate).toBe(1.0);
  });

  it('应该计算 ROI', () => {
    const sessions: DecisionChain[] = [
      {
        session_id: 's1',
        timestamp: '2026-05-10T10:00:00Z',
        user_query: '分析',
        tool_calls: [
          { tool_name: 'get_financial_data', arguments: {}, timestamp: '2026-05-10T10:00:00Z' }
        ],
        decision: { action: 'buy', symbol: '600036', reason: '买入' },
        resources: { tokens: 2000, cost: 0.02, duration_ms: 3000 }
      }
    ];
    
    const trades = [
      { session_id: 's1', symbol: '600036', return: 0.10 }  // 10% 收益
    ];
    
    const result = evaluateToolEfficiency(sessions, trades);
    const toolStats = result[0];
    
    expect(toolStats.avg_return).toBe(0.10);
    expect(toolStats.cost_per_call).toBe(0.02);
    expect(toolStats.roi).toBeCloseTo(5.0, 1);  // 10% / 0.02 = 5.0
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- session-analyzer.test.ts
```

Expected: FAIL with "evaluateToolEfficiency is not a function"

- [ ] **Step 3: 实现工具效能评估函数**

```typescript
import type { ToolEfficiency } from '../../types/evolution.js';

interface TradeResult {
  session_id: string;
  symbol: string;
  return: number;
}

/**
 * 评估工具效能
 */
export function evaluateToolEfficiency(
  sessions: DecisionChain[],
  trades: TradeResult[]
): ToolEfficiency[] {
  // 构建 session_id -> trade 映射
  const tradeMap = new Map<string, TradeResult>();
  for (const trade of trades) {
    tradeMap.set(trade.session_id, trade);
  }
  
  // 统计每个工具的使用情况
  const toolStats = new Map<string, {
    calls: number;
    decisions: number;
    wins: number;
    totalReturn: number;
    totalTokens: number;
    totalCost: number;
  }>();
  
  for (const session of sessions) {
    const trade = tradeMap.get(session.session_id);
    const hasDecision = session.decision.action !== '';
    const isWin = trade && trade.return > 0;
    
    for (const toolCall of session.tool_calls) {
      const stats = toolStats.get(toolCall.tool_name) || {
        calls: 0,
        decisions: 0,
        wins: 0,
        totalReturn: 0,
        totalTokens: 0,
        totalCost: 0
      };
      
      stats.calls++;
      if (hasDecision) {
        stats.decisions++;
        if (isWin) stats.wins++;
        if (trade) stats.totalReturn += trade.return;
      }
      stats.totalTokens += session.resources.tokens;
      stats.totalCost += session.resources.cost;
      
      toolStats.set(toolCall.tool_name, stats);
    }
  }
  
  // 转换为 ToolEfficiency 数组
  const result: ToolEfficiency[] = [];
  
  for (const [toolName, stats] of toolStats.entries()) {
    const winRate = stats.decisions > 0 ? stats.wins / stats.decisions : 0;
    const avgReturn = stats.decisions > 0 ? stats.totalReturn / stats.decisions : 0;
    const avgTokens = stats.calls > 0 ? stats.totalTokens / stats.calls : 0;
    const costPerCall = stats.calls > 0 ? stats.totalCost / stats.calls : 0;
    const roi = costPerCall > 0 ? avgReturn / costPerCall : 0;
    
    // 评级：基于 ROI
    let rating: 1 | 2 | 3 | 4 | 5;
    if (roi >= 50) rating = 5;
    else if (roi >= 20) rating = 4;
    else if (roi >= 5) rating = 3;
    else if (roi >= 0) rating = 2;
    else rating = 1;
    
    result.push({
      tool_name: toolName,
      call_count: stats.calls,
      decisions_after_call: stats.decisions,
      win_rate: winRate,
      avg_return: avgReturn,
      avg_tokens: avgTokens,
      cost_per_call: costPerCall,
      roi,
      rating
    });
  }
  
  return result.sort((a, b) => b.roi - a.roi);
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- session-analyzer.test.ts
```

Expected: PASS (4 tests)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/session-analyzer.ts src/services/intelligence/session-analyzer.test.ts
git commit -m "feat(evolution): 实现工具效能评估"
```

---

## Task 8: 经验库管理器

**Files:**
- Create: `src/services/intelligence/experience-manager.ts`
- Create: `src/services/intelligence/experience-manager.test.ts`

- [ ] **Step 1: 编写经验库加载测试**

```typescript
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { loadExperienceBase, saveExperienceBase, addExperience } from './experience-manager.js';
import { existsSync, mkdirSync, writeFileSync, unlinkSync, rmdirSync } from 'fs';
import { join } from 'path';

const TEST_DIR = join(process.cwd(), '.pi-invest-test');
const TEST_EXPERIENCE_FILE = join(TEST_DIR, 'experience', 'experience-base.json');

describe('ExperienceManager', () => {
  beforeEach(() => {
    if (!existsSync(TEST_DIR)) {
      mkdirSync(TEST_DIR, { recursive: true });
      mkdirSync(join(TEST_DIR, 'experience'), { recursive: true });
    }
  });

  afterEach(() => {
    if (existsSync(TEST_EXPERIENCE_FILE)) {
      unlinkSync(TEST_EXPERIENCE_FILE);
    }
    if (existsSync(join(TEST_DIR, 'experience'))) {
      rmdirSync(join(TEST_DIR, 'experience'));
    }
    if (existsSync(TEST_DIR)) {
      rmdirSync(TEST_DIR);
    }
  });

  it('应该加载空经验库', () => {
    const base = loadExperienceBase(TEST_DIR);
    
    expect(base.version).toBe('1.0');
    expect(base.experiences).toEqual([]);
  });

  it('应该加载现有经验库', () => {
    const mockBase = {
      version: '1.0',
      last_updated: '2026-05-14',
      experiences: [
        {
          id: 'exp_001',
          scenario: '追涨买入',
          pattern: { conditions: ['涨幅>5%'], action: 'buy' as const },
          outcomes: { total_cases: 5, win_rate: 0.2, avg_return: -0.03 },
          recommendation: 'avoid' as const,
          reason: '胜率低',
          examples: [],
          confidence: 0.8,
          last_updated: '2026-05-14'
        }
      ]
    };
    
    writeFileSync(TEST_EXPERIENCE_FILE, JSON.stringify(mockBase, null, 2));
    
    const base = loadExperienceBase(TEST_DIR);
    
    expect(base.experiences).toHaveLength(1);
    expect(base.experiences[0].id).toBe('exp_001');
    expect(base.experiences[0].scenario).toBe('追涨买入');
  });

  it('应该保存经验库', () => {
    const base = loadExperienceBase(TEST_DIR);
    
    base.experiences.push({
      id: 'exp_002',
      scenario: 'MACD金叉',
      pattern: { conditions: ['MACD>0'], action: 'buy' },
      outcomes: { total_cases: 10, win_rate: 0.7, avg_return: 0.05 },
      recommendation: 'moderate',
      reason: '胜率较高',
      examples: [],
      confidence: 0.85,
      last_updated: '2026-05-14'
    });
    
    saveExperienceBase(base, TEST_DIR);
    
    const reloaded = loadExperienceBase(TEST_DIR);
    expect(reloaded.experiences).toHaveLength(1);
    expect(reloaded.experiences[0].scenario).toBe('MACD金叉');
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- experience-manager.test.ts
```

Expected: FAIL with "Cannot find module './experience-manager.js'"

- [ ] **Step 3: 实现经验库管理器**

```typescript
/**
 * Experience Manager - 经验库管理器
 * 
 * 管理历史经验的存储、加载和查询
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import type { ExperienceBase, Experience } from '../../types/evolution.js';

const DEFAULT_BASE_DIR = join(process.cwd(), '.pi-invest');

/**
 * 获取经验库文件路径
 */
function getExperienceFilePath(baseDir: string = DEFAULT_BASE_DIR): string {
  return join(baseDir, 'experience', 'experience-base.json');
}

/**
 * 加载经验库
 */
export function loadExperienceBase(baseDir: string = DEFAULT_BASE_DIR): ExperienceBase {
  const filePath = getExperienceFilePath(baseDir);
  
  if (!existsSync(filePath)) {
    return {
      version: '1.0',
      last_updated: new Date().toISOString().split('T')[0],
      experiences: []
    };
  }
  
  const content = readFileSync(filePath, 'utf-8');
  return JSON.parse(content);
}

/**
 * 保存经验库
 */
export function saveExperienceBase(
  base: ExperienceBase,
  baseDir: string = DEFAULT_BASE_DIR
): void {
  const filePath = getExperienceFilePath(baseDir);
  const dir = join(baseDir, 'experience');
  
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true });
  }
  
  base.last_updated = new Date().toISOString().split('T')[0];
  writeFileSync(filePath, JSON.stringify(base, null, 2));
}

/**
 * 添加经验
 */
export function addExperience(
  experience: Experience,
  baseDir: string = DEFAULT_BASE_DIR
): void {
  const base = loadExperienceBase(baseDir);
  
  // 检查是否已存在
  const existingIndex = base.experiences.findIndex(e => e.id === experience.id);
  
  if (existingIndex >= 0) {
    base.experiences[existingIndex] = experience;
  } else {
    base.experiences.push(experience);
  }
  
  saveExperienceBase(base, baseDir);
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- experience-manager.test.ts
```

Expected: PASS (3 tests)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/experience-manager.ts src/services/intelligence/experience-manager.test.ts
git commit -m "feat(evolution): 实现经验库管理器"
```

---

## Task 9: 经验库查询功能

**Files:**
- Modify: `src/services/intelligence/experience-manager.ts`
- Modify: `src/services/intelligence/experience-manager.test.ts`

- [ ] **Step 1: 编写经验查询测试**

```typescript
import { queryExperience } from './experience-manager.js';

describe('ExperienceManager - queryExperience', () => {
  beforeEach(() => {
    const base = {
      version: '1.0',
      last_updated: '2026-05-14',
      experiences: [
        {
          id: 'exp_001',
          scenario: '追涨买入',
          pattern: { conditions: ['涨幅>5%', 'RSI>70'], action: 'buy' as const },
          outcomes: { total_cases: 8, win_rate: 0.25, avg_return: -0.035 },
          recommendation: 'avoid' as const,
          reason: '胜率低',
          examples: [],
          confidence: 0.88,
          last_updated: '2026-05-14'
        },
        {
          id: 'exp_002',
          scenario: 'MACD金叉买入',
          pattern: { conditions: ['MACD>0', '成交量放大'], action: 'buy' as const },
          outcomes: { total_cases: 12, win_rate: 0.75, avg_return: 0.058 },
          recommendation: 'moderate' as const,
          reason: '胜率较高',
          examples: [],
          confidence: 0.82,
          last_updated: '2026-05-14'
        }
      ]
    };
    
    writeFileSync(TEST_EXPERIENCE_FILE, JSON.stringify(base, null, 2));
  });

  it('应该根据场景查询经验', () => {
    const results = queryExperience({ scenario: '追涨' }, TEST_DIR);
    
    expect(results).toHaveLength(1);
    expect(results[0].scenario).toBe('追涨买入');
  });

  it('应该根据条件查询经验', () => {
    const results = queryExperience(
      { conditions: ['MACD>0'] },
      TEST_DIR
    );
    
    expect(results).toHaveLength(1);
    expect(results[0].scenario).toBe('MACD金叉买入');
  });

  it('应该按置信度排序', () => {
    const results = queryExperience({ scenario: '买入' }, TEST_DIR);
    
    expect(results).toHaveLength(2);
    expect(results[0].confidence).toBeGreaterThanOrEqual(results[1].confidence);
  });

  it('应该返回空数组如果没有匹配', () => {
    const results = queryExperience({ scenario: '不存在的场景' }, TEST_DIR);
    
    expect(results).toEqual([]);
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- experience-manager.test.ts
```

Expected: FAIL with "queryExperience is not a function"

- [ ] **Step 3: 实现经验查询函数**

```typescript
interface QueryParams {
  scenario?: string;
  symbol?: string;
  conditions?: string[];
}

/**
 * 计算文本相似度（简单实现）
 */
function similarity(text1: string, text2: string): number {
  const words1 = text1.toLowerCase().split('');
  const words2 = text2.toLowerCase().split('');
  
  let matches = 0;
  for (const word of words1) {
    if (words2.includes(word)) {
      matches++;
    }
  }
  
  return matches / Math.max(words1.length, words2.length);
}

/**
 * 检查条件是否匹配
 */
function matchConditions(patternConditions: string[], queryConditions: string[]): boolean {
  for (const qc of queryConditions) {
    const found = patternConditions.some(pc => 
      pc.toLowerCase().includes(qc.toLowerCase()) ||
      qc.toLowerCase().includes(pc.toLowerCase())
    );
    if (found) return true;
  }
  return false;
}

/**
 * 查询经验
 */
export function queryExperience(
  params: QueryParams,
  baseDir: string = DEFAULT_BASE_DIR
): Experience[] {
  const base = loadExperienceBase(baseDir);
  let results = base.experiences;
  
  // 1. 场景文本匹配
  if (params.scenario) {
    results = results.filter(exp => 
      similarity(exp.scenario, params.scenario!) > 0.3
    );
  }
  
  // 2. 条件匹配
  if (params.conditions && params.conditions.length > 0) {
    results = results.filter(exp => 
      matchConditions(exp.pattern.conditions, params.conditions!)
    );
  }
  
  // 3. 按置信度排序
  return results.sort((a, b) => b.confidence - a.confidence);
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- experience-manager.test.ts
```

Expected: PASS (7 tests)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/experience-manager.ts src/services/intelligence/experience-manager.test.ts
git commit -m "feat(evolution): 实现经验查询功能"
```

---

## Task 10: 补偿器 - 调整策略

**Files:**
- Create: `src/services/intelligence/compensator.ts`
- Create: `src/services/intelligence/compensator.test.ts`

- [ ] **Step 1: 编写补偿器测试**

```typescript
import { describe, it, expect } from '@jest/globals';
import { determineOptimizerStrategy, generateOptimizationSuggestions } from './compensator.js';
import type { ToolEfficiency } from '../../types/evolution.js';

describe('Compensator - determineOptimizerStrategy', () => {
  it('应该为小差距返回微调策略', () => {
    const strategy = determineOptimizerStrategy(1.5);
    
    expect(strategy.level).toBe('minor');
    expect(strategy.actions).toContain('adjust_parameters');
    expect(strategy.actions).toContain('update_experience');
  });

  it('应该为中差距返回中度调整策略', () => {
    const strategy = determineOptimizerStrategy(3);
    
    expect(strategy.level).toBe('moderate');
    expect(strategy.actions).toContain('add_tools');
    expect(strategy.actions).toContain('remove_tools');
  });

  it('应该为大差距返回重大调整策略', () => {
    const strategy = determineOptimizerStrategy(6);
    
    expect(strategy.level).toBe('major');
    expect(strategy.actions).toContain('redesign_strategy');
    expect(strategy.actions).toContain('update_algorithms');
  });
});

describe('Compensator - generateOptimizationSuggestions', () => {
  it('应该建议移除低效工具', () => {
    const toolStats: ToolEfficiency[] = [
      {
        tool_name: 'get_stock_news',
        call_count: 45,
        decisions_after_call: 40,
        win_rate: 0.48,
        avg_return: -0.008,
        avg_tokens: 500,
        cost_per_call: 0.005,
        roi: -1.6,
        rating: 1
      }
    ];
    
    const suggestions = generateOptimizationSuggestions({
      level: 'moderate',
      toolStats,
      weaknesses: []
    });
    
    const removeSuggestion = suggestions.find(s => s.type === 'remove_tool');
    expect(removeSuggestion).toBeDefined();
    expect(removeSuggestion!.description).toContain('get_stock_news');
    expect(removeSuggestion!.priority).toBe('high');
  });

  it('应该建议新增工具解决弱点', () => {
    const suggestions = generateOptimizationSuggestions({
      level: 'moderate',
      toolStats: [],
      weaknesses: ['风控能力']
    });
    
    const addSuggestion = suggestions.find(s => 
      s.type === 'add_tool' && s.description.includes('止损')
    );
    expect(addSuggestion).toBeDefined();
    expect(addSuggestion!.priority).toBe('high');
  });

  it('应该建议更新经验库', () => {
    const suggestions = generateOptimizationSuggestions({
      level: 'minor',
      toolStats: [],
      weaknesses: [],
      newPatterns: [
        { pattern: '追涨买入', winRate: 0.25, avgReturn: -0.035 }
      ]
    });
    
    const expSuggestion = suggestions.find(s => s.type === 'update_experience');
    expect(expSuggestion).toBeDefined();
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- compensator.test.ts
```

Expected: FAIL with "Cannot find module './compensator.js'"

- [ ] **Step 3: 实现补偿器**

```typescript
/**
 * Compensator - 补偿器（控制器）
 * 
 * 根据误差信号产生控制动作，调整 Agent 能力
 */

import type { 
  OptimizerStrategy, 
  OptimizerAction,
  OptimizationSuggestion,
  ToolEfficiency 
} from '../../types/evolution.js';

/**
 * 确定优化策略
 */
export function determineOptimizerStrategy(gap: number): OptimizerStrategy {
  const absGap = Math.abs(gap);
  
  if (absGap < 2) {
    return {
      level: 'minor',
      actions: ['adjust_parameters', 'update_experience']
    };
  } else if (absGap < 5) {
    return {
      level: 'moderate',
      actions: ['add_tools', 'remove_tools', 'update_experience']
    };
  } else {
    return {
      level: 'major',
      actions: ['redesign_strategy', 'add_tools', 'remove_tools', 'update_algorithms']
    };
  }
}

interface OptimizationContext {
  level: 'minor' | 'moderate' | 'major';
  toolStats: ToolEfficiency[];
  weaknesses: string[];
  newPatterns?: Array<{
    pattern: string;
    winRate: number;
    avgReturn: number;
  }>;
}

/**
 * 生成优化建议
 */
export function generateOptimizationSuggestions(
  context: OptimizationContext
): OptimizationSuggestion[] {
  const suggestions: OptimizationSuggestion[] = [];
  let idCounter = 1;
  
  // 1. 移除低效工具（ROI < 0 或 rating = 1）
  for (const tool of context.toolStats) {
    if (tool.roi < 0 || tool.rating === 1) {
      suggestions.push({
        id: `opt_${idCounter++}`,
        type: 'remove_tool',
        priority: 'high',
        description: `移除工具：${tool.tool_name}`,
        reason: `ROI为${tool.roi.toFixed(1)}，胜率${(tool.win_rate * 100).toFixed(0)}%，表现不佳`,
        expectedImpact: '减少噪音，降低决策错误率',
        data: { toolName: tool.tool_name, evidence: tool }
      });
    }
  }
  
  // 2. 根据弱点新增工具
  for (const weakness of context.weaknesses) {
    if (weakness === '风控能力') {
      suggestions.push({
        id: `opt_${idCounter++}`,
        type: 'add_tool',
        priority: 'high',
        description: '新增工具：check_stop_loss_trigger',
        reason: '止损执行率不足，需要自动检查止损条件',
        expectedImpact: '减少亏损扩大，改善最大回撤',
        data: {
          toolName: 'check_stop_loss_trigger',
          description: '检查持仓是否触发止损条件'
        }
      });
    }
    
    if (weakness === '选股能力') {
      suggestions.push({
        id: `opt_${idCounter++}`,
        type: 'add_tool',
        priority: 'medium',
        description: '新增工具：analyze_sector_rotation',
        reason: '缺少宏观视角，可能错过行业轮动机会',
        expectedImpact: '提升选股质量，增加胜率2-3%',
        data: {
          toolName: 'analyze_sector_rotation',
          description: '分析当前市场的行业轮动趋势'
        }
      });
    }
  }
  
  // 3. 更新经验库
  if (context.newPatterns && context.newPatterns.length > 0) {
    for (const pattern of context.newPatterns) {
      suggestions.push({
        id: `opt_${idCounter++}`,
        type: 'update_experience',
        priority: pattern.winRate < 0.4 ? 'high' : 'medium',
        description: `更新经验：${pattern.pattern}`,
        reason: `发现新模式，胜率${(pattern.winRate * 100).toFixed(0)}%，平均收益${(pattern.avgReturn * 100).toFixed(1)}%`,
        expectedImpact: pattern.winRate < 0.4 ? '避免重复错误' : '复制成功经验',
        data: { pattern }
      });
    }
  }
  
  return suggestions;
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- compensator.test.ts
```

Expected: PASS (6 tests)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/compensator.ts src/services/intelligence/compensator.test.ts
git commit -m "feat(evolution): 实现补偿器调整策略"
```

---

## Task 11: 进化报告生成器

**Files:**
- Create: `src/services/intelligence/evolution-reporter.ts`
- Create: `src/services/intelligence/evolution-reporter.test.ts`

- [ ] **Step 1: 编写报告生成测试**

```typescript
import { describe, it, expect } from '@jest/globals';
import { generateEvolutionReport } from './evolution-reporter.js';
import type { AttributionResult, ToolEfficiency } from '../../types/evolution.js';

describe('EvolutionReporter - generateEvolutionReport', () => {
  it('应该生成完整的进化报告', () => {
    const attribution: AttributionResult = {
      rootCause: 'capability_insufficient',
      confidence: 0.85,
      reasons: ['跑输大盘2%', '决策错误率30%'],
      recommendation: 'trigger_optimizer'
    };
    
    const toolStats: ToolEfficiency[] = [
      {
        tool_name: 'calculate_technical_indicators',
        call_count: 50,
        decisions_after_call: 45,
        win_rate: 0.72,
        avg_return: 0.032,
        avg_tokens: 1200,
        cost_per_call: 0.012,
        roi: 2.67,
        rating: 3
      }
    ];
    
    const report = generateEvolutionReport({
      period: '2026-05',
      performance: {
        target: 12,
        actual: 10,
        gap: 2,
        market: 8,
        winRate: 0.68,
        maxDrawdown: -6,
        sharpeRatio: 1.3
      },
      attribution,
      toolStats,
      suggestions: []
    });
    
    expect(report.period).toBe('2026-05');
    expect(report.performance.gap).toBe(2);
    expect(report.attribution.rootCause).toBe('capability_insufficient');
    expect(report.toolEfficiency).toHaveLength(1);
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- evolution-reporter.test.ts
```

Expected: FAIL with "Cannot find module './evolution-reporter.js'"

- [ ] **Step 3: 实现报告生成器**

```typescript
/**
 * Evolution Reporter - 进化报告生成器
 * 
 * 生成结构化的进化报告
 */

import type { 
  EvolutionReport,
  AttributionResult,
  ToolEfficiency,
  OptimizationSuggestion
} from '../../types/evolution.js';

interface ReportInput {
  period: string;
  performance: {
    target: number;
    actual: number;
    gap: number;
    market: number;
    winRate: number;
    maxDrawdown: number;
    sharpeRatio: number;
  };
  attribution: AttributionResult;
  toolStats: ToolEfficiency[];
  suggestions: OptimizationSuggestion[];
  successPatterns?: Array<{
    pattern: string;
    count: number;
    winRate: number;
    avgReturn: number;
  }>;
  failurePatterns?: Array<{
    pattern: string;
    count: number;
    winRate: number;
    avgLoss: number;
  }>;
}

/**
 * 生成进化报告
 */
export function generateEvolutionReport(input: ReportInput): EvolutionReport {
  return {
    period: input.period,
    performance: input.performance,
    attribution: input.attribution,
    sessionAnalysis: {
      totalSessions: input.toolStats.reduce((sum, t) => sum + t.decisions_after_call, 0),
      successPatterns: input.successPatterns || [],
      failurePatterns: input.failurePatterns || []
    },
    toolEfficiency: input.toolStats,
    suggestions: input.suggestions
  };
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- evolution-reporter.test.ts
```

Expected: PASS (1 test)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/evolution-reporter.ts src/services/intelligence/evolution-reporter.test.ts
git commit -m "feat(evolution): 实现进化报告生成器"
```

---

## Task 12: 报告 Markdown 格式化

**Files:**
- Modify: `src/services/intelligence/evolution-reporter.ts`
- Modify: `src/services/intelligence/evolution-reporter.test.ts`

- [ ] **Step 1: 编写 Markdown 格式化测试**

```typescript
import { formatReportAsMarkdown } from './evolution-reporter.js';

describe('EvolutionReporter - formatReportAsMarkdown', () => {
  it('应该生成 Markdown 格式报告', () => {
    const report: EvolutionReport = {
      period: '2026-05',
      performance: {
        target: 12,
        actual: 10,
        gap: 2,
        market: 8,
        winRate: 0.68,
        maxDrawdown: -6,
        sharpeRatio: 1.3
      },
      attribution: {
        rootCause: 'capability_insufficient',
        confidence: 0.85,
        reasons: ['跑输大盘2%'],
        recommendation: 'trigger_optimizer'
      },
      sessionAnalysis: {
        totalSessions: 50,
        successPatterns: [],
        failurePatterns: []
      },
      toolEfficiency: [],
      suggestions: []
    };
    
    const markdown = formatReportAsMarkdown(report);
    
    expect(markdown).toContain('# 进化报告 2026-05');
    expect(markdown).toContain('## 📊 本月表现');
    expect(markdown).toContain('| 月收益率 | +12% | +10% | +2% | +8% |');
    expect(markdown).toContain('## 🔍 减法器归因分析');
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- evolution-reporter.test.ts
```

Expected: FAIL with "formatReportAsMarkdown is not a function"

- [ ] **Step 3: 实现 Markdown 格式化**

```typescript
/**
 * 格式化为 Markdown
 */
export function formatReportAsMarkdown(report: EvolutionReport): string {
  const lines: string[] = [];
  
  // 标题
  lines.push(`# 进化报告 ${report.period}`);
  lines.push('');
  
  // 本月表现
  lines.push('## 📊 本月表现');
  lines.push('');
  lines.push('| 指标 | 目标 | 实际 | 差距 | 大盘 |');
  lines.push('|------|------|------|------|------|');
  lines.push(`| 月收益率 | +${report.performance.target}% | +${report.performance.actual}% | +${report.performance.gap}% | +${report.performance.market}% |`);
  lines.push(`| 胜率 | - | ${(report.performance.winRate * 100).toFixed(0)}% | - | - |`);
  lines.push(`| 最大回撤 | - | ${report.performance.maxDrawdown}% | - | - |`);
  lines.push(`| 夏普比率 | - | ${report.performance.sharpeRatio.toFixed(1)} | - | - |`);
  lines.push('');
  lines.push(`**减法器信号**：${report.performance.gap < 2 ? '微调' : report.performance.gap < 5 ? '中度调整' : '重大调整'}（差距 ${report.performance.gap}%）`);
  lines.push('');
  
  // 归因分析
  lines.push('## 🔍 减法器归因分析');
  lines.push('');
  lines.push(`### 差距：+${report.performance.gap}%（${report.performance.gap > 0 ? '未达标' : '超额完成'}）`);
  lines.push('');
  lines.push('#### 归因判断');
  lines.push('');
  lines.push(`**根本原因：${report.attribution.rootCause === 'target_unrealistic' ? '目标不合理' : '能力需要优化'}**`);
  lines.push(`- 置信度：${(report.attribution.confidence * 100).toFixed(0)}%`);
  lines.push(`- 原因：`);
  for (const reason of report.attribution.reasons) {
    lines.push(`  - ${reason}`);
  }
  lines.push('');
  
  // 工具效能
  if (report.toolEfficiency.length > 0) {
    lines.push('## 🛠️ 工具效能评估');
    lines.push('');
    lines.push('| 工具名称 | 调用次数 | 决策后胜率 | 平均收益 | ROI | 评级 |');
    lines.push('|---------|---------|-----------|---------|-----|------|');
    
    for (const tool of report.toolEfficiency) {
      const stars = '⭐'.repeat(tool.rating);
      lines.push(`| ${tool.tool_name} | ${tool.call_count} | ${(tool.win_rate * 100).toFixed(0)}% | ${(tool.avg_return * 100).toFixed(1)}% | ${tool.roi.toFixed(1)} | ${stars} |`);
    }
    lines.push('');
  }
  
  // 优化建议
  if (report.suggestions.length > 0) {
    lines.push('## 💡 补偿器调整方案');
    lines.push('');
    
    const addSuggestions = report.suggestions.filter(s => s.type === 'add_tool');
    const removeSuggestions = report.suggestions.filter(s => s.type === 'remove_tool');
    const updateSuggestions = report.suggestions.filter(s => s.type === 'update_experience');
    
    if (addSuggestions.length > 0) {
      lines.push('### ➕ 新增能力');
      lines.push('');
      for (const s of addSuggestions) {
        lines.push(`#### ${s.description}`);
        lines.push(`- **原因**：${s.reason}`);
        lines.push(`- **预期效果**：${s.expectedImpact}`);
        lines.push('');
      }
    }
    
    if (removeSuggestions.length > 0) {
      lines.push('### ➖ 移除能力');
      lines.push('');
      for (const s of removeSuggestions) {
        lines.push(`#### ${s.description}`);
        lines.push(`- **原因**：${s.reason}`);
        lines.push(`- **预期效果**：${s.expectedImpact}`);
        lines.push('');
      }
    }
    
    if (updateSuggestions.length > 0) {
      lines.push('### 📝 经验库更新');
      lines.push('');
      for (const s of updateSuggestions) {
        lines.push(`- ${s.description}：${s.reason}`);
      }
      lines.push('');
    }
  }
  
  lines.push('---');
  lines.push('');
  lines.push(`**生成时间**：${new Date().toISOString()}`);
  
  return lines.join('\n');
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- evolution-reporter.test.ts
```

Expected: PASS (2 tests)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/evolution-reporter.ts src/services/intelligence/evolution-reporter.test.ts
git commit -m "feat(evolution): 实现报告 Markdown 格式化"
```

---

## Task 13: 进化服务主入口

**Files:**
- Create: `src/services/intelligence/evolution-service.ts`
- Create: `src/services/intelligence/evolution-service.test.ts`

- [ ] **Step 1: 编写进化服务测试**

```typescript
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { runWeeklyEvolution } from './evolution-service.js';
import { existsSync, mkdirSync, writeFileSync, unlinkSync, rmdirSync, readdirSync } from 'fs';
import { join } from 'path';

const TEST_DIR = join(process.cwd(), '.pi-invest-test');

describe('EvolutionService - runWeeklyEvolution', () => {
  beforeEach(() => {
    if (!existsSync(TEST_DIR)) {
      mkdirSync(TEST_DIR, { recursive: true });
    }
    
    // 创建测试数据
    mkdirSync(join(TEST_DIR, 'sessions'), { recursive: true });
    mkdirSync(join(TEST_DIR, 'evolution'), { recursive: true });
    
    // 模拟 trades.json
    writeFileSync(
      join(TEST_DIR, 'trades.json'),
      JSON.stringify([
        {
          date: '2026-05-10',
          symbol: '600036',
          action: 'buy',
          price: 45,
          quantity: 100,
          session_id: 's1'
        },
        {
          date: '2026-05-15',
          symbol: '600036',
          action: 'sell',
          price: 47,
          quantity: 100,
          session_id: 's2',
          return: 0.044
        }
      ])
    );
  });

  afterEach(() => {
    // 清理测试目录
    const cleanDir = (dir: string) => {
      if (existsSync(dir)) {
        const files = readdirSync(dir);
        for (const file of files) {
          const filePath = join(dir, file);
          if (existsSync(filePath)) {
            unlinkSync(filePath);
          }
        }
        rmdirSync(dir);
      }
    };
    
    cleanDir(join(TEST_DIR, 'sessions'));
    cleanDir(join(TEST_DIR, 'evolution'));
    cleanDir(join(TEST_DIR, 'experience'));
    if (existsSync(join(TEST_DIR, 'trades.json'))) {
      unlinkSync(join(TEST_DIR, 'trades.json'));
    }
    if (existsSync(TEST_DIR)) {
      rmdirSync(TEST_DIR);
    }
  });

  it('应该运行完整的进化流程', async () => {
    const result = await runWeeklyEvolution({
      baseDir: TEST_DIR,
      target: 10,
      marketReturn: 8
    });
    
    expect(result.report).toBeDefined();
    expect(result.report.period).toBeDefined();
    expect(result.report.performance).toBeDefined();
    expect(result.report.attribution).toBeDefined();
    
    // 检查报告文件是否生成
    const evolutionDir = join(TEST_DIR, 'evolution');
    const files = readdirSync(evolutionDir);
    expect(files.length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: 运行测试验证失败**

```bash
npm test -- evolution-service.test.ts
```

Expected: FAIL with "Cannot find module './evolution-service.js'"

- [ ] **Step 3: 实现进化服务主入口**

```typescript
/**
 * Evolution Service - 进化服务主入口
 * 
 * 协调各个组件完成完整的进化流程
 */

import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync } from 'fs';
import { join } from 'path';
import { calculateGap, attributeGap } from './comparator.js';
import { parseSessionEvents, evaluateToolEfficiency } from './session-analyzer.js';
import { determineOptimizerStrategy, generateOptimizationSuggestions } from './compensator.js';
import { generateEvolutionReport, formatReportAsMarkdown } from './evolution-reporter.js';
import type { DecisionQualityMetrics, EvolutionReport } from '../../types/evolution.js';

interface EvolutionOptions {
  baseDir?: string;
  target: number;
  marketReturn: number;
  historicalReturns?: number[];
  marketVolatility?: number;
}

interface EvolutionResult {
  report: EvolutionReport;
  reportPath: string;
}

/**
 * 运行每周进化分析
 */
export async function runWeeklyEvolution(
  options: EvolutionOptions
): Promise<EvolutionResult> {
  const baseDir = options.baseDir || join(process.cwd(), '.pi-invest');
  
  console.log('🔄 开始每周进化分析...');
  
  // 1. 加载交易数据
  const tradesPath = join(baseDir, 'trades.json');
  const trades = existsSync(tradesPath) 
    ? JSON.parse(readFileSync(tradesPath, 'utf-8'))
    : [];
  
  // 2. 计算实际收益
  const totalReturn = trades
    .filter((t: any) => t.return !== undefined)
    .reduce((sum: number, t: any) => sum + t.return, 0);
  const actualReturn = trades.length > 0 ? (totalReturn / trades.length) * 100 : 0;
  
  // 3. 计算差距
  const gap = calculateGap(options.target, actualReturn, options.marketReturn);
  
  console.log(`📊 本周收益：${actualReturn.toFixed(2)}%`);
  console.log(`🎯 目标差距：${gap.gap.toFixed(2)}%`);
  
  // 4. 加载 session 数据（简化版，实际需要解析 sessions 目录）
  const sessionsDir = join(baseDir, 'sessions');
  const sessionIds = existsSync(sessionsDir) ? readdirSync(sessionsDir) : [];
  
  // 5. 计算决策质量指标（简化版）
  const decisionQuality: DecisionQualityMetrics = {
    recentReturns: [actualReturn],
    errorRate: 0.3,
    stopLossExecutionRate: 0.7
  };
  
  // 6. 归因分析
  const attribution = attributeGap(
    gap,
    options.historicalReturns || [8, 9, 10],
    options.marketVolatility || 3,
    decisionQuality
  );
  
  console.log(`🔍 归因结果：${attribution.rootCause}`);
  
  // 7. 如果需要调整目标
  if (attribution.recommendation === 'adjust_target') {
    console.log(`🎯 建议调整目标：${options.target}% → ${attribution.suggestedTarget}%`);
  }
  
  // 8. 工具效能评估（简化版）
  const toolStats = [];
  
  // 9. 生成优化建议
  const strategy = determineOptimizerStrategy(gap.gap);
  const suggestions = generateOptimizationSuggestions({
    level: strategy.level,
    toolStats,
    weaknesses: attribution.rootCause === 'capability_insufficient' 
      ? ['决策准确性', '风控能力']
      : []
  });
  
  console.log(`💡 生成 ${suggestions.length} 条改进建议`);
  
  // 10. 生成报告
  const report = generateEvolutionReport({
    period: new Date().toISOString().slice(0, 7),
    performance: {
      target: options.target,
      actual: actualReturn,
      gap: gap.gap,
      market: options.marketReturn,
      winRate: 0.68,
      maxDrawdown: -6,
      sharpeRatio: 1.3
    },
    attribution,
    toolStats,
    suggestions
  });
  
  // 11. 保存报告
  const evolutionDir = join(baseDir, 'evolution');
  if (!existsSync(evolutionDir)) {
    mkdirSync(evolutionDir, { recursive: true });
  }
  
  const reportPath = join(evolutionDir, `${report.period}.md`);
  const markdown = formatReportAsMarkdown(report);
  writeFileSync(reportPath, markdown);
  
  console.log(`📝 进化报告已保存：${reportPath}`);
  
  return { report, reportPath };
}
```

- [ ] **Step 4: 运行测试验证通过**

```bash
npm test -- evolution-service.test.ts
```

Expected: PASS (1 test)

- [ ] **Step 5: 提交**

```bash
git add src/services/intelligence/evolution-service.ts src/services/intelligence/evolution-service.test.ts
git commit -m "feat(evolution): 实现进化服务主入口"
```

---

## Task 14: 经验库查询工具（供 Agent 调用）

**Files:**
- Create: `src/infrastructure/tools/experience-tool.ts`

- [ ] **Step 1: 实现经验库查询工具**

```typescript
/**
 * Experience Tool - 经验库查询工具
 * 
 * 供 Agent 调用，查询历史经验作为决策参考
 */

import { Type } from '@sinclair/typebox';
import { queryExperience } from '../../services/intelligence/experience-manager.js';

export const query_experience_schema = Type.Object({
  scenario: Type.Optional(Type.String({ description: '场景描述，如"追涨买入"、"MACD金叉"' })),
  symbol: Type.Optional(Type.String({ description: '股票代码' })),
  conditions: Type.Optional(Type.Array(Type.String(), { description: '条件列表，如["涨幅>5%", "RSI>70"]' }))
});

/**
 * 查询经验库
 */
export function query_experience(params: {
  scenario?: string;
  symbol?: string;
  conditions?: string[];
}): string {
  try {
    const experiences = queryExperience(params);
    
    if (experiences.length === 0) {
      return JSON.stringify({
        success: true,
        message: '未找到匹配的历史经验',
        data: []
      });
    }
    
    // 格式化返回结果
    const formatted = experiences.map(exp => ({
      scenario: exp.scenario,
      action: exp.pattern.action,
      recommendation: exp.recommendation,
      outcomes: {
        total_cases: exp.outcomes.total_cases,
        win_rate: `${(exp.outcomes.win_rate * 100).toFixed(0)}%`,
        avg_return: `${(exp.outcomes.avg_return * 100).toFixed(1)}%`
      },
      reason: exp.reason,
      confidence: `${(exp.confidence * 100).toFixed(0)}%`
    }));
    
    return JSON.stringify({
      success: true,
      message: `找到 ${experiences.length} 条相关经验`,
      data: formatted
    }, null, 2);
  } catch (error) {
    return JSON.stringify({
      success: false,
      error: error instanceof Error ? error.message : String(error)
    });
  }
}
```

- [ ] **Step 2: 提交**

```bash
git add src/infrastructure/tools/experience-tool.ts
git commit -m "feat(evolution): 添加经验库查询工具"
```

---

## Task 15: 集成到 CronService

**Files:**
- Modify: `src/services/operations/cron-service.ts`

- [ ] **Step 1: 读取现有 CronService**

```bash
cat src/services/operations/cron-service.ts | head -50
```

- [ ] **Step 2: 在 CronService 中添加每周进化任务**

在 `CronService` 的任务列表中添加：

```typescript
import { runWeeklyEvolution } from '../intelligence/evolution-service.js';

// 在 CronService 类中添加方法
async executeWeeklyEvolution() {
  console.log('🔄 执行每周进化分析...');
  
  try {
    const result = await runWeeklyEvolution({
      target: 10,  // 从配置读取
      marketReturn: 8,  // 从市场数据获取
      historicalReturns: [8, 9, 10],
      marketVolatility: 3
    });
    
    console.log(`✅ 进化分析完成，报告已保存：${result.reportPath}`);
    
    // TODO: 发送通知给用户
    
  } catch (error) {
    console.error('❌ 进化分析失败:', error);
  }
}
```

在 CRON.json 中添加任务配置：

```json
{
  "name": "weekly-evolution",
  "description": "每周进化分析",
  "schedule": "0 20 * * 0",
  "enabled": true,
  "handler": "executeWeeklyEvolution"
}
```

- [ ] **Step 3: 测试集成**

```bash
npm test -- cron-service.test.ts
```

Expected: 现有测试仍然通过

- [ ] **Step 4: 提交**

```bash
git add src/services/operations/cron-service.ts
git commit -m "feat(evolution): 集成每周进化任务到 CronService"
```

---

## Task 16: 端到端集成测试

**Files:**
- Create: `src/services/intelligence/evolution-integration.test.ts`

- [ ] **Step 1: 编写端到端测试**

```typescript
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { runWeeklyEvolution } from './evolution-service.js';
import { loadExperienceBase, addExperience } from './experience-manager.js';
import { existsSync, mkdirSync, writeFileSync, unlinkSync, rmdirSync, readdirSync, readFileSync } from 'fs';
import { join } from 'path';

const TEST_DIR = join(process.cwd(), '.pi-invest-test-e2e');

describe('Evolution System - End-to-End Integration', () => {
  beforeEach(() => {
    // 创建完整的测试环境
    if (!existsSync(TEST_DIR)) {
      mkdirSync(TEST_DIR, { recursive: true });
    }
    
    mkdirSync(join(TEST_DIR, 'sessions'), { recursive: true });
    mkdirSync(join(TEST_DIR, 'evolution'), { recursive: true });
    mkdirSync(join(TEST_DIR, 'experience'), { recursive: true });
    
    // 创建模拟交易数据
    const trades = [
      {
        date: '2026-05-10',
        symbol: '600036',
        action: 'buy',
        price: 45,
        quantity: 100,
        session_id: 's1'
      },
      {
        date: '2026-05-12',
        symbol: '600036',
        action: 'sell',
        price: 47.25,
        quantity: 100,
        session_id: 's2',
        return: 0.05
      },
      {
        date: '2026-05-13',
        symbol: '601899',
        action: 'buy',
        price: 20,
        quantity: 200,
        session_id: 's3'
      },
      {
        date: '2026-05-14',
        symbol: '601899',
        action: 'sell',
        price: 19.5,
        quantity: 200,
        session_id: 's4',
        return: -0.025
      }
    ];
    
    writeFileSync(join(TEST_DIR, 'trades.json'), JSON.stringify(trades, null, 2));
  });

  afterEach(() => {
    // 清理
    const cleanDir = (dir: string) => {
      if (existsSync(dir)) {
        const items = readdirSync(dir);
        for (const item of items) {
          const itemPath = join(dir, item);
          const stat = require('fs').statSync(itemPath);
          if (stat.isDirectory()) {
            cleanDir(itemPath);
          } else {
            unlinkSync(itemPath);
          }
        }
        rmdirSync(dir);
      }
    };
    
    cleanDir(TEST_DIR);
  });

  it('应该完成完整的进化流程', async () => {
    // 1. 运行进化分析
    const result = await runWeeklyEvolution({
      baseDir: TEST_DIR,
      target: 10,
      marketReturn: 8,
      historicalReturns: [8, 9, 10],
      marketVolatility: 3
    });
    
    // 2. 验证报告生成
    expect(result.report).toBeDefined();
    expect(result.report.period).toBeDefined();
    expect(result.report.performance.actual).toBeCloseTo(1.25, 1); // (5% - 2.5%) / 2
    expect(result.report.attribution).toBeDefined();
    
    // 3. 验证报告文件存在
    expect(existsSync(result.reportPath)).toBe(true);
    
    // 4. 验证报告内容
    const reportContent = readFileSync(result.reportPath, 'utf-8');
    expect(reportContent).toContain('# 进化报告');
    expect(reportContent).toContain('## 📊 本月表现');
    expect(reportContent).toContain('## 🔍 减法器归因分析');
    
    // 5. 验证建议生成
    expect(result.report.suggestions.length).toBeGreaterThan(0);
    
    console.log('✅ 端到端测试通过');
    console.log(`📝 报告路径：${result.reportPath}`);
    console.log(`💡 建议数量：${result.report.suggestions.length}`);
  });

  it('应该正确处理经验库更新', async () => {
    // 1. 添加初始经验
    addExperience({
      id: 'exp_test_001',
      scenario: '测试场景',
      pattern: { conditions: ['测试条件'], action: 'buy' },
      outcomes: { total_cases: 5, win_rate: 0.6, avg_return: 0.03 },
      recommendation: 'moderate',
      reason: '测试原因',
      examples: [],
      confidence: 0.75,
      last_updated: '2026-05-14'
    }, TEST_DIR);
    
    // 2. 验证经验库加载
    const base = loadExperienceBase(TEST_DIR);
    expect(base.experiences).toHaveLength(1);
    expect(base.experiences[0].id).toBe('exp_test_001');
    
    // 3. 运行进化分析
    const result = await runWeeklyEvolution({
      baseDir: TEST_DIR,
      target: 10,
      marketReturn: 8
    });
    
    // 4. 验证流程完成
    expect(result.report).toBeDefined();
    
    console.log('✅ 经验库集成测试通过');
  });
});
```

- [ ] **Step 2: 运行端到端测试**

```bash
npm test -- evolution-integration.test.ts
```

Expected: PASS (2 tests)

- [ ] **Step 3: 提交**

```bash
git add src/services/intelligence/evolution-integration.test.ts
git commit -m "test(evolution): 添加端到端集成测试"
```

---

## Task 17: 文档和最终验证

**Files:**
- Create: `docs/evolution-system-usage.md`

- [ ] **Step 1: 创建使用文档**

```markdown
# Agent 自我进化功能使用指南

## 概述

Agent 自我进化功能基于控制论的负反馈控制系统，通过分析历史决策数据和盈利反馈，持续优化投资决策能力。

## 核心组件

### 1. 减法器（Comparator）
- 计算目标收益与实际收益的差距
- 归因分析：判断是目标问题还是能力问题

### 2. 补偿器（Compensator）
- 根据差距大小决定调整策略
- 生成具体的优化建议

### 3. 经验库（Experience Base）
- 存储历史成功/失败模式
- 供 Agent 查询作为决策参考

## 使用方式

### 自动触发

每周日晚 20:00 自动运行进化分析，生成报告到 `.pi-invest/evolution/YYYY-MM.md`

### 手动触发

```typescript
import { runWeeklyEvolution } from './src/services/intelligence/evolution-service.js';

const result = await runWeeklyEvolution({
  target: 10,           // 目标收益率 10%
  marketReturn: 8,      // 大盘收益率 8%
  historicalReturns: [8, 9, 10],
  marketVolatility: 3
});

console.log('报告路径:', result.reportPath);
```

### Agent 查询经验库

```typescript
// Agent 可以调用 query_experience 工具
query_experience({
  scenario: "追涨买入",
  conditions: ["涨幅>5%", "RSI>70"]
})
```

## 数据结构

### 进化报告
- 路径：`.pi-invest/evolution/YYYY-MM.md`
- 格式：Markdown
- 内容：性能分析、归因结果、工具效能、优化建议

### 经验库
- 路径：`.pi-invest/experience/experience-base.json`
- 格式：JSON
- 内容：历史模式、胜率、平均收益、推荐建议

## 工作流程

1. **数据收集**：加载交易记录、session 日志
2. **差距计算**：目标 - 实际 = 差距
3. **归因分析**：判断根本原因
4. **策略决定**：小/中/大调整
5. **生成建议**：新增/移除工具、更新经验
6. **生成报告**：保存 Markdown 报告
7. **用户审核**：人工审核建议
8. **应用改进**：更新配置和代码

## 注意事项

1. 所有改进建议需人工审核后应用
2. 配置版本化管理，可随时回滚
3. 经验置信度随时间衰减
4. 避免过度优化（每次最多3-5条改进）
```

- [ ] **Step 2: 运行所有测试**

```bash
npm test
```

Expected: 所有测试通过

- [ ] **Step 3: 验证类型检查**

```bash
npm run build
```

Expected: 编译成功，无类型错误

- [ ] **Step 4: 最终提交**

```bash
git add docs/evolution-system-usage.md
git commit -m "docs(evolution): 添加使用文档"
git push
```

---

## 自审清单

完成所有任务后，检查以下项目：

- [ ] 所有类型定义完整且一致
- [ ] 所有函数都有对应的测试
- [ ] 测试覆盖率 >80%
- [ ] 没有使用占位符或 TODO
- [ ] 代码遵循项目风格
- [ ] 提交信息清晰规范
- [ ] 文档完整且准确
- [ ] 端到端测试通过
- [ ] 与现有系统集成无冲突

## 文件结构规划

本功能将创建以下文件：

### 核心服务层
- `src/services/intelligence/evolution-service.ts` - 进化服务主入口
- `src/services/intelligence/comparator.ts` - 减法器（差距计算与归因）
- `src/services/intelligence/compensator.ts` - 补偿器（能力调整策略）
- `src/services/intelligence/session-analyzer.ts` - Session 分析器
- `src/services/intelligence/experience-manager.ts` - 经验库管理器
- `src/services/intelligence/evolution-reporter.ts` - 进化报告生成器

### 测试文件
- `src/services/intelligence/comparator.test.ts`
- `src/services/intelligence/compensator.test.ts`
- `src/services/intelligence/session-analyzer.test.ts`
- `src/services/intelligence/experience-manager.test.ts`
- `src/services/intelligence/evolution-reporter.test.ts`
- `src/services/intelligence/evolution-service.test.ts`

### 类型定义
- `src/types/evolution.ts` - 进化功能相关类型定义

### 工具层
- `src/infrastructure/tools/experience-tool.ts` - 经验库查询工具（供 Agent 调用）

### 数据目录
- `.pi-invest/evolution/` - 进化报告目录
- `.pi-invest/experience/` - 经验库目录

---

