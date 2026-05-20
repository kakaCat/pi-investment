import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { dirname } from "node:path";

export const JOB_TYPES = [
  "data_update",
  "factor_compute",
  "signal_generate",
  "model_train",
  "backtest_run",
  "daily_report",
  "risk_check",
] as const;

export const JOB_STATUSES = [
  "queued",
  "running",
  "success",
  "failed",
  "cancelled",
] as const;

export type JobType = (typeof JOB_TYPES)[number];
export type JobStatus = (typeof JOB_STATUSES)[number];
export type JobParams = Record<string, unknown>;

export interface JobRecord<Result = unknown> {
  id: string;
  type: JobType;
  status: JobStatus;
  params: JobParams;
  result?: Result;
  error?: string;
  logs: string[];
  attempts: number;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  finishedAt?: string;
}

export interface JobExecutionContext {
  job: Readonly<JobRecord>;
  log: (message: string) => void;
  signal: AbortSignal;
}

export type JobExecutor<Result = unknown> = (
  context: JobExecutionContext
) => Result | Promise<Result>;

export type JobExecutorMap = Partial<Record<JobType, JobExecutor>>;

export interface JobServiceOptions {
  executors?: JobExecutorMap;
  now?: () => Date;
  idGenerator?: () => string;
  storagePath?: string;
  timeoutMs?: number;
}

export class JobService {
  private readonly jobs = new Map<string, JobRecord>();
  private readonly executors: JobExecutorMap;
  private readonly now: () => Date;
  private idGenerator: () => string;
  private readonly customIdGenerator: boolean;
  private readonly storagePath?: string;
  private readonly timeoutMs?: number;
  private readonly runningControllers = new Map<string, AbortController>();
  private storageWarning?: string;

  constructor(options: JobServiceOptions = {}) {
    this.executors = { ...options.executors };
    this.now = options.now ?? (() => new Date());
    this.customIdGenerator = Boolean(options.idGenerator);
    this.idGenerator = options.idGenerator ?? createDefaultIdGenerator();
    this.storagePath = options.storagePath;
    this.timeoutMs = resolveTimeoutMs(options.timeoutMs);
    this.loadJobs();
    this.recoverStaleRunningJobs();
    if (!this.customIdGenerator) {
      this.idGenerator = createDefaultIdGenerator(getNextJobNumber(this.jobs.values()));
    }
  }

  create(type: JobType, params: JobParams = {}): JobRecord {
    const activeJob = this.findActiveJobByType(type);
    if (activeJob) {
      throw new Error(`Active job already exists for type ${type}: ${activeJob.id}`);
    }

    const timestamp = this.timestamp();
    const job: JobRecord = {
      id: this.idGenerator(),
      type,
      status: "queued",
      params,
      logs: [],
      attempts: 0,
      createdAt: timestamp,
      updatedAt: timestamp,
    };

    this.jobs.set(job.id, job);
    this.persistJobs();
    return this.copy(job);
  }

  registerExecutor(type: JobType, executor: JobExecutor): void {
    this.executors[type] = executor;
  }

  list(): JobRecord[] {
    return Array.from(this.jobs.values(), (job) => this.copy(job));
  }

  get(id: string): JobRecord | undefined {
    const job = this.jobs.get(id);
    return job ? this.copy(job) : undefined;
  }

  async run(id: string): Promise<JobRecord> {
    const job = this.requireJob(id);

    if (job.status === "running") {
      throw new Error(`Job is already running: ${id}`);
    }
    if (job.status === "success") {
      throw new Error(`Job already succeeded: ${id}`);
    }
    if (job.status === "cancelled") {
      throw new Error(`Job is cancelled: ${id}`);
    }

    return this.execute(job);
  }

  async retry(id: string): Promise<JobRecord> {
    const job = this.requireJob(id);

    if (job.status !== "failed") {
      throw new Error(`Only failed jobs can be retried: ${id}`);
    }

    return this.execute(job);
  }

  cancel(id: string): JobRecord {
    const job = this.requireJob(id);

    if (job.status === "running") {
      const controller = this.runningControllers.get(id);
      if (!controller) {
        throw new Error(`Running job cannot be cancelled because abort controller is missing: ${id}`);
      }
      const timestamp = this.timestamp();
      job.status = "cancelled";
      job.updatedAt = timestamp;
      job.finishedAt = timestamp;
      job.error = undefined;
      controller.abort();
      this.persistJobs();
      return this.copy(job);
    }
    if (job.status === "success" || job.status === "failed") {
      throw new Error(`Completed jobs cannot be cancelled: ${id}`);
    }

    const timestamp = this.timestamp();
    job.status = "cancelled";
    job.updatedAt = timestamp;
    job.finishedAt = timestamp;
    this.persistJobs();
    return this.copy(job);
  }

  getStorageWarning(): string | undefined {
    return this.storageWarning;
  }

