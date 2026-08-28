# Phase 1: 核心框架重构完成报告（修正版）

**日期**: 2026-08-28  
**状态**: ✅ 完成（已修正架构错误）  
**执行模型**: Claude Opus 4.6

---

## 🎯 架构修正说明

### 问题发现

初始实现时，我犯了**过度设计**的错误：
- ❌ 在 `core` 包中实现了具体的 validators
- ❌ 在 `core` 包中实现了具体的 routing rules
- ❌ 在 `core` 包中实现了具体的 schema templates
- ❌ 在 `core` 包中实现了具体的校验逻辑

**错误根源**：把 `core` 包当成了"工具库"，而不是"规范定义"。

### 正确的架构理解

根据设计文档（TOOL-FRAMEWORK-DSH-COMPATIBLE.md），`core` 包应该：

✅ **只定义规范**：
- 类型定义（TypeScript interfaces/types）
- 三段式接口契约
- 通用的流程框架

❌ **不包含具体实现**：
- 具体的业务校验器（如 `validateTradingHours`）
- 具体的路由规则（如 `portfolio_trade → watch_manage`）
- 具体的 schema 模板（如 `symbolInputField`）

**关键原则**：各工具在自己的目录下实现具体逻辑。

---

## 📁 最终的 core 包结构

```
packages/core/
├── src/
│   ├── types.ts       (253 行) - 纯类型定义和接口规范
│   └── index.ts       (107 行) - 导出类型 + 两个通用辅助函数
├── package.json
├── tsconfig.json
└── README.md
```

### types.ts - 定义规范

```typescript
// 1. 类型定义
export enum ErrorType { ... }
export interface ValidationResult { ... }
export interface BusinessContext { ... }
export interface ToolRoutingGuide { ... }
export interface ToolRoutingRule { ... }
export interface EnhancedToolResult { ... }

// 2. 三段式接口规范
export interface InputValidator {
  validate(args: any): ValidationResult;
}

export interface TaskExecutor {
  execute(args: any, context: BusinessContext): Promise<any>;
  validateBusinessRules?(args: any, context: BusinessContext): ValidationResult | Promise<ValidationResult>;
}

export interface OutputWrapper {
  validate(data: any, context: BusinessContext): ValidationResult;
  getRoutingRules?(): ToolRoutingRule[];
}

export interface ThreePhaseToolHandler {
  name: string;
  inputValidator: InputValidator;
  taskExecutor: TaskExecutor;
  outputWrapper: OutputWrapper;
}
```

### index.ts - 提供通用辅助函数

```typescript
// 1. 导出所有类型
export * from './types';

// 2. 路由匹配辅助函数（通用逻辑，不涉及具体业务）
export function getToolRoutingGuide(
  currentTool: string,
  error: ValidationResult,
  context: BusinessContext,
  routingRules: ToolRoutingRule[]
): ToolRoutingGuide { ... }

// 3. 三段式流程执行框架（通用逻辑，不涉及具体业务）
export async function executeThreePhaseFlow(
  handler: ThreePhaseToolHandler,
  args: any
): Promise<EnhancedToolResult> { ... }
```

---

## 🏗️ 各工具应该如何实现

### 文件组织结构

```
packages/trading/src/tools/PortfolioTradeTool/
├── schema.ts          ← 定义 input/output schema
├── validators.ts      ← 定义业务校验器（如 validateTradingHours）
├── routing-rules.ts   ← 定义路由规则
├── handler.ts         ← 实现 ThreePhaseToolHandler 接口
├── tool.ts            ← DSH 工具定义
└── index.ts           ← 导出
```

### 示例：handler.ts

