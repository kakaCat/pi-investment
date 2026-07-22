# agent-ts 账户工具改造实施计划（计划 2）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** agent-ts 的 portfolio_* 工具接入多账户域：修复 portfolio_trade 断链（v2 不存在的 /api/portfolio/trade → /api/simulation/accounts/<name>/trade），账户显式化（agent 代管策略账户，必须显式指定 account）。

**Architecture:** QuantV2Client 新增 5 个账户方法（fetchV2 统一错误处理）；portfolio_status 扩展 list/get 双 action（list=账户发现，get=指定账户详情）；portfolio_trade/portfolio_analyze 新增必填 account 参数；新增 portfolio_account 工具（开户/归档）。v2 的 400/404 响应自带 available_accounts，工具原样透传给模型。

**Tech Stack:** TypeScript ESM、@sinclair/typebox、Jest（--experimental-vm-modules，co-located *.test.ts）。

**Spec:** `docs/superpowers/specs/2026-07-19-multi-account-domain-design.md` §5
**前置：** 计划 1 已完成——v2 端点 `GET/POST /api/simulation/accounts`、`GET /api/simulation/accounts/<name>`、`POST /api/simulation/accounts/<name>/trade`、`GET /api/simulation/trades|performance`（account_name 必填，400/404 带 available_accounts）。

**工作目录：** `agent-ts/`（monorepo 父仓库统一管理，新建 feature 分支）

---

### Task 0: 建分支

- [ ] **Step 1: 创建 feature 分支**

```bash
cd /Users/mac/Documents/ai/pi-investment
git checkout -b feature/multi-account-agent
```

---

### Task 1: QuantV2Client 账户方法

**Files:**
- Modify: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`（追加函数）
- Test: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client-accounts.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// agent-ts/src/infrastructure/adapters/quant/quant-v2-client-accounts.test.ts
import { describe, expect, test, jest, beforeEach } from "@jest/globals";
import {
  listAccounts,
  getAccount,
  createAccount,
  executeAccountTrade,
  getAccountTrades,
} from "./quant-v2-client.js";

const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
(global as any).fetch = mockFetch;

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("QuantV2Client 账户方法", () => {
  beforeEach(() => mockFetch.mockReset());

  test("listAccounts 调用账户发现端点", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: { accounts: [], total: 0 } }));
    await listAccounts();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/simulation/accounts"),
      expect.anything(),
    );
  });

  test("getAccount 按账户名查询", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: {} }));
    await getAccount("v13_simulation");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/simulation/accounts/v13_simulation"),
      expect.anything(),
    );
  });

  test("createAccount POST 开户参数", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: { account_name: "x" } }));
    await createAccount({ account_name: "x", initial_capital: 50000, display_name: "X" });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/api/simulation/accounts");
    expect(opts?.method).toBe("POST");
    expect(JSON.parse(String(opts?.body))).toMatchObject({ account_name: "x", initial_capital: 50000 });
  });

  test("executeAccountTrade POST 到账户交易端点", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: { order_id: 1 } }));
    await executeAccountTrade("v13_simulation", {
      action: "buy", symbol: "600519", shares: 100, reason: "测试买入理由：不少于十个字",
    });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/api/simulation/accounts/v13_simulation/trade");
    expect(opts?.method).toBe("POST");
  });

  test("getAccountTrades 携带 account_name", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: [] }));
    await getAccountTrades("v13_simulation", 50);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/simulation/trades?account_name=v13_simulation"),
      expect.anything(),
    );
  });

  test("v2 错误响应（400/404）透传 available_accounts", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ success: false, error: "account_name is required", available_accounts: ["v13_simulation"] }, 400));
    await expect(getAccountTrades("", 50)).rejects.toThrow(/account_name is required/);
  });
});
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/mac/Documents/ai/pi-investment/agent-ts
npx jest src/infrastructure/adapters/quant/quant-v2-client-accounts.test.ts 2>&1 | tail -5
```
预期：FAIL（函数未导出）

