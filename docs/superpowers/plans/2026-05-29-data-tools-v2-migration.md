# Data Tools V2 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `data_fetch_kline` and `data_fetch_stock` tools from v1 Python daemon to quantsys-v2 HTTP API

**Architecture:** Replace `callQuantSysDaemon` calls with `quant-v2-client` HTTP calls to v2 API endpoints. Add new client methods `getKlineHistory` and `getStockData` to `quant-v2-client.ts`. Update existing tests to mock v2 client instead of daemon adapter.

**Tech Stack:** TypeScript, quantsys-v2 Flask API (port 5001), Jest

---

## File Structure

**New files:**
- None (all modifications to existing files)

**Modified files:**
- `src/infrastructure/quant/quant-v2-client.ts` - Add `getKlineHistory` and `getStockData` methods
- `src/infrastructure/quant/types.ts` - Add `KlineData` and `StockData` types
- `src/infrastructure/tools/data/fetch-kline-tool.ts` - Replace daemon call with v2 client
- `src/infrastructure/tools/data/fetch-stock-tool.ts` - Replace daemon calls with v2 client
- `src/infrastructure/tools/data/fetch-kline-tool.test.ts` - Update mocks to use v2 client
- `src/infrastructure/tools/data/fetch-stock-tool.test.ts` - Update mocks to use v2 client

---

## Task 1: Add Type Definitions

**Files:**
- Modify: `src/infrastructure/quant/types.ts:200-250`

- [ ] **Step 1: Add KlineData type definition**

Add after line 200 (after `QuantV2Error` class):

```typescript
// K线数据类型
export interface KlineDataPoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  change_pct: number;
}

export interface KlineData {
  success?: boolean;
  symbol: string;
  period: 'daily' | 'weekly' | 'monthly';
  count: number;
  data: KlineDataPoint[];
  error?: string;
}
```

- [ ] **Step 2: Add StockData type definitions**

Add after KlineData types:

```typescript
// 股票基础数据类型
export interface StockInfo {
  symbol: string;
  name: string;
  market?: string;
  industry?: string;
  sector?: string;
  market_cap?: number;
  pe_ratio?: number;
  pb_ratio?: number;
}

export interface StockPrice {
  symbol: string;
  name?: string;
  price: number;
  change_pct: number;
  high: number;
  low: number;
  open: number;
  volume: number;
  source?: string;
}

export interface StockNews {
  title: string;
  date: string;
  source?: string;
  url?: string;
  summary?: string;
}

export interface StockAnnouncement {
  title: string;
  date: string;
  type?: string;
  url?: string;
}

export interface StockData {
  success?: boolean;
  info?: StockInfo | null;
  price?: StockPrice | null;
  news?: StockNews[] | null;
  announcements?: StockAnnouncement[] | null;
  info_error?: string;
  price_error?: string;
  news_error?: string;
  announcements_error?: string;
  error?: string;
}
```

- [ ] **Step 3: Commit type definitions**

```bash
git add src/infrastructure/quant/types.ts
git commit -m "feat(types): add KlineData and StockData types for v2 migration"
```

---

## Task 2: Add getKlineHistory Client Method

**Files:**
- Modify: `src/infrastructure/quant/quant-v2-client.ts:689-750`
- Test: `src/infrastructure/quant/quant-v2-client.test.ts` (manual testing via tool tests)

- [ ] **Step 1: Write failing test for getKlineHistory**

Update `src/infrastructure/tools/data/fetch-kline-tool.test.ts` to prepare for v2 client:

```typescript
// At top of file, replace daemon mock with v2 client mock
const mockGetKlineHistory = jest.fn<(symbol: string, period?: string, startDate?: string, endDate?: string, limit?: number) => Promise<KlineData>>();

jest.unstable_mockModule('../../quant/quant-v2-client.js', () => ({
  getKlineHistory: mockGetKlineHistory
}));
```

- [ ] **Step 2: Add getKlineHistory method to quant-v2-client.ts**

