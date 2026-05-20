import { describe, expect, test } from "@jest/globals";
import { PostgresSchedulerStore, type Queryable } from "./postgres-scheduler-store.js";
import type { SchedulerRun, SchedulerTask } from "./scheduler-service.js";

class FakeDb implements Queryable {
  queries: Array<{ sql: string; params: unknown[] }> = [];
  tasks = new Map<string, SchedulerTask>();
  runs = new Map<string, SchedulerRun>();

  async query(sql: string, params: unknown[] = []): Promise<{ rows: unknown[] }> {
    this.queries.push({ sql, params });
    const normalized = sql.replace(/\s+/g, " ").trim();
    if (normalized.startsWith("CREATE TABLE")) {
      return { rows: [] };
    }
    if (normalized.startsWith("INSERT INTO scheduler_tasks")) {
      const task = rowToTask(params);
      this.tasks.set(task.id, task);
      return { rows: [taskToRow(task)] };
    }
    if (normalized.startsWith("UPDATE scheduler_tasks SET deleted_at")) {
      const [deletedAt, id] = params as [string, string];
      const task = this.tasks.get(id)!;
      task.deletedAt = deletedAt;
      task.enabled = false;
      task.updatedAt = deletedAt;
      return { rows: [] };
    }
    if (normalized.startsWith("SELECT * FROM scheduler_tasks WHERE id")) {
      const task = this.tasks.get(String(params[0]));
      return { rows: task ? [taskToRow(task)] : [] };
    }
    if (normalized.startsWith("SELECT * FROM scheduler_tasks")) {
      return { rows: Array.from(this.tasks.values()).map(taskToRow) };
    }
    if (normalized.startsWith("INSERT INTO scheduler_runs")) {
      const run = rowToRun(params);
      this.runs.set(run.id, run);
      return { rows: [runToRow(run)] };
    }
    if (normalized.startsWith("UPDATE scheduler_runs SET")) {
      const id = String(params[params.length - 1]);
      const run = this.runs.get(id)!;
      Object.assign(run, {
        status: params[0] as SchedulerRun["status"],
        triggeredAt: params[1] as string | undefined,
        startedAt: params[2] as string | undefined,
        finishedAt: params[3] as string | undefined,
        durationMs: params[4] as number | undefined,
        error: params[5] as string | undefined,
        compensationReason: params[6] as string | undefined,
        updatedAt: params[7] as string,
      });
      return { rows: [runToRow(run)] };
    }
    if (normalized.startsWith("SELECT * FROM scheduler_runs")) {
      return { rows: Array.from(this.runs.values()).map(runToRow) };
    }
    return { rows: [] };
  }
}

describe("PostgresSchedulerStore", () => {
  test("creates scheduler tables", async () => {
    const db = new FakeDb();
    const store = new PostgresSchedulerStore(db);

    await store.migrate();

    expect(db.queries.some((query) => query.sql.includes("CREATE TABLE IF NOT EXISTS scheduler_tasks"))).toBe(true);
    expect(db.queries.some((query) => query.sql.includes("CREATE TABLE IF NOT EXISTS scheduler_runs"))).toBe(true);
  });

  test("stores and reads scheduler tasks with json payload", async () => {
    const db = new FakeDb();
    const store = new PostgresSchedulerStore(db);

    await store.createTask({
      id: "task-1",
      name: "Delay task",
      enabled: true,
      scheduleKind: "delay",
      delaySeconds: 300,
      payload: { kind: "agent_turn", message: "check later" },
      compensationEnabled: false,
      compensationMaxAttempts: 1,
      deleteAfterRun: true,
      createdAt: "2026-05-20T01:00:00.000Z",
      updatedAt: "2026-05-20T01:00:00.000Z",
    });

    const loaded = await store.getTask("task-1");

    expect(loaded).toMatchObject({
      id: "task-1",
      scheduleKind: "delay",
      delaySeconds: 300,
      payload: { kind: "agent_turn", message: "check later" },
      deleteAfterRun: true,
    });
  });

  test("stores and updates run records", async () => {
    const db = new FakeDb();
    const store = new PostgresSchedulerStore(db);

    await store.createRun({
      id: "run-1",
      taskId: "task-1",
      taskName: "Task",
      scheduledFor: "2026-05-20T01:00:00.000Z",
      triggerType: "scheduled",
      status: "triggered",
      payload: { kind: "system_event" },
      createdAt: "2026-05-20T01:00:00.000Z",
      updatedAt: "2026-05-20T01:00:00.000Z",
    });
    const updated = await store.updateRun("run-1", {
      status: "success",
      finishedAt: "2026-05-20T01:01:00.000Z",
      durationMs: 60000,
      updatedAt: "2026-05-20T01:01:00.000Z",
    });

    expect(updated).toMatchObject({
      id: "run-1",
      status: "success",
      durationMs: 60000,
    });
    expect(await store.listRuns({ taskId: "task-1" })).toHaveLength(1);
  });
});