- [ ] **Step 3: 实现客户端方法（追加到 quant-v2-client.ts 末尾）**

```typescript
// ==================== 多账户域（simulation accounts） ====================

export interface AccountSummary {
  account_name: string;
  display_name: string | null;
  strategy_name: string | null;
  status: string;
  cash_available: number;
  cash_frozen: number;
  position_value: number;
  total_value: number;
  cumulative_return: number;
  positions_count: number;
}

export interface AccountTradeRequest {
  action: "buy" | "sell";
  symbol: string;
  shares?: number;
  amount?: number;
  price_limit?: number;
  reason: string;
}

/** 账户发现：列出账户 + 摘要 */
export async function listAccounts(): Promise<{ accounts: AccountSummary[]; total: number }> {
  const result = await fetchV2<{ success: boolean; data: { accounts: AccountSummary[]; total: number } }>(
    `${V2_API_BASE}/api/simulation/accounts`,
  );
  return result.data;
}

/** 查询账户详情（资金两态 + 持仓） */
export async function getAccount(accountName: string): Promise<any> {
  const result = await fetchV2<{ success: boolean; data: any }>(
    `${V2_API_BASE}/api/simulation/accounts/${encodeURIComponent(accountName)}`,
  );
  return result.data;
}

/** 开户 */
export async function createAccount(params: {
  account_name: string;
  initial_capital: number;
  display_name?: string;
  strategy_name?: string;
}): Promise<{ account_name: string }> {
  const result = await fetchV2<{ success: boolean; data: { account_name: string } }>(
    `${V2_API_BASE}/api/simulation/accounts`,
    { method: "POST", body: params },
  );
  return result.data;
}

/** 手工/代管交易（agent 虚拟仓核心） */
export async function executeAccountTrade(
  accountName: string,
  req: AccountTradeRequest,
): Promise<any> {
  const result = await fetchV2<{ success: boolean; data: any }>(
    `${V2_API_BASE}/api/simulation/accounts/${encodeURIComponent(accountName)}/trade`,
    { method: "POST", body: req },
  );
  return result.data;
}

/** 账户交易记录 */
export async function getAccountTrades(accountName: string, limit = 50): Promise<any[]> {
  const result = await fetchV2<{ success: boolean; data: any[] }>(
    `${V2_API_BASE}/api/simulation/trades?account_name=${encodeURIComponent(accountName)}&limit=${limit}`,
  );
  return result.data;
}

/** 账户绩效（净值快照） */
export async function getAccountPerformance(accountName: string): Promise<any> {
  const result = await fetchV2<{ success: boolean; data: any }>(
    `${V2_API_BASE}/api/simulation/performance?account_name=${encodeURIComponent(accountName)}`,
  );
  return result.data;
}
```

- [ ] **Step 4: 测试通过**

```bash
npx jest src/infrastructure/adapters/quant/quant-v2-client-accounts.test.ts 2>&1 | tail -3
```
预期：6 个测试全过

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts agent-ts/src/infrastructure/adapters/quant/quant-v2-client-accounts.test.ts
git commit -m "feat: QuantV2Client 多账户方法（发现/详情/开户/交易/记录/绩效）"
```

---

### Task 2: portfolio_status 工具改造（list/get 双 action）

**Files:**
- Modify: `agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.ts`
- Modify: `agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts`

- [ ] **Step 1: 先更新失败测试（computePortfolioView 对齐新域模型 + account 必填）**

```typescript
// portfolio-status-tool.test.ts 追加
import { getPortfolioStatus } from "./portfolio-status-tool.js";

describe("portfolio_status 账户显式化", () => {
  test("action=get 缺 account 返回错误和提示", async () => {
    const result = await getPortfolioStatus({ action: "get" } as any);
    expect((result as any).success).toBe(false);
    expect((result as any).error).toMatch(/account/);
  });
});

