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
    service.add("600519", 100, 10, "茅台", "A");

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
});
