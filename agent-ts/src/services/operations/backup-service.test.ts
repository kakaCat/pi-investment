import { mkdir, mkdtemp, readFile, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { describe, expect, test } from "@jest/globals";

import { BackupService } from "./backup-service.js";

async function makeRoot(): Promise<string> {
  return await mkdtemp(join(tmpdir(), "pi-invest-backup-"));
}

async function writeJson(path: string, value: unknown): Promise<void> {
  await mkdir(join(path, ".."), { recursive: true });
  await writeFile(path, JSON.stringify(value, null, 2));
}

describe("BackupService", () => {
  test("createBackup copies present local state and records skipped missing entries", async () => {
    const rootDir = await makeRoot();
    await mkdir(join(rootDir, ".pi-invest/jobs"), { recursive: true });
    await writeFile(join(rootDir, ".pi-invest/jobs/job-1.json"), "job-state");
    await mkdir(join(rootDir, ".pi-invest/audit"), { recursive: true });
    await writeFile(join(rootDir, ".pi-invest/audit/audit.log"), "audit-state");
    await writeJson(join(rootDir, "quant/.pi-invest/signals.json"), { signal: "hold" });

    const result = await new BackupService(rootDir).createBackup();

    expect(result.backupDir).toMatch(/\.pi-invest\/backups\/\d{4}-\d{2}-\d{2}T/);
    expect(result.manifest.rootDir).toBe(rootDir);
    expect(Date.parse(result.manifest.created_at)).not.toBeNaN();
    expect(result.manifest.copied.map((entry) => entry.source).sort()).toEqual(
      [".pi-invest/audit", ".pi-invest/jobs", "quant/.pi-invest/signals.json"].sort(),
    );
    expect(result.manifest.skipped_missing.map((entry) => entry.source).sort()).toEqual(
      [
        "quant/.pi-invest/daily_report.json",
        "quant/quantsys/ml/models/training_report_latest.json",
      ].sort(),
    );

    expect(await readFile(join(result.backupDir, ".pi-invest/jobs/job-1.json"), "utf8")).toBe("job-state");
    expect(await readFile(join(result.backupDir, ".pi-invest/audit/audit.log"), "utf8")).toBe("audit-state");
    expect(JSON.parse(await readFile(join(result.backupDir, "manifest.json"), "utf8")).rootDir).toBe(rootDir);
  });

  test("planRestore reads a manifest and reports restore targets without writing files", async () => {
    const rootDir = await makeRoot();
    const service = new BackupService(rootDir);
    await mkdir(join(rootDir, ".pi-invest/jobs"), { recursive: true });
    await writeFile(join(rootDir, ".pi-invest/jobs/job-1.json"), "job-state");
    const backup = await service.createBackup();

    await writeFile(join(rootDir, ".pi-invest/jobs/job-1.json"), "changed-after-backup");

    const plan = await service.planRestore(backup.backupDir);

    expect(plan.dryRun).toBe(true);
    expect(plan.skipped_missing).toEqual(backup.manifest.skipped_missing);
    expect(plan.wouldRestore).toEqual([
      {
        source: ".pi-invest/jobs",
        from: join(backup.backupDir, ".pi-invest/jobs"),
        to: join(rootDir, ".pi-invest/jobs"),
        kind: "directory",
      },
    ]);
    expect(await readFile(join(rootDir, ".pi-invest/jobs/job-1.json"), "utf8")).toBe("changed-after-backup");
    await expect(stat(join(rootDir, ".pi-invest/audit"))).rejects.toThrow();
  });

  test("restoreBackup replaces local state only with explicit confirmation", async () => {
    const rootDir = await makeRoot();
    const service = new BackupService(rootDir);
    await mkdir(join(rootDir, ".pi-invest/jobs"), { recursive: true });
    await writeFile(join(rootDir, ".pi-invest/jobs/job-1.json"), "job-state");
    const backup = await service.createBackup();
    await writeFile(join(rootDir, ".pi-invest/jobs/job-1.json"), "changed-after-backup");

    await expect(service.restoreBackup(backup.backupDir, "WRONG")).rejects.toThrow(
      "confirmation must be RESTORE_LOCAL_STATE",
    );

    const result = await service.restoreBackup(backup.backupDir, "RESTORE_LOCAL_STATE");

    expect(result.dryRun).toBe(false);
    expect(result.restored).toEqual([
      {
        source: ".pi-invest/jobs",
        from: join(backup.backupDir, ".pi-invest/jobs"),
        to: join(rootDir, ".pi-invest/jobs"),
        kind: "directory",
      },
    ]);
    expect(await readFile(join(rootDir, ".pi-invest/jobs/job-1.json"), "utf8")).toBe("job-state");
  });
});
