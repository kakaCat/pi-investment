import type {
  SchedulerRun,
  SchedulerStore,
  SchedulerTask,
} from "./scheduler-service.js";

export interface Queryable {
  query(sql: string, params?: unknown[]): Promise<{ rows: unknown[] }>;
}

export class PostgresSchedulerStore implements SchedulerStore {
  constructor(private readonly db: Queryable) {}

  async migrate(): Promise<void> {
    await this.db.query(`
      CREATE TABLE IF NOT EXISTS scheduler_tasks (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        schedule_kind TEXT NOT NULL,
        schedule_expr TEXT,
        schedule_at TIMESTAMPTZ,
        every_seconds INTEGER,
        delay_seconds INTEGER,
        anchor_at TIMESTAMPTZ,
        payload JSONB NOT NULL,
        compensation_enabled BOOLEAN NOT NULL DEFAULT FALSE,
        compensation_check_after TEXT,
        compensation_max_attempts INTEGER NOT NULL DEFAULT 1,
        delete_after_run BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        deleted_at TIMESTAMPTZ
      )
    `);
    await this.db.query(`
      CREATE TABLE IF NOT EXISTS scheduler_runs (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        task_name TEXT NOT NULL,
        scheduled_for TIMESTAMPTZ NOT NULL,
        trigger_type TEXT NOT NULL,
        status TEXT NOT NULL,
        triggered_at TIMESTAMPTZ,
        started_at TIMESTAMPTZ,
        finished_at TIMESTAMPTZ,
        duration_ms INTEGER,
        error TEXT,
        compensation_reason TEXT,
        payload JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
      )
    `);
    await this.db.query("CREATE INDEX IF NOT EXISTS idx_scheduler_runs_task_id ON scheduler_runs(task_id)");
    await this.db.query("CREATE INDEX IF NOT EXISTS idx_scheduler_runs_scheduled_for ON scheduler_runs(scheduled_for)");
  }

  async listTasks(options: { enabledOnly?: boolean; includeDeleted?: boolean } = {}): Promise<SchedulerTask[]> {
    const where: string[] = [];
    const params: unknown[] = [];
    if (options.enabledOnly) {
      where.push("enabled = true");
    }
    if (!options.includeDeleted) {
      where.push("deleted_at IS NULL");
    }
    const result = await this.db.query(
      `SELECT * FROM scheduler_tasks${where.length ? ` WHERE ${where.join(" AND ")}` : ""} ORDER BY id`,
      params,
    );
    return result.rows.map(rowToTask);
  }

  async getTask(id: string): Promise<SchedulerTask | undefined> {
    const result = await this.db.query("SELECT * FROM scheduler_tasks WHERE id = $1", [id]);
    return result.rows[0] ? rowToTask(result.rows[0]) : undefined;
  }

  async createTask(task: SchedulerTask): Promise<SchedulerTask> {
    const result = await this.db.query(
      `
      INSERT INTO scheduler_tasks (
        id, name, enabled, schedule_kind, schedule_expr, schedule_at,
        every_seconds, delay_seconds, anchor_at, payload,
        compensation_enabled, compensation_check_after, compensation_max_attempts,
        delete_after_run, created_at, updated_at, deleted_at
      ) VALUES (
        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
        $11, $12, $13, $14, $15, $16, $17
      )
      RETURNING *
      `,
      taskParams(task),
    );
    return rowToTask(result.rows[0]);
  }

  async updateTask(id: string, updates: Partial<SchedulerTask>): Promise<SchedulerTask> {
    const existing = await this.getTask(id);
    if (!existing) {
      throw new Error(`Scheduler task not found: ${id}`);
    }
    const updated = { ...existing, ...updates, id };
    const result = await this.db.query(
      `
      UPDATE scheduler_tasks SET
        name = $2,
        enabled = $3,
        schedule_kind = $4,
        schedule_expr = $5,
        schedule_at = $6,
        every_seconds = $7,
        delay_seconds = $8,
        anchor_at = $9,
        payload = $10,
        compensation_enabled = $11,
        compensation_check_after = $12,
        compensation_max_attempts = $13,
        delete_after_run = $14,
        created_at = $15,
        updated_at = $16,
        deleted_at = $17
      WHERE id = $1
      RETURNING *
      `,
      taskParams(updated),
    );
    return rowToTask(result.rows[0]);
  }

  async softDeleteTask(id: string, deletedAt: string): Promise<void> {
    await this.db.query(
      "UPDATE scheduler_tasks SET deleted_at = $1, enabled = false, updated_at = $1 WHERE id = $2",
      [deletedAt, id],
    );
  }

  async createRun(run: SchedulerRun): Promise<SchedulerRun> {
    const result = await this.db.query(
      `
      INSERT INTO scheduler_runs (
        id, task_id, task_name, scheduled_for, trigger_type, status,
        triggered_at, started_at, finished_at, duration_ms, error,
        compensation_reason, payload, created_at, updated_at
      ) VALUES (
        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
        $11, $12, $13, $14, $15
      )
      RETURNING *
      `,
      runParams(run),
    );
    return rowToRun(result.rows[0]);
  }

