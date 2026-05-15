import { describe, expect, test } from "@jest/globals";
import { mkdtempSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { TradeService } from "./trade-service.js";

function makeService(): TradeService {
  return new TradeService(mkdtempSync(join(tmpdir(), "pi-invest-trades-")));
}

describe("TradeService", () => {
  test("rejects oversell trades", () => {
    const service = makeService();
    service.add("2026-03-20", "600519", "茅台", "buy", 100, 10);

    expect(() => {
      service.add("2026-03-21", "600519", "茅台", "sell", 120, 11);
    }).toThrow("卖出数量超过当前持仓");
  });

  test("rebuilds snapshot after partial sell", () => {
    const service = makeService();
    service.add("2026-03-20", "600519", "茅台", "buy", 100, 10, 5);
    service.add("2026-03-21", "600519", "茅台", "sell", 40, 12, 5);

    const position = service.buildSnapshot().get("600519");
    expect(position).toBeDefined();
    expect(position?.quantity).toBe(60);
    expect(position?.avg_cost).toBe(10.05);
    expect(position?.realized_pnl).toBeCloseTo(73, 6);
  });

  test("migrates old array format to new object format", () => {
    const testDir = mkdtempSync(join(tmpdir(), "pi-invest-migration-"));
    const tradesPath = join(testDir, "trades.json");

    // 写入旧的数组格式
    const oldFormat = [
      {
        id: "test1",
        date: "2026-03-20",
        symbol: "600519",
        name: "茅台",
        action: "buy",
        quantity: 100,
        price: 1800,
        commission: 45,
        amount: 180000,
        market: "A",
        notes: "测试"
      }
    ];
    writeFileSync(tradesPath, JSON.stringify(oldFormat, null, 2));

    // 加载应该自动迁移
    const service = new TradeService(testDir);
    const data = service.load();

    // 验证新格式
    expect(data.trades).toHaveLength(1);
    expect(data.trades[0].symbol).toBe("600519");
    expect(data.last_updated).toBeTruthy();
  });
});
