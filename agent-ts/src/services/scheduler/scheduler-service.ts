export type ScheduleKind = "cron" | "every" | "at" | "delay";
export type SchedulerTriggerType = "scheduled" | "manual" | "compensation";
export type SchedulerRunStatus =
  | "triggered"
  | "running"
  | "success"
  | "failed"
  | "skipped"
  | "missed"
  | "compensated"
  | "compensation_failed";

export interface SchedulerTask {
  id: string;
  name: string;
  enabled: boolean;
  scheduleKind: ScheduleKind;
  scheduleExpr?: string;
  scheduleAt?: string;
  everySeconds?: number;
  delaySeconds?: number;
  anchorAt?: string;
  payload: Record<string, unknown>;
  compensationEnabled: boolean;
  compensationCheckAfter?: string;
  compensationMaxAttempts: number;
  deleteAfterRun: boolean;
  createdAt: string;
  updatedAt: string;
  deletedAt?: string;
}

export interface SchedulerRun {
  id: string;
  taskId: string;
  taskName: string;
  scheduledFor: string;
  triggerType: SchedulerTriggerType;
  status: SchedulerRunStatus;
  triggeredAt?: string;
  startedAt?: string;
  finishedAt?: string;
  durationMs?: number;
  error?: string;
  compensationReason?: string;
  payload: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface SchedulerTaskSummary extends SchedulerTask {
  nextRunAt: string | null;
  lastRun?: SchedulerRun;
  todayTriggered: boolean;
  todaySuccess: boolean;
  compensationDue: boolean;
}

export interface SchedulerStore {
  listTasks(options?: { enabledOnly?: boolean; includeDeleted?: boolean }): Promise<SchedulerTask[]>;
  getTask(id: string): Promise<SchedulerTask | undefined>;
  createTask(task: SchedulerTask): Promise<SchedulerTask>;
  updateTask(id: string, updates: Partial<SchedulerTask>): Promise<SchedulerTask>;
  softDeleteTask(id: string, deletedAt: string): Promise<void>;
  createRun(run: SchedulerRun): Promise<SchedulerRun>;
  updateRun(id: string, updates: Partial<SchedulerRun>): Promise<SchedulerRun>;
  listRuns(options?: { taskId?: string; date?: string; limit?: number }): Promise<SchedulerRun[]>;
}

export interface SchedulerExecutionContext {
  task: SchedulerTask;
  run: SchedulerRun;
  triggerType: SchedulerTriggerType;
}

export type SchedulerExecutor = (context: SchedulerExecutionContext) => unknown | Promise<unknown>;

export interface SchedulerServiceOptions {
  store: SchedulerStore;
  executor: SchedulerExecutor;
  now?: () => Date;
  idGenerator?: () => string;
  /**
   * Misfire grace period in milliseconds (default: 5 minutes)
   * Tasks scheduled more than this duration in the past will be skipped
   * and rescheduled to the next period instead of executing immediately.
   *
   * This follows the misfire handling pattern from OpenClaw's isolated-agent,
   * where expired tasks are not "caught up" but rather rescheduled to avoid
   * executing stale work after system downtime.
   */
  misfireGracePeriodMs?: number;
  /**
   * Maximum execution timeout per task in milliseconds (default: 60 minutes)
   * Tasks exceeding this duration will be marked as failed.
   */
  taskTimeoutMs?: number;
}

interface LoadedTask {
  task: SchedulerTask;
  nextRunAt: number | null;
}

export class SchedulerService {
  private readonly store: SchedulerStore;
  private readonly executor: SchedulerExecutor;
  private readonly now: () => Date;
  private readonly idGenerator: () => string;
  private readonly loadedTasks = new Map<string, LoadedTask>();
  private readonly runningTaskIds = new Set<string>();
  private readonly taskTimeouts = new Map<string, ReturnType<typeof setTimeout>>();
  private ticker: ReturnType<typeof setInterval> | null = null;
  private readonly misfireGracePeriodMs: number;
  private readonly taskTimeoutMs: number;

  constructor(options: SchedulerServiceOptions) {
    this.store = options.store;
    this.executor = options.executor;
    this.now = options.now ?? (() => new Date());
    this.idGenerator = options.idGenerator ?? (() => `run-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`);
    this.misfireGracePeriodMs = options.misfireGracePeriodMs ?? 5 * 60 * 1000; // 5 minutes
    this.taskTimeoutMs = options.taskTimeoutMs ?? 60 * 60 * 1000; // 60 minutes
  }

