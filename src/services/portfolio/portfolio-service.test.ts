import { describe, expect, test } from "@jest/globals";
import { mkdtempSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { buildPortfolioSnapshotFromQuotes, PortfolioService, type Holding } from "./portfolio-service.js";

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

    const snapshot = buildPortfolioSnapshotFromQuotes(holdings, [
      { name: "贵州茅台", price: 12, change_pct: 5 },
      { price: 18, change_pct: -1.5 },
    ]);

    expect(snapshot.holdings[0].name).toBe("贵州茅台");
    expect(snapshot.holdings[0].pnl_amount).toBe(200);
    expect(snapshot.holdings[1].pnl_amount).toBe(-100);
    expect(snapshot.total_cost).toBe(2000);
    expect(snapshot.total_value).toBe(2100);
    expect(snapshot.total_pnl).toBe(100);
    expect(snapshot.total_pnl_pct).toBe(5);
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
});
