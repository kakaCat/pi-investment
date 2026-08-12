/**
 * Query Experience Tool Tests（W1.4 provider 架构）
 *
 * 工具层只测"参数 → provider.queryExperience → 文本返回"的契约；
 * 检索逻辑本身由 src/services/memory/ 下的测试覆盖。
 */
import { beforeEach, describe, expect, jest, test } from "@jest/globals";

const queryExperienceMock = jest.fn<(params: any) => Promise<string>>();

jest.unstable_mockModule("../../../services/memory/index.js", () => ({
  getMemoryProvider: () => ({
    queryExperience: queryExperienceMock,
  }),
}));

const { queryExperienceTool } = await import("./query-experience-tool.js");

describe("query_experience tool (W1.4 provider 架构)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("参数透传到 provider.queryExperience", async () => {
    queryExperienceMock.mockResolvedValueOnce("找到 1 条相关经验:\n━━━ 机械止盈 ━━━");

    const params = { scenario: "浮盈触及+10%回落", symbol: "300561", limit: 3 };
    const result = await (queryExperienceTool.execute as any)("test-call", params);

    expect(queryExperienceMock).toHaveBeenCalledWith(params);
    const content0 = result.content[0];
    if (content0.type === "text") {
      expect(content0.text).toContain("机械止盈");
    }
  });

  test("无命中时返回空提示", async () => {
    queryExperienceMock.mockResolvedValueOnce("未找到相关历史经验。");

    const result = await (queryExperienceTool.execute as any)("test-call", {
      scenario: "不存在的场景",
    });

    const content0 = result.content[0];
    if (content0.type === "text") {
      expect(content0.text).toContain("未找到");
    }
  });

  test("provider 抛错时返回错误文本", async () => {
    queryExperienceMock.mockRejectedValueOnce(new Error("boom"));

    const result = await (queryExperienceTool.execute as any)("test-call", {
      scenario: "x",
    });

    const content0 = result.content[0];
    if (content0.type === "text") {
      expect(content0.text).toMatch(/失败|错误|Error|boom/i);
    }
  });
});