  async reloadTasks(): Promise<void> {
    const tasks = await this.store.listTasks({ enabledOnly: true });
    this.loadedTasks.clear();
    const nowMs = this.now().getTime();
    for (const task of tasks) {
      this.loadedTasks.set(task.id, {
        task,
        nextRunAt: computeNextRunAt(task, nowMs),
      });
    }
  }

  start(): void {
    if (this.ticker) {
      return;
    }
    this.ticker = setInterval(() => {
      void this.tick();
      void this.scanCompensations();
    }, 1000);
    this.ticker.unref?.();
  }

  stop(): void {
    if (!this.ticker) {
      return;
    }
    clearInterval(this.ticker);
    this.ticker = null;
    // Clear all timeout watchdogs
    for (const timeout of this.taskTimeouts.values()) {
      clearTimeout(timeout);
    }
    this.taskTimeouts.clear();
  }

  async tick(): Promise<void> {
    const now = this.now();
    for (const loaded of this.loadedTasks.values()) {
      if (!loaded.nextRunAt || now.getTime() < loaded.nextRunAt) {
        continue;
      }
      if (this.runningTaskIds.has(loaded.task.id)) {
        await this.recordMissedOrSkipped(loaded.task, new Date(loaded.nextRunAt), "skipped", "task already running");
        loaded.nextRunAt = computeNextRunAt(loaded.task, now.getTime());
        continue;
      }

      const scheduledFor = new Date(loaded.nextRunAt);
      const delayMs = now.getTime() - loaded.nextRunAt;

      // Misfire detection: if task is more than grace period late, skip it
      // This prevents executing stale work after system downtime or long pauses
      // Following OpenClaw's isolated-agent pattern: expired tasks reschedule, don't catch up
      if (delayMs > this.misfireGracePeriodMs) {
        await this.recordMissedOrSkipped(
          loaded.task,
          scheduledFor,
          "skipped",
          `misfire: task expired by ${Math.round(delayMs / 1000)}s (grace period: ${Math.round(this.misfireGracePeriodMs / 1000)}s)`
        );
        loaded.nextRunAt = computeNextRunAt(loaded.task, now.getTime());
        continue;
      }

      await this.executeTask(loaded.task, "scheduled", scheduledFor);
      if (loaded.task.deleteAfterRun || loaded.task.scheduleKind === "delay") {
        await this.store.softDeleteTask(loaded.task.id, iso(now));
        this.loadedTasks.delete(loaded.task.id);
      } else {
        loaded.nextRunAt = computeNextRunAt(loaded.task, now.getTime());
      }
    }
  }

  async triggerTask(taskId: string, triggerType: SchedulerTriggerType = "manual"): Promise<SchedulerRun> {
    const task = await this.store.getTask(taskId);
    if (!task || task.deletedAt) {
      throw new Error(`Scheduler task not found: ${taskId}`);
    }
    return this.executeTask(task, triggerType, this.now());
  }

  async scanCompensations(): Promise<void> {
    const now = this.now();
    const tasks = await this.store.listTasks({ enabledOnly: true });
    for (const task of tasks) {
      if (!task.compensationEnabled || !task.compensationCheckAfter || task.scheduleKind !== "cron") {
        continue;
      }
      if (!wasCronDueToday(task, now) || !isAfterTimeOfDay(now, task.compensationCheckAfter)) {
        continue;
      }

      const today = localDateKey(now);
      const runs = await this.store.listRuns({ taskId: task.id, date: today });
      const alreadySatisfied = runs.some((run) =>
        ["success", "compensated", "running", "triggered"].includes(run.status)
      );
      if (alreadySatisfied) {
        continue;
      }
      const compensationAttempts = runs.filter((run) => run.triggerType === "compensation" && run.status !== "missed").length;
      if (compensationAttempts >= task.compensationMaxAttempts) {
        continue;
      }

      const reason = `missed scheduled run for ${today}`;
      await this.recordMissedOrSkipped(task, now, "missed", reason, "compensation");
      const run = await this.executeTask(task, "compensation", now, reason);
      if (run.status === "success") {
        await this.store.updateRun(run.id, { status: "compensated", updatedAt: iso(this.now()) });
      } else if (run.status === "failed") {
        await this.store.updateRun(run.id, { status: "compensation_failed", updatedAt: iso(this.now()) });
      }
    }
  }

