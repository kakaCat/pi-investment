# 港股汇率处理完整设计

**日期**: 2026-05-16  
**作者**: Claude (Opus 4.6)  
**状态**: Draft

---

## 1. 背景与问题

### 1.1 当前问题

用户持有港股（小米、腾讯、阿里），现有系统存在以下问题：

1. **成本记录不完整**：只记录了人民币成本，缺少港币成本和买入汇率
2. **汇率因素未考虑**：查询持仓时，直接把港币和人民币市值相加，导致总市值、总盈亏不准确
3. **无法区分波动来源**：无法区分盈亏是来自股价波动还是汇率波动

### 1.2 港股通汇率规则

根据港股通交易规则：

- **参考汇率来源**：中国外汇交易中心每个交易日上午公布
- **汇率固定性**：当日所有交易使用同一个参考汇率，不随盘中波动
- **成本锁定**：买入时用T日参考汇率，成本永久锁定
- **结算周期**：T+2结算，但使用T日汇率

### 1.3 设计目标

1. **成本锁定**：买入时记录港币价格和汇率，人民币成本永久锁定
2. **市值准确**：查询时用当日参考汇率转换港股市值
3. **向后兼容**：不影响现有A股逻辑和数据
4. **数据迁移**：为现有港股持仓补充汇率信息

---

## 2. 数据结构设计

### 2.1 持仓数据结构（Holding）

```typescript
export interface Holding {
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;              // 人民币成本（CNY），所有股票统一
  avg_cost_hkd?: number;         // 🆕 港币成本（HKD），仅港股
  purchase_fx_rate?: number;     // 🆕 买入时汇率（HKD→CNY），仅港股
  market: "A" | "HK";
  notes: string;
  added_date: string;
  stop_loss?: number | null;
  target_price?: number | null;
  sector?: string;
  buy_reason?: string;
}
```

**字段说明**：
- `avg_cost`: 人民币成本，A股和港股都用CNY，便于统一计算总成本
- `avg_cost_hkd`: 港币成本（如666.57 HKD），用于查询时对比港币价格
- `purchase_fx_rate`: 买入时汇率（如0.8820），用于验证和追溯

**示例**：
```json
{
  "symbol": "00700",
  "name": "腾讯控股",
  "quantity": 100,
  "avg_cost": 587.84,
  "avg_cost_hkd": 666.57,
  "purchase_fx_rate": 0.8820,
  "market": "HK"
}
```

### 2.2 汇率缓存结构（FxRates）

**文件位置**：`.pi-invest/fx-rates.json`

```typescript
interface FxRatesFile {
  rates: {
    [pair: string]: {
      rate: number;           // 汇率值
      date: string;           // 日期 YYYY-MM-DD
      updated_at: string;     // 更新时间
      source: string;         // 数据源（sina）
    };
  };
  last_updated: string;
}
```

**示例**：
```json
{
  "rates": {
    "HKDCNY": {
      "rate": 0.8850,
      "date": "2026-05-16",
      "updated_at": "2026-05-16 09:00:15",
      "source": "sina"
    }
  },
  "last_updated": "2026-05-16 09:00:15"
}
```

### 2.3 交易记录结构（Trade）

```typescript
export interface Trade {
  id: string;
  date: string;
  symbol: string;
  name: string;
  action: "buy" | "sell";
  quantity: number;
  price: number;                 // 成交价（CNY）
  price_hkd?: number;            // 🆕 港币成交价（HKD），仅港股
  fx_rate?: number;              // 🆕 成交时汇率，仅港股
  commission: number;
  amount: number;                // 成交金额（CNY）
  market: "A" | "HK";
  notes: string;
  pnl?: number;
  pnl_pct?: number;
}
```

---

## 3. 汇率服务设计

### 3.1 FxRateService 类

**文件位置**：`src/services/fx-rate-service.ts`

**核心方法**：

