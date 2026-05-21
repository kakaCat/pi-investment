import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const runQuantCliMock = jest.fn<
  (domain: string, action: string, params?: Record<string, unknown>) => Promise<any>
>();

await jest.unstable_mockModule("./quant-cli-client.js", () => ({
  runQuantCli: runQuantCliMock,
}));

const {
  checkTradeRiskViaQuantCli,
  calculatePositionSizeViaQuantCli,
  calculateStopLossViaQuantCli,
} = await import("./risk-query-cli-adapter.js");

describe("risk-query-cli-adapter", () => {
  beforeEach(() => {
    runQuantCliMock.mockReset();
  });

  test("routes risk helpers to quant risk CLI commands", async () => {
    runQuantCliMock
      .mockResolvedValueOnce({ ok: true, command: "risk.trade_check", data: { passed: true } })
      .mockResolvedValueOnce({ ok: true, command: "risk.position_size", data: { shares: 200 } })
      .mockResolvedValueOnce({ ok: true, command: "risk.stop_loss", data: { stop_loss_price: 99 } });

    expect(JSON.parse(await checkTradeRiskViaQuantCli({
      symbol: "600519",
      action: "buy",
      price: 100.5,
      shares: 300,
    }))).toEqual({ passed: true });
    expect(JSON.parse(await calculatePositionSizeViaQuantCli({
      symbol: "600519",
      price: 100.5,
      signal_strength: 0.8,
    }))).toEqual({ shares: 200 });
    expect(JSON.parse(await calculateStopLossViaQuantCli({
      symbol: "600519",
      entry_price: 90,
      current_price: 100,
      highest_price: 110,
    }))).toEqual({ stop_loss_price: 99 });

    expect(runQuantCliMock).toHaveBeenNthCalledWith(1, "risk", "trade-check", {
      symbol: "600519",
      action: "buy",
      price: 100.5,
      shares: 300,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(2, "risk", "position-size", {
      symbol: "600519",
      price: 100.5,
      signal_strength: 0.8,
    });
    expect(runQuantCliMock).toHaveBeenNthCalledWith(3, "risk", "stop-loss", {
      symbol: "600519",
      entry_price: 90,
      current_price: 100,
      highest_price: 110,
    });
  });

  test("returns stable JSON error when CLI call fails", async () => {
    runQuantCliMock.mockRejectedValueOnce(new Error("QUANT_CLI_FAILED: offline"));

    const result = JSON.parse(await checkTradeRiskViaQuantCli({
      symbol: "600519",
      action: "buy",
      price: 100,
      shares: 100,
    }));

    expect(result.error).toContain("QUANT_CLI_FAILED");
    expect(result.symbol).toBe("600519");
    expect(result._source).toBe("quant_cli");
    expect(result._no_operation_performed).toBe(true);
  });
});
