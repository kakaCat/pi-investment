import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const screenStocksBySectorViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();
const screenStocksQualityViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();

await jest.unstable_mockModule("../../quant/screening-query-cli-adapter.js", () => ({
  screenStocksBySectorViaQuantCli: screenStocksBySectorViaQuantCliMock,
  screenStocksQualityViaQuantCli: screenStocksQualityViaQuantCliMock,
}));

const {
  screenStocksTool,
  screenStocksQualityTool,
} = await import("./screening-tools.js");

describe("screening tools", () => {
  beforeEach(() => {
    screenStocksBySectorViaQuantCliMock.mockReset();
    screenStocksQualityViaQuantCliMock.mockReset();
  });

  test("routes screening tool execution through quant CLI adapter", async () => {
    screenStocksBySectorViaQuantCliMock.mockResolvedValueOnce("{\"count\":1}");
    screenStocksQualityViaQuantCliMock.mockResolvedValueOnce("{\"qualified\":1}");

    await (screenStocksTool.execute as any)("call-1", {
      sector: "白酒",
      min_roe: 15,
      max_pe: 30,
      limit: 8,
    });
    await (screenStocksQualityTool.execute as any)("call-2", {
      sector: "白酒",
      min_score: 65,
      max_pe: 30,
      limit: 5,
    });

    expect(screenStocksBySectorViaQuantCliMock).toHaveBeenCalledWith({
      sector: "白酒",
      min_roe: 15,
      max_pe: 30,
      limit: 8,
    });
    expect(screenStocksQualityViaQuantCliMock).toHaveBeenCalledWith({
      sector: "白酒",
      min_score: 65,
      max_pe: 30,
      limit: 5,
    });
  });
});
