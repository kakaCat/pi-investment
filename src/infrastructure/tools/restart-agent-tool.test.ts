import { describe, expect, jest, test } from "@jest/globals";

const execSyncMock = jest.fn();
const actualChildProcess = await import("node:child_process");

jest.unstable_mockModule("child_process", () => ({
  ...actualChildProcess,
  execSync: execSyncMock,
}));

const { buildRestartExecPlan, resetTerminalForRestart } = await import("./restart-agent-tool.js");

describe("resetTerminalForRestart", () => {
  test("cleans TUI keyboard modes and restores UTF-8 terminal input before restart", () => {
    const write = jest.fn();
    const setRawMode = jest.fn();
    const stdin = { isTTY: true, setRawMode };
    const stdout = { write };

    resetTerminalForRestart({ stdin, stdout });

    expect(write).toHaveBeenCalledWith("\x1b[?2004l");
    expect(write).toHaveBeenCalledWith("\x1b[<u");
    expect(write).toHaveBeenCalledWith("\x1b[>4;0m");
    expect(setRawMode).toHaveBeenCalledWith(false);
    expect(execSyncMock).toHaveBeenCalledWith("stty sane 2>/dev/null || true", {
      stdio: "ignore",
      timeout: 1000,
    });
    expect(execSyncMock).toHaveBeenCalledWith("stty iutf8 2>/dev/null || true", {
      stdio: "ignore",
      timeout: 1000,
    });
  });
});

describe("buildRestartExecPlan", () => {
  test("uses execve-compatible argv for the local tsx binary", () => {
    const plan = buildRestartExecPlan({
      projectRoot: "/project",
      argv: ["/node", "/project/src/index.ts"],
      localTsxExists: true,
    });

    expect(plan.file).toBe("/project/node_modules/.bin/tsx");
    expect(plan.args).toEqual(["/project/node_modules/.bin/tsx", "/project/src/index.ts"]);
  });

  test("falls back to node plus the current argv when no local tsx binary is available", () => {
    const plan = buildRestartExecPlan({
      projectRoot: "/project",
      argv: ["/node", "--loader", "tsx", "/project/src/index.ts"],
      execPath: "/node",
      localTsxExists: false,
    });

    expect(plan.file).toBe("/node");
    expect(plan.args).toEqual(["/node", "--loader", "tsx", "/project/src/index.ts"]);
  });
});
