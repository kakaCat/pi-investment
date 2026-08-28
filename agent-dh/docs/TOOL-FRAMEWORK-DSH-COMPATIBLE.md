# Agent-DH 工具框架设计方案（DSH 兼容版）

**设计理念：** 完全兼容 DSH 框架 + 三层架构 + 入参校验提前 + 出参包装

**参考文章：**
- https://juejin.cn/post/7675595046833864713 （DSH 框架规范）
- https://juejin.cn/post/7670582248600567818 （三层架构）
- https://juejin.cn/post/7667795867840380966 （入参校验、出参包装）

---

## 🎯 核心设计原则

### 1. 完全兼容 DSH 框架

**DSH defineTool 规范：**
```typescript
ctx.tools.register(defineTool({
  name: string;                    // 工具名称
  description: string;             // 工具描述
  parameters: ParameterSchemaSpec; // 参数 Schema
  output: {
    schema: JsonSchema;            // 输出 Schema
    render?: (args, value) => ToolRenderResult[];  // 可选渲染函数
  };
  timeoutMs?: number;              // 超时时间
  execute: (args: any) => Promise<any>;  // 执行函数
}));
```

### 2. 三层架构 + BaseTool 抽象

我们的框架在**不破坏 DSH 规范**的前提下，提供：
- ✅ 三层文件组织（prompt/schema/tool）
- ✅ BaseTool 抽象类（统一流程）
- ✅ 参数校验提前（execute 前）
- ✅ 出参统一包装
- ✅ 通过适配器转换为 DSH 格式

**关键：** BaseTool 是**内部抽象**，最终通过适配器转换为 DSH 的 `defineTool` 格式注册。

---

## 🏗️ 完整架构设计

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    DSH Framework                        │
│              ctx.tools.register(defineTool)             │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ 适配器转换
                       ↓
┌─────────────────────────────────────────────────────────┐
│              Tool Framework (内部抽象)                   │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  BaseTool    │  │  validators  │  │ ToolRegistry │ │
│  │  (抽象基类)  │  │  (校验器)    │  │  (注册中心)  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │              具体工具实现                         │  │
│  │  PortfolioTradeTool extends BaseTool             │  │
│  │    - prompt.ts    (描述层)                        │  │
│  │    - schema.ts    (Schema层)                      │  │
│  │    - tool.ts      (执行层)                        │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 文件组织结构

```
packages/trading/src/tools/PortfolioTradeTool/
├── prompt.ts              ← 描述层：给模型看的提示词
├── schema.ts              ← Schema 层：参数定义与校验规则
├── preconditions.ts       ← 前置条件（可选）
├── PortfolioTradeTool.ts  ← 执行层：业务逻辑（继承 BaseTool）
└── index.ts               ← 导出 + DSH 适配器
```

---

## 🔧 核心实现

### 1. BaseTool 抽象基类

