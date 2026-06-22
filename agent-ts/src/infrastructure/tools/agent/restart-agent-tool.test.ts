import { describe, expect, jest, test } from "@jest/globals";

const execSyncMock = jest.fn();
const actualChildProcess = await import("node:child_process");

jest.unstable_mockModule("child_process", () => ({
  ...actualChildProcess,
  execSync: execSyncMock,
}));

const { buildRestartContext, buildRestartExecPlan, findProjectRoot, resetTerminalForRestart } = await import("./restart-agent-tool.js");

describe("buildRestartContext", () => {
  test("stores the SDK session file and id so restart can resume the same session", () => {
    const context = buildRestartContext({
      cwd: "/project",
      prevSessionKey: "20260521010101_abcd1234",
      conversationMessages: [
        { role: "user", content: "hello", timestamp: "2026-05-21T00:00:00.000Z" },
      ],
      sdkSessionFile: "/Users/mac/.pi/agent/sessions/project/session.jsonl",
      sdkSessionId: "sdk-session-id",
      env: {
        NODE_ENV: "test",
        BACKGROUND_MODE: "false",
      },
    });

    expect(context.prevSessionKey).toBe("20260521010101_abcd1234");
    expect(context.sdkSessionFile).toBe("/Users/mac/.pi/agent/sessions/project/session.jsonl");
    expect(context.sdkSessionId).toBe("sdk-session-id");
    expect(context.conversationMessageCount).toBe(1);
    expect(context.messages).toHaveLength(1);
  });
});

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
  test("finds the repository root from a nested source directory", () => {
    expect(findProjectRoot("/Users/mac/Documents/ai/pi-investment/src/infrastructure/tools/agent")).toBe(
      "/Users/mac/Documents/ai/pi-investment",
    );
  });

  test("uses execve-compatible argv for the local tsx binary", () => {
    const plan = buildRestartExecPlan({
      projectRoot: "/project",
      argv: ["/node", "/project/src/index.ts"],
      localTsxExists: true,
    });

    expect(plan.file).toBe("/project/node_modules/.bin/tsx");
    expect(plan.args).toEqual(["/project/node_modules/.bin/tsx", "/project/src/index.ts"]);
  });

  test("uses the repository root by default so restart can find the local tsx binary", () => {
    const plan = buildRestartExecPlan({
      argv: ["/node", "/Users/mac/Documents/ai/pi-investment/src/index.ts"],
    });

    expect(plan.file).toBe("/Users/mac/Documents/ai/pi-investment/agent-ts/node_modules/.bin/tsx");
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