```typescript
export class FxRateService {
  private cachePath: string;  // .pi-invest/fx-rates.json
  
  constructor(piDir: string) {
    this.cachePath = join(piDir, "fx-rates.json");
  }
  
  /**
   * 获取汇率（优先缓存，失败则实时获取）
   * @param pair 货币对（目前仅支持 HKDCNY）
   * @returns 汇率值
   */
  async getRate(pair: "HKDCNY"): Promise<number>
  
  /**
   * 从新浪获取实时汇率
   */
  async fetchRateFromSina(pair: "HKDCNY"): Promise<number>
  
  /**
   * 更新缓存（由 cron 调用）
   */
  async updateCache(): Promise<void>
  
  /**
   * 读取缓存
   */
  private loadCache(): FxRatesFile
  
  /**
   * 保存缓存
   */
  private saveCache(data: FxRatesFile): void
  
  /**
   * 检查缓存是否过期（超过24小时）
   */
  private isCacheStale(date: string): boolean
  
  /**
   * 判断是否非交易日
   */
  private isNonTradingDay(): boolean
}
```

### 3.2 新浪汇率数据源

**接口**：`https://hq.sinajs.cn/list=HKDCNY`

**返回格式**：
```
var hq_str_HKDCNY="0.8850,0.8860,0.8840,2026-05-16 09:00:00";
```

**解析逻辑**：
```typescript
// src/infrastructure/data-sources/sina.ts
export async function fetchSinaFxRate(pair: string): Promise<number> {
  const url = `https://hq.sinajs.cn/list=${pair}`;
  const response = await fetch(url);
  const text = await response.text();
  
  const match = text.match(/"([^"]+)"/);
  if (!match) throw new Error("汇率数据解析失败");
  
  const parts = match[1].split(",");
  return parseFloat(parts[0]);  // 取第一个值（买入价）
}
```

### 3.3 降级策略

```typescript
async getRate(pair: "HKDCNY"): Promise<number> {
  try {
    // 1. 优先使用缓存（24小时内有效）
    const cache = this.loadCache();
    const cached = cache.rates[pair];
    if (cached && !this.isCacheStale(cached.date)) {
      return cached.rate;
    }
    
    // 2. 缓存过期，尝试实时获取
    const rate = await this.fetchRateFromSina(pair);
    this.saveCache({
      ...cache,
      rates: {
        ...cache.rates,
        [pair]: {
          rate,
          date: chinaDate(),
          updated_at: chinaDateTime(),
          source: "sina"
        }
      },
      last_updated: chinaDateTime()
    });
    return rate;
    
  } catch (error) {
    // 3. 实时获取失败，使用旧缓存（即使过期）
    const cache = this.loadCache();
    if (cache.rates[pair]) {
      console.warn(`⚠️ 汇率获取失败，使用缓存值: ${cache.rates[pair].rate} (${cache.rates[pair].date})`);
      return cache.rates[pair].rate;
    }
    
    // 4. 无缓存，使用默认值（最后手段）
    console.error("❌ 汇率获取失败且无缓存，使用默认值 0.88");
    return 0.88;
  }
}
```

**Why**: 四层降级确保系统在任何情况下都能运行，避免因汇率获取失败导致持仓查询崩溃。

**How to apply**: 
- 正常情况：使用当日缓存
- 网络故障：使用前一日缓存
- 系统初始化：使用硬编码默认值

---

## 4. Cron 定时任务设计

### 4.1 Cron 任务配置

**文件位置**：`.pi-invest/CRON.json`

**新增任务**：
```json
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

**配置说明**：
- `expr: "0 9 * * 1-5"` - 每个交易日（周一至周五）上午9:00执行
- `kind: "system_event"` - 系统事件，不触发agent对话
- 执行时机：开盘前更新，确保当日交易使用最新汇率

**Why**: 港股通使用当日参考汇率，每日9:00更新确保全天使用正确汇率。

### 4.2 Cron 处理逻辑

**文件位置**：`src/api/index.ts`（或主入口文件）

