# Phase 3: TypeScript Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `strategy_execute` tool to TypeScript Agent, enabling users to get trading signals with risk management parameters from upgraded strategies.

**Architecture:** Direct HTTP calls from TypeScript tool → quantsys-v2 `/api/strategy/run` endpoint → upgraded strategies (Phase 2). Returns formatted text + raw signal data.

**Tech Stack:** TypeScript, @sinclair/typebox, fetch API, vitest

---

## File Structure

### Files to Create
1. `src/infrastructure/tools/strategy/execute-tool.ts` - Tool definition (~120 lines)
2. `src/infrastructure/tools/strategy/execute-tool.test.ts` - Unit tests (~150 lines)

### Files to Modify
1. `src/infrastructure/quant/types.ts` - Add 5 new type definitions (~80 lines)
2. `src/infrastructure/quant/quant-v2-client.ts` - Add `executeStrategy()` method (~50 lines)
3. `src/infrastructure/quant/formatters.ts` - Add `formatStrategySignal()` function (~100 lines)
4. `src/infrastructure/tools/index.ts` - Register new tool (~2 lines)

---

## Task 1: Add Type Definitions

**Files:**
- Modify: `src/infrastructure/quant/types.ts` (append to end of file)

- [ ] **Step 1: Add StrategyExecuteParams interface**

```typescript
// 策略执行请求参数
export interface StrategyExecuteParams {
  symbol: string;           // 股票代码（如 "600519.SH"）
  strategy_name: string;    // 策略名称（如 "VolatilityBreakout"）
  date?: string;            // 可选：指定日期（默认最新）
}
```

- [ ] **Step 2: Add StopLossConfig interface**

```typescript
// 止损配置
export interface StopLossConfig {
  type: 'atr' | 'percent' | 'trailing' | 'fixed';
  price: number;            // 止损价格
  params: {
    atr_value?: number;           // ATR 值
    atr_multiplier?: number;      // ATR 倍数
    percent?: number;             // 百分比
    trailing_percent?: number;    // 追踪百分比
  };
}
```

- [ ] **Step 3: Add PositionSizingConfig interface**

```typescript
// 仓位管理配置
export interface PositionSizingConfig {
  method: 'kelly' | 'fixed_percent' | 'fixed_shares';
  value: number | null;     // 具体值（Kelly 返回 null，需要账户余额计算）
  params: {
    win_rate?: number;            // 胜率
    profit_loss_ratio?: number;   // 盈亏比
    kelly_fraction?: number;      // Kelly 系数
    percent?: number;             // 固定百分比
    shares?: number;              // 固定股数
  };
}
```

- [ ] **Step 4: Add RiskManagement interface**

```typescript
// 风险管理配置
export interface RiskManagement {
  stop_loss?: StopLossConfig;
  position_sizing?: PositionSizingConfig;
  take_profit?: StopLossConfig;  // 可选：止盈（结构同止损）
}
```

- [ ] **Step 5: Add StrategySignal interface**

```typescript
// 策略信号
export interface StrategySignal {
  success: boolean;
  symbol: string;
  name: string;              // 股票名称
  strategy: string;          // 策略名称
  action: 'buy' | 'sell' | 'hold';
  confidence: number;        // 0-1
  reason: string;
  risk_management?: RiskManagement;
  indicators?: Record<string, number>;  // 技术指标
  timestamp: string;
  error?: string;
}
```

- [ ] **Step 6: Verify TypeScript compilation**

Run: `npm run build`
Expected: No TypeScript errors

- [ ] **Step 7: Commit type definitions**

```bash
git add src/infrastructure/quant/types.ts
git commit -m "feat(types): add strategy execution type definitions"
```

---

## Task 2: Add executeStrategy Client Method

**Files:**
- Modify: `src/infrastructure/quant/quant-v2-client.ts` (append before the closing exports)

- [ ] **Step 1: Add executeStrategy function**

