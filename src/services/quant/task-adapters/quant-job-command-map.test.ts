import path from "path";
import { describe, expect, test } from "@jest/globals";
import {
  getQuantJobAdapter,
  listQuantJobAdapters,
} from "./quant-job-command-map.js";

describe("quant job command map", () => {
  test("maps job service types to existing script commands without executing them", () => {
    expect(getQuantJobAdapter("factor_compute")).toEqual({
      jobType: "factor_compute",
      type: "command",
      script: "quant/scripts/calculate_factors.py",
      command: "python3",
      args: [path.join("quant", "scripts", "calculate_factors.py")],
      cwd: ".",
      paramsToArgs: {
        symbols: "--symbols",
      },
      notes: "Synchronous factor calculation over selected symbols or all A-share symbols.",
    });

    expect(getQuantJobAdapter("signal_generate")).toMatchObject({
      type: "command",
      script: "quant/scripts/generate_signals.py",
      command: "python3",
      args: [path.join("quant", "scripts", "generate_signals.py")],
      cwd: ".",
      paramsToArgs: {
        symbols: "--symbols",
      },
    });
  });

  test("maps data update to the repo-native kline pipeline command", () => {
    expect(getQuantJobAdapter("data_update")).toEqual({
      jobType: "data_update",
      type: "command",
      script: "quant/quantsys/data/pipeline.py",
      command: "python3",
      args: [
        path.join("quant", "quantsys", "data", "pipeline.py"),
        "update-klines",
      ],
      cwd: ".",
      paramsToArgs: {
        symbols: "--symbols",
        days: "--days",
      },
      notes:
        "Updates recent K-lines for tracked symbols through the standalone data pipeline. Does not refresh stock lists or run asynchronously.",
    });
  });

  test("documents parameter pass-through for model training and backtest commands", () => {
    expect(getQuantJobAdapter("model_train")).toMatchObject({
      script: "quant/scripts/ml_retrain.py",
      paramsToArgs: {
        days: "--days",
        symbols: "--symbols",
        futureDays: "--future-days",
        threshold: "--threshold",
        model: "--model",
        tune: "--tune",
        trials: "--trials",
        cvSplits: "--cv-splits",
        dbPath: "--db-path",
        useFeatureEngineering: "--use-feature-engineering",
        jobId: "--job-id",
      },
    });

    expect(getQuantJobAdapter("backtest_run")).toMatchObject({
      script: "quant/scripts/weekly_backtest.py",
      paramsToArgs: {
        symbol: "--symbol",
        symbols: "--symbols",
        days: "--days",
        start: "--start",
        end: "--end",
        capital: "--capital",
        commission: "--commission",
        slippage: "--slippage",
        jobId: "--job-id",
      },
    });
  });

  test("returns every JobService job type exactly once", () => {
    const adapters = listQuantJobAdapters();
    const byType = new Map(adapters.map((adapter) => [adapter.jobType, adapter]));

    expect(adapters).toHaveLength(7);
    expect([...byType.keys()].sort()).toEqual([
      "backtest_run",
      "daily_report",
      "data_update",
      "factor_compute",
      "model_train",
      "risk_check",
      "signal_generate",
    ]);
    expect(byType.get("daily_report")).toMatchObject({
      type: "command",
      script: "quant/scripts/daily_report.py",
      paramsToArgs: { outputDir: "--output-dir" },
    });
    expect(byType.get("risk_check")).toMatchObject({
      type: "command",
      script: "quant/scripts/risk_check.py",
      paramsToArgs: {
        symbols: "--symbols",
        accountValue: "--account-value",
      },
    });
  });
});
