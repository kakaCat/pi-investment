import { describe, expect, it, jest } from "@jest/globals";

import { buildQuantCliArgs, runQuantCli } from "./quant-cli-client.js";

describe("quant-cli-client", () => {
  it("builds python module args with domain action and json flag", () => {
    const args = buildQuantCliArgs("backtest", "run", {
      symbol: "600519",
      days: 365,
      tune: true,
      ignored: undefined,
      empty: false,
    });

    expect(args).toEqual([
      "-m",
      "quantsys.cli",
      "backtest",
      "+run",
      "--json",
      "--symbol",
      "600519",
      "--days",
      "365",
      "--tune",
    ]);
  });

  it("parses successful quant cli json output", async () => {
    const spawn = jest.fn(() =>
      Promise.resolve({
        exitCode: 0,
        stdout: JSON.stringify({
          ok: true,
          command: "data.status",
          data: { exists: true },
          error: null,
        }),
        stderr: "",
      })
    );

    const result = await runQuantCli("data", "status", {}, { spawn });

    expect(result.ok).toBe(true);
    expect(result.command).toBe("data.status");
    expect(result.data).toEqual({ exists: true });
    expect(spawn).toHaveBeenCalledWith(
      "python",
      ["-m", "quantsys.cli", "data", "+status", "--json"],
      expect.objectContaining({ cwd: expect.stringContaining("/quant") }),
      undefined
    );
  });

  it("throws a readable error when cli returns ok false", async () => {
    const spawn = jest.fn(() =>
      Promise.resolve({
        exitCode: 2,
        stdout: JSON.stringify({
          ok: false,
          command: "unknown.missing",
          error: { code: "UNKNOWN_COMMAND", message: "Unknown command" },
        }),
        stderr: "",
      })
    );

    await expect(
      runQuantCli("unknown", "missing", {}, { spawn })
    ).rejects.toThrow("UNKNOWN_COMMAND: Unknown command");
  });
});