```typescript
/**
 * 执行策略并返回信号（带风险管理参数）
 */
export async function executeStrategy(
  params: StrategyExecuteParams
): Promise<StrategySignal> {
  try {
    const response = await fetch(
      `${V2_API_BASE}/api/strategy/run`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          symbol: params.symbol,
          strategy_name: params.strategy_name,
          date: params.date,
        }),
        signal: AbortSignal.timeout(V2_TIMEOUT_MS),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new QuantV2Error(
        errorData.error || `HTTP ${response.status}`,
        response.status,
        '/api/strategy/run'
      );
    }

    const data = await response.json();
    
    if (!data.success) {
      throw new QuantV2Error(
        data.error || '策略执行失败',
        undefined,
        '/api/strategy/run'
      );
    }

    return data as StrategySignal;
  } catch (error) {
    if (error instanceof QuantV2Error) {
      throw error;
    }
    throw new QuantV2Error(
      `策略执行失败: ${error instanceof Error ? error.message : String(error)}`,
      undefined,
      '/api/strategy/run'
    );
  }
}
```

- [ ] **Step 2: Verify TypeScript compilation**

Run: `npm run build`
Expected: No TypeScript errors

- [ ] **Step 3: Commit client method**

```bash
git add src/infrastructure/quant/quant-v2-client.ts
git commit -m "feat(client): add executeStrategy method for v2 API"
```

---

## Task 3: Add formatStrategySignal Formatter

**Files:**
- Modify: `src/infrastructure/quant/formatters.ts` (append to end of file)

- [ ] **Step 1: Add formatStrategySignal function signature and header**

```typescript
/**
 * 格式化策略信号为可读文本
 */
export function formatStrategySignal(signal: StrategySignal): string {
  const lines: string[] = [];

  // 标题
  lines.push(`【策略信号】${signal.name} (${signal.symbol})`);
  lines.push(`策略: ${signal.strategy}`);
  lines.push(`时间: ${signal.timestamp}`);
  lines.push('');
```

- [ ] **Step 2: Add signal formatting section**

```typescript
  // 信号
  const actionMap = { buy: '买入', sell: '卖出', hold: '持有' };
  const actionText = actionMap[signal.action] || signal.action;
  lines.push(`信号: ${actionText}`);
  lines.push(`置信度: ${formatPercent(signal.confidence * 100, 1)}`);
  lines.push(`理由: ${signal.reason}`);
  lines.push('');
```

- [ ] **Step 3: Add risk management formatting - stop loss**

```typescript
  // 风险管理
  if (signal.risk_management) {
    lines.push('【风险管理】');
    
    // 止损
    if (signal.risk_management.stop_loss) {
      const sl = signal.risk_management.stop_loss;
      lines.push(`止损价格: ${formatNumber(sl.price, 2)} 元`);
      
      if (sl.type === 'atr' && sl.params.atr_value && sl.params.atr_multiplier) {
        lines.push(`  类型: ATR止损 (${sl.params.atr_multiplier}倍ATR)`);
        lines.push(`  ATR值: ${formatNumber(sl.params.atr_value, 2)}`);
      } else if (sl.type === 'percent' && sl.params.percent) {
        lines.push(`  类型: 固定百分比止损 (${formatPercent(sl.params.percent)})`);
      } else if (sl.type === 'trailing' && sl.params.trailing_percent) {
        lines.push(`  类型: 追踪止损 (${formatPercent(sl.params.trailing_percent)})`);
      } else if (sl.type === 'fixed') {
        lines.push(`  类型: 固定价格止损`);
      }
    }
```

- [ ] **Step 4: Add risk management formatting - position sizing**

```typescript
    // 仓位管理
    if (signal.risk_management.position_sizing) {
      const ps = signal.risk_management.position_sizing;
      lines.push('');
      lines.push('仓位建议:');
      
      if (ps.method === 'kelly' && ps.params.win_rate && ps.params.profit_loss_ratio) {
        lines.push(`  方法: Kelly准则`);
        lines.push(`  胜率: ${formatPercent(ps.params.win_rate * 100, 1)}`);
        lines.push(`  盈亏比: ${formatNumber(ps.params.profit_loss_ratio, 2)}`);
        lines.push(`  Kelly系数: ${formatNumber(ps.params.kelly_fraction || 0.25, 2)}`);
        lines.push(`  说明: 需要根据账户余额计算具体仓位`);
      } else if (ps.method === 'fixed_percent' && ps.params.percent) {
        lines.push(`  方法: 固定比例`);
        lines.push(`  比例: ${formatPercent(ps.params.percent * 100)}`);
      } else if (ps.method === 'fixed_shares' && ps.params.shares) {
        lines.push(`  方法: 固定股数`);
        lines.push(`  股数: ${formatNumber(ps.params.shares, 0)} 股`);
      }
    }
```

