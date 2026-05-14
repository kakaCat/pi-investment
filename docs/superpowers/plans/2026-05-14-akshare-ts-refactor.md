# akshare-ts 模块拆分实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 1,248 行的 `src/infrastructure/akshare-ts/index.ts` 拆分为 10 个职责清晰的模块文件，建立数据层 → 指标层 → 服务层的分层架构

**Architecture:** 采用渐进式迁移策略，先提取共享层，再按数据层 → 指标层 → 服务层顺序迁移，最后重写导出层。每个阶段独立可验证，保持向后兼容。

**Tech Stack:** TypeScript, Node.js, 现有的 data-sources 模块（sina/eastmoney/stooq）

---

## 文件结构规划

**新建文件：**
- `src/infrastructure/akshare-ts/shared.ts` — 共享工具函数和类型（~100行）
- `src/infrastructure/akshare-ts/data/market.ts` — 市场数据获取（~150行）
- `src/infrastructure/akshare-ts/data/financial.ts` — 财务数据获取（~200行）
- `src/infrastructure/akshare-ts/indicators/technical.ts` — 技术指标计算（~150行）
- `src/infrastructure/akshare-ts/indicators/chart-patterns.ts` — K线形态识别（~200行）
- `src/infrastructure/akshare-ts/services/buy-range.ts` — 买入区间计算（~80行）
- `src/infrastructure/akshare-ts/services/price-action.ts` — 走势分析（~120行）
- `src/infrastructure/akshare-ts/services/exit-plan.ts` — 止盈计划（~60行）
- `src/infrastructure/akshare-ts/services/peer-comparison.ts` — 同业对比（~80行）
- `src/infrastructure/akshare-ts/portfolio.ts` — 持仓管理（~60行）

**修改文件：**
- `src/infrastructure/akshare-ts/index.ts` — 重写为纯导出层（~80行）

**备份文件：**
- `src/infrastructure/akshare-ts/index.ts.backup` — 原始文件备份

---

## Task 1: 准备工作 - 创建目录结构和备份

**Files:**
- Create: `src/infrastructure/akshare-ts/data/`
- Create: `src/infrastructure/akshare-ts/indicators/`
- Create: `src/infrastructure/akshare-ts/services/`
- Backup: `src/infrastructure/akshare-ts/index.ts` → `index.ts.backup`

- [ ] **Step 1: 创建子目录**

```bash
mkdir -p src/infrastructure/akshare-ts/data
mkdir -p src/infrastructure/akshare-ts/indicators
mkdir -p src/infrastructure/akshare-ts/services
```

- [ ] **Step 2: 备份原始文件**

```bash
cp src/infrastructure/akshare-ts/index.ts src/infrastructure/akshare-ts/index.ts.backup
```

- [ ] **Step 3: 验证备份**

```bash
ls -lh src/infrastructure/akshare-ts/index.ts.backup
wc -l src/infrastructure/akshare-ts/index.ts.backup
```

Expected: 文件存在，行数约 1248 行

- [ ] **Step 4: 提交准备工作**

```bash
git add src/infrastructure/akshare-ts/index.ts.backup
git commit -m "chore(akshare-ts): backup original index.ts before refactoring"
```

---

## Task 2: 提取共享层 - shared.ts

**Files:**
- Create: `src/infrastructure/akshare-ts/shared.ts`
- Read: `src/infrastructure/akshare-ts/index.ts.backup` (lines 10-156)

- [ ] **Step 1: 创建 shared.ts 文件头部**

```typescript
/**
 * Shared utilities, types, and services for akshare-ts
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { execFile } from "child_process";
import { promisify } from "util";
import { fileURLToPath } from "url";
import { StockDBService, KlineCacheService } from "../../services/data/stock-db-index.js";
import { callPythonDaemon } from "../tools/python-bridge.js";

const execFileAsync = promisify(execFile);
const __dirname = fileURLToPath(new URL(".", import.meta.url));
const pythonScript = join(__dirname, "..", "..", "..", "python", "akshare_bridge.py");
```

- [ ] **Step 2: 添加 Python 桥接函数**

