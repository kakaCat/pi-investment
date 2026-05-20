import { describe, expect, jest, test, beforeEach } from "@jest/globals";

const getMarketOverviewViaQuantCliMock = jest.fn<() => Promise<string>>();
const getSectorListViaQuantCliMock = jest.fn<() => Promise<string>>();
const getConceptStocksViaQuantCliMock = jest.fn<(concept: string) => Promise<string>>();
const getConceptListViaQuantCliMock = jest.fn<() => Promise<string>>();
const getMacroDataViaQuantCliMock = jest.fn<(indicators?: string[]) => Promise<string>>();
const getNorthFlowViaQuantCliMock = jest.fn<() => Promise<string>>();
const getSectorFundFlowViaQuantCliMock = jest.fn<() => Promise<string>>();
const getMarketMarginViaQuantCliMock = jest.fn<() => Promise<string>>();
const getMarketNewsViaQuantCliMock = jest.fn<(num?: number) => Promise<string>>();
const getHotStocksViaQuantCliMock = jest.fn<(market?: string) => Promise<string>>();

await jest.unstable_mockModule("../../quant/market-query-cli-adapter.js", () => ({
  getMarketOverviewViaQuantCli: getMarketOverviewViaQuantCliMock,
  getSectorListViaQuantCli: getSectorListViaQuantCliMock,
  getConceptStocksViaQuantCli: getConceptStocksViaQuantCliMock,
  getConceptListViaQuantCli: getConceptListViaQuantCliMock,
  getMacroDataViaQuantCli: getMacroDataViaQuantCliMock,
  getNorthFlowViaQuantCli: getNorthFlowViaQuantCliMock,
  getSectorFundFlowViaQuantCli: getSectorFundFlowViaQuantCliMock,
  getMarketMarginViaQuantCli: getMarketMarginViaQuantCliMock,
  getMarketNewsViaQuantCli: getMarketNewsViaQuantCliMock,
  getHotStocksViaQuantCli: getHotStocksViaQuantCliMock,
}));

const {
  getMarketOverviewTool,
  getSectorListTool,
  getConceptStocksTool,
  getConceptListTool,
  getMacroDataTool,
  getNorthFlowTool,
  getSectorFundFlowTool,
  getMarketMarginTool,
  getMarketNewsTool,
  getHotStocksTool,
} = await import("./market-tools.js");

describe("market tools", () => {
  beforeEach(() => {
    getMarketOverviewViaQuantCliMock.mockReset();
    getSectorListViaQuantCliMock.mockReset();
    getConceptStocksViaQuantCliMock.mockReset();
    getConceptListViaQuantCliMock.mockReset();
    getMacroDataViaQuantCliMock.mockReset();
    getNorthFlowViaQuantCliMock.mockReset();
    getSectorFundFlowViaQuantCliMock.mockReset();
    getMarketMarginViaQuantCliMock.mockReset();
    getMarketNewsViaQuantCliMock.mockReset();
    getHotStocksViaQuantCliMock.mockReset();
  });

  test("routes market tool execution through quant CLI adapter", async () => {
    getMarketOverviewViaQuantCliMock.mockResolvedValueOnce("{\"indices\":{}}");
    getSectorListViaQuantCliMock.mockResolvedValueOnce("{\"count\":1}");
    getConceptStocksViaQuantCliMock.mockResolvedValueOnce("{\"concept\":\"人工智能\"}");
    getConceptListViaQuantCliMock.mockResolvedValueOnce("{\"count\":2}");
    getMacroDataViaQuantCliMock.mockResolvedValueOnce("{\"pmi\":[]}");
    getNorthFlowViaQuantCliMock.mockResolvedValueOnce("{\"data\":[]}");
    getSectorFundFlowViaQuantCliMock.mockResolvedValueOnce("{\"count\":3}");
    getMarketMarginViaQuantCliMock.mockResolvedValueOnce("{\"count\":4}");
    getMarketNewsViaQuantCliMock.mockResolvedValueOnce("{\"sources\":[]}");
    getHotStocksViaQuantCliMock.mockResolvedValueOnce("{\"market\":\"港股\"}");

    await (getMarketOverviewTool.execute as any)("call-1", {});
    await (getSectorListTool.execute as any)("call-2", {});
    await (getConceptStocksTool.execute as any)("call-3", { concept: "人工智能" });
    await (getConceptListTool.execute as any)("call-4", {});
    await (getMacroDataTool.execute as any)("call-5", { indicators: ["pmi", "cpi"] });
    await (getNorthFlowTool.execute as any)("call-6", {});
    await (getSectorFundFlowTool.execute as any)("call-7", {});
    await (getMarketMarginTool.execute as any)("call-8", {});
    await (getMarketNewsTool.execute as any)("call-9", { num: 9 });
    await (getHotStocksTool.execute as any)("call-10", { market: "港股" });

    expect(getMarketOverviewViaQuantCliMock).toHaveBeenCalledWith();
    expect(getSectorListViaQuantCliMock).toHaveBeenCalledWith();
    expect(getConceptStocksViaQuantCliMock).toHaveBeenCalledWith("人工智能");
    expect(getConceptListViaQuantCliMock).toHaveBeenCalledWith();
    expect(getMacroDataViaQuantCliMock).toHaveBeenCalledWith(["pmi", "cpi"]);
    expect(getNorthFlowViaQuantCliMock).toHaveBeenCalledWith();
    expect(getSectorFundFlowViaQuantCliMock).toHaveBeenCalledWith();
    expect(getMarketMarginViaQuantCliMock).toHaveBeenCalledWith();
    expect(getMarketNewsViaQuantCliMock).toHaveBeenCalledWith(9);
    expect(getHotStocksViaQuantCliMock).toHaveBeenCalledWith("港股");
  });
});