```typescript
const fxRateService = new FxRateService(PI_DIR);

const cronService = new CronService(
  cronFile,
  PI_DIR,
  async (payload: CronJobPayload) => {
    if (payload.kind === "system_event" && payload.message === "update_fx_rates") {
      try {
        await fxRateService.updateCache();
        console.log("✅ 汇率缓存已更新");
      } catch (error) {
        console.error("❌ 汇率更新失败:", error);
      }
    }
    // ... 其他 payload 处理
  }
);
```

### 4.3 执行时间表

| 时间 | 任务 | 说明 |
|------|------|------|
| 09:00 | 更新汇率缓存 | 获取当日参考汇率 |
| 09:30 | 检查挂单 | 使用当日汇率计算港股触发条件 |
| 15:35 | 每日复盘 | 使用当日汇率计算持仓市值 |

---

(文档第一部分已写入，继续下一部分...)

## 5. 业务逻辑设计

### 5.1 买入港股流程

```typescript
// PortfolioService.addHKStock()
async addHKStock(
  symbol: string,
  quantity: number,
  priceHKD: number,        // 港币成交价
  commission: number = 0,
  name: string = "",
  notes: string = ""
): Promise<{ success: boolean; message: string; updatedHolding?: Holding }> {
  
  // 1. 获取当日参考汇率
  const fxRate = await fxRateService.getRate("HKDCNY");
  
  // 2. 计算人民币成本
  const totalCostHKD = priceHKD * quantity;
  const commissionCNY = commission;  // 假设手续费已是人民币
  const totalCostCNY = totalCostHKD * fxRate + commissionCNY;
  const avgCostCNY = totalCostCNY / quantity;
  
  // 3. 检查是否已有持仓
  const existingHolding = this.load().holdings.find(h => h.symbol === symbol);
  
  if (existingHolding) {
    // 加仓：加权平均
    return this.addToExistingHKHolding(existingHolding, quantity, priceHKD, avgCostCNY, fxRate);
  } else {
    // 新建持仓
    const newHolding: Holding = {
      symbol,
      name,
      quantity,
      avg_cost: avgCostCNY,           // 人民币成本
      avg_cost_hkd: priceHKD,         // 港币成本
      purchase_fx_rate: fxRate,       // 买入汇率
      market: "HK",
      notes,
      added_date: chinaDate(),
    };
    
    // 保存持仓
    const data = this.load();
    data.holdings.push(newHolding);
    this.save(data);
    
    return {
      success: true,
      message: `${symbol} 已录入持仓`,
      updatedHolding: newHolding
    };
  }
}
```

### 5.2 加仓港股流程（加权平均）

```typescript
private addToExistingHKHolding(
  existing: Holding,
  newQuantity: number,
  newPriceHKD: number,
  newAvgCostCNY: number,
  newFxRate: number
): { success: boolean; message: string; updatedHolding?: Holding } {
  
  // 加权平均人民币成本
  const totalCostCNY = 
    existing.avg_cost * existing.quantity +
    newAvgCostCNY * newQuantity;
  const totalQty = existing.quantity + newQuantity;
  const avgCostCNY = roundN(totalCostCNY / totalQty);
  
  // 加权平均港币成本
  const totalCostHKD = 
    (existing.avg_cost_hkd || 0) * existing.quantity +
    newPriceHKD * newQuantity;
  const avgCostHKD = roundN(totalCostHKD / totalQty);
  
  // 加权平均汇率（验证用）
  const avgFxRate = roundN(avgCostCNY / avgCostHKD, 4);
  
  // 更新持仓
  existing.quantity = totalQty;
  existing.avg_cost = avgCostCNY;
  existing.avg_cost_hkd = avgCostHKD;
  existing.purchase_fx_rate = avgFxRate;
  
  this.save(this.load());
  
  return {
    success: true,
    message: `${existing.symbol} 已加仓，新均价 ${avgCostCNY.toFixed(2)} CNY (${avgCostHKD.toFixed(2)} HKD)`,
    updatedHolding: existing
  };
}
```