- [ ] **Step 5: Add risk management formatting - take profit and indicators**

```typescript
    // 止盈（可选）
    if (signal.risk_management.take_profit) {
      const tp = signal.risk_management.take_profit;
      lines.push('');
      lines.push(`止盈价格: ${formatNumber(tp.price, 2)} 元`);
    }

    lines.push('');
  }

  // 技术指标
  if (signal.indicators && Object.keys(signal.indicators).length > 0) {
    lines.push('【技术指标】');
    for (const [key, value] of Object.entries(signal.indicators)) {
      const displayName = key.toUpperCase();
      lines.push(`${displayName}: ${formatNumber(value, 2)}`);
    }
    lines.push('');
  }

  return lines.join('\n');
}
```

- [ ] **Step 6: Verify TypeScript compilation**

Run: `npm run build`
Expected: No TypeScript errors

- [ ] **Step 7: Commit formatter function**

```bash
git add src/infrastructure/quant/formatters.ts
git commit -m "feat(formatters): add formatStrategySignal for risk management display"
```

---

## Task 4: Create Strategy Execute Tool

**Files:**
- Create: `src/infrastructure/tools/strategy/execute-tool.ts`

- [ ] **Step 1: Create strategy directory if not exists**

Run: `mkdir -p src/infrastructure/tools/strategy`
Expected: Directory created or already exists

- [ ] **Step 2: Create execute-tool.ts with imports and tool definition start**

```typescript
/**
 * 策略执行工具 - 运行单个策略并返回信号（含风险管理参数）
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { executeStrategy } from "../../quant/quant-v2-client.js";
import { formatStrategySignal } from "../../quant/formatters.js";

export const strategyExecuteTool: ToolDefinition = {
  name: "strategy_execute",
  label: "执行策略",
  description:
    "执行单个量化策略，返回交易信号和完整的风险管理参数。\n" +
    "支持的策略包括：VolatilityBreakout（波动突破）、Turtle（海龟）、" +
    "DonchianChannel（唐奇安通道）、Momentum（动量）等。\n" +
    "返回内容：买卖信号、置信度、止损价格、仓位建议、技术指标。\n" +
    "适用场景：获取策略对特定股票的判断和风控建议。",

  parameters: Type.Object({
    symbol: Type.String({
      description: "股票代码，支持带后缀（600519.SH）或不带后缀（600519）"
    }),
    strategy: Type.String({
      description: "策略名称，如：VolatilityBreakout, Turtle, DonchianChannel, Momentum"
    }),
    date: Type.Optional(Type.String({
      description: "可选：指定日期（YYYY-MM-DD格式），默认使用最新数据"
    }))
  }),
```

- [ ] **Step 3: Add execute function with parameter validation**

```typescript
  execute: async (_toolCallId: string, params: any) => {
    try {
      // 参数验证
      if (!params?.symbol || typeof params.symbol !== 'string') {
        return {
          content: [{
            type: "text" as const,
            text: "错误：缺少必需参数 symbol（股票代码）"
          }],
          details: undefined
        };
      }

      if (!params?.strategy || typeof params.strategy !== 'string') {
        return {
          content: [{
            type: "text" as const,
            text: "错误：缺少必需参数 strategy（策略名称）"
          }],
          details: undefined
        };
      }
```

- [ ] **Step 4: Add symbol normalization logic**

