# Agent 自我进化功能 - 设计文档

**日期**：2026-05-14  
**版本**：v1.0  
**状态**：待审核

---

## 一、功能概述

### 1.1 核心目标

为 Agent 添加自我进化能力，通过分析历史决策数据和盈利反馈，持续优化自身的投资决策能力。

### 1.2 核心理念

**基于控制论的负反馈控制系统，通过减法器/补偿器/效应器持续优化 Agent**

### 1.3 理论基础

本功能基于**控制论（Cybernetics）**的经典负反馈控制系统设计：

```
目标值（期望收益）
    ↓
减法器（比较器）：计算误差 = 目标 - 实际
    ↓
误差信号（目标差距）
    ↓
补偿器（控制器）：根据误差产生控制动作
    ↓
效应器（执行机构）：Agent 执行决策
    ↓
实际输出（盈利结果）
    ↓
反馈回路 ──────────┘
```

### 1.4 关键机制

#### 减法器（比较器 / Comparator）
- **控制论定义**：计算目标值与实际值的偏差
- **本功能定义**：预期盈利目标 - 实际盈利结果 = 误差信号
- **作用**：产生驱动优化的误差信号
- **关键**：需要归因分析（目标问题 vs 能力问题）

#### 补偿器（控制器 / Controller/Compensator）
- **控制论定义**：根据误差信号产生控制动作
- **本功能定义**：根据误差大小调整 Agent 能力配置
- **控制策略**：
  - 小误差（<2%）→ 微调参数
  - 中误差（2-5%）→ 新增/移除工具
  - 大误差（>5%）→ 重构策略
- **包含**：新增工具/数据源/算法 + 移除低效组件

#### 效应器（执行机构 / Actuator）
- **控制论定义**：执行控制动作，影响被控对象
- **本功能定义**：Agent 分析后输出买卖建议
- **执行**：用户审核后执行交易
- **反馈**：执行结果反馈到减法器，形成闭环

---

## 二、功能架构

### 2.1 控制论模型

```
┌─────────────────────────────────────────────────────────────┐
│                      控制论反馈系统                           │
└─────────────────────────────────────────────────────────────┘

设定值（目标收益）
    ↓
┌─────────────────────────────────────────────────────────────┐
│  减法器（比较器）                                             │
│  误差 = 目标 - 实际                                          │
│  + 归因分析：目标问题 vs 能力问题                            │
└─────────────────────────────────────────────────────────────┘
    ↓
误差信号（目标差距）
    ↓
┌─────────────────────────────────────────────────────────────┐
│  补偿器（控制器）                                             │
│  • 小误差 <2%  → 微调参数                                    │
│  • 中误差 2-5% → 新增/移除工具                               │
│  • 大误差 >5%  → 重构策略                                    │
└─────────────────────────────────────────────────────────────┘
    ↓
控制信号（能力调整指令）
    ↓
┌─────────────────────────────────────────────────────────────┐
│  效应器（执行机构）                                           │
│  Agent 输出决策建议 → 用户执行交易                           │
└─────────────────────────────────────────────────────────────┘
    ↓
实际输出（盈利结果）
    ↓
反馈测量 ──────────────────────────────────────────────┐
                                                      │
                                                      ↓
                                            反馈到减法器
```

### 2.2 整体流程图

```
┌─────────────────────────────────────────────────────────────┐
│  1. 目标设定                                                  │
│     设定周/月收益目标                                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Agent 运行（使用当前能力配置）                            │
│     • 调用工具分析市场                                        │
│     • 查询经验库参考历史                                      │
│     • 生成决策建议                                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 效应器输出                                                │
│     Agent 输出买卖建议（含理由、仓位、止损等）                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. 用户执行交易                                              │
│     用户审核建议后执行实际交易                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  5. 产生结果                                                  │
│     记录到 trades.json 和 portfolio.json                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  6. 减法器计算                                                │
│     目标 - 实际 = 差距                                        │
│     → 归因分析：目标问题 vs 能力问题                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  7. 数据分析                                                  │
│     • Session 分析：解析决策链路                              │
│     • 决策-收益关联：匹配决策与结果                           │
│     • 模式挖掘：识别成功/失败模式                             │
│     • 工具效能评估：评估每个工具的价值                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  8. 补偿器调整（如果是能力问题）                              │
│     ➕ 新增：工具/数据源/算法/经验                            │
│     ➖ 移除：低效工具/失效算法                                │
│     📝 更新：经验库                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  9. 目标调整（如果是目标问题）                                │
│     根据大盘、历史、波动率调整目标                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  10. 记录进化文档                                             │
│      写入 .pi-invest/evolution/YYYY-MM.md                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
                    下周/下月继续循环
```

