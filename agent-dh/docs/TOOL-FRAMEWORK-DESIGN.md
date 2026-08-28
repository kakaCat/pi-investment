# Agent-DH 工具框架设计方案

**设计理念：** 参考三层架构（描述层/执行层/展示层）+ 入参校验提前 + 出参统一包装

**参考文章：**
- https://juejin.cn/post/7670582248600567818 （三层架构）
- https://juejin.cn/post/7667795867840380966 （入参校验、出参包装）

---

## 📐 核心设计理念

### 1. 三层分离架构

```
packages/trading/src/tools/PortfolioTradeTool/
├── prompt.ts              ← 描述层：给模型看的提示词（独立资产）
├── schema.ts              ← Schema 层：参数定义与校验规则
├── preconditions.ts       ← 前置条件（可选）
├── PortfolioTradeTool.ts  ← 执行层：业务逻辑
├── render.tsx             ← 展示层：结果渲染（可选）
└── index.ts               ← 导出层
```

**优势：**
- 🎯 **提示词独立** - 便于优化和 A/B 测试，不影响代码
- 🎯 **Schema 复用** - 前端/后端/文档共用一套定义
- 🎯 **逻辑清晰** - 业务代码只关注核心逻辑
- 🎯 **易于测试** - 每层可独立测试

### 2. 统一的抽象基类

所有工具继承 `BaseTool<TParams, TResult>`：

```typescript
export abstract class BaseTool<TParams, TResult> {
  // 子类必须实现
  protected abstract readonly metadata: ToolMetadata;
  protected abstract readonly prompt: ToolPrompt;
  protected abstract readonly schema: ToolSchema<TParams>;
  protected abstract execute(ctx: ToolContext<TParams>): Promise<TResult>;
  
  // 可选钩子
  protected async postProcess(ctx, result): Promise<TResult> { ... }
  protected async onError(ctx, error): Promise<void> { ... }
  
  // 框架统一调用
  async call(args: TParams): Promise<ToolResponse<TResult>> { ... }
}
```

**自动提供：**
- ✅ 参数校验（基于 schema.parameters）
- ✅ 前置条件检查
- ✅ 错误捕获与包装
- ✅ 调用日志记录
- ✅ 链路追踪（executionId）
- ✅ 耗时统计

### 3. 统一的响应格式

```typescript
interface ToolResponse<T> {
  success: boolean;
  data?: T;                  // 成功时的数据
  error?: {                  // 失败时的错误
    code: string;
    message: string;
    details?: any;
  };
  meta: {
    toolName: string;
    duration: number;        // 执行耗时（ms）
    timestamp: string;
    executionId: string;     // 链路追踪ID
  };
  blocked?: boolean;         // 业务拒绝标记
  reason?: string;           // 拒绝原因
}
```

---

## 🏗️ 完整实现示例

以下是 `PortfolioTradeTool` 的完整实现，展示如何使用框架。

### 文件 1: prompt.ts（描述层）

```typescript
// packages/trading/src/tools/PortfolioTradeTool/prompt.ts

import type { ToolPrompt } from '@pi-investment/tool-framework';

export const portfolioTradePrompt: ToolPrompt = {
  description: 
    '执行虚拟仓买卖委托（写操作，立即成交并改变持仓）。' +
    '执行前应先确认：用 account_info 查可用资金、用 position_list 查可卖数量、用 risk_controller 计算建议仓位。',

  useCases: [
    '买入看好的标的建仓',
    '卖出持仓止盈或止损',
    '调仓换股',
    '清仓离场',
  ],

  examples: [
    {
      title: '买入贵州茅台',
      params: {
        action: 'BUY',
        symbol: '600519',
        quantity: 100,
        reason: 'R-001 买入前确认：资金充足、仓位合规',
      },
      expectedResult: '订单ID: xxx, 成交价: 1850.00',
    },
  ],

  notes: [
    '⚠️  宪法第1条：仅 A股交易日 9:30-11:30、13:00-15:00 可执行买卖委托',
    '⚠️  R-008：下单前必须检索历史经验',
    '💡 大额订单考虑用 algo_execute 拆单',
  ],

  relatedTools: ['account_info', 'position_list', 'risk_controller'],
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
    // ... 其他参数
  },

  output: {
    schema: { /* JSON Schema */ },
    render: (args, value) => [{
      type: 'text',
      text: `✅ ${value.action} ${value.symbol} x${value.quantity}股`,
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
import { portfolioTradePrompt } from './prompt';
import { portfolioTradeSchema, PortfolioTradeParams, PortfolioTradeResult } from './schema';
import { tradingHoursPrecondition } from './preconditions';

export class PortfolioTradeTool extends BaseTool<PortfolioTradeParams, PortfolioTradeResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'portfolio_trade',
    category: 'trading',
    version: '2.0.0',
    riskLevel: 'high',
    dependencies: ['account_info', 'position_list'],
    tags: ['trade', 'buy', 'sell'],
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

    // 1. 领域检查（框架已完成参数校验和前置条件）
    if (args.action === 'BUY') {
      await this.checkCircuitBreaker();
      await this.checkRegimeLimit(args);
      await this.checkManipulation(args);
    }

    // 2. 执行交易
    const result = await this.qv2.executeTrade({
      action: args.action,
      symbol: args.symbol,
      quantity: args.quantity,
      price: args.price,
      account_name: args.account_name || 'agent_virtual',
    });

    return result;
  }

  /**
   * 后置处理：信号追踪、滑点记录
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
   * 业务拒绝辅助方法（框架提供）
   */
  private async checkCircuitBreaker(): Promise<void> {
    const status = await this.getCircuitBreakerStatus();
    if (status.active) {
      this.blocked(`熔断激活：60日回撤 ${status.drawdown}%，禁止新开仓`);
    }
  }

  // ... 其他业务方法
}
```