describe("computePortfolioView 新域模型", () => {
  test("资金两态 + 新持仓列映射", () => {
    const view = computePortfolioView({
      cash_available: "110030.89",
      cash_frozen: "0",
      position_value: "38255",
      total_value: "148285.89",
      cumulative_return: "0.483",
      positions: [{
        symbol: "601888", shares_total: 700, shares_available: 700,
        avg_cost: "52.87", current_price: "54.65", market_value: "38255",
        profit_total: "1246", profit_total_rate: "0.0337",
      }],
    });
    expect(view.cash).toBeCloseTo(110030.89, 2);
    expect(view.total_assets).toBeCloseTo(148285.89, 2);
    expect(view.total_market_value).toBeCloseTo(38255, 2);
    expect(view.holdings[0].shares).toBe(700);
    expect(view.holdings[0].cost_price).toBeCloseTo(52.87, 2);
    expect(view.holdings[0].pnl).toBeCloseTo(1246, 2);
  });
});
```

并导出 `getPortfolioStatus`（当前为模块内私有函数，改为 export）。

- [ ] **Step 2: 运行确认失败**

```bash
npx jest src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts 2>&1 | tail -5
```
预期：FAIL

- [ ] **Step 3: 改造工具**

`portfolio-status-tool.ts` 关键改动：

```typescript
import { listAccounts, getAccount } from "../../adapters/quant/quant-v2-client.js";

interface PortfolioStatusInput {
  action?: "list" | "get";
  account?: string;
  detailed?: boolean;
}

// computePortfolioView 内字段映射更新（持仓新列 + 资金两态）：
//   cash: Number(portfolio.cash_available ?? portfolio.cash) || 0
//   持仓市值直接用 position_value（缺失时回退恒等式推导）
//   holdings: h.shares_total ?? h.shares；h.avg_cost ?? h.avg_price；
//             h.profit_total ?? h.profit；h.profit_total_rate ?? h.profit_rate

export async function getPortfolioStatus(input: PortfolioStatusInput) {
  const action = input.action ?? "get";
  try {
    if (action === "list") {
      const { accounts, total } = await listAccounts();
      return {
        success: true,
        accounts,
        total,
        summary: accounts.length === 0
          ? "当前没有任何账户"
          : `共 ${total} 个账户：\n` + accounts.map(a =>
              `  - ${a.account_name}（${a.display_name ?? ""}）` +
              `${a.strategy_name ? ` [策略:${a.strategy_name}]` : ""}` +
              ` 总资产 ¥${a.total_value.toLocaleString("zh-CN")}` +
              ` 收益率 ${(a.cumulative_return * 100).toFixed(2)}%`).join("\n"),
        hint: "使用 portfolio_status({ action: 'get', account: '<账户名>' }) 查看指定账户",
      };
    }
    // action=get：account 必填
    if (!input.account) {
      return {
        success: false,
        error: "缺少必填参数 account（代管账户名）",
        hint: "先用 portfolio_status({ action: 'list' }) 查看可用账户",
      };
    }
    const data = await getAccount(input.account);
    return computePortfolioView(data);
  } catch (error) {
    return {
      success: false,
      error: `API调用失败: ${error instanceof Error ? error.message : String(error)}`,
      hint: "请检查quantsys-v2服务是否运行，或先用 action=list 确认账户名",
    };
  }
}
```

工具定义更新（name/label 不变，description 与 parameters）：

```typescript
parameters: Type.Object({
  action: Type.Optional(Type.Union([Type.Literal("list"), Type.Literal("get")], {
    description: "list=账户发现（列出所有代管账户）；get=查看指定账户（默认）",
    default: "get",
  })),
  account: Type.Optional(Type.String({
    description: "账户名（action=get 时必填），如 v13_simulation。不确定时先用 action=list",
  })),
  detailed: Type.Optional(Type.Boolean({ description: "是否返回详细信息", default: false })),
}),
// description 要点：
// "Agent 是策略账户的操盘手。交易/查仓前必须先 action=list 确认目标账户，禁止臆测账户名。"
```

- [ ] **Step 4: 测试通过**

```bash
npx jest src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts 2>&1 | tail -3
```
预期：全过（含既有恒等式用例——若旧用例字段名冲突，按新域模型修正期望值）

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.ts agent-ts/src/infrastructure/tools/portfolio/portfolio-status-tool.test.ts
git commit -m "feat: portfolio_status 双 action（list 账户发现 / get 指定账户，account 必填）"
```

