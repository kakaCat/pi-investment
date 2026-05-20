import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const getStockInfoViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getStockPriceViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getStockHistoryViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();
const getStockNewsViaQuantCliMock = jest.fn<(symbol: string, num?: number) => Promise<string>>();
const getAnnouncementsViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();

await jest.unstable_mockModule("../../quant/stock-query-cli-adapter.js", () => ({
  getStockInfoViaQuantCli: getStockInfoViaQuantCliMock,
  getStockPriceViaQuantCli: getStockPriceViaQuantCliMock,
  getStockHistoryViaQuantCli: getStockHistoryViaQuantCliMock,
  getStockNewsViaQuantCli: getStockNewsViaQuantCliMock,
  getAnnouncementsViaQuantCli: getAnnouncementsViaQuantCliMock,
}));

const {
  getStockInfoTool,
  getStockPriceTool,
  getStockHistoryTool,
  getStockNewsTool,
  getAnnouncementsTool,
} = await import("./stock-query-tools.js");

describe("stock query tools", () => {
  beforeEach(() => {
    getStockInfoViaQuantCliMock.mockReset();
    getStockPriceViaQuantCliMock.mockReset();
    getStockHistoryViaQuantCliMock.mockReset();
    getStockNewsViaQuantCliMock.mockReset();
    getAnnouncementsViaQuantCliMock.mockReset();
  });

  test("routes stock query tool execution through quant CLI adapter", async () => {
    getStockInfoViaQuantCliMock.mockResolvedValueOnce("{\"symbol\":\"600519\"}");
    getStockPriceViaQuantCliMock.mockResolvedValueOnce("{\"price\":100.5}");
    getStockHistoryViaQuantCliMock.mockResolvedValueOnce("{\"count\":30}");
    getStockNewsViaQuantCliMock.mockResolvedValueOnce("{\"count\":5}");
    getAnnouncementsViaQuantCliMock.mockResolvedValueOnce("{\"count\":1}");

    await (getStockInfoTool.execute as any)("call-1", { symbol: "600519" });
    await (getStockPriceTool.execute as any)("call-2", { symbol: "600519" });
    await (getStockHistoryTool.execute as any)("call-3", {
      symbol: "600519",
      period: "daily",
      start_date: "20260101",
      end_date: "20260520",
    });
    await (getStockNewsTool.execute as any)("call-4", { symbol: "600519", num: 5 });
    await (getAnnouncementsTool.execute as any)("call-5", { symbol: "600519" });

    expect(getStockInfoViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(getStockPriceViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(getStockHistoryViaQuantCliMock).toHaveBeenCalledWith({
      symbol: "600519",
      period: "daily",
      start_date: "20260101",
      end_date: "20260520",
    });
    expect(getStockNewsViaQuantCliMock).toHaveBeenCalledWith("600519", 5);
    expect(getAnnouncementsViaQuantCliMock).toHaveBeenCalledWith("600519");
  });

  test("rejects invalid symbols before invoking quant CLI", async () => {
    const result = await (getStockPriceTool.execute as any)("call-1", { symbol: "AAPL.US" });

    expect(getStockPriceViaQuantCliMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("不支持的股票代码");
  });
});