```typescript
/**
 * callPython - Direct Python bridge for functions not yet in TS
 */
export async function callPython(func: string, args: Record<string, unknown> = {}): Promise<string> {
  try {
    const argsJson = JSON.stringify(args);
    const { stdout } = await execFileAsync(
      "python3",
      [pythonScript, func, argsJson],
      { timeout: 60000 }
    );
    return stdout.trim();
  } catch (error: unknown) {
    if (error instanceof Error) {
      const spawnError = error as any;
      const stderr = spawnError.stderr ? String(spawnError.stderr).trim() : "";
      const msg = stderr || error.message;
      return JSON.stringify({ error: `Python调用失败: ${msg}` });
    }
    return JSON.stringify({ error: "Python调用失败（未知错误）" });
  }
}

export type JsonRecord = Record<string, unknown>;

export async function callPythonBridge(func: string, args: Record<string, unknown> = {}): Promise<JsonRecord> {
  const result = await callPythonDaemon(func, args);
  return JSON.parse(result) as JsonRecord;
}
```

- [ ] **Step 3: 添加工具函数**

```typescript
export function r2(v: number | null): number {
  return roundN(v, 2) ?? 0;
}

export function r4(v: number | null): number {
  return roundN(v, 4) ?? 0;
}

function roundN(v: number | null, decimals: number): number | null {
  if (v === null || !Number.isFinite(v)) return null;
  const factor = Math.pow(10, decimals);
  return Math.round(v * factor) / factor;
}

export function toNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value === "string") {
    const raw = value.trim();
    const unit = raw.includes("亿") ? 1e8 : raw.includes("万") ? 1e4 : 1;
    const cleaned = raw.replace(/,/g, "").replace(/%/g, "").replace(/[^\d.-]/g, "");
    const num = Number.parseFloat(cleaned);
    return Number.isFinite(num) ? num * unit : 0;
  }
  return 0;
}

export function findNumber(record: JsonRecord, keys: readonly string[]): number {
  for (const key of keys) {
    if (key in record && record[key] != null && `${record[key]}` !== "") {
      return toNumber(record[key]);
    }
  }
  return 0;
}

export function findString(record: JsonRecord, keys: readonly string[]): string {
  for (const key of keys) {
    if (key in record && record[key] != null && `${record[key]}`.trim() !== "") {
      return String(record[key]).trim();
    }
  }
  return "";
}

export function median(values: number[]): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

export function normalizeHolderName(name: string): string {
  return name.replace(/\s+/g, "").replace(/[（(].*?[）)]/g, "").trim();
}

export function computeQuarterEnds(limit = 8): string[] {
  const today = new Date();
  const year = today.getFullYear();
  const month = today.getMonth() + 1;
  const day = today.getDate();
  
  const quarterEnds = [
    { month: 3, day: 31, suffix: "0331" },
    { month: 6, day: 30, suffix: "0630" },
    { month: 9, day: 30, suffix: "0930" },
    { month: 12, day: 31, suffix: "1231" },
  ];

  const result: string[] = [];
  let currentYear = year;
  while (result.length < limit) {
    for (let i = quarterEnds.length - 1; i >= 0 && result.length < limit; i--) {
      const end = quarterEnds[i];
      if (
        currentYear === year &&
        (month < end.month || (month === end.month && day <= end.day))
      ) {
        continue;
      }
      result.push(`${currentYear}${end.suffix}`);
    }
    currentYear -= 1;
  }
  return result;
}

export function getQualityRating(score: number): "优秀" | "良好" | "一般" | "较差" {
  if (score >= 80) return "优秀";
  if (score >= 65) return "良好";
  if (score >= 50) return "一般";
  return "较差";
}
```

- [ ] **Step 4: 添加共享服务（懒加载）**

```typescript
const piDir = ".pi-invest";
let _stockDB: StockDBService | null = null;
let _klineCache: KlineCacheService | null = null;

export function getStockDB(): StockDBService {
  if (!_stockDB) _stockDB = new StockDBService(piDir);
  return _stockDB;
}

export function getKlineCache(): KlineCacheService {
  if (!_klineCache) _klineCache = new KlineCacheService(getStockDB());
  return _klineCache;
}
```

- [ ] **Step 5: 添加类型定义**

```typescript
export interface PortfolioData {
  holdings: Array<{
    symbol: string;
    quantity: number;
    avg_cost: number;
    notes: string;
    added_date: string;
    name?: string;
  }>;
  last_updated: string;
}

export type TsFn = (args: Record<string, unknown>) => Promise<string> | string;
```

