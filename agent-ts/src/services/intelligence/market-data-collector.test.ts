import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const getIndexHistoryViaQuantCliMock = jest.fn<(params: any) => Promise<string>>();
const getMarketOverviewViaQuantCliMock = jest.fn<() => Promise<string>>();
const getSectorFundFlowViaQuantCliMock = jest.fn<() => Promise<string>>();

await jest.unstable_mockModule("../../infrastructure/quant/market-query-cli-adapter.js", () => ({
  getIndexHistoryViaQuantCli: getIndexHistoryViaQuantCliMock,
  getMarketOverviewViaQuantCli: getMarketOverviewViaQuantCliMock,
  getSectorFundFlowViaQuantCli: getSectorFundFlowViaQuantCliMock,
}));

// @ts-ignore - Module stub needed
const { collectMarketContext } = await import("./market-data-collector.js");

describe("market-data-collector", () => {
  beforeEach(() => {
    getIndexHistoryViaQuantCliMock.mockReset();
    getMarketOverviewViaQuantCliMock.mockReset();
    getSectorFundFlowViaQuantCliMock.mockReset();
  });

  test("collects market context through quant CLI market adapter", async () => {
    const history = {
      success: true,
      data: [
        { date: "2026-05-01", open: 100, high: 101, low: 99, close: 100, volume: 1000 },
        { date: "2026-05-20", open: 100, high: 110, low: 98, close: 110, volume: 1200 },
      ],
    };
    getIndexHistoryViaQuantCliMock.mockResolvedValue(JSON.stringify(history));
    getSectorFundFlowViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [{ sector: "银行", change_pct: 1.2, net_inflow: 1000, leading_stocks: ["600000"] }],
    }));
    getMarketOverviewViaQuantCliMock.mockResolvedValue(JSON.stringify({
      indices: {
        "上证指数": { change_pct: 1 },
        "深证成指": { change_pct: 1 },
      },
    }));

    const context = await collectMarketContext("2026-05-01", "2026-05-20", 19);

    expect(getIndexHistoryViaQuantCliMock).toHaveBeenCalledWith({
      symbol: "sh000001",
      start_date: "2026-05-01",
      end_date: "2026-05-20",
    });
    expect(getSectorFundFlowViaQuantCliMock).toHaveBeenCalled();
    expect(getMarketOverviewViaQuantCliMock).toHaveBeenCalled();
    expect(context.indices.sh000001.currentPrice).toBe(110);
    expect(context.sectorPerformance[0].sector).toBe("银行");
    expect(context.sentiment.sentiment).toBe("neutral");
  });
});