Add after `getDividends` function (around line 750):

```typescript
/**
 * 获取K线历史数据
 * @param symbol 股票代码
 * @param period 周期 (daily/weekly/monthly)
 * @param startDate 开始日期 YYYYMMDD
 * @param endDate 结束日期 YYYYMMDD
 * @param limit 最大返回条数 (默认60)
 */
export async function getKlineHistory(
  symbol: string,
  period: 'daily' | 'weekly' | 'monthly' = 'daily',
  startDate?: string,
  endDate?: string,
  limit: number = 60,
): Promise<KlineData> {
  if (!symbol || symbol.trim() === '') {
    throw new QuantV2Error('股票代码不能为空', 400);
  }

  const params: Record<string, string | number> = {
    period,
    limit: Math.min(limit, 200),
  };

  if (startDate) {
    // Convert YYYYMMDD to YYYY-MM-DD
    params.start_date = startDate.length === 8
      ? `${startDate.slice(0, 4)}-${startDate.slice(4, 6)}-${startDate.slice(6, 8)}`
      : startDate;
  }

  if (endDate) {
    // Convert YYYYMMDD to YYYY-MM-DD
    params.end_date = endDate.length === 8
      ? `${endDate.slice(0, 4)}-${endDate.slice(4, 6)}-${endDate.slice(6, 8)}`
      : endDate;
  }

  const queryString = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  ).toString();

  const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/history?${queryString}`;
  
  try {
    const response = await fetchV2<KlineData>(url);
    return {
      success: true,
      ...response,
    };
  } catch (error) {
    if (error instanceof QuantV2Error) {
      return {
        success: false,
        symbol,
        period,
        count: 0,
        data: [],
        error: error.message,
      };
    }
    throw error;
  }
}
```

- [ ] **Step 3: Export getKlineHistory**

Verify export is added at the end of the file (should be automatic with `export async function`).

- [ ] **Step 4: Commit getKlineHistory implementation**

```bash
git add src/infrastructure/quant/quant-v2-client.ts
git commit -m "feat(v2-client): add getKlineHistory method for K-line data"
```

---

## Task 3: Add getStockData Client Method

**Files:**
- Modify: `src/infrastructure/quant/quant-v2-client.ts:800-950`

- [ ] **Step 1: Add getStockData method**

Add after `getKlineHistory`:

```typescript
/**
 * 获取股票基础数据（info/price/news/announcements）
 * @param symbol 股票代码
 * @param fields 要获取的字段列表
 * @param newsNum 新闻条数（仅当fields包含news时有效）
 */
