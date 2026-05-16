import { describe, expect, test, jest } from "@jest/globals";
import { mkdtempSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { buildPortfolioSnapshotFromQuotes, PortfolioService, type Holding } from "./portfolio-service.js";
import { TradeService } from "./trade-service.js";
import { FxRateServiceAdapter } from "../fx-rate-service-adapter.js";
import * as akshareTs from "../../infrastructure/akshare-ts/index.js";

describe("buildPortfolioSnapshotFromQuotes", () => {
  test("calculates per-position and aggregate pnl", () => {
    const holdings: Holding[] = [
      {
        symbol: "600519",
        name: "茅台",
        quantity: 100,
        avg_cost: 10,
        market: "A",
        notes: "",
        added_date: "2026-03-20",
      },
      {
        symbol: "00700",
        name: "腾讯",
        quantity: 50,
        avg_cost: 20,
        market: "HK",
        notes: "",
        added_date: "2026-03-20",
      },
    ];

    // For HK stock: price 18 HKD * 0.88 FX rate = 15.84 CNY
    // P&L: (15.84 - 20) * 50 = -208
    const snapshot = buildPortfolioSnapshotFromQuotes(holdings, [
      { name: "贵州茅台", price: 12, change_pct: 5 },
      { price: 18, change_pct: -1.5 },
    ], 0.88);

    expect(snapshot.holdings[0].name).toBe("贵州茅台");
    expect(snapshot.holdings[0].pnl_amount).toBe(200);
    expect(snapshot.holdings[1].pnl_amount).toBe(-208);
    expect(snapshot.total_cost).toBe(2000);
    expect(snapshot.total_value).toBe(1992); // 1200 + 792
    expect(snapshot.total_pnl).toBe(-8); // 200 + (-208)
    expect(snapshot.total_pnl_pct).toBe(-0.4);
  });
});

describe("PortfolioService", () => {
  test("replaceHoldings overwrites old positions instead of merging", () => {
    const service = new PortfolioService(mkdtempSync(join(tmpdir(), "pi-invest-portfolio-")));
    service.add("600519", 100, 10, 0, "茅台", "A");

    service.replaceHoldings([
      {
        symbol: "00700",
        name: "腾讯",
        quantity: 50,
        avg_cost: 20,
        market: "HK",
        notes: "从交易历史重建",
        added_date: "2026-03-21",
      },
    ]);

    const data = service.load();
    expect(data.holdings).toHaveLength(1);
    expect(data.holdings[0].symbol).toBe("00700");
  });

  test("sell() reduces position and calculates P&L", () => {
    const service = new PortfolioService(mkdtempSync(join(tmpdir(), "pi-invest-portfolio-")));
    service.add("600519", 100, 10, 0, "茅台", "A");

    const result = service.sell("600519", 30, 12, 0, "部分卖出");

    expect(result.success).toBe(true);
    expect(result.quantity).toBe(30);
    expect(result.remaining).toBe(70);
    expect(result.pnlAmount).toBe(60); // (12 - 10) * 30
    expect(result.pnlPct).toBe(20); // (12 - 10) / 10 * 100

    // ✅ 验证返回了更新后的持仓
    expect(result.updatedHolding).toBeDefined();
    expect(result.updatedHolding?.symbol).toBe("600519");
    expect(result.updatedHolding?.quantity).toBe(70);

    const data = service.load();
    expect(data.holdings).toHaveLength(1);
    expect(data.holdings[0].quantity).toBe(70);
  });

  test("sell() clears position when selling all shares", () => {
    const service = new PortfolioService(mkdtempSync(join(tmpdir(), "pi-invest-portfolio-")));
    service.add("600519", 100, 10, 0, "茅台", "A");

    const result = service.sell("600519", 100, 12);

    expect(result.success).toBe(true);
    expect(result.remaining).toBe(0);

    // ✅ 清仓后不应该有 updatedHolding
    expect(result.updatedHolding).toBeUndefined();

    const data = service.load();
    expect(data.holdings).toHaveLength(0);
  });

  test("sell() throws error when position not found", () => {
    const service = new PortfolioService(mkdtempSync(join(tmpdir(), "pi-invest-portfolio-")));

    expect(() => service.sell("600519", 100, 12)).toThrow("未找到持仓: 600519");
  });

  test("sell() throws error when insufficient shares", () => {
    const service = new PortfolioService(mkdtempSync(join(tmpdir(), "pi-invest-portfolio-")));
    service.add("600519", 50, 10, 0, "茅台", "A");

    expect(() => service.sell("600519", 100, 12)).toThrow("持仓不足");
  });

  test("sell() records pnl to TradeService when integrated", () => {
    const testDir = mkdtempSync(join(tmpdir(), "pi-invest-integrated-"));
    const portfolioService = new PortfolioService(testDir);
    const tradeService = new TradeService(testDir);

    // 集成 TradeService
    portfolioService.setTradeService(tradeService);

    // 先通过 TradeService 记录买入（这样 TradeService 才知道有持仓）
    tradeService.add("2026-03-20", "600519", "茅台", "buy", 100, 10, 5, "A", "建仓");

    // 同步到 PortfolioService（实际使用中会通过 replaceHoldings 同步）
    portfolioService.add("600519", 100, 10, 5, "茅台", "A");

    // 卖出获利
    const result = portfolioService.sell("600519", 40, 15, 3, "止盈");

    expect(result.success).toBe(true);
    expect(result.pnlAmount).toBe(195); // (15 * 40 - 3) - (10.05 * 40) = 597 - 402 = 195
    expect(result.tradeRecorded).toBe(true);

    // 验证交易记录包含盈亏
    const trades = tradeService.load().trades;
    const sellTrade = trades.find(t => t.action === "sell");

    expect(sellTrade).toBeDefined();
    expect(sellTrade?.pnl).toBe(195);
    expect(sellTrade?.pnl_pct).toBeCloseTo(48.51, 1); // 195 / 402 * 100
  });

  test("stores HK stock without FX fields when using add()", () => {
    const testDir = mkdtempSync(join(tmpdir(), "pi-invest-hk-fx-"));
    const service = new PortfolioService(testDir);

    const result = service.add("00700", 100, 589.71, 0, "腾讯控股", "HK", "");

    const data = service.load();
    const holding = data.holdings.find(h => h.symbol === "00700");

    expect(holding).toBeDefined();
    expect(holding?.avg_cost).toBe(589.71);
    expect(holding?.avg_cost_hkd).toBeUndefined(); // add() doesn't set HK fields
    expect(holding?.purchase_fx_rate).toBeUndefined(); // addHKStock() will set these in Task 5
  });

  test("addHKStock records HKD price and FX rate", async () => {
    const testDir = mkdtempSync(join(tmpdir(), "pi-invest-hk-fx-"));
    const service = new PortfolioService(testDir);

    // Mock FX rate by creating a fresh cache
    const cache = {
      rates: {
        HKDCNY: {
          rate: 0.8850,
          date: "2026-05-16",
          updated_at: "2026-05-16 09:00:00",
          source: "sina"
        }
      },
      last_updated: "2026-05-16 09:00:00"
    };
    writeFileSync(join(testDir, "fx-rates.json"), JSON.stringify(cache, null, 2));

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

    expect(holding?.avg_cost).toBeCloseTo(589.91, 2); // 666.57 * 0.8850 = 589.91
    expect(holding?.avg_cost_hkd).toBe(666.57);
    expect(holding?.purchase_fx_rate).toBe(0.8850);
    expect(holding?.market).toBe("HK");
  });

  test("addHKStock calculates weighted average when adding to existing position", async () => {
    const testDir = mkdtempSync(join(tmpdir(), "pi-invest-hk-fx-"));
    const service = new PortfolioService(testDir);

    // Setup FX rate cache
    const cache = {
      rates: {
        HKDCNY: { rate: 0.8850, date: "2026-05-16", updated_at: "2026-05-16 09:00:00", source: "sina" }
      },
      last_updated: "2026-05-16 09:00:00"
    };
    writeFileSync(join(testDir, "fx-rates.json"), JSON.stringify(cache, null, 2));

    // First purchase: 100 shares at 666.57 HKD
    await service.addHKStock("00700", 100, 666.57, 0, "腾讯控股", "");

    // Second purchase: 50 shares at 680.00 HKD
    await service.addHKStock("00700", 50, 680.00, 0, "腾讯控股", "");

    const data = service.load();
    const holding = data.holdings.find(h => h.symbol === "00700");

    // Weighted average HKD: (666.57*100 + 680.00*50) / 150 = 671.05
    expect(holding?.avg_cost_hkd).toBeCloseTo(671.05, 2);
    // Weighted average CNY: (589.91*100 + 601.80*50) / 150 = 593.87
    expect(holding?.avg_cost).toBeCloseTo(593.87, 2);
    expect(holding?.quantity).toBe(150);
  });

  test("getWithPnL converts HK stock prices from HKD to CNY", async () => {
    const testDir = mkdtempSync(join(tmpdir(), "pi-invest-hk-fx-"));

    // Setup FX rate cache with current rate (0.8800)
    const currentCache = {
      rates: {
        HKDCNY: { rate: 0.8800, date: "2026-05-16", updated_at: "2026-05-16 15:00:00", source: "sina" }
      },
      last_updated: "2026-05-16 15:00:00"
    };
    writeFileSync(join(testDir, "fx-rates.json"), JSON.stringify(currentCache, null, 2));

    // Create holdings manually (simulating what addHKStock would do)
    const holdings: Holding[] = [
      {
        symbol: "00700",
        name: "腾讯控股",
        quantity: 100,
        avg_cost: 589.91,  // 666.57 * 0.8850 (purchase rate)
        avg_cost_hkd: 666.57,
        purchase_fx_rate: 0.8850,
        market: "HK",
        notes: "",
        added_date: "2026-05-16"
      }
    ];

    // Mock price results (HKD price from market)
    const priceResults = [
      { price: 670.00, name: "腾讯控股", change_pct: 0.5 }
    ];

    // Test buildPortfolioSnapshotFromQuotes with FX rate
    const snapshot = buildPortfolioSnapshotFromQuotes(holdings, priceResults, 0.8800);

    const holding = snapshot.holdings[0];

    // Verify HKD price is stored
    expect(holding.current_price_hkd).toBe(670.00);

    // Verify current FX rate is stored
    expect(holding.current_fx_rate).toBe(0.8800);

    // Verify CNY price is calculated: 670 * 0.88 = 589.60
    expect(holding.current_price).toBeCloseTo(589.60, 2);

    // Verify market value: 589.60 * 100 = 58960
    expect(holding.market_value).toBeCloseTo(58960, 2);

    // Verify P&L calculation (cost was 589.91, current 589.60)
    expect(holding.pnl_amount).toBeCloseTo(-31, 0);
  });
});