```typescript
// packages/tool-framework/src/BaseTool.ts

import { v4 as uuidv4 } from 'uuid';
import { validateParams } from './validation';

/**
 * 工具抽象基类
 * 提供统一的流程控制，但最终通过适配器转为 DSH 格式
 */
export abstract class BaseTool<TParams = any, TResult = any> {
  // 子类必须实现的抽象属性
  protected abstract readonly metadata: ToolMetadata;
  protected abstract readonly prompt: ToolPrompt;
  protected abstract readonly schema: ToolSchema<TParams>;
  protected preconditions?: ToolPrecondition[] = [];

  /**
   * 核心执行方法（子类实现业务逻辑）
   */
  protected abstract execute(ctx: ToolContext<TParams>): Promise<TResult>;

  /**
   * 后置处理钩子（可选）
   */
  protected async postProcess(
    ctx: ToolContext<TParams>,
    result: TResult
  ): Promise<TResult> {
    return result;
  }

  /**
   * 错误处理钩子（可选）
   */
  protected async onError(ctx: ToolContext<TParams>, error: Error): Promise<void> {
    console.error(`[${this.metadata.name}] Error:`, error);
  }

  /**
   * 统一调用入口
   * 注意：这个方法不直接被 DSH 调用，而是通过适配器包装
   */
  async call(args: TParams, context?: Partial<ToolContext>): Promise<ToolResponse<TResult>> {
    const executionId = uuidv4();
    const startTime = Date.now();

    const ctx: ToolContext<TParams> = {
      args,
      trace: {
        executionId,
        parentExecutionId: context?.trace?.executionId,
        depth: (context?.trace?.depth ?? 0) + 1,
      },
    };

    try {
      // 1. 参数校验（基于 schema.parameters）
      this.validateParameters(args);

      // 2. 前置条件检查
      await this.checkPreconditions(ctx);

      // 3. 执行业务逻辑
      let result = await this.execute(ctx);

      // 4. 后置处理
      result = await this.postProcess(ctx, result);

      // 5. 记录调用日志（异步，不阻塞）
      this.logToolCall(ctx, result, Date.now() - startTime).catch(console.warn);

      // 6. 返回统一响应
      return {
        success: true,
        data: result,
        meta: {
          toolName: this.metadata.name,
          duration: Date.now() - startTime,
          timestamp: new Date().toISOString(),
          executionId,
        },
      };
    } catch (error: any) {
      await this.onError(ctx, error);
      this.logToolCall(ctx, null, Date.now() - startTime, error).catch(console.warn);

      return {
        success: false,
        error: {
          code: error.code || 'INTERNAL_ERROR',
          message: error.message,
          details: error.details,
        },
        meta: {
          toolName: this.metadata.name,
          duration: Date.now() - startTime,
          timestamp: new Date().toISOString(),
          executionId,
        },
        blocked: error.blocked || false,
        reason: error.blocked ? error.message : undefined,
      };
    }
  }

  /**
   * 转换为 DSH defineTool 格式（适配器方法）
   */
  toDSHToolDefinition(): DSHToolDefinition {
    return {
      name: this.metadata.name,
      description: this.prompt.description,
      parameters: this.convertParametersToSchemaSpec(this.schema.parameters),
      output: this.schema.output,
      timeoutMs: this.metadata.timeoutMs || 10000,
      execute: async (args: any) => {
        // DSH 的 execute 函数
        const response = await this.call(args);
        
        // 业务拒绝：返回特殊格式（不抛异常）
        if (response.blocked) {
          return {
            success: false,
            blocked: true,
            reason: response.reason,
          };
        }
        
        // 成功：直接返回 data
        if (response.success) {
          return response.data;
        }
        
        // 系统错误：抛出（让 DSH 处理）
        throw new Error(response.error?.message || '工具执行失败');
      },
    };
  }

  /**
   * 参数校验
   */
  private validateParameters(args: TParams): void {
    const rules = Object.entries(this.schema.parameters).map(([field, def]) => ({
      field,
      required: def.required,
      validator: def.validator,
      errorMessage: def.errorMessage,
    }));

    validateParams(args, rules);
  }

  /**
   * 前置条件检查
   */
  private async checkPreconditions(ctx: ToolContext<TParams>): Promise<void> {
    if (!this.preconditions?.length) return;

    for (const precond of this.preconditions) {
      const passed = await precond.check(ctx);
      if (!passed) {
        throw new Error(`前置条件失败: ${precond.errorMessage}`);
      }
    }
  }

  /**
   * 转换为 DSH ParameterSchemaSpec
   */
  private convertParametersToSchemaSpec(params: Record<string, ParameterDefinition>): any {
    const schemaSpec: any = {};
    
    for (const [key, def] of Object.entries(params)) {
      schemaSpec[key] = {
        type: def.type,
        description: def.description,
        required: def.required,
        default: def.default,
        enum: def.enum,
      };
    }
    
    return schemaSpec;
  }

  /**
   * 业务拒绝辅助方法
   */
  protected blocked(reason: string): never {
    const error: any = new Error(reason);
    error.blocked = true;
    throw error;
  }

  /**
   * 记录调用日志（子类可覆盖）
   */
  protected async logToolCall(
    ctx: ToolContext<TParams>,
    result: TResult | null,
    duration: number,
    error?: Error
  ): Promise<void> {
    const log = {
      toolName: this.metadata.name,
      executionId: ctx.trace?.executionId,
      args: ctx.args,
      success: !error,
      duration,
      timestamp: new Date().toISOString(),
      error: error ? { message: error.message } : undefined,
    };

    // 默认实现：写入 OsMemory（子类可覆盖）
    await this.writeToMemory(log);
  }

  /**
   * 写入 OsMemory（子类可覆盖）
   */
  protected async writeToMemory(log: any): Promise<void> {
    // 默认空实现
  }
}
```

