# Agent-DH 工具框架设计（简化版 + DSH 兼容）

**设计理念：** DSH 兼容 + 三层架构简化 + 入参校验提前 + 出参包装 + render 展示

---

## 🎯 核心改进点

### 1. 简化文件结构（3个文件）

**Before（复杂）：**
```
PortfolioTradeTool/
├── prompt.ts          ← 描述层
├── schema.ts          ← Schema 层
├── preconditions.ts   ← 前置条件（单独文件）
├── PortfolioTradeTool.ts  ← 执行层
└── index.ts           ← 导出层
```

**After（简化）：**
```
PortfolioTradeTool/
├── prompt.ts          ← 描述层：提示词 + Schema + 前置条件
├── PortfolioTradeTool.ts  ← 执行层：继承 BaseTool
└── index.ts           ← 适配器：转为 DSH 格式
```

### 2. render 函数位置

**render 函数在 prompt.ts 的 output 定义中：**
```typescript
export const portfolioTradePrompt = {
  // ...
  output: {
    schema: { /* JSON Schema */ },
    render: (args, value) => [{     // ← render 在这里
      type: 'text',
      text: `✅ ${value.action} ${value.symbol}`,
    }],
  },
};
```

---

## 📁 完整实现示例

### 文件 1: prompt.ts（描述层 + Schema + render）

