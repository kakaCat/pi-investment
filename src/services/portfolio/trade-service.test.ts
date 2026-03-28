import { describe, expect, test } from "@jest/globals";
import { mkdtempSync } from "fs";
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
});