```typescript
      // 标准化股票代码（确保有后缀）
      let symbol = params.symbol.trim();
      if (!/\.(SH|SZ|BJ)$/.test(symbol)) {
        // 6开头 → 上海，0/3开头 → 深圳，8开头 → 北京
        if (symbol.startsWith('6')) {
          symbol = `${symbol}.SH`;
        } else if (symbol.startsWith('0') || symbol.startsWith('3')) {
          symbol = `${symbol}.SZ`;
        } else if (symbol.startsWith('8')) {
          symbol = `${symbol}.BJ`;
        } else {
          return {
            content: [{
              type: "text" as const,
              text: `错误：无法识别股票代码格式: ${symbol}`
            }],
            details: undefined
          };
        }
      }
```

- [ ] **Step 5: Add API call and response formatting**

```typescript
      // 调用 v2 API
      const signal = await executeStrategy({
        symbol,
        strategy_name: params.strategy,
        date: params.date
      });

      // 格式化输出
      const formattedText = formatStrategySignal(signal);

      return {
        content: [{
          type: "text" as const,
          text: formattedText
        }],
        details: signal  // 保留原始信号数据
      };

    } catch (error) {
      return {
        content: [{
          type: "text" as const,
          text: `策略执行失败: ${error instanceof Error ? error.message : String(error)}`
        }],
        details: undefined
      };
    }
  }
};
```

- [ ] **Step 6: Verify TypeScript compilation**

Run: `npm run build`
Expected: No TypeScript errors

- [ ] **Step 7: Commit tool implementation**

```bash
git add src/infrastructure/tools/strategy/execute-tool.ts
git commit -m "feat(tools): add strategy_execute tool for risk management"
```

---

## Task 5: Register Tool in Index

**Files:**
- Modify: `src/infrastructure/tools/index.ts`

- [ ] **Step 1: Add import for strategyExecuteTool**

Find the section with tool imports and add:

```typescript
export { strategyExecuteTool } from './strategy/execute-tool.js';
```

- [ ] **Step 2: Add tool to allTools array**

Find the `allTools` array and add `strategyExecuteTool` to it:

```typescript
const allTools: ToolDefinition[] = [
  // ... existing tools
  strategyExecuteTool,
];
```

- [ ] **Step 3: Verify TypeScript compilation**

Run: `npm run build`
Expected: No TypeScript errors

- [ ] **Step 4: Verify tool is registered**

Run: `npm run dev` and check that the tool appears in the tool list
Expected: `strategy_execute` tool is available

- [ ] **Step 5: Commit tool registration**

```bash
git add src/infrastructure/tools/index.ts
git commit -m "feat(tools): register strategy_execute tool"
```

---

## Task 6: Add Unit Tests

**Files:**
- Create: `src/infrastructure/tools/strategy/execute-tool.test.ts`

- [ ] **Step 1: Create test file with imports and describe block**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { strategyExecuteTool } from './execute-tool.js';
import * as client from '../../quant/quant-v2-client.js';