```typescript
// packages/trading/src/tools/PortfolioTradeTool/prompt.ts

import type { ToolPrompt, ToolPrecondition } from '@pi-investment/tool-framework';
import { validators } from '@pi-investment/tool-framework';
import { assertTradingHours } from '../../utils/trading-hours';

/**
 * 参数类型定义
 */
export interface PortfolioTradeParams {
  action: 'BUY' | 'SELL';
  symbol: string;
  quantity: number;
  price?: number;
  reason?: string;
  account_name?: string;
}

/**
 * 返回结果类型定义
 */
export interface PortfolioTradeResult {
  order_id: string;
  action: string;
  symbol: string;
  quantity: number;
  price: number;
  amount: number;
  status: 'filled' | 'partial' | 'rejected';
  timestamp: string;
  slippage?: {
    decision_price: number;
    fill_price: number;
    slippage_pct: number;
  };
}

/**
 * 工具定义（提示词 + Schema + render）
 */
export const portfolioTradePrompt: ToolPrompt<PortfolioTradeParams, PortfolioTradeResult> = {
  // ========== 描述层 ==========
  description: 
    '执行虚拟仓买卖委托（写操作，立即成交并改变持仓）。' +
    '执行前应先确认：用 account_info 查可用资金、用 position_list 查可卖数量。',

  useCases: [
    '买入看好的标的建仓',
    '卖出持仓止盈或止损',
    '调仓换股',
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
      expectedResult: '订单ID: xxx, 成交价: 1850.00, 状态: filled',
    },
  ],

  notes: [
    '⚠️  宪法第1条：仅 A股交易日 9:30-11:30、13:00-15:00 可执行买卖委托',
    '⚠️  R-008：下单前必须检索历史经验',
    '⚠️  买入前会自动检查：熔断状态、仓位上限、ST禁区',
  ],

  relatedTools: ['account_info', 'position_list', 'risk_controller'],

  // ========== Schema 层 ==========
  parameters: {
    action: {
      type: 'string',
      description: 'BUY：买入；SELL：卖出',
      required: true,
      enum: ['BUY', 'SELL'],
      example: 'BUY',
    },
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，如 600519',
      required: true,
      validator: validators.isStockCode,
      errorMessage: 'symbol 必须是6位数字股票代码',
      example: '600519',
    },
    quantity: {
      type: 'integer',
      description: '交易数量（股），买入必须是100的整数倍',
      required: true,
      validator: validators.isMultipleOf(100),
      errorMessage: '数量必须是100的正整数倍',
      example: 100,
    },
    price: {
      type: 'number',
      description: '委托价格（元）。不传则按市价成交',
      required: false,
      example: 1850.0,
    },
    reason: {
      type: 'string',
      description: '决策依据（强烈建议填写）：引用规则ID + 理由',
      required: false,
      example: 'R-001 买入前确认：资金充足、仓位合规',
    },
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      required: false,
      default: 'agent_virtual',
      example: 'agent_virtual',
    },
  },

  // ========== 输出 Schema + render 展示函数 ==========
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
        status: { type: 'string', description: '状态：filled/partial/rejected' },
        timestamp: { type: 'string', description: '成交时间' },
        slippage: {
          type: 'object',
          description: '滑点信息',
          properties: {
            decision_price: { type: 'number', description: '决策时价' },
            fill_price: { type: 'number', description: '成交价' },
            slippage_pct: { type: 'number', description: '滑点比例（%）' },
          },
        },
      },
      additionalProperties: true,
    },
    
    /**
     * render 函数：将工具结果转换为展示格式
     * 这就是你提到的 mapToolResultToToolResultBlockParam 的作用
     */
    render: (args: PortfolioTradeParams, value: PortfolioTradeResult) => {
      // 成功交易的展示
      if (value.status === 'filled') {
        const slippageText = value.slippage 
          ? `\n滑点: ${value.slippage.slippage_pct.toFixed(2)}% (决策价 ${value.slippage.decision_price} → 成交价 ${value.slippage.fill_price})`
          : '';
        
        return [{
          type: 'text',
          text: 
            `✅ 交易成功\n` +
            `操作: ${value.action} ${value.symbol}\n` +
            `数量: ${value.quantity}股\n` +
            `价格: ¥${value.price.toFixed(2)}\n` +
            `金额: ¥${value.amount.toFixed(2)}\n` +
            `订单ID: ${value.order_id}\n` +
            `时间: ${value.timestamp}${slippageText}`,
        }];
      }
      
      // 部分成交
      if (value.status === 'partial') {
        return [{
          type: 'text',
          text: `⚠️  部分成交: ${value.symbol} ${value.quantity}股，订单ID: ${value.order_id}`,
        }];
      }
      
      // 拒绝
      return [{
        type: 'text',
        text: `❌ 交易被拒绝: ${value.symbol}，订单ID: ${value.order_id}`,
      }];
    },
  },
};

/**
 * 前置条件定义（在同一个文件中）
 */
export const portfolioTradePreconditions: ToolPrecondition[] = [
  {
    name: 'trading_hours',
    check: () => {
      try {
        assertTradingHours();
        return true;
      } catch {
        return false;
      }
    },
    errorMessage: '非交易时段禁止下单（宪法第1条）。仅 A股交易日 9:30-11:30、13:00-15:00 可执行买卖委托',
  },
];
```

### 文件 2: PortfolioTradeTool.ts（执行层）

