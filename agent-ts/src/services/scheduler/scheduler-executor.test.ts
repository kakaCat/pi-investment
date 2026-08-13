import { createSchedulerExecutor } from "./scheduler-executor.js";
import type { AgentKind } from "../../domain/agent-roles/types.js";
import type { SchedulerTask } from "./scheduler-service.js";

function taskWith(payload: Record<string, unknown>): SchedulerTask {
  return {
    id: "t1",
    name: "test",
    enabled: true,
    scheduleKind: "cron",
    scheduleExpr: "0 0 * * *",
    payload,
    compensationEnabled: false,
    compensationMaxAttempts: 0,
    deleteAfterRun: false,
    createdAt: "",
    updatedAt: "",
  };
}

function ctx(task: SchedulerTask) {
  return { task, run: {} as never, triggerType: "scheduled" as const };
}

describe("createSchedulerExecutor", () => {
  it("agent_turn 带 agentKind 时透传给 promptAgent（A2-T2）", async () => {
    const calls: Array<{ message: string; agentKind?: AgentKind }> = [];
    const executor = createSchedulerExecutor({
      promptAgent: async (message, agentKind) => {
        calls.push({ message, agentKind });
      },
    });

    await executor(ctx(taskWith({ kind: "agent_turn", message: "hi", agentKind: "evolution" })));

    expect(calls).toEqual([{ message: "hi", agentKind: "evolution" }]);
  });

  it("agent_turn 不带 agentKind 时透传 undefined（fin 现状）", async () => {
    const calls: Array<{ message: string; agentKind?: AgentKind }> = [];
    const executor = createSchedulerExecutor({
      promptAgent: async (message, agentKind) => {
        calls.push({ message, agentKind });
      },
    });

    await executor(ctx(taskWith({ kind: "agent_turn", message: "morning" })));

    expect(calls).toEqual([{ message: "morning", agentKind: undefined }]);
  });

  it("weekly_evolution 不再直接分派（已迁移为 agent_turn）", async () => {
    const executor = createSchedulerExecutor({ promptAgent: async () => {} });

    await expect(
      executor(ctx(taskWith({ kind: "weekly_evolution" }))),
    ).rejects.toThrow(/Unsupported scheduler payload kind/);
  });
});