---

### Task 3: portfolio_trade 工具修复（断链 → simulation 交易端点）

**Files:**
- Modify: `agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.ts`
- Test: `agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.test.ts`（新建）

- [ ] **Step 1: 写失败测试**

```typescript
// portfolio-trade-tool.test.ts
import { describe, expect, test, jest, beforeEach } from "@jest/globals";
import { portfolioTradeTool } from "./portfolio-trade-tool.js";

const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
(global as any).fetch = mockFetch;

describe("portfolio_trade 账户显式化", () => {
  beforeEach(() => mockFetch.mockReset());

  test("缺 account 直接拒绝", async () => {
    const result = await portfolioTradeTool.execute("t1", {
      action: "buy", symbol: "600519", reason: "测试买入理由：不少于十个字",
    } as any) as any;
    expect(result.success).toBe(false);
    expect(result.error).toMatch(/account/);
  });

  test("交易提交到 simulation 账户端点（不再调 /api/portfolio/trade）", async () => {
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      success: true,
      data: { order_id: 1, order_status: "filled", price: 10, shares: 100, amount: 1000 },
    }), { status: 200 }));
    const result = await portfolioTradeTool.execute("t2", {
      action: "buy", symbol: "600519", account: "v13_simulation",
      shares: 100, reason: "测试买入理由：不少于十个字",
    } as any) as any;
    expect(result.success).toBe(true);
    const [url] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/api/simulation/accounts/v13_simulation/trade");
    expect(String(url)).not.toContain("/api/portfolio/trade");
  });
});
```

- [ ] **Step 2: 运行确认失败**

```bash
npx jest src/infrastructure/tools/portfolio/portfolio-trade-tool.test.ts 2>&1 | tail -5
```
预期：FAIL（当前实现调 /api/portfolio/trade 且无 account 校验）

- [ ] **Step 3: 改造工具（核心 diff）**

```typescript
import { executeAccountTrade } from "../../adapters/quant/quant-v2-client.js";

interface PortfolioTradeInput {
  action: "buy" | "sell";
  symbol: string;
  account: string;            // 新增必填：代管账户名
  reason: string;
  amount?: number;
  shares?: number;
  price_limit?: number;
  strategy?: string;
}

async function executePortfolioTrade(input: PortfolioTradeInput) {
  if (!input.account) {
    return {
      success: false,
      error: "缺少必填参数 account（代管账户名）",
      hint: "先用 portfolio_status({ action: 'list' }) 查看可用账户",
    };
  }
  if (!input.reason || input.reason.trim().length < 10) {
    return {
      success: false,
      error: "必须提供详细的交易理由（至少10字）",
      hint: "例如：技术面突破+机构增持+RSI超卖反弹",
    };
  }
  try {
    const data = await executeAccountTrade(input.account, {
      action: input.action,
      symbol: input.symbol,
      amount: input.amount,
      shares: input.shares,
      price_limit: input.price_limit,
      reason: `${input.reason}${input.strategy ? ` [策略:${input.strategy}]` : ""}`,
    });
    return {
      success: true,
      order_id: data.order_id,
      message: `${input.action === "buy" ? "买入" : "卖出"}订单已成交`,
      details: {
        account: input.account,
        symbol: input.symbol,
        action: input.action,
        price: data.price,
        shares: data.shares,
        amount: data.amount,
        commission: data.commission,
        realized_pnl: data.realized_pnl ?? undefined,
        reason: input.reason,
      },
      note: input.action === "buy"
        ? "T+1规则：今日买入，明日才能卖出"
        : "卖出已成交，已实现盈亏见 realized_pnl",
    };
  } catch (error) {
    return {
      success: false,
      error: `交易执行失败: ${error instanceof Error ? error.message : String(error)}`,
      hint: "账户名错误或风控拦截；先用 portfolio_status({ action: 'list' }) 确认账户",
    };
  }
}
```