```typescript
// packages/trading/src/tools/PortfolioTradeTool/PortfolioTradeTool.ts

import { BaseTool, ToolContext, ToolMetadata } from '@pi-investment/tool-framework';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';
import { 
  portfolioTradePrompt, 
  portfolioTradePreconditions,
  PortfolioTradeParams, 
  PortfolioTradeResult 
} from './prompt';

/**
 * 组合交易工具
 */
export class PortfolioTradeTool extends BaseTool<PortfolioTradeParams, PortfolioTradeResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'portfolio_trade',
    category: 'trading',
    version: '2.0.0',
    riskLevel: 'high',
    timeoutMs: 10000,
    dependencies: ['account_info', 'position_list'],
    tags: ['trade', 'buy', 'sell'],
  };

  protected readonly prompt = portfolioTradePrompt;
  protected readonly preconditions = portfolioTradePreconditions;

  constructor(
    private qv2: QuantsysV2Client,
    private osMemory: OsMemoryStore
  ) {
    super();
  }

  /**
   * 核心执行逻辑（只写业务代码，框架自动处理参数校验、前置检查）
   */
  protected async execute(ctx: ToolContext<PortfolioTradeParams>): Promise<PortfolioTradeResult> {
    const { args } = ctx;

    // 1. 业务校验（领域逻辑）
    if (args.action === 'BUY') {
      await this.checkCircuitBreaker();
      await this.checkRegimeLimit(args);
      await this.checkManipulation(args);
    }

    // 2. 捕获决策时价（用于滑点计算）
    const decisionPrice = await this.captureDecisionPrice(args.symbol);

    // 3. 执行交易
    const result = await this.qv2.executeTrade({
      action: args.action,
      symbol: args.symbol,
      quantity: args.quantity,
      price: args.price,
      account_name: args.account_name || 'agent_virtual',
      order_type: args.price ? 'limit' : 'market',
      reason: args.reason,
    });

    // 4. 计算滑点
    const slippage = this.calculateSlippage(args.action, decisionPrice, result.price);

    return {
      ...result,
      slippage,
    };
  }

  /**
   * 后置处理：信号追踪、滑点记录
   */
  protected async postProcess(
    ctx: ToolContext<PortfolioTradeParams>,
    result: PortfolioTradeResult
  ): Promise<PortfolioTradeResult> {
    const { args } = ctx;

    // 买入成交后自动记录信号
    if (args.action === 'BUY' && result.status === 'filled') {
      await this.recordSignal(args, result).catch(console.warn);
    }

    // 记录滑点
    if (result.slippage) {
      await this.recordSlippage(args, result).catch(console.warn);
    }

    return result;
  }

  /**
   * 业务校验方法
   */
  private async checkCircuitBreaker(): Promise<void> {
    const memories = await this.osMemory.search({
      query: 'circuit_breaker_status',
      namespace: 'risk',
      top_k: 1,
    });

    if (memories?.memories?.length > 0) {
      const status = JSON.parse(memories.memories[0].content || '{}');
      if (status.active) {
        this.blocked(`熔断激活：60日回撤 ${status.triggered_drawdown?.toFixed(2)}%，禁止新开仓`);
      }
    }
  }

  private async checkRegimeLimit(args: PortfolioTradeParams): Promise<void> {
    // 实现省略（参考原有代码）
  }

  private async checkManipulation(args: PortfolioTradeParams): Promise<void> {
    if (args.symbol.includes('ST')) {
      this.blocked('ST 禁区：ST/*ST 股票禁止买入（交易宪法第 5 条）');
    }
    
    // 操纵嫌疑检测
    const manipResult = await this.qv2.detectManipulation(args.symbol, 30);
    const suspicionScore = Number(manipResult?.manipulation_score || 0);
    
    if (suspicionScore > 70) {
      this.blocked(`操纵嫌疑：嫌疑评分 ${suspicionScore.toFixed(1)} >70，禁止买入`);
    }
  }

  private async captureDecisionPrice(symbol: string): Promise<number | undefined> {
    try {
      const quote = await this.qv2.getQuote(symbol);
      return Number(quote?.price) > 0 ? Number(quote.price) : undefined;
    } catch {
      return undefined;
    }
  }

  private calculateSlippage(
    action: string,
    decisionPrice: number | undefined,
    fillPrice: number
  ): PortfolioTradeResult['slippage'] | undefined {
    if (!decisionPrice || fillPrice <= 0) return undefined;

    const dirSign = action === 'SELL' ? -1 : 1;
    const slippagePct = +(((fillPrice - decisionPrice) / decisionPrice * 100) * dirSign).toFixed(3);

    return {
      decision_price: decisionPrice,
      fill_price: fillPrice,
      slippage_pct: slippagePct,
    };
  }

  private async recordSignal(args: PortfolioTradeParams, result: PortfolioTradeResult): Promise<void> {
    await this.qv2.recordSignal({
      signal_date: new Date().toISOString().slice(0, 10),
      symbol: args.symbol,
      price: result.price,
      source: this.inferSource(args.reason),
      grade: this.inferGrade(args.reason),
      reason: args.reason || '',
    });
  }

  private async recordSlippage(args: PortfolioTradeParams, result: PortfolioTradeResult): Promise<void> {
    if (!result.slippage) return;

    await this.osMemory.write({
      title: `slippage ${args.symbol} ${args.action} ${result.slippage.slippage_pct}%`,
      content: `滑点记录：${args.symbol} ${args.action} ${args.quantity}股，` +
               `决策时价 ${result.slippage.decision_price} → 成交 ${result.slippage.fill_price}，` +
               `滑点 ${result.slippage.slippage_pct}%`,
      namespace: 'trade:slippage',
      tags: ['slippage', args.symbol, args.action],
    });
  }

  private inferSource(reason?: string): string {
    if (!reason) return 'manual';
    if (reason.includes('strategy_execute')) return 'strategy_execute';
    if (reason.includes('opportunity_scan')) return 'opportunity_scan';
    if (reason.includes('mainline_stocks')) return 'mainline_stocks';
    return 'manual';
  }

  private inferGrade(reason?: string): 'A' | 'B' | 'C' {
    if (!reason) return 'C';
    if (reason.includes('A级') || reason.includes('(A)')) return 'A';
    if (reason.includes('B级') || reason.includes('(B)')) return 'B';
    return 'C';
  }

  /**
   * 覆盖日志记录方法
   */
  protected async writeToMemory(log: any): Promise<void> {
    await this.osMemory.write({
      title: `tool_call: ${log.toolName}`,
      content: JSON.stringify(log),
      namespace: 'tool:calls',
      tags: ['tool_call', log.toolName, log.success ? 'success' : 'error'],
    });
  }
}
```

