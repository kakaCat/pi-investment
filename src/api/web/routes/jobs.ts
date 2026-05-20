import { Router } from "express";
import * as path from "path";
import { JobService, type JobType, JOB_TYPES } from "../../../services/jobs/job-service.js";
import { JobAlertService } from "../../../services/operations/job-alert-service.js";
import { JobAuditService, type JobAuditAction } from "../../../services/operations/job-audit-service.js";
import { QuantTaskRunner } from "../../../services/quant/task-adapters/quant-task-runner.js";
import { requireOpsAuth } from "../middleware/ops-auth.js";

const router = Router();
const taskRunner = new QuantTaskRunner();
const jobService = new JobService({
  storagePath: path.join(process.cwd(), ".pi-invest/jobs/job-store.json"),
});
const jobAlertService = new JobAlertService({
  notify: async (message) => {
    console.warn(`[job-alert] ${message}`);
  },
});
const jobAuditService = new JobAuditService();

for (const jobType of JOB_TYPES) {
  jobService.registerExecutor(jobType, async ({ job, log, signal }) => {
    log(`starting ${job.type}`);
    const result = await taskRunner.run(job.type, job.params, signal);
    log(`finished ${job.type} with exit code ${result.exitCode}`);
    return result;
  });
}

router.get("/", (_req, res) => {
  const jobs = jobService.list();
  res.json({
    success: true,
    count: jobs.length,
    jobs,
    warning: jobService.getStorageWarning(),
  });
});

router.get("/:id", (req, res, next) => {
  try {
    const job = jobService.get(req.params.id);
    if (!job) {
      res.status(404);
      throw new Error("Job not found");
    }
    res.json({ success: true, data: job });
  } catch (error) {
    next(error);
  }
});

router.post("/:type/run", requireOpsAuth(), (req, res, next) => {
  try {
    const type = req.params.type as JobType;
    if (!isJobType(type)) {
      res.status(400);
      throw new Error(`Unsupported job type: ${req.params.type}`);
    }

    const job = jobService.create(type, withJobDefaults(type, req.body ?? {}));
    void auditJobAction("run", job, req);
    void jobService.run(job.id).then(alertIfFailed).catch((error) => {
      console.error(`[jobs] background job failed: ${job.id}`, error);
    });

    res.status(202).json({ success: true, data: job });
  } catch (error) {
    if (error instanceof Error && error.message.startsWith("Active job already exists")) {
      res.status(409);
    }
    next(error);
  }
});

router.post("/:id/retry", requireOpsAuth(), (req, res, next) => {
  try {
    const jobId = String(req.params.id);
    const job = jobService.get(jobId);
    if (!job) {
      res.status(404);
      throw new Error("Job not found");
    }
    if (job.status !== "failed") {
      res.status(409);
      throw new Error(`Only failed jobs can be retried: ${job.id}`);
    }

    const retried = jobService.get(job.id);
    if (retried) {
      void auditJobAction("retry", retried, req);
    }
    void jobService.retry(job.id).then(alertIfFailed).catch((error) => {
      console.error(`[jobs] background retry failed: ${job.id}`, error);
    });
    res.status(202).json({ success: true, data: jobService.get(job.id) });
  } catch (error) {
    next(error);
  }
});

router.post("/:id/cancel", requireOpsAuth(), (req, res, next) => {
  try {
    const jobId = String(req.params.id);
    const job = jobService.get(jobId);
    if (!job) {
      res.status(404);
      throw new Error("Job not found");
    }

    const cancelled = jobService.cancel(job.id);
    void auditJobAction("cancel", cancelled, req);
    res.json({ success: true, data: cancelled });
  } catch (error) {
    next(error);
  }
});

function isJobType(value: string): value is JobType {
  return (JOB_TYPES as readonly string[]).includes(value);
}

function withJobDefaults(type: JobType, params: Record<string, unknown>): Record<string, unknown> {
  if (type === "data_update") {
    return { days: 5, ...params };
  }

  return params;
}

async function alertIfFailed(job: { id: string; type: JobType; status: string; error?: string }): Promise<void> {
  if (job.status !== "failed") {
    return;
  }

  await jobAlertService.alertJobFailure({
    jobId: job.id,
    jobType: job.type,
    status: job.status,
    error: job.error,
  });
}

async function auditJobAction(
  action: JobAuditAction,
  job: ReturnType<JobService["get"]> extends infer T ? NonNullable<T> : never,
  req: { ip?: string; headers: { [key: string]: string | string[] | undefined } },
): Promise<void> {
  try {
    const actorHeader = req.headers["x-pi-actor"];
    const userAgent = req.headers["user-agent"];
    await jobAuditService.record({
      action,
      jobId: job.id,
      jobType: job.type,
      status: job.status,
      params: job.params,
      actor: Array.isArray(actorHeader) ? actorHeader[0] : actorHeader,
      ip: req.ip,
      userAgent: Array.isArray(userAgent) ? userAgent[0] : userAgent,
    });
  } catch (error) {
    console.warn("[job-audit] failed to write audit event", error);
  }
}

export { router as jobsRouter };
