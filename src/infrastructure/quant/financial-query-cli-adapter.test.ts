import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const runQuantCliMock = jest.fn<
  (domain: string, action: string, params?: Record<string, unknown>) => Promise<any>
>();

await jest.unstable_mockModule("./quant-cli-client.js", () => ({
  runQuantCli: runQuantCliMock,
}));

const {
  getFinancialIndicatorsViaQuantCli,
  getFinancialStatementsViaQuantCli,
  getHkFinancialsViaQuantCli,
  getHkAnalysisViaQuantCli,
} = await import("./financial-query-cli-adapter.js");

describe("financial-query-cli-adapter", () => {
  beforeEach(() => {
    runQuantCliMock.mockReset();
  });

  test("routes financial helpers to quant financial CLI commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({ ok: true, command: "financial.indicators", data: { quarters: [] } })
      .mockResolvedValueOnce({ ok: true, command: "financial.statements", data: { income_statement: {} } })
      .mockResolvedValueOnce({ ok: true, command: "financial.hk_financials", data: { market: "HK" } })
      .mockResolvedValueOnce({ ok: true, command: "financial.hk_analysis", data: { market: "HK" } });

    expect(JSON.parse(await getFinancialIndicatorsViaQuantCli("600519"))).toEqual({ quarters: [] });
    expect(JSON.parse(await getFinancialStatementsViaQuantCli({
      symbol: "600519",
      statement: "income",
      recent_n: 4,
    }))).toEqual({ income_statement: {} });
    expect(JSON.parse(await getHkFinancialsViaQuantCli("9988"))).toEqual({ market: "HK" });
    expect(JSON.parse(await getHkAnalysisViaQuantCli("9988"))).toEqual({ market: "HK" });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "financial", "indicators", { symbol: "600519" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "financial", "statements", {
      symbol: "600519",
      statement: "income",
      recent_n: 4,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(3, "financial", "hk-financials", { symbol: "9988" });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(4, "financial", "hk-analysis", { symbol: "9988" });
  });

  test("returns stable JSON error when CLI call fails", async () => {
    runQuantCliMock.mockRejectedValueOnce(new Error("QUANT_CLI_FAILED: offline"));

    const result = JSON.parse(await getFinancialIndicatorsViaQuantCli("600519"));

    expect(result.error).toContain("QUANT_CLI_FAILED");
    expect(result.symbol).toBe("600519");
    expect(result._source).toBe("quant_cli");
    expect(result._no_operation_performed).toBe(true);
  });
});

