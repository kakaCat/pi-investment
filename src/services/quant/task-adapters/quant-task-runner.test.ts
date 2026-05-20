import { mkdir, mkdtemp, rm, writeFile } from "fs/promises";
import os from "os";
import path from "path";
import { afterEach, describe, expect, jest, test } from "@jest/globals";
import { buildQuantTaskCommand, QuantTaskRunner } from "./quant-task-runner.js";

afterEach(() => {
  jest.restoreAllMocks();
});

describe("buildQuantTaskCommand", () => {
  test("maps supported quant job types to existing script commands", () => {
    const command = buildQuantTaskCommand("signal_generate", {
      projectRoot: "/repo",
    });

    expect(command).toEqual({
      command: "python3",
      args: [path.join("/repo", "quant/scripts/generate_signals.py")],
      cwd: path.join("/repo", "quant"),
    });
  });

  test("maps data update to the local kline pipeline command", () => {
    const command = buildQuantTaskCommand("data_update", {
      projectRoot: "/repo",
    });

    expect(command).toEqual({
      command: "python3",
      args: [
        path.join("/repo", "quant/quantsys/data/pipeline.py"),
        "update-klines",
      ],
      cwd: path.join("/repo", "quant"),
    });
  });

  test("maps supported params to command arguments", () => {
    const command = buildQuantTaskCommand("model_train", {
      projectRoot: "/repo",
      params: { symbols: ["000001", "600036"], days: 30, model: "xgboost", useFeatureEngineering: true },
    });

    expect(command.args).toEqual([
      path.join("/repo", "quant/scripts/ml_retrain.py"),
      "--symbols",
      "000001,600036",
      "--days",
      "30",
      "--model",
      "xgboost",
      "--use-feature-engineering",
    ]);
  });

  test("passes selected symbols to factor and signal scripts", () => {
    const factorCommand = buildQuantTaskCommand("factor_compute", {
      projectRoot: "/repo",
      params: { symbols: ["000001", "600036"] },
    });
    const signalCommand = buildQuantTaskCommand("signal_generate", {
      projectRoot: "/repo",
      params: { symbols: ["000001", "600036"] },
    });

    expect(factorCommand.args).toEqual([
      path.join("/repo", "quant/scripts/calculate_factors.py"),
      "--symbols",
      "000001,600036",
    ]);
    expect(signalCommand.args).toEqual([
      path.join("/repo", "quant/scripts/generate_signals.py"),
      "--symbols",
      "000001,600036",
    ]);
  });

  test("allows conservative data update params to override defaults", () => {
    const command = buildQuantTaskCommand("data_update", {
      projectRoot: "/repo",
      params: { symbols: ["600519", "000001"], days: 2, force: true },
    });

    expect(command.args).toEqual([
      path.join("/repo", "quant/quantsys/data/pipeline.py"),
      "update-klines",
      "--symbols",
      "600519,000001",
      "--days",
      "2",
    ]);
  });
});

describe("QuantTaskRunner", () => {
  test("fails before spawn when the mapped script is missing", async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), "quant-runner-"));
    const runner = new QuantTaskRunner({ projectRoot: tempRoot });

    try {
      await expect(runner.run("daily_report")).rejects.toThrow(
        "Quant task script not found"
      );
    } finally {
      await rm(tempRoot, { recursive: true, force: true });
    }
  });

  test("executes a mapped script and returns stdout stderr and exit code", async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), "quant-runner-"));
    const scriptPath = path.join(tempRoot, "quant/scripts/daily_report.py");
    const runner = new QuantTaskRunner({ projectRoot: tempRoot });

    try {
      await mkdir(path.dirname(scriptPath), { recursive: true });
      await writeFile(
        scriptPath,
        "print('daily report ok')\n",
        "utf8"
      );

      const result = await runner.run("daily_report");

      expect(result).toMatchObject({
        exitCode: 0,
        stdout: "daily report ok\n",
        stderr: "",
      });
    } finally {
      await rm(tempRoot, { recursive: true, force: true });
    }
  });

  test("truncates verbose command output before returning result", async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), "quant-runner-"));
    const scriptPath = path.join(tempRoot, "quant/scripts/daily_report.py");
    const runner = new QuantTaskRunner({
      projectRoot: tempRoot,
      maxOutputChars: 12,
    });

    try {
      await mkdir(path.dirname(scriptPath), { recursive: true });
      await writeFile(
        scriptPath,
        "import sys\nprint('abcdefghijklmnopqrstuvwxyz')\nprint('0123456789abcdef', file=sys.stderr)\n",
        "utf8"
      );

      const result = await runner.run("daily_report");

      expect(result.stdout).toBe("pqrstuvwxyz\n");
      expect(result.stderr).toBe("56789abcdef\n");
    } finally {
      await rm(tempRoot, { recursive: true, force: true });
    }
  });

  test("kills a running command when abort signal fires", async () => {
    const tempRoot = await mkdtemp(path.join(os.tmpdir(), "quant-runner-"));
    const scriptPath = path.join(tempRoot, "quant/scripts/daily_report.py");
    const controller = new AbortController();
    const runner = new QuantTaskRunner({ projectRoot: tempRoot });

    try {
      await mkdir(path.dirname(scriptPath), { recursive: true });
      await writeFile(
        scriptPath,
        "import time\nprint('started', flush=True)\ntime.sleep(30)\n",
        "utf8"
      );

      const running = runner.run("daily_report", {}, controller.signal);
      setTimeout(() => controller.abort(), 100);

      await expect(running).rejects.toThrow("Quant task aborted");
    } finally {
      await rm(tempRoot, { recursive: true, force: true });
    }
  });
});
