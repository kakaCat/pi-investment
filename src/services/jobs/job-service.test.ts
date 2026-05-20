import { afterEach, describe, expect, jest, test } from "@jest/globals";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  JOB_STATUSES,
  JOB_TYPES,
  JobService,
  type JobExecutorMap,
} from "./job-service.js";

describe("JobService", () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  test("creates queued jobs and exposes them through get and list", () => {
    const service = new JobService({
      now: () => new Date("2026-05-19T01:00:00.000Z"),
      idGenerator: () => "job-1",
    });

    const job = service.create("data_update", { symbols: ["600519"] });

    expect(JOB_TYPES).toEqual([
      "data_update",
      "factor_compute",
      "signal_generate",
      "model_train",
      "backtest_run",
      "daily_report",
      "risk_check",
    ]);
    expect(JOB_STATUSES).toEqual([
      "queued",
      "running",
      "success",
      "failed",
      "cancelled",
    ]);
    expect(job).toMatchObject({
      id: "job-1",
      type: "data_update",
      status: "queued",
      params: { symbols: ["600519"] },
      logs: [],
      attempts: 0,
      createdAt: "2026-05-19T01:00:00.000Z",
      updatedAt: "2026-05-19T01:00:00.000Z",
    });
    expect(service.get("job-1")).toEqual(job);
    expect(service.list()).toEqual([job]);
  });

  test("runs a queued job with the injected executor and records result logs and timestamps", async () => {
    const dates = [
      new Date("2026-05-19T01:00:00.000Z"),
      new Date("2026-05-19T01:01:00.000Z"),
      new Date("2026-05-19T01:02:00.000Z"),
    ];
    const executors: JobExecutorMap = {
      factor_compute: async ({ job, log }) => {
        log(`computing ${String(job.params.symbol)}`);
        return { factors: 12 };
      },
    };
    const service = new JobService({
      executors,
      now: () => dates.shift() ?? new Date("2026-05-19T01:03:00.000Z"),
      idGenerator: () => "job-1",
    });

    service.create("factor_compute", { symbol: "600519" });
    const job = await service.run("job-1");

    expect(job).toMatchObject({
      id: "job-1",
      type: "factor_compute",
      status: "success",
      result: { factors: 12 },
      error: undefined,
      logs: ["computing 600519"],
      attempts: 1,
      createdAt: "2026-05-19T01:00:00.000Z",
      startedAt: "2026-05-19T01:01:00.000Z",
      finishedAt: "2026-05-19T01:02:00.000Z",
      updatedAt: "2026-05-19T01:02:00.000Z",
    });
  });

  test("records failed jobs with an error message", async () => {
    const service = new JobService({
      executors: {
        signal_generate: async () => {
          throw new Error("missing factor data");
        },
      },
      idGenerator: () => "job-1",
    });

    service.create("signal_generate", { symbol: "00700" });
    const job = await service.run("job-1");

    expect(job.status).toBe("failed");
    expect(job.error).toBe("missing factor data");
    expect(job.finishedAt).toBeDefined();
    expect(job.updatedAt).toBe(job.finishedAt);
  });

  test("fails jobs when executor exceeds configured timeout", async () => {
    jest.useFakeTimers();
    const service = new JobService({
      executors: {
        data_update: () => new Promise(() => {
          // Intentionally never resolves.
        }),
      },
      idGenerator: () => "job-1",
      timeoutMs: 1000,
    });

    service.create("data_update");
    const running = service.run("job-1");

    await jest.advanceTimersByTimeAsync(1000);
    const job = await running;

    expect(job.status).toBe("failed");
    expect(job.error).toBe("Job timed out after 1000ms");
    expect(job.finishedAt).toBeDefined();
    expect(job.updatedAt).toBe(job.finishedAt);
  });

  test("fails timed out retry attempts", async () => {
    jest.useFakeTimers();
    const service = new JobService({
      executors: {
        backtest_run: async () => {
          throw new Error("first failure");
        },
      },
      idGenerator: () => "job-1",
      timeoutMs: 1000,
    });

    service.create("backtest_run");
    await service.run("job-1");
    service.registerExecutor("backtest_run", () => new Promise(() => {
      // Intentionally never resolves.
    }));

    const retrying = service.retry("job-1");
    await jest.advanceTimersByTimeAsync(1000);
    const retried = await retrying;

    expect(retried.status).toBe("failed");
    expect(retried.error).toBe("Job timed out after 1000ms");
    expect(retried.attempts).toBe(2);
  });

  test("retries a failed job and clears previous error on success", async () => {
    let shouldFail = true;
    const service = new JobService({
      executors: {
        backtest_run: async ({ log }) => {
          log("attempt");
          if (shouldFail) {
            shouldFail = false;
            throw new Error("temporary failure");
          }
          return { sharpe: 1.2 };
        },
      },
      idGenerator: () => "job-1",
    });

    service.create("backtest_run", { strategy: "mean-reversion" });
    const failed = await service.run("job-1");
    const retried = await service.retry("job-1");

    expect(failed.status).toBe("failed");
    expect(retried.status).toBe("success");
    expect(retried.result).toEqual({ sharpe: 1.2 });
    expect(retried.error).toBeUndefined();
    expect(retried.attempts).toBe(2);
    expect(retried.logs).toEqual(["attempt", "attempt"]);
  });

  test("rejects retry for jobs that are not failed", async () => {
    const service = new JobService({
      executors: {
        daily_report: async () => ({ ok: true }),
      },
      idGenerator: () => "job-1",
    });

    service.create("daily_report");
    await service.run("job-1");

    await expect(service.retry("job-1")).rejects.toThrow(
      "Only failed jobs can be retried: job-1"
    );
  });

  test("cancels queued jobs and persists the terminal status", async () => {
    const tempDir = await mkdtemp(join(tmpdir(), "jobs-"));
    const storagePath = join(tempDir, "jobs.json");
    const dates = [
      new Date("2026-05-19T01:00:00.000Z"),
      new Date("2026-05-19T01:01:00.000Z"),
    ];
    const service = new JobService({
      storagePath,
      now: () => dates.shift() ?? new Date("2026-05-19T01:02:00.000Z"),
      idGenerator: () => "job-1",
    });

    service.create("daily_report");
    const cancelled = service.cancel("job-1");

    expect(cancelled).toMatchObject({
      id: "job-1",
      status: "cancelled",
      finishedAt: "2026-05-19T01:01:00.000Z",
      updatedAt: "2026-05-19T01:01:00.000Z",
    });

    const persisted = JSON.parse(await readFile(storagePath, "utf8"));
    expect(persisted.jobs[0]).toMatchObject({
      id: "job-1",
      status: "cancelled",
      finishedAt: "2026-05-19T01:01:00.000Z",
      updatedAt: "2026-05-19T01:01:00.000Z",
    });

    await rm(tempDir, { recursive: true, force: true });
  });

  test("cancels running jobs and aborts the executor signal", async () => {
    let abortSignal: AbortSignal | undefined;
    const service = new JobService({
      executors: {
        signal_generate: ({ signal }) => new Promise<void>((_resolve, reject) => {
          abortSignal = signal;
          signal.addEventListener("abort", () => reject(new Error("executor aborted")), { once: true });
        }),
      },
      idGenerator: () => "job-1",
    });

    service.create("signal_generate");
    const running = service.run("job-1");

    expect(service.get("job-1")?.status).toBe("running");
    expect(abortSignal?.aborted).toBe(false);
    const cancelled = service.cancel("job-1");
    const finished = await running;

    expect(abortSignal?.aborted).toBe(true);
    expect(cancelled.status).toBe("cancelled");
    expect(finished.status).toBe("cancelled");
    expect(finished.error).toBeUndefined();
  });

  test("rejects creating a duplicate active job of the same type", () => {
    const service = new JobService({
      idGenerator: (() => {
        let nextId = 1;
        return () => `job-${nextId++}`;
      })(),
    });

    service.create("model_train", { days: 90 });

    expect(() => service.create("model_train", { days: 30 })).toThrow(
      "Active job already exists for type model_train: job-1"
    );
    expect(service.create("daily_report").id).toBe("job-2");
  });

  test("allows creating the same job type after terminal status", () => {
    const service = new JobService({
      idGenerator: (() => {
        let nextId = 1;
        return () => `job-${nextId++}`;
      })(),
    });

    service.create("model_train", { days: 90 });
    service.cancel("job-1");
    const replacement = service.create("model_train", { days: 30 });

    expect(replacement.id).toBe("job-2");
    expect(replacement.type).toBe("model_train");
  });

  test("persists created and completed job when storage is enabled", async () => {
    const tempDir = await mkdtemp(join(tmpdir(), "jobs-"));
    const storagePath = join(tempDir, "jobs.json");
    const dates = [
      new Date("2026-05-19T01:00:00.000Z"),
      new Date("2026-05-19T01:01:00.000Z"),
      new Date("2026-05-19T01:02:00.000Z"),
    ];
    const service = new JobService({
      storagePath,
      executors: {
        factor_compute: async ({ log }) => {
          log("started factors");
          return { factors: 3 };
        },
      },
      now: () => dates.shift() ?? new Date("2026-05-19T01:03:00.000Z"),
      idGenerator: () => "job-1",
    });

    service.create("factor_compute", { symbol: "600519" });
    await service.run("job-1");

    const persisted = JSON.parse(await readFile(storagePath, "utf8"));
    expect(persisted.jobs).toHaveLength(1);
    expect(persisted.jobs[0]).toMatchObject({
      id: "job-1",
      type: "factor_compute",
      status: "success",
      params: { symbol: "600519" },
      result: { factors: 3 },
      logs: ["started factors"],
      attempts: 1,
      createdAt: "2026-05-19T01:00:00.000Z",
      startedAt: "2026-05-19T01:01:00.000Z",
      finishedAt: "2026-05-19T01:02:00.000Z",
      updatedAt: "2026-05-19T01:02:00.000Z",
    });

    await rm(tempDir, { recursive: true, force: true });
  });

  test("loads persisted jobs on new service instance", async () => {
    const tempDir = await mkdtemp(join(tmpdir(), "jobs-"));
    const storagePath = join(tempDir, "jobs.json");
    const first = new JobService({
      storagePath,
      idGenerator: () => "job-1",
      now: () => new Date("2026-05-19T01:00:00.000Z"),
    });

    const created = first.create("data_update", { symbols: ["600519"] });
    const second = new JobService({ storagePath });

    expect(second.get("job-1")).toEqual(created);
    expect(second.list()).toEqual([created]);

    await rm(tempDir, { recursive: true, force: true });
  });

  test("recovers persisted running jobs as failed on startup", async () => {
    const tempDir = await mkdtemp(join(tmpdir(), "jobs-"));
    const storagePath = join(tempDir, "jobs.json");
    await writeFile(
      storagePath,
      JSON.stringify({
        jobs: [
          {
            id: "job-1",
            type: "data_update",
            status: "running",
            params: { symbols: ["600519"] },
            logs: ["started"],
            attempts: 1,
            createdAt: "2026-05-19T01:00:00.000Z",
            startedAt: "2026-05-19T01:01:00.000Z",
            updatedAt: "2026-05-19T01:01:00.000Z",
          },
        ],
      }),
      "utf8"
    );

    const service = new JobService({
      storagePath,
      now: () => new Date("2026-05-19T02:00:00.000Z"),
    });
    const recovered = service.get("job-1");
    const persisted = JSON.parse(await readFile(storagePath, "utf8"));

    expect(recovered).toMatchObject({
      id: "job-1",
      status: "failed",
      error: "Recovered stale running job on service startup",
      finishedAt: "2026-05-19T02:00:00.000Z",
      updatedAt: "2026-05-19T02:00:00.000Z",
    });
    expect(persisted.jobs[0]).toMatchObject({
      id: "job-1",
      status: "failed",
      error: "Recovered stale running job on service startup",
      finishedAt: "2026-05-19T02:00:00.000Z",
      updatedAt: "2026-05-19T02:00:00.000Z",
    });

    await rm(tempDir, { recursive: true, force: true });
  });

  test("default id generator continues after loaded numeric job ids", async () => {
    const tempDir = await mkdtemp(join(tmpdir(), "jobs-"));
    const storagePath = join(tempDir, "jobs.json");
    await writeFile(
      storagePath,
      JSON.stringify({
        jobs: [
          {
            id: "job-7",
            type: "daily_report",
            status: "success",
            params: {},
            logs: [],
            attempts: 1,
            createdAt: "2026-05-19T01:00:00.000Z",
            updatedAt: "2026-05-19T01:00:00.000Z",
          },
        ],
      }),
      "utf8"
    );

    const service = new JobService({ storagePath });
    const created = service.create("risk_check");

    expect(created.id).toBe("job-8");

    await rm(tempDir, { recursive: true, force: true });
  });

  test("handles corrupt and missing stores gracefully", async () => {
    const tempDir = await mkdtemp(join(tmpdir(), "jobs-"));
    const missingPath = join(tempDir, "missing.json");
    const corruptPath = join(tempDir, "corrupt.json");
    await writeFile(corruptPath, "{not json", "utf8");

    const missing = new JobService({ storagePath: missingPath });
    const corrupt = new JobService({ storagePath: corruptPath });

    expect(missing.list()).toEqual([]);
    expect(missing.getStorageWarning()).toBeUndefined();
    expect(corrupt.list()).toEqual([]);
    expect(corrupt.getStorageWarning()).toContain("Failed to load job store");

    await rm(tempDir, { recursive: true, force: true });
  });

  test("persists failed retry lifecycle", async () => {
    const tempDir = await mkdtemp(join(tmpdir(), "jobs-"));
    const storagePath = join(tempDir, "jobs.json");
    let attempt = 0;
    const service = new JobService({
      storagePath,
      executors: {
        backtest_run: async ({ log }) => {
          attempt += 1;
          log(`attempt ${attempt}`);
          if (attempt === 1) {
            throw new Error("temporary failure");
          }
          return { sharpe: 1.5 };
        },
      },
      idGenerator: () => "job-1",
    });

    service.create("backtest_run", { strategy: "momentum" });
    await service.run("job-1");
    const failedStore = JSON.parse(await readFile(storagePath, "utf8"));
    expect(failedStore.jobs[0]).toMatchObject({
      status: "failed",
      error: "temporary failure",
      logs: ["attempt 1"],
      attempts: 1,
    });

    await service.retry("job-1");
    const retriedStore = JSON.parse(await readFile(storagePath, "utf8"));
    expect(retriedStore.jobs[0]).toMatchObject({
      status: "success",
      result: { sharpe: 1.5 },
      logs: ["attempt 1", "attempt 2"],
      attempts: 2,
    });
    expect(retriedStore.jobs[0]).not.toHaveProperty("error");

    await rm(tempDir, { recursive: true, force: true });
  });
});