---

## 📝 完整实现示例

### 文件 1: prompt.ts（描述层）

```typescript
// packages/trading/src/tools/PortfolioTradeTool/prompt.ts

import type { ToolPrompt } from '@pi-investment/tool-framework';

export const portfolioTradePrompt: ToolPrompt = {
  description: 
    '执行虚拟仓买卖委托（写操作，立即成交并改变持仓）。' +
    '执行前应先确认：用 account_info 查可用资金、用 position_list 查可卖数量。',

  useCases: [
    '买入看好的标的建仓',
    '卖出持仓止盈或止损',
  ],

  examples: [
    {
      title: '买入贵州茅台',
      params: {
        action: 'BUY',
        symbol: '600519',
        quantity: 100,
      },
    },
  ],

  notes: [
    '⚠️  宪法第1条：仅 A股交易日 9:30-11:30、13:00-15:00 可执行买卖委托',
    '⚠️  买入前会自动检查：熔断状态、仓位上限、ST禁区',
  ],

  relatedTools: ['account_info', 'position_list'],
};
```

### 文件 2: schema.ts（Schema 层）

```typescript
// packages/trading/src/tools/PortfolioTradeTool/schema.ts

import type { ToolSchema } from '@pi-investment/tool-framework';
import { validators } from '@pi-investment/tool-framework';

export interface PortfolioTradeParams {
  action: 'BUY' | 'SELL';
  symbol: string;
  quantity: number;
  price?: number;
  reason?: string;
  account_name?: string;
}

export interface PortfolioTradeResult {
  order_id: string;
  action: string;
  symbol: string;
  quantity: number;
  price: number;
  amount: number;
  status: 'filled' | 'partial' | 'rejected';
  timestamp: string;
}

export const portfolioTradeSchema: ToolSchema<PortfolioTradeParams> = {
  parameters: {
    action: {
      type: 'string',
      description: 'BUY：买入；SELL：卖出',
      required: true,
      enum: ['BUY', 'SELL'],
    },
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，如 600519',
      required: true,
      validator: validators.isStockCode,
      errorMessage: 'symbol 必须是6位数字股票代码',
    },
    quantity: {
      type: 'integer',
      description: '交易数量（股），买入必须是100的整数倍',
      required: true,
      validator: validators.isMultipleOf(100),
      errorMessage: '数量必须是100的正整数倍',
    },
    price: {
      type: 'number',
      description: '委托价格（元）。不传则按市价成交',
      required: false,
    },
    reason: {
      type: 'string',
      description: '决策依据（强烈建议填写）',
      required: false,
    },
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      required: false,
      default: 'agent_virtual',
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        order_id: { type: 'string', description: '订单ID' },
        action: { type: 'string', description: '操作方向' },
        symbol: { type: 'string', description: '股票代码' },
        quantity: { type: 'integer', description: '成交数量' },
        price: { type: 'number', description: '成交价格' },
        amount: { type: 'number', description: '成交金额' },
        status: { type: 'string', description: '状态' },
        timestamp: { type: 'string', description: '成交时间' },
      },
      additionalProperties: true,
    },
    render: (_args: any, value: any) => [{
      type: 'text',
      text: `✅ ${value.action} ${value.symbol} x${value.quantity}股 @ ¥${value.price}\n` +
            `订单ID: ${value.order_id}\n状态: ${value.status}`,
    }],
  },
};
```

### 文件 3: preconditions.ts（前置条件）

```typescript
// packages/trading/src/tools/PortfolioTradeTool/preconditions.ts

import type { ToolPrecondition } from '@pi-investment/tool-framework';
import { assertTradingHours } from '../../utils/trading-hours';

export const tradingHoursPrecondition: ToolPrecondition = {
  name: 'trading_hours',
  check: () => {
    try {
      assertTradingHours();
      return true;
    } catch {
      return false;
    }
  },
  errorMessage: '非交易时段禁止下单（宪法第1条）',
};
```

### 文件 4: PortfolioTradeTool.ts（执行层）