- [ ] **Step 6: 验证 shared.ts 编译**

```bash
npx tsc --noEmit src/infrastructure/akshare-ts/shared.ts
```

Expected: 无编译错误

- [ ] **Step 7: 提交 shared.ts**

```bash
git add src/infrastructure/akshare-ts/shared.ts
git commit -m "refactor(akshare-ts): extract shared utilities to shared.ts"
```

---


## Task 3: 数据层 - market.ts（市场数据获取）

**Files:**
- Create: `src/infrastructure/akshare-ts/data/market.ts`
- Read: `src/infrastructure/akshare-ts/index.ts.backup` (lines 164-386)

- [ ] **Step 1: 创建 market.ts 文件头部和导入**

创建文件 `src/infrastructure/akshare-ts/data/market.ts`，内容包含导入语句和 8 个市场数据函数。

- [ ] **Step 2: 从 index.ts.backup 复制以下函数到 market.ts**

复制函数：
- `get_stock_realtime_price` (lines 166-197)
- `get_stock_history` (lines 201-248)
- `get_stock_info` (lines 252-280)
- `get_market_overview` (lines 284-304)
- `get_sector_list` (lines 308-320)
- `get_hk_stock_price` (lines 323-342)
- `get_hk_stock_info` (lines 345-361)
- `get_hk_stock_history` (lines 364-386)

更新导入路径：
- `./shared.js` → `../shared.js`
- `../../services/data/stock-db-index.js` 保持不变

- [ ] **Step 3: 验证 market.ts 编译**

```bash
npx tsc --noEmit src/infrastructure/akshare-ts/data/market.ts
```

Expected: 无编译错误

- [ ] **Step 4: 提交 market.ts**

```bash
git add src/infrastructure/akshare-ts/data/market.ts
git commit -m "refactor(akshare-ts): extract market data layer to data/market.ts"
```

---

## Task 4: 数据层 - financial.ts（财务数据获取）

**Files:**
- Create: `src/infrastructure/akshare-ts/data/financial.ts`
- Read: `src/infrastructure/akshare-ts/index.ts.backup` (lines 528-878)

- [ ] **Step 1: 从 index.ts.backup 复制财务相关函数到 financial.ts**

复制函数：
- `get_stock_valuation` (lines 528-537)
- `get_pe_percentile` (lines 540-549)
- `extractStatementRows` (lines 550-559, 内部函数)
- `get_quality_score` (lines 560-693)
- `get_stock_fund_flow` (lines 695-766)
- `fetchTopHolderSnapshot` (lines 768-788, 内部函数)
- `get_holder_changes` (lines 790-878)

更新导入：
```typescript
import { callPythonBridge, findNumber, findString, normalizeHolderName, computeQuarterEnds, r2, JsonRecord } from "../shared.js";
import { today } from "../../data-sources/http-client.js";
```

- [ ] **Step 2: 验证 financial.ts 编译**

```bash
npx tsc --noEmit src/infrastructure/akshare-ts/data/financial.ts
```

Expected: 无编译错误

- [ ] **Step 3: 提交 financial.ts**

```bash
git add src/infrastructure/akshare-ts/data/financial.ts
git commit -m "refactor(akshare-ts): extract financial data layer to data/financial.ts"
```

---

## Task 5: 指标层 - technical.ts（技术指标计算）

**Files:**
- Create: `src/infrastructure/akshare-ts/indicators/technical.ts`
- Read: `src/infrastructure/akshare-ts/index.ts.backup` (lines 389-478)

- [ ] **Step 1: 从 index.ts.backup 复制 calculate_technical_indicators 到 technical.ts**

复制函数：
- `calculate_technical_indicators` (lines 389-478)

更新导入：
```typescript
import {
  rollingMean, rsi as calcRsi, macd as calcMacd, bollinger, lastNum,
  kdj as calcKdj, atr as calcAtr, obv as calcObv, cci as calcCci,
  klinesToNumbers,
} from "../../data-sources/technical.js";
import { get_stock_history, get_stock_realtime_price } from "../data/market.js";
import { r2, r4, cleanSymbol } from "../shared.js";
import { today } from "../../data-sources/http-client.js";
```

- [ ] **Step 2: 验证 technical.ts 编译**

```bash
npx tsc --noEmit src/infrastructure/akshare-ts/indicators/technical.ts
```