parameters 增加：

```typescript
account: Type.String({
  description: "代管账户名（必填），如 v13_simulation。不确定时先 portfolio_status({ action: 'list' })",
}),
```

description 要点更新：强调「Agent 是策略账户操盘手，每笔交易必须指定 account 和 reason」。

- [ ] **Step 4: 测试通过 + 该文件相关测试全跑**

```bash
npx jest src/infrastructure/tools/portfolio/ 2>&1 | tail -4
```
预期：全过

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.ts agent-ts/src/infrastructure/tools/portfolio/portfolio-trade-tool.test.ts
git commit -m "fix: portfolio_trade 断链修复（改调 simulation 账户交易端点）+ account 必填"
```

---

### Task 4: portfolio_analyze 工具改造（account 必填）

**Files:**
- Modify: `agent-ts/src/infrastructure/tools/portfolio/portfolio-analyze-tool.ts`
- Test: `agent-ts/src/infrastructure/tools/portfolio/portfolio-analyze-tool.test.ts`（新建）

- [ ] **Step 1: 写失败测试**

```typescript
// portfolio-analyze-tool.test.ts
import { describe, expect, test, jest, beforeEach } from "@jest/globals";
import { portfolioAnalyzeTool } from "./portfolio-analyze-tool.js";

const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
(global as any).fetch = mockFetch;

describe("portfolio_analyze 账户显式化", () => {
  beforeEach(() => mockFetch.mockReset());

  test("缺 account 直接拒绝", async () => {
    const result = await portfolioAnalyzeTool.execute("t1", {} as any) as any;
    expect(result.success).toBe(false);
    expect(result.error).toMatch(/account/);
  });

  test("按 account 查询持仓并给出止盈建议（新域模型字段）", async () => {
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      success: true,
      data: {
        account_name: "v13_simulation", cash_available: 50000, position_value: 60000,
        total_value: 110000, cumulative_return: 0.1,
        positions: [{
          symbol: "600519", shares_total: 40, shares_available: 40,
          avg_cost: 1000, current_price: 1150, market_value: 46000,
          profit_total: 6000, profit_total_rate: 0.15,
        }],
      },
    }), { status: 200 }));
    const result = await portfolioAnalyzeTool.execute("t2", { account: "v13_simulation" } as any) as any;
    expect(result.success).toBe(true);
    expect(String(mockFetch.mock.calls[0][0])).toContain("/api/simulation/accounts/v13_simulation");
    expect(result.analysis[0].action).toBe("take_profit");
  });
});
```

- [ ] **Step 2: 运行确认失败**

```bash
npx jest src/infrastructure/tools/portfolio/portfolio-analyze-tool.test.ts 2>&1 | tail -5
```
预期：FAIL

- [ ] **Step 3: 改造工具（核心 diff）**

```typescript
import { getAccount } from "../../adapters/quant/quant-v2-client.js";

interface PortfolioAnalyzeInput {
  account: string;          // 新增必填
  check_risk?: boolean;
}

// analyzePortfolio 开头：
if (!input.account) {
  return {
    success: false,
    error: "缺少必填参数 account（代管账户名）",
    hint: "先用 portfolio_status({ action: 'list' }) 查看可用账户",
  };
}
const portfolio = await getAccount(input.account);
const holdings = portfolio.positions || [];