export async function getStockData(
  symbol: string,
  fields: Array<'info' | 'price' | 'news' | 'announcements'> = ['info', 'price'],
  newsNum: number = 10,
): Promise<StockData> {
  if (!symbol || symbol.trim() === '') {
    throw new QuantV2Error('股票代码不能为空', 400);
  }

  const result: StockData = { success: true };
  const fetchPromises: Promise<void>[] = [];

  // Fetch info
  if (fields.includes('info')) {
    fetchPromises.push(
      (async () => {
        try {
          const url = `${V2_API_BASE}/api/stocks/${encodeURIComponent(symbol)}`;
          const data = await fetchV2<StockInfo>(url);
          result.info = data;
        } catch (error) {
          result.info = null;
          result.info_error = error instanceof Error ? error.message : String(error);
        }
      })()
    );
  }

  // Fetch price
  if (fields.includes('price')) {
    fetchPromises.push(
      (async () => {
        try {
          const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/quote`;
          const data = await fetchV2<StockPrice>(url);
          result.price = data;
        } catch (error) {
          result.price = null;
          result.price_error = error instanceof Error ? error.message : String(error);
        }
      })()
    );
  }

  // Fetch news
  if (fields.includes('news')) {
    fetchPromises.push(
      (async () => {
        try {
          const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/news?num=${newsNum}`;
          const data = await fetchV2<{ news: StockNews[] }>(url);
          result.news = data.news || [];
        } catch (error) {
          result.news = null;
          result.news_error = error instanceof Error ? error.message : String(error);
        }
      })()
    );
  }

  // Fetch announcements
  if (fields.includes('announcements')) {
    fetchPromises.push(
      (async () => {
        try {
          const url = `${V2_API_BASE}/api/stock/${encodeURIComponent(symbol)}/announcements`;
          const data = await fetchV2<{ announcements: StockAnnouncement[] }>(url);
          result.announcements = data.announcements || [];
        } catch (error) {
          result.announcements = null;
          result.announcements_error = error instanceof Error ? error.message : String(error);
        }
      })()
    );
  }

  // Wait for all fetches to complete
  await Promise.all(fetchPromises);

  // Check if all fields failed
  const hasAnySuccess = fields.some(field => {
    if (field === 'info') return result.info !== null;
    if (field === 'price') return result.price !== null;
    if (field === 'news') return result.news !== null;
    if (field === 'announcements') return result.announcements !== null;
    return false;
  });

  if (!hasAnySuccess) {
    result.success = false;
    const firstError = result.info_error || result.price_error || result.news_error || result.announcements_error;
    result.error = firstError || '所有数据获取失败';
  }

  return result;
}
```

- [ ] **Step 2: Commit getStockData implementation**

```bash
git add src/infrastructure/quant/quant-v2-client.ts
git commit -m "feat(v2-client): add getStockData method for stock info/price/news/announcements"
```

---

## Task 4: Migrate fetch-kline-tool to V2

**Files:**
- Modify: `src/infrastructure/tools/data/fetch-kline-tool.ts:1-122`
- Test: `src/infrastructure/tools/data/fetch-kline-tool.test.ts`

- [ ] **Step 1: Update imports in fetch-kline-tool.ts**

Replace line 10:

```typescript
// OLD:
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

// NEW:
import { getKlineHistory } from "../../quant/quant-v2-client.js";
import type { KlineData } from "../../quant/types.js";
```

- [ ] **Step 2: Update execute function to use v2 client**

Replace lines 68-119 (entire execute function):

```typescript
  execute: async (_toolCallId, params: FetchKlineParams) => {
    const { symbol, period = DEFAULT_PERIOD, start_date, end_date } = params;

    // 验证股票代码
    const market = detectMarket(symbol);
    if (market === "invalid") {
      const errorResponse = {
        success: false,
        error: `不支持的股票代码 "${symbol}"。本系统支持A股（6位数字）和港股（1-5位数字或含.HK后缀）。`,
        invalid_format: true
      };

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(errorResponse)
        }],
        details: undefined
      };
    }

    // 调用 v2 API
    try {
      const result = await getKlineHistory(symbol, period, start_date, end_date);

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(result)
        }],
        details: undefined
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      const errorResponse = {
        success: false,
        error: `获取K线数据失败: ${errorMsg}`
      };

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(errorResponse)
        }],
        details: undefined
      };
    }
  }
```

- [ ] **Step 3: Update test file to mock v2 client**

Update `src/infrastructure/tools/data/fetch-kline-tool.test.ts` lines 7-12:

```typescript
// Replace daemon mock with v2 client mock
const mockGetKlineHistory = jest.fn<(symbol: string, period?: 'daily' | 'weekly' | 'monthly', startDate?: string, endDate?: string, limit?: number) => Promise<any>>();

jest.unstable_mockModule('../../quant/quant-v2-client.js', () => ({
  getKlineHistory: mockGetKlineHistory
}));
```

- [ ] **Step 4: Update test expectations**

Update test at line 48-58 to expect v2 client call:

```typescript
mockGetKlineHistory.mockResolvedValueOnce({
  success: true,
  symbol: '600519',
  period: 'daily',
  count: 2,
  data: [
    { date: '2026-05-20', open: 1800, high: 1820, low: 1790, close: 1810, volume: 1500000, change_pct: 1.2 },
    { date: '2026-05-21', open: 1810, high: 1830, low: 1800, close: 1825, volume: 1600000, change_pct: 0.8 }
  ]
});

