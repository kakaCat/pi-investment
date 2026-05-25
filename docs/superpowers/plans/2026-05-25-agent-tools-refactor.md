# Agent 工具重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 61 个工具重构为 30 个工具，按六层架构组织（数据管道、因子工厂、模型层、组合构建、执行引擎、监控运维），统一命名规范，直接替换旧工具。

**Architecture:** 
- 六层架构映射：L1 数据管道 (data_*) → L2 因子工厂 (factor_*) → L3 模型层 (model_*) → L4 组合构建 (portfolio_*) → L5 执行引擎 (trade_*) → L6 监控运维 (monitor_*)
- 智能路由模式：高层工具根据参数路由到具体实现
- 批量计算模式：因子工具支持批量计算多个因子

**Tech Stack:** TypeScript, @sinclair/typebox, quantsys-daemon-adapter, CLI adapters

---

## 文件结构

### 新增目录
```
src/infrastructure/tools/
├── data/                       # L1: 数据管道工具
│   ├── fetch-kline-tool.ts
│   ├── fetch-financial-tool.ts
│   ├── fetch-stock-tool.ts
│   ├── validate-tool.ts
│   └── sync-tool.ts
├── factor/                     # L2: 因子工厂工具
│   ├── calculate-tool.ts
│   ├── analyze-ic-tool.ts
│   ├── backtest-tool.ts
│   ├── monitor-tool.ts
│   └── list-tool.ts
├── model/                      # L3: 模型层工具
│   ├── train-tool.ts
│   ├── predict-tool.ts
│   ├── evaluate-tool.ts
│   ├── monitor-tool.ts
│   └── list-tool.ts
├── portfolio/                  # L4: 组合构建工具
│   ├── optimize-tool.ts
│   ├── risk-budget-tool.ts
│   ├── rebalance-tool.ts
│   ├── stress-test-tool.ts
│   └── dashboard-tool.ts
├── trade/                      # L5: 执行引擎工具
│   ├── create-order-tool.ts
│   ├── manage-orders-tool.ts
│   ├── execute-algo-tool.ts
│   ├── reconcile-tool.ts
│   └── monitor-tool.ts
└── monitor/                    # L6: 监控运维工具
    ├── risk-tool.ts
    ├── signal-tool.ts
    ├── execution-tool.ts
    ├── alert-tool.ts
    └── attribution-tool.ts
```

### 删除目录
```
src/infrastructure/tools/
├── invest/                     # 删除整个目录（13个文件）
├── analysis/                   # 删除整个目录
└── trading/                    # 删除整个目录
```

### 修改文件
- `src/infrastructure/tools/index.ts` - 重写工具注册逻辑
- `src/infrastructure/tools/agent/*` - 保持不变
- `src/infrastructure/tools/shared/*` - 保持不变

---

## Task 1: 创建 L1 数据管道工具 - data_fetch_stock

