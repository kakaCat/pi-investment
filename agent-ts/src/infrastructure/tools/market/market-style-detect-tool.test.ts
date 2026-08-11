/**
 * market_style_detect 工具契约测试
 *
 * 回归背景（2026-08-11）：旧 formatter 期望 {current_style, trend_slope,
 * momentum_score} 等字段，但后端 /api/market/style 实际返回
 * {style, confidence, scores, indicators(camelCase), recommendedFactors}，
 * 导致报告全部渲染为空（只剩表头）。本测试锁定真实后端契约。
 */

import { beforeEach, describe, expect, it, jest } from "@jest/globals";

const mockRun = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule("../../adapters/quant/quant-v2-client.js", () => ({
  runQuantV2: mockRun,
}));

const { marketStyleDetectTool } = await import("./market-style-detect-tool.js");

beforeEach(() => { mockRun.mockReset(); });

const exec = (params: any = {}) => marketStyleDetectTool.execute("test-id", params);

// 与 FastAPI /api/market/style（api_response camelCase）一致的响应
const BACKEND_DATA = {
  style: "growth",
  confidence: 0.47,
  scores: { value: 0.3, growth: 0.47, cycle: 0.23 },
  indicators: {
    bankingPerformance: 2.5,
    techPerformance: 5.8,
    cyclePerformance: -1.2,
    marketVolumeChange: 15.6,
    marketVolatility: 0.018,
  },
  recommendedFactors: ["roe", "revenue_growth", "macd", "momentum"],
  detectionDate: "2026-08-11",
};

describe("market_style_detect", () => {
  it("按真实后端契约渲染完整报告（不再输出空表）", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "market.style", data: BACKEND_DATA } as any);
    const result = await exec();
    const text = (result.content[0] as any).text;

    expect(text).toContain("成长风格");
    expect(text).toContain("47.0%");            // 置信度
    expect(text).toContain("风格评分");
    expect(text).toContain("银行板块涨幅");
    expect(text).toContain("科技板块涨幅");
    expect(text).toContain("+15.6%");           // 成交量变化
    expect(text).toContain("1.80%");            // 波动率
    expect(text).toContain("`roe`");            // 推荐因子
    expect(text).toContain("投资建议");
    expect(text).toContain("策略建议");
  });

  it("兼容 snake_case 字段（recommended_factors / detection_date）", async () => {
    mockRun.mockResolvedValue({
      ok: true,
      command: "market.style",
      data: {
        style: "value",
        confidence: 0.5,
        scores: { value: 0.5, growth: 0.3, cycle: 0.2 },
        indicators: { banking_performance: 4.2, market_volatility: 0.025 },
        recommended_factors: ["pe", "pb"],
        detection_date: "2026-08-11",
      },
    } as any);
    const result = await exec();
    const text = (result.content[0] as any).text;

    expect(text).toContain("价值风格");
    expect(text).toContain("`pe`");
    expect(text).toContain("4.2%");
  });

  it("data 缺少 style 时返回明确错误而非空表", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "market.style", data: {} } as any);
    const result = await exec();
    expect((result.content[0] as any).text).toContain("未获取到市场风格数据");
  });

  it("后端返回 ok=false 时抛出错误信息", async () => {
    mockRun.mockResolvedValue({ ok: false, command: "market.style", error: { message: "boom" } } as any);
    const result = await exec();
    expect((result.content[0] as any).text).toContain("市场风格检测失败");
    expect((result.content[0] as any).text).toContain("boom");
  });
});