function taskToRow(task: SchedulerTask) {
  return {
    id: task.id,
    name: task.name,
    enabled: task.enabled,
    schedule_kind: task.scheduleKind,
    schedule_expr: task.scheduleExpr,
    schedule_at: task.scheduleAt,
    every_seconds: task.everySeconds,
    delay_seconds: task.delaySeconds,
    anchor_at: task.anchorAt,
    payload: task.payload,
    compensation_enabled: task.compensationEnabled,
    compensation_check_after: task.compensationCheckAfter,
    compensation_max_attempts: task.compensationMaxAttempts,
    delete_after_run: task.deleteAfterRun,
    created_at: task.createdAt,
    updated_at: task.updatedAt,
    deleted_at: task.deletedAt,
  };
}

function rowToTask(params: unknown[]): SchedulerTask {
  return {
    id: String(params[0]),
    name: String(params[1]),
    enabled: Boolean(params[2]),
    scheduleKind: params[3] as SchedulerTask["scheduleKind"],
    scheduleExpr: params[4] as string | undefined,
    scheduleAt: params[5] as string | undefined,
    everySeconds: params[6] as number | undefined,
    delaySeconds: params[7] as number | undefined,
    anchorAt: params[8] as string | undefined,
    payload: params[9] as Record<string, unknown>,
    compensationEnabled: Boolean(params[10]),
    compensationCheckAfter: params[11] as string | undefined,
    compensationMaxAttempts: Number(params[12]),
    deleteAfterRun: Boolean(params[13]),
    createdAt: String(params[14]),
    updatedAt: String(params[15]),
    deletedAt: params[16] as string | undefined,
  };
}

function runToRow(run: SchedulerRun) {
  return {
    id: run.id,
    task_id: run.taskId,
    task_name: run.taskName,
    scheduled_for: run.scheduledFor,
    trigger_type: run.triggerType,
    status: run.status,
    triggered_at: run.triggeredAt,
    started_at: run.startedAt,
    finished_at: run.finishedAt,
    duration_ms: run.durationMs,
    error: run.error,
    compensation_reason: run.compensationReason,
    payload: run.payload,
    created_at: run.createdAt,
    updated_at: run.updatedAt,
  };
}

function rowToRun(params: unknown[]): SchedulerRun {
  return {
    id: String(params[0]),
    taskId: String(params[1]),
    taskName: String(params[2]),
    scheduledFor: String(params[3]),
    triggerType: params[4] as SchedulerRun["triggerType"],
    status: params[5] as SchedulerRun["status"],
    triggeredAt: params[6] as string | undefined,
    startedAt: params[7] as string | undefined,
    finishedAt: params[8] as string | undefined,
    durationMs: params[9] as number | undefined,
    error: params[10] as string | undefined,
    compensationReason: params[11] as string | undefined,
    payload: params[12] as Record<string, unknown>,
    createdAt: String(params[13]),
    updatedAt: String(params[14]),
  };
}
