import * as fs from "fs/promises";
import * as path from "path";

export type PlatformCheckStatus = "healthy" | "degraded" | "unavailable";
export type PlatformOverallStatus = PlatformCheckStatus;

export interface PlatformStatusCheck {
  name: "database" | "signals" | "model" | "daily_report";
  status: PlatformCheckStatus;
  message: string;
  details?: Record<string, unknown>;
}

export interface PlatformStatus {
  overall_status: PlatformOverallStatus;
  generated_at: string;
  checks: PlatformStatusCheck[];
}

export interface PlatformStatusPaths {
  database: string;
  signalsDirectory: string;
  signalsFallback: string;
  trainingReport: string;
  xgboostModel: string;
  dailyReportJson: string;
  dailyReportDirectory: string;
}

export interface PlatformArtifactMaxAgeMs {
  signals: number;
  model: number;
  daily_report: number;
}

export interface PlatformStatusServiceOptions {
  rootDir?: string;
  paths?: Partial<PlatformStatusPaths>;
  artifactMaxAgeMs?: Partial<PlatformArtifactMaxAgeMs>;
  now?: () => Date;
  databaseInfo?: DatabaseInfoProvider;
}

interface FileDetails {
  path: string;
  size_bytes: number;
  modified_at: string;
}

export interface DatabaseReadiness {
  connected: boolean;
  info?: Record<string, unknown> | null;
  error?: string;
}

export type DatabaseInfoProvider = () => Promise<DatabaseReadiness>;

const DEFAULT_PATHS: PlatformStatusPaths = {
  database: ".pi-invest/stock-db/stocks.db",
  signalsDirectory: ".pi-invest/quant/signals",
  signalsFallback: "quant/.pi-invest/signals.json",
  trainingReport: "quant/quantsys/ml/models/training_report_latest.json",
  xgboostModel: "quant/quantsys/ml/models/xgboost_latest.pkl",
  dailyReportJson: "quant/.pi-invest/daily_report.json",
  dailyReportDirectory: "quant/.pi-invest",
};

const DEFAULT_ARTIFACT_MAX_AGE_MS: PlatformArtifactMaxAgeMs = {
  signals: 7 * 24 * 60 * 60 * 1000,
  model: 30 * 24 * 60 * 60 * 1000,
  daily_report: 7 * 24 * 60 * 60 * 1000,
};

export class PlatformStatusService {
  private readonly rootDir: string;
  private readonly paths: PlatformStatusPaths;
  private readonly artifactMaxAgeMs: PlatformArtifactMaxAgeMs;
  private readonly now: () => Date;
  private readonly databaseInfo: DatabaseInfoProvider;

  constructor(options: PlatformStatusServiceOptions = {}) {
    this.rootDir = options.rootDir ?? process.cwd();
    this.paths = { ...DEFAULT_PATHS, ...options.paths };
    this.artifactMaxAgeMs = { ...DEFAULT_ARTIFACT_MAX_AGE_MS, ...options.artifactMaxAgeMs };
    this.now = options.now ?? (() => new Date());
    this.databaseInfo = options.databaseInfo ?? (() => this.getConfiguredDatabaseInfo());
  }

  async getStatus(): Promise<PlatformStatus> {
    const checks = await Promise.all([
      this.checkDatabase(),
      this.checkSignals(),
      this.checkModel(),
      this.checkDailyReport(),
    ]);

    return {
      overall_status: this.getOverallStatus(checks),
      generated_at: this.now().toISOString(),
      checks,
    };
  }

  private getOverallStatus(checks: PlatformStatusCheck[]): PlatformOverallStatus {
    const database = checks.find((check) => check.name === "database");

    if (database?.status === "unavailable") {
      return "unavailable";
    }

    if (checks.every((check) => check.status === "healthy")) {
      return "healthy";
    }

    return "degraded";
  }

