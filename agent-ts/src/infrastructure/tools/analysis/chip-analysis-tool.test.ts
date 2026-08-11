/**
 * Chip Analysis Tool - 测试
 * 筹码分布（成本分布）工具：调 v2 GET /api/analysis/chip-distribution/{symbol}。
 * 模式跟随 chan-analyze-tool.test.ts（@jest/globals + unstable_mockModule）。
 */
import { beforeEach, describe, expect, it, jest } from "@jest/globals";

const mockRun = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule("../../adapters/quant/quant-v2-client.js", () => ({
  runQuantV2: mockRun,
}));

const { chipAnalysisTool } = await import("./chip-analysis-tool.js");

beforeEach(() => { mockRun.mockReset(); });

const SAMPLE = {
  symbol: "600519",
  asOf: "2026-08-10",
  close: 1348.86,
  curve: [
    { price: 1290, weight: 0.4 },
    { price: 1310, weight: 0.6 },
  ],
  metrics: {
    profitRatio: 0.62, avgCost: 1289.5,
    cost90Low: 1191, cost90High: 1350,
    cost70Low: 1214, cost70High: 1342,
    peakPrice: 1310, concentration: 0.1,
  },
};

describe("chip_analysis tool", () => {
  it("缺少 symbol 返回错误", async () => {
    const result = await chipAnalysisTool.execute("t1", {});
    expect(result.details).toMatchObject({ success: false });
  });

  it("正常返回含获利盘/成本/峰位解读", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "analysis.chipDistribution", data: SAMPLE });
    const result = await chipAnalysisTool.execute("t2", { symbol: "600519" });
    expect(mockRun).toHaveBeenCalledWith("analysis.chipDistribution", { symbol: "600519" });
    const text = (result.content[0] as any).text;
    expect(text).toContain("获利盘");
    expect(text).toContain("62");
    expect(text).toContain("1289.5");
    expect(text).toContain("密集峰");
  });

  it("后端返回 error 时透传", async () => {
    mockRun.mockResolvedValue({ ok: true, command: "analysis.chipDistribution", data: { symbol: "X", error: "筹码分布未计算" } });
    const result = await chipAnalysisTool.execute("t3", { symbol: "X" });
    expect((result.content[0] as any).text).toContain("未计算");
  });
});