  async listTaskSummaries(): Promise<SchedulerTaskSummary[]> {
    const tasks = await this.store.listTasks();
    const today = localDateKey(this.now());
    return Promise.all(tasks.map(async (task) => {
      const runs = await this.store.listRuns({ taskId: task.id, limit: 50 });
      const todayRuns = runs.filter((run) => localDateKey(new Date(run.scheduledFor)) === today);
      const loaded = this.loadedTasks.get(task.id);
      return {
        ...task,
        nextRunAt: loaded?.nextRunAt ? iso(new Date(loaded.nextRunAt)) : null,
        lastRun: runs[0],
        todayTriggered: todayRuns.some((run) => ["triggered", "running", "success", "failed", "compensated"].includes(run.status)),
        todaySuccess: todayRuns.some((run) => ["success", "compensated"].includes(run.status)),
        compensationDue: task.compensationEnabled && todayRuns.some((run) => run.status === "missed"),
      };
    }));
  }

  private async executeTask(
    task: SchedulerTask,
    triggerType: SchedulerTriggerType,
    scheduledFor: Date,
    compensationReason?: string,
  ): Promise<SchedulerRun> {
    const now = this.now();
    let run = await this.store.createRun({
      id: this.idGenerator(),
      taskId: task.id,
      taskName: task.name,
      scheduledFor: iso(scheduledFor),
      triggerType,
      status: "triggered",
      triggeredAt: iso(now),
      payload: task.payload,
      compensationReason,
      createdAt: iso(now),
      updatedAt: iso(now),
    });

    this.runningTaskIds.add(task.id);
    const startedAt = this.now();
    run = await this.store.updateRun(run.id, {
      status: "running",
      startedAt: iso(startedAt),
      updatedAt: iso(startedAt),
    });

    // Watchdog: set timeout to mark task as failed if it exceeds taskTimeoutMs
    let timedOut = false;
    const timeoutHandle = setTimeout(async () => {
      timedOut = true;
      const timeoutAt = this.now();
      console.error(`[SchedulerService] Task ${task.name} (${task.id}) exceeded timeout of ${this.taskTimeoutMs}ms`);
      try {
        await this.store.updateRun(run.id, {
          status: "failed",
          finishedAt: iso(timeoutAt),
          durationMs: Math.max(0, timeoutAt.getTime() - startedAt.getTime()),
          error: `Task execution exceeded timeout of ${Math.round(this.taskTimeoutMs / 1000)}s`,
          updatedAt: iso(timeoutAt),
        });
      } catch (error) {
        console.error(`[SchedulerService] Failed to update run after timeout:`, error);
      }
      this.runningTaskIds.delete(task.id);
    }, this.taskTimeoutMs);

    this.taskTimeouts.set(task.id, timeoutHandle);

    try {
      await this.executor({ task, run, triggerType });

      // Clear the timeout if task completes before timeout
      clearTimeout(timeoutHandle);
      this.taskTimeouts.delete(task.id);

      // Don't update if already timed out
      if (timedOut) {
        return run;
      }

      const finishedAt = this.now();
      return this.store.updateRun(run.id, {
        status: "success",
        finishedAt: iso(finishedAt),
        durationMs: Math.max(0, finishedAt.getTime() - startedAt.getTime()),
        updatedAt: iso(finishedAt),
      });
    } catch (error) {
      clearTimeout(timeoutHandle);
      this.taskTimeouts.delete(task.id);

      if (timedOut) {
        return run;
      }

      const finishedAt = this.now();
      return this.store.updateRun(run.id, {
        status: "failed",
        finishedAt: iso(finishedAt),
        durationMs: Math.max(0, finishedAt.getTime() - startedAt.getTime()),
        error: error instanceof Error ? error.message : String(error),
        updatedAt: iso(finishedAt),
      });
    } finally {
      this.runningTaskIds.delete(task.id);
    }
  }

  private async recordMissedOrSkipped(
    task: SchedulerTask,
    scheduledFor: Date,
    status: "missed" | "skipped",
    reason: string,
    triggerType: SchedulerTriggerType = "scheduled",
  ): Promise<SchedulerRun> {
    const now = this.now();
    return this.store.createRun({
      id: this.idGenerator(),
      taskId: task.id,
      taskName: task.name,
      scheduledFor: iso(scheduledFor),
      triggerType,
      status,
      error: status === "skipped" ? reason : undefined,
      compensationReason: status === "missed" ? reason : undefined,
      payload: task.payload,
      createdAt: iso(now),
      updatedAt: iso(now),
    });
  }
}

export class InMemorySchedulerStore implements SchedulerStore {
  private tasks = new Map<string, SchedulerTask>();
  private runs = new Map<string, SchedulerRun>();