```typescript
import {
  ThreePhaseToolHandler,
  ValidationResult,
  ErrorType,
} from '@pi-investment/core';

export const portfolioTradeHandler: ThreePhaseToolHandler = {
  name: 'portfolio_trade',

  // Phase 1: 入参校验（具体实现）
  inputValidator: {
    validate(args): ValidationResult {
      // 检查 symbol
      if (!args.symbol || !/^\d{6}$/.test(args.symbol)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'symbol',
          issue: 'symbol 必须是6位数字股票代码',
          received: args.symbol,
          expected: '6位数字',
          example: '600519',
          guide: '请修正 symbol。正确格式：6位数字',
          commonMistakes: [
            '不要包含交易所前缀（如 SH600519）',
            '不要使用股票名称（如 贵州茅台）',
          ],
        };
      }

      // 检查 quantity
      if (!args.quantity || args.quantity % 100 !== 0) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'quantity',
          issue: '数量必须是100的正整数倍',
          received: args.quantity,
          expected: '100的正整数倍',
          example: '200',
        };
      }

      return { success: true };
    },
  },

  // Phase 2: 任务执行（具体实现）
  taskExecutor: {
    async execute(args, context) {
      // 执行交易
      const result = await qv2.executeTrade({
        action: args.action,
        symbol: args.symbol,
        quantity: args.quantity,
        price: args.price,
        account_name: args.account_name || 'agent_virtual',
      });
      return result;
    },

    validateBusinessRules(args, context): ValidationResult {
      // 交易时段检查
      const now = new Date();
      const hours = now.getHours();
      const minutes = now.getMinutes();
      const time = hours * 100 + minutes;

      const isTradingHours =
        (time >= 930 && time <= 1130) || (time >= 1300 && time <= 1500);

      if (!isTradingHours) {
        return {
          success: false,
          errorType: ErrorType.BUSINESS_REJECTION,
          rule: '交易时段限制',
          issue: '当前非交易时段（9:30-11:30, 13:00-15:00）',
          currentTime: now.toLocaleString('zh-CN'),
          guide: '交易时段外无法下单',
          solutions: [
            {
              approach: 'wait',
              description: '等待至下一交易时段',
            },
            {
              approach: 'use_alternative',
              tool: 'watch_manage',
              reason: '可以设置价格提醒，在交易时段自动通知',
              example: `watch_manage({ action: 'create', symbol: '${args.symbol}', condition: 'price<100' })`,
            },
          ],
        };
      }

      return { success: true };
    },
  },

  // Phase 3: 出参包装（具体实现）
  outputWrapper: {
    validate(data, context): ValidationResult {
      // 检查必需字段
      if (!data || !data.order_id) {
        return {
          success: false,
          errorType: ErrorType.OUTPUT_ERROR,
          issue: '后端数据结构异常',
          missingFields: [
            {
              field: 'order_id',
              description: '订单ID',
              impact: '无法追踪订单',
            },
          ],
        };
      }

      return { success: true, data };
    },

    getRoutingRules() {
      return [
        {
          from: 'portfolio_trade',
          condition: (err) => err.rule === '交易时段限制',
          to: 'watch_manage',
          reason: '非交易时段可以设置价格提醒',
          example: (context) =>
            `watch_manage({ action: 'create', symbol: '${context.symbol}', condition: 'price<100' })`,
        },
        {
          from: 'portfolio_trade',
          condition: (err) => err.rule === '资金充足性检查',
          to: 'position_list',
          reason: '资金不足时可以先查看持仓，考虑卖出释放资金',
          example: 'position_list() 然后选择盈利标的卖出',
        },
      ];
    },
  },
};
```

### 示例：tool.ts（DSH 集成）