### 2.2 数据流图

```
Session 日志 ──┐
               ├──→ 分析引擎 ──→ 减法器归因 ──→ 补偿器调整 ──→ 进化文档
交易记录 ──────┤                                              ↓
               │                                         配置更新
持仓数据 ──────┤                                              ↓
               │                                         影响下次
每日复盘 ──────┘                                         效应器输出
```

---

## 三、核心组件设计

### 3.1 减法器（目标差距计算与归因）

#### 3.1.1 差距计算

```typescript
interface PerformanceGap {
  target: number;           // 目标收益率
  actual: number;           // 实际收益率
  gap: number;              // 差距 = target - actual
  market: number;           // 大盘收益率
  alpha: number;            // 超额收益 = actual - market
}

function calculateGap(
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

#### 3.1.2 归因分析

```typescript
interface AttributionResult {
  rootCause: 'target_unrealistic' | 'capability_insufficient';
  confidence: number;
  reasons: string[];
  recommendation: 'adjust_target' | 'trigger_optimizer';
}

function attributeGap(
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
      recommendation: 'adjust_target'
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

#### 3.1.3 目标合理性检查

```typescript
interface TargetRealisticCheck {
  realistic: boolean;
  reasons: string[];
  suggestedTarget?: number;
}

function checkTargetRealistic(
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
  const avgHistorical = average(historicalReturns);
  if (target > avgHistorical * 2) {
    realistic = false;
    reasons.push(`目标是历史平均的${(target/avgHistorical).toFixed(1)}倍，不现实`);
  }
  
  // 检查3：对比市场波动率
  if (target > marketVolatility * 3) {
    realistic = false;
    reasons.push(`目标超出市场波动率的3倍，风险过高`);
  }
  
  // 建议目标
  const suggestedTarget = realistic ? undefined : market + 1.5; // 大盘 + 1.5% Alpha
  
  return { realistic, reasons, suggestedTarget };
}
```

#### 3.1.4 Agent 能力评估

```typescript
interface CapabilityCheck {
  capable: boolean;
  reasons: string[];
  weaknesses: string[];
}

function evaluateAgentCapability(
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

---


### 3.2 补偿器（能力调整器）

#### 3.2.1 调整策略

根据减法器信号强度，决定调整幅度：

```typescript
interface OptimizerStrategy {
  level: 'minor' | 'moderate' | 'major';
  actions: OptimizerAction[];
}

function determineOptimizerStrategy(gap: number): OptimizerStrategy {
  if (Math.abs(gap) < 2) {
    return {
      level: 'minor',
      actions: ['adjust_parameters', 'update_experience']
    };
  } else if (Math.abs(gap) < 5) {
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
```

#### 3.2.2 工具层调整

**新增工具**：

```typescript
interface ToolAddition {
  name: string;
  description: string;
  implementation: Function;
  reason: string;
  expectedImpact: string;
}

// 示例：新增止损检查工具
const stopLossChecker: ToolAddition = {
  name: "check_stop_loss_trigger",
  description: "检查持仓是否触发止损条件",
  implementation: checkStopLossTrigger,
  reason: "Session 分析发现5次亏损中3次是止损不及时",
  expectedImpact: "减少亏损扩大，改善最大回撤"
};
```

**移除工具**：

```typescript
interface ToolRemoval {
  name: string;
  reason: string;
  evidence: {
    callCount: number;
    winRate: number;
    avgReturn: number;
  };
}

// 示例：移除低效工具
const newsToolRemoval: ToolRemoval = {
  name: "get_stock_news",
  reason: "调用频繁但对收益无明显贡献",
  evidence: {
    callCount: 38,
    winRate: 0.45,
    avgReturn: -0.005
  }
};
```

#### 3.2.3 经验库更新

**经验库结构**：

```typescript
interface Experience {
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
```

**经验查询工具**：

```typescript
// Agent 调用的工具
function query_experience(params: {
  scenario: string;
  symbol?: string;
  conditions?: string[];
}): Experience[] {
  
  const experienceBase = loadExperienceBase();
  
  // 1. 文本相似度匹配
  const textMatches = experienceBase.filter(exp => 
    similarity(exp.scenario, params.scenario) > 0.7
  );
  
  // 2. 条件匹配
  if (params.conditions) {
    return textMatches.filter(exp => 
      matchConditions(exp.pattern.conditions, params.conditions)
    );
  }
  
  // 3. 按置信度排序
  return textMatches.sort((a, b) => b.confidence - a.confidence);
}
```


### 3.3 效应器（决策输出）

#### 3.3.1 输出格式

```typescript
interface EffectorOutput {
  action: 'buy' | 'sell' | 'hold';
  symbol: string;
  name: string;
  
  // 买入/卖出建议
  suggested_quantity?: number;
  suggested_price?: number;
  
  // 风控参数
  stop_loss?: number;
  take_profit?: number;
  max_position?: number;
  
  // 决策依据
  reason: string;
  tool_chain: string[];
  key_indicators: Record<string, any>;
  
  // 经验参考
  similar_cases?: Experience[];
  
  // 置信度
  confidence: number;
  
  // 风险评估
  risk_level: 'low' | 'medium' | 'high';
  risk_factors: string[];
}
```

### 3.4 Session 分析器

#### 3.4.1 解析决策链路

```typescript
interface DecisionChain {
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
```

#### 3.4.2 工具效能评估

```typescript
interface ToolEfficiency {
  tool_name: string;
  call_count: number;
  decisions_after_call: number;
  win_rate: number;
  avg_return: number;
  avg_tokens: number;
  cost_per_call: number;
  roi: number; // 投资回报率
  rating: 1 | 2 | 3 | 4 | 5;
}
```

---

## 四、数据结构

### 4.1 进化文档格式

**路径**：`.pi-invest/evolution/YYYY-MM.md`

```markdown
# 进化报告 2026-05

## 📊 本月表现

| 指标 | 目标 | 实际 | 差距 | 大盘 |
|------|------|------|------|------|
| 月收益率 | +12% | +10% | +2% | +8% |
| 胜率 | 70% | 68% | +2% | - |
| 最大回撤 | -5% | -6% | -1% | -7% |
| 夏普比率 | 1.5 | 1.3 | -0.2 | 1.0 |

**减法器信号**：中度调整（差距 2%）

---

## 🔍 减法器归因分析

### 差距：+2%（未达标）

#### 归因判断

**1. 目标合理性检查**
```
✅ 大盘对比：目标+12% vs 大盘+8%，差距4%（合理）
✅ 历史对比：过去3月平均+10.5%，目标+12%（略高但可达）
✅ 波动率对比：市场波动率3.2%，目标在4倍波动范围内（合理）

结论：目标设定合理
```

**2. Agent 能力评估**
```
✅ 大盘对比：实际+10% vs 大盘+8%，跑赢2%（能力正常）
⚠️ 趋势分析：过去3月收益 +11% → +10.5% → +10%（轻微下降）
⚠️ 决策质量：50次决策中12次失误，错误率24%（略高）

结论：Agent 能力基本正常，但有改进空间
```

#### 最终判断
**根本原因：能力需要微调**
- 目标合理
- 能力基本达标但有优化空间
- 执行中度调整

---

## 📈 Session 深度分析

### 决策质量分布
- 优秀决策(>10%)：15 次
- 良好决策(5-10%)：23 次
- 一般决策(0-5%)：8 次
- 亏损决策(<0%)：12 次

### 成功模式（本月新发现）

#### 模式 #1：技术面+基本面组合
- **出现次数**：18 次
- **胜率**：83%
- **平均收益**：+7.2%
- **工具链**：calculate_technical_indicators → get_financial_data → calculate_buy_range
- **典型案例**：
  - 招商银行（+5.2%）- Session: 20260512T03120_ad0937f0
  - 紫金矿业（+8.1%）- Session: 20260518T14230_bc7f92a1

#### 模式 #2：MACD金叉+成交量确认
- **出现次数**：12 次
- **胜率**：75%
- **平均收益**：+5.8%
- **特征**：MACD柱>0 且成交量放大>20%

### 失败模式（需要改进）

#### 模式 #1：追涨买入
- **出现次数**：8 次
- **胜率**：25%
- **平均损失**：-3.5%
- **特征**：当日涨幅>5% 且 RSI>70
- **典型案例**：
  - 海螺水泥（-3.8%）- Session: 20260511T02554_bd095f2b

#### 模式 #2：止损不及时
- **出现次数**：7 次
- **胜率**：29%
- **平均损失**：-6.2%
- **问题**：跌破止损位但未及时卖出

---

## 🛠️ 工具效能评估

| 工具名称 | 调用次数 | 决策后胜率 | 平均收益 | Token消耗 | ROI | 评级 |
|---------|---------|-----------|---------|----------|-----|------|
| calculate_technical_indicators | 68 | 72% | +3.2% | 1200 | 26.7 | ⭐⭐⭐⭐⭐ |
| get_financial_data | 24 | 79% | +5.1% | 800 | 63.8 | ⭐⭐⭐⭐⭐ |
| query_experience | 42 | 76% | +4.3% | 400 | 107.5 | ⭐⭐⭐⭐⭐ |
| get_market_overview | 55 | 65% | +2.1% | 600 | 35.0 | ⭐⭐⭐⭐ |
| get_stock_realtime_price | 78 | 52% | +0.3% | 300 | 10.0 | ⚠️ 过度依赖 |
| get_stock_news | 45 | 48% | -0.8% | 500 | -16.0 | ❌ 建议移除 |

**关键发现**：
- ✅ 经验库工具效果优秀（ROI 107.5）
- ✅ 基本面分析使用不足但效果好
- ⚠️ 实时价格工具调用过频但价值低
- ❌ 新闻工具负收益，建议移除

---

## 💡 补偿器调整方案

基于减法器信号（差距+2%），执行中度调整：

### ➕ 新增能力

#### 1. 新增工具：check_stop_loss_trigger
- **原因**：7次亏损中5次是止损不及时
- **功能**：自动检查持仓是否触发止损条件
- **预期效果**：减少亏损扩大，改善最大回撤从-6%到-5%

#### 2. 新增工具：analyze_sector_rotation
- **原因**：缺少宏观视角，可能错过行业轮动机会
- **功能**：分析当前市场的行业轮动趋势
- **预期效果**：提升选股质量，增加胜率2-3%

#### 3. 增强经验库
- **新增经验**：追涨买入（胜率25%，建议避免）
- **新增经验**：技术面+基本面组合（胜率83%，积极推荐）

### ➖ 移除能力

#### 1. 移除工具：get_stock_news
- **原因**：调用45次，胜率48%，平均收益-0.8%，ROI为负
- **数据支持**：连续3个月表现不佳
- **预期效果**：减少噪音，降低决策错误率

#### 2. 限制工具：get_stock_realtime_price
- **原因**：调用过频（78次）但价值低（ROI仅10）
- **限制方案**：每只股票每天最多调用3次
- **预期效果**：减少token消耗，提高决策效率

### 📝 参数调整

#### 1. 止损阈值收紧
- **原参数**：-8%
- **新参数**：-5%
- **原因**：最大回撤-6%超出目标-5%

#### 2. 基本面分析权重提升
- **调整**：在功能提示词中强调"买入决策必须包含财务分析"
- **原因**：基本面工具胜率79%但使用率仅35%

---

## 📝 目标调整历史

| 日期 | 原目标 | 新目标 | 调整原因 |
|------|--------|--------|----------|
| 2026-04 | +10% | +10% | 无需调整 |
| 2026-05 | +12% | +12% | 无需调整（目标合理） |

---

## 📈 预期效果

调整后预期（2026-06）：
- 月收益率：+12%（达标）
- 胜率：72%（提升4%）
- 最大回撤：-5%（达标）
- 夏普比率：1.5（提升0.2）

**验证指标**：
- ✅ 止损工具调用率 >80%
- ✅ 基本面工具使用率 >60%
- ✅ 追涨交易次数 <3
- ✅ 新闻工具调用次数 = 0

---

**配置版本**：v7  
**上次更新**：2026-05-31  
**下次评估**：2026-06-30
```

### 4.2 经验库格式

**路径**：`.pi-invest/experience/experience-base.json`

```json
{
  "version": "1.0",
  "last_updated": "2026-05-31",
  "experiences": [
    {
      "id": "exp_001",
      "scenario": "追涨买入",
      "pattern": {
        "conditions": ["当日涨幅>5%", "RSI>70"],
        "action": "buy"
      },
      "outcomes": {
        "total_cases": 8,
        "win_rate": 0.25,
        "avg_return": -0.035,
        "max_loss": -0.062
      },
      "recommendation": "avoid",
      "reason": "历史数据显示追涨买入胜率低，容易买在高点",
      "examples": [
        {
          "date": "2026-05-10",
          "symbol": "600585",
          "session_id": "20260511T02554_bd095f2b",
          "result": -0.038
        }
      ],
      "confidence": 0.88,
      "last_updated": "2026-05-31"
    }
  ]
}
```

### 4.3 配置版本管理

**目录结构**：
```
src/core/agent/
├── system-prompt.ts          # 当前版本
├── versions/
│   ├── system-prompt-v1.ts   # 历史版本1
│   ├── system-prompt-v2.ts   # 历史版本2
│   └── system-prompt-v7.ts   # 最新版本
└── version-history.md        # 版本变更记录
```

**版本变更记录格式**：
```markdown
# 功能配置版本历史

## v7 (2026-05-31)
- ➕ 新增工具：check_stop_loss_trigger
- ➕ 新增工具：analyze_sector_rotation
- ➖ 移除工具：get_stock_news
- 📝 调整参数：止损阈值 -8% → -5%
- 📝 强化规则：买入必须包含财务分析

## v6 (2026-04-30)
- ➕ 新增工具：query_experience
- 📝 调整参数：凯利公式使用半凯利
```

---

## 五、执行流程

### 5.1 每周日晚自动触发

```typescript
async function weeklyEvolutionCycle() {
  console.log('🔄 开始每周进化分析...');
  
  // 1. 收集本周数据
  const weekStart = getWeekStart();
  const weekEnd = getWeekEnd();
  
  const sessions = loadSessionsFromDateRange(weekStart, weekEnd);
  const trades = loadTradesFromDateRange(weekStart, weekEnd);
  const portfolio = loadPortfolio();
  
  // 2. 计算本周表现
  const performance = calculateWeeklyPerformance(trades, portfolio);
  const marketReturn = getMarketReturn(weekStart, weekEnd);
  
  // 3. 减法器计算
  const target = getWeeklyTarget();
  const gap = calculateGap(target, performance.return, marketReturn);
  
  // 4. 归因分析
  const attribution = attributeGap(
    gap,
    getHistoricalReturns(),
    getMarketVolatility(),
    analyzeDecisionQuality(sessions, trades)
  );
  
  console.log(`📊 本周收益：${performance.return}%`);
  console.log(`🎯 目标差距：${gap.gap}%`);
  console.log(`🔍 归因结果：${attribution.rootCause}`);
  
  // 5. 根据归因结果采取行动
  if (attribution.recommendation === 'adjust_target') {
    // 调整目标
    const newTarget = attribution.suggestedTarget;
    updateTarget(newTarget);
    console.log(`🎯 目标已调整：${target}% → ${newTarget}%`);
  } else {
    // 触发补偿器
    const analysis = await analyzePerformance(sessions, trades);
    const suggestions = generateOptimizationSuggestions(analysis);
    
    console.log(`💡 生成 ${suggestions.length} 条改进建议`);
    
    // 6. 生成进化报告
    const report = generateEvolutionReport({
      week: getWeekNumber(),
      performance,
      gap,
      attribution,
      analysis,
      suggestions
    });
    
    // 7. 保存报告
    const reportPath = saveEvolutionReport(report);
    console.log(`📝 进化报告已保存：${reportPath}`);
    
    // 8. 通知用户审核
    notifyUser({
      title: '每周进化报告已生成',
      message: `本周收益${performance.return}%，${suggestions.length}条改进建议待审核`,
      reportPath
    });
  }
}
```

### 5.2 用户审核与应用

```typescript
async function applyOptimizations(
  suggestions: OptimizationSuggestion[],
  selectedIds: string[]
) {
  console.log(`🛠️ 应用 ${selectedIds.length} 条改进...`);
  
  const selected = suggestions.filter(s => selectedIds.includes(s.id));
  
  for (const suggestion of selected) {
    switch (suggestion.type) {
      case 'add_tool':
        await addTool(suggestion.tool);
        console.log(`✅ 已新增工具：${suggestion.tool.name}`);
        break;
        
      case 'remove_tool':
        await removeTool(suggestion.toolName);
        console.log(`✅ 已移除工具：${suggestion.toolName}`);
        break;
        
      case 'update_experience':
        await updateExperienceBase(suggestion.experience);
        console.log(`✅ 已更新经验库`);
        break;
        
      case 'adjust_parameter':
        await adjustParameter(suggestion.parameter, suggestion.newValue);
        console.log(`✅ 已调整参数：${suggestion.parameter}`);
        break;
    }
  }
  
  // 保存新版本配置
  const newVersion = incrementVersion();
  await saveConfigVersion(newVersion);
  console.log(`📦 配置已更新到版本 v${newVersion}`);
  
  // 记录到进化文档
  await appendToEvolutionReport({
    appliedSuggestions: selected,
    version: newVersion,
    timestamp: new Date().toISOString()
  });
}
```

---

## 六、关键特性

### 6.1 数据驱动
- 所有改进基于真实 Session 数据
- 量化评估每个工具的价值
- 用数据说话，避免主观臆断

### 6.2 可追溯
- 进化文档记录每次改进的前后对比
- 配置版本管理，随时回溯
- 清晰的因果链条

### 6.3 可回滚
- 配置版本化管理
- 可以回退到任意历史版本
- 降低改进风险

### 6.4 人工把关
- 改进建议需人工审核后应用
- 避免 Agent 自我破坏
- 保持功能稳定性

### 6.5 持续迭代
- 每周自动分析
- 持续优化
- 形成正向反馈循环

---

## 七、风险控制

### 7.1 过度优化风险
- **问题**：频繁调整导致功能不稳定
- **控制**：
  - 差距<2%时只做微调
  - 每次最多应用3-5条改进
  - 观察期至少1周

### 7.2 归因错误风险
- **问题**：误判目标问题为能力问题
- **控制**：
  - 双重检查机制
  - 置信度评分
  - 人工最终审核

### 7.3 经验过拟合风险
- **问题**：历史经验不适用于新市场环境
- **控制**：
  - 经验置信度随时间衰减
  - 定期清理过时经验
  - 标注市场环境标签

### 7.4 工具依赖风险
- **问题**：移除关键工具导致能力下降
- **控制**：
  - 移除前评估影响范围
  - 保留工具代码，只是禁用
  - 可快速恢复

---

## 八、成功指标

### 8.1 短期指标（每周）
- 收益率达标率 >80%
- 胜率提升趋势
- 最大回撤控制在目标内

### 8.2 中期指标（每月）
- 跑赢大盘
- 夏普比率 >1.5
- 工具效能持续优化

### 8.3 长期指标（每季度）
- 配置版本迭代 >3次
- 经验库条目 >20条
- 决策错误率 <15%

---

## 九、未来扩展

### 9.1 A/B 测试
- 同时运行多个配置版本
- 对比效果
- 科学验证改进

### 9.2 自动回测
- 在历史数据上验证改进
- 降低实盘风险

### 9.3 多Agent协作
- 不同策略的Agent并行运行
- 组合优化

---

**文档结束**
