import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { describe, expect, test } from "@jest/globals";
import { JobAuditService } from "./job-audit-service.js";

describe("JobAuditService", () => {
  test("appends job audit events as JSONL", async () => {
    const tempDir = await mkdtemp(path.join(os.tmpdir(), "job-audit-"));
    const auditPath = path.join(tempDir, "audit/jobs.jsonl");
    const service = new JobAuditService({
      auditPath,
      now: () => new Date("2026-05-19T12:00:00.000Z"),
    });

    try {
      await service.record({
        action: "run",
        jobId: "job-1",
        jobType: "model_train",
        status: "queued",
        params: { days: 90 },
        actor: "researcher-a",
        ip: "127.0.0.1",
        userAgent: "curl/8.0",
      });
      await service.record({
        action: "cancel",
        jobId: "job-1",
        jobType: "model_train",
        status: "cancelled",
      });

      const lines = (await readFile(auditPath, "utf8")).trim().split("\n");
      expect(lines).toHaveLength(2);
      expect(JSON.parse(lines[0])).toEqual({
        timestamp: "2026-05-19T12:00:00.000Z",
        action: "run",
        jobId: "job-1",
        jobType: "model_train",
        status: "queued",
        params: { days: 90 },
        actor: "researcher-a",
        ip: "127.0.0.1",
        userAgent: "curl/8.0",
      });
      expect(JSON.parse(lines[1])).toMatchObject({
        timestamp: "2026-05-19T12:00:00.000Z",
        action: "cancel",
        jobId: "job-1",
        jobType: "model_train",
        status: "cancelled",
      });
    } finally {
      await rm(tempDir, { recursive: true, force: true });
    }
  });

  test("redacts sensitive params before writing audit records", async () => {
    const tempDir = await mkdtemp(path.join(os.tmpdir(), "job-audit-"));
    const auditPath = path.join(tempDir, "jobs.jsonl");
    const service = new JobAuditService({ auditPath });

    try {
      await service.record({
        action: "run",
        jobId: "job-2",
        jobType: "data_update",
        status: "queued",
        params: {
          token: "secret-token",
          apiKey: "secret-key",
          nested: { password: "secret-password", source: "hs300" },
        },
      });

      const line = (await readFile(auditPath, "utf8")).trim();
      expect(JSON.parse(line).params).toEqual({
        token: "[REDACTED]",
        apiKey: "[REDACTED]",
        nested: { password: "[REDACTED]", source: "hs300" },
      });
    } finally {
      await rm(tempDir, { recursive: true, force: true });
    }
  });
});
