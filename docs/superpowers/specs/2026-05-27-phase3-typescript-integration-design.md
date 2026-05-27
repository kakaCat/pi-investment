# Phase 3: TypeScript Integration Design

**日期**: 2026-05-27  
**状态**: 设计阶段  
**前置条件**: Phase 2 策略升级完成

---

## 执行摘要

Phase 3 为 TypeScript Agent 添加策略执行工具，使 Agent 能够调用升级后的策略并获取完整的风险管理参数（止损价格、仓位建议）。采用直接调用 quantsys-v2 API 的方案，与现有工具架构保持一致。

---

## 目标

### 主要目标
- 新增 `strategy_execute` 工具，支持单股单策略执行
- 返回格式化文本 + 原始信号数据（双重输出）
- 完整展示风险管理参数（止损、仓位、技术指标）

### 非目标
- 多股扫描（应该是独立的 `strategy_scan` 工具）
- 策略回测（已有 `quant_cli` 的 backtest 命令）
- 策略参数调优（Phase 4 或更晚）

---

## 架构设计

### 整体架构

```
TypeScript Agent (src/)
  └─ strategy_execute_tool.ts (新增)
       ↓ 调用
  └─ quant-v2-client.ts (扩展)
       ↓ HTTP POST
quantsys-v2 Backend (Python)
  └─ /api/strategy/run (已存在)
       ↓ 调用
  └─ StrategyService (已存在)
       ↓ 执行
  └─ 升级后的策略类 (Phase 2 完成)
       ↓ 返回
  └─ 信号 + risk_management
```

### 数据流

1. **Agent 调用工具**: `strategy_execute({ symbol: "600519", strategy: "VolatilityBreakout" })`
2. **TypeScript 工具**: 验证参数 → 调用 `executeStrategy()` 客户端方法
3. **HTTP 客户端**: `POST /api/strategy/run` with `{ symbol, strategy_name }`
4. **Python 后端**: 加载策略 → 获取数据 → 执行策略 → 返回信号
5. **TypeScript 格式化**: `formatStrategySignal()` 转换为可读文本 + 保留原始数据
6. **返回 Agent**: `{ content: [{ type: 'text', text: '...' }], details: {...} }`

### 方案选择

**选择方案 B：直接调用 v2 API**

**理由**:
- 与现有工具（`factor_calculate`、`opportunity_scan`）架构一致
- TypeScript 端到端类型安全
- 不依赖 quant_cli 中间层，更直接清晰
- `/api/strategy/run` 端点已存在，只需添加客户端封装

**替代方案**:
- 方案 A（复用 quant_cli）: 增加中间层复杂度
- 方案 C（新增专用端点）: 过度设计，现有端点已足够

---

## 技术实现

### 1. 类型定义（types.ts）

```typescript
// 策略执行请求参数
export interface StrategyExecuteParams {
  symbol: string;           // 股票代码（如 "600519.SH"）
  strategy_name: string;    // 策略名称（如 "VolatilityBreakout"）
  date?: string;            // 可选：指定日期（默认最新）
}

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

// 风险管理配置
export interface RiskManagement {
  stop_loss?: StopLossConfig;
  position_sizing?: PositionSizingConfig;
  take_profit?: StopLossConfig;  // 可选：止盈（结构同止损）
}

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

**关键设计决策**:
- `symbol` 格式: 支持带后缀（600519.SH）和不带后缀（600519）
- `date` 参数: 可选，支持历史回测
- `indicators` 字段: 保留策略暴露的技术指标
- `error` 字段: 当 success=false 时包含错误信息

### 2. 客户端方法（quant-v2-client.ts）

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

**错误处理策略**:
- 网络超时: 30 秒超时（V2_TIMEOUT_MS）
- HTTP 错误: 抛出 QuantV2Error，包含状态码
- 业务错误: 后端返回 `success: false`，抛出错误
- 数据不足: 后端返回错误信息（如"K线数据不足"）

### 3. 格式化函数（formatters.ts）

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

  // 信号
  const actionMap = { buy: '买入', sell: '卖出', hold: '持有' };
  const actionText = actionMap[signal.action] || signal.action;
  lines.push(`信号: ${actionText}`);
  lines.push(`置信度: ${formatPercent(signal.confidence * 100, 1)}`);
  lines.push(`理由: ${signal.reason}`);
  lines.push('');

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

**格式化示例输出**:

```
【策略信号】贵州茅台 (600519.SH)
策略: VolatilityBreakout
时间: 2026-05-27T10:30:00

信号: 买入
置信度: 85.0%
理由: 突破上阈值

【风险管理】
止损价格: 1,650.50 元
  类型: ATR止损 (2倍ATR)
  ATR值: 25.30

仓位建议:
  方法: Kelly准则
  胜率: 55.0%
  盈亏比: 2.00
  Kelly系数: 0.25
  说明: 需要根据账户余额计算具体仓位

【技术指标】
ATR: 25.30
RSI: 45.20
```

### 4. 工具定义（strategy/execute-tool.ts）

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

**关键设计点**:
- 股票代码标准化: 自动添加市场后缀（SH/SZ/BJ）
- 参数验证: 在工具层验证必需参数
- 错误处理: 捕获所有异常，返回友好错误信息
- 双重输出: 格式化文本 + 原始数据（details）

### 5. 工具注册（tools/index.ts）

```typescript
// 在 strategy 目录导出
export { strategyExecuteTool } from './strategy/execute-tool.js';