  private async execute(job: JobRecord): Promise<JobRecord> {
    const executor = this.executors[job.type];
    if (!executor) {
      throw new Error(`No executor registered for job type: ${job.type}`);
    }

    const startedAt = this.timestamp();
    job.status = "running";
    job.startedAt = startedAt;
    job.finishedAt = undefined;
    job.updatedAt = startedAt;
    job.error = undefined;
    job.result = undefined;
    job.attempts += 1;
    this.persistJobs();

    const controller = new AbortController();
    this.runningControllers.set(job.id, controller);

    try {
      let active = true;
      const result = await this.withTimeout(
        executor({
          job: this.copy(job),
          signal: controller.signal,
          log: (message) => {
            if (!active) {
              return;
            }
            job.logs.push(message);
            this.persistJobs();
          },
        })
      ).finally(() => {
        active = false;
      });
      if (isCancelled(job)) {
        return this.copy(job);
      }
      const finishedAt = this.timestamp();
      job.status = "success";
      job.result = result;
      job.finishedAt = finishedAt;
      job.updatedAt = finishedAt;
      this.persistJobs();
      return this.copy(job);
    } catch (error) {
      if (isCancelled(job)) {
        return this.copy(job);
      }
      const isTimeout = error instanceof JobTimeoutError;
      const finishedAt = this.timestamp();
      job.status = "failed";
      job.error = isTimeout
        ? `Job timed out after ${this.timeoutMs}ms`
        : error instanceof Error ? error.message : String(error);
      job.finishedAt = finishedAt;
      job.updatedAt = finishedAt;
      this.persistJobs();
      return this.copy(job);
    } finally {
      this.runningControllers.delete(job.id);
    }
  }

  private recoverStaleRunningJobs(): void {
    let recovered = false;
    for (const job of this.jobs.values()) {
      if (job.status !== "running") {
        continue;
      }

      const recoveredAt = this.timestamp();
      job.status = "failed";
      job.error = "Recovered stale running job on service startup";
      job.finishedAt = recoveredAt;
      job.updatedAt = recoveredAt;
      recovered = true;
    }

    if (recovered) {
      this.persistJobs();
    }
  }

  private withTimeout<Result>(operation: Result | Promise<Result>): Promise<Result> {
    if (!this.timeoutMs) {
      return Promise.resolve(operation);
    }

    return new Promise<Result>((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new JobTimeoutError());
      }, this.timeoutMs);

      Promise.resolve(operation)
        .then(resolve, reject)
        .finally(() => {
          clearTimeout(timer);
        });
    });
  }

  private loadJobs(): void {
    if (!this.storagePath || !existsSync(this.storagePath)) {
      return;
    }

    try {
      const parsed = JSON.parse(readFileSync(this.storagePath, "utf8")) as {
        jobs?: JobRecord[];
      };
      if (!Array.isArray(parsed.jobs)) {
        throw new Error("Job store must contain a jobs array");
      }

      this.jobs.clear();
      for (const job of parsed.jobs) {
        if (isJobRecord(job)) {
          this.jobs.set(job.id, this.copy(job));
        }
      }
    } catch (error) {
      this.jobs.clear();
      this.storageWarning = `Failed to load job store: ${
        error instanceof Error ? error.message : String(error)
      }`;
    }
  }

  private persistJobs(): void {
    if (!this.storagePath) {
      return;
    }

    const directory = dirname(this.storagePath);
    mkdirSync(directory, { recursive: true });

    const tempPath = `${this.storagePath}.tmp-${process.pid}`;
    const payload = JSON.stringify(
      {
        jobs: this.list(),
      },
      null,
      2
    );
    writeFileSync(tempPath, `${payload}\n`, "utf8");
    renameSync(tempPath, this.storagePath);
  }

  private requireJob(id: string): JobRecord {
    const job = this.jobs.get(id);
    if (!job) {
      throw new Error(`Job not found: ${id}`);
    }
    return job;
  }

  private findActiveJobByType(type: JobType): JobRecord | undefined {
    return Array.from(this.jobs.values()).find((job) => {
      return job.type === type && (job.status === "queued" || job.status === "running");
    });
  }

  private timestamp(): string {
    return this.now().toISOString();
  }

  private copy<Result>(job: JobRecord<Result>): JobRecord<Result> {
    return {
      ...job,
      params: { ...job.params },
      logs: [...job.logs],
    };
  }
}

class JobTimeoutError extends Error {
  constructor() {
    super("Job timed out");
  }
}

function resolveTimeoutMs(optionTimeoutMs: number | undefined): number | undefined {
  const timeoutMs = optionTimeoutMs ?? parseTimeoutMs(process.env.JOB_SERVICE_TIMEOUT_MS);
  return timeoutMs && timeoutMs > 0 ? timeoutMs : undefined;
}

function parseTimeoutMs(value: string | undefined): number | undefined {
  if (!value) {
    return undefined;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function isCancelled(job: JobRecord): boolean {
  return job.status === "cancelled";
}

function createDefaultIdGenerator(startAt: number = 1): () => string {
  let nextId = startAt;
  return () => `job-${nextId++}`;
}

function getNextJobNumber(jobs: Iterable<JobRecord>): number {
  let max = 0;
  for (const job of jobs) {
    const match = /^job-(\d+)$/.exec(job.id);
    if (match) {
      max = Math.max(max, Number(match[1]));
    }
  }
  return max + 1;
}

function isJobRecord(value: unknown): value is JobRecord {
  if (!value || typeof value !== "object") {
    return false;
  }

  const job = value as Partial<JobRecord>;
  return (
    typeof job.id === "string" &&
    JOB_TYPES.includes(job.type as JobType) &&
    JOB_STATUSES.includes(job.status as JobStatus) &&
    typeof job.params === "object" &&
    job.params !== null &&
    Array.isArray(job.logs) &&
    job.logs.every((log) => typeof log === "string") &&
    typeof job.attempts === "number" &&
    typeof job.createdAt === "string" &&
    typeof job.updatedAt === "string"
  );
}