Expected: 无编译错误

- [ ] **Step 3: 提交 technical.ts**

```bash
git add src/infrastructure/akshare-ts/indicators/technical.ts
git commit -m "refactor(akshare-ts): extract technical indicators to indicators/technical.ts"
```

---

## Task 6: 指标层 - chart-patterns.ts（K线形态识别）

**Files:**
- Create: `src/infrastructure/akshare-ts/indicators/chart-patterns.ts`
- Read: `src/infrastructure/akshare-ts/index.ts.backup` (lines 1098-1155)

- [ ] **Step 1: 从 index.ts.backup 复制 analyze_candlestick 到 chart-patterns.ts**

复制函数：
- `analyze_candlestick` (lines 1098-1155)

更新导入：
```typescript
import {
  candlestickPatterns, trendLines, fibonacci, priceGaps,
  klinesToNumbers,
} from "../../data-sources/technical.js";
import { fetchSinaKlines } from "../../data-sources/sina.js";
import { safeFloat, today } from "../../data-sources/http-client.js";
import { r2, cleanSymbol } from "../shared.js";
```

- [ ] **Step 2: 验证 chart-patterns.ts 编译**

```bash
npx tsc --noEmit src/infrastructure/akshare-ts/indicators/chart-patterns.ts
```

Expected: 无编译错误

- [ ] **Step 3: 提交 chart-patterns.ts**

```bash
git add src/infrastructure/akshare-ts/indicators/chart-patterns.ts
git commit -m "refactor(akshare-ts): extract chart patterns to indicators/chart-patterns.ts"
```

---

## Task 7: 服务层 - buy-range.ts（买入区间计算）

**Files:**
- Create: `src/infrastructure/akshare-ts/services/buy-range.ts`
- Read: `src/infrastructure/akshare-ts/index.ts.backup` (lines 482-524)

- [ ] **Step 1: 从 index.ts.backup 复制 calculate_buy_range 到 buy-range.ts**

复制函数：
- `calculate_buy_range` (lines 482-524)

更新导入：
```typescript
import { fetchSinaKlines, klinesToNumbers } from "../../data-sources/sina.js";
import { rollingMean, bollinger, lastNum } from "../../data-sources/technical.js";
import { r2, cleanSymbol } from "../shared.js";
```

- [ ] **Step 2: 验证 buy-range.ts 编译**

```bash
npx tsc --noEmit src/infrastructure/akshare-ts/services/buy-range.ts
```

Expected: 无编译错误

- [ ] **Step 3: 提交 buy-range.ts**

```bash
git add src/infrastructure/akshare-ts/services/buy-range.ts
git commit -m "refactor(akshare-ts): extract buy range service to services/buy-range.ts"
```

---

## Task 8: 服务层 - price-action.ts（走势分析）

**Files:**
- Create: `src/infrastructure/akshare-ts/services/price-action.ts`
- Read: `src/infrastructure/akshare-ts/index.ts.backup` (lines 996-1089)

- [ ] **Step 1: 从 index.ts.backup 复制 analyze_price_action 到 price-action.ts**

复制函数：
- `analyze_price_action` (lines 996-1089)

更新导入：
```typescript
import { fetchSinaKlines, klinesToNumbers } from "../../data-sources/sina.js";
import {
  rollingMean, swingLevels, calcObv, calcAtr, calcKdj, calcCci, calcRsi, lastNum,
} from "../../data-sources/technical.js";
import { today } from "../../data-sources/http-client.js";
import { r2, cleanSymbol } from "../shared.js";
```

- [ ] **Step 2: 验证 price-action.ts 编译**

```bash
npx tsc --noEmit src/infrastructure/akshare-ts/services/price-action.ts
```

Expected: 无编译错误

- [ ] **Step 3: 提交 price-action.ts**

```bash
git add src/infrastructure/akshare-ts/services/price-action.ts
git commit -m "refactor(akshare-ts): extract price action service to services/price-action.ts"
```

---

## Task 9: 服务层 - exit-plan.ts（止盈计划）

**Files:**
- Create: `src/infrastructure/akshare-ts/services/exit-plan.ts`
- Read: `src/infrastructure/akshare-ts/index.ts.backup` (lines 882-924)

- [ ] **Step 1: 从 index.ts.backup 复制 get_exit_plan 到 exit-plan.ts**

