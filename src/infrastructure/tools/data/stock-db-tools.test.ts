import { describe, expect, jest, test } from "@jest/globals";

const execSyncMock = jest.fn<(command: string, options?: { cwd?: string; encoding?: string }) => string>();
const actualChildProcess = await import("node:child_process");

jest.unstable_mockModule("child_process", () => ({
  ...actualChildProcess,
  execSync: execSyncMock,
}));

const { manageStockDBTool } = await import("./stock-db-tools.js");
const { allCustomTools } = await import("./index.js");

describe("manageStockDBTool", () => {
  test("runs full pipeline update for the given market", async () => {
    execSyncMock.mockReturnValueOnce("pipeline updated");

    const result = await (manageStockDBTool.execute as any)("test-call", {
      action: "pipeline_update",
      market: "HK",
    });

    expect(execSyncMock).toHaveBeenCalledWith("python pipeline/pipeline.py full --market HK", {
      cwd: process.cwd(),
      encoding: "utf-8",
    });
    expect(result.content[0].text).toBe("pipeline updated");
  });

  test("runs pipeline status command", async () => {
    execSyncMock.mockReturnValueOnce("pipeline status");

    const result = await (manageStockDBTool.execute as any)("test-call", {
      action: "pipeline_status",
    });

    expect(execSyncMock).toHaveBeenCalledWith("python pipeline/pipeline.py status", {
      cwd: process.cwd(),
      encoding: "utf-8",
    });
    expect(result.content[0].text).toBe("pipeline status");
  });

  test("registers the tool in the custom tool list", () => {
    expect(allCustomTools.some((tool: { name: string }) => tool.name === "manage_stock_db")).toBe(true);
  });
});
