import { describe, expect, jest, test } from "@jest/globals";
import express from "express";
import http from "node:http";
import type { AddressInfo } from "node:net";
import type { Socket } from "node:net";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";

await jest.unstable_mockModule("../../../services/jobs/job-service.js", () => {
  class JobService {
    private jobs = new Map<string, { id: string; type: string; status: string; params: Record<string, unknown> }>();

    constructor() {
      this.jobs.set("job-1", { id: "job-1", type: "data_update", status: "failed", params: { days: 5 } });
    }

    registerExecutor(): void {}
    list() { return Array.from(this.jobs.values()); }
    get(id: string) { return this.jobs.get(id) ?? null; }
    create(type: string, params: Record<string, unknown>) {
      const job = { id: `job-${this.jobs.size + 1}`, type, status: "queued", params };
      this.jobs.set(job.id, job);
      return job;
    }
    async run(id: string) { const job = this.jobs.get(id); if (job) job.status = "success"; return job; }
    async retry(id: string) { const job = this.jobs.get(id); if (job) job.status = "success"; return job; }
    cancel(id: string) { const job = this.jobs.get(id); if (!job) return null; job.status = "cancelled"; return job; }
    getStorageWarning() { return undefined; }
  }

  return { JobService, JOB_TYPES: ["data_update", "factor_compute", "model_train", "backtest_run", "daily_report", "risk_check", "weekly_backtest", "weekly_performance"] };
});

await jest.unstable_mockModule("../../../services/quant/task-adapters/quant-task-runner.js", () => ({
  QuantTaskRunner: class {
    async run(): Promise<{ exitCode: number }> {
      return { exitCode: 0 };
    }
  },
}));

await jest.unstable_mockModule("../../../services/scheduler/scheduler-runtime.js", () => ({
  getSchedulerRuntime: async () => ({
    store: {
      migrate: async () => undefined,
      createTask: async (task: unknown) => task,
      updateTask: async (id: string, updates: Record<string, unknown>) => ({ id, ...updates }),
      softDeleteTask: async () => undefined,
      listTasks: async () => [],
      getTask: async () => ({ id: "task-1", enabled: true, scheduleKind: "delay", deleteAfterRun: false, payload: {}, compensationEnabled: false, compensationMaxAttempts: 1, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }),
      createRun: async (run: unknown) => run,
      updateRun: async (id: string, updates: Record<string, unknown>) => ({ id, ...updates }),
      listRuns: async () => [
        { id: "run-ok", taskId: "task-1", taskName: "Task", scheduledFor: "2026-05-20T01:00:00.000Z", triggerType: "scheduled", status: "success", payload: {}, createdAt: "2026-05-20T01:00:00.000Z", updatedAt: "2026-05-20T01:00:00.000Z" },
        { id: "run-failed", taskId: "task-1", taskName: "Task", scheduledFor: "2026-05-20T02:00:00.000Z", triggerType: "scheduled", status: "failed", error: "boom", payload: {}, createdAt: "2026-05-20T02:00:00.000Z", updatedAt: "2026-05-20T02:00:00.000Z" },
      ],
    },
    service: {
      listTaskSummaries: async () => [],
      reloadTasks: async () => undefined,
      triggerTask: async () => ({ id: "run-1", status: "success" }),
    },
  }),
}));

const { jobsRouter } = await import("./jobs.js");
const { schedulerRouter } = await import("./scheduler.js");
const { platformRouter } = await import("./platform.js");
const { BackupService } = await import("../../../services/operations/backup-service.js");
const { JobAuditService } = await import("../../../services/operations/job-audit-service.js");

type JsonResponse<T> = {
  status: number;
  body: T;
};

async function withServer<T>(app: express.Express, run: (baseUrl: string) => Promise<T>): Promise<T> {
  const server = app.listen(0);
  const sockets = new Set<Socket>();
  server.on("connection", (socket) => {
    sockets.add(socket);
    socket.once("close", () => sockets.delete(socket));
  });
  try {
    await new Promise<void>((resolve) => server.once("listening", resolve));
    const address = server.address() as AddressInfo;
    return await run(`http://127.0.0.1:${address.port}`);
  } finally {
    server.closeAllConnections();
    for (const socket of sockets) {
      socket.destroy();
    }
    await new Promise<void>((resolve, reject) => {
      server.close((error) => error ? reject(error) : resolve());
    });
  }
}

async function requestJson<T>(url: string, options: { method?: string; headers?: Record<string, string>; body?: string } = {}): Promise<JsonResponse<T>> {
  return new Promise((resolve, reject) => {
    const request = http.request(url, {
      method: options.method ?? "GET",
      headers: options.headers,
      agent: false,
    }, (response) => {
      let rawBody = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { rawBody += chunk; });
      response.on("end", () => {
        resolve({ status: response.statusCode ?? 0, body: JSON.parse(rawBody) as T });
      });
    });
    request.on("error", reject);
    if (options.body) request.write(options.body);
    request.end();
  });
}