复制函数：
- `get_exit_plan` (lines 882-924)

更新导入：
```typescript
import { get_stock_realtime_price } from "../data/market.js";
import { r2, cleanSymbol } from "../shared.js";
import { today } from "../../data-sources/http-client.js";
```

- [ ] **Step 2: 验证 exit-plan.ts 编译**

```bash
npx tsc --noEmit src/infrastructure/akshare-ts/services/exit-plan.ts
```

Expected: 无编译错误

- [ ] **Step 3: 提交 exit-plan.ts**

```bash
git add src/infrastructure/akshare-ts/services/exit-plan.ts
git commit -m "refactor(akshare-ts): extract exit plan service to services/exit-plan.ts"
```

---

## Task 10: 服务层 - peer-comparison.ts（同业对比）

**Files:**
- Create: `src/infrastructure/akshare-ts/services/peer-comparison.ts`
- Read: `src/infrastructure/akshare-ts/index.ts.backup` (lines 1159-1217)

- [ ] **Step 1: 从 index.ts.backup 复制 compare_peers 到 peer-comparison.ts**

复制函数：
- `compare_peers` (lines 1159-1217)

更新导入：
```typescript
import { get_stock_info, get_sector_list, get_stock_realtime_price } from "../data/market.js";
import { safeFloat, today } from "../../data-sources/http-client.js";
```

- [ ] **Step 2: 验证 peer-comparison.ts 编译**

```bash
npx tsc --noEmit src/infrastructure/akshare-ts/services/peer-comparison.ts
```

Expected: 无编译错误

- [ ] **Step 3: 提交 peer-comparison.ts**

```bash
git add src/infrastructure/akshare-ts/services/peer-comparison.ts
git commit -m "refactor(akshare-ts): extract peer comparison service to services/peer-comparison.ts"
```

---


## Task 11: 其他模块 - portfolio.ts（持仓管理）

**Files:**
- Create: `src/infrastructure/akshare-ts/portfolio.ts`
- Read: `src/infrastructure/akshare-ts/index.ts.backup` (lines 928-981)

- [ ] **Step 1: 从 index.ts.backup 复制持仓管理相关代码到 portfolio.ts**

复制内容：
- `portfolioPath` 常量定义 (line 928)
- `PortfolioData` 接口定义 (lines 930-934)
- `loadPortfolio` 函数 (lines 936-939)
- `savePortfolio` 函数 (lines 941-944)
- `manage_portfolio` 函数 (lines 946-981)

更新导入：
```typescript
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import { today, nowStr } from "../data-sources/http-client.js";
```

注意：`PortfolioData` 类型已在 shared.ts 中定义，需要从 shared.ts 导入而不是重复定义。

- [ ] **Step 2: 验证 portfolio.ts 编译**

```bash
npx tsc --noEmit src/infrastructure/akshare-ts/portfolio.ts
```

Expected: 无编译错误

- [ ] **Step 3: 提交 portfolio.ts**

```bash
git add src/infrastructure/akshare-ts/portfolio.ts
git commit -m "refactor(akshare-ts): extract portfolio management to portfolio.ts"
```

---

## Task 12: 重写导出层 - index.ts

**Files:**
- Modify: `src/infrastructure/akshare-ts/index.ts`
- Read: `src/infrastructure/akshare-ts/index.ts.backup` (lines 1220-1248)

- [ ] **Step 1: 重写 index.ts 为纯导出层**

完全替换 `src/infrastructure/akshare-ts/index.ts` 内容：

