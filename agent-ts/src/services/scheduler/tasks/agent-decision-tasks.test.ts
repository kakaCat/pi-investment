import { createAgentDecisionTasks } from "./agent-decision-tasks.js";

describe("createAgentDecisionTasks", () => {
  const tasks = createAgentDecisionTasks();
  const byName = (n: string) => tasks.find(t => t.name === n);

  it("包含每周进化任务（周日 20:00）", () => {
    const weekly = byName("weekly_evolution");
    expect(weekly).toBeDefined();
    expect(weekly!.scheduleKind).toBe("cron");
    expect(weekly!.scheduleExpr).toBe("0 20 * * 0");
    expect(weekly!.enabled).toBe(true);
  });

  it("每周进化任务迁移为 evolution Agent 的 agent_turn（A2-T2）", () => {
    const weekly = byName("weekly_evolution");
    const payload = weekly!.payload as any;
    expect(payload.kind).toBe("agent_turn");
    expect(payload.agentKind).toBe("evolution");
    const msg = payload.message as string;
    expect(typeof msg).toBe("string");
    expect(msg.length).toBeGreaterThan(50);
  });

  it("每周进化任务提示词：仅提案、不自动执行、写入 evolution 域", () => {
    const weekly = byName("weekly_evolution");
    const msg = (weekly!.payload as any).message as string;
    expect(msg).toContain("evolution_run");
    expect(msg).toContain("evolution_leaderboard");
    expect(msg).toContain("不自动执行");
    expect(msg).toContain("evolution 域");
    expect(msg).toContain("零改动");
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

  it("日复盘包含进化适应度排行自评步骤", () => {
    const review = byName("daily_ai_review");
    const msg = (review!.payload as any).message as string;
    expect(msg).toContain("evolution_leaderboard");
    expect(msg).toContain("上涨捕获");
  });
});
