import { afterEach, beforeEach, describe, expect, test } from "@jest/globals";
import * as fs from "fs/promises";
import * as os from "os";
import * as path from "path";
import { PlatformStatusService } from "./PlatformStatusService.js";

async function makeTempRoot(): Promise<string> {
  return fs.mkdtemp(path.join(os.tmpdir(), "platform-status-"));
}

async function writeFile(rootDir: string, relativePath: string, contents = "ok"): Promise<string> {
  const absolutePath = path.join(rootDir, relativePath);
  await fs.mkdir(path.dirname(absolutePath), { recursive: true });
  await fs.writeFile(absolutePath, contents);
  return absolutePath;
}

async function touch(rootDir: string, relativePath: string, date: Date): Promise<string> {
  const absolutePath = await writeFile(rootDir, relativePath);
  await fs.utimes(absolutePath, date, date);
  return absolutePath;
}

describe("PlatformStatusService", () => {
  const originalProvider = process.env.QUANT_DB_PROVIDER;

  beforeEach(() => {
    process.env.QUANT_DB_PROVIDER = "sqlite";
  });

  afterEach(() => {
    if (originalProvider === undefined) {
      delete process.env.QUANT_DB_PROVIDER;
    } else {
      process.env.QUANT_DB_PROVIDER = originalProvider;
    }
  });

  test("returns healthy when all primary readiness artifacts are present", async () => {
    const rootDir = await makeTempRoot();
    const now = new Date("2026-05-19T08:00:00.000Z");

    const databasePath = await writeFile(rootDir, ".pi-invest/stock-db/stocks.db", "sqlite");
    const signalPath = await touchJson(rootDir, ".pi-invest/quant/signals/signal-a.json", new Date("2026-05-19T07:00:00.000Z"));
    const modelPath = await writeFile(rootDir, "quant/quantsys/ml/models/training_report_latest.json", "{}");
    const reportPath = await writeFile(rootDir, "quant/.pi-invest/daily_report.json", "{}");

    const status = await new PlatformStatusService({
      rootDir,
      now: () => now,
    }).getStatus();

    expect(status).toMatchObject({
      overall_status: "healthy",
      generated_at: now.toISOString(),
      checks: [
        {
          name: "database",
          status: "healthy",
          details: expect.objectContaining({ path: databasePath, exists: true }),
        },
        {
          name: "signals",
          status: "healthy",
          details: expect.objectContaining({ source: "signals_directory", path: signalPath }),
        },
        {
          name: "model",
          status: "healthy",
          details: expect.objectContaining({ source: "training_report", path: modelPath }),
        },
        {
          name: "daily_report",
          status: "healthy",
          details: expect.objectContaining({ source: "daily_report_json", path: reportPath }),
        },
      ],
    });
  });

  test("uses PostgreSQL readiness details without requiring a SQLite file", async () => {
    const rootDir = await makeTempRoot();
    const now = new Date("2026-05-19T08:00:00.000Z");
    process.env.QUANT_DB_PROVIDER = "postgres";

    await touchJson(rootDir, ".pi-invest/quant/signals/signal-a.json", new Date("2026-05-19T07:00:00.000Z"));
    await writeFile(rootDir, "quant/quantsys/ml/models/training_report_latest.json", "{}");
    await writeFile(rootDir, "quant/.pi-invest/daily_report.json", "{}");

    const status = await new PlatformStatusService({
      rootDir,
      now: () => now,
      databaseInfo: async () => ({
        connected: true,
        info: {
          provider: "postgres",
          database: "quant_investment",
          size_mb: 123.4,
          size_display: "123.4 MB",
        },
      }),
    }).getStatus();

    expect(status.overall_status).toBe("healthy");
    expect(status.checks.find((check) => check.name === "database")).toMatchObject({
      status: "healthy",
      message: "PostgreSQL database is connected.",
      details: expect.objectContaining({
        provider: "postgres",
        database: "quant_investment",
        exists: true,
      }),
    });
  });

  test("uses fallback artifacts when primary signals, model report, and daily report JSON are absent", async () => {
    const rootDir = await makeTempRoot();

    await writeFile(rootDir, ".pi-invest/stock-db/stocks.db");
    const signalsFallbackPath = await writeFile(rootDir, "quant/.pi-invest/signals.json", "{}");
    const modelFallbackPath = await writeFile(rootDir, "quant/quantsys/ml/models/xgboost_latest.pkl", "model");
    const markdownReportPath = await touch(
      rootDir,
      "quant/.pi-invest/daily_report_2026-05-19.md",
      new Date("2026-05-19T07:00:00.000Z"),
    );

    const status = await new PlatformStatusService({ rootDir }).getStatus();

    expect(status.overall_status).toBe("healthy");
    expect(status.checks.find((check) => check.name === "signals")).toMatchObject({
      status: "healthy",
      details: expect.objectContaining({ source: "signals_fallback", path: signalsFallbackPath }),
    });
    expect(status.checks.find((check) => check.name === "model")).toMatchObject({
      status: "healthy",
      details: expect.objectContaining({ source: "xgboost_model", path: modelFallbackPath }),
    });
    expect(status.checks.find((check) => check.name === "daily_report")).toMatchObject({
      status: "healthy",
      details: expect.objectContaining({ source: "daily_report_markdown", path: markdownReportPath }),
    });
  });

  test("marks the platform unavailable when the database is missing", async () => {
    const rootDir = await makeTempRoot();

    await writeFile(rootDir, ".pi-invest/quant/signals/signal-a.json", "{}");
    await writeFile(rootDir, "quant/quantsys/ml/models/training_report_latest.json", "{}");
    await writeFile(rootDir, "quant/.pi-invest/daily_report.json", "{}");

    const status = await new PlatformStatusService({ rootDir }).getStatus();

    expect(status.overall_status).toBe("unavailable");
    expect(status.checks.find((check) => check.name === "database")).toMatchObject({
      status: "unavailable",
      message: "SQLite stock database was not found.",
    });
  });

  test("marks the platform degraded when optional operational artifacts are missing", async () => {
    const rootDir = await makeTempRoot();

    await writeFile(rootDir, ".pi-invest/stock-db/stocks.db");

    const status = await new PlatformStatusService({ rootDir }).getStatus();

    expect(status.overall_status).toBe("degraded");
    expect(status.checks).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ name: "signals", status: "unavailable" }),
        expect.objectContaining({ name: "model", status: "unavailable" }),
        expect.objectContaining({ name: "daily_report", status: "unavailable" }),
      ]),
    );
  });

  test("selects the newest signal and daily report markdown files by mtime", async () => {
    const rootDir = await makeTempRoot();

    await writeFile(rootDir, ".pi-invest/stock-db/stocks.db");
    await touchJson(rootDir, ".pi-invest/quant/signals/old.json", new Date("2026-05-18T07:00:00.000Z"));
    const newestSignalPath = await touchJson(rootDir, ".pi-invest/quant/signals/new.json", new Date("2026-05-19T07:00:00.000Z"));
    await writeFile(rootDir, "quant/quantsys/ml/models/training_report_latest.json", "{}");
    await touch(rootDir, "quant/.pi-invest/daily_report_2026-05-18.md", new Date("2026-05-18T07:00:00.000Z"));
    const newestReportPath = await touch(rootDir, "quant/.pi-invest/daily_report_2026-05-19.md", new Date("2026-05-19T07:00:00.000Z"));

    const status = await new PlatformStatusService({ rootDir }).getStatus();

    expect(status.checks.find((check) => check.name === "signals")).toMatchObject({
      details: expect.objectContaining({ path: newestSignalPath }),
    });
    expect(status.checks.find((check) => check.name === "daily_report")).toMatchObject({
      details: expect.objectContaining({ path: newestReportPath }),
    });
  });

  test("marks JSON artifacts degraded when their contents are invalid", async () => {
    const rootDir = await makeTempRoot();

    await writeFile(rootDir, ".pi-invest/stock-db/stocks.db");
    await writeFile(rootDir, ".pi-invest/quant/signals/signal-a.json", "{invalid");
    await writeFile(rootDir, "quant/quantsys/ml/models/training_report_latest.json", "{invalid");
    await writeFile(rootDir, "quant/.pi-invest/daily_report.json", "{invalid");

    const status = await new PlatformStatusService({ rootDir }).getStatus();

    expect(status.overall_status).toBe("degraded");
    expect(status.checks).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          name: "signals",
          status: "degraded",
          message: "Latest signal file is invalid JSON.",
        }),
        expect.objectContaining({
          name: "model",
          status: "degraded",
          message: "Model freshness artifact is invalid JSON.",
        }),
        expect.objectContaining({
          name: "daily_report",
          status: "degraded",
          message: "Daily report JSON is invalid JSON.",
        }),
      ]),
    );
  });

  test("marks artifacts degraded when modified_at exceeds configured max age thresholds", async () => {
    const rootDir = await makeTempRoot();
    const now = new Date("2026-05-19T08:00:00.000Z");

    await writeFile(rootDir, ".pi-invest/stock-db/stocks.db");
    await touchJson(rootDir, ".pi-invest/quant/signals/signal-a.json", new Date("2026-05-19T05:59:59.000Z"));
    await touchJson(rootDir, "quant/quantsys/ml/models/training_report_latest.json", new Date("2026-05-18T07:59:59.000Z"));
    await touchJson(rootDir, "quant/.pi-invest/daily_report.json", new Date("2026-05-19T06:59:59.000Z"));

    const status = await new PlatformStatusService({
      rootDir,
      now: () => now,
      artifactMaxAgeMs: {
        signals: 2 * 60 * 60 * 1000,
        model: 24 * 60 * 60 * 1000,
        daily_report: 60 * 60 * 1000,
      },
    }).getStatus();

    expect(status.overall_status).toBe("degraded");
    expect(status.checks).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          name: "signals",
          status: "degraded",
          message: "Latest signal file is stale.",
          details: expect.objectContaining({ max_age_ms: 2 * 60 * 60 * 1000 }),
        }),
        expect.objectContaining({
          name: "model",
          status: "degraded",
          message: "Model freshness artifact is stale.",
          details: expect.objectContaining({ max_age_ms: 24 * 60 * 60 * 1000 }),
        }),
        expect.objectContaining({
          name: "daily_report",
          status: "degraded",
          message: "Daily report JSON is stale.",
          details: expect.objectContaining({ max_age_ms: 60 * 60 * 1000 }),
        }),
      ]),
    );
  });
});

async function touchJson(rootDir: string, relativePath: string, date: Date): Promise<string> {
  const absolutePath = await writeFile(rootDir, relativePath, "{}");
  await fs.utimes(absolutePath, date, date);
  return absolutePath;
}
