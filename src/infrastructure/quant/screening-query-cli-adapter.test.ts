import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const runQuantCliMock = jest.fn<
  (domain: string, action: string, params?: Record<string, unknown>) => Promise<any>
>();

await jest.unstable_mockModule("./quant-cli-client.js", () => ({
  runQuantCli: runQuantCliMock,
}));

const {
  screenStocksBySectorViaQuantCli,
  screenStocksQualityViaQuantCli,
} = await import("./screening-query-cli-adapter.js");

describe("screening-query-cli-adapter", () => {
  beforeEach(() => {
    runQuantCliMock.mockReset();
  });

  test("routes screening helpers to quant screening CLI commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({ ok: true, command: "screening.sector", data: { count: 1 } })
      .mockResolvedValueOnce({ ok: true, command: "screening.quality", data: { qualified: 1 } });

    expect(JSON.parse(await screenStocksBySectorViaQuantCli({
      sector: "白酒",
      min_roe: 15,
      max_pe: 30,
      limit: 8,
    }))).toEqual({ count: 1 });
    expect(JSON.parse(await screenStocksQualityViaQuantCli({
      sector: "白酒",
      min_score: 65,
      max_pe: 30,
      limit: 5,
    }))).toEqual({ qualified: 1 });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "screening", "sector", {
      sector: "白酒",
      min_roe: 15,
      max_pe: 30,
      limit: 8,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "screening", "quality", {
      sector: "白酒",
      min_score: 65,
      max_pe: 30,
      limit: 5,
    });
  });

  test("returns stable JSON error when CLI call fails", async () => {
    runQuantCliMock.mockRejectedValueOnce(new Error("QUANT_CLI_FAILED: offline"));

    const result = JSON.parse(await screenStocksBySectorViaQuantCli({ sector: "白酒" }));

    expect(result.error).toContain("QUANT_CLI_FAILED");
    expect(result.sector).toBe("白酒");
    expect(result._source).toBe("quant_cli");
    expect(result._no_operation_performed).toBe(true);
  });
});