// T+1 判定改用 shares_available（替代不可靠的 days_held===0）：
//   if ((holding.shares_available ?? holding.shares_total ?? 0) <= 0) → wait_t1
// 字段映射：pnl_pct = holding.profit_total_rate（小数）× 100
//   shares: holding.shares_total；cost_price: holding.avg_cost；
//   pnl: holding.profit_total
// 注意：v2 profit_total_rate 是小数（0.15 = 15%），tool 内分析阈值用百分比，
//   统一 pnl_pct = Number(holding.profit_total_rate ?? 0) * 100
```

parameters 增加 `account`（同 Task 3 description 风格）。

- [ ] **Step 4: 测试通过**

```bash
npx jest src/infrastructure/tools/portfolio/portfolio-analyze-tool.test.ts 2>&1 | tail -3
```
预期：2 个测试全过

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/infrastructure/tools/portfolio/portfolio-analyze-tool.ts agent-ts/src/infrastructure/tools/portfolio/portfolio-analyze-tool.test.ts
git commit -m "feat: portfolio_analyze account 必填 + T+1 改用 shares_available 判定"
```

---

### Task 5: portfolio_account 新工具（开户/归档）+ 注册

**Files:**
- Create: `agent-ts/src/infrastructure/tools/portfolio/portfolio-account-tool.ts`
- Modify: `agent-ts/src/infrastructure/tools/index.ts`（import + 注册）
- Test: `agent-ts/src/infrastructure/tools/portfolio/portfolio-account-tool.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// portfolio-account-tool.test.ts
import { describe, expect, test, jest, beforeEach } from "@jest/globals";
import { portfolioAccountTool } from "./portfolio-account-tool.js";

const mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
(global as any).fetch = mockFetch;

describe("portfolio_account 开户", () => {
  beforeEach(() => mockFetch.mockReset());

  test("create 提交开户参数", async () => {
    mockFetch.mockResolvedValueOnce(new Response(JSON.stringify({
      success: true, data: { account_name: "manual_test" },
    }), { status: 201 }));
    const result = await portfolioAccountTool.execute("t1", {
      action: "create", account_name: "manual_test", initial_capital: 100000,
      display_name: "手工测试仓",
    } as any) as any;
    expect(result.success).toBe(true);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("/api/simulation/accounts");
    expect(opts?.method).toBe("POST");
  });

  test("禁止创建名为 default 的账户", async () => {
    const result = await portfolioAccountTool.execute("t2", {
      action: "create", account_name: "default", initial_capital: 100000,
    } as any) as any;
    expect(result.success).toBe(false);
    expect(mockFetch).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 运行确认失败**

```bash
npx jest src/infrastructure/tools/portfolio/portfolio-account-tool.test.ts 2>&1 | tail -3
```
预期：FAIL

- [ ] **Step 3: 实现工具**

```typescript
/**
 * Portfolio Account Tool - 账户管理（开户）
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution } from "../shared/error-handler.js";
import { createAccount } from "../../adapters/quant/quant-v2-client.js";

interface PortfolioAccountInput {
  action: "create";
  account_name: string;
  initial_capital: number;
  display_name?: string;
  strategy_name?: string;
}

async function manageAccount(input: PortfolioAccountInput) {
  if (input.account_name === "default") {
    return { success: false, error: "禁止使用账户名 default（历史公共账户，已废弃）" };
  }
  try {
    const data = await createAccount({
      account_name: input.account_name,
      initial_capital: input.initial_capital,
      display_name: input.display_name,
      strategy_name: input.strategy_name,
    });
    return {
      success: true,
      account_name: data.account_name,
      message: `账户 ${data.account_name} 开户成功，初始资金 ¥${input.initial_capital.toLocaleString("zh-CN")}`,
    };
  } catch (error) {
    return {
      success: false,
      error: `开户失败: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

export const portfolioAccountTool: ToolDefinition = {
  name: "portfolio_account",
  label: "账户管理",
  description:
    "开立新的模拟账户（agent 代管账户体系）。账户名规范：策略账户 {策略}_simulation，" +
    "其他用途自由命名（禁止 default）。开户后可用 portfolio_trade 指定该账户交易。",
  parameters: Type.Object({
    action: Type.Literal("create", { description: "create=开户" }),
    account_name: Type.String({ description: "账户名（禁止 default）" }),
    initial_capital: Type.Number({ description: "初始资金（元）", minimum: 1000 }),
    display_name: Type.Optional(Type.String({ description: "显示名" })),
    strategy_name: Type.Optional(Type.String({ description: "绑定策略名（可选）" })),
  }),
  execute: async (toolCallId: string, input: PortfolioAccountInput) => {
    return wrapToolExecution(async () => await manageAccount(input), { toolName: "portfolio_account" });
  },
};
```

注册（`tools/index.ts`）：

```typescript
import { portfolioAccountTool } from "./portfolio/portfolio-account-tool.js";  // 新增：账户管理
// ...allTools 数组中 portfolioTradeTool 附近追加：
  portfolioAccountTool,           // portfolio_account - 账户管理（开户）
```

- [ ] **Step 4: 测试通过**

```bash
npx jest src/infrastructure/tools/portfolio/portfolio-account-tool.test.ts 2>&1 | tail -3
```
预期：2 个测试全过

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/infrastructure/tools/portfolio/portfolio-account-tool.ts agent-ts/src/infrastructure/tools/portfolio/portfolio-account-tool.test.ts agent-ts/src/infrastructure/tools/index.ts
git commit -m "feat: portfolio_account 工具（开户，禁 default）并注册"
```

---

### Task 6: 调度任务提示词更新 + 全量回归 + e2e

**Files:**
- Modify: `agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts`
- Modify: `agent-ts/src/api/wake-channel.ts`

- [ ] **Step 1: 更新提示词中的工具用法指引**

`agent-decision-tasks.ts` 与 `wake-channel.ts` 中所有 `portfolio_status` / `portfolio_trade` 用法说明，统一改为账户显式化流程：

```
1. 使用 portfolio_status({ action: 'list' }) 查看所有代管账户
2. 使用 portfolio_status({ action: 'get', account: '<账户名>' }) 查看指定账户持仓
3. 使用 portfolio_trade({ account: '<账户名>', action, symbol, shares/amount, reason }) 执行交易
```

逐一替换原文中 `portfolio_status 查看当前虚拟仓状态`、`portfolio_trade 执行卖出/买入` 等旧表述（保持任务结构不变，仅更新工具调用指引段落）。

- [ ] **Step 2: 全量 jest 回归**

```bash
npm test 2>&1 | tail -6
```
预期：全绿；若既有用例引用 portfolio_* 旧行为（硬编码 default），按新契约修正

- [ ] **Step 3: tsc 构建检查**

```bash
npm run build 2>&1 | tail -3
```
预期：无错误

- [ ] **Step 4: e2e 冒烟（v2 后端运行中）**

```bash
export NO_PROXY=127.0.0.1,localhost
# 验证工具依赖的端点全部可用
curl -s http://127.0.0.1:5001/api/simulation/accounts | python3 -c "import json,sys; assert json.load(sys.stdin)['success']; print('✅ listAccounts')"
curl -s http://127.0.0.1:5001/api/simulation/accounts/v13_simulation | python3 -c "import json,sys; assert json.load(sys.stdin)['success']; print('✅ getAccount')"
curl -s "http://127.0.0.1:5001/api/simulation/trades?account_name=v13_simulation&limit=1" | python3 -c "import json,sys; assert json.load(sys.stdin)['success']; print('✅ getAccountTrades')"
```

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/services/scheduler/tasks/agent-decision-tasks.ts agent-ts/src/api/wake-channel.ts
git commit -m "docs: 调度任务与唤醒通道提示词改为账户显式化流程"
```

---

## Self-Review 记录

- 覆盖：spec §5 全部（client 方法、status list/get、trade 修复+account 必填、analyze account 必填、account 新工具、提示词）✅
- 类型一致性：`listAccounts/getAccount/executeAccountTrade/createAccount` 在 Task 1 定义、Task 2/3/4/5 使用签名一致；`getPortfolioStatus` 导出供测试 ✅
- 已知注意点：Task 2 既有恒等式测试用例使用旧字段（cash/shares/avg_price），computePortfolioView 需保持对旧字段的 `??` 兼容映射，避免破坏既有用例；portfolio_trade 的 `strategy` 参数拼入 reason 保留审计信息（v2 端点无 strategy 字段）
