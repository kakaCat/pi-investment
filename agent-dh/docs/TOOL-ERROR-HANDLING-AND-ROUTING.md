# Agent-DH 工具框架：智能错误提示与工具路由设计

**设计理念：** 不只告诉 Agent "错了"，而是告诉它"为什么错"、"怎么改"、"或者试试别的工具"

**核心目标：**
1. **入参错误** → 明确指出问题 + 提供示例 + 引导修正
2. **出参错误** → 说明数据异常 + 给出可能原因 + 推荐替代方案
3. **业务错误** → 解释业务约束 + 提供解决路径 + 推荐其他工具
4. **工具路由** → A 工具不行时，自动推荐 B 工具

---

## 📑 目录

- [问题背景](#问题背景)
- [设计目标](#设计目标)
- [错误分类与处理策略](#错误分类与处理策略)
- [核心实现](#核心实现)
- [业务场景示例](#业务场景示例)
- [工具路由策略](#工具路由策略)
- [最佳实践](#最佳实践)

---

## ❓ 问题背景

### 当前问题

**场景 1：入参错误，Agent 不知道怎么改**
```
❌ 当前：Error: symbol 格式错误
✅ 需要：告诉 Agent symbol 应该是什么格式，给出示例
```

**场景 2：出参无数据，Agent 不知道为什么**
```
❌ 当前：返回 null
✅ 需要：解释为什么没数据（股票不存在？接口异常？），引导 Agent 下一步操作
```

**场景 3：业务拒绝，Agent 不知道怎么办**
```
❌ 当前：Error: 资金不足
✅ 需要：说明当前资金、所需资金、可以减少数量或换便宜的股票
```

**场景 4：工具不适用，Agent 不知道换哪个**
```
❌ 当前：portfolio_trade 失败
✅ 需要：这是非交易时段，可以用 watch_manage 设置价格提醒
```

---

## 🎯 设计目标

### 1. 让 Agent 能自我修复
- 明确告知哪里错了
- 提供正确的示例
- 给出修正步骤

### 2. 让 Agent 能理解业务
- 解释业务规则和约束
- 说明为什么不能执行
- 提供可行的替代方案

### 3. 让 Agent 能选择工具
- A 工具不适用时推荐 B 工具
- 根据场景智能路由
- 避免重复尝试失败的工具

---

## 🏗️ 错误分类与处理策略

### 错误分类矩阵

| 错误类型 | 触发时机 | 返回内容 | Agent 行动 |
|---------|---------|---------|-----------|
| **入参错误** | 参数格式/类型不对 | 期望格式 + 示例 + 修正建议 | 修正参数重试 |
| **入参为空** | 必填参数缺失 | 参数说明 + 示例 + 用途说明 | 补充参数重试 |
| **出参错误** | 后端数据结构异常 | 期望结构 + 实际数据 + 可能原因 | 报告问题或换工具 |
| **出参无数据** | 查询无结果 | 无数据原因 + 检查建议 + 替代方案 | 调整条件或换工具 |
| **业务拒绝** | 违反业务规则 | 规则说明 + 当前状态 + 解决路径 | 调整策略或换工具 |
| **工具不适用** | 场景不匹配 | 不适用原因 + 推荐工具 | 切换到推荐工具 |

---

## 💻 核心实现

### 1. 入参校验增强

```typescript
/**
 * 入参校验（返回结构化提示，不抛异常）
 */
export function validateInput(args: any, schema: InputSchema): ValidationResult {
  for (const [field, rule] of Object.entries(schema)) {
    const value = args[field];
    
    // 1. 必填检查
    if (rule.required && !value) {
      return {
        success: false,
        errorType: 'INPUT_EMPTY',
        field,
        issue: `${field} 是必填参数`,
        expected: rule.expectedFormat,
        example: rule.example,
        guide: `请提供 ${field}。${rule.description}`,
        // 业务上下文
        businessContext: {
          why: `${field} 用于 ${rule.purpose}`,
          impact: `缺少 ${field} 将无法 ${rule.impact}`
        }
      };
    }
    
    // 2. 格式检查
    if (value && rule.validator && !rule.validator(value)) {
      return {
        success: false,
        errorType: 'INPUT_ERROR',
        field,
        issue: rule.errorMessage,
        received: value,
        expected: rule.expectedFormat,
        example: rule.example,
        guide: `请修正 ${field}。正确格式：${rule.expectedFormat}`,
        // 常见错误提示
        commonMistakes: rule.commonMistakes || []
      };
    }
  }
  
  return { success: true };
}

// 使用示例
const inputSchema = {
  symbol: {
    required: true,
    validator: (v) => /^\d{6}$/.test(v),
    expectedFormat: '6位数字',
    example: '600519',
    description: 'A股股票代码',
    purpose: '唯一标识一只股票',
    impact: '执行交易',
    commonMistakes: [
      '不要包含交易所前缀（如 SH600519）',
      '不要使用股票名称（如 贵州茅台）'
    ]
  }
};
```

### 2. 出参校验增强

```typescript
/**
 * 出参校验（识别数据异常，给出引导）
 */
export function validateOutput(
  data: any, 
  schema: OutputSchema,
  context: BusinessContext
): ValidationResult {
  
  // 1. 空数据检查
  if (!data || Object.keys(data).length === 0) {
    return {
      success: false,
      errorType: 'OUTPUT_EMPTY',
      issue: '后端未返回数据',
      possibleReasons: [
        `股票代码 ${context.symbol} 可能不存在`,
        '该股票可能已退市',
        '数据接口暂时异常'
      ],
      guide: '请检查股票代码是否正确',
      // 推荐替代方案
      alternatives: [
        {
          action: 'retry',
          description: '稍后重试当前操作'
        },
        {
          action: 'use_tool',
          tool: 'screening',
          reason: '可以先用 screening 工具搜索股票，确认代码是否正确'
        }
      ]
    };
  }
  
  // 2. 字段缺失检查
  const missingFields = [];
  for (const [field, rule] of Object.entries(schema)) {
    if (rule.required && !(field in data)) {
      missingFields.push({
        field,
        description: rule.description,
        impact: rule.impact
      });
    }
  }
  
  if (missingFields.length > 0) {
    return {
      success: false,
      errorType: 'OUTPUT_ERROR',
      issue: '后端数据结构异常',
      missingFields,
      received: Object.keys(data),
      expected: Object.keys(schema).filter(k => schema[k].required),
      guide: '数据源异常，请报告此问题',
      // 推荐替代方案
      alternatives: [
        {
          action: 'use_tool',
          tool: getAlternativeTool(context.currentTool),
          reason: `${context.currentTool} 数据异常，可尝试 ${getAlternativeTool(context.currentTool)}`
        }
      ]
    };
  }
  
  return { success: true, data };
}
```

### 3. 业务校验增强

```typescript
/**
 * 业务规则校验（解释约束，提供解决路径）
 */
export function validateBusinessRules(
  args: any,
  context: BusinessContext
): ValidationResult {
  
  // 示例：交易时段检查
  if (!isTradingHours()) {
    return {
      success: false,
      errorType: 'BUSINESS_REJECTION',
      rule: '交易时段限制',
      issue: '当前非交易时段（9:30-11:30, 13:00-15:00）',
      currentTime: new Date().toLocaleString('zh-CN'),
      nextTradingTime: getNextTradingTime(),
      guide: '交易时段外无法下单',
      // 业务解决方案
      solutions: [
        {
          approach: 'wait',
          description: `等待至下一交易时段：${getNextTradingTime()}`
        },
        {
          approach: 'use_alternative',
          tool: 'watch_manage',
          reason: '可以设置价格提醒，在交易时段自动通知',
          example: `watch_manage({ action: 'create', symbol: '${args.symbol}', condition: 'price<100' })`
        }
      ]
    };
  }
  
  // 示例：资金不足
  const cost = args.quantity * getCurrentPrice(args.symbol);
  const cash = context.availableCash;
  
  if (cost > cash) {
    return {
      success: false,
      errorType: 'BUSINESS_REJECTION',
      rule: '资金充足性检查',
      issue: '可用资金不足',
      required: cost,
      available: cash,
      shortage: cost - cash,
      guide: '当前资金无法完成此笔交易',
      // 业务解决方案
      solutions: [
        {
          approach: 'reduce_quantity',
          description: `减少买入数量至 ${Math.floor(cash / getCurrentPrice(args.symbol) / 100) * 100} 股`,
          adjustedArgs: {
            ...args,
            quantity: Math.floor(cash / getCurrentPrice(args.symbol) / 100) * 100
          }
        },
        {
          approach: 'sell_first',
          tool: 'position_list',
          reason: '可以先卖出部分持仓释放资金',
          example: 'position_list() 查看当前持仓，选择盈利标的卖出'
        }
      ]
    };
  }
  
  return { success: true };
}
```

### 4. 工具路由引导

```typescript
/**
 * 工具路由策略（A 不行推荐 B）
 */
export function getToolRoutingGuide(
  currentTool: string,
  error: ValidationResult,
  context: BusinessContext
): ToolRoutingGuide {
  
  // 路由规则表
  const routingRules: ToolRoutingRule[] = [
    {
      from: 'portfolio_trade',
      condition: (err) => err.rule === '交易时段限制',
      to: 'watch_manage',
      reason: '非交易时段可以设置价格提醒',
      example: `watch_manage({ action: 'create', name: '茅台突破2000', symbol: '600519', condition: 'price>2000' })`
    },
    {
      from: 'data_fetch_quote',
      condition: (err) => err.errorType === 'OUTPUT_EMPTY',
      to: 'screening',
      reason: '股票代码可能错误，可以先搜索确认',
      example: `screening({ filters: { name: '茅台' } })`
    },
    {
      from: 'portfolio_trade',
      condition: (err) => err.rule === '资金充足性检查',
      to: 'position_list',
      reason: '资金不足时可以先查看持仓，考虑卖出释放资金',
      example: 'position_list() 然后选择盈利标的卖出'
    },
    {
      from: 'model_predict',
      condition: (err) => err.errorType === 'OUTPUT_ERROR',
      to: 'strategy_execute',
      reason: 'ML模型数据异常时，可以用策略信号代替',
      example: `strategy_execute({ strategy_id: 1, symbols: ['${context.symbol}'], mode: 'signal' })`
    },
    {
      from: 'data_fetch_financial',
      condition: (err) => err.errorType === 'OUTPUT_EMPTY',
      to: 'data_fetch_quote',
      reason: '财务数据缺失时，可以先用行情数据进行技术分析',
      example: `data_fetch_quote({ symbol: '${context.symbol}' })`
    }
  ];
  
  // 匹配路由规则
  for (const rule of routingRules) {
    if (rule.from === currentTool && rule.condition(error)) {
      return {
        shouldRoute: true,
        recommendedTool: rule.to,
        reason: rule.reason,
        example: rule.example,
        confidence: 'high'
      };
    }
  }
  
  return { shouldRoute: false };
}
```

### 5. 完整工具包装

```typescript
/**
 * 增强的工具执行器（集成所有校验和路由）
 */
export async function enhancedToolExecute(
  toolName: string,
  args: any,
  schemas: { input: InputSchema; output: OutputSchema },
  businessValidator?: BusinessValidator
): Promise<EnhancedToolResult> {
  
  const context: BusinessContext = {
    currentTool: toolName,
    timestamp: new Date(),
    ...args
  };
  
  // 1️⃣ 入参校验
  const inputCheck = validateInput(args, schemas.input);
  if (!inputCheck.success) {
    return {
      success: false,
      error: inputCheck,
      routing: getToolRoutingGuide(toolName, inputCheck, context)
    };
  }
  
  // 2️⃣ 业务规则校验
  if (businessValidator) {
    const businessCheck = businessValidator(args, context);
    if (!businessCheck.success) {
      return {
        success: false,
        error: businessCheck,
        routing: getToolRoutingGuide(toolName, businessCheck, context)
      };
    }
  }
  
  // 3️⃣ 执行业务逻辑
  let rawResult;
  try {
    rawResult = await executeBusinessLogic(toolName, args);
  } catch (err: any) {
    return {
      success: false,
      error: {
        errorType: 'EXECUTION_ERROR',
        issue: err.message,
        guide: '工具执行失败，请稍后重试'
      }
    };
  }
  
  // 4️⃣ 出参校验
  const outputCheck = validateOutput(rawResult, schemas.output, context);
  if (!outputCheck.success) {
    return {
      success: false,
      error: outputCheck,
      routing: getToolRoutingGuide(toolName, outputCheck, context)
    };
  }
  
  // ✅ 成功
  return {
    success: true,
    data: outputCheck.data
  };
}
```

---

## 📊 业务场景示例

### 场景 1：入参错误 - 股票代码格式错误

**调用：**
```typescript
portfolio_trade({
  action: 'BUY',
  symbol: 'SH600519',  // ❌ 错误：包含了交易所前缀
  quantity: 100
})
```

**返回：**
```json
{
  "success": false,
  "error": {
    "errorType": "INPUT_ERROR",
    "field": "symbol",
    "issue": "股票代码格式错误",
    "received": "SH600519",
    "expected": "6位数字",
    "example": "600519",
    "guide": "请修正 symbol。正确格式：6位数字",
    "commonMistakes": [
      "不要包含交易所前缀（如 SH600519）",
      "不要使用股票名称（如 贵州茅台）"
    ]
  }
}
```

**Agent 理解：** 我应该去掉 "SH" 前缀，重试 `portfolio_trade({ symbol: '600519', ... })`

---

### 场景 2：出参无数据 - 股票不存在

**调用：**
```typescript
data_fetch_quote({ symbol: '999999' })
```

**返回：**
```json
{
  "success": false,
  "error": {
    "errorType": "OUTPUT_EMPTY",
    "issue": "后端未返回数据",
    "possibleReasons": [
      "股票代码 999999 可能不存在",
      "该股票可能已退市",
      "数据接口暂时异常"
    ],
    "guide": "请检查股票代码是否正确",
    "alternatives": [
      {
        "action": "use_tool",
        "tool": "screening",
        "reason": "可以先用 screening 工具搜索股票，确认代码是否正确"
      }
    ]
  },
  "routing": {
    "shouldRoute": true,
    "recommendedTool": "screening",
    "reason": "股票代码可能错误，可以先搜索确认",
    "example": "screening({ filters: { name: '茅台' } })"
  }
}
```

**Agent 理解：** 这个股票代码不存在，我应该用 screening 工具搜索正确的代码

---

### 场景 3：业务拒绝 - 非交易时段

**调用：**
```typescript
portfolio_trade({
  action: 'BUY',
  symbol: '600519',
  quantity: 100
})
// 当前时间：20:00（盘后）
```

**返回：**
```json
{
  "success": false,
  "error": {
    "errorType": "BUSINESS_REJECTION",
    "rule": "交易时段限制",
    "issue": "当前非交易时段（9:30-11:30, 13:00-15:00）",
    "currentTime": "2024-08-28 20:00:00",
    "nextTradingTime": "2024-08-29 09:30:00",
    "guide": "交易时段外无法下单",
    "solutions": [
      {
        "approach": "wait",
        "description": "等待至下一交易时段：2024-08-29 09:30:00"
      },
      {
        "approach": "use_alternative",
        "tool": "watch_manage",
        "reason": "可以设置价格提醒，在交易时段自动通知",
        "example": "watch_manage({ action: 'create', symbol: '600519', condition: 'price<2000' })"
      }
    ]
  },
  "routing": {
    "shouldRoute": true,
    "recommendedTool": "watch_manage",
    "reason": "非交易时段可以设置价格提醒",
    "example": "watch_manage({ action: 'create', name: '茅台突破2000', symbol: '600519', condition: 'price>2000' })"
  }
}
```

**Agent 理解：** 现在不能交易，我应该用 watch_manage 设置提醒，明天开盘时再操作

---

### 场景 4：业务拒绝 - 资金不足

**调用：**
```typescript
portfolio_trade({
  action: 'BUY',
  symbol: '600519',
  quantity: 1000  // 需要 180万
})
// 当前可用资金：50万
```

**返回：**
```json
{
  "success": false,
  "error": {
    "errorType": "BUSINESS_REJECTION",
    "rule": "资金充足性检查",
    "issue": "可用资金不足",
    "required": 1800000,
    "available": 500000,
    "shortage": 1300000,
    "guide": "当前资金无法完成此笔交易",
    "solutions": [
      {
        "approach": "reduce_quantity",
        "description": "减少买入数量至 200 股",
        "adjustedArgs": {
          "action": "BUY",
          "symbol": "600519",
          "quantity": 200
        }
      },
      {
        "approach": "sell_first",
        "tool": "position_list",
        "reason": "可以先卖出部分持仓释放资金",
        "example": "position_list() 查看当前持仓，选择盈利标的卖出"
      }
    ]
  }
}
```

**Agent 理解：** 资金不够，我有两个选择：
1. 减少数量到 200 股
2. 先用 position_list 看看持仓，卖点东西释放资金

---

### 场景 5：出参错误 - 数据结构异常

**调用：**
```typescript
data_fetch_financial({ symbol: '600519' })
```

**后端返回：**
```json
{ "symbol": "600519" }  // 缺少 revenue、net_profit 等字段
```

**工具返回：**
```json
{
  "success": false,
  "error": {
    "errorType": "OUTPUT_ERROR",
    "issue": "后端数据结构异常",
    "missingFields": [
      { "field": "revenue", "description": "营业收入", "impact": "无法评估公司营收规模" },
      { "field": "net_profit", "description": "净利润", "impact": "无法评估盈利能力" }
    ],
    "received": ["symbol"],
    "expected": ["symbol", "revenue", "net_profit", "roe", "eps"],
    "guide": "数据源异常，请报告此问题",
    "alternatives": [
      {
        "action": "use_tool",
        "tool": "data_fetch_quote",
        "reason": "财务数据异常，可以先用行情数据进行技术分析"
      }
    ]
  },
  "routing": {
    "shouldRoute": true,
    "recommendedTool": "data_fetch_quote",
    "reason": "财务数据缺失时，可以先用行情数据进行技术分析",
    "example": "data_fetch_quote({ symbol: '600519' })"
  }
}
```

**Agent 理解：** 财务数据接口有问题，我应该换用 data_fetch_quote 从技术面分析

---

## 🔀 工具路由策略

### 路由规则表

| 当前工具 | 失败原因 | 推荐工具 | 推荐理由 | 示例 |
|---------|---------|---------|---------|------|
| portfolio_trade | 非交易时段 | watch_manage | 可以设置价格提醒 | `watch_manage({ action: 'create', ... })` |
| portfolio_trade | 资金不足 | position_list | 先查持仓，释放资金 | `position_list()` |
| data_fetch_quote | 股票不存在 | screening | 搜索正确代码 | `screening({ filters: { name: '茅台' } })` |
| data_fetch_financial | 数据缺失 | data_fetch_quote | 改用技术分析 | `data_fetch_quote({ symbol })` |
| model_predict | 模型异常 | strategy_execute | 改用策略信号 | `strategy_execute({ strategy_id: 1 })` |
| strategy_execute | 无信号 | opportunity_scan | 扩大选股范围 | `opportunity_scan({ limit: 10 })` |

### 路由决策流程

```
工具执行失败
    ↓
识别失败类型
    ↓
┌─────────────┬─────────────┬─────────────┐
│  入参错误   │  出参异常   │  业务拒绝   │
└─────────────┴─────────────┴─────────────┘
       ↓              ↓              ↓
  修正参数        匹配路由规则    提供解决方案
       ↓              ↓              ↓
    重试         推荐替代工具    调整策略或换工具
```

---

## 🎓 最佳实践

### 1. 错误提示编写规范

✅ **DO：**
```typescript
{
  issue: "symbol 必须是6位数字股票代码",
  received: "SH600519",
  expected: "6位数字",
  example: "600519",
  commonMistakes: ["不要包含交易所前缀"]
}
```

❌ **DON'T：**
```typescript
{
  error: "参数错误"  // 太模糊，Agent 无法理解
}
```

### 2. 业务约束说明规范

✅ **DO：**
```typescript
{
  rule: "交易时段限制",
  issue: "当前非交易时段（9:30-11:30, 13:00-15:00）",
  currentTime: "20:00",
  nextTradingTime: "明日 09:30",
  solutions: [
    { approach: "wait", description: "..." },
    { approach: "use_alternative", tool: "watch_manage", ... }
  ]
}
```

❌ **DON'T：**
```typescript
{
  error: "不能交易"  // 没说为什么，也没给解决方案
}
```

### 3. 工具路由推荐规范

✅ **DO：**
```typescript
{
  routing: {
    shouldRoute: true,
    recommendedTool: "watch_manage",
    reason: "非交易时段可以设置价格提醒",
    example: "watch_manage({ action: 'create', ... })",
    confidence: "high"
  }
}
```

❌ **DON'T：**
```typescript
{
  suggestion: "试试其他工具"  // 没说具体哪个工具，怎么用
}
```

### 4. 测试用例覆盖

每个工具应覆盖以下测试场景：

```typescript
describe('PortfolioTradeTool 错误处理', () => {
  // 入参错误
  it('symbol 格式错误时应返回友好提示', () => { ... });
  it('quantity 不是100倍数时应返回友好提示', () => { ... });
  
  // 业务拒绝
  it('非交易时段应推荐 watch_manage', () => { ... });
  it('资金不足应提供减少数量或卖出持仓方案', () => { ... });
  
  // 出参异常
  it('后端数据缺失应推荐替代工具', () => { ... });
});
```

---

## 📋 实施清单

- [ ] 为每个工具定义 InputSchema（包含 commonMistakes）
- [ ] 为每个工具定义 OutputSchema（包含字段 impact 说明）
- [ ] 为每个工具定义 BusinessValidator（业务规则校验）
- [ ] 建立工具路由规则表（A→B 的推荐关系）
- [ ] 编写完整的错误处理测试用例
- [ ] 更新工具文档（增加错误处理示例）

---

**文档版本：** v1.0  
**创建时间：** 2026-08-28  
**维护团队：** PI Investment Agent Team  
**相关文档：**
- [TOOL-FRAMEWORK-DESIGN.md](./TOOL-FRAMEWORK-DESIGN.md)
- [TOOL-FRAMEWORK-DSH-COMPATIBLE.md](./TOOL-FRAMEWORK-DSH-COMPATIBLE.md)

---

## ⏱️ 异步工具处理

### 设计背景

某些工具执行时间较长，容易超时：
- **数据同步工具**（如 kline_daily_sync）：可能需要 1-2 分钟
- **回测工具**（如 strategy_execute backtest）：可能需要 30-60 秒
- **模型训练**（如 model_train）：可能需要 1-5 分钟
- **批量查询**（如扫描全市场）：可能需要 1-2 分钟

**问题：**
- 同步等待会阻塞 LLM 对话
- 超时会导致任务失败
- LLM 不知道任务还在进行中

**解决方案：** 异步工具 + 任务追踪 + 主动通知

---

### 异步工具返回格式

```typescript
/**
 * 异步工具立即返回（不等待完成）
 */
interface AsyncToolResponse {
  success: true;
  async: true;  // ← 标识这是异步任务
  taskId: string;  // 任务ID，用于后续查询
  taskType: string;  // 任务类型
  estimatedTime: string;  // 预计完成时间
  status: 'pending' | 'running';
  message: string;  // 给 LLM 看的说明
  // 如何查询结果
  howToCheck: {
    tool: string;  // 查询工具名
    args: any;  // 查询参数
    example: string;  // 使用示例
  };
  // 完成后的通知方式
  notification?: {
    method: 'feishu' | 'polling';
    description: string;
  };
}
```

---

### 实现示例

#### 1. 异步工具定义

```typescript
// 示例：K线数据同步（耗时较长）
export const klineDailySyncTool = defineTool({
  name: 'kline_daily_sync',
  description: '执行每日K线同步（异步任务，1-2分钟）',
  
  parameters: {
    date: {
      type: 'string',
      pattern: '^\\d{4}-\\d{2}-\\d{2}$',
      description: '同步日期 YYYY-MM-DD'
    }
  },
  
  // ⏱️ 标记为异步工具
  metadata: {
    isAsync: true,
    estimatedDuration: 120000,  // 120秒
    timeoutMs: 180000  // 3分钟超时
  },
  
  execute: async (args) => {
    // 1. 立即创建异步任务
    const taskId = await createAsyncTask({
      type: 'kline_sync',
      args,
      estimatedDuration: 120000
    });
    
    // 2. 后台执行（不阻塞）
    executeInBackground(taskId, async () => {
      const result = await doKlineSync(args.date);
      await saveTaskResult(taskId, result);
      
      // 3. 完成后通知
      await notifyTaskComplete(taskId, {
        method: 'feishu',
        content: `K线同步完成：${result.success_count} 只股票`
      });
    });
    
    // 4. 立即返回（告知 LLM 任务已提交）
    return {
      success: true,
      async: true,
      taskId,
      taskType: 'kline_sync',
      estimatedTime: '约 2 分钟',
      status: 'running',
      message: `K线同步任务已启动（任务ID: ${taskId}）。预计 2 分钟后完成，完成后将通过飞书通知。`,
      howToCheck: {
        tool: 'task_status',
        args: { taskId },
        example: `task_status({ taskId: '${taskId}' })`
      },
      notification: {
        method: 'feishu',
        description: '完成后将自动发送飞书通知'
      }
    };
  }
});
```

#### 2. 任务状态查询工具

```typescript
export const taskStatusTool = defineTool({
  name: 'task_status',
  description: '查询异步任务状态',
  
  parameters: {
    taskId: {
      type: 'string',
      description: '任务ID（由异步工具返回）'
    }
  },
  
  execute: async ({ taskId }) => {
    const task = await getTask(taskId);
    
    if (!task) {
      return {
        success: false,
        error: {
          errorType: 'TASK_NOT_FOUND',
          issue: `任务 ${taskId} 不存在`,
          guide: '请检查 taskId 是否正确'
        }
      };
    }
    
    // 任务进行中
    if (task.status === 'running') {
      return {
        success: true,
        taskId,
        status: 'running',
        progress: task.progress,  // 进度百分比
        message: `任务进行中（${task.progress}%），预计还需 ${task.remainingTime}`,
        startedAt: task.startedAt,
        estimatedCompleteAt: task.estimatedCompleteAt
      };
    }
    
    // 任务完成
    if (task.status === 'completed') {
      return {
        success: true,
        taskId,
        status: 'completed',
        message: '任务已完成',
        result: task.result,  // 实际结果数据
        completedAt: task.completedAt,
        duration: task.duration
      };
    }
    
    // 任务失败
    if (task.status === 'failed') {
      return {
        success: false,
        taskId,
        status: 'failed',
        error: task.error,
        message: `任务失败：${task.error.message}`,
        failedAt: task.failedAt
      };
    }
  }
});
```

---

### LLM 交互示例

#### 场景：用户要求同步K线数据

**Round 1：提交任务**

```
User: 请同步昨天的K线数据

LLM: 好的，我来执行K线同步。
→ 调用 kline_daily_sync({ date: '2024-08-27' })

← 返回：
{
  "async": true,
  "taskId": "task_kline_20240828_001",
  "estimatedTime": "约 2 分钟",
  "message": "K线同步任务已启动，预计 2 分钟后完成，完成后将通过飞书通知。",
  "howToCheck": {
    "tool": "task_status",
    "args": { "taskId": "task_kline_20240828_001" }
  }
}

LLM: K线同步任务已启动（任务ID: task_kline_20240828_001）。
     这个任务大约需要 2 分钟，我已经提交到后台执行。
     完成后会通过飞书自动通知你，你也可以随时让我查询进度。
```

**Round 2：用户询问进度（1分钟后）**

```
User: 同步进度怎么样了？

LLM: 我来查一下。
→ 调用 task_status({ taskId: 'task_kline_20240828_001' })

← 返回：
{
  "status": "running",
  "progress": 65,
  "message": "任务进行中（65%），预计还需 40 秒"
}

LLM: 同步任务进行中，已完成 65%，预计还需 40 秒。
```

**Round 3：任务完成（飞书通知）**

```
[飞书通知]
✅ K线同步完成
- 成功：3850 只股票
- 失败：12 只股票
- 耗时：1分48秒

User: 看到了，数据同步完了

LLM: 是的，K线数据已经同步完成，成功 3850 只股票。
     现在可以进行数据分析或回测了。
```

---

### 工具标记规范

#### 在工具描述中明确标注

```typescript
{
  name: 'model_train',
  description: '训练新的 ML 预测模型（⏱️ 异步任务，1-5分钟）',
  //                              ↑ 明确告知 LLM 这是异步的
}
```

```typescript
{
  name: 'strategy_execute',
  description: '执行策略：signal 模式实时（<5秒），backtest 模式异步（⏱️ 30-60秒）',
  //                                                        ↑ 说明不同模式的耗时
}
```

#### 在参数中提供异步选项

```typescript
{
  name: 'strategy_execute',
  parameters: {
    mode: {
      type: 'string',
      enum: ['signal', 'backtest'],
      description: 'signal：实时信号（快）；backtest：历史回测（⏱️ 异步，30-60秒）'
    },
    async: {
      type: 'boolean',
      description: '是否异步执行（仅 backtest 模式支持）。true=立即返回任务ID，false=等待完成',
      default: true
    }
  }
}
```

---

### 异步工具清单

| 工具名 | 耗时 | 是否支持异步 | 说明 |
|--------|------|------------|------|
| kline_daily_sync | 1-2分钟 | ✅ 默认异步 | K线数据同步 |
| model_train | 1-5分钟 | ✅ 默认异步 | 模型训练 |
| strategy_execute (backtest) | 30-60秒 | ✅ 可选异步 | 策略回测 |
| evolution_run | 30-90秒 | ✅ 可选异步 | 策略进化 |
| screening | 5-15秒 | ⚠️ 同步 | 全市场筛选（可优化） |
| opportunity_scan | 5-10秒 | ⚠️ 同步 | 机会扫描（可优化） |

---

### 错误处理：超时场景

```typescript
// 同步模式下超时
export function handleTimeout(toolName: string, args: any): ToolResponse {
  return {
    success: false,
    errorType: 'TIMEOUT',
    issue: `${toolName} 执行超时（超过 60 秒）`,
    guide: '此工具耗时较长，建议使用异步模式',
    solutions: [
      {
        approach: 'use_async',
        description: '使用异步模式执行',
        example: `${toolName}({ ...args, async: true })`,
        benefit: '立即返回任务ID，不阻塞对话'
      },
      {
        approach: 'reduce_scope',
        description: '缩小查询范围',
        example: '减少回测天数或股票数量'
      }
    ]
  };
}
```

**LLM 收到超时错误后：**

```json
{
  "success": false,
  "errorType": "TIMEOUT",
  "issue": "strategy_execute 执行超时（超过 60 秒）",
  "solutions": [
    {
      "approach": "use_async",
      "example": "strategy_execute({ ...args, async: true })"
    }
  ]
}
```

**LLM 理解：** 这个操作太慢了，我应该改用异步模式，这样不会阻塞对话。

---

### 最佳实践

#### 1. 什么时候用异步？

✅ **应该异步：**
- 预计超过 30 秒的操作
- 涉及大量数据处理
- 外部 API 调用较多
- 用户不需要立即看到结果

❌ **不应该异步：**
- 5 秒内能完成的操作
- 用户需要立即基于结果做决策
- 简单的查询操作

#### 2. 异步工具设计原则

```typescript
// ✅ 好的设计
{
  name: 'model_train',
  description: '训练模型（⏱️ 异步，1-5分钟）',  // 明确标注
  async: true,  // 标记为异步
  estimatedDuration: 180000,  // 预估时长
  notification: true  // 支持完成通知
}

// ❌ 不好的设计
{
  name: 'model_train',
  description: '训练模型',  // 没说需要多久
  // 没有异步标记，LLM 会以为很快就完成
}
```

#### 3. 通知策略

```typescript
// 任务完成后的通知优先级
const notificationPriority = {
  // 重要任务 → 飞书高优先级
  critical: ['model_train', 'kline_daily_sync'],
  
  // 一般任务 → 飞书普通消息
  normal: ['strategy_execute', 'evolution_run'],
  
  // 仅轮询 → 不主动通知
  polling: ['background_analysis']
};
```

---

### 实施清单

- [ ] 识别所有耗时超过 30 秒的工具
- [ ] 为耗时工具添加异步支持
- [ ] 在工具描述中标注 ⏱️ 和预估时长
- [ ] 实现 `task_status` 查询工具
- [ ] 实现任务完成后的飞书通知
- [ ] 编写异步工具的测试用例
- [ ] 更新工具文档（添加异步使用示例）

---

**文档版本：** v1.1  
**更新时间：** 2026-08-28  
**新增内容：** 异步工具处理设计
