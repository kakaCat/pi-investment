import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const cacheManagerMock = {
  get: jest.fn<() => Promise<any>>(async () => null),
  set: jest.fn<() => Promise<void>>(async () => undefined),
  invalidateByPattern: jest.fn<() => Promise<number>>(async () => 0),
};
const getStockHistoryViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();

await jest.unstable_mockModule("../../domain/cache/core/cache-manager.js", () => ({
  CacheManager: {
    getInstance: () => cacheManagerMock,
  },
}));

await jest.unstable_mockModule("../../infrastructure/quant/stock-query-cli-adapter.js", () => ({
  getStockHistoryViaQuantCli: getStockHistoryViaQuantCliMock,
}));

const { KlineCacheAdapter } = await import("./kline-cache-adapter.js");

describe("KlineCacheAdapter", () => {
  beforeEach(() => {
    cacheManagerMock.get.mockReset().mockResolvedValue(null);
    cacheManagerMock.set.mockReset().mockResolvedValue(undefined);
    cacheManagerMock.invalidateByPattern.mockReset().mockResolvedValue(0);
    getStockHistoryViaQuantCliMock.mockReset();
  });

  test("fetches missing history through quant CLI", async () => {
    const db = {
      getKlines: jest.fn(() => []),
      saveKlines: jest.fn(() => 1),
      getLatestKlineDate: jest.fn(() => null),
    };
    getStockHistoryViaQuantCliMock.mockResolvedValueOnce(JSON.stringify({
      data: [{ date: "2026-05-19", close: 10 }],
    }));

    const result = await new KlineCacheAdapter(db as any).getHistory(
      "600519",
      "2026-05-01",
      "2026-05-20",
    );

    expect(getStockHistoryViaQuantCliMock).toHaveBeenCalledWith({
      symbol: "600519",
      period: "daily",
      start_date: "2026-05-01",
      end_date: "2026-05-20",
    });
    expect(result).toEqual([{ date: "2026-05-19", close: 10 }]);
    expect(db.saveKlines).toHaveBeenCalledWith("600519", [{ date: "2026-05-19", close: 10 }]);
  });

  test("updates missing symbol range through quant CLI", async () => {
    const db = {
      getKlines: jest.fn(() => []),
      saveKlines: jest.fn(() => 1),
      getLatestKlineDate: jest.fn(() => "2000-01-01"),
    };
    getStockHistoryViaQuantCliMock.mockResolvedValueOnce(JSON.stringify({
      data: [{ date: "2026-05-20", close: 10 }],
    }));

    const count = await new KlineCacheAdapter(db as any).updateSymbol("600519");

    expect(getStockHistoryViaQuantCliMock).toHaveBeenCalledWith(expect.objectContaining({
      symbol: "600519",
      period: "daily",
      start_date: "2000-01-02",
    }));
    expect(count).toBe(1);
    expect(cacheManagerMock.invalidateByPattern).toHaveBeenCalledWith("daily", "kline:600519:*");
  });
});
