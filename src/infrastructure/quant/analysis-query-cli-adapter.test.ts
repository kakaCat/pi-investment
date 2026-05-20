import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const runQuantCliMock = jest.fn<
  (domain: string, action: string, params?: Record<string, unknown>) => Promise<any>
>();

await jest.unstable_mockModule("./quant-cli-client.js", () => ({
  runQuantCli: runQuantCliMock,
}));

const {
  analyzeTechnicalViaQuantCli,
  analyzePriceActionViaQuantCli,
  analyzeCandlestickViaQuantCli,
  getBuyRangeViaQuantCli,
  getValuationViaQuantCli,
  getPePercentileViaQuantCli,
  getQualityScoreViaQuantCli,
  getExitPlanViaQuantCli,
  comparePeersViaQuantCli,
} = await import("./analysis-query-cli-adapter.js");

describe("analysis-query-cli-adapter", () => {
  beforeEach(() => {
    runQuantCliMock.mockReset();
  });

  test("routes analysis helpers to quant analysis CLI commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({ ok: true, command: "analysis.technical", data: { signals: [] } })
      .mockResolvedValueOnce({ ok: true, command: "analysis.price_action", data: { trend: {} } })
      .mockResolvedValueOnce({ ok: true, command: "analysis.candlestick", data: { patterns: [] } })
      .mockResolvedValueOnce({ ok: true, command: "analysis.buy_range", data: { ideal_buy: 98 } })
      .mockResolvedValueOnce({ ok: true, command: "analysis.valuation", data: { pe: 22 } })
      .mockResolvedValueOnce({ ok: true, command: "analysis.pe_percentile", data: { pe_percentile: 45 } })
      .mockResolvedValueOnce({ ok: true, command: "analysis.quality", data: { score: 80 } })
      .mockResolvedValueOnce({ ok: true, command: "analysis.exit_plan", data: { shares: 200 } })
      .mockResolvedValueOnce({ ok: true, command: "analysis.peers", data: { sector: "白酒" } });

    expect(JSON.parse(await analyzeTechnicalViaQuantCli("600519"))).toEqual({ signals: [] });
    expect(JSON.parse(await analyzePriceActionViaQuantCli("600519", 80))).toEqual({ trend: {} });
    expect(JSON.parse(await analyzeCandlestickViaQuantCli("600519"))).toEqual({ patterns: [] });
    expect(JSON.parse(await getBuyRangeViaQuantCli("600519", 100.5))).toEqual({ ideal_buy: 98 });
    expect(JSON.parse(await getValuationViaQuantCli("600519"))).toEqual({ pe: 22 });
    expect(JSON.parse(await getPePercentileViaQuantCli("600519", 3))).toEqual({ pe_percentile: 45 });
    expect(JSON.parse(await getQualityScoreViaQuantCli("600519"))).toEqual({ score: 80 });
    expect(JSON.parse(await getExitPlanViaQuantCli("600519", 90, 200))).toEqual({ shares: 200 });
    expect(JSON.parse(await comparePeersViaQuantCli("600519"))).toEqual({ sector: "白酒" });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "analysis", "technical", { symbol: "600519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "analysis", "price-action", {
      symbol: "600519",
      period: 80,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(3, "analysis", "candlestick", { symbol: "600519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(4, "analysis", "buy-range", {
      symbol: "600519",
      current_price: 100.5,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(5, "analysis", "valuation", { symbol: "600519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(6, "analysis", "pe-percentile", {
      symbol: "600519",
      years: 3,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(7, "analysis", "quality", { symbol: "600519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(8, "analysis", "exit-plan", {
      symbol: "600519",
      buy_price: 90,
      shares: 200,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(9, "analysis", "peers", { symbol: "600519" });
  });

  test("returns stable JSON error when CLI call fails", async () => {
    runQuantCliMock.mockRejectedValueOnce(new Error("QUANT_CLI_FAILED: offline"));

    const result = JSON.parse(await analyzeTechnicalViaQuantCli("600519"));

    expect(result.error).toContain("QUANT_CLI_FAILED");
    expect(result.symbol).toBe("600519");
    expect(result._source).toBe("quant_cli");
    expect(result._no_operation_performed).toBe(true);
  });
});