```typescript
/**
 * AkShare-TS — TypeScript-native market data
 * 
 * Unified export layer for all akshare-ts modules
 */

// Re-export data layer
export {
  get_stock_realtime_price,
  get_stock_history,
  get_stock_info,
  get_market_overview,
  get_sector_list,
  get_hk_stock_price,
  get_hk_stock_info,
  get_hk_stock_history,
  cleanSymbol,
} from './data/market.js';

export {
  get_quality_score,
  get_stock_valuation,
  get_pe_percentile,
  get_stock_fund_flow,
  get_holder_changes,
} from './data/financial.js';

// Re-export indicators layer
export {
  calculate_technical_indicators,
} from './indicators/technical.js';

export {
  analyze_candlestick,
} from './indicators/chart-patterns.js';

// Re-export services layer
export {
  calculate_buy_range,
} from './services/buy-range.js';

export {
  analyze_price_action,
} from './services/price-action.js';

export {
  get_exit_plan,
} from './services/exit-plan.js';

export {
  compare_peers,
} from './services/peer-comparison.js';

// Re-export portfolio
export {
  manage_portfolio,
} from './portfolio.js';

// Re-export shared utilities
export {
  callPython,
  getQualityRating,
} from './shared.js';

// Function registry for tool routing
import type { TsFn } from './shared.js';
import {
  get_stock_realtime_price,
  get_stock_history,
  get_stock_info,
  get_market_overview,
  get_sector_list,
  get_hk_stock_price,
  get_hk_stock_info,
  get_hk_stock_history,
} from './data/market.js';
import {
  get_quality_score,
  get_stock_valuation,
  get_pe_percentile,
  get_stock_fund_flow,
  get_holder_changes,
} from './data/financial.js';
import { calculate_technical_indicators } from './indicators/technical.js';
import { analyze_candlestick } from './indicators/chart-patterns.js';
import { calculate_buy_range } from './services/buy-range.js';
import { analyze_price_action } from './services/price-action.js';
import { get_exit_plan } from './services/exit-plan.js';
import { compare_peers } from './services/peer-comparison.js';
import { manage_portfolio } from './portfolio.js';

export const TS_FUNCTIONS: Record<string, TsFn> = {
  get_stock_realtime_price: (a) => get_stock_realtime_price(a.symbol as string),
  get_stock_history: (a) => get_stock_history(
    a.symbol as string,
    a.period as string | undefined,
    a.start_date as string | undefined,
    a.end_date as string | undefined,
    undefined,
    a._skip_cache as boolean | undefined
  ),
  get_stock_info: (a) => get_stock_info(a.symbol as string),
  get_market_overview: () => get_market_overview(),
  get_sector_list: () => get_sector_list(),
  get_hk_stock_price: (a) => get_hk_stock_price(a.symbol as string),
  get_hk_stock_info: (a) => get_hk_stock_info(a.symbol as string),
  get_hk_stock_history: (a) => get_hk_stock_history(a.symbol as string, a.period as string | undefined),
  calculate_technical_indicators: (a) => calculate_technical_indicators(a.symbol as string),
  calculate_buy_range: (a) => calculate_buy_range(a.symbol as string, a.current_price as number | undefined),
  get_stock_valuation: (a) => get_stock_valuation(a.symbol as string),
  get_pe_percentile: (a) => get_pe_percentile(a.symbol as string, a.years as number | undefined),
  get_quality_score: (a) => get_quality_score(a.symbol as string),
  get_stock_fund_flow: (a) => get_stock_fund_flow(a.symbol as string, a.days as number | undefined),
  get_holder_changes: (a) => get_holder_changes(a.symbol as string),
  get_exit_plan: (a) => get_exit_plan(a.symbol as string, a.buy_price as number, a.shares as number | undefined),
  analyze_price_action: (a) => analyze_price_action(a.symbol as string, a.period as number | undefined),
  analyze_candlestick: (a) => analyze_candlestick(a.symbol as string),
  compare_peers: (a) => compare_peers(a.symbol as string),
  manage_portfolio: (a) => manage_portfolio(
    a.action as string,
    a.symbol as string | undefined,
    a.quantity as number | undefined,
    a.avg_cost as number | undefined,
    a.notes as string | undefined,
  ),
};
```

- [ ] **Step 2: 验证 index.ts 编译**

```bash
npx tsc --noEmit src/infrastructure/akshare-ts/index.ts
```

Expected: 无编译错误

- [ ] **Step 3: 验证所有导出可访问**

```bash
node -e "import('./src/infrastructure/akshare-ts/index.js').then(m => console.log(Object.keys(m).length))"
```

Expected: 输出 22（22 个导出函数）

- [ ] **Step 4: 提交新的 index.ts**

```bash
git add src/infrastructure/akshare-ts/index.ts
git commit -m "refactor(akshare-ts): rewrite index.ts as pure export layer"
```

---

## Task 13: 集成测试和清理

**Files:**
- Test: `src/infrastructure/tools/invest-tools.ts`
- Remove: `src/infrastructure/akshare-ts/index.ts.backup`

- [ ] **Step 1: 验证主要消费者正常工作**