  constructor(tasks: SchedulerTask[] = []) {
    for (const task of tasks) {
      this.tasks.set(task.id, { ...task });
    }
  }

  async listTasks(options: { enabledOnly?: boolean; includeDeleted?: boolean } = {}): Promise<SchedulerTask[]> {
    return Array.from(this.tasks.values())
      .filter((task) => options.includeDeleted || !task.deletedAt)
      .filter((task) => !options.enabledOnly || task.enabled)
      .map((task) => ({ ...task, payload: { ...task.payload } }));
  }

  async getTask(id: string): Promise<SchedulerTask | undefined> {
    const task = this.tasks.get(id);
    return task ? { ...task, payload: { ...task.payload } } : undefined;
  }

  async createTask(task: SchedulerTask): Promise<SchedulerTask> {
    this.tasks.set(task.id, { ...task, payload: { ...task.payload } });
    return { ...task, payload: { ...task.payload } };
  }

  async updateTask(id: string, updates: Partial<SchedulerTask>): Promise<SchedulerTask> {
    const existing = this.tasks.get(id);
    if (!existing) {
      throw new Error(`Scheduler task not found: ${id}`);
    }
    const updated = { ...existing, ...updates, payload: updates.payload ?? existing.payload };
    this.tasks.set(id, updated);
    return { ...updated, payload: { ...updated.payload } };
  }

  async softDeleteTask(id: string, deletedAt: string): Promise<void> {
    await this.updateTask(id, { enabled: false, deletedAt, updatedAt: deletedAt });
  }

  async createRun(run: SchedulerRun): Promise<SchedulerRun> {
    this.runs.set(run.id, { ...run, payload: { ...run.payload } });
    return { ...run, payload: { ...run.payload } };
  }

  async updateRun(id: string, updates: Partial<SchedulerRun>): Promise<SchedulerRun> {
    const existing = this.runs.get(id);
    if (!existing) {
      throw new Error(`Scheduler run not found: ${id}`);
    }
    const updated = { ...existing, ...updates, payload: updates.payload ?? existing.payload };
    this.runs.set(id, updated);
    return { ...updated, payload: { ...updated.payload } };
  }

  async listRuns(options: { taskId?: string; date?: string; limit?: number } = {}): Promise<SchedulerRun[]> {
    const runs = Array.from(this.runs.values())
      .filter((run) => !options.taskId || run.taskId === options.taskId)
      .filter((run) => !options.date || localDateKey(new Date(run.scheduledFor)) === options.date)
      .sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt));
    return runs.slice(0, options.limit ?? runs.length).map((run) => ({ ...run, payload: { ...run.payload } }));
  }
}

export function computeNextRunAt(task: SchedulerTask, fromMs: number): number | null {
  if (!task.enabled || task.deletedAt) {
    return null;
  }
  if (task.scheduleKind === "at") {
    if (!task.scheduleAt) {
      return null;
    }
    const at = Date.parse(task.scheduleAt);
    return Number.isFinite(at) && at >= fromMs ? at : null;
  }
  if (task.scheduleKind === "delay") {
    const anchor = Date.parse(task.anchorAt ?? task.createdAt);
    const delayMs = (task.delaySeconds ?? 0) * 1000;
    const due = anchor + delayMs;
    return Number.isFinite(due) ? due : null;
  }
  if (task.scheduleKind === "every") {
    const everyMs = (task.everySeconds ?? 3600) * 1000;
    const anchor = Date.parse(task.anchorAt ?? task.createdAt);
    if (!Number.isFinite(anchor) || everyMs <= 0) {
      return null;
    }
    if (fromMs < anchor) {
      return anchor;
    }
    return anchor + (Math.floor((fromMs - anchor) / everyMs) + 1) * everyMs;
  }
  if (task.scheduleKind === "cron") {
    return task.scheduleExpr ? nextCronRunMs(task.scheduleExpr, fromMs) : null;
  }
  return null;
}

type CronFields = {
  minute: number[];
  hour: number[];
  dayOfMonth: number[];
  month: number[];
  dayOfWeek: number[];
};

