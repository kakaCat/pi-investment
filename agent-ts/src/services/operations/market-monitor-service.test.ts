import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const getStockPriceViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getSessionMock = jest.fn<() => Promise<{ prompt: (context: string) => Promise<void> }>>();
const getWithPnLMock = jest.fn<() => Promise<{ holdings: any[] }>>();

await jest.unstable_mockModule("../../infrastructure/quant/stock-query-cli-adapter.js", () => ({
  getAnnouncementsViaQuantCli: jest.fn(),
  getBatchStockPricesViaQuantCli: jest.fn(),
  getStockPriceViaQuantCli: getStockPriceViaQuantCliMock,
  getStockNewsViaQuantCli: jest.fn(),
  getStockHistoryViaQuantCli: jest.fn(),
  getStockInfoViaQuantCli: jest.fn(),
  getStockListViaQuantCli: jest.fn(),
}));

await jest.unstable_mockModule("../../core/agent/agent-loop.js", () => ({
  getSession: getSessionMock,
}));

await jest.unstable_mockModule("../portfolio/portfolio-service.js", () => ({
  PortfolioService: jest.fn().mockImplementation(() => ({
    getWithPnL: getWithPnLMock,
  })),
}));

const { AlertDeduper, MarketMonitorService, isWithinTradingHours } = await import("./market-monitor-service.js");

describe("market monitor guards", () => {
  test("allows trading time in weekday 09:30-15:00 Asia/Shanghai", () => {
    expect(isWithinTradingHours(new Date("2026-03-31T01:30:00.000Z"))).toBe(true); // 09:30 CST
    expect(isWithinTradingHours(new Date("2026-03-31T07:00:00.000Z"))).toBe(true); // 15:00 CST
  });

  test("blocks time outside trading window or weekend", () => {
    expect(isWithinTradingHours(new Date("2026-03-31T01:29:00.000Z"))).toBe(false); // 09:29 CST
    expect(isWithinTradingHours(new Date("2026-03-31T07:01:00.000Z"))).toBe(false); // 15:01 CST
    expect(isWithinTradingHours(new Date("2026-04-04T02:00:00.000Z"))).toBe(false); // Saturday
  });
});

describe("AlertDeduper", () => {
  test("deduplicates same symbol within 30 minutes", () => {
    const deduper = new AlertDeduper();
    const t0 = 1000;
    const t20m = t0 + 20 * 60 * 1000;
    const t31m = t0 + 31 * 60 * 1000;

    expect(deduper.shouldNotify("600519", t0)).toBe(true);
    deduper.markSent("600519", t0);

    expect(deduper.shouldNotify("600519", t20m)).toBe(false);
    expect(deduper.shouldNotify("600519", t31m)).toBe(true);
  });
});

describe("MarketMonitorService", () => {
  beforeEach(() => {
    getStockPriceViaQuantCliMock.mockReset();
    getSessionMock.mockReset();
    getWithPnLMock.mockReset();
  });

  test("fetches holding quotes through quant CLI before agent analysis", async () => {
    const prompt = jest.fn<() => Promise<void>>().mockResolvedValue(undefined);
    getSessionMock.mockResolvedValue({ prompt });
    getWithPnLMock.mockResolvedValue({
      holdings: [{ symbol: "600519", name: "贵州茅台", quantity: 100, cost: 100 }],
    });
    getStockPriceViaQuantCliMock.mockResolvedValue(JSON.stringify({
      name: "贵州茅台",
      price: 100,
      change_pct: 4,
      volume: 1000,
    }));

    await new MarketMonitorService().tick();

    expect(getStockPriceViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(prompt).toHaveBeenCalledWith(expect.stringContaining("贵州茅台"));
  });
});