```bash
npx tsc --noEmit src/infrastructure/tools/invest-tools.ts
```

Expected: 无编译错误

- [ ] **Step 2: 手动测试关键函数（可选但推荐）**

创建临时测试脚本 `test-refactor.js`：

```javascript
import {
  get_stock_realtime_price,
  calculate_technical_indicators,
  calculate_buy_range,
} from './src/infrastructure/akshare-ts/index.js';

async function test() {
  console.log('Testing get_stock_realtime_price...');
  const price = await get_stock_realtime_price('600519');
  console.log('✓ Price:', JSON.parse(price).symbol);

  console.log('Testing calculate_technical_indicators...');
  const tech = await calculate_technical_indicators('600519');
  console.log('✓ Technical:', JSON.parse(tech).symbol);

  console.log('Testing calculate_buy_range...');
  const range = await calculate_buy_range('600519');
  console.log('✓ Buy range:', JSON.parse(range).symbol);

  console.log('\n✅ All tests passed!');
}

test().catch(console.error);
```

运行测试：
```bash
node test-refactor.js
```

Expected: 所有函数正常返回数据

- [ ] **Step 3: 删除测试脚本（如果创建了）**

```bash
rm -f test-refactor.js
```

- [ ] **Step 4: 删除备份文件**

```bash
git rm src/infrastructure/akshare-ts/index.ts.backup
```

- [ ] **Step 5: 最终提交**

```bash
git commit -m "chore(akshare-ts): remove backup file after successful refactoring"
```

- [ ] **Step 6: 验证文件结构**

```bash
find src/infrastructure/akshare-ts -name "*.ts" -type f | sort
```

Expected 输出：
```
src/infrastructure/akshare-ts/data/financial.ts
src/infrastructure/akshare-ts/data/market.ts
src/infrastructure/akshare-ts/indicators/chart-patterns.ts
src/infrastructure/akshare-ts/indicators/technical.ts
src/infrastructure/akshare-ts/index.ts
src/infrastructure/akshare-ts/portfolio.ts
src/infrastructure/akshare-ts/services/buy-range.ts
src/infrastructure/akshare-ts/services/exit-plan.ts
src/infrastructure/akshare-ts/services/peer-comparison.ts
src/infrastructure/akshare-ts/services/price-action.ts
src/infrastructure/akshare-ts/shared.ts
```

- [ ] **Step 7: 统计代码行数**

```bash
wc -l src/infrastructure/akshare-ts/**/*.ts src/infrastructure/akshare-ts/*.ts | tail -1
```

Expected: 总行数约 1,280 行（略高于原来的 1,248 行）

---

## 完成检查清单

重构完成后，验证以下内容：

**✅ 编译验证：**
- [ ] 所有新文件通过 TypeScript 编译
- [ ] 无循环依赖警告
- [ ] 无类型错误

**✅ 导出验证：**
- [ ] `index.ts` 导出所有 22 个函数
- [ ] `TS_FUNCTIONS` 注册表包含所有函数映射
- [ ] 外部调用者可以正常 import

**✅ 功能验证：**
- [ ] `get_stock_realtime_price('600519')` 返回实时行情
- [ ] `calculate_technical_indicators('600519')` 返回技术指标
- [ ] `calculate_buy_range('600519')` 返回买入区间
- [ ] `manage_portfolio('get')` 返回持仓列表

**✅ 架构验证：**
- [ ] 数据层不依赖指标层或服务层
- [ ] 指标层不依赖服务层
- [ ] 所有模块都可以使用 shared.ts
- [ ] 文件行数符合预期（60-200 行/文件）

**✅ Git 历史：**
- [ ] 每个模块有独立的提交
- [ ] 提交信息清晰描述改动
- [ ] 备份文件已删除

---

## 预期收益

**代码结构：**
- ✅ 10 个模块文件，每个 60-200 行
- ✅ 清晰的分层架构：数据层 → 指标层 → 服务层
- ✅ 单一职责原则

**功能行为：**
- ✅ 所有函数行为完全一致
- ✅ 返回数据格式不变
- ✅ 向后兼容，外部调用者无需修改

**可维护性：**
- ✅ 每个模块职责单一，易于理解
- ✅ 依赖关系清晰，易于测试
- ✅ 新功能有明确的归属位置

---

**实施计划完成日期：** 2026-05-14

