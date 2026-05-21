import { describe, expect, jest, test, beforeEach } from "@jest/globals";
import { mkdtempSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

const getMarketOverviewViaQuantCliMock = jest.fn<() => Promise<string>>();
const getStockPriceViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const analyzeTechnicalViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();

await jest.unstable_mockModule("../../infrastructure/quant/market-query-cli-adapter.js", () => ({
  getMarketOverviewViaQuantCli: getMarketOverviewViaQuantCliMock,
}));

await jest.unstable_mockModule("../../infrastructure/quant/stock-query-cli-adapter.js", () => ({
  getStockPriceViaQuantCli: getStockPriceViaQuantCliMock,
}));

await jest.unstable_mockModule("../../infrastructure/quant/analysis-query-cli-adapter.js", () => ({
  analyzeTechnicalViaQuantCli: analyzeTechnicalViaQuantCliMock,
}));

const {
  DailyReviewService,
  formatMarketOverviewSection,
  formatReviewNewsSection,
} = await import("./daily-review-service.js");

describe("DailyReviewService helpers", () => {
  test("formats market overview from object-shaped indices", () => {
    const result = formatMarketOverviewSection({
      indices: {
        上证指数: { price: 3200.12, change_pct: 1.23 },
        深证成指: { price: 10100.55, change_pct: -0.45 },
      },
    });

    expect(result).toContain("上证指数：3200.12 （+1.23%）");
    expect(result).toContain("深证成指：10100.55 （-0.45%）");
  });

  test("formats news from data field", () => {
    const result = formatReviewNewsSection({
      data: [
        { title: "公告一", date: "2026-03-21 09:00:00" },
        { title: "公告二", date: "2026-03-21 10:00:00" },
      ],
    });

    expect(result).toContain("公告一");
    expect(result).toContain("公告二");
  });
});

describe("DailyReviewService", () => {
  beforeEach(() => {
    getMarketOverviewViaQuantCliMock.mockReset();
    getStockPriceViaQuantCliMock.mockReset();
    analyzeTechnicalViaQuantCliMock.mockReset();
  });

  test("runs review with market, price, and technical data from quant CLI", async () => {
    const testDir = mkdtempSync(join(tmpdir(), "pi-review-test-"));
    writeFileSync(join(testDir, "portfolio.json"), JSON.stringify({
      holdings: [{ symbol: "600519", name: "贵州茅台", quantity: 100, avg_cost: 100, market: "A" }],
      last_updated: "2026-05-20 15:30:00",
    }, null, 2));
    getMarketOverviewViaQuantCliMock.mockResolvedValue(JSON.stringify({
      indices: { 上证指数: { price: 3200, change_pct: 1.2 } },
    }));
    getStockPriceViaQuantCliMock.mockResolvedValue(JSON.stringify({
      price: 110,
      change_pct: 2,
    }));
    analyzeTechnicalViaQuantCliMock.mockResolvedValue(JSON.stringify({
      ma20: 100,
      ma60: 90,
      rsi: 55,
      macd_histogram: 0.1,
    }));

    const report = await new DailyReviewService(testDir).run();

    expect(getMarketOverviewViaQuantCliMock).toHaveBeenCalled();
    expect(getStockPriceViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(analyzeTechnicalViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(report).toContain("贵州茅台");
    expect(report).toContain("上证指数");
  });
});