describe('strategyExecuteTool', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
```

- [ ] **Step 2: Add test for successful execution with full risk management**

```typescript
  it('should execute strategy successfully with full risk management', async () => {
    const mockSignal = {
      success: true,
      symbol: '600519.SH',
      name: '贵州茅台',
      strategy: 'VolatilityBreakout',
      action: 'buy' as const,
      confidence: 0.85,
      reason: '突破上阈值',
      risk_management: {
        stop_loss: {
          type: 'atr' as const,
          price: 1650.50,
          params: { atr_value: 25.30, atr_multiplier: 2.0 }
        },
        position_sizing: {
          method: 'kelly' as const,
          value: null,
          params: { win_rate: 0.55, profit_loss_ratio: 2.0, kelly_fraction: 0.25 }
        }
      },
      indicators: { atr: 25.30, rsi: 45.20 },
      timestamp: '2026-05-27T10:30:00'
    };

    vi.spyOn(client, 'executeStrategy').mockResolvedValue(mockSignal);

    const result = await strategyExecuteTool.execute('test-call-id', {
      symbol: '600519',
      strategy: 'VolatilityBreakout'
    });

    expect(result.content[0].text).toContain('贵州茅台');
    expect(result.content[0].text).toContain('买入');
    expect(result.content[0].text).toContain('85.0%');
    expect(result.content[0].text).toContain('止损价格: 1,650.50');
    expect(result.content[0].text).toContain('Kelly准则');
    expect(result.details).toEqual(mockSignal);
  });
```

- [ ] **Step 3: Add test for symbol normalization**

```typescript
  it('should normalize symbol without suffix', async () => {
    const executeSpy = vi.spyOn(client, 'executeStrategy').mockResolvedValue({
      success: true,
      symbol: '600519.SH',
      name: '贵州茅台',
      strategy: 'Turtle',
      action: 'hold' as const,
      confidence: 0.5,
      reason: '无信号',
      timestamp: '2026-05-27T10:30:00'
    });

    await strategyExecuteTool.execute('test-call-id', {
      symbol: '600519',
      strategy: 'Turtle'
    });

    expect(executeSpy).toHaveBeenCalledWith({
      symbol: '600519.SH',
      strategy_name: 'Turtle',
      date: undefined
    });
  });
```

- [ ] **Step 4: Add test for missing parameters**

```typescript
  it('should handle missing symbol parameter', async () => {
    const result = await strategyExecuteTool.execute('test-call-id', {
      strategy: 'Turtle'
    });

    expect(result.content[0].text).toContain('错误：缺少必需参数 symbol');
  });

  it('should handle missing strategy parameter', async () => {
    const result = await strategyExecuteTool.execute('test-call-id', {
      symbol: '600519'
    });

    expect(result.content[0].text).toContain('错误：缺少必需参数 strategy');
  });
```

- [ ] **Step 5: Add test for API errors**

```typescript
  it('should handle API errors gracefully', async () => {
    vi.spyOn(client, 'executeStrategy').mockRejectedValue(
      new Error('K线数据不足')
    );

    const result = await strategyExecuteTool.execute('test-call-id', {
      symbol: '600519',
      strategy: 'Turtle'
    });

    expect(result.content[0].text).toContain('策略执行失败');
    expect(result.content[0].text).toContain('K线数据不足');
  });
```

- [ ] **Step 6: Add test for optional date parameter**

```typescript
  it('should support optional date parameter', async () => {
    const executeSpy = vi.spyOn(client, 'executeStrategy').mockResolvedValue({
      success: true,
      symbol: '600519.SH',
      name: '贵州茅台',
      strategy: 'Momentum',
      action: 'sell' as const,
      confidence: 0.75,
      reason: '动量减弱',
      timestamp: '2026-01-15T10:30:00'
    });

    await strategyExecuteTool.execute('test-call-id', {
      symbol: '600519.SH',
      strategy: 'Momentum',
      date: '2026-01-15'
    });

    expect(executeSpy).toHaveBeenCalledWith({
      symbol: '600519.SH',
      strategy_name: 'Momentum',
      date: '2026-01-15'
    });
  });
});
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `npm test execute-tool.test.ts`
Expected: All 6 tests pass

- [ ] **Step 8: Commit unit tests**

```bash
git add src/infrastructure/tools/strategy/execute-tool.test.ts
git commit -m "test(tools): add unit tests for strategy_execute tool"
```

---

## Self-Review Checklist

Before marking complete, verify:

- [ ] All type definitions match between tasks (StrategySignal, RiskManagement, etc.)
- [ ] No placeholders ("TBD", "TODO", etc.) in any task
- [ ] All code blocks are complete and runnable
- [ ] All file paths are absolute and correct
- [ ] All test cases cover the spec requirements
- [ ] Commit messages follow conventional commits format

---

## Success Criteria

- ✅ All TypeScript compilation passes without errors
- ✅ All 6 unit tests pass
- ✅ Tool is registered and appears in tool list
- ✅ Manual test: Can execute strategy and see formatted output
- ✅ Manual test: Error handling works for invalid inputs

---

## Manual Testing

After implementation, test manually:

```bash
# 1. Start quantsys-v2 backend
cd quantsys-v2 && python start_all.py

# 2. Start TypeScript Agent
npm run dev

# 3. Test commands
> 执行 VolatilityBreakout 策略分析 600519
> 执行 Turtle 策略分析 000001
> 执行 Momentum 策略分析 300750
```

Expected output should include:
- 策略信号标题
- 买入/卖出/持有信号
- 置信度
- 风险管理（止损价格、仓位建议）
- 技术指标
