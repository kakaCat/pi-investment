import { describe, expect, test, jest } from "@jest/globals";

const getNorthFlowViaQuantCliMock = jest.fn<() => Promise<string>>();
const getMarketMarginViaQuantCliMock = jest.fn<() => Promise<string>>();
const getMacroDataViaQuantCliMock = jest.fn<() => Promise<string>>();
const getMarketOverviewViaQuantCliMock = jest.fn<() => Promise<string>>();
const getHotStocksViaQuantCliMock = jest.fn<() => Promise<string>>();

await jest.unstable_mockModule("../quant/market-query-cli-adapter.js", () => ({
  getNorthFlowViaQuantCli: getNorthFlowViaQuantCliMock,
  getMarketMarginViaQuantCli: getMarketMarginViaQuantCliMock,
  getMacroDataViaQuantCli: getMacroDataViaQuantCliMock,
  getMarketOverviewViaQuantCli: getMarketOverviewViaQuantCliMock,
  getHotStocksViaQuantCli: getHotStocksViaQuantCliMock,
}));

import type { AgentToolResult } from "@mariozechner/pi-coding-agent";
type AnyAgentToolResult = AgentToolResult<any>;
const { testMarketSentimentTool } = await import("./test-market-sentiment-tool.js");

describe("testMarketSentimentTool", () => {
  beforeEach(() => {
    getNorthFlowViaQuantCliMock.mockReset();
    getMarketMarginViaQuantCliMock.mockReset();
    getMacroDataViaQuantCliMock.mockReset();
    getMarketOverviewViaQuantCliMock.mockReset();
    getHotStocksViaQuantCliMock.mockReset();
  });

  function callTool(params: Record<string, unknown>): Promise<AnyAgentToolResult> {
    return testMarketSentimentTool.execute(
      "test-call-id",
      params,
      undefined as any,
      undefined as any,
      undefined as any,
    ) as Promise<AnyAgentToolResult>;
  }

  // ── Test case 1: Normal case with all data available ──
  test("returns composite sentiment score when all data sources are available", async () => {
    getNorthFlowViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [
        { net_inflow: 5000000000 },
        { net_inflow: 3000000000 },
        { net_inflow: 4000000000 },
        { net_inflow: 2000000000 },
        { net_inflow: 6000000000 },
      ],
    }));
    getMarketMarginViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [
        { total_margin: 15000 },
        { total_margin: 15500 },
      ],
    }));
    getMacroDataViaQuantCliMock.mockResolvedValue(JSON.stringify({
      pmi: [
        { value: 50.8 },
        { value: 51.2 },
      ],
    }));
    getMarketOverviewViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [
        { change_pct: 0.85 },
        { change_pct: 1.20 },
        { change_pct: 1.50 },
        { change_pct: 0.60 },
        { change_pct: 0.95 },
      ],
    }));
    getHotStocksViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [
        { change_pct: 3.5 },
        { change_pct: 2.1 },
        { change_pct: -1.2 },
        { change_pct: 4.8 },
        { change_pct: 6.2 },
      ],
    }));

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;

    expect(text).toContain("市场情绪分析");
    expect(text).toContain("综合情绪指数");
    expect(text).toContain("北向资金");
    expect(text).toContain("融资融券");
    expect(text).toContain("热点情绪");
    expect(text).toContain("大盘趋势");
    expect(text).toContain("宏观情绪");
    expect(text).toContain("操作建议");

    const details = result.details as any;
    expect(details).toBeDefined();
    expect(details.compositeScore).toBeGreaterThanOrEqual(0);
    expect(details.compositeScore).toBeLessThanOrEqual(100);
    expect(details.sentimentLabel).toBeDefined();
    expect(details.advice).toBeDefined();

    expect(details.compositeScore).toBeGreaterThan(50);
  });

  // ── Test case 2: All data sources fail ──
  test("gracefully handles all data source failures", async () => {
    const errorJson = JSON.stringify({ error: "API timeout" });
    getNorthFlowViaQuantCliMock.mockResolvedValue(errorJson);
    getMarketMarginViaQuantCliMock.mockResolvedValue(errorJson);
    getMacroDataViaQuantCliMock.mockResolvedValue(errorJson);
    getMarketOverviewViaQuantCliMock.mockResolvedValue(errorJson);
    getHotStocksViaQuantCliMock.mockResolvedValue(errorJson);

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;

    expect(text).toContain("市场情绪分析");
    expect(text).toContain("综合情绪指数");

    const details = result.details as any;
    expect(details).toBeDefined();
    expect(details.compositeScore).toBe(50);
    expect(details.sentimentLabel).toBe("中性");
  });

  // ── Test case 3: Extreme negative market data ──
  test("correctly identifies extreme fear with strongly negative data", async () => {
    getNorthFlowViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [
        { net_inflow: -8000000000 },
        { net_inflow: -6000000000 },
        { net_inflow: -10000000000 },
        { net_inflow: -5000000000 },
        { net_inflow: -7000000000 },
      ],
    }));
    getMarketMarginViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [
        { total_margin: 16000 },
        { total_margin: 15200 },
      ],
    }));
    getMacroDataViaQuantCliMock.mockResolvedValue(JSON.stringify({
      pmi: [
        { value: 48.5 },
        { value: 47.2 },
      ],
    }));
    getMarketOverviewViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [
        { change_pct: -2.30 },
        { change_pct: -2.80 },
        { change_pct: -3.10 },
        { change_pct: -1.90 },
        { change_pct: -2.50 },
      ],
    }));
    getHotStocksViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [
        { change_pct: -7.2 },
        { change_pct: -5.8 },
        { change_pct: -3.1 },
        { change_pct: -9.5 },
        { change_pct: -4.3 },
      ],
    }));

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const details = result.details as any;
    expect(details).toBeDefined();
    expect(details.compositeScore).toBeLessThan(50);
    expect(details.sentimentLabel).toMatch(/恐惧/);
  });

  // ── Test case 4: Partial data ──
  test("handles partial data gracefully", async () => {
    getNorthFlowViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [
        { net_inflow: 2000000000 },
        { net_inflow: 1000000000 },
      ],
    }));
    getMarketMarginViaQuantCliMock.mockRejectedValue(new Error("Timeout"));
    getMacroDataViaQuantCliMock.mockResolvedValue('{"pmi": [{"value": 50.5}]}');
    getMarketOverviewViaQuantCliMock.mockRejectedValue(new Error("Network error"));
    getHotStocksViaQuantCliMock.mockResolvedValue(JSON.stringify({
      data: [
        { change_pct: 1.2 },
        { change_pct: 0.8 },
      ],
    }));

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    expect(text).toContain("市场情绪分析");
    expect(text).toContain("北向资金");

    const details = result.details as any;
    expect(details).toBeDefined();
    expect(details.compositeScore).toBeGreaterThanOrEqual(0);
    expect(details.compositeScore).toBeLessThanOrEqual(100);
  });

  // ── Test case 5: Empty data arrays ──
  test("handles empty data arrays gracefully", async () => {
    getNorthFlowViaQuantCliMock.mockResolvedValue(JSON.stringify({ data: [] }));
    getMarketMarginViaQuantCliMock.mockResolvedValue(JSON.stringify({ data: [] }));
    getMacroDataViaQuantCliMock.mockResolvedValue(JSON.stringify({ pmi: [] }));
    getMarketOverviewViaQuantCliMock.mockResolvedValue(JSON.stringify({ data: [] }));
    getHotStocksViaQuantCliMock.mockResolvedValue(JSON.stringify({ data: [] }));

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const details = result.details as any;
    expect(details).toBeDefined();
    expect(details.compositeScore).toBe(50);
    expect(details.sentimentLabel).toBe("中性");
  });
});
