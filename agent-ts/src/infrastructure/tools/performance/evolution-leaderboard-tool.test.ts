/**
 * Evolution Leaderboard Tool - 测试
 * 模式跟随 chan-analyze-tool.test.ts（@jest/globals + unstable_mockModule）。
 */
import { beforeEach, describe, expect, it, jest } from "@jest/globals";

const mockRun = jest.fn<(...args: any[]) => Promise<any>>();

jest.unstable_mockModule("../../adapters/quant/quant-v2-client.js", () => ({
  runQuantV2: mockRun,
}));

const { evolutionLeaderboardTool } = await import("./evolution-leaderboard-tool.js");

beforeEach(() => { mockRun.mockReset(); });

describe("evolution_leaderboard", () => {
  it("格式化排行榜含排名/适应度/捕获明细", async () => {
    mockRun.mockResolvedValue({
      ok: true, command: "evolution.leaderboard",
      data: {
        windowEnd: "2026-08-05", windowDays: 20,
        ranking: [
          { rank: 1, accountName: "agent_virtual", fitness: 0.7,
            upCapture: 1.2, downCapture: 0.5, upDays: 10, downDays: 7, status: "ok" },
          { rank: 2, accountName: "v14_simulation", fitness: -0.7,
            upCapture: 0.8, downCapture: 1.5, upDays: 10, downDays: 7, status: "ok" },
        ],
      },
    });
    const result = await evolutionLeaderboardTool.execute("t1", {});
    const text = (result.content[0] as any).text;
    expect(mockRun).toHaveBeenCalledWith("evolution.leaderboard", { window: 20 });
    expect(text).toContain("agent_virtual");
    expect(text).toContain("0.70");
    expect(text).toContain("上涨捕获 1.20");
    expect(text).toContain("下跌捕获 0.50");
  });

  it("空排行返回引导文案", async () => {
    mockRun.mockResolvedValue({
      ok: true, command: "evolution.leaderboard",
      data: { windowEnd: null, ranking: [], message: "尚无适应度数据" },
    });
    const result = await evolutionLeaderboardTool.execute("t2", {});
    expect((result.content[0] as any).text).toContain("尚无适应度数据");
  });

  it("v2 错误返回 success=false", async () => {
    mockRun.mockRejectedValue(new Error("connect ECONNREFUSED"));
    const result = await evolutionLeaderboardTool.execute("t3", {});
    expect((result.details as any).success).toBe(false);
  });
});
