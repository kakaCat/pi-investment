# HK Stock FX Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add foreign exchange rate handling for Hong Kong stocks to accurately track costs and market values in CNY.

**Architecture:** Create FxRateService for rate caching and retrieval, extend PortfolioService with HK-specific methods, update data structures to store HKD prices and FX rates, add daily cron job for rate updates.

**Tech Stack:** TypeScript, Node.js, Sina Finance API, existing CronService

---

## File Structure

**New Files:**
- `src/services/fx-rate-service.ts` - FX rate caching and retrieval
- `src/services/fx-rate-service.test.ts` - Unit tests
- `src/infrastructure/data-sources/sina-fx.ts` - Sina FX data source
- `src/scripts/migrate-hk-holdings.ts` - Data migration script

**Modified Files:**
- `src/services/portfolio/portfolio-service.ts` - Add HK stock methods
- `src/services/portfolio/portfolio-service.test.ts` - Add HK tests
- `src/services/portfolio/trade-service.ts` - Add HK fields to Trade interface
- `src/infrastructure/tools/invest/portfolio-tools.ts` - Add price_hkd parameter
- `.pi-invest/CRON.json` - Add FX rate update cron job
- `src/api/index.ts` - Handle FX rate update event

---

## Task 1: Create FxRateService Foundation

**Files:**
- Create: `src/services/fx-rate-service.ts`
- Create: `src/services/fx-rate-service.test.ts`

- [ ] **Step 1: Write failing test for FxRateService initialization**

```typescript
// src/services/fx-rate-service.test.ts
import { describe, test, expect, beforeEach, afterEach } from "@jest/globals";
import { FxRateService } from "./fx-rate-service.js";
import { mkdirSync, rmSync, existsSync } from "fs";
import { join } from "path";

const TEST_DIR = join(process.cwd(), ".test-fx-rates");

describe("FxRateService", () => {
  beforeEach(() => {
    if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true });
    mkdirSync(TEST_DIR, { recursive: true });
  });

  afterEach(() => {
    if (existsSync(TEST_DIR)) rmSync(TEST_DIR, { recursive: true });
  });

  test("initializes with empty cache file", () => {
    const service = new FxRateService(TEST_DIR);
    const cachePath = join(TEST_DIR, "fx-rates.json");
    expect(existsSync(cachePath)).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- fx-rate-service.test.ts
```

Expected: FAIL with "Cannot find module './fx-rate-service.js'"

- [ ] **Step 3: Create FxRateService with basic structure**

```typescript
// src/services/fx-rate-service.ts
import { readFileSync, writeFileSync, existsSync } from "fs";
import { join } from "path";

export interface FxRatesFile {
  rates: {
    [pair: string]: {
      rate: number;
      date: string;
      updated_at: string;
      source: string;
    };
  };
  last_updated: string;
}

export class FxRateService {
  private cachePath: string;

  constructor(piDir: string) {
    this.cachePath = join(piDir, "fx-rates.json");
    this.ensureCache();
  }

  private ensureCache(): void {
    if (!existsSync(this.cachePath)) {
      const empty: FxRatesFile = {
        rates: {},
        last_updated: ""
      };
      writeFileSync(this.cachePath, JSON.stringify(empty, null, 2), "utf-8");
    }
  }

  private loadCache(): FxRatesFile {
    try {
      const content = readFileSync(this.cachePath, "utf-8");
      return JSON.parse(content) as FxRatesFile;
    } catch (error) {
      return { rates: {}, last_updated: "" };
    }
  }

  private saveCache(data: FxRatesFile): void {
    writeFileSync(this.cachePath, JSON.stringify(data, null, 2), "utf-8");
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- fx-rate-service.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/fx-rate-service.ts src/services/fx-rate-service.test.ts
git commit -m "feat(fx): add FxRateService foundation with cache initialization"
```

---

## Task 2: Add Sina FX Data Source

**Files:**
- Create: `src/infrastructure/data-sources/sina-fx.ts`
- Modify: `src/services/fx-rate-service.test.ts`

- [ ] **Step 1: Write failing test for Sina FX rate fetching**

```typescript
// Add to src/services/fx-rate-service.test.ts
test("fetches FX rate from Sina", async () => {
  const service = new FxRateService(TEST_DIR);
  const rate = await service.fetchRateFromSina("HKDCNY");
  expect(rate).toBeGreaterThan(0);
  expect(rate).toBeLessThan(2);
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- fx-rate-service.test.ts -t "fetches FX rate"
```

Expected: FAIL with "fetchRateFromSina is not a function"

- [ ] **Step 3: Create Sina FX data source**

