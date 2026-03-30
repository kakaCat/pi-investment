import { describe, expect, test } from "@jest/globals";
import { quickFilter, type MonitorQuote } from "./market-filter.js";

describe("quickFilter", () => {
  test("detects high volatility from common quote fields", () => {
    const quotes: MonitorQuote[] = [
      { symbol: "600519", name: "茅台", change_pct: 4.2, price: 1600 },
      { symbol: "300750", name: "宁德", pct_chg: 1.2, current_price: 220 },
    ];

    const result = quickFilter(quotes, { holdings: [] });

    expect(result.needsAgentAnalysis).toBe(true);
    expect(result.urgency).toBeGreaterThanOrEqual(2);
    expect(result.signals.high_volatility.map((q) => q.symbol)).toContain("600519");
    expect(result.signals.high_volatility.map((q) => q.symbol)).not.toContain("300750");
  });

  test("detects near support and breakout with fallback keys", () => {
    const quotes: MonitorQuote[] = [
      { symbol: "000001", price: 10.1, support: 10 },
      { symbol: "000002", current: 10.6, resistance: 10.5 },
    ];

    const result = quickFilter(quotes, { holdings: [] });

    expect(result.signals.near_support.map((q) => q.symbol)).toContain("000001");
    expect(result.signals.breakout.map((q) => q.symbol)).toContain("000002");
  });

  test("returns calm status when no signals", () => {
    const quotes: MonitorQuote[] = [
      { symbol: "600000", change_pct: 0.2, price: 10.0, support: 8.0, resistance: 12.0 },
    ];

    const result = quickFilter(quotes, { holdings: [] });

    expect(result.needsAgentAnalysis).toBe(false);
    expect(result.urgency).toBe(0);
    expect(result.candidates).toHaveLength(0);
  });
});