```typescript
// packages/trading/src/tools/PortfolioTradeTool/PortfolioTradeTool.ts

import { BaseTool, ToolContext, ToolMetadata } from '@pi-investment/tool-framework';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';
import { portfolioTradePrompt } from './prompt';
import { portfolioTradeSchema, PortfolioTradeParams, PortfolioTradeResult } from './schema';
import { tradingHoursPrecondition } from './preconditions';

export class PortfolioTradeTool extends BaseTool<PortfolioTradeParams, PortfolioTradeResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'portfolio_trade',
    category: 'trading',
    version: '2.0.0',
    riskLevel: 'high',
    timeoutMs: 10000,
  };

  protected readonly prompt = portfolioTradePrompt;
  protected readonly schema = portfolioTradeSchema;
  protected readonly preconditions = [tradingHoursPrecondition];

  constructor(
    private qv2: QuantsysV2Client,
    private osMemory: OsMemoryStore
  ) {
    super();
  }

  /**
   * 核心执行逻辑（只关注业务）
   */
  protected async execute(ctx: ToolContext<PortfolioTradeParams>): Promise<PortfolioTradeResult> {
    const { args } = ctx;

    // 业务检查（框架已完成参数校验和前置条件）
    if (args.action === 'BUY') {
      await this.checkCircuitBreaker();
      await this.checkRegimeLimit(args);
      await this.checkManipulation(args);
    }

    // 执行交易
    const result = await this.qv2.executeTrade({
      action: args.action,
      symbol: args.symbol,
      quantity: args.quantity,
      price: args.price,
      account_name: args.account_name || 'agent_virtual',
      order_type: args.price ? 'limit' : 'market',
      reason: args.reason,
    });

    return result;
  }

  /**
   * 后置处理
   */
  protected async postProcess(
    ctx: ToolContext<PortfolioTradeParams>,
    result: PortfolioTradeResult
  ): Promise<PortfolioTradeResult> {
    // 买入成交后自动记录信号
    if (ctx.args.action === 'BUY' && result.status === 'filled') {
      await this.recordSignal(ctx.args, result).catch(console.warn);
    }
    return result;
  }

  /**
   * 业务检查方法
   */
  private async checkCircuitBreaker(): Promise<void> {
    const status = await this.getCircuitBreakerStatus();
    if (status.active) {
      this.blocked(`熔断激活：禁止新开仓`);
    }
  }

  private async checkRegimeLimit(args: PortfolioTradeParams): Promise<void> {
    // 实现省略
  }

  private async checkManipulation(args: PortfolioTradeParams): Promise<void> {
    if (args.symbol.includes('ST')) {
      this.blocked('ST 禁区：ST/*ST 股票禁止买入');
    }
  }

  private async getCircuitBreakerStatus(): Promise<any> {
    // 实现省略
    return { active: false };
  }

  private async recordSignal(args: PortfolioTradeParams, result: PortfolioTradeResult): Promise<void> {
    // 实现省略
  }

  /**
   * 覆盖日志记录，写入 OsMemory
   */
  protected async writeToMemory(log: any): Promise<void> {
    await this.osMemory.write({
      title: `tool_call: ${log.toolName}`,
      content: JSON.stringify(log),
      namespace: 'tool:calls',
      tags: ['tool_call', log.toolName],
    });
  }
}
```

### 文件 5: index.ts（导出 + DSH 适配器）

```typescript
// packages/trading/src/tools/PortfolioTradeTool/index.ts

import { defineTool } from '@deepseek-ai/dsh-tools';
import { PortfolioTradeTool } from './PortfolioTradeTool';

/**
 * 工具实例导出
 */
export { PortfolioTradeTool } from './PortfolioTradeTool';
export { portfolioTradePrompt } from './prompt';
export { portfolioTradeSchema } from './schema';
export type { PortfolioTradeParams, PortfolioTradeResult } from './schema';

/**
 * DSH 适配器：将 BaseTool 转换为 DSH defineTool 格式
 */
export function createPortfolioTradeTool(qv2: any, osMemory: any) {
  const tool = new PortfolioTradeTool(qv2, osMemory);
  
  // 方式1：使用 toDSHToolDefinition() 方法
  return defineTool(tool.toDSHToolDefinition() as any);
  
  // 方式2：手动构建（更灵活）
  // return defineTool({
  //   name: tool.getMetadata().name,
  //   description: tool.getPrompt().description,
  //   parameters: ...,
  //   output: ...,
  //   execute: async (args) => {
  //     const response = await tool.call(args);
  //     if (response.blocked) {
  //       return { success: false, blocked: true, reason: response.reason };
  //     }
  //     if (response.success) return response.data;
  //     throw new Error(response.error?.message || '执行失败');
  //   },
  // } as any);
}
```

