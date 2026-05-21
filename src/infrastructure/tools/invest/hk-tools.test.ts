import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const getHkMarketOverviewViaQuantCliMock = jest.fn<() => Promise<string>>();
const getHkSouthFlowViaQuantCliMock = jest.fn<() => Promise<string>>();
const getHkTechnicalViaQuantCliMock = jest.fn<(symbol: string) => Promise<string>>();
const getHkHotRankViaQuantCliMock = jest.fn<() => Promise<string>>();

await jest.unstable_mockModule("../../quant/hk-query-cli-adapter.js", () => ({
  getHkMarketOverviewViaQuantCli: getHkMarketOverviewViaQuantCliMock,
  getHkSouthFlowViaQuantCli: getHkSouthFlowViaQuantCliMock,
  getHkTechnicalViaQuantCli: getHkTechnicalViaQuantCliMock,
  getHkHotRankViaQuantCli: getHkHotRankViaQuantCliMock,
}));

const {
  getHkMarketOverviewTool,
  getHkSouthFlowTool,
  getHkTechnicalTool,
  getHkHotRankTool,
} = await import("./hk-tools.js");

describe("HK tools", () => {
  beforeEach(() => {
    getHkMarketOverviewViaQuantCliMock.mockReset();
    getHkSouthFlowViaQuantCliMock.mockReset();
    getHkTechnicalViaQuantCliMock.mockReset();
    getHkHotRankViaQuantCliMock.mockReset();
  });

  test("routes HK tool execution through quant CLI adapter while preserving tool names", async () => {
    getHkMarketOverviewViaQuantCliMock.mockResolvedValueOnce("{\"indices\":[]}");
    getHkSouthFlowViaQuantCliMock.mockResolvedValueOnce("{\"data\":[]}");
    getHkTechnicalViaQuantCliMock.mockResolvedValueOnce("{\"symbol\":\"09988\"}");
    getHkHotRankViaQuantCliMock.mockResolvedValueOnce("{\"stocks\":[]}");

    expect(getHkMarketOverviewTool.name).toBe("get_hk_market_overview");
    expect(getHkSouthFlowTool.name).toBe("get_hk_south_flow");
    expect(getHkTechnicalTool.name).toBe("get_hk_technical");
    expect(getHkHotRankTool.name).toBe("get_hk_hot_rank");

    await (getHkMarketOverviewTool.execute as any)("call-1", {});
    await (getHkSouthFlowTool.execute as any)("call-2", {});
    await (getHkTechnicalTool.execute as any)("call-3", { symbol: "9988" });
    await (getHkHotRankTool.execute as any)("call-4", {});

    expect(getHkMarketOverviewViaQuantCliMock).toHaveBeenCalledWith();
    expect(getHkSouthFlowViaQuantCliMock).toHaveBeenCalledWith();
    expect(getHkTechnicalViaQuantCliMock).toHaveBeenCalledWith("9988");
    expect(getHkHotRankViaQuantCliMock).toHaveBeenCalledWith();
  });
});