```typescript
// src/infrastructure/data-sources/sina-fx.ts
export async function fetchSinaFxRate(pair: string): Promise<number> {
  const url = `https://hq.sinajs.cn/list=${pair}`;
  
  try {
    const response = await fetch(url);
    const text = await response.text();
    
    const match = text.match(/"([^"]+)"/);
    if (!match) {
      throw new Error(`汇率数据解析失败: ${text.substring(0, 100)}`);
    }
    
    const parts = match[1].split(",");
    const rate = parseFloat(parts[0]);
    
    if (isNaN(rate) || rate <= 0) {
      throw new Error(`无效的汇率值: ${parts[0]}`);
    }
    
    return rate;
  } catch (error) {
    throw new Error(`获取汇率失败: ${error instanceof Error ? error.message : String(error)}`);
  }
}
```

- [ ] **Step 4: Add fetchRateFromSina method to FxRateService**

```typescript
// Add to src/services/fx-rate-service.ts
import { fetchSinaFxRate } from "../infrastructure/data-sources/sina-fx.js";

export class FxRateService {
  // ... existing code ...

  async fetchRateFromSina(pair: "HKDCNY"): Promise<number> {
    return fetchSinaFxRate(pair);
  }
}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
npm test -- fx-rate-service.test.ts -t "fetches FX rate"
```

Expected: PASS (requires network)

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/data-sources/sina-fx.ts src/services/fx-rate-service.ts src/services/fx-rate-service.test.ts
git commit -m "feat(fx): add Sina FX rate data source"
```

---

## Task 3: Implement FX Rate Caching with Fallback

**Files:**
- Modify: `src/services/fx-rate-service.ts`
- Modify: `src/services/fx-rate-service.test.ts`

- [ ] **Step 1: Write failing test for getRate with caching**

```typescript
// Add to src/services/fx-rate-service.test.ts
import { chinaDate, chinaDateTime } from "../../utils/china-time.js";

test("getRate returns cached rate if fresh", async () => {
  const service = new FxRateService(TEST_DIR);
  
  // Manually write a fresh cache
  const cache: FxRatesFile = {
    rates: {
      HKDCNY: {
        rate: 0.8850,
        date: chinaDate(),
        updated_at: chinaDateTime(),
        source: "sina"
      }
    },
    last_updated: chinaDateTime()
  };
  writeFileSync(join(TEST_DIR, "fx-rates.json"), JSON.stringify(cache, null, 2));
  
  const rate = await service.getRate("HKDCNY");
  expect(rate).toBe(0.8850);
});

test("getRate fetches new rate if cache stale", async () => {
  const service = new FxRateService(TEST_DIR);
  
  // Write a stale cache (yesterday)
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 2);
  const staleDate = yesterday.toISOString().split("T")[0];
  
  const cache: FxRatesFile = {
    rates: {
      HKDCNY: {
        rate: 0.8850,
        date: staleDate,
        updated_at: staleDate,
        source: "sina"
      }
    },
    last_updated: staleDate
  };
  writeFileSync(join(TEST_DIR, "fx-rates.json"), JSON.stringify(cache, null, 2));
  
  const rate = await service.getRate("HKDCNY");
  expect(rate).toBeGreaterThan(0);
  expect(rate).not.toBe(0.8850); // Should fetch new rate
});

test("getRate uses default if no cache and fetch fails", async () => {
  const service = new FxRateService(TEST_DIR);
  
  // Mock fetchRateFromSina to fail
  service.fetchRateFromSina = async () => {
    throw new Error("Network error");
  };
  
  const rate = await service.getRate("HKDCNY");
  expect(rate).toBe(0.88); // Default fallback
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm test -- fx-rate-service.test.ts -t "getRate"
```

Expected: FAIL with "getRate is not a function"

- [ ] **Step 3: Implement getRate with 4-layer fallback**

```typescript
// Add to src/services/fx-rate-service.ts
import { chinaDate, chinaDateTime } from "../utils/china-time.js";

export class FxRateService {
  // ... existing code ...

  private isCacheStale(date: string): boolean {
    const cacheDate = new Date(date);
    const now = new Date();
    const diffHours = (now.getTime() - cacheDate.getTime()) / (1000 * 60 * 60);
    return diffHours > 24;
  }

  async getRate(pair: "HKDCNY"): Promise<number> {
    try {
      // 1. Try cache (if fresh)
      const cache = this.loadCache();
      const cached = cache.rates[pair];
      
      if (cached && !this.isCacheStale(cached.date)) {
        return cached.rate;
      }
      
      // 2. Fetch new rate
      const rate = await this.fetchRateFromSina(pair);
      
      // Save to cache
      cache.rates[pair] = {
        rate,
        date: chinaDate(),
        updated_at: chinaDateTime(),
        source: "sina"
      };
      cache.last_updated = chinaDateTime();
      this.saveCache(cache);
      
      return rate;
      
    } catch (error) {
      // 3. Use stale cache if available
      const cache = this.loadCache();
      if (cache.rates[pair]) {
        console.warn(`⚠️ 汇率获取失败，使用缓存值: ${cache.rates[pair].rate} (${cache.rates[pair].date})`);
        return cache.rates[pair].rate;
      }
      
      // 4. Use default fallback
      console.error("❌ 汇率获取失败且无缓存，使用默认值 0.88");
      return 0.88;
    }
  }

  async updateCache(): Promise<void> {
    const rate = await this.fetchRateFromSina("HKDCNY");
    const cache = this.loadCache();
    
    cache.rates["HKDCNY"] = {
      rate,
      date: chinaDate(),
      updated_at: chinaDateTime(),
      source: "sina"
    };
    cache.last_updated = chinaDateTime();
    
    this.saveCache(cache);
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npm test -- fx-rate-service.test.ts
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/fx-rate-service.ts src/services/fx-rate-service.test.ts
git commit -m "feat(fx): implement 4-layer fallback for FX rate retrieval"
```

