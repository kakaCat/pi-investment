import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const runQuantCliMock = jest.fn<
  (domain: string, action: string, params?: Record<string, unknown>) => Promise<any>
>();

await jest.unstable_mockModule("./quant-cli-client.js", () => ({
  runQuantCli: runQuantCliMock,
}));

const {
  getBatchStockPricesViaQuantCli,
  getStockListViaQuantCli,
  getStockInfoViaQuantCli,
  getStockPriceViaQuantCli,
  getStockHistoryViaQuantCli,
  getStockNewsViaQuantCli,
  getAnnouncementsViaQuantCli,
} = await import("./stock-query-cli-adapter.js");

describe("stock-query-cli-adapter", () => {
  beforeEach(() => {
    runQuantCliMock.mockReset();
  });

  test("routes stock query helpers to quant stock CLI commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({ ok: true, command: "stock.info", data: { symbol: "600519" } })
      .mockResolvedValueOnce({ ok: true, command: "stock.quote", data: { price: 100.5 } })
      .mockResolvedValueOnce({ ok: true, command: "stock.history", data: { count: 30 } })
      .mockResolvedValueOnce({ ok: true, command: "stock.news", data: { count: 5 } })
      .mockResolvedValueOnce({ ok: true, command: "stock.announcements", data: { count: 1 } })
      .mockResolvedValueOnce({ ok: true, command: "stock.batch_quotes", data: { prices: { "600519": 100.5 } } })
      .mockResolvedValueOnce({ ok: true, command: "stock.list", data: { stocks: [{ code: "600519" }] } });

    expect(JSON.parse(await getStockInfoViaQuantCli("600519"))).toEqual({ symbol: "600519" });
    expect(JSON.parse(await getStockPriceViaQuantCli("600519"))).toEqual({ price: 100.5 });
    expect(JSON.parse(await getStockHistoryViaQuantCli({
      symbol: "600519",
      period: "daily",
      start_date: "20260101",
      end_date: "20260520",
    }))).toEqual({ count: 30 });
    expect(JSON.parse(await getStockNewsViaQuantCli("600519", 5))).toEqual({ count: 5 });
    expect(JSON.parse(await getAnnouncementsViaQuantCli("600519"))).toEqual({ count: 1 });
    expect(JSON.parse(await getBatchStockPricesViaQuantCli(["600519"]))).toEqual({ prices: { "600519": 100.5 } });
    expect(JSON.parse(await getStockListViaQuantCli("A"))).toEqual({ stocks: [{ code: "600519" }] });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "stock", "info", { symbol: "600519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "stock", "quote", { symbol: "600519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(3, "stock", "history", {
      symbol: "600519",
      period: "daily",
      start_date: "20260101",
      end_date: "20260520",
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(4, "stock", "news", {
      symbol: "600519",
      num: 5,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(5, "stock", "announcements", {
      symbol: "600519",
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(6, "stock", "batch-quotes", {
      symbols: ["600519"],
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(7, "stock", "list", {
      market: "A",
      source: "live",
    });
  });

  test("returns stable JSON error when CLI call fails", async () => {
    runQuantCliMock.mockRejectedValueOnce(new Error("QUANT_CLI_FAILED: offline"));

    const result = JSON.parse(await getStockPriceViaQuantCli("600519"));

    expect(result.error).toContain("QUANT_CLI_FAILED");
    expect(result.symbol).toBe("600519");
    expect(result._no_operation_performed).toBe(true);
  });
});