**示例**：
```
已有持仓：100股 @ 666.57 HKD，汇率 0.8820，成本 587.84 CNY/股
新买入：100股 @ 680.00 HKD，汇率 0.8850，成本 601.80 CNY/股

加权平均：
- 人民币成本 = (587.84×100 + 601.80×100) / 200 = 594.82 CNY/股
- 港币成本 = (666.57×100 + 680.00×100) / 200 = 673.29 HKD/股
- 平均汇率 = 594.82 / 673.29 = 0.8835
```

### 5.3 查询持仓市值流程

```typescript
async getPortfolioWithPnL(): Promise<PortfolioSnapshot> {
  const holdings = this.load().holdings;
  
  if (holdings.length === 0) {
    return { holdings: [], total_cost: 0, total_value: 0, total_pnl: 0, total_pnl_pct: 0, as_of: chinaDate() };
  }
  
  // 1. 获取当日参考汇率
  const fxRate = await fxRateService.getRate("HKDCNY");
  
  // 2. 并行获取所有持仓实时价格
  const priceResults = await Promise.all(
    holdings.map(h => {
      if (h.market === "HK") {
        return get_hk_stock_price(h.symbol);  // 返回港币价格
      } else {
        return get_stock_realtime_price(h.symbol);  // 返回人民币价格
      }
    })
  );
  
  // 3. 计算盈亏
  let totalCost = 0;
  let totalValue = 0;
  
  const enriched: HoldingWithPnL[] = holdings.map((h, i) => {
    const priceData = JSON.parse(priceResults[i]);
    
    if (h.market === "HK") {
      // 港股逻辑
      const currentPriceHKD = priceData.price || 0;
      const currentPriceCNY = currentPriceHKD * fxRate;  // 用当日汇率转换
      const marketValueCNY = currentPriceCNY * h.quantity;
      const costCNY = h.avg_cost * h.quantity;
      const pnlAmount = roundN(marketValueCNY - costCNY);
      const pnlPct = costCNY > 0 ? roundN((pnlAmount / costCNY) * 100) : 0;
      
      totalCost += costCNY;
      totalValue += marketValueCNY;
      
      return {
        ...h,
        current_price: currentPriceCNY,      // 显示人民币价格
        current_price_hkd: currentPriceHKD,  // 同时保留港币价格
        current_fx_rate: fxRate,             // 当前汇率
        change_pct: priceData.change_pct || 0,
        market_value: marketValueCNY,
        pnl_amount: pnlAmount,
        pnl_pct: pnlPct,
      };
    } else {
      // A股逻辑（保持不变）
      const currentPriceCNY = priceData.price || 0;
      const marketValueCNY = currentPriceCNY * h.quantity;
      const costCNY = h.avg_cost * h.quantity;
      const pnlAmount = roundN(marketValueCNY - costCNY);
      const pnlPct = costCNY > 0 ? roundN((pnlAmount / costCNY) * 100) : 0;
      
      totalCost += costCNY;
      totalValue += marketValueCNY;
      
      return {
        ...h,
        current_price: currentPriceCNY,
        change_pct: priceData.change_pct || 0,
        market_value: marketValueCNY,
        pnl_amount: pnlAmount,
        pnl_pct: pnlPct,
      };
    }
  });
  
  const totalPnl = roundN(totalValue - totalCost);
  const totalPnlPct = totalCost > 0 ? roundN((totalPnl / totalCost) * 100) : 0;
  
  return {
    holdings: enriched,
    total_cost: totalCost,
    total_value: totalValue,
    total_pnl: totalPnl,
    total_pnl_pct: totalPnlPct,
    as_of: chinaDate(),
  };
}
```

**Why**: 港股用当日汇率转换市值，确保总市值准确反映当前价值（包含汇率变化）。

### 5.4 卖出港股流程