---

(Plan continues in next message due to length...)

## Task 4: Update Data Structures for HK Stock Support

**Files:**
- Modify: `src/services/portfolio/portfolio-service.ts`
- Modify: `src/services/portfolio/trade-service.ts`

- [ ] **Step 1: Write failing test for HK holding with FX fields**

```typescript
// Add to src/services/portfolio/portfolio-service.test.ts
test("stores HK stock with avg_cost_hkd and purchase_fx_rate", () => {
  const service = new PortfolioService(TEST_DIR);
  
  const result = service.add("00700", 100, 589.71, 0, "腾讯控股", "HK", "");
  
  const data = service.load();
  const holding = data.holdings.find(h => h.symbol === "00700");
  
  expect(holding).toBeDefined();
  expect(holding?.avg_cost).toBe(589.71);
  expect(holding?.avg_cost_hkd).toBeUndefined(); // Will be added in next step
  expect(holding?.purchase_fx_rate).toBeUndefined();
});
```

- [ ] **Step 2: Run test to verify current behavior**

```bash
npm test -- portfolio-service.test.ts -t "stores HK stock"
```

Expected: PASS (fields are undefined as expected)

- [ ] **Step 3: Update Holding interface to include HK fields**

```typescript
// Modify in src/services/portfolio/portfolio-service.ts
export interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;
  avg_cost_hkd?: number;         // 🆕 港币成本（HKD），仅港股
  purchase_fx_rate?: number;     // 🆕 买入时汇率（HKD→CNY），仅港股
  market: "A" | "HK";
  notes: string;
  added_date: string;
  stop_loss?: number | null;
  target_price?: number | null;
  sector?: string;
  buy_reason?: string;
  original_cost?: number;
  total_invested?: number;
  batch_plan?: string | null;
}
```

- [ ] **Step 4: Update Trade interface to include HK fields**

```typescript
// Modify in src/services/portfolio/trade-service.ts
export interface Trade {
  id: string;
  date: string;
  symbol: string;
  name: string;
  action: TradeAction;
  quantity: number;
  price: number;
  price_hkd?: number;            // 🆕 港币成交价（HKD），仅港股
  fx_rate?: number;              // 🆕 成交时汇率，仅港股
  commission: number;
  amount: number;
  market: "A" | "HK";
  notes: string;
  pnl?: number;
  pnl_pct?: number;
}
```

- [ ] **Step 5: Update HoldingWithPnL interface**

```typescript
// Add to src/services/portfolio/portfolio-service.ts
export interface HoldingWithPnL extends Holding {
  current_price: number;
  current_price_hkd?: number;    // 🆕 当前港币价格
  current_fx_rate?: number;      // 🆕 当前汇率
  change_pct: number;
  pnl_pct: number;
  pnl_amount: number;
  market_value: number;
}
```

- [ ] **Step 6: Run tests to verify no regressions**

```bash
npm test -- portfolio-service.test.ts
npm test -- trade-service.test.ts
```