**Files:**
- Create: `src/infrastructure/tools/data/fetch-stock-tool.ts`
- Reference: `src/infrastructure/tools/invest/stock-query-tools.ts:10-128`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p src/infrastructure/tools/data
```

- [ ] **Step 2: 实现 data_fetch_stock 工具（整合 info/price/news/announcements）**

创建 `src/infrastructure/tools/data/fetch-stock-tool.ts`:

```typescript
/**
 * L1 数据管道工具 - 股票数据获取
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { detectMarket } from "../shared/validators.js";
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

export const dataFetchStockTool: ToolDefinition = {
  name: "data_fetch_stock",
  label: "获取股票数据",
  description:
    "获取股票基础数据，支持多字段组合查询：info（基本信息）、price（实时价格）、news（新闻）、announcements（公告）。" +
    "支持 A 股（6位代码）和港股（1-5位代码或 .HK 后缀）。" +
    "使用 fields 参数指定需要的字段，可单独或组合查询。" +
    "返回 JSON 格式，包含请求的所有字段数据。",
  parameters: Type.Object({
    symbol: Type.String({ 
      description: "股票代码：A股6位数字（如 '600519'）或港股1-5位数字（如 '9988' 或 '9988.HK'）" 
    }),
    fields: Type.Array(Type.String(), { 
      description: "需要的字段列表，可选值：'info'（基本信息）、'price'（实时价格）、'news'（新闻）、'announcements'（公告）。可组合查询。",
      default: ["info", "price"]
    }),
  }),
  execute: async (_toolCallId, params: any) => {
    const market = detectMarket(params.symbol);
    if (market === "invalid") {
      return { 
        content: [{ 
          type: "text" as const, 
          text: JSON.stringify({ 
            error: `不支持的股票代码 "${params.symbol}"。本系统支持A股（6位数字）和港股（1-5位数字或含.HK后缀）。`, 
            invalid_format: true 
          }) 
        }], 
        details: undefined 
      };
    }

    const results: any = { symbol: params.symbol };
    const fields = params.fields || ["info", "price"];

    // 根据 fields 参数路由到具体实现
    for (const field of fields) {
      try {
        switch (field) {
          case "info":
            const infoResult = await callQuantSysDaemon("get_stock_info", { symbol: params.symbol });
            results.info = JSON.parse(infoResult);
            break;
          case "price":
            const priceResult = await callQuantSysDaemon("get_stock_realtime_price", { symbol: params.symbol });
            results.price = JSON.parse(priceResult);
            break;
          case "news":
            const newsResult = await callQuantSysDaemon("get_stock_news", { symbol: params.symbol, num: 10 });
            results.news = JSON.parse(newsResult);
            break;
          case "announcements":
            const announcementsResult = await callQuantSysDaemon("get_announcements", { symbol: params.symbol });
            results.announcements = JSON.parse(announcementsResult);
            break;
          default:
            results[field] = { error: `Unknown field: ${field}` };
        }
      } catch (error: any) {
        results[field] = { error: error.message };
      }
    }

    return { content: [{ type: "text" as const, text: JSON.stringify(results, null, 2) }], details: undefined };
  },
};
```

- [ ] **Step 3: 编写测试**

创建 `src/infrastructure/tools/data/fetch-stock-tool.test.ts`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { dataFetchStockTool } from './fetch-stock-tool.js';
import * as quantsysDaemon from '../../quant/quantsys-daemon-adapter.js';

vi.mock('../../quant/quantsys-daemon-adapter.js');

describe('dataFetchStockTool', () => {
  it('should fetch info and price by default', async () => {
    vi.mocked(quantsysDaemon.callQuantSysDaemon)
      .mockResolvedValueOnce(JSON.stringify({ name: '贵州茅台', sector: '白酒' }))
      .mockResolvedValueOnce(JSON.stringify({ price: 1800, change_pct: 2.5 }));

    const result = await dataFetchStockTool.execute('test-call', { symbol: '600519' });
    const data = JSON.parse(result.content[0].text);

    expect(data.symbol).toBe('600519');
    expect(data.info.name).toBe('贵州茅台');
    expect(data.price.price).toBe(1800);
  });

  it('should fetch only requested fields', async () => {
    vi.mocked(quantsysDaemon.callQuantSysDaemon)
      .mockResolvedValueOnce(JSON.stringify({ title: 'News 1' }));

    const result = await dataFetchStockTool.execute('test-call', { 
      symbol: '600519', 
      fields: ['news'] 
    });
    const data = JSON.parse(result.content[0].text);

    expect(data.news).toBeDefined();
    expect(data.info).toBeUndefined();
    expect(data.price).toBeUndefined();
  });

  it('should reject invalid stock codes', async () => {
    const result = await dataFetchStockTool.execute('test-call', { symbol: 'INVALID' });
    const data = JSON.parse(result.content[0].text);

    expect(data.error).toContain('不支持的股票代码');
    expect(data.invalid_format).toBe(true);
  });
});
```

- [ ] **Step 4: 运行测试**

```bash
npm test -- src/infrastructure/tools/data/fetch-stock-tool.test.ts
```

Expected: 所有测试通过

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/tools/data/
git commit -m "feat(tools): add data_fetch_stock tool (L1 data pipeline)

- 整合 get_stock_info/price/news/announcements 为单一工具
- 支持多字段组合查询
- 智能路由到具体数据源
- 统一错误处理"
```

---


## Task 2-6: 创建其他层级工具（简化版）

由于篇幅限制，Task 2-6 采用简化描述。执行时参考 Task 1 的模式展开。

### Task 2: L1 数据管道 - data_fetch_kline 和 data_fetch_financial
- 重命名 get_stock_history → data_fetch_kline
- 重命名 get_financial_data → data_fetch_financial

### Task 3: L2 因子工厂 - factor_calculate
- 整合 analyze_technical, get_valuation, get_quality_score 等
- 使用 factors 参数批量计算

### Task 4: L4 组合构建 - portfolio_rebalance
- 重命名 manage_portfolio → portfolio_rebalance

### Task 5: L5 执行引擎 - trade_manage_orders
- 重命名 manageOrdersTool → trade_manage_orders

### Task 6: L6 监控运维 - monitor_alert
- 重命名 notificationTools → monitor_alert

---

## Task 7: 更新工具注册中心

**Files:** src/infrastructure/tools/index.ts

- [ ] Step 1: 删除旧工具导入
- [ ] Step 2: 添加新工具导入
- [ ] Step 3: 重写 allCustomTools 数组
- [ ] Step 4: 运行 npm run build
- [ ] Step 5: Commit

---

## Task 8: 删除旧工具目录

- [ ] Step 1: git rm -r src/infrastructure/tools/invest/ analysis/ trading/
- [ ] Step 2: npm test
- [ ] Step 3: Commit

---

## Task 9: 更新文档

- [ ] Step 1: 更新 CLAUDE.md
- [ ] Step 2: Commit

---

## Task 10: 端到端测试

- [ ] Step 1: 编写集成测试
- [ ] Step 2: npm test
- [ ] Step 3: Commit

---

## 成功标准

- ✅ 工具数量从 61 降到 30
- ✅ 统一命名规范
- ✅ 所有测试通过

