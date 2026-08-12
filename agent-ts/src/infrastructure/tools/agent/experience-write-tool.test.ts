/**
 * Experience Write Tool Tests（W1.4 provider 架构）
 *
 * 工具层只测"参数规整 → provider.writeExperience → 响应形状"的契约
 * （含 symbol 自动生成 example 的工具层逻辑）；
 * 持久化与检索逻辑由 src/services/memory/ 下的测试覆盖。
 */
import { beforeEach, describe, expect, jest, test } from "@jest/globals";

const writeExperienceMock = jest.fn<(params: any) => Promise<{ success: boolean; id?: number; message: string }>>();

jest.unstable_mockModule("../../../services/memory/index.js", () => ({
  getMemoryProvider: () => ({
    writeExperience: writeExperienceMock,
  }),
}));

const { experienceWriteTool } = await import("./experience-write-tool.js");

const baseParams = {
  scenario: "MACD金叉买入",
  conditions: ["MACD金叉", "成交量放大"],
  action: "buy",
  total_cases: 10,
  win_rate: 0.7,
  avg_return: 5.2,
  recommendation: "moderate",
  reason: "技术形态良好",
  confidence: 0.8,
};

describe("experience_write tool (W1.4 provider 架构)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("成功写入：参数透传 + 响应含 success/data", async () => {
    writeExperienceMock.mockResolvedValueOnce({ success: true, id: 7, message: "ok" });

    const result = await (experienceWriteTool.execute as any)("test-call", { ...baseParams });

    expect(writeExperienceMock).toHaveBeenCalledTimes(1);
    const arg = writeExperienceMock.mock.calls[0][0] as any;
    expect(arg.scenario).toBe("MACD金叉买入");
    expect(arg.action).toBe("buy");
    expect(arg.recommendation).toBe("moderate");

    const content0 = result.content[0];
    if (content0.type === "text") {
      const data = JSON.parse(content0.text);
      expect(data.success).toBe(true);
      expect(data.data.action).toBe("buy");
      expect(data.data.recommendation).toBe("moderate");
    }
  });

  test("symbol 无 examples 时自动生成最小 example", async () => {
    writeExperienceMock.mockResolvedValueOnce({ success: true, message: "ok" });

    await (experienceWriteTool.execute as any)("test-call", { ...baseParams, symbol: "000858" });

    const arg = writeExperienceMock.mock.calls[0][0] as any;
    expect(arg.examples.length).toBe(1);
    expect(arg.examples[0].symbol).toBe("000858");
    expect(arg.examples[0].result).toBe(baseParams.avg_return);
    expect(arg.symbol).toBe("000858");
  });

  test("显式 examples 列表不被覆盖", async () => {
    writeExperienceMock.mockResolvedValueOnce({ success: true, message: "ok" });

    const examples = [
      { date: "2026-08-05", symbol: "300469", session_id: "v13_simulation", result: 12.6 },
      { date: "2026-08-05", symbol: "300045", session_id: "v13_simulation", result: 9.4 },
    ];
    await (experienceWriteTool.execute as any)("test-call", { ...baseParams, symbol: "601318", examples });

    const arg = writeExperienceMock.mock.calls[0][0] as any;
    expect(arg.examples.length).toBe(2);
    expect(arg.examples[0].symbol).toBe("300469");
  });

  test("sell 经验正确透传", async () => {
    writeExperienceMock.mockResolvedValueOnce({ success: true, message: "ok" });

    const result = await (experienceWriteTool.execute as any)("test-call", {
      ...baseParams,
      scenario: "浮盈触及+10%且盘中回落",
      action: "sell",
    });

    const arg = writeExperienceMock.mock.calls[0][0] as any;
    expect(arg.action).toBe("sell");
    const content0 = result.content[0];
    if (content0.type === "text") {
      const data = JSON.parse(content0.text);
      expect(data.data.action).toBe("sell");
    }
  });

  test("provider 返回失败时 success=false 透传", async () => {
    writeExperienceMock.mockResolvedValueOnce({ success: false, message: "v2 证据链门禁拦截" });

    const result = await (experienceWriteTool.execute as any)("test-call", { ...baseParams });

    const content0 = result.content[0];
    if (content0.type === "text") {
      const data = JSON.parse(content0.text);
      expect(data.success).toBe(false);
    }
  });

  test("provider 抛错时返回错误文本", async () => {
    writeExperienceMock.mockRejectedValueOnce(new Error("provider not initialized"));

    const result = await (experienceWriteTool.execute as any)("test-call", { ...baseParams });

    const content0 = result.content[0];
    if (content0.type === "text") {
      expect(content0.text).toMatch(/失败|错误|Error|provider/i);
    }
  });
});