const result = await (dataFetchKlineTool.execute as any)('test-call-id', { symbol: '600519' });

expect(mockGetKlineHistory).toHaveBeenCalledTimes(1);
expect(mockGetKlineHistory).toHaveBeenCalledWith('600519', 'daily', undefined, undefined);
```

- [ ] **Step 5: Run tests to verify migration**

```bash
npm test -- src/infrastructure/tools/data/fetch-kline-tool.test.ts
```

Expected: All tests pass

- [ ] **Step 6: Commit fetch-kline-tool migration**

```bash
git add src/infrastructure/tools/data/fetch-kline-tool.ts src/infrastructure/tools/data/fetch-kline-tool.test.ts
git commit -m "feat(tools): migrate data_fetch_kline to v2 API"
```

---

## Task 5: Migrate fetch-stock-tool to V2

**Files:**
- Modify: `src/infrastructure/tools/data/fetch-stock-tool.ts:1-154`
- Test: `src/infrastructure/tools/data/fetch-stock-tool.test.ts`

- [ ] **Step 1: Update imports in fetch-stock-tool.ts**

Replace line 10:

```typescript
// OLD:
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";

// NEW:
import { getStockData } from "../../quant/quant-v2-client.js";
import type { StockData } from "../../quant/types.js";
```

- [ ] **Step 2: Remove fetchField helper function**

Delete lines 29-64 (entire `fetchField` function - no longer needed).

- [ ] **Step 3: Update execute function to use v2 client**

Replace lines 102-152 (execute function body):

```typescript
  execute: async (_toolCallId, params: FetchStockParams) => {
    const { symbol, fields = ["info", "price"], news_num = DEFAULT_NEWS_COUNT } = params;

    // 验证股票代码
    const market = detectMarket(symbol);
    if (market === "invalid") {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            error: `不支持的股票代码 "${symbol}"。本系统支持A股（6位数字）和港股（1-5位数字或含.HK后缀）。`,
            invalid_format: true
          })
        }],
        details: undefined
      };
    }

    // 调用 v2 API
    try {
      const result = await getStockData(symbol, fields, news_num);

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify(result, null, 2)
        }],
        details: undefined
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            error: `获取股票数据失败: ${errorMsg}`
          })
        }],
        details: undefined
      };
    }
  }
```

- [ ] **Step 4: Update test file to mock v2 client**

Update `src/infrastructure/tools/data/fetch-stock-tool.test.ts` lines 6-11:

```typescript
// Replace daemon mock with v2 client mock
const mockGetStockData = jest.fn<(symbol: string, fields?: Array<'info' | 'price' | 'news' | 'announcements'>, newsNum?: number) => Promise<any>>();

jest.unstable_mockModule('../../quant/quant-v2-client.js', () => ({
  getStockData: mockGetStockData
}));
```

- [ ] **Step 5: Update test expectations**

Update test at line 42-75 to expect v2 client call:

```typescript
mockGetStockData.mockResolvedValueOnce({
  success: true,
  info: {
    symbol: '600519',
    name: '贵州茅台',
    sector: '食品饮料',
    market_cap: 2250000000000
  },
  price: {
    symbol: '600519',
    price: 1800.50,
    change_pct: 2.5,
    volume: 1500000
  }
});

const result = await (dataFetchStockTool.execute as any)('test-call-id', { symbol: '600519' });

expect(mockGetStockData).toHaveBeenCalledTimes(1);
expect(mockGetStockData).toHaveBeenCalledWith('600519', ['info', 'price'], 10);

