import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const analyzeTechnicalViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const analyzePriceActionViaQuantCliMock = jest.fn<(symbol: string, period?: number) => Promise<string>>();
const analyzeCandlestickViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getBuyRangeViaQuantCliMock = jest.fn<(symbol: string, currentPrice?: number) => Promise<string>>();
const getValuationViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getPePercentileViaQuantCliMock = jest.fn<(symbol: string, years?: number) => Promise<string>>();
const getQualityScoreViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getExitPlanViaQuantCliMock = jest.fn<(symbol: string, buyPrice: number, shares?: number) => Promise<string>>();
const comparePeersViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();

await jest.unstable_mockModule("../../quant/analysis-query-cli-adapter.js", () => ({
  analyzeTechnicalViaQuantCli: analyzeTechnicalViaQuantCliMock,
  analyzePriceActionViaQuantCli: analyzePriceActionViaQuantCliMock,
  analyzeCandlestickViaQuantCli: analyzeCandlestickViaQuantCliMock,
  getBuyRangeViaQuantCli: getBuyRangeViaQuantCliMock,
  getValuationViaQuantCli: getValuationViaQuantCliMock,
  getPePercentileViaQuantCli: getPePercentileViaQuantCliMock,
  getQualityScoreViaQuantCli: getQualityScoreViaQuantCliMock,
  getExitPlanViaQuantCli: getExitPlanViaQuantCliMock,
  comparePeersViaQuantCli: comparePeersViaQuantCliMock,
}));

const {
  analyzeTechnicalTool,
  analyzePriceActionTool,
  analyzeCandlestickTool,
  getBuyRangeTool,
  getValuationTool,
  getPePercentileTool,
  getQualityScoreTool,
  getExitPlanTool,
  comparePeersTool,
} = await import("./analysis-tools.js");

describe("analysis tools", () => {
  beforeEach(() => {
    analyzeTechnicalViaQuantCliMock.mockReset();
    analyzePriceActionViaQuantCliMock.mockReset();
    analyzeCandlestickViaQuantCliMock.mockReset();
    getBuyRangeViaQuantCliMock.mockReset();
    getValuationViaQuantCliMock.mockReset();
    getPePercentileViaQuantCliMock.mockReset();
    getQualityScoreViaQuantCliMock.mockReset();
    getExitPlanViaQuantCliMock.mockReset();
    comparePeersViaQuantCliMock.mockReset();
  });

  test("routes analysis tool execution through quant CLI adapter", async () => {
    analyzeTechnicalViaQuantCliMock.mockResolvedValueOnce("{\"signals\":[]}");
    analyzePriceActionViaQuantCliMock.mockResolvedValueOnce("{\"trend\":{}}");
    analyzeCandlestickViaQuantCliMock.mockResolvedValueOnce("{\"patterns\":[]}");
    getBuyRangeViaQuantCliMock.mockResolvedValueOnce("{\"ideal_buy\":98}");
    getValuationViaQuantCliMock.mockResolvedValueOnce("{\"pe\":22}");
    getPePercentileViaQuantCliMock.mockResolvedValueOnce("{\"pe_percentile\":45}");
    getQualityScoreViaQuantCliMock.mockResolvedValueOnce("{\"score\":80}");
    getExitPlanViaQuantCliMock.mockResolvedValueOnce("{\"shares\":200}");
    comparePeersViaQuantCliMock.mockResolvedValueOnce("{\"sector\":\"白酒\"}");

    await (analyzeTechnicalTool.execute as any)("call-1", { symbol: "600519" });
    await (analyzePriceActionTool.execute as any)("call-2", { symbol: "600519", period: 80 });
    await (analyzeCandlestickTool.execute as any)("call-3", { symbol: "600519" });
    await (getBuyRangeTool.execute as any)("call-4", { symbol: "600519", current_price: 100.5 });
    await (getValuationTool.execute as any)("call-5", { symbol: "600519" });
    await (getPePercentileTool.execute as any)("call-6", { symbol: "600519", years: 3 });
    await (getQualityScoreTool.execute as any)("call-7", { symbol: "600519" });
    await (getExitPlanTool.execute as any)("call-8", {
      symbol: "600519",
      buy_price: 90,
      shares: 200,
    });
    await (comparePeersTool.execute as any)("call-9", { symbol: "600519" });

    expect(analyzeTechnicalViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(analyzePriceActionViaQuantCliMock).toHaveBeenCalledWith("600519", 80);
    expect(analyzeCandlestickViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(getBuyRangeViaQuantCliMock).toHaveBeenCalledWith("600519", 100.5);
    expect(getValuationViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(getPePercentileViaQuantCliMock).toHaveBeenCalledWith("600519", 3);
    expect(getQualityScoreViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(getExitPlanViaQuantCliMock).toHaveBeenCalledWith("600519", 90, 200);
    expect(comparePeersViaQuantCliMock).toHaveBeenCalledWith("600519");
  });

  test("rejects invalid symbols before invoking quant CLI", async () => {
    const result = await (analyzeTechnicalTool.execute as any)("call-1", { symbol: "AAPL.US" });

    expect(analyzeTechnicalViaQuantCliMock).not.toHaveBeenCalled();
    expect(result.content[0].text).toContain("不支持的股票代码");
  });
});