### 文件 3: index.ts（适配器 + 导出）

```typescript
// packages/trading/src/tools/PortfolioTradeTool/index.ts

import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';
import { PortfolioTradeTool } from './PortfolioTradeTool';

/**
 * 导出工具类和类型
 */
export { PortfolioTradeTool } from './PortfolioTradeTool';
export { portfolioTradePrompt } from './prompt';
export type { PortfolioTradeParams, PortfolioTradeResult } from './prompt';

/**
 * 创建 DSH 工具的适配器函数
 * 这是连接 BaseTool 和 DSH 框架的桥梁
 */
export function createPortfolioTradeTool(qv2: QuantsysV2Client, osMemory: OsMemoryStore) {
  const tool = new PortfolioTradeTool(qv2, osMemory);
  
  // 转换为 DSH defineTool 格式
  return defineTool(tool.toDSHToolDefinition() as any);
}
```

---

## 🔧 BaseTool 实现（含 render 支持）

```typescript
// packages/tool-framework/src/BaseTool.ts

export abstract class BaseTool<TParams = any, TResult = any> {
  protected abstract readonly metadata: ToolMetadata;
  protected abstract readonly prompt: ToolPrompt<TParams, TResult>;
  protected preconditions?: ToolPrecondition[] = [];

  protected abstract execute(ctx: ToolContext<TParams>): Promise<TResult>;

  /**
   * 转换为 DSH defineTool 格式
   */
  toDSHToolDefinition() {
    return {
      name: this.metadata.name,
      description: this.prompt.description,
      parameters: this.convertParameters(this.prompt.parameters),
      output: {
        schema: this.prompt.output.schema,
        render: this.prompt.output.render,  // ← render 函数直接从 prompt 传递
      },
      timeoutMs: this.metadata.timeoutMs || 10000,
      execute: async (args: TParams) => {
        const response = await this.call(args);
        
        // 业务拒绝
        if (response.blocked) {
          return { success: false, blocked: true, reason: response.reason };
        }
        
        // 成功
        if (response.success) return response.data;
        
        // 系统错误
        throw new Error(response.error?.message || '工具执行失败');
      },
    };
  }

  /**
   * 统一调用入口
   */
  async call(args: TParams): Promise<ToolResponse<TResult>> {
    const executionId = uuidv4();
    const startTime = Date.now();

    try {
      // 1. 参数校验
      this.validateParameters(args);

      // 2. 前置条件检查
      await this.checkPreconditions(args);

      // 3. 执行业务逻辑
      let result = await this.execute({ args, trace: { executionId, depth: 0 } });

      // 4. 后置处理
      result = await this.postProcess({ args, trace: { executionId, depth: 0 } }, result);

      // 5. 记录日志（异步）
      this.logToolCall({ args, trace: { executionId, depth: 0 } }, result, Date.now() - startTime)
        .catch(console.warn);

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
      await this.onError({ args, trace: { executionId, depth: 0 } }, error);

      return {
        success: false,
        error: {
          code: error.code || 'INTERNAL_ERROR',
          message: error.message,
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

  private convertParameters(params: Record<string, ParameterDefinition>) {
    const result: any = {};
    for (const [key, def] of Object.entries(params)) {
      result[key] = {
        type: def.type,
        description: def.description,
        required: def.required,
        default: def.default,
        enum: def.enum,
      };
    }
    return result;
  }

  protected blocked(reason: string): never {
    const error: any = new Error(reason);
    error.blocked = true;
    throw error;
  }

  // ... 其他方法省略
}
```