  private async checkDatabase(): Promise<PlatformStatusCheck> {
    if (this.getDatabaseProvider() === "postgres") {
      const readiness = await this.databaseInfo();

      if (!readiness.connected) {
        return {
          name: "database",
          status: "unavailable",
          message: "PostgreSQL database is not connected.",
          details: {
            provider: "postgres",
            exists: false,
            ...(readiness.info ?? {}),
            ...(readiness.error ? { error: readiness.error } : {}),
          },
        };
      }

      return {
        name: "database",
        status: "healthy",
        message: "PostgreSQL database is connected.",
        details: {
          provider: "postgres",
          exists: true,
          ...(readiness.info ?? {}),
        },
      };
    }

    const file = await this.getFileDetails(this.paths.database);

    if (!file) {
      return {
        name: "database",
        status: "unavailable",
        message: "SQLite stock database was not found.",
        details: { provider: "sqlite", path: this.resolvePath(this.paths.database), exists: false },
      };
    }

    return {
      name: "database",
      status: "healthy",
      message: "SQLite stock database is present.",
      details: { provider: "sqlite", ...file, exists: true },
    };
  }

  private getDatabaseProvider(): "postgres" | "sqlite" {
    const provider = (process.env.QUANT_DB_PROVIDER ?? "postgres").trim().toLowerCase();
    if (provider === "sqlite") {
      return "sqlite";
    }
    return "postgres";
  }

  private async getConfiguredDatabaseInfo(): Promise<DatabaseReadiness> {
    const { Client } = await import("pg");
    const connectionString = process.env.QUANT_DATABASE_URL
      || process.env.DATABASE_URL
      || process.env.POSTGRES_DSN;
    const client = new Client(connectionString
      ? { connectionString }
      : {
          database: process.env.PGDATABASE || "quant_investment",
          host: process.env.PGHOST,
          port: process.env.PGPORT ? Number(process.env.PGPORT) : undefined,
          user: process.env.PGUSER,
          password: process.env.PGPASSWORD,
        });

    try {
      await client.connect();
      const result = await client.query("SELECT current_database() AS database, pg_database_size(current_database()) AS size_bytes");
      const row = result.rows[0] as { database?: string; size_bytes?: string | number } | undefined;
      const sizeBytes = Number(row?.size_bytes ?? 0);
      const sizeMb = sizeBytes / (1024 * 1024);

      return {
        connected: true,
        info: {
          provider: "postgres",
          database: row?.database ?? process.env.PGDATABASE ?? "quant_investment",
          size_mb: Math.round(sizeMb * 100) / 100,
          size_display: sizeMb >= 1024 ? `${(sizeMb / 1024).toFixed(1)} GB` : `${sizeMb.toFixed(1)} MB`,
        },
      };
    } catch (error) {
      return {
        connected: false,
        info: {
          provider: "postgres",
          database: process.env.PGDATABASE ?? "quant_investment",
        },
        error: error instanceof Error ? error.message : "Unknown PostgreSQL connection error.",
      };
    } finally {
      await client.end().catch(() => undefined);
    }
  }