```typescript
async sellHKStock(
  symbol: string,
  quantity: number,
  priceHKD: number,
  commission: number = 0,
  notes: string = ""
): Promise<SellResult> {
  
  // 1. 获取当日汇率
  const fxRate = await fxRateService.getRate("HKDCNY");
  
  // 2. 计算人民币价格
  const priceCNY = priceHKD * fxRate;
  
  // 3. 调用通用卖出逻辑
  const result = this.sell(symbol, quantity, priceCNY, commission, notes);
  
  // 4. 记录交易时补充港币信息
  if (result.tradeRecorded && this.tradeService) {
    // 更新最后一条交易记录，添加港币价格和汇率
    const trades = this.tradeService.load().trades;
    const lastTrade = trades[trades.length - 1];
    if (lastTrade && lastTrade.symbol === symbol) {
      lastTrade.price_hkd = priceHKD;
      lastTrade.fx_rate = fxRate;
      this.tradeService.save({ trades, last_updated: chinaDateTime() });
    }
  }
  
  return result;
}
```

---

## 6. Agent 工具修改

### 6.1 manage_portfolio 工具修改

**文件位置**：`src/infrastructure/tools/invest/portfolio-tools.ts`

**修改内容**：

1. **新增参数**：
```typescript
parameters: Type.Object({
  // ... 现有参数
  price_hkd: Type.Optional(Type.Number({ 
    description: "🆕 HK stock price in HKD (港股港币价格，仅港股需要，如 666.57)" 
  })),
})
```

2. **修改 add 操作逻辑**：
```typescript
if (action === "add") {
  // 参数验证
  if (!symbol || quantity == null) {
    return { error: "add 需要 symbol, quantity" };
  }
  
  // 港股：需要 price_hkd
  if (market === "HK") {
    if (!price_hkd) {
      return { error: "港股需要提供 price_hkd（港币价格）" };
    }
    
    // 调用港股专用方法
    const res = await _portfolioSvc.addHKStock(
      symbol, 
      quantity, 
      price_hkd, 
      commission || 0, 
      name || "", 
      notes || ""
    );
    
    // 记录交易
    const fxRate = await fxRateService.getRate("HKDCNY");
    const priceCNY = price_hkd * fxRate;
    const ts = new TradeService(PI_DIR);
    ts.add(
      chinaDate(), 
      symbol, 
      name || symbol, 
      "buy", 
      quantity, 
      priceCNY,      // 人民币价格
      commission || 0, 
      "HK", 
      notes || "手动录入",
      undefined,
      undefined,
      price_hkd,     // 港币价格
      fxRate         // 汇率
    );
    
    return { content: [{ type: "text", text: JSON.stringify(res) }] };
  } 
  
  // A股：保持原逻辑
  else {
    if (!avg_cost) {
      return { error: "A股需要提供 avg_cost（人民币成本）" };
    }
    
    const res = _portfolioSvc.add(
      symbol, 
      quantity, 
      avg_cost, 
      commission || 0, 
      name || "", 
      market || "A", 
      notes || ""
    );
    
    // ... 原有逻辑
  }
}
```

**Why**: 港股和A股的买入逻辑不同，港股需要汇率转换，因此分开处理。

**How to apply**: 
- Agent 买入港股时，必须提供 `price_hkd` 参数
- Agent 买入A股时，保持原有调用方式不变

### 6.2 工具使用示例

**买入港股**：
```typescript
manage_portfolio({
  action: "add",
  symbol: "00700",
  name: "腾讯控股",
  quantity: 100,
  price_hkd: 666.57,        // 港币价格
  market: "HK",
  commission: 50
})

// 工具内部：
// 1. 获取汇率 0.8850
// 2. 计算 avg_cost = 666.57 × 0.8850 = 589.71 CNY
// 3. 保存 avg_cost=589.71, avg_cost_hkd=666.57, purchase_fx_rate=0.8850
```

**买入A股**（保持不变）：
```typescript
manage_portfolio({
  action: "add",
  symbol: "600519",
  name: "贵州茅台",
  quantity: 100,
  avg_cost: 1750.00,        // 人民币价格
  market: "A",
  commission: 25
})
```