describe("jobs and scheduler governance", () => {
  test("job actions write audit events", async () => {
    const tempDir = await mkdtemp(path.join(os.tmpdir(), "job-governance-"));
    const auditPath = path.join(tempDir, "audit/jobs.jsonl");
    const audit = new JobAuditService({ auditPath, now: () => new Date("2026-05-20T01:00:00.000Z") });
    await audit.record({
      action: "run",
      jobId: "job-1",
      jobType: "data_update",
      status: "queued",
      params: { token: "secret", days: 5 },
      actor: "ops",
    });
    const line = await readFile(auditPath, "utf8");
    expect(JSON.parse(line).params).toEqual({ token: "[REDACTED]", days: 5 });
  });

  test("backup service records manifest and restore dry-run", async () => {
    const tempDir = await mkdtemp(path.join(os.tmpdir(), "backup-governance-"));
    await mkdir(path.join(tempDir, ".pi-invest/jobs"), { recursive: true });
    await writeFile(path.join(tempDir, ".pi-invest/jobs/job.json"), "x");
    const service = new BackupService(tempDir, () => new Date("2026-05-20T01:00:00.000Z"));
    const backup = await service.createBackup();
    const plan = await service.planRestore(backup.backupDir);
    expect(plan.dryRun).toBe(true);
    expect(plan.wouldRestore.length).toBeGreaterThan(0);
  });

  test("jobs and scheduler routes remain operable for read paths", async () => {
    const app = express();
    app.use(express.json());
    app.use("/api/jobs", jobsRouter);
    app.use("/api/scheduler", schedulerRouter);

    await withServer(app, async (baseUrl) => {
      const jobs = await requestJson<{ success?: boolean; count?: number; jobs?: unknown[] }>(`${baseUrl}/api/jobs`);
      const tasks = await requestJson<{ success?: boolean; tasks?: unknown[] }>(`${baseUrl}/api/scheduler/tasks`);
      const runs = await requestJson<{ success?: boolean; runs?: unknown[] }>(`${baseUrl}/api/scheduler/runs`);
      const failedRuns = await requestJson<{ success?: boolean; count?: number; runs?: Array<{ id: string }> }>(`${baseUrl}/api/scheduler/runs/failed`);
      expect(jobs.status).toBe(200);
      expect(tasks.status).toBe(200);
      expect(runs.status).toBe(200);
      expect(failedRuns.status).toBe(200);
      expect(failedRuns.body.count).toBe(1);
      expect(failedRuns.body.runs?.[0]?.id).toBe("run-failed");
    });
  });

  test("backup and restore-plan platform routes are protected by ops token", async () => {
    const previousToken = process.env.OPS_API_TOKEN;
    process.env.OPS_API_TOKEN = "secret-token";
    const app = express();
    app.use(express.json());
    app.use("/api/platform", platformRouter);

    try {
      await withServer(app, async (baseUrl) => {
        const backupWithoutToken = await requestJson<{ success?: boolean; error?: string }>(
          `${baseUrl}/api/platform/backups`,
          { method: "POST" },
        );
        const restoreWithoutToken = await requestJson<{ success?: boolean; error?: string }>(
          `${baseUrl}/api/platform/restore-plan`,
          {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ backupDir: "/tmp/backup" }),
          },
        );
        const restoreExecuteWithoutToken = await requestJson<{ success?: boolean; error?: string }>(
          `${baseUrl}/api/platform/restore`,
          {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ backupDir: "/tmp/backup", confirmation: "RESTORE_LOCAL_STATE" }),
          },
        );

        expect(backupWithoutToken.status).toBe(401);
        expect(restoreWithoutToken.status).toBe(401);
        expect(restoreExecuteWithoutToken.status).toBe(401);
        expect(backupWithoutToken.body.error).toBe("Missing or invalid operations token");
        expect(restoreWithoutToken.body.error).toBe("Missing or invalid operations token");
        expect(restoreExecuteWithoutToken.body.error).toBe("Missing or invalid operations token");
      });
    } finally {
      if (previousToken === undefined) {
        delete process.env.OPS_API_TOKEN;
      } else {
        process.env.OPS_API_TOKEN = previousToken;
      }
    }
  });

  test("backup route creates a manifest when authorized", async () => {
    const previousToken = process.env.OPS_API_TOKEN;
    process.env.OPS_API_TOKEN = "secret-token";
    const app = express();
    app.use(express.json());
    app.use("/api/platform", platformRouter);

    try {
      await withServer(app, async (baseUrl) => {
        const backup = await requestJson<{ success?: boolean; data?: { backupDir?: string; manifest?: { copied?: unknown[]; skipped_missing?: unknown[] } } }>(
          `${baseUrl}/api/platform/backups`,
          {
            method: "POST",
            headers: { authorization: "Bearer secret-token" },
          },
        );

        expect(backup.status).toBe(201);
        expect(backup.body.success).toBe(true);
        expect(typeof backup.body.data?.backupDir).toBe("string");
        expect(Array.isArray(backup.body.data?.manifest?.copied)).toBe(true);
        expect(Array.isArray(backup.body.data?.manifest?.skipped_missing)).toBe(true);
      });
    } finally {
      if (previousToken === undefined) {
        delete process.env.OPS_API_TOKEN;
      } else {
        process.env.OPS_API_TOKEN = previousToken;
      }
    }
  });
});