### 文件 5: index.ts（导出层）

```typescript
// packages/trading/src/tools/PortfolioTradeTool/index.ts

export { PortfolioTradeTool } from './PortfolioTradeTool';
export { portfolioTradePrompt } from './prompt';
export { portfolioTradeSchema } from './schema';
export type { PortfolioTradeParams, PortfolioTradeResult } from './schema';
```

---

## 🔧 核心框架实现

### 1. BaseTool 抽象基类

```typescript
// packages/tool-framework/src/BaseTool.ts

export abstract class BaseTool<TParams = any, TResult = any> {
  // 子类必须实现的抽象属性
  protected abstract readonly metadata: ToolMetadata;
  protected abstract readonly prompt: ToolPrompt;
  protected abstract readonly schema: ToolSchema<TParams>;
  
  // 子类必须实现的核心方法
  protected abstract execute(ctx: ToolContext<TParams>): Promise<TResult>;
  
  // 可选钩子
  protected async postProcess(ctx: ToolContext<TParams>, result: TResult): Promise<TResult> {
    return result;
  }
  
  protected async onError(ctx: ToolContext<TParams>, error: Error): Promise<void> {
    console.error(`[${this.metadata.name}] Error:`, error);
  }

  /**
   * 统一调用入口（框架层）
   * 自动完成：参数校验 → 前置检查 → 执行 → 后置处理 → 日志记录
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
      // 1. 参数校验（自动）
      this.validateParameters(args);

      // 2. 前置条件检查（自动）
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
   * 参数校验（基于 schema.parameters）
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
   * 业务拒绝辅助方法
   */
  protected blocked(reason: string): never {
    const error: any = new Error(reason);
    error.blocked = true;
    throw error;
  }
}
```

### 2. 统一参数校验

```typescript
// packages/tool-framework/src/validation.ts

export interface ValidationRule {
  field: string;
  required?: boolean;
  validator?: (value: any) => boolean;
  errorMessage?: string;
}

export function validateParams(args: any, rules: ValidationRule[]): void {
  const errors: string[] = [];
  
  for (const rule of rules) {
    const value = args?.[rule.field];
    
    // 必填校验
    if (rule.required && (value === undefined || value === null || value === '')) {
      errors.push(`${rule.field} 是必填参数`);
      continue;
    }
    
    // 跳过未提供的可选参数
    if (value === undefined || value === null) continue;
    
    // 自定义校验
    if (rule.validator && !rule.validator(value)) {
      errors.push(rule.errorMessage || `${rule.field} 格式不正确`);
    }
  }
  
  if (errors.length > 0) {
    throw new Error(`参数校验失败：${errors.join('；')}`);
  }
}

/**
 * 常用校验器
 */
export const validators = {
  isStockCode: (value: string) => /^\d{6}$/.test(value),
  isDate: (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value),
  isMultipleOf: (multiple: number) => (value: number) => 
    Number.isInteger(value) && value > 0 && value % multiple === 0,
  isOneOf: (values: any[]) => (value: any) => values.includes(value),
};
```

---

## 📊 工具注册与管理

### 1. 插件中注册工具

```typescript
// packages/trading/src/index.ts

export default class TradingPlugin extends Service {
  private registerTools() {
    const { ctx } = this;

    // 创建工具实例
    const portfolioTradeTool = new PortfolioTradeTool(this.qv2, this.osMemory);

    // 转换为 DSH Tool 格式并注册
    ctx.tools.register(defineTool({
      name: portfolioTradeTool.getMetadata().name,
      description: portfolioTradeTool.getPrompt().description,
      parameters: portfolioTradeTool.getSchema().parameters,
      output: portfolioTradeTool.getSchema().output,
      timeoutMs: 10000,
      
      execute: async (args: any) => {
        const response = await portfolioTradeTool.call(args);
        
        // 业务拒绝：返回特殊格式
        if (response.blocked) {
          return {
            success: false,
            blocked: true,
            reason: response.reason,
          };
        }
        
        // 成功：返回 data
        if (response.success) {
          return response.data;
        }
        
        // 系统错误：抛出
        throw new Error(response.error?.message || '工具执行失败');
      },
    } as any));
  }
}
```