**查询持仓**：
```typescript
manage_portfolio({ action: "get_with_pnl" })

// 返回示例：
{
  "holdings": [
    {
      "symbol": "00700",
      "name": "腾讯控股",
      "quantity": 100,
      "avg_cost": 589.71,           // 人民币成本（锁定）
      "avg_cost_hkd": 666.57,       // 港币成本
      "purchase_fx_rate": 0.8850,   // 买入汇率
      "current_price": 592.95,      // 当前人民币价格
      "current_price_hkd": 670.00,  // 当前港币价格
      "current_fx_rate": 0.8850,    // 当日汇率
      "market_value": 59295.00,     // 市值（CNY）
      "pnl_amount": 324.00,         // 盈亏（CNY）
      "pnl_pct": 0.55,              // 盈亏比例
      "market": "HK"
    }
  ],
  "total_cost": 589710.00,
  "total_value": 592950.00,
  "total_pnl": 3240.00,
  "total_pnl_pct": 0.55
}
```

### 6.3 向后兼容性

**A股不受影响**：
- 新增字段是可选的（`?`），A股不填
- 查询逻辑通过 `market` 字段区分
- A股工具调用方式完全不变

**旧港股持仓兼容**：
- 如果 `avg_cost_hkd` 为空，临时用当前汇率反推
- 提示用户运行迁移脚本补充数据

---


## 7. 数据迁移设计

### 7.1 迁移脚本

**文件位置**：`src/scripts/migrate-hk-holdings.ts`

**目的**：为现有港股持仓添加 `avg_cost_hkd` 和 `purchase_fx_rate` 字段

**方法**：用当前汇率反推港币成本

```typescript
import { PortfolioService } from "../services/portfolio/portfolio-service.js";
import { FxRateService } from "../services/fx-rate-service.js";
import { writeFileSync } from "fs";
import { join } from "path";

const PI_DIR = join(process.cwd(), ".pi-invest");

async function migrateHKHoldings() {
  const portfolioService = new PortfolioService(PI_DIR);
  const fxRateService = new FxRateService(PI_DIR);
  
  console.log("🔄 开始迁移港股持仓数据...\n");
  
  // 1. 备份原文件
  const backupPath = join(PI_DIR, `portfolio.backup.${Date.now()}.json`);
  const originalData = portfolioService.load();
  writeFileSync(backupPath, JSON.stringify(originalData, null, 2));
  console.log(`✅ 已备份到: ${backupPath}\n`);
  
  // 2. 获取当前汇率
  const currentFxRate = await fxRateService.getRate("HKDCNY");
  console.log(`当前汇率: ${currentFxRate}\n`);
  
  // 3. 迁移港股持仓
  let migratedCount = 0;
  
  for (const holding of originalData.holdings) {
    if (holding.market === "HK" && !holding.avg_cost_hkd) {
      // 反推港币成本
      const avgCostHKD = holding.avg_cost / currentFxRate;
      
      console.log(`📊 ${holding.symbol} ${holding.name}`);
      console.log(`   人民币成本: ${holding.avg_cost.toFixed(2)} CNY`);
      console.log(`   反推港币成本: ${avgCostHKD.toFixed(2)} HKD`);
      console.log(`   记录汇率: ${currentFxRate}`);
      console.log(`   ⚠️  注意：反推的港币成本不是真实买入价，仅作估算\n`);
      
      // 更新字段
      holding.avg_cost_hkd = Math.round(avgCostHKD * 100) / 100;
      holding.purchase_fx_rate = currentFxRate;
      
      migratedCount++;
    }
  }
  
  // 4. 保存
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

### 7.2 迁移前后对比

**迁移前**：
```json
{
  "symbol": "00700",
  "name": "腾讯控股",
  "quantity": 100,
  "avg_cost": 666.57,
  "market": "HK",
  "added_date": "2026-05-07"
}
```

**迁移后**：
```json
{
  "symbol": "00700",
  "name": "腾讯控股",
  "quantity": 100,
  "avg_cost": 666.57,
  "avg_cost_hkd": 753.15,
  "purchase_fx_rate": 0.8850,
  "market": "HK",
  "added_date": "2026-05-07"
}
```

### 7.3 迁移注意事项

1. **自动备份**：迁移前自动备份 `portfolio.json` 到 `portfolio.backup.{timestamp}.json`
2. **幂等性**：可重复执行，已迁移的持仓不会重复处理
3. **汇率准确性**：反推的汇率不是真实买入汇率，仅作估算
4. **手动修正**：如果记得真实买入价，建议手动修正 `avg_cost_hkd` 字段

**Why**: 用当前汇率反推不准确，但总比没有好。用户可以根据交易记录手动修正。

---

## 8. 错误处理与边界情况

### 8.1 汇率获取失败

**场景**：新浪接口不可用，无法获取汇率

**处理策略**：四层降级
1. 使用缓存（24小时内有效）
2. 尝试实时获取
3. 使用过期缓存（降级）
4. 使用硬编码默认值 0.88（最后手段）

**代码**：见第3.3节

### 8.2 港股价格获取失败

**场景**：查询持仓时，某只港股价格获取失败

**处理策略**：
```typescript
const priceResults = await Promise.all(
  holdings.map(h => 
    h.market === "HK" 
      ? get_hk_stock_price(h.symbol).catch(() => JSON.stringify({ 
          error: "价格获取失败", 
          price: 0,
          symbol: h.symbol 
        }))
      : get_stock_realtime_price(h.symbol).catch(...)
  )
);

