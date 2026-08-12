import { afterEach, describe, expect, jest, test } from "@jest/globals";
import { mkdtempSync, readFileSync, rmSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";

const originalCwd = process.cwd();
let tempDir: string | null = null;

afterEach(() => {
  process.chdir(originalCwd);
  jest.resetModules();
  jest.restoreAllMocks();
  if (tempDir) {
    rmSync(tempDir, { recursive: true, force: true });
    tempDir = null;
  }
});

/** 构造一个只实现 subscribe 的假 session，捕获 attachLogger 注册的事件监听器 */
function createFakeSession() {
  const listeners: Array<(event: any) => void> = [];
  return {
    session: {
      subscribe: (fn: (event: any) => void) => {
        listeners.push(fn);
        return () => {};
      },
    },
    emit: (event: any) => listeners.forEach((fn) => fn(event)),
  };
}

describe("attachLogger auto_retry 事件", () => {
  test("auto_retry_start 输出 console 提示并写 llm.retry 事件", async () => {
    tempDir = mkdtempSync(join(tmpdir(), "pi-invest-retry-vis-"));
    process.chdir(tempDir);

    const logger = await import("../logging/observable-logger.js");
    logger.initSession("20260730020101_retryvis1");

    const { attachLogger } = await import("./session-factory.js");
    const { session, emit } = createFakeSession();
    attachLogger(session as any, "main");

    const logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    emit({ type: "auto_retry_start", attempt: 2, maxAttempts: 5, delayMs: 6000, errorMessage: "terminated" });

    expect(logSpy).toHaveBeenCalledWith(
      expect.stringContaining("6s 后重试 (2/5): terminated")
    );

    const eventsFile = join(tempDir, ".pi-invest", "sessions", "20260730020101_retryvis1", "events.jsonl");
    const events = readFileSync(eventsFile, "utf-8").trim().split("\n").map((line) => JSON.parse(line));
    const retryEvent = events.find((event) => event.event === "llm.retry" && event.phase === "start");
    expect(retryEvent).toBeDefined();
    expect(retryEvent.attempt).toBe(2);
    expect(retryEvent.maxAttempts).toBe(5);
    expect(retryEvent.delayMs).toBe(6000);
    expect(retryEvent.errorMessage).toBe("terminated");
  });

  test("auto_retry_end 成功时输出 ✅ 并落日志", async () => {
    tempDir = mkdtempSync(join(tmpdir(), "pi-invest-retry-vis-ok-"));
    process.chdir(tempDir);

    const logger = await import("../logging/observable-logger.js");
    logger.initSession("20260730020202_retryvis2");

    const { attachLogger } = await import("./session-factory.js");
    const { session, emit } = createFakeSession();
    attachLogger(session as any, "main");

    const logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    emit({ type: "auto_retry_end", success: true, attempt: 2 });

    expect(logSpy).toHaveBeenCalledWith(expect.stringContaining("重试成功"));

    const eventsFile = join(tempDir, ".pi-invest", "sessions", "20260730020202_retryvis2", "events.jsonl");
    const events = readFileSync(eventsFile, "utf-8").trim().split("\n").map((line) => JSON.parse(line));
    const retryEvent = events.find((event) => event.event === "llm.retry" && event.phase === "end");
    expect(retryEvent.success).toBe(true);
    expect(retryEvent.attempt).toBe(2);
  });

  test("auto_retry_end 失败时输出 ❌ 并落 finalError", async () => {
    tempDir = mkdtempSync(join(tmpdir(), "pi-invest-retry-vis-fail-"));
    process.chdir(tempDir);

    const logger = await import("../logging/observable-logger.js");
    logger.initSession("20260730020303_retryvis3");

    const { attachLogger } = await import("./session-factory.js");
    const { session, emit } = createFakeSession();
    attachLogger(session as any, "main");

    const errSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    emit({ type: "auto_retry_end", success: false, attempt: 5, finalError: "terminated" });

    expect(errSpy).toHaveBeenCalledWith(
      expect.stringContaining("重试耗尽（5 次）: terminated")
    );

    const eventsFile = join(tempDir, ".pi-invest", "sessions", "20260730020303_retryvis3", "events.jsonl");
    const events = readFileSync(eventsFile, "utf-8").trim().split("\n").map((line) => JSON.parse(line));
    const retryEvent = events.find((event) => event.event === "llm.retry" && event.phase === "end");
    expect(retryEvent.success).toBe(false);
    expect(retryEvent.finalError).toBe("terminated");
  });
});

describe("wrapSessionWithLogger 技能路由", () => {
  /** 假 session：带 subscribe（attachLogger 用）+ prompt 捕获实际收到的消息 */
  function createPromptCapturingSession() {
    const received: Array<{ message: string; options: any }> = [];
    return {
      session: {
        subscribe: () => () => {},
        prompt: async (message: string, options?: any) => {
          received.push({ message, options });
        },
      },
      received,
    };
  }

  test("交互消息照常强制路由", async () => {
    tempDir = mkdtempSync(join(tmpdir(), "pi-invest-routing-"));
    process.chdir(tempDir);

    const logger = await import("../logging/observable-logger.js");
    logger.initSession("20260812000001_routing1");

    const { initSkillRouter } = await import("../../services/intelligence/skill-router.js");
    initSkillRouter([{ name: "portfolio-entry" }] as any);

    const { wrapSessionWithLogger } = await import("./session-factory.js");
    const { session, received } = createPromptCapturingSession();
    wrapSessionWithLogger(session as any);

    await session.prompt("帮我记录交易，我卖了茅台100股");

    expect(received[0].message).toBe("/skill:portfolio-entry 帮我记录交易，我卖了茅台100股");
  });

  test("skipSkillRouting 的调度消息原样透传、不强制路由", async () => {
    tempDir = mkdtempSync(join(tmpdir(), "pi-invest-routing-"));
    process.chdir(tempDir);

    const logger = await import("../logging/observable-logger.js");
    logger.initSession("20260812000002_routing2");

    const { initSkillRouter } = await import("../../services/intelligence/skill-router.js");
    initSkillRouter([{ name: "portfolio-entry" }] as any);

    const { wrapSessionWithLogger } = await import("./session-factory.js");
    const { session, received } = createPromptCapturingSession();
    wrapSessionWithLogger(session as any);

    const taskMessage = "📚 每日复盘：记录交易总结，分析卖出买入决策";
    await session.prompt(taskMessage, { skipSkillRouting: true });

    expect(received[0].message).toBe(taskMessage);
  });
});