  private async checkSignals(): Promise<PlatformStatusCheck> {
    const latestSignal = await this.getLatestFileInDirectory(this.paths.signalsDirectory);

    if (latestSignal) {
      const invalidJson = await this.getInvalidJsonDetails(latestSignal);

      if (invalidJson) {
        return {
          name: "signals",
          status: "degraded",
          message: "Latest signal file is invalid JSON.",
          details: {
            source: "signals_directory",
            ...latestSignal,
            ...invalidJson,
          },
        };
      }

      const stale = this.getStaleDetails(latestSignal, this.artifactMaxAgeMs.signals);

      if (stale) {
        return {
          name: "signals",
          status: "degraded",
          message: "Latest signal file is stale.",
          details: {
            source: "signals_directory",
            ...latestSignal,
            ...stale,
          },
        };
      }

      return {
        name: "signals",
        status: "healthy",
        message: "Latest signal file was found.",
        details: {
          source: "signals_directory",
          ...latestSignal,
        },
      };
    }

    const fallback = await this.getFileDetails(this.paths.signalsFallback);

    if (fallback) {
      const invalidJson = await this.getInvalidJsonDetails(fallback);

      if (invalidJson) {
        return {
          name: "signals",
          status: "degraded",
          message: "Fallback signals file is invalid JSON.",
          details: {
            source: "signals_fallback",
            ...fallback,
            ...invalidJson,
          },
        };
      }

      const stale = this.getStaleDetails(fallback, this.artifactMaxAgeMs.signals);

      if (stale) {
        return {
          name: "signals",
          status: "degraded",
          message: "Fallback signals file is stale.",
          details: {
            source: "signals_fallback",
            ...fallback,
            ...stale,
          },
        };
      }

      return {
        name: "signals",
        status: "healthy",
        message: "Fallback signals file was found.",
        details: {
          source: "signals_fallback",
          ...fallback,
        },
      };
    }

    return {
      name: "signals",
      status: "unavailable",
      message: "No signal files were found.",
      details: {
        paths_checked: [
          this.resolvePath(this.paths.signalsDirectory),
          this.resolvePath(this.paths.signalsFallback),
        ],
      },
    };
  }

  private async checkModel(): Promise<PlatformStatusCheck> {
    const candidates = await this.getExistingFiles([
      { label: "training_report", relativePath: this.paths.trainingReport },
      { label: "xgboost_model", relativePath: this.paths.xgboostModel },
    ]);
    const freshest = this.getFreshestCandidate(candidates);

    if (!freshest) {
      return {
        name: "model",
        status: "unavailable",
        message: "No model freshness artifact was found.",
        details: {
          paths_checked: [
            this.resolvePath(this.paths.trainingReport),
            this.resolvePath(this.paths.xgboostModel),
          ],
        },
      };
    }

    const invalidJson = freshest.label === "training_report"
      ? await this.getInvalidJsonDetails(freshest.file)
      : undefined;

    if (invalidJson) {
      return {
        name: "model",
        status: "degraded",
        message: "Model freshness artifact is invalid JSON.",
        details: {
          source: freshest.label,
          ...freshest.file,
          ...invalidJson,
        },
      };
    }

    const stale = this.getStaleDetails(freshest.file, this.artifactMaxAgeMs.model);

    if (stale) {
      return {
        name: "model",
        status: "degraded",
        message: "Model freshness artifact is stale.",
        details: {
          source: freshest.label,
          ...freshest.file,
          ...stale,
        },
      };
    }

    return {
      name: "model",
      status: "healthy",
      message: "Model freshness artifact is present.",
      details: {
        source: freshest.label,
        ...freshest.file,
      },
    };
  }

