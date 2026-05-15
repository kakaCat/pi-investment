import { describe, expect, test, jest } from "@jest/globals";

// ── Mock callPython using ESM-compatible jest.unstable_mockModule ──
const mockCallPython = jest.fn<(...args: string[]) => Promise<string>>();

await jest.unstable_mockModule("./invest-tools.js", () => ({
  callPython: mockCallPython,
}));

const { analyzeSectorRotationTool } = await import("./analyze-sector-rotation-tool.js");

describe("analyzeSectorRotationTool", () => {
  beforeEach(() => {
    mockCallPython.mockReset();
  });

  function callTool(
    params: Record<string, unknown>,
  ): ReturnType<typeof analyzeSectorRotationTool.execute> {
    return analyzeSectorRotationTool.execute(
      "test-call-id",
      params,
      undefined as any,
      undefined as any,
      undefined as any,
    );
  }

  // ── Test case 1: Normal case — sectors with mixed inflows/outflows ──
  test("returns sorted top gainers and decliners with signals", async () => {
    mockCallPython.mockImplementation(async () =>
      JSON.stringify({
        data: [
          { name: "白酒", net_inflow: 5000000000, inflow_pct: 3.5, price: 8000, pct_chg: 1.8 },
          { name: "新能源", net_inflow: 3000000000, inflow_pct: 2.1, price: 5500, pct_chg: 0.9 },
          { name: "医药", net_inflow: 2000000000, inflow_pct: 1.5, price: 4200, pct_chg: 0.5 },
          { name: "半导体", net_inflow: 1000000000, inflow_pct: 0.8, price: 3600, pct_chg: 0.3 },
          { name: "银行", net_inflow: 500000000, inflow_pct: 0.3, price: 2800, pct_chg: -0.1 },
          { name: "房地产", net_inflow: 0, inflow_pct: 0, price: 1900, pct_chg: -0.5 },
          { name: "煤炭", net_inflow: -1000000000, inflow_pct: -0.6, price: 2100, pct_chg: -0.8 },
          { name: "钢铁", net_inflow: -2000000000, inflow_pct: -1.2, price: 1500, pct_chg: -1.2 },
          { name: "化工", net_inflow: -3000000000, inflow_pct: -2.5, price: 3200, pct_chg: -2.1 },
          { name: "建材", net_inflow: -4000000000, inflow_pct: -3.0, price: 1800, pct_chg: -2.5 },
        ],
      }),
    );

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;

    // Contains header and rotation stage
    expect(text).toContain("行业轮动分析");
    expect(text).toContain("轮动阶段");

    // Contains flow direction tables
    expect(text).toContain("资金流入TOP5");
    expect(text).toContain("资金流出TOP5");

    // Top gainers should include strong inflow sectors
    expect(text).toContain("白酒");
    expect(text).toContain("新能源");

    // Top decliners should include strong outflow sectors
    expect(text).toContain("化工");
    expect(text).toContain("建材");

    // Strong inflow signal should be present (inflow_pct > 2)
    expect(text).toContain("强势流入");
    expect(text).toContain("白酒");

    // Strong outflow signal should be present (inflow_pct < -2)
    expect(text).toContain("强势流出");
    expect(text).toContain("化工");
    expect(text).toContain("建材");

    // Advice section
    expect(text).toContain("建议");
    expect(text).toContain("关注方向");

    // Details object
    const details = result.details as any;
    expect(details).toBeDefined();
    expect(details.topGainers).toHaveLength(5);
    expect(details.topDecliners).toHaveLength(5);
    expect(details.signals).toBeInstanceOf(Array);
    expect(details.signals.length).toBeGreaterThanOrEqual(2);
    expect(details.rotationStage).toBeDefined();
  });

  // ── Test case 2: Error handling — callPython throws ──
  test("returns friendly error when callPython throws", async () => {
    mockCallPython.mockRejectedValue(new Error("API timeout after 30s"));

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    expect(text).toContain("行业轮动分析失败");
    expect(text).toContain("API timeout");
    expect(result.details).toBeUndefined();
  });

  // ── Test case 3: Error handling — API returns error JSON ──
  test("returns friendly error when API returns error in data", async () => {
    mockCallPython.mockResolvedValue(
      JSON.stringify({ error: "市场未开盘，暂无数据" }),
    );

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    expect(text).toContain("获取行业资金流数据失败");
    expect(text).toContain("市场未开盘");
    expect(result.details).toBeUndefined();
  });

  // ── Test case 4: Empty data array ──
  test("handles empty sectors data gracefully", async () => {
    mockCallPython.mockResolvedValue(JSON.stringify({ data: [] }));

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    expect(text).toBe("未获取到行业资金流数据");
    expect(result.details).toBeUndefined();
  });

  // ── Test case 5: Everything is positive (no outflow sectors) ──
  test("handles all-positive sector flows correctly", async () => {
    mockCallPython.mockResolvedValue(
      JSON.stringify({
        data: [
          { name: "白酒", net_inflow: 8000000000, inflow_pct: 5.0, price: 8000, pct_chg: 2.5 },
          { name: "新能源", net_inflow: 6000000000, inflow_pct: 4.0, price: 5500, pct_chg: 1.8 },
          { name: "医药", net_inflow: 4000000000, inflow_pct: 3.0, price: 4200, pct_chg: 1.2 },
          { name: "半导体", net_inflow: 2000000000, inflow_pct: 2.0, price: 3600, pct_chg: 0.8 },
          { name: "银行", net_inflow: 1000000000, inflow_pct: 1.0, price: 2800, pct_chg: 0.3 },
        ],
      }),
    );

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    // When all sectors have positive inflow but the rotation logic still sees
    // the bottom 5 (reversed top 5) as "decliners"), it'll show 轮动中.
    // The key signal is still "强势流入" since inflow_pct > 2.
    expect(text).toContain("流入TOP5");
    expect(text).toContain("建议");
    expect(text).toContain("关注方向");

    // Strong inflow signals should be present
    expect(text).toContain("强势流入");
    expect(text).toContain("白酒");

    // No 强势 outflow signal when no sectors have negative net_inflow
    // (bank has positive inflow, just lower)
    const details = result.details as any;
    expect(details.rotationStage).toBeDefined();
    expect(details.signals.find((s: string) => s.includes("强势流出"))).toBeUndefined();
  });

  // ── Test case 6: All data is negative (no inflow sectors) ──
  test("handles all-negative sector flows as 普跌", async () => {
    mockCallPython.mockResolvedValue(
      JSON.stringify({
        data: [
          { name: "房地产", net_inflow: -1000000000, inflow_pct: -0.8, price: 1900, pct_chg: -0.6 },
          { name: "煤炭", net_inflow: -3000000000, inflow_pct: -2.0, price: 2100, pct_chg: -1.5 },
          { name: "钢铁", net_inflow: -4000000000, inflow_pct: -3.0, price: 1500, pct_chg: -2.0 },
          { name: "化工", net_inflow: -5000000000, inflow_pct: -4.0, price: 3200, pct_chg: -3.0 },
          { name: "建材", net_inflow: -6000000000, inflow_pct: -5.0, price: 1800, pct_chg: -3.5 },
        ],
      }),
    );

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    expect(text).toContain("普跌");
    expect(text).toContain("流出TOP5");
    expect(text).toContain("规避方向");

    const details = result.details as any;
    expect(details.rotationStage).toContain("普跌");
  });

  // ── Test case 7: Custom days parameter ──
  test("accepts custom days parameter in output header", async () => {
    mockCallPython.mockResolvedValue(
      JSON.stringify({
        data: [
          { name: "白酒", net_inflow: 1000000000, inflow_pct: 1.0, price: 8000, pct_chg: 0.5 },
        ],
      }),
    );

    const result = await callTool({ days: 10 });

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;
    expect(text).toContain("近10日");
  });

  // ── Test case 8: Rotation pattern detection ──
  test("detects clear rotation pattern when inflow sectors rise and outflow sectors fall", async () => {
    mockCallPython.mockImplementation(async () =>
      JSON.stringify({
        data: [
          { name: "白酒", net_inflow: 6000000000, inflow_pct: 4.0, price: 8000, pct_chg: 2.0 },
          { name: "新能源", net_inflow: 5000000000, inflow_pct: 3.5, price: 5500, pct_chg: 1.5 },
          { name: "医药", net_inflow: 3000000000, inflow_pct: 2.5, price: 4200, pct_chg: 1.0 },
          { name: "半导体", net_inflow: 2000000000, inflow_pct: 1.5, price: 3600, pct_chg: 0.5 },
          { name: "银行", net_inflow: 1000000000, inflow_pct: 0.5, price: 2800, pct_chg: -0.2 },
          { name: "房地产", net_inflow: -1000000000, inflow_pct: -0.5, price: 1900, pct_chg: -0.8 },
          { name: "煤炭", net_inflow: -2000000000, inflow_pct: -1.5, price: 2100, pct_chg: -1.2 },
          { name: "钢铁", net_inflow: -4000000000, inflow_pct: -3.0, price: 1500, pct_chg: -2.5 },
          { name: "化工", net_inflow: -5000000000, inflow_pct: -4.0, price: 3200, pct_chg: -3.0 },
          { name: "建材", net_inflow: -6000000000, inflow_pct: -5.0, price: 1800, pct_chg: -3.5 },
        ],
      }),
    );

    const result = await callTool({});

    expect(result.content).toHaveLength(1);
    const text = (result.content[0] as any).text;

    // Should contain the clear rotation signal
    expect(text).toContain("轮动清晰");
    expect(text).toContain("轮动格局明确");

    const details = result.details as any;
    expect(details.signals).toBeInstanceOf(Array);
    const rotationSignal = details.signals.find(
      (s: string) => s.includes("轮动清晰"),
    );
    expect(rotationSignal).toBeDefined();
  });
});
