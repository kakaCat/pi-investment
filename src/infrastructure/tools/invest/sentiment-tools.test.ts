import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const getStockFundFlowViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();
const getLhbViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();
const getInsiderTradesViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getFundHoldingsViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getTopFundStocksViaQuantCliMock = jest.fn<() => Promise<string>>();
const getTopHoldersViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getHolderChangesViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getMarginDataViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();

await jest.unstable_mockModule("../../quant/sentiment-query-cli-adapter.js", () => ({
  getStockFundFlowViaQuantCli: getStockFundFlowViaQuantCliMock,
  getLhbViaQuantCli: getLhbViaQuantCliMock,
  getInsiderTradesViaQuantCli: getInsiderTradesViaQuantCliMock,
  getFundHoldingsViaQuantCli: getFundHoldingsViaQuantCliMock,
  getTopFundStocksViaQuantCli: getTopFundStocksViaQuantCliMock,
  getTopHoldersViaQuantCli: getTopHoldersViaQuantCliMock,
  getHolderChangesViaQuantCli: getHolderChangesViaQuantCliMock,
  getMarginDataViaQuantCli: getMarginDataViaQuantCliMock,
}));

const {
  getStockFundFlowTool,
  getLhbTool,
  getInsiderTradesTool,
  getFundHoldingsTool,
  getTopFundStocksTool,
  getTopHoldersTool,
  getHolderChangesTool,
  getMarginDataTool,
} = await import("./sentiment-tools.js");

describe("sentiment tools", () => {
  beforeEach(() => {
    getStockFundFlowViaQuantCliMock.mockReset();
    getLhbViaQuantCliMock.mockReset();
    getInsiderTradesViaQuantCliMock.mockReset();
    getFundHoldingsViaQuantCliMock.mockReset();
    getTopFundStocksViaQuantCliMock.mockReset();
    getTopHoldersViaQuantCliMock.mockReset();
    getHolderChangesViaQuantCliMock.mockReset();
    getMarginDataViaQuantCliMock.mockReset();
  });

  test("routes sentiment tool execution through quant CLI adapter", async () => {
    getStockFundFlowViaQuantCliMock.mockResolvedValueOnce("{\"count\":5}");
    getLhbViaQuantCliMock.mockResolvedValueOnce("{\"count\":1}");
    getInsiderTradesViaQuantCliMock.mockResolvedValueOnce("{\"count\":2}");
    getFundHoldingsViaQuantCliMock.mockResolvedValueOnce("{\"count\":3}");
    getTopFundStocksViaQuantCliMock.mockResolvedValueOnce("{\"data\":[]}");
    getTopHoldersViaQuantCliMock.mockResolvedValueOnce("{\"count\":10}");
    getHolderChangesViaQuantCliMock.mockResolvedValueOnce("{\"count\":8}");
    getMarginDataViaQuantCliMock.mockResolvedValueOnce("{\"count\":10}");

    await (getStockFundFlowTool.execute as any)("call-1", { symbol: "600519", days: 5 });
    await (getLhbTool.execute as any)("call-2", { symbol: "600519", date: "20260519" });
    await (getInsiderTradesTool.execute as any)("call-3", { symbol: "600519" });
    await (getFundHoldingsTool.execute as any)("call-4", { symbol: "600519" });
    await (getTopFundStocksTool.execute as any)("call-5", {});
    await (getTopHoldersTool.execute as any)("call-6", { symbol: "600519" });
    await (getHolderChangesTool.execute as any)("call-7", { symbol: "600519" });
    await (getMarginDataTool.execute as any)("call-8", { symbol: "600519" });

    expect(getStockFundFlowViaQuantCliMock).toHaveBeenCalledWith({ symbol: "600519", days: 5 });
    expect(getLhbViaQuantCliMock).toHaveBeenCalledWith({ symbol: "600519", date: "20260519" });
    expect(getInsiderTradesViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(getFundHoldingsViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(getTopFundStocksViaQuantCliMock).toHaveBeenCalledWith();
    expect(getTopHoldersViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(getHolderChangesViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(getMarginDataViaQuantCliMock).toHaveBeenCalledWith("600519");
  });

  test("rejects invalid symbols before invoking quant CLI", async () => {
    const result = await (getStockFundFlowTool.execute as any)("call-1", {
      symbol: "AAPL.US",
    });

    expect(getStockFundFlowViaQuantCliMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("不支持的股票代码");
  });
});