// 计算时跳过价格为0的持仓
if (currentPriceHKD === 0) {
  return {
    ...h,
    current_price: 0,
    market_value: 0,
    pnl_amount: 0,
    pnl_pct: 0,
    error: "价格获取失败"
  };
}
```

### 8.3 数据不一致

**场景1**：旧持仓没有 `avg_cost_hkd`

**处理**：
```typescript
if (holding.market === "HK" && !holding.avg_cost_hkd) {
  console.warn(`⚠️ ${holding.symbol} 缺少港币成本，请运行迁移脚本`);
  // 临时用当前汇率反推
  const fxRate = await getFxRate("HKDCNY");
  holding.avg_cost_hkd = holding.avg_cost / fxRate;
}
```

**场景2**：`avg_cost` 与 `avg_cost_hkd × purchase_fx_rate` 不一致

**处理**：
```typescript
// 验证数据一致性（开发模式）
if (process.env.NODE_ENV === "development") {
  const calculatedCost = holding.avg_cost_hkd * holding.purchase_fx_rate;
  const diff = Math.abs(calculatedCost - holding.avg_cost);
  if (diff > 0.1) {
    console.warn(
      `⚠️ ${holding.symbol} 成本数据不一致: ` +
      `avg_cost=${holding.avg_cost}, ` +
      `avg_cost_hkd×fx_rate=${calculatedCost.toFixed(2)}`
    );
  }
}
```

### 8.4 非交易日查询

**场景**：周末或节假日查询持仓，无法获取当日汇率

**处理**：
```typescript
private isNonTradingDay(): boolean {
  const now = new Date();
  const day = now.getDay();
  const hour = now.getHours();
  
  // 周末
  if (day === 0 || day === 6) return true;
  
  // 工作日但非交易时间（简化判断）
  if (hour < 9 || hour > 15) return true;
  
  return false;
}

