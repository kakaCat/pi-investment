import { createAgentDecisionTasks } from "./agent-decision-tasks.js";

describe("createAgentDecisionTasks", () => {
  const tasks = createAgentDecisionTasks();
  const byName = (n: string) => tasks.find(t => t.name === n);

  it("包含每周进化任务（周日 20:00）", () => {
    const weekly = byName("weekly_evolution");
    expect(weekly).toBeDefined();
    expect(weekly!.scheduleKind).toBe("cron");
    expect(weekly!.scheduleExpr).toBe("0 20 * * 0");
    expect((weekly!.payload as any).kind).toBe("weekly_evolution");
    expect(weekly!.enabled).toBe(true);
  });

  it("早盘任务固定唯一账本 agent_virtual", () => {
    const morning = byName("morning_ai_analysis");
    const msg = (morning!.payload as any).message as string;
    expect(msg).toContain("agent_virtual");
  });

  it("早盘任务包含昨日信号兜底检查", () => {
    const morning = byName("morning_ai_analysis");
    const msg = (morning!.payload as any).message as string;
    expect(msg).toContain("兜底");
    expect(msg).toContain("signals_ready");
  });

  it("日复盘包含信号处理覆盖率统计", () => {
    const review = byName("daily_ai_review");
    const msg = (review!.payload as any).message as string;
    expect(msg).toContain("覆盖率");
  });
});
