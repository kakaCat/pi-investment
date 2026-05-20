import * as path from "path";
import type { JobType } from "../../jobs/job-service.js";

export type QuantJobAdapter = QuantCommandJobAdapter;

export interface QuantCommandJobAdapter {
  jobType: JobType;
  type: "command";
  script: string;
  command: "python3";
  args: string[];
  cwd: ".";
  paramsToArgs?: Record<string, string>;
  notes: string;
}

const SCRIPT_DIR = path.join("quant", "scripts");
const DATA_PIPELINE_SCRIPT = path.join("quant", "quantsys", "data", "pipeline.py");

const ADAPTERS: Record<JobType, QuantJobAdapter> = {
  data_update: {
    jobType: "data_update",
    type: "command",
    script: DATA_PIPELINE_SCRIPT,
    command: "python3",
    args: [DATA_PIPELINE_SCRIPT, "update-klines"],
    cwd: ".",
    paramsToArgs: {
      symbols: "--symbols",
      days: "--days",
    },
    notes:
      "Updates recent K-lines for tracked symbols through the standalone data pipeline. Does not refresh stock lists or run asynchronously.",
  },
  factor_compute: commandAdapter(
    "factor_compute",
    "calculate_factors.py",
    "Synchronous factor calculation over selected symbols or all A-share symbols.",
    {
      symbols: "--symbols",
    }
  ),
  signal_generate: commandAdapter(
    "signal_generate",
    "generate_signals.py",
    "Synchronous signal generation that writes quant/.pi-invest/signals.json.",
    {
      symbols: "--symbols",
    }
  ),
  model_train: commandAdapter(
    "model_train",
    "ml_retrain.py",
    "Asynchronous-capable model retraining script; pass jobId as --job-id if the caller tracks status.",
    {
      symbols: "--symbols",
      days: "--days",
      futureDays: "--future-days",
      threshold: "--threshold",
      model: "--model",
      tune: "--tune",
      trials: "--trials",
      cvSplits: "--cv-splits",
      dbPath: "--db-path",
      useFeatureEngineering: "--use-feature-engineering",
      jobId: "--job-id",
    }
  ),
  backtest_run: commandAdapter(
    "backtest_run",
    "weekly_backtest.py",
    "Backtest script supports single symbol or comma-separated symbols.",
    {
      symbol: "--symbol",
      symbols: "--symbols",
      days: "--days",
      start: "--start",
      end: "--end",
      capital: "--capital",
      commission: "--commission",
      slippage: "--slippage",
      jobId: "--job-id",
    }
  ),
  daily_report: commandAdapter(
    "daily_report",
    "daily_report.py",
    "Generates daily report files under the configured output directory.",
    { outputDir: "--output-dir" }
  ),
  risk_check: commandAdapter(
    "risk_check",
    "risk_check.py",
    "CLI wrapper around POST /api/risk/check; requires quant API server availability.",
    {
      symbols: "--symbols",
      accountValue: "--account-value",
    }
  ),
};

export function getQuantJobAdapter(jobType: JobType): QuantJobAdapter {
  return cloneAdapter(ADAPTERS[jobType]);
}

export function listQuantJobAdapters(): QuantJobAdapter[] {
  return Object.values(ADAPTERS).map(cloneAdapter);
}

function commandAdapter(
  jobType: JobType,
  filename: string,
  notes: string,
  paramsToArgs?: Record<string, string>
): QuantCommandJobAdapter {
  const script = path.join(SCRIPT_DIR, filename);
  return {
    jobType,
    type: "command",
    script,
    command: "python3",
    args: [script],
    cwd: ".",
    ...(paramsToArgs ? { paramsToArgs } : {}),
    notes,
  };
}

function cloneAdapter(adapter: QuantJobAdapter): QuantJobAdapter {
  return {
    ...adapter,
    args: [...adapter.args],
    ...(adapter.paramsToArgs
      ? { paramsToArgs: { ...adapter.paramsToArgs } }
      : {}),
  };
}
