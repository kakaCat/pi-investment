import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const analyzePriceActionViaQuantCliMock = jest.fn<(symbol: string, period?: number) => Promise<string>>();
const analyzeCandlestickViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const analyzeTechnicalViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getStockHistoryViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();
const getStockNewsViaQuantCliMock = jest.fn<(symbol: string, num?: number) => Promise<string>>();
const getAnnouncementsViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getStockFundFlowViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();

await jest.unstable_mockModule("../../infrastructure/quant/analysis-query-cli-adapter.js", () => ({
  analyzePriceActionViaQuantCli: analyzePriceActionViaQuantCliMock,
  analyzeCandlestickViaQuantCli: analyzeCandlestickViaQuantCliMock,
  analyzeTechnicalViaQuantCli: analyzeTechnicalViaQuantCliMock,
}));

await jest.unstable_mockModule("../../infrastructure/quant/stock-query-cli-adapter.js", () => ({
  getStockHistoryViaQuantCli: getStockHistoryViaQuantCliMock,
  getStockNewsViaQuantCli: getStockNewsViaQuantCliMock,
  getAnnouncementsViaQuantCli: getAnnouncementsViaQuantCliMock,
}));

await jest.unstable_mockModule("../../infrastructure/quant/sentiment-query-cli-adapter.js", () => ({
  getStockFundFlowViaQuantCli: getStockFundFlowViaQuantCliMock,
}));

const { StopLossAnalyzer } = await import("./stop-loss-analyzer-service.js");

describe("StopLossAnalyzer", () => {
  beforeEach(() => {
    analyzePriceActionViaQuantCliMock.mockReset();
    analyzeCandlestickViaQuantCliMock.mockReset();
    analyzeTechnicalViaQuantCliMock.mockReset();
    getStockHistoryViaQuantCliMock.mockReset();
    getStockNewsViaQuantCliMock.mockReset();
    getAnnouncementsViaQuantCliMock.mockReset();
    getStockFundFlowViaQuantCliMock.mockReset();
  });

  test("uses quant CLI adapters for all stock data dimensions", async () => {
    analyzePriceActionViaQuantCliMock.mockResolvedValue(JSON.stringify({
      trend: "下降",
      nearestSupport: 90,
      nearestResistance: 120,
    }));
    analyzeCandlestickViaQuantCliMock.mockResolvedValue(JSON.stringify({ patterns: ["黄昏星"] }));
    analyzeTechnicalViaQuantCliMock.mockResolvedValue(JSON.stringify({
      signals: ["MACD死叉"],
      rsi: 75,
    }));
    getStockHistoryViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: Array.from({ length: 25 }, (_, index) => ({
        date: `2026-05-${String(index + 1).padStart(2, "0")}`,
        volume: index === 24 ? 3000 : 1000,
      })),
    }));
    getStockFundFlowViaQuantCliMock.mockResolvedValue(JSON.stringify({
      main_force_net_inflow: -100,
      smallOrderNetInflow: 90,
    }));
    getStockNewsViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [{ title: "公司业绩预警" }],
    }));
    getAnnouncementsViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [{ title: "关于业绩预亏的公告" }],
    }));

    const report = await new StopLossAnalyzer().analyze({
      symbol: "600519",
      name: "贵州茅台",
      currentPrice: 88,
      costPrice: 100,
      stopLossPrice: 90,
      market: "A",
    });

    expect(analyzePriceActionViaQuantCliMock).toHaveBeenCalledWith("600519", 60);
    expect(analyzeCandlestickViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(analyzeTechnicalViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(getStockHistoryViaQuantCliMock).toHaveBeenCalledWith({
      symbol: "600519",
      period: "daily",
      limit: 60,
    });
    expect(getStockFundFlowViaQuantCliMock).toHaveBeenCalledWith({ symbol: "600519" });
    expect(getStockNewsViaQuantCliMock).toHaveBeenCalledWith("600519", 10);
    expect(getAnnouncementsViaQuantCliMock).toHaveBeenCalledWith("600519");
    expect(report.fundamentals.earningsWarning).toBe(true);
  });
});
