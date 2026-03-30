import { afterEach, describe, expect, test } from "@jest/globals";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import { FeishuSessionManager, type FeishuAgentSession } from "./feishu-session-manager.js";

interface MockSession {
  prompt: (text: string) => Promise<void>;
  abort: () => Promise<void>;
  dispose: () => void;
  agent: {
    state: {
      messages: Array<{ role: string; content: Array<{ type: string; text: string }> }>;
    };
  };
}

function flushMicrotasks(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function createDeferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T | PromiseLike<T>) => void;
  reject: (reason?: unknown) => void;
} {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });

  return { promise, resolve, reject };
}

describe("FeishuSessionManager", () => {
  const tempDirs: string[] = [];

  afterEach(() => {
    for (const dir of tempDirs.splice(0)) {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  test("deduplicates message ids", () => {
    const rootDir = mkdtempSync(join(tmpdir(), "feishu-manager-"));
    tempDirs.push(rootDir);

    const manager = new FeishuSessionManager({
      sessionsRootDir: rootDir,
      createSession: async () => ({
        prompt: async () => {},
        abort: async () => {},
        dispose: () => {},
        agent: { state: { messages: [] } },
      }),
    });

    expect(manager.isDuplicate("msg-1")).toBe(false);
    expect(manager.isDuplicate("msg-1")).toBe(true);

    manager.shutdown();
  });

  test("serializes messages within the same chat and writes log entries", async () => {
    const rootDir = mkdtempSync(join(tmpdir(), "feishu-manager-"));
    tempDirs.push(rootDir);

    const firstTurn = createDeferred<void>();
    const secondTurn = createDeferred<void>();
    const promptCalls: string[] = [];
    let promptCount = 0;

    const session: MockSession = {
      prompt: async (text: string) => {
        promptCalls.push(text);
        promptCount += 1;
        if (promptCount === 1) {
          await firstTurn.promise;
        } else {
          await secondTurn.promise;
        }
      },
      abort: async () => {},
      dispose: () => {},
      agent: { state: { messages: [] } },
    };

    const manager = new FeishuSessionManager({
      sessionsRootDir: rootDir,
      createSession: async () => session,
      extractReply: () => {
        return `reply-${promptCount}`;
      },
    });

    const firstPromise = manager.processMessage("chat-a", "msg-1", "first");
    await flushMicrotasks();
    const secondPromise = manager.processMessage("chat-a", "msg-2", "second");
    await flushMicrotasks();

    expect(manager.isProcessing("chat-a")).toBe(true);
    expect(promptCalls).toEqual(["first"]);

    firstTurn.resolve();
    await flushMicrotasks();
    expect(promptCalls).toEqual(["first", "second"]);

    secondTurn.resolve();

    await expect(firstPromise).resolves.toBe("reply-1");
    await expect(secondPromise).resolves.toBe("reply-2");

    const logFile = join(rootDir, "chat-a", "log.jsonl");
    expect(existsSync(logFile)).toBe(true);

    const lines = readFileSync(logFile, "utf-8")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));

    expect(lines).toHaveLength(4);
    expect(lines[0]).toMatchObject({ role: "user", content: "first", message_id: "msg-1" });
    expect(lines[1]).toMatchObject({ role: "assistant", content: "reply-1" });
    expect(lines[2]).toMatchObject({ role: "user", content: "second", message_id: "msg-2" });
    expect(lines[3]).toMatchObject({ role: "assistant", content: "reply-2" });

    manager.shutdown();
  });

  test("processes different chats in parallel", async () => {
    const rootDir = mkdtempSync(join(tmpdir(), "feishu-manager-"));
    tempDirs.push(rootDir);

    const pending = new Map<string, ReturnType<typeof createDeferred<void>>>();
    const started: string[] = [];

    const manager = new FeishuSessionManager({
      sessionsRootDir: rootDir,
      createSession: async (chatId: string): Promise<FeishuAgentSession> => {
        const deferred = createDeferred<void>();
        pending.set(chatId, deferred);

        return {
          prompt: async () => {
            started.push(chatId);
            await deferred.promise;
          },
          abort: async () => {},
          dispose: () => {},
          agent: { state: { messages: [] } },
        };
      },
      extractReply: (_session: FeishuAgentSession, chatId: string) => `reply-${chatId}`,
    });

    const firstPromise = manager.processMessage("chat-a", "msg-1", "hello");
    const secondPromise = manager.processMessage("chat-b", "msg-2", "world");
    await flushMicrotasks();

    expect(started.sort()).toEqual(["chat-a", "chat-b"]);

    pending.get("chat-a")!.resolve();
    pending.get("chat-b")!.resolve();

    await expect(firstPromise).resolves.toBe("reply-chat-a");
    await expect(secondPromise).resolves.toBe("reply-chat-b");

    manager.shutdown();
  });

  test("aborts the active chat task and clears queued work", async () => {
    const rootDir = mkdtempSync(join(tmpdir(), "feishu-manager-"));
    tempDirs.push(rootDir);

    const runningTurn = createDeferred<void>();
    const abortError = new Error("aborted");
    let abortInvoked = false;

    const session: MockSession = {
      prompt: async () => runningTurn.promise,
      abort: async () => {
        abortInvoked = true;
        runningTurn.reject(abortError);
      },
      dispose: () => {},
      agent: { state: { messages: [] } },
    };

    const manager = new FeishuSessionManager({
      sessionsRootDir: rootDir,
      createSession: async () => session,
    });

    const firstPromise = manager.processMessage("chat-a", "msg-1", "first");
    await flushMicrotasks();
    const secondPromise = manager.processMessage("chat-a", "msg-2", "second");
    await flushMicrotasks();

    await expect(manager.abort("chat-a")).resolves.toBe(true);
    expect(abortInvoked).toBe(true);

    await expect(firstPromise).rejects.toThrow("aborted");
    await expect(secondPromise).rejects.toThrow("cancelled");

    manager.shutdown();
  });
});
