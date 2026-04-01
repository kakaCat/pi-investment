import { describe, expect, jest, test } from "@jest/globals";

const execSyncMock = jest.fn<(command: string, options?: { encoding?: string }) => string>();
const actualChildProcess = await import("node:child_process");

jest.unstable_mockModule("child_process", () => ({
  ...actualChildProcess,
  execSync: execSyncMock,
}));

const { QuantService } = await import("./quant-service.js");

describe("QuantService", () => {
  test("runs backtest command for a named strategy", () => {
    execSyncMock.mockReturnValueOnce("strategy backtest");
    const service = new QuantService();

    const output = service.backtestStrategy("momentum");

    expect(execSyncMock).toHaveBeenCalledWith("python ml-pipeline/ml_pipeline.py backtest --strategy momentum", {
      encoding: "utf-8",
    });
    expect(output).toBe("strategy backtest");
  });
});
