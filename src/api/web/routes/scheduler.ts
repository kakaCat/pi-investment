import { randomUUID } from "node:crypto";
import { Router } from "express";
import { requireOpsAuth } from "../middleware/ops-auth.js";
import { getSchedulerRuntime } from "../../../services/scheduler/scheduler-runtime.js";
import type { ScheduleKind, SchedulerTask } from "../../../services/scheduler/scheduler-service.js";

const router = Router();

router.get("/tasks", async (_req, res, next) => {
  try {
    const { service } = await getSchedulerRuntime();
    res.json({ success: true, tasks: await service.listTaskSummaries() });
  } catch (error) {
    next(error);
  }
});

router.post("/tasks", requireOpsAuth(), async (req, res, next) => {
  try {
    const { store, service } = await getSchedulerRuntime();
    const now = new Date().toISOString();
    const task = normalizeTask(req.body ?? {}, now);
    const created = await store.createTask(task);
    await service.reloadTasks();
    res.status(201).json({ success: true, data: created });
  } catch (error) {
    next(error);
  }
});

router.put("/tasks/:id", requireOpsAuth(), async (req, res, next) => {
  try {
    const { store, service } = await getSchedulerRuntime();
    const updated = await store.updateTask(String(req.params.id), {
      ...req.body,
      updatedAt: new Date().toISOString(),
    });
    await service.reloadTasks();
    res.json({ success: true, data: updated });
  } catch (error) {
    next(error);
  }
});

router.post("/tasks/:id/enable", requireOpsAuth(), async (req, res, next) => {
  try {
    const { store, service } = await getSchedulerRuntime();
    const updated = await store.updateTask(String(req.params.id), {
      enabled: true,
      updatedAt: new Date().toISOString(),
    });
    await service.reloadTasks();
    res.json({ success: true, data: updated });
  } catch (error) {
    next(error);
  }
});

router.post("/tasks/:id/disable", requireOpsAuth(), async (req, res, next) => {
  try {
    const { store, service } = await getSchedulerRuntime();
    const updated = await store.updateTask(String(req.params.id), {
      enabled: false,
      updatedAt: new Date().toISOString(),
    });
    await service.reloadTasks();
    res.json({ success: true, data: updated });
  } catch (error) {
    next(error);
  }
});

router.delete("/tasks/:id", requireOpsAuth(), async (req, res, next) => {
  try {
    const { store, service } = await getSchedulerRuntime();
    await store.softDeleteTask(String(req.params.id), new Date().toISOString());
    await service.reloadTasks();
    res.json({ success: true });
  } catch (error) {
    next(error);
  }
});

router.get("/tasks/:id/runs", async (req, res, next) => {
  try {
    const { store } = await getSchedulerRuntime();
    const limit = req.query.limit ? Number(req.query.limit) : 50;
    res.json({ success: true, runs: await store.listRuns({ taskId: String(req.params.id), limit }) });
  } catch (error) {
    next(error);
  }
});

router.get("/runs", async (req, res, next) => {
  try {
    const { store } = await getSchedulerRuntime();
    const limit = req.query.limit ? Number(req.query.limit) : 100;
    const date = typeof req.query.date === "string" ? req.query.date : undefined;
    res.json({ success: true, runs: await store.listRuns({ date, limit }) });
  } catch (error) {
    next(error);
  }
});

router.get("/runs/failed", async (req, res, next) => {
  try {
    const { store } = await getSchedulerRuntime();
    const limit = req.query.limit ? Number(req.query.limit) : 50;
    const date = typeof req.query.date === "string" ? req.query.date : undefined;
    const runs = await store.listRuns({ date, limit: Math.max(limit * 3, limit) });
    const failed = runs
      .filter((run) => ["failed", "missed", "skipped", "compensation_failed"].includes(run.status))
      .slice(0, limit);
    res.json({ success: true, count: failed.length, runs: failed });
  } catch (error) {
    next(error);
  }
});

router.post("/tasks/:id/trigger", requireOpsAuth(), async (req, res, next) => {
  try {
    const { service } = await getSchedulerRuntime();
    res.json({ success: true, data: await service.triggerTask(String(req.params.id), "manual") });
  } catch (error) {
    next(error);
  }
});

router.post("/tasks/:id/compensate", requireOpsAuth(), async (req, res, next) => {
  try {
    const { service } = await getSchedulerRuntime();
    res.json({ success: true, data: await service.triggerTask(String(req.params.id), "compensation") });
  } catch (error) {
    next(error);
  }
});

function normalizeTask(input: Record<string, unknown>, now: string): SchedulerTask {
  const scheduleKind = input.scheduleKind as ScheduleKind;
  if (!["cron", "every", "at", "delay"].includes(scheduleKind)) {
    throw new Error("scheduleKind must be cron, every, at, or delay");
  }
  return {
    id: String(input.id || randomUUID().slice(0, 12)),
    name: String(input.name || "未命名定时任务"),
    enabled: input.enabled !== false,
    scheduleKind,
    scheduleExpr: optionalString(input.scheduleExpr),
    scheduleAt: optionalString(input.scheduleAt),
    everySeconds: optionalNumber(input.everySeconds),
    delaySeconds: optionalNumber(input.delaySeconds),
    anchorAt: optionalString(input.anchorAt),
    payload: isRecord(input.payload) ? input.payload : {},
    compensationEnabled: input.compensationEnabled === true,
    compensationCheckAfter: optionalString(input.compensationCheckAfter),
    compensationMaxAttempts: optionalNumber(input.compensationMaxAttempts) ?? 1,
    deleteAfterRun: input.deleteAfterRun === true,
    createdAt: now,
    updatedAt: now,
  };
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function optionalNumber(value: unknown): number | undefined {
  if (value === undefined || value === null || value === "") {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export { router as schedulerRouter };