---

## 🔌 插件注册（完全兼容 DSH）

```typescript
// packages/trading/src/index.ts

import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';
import { createPortfolioTradeTool } from './tools/PortfolioTradeTool';

export default class TradingPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;
  private osMemory: OsMemoryStore;

  constructor(ctx: Context, config: any) {
    super(ctx, 'trading');

    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });

    this.osMemory = new OsMemoryStore({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
    });

    this.registerTools();
  }

  private registerTools() {
    const { ctx } = this;

    // 使用适配器创建 DSH 工具并注册
    ctx.tools.register(createPortfolioTradeTool(this.qv2, this.osMemory));
    
    // 其他工具...
  }
}
```

---

## 📊 关键优势

### 1. 完全兼容 DSH ✅
- 最终调用 `defineTool` 注册到 DSH 框架
- 遵循 DSH 的 `execute` 签名
- 支持 DSH 的 `output.render` 功能
- 不破坏任何 DSH 原有机制

### 2. 三层架构 ✅
- **描述层**（prompt.ts）：提示词独立维护
- **Schema 层**（schema.ts）：参数定义 + 校验规则
- **执行层**（tool.ts）：业务逻辑清晰

### 3. 统一流程 ✅
- 参数校验提前（execute 前）
- 前置条件检查
- 后置处理钩子
- 统一错误处理
- 调用日志记录

### 4. 渐进式迁移 ✅
- 老工具：继续直接用 `defineTool`
- 新工具：使用 `BaseTool + 适配器`
- 可以混合使用，互不影响

---

## 🚀 迁移步骤

### 第1步：创建 tool-framework 包

```bash
mkdir -p packages/tool-framework/src
cd packages/tool-framework
pnpm init
```

**实现文件：**
1. `types.ts` - 类型定义
2. `validation.ts` - 参数校验
3. `BaseTool.ts` - 抽象基类（含 DSH 适配器）
4. `index.ts` - 统一导出

### 第2步：迁移 1 个工具验证

选择 **watch_manage**（最简单）：

**Before（直接 defineTool）：**
```typescript
ctx.tools.register(defineTool({
  name: 'watch_manage',
  description: '...',
  parameters: { ... },
  execute: async (args) => {
    // 手工参数校验
    if (action === 'create') {
      const missing = [];
      if (!name) missing.push('name');
      // ...
    }
    return qv2.manageWatchRule(args);
  },
}));
```

**After（BaseTool + 适配器）：**
```typescript
// 1. 创建工具类
class WatchManageTool extends BaseTool {
  protected execute(ctx) {
    // 只写业务逻辑，框架已完成参数校验
    return this.qv2.manageWatchRule(ctx.args);
  }
}

// 2. 通过适配器注册
ctx.tools.register(createWatchManageTool(qv2));
```

### 第3步：对比验证

- ✅ 功能一致性：新旧实现行为完全一致
- ✅ 性能：适配器开销可忽略（<1ms）
- ✅ 错误处理：业务拒绝、系统错误都正确处理

### 第4步：逐步迁移其他工具

优先级：
1. **watch_manage** - 最简单，验证框架
2. **signal_track** - 已有良好校验
3. **portfolio_trade** - 核心交易工具
4. 其他工具...

---

## 📝 总结

### 设计亮点

1. **完全兼容 DSH** - 通过适配器模式无缝集成
2. **三层架构** - 提示词/Schema/逻辑分离
3. **统一流程** - 参数校验、前置检查、后置处理自动化
4. **渐进迁移** - 新老工具可以共存
5. **向后兼容** - 不破坏现有代码

### 实施路径

- **Week 1**：创建 tool-framework 包 + 迁移 watch_manage 验证
- **Week 2**：迁移 signal_track + portfolio_trade
- **Week 3**：迁移其他高频工具
- **Week 4**：监控统计 + 质量报告

---

**文档版本：** v2.0 (DSH Compatible)  
**创建时间：** 2026-08-28T02:20:22.880Z  
**维护者：** PI Investment Agent Team
