import { cp, mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import { join } from "node:path";

export interface BackupEntry {
  source: string;
  backupPath: string;
  kind: "directory" | "file";
}

export interface SkippedBackupEntry {
  source: string;
  reason: "missing";
}

export interface BackupManifest {
  created_at: string;
  copied: BackupEntry[];
  skipped_missing: SkippedBackupEntry[];
  rootDir: string;
}

export interface BackupResult {
  backupDir: string;
  manifest: BackupManifest;
}

export interface RestorePlanEntry {
  source: string;
  from: string;
  to: string;
  kind: "directory" | "file";
}

export interface RestorePlan {
  dryRun: true;
  backupDir: string;
  manifest: BackupManifest;
  wouldRestore: RestorePlanEntry[];
  skipped_missing: SkippedBackupEntry[];
}

export interface RestoreResult {
  dryRun: false;
  backupDir: string;
  restored: RestorePlanEntry[];
  skipped_missing: SkippedBackupEntry[];
}

const LOCAL_STATE_PATHS = [
  ".pi-invest/jobs",
  ".pi-invest/audit",
  "quant/.pi-invest/signals.json",
  "quant/.pi-invest/daily_report.json",
  "quant/quantsys/ml/models/training_report_latest.json",
] as const;

export class BackupService {
  constructor(
    private readonly rootDir: string = process.cwd(),
    private readonly now: () => Date = () => new Date(),
  ) {}

  async createBackup(): Promise<BackupResult> {
    const createdAt = this.now().toISOString();
    const backupDir = join(this.rootDir, ".pi-invest", "backups", safeTimestamp(createdAt));
    const copied: BackupEntry[] = [];
    const skipped_missing: SkippedBackupEntry[] = [];

    await mkdir(backupDir, { recursive: true });

    for (const source of LOCAL_STATE_PATHS) {
      const sourcePath = join(this.rootDir, source);
      const backupPath = join(backupDir, source);
      const sourceStat = await stat(sourcePath).catch((error: NodeJS.ErrnoException) => {
        if (error.code === "ENOENT") {
          return undefined;
        }
        throw error;
      });

      if (!sourceStat) {
        skipped_missing.push({ source, reason: "missing" });
        continue;
      }

      await mkdir(join(backupPath, ".."), { recursive: true });
      await cp(sourcePath, backupPath, { recursive: sourceStat.isDirectory() });
      copied.push({
        source,
        backupPath: source,
        kind: sourceStat.isDirectory() ? "directory" : "file",
      });
    }

    const manifest: BackupManifest = {
      created_at: createdAt,
      copied,
      skipped_missing,
      rootDir: this.rootDir,
    };
    await writeFile(join(backupDir, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

    return { backupDir, manifest };
  }

  async planRestore(backupDir: string): Promise<RestorePlan> {
    const manifest = JSON.parse(await readFile(join(backupDir, "manifest.json"), "utf8")) as BackupManifest;

    return {
      dryRun: true,
      backupDir,
      manifest,
      wouldRestore: manifest.copied.map((entry) => ({
        source: entry.source,
        from: join(backupDir, entry.backupPath),
        to: join(this.rootDir, entry.source),
        kind: entry.kind,
      })),
      skipped_missing: manifest.skipped_missing,
    };
  }

  async restoreBackup(backupDir: string, confirmation: string): Promise<RestoreResult> {
    if (confirmation !== "RESTORE_LOCAL_STATE") {
      throw new Error("confirmation must be RESTORE_LOCAL_STATE");
    }

    const plan = await this.planRestore(backupDir);
    for (const entry of plan.wouldRestore) {
      assertSafeRestoreTarget(this.rootDir, entry.to);
      await rm(entry.to, { recursive: true, force: true });
      await mkdir(join(entry.to, ".."), { recursive: true });
      await cp(entry.from, entry.to, { recursive: entry.kind === "directory" });
    }

    return {
      dryRun: false,
      backupDir,
      restored: plan.wouldRestore,
      skipped_missing: plan.skipped_missing,
    };
  }
}

function safeTimestamp(timestamp: string): string {
  return timestamp.replace(/:/g, "-");
}

function assertSafeRestoreTarget(rootDir: string, targetPath: string): void {
  const normalizedRoot = join(rootDir, ".");
  const normalizedTarget = join(targetPath, ".");
  if (!normalizedTarget.startsWith(normalizedRoot)) {
    throw new Error(`restore target escapes rootDir: ${targetPath}`);
  }
}
