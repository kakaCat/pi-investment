import { describe, expect, jest, test } from "@jest/globals";
import {
  InMemorySchedulerStore,
  SchedulerService,
  type SchedulerExecutor,
  type SchedulerTask,
} from "./scheduler-service.js";

function task(overrides: Partial<SchedulerTask> = {}): SchedulerTask {
  return {
    id: "task-1",
    name: "Test task",
    enabled: true,
    scheduleKind: "delay",
    delaySeconds: 60,
    payload: { kind: "agent_turn", message: "run test task" },
    compensationEnabled: false,
    compensationMaxAttempts: 1,
    deleteAfterRun: false,
    createdAt: "2026-05-20T01:00:00.000Z",
    updatedAt: "2026-05-20T01:00:00.000Z",
    ...overrides,
  };
}

describe("SchedulerService", () => {
  test("fires a due delay task and records the full run lifecycle", async () => {
    const store = new InMemorySchedulerStore([
      task({ anchorAt: "2026-05-20T01:00:00.000Z", deleteAfterRun: true }),
    ]);
    const executed: unknown[] = [];
    const executor: SchedulerExecutor = async ({ task }) => {
      executed.push(task.payload);
      return { ok: true };
    };
    const service = new SchedulerService({
      store,
      executor,
      now: () => new Date("2026-05-20T01:01:00.000Z"),
      idGenerator: () => "run-1",
    });

    await service.reloadTasks();
    await service.tick();

    expect(executed).toEqual([{ kind: "agent_turn", message: "run test task" }]);
    const runs = await store.listRuns({ taskId: "task-1" });
    expect(runs).toHaveLength(1);
    expect(runs[0]).toMatchObject({
      id: "run-1",
      taskId: "task-1",
      taskName: "Test task",
      triggerType: "scheduled",
      status: "success",
      scheduledFor: "2026-05-20T01:01:00.000Z",
      triggeredAt: "2026-05-20T01:01:00.000Z",
      startedAt: "2026-05-20T01:01:00.000Z",
      finishedAt: "2026-05-20T01:01:00.000Z",
      payload: { kind: "agent_turn", message: "run test task" },
    });
    expect((await store.listTasks({ includeDeleted: true }))[0].deletedAt).toBe("2026-05-20T01:01:00.000Z");
  });

  test("records failed scheduled tasks with the error message", async () => {
    const store = new InMemorySchedulerStore([
      task({ scheduleKind: "at", scheduleAt: "2026-05-20T01:00:00.000Z" }),
    ]);
    const service = new SchedulerService({
      store,
      executor: async () => {
        throw new Error("boom");
      },
      now: () => new Date("2026-05-20T01:00:00.000Z"),
      idGenerator: () => "run-1",
    });

    await service.reloadTasks();
    await service.tick();

    const runs = await store.listRuns({ taskId: "task-1" });
    expect(runs[0]).toMatchObject({
      triggerType: "scheduled",
      status: "failed",
      error: "boom",
    });
  });

  test("compensates a daily task that missed today's scheduled run", async () => {
    const store = new InMemorySchedulerStore([
      task({
        scheduleKind: "cron",
        scheduleExpr: "30 8 * * 1-5",
        compensationEnabled: true,
        compensationCheckAfter: "09:30",
        compensationMaxAttempts: 1,
      }),
    ]);
    const executor = jest.fn<() => Promise<void>>().mockResolvedValue(undefined);
    const service = new SchedulerService({
      store,
      executor: async () => executor(),
      now: () => new Date("2026-05-20T02:00:00.000Z"),
      idGenerator: (() => {
        const ids = ["missed-1", "run-1"];
        return () => ids.shift() ?? "run-x";
      })(),
    });

    await service.reloadTasks();
    await service.scanCompensations();

    const runs = await store.listRuns({ taskId: "task-1" });
    expect(runs.map((run) => [run.id, run.triggerType, run.status])).toEqual([
      ["missed-1", "compensation", "missed"],
      ["run-1", "compensation", "compensated"],
    ]);
    expect(runs[1].compensationReason).toBe("missed scheduled run for 2026-05-20");
    expect(executor).toHaveBeenCalledTimes(1);
  });

  test("does not compensate when today's task already succeeded", async () => {
    const store = new InMemorySchedulerStore([
      task({
        scheduleKind: "cron",
        scheduleExpr: "30 8 * * 1-5",
        compensationEnabled: true,
        compensationCheckAfter: "09:30",
      }),
    ]);
    await store.createRun({
      id: "existing",
      taskId: "task-1",
      taskName: "Test task",
      scheduledFor: "2026-05-20T00:30:00.000Z",
      triggerType: "scheduled",
      status: "success",
      payload: {},
      createdAt: "2026-05-20T00:31:00.000Z",
      updatedAt: "2026-05-20T00:31:00.000Z",
    });
    const executor = jest.fn<() => Promise<void>>().mockResolvedValue(undefined);
    const service = new SchedulerService({
      store,
      executor: async () => executor(),
      now: () => new Date("2026-05-20T02:00:00.000Z"),
    });

    await service.reloadTasks();
    await service.scanCompensations();

    expect(executor).not.toHaveBeenCalled();
    expect(await store.listRuns({ taskId: "task-1" })).toHaveLength(1);
  });

  test("manual trigger records trigger_type manual", async () => {
    const store = new InMemorySchedulerStore([task()]);
    const service = new SchedulerService({
      store,
      executor: async () => undefined,
      now: () => new Date("2026-05-20T03:00:00.000Z"),
      idGenerator: () => "manual-1",
    });

    await service.reloadTasks();
    const run = await service.triggerTask("task-1", "manual");

    expect(run).toMatchObject({
      id: "manual-1",
      triggerType: "manual",
      status: "success",
    });
  });
});