const response = JSON.parse(getResponseText(result));
expect(response.info).toBeDefined();
expect(response.price).toBeDefined();
expect(response.info.symbol).toBe('600519');
expect(response.price.price).toBe(1800.50);
```

- [ ] **Step 6: Run tests to verify migration**

```bash
npm test -- src/infrastructure/tools/data/fetch-stock-tool.test.ts
```

Expected: All tests pass

- [ ] **Step 7: Commit fetch-stock-tool migration**

```bash
git add src/infrastructure/tools/data/fetch-stock-tool.ts src/infrastructure/tools/data/fetch-stock-tool.test.ts
git commit -m "feat(tools): migrate data_fetch_stock to v2 API"
```

---

## Task 6: Integration Testing

**Files:**
- Manual testing with real quantsys-v2 backend

- [ ] **Step 1: Start quantsys-v2 backend**

```bash
cd quantsys-v2 && python start_all.py
```

Expected: REST API starts on port 5001

- [ ] **Step 2: Test data_fetch_kline with real backend**

Start the TypeScript agent and test:

```bash
npm run dev
```

In agent prompt:
```
data_fetch_kline({ symbol: "600519", period: "daily" })
```

Expected: Returns K-line data from v2 API

- [ ] **Step 3: Test data_fetch_stock with real backend**

In agent prompt:
```
data_fetch_stock({ symbol: "600519", fields: ["info", "price"] })
```

Expected: Returns stock info and price from v2 API

- [ ] **Step 4: Test error handling**

In agent prompt:
```
data_fetch_kline({ symbol: "INVALID" })
```

Expected: Returns error message about invalid stock code

- [ ] **Step 5: Run full test suite**

```bash
npm test
```

Expected: All tests pass

- [ ] **Step 6: Commit integration test results**

If any issues found, fix them and commit. Otherwise, create a summary commit:

```bash
git add -A
git commit -m "test: verify data tools v2 migration with integration tests"
```

---

## Task 7: Update Documentation

**Files:**
- Modify: `CLAUDE.md:100-150`

- [ ] **Step 1: Update v2 migration status in CLAUDE.md**

Find the "v2 迁移（2026-05-25）" section and update:

```markdown
**v2 迁移（2026-05-29）**：核心工具已从 v1 Python daemon 迁移到 quantsys-v2 Flask API (端口 5001)：
- `data_fetch_kline` — 使用 v2 API `/api/stock/{symbol}/history`
- `data_fetch_stock` — 使用 v2 API `/api/stocks/{symbol}`, `/api/stock/{symbol}/quote`, `/api/stock/{symbol}/news`, `/api/stock/{symbol}/announcements`
- `data_fetch_financial` — 使用 v2 API `/api/data/financials`
- `data_fetch_dividend` — 使用 v2 API `/api/stock/{symbol}/dividends`
- `factor_calculate` — 使用 v2 API `/api/factors/compute`
- `factor_analyze` — 使用 v2 API `/api/analysis/factors`
- `invest_opportunity_scan` — 使用 v2 API `/api/signals/opportunities`
- `trade_algo_execute` — 使用 v2 API `/api/orders/algo-execute`

**v1 保留工具**（已全部迁移至 v2）：
- ~~`data_fetch_stock`, `data_fetch_kline` — 基础数据获取~~ ✅ 已迁移
- `model_*` 系列 — 模型训练、预测、评估、监控（待迁移）
```

- [ ] **Step 2: Commit documentation update**

```bash
git add CLAUDE.md
git commit -m "docs: update v2 migration status for data tools"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ data_fetch_kline migration (Task 2, 4)
- ✅ data_fetch_stock migration (Task 3, 5)
- ✅ Type definitions (Task 1)
- ✅ Tests updated (Task 4, 5)
- ✅ Integration testing (Task 6)
- ✅ Documentation (Task 7)

**Placeholder scan:**
- ✅ No TBD/TODO markers
- ✅ All code blocks complete
- ✅ All commands have expected output

**Type consistency:**
- ✅ KlineData type used consistently
- ✅ StockData type used consistently
- ✅ Method signatures match across tool and client

**Dependencies:**
- ✅ Task 1 (types) must complete before Task 2-3 (client methods)
- ✅ Task 2-3 (client methods) must complete before Task 4-5 (tool migration)
- ✅ Task 4-5 (tool migration) must complete before Task 6 (integration testing)
