import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const runQuantCliMock = jest.fn<
  (domain: string, action: string, params?: Record<string, unknown>) => Promise<any>
>();

await jest.unstable_mockModule("./quant-cli-client.js", () => ({
  runQuantCli: runQuantCliMock,
}));

const {
  getHkMarketOverviewViaQuantCli,
  getHkSouthFlowViaQuantCli,
  getHkTechnicalViaQuantCli,
  getHkHotRankViaQuantCli,
} = await import("./hk-query-cli-adapter.js");

describe("hk-query-cli-adapter", () => {
  beforeEach(() => {
    runQuantCliMock.mockReset();
  });

  test("routes HK helpers to quant hk CLI commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({ ok: true, command: "hk.market_overview", data: { indices: [] } })
      .mockResolvedValueOnce({ ok: true, command: "hk.south_flow", data: { data: [] } })
      .mockResolvedValueOnce({ ok: true, command: "hk.technical", data: { symbol: "09988" } })
      .mockResolvedValueOnce({ ok: true, command: "hk.hot_rank", data: { stocks: [] } });

    expect(JSON.parse(await getHkMarketOverviewViaQuantCli())).toEqual({ indices: [] });
    expect(JSON.parse(await getHkSouthFlowViaQuantCli())).toEqual({ data: [] });
    expect(JSON.parse(await getHkTechnicalViaQuantCli("9988"))).toEqual({ symbol: "09988" });
    expect(JSON.parse(await getHkHotRankViaQuantCli())).toEqual({ stocks: [] });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "hk", "market-overview", {});
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "hk", "south-flow", {});
    expect(runQuantCliMock).toHaveBeenNthCalledWith(3, "hk", "technical", { symbol: "9988" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(4, "hk", "hot-rank", {});
  });

  test("returns stable JSON error when CLI call fails", async () => {
    runQuantCliMock.mockRejectedValueOnce(new Error("QUANT_CLI_FAILED: offline"));

    const result = JSON.parse(await getHkTechnicalViaQuantCli("9988"));

    expect(result.error).toContain("QUANT_CLI_FAILED");
    expect(result.symbol).toBe("9988");
    expect(result._source).toBe("quant_cli");
    expect(result._no_operation_performed).toBe(true);
  });
});