async getRate(pair: "HKDCNY"): Promise<number> {
  const cached = this.loadCache().rates[pair];
  
  // 如果今天是非交易日，使用缓存（即使"过期"）
  if (this.isNonTradingDay()) {
    if (cached) {
      console.log(`ℹ️ 非交易日，使用 ${cached.date} 汇率 ${cached.rate}`);
      return cached.rate;
    }
  }
  
  // ... 正常逻辑
}
```

---

## 9. 实施计划

### 9.1 实施步骤

1. **Phase 1: 基础设施**
   - [ ] 实现 `FxRateService` 类
   - [ ] 添加新浪汇率数据源
   - [ ] 实现汇率缓存逻辑
   - [ ] 单元测试

2. **Phase 2: 数据结构**
   - [ ] 更新 `Holding` 接口
   - [ ] 更新 `Trade` 接口
   - [ ] 更新 `HoldingWithPnL` 接口

3. **Phase 3: 业务逻辑**
   - [ ] 实现 `PortfolioService.addHKStock()`
   - [ ] 实现 `PortfolioService.sellHKStock()`
   - [ ] 更新 `PortfolioService.getWithPnL()` 支持港股汇率转换
   - [ ] 更新 `TradeService` 支持港股字段

4. **Phase 4: Agent 工具**
   - [ ] 更新 `manage_portfolio` 工具参数
   - [ ] 更新 `manage_portfolio` 工具逻辑
   - [ ] 更新 `check_pending_orders` 工具（如需要）

5. **Phase 5: Cron 任务**
   - [ ] 添加 `update-fx-rates` cron 任务到 `CRON.json`
   - [ ] 更新主入口文件处理 `system_event`

6. **Phase 6: 数据迁移**
   - [ ] 编写迁移脚本 `migrate-hk-holdings.ts`
   - [ ] 备份现有数据
   - [ ] 执行迁移
   - [ ] 验证迁移结果

7. **Phase 7: 测试与验证**
   - [ ] 单元测试
   - [ ] 集成测试
   - [ ] 手动测试买入/卖出/查询流程
   - [ ] 验证 A 股不受影响

### 9.2 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 汇率接口不可用 | 无法获取汇率 | 四层降级策略 + 缓存 |
| 数据迁移失败 | 旧数据丢失 | 自动备份 + 幂等性 |
| A股逻辑受影响 | 现有功能异常 | 通过 `market` 字段隔离 + 充分测试 |
| 反推汇率不准确 | 成本数据偏差 | 提示用户手动修正 + 记录真实汇率 |

### 9.3 验收标准

**功能验收**：
- [ ] 买入港股时，正确记录港币价格和汇率
- [ ] 查询持仓时，港股市值用当日汇率转换
- [ ] 总市值、总盈亏计算准确（港股+A股）
- [ ] A股功能不受影响
- [ ] Cron 任务每日自动更新汇率

**数据验收**：
- [ ] 所有港股持仓包含 `avg_cost_hkd` 和 `purchase_fx_rate`
- [ ] 汇率缓存文件正常生成和更新
- [ ] 交易记录包含港币价格和汇率

**性能验收**：
- [ ] 查询持仓响应时间 < 2秒
- [ ] 汇率缓存命中率 > 95%

---

## 10. 总结

### 10.1 核心设计决策

1. **历史成本法**：成本锁定在买入时汇率，不随市场汇率变化
2. **当日参考汇率**：查询市值时使用当日参考汇率，符合港股通规则
3. **向后兼容**：新增字段可选，A股逻辑零改动
4. **四层降级**：确保汇率获取的高可用性

### 10.2 关键技术点

- **数据结构**：`avg_cost_hkd` + `purchase_fx_rate` 记录港股汇率信息
- **汇率服务**：`FxRateService` 提供缓存 + 实时获取 + 降级策略
- **Cron 任务**：每日 9:00 自动更新汇率缓存
- **业务隔离**：通过 `market` 字段区分 A 股和港股逻辑

### 10.3 未来扩展

1. **多币种支持**：扩展到美股（USD→CNY）
2. **汇兑损益分析**：单独统计汇率波动带来的盈亏
3. **历史汇率查询**：支持查询任意日期的汇率
4. **汇率预警**：汇率大幅波动时发送通知

---

**设计完成日期**: 2026-05-16  
**下一步**: 编写实施计划（writing-plans skill）