```typescript
import { defineTool } from '@deepseek-ai/dsh-tools';
import { executeThreePhaseFlow } from '@pi-investment/core';
import { portfolioTradeHandler } from './handler';

export const portfolioTradeTool = defineTool({
  name: 'portfolio_trade',
  description: '执行虚拟仓买卖委托',
  parameters: {
    action: {
      type: 'string',
      description: 'BUY：买入；SELL：卖出',
      enum: ['BUY', 'SELL'],
    },
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，如 600519',
    },
    quantity: {
      type: 'integer',
      description: '交易数量（股），买入必须是100的整数倍',
    },
  },
  output: {
    schema: {
      type: 'object',
      properties: {
        order_id: { type: 'string' },
        status: { type: 'string' },
      },
    },
  },
  execute: async (args) => {
    // 使用三段式框架执行
    const result = await executeThreePhaseFlow(portfolioTradeHandler, args);

    if (!result.success) {
      // 返回友好的错误信息
      const errorMsg = formatErrorMessage(result.error!);
      if (result.routing?.shouldRoute) {
        return {
          success: false,
          error: errorMsg,
          suggestion: `推荐使用: ${result.routing.recommendedTool}`,
          example: result.routing.example,
        };
      }
      throw new Error(errorMsg);
    }

    return result.data;
  },
});

function formatErrorMessage(error: any): string {
  let msg = error.issue || '未知错误';
  if (error.guide) msg += `\n💡 ${error.guide}`;
  if (error.example) msg += `\n示例: ${error.example}`;
  return msg;
}
```

---

## 📊 架构对比

### Before（错误的架构）

```
packages/core/src/
├── error-handling.ts      ← ❌ 包含具体的校验逻辑实现
├── business-validators.ts ← ❌ 包含具体的业务校验器
├── routing-rules.ts       ← ❌ 包含具体的路由规则
├── schema-templates.ts    ← ❌ 包含具体的 schema 模板
└── index.ts
```

**问题**：
- core 包变成了"实现库"
- 各工具无法定义自己的校验逻辑
- 违反了"只定义规范"的原则

### After（正确的架构）

```
packages/core/src/
├── types.ts    ← ✅ 只定义类型和接口
└── index.ts    ← ✅ 导出类型 + 通用辅助函数

packages/trading/src/tools/PortfolioTradeTool/
├── schema.ts          ← ✅ 工具自己的 schema
├── validators.ts      ← ✅ 工具自己的校验器
├── routing-rules.ts   ← ✅ 工具自己的路由规则
├── handler.ts         ← ✅ 实现 ThreePhaseToolHandler
└── tool.ts            ← ✅ DSH 工具定义
```

**优势**：
- core 包只定义规范
- 各工具完全自主实现
- 符合"接口与实现分离"原则

---

## ✅ 核心原则总结

### Core 包的职责

1. **定义类型** - TypeScript 接口和类型
2. **定义契约** - 工具必须实现的接口
3. **提供框架** - 通用的流程控制逻辑

### Core 包不应该做什么

1. ❌ 不实现具体的校验器
2. ❌ 不定义具体的路由规则
3. ❌ 不提供具体的 schema 模板
4. ❌ 不包含任何业务逻辑

### 各工具的职责

1. **实现接口** - 根据 core 定义的接口实现自己的逻辑
2. **定义规则** - 定义自己的校验规则、路由规则
3. **处理业务** - 实现具体的业务逻辑

---

## 🎓 设计理念

**"core 定义 what，工具实现 how"**

- `core` 定义：工具应该有哪些阶段？每个阶段的输入输出是什么？
- `工具` 实现：每个阶段具体怎么做校验？怎么执行业务？怎么处理错误？

这样的架构：
- ✅ 各工具完全独立
- ✅ 可以灵活定制
- ✅ 符合开闭原则
- ✅ 易于测试和维护

---

## 📋 下一步：Phase 2

现在 core 包的架构已经正确，可以开始 Phase 2：
- 重构 m4_circuit_breaker_check 工具（已修复 API 调用错误）
- 重构 portfolio_trade 工具
- 重构 watch_manage 工具
- 其他高优先级工具...

---

**完成时间**: 2026-08-28  
**审查状态**: 架构已修正，待用户确认  
**核心文件**: `packages/core/src/types.ts`, `packages/core/src/index.ts`
