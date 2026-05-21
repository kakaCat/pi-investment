import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const runQuantCliMock = jest.fn<
  (domain: string, action: string, params?: Record<string, unknown>) => Promise<any>
>();

await jest.unstable_mockModule("./quant-cli-client.js", () => ({
  runQuantCli: runQuantCliMock,
}));

const {
  getStockFundFlowViaQuantCli,
  getLhbViaQuantCli,
  getInsiderTradesViaQuantCli,
  getFundHoldingsViaQuantCli,
  getTopFundStocksViaQuantCli,
  getTopHoldersViaQuantCli,
  getHolderChangesViaQuantCli,
  getMarginDataViaQuantCli,
} = await import("./sentiment-query-cli-adapter.js");

describe("sentiment-query-cli-adapter", () => {
  beforeEach(() => {
    runQuantCliMock.mockReset();
  });

  test("routes sentiment helpers to quant sentiment CLI commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({ ok: true, command: "sentiment.stock_fund_flow", data: { count: 5 } })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.lhb", data: { count: 1 } })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.insider_trades", data: { count: 2 } })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.fund_holdings", data: { count: 3 } })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.top_fund_stocks", data: { data: [] } })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.top_holders", data: { count: 10 } })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.holder_changes", data: { count: 8 } })
      .mockResolvedValueOnce({ ok: true, command: "sentiment.margin_data", data: { count: 10 } });

    expect(JSON.parse(await getStockFundFlowViaQuantCli({ symbol: "600519", days: 5 }))).toEqual({ count: 5 });
    expect(JSON.parse(await getLhbViaQuantCli({ symbol: "600519", date: "20260519" }))).toEqual({ count: 1 });
    expect(JSON.parse(await getInsiderTradesViaQuantCli("600519"))).toEqual({ count: 2 });
    expect(JSON.parse(await getFundHoldingsViaQuantCli("600519"))).toEqual({ count: 3 });
    expect(JSON.parse(await getTopFundStocksViaQuantCli())).toEqual({ data: [] });
    expect(JSON.parse(await getTopHoldersViaQuantCli("600519"))).toEqual({ count: 10 });
    expect(JSON.parse(await getHolderChangesViaQuantCli("600519"))).toEqual({ count: 8 });
    expect(JSON.parse(await getMarginDataViaQuantCli("600519"))).toEqual({ count: 10 });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "sentiment", "stock-fund-flow", { symbol: "600519", days: 5 });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "sentiment", "lhb", { symbol: "600519", date: "20260519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(3, "sentiment", "insider-trades", { symbol: "600519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(4, "sentiment", "fund-holdings", { symbol: "600519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(5, "sentiment", "top-fund-stocks", {});
    expect(runQuantCliMock).toHaveBeenNthCalledWith(6, "sentiment", "top-holders", { symbol: "600519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(7, "sentiment", "holder-changes", { symbol: "600519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(8, "sentiment", "margin-data", { symbol: "600519" });
  });

  test("returns stable JSON error when CLI call fails", async () => {
    runQuantCliMock.mockRejectedValueOnce(new Error("QUANT_CLI_FAILED: offline"));

    const result = JSON.parse(await getStockFundFlowViaQuantCli({ symbol: "600519" }));

    expect(result.error).toContain("QUANT_CLI_FAILED");
    expect(result.symbol).toBe("600519");
    expect(result._source).toBe("quant_cli");
    expect(result._no_operation_performed).toBe(true);
  });
});