// 在工具注册列表中添加
const allTools: ToolDefinition[] = [
  // ... 现有工具
  strategyExecuteTool,
];
```

---

## 测试策略

### 单元测试（execute-tool.test.ts）

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { strategyExecuteTool } from './execute-tool.js';
import * as client from '../../quant/quant-v2-client.js';

describe('strategyExecuteTool', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

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

  it('should handle missing symbol parameter', async () => {
    const result = await strategyExecuteTool.execute('test-call-id', {
      strategy: 'Turtle'
    });

    expect(result.content[0].text).toContain('错误：缺少必需参数 symbol');
  });

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

### 集成测试场景

1. **正常流程**: 执行策略 → 返回买入信号 → 包含完整风控参数
2. **持有信号**: 策略返回 hold → 不包含 risk_management 字段
3. **数据不足**: 后端返回错误 → 工具返回友好错误信息
4. **网络超时**: API 超时 → 捕获并返回超时错误
5. **无效策略名**: 后端返回"策略不存在" → 工具透传错误

### 手动测试步骤

```bash
# 1. 启动 quantsys-v2 后端
cd quantsys-v2 && python start_all.py

# 2. 启动 TypeScript Agent
npm run dev

# 3. 测试命令
> 执行 VolatilityBreakout 策略分析 600519
> 执行 Turtle 策略分析 000001
> 执行 Momentum 策略分析 300750
```

---

## 文件变更清单

### 新增文件

1. `src/infrastructure/tools/strategy/execute-tool.ts` - 策略执行工具定义（~120 行）
2. `src/infrastructure/tools/strategy/execute-tool.test.ts` - 单元测试（~150 行）

### 修改文件

1. `src/infrastructure/quant/types.ts` - 添加类型定义（~80 行新增）
   - `StrategyExecuteParams`
   - `StopLossConfig`
   - `PositionSizingConfig`
   - `RiskManagement`
   - `StrategySignal`

2. `src/infrastructure/quant/quant-v2-client.ts` - 添加客户端方法（~50 行新增）
   - `executeStrategy()` 函数

3. `src/infrastructure/quant/formatters.ts` - 添加格式化函数（~100 行新增）
   - `formatStrategySignal()` 函数

4. `src/infrastructure/tools/index.ts` - 注册新工具（~2 行修改）
   - 导出 `strategyExecuteTool`
   - 添加到 `allTools` 数组

### 代码统计

- **新增代码**: ~500 行（工具 + 类型 + 客户端 + 格式化 + 测试）
- **修改代码**: ~10 行（工具注册）
- **测试覆盖率**: 100%（新增功能）

---

## 依赖关系

### 前置依赖

- ✅ Phase 1: 风险管理基础设施（已完成）
- ✅ Phase 2: 策略升级（已完成）
- ✅ quantsys-v2 `/api/strategy/run` 端点（已存在）

### 后续依赖

- Phase 4: 文档和示例（依赖 Phase 3）
- 多股策略扫描工具（可选，独立开发）

---

## 风险和缓解

### 风险 1: 后端 API 响应格式不匹配

**描述**: `/api/strategy/run` 返回的信号格式可能与预期不一致

**缓解**:
- 在实现前验证后端 API 响应格式
- 添加运行时类型验证（可选使用 zod）
- 完善错误处理，捕获格式错误

### 风险 2: 策略执行时间过长

**描述**: 某些策略可能需要大量计算，导致超时

**缓解**:
- 设置 30 秒超时（V2_TIMEOUT_MS）
- 后端优化策略执行性能
- 考虑添加进度反馈（Phase 4）

### 风险 3: 股票代码标准化逻辑不完整

**描述**: 可能存在特殊格式的股票代码无法识别

**缓解**:
- 支持常见格式（6/0/3/8 开头）
- 返回清晰的错误信息
- 后续根据实际使用情况扩展

---

## 成功标准

### 功能完整性

- ✅ 工具能够成功调用 quantsys-v2 API
- ✅ 返回格式化文本 + 原始信号数据
- ✅ 正确展示止损价格、仓位建议、技术指标
- ✅ 支持所有 Phase 2 升级的策略

### 质量标准

- ✅ 单元测试覆盖率 > 90%
- ✅ 所有测试通过
- ✅ 类型安全（无 TypeScript 错误）
- ✅ 错误处理完善（网络、业务、数据错误）

### 用户体验

- ✅ 格式化输出清晰易读
- ✅ 错误信息友好明确
- ✅ 响应时间 < 5 秒（正常情况）
- ✅ Agent 能够直接展示结果给用户

---

## 后续工作

### Phase 4: 文档和示例

- 编写策略执行工具使用指南
- 创建风控功能使用示例
- 更新 CLAUDE.md 工具说明

### 可选扩展

- **多股策略扫描**: 新增 `strategy_scan` 工具
- **策略对比**: 对比多个策略对同一股票的判断
- **历史信号查询**: 查询策略的历史信号记录
- **信号验证**: 验证历史信号的准确率

---

## 结论

Phase 3 通过新增 `strategy_execute` 工具，将 Phase 2 升级的策略风险管理功能暴露给 TypeScript Agent。采用直接调用 v2 API 的方案，与现有工具架构保持一致，实现清晰、类型安全、易于维护。

**预计工作量**: 3-4 小时  
**复杂度**: 中等  
**优先级**: 高（完成 Phase 2 后的自然延续）

**状态**: ✅ 设计完成，等待实现