---

## 📊 关键改进总结

### 1. 文件结构简化 ✅

**Before（5个文件）：**
- prompt.ts
- schema.ts
- preconditions.ts
- tool.ts
- index.ts

**After（3个文件）：**
- **prompt.ts** - 描述 + Schema + 类型 + 前置条件 + render
- **tool.ts** - 执行层（继承 BaseTool）
- **index.ts** - 适配器 + 导出

### 2. render 函数位置明确 ✅

```typescript
export const portfolioTradePrompt = {
  // ...
  output: {
    schema: { /* JSON Schema */ },
    
    // render 在这里：将工具结果格式化为展示内容
    render: (args, value) => [{
      type: 'text',
      text: `✅ ${value.action} ${value.symbol} x${value.quantity}股`,
    }],
  },
};
```

**render 的作用：**
- 将工具返回的原始数据（JSON）转换为用户友好的展示格式
- 支持多种展示类型：text / markdown / json / table
- 这就是 `mapToolResultToToolResultBlockParam` 的功能

### 3. 完全兼容 DSH ✅

```typescript
// BaseTool.toDSHToolDefinition()
output: {
  schema: this.prompt.output.schema,
  render: this.prompt.output.render,  // ← 直接传递给 DSH
}
```

### 4. 类型安全 ✅

```typescript
export interface ToolPrompt<TParams, TResult> {
  // ...
  output: {
    schema: JsonSchema;
    render?: (args: TParams, value: TResult) => ToolRenderResult[];
    //         ↑ 参数       ↑ 返回值    类型安全！
  };
}
```

---

## 🚀 使用示例

### 插件注册

```typescript
// packages/trading/src/index.ts

export default class TradingPlugin extends Service {
  private registerTools() {
    const { ctx } = this;
    
    // 使用适配器创建 DSH 工具
    ctx.tools.register(createPortfolioTradeTool(this.qv2, this.osMemory));
  }
}
```

### 效果

**工具调用：**
```typescript
portfolio_trade({ action: 'BUY', symbol: '600519', quantity: 100 })
```

**展示结果（通过 render 函数格式化）：**
```
✅ 交易成功
操作: BUY 600519
数量: 100股
价格: ¥1850.00
金额: ¥185000.00
订单ID: order_12345
时间: 2026-08-27T12:34:56
滑点: 0.05% (决策价 1849.00 → 成交价 1850.00)
```

---

**文档版本：** v3.0 (Simplified + DSH Compatible)  
**创建时间：** 2026-08-28T02:32:49.457Z