### 2. 工具注册中心

```typescript
// packages/tool-framework/src/ToolRegistry.ts

export class ToolRegistry {
  private static instance: ToolRegistry;
  private tools: Map<string, BaseTool> = new Map();

  static getInstance(): ToolRegistry {
    if (!ToolRegistry.instance) {
      ToolRegistry.instance = new ToolRegistry();
    }
    return ToolRegistry.instance;
  }

  register(tool: BaseTool): void {
    this.tools.set(tool.getMetadata().name, tool);
  }

  get(name: string): BaseTool | undefined {
    return this.tools.get(name);
  }

  list(): ToolMetadata[] {
    return Array.from(this.tools.values()).map(t => t.getMetadata());
  }

  /**
   * 分析工具依赖
   */
  analyzeDependencies(toolName: string): {
    directDeps: string[];
    allDeps: string[];
    dependents: string[];
  } {
    // 实现依赖分析逻辑
  }
}
```

---

## 📈 监控与统计

### 工具调用分析器

```typescript
// packages/tool-framework/src/ToolAnalytics.ts

export class ToolAnalytics {
  /**
   * 统计工具调用情况
   */
  async getToolCallStats(options: {
    toolName?: string;
    startDate?: string;
    endDate?: string;
  }): Promise<ToolCallStats> {
    // 从 OsMemory 读取 tool:calls 日志
    // 统计成功率、平均耗时、P50/P95/P99、错误分布
  }

  /**
   * 生成工具质量报告
   */
  async generateQualityReport(days: number = 7): Promise<ToolQualityReport> {
    // 计算每个工具的质量评分（0-100）
    // 评分 = 可用性(70%) + 性能(30%)
    // 可用性 = 成功率
    // 性能 = 基于 P95 耗时打分
  }
}
```

---

## 🚀 迁移指南

### 迁移步骤

**第1步：创建 tool-framework 包**

```bash
mkdir -p packages/tool-framework/src
cd packages/tool-framework
pnpm init
```

**第2步：实现核心抽象**

按顺序实现：
1. `types.ts` - 类型定义
2. `validation.ts` - 参数校验
3. `BaseTool.ts` - 抽象基类
4. `ToolRegistry.ts` - 注册中心
5. `ToolAnalytics.ts` - 统计分析

**第3步：迁移 P0 工具（验证效果）**

优先迁移 3 个工具验证框架：
1. **portfolio_trade** - 核心交易工具
2. **watch_manage** - 已有良好校验
3. **signal_track** - 已有良好校验

**第4步：渐进式迁移**

- 新工具：直接使用 BaseTool
- 老工具：保持现状，逐步迁移
- 兼容性：通过适配器对接 DSH 框架

**第5步：监控验证**

- 对比新旧实现的行为差异
- 监控工具调用日志
- 逐步替换生产环境

### 迁移优先级清单

| 工具 | 分类 | 风险 | 优先级 | 备注 |
|------|------|------|--------|------|
| portfolio_trade | trading | high | P0 | 核心交易 |
| watch_manage | intelligence | low | P0 | 已有良好校验 |
| signal_track | intelligence | low | P0 | 已有良好校验 |
| data_fetch_quote | data | low | P1 | 高频查询 |
| account_info | data | low | P1 | 高频查询 |
| position_list | data | low | P1 | 高频查询 |

---

## ✅ 框架优势总结

### 1. 统一规范
- ✅ 所有工具遵循统一的三层架构
- ✅ 统一的参数校验、出参格式、错误处理
- ✅ 代码风格一致，易于维护

### 2. 职责分离
- ✅ 提示词独立维护（prompt.ts）
- ✅ Schema 独立定义（schema.ts）
- ✅ 执行逻辑清晰（ToolClass）

### 3. 可观测性
- ✅ 自动记录所有工具调用日志
- ✅ 链路追踪（executionId + parentExecutionId）
- ✅ 质量监控（成功率、耗时、错误分布）

### 4. 扩展性
- ✅ 基于继承的扩展模型
- ✅ 前置条件、后置处理钩子
- ✅ 工具注册中心、依赖分析

### 5. 向后兼容
- ✅ 渐进式迁移，老工具继续工作
- ✅ 适配器模式对接 DSH 框架

---

## 📝 下一步行动

1. ✅ 阅读并理解本设计文档
2. 🔥 **创建 `packages/tool-framework` 包**
3. 🔥 **实现核心抽象（BaseTool + validation）**
4. 🔥 **迁移 3 个 P0 工具验证效果**
5. 🚀 逐步迁移其他工具
6. 🎯 建立监控与质量体系

---

**文档版本：** v1.0  
**创建时间：** 2026-08-27T17:32:48.169Z  
**维护者：** PI Investment Agent Team
