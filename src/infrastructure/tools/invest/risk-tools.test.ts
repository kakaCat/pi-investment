import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const checkTradeRiskViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();
const calculatePositionSizeViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();
const calculateStopLossViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();

await jest.unstable_mockModule("../../quant/risk-query-cli-adapter.js", () => ({
  checkTradeRiskViaQuantCli: checkTradeRiskViaQuantCliMock,
  calculatePositionSizeViaQuantCli: calculatePositionSizeViaQuantCliMock,
  calculateStopLossViaQuantCli: calculateStopLossViaQuantCliMock,
}));

const {
  checkTradeRiskTool,
  calculatePositionSizeTool,
  calculateStopLossTool,
} = await import("./risk-tools.js");

describe("risk tools", () => {
  beforeEach(() => {
    checkTradeRiskViaQuantCliMock.mockReset();
    calculatePositionSizeViaQuantCliMock.mockReset();
    calculateStopLossViaQuantCliMock.mockReset();
  });

  test("routes risk tool execution through quant CLI adapter", async () => {
    checkTradeRiskViaQuantCliMock.mockResolvedValueOnce("{\"passed\":true}");
    calculatePositionSizeViaQuantCliMock.mockResolvedValueOnce("{\"shares\":200}");
    calculateStopLossViaQuantCliMock.mockResolvedValueOnce("{\"stop_loss_price\":99}");

    await (checkTradeRiskTool.execute as any)("call-1", {
      symbol: "600519",
      action: "buy",
      price: 100.5,
      shares: 300,
    });
    await (calculatePositionSizeTool.execute as any)("call-2", {
      symbol: "600519",
      price: 100.5,
      signal_strength: 0.8,
    });
    await (calculateStopLossTool.execute as any)("call-3", {
      symbol: "600519",
      entry_price: 90,
      current_price: 100,
      highest_price: 110,
    });

    expect(checkTradeRiskViaQuantCliMock).toHaveBeenCalledWith({
      symbol: "600519",
      action: "buy",
      price: 100.5,
      shares: 300,
    });
    expect(calculatePositionSizeViaQuantCliMock).toHaveBeenCalledWith({
      symbol: "600519",
      price: 100.5,
      signal_strength: 0.8,
    });
    expect(calculateStopLossViaQuantCliMock).toHaveBeenCalledWith({
      symbol: "600519",
      entry_price: 90,
      current_price: 100,
      highest_price: 110,
    });
  });

  test("rejects invalid symbols before invoking quant CLI", async () => {
    const result = await (checkTradeRiskTool.execute as any)("call-1", {
      symbol: "AAPL.US",
      action: "buy",
      price: 100,
      shares: 100,
    });

    expect(checkTradeRiskViaQuantCliMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("不支持的股票代码");
  });
});
