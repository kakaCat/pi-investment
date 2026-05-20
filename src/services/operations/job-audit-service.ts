import { appendFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import type { JobStatus, JobType } from "../jobs/job-service.js";

export type JobAuditAction = "run" | "retry" | "cancel";

export interface JobAuditEvent {
  action: JobAuditAction;
  jobId: string;
  jobType: JobType;
  status: JobStatus;
  params?: Record<string, unknown>;
  actor?: string;
  ip?: string;
  userAgent?: string;
}

export interface JobAuditServiceOptions {
  auditPath?: string;
  now?: () => Date;
}

const SENSITIVE_KEY_PATTERN = /password|token|secret|api[_-]?key|authorization/i;

export class JobAuditService {
  private readonly auditPath: string;
  private readonly now: () => Date;

  constructor(options: JobAuditServiceOptions = {}) {
    this.auditPath = options.auditPath ?? join(".pi-invest", "audit", "jobs.jsonl");
    this.now = options.now ?? (() => new Date());
  }

  async record(event: JobAuditEvent): Promise<void> {
    await mkdir(dirname(this.auditPath), { recursive: true });

    const payload = {
      timestamp: this.now().toISOString(),
      ...event,
      ...(event.params ? { params: redactSensitiveValues(event.params) } : {}),
    };

    await appendFile(this.auditPath, `${JSON.stringify(payload)}\n`, "utf8");
  }
}

function redactSensitiveValues(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(redactSensitiveValues);
  }

  if (!value || typeof value !== "object") {
    return value;
  }

  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, nestedValue]) => [
      key,
      SENSITIVE_KEY_PATTERN.test(key) ? "[REDACTED]" : redactSensitiveValues(nestedValue),
    ]),
  );
}
