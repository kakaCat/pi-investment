import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const runQuantCliMock = jest.fn<
  (domain: string, action: string, params?: Record<string, unknown>) => Promise<any>
>();

await jest.unstable_mockModule("./quant-cli-client.js", () => ({
  runQuantCli: runQuantCliMock,
}));

const {
  getMarketOverviewViaQuantCli,
  getSectorListViaQuantCli,
  getConceptStocksViaQuantCli,
  getConceptListViaQuantCli,
  getMacroDataViaQuantCli,
  getNorthFlowViaQuantCli,
  getSectorFundFlowViaQuantCli,
  getMarketMarginViaQuantCli,
  getMarketNewsViaQuantCli,
  getHotStocksViaQuantCli,
} = await import("./market-query-cli-adapter.js");

describe("market-query-cli-adapter", () => {
  beforeEach(() => {
    runQuantCliMock.mockReset();
  });

  test("routes market helpers to quant market CLI commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({ ok: true, command: "market.overview", data: { indices: {} } })
      .mockResolvedValueOnce({ ok: true, command: "market.sectors", data: { count: 1 } })
      .mockResolvedValueOnce({ ok: true, command: "market.concept_stocks", data: { concept: "人工智能" } })
      .mockResolvedValueOnce({ ok: true, command: "market.concepts", data: { count: 2 } })
      .mockResolvedValueOnce({ ok: true, command: "market.macro", data: { pmi: [] } })
      .mockResolvedValueOnce({ ok: true, command: "market.north_flow", data: { data: [] } })
      .mockResolvedValueOnce({ ok: true, command: "market.sector_flow", data: { count: 3 } })
      .mockResolvedValueOnce({ ok: true, command: "market.margin", data: { count: 4 } })
      .mockResolvedValueOnce({ ok: true, command: "market.news", data: { sources: [] } })
      .mockResolvedValueOnce({ ok: true, command: "market.hot_stocks", data: { market: "港股" } });

    expect(JSON.parse(await getMarketOverviewViaQuantCli())).toEqual({ indices: {} });
    expect(JSON.parse(await getSectorListViaQuantCli())).toEqual({ count: 1 });
    expect(JSON.parse(await getConceptStocksViaQuantCli("人工智能"))).toEqual({ concept: "人工智能" });
    expect(JSON.parse(await getConceptListViaQuantCli())).toEqual({ count: 2 });
    expect(JSON.parse(await getMacroDataViaQuantCli(["pmi", "cpi"]))).toEqual({ pmi: [] });
    expect(JSON.parse(await getNorthFlowViaQuantCli())).toEqual({ data: [] });
    expect(JSON.parse(await getSectorFundFlowViaQuantCli())).toEqual({ count: 3 });
    expect(JSON.parse(await getMarketMarginViaQuantCli())).toEqual({ count: 4 });
    expect(JSON.parse(await getMarketNewsViaQuantCli(9))).toEqual({ sources: [] });
    expect(JSON.parse(await getHotStocksViaQuantCli("港股"))).toEqual({ market: "港股" });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "market", "overview", {});
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "market", "sectors", {});
    expect(runQuantCliMock).toHaveBeenNthCalledWith(3, "market", "concept-stocks", { concept: "人工智能" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(4, "market", "concepts", {});
    expect(runQuantCliMock).toHaveBeenNthCalledWith(5, "market", "macro", { indicators: ["pmi", "cpi"] });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(6, "market", "north-flow", {});
    expect(runQuantCliMock).toHaveBeenNthCalledWith(7, "market", "sector-flow", {});
    expect(runQuantCliMock).toHaveBeenNthCalledWith(8, "market", "margin", {});
    expect(runQuantCliMock).toHaveBeenNthCalledWith(9, "market", "news", { num: 9 });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(10, "market", "hot-stocks", { market: "港股" });
  });

  test("returns stable JSON error when CLI call fails", async () => {
    runQuantCliMock.mockRejectedValueOnce(new Error("QUANT_CLI_FAILED: offline"));

    const result = JSON.parse(await getMarketOverviewViaQuantCli());

    expect(result.error).toContain("QUANT_CLI_FAILED");
    expect(result._source).toBe("quant_cli");
    expect(result._no_operation_performed).toBe(true);
  });
});