  private async checkDailyReport(): Promise<PlatformStatusCheck> {
    const dailyReportJson = await this.getFileDetails(this.paths.dailyReportJson);

    if (dailyReportJson) {
      const invalidJson = await this.getInvalidJsonDetails(dailyReportJson);

      if (invalidJson) {
        return {
          name: "daily_report",
          status: "degraded",
          message: "Daily report JSON is invalid JSON.",
          details: {
            source: "daily_report_json",
            ...dailyReportJson,
            ...invalidJson,
          },
        };
      }

      const stale = this.getStaleDetails(dailyReportJson, this.artifactMaxAgeMs.daily_report);

      if (stale) {
        return {
          name: "daily_report",
          status: "degraded",
          message: "Daily report JSON is stale.",
          details: {
            source: "daily_report_json",
            ...dailyReportJson,
            ...stale,
          },
        };
      }

      return {
        name: "daily_report",
        status: "healthy",
        message: "Daily report JSON was found.",
        details: {
          source: "daily_report_json",
          ...dailyReportJson,
        },
      };
    }

    const latestMarkdownReport = await this.getLatestFileInDirectory(
      this.paths.dailyReportDirectory,
      /^daily_report_.*\.md$/,
    );

    if (latestMarkdownReport) {
      const stale = this.getStaleDetails(latestMarkdownReport, this.artifactMaxAgeMs.daily_report);

      if (stale) {
        return {
          name: "daily_report",
          status: "degraded",
          message: "Latest daily report markdown is stale.",
          details: {
            source: "daily_report_markdown",
            ...latestMarkdownReport,
            ...stale,
          },
        };
      }

      return {
        name: "daily_report",
        status: "healthy",
        message: "Latest daily report markdown was found.",
        details: {
          source: "daily_report_markdown",
          ...latestMarkdownReport,
        },
      };
    }

    return {
      name: "daily_report",
      status: "unavailable",
      message: "No daily report artifact was found.",
      details: {
        paths_checked: [
          this.resolvePath(this.paths.dailyReportJson),
          this.resolvePath(this.paths.dailyReportDirectory),
        ],
      },
    };
  }

  private async getExistingFiles(
    candidates: Array<{ label: string; relativePath: string }>,
  ): Promise<Array<{ label: string; file: FileDetails }>> {
    const results = await Promise.all(
      candidates.map(async (candidate) => {
        const file = await this.getFileDetails(candidate.relativePath);
        return file ? { label: candidate.label, file } : undefined;
      }),
    );

    return results.filter((result): result is { label: string; file: FileDetails } => Boolean(result));
  }

  private getFreshestCandidate(
    candidates: Array<{ label: string; file: FileDetails }>,
  ): { label: string; file: FileDetails } | undefined {
    return candidates.sort((left, right) => {
      return Date.parse(right.file.modified_at) - Date.parse(left.file.modified_at);
    })[0];
  }

  private async getLatestFileInDirectory(
    relativePath: string,
    namePattern?: RegExp,
  ): Promise<FileDetails | undefined> {
    const directory = this.resolvePath(relativePath);

    try {
      const entries = await fs.readdir(directory, { withFileTypes: true });
      const files = await Promise.all(
        entries
          .filter((entry) => entry.isFile())
          .filter((entry) => !namePattern || namePattern.test(entry.name))
          .map((entry) => this.getFileDetails(path.join(relativePath, entry.name))),
      );

      return files
        .filter((file): file is FileDetails => Boolean(file))
        .sort((left, right) => Date.parse(right.modified_at) - Date.parse(left.modified_at))[0];
    } catch {
      return undefined;
    }
  }

  private async getFileDetails(relativePath: string): Promise<FileDetails | undefined> {
    const absolutePath = this.resolvePath(relativePath);

    try {
      const stats = await fs.stat(absolutePath);

      if (!stats.isFile()) {
        return undefined;
      }

      return {
        path: absolutePath,
        size_bytes: stats.size,
        modified_at: stats.mtime.toISOString(),
      };
    } catch {
      return undefined;
    }
  }

  private resolvePath(relativePath: string): string {
    return path.resolve(this.rootDir, relativePath);
  }

  private async getInvalidJsonDetails(file: FileDetails): Promise<Record<string, unknown> | undefined> {
    try {
      const contents = await fs.readFile(file.path, "utf8");
      JSON.parse(contents);
      return undefined;
    } catch (error) {
      return {
        valid_json: false,
        json_error: error instanceof Error ? error.message : "Invalid JSON.",
      };
    }
  }

  private getStaleDetails(file: FileDetails, maxAgeMs: number): Record<string, unknown> | undefined {
    const ageMs = this.now().getTime() - Date.parse(file.modified_at);

    if (ageMs <= maxAgeMs) {
      return undefined;
    }

    return {
      age_ms: ageMs,
      max_age_ms: maxAgeMs,
    };
  }
}

export default PlatformStatusService;