  async updateRun(id: string, updates: Partial<SchedulerRun>): Promise<SchedulerRun> {
    const existing = (await this.listRuns()).find((run) => run.id === id);
    if (!existing) {
      throw new Error(`Scheduler run not found: ${id}`);
    }
    const updated = { ...existing, ...updates, id };
    const result = await this.db.query(
      `
      UPDATE scheduler_runs SET
        status = $1,
        triggered_at = $2,
        started_at = $3,
        finished_at = $4,
        duration_ms = $5,
        error = $6,
        compensation_reason = $7,
        updated_at = $8
      WHERE id = $9
      RETURNING *
      `,
      [
        updated.status,
        updated.triggeredAt,
        updated.startedAt,
        updated.finishedAt,
        updated.durationMs,
        updated.error,
        updated.compensationReason,
        updated.updatedAt,
        id,
      ],
    );
    return rowToRun(result.rows[0]);
  }

  async listRuns(options: { taskId?: string; date?: string; limit?: number } = {}): Promise<SchedulerRun[]> {
    const where: string[] = [];
    const params: unknown[] = [];
    if (options.taskId) {
      params.push(options.taskId);
      where.push(`task_id = $${params.length}`);
    }
    if (options.date) {
      params.push(`${options.date}T00:00:00.000Z`);
      where.push(`scheduled_for >= $${params.length}`);
      params.push(`${options.date}T23:59:59.999Z`);
      where.push(`scheduled_for <= $${params.length}`);
    }
    const limit = options.limit ?? 100;
    params.push(limit);
    const result = await this.db.query(
      `SELECT * FROM scheduler_runs${where.length ? ` WHERE ${where.join(" AND ")}` : ""} ORDER BY created_at DESC LIMIT $${params.length}`,
      params,
    );
    return result.rows.map(rowToRun);
  }
}

function taskParams(task: SchedulerTask): unknown[] {
  return [
    task.id,
    task.name,
    task.enabled,
    task.scheduleKind,
    task.scheduleExpr,
    task.scheduleAt,
    task.everySeconds,
    task.delaySeconds,
    task.anchorAt,
    task.payload,
    task.compensationEnabled,
    task.compensationCheckAfter,
    task.compensationMaxAttempts,
    task.deleteAfterRun,
    task.createdAt,
    task.updatedAt,
    task.deletedAt,
  ];
}

function runParams(run: SchedulerRun): unknown[] {
  return [
    run.id,
    run.taskId,
    run.taskName,
    run.scheduledFor,
    run.triggerType,
    run.status,
    run.triggeredAt,
    run.startedAt,
    run.finishedAt,
    run.durationMs,
    run.error,
    run.compensationReason,
    run.payload,
    run.createdAt,
    run.updatedAt,
  ];
}

function rowToTask(row: unknown): SchedulerTask {
  const record = row as Record<string, unknown>;
  return {
    id: String(record.id),
    name: String(record.name),
    enabled: Boolean(record.enabled),
    scheduleKind: record.schedule_kind as SchedulerTask["scheduleKind"],
    scheduleExpr: maybeString(record.schedule_expr),
    scheduleAt: maybeIso(record.schedule_at),
    everySeconds: maybeNumber(record.every_seconds),
    delaySeconds: maybeNumber(record.delay_seconds),
    anchorAt: maybeIso(record.anchor_at),
    payload: parseJsonRecord(record.payload),
    compensationEnabled: Boolean(record.compensation_enabled),
    compensationCheckAfter: maybeString(record.compensation_check_after),
    compensationMaxAttempts: Number(record.compensation_max_attempts ?? 1),
    deleteAfterRun: Boolean(record.delete_after_run),
    createdAt: requireIso(record.created_at),
    updatedAt: requireIso(record.updated_at),
    deletedAt: maybeIso(record.deleted_at),
  };
}

function rowToRun(row: unknown): SchedulerRun {
  const record = row as Record<string, unknown>;
  return {
    id: String(record.id),
    taskId: String(record.task_id),
    taskName: String(record.task_name),
    scheduledFor: requireIso(record.scheduled_for),
    triggerType: record.trigger_type as SchedulerRun["triggerType"],
    status: record.status as SchedulerRun["status"],
    triggeredAt: maybeIso(record.triggered_at),
    startedAt: maybeIso(record.started_at),
    finishedAt: maybeIso(record.finished_at),
    durationMs: maybeNumber(record.duration_ms),
    error: maybeString(record.error),
    compensationReason: maybeString(record.compensation_reason),
    payload: parseJsonRecord(record.payload),
    createdAt: requireIso(record.created_at),
    updatedAt: requireIso(record.updated_at),
  };
}

function parseJsonRecord(value: unknown): Record<string, unknown> {
  if (typeof value === "string") {
    return JSON.parse(value) as Record<string, unknown>;
  }
  if (value && typeof value === "object") {
    return value as Record<string, unknown>;
  }
  return {};
}

function maybeString(value: unknown): string | undefined {
  return value === null || value === undefined ? undefined : String(value);
}

function maybeNumber(value: unknown): number | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function maybeIso(value: unknown): string | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  return requireIso(value);
}

function requireIso(value: unknown): string {
  if (value instanceof Date) {
    return value.toISOString();
  }
  return String(value);
}