function nextCronRunMs(expr: string, fromMs: number): number | null {
  const fields = parseCronExpression(expr);
  if (!fields) {
    return null;
  }
  const next = computeNextCronRun(fields, new Date(fromMs));
  return next ? next.getTime() : null;
}

function parseCronExpression(expr: string): CronFields | null {
  const ranges = [
    [0, 59],
    [0, 23],
    [1, 31],
    [1, 12],
    [0, 6],
  ] as const;
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) {
    return null;
  }
  const expanded = parts.map((part, index) => expandCronField(part, ranges[index][0], ranges[index][1]));
  if (expanded.some((part) => !part)) {
    return null;
  }
  return {
    minute: expanded[0]!,
    hour: expanded[1]!,
    dayOfMonth: expanded[2]!,
    month: expanded[3]!,
    dayOfWeek: expanded[4]!,
  };
}

function expandCronField(field: string, min: number, max: number): number[] | null {
  const values = new Set<number>();
  for (const part of field.split(",")) {
    const [rangePart, stepPart] = part.split("/");
    const step = stepPart ? Number.parseInt(stepPart, 10) : 1;
    if (!Number.isInteger(step) || step < 1) {
      return null;
    }
    if (rangePart === "*") {
      for (let value = min; value <= max; value += step) {
        values.add(value);
      }
      continue;
    }
    if (rangePart?.includes("-")) {
      const [rawStart, rawEnd] = rangePart.split("-");
      const start = Number.parseInt(rawStart, 10);
      const end = Number.parseInt(rawEnd, 10);
      if (!Number.isInteger(start) || !Number.isInteger(end) || start > end) {
        return null;
      }
      for (let value = start; value <= end; value += step) {
        const normalized = normalizeCronValue(value, min, max);
        if (normalized === null) {
          return null;
        }
        values.add(normalized);
      }
      continue;
    }
    const value = Number.parseInt(rangePart ?? "", 10);
    const normalized = normalizeCronValue(value, min, max);
    if (normalized === null) {
      return null;
    }
    values.add(normalized);
  }
  return Array.from(values).sort((left, right) => left - right);
}

function normalizeCronValue(value: number, min: number, max: number): number | null {
  if (min === 0 && max === 6 && value === 7) {
    return 0;
  }
  if (!Number.isInteger(value) || value < min || value > max) {
    return null;
  }
  return value;
}

function computeNextCronRun(fields: CronFields, from: Date): Date | null {
  const minuteSet = new Set(fields.minute);
  const hourSet = new Set(fields.hour);
  const domSet = new Set(fields.dayOfMonth);
  const monthSet = new Set(fields.month);
  const dowSet = new Set(fields.dayOfWeek);
  const domWild = fields.dayOfMonth.length === 31;
  const dowWild = fields.dayOfWeek.length === 7;
  const candidate = new Date(from.getTime());
  candidate.setSeconds(0, 0);
  candidate.setMinutes(candidate.getMinutes() + 1);

  for (let index = 0; index < 366 * 24 * 60; index++) {
    const month = candidate.getMonth() + 1;
    const dom = candidate.getDate();
    const dow = candidate.getDay();
    const dayMatches = domWild && dowWild
      ? true
      : domWild
        ? dowSet.has(dow)
        : dowWild
          ? domSet.has(dom)
          : domSet.has(dom) || dowSet.has(dow);
    if (
      monthSet.has(month) &&
      dayMatches &&
      hourSet.has(candidate.getHours()) &&
      minuteSet.has(candidate.getMinutes())
    ) {
      return candidate;
    }
    candidate.setMinutes(candidate.getMinutes() + 1);
  }
  return null;
}

function wasCronDueToday(task: SchedulerTask, now: Date): boolean {
  if (!task.scheduleExpr) {
    return false;
  }
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const end = new Date(now);
  end.setHours(23, 59, 59, 999);
  const next = nextCronRunMs(task.scheduleExpr, start.getTime() - 60_000);
  return next !== null && next <= end.getTime();
}

function isAfterTimeOfDay(now: Date, timeOfDay: string): boolean {
  const [hours, minutes] = timeOfDay.split(":").map((part) => Number.parseInt(part, 10));
  if (!Number.isInteger(hours) || !Number.isInteger(minutes)) {
    return false;
  }
  const threshold = new Date(now);
  threshold.setHours(hours, minutes, 0, 0);
  return now.getTime() >= threshold.getTime();
}

function localDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function iso(date: Date): string {
  return date.toISOString();
}