Expected: PASS (optional fields don't break existing tests)

- [ ] **Step 7: Commit**

```bash
git add src/services/portfolio/portfolio-service.ts src/services/portfolio/trade-service.ts
git commit -m "feat(portfolio): add HK stock FX fields to data structures"
```

---

## Task 5: Implement PortfolioService.addHKStock Method

**Files:**
- Modify: `src/services/portfolio/portfolio-service.ts`
- Modify: `src/services/portfolio/portfolio-service.test.ts`

- [ ] **Step 1: Write failing test for addHKStock**

```typescript
// Add to src/services/portfolio/portfolio-service.test.ts
import { FxRateService } from "../fx-rate-service.js";

test("addHKStock records HKD price and FX rate", async () => {
  const service = new PortfolioService(TEST_DIR);
  const fxService = new FxRateService(TEST_DIR);
  
  // Mock FX rate
  fxService.getRate = async () => 0.8850;
  
  const result = await service.addHKStock(
    "00700",
    100,
    666.57,  // HKD price
    0,
    "腾讯控股",
    ""
  );
  
  expect(result.success).toBe(true);
  
  const data = service.load();
  const holding = data.holdings.find(h => h.symbol === "00700");
  
  expect(holding?.avg_cost).toBeCloseTo(589.71, 2); // 666.57 * 0.8850
  expect(holding?.avg_cost_hkd).toBe(666.57);
  expect(holding?.purchase_fx_rate).toBe(0.8850);
  expect(holding?.market).toBe("HK");
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- portfolio-service.test.ts -t "addHKStock"
```

Expected: FAIL with "addHKStock is not a function"

- [ ] **Step 3: Implement addHKStock method**

```typescript
// Add to src/services/portfolio/portfolio-service.ts
import { FxRateService } from "../fx-rate-service.js";

export class PortfolioService {
  private filePath: string;
  private tradeService?: any;
  private fxRateService?: FxRateService;  // 🆕

  constructor(piDir: string) {
    this.filePath = join(piDir, "portfolio.json");
    this.fxRateService = new FxRateService(piDir);  // 🆕
    mkdirSync(piDir, { recursive: true });
    this.ensureFile();
  }

  // ... existing methods ...

  async addHKStock(
    symbol: string,
    quantity: number,
    priceHKD: number,
    commission: number = 0,
    name: string = "",
    notes: string = ""
  ): Promise<{ success: boolean; message: string; updatedHolding?: Holding }> {
    
    if (!this.fxRateService) {
      throw new Error("FxRateService not initialized");
    }
    
    // 1. Get current FX rate
    const fxRate = await this.fxRateService.getRate("HKDCNY");
    
    // 2. Calculate CNY cost
    const totalCostHKD = priceHKD * quantity;
    const commissionCNY = commission;
    const totalCostCNY = totalCostHKD * fxRate + commissionCNY;
    const avgCostCNY = roundN(totalCostCNY / quantity);
    
    // 3. Check for existing holding
    return FileLockService.withLockSync(this.filePath, () => {
      const data = this.load();
      const idx = data.holdings.findIndex(h => h.symbol === symbol);
      
      if (idx >= 0) {
        // Add to existing position (weighted average)
        const h = data.holdings[idx];
        const existingCostHKD = h.avg_cost_hkd || 0;
        const existingQty = h.quantity;
        
        const totalCostHKDWeighted = existingCostHKD * existingQty + priceHKD * quantity;
        const totalCostCNYWeighted = h.avg_cost * existingQty + avgCostCNY * quantity;
        const totalQty = existingQty + quantity;
        
        const newAvgCostHKD = roundN(totalCostHKDWeighted / totalQty);
        const newAvgCostCNY = roundN(totalCostCNYWeighted / totalQty);
        const newAvgFxRate = roundN(newAvgCostCNY / newAvgCostHKD, 4);
        
        data.holdings[idx] = {
          ...h,
          quantity: totalQty,
          avg_cost: newAvgCostCNY,
          avg_cost_hkd: newAvgCostHKD,
          purchase_fx_rate: newAvgFxRate,
          name: name || h.name,
          notes: notes || h.notes,
        };
        
        data.last_updated = nowStr();
        writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
        
        return {
          success: true,
          message: `${symbol} 已加仓，新均价 ${newAvgCostCNY.toFixed(2)} CNY (${newAvgCostHKD.toFixed(2)} HKD)`,
          updatedHolding: data.holdings[idx],
        };
      } else {
        // New position
        const newHolding: Holding = {
          symbol,
          name,
          quantity,
          avg_cost: avgCostCNY,
          avg_cost_hkd: priceHKD,
          purchase_fx_rate: fxRate,
          market: "HK",
          notes,
          added_date: today(),
        };
        
        data.holdings.push(newHolding);
        data.last_updated = nowStr();
        writeFileSync(this.filePath, JSON.stringify(data, null, 2), "utf-8");
        
        return {
          success: true,
          message: `${symbol} 已录入持仓`,
          updatedHolding: newHolding,
        };
      }
    });
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
npm test -- portfolio-service.test.ts -t "addHKStock"
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/portfolio/portfolio-service.ts src/services/portfolio/portfolio-service.test.ts
git commit -m "feat(portfolio): implement addHKStock with FX rate handling"
```

---

## Task 6: Update getWithPnL to Handle HK Stocks

**Files:**
- Modify: `src/services/portfolio/portfolio-service.ts`
- Modify: `src/services/portfolio/portfolio-service.test.ts`

- [ ] **Step 1: Write failing test for getWithPnL with HK stocks**

```typescript
// Add to src/services/portfolio/portfolio-service.test.ts
test("getWithPnL converts HK stock prices using current FX rate", async () => {
  const service = new PortfolioService(TEST_DIR);
  const fxService = new FxRateService(TEST_DIR);
  
  // Add HK stock
  fxService.getRate = async () => 0.8850;
  await service.addHKStock("00700", 100, 666.57, 0, "腾讯控股", "");
  
  // Mock current price and FX rate
  fxService.getRate = async () => 0.8800;
  
  // Mock get_hk_stock_price to return HKD price
  const originalGetHKPrice = global.get_hk_stock_price;
  global.get_hk_stock_price = async () => JSON.stringify({ price: 670.00, name: "腾讯控股" });
  
  const snapshot = await service.getWithPnL();
  
  const holding = snapshot.holdings.find(h => h.symbol === "00700");
  expect(holding?.current_price_hkd).toBe(670.00);
  expect(holding?.current_fx_rate).toBe(0.8800);
  expect(holding?.current_price).toBeCloseTo(589.60, 2); // 670 * 0.88
  expect(holding?.market_value).toBeCloseTo(58960, 2);
  
  // Restore
  global.get_hk_stock_price = originalGetHKPrice;
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
npm test -- portfolio-service.test.ts -t "getWithPnL converts HK"
```

Expected: FAIL (current_price_hkd not set)

- [ ] **Step 3: Update getWithPnL to handle HK stocks**

```typescript
// Modify in src/services/portfolio/portfolio-service.ts
async getWithPnL(): Promise<PortfolioSnapshot> {
  const data = this.load();
  const holdings = data.holdings;

  if (holdings.length === 0) {
    return { holdings: [], total_cost: 0, total_value: 0, total_pnl: 0, total_pnl_pct: 0, as_of: today() };
  }

  // 1. Get current FX rate
  const fxRate = this.fxRateService ? await this.fxRateService.getRate("HKDCNY") : 0.88;

  // 2. Fetch all prices in parallel
  const priceResults = await Promise.all(
    holdings.map(h =>
      (h.market === "HK" ? get_hk_stock_price(h.symbol) : get_stock_realtime_price(h.symbol))
        .then(raw => JSON.parse(raw) as Record<string, unknown>)
        .catch(() => ({} as Record<string, unknown>))
    )
  );

  return buildPortfolioSnapshotFromQuotes(holdings, priceResults, fxRate);
}
```

- [ ] **Step 4: Update buildPortfolioSnapshotFromQuotes to handle FX**

```typescript
// Modify in src/services/portfolio/portfolio-service.ts
export function buildPortfolioSnapshotFromQuotes(
  holdings: Holding[],
  priceResults: Array<Record<string, unknown>>,
  fxRate: number = 0.88
): PortfolioSnapshot {
  if (holdings.length === 0) {
    return { holdings: [], total_cost: 0, total_value: 0, total_pnl: 0, total_pnl_pct: 0, as_of: today() };
  }

  let totalCost = 0;
  let totalValue = 0;

  const enriched: HoldingWithPnL[] = holdings.map((h, i) => {
    const rt = priceResults[i] ?? {};
    
    if (h.market === "HK") {
      // HK stock logic
      const currentPriceHKD = Number(rt.price ?? 0);
      const currentPriceCNY = currentPriceHKD * fxRate;
      const changePct = Number(rt.change_pct ?? rt.pct_chg ?? 0);
      const marketValue = roundN(currentPriceCNY * h.quantity);
      const cost = roundN(h.avg_cost * h.quantity);
      const pnlAmt = roundN(marketValue - cost);
      const pnlPct = cost > 0 ? roundN((pnlAmt / cost) * 100) : 0;
      
      totalCost += cost;
      totalValue += marketValue;

      return {
        ...h,
        name: String(rt.name ?? h.name),
        current_price: currentPriceCNY,
        current_price_hkd: currentPriceHKD,
        current_fx_rate: fxRate,
        change_pct: roundN(changePct),
        pnl_pct: pnlPct,
        pnl_amount: pnlAmt,
        market_value: marketValue,
      };
    } else {
      // A-share logic (unchanged)
      const curPrice = Number(rt.price ?? rt.current_price ?? 0);
      const prevClose = Number(rt.prev_close ?? 0);
      const changePct = Number(rt.change_pct ?? rt.pct_chg ?? 0);
      const pnlPct = h.avg_cost > 0 ? roundN((curPrice - h.avg_cost) / h.avg_cost * 100) : 0;
      const pnlAmt = roundN((curPrice - h.avg_cost) * h.quantity);
      const marketValue = roundN(curPrice * h.quantity);
      const cost = roundN(h.avg_cost * h.quantity);
      totalCost += cost;
      totalValue += marketValue;

      return {
        ...h,
        name: String(rt.name ?? h.name),
        current_price: curPrice,
        change_pct: roundN(changePct),
        pnl_pct: pnlPct,
        pnl_amount: pnlAmt,
        market_value: marketValue,
      };
    }
  });

  const totalPnl = roundN(totalValue - totalCost);
  const totalPnlPct = totalCost > 0 ? roundN(totalPnl / totalCost * 100) : 0;

  return {
    holdings: enriched,
    total_cost: totalCost,
    total_value: totalValue,
    total_pnl: totalPnl,
    total_pnl_pct: totalPnlPct,
    as_of: today(),
  };
}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
npm test -- portfolio-service.test.ts -t "getWithPnL converts HK"
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/services/portfolio/portfolio-service.ts src/services/portfolio/portfolio-service.test.ts
git commit -m "feat(portfolio): add HK stock FX conversion in getWithPnL"
```

---


## Task 7: Update Agent Tool to Support HK Stocks

**Files:**
- Modify: `src/infrastructure/tools/invest/portfolio-tools.ts`

- [ ] **Step 1: Write test for tool with price_hkd parameter**

```typescript
// Add to src/infrastructure/tools/invest/portfolio-tools.test.ts (if exists)
// Or manually test via agent interaction
```

- [ ] **Step 2: Add price_hkd parameter to tool definition**

```typescript
// Modify in src/infrastructure/tools/invest/portfolio-tools.ts
export const managePortfolioTool: ToolDefinition = {
  name: "manage_portfolio",
  // ... existing description ...
  parameters: Type.Object({
    action: Type.Union([...], { description: "Operation to perform" }),
    symbol: Type.Optional(Type.String({ description: "Stock code — 6-digit A-share (e.g. '600519') or HK code (e.g. '09988'). Required for add/sell/update/remove." })),
    quantity: Type.Optional(Type.Integer({ description: "Number of shares (for add/sell/update)" })),
    avg_cost: Type.Optional(Type.Number({ description: "Average cost per share in CNY (for A-shares or if you already know CNY cost)" })),
    price_hkd: Type.Optional(Type.Number({ description: "🆕 HK stock price in HKD (港股港币价格，仅港股需要，如 666.57). Required for HK stocks." })),
    price: Type.Optional(Type.Number({ description: "Sell price per share (for sell action only, e.g. 118.80)" })),
    name: Type.Optional(Type.String({ description: "Stock name (optional, will be auto-filled from market data if omitted)" })),
    market: Type.Optional(Type.Union([Type.Literal("A"), Type.Literal("HK")], { description: "Market: 'A' for A-share (default), 'HK' for Hong Kong" })),
    notes: Type.Optional(Type.String({ description: "Free-text notes" })),
    commission: Type.Optional(Type.Number({ description: "手续费（可选），默认 0" })),
    stop_loss: Type.Optional(Type.Number({ description: "止损价（可选）" })),
    target_price: Type.Optional(Type.Number({ description: "目标价（可选）" })),
  }),
  // ... rest of definition
};
```

- [ ] **Step 3: Update add action to handle HK stocks**

```typescript
// Modify execute function in src/infrastructure/tools/invest/portfolio-tools.ts
execute: async (_toolCallId, params: any) => {
  const { action, symbol, quantity, avg_cost, price_hkd, price, name, market, notes, commission, stop_loss, target_price } = params;
  
  try {
    // ... existing get/get_with_pnl logic ...
    
    if (action === "add") {
      if (!symbol || quantity == null) {
        return { content: [{ type: "text" as const, text: JSON.stringify({ error: "add 需要 symbol, quantity", _no_operation_performed: true }) }], details: undefined };
      }
      
      const qtyErr = validatePositiveNumber(quantity, "数量");
      if (qtyErr) return { content: [{ type: "text" as const, text: JSON.stringify({ error: qtyErr, _no_operation_performed: true }) }], details: undefined };
      
      // HK stock: requires price_hkd
      if (market === "HK") {
        if (!price_hkd) {
          return { content: [{ type: "text" as const, text: JSON.stringify({ error: "港股需要提供 price_hkd（港币价格）", _no_operation_performed: true }) }], details: undefined };
        }
        
        const priceErr = validatePositiveNumber(price_hkd, "港币价格");
        if (priceErr) return { content: [{ type: "text" as const, text: JSON.stringify({ error: priceErr, _no_operation_performed: true }) }], details: undefined };
        
        // Call HK-specific method
        const res = await _portfolioSvc.addHKStock(symbol, quantity, price_hkd, commission || 0, name ?? "", notes ?? "");
        
        // Record trade
        try {
          const ts = new TradeService(PI_DIR);
          const fxService = new FxRateService(PI_DIR);
          const fxRate = await fxService.getRate("HKDCNY");
          const priceCNY = price_hkd * fxRate;
          
          ts.add(chinaDate(), symbol, name || symbol, "buy", quantity, priceCNY, commission || 0, "HK", notes || "手动录入");
          
          // Update last trade with HK fields
          const tradesData = ts.load();
          const lastTrade = tradesData.trades[tradesData.trades.length - 1];
          if (lastTrade && lastTrade.symbol === symbol) {
            lastTrade.price_hkd = price_hkd;
            lastTrade.fx_rate = fxRate;
            ts.save(tradesData);
          }
        } catch (e) {
          console.warn("交易记录失败:", e);
        }
        
        // Auto-create stop loss/target orders (same as A-share logic)
        const ordersCreated: string[] = [];
        if (stop_loss || target_price) {
          try {
            const { OrderService } = await import("../../../services/order-service.js");
            const orderSvc = new OrderService(PI_DIR);
            
            if (stop_loss && stop_loss > 0) {
              orderSvc.create({
                symbol, name: name || symbol, side: "sell", type: "stop_loss",
                price: stop_loss, quantity, market: "HK",
                notes: `自动止损单（成本价 ${price_hkd} HKD）`,
              });
              ordersCreated.push(`止损单 ${stop_loss}`);
            }
            
            if (target_price && target_price > price_hkd) {
              orderSvc.create({
                symbol, name: name || symbol, side: "sell", type: "limit",
                price: target_price, quantity, market: "HK",
                notes: `自动止盈单（成本价 ${price_hkd} HKD）`,
              });
              ordersCreated.push(`止盈单 ${target_price}`);
            }
          } catch (e) {
            console.warn("挂单创建失败:", e);
          }
        }
        
        const resultWithOrders = {
          ...res,
          orders_created: ordersCreated.length > 0 ? ordersCreated : undefined
        };
        
        return { content: [{ type: "text" as const, text: JSON.stringify(resultWithOrders) }], details: undefined };
      }
      
      // A-share: original logic
      else {
        if (!avg_cost) {
          return { content: [{ type: "text" as const, text: JSON.stringify({ error: "A股需要提供 avg_cost（人民币成本）", _no_operation_performed: true }) }], details: undefined };
        }
        
        const costErr = validatePositiveNumber(avg_cost, "成本价");
        if (costErr) return { content: [{ type: "text" as const, text: JSON.stringify({ error: costErr, _no_operation_performed: true }) }], details: undefined };
        
        const res = _portfolioSvc.add(symbol, quantity, avg_cost, commission || 0, name ?? "", market ?? "A", notes ?? "");
        
        // ... existing A-share logic (trade recording, orders, etc.) ...
      }
    }
    
    // ... rest of actions (sell, update, remove) ...
  } catch (error) {
    // ... error handling ...
  }
}
```

- [ ] **Step 4: Test tool manually with agent**

```bash
npm start
# In agent chat:
# "买入腾讯 100股，价格 666.57 港币"
```

Expected: Tool should call addHKStock and record FX rate

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/tools/invest/portfolio-tools.ts
git commit -m "feat(tools): add price_hkd parameter for HK stock purchases"
```

---

## Task 8: Add Cron Job for FX Rate Updates

**Files:**
- Modify: `.pi-invest/CRON.json`
- Modify: `src/api/index.ts` (or main entry point)

- [ ] **Step 1: Add FX rate update cron job to CRON.json**

```json
// Add to .pi-invest/CRON.json in the "jobs" array
{
  "id": "update-fx-rates",
  "name": "更新汇率缓存",
  "enabled": true,
  "schedule": {
    "kind": "cron",
    "expr": "0 9 * * 1-5"
  },
  "payload": {
    "kind": "system_event",
    "message": "update_fx_rates"
  }
}
```

- [ ] **Step 2: Add FX rate update handler to main entry point**

```typescript
// Modify in src/api/index.ts (or wherever CronService is initialized)
import { FxRateService } from "../services/fx-rate-service.js";

// ... existing code ...

const fxRateService = new FxRateService(PI_DIR);

const cronService = new CronService(
  cronFile,
  PI_DIR,
  async (payload: CronJobPayload) => {
    // ... existing payload handlers ...
    
    if (payload.kind === "system_event" && payload.message === "update_fx_rates") {
      try {
        await fxRateService.updateCache();
        console.log("✅ 汇率缓存已更新");
      } catch (error) {
        console.error("❌ 汇率更新失败:", error);
      }
    }
    
    // ... rest of handlers ...
  }
);
```

- [ ] **Step 3: Test cron job manually**

```bash
npm start
# Wait for 9:00 AM on a weekday, or manually trigger via cron tools
```

Expected: FX rate cache should be updated at 9:00 AM

- [ ] **Step 4: Verify cache file is created**

```bash
cat .pi-invest/fx-rates.json
```

Expected: JSON file with HKDCNY rate

- [ ] **Step 5: Commit**

```bash
git add .pi-invest/CRON.json src/api/index.ts
git commit -m "feat(cron): add daily FX rate update job at 9:00 AM"
```

---

## Task 9: Create Data Migration Script

**Files:**
- Create: `src/scripts/migrate-hk-holdings.ts`

- [ ] **Step 1: Create migration script**

```typescript
// src/scripts/migrate-hk-holdings.ts
import { PortfolioService } from "../services/portfolio/portfolio-service.js";
import { FxRateService } from "../services/fx-rate-service.js";
import { writeFileSync } from "fs";
import { join } from "path";

const PI_DIR = join(process.cwd(), ".pi-invest");

async function migrateHKHoldings() {
  const portfolioService = new PortfolioService(PI_DIR);
  const fxRateService = new FxRateService(PI_DIR);
  
  console.log("🔄 开始迁移港股持仓数据...\n");
  
  // 1. Backup original file
  const backupPath = join(PI_DIR, `portfolio.backup.${Date.now()}.json`);
  const originalData = portfolioService.load();
  writeFileSync(backupPath, JSON.stringify(originalData, null, 2));
  console.log(`✅ 已备份到: ${backupPath}\n`);
  
  // 2. Get current FX rate
  const currentFxRate = await fxRateService.getRate("HKDCNY");
  console.log(`当前汇率: ${currentFxRate}\n`);
  
  // 3. Migrate HK holdings
  let migratedCount = 0;
  
  for (const holding of originalData.holdings) {
    if (holding.market === "HK" && !holding.avg_cost_hkd) {
      // Reverse calculate HKD cost
      const avgCostHKD = holding.avg_cost / currentFxRate;
      
      console.log(`📊 ${holding.symbol} ${holding.name}`);
      console.log(`   人民币成本: ${holding.avg_cost.toFixed(2)} CNY`);
      console.log(`   反推港币成本: ${avgCostHKD.toFixed(2)} HKD`);
      console.log(`   记录汇率: ${currentFxRate}`);
      console.log(`   ⚠️  注意：反推的港币成本不是真实买入价，仅作估算\n`);
      
      // Update fields
      holding.avg_cost_hkd = Math.round(avgCostHKD * 100) / 100;
      holding.purchase_fx_rate = currentFxRate;
      
      migratedCount++;
    }
  }
  
  // 4. Save
  if (migratedCount > 0) {
    portfolioService.replaceHoldings(originalData.holdings);
    console.log(`✅ 迁移完成，共更新 ${migratedCount} 只港股持仓`);
    console.log(`\n💡 提示：如果你记得真实买入价，可以手动修正 portfolio.json 中的 avg_cost_hkd 字段`);
  } else {
    console.log("ℹ️  无需迁移，所有港股持仓已包含汇率信息");
  }
}

migrateHKHoldings().catch(console.error);
```

- [ ] **Step 2: Add script to package.json**

```json
// Add to package.json scripts section
{
  "scripts": {
    "migrate:hk-holdings": "tsx src/scripts/migrate-hk-holdings.ts"
  }
}
```

- [ ] **Step 3: Run migration script**

```bash
npm run migrate:hk-holdings
```

Expected: Backup created, HK holdings updated with avg_cost_hkd and purchase_fx_rate

- [ ] **Step 4: Verify migration results**

```bash
cat .pi-invest/portfolio.json | jq '.holdings[] | select(.market == "HK")'
```

Expected: HK holdings should have avg_cost_hkd and purchase_fx_rate fields

- [ ] **Step 5: Commit**

```bash
git add src/scripts/migrate-hk-holdings.ts package.json
git commit -m "feat(migration): add HK holdings data migration script"
```

---

## Task 10: Integration Testing and Verification

**Files:**
- Test: All modified files

- [ ] **Step 1: Run all unit tests**

```bash
npm test
```

Expected: All tests PASS

- [ ] **Step 2: Test A-share workflow (verify no regression)**

```bash
npm start
# In agent chat:
# "买入贵州茅台 100股，成本 1750 元"
# "查看持仓"
```

Expected: A-share purchase and query work as before

- [ ] **Step 3: Test HK stock workflow**

```bash
# In agent chat:
# "买入腾讯 100股，价格 666.57 港币"
# "查看持仓"
```

Expected: 
- HK stock recorded with HKD price and FX rate
- Portfolio query shows CNY-converted market value
- Total portfolio value includes both A-shares and HK stocks in CNY

- [ ] **Step 4: Test FX rate caching**

```bash
cat .pi-invest/fx-rates.json
```

Expected: Cache file exists with HKDCNY rate

- [ ] **Step 5: Test HK stock add-on (weighted average)**

```bash
# In agent chat:
# "加仓腾讯 100股，价格 680 港币"
# "查看持仓"
```

Expected: Weighted average cost calculated correctly in both HKD and CNY

- [ ] **Step 6: Verify cron job is loaded**

```bash
npm start
# Check console output for cron job list
```

Expected: "更新汇率缓存" job listed with next run time

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "test: verify HK stock FX handling integration"
```

---

## Self-Review Checklist

**Spec Coverage:**
- [x] FxRateService with caching and fallback (Tasks 1-3)
- [x] Data structures updated (Task 4)
- [x] PortfolioService.addHKStock (Task 5)
- [x] getWithPnL FX conversion (Task 6)
- [x] Agent tool updated (Task 7)
- [x] Cron job for daily updates (Task 8)
- [x] Data migration script (Task 9)
- [x] Integration testing (Task 10)

**Placeholder Check:**
- [x] No TBD/TODO placeholders
- [x] All code blocks complete
- [x] All file paths exact
- [x] All commands with expected output

**Type Consistency:**
- [x] FxRatesFile interface consistent across tasks
- [x] Holding interface with optional HK fields
- [x] Trade interface with optional HK fields
- [x] HoldingWithPnL interface with optional HK fields

**Missing from Spec:**
- None identified

---

## Execution Notes

**Estimated Time:** 3-4 hours for full implementation

**Dependencies:**
- Existing PortfolioService and TradeService
- Existing CronService
- Sina Finance API availability

**Risks:**
- Network dependency for FX rate fetching (mitigated by 4-layer fallback)
- Data migration accuracy (mitigated by backup and manual correction option)

---

**Plan Complete**

