import { mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { ChannelSessionManager, type ChannelAgentSession } from "./channel-session-manager.js";
import { readEvents, resetSessionEventState } from "./session-events.js";

function fakeSession(reply = "ok"): ChannelAgentSession & { prompted: string[] } {
  const prompted: string[] = [];
  return {
    prompted,
    async prompt(text: string) { prompted.push(text); },
    async abort() {},
    dispose() {},
    agent: { state: { messages: [{ role: "assistant", content: reply }] } },
  } as any;
}

describe("ChannelSessionManager (gateway 版)", () => {
  let dir: string;
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "csm-"));
    resetSessionEventState(dir);
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it("消息处理全流程并发射 session 事件", async () => {
    const session = fakeSession("分析结果");
    const mgr = new ChannelSessionManager({
      channelName: "Wake",
      sessionsRootDir: dir,
      createSession: async () => session,
    });

    const reply = await mgr.processMessage("agent:main:wake:default", "m1", "你好");

    expect(reply).toBe("分析结果");
    expect(session.prompted).toEqual(["你好"]);

    const events = readEvents(join(dir, "agent:main:wake:default"));
    const types = events.map((e) => e.type);
    expect(types).toEqual(["session_start", "user_message", "assistant_reply"]);
  });

  it("abort 时 reject 排队中的 promise（修复悬挂 bug）", async () => {
    let releaseFirst!: () => void;
    const slowSession: ChannelAgentSession = {
      prompt: () => new Promise<void>((resolve) => { releaseFirst = resolve; }),
      abort: async () => { releaseFirst(); },
      dispose() {},
      agent: { state: { messages: [] } },
    } as any;

    const mgr = new ChannelSessionManager({
      channelName: "Wake",
      sessionsRootDir: dir,
      createSession: async () => slowSession,
    });

    const first = mgr.processMessage("agent:main:wake:default", "m1", "慢任务");
    // 等第一条开始处理后再排第二条
    await new Promise((r) => setTimeout(r, 50));
    const second = mgr.processMessage("agent:main:wake:default", "m2", "排队任务");
    // 等第二条真正进入队列（processMessage 内部 getOrCreateSession 是异步的）
    await new Promise((r) => setTimeout(r, 50));

    const aborted = await mgr.abort("agent:main:wake:default");
    expect(aborted).toBe(true);
    await expect(second).rejects.toThrow("Task cancelled");
    await first;
  });

  it("LLM 调用失败（stopReason=error）时 reject，而不是静默返回空串", async () => {
    // 复现 2026-08-05 事故：Kimi 401 → SDK 记录 stopReason=error 的空 assistant 消息但不抛出，
    // gateway 把空串当成功回复，v2 误判"送达成功"不重试，watch 事件全部无声丢失
    const session: ChannelAgentSession = {
      async prompt() {},
      async abort() {},
      dispose() {},
      agent: {
        state: {
          messages: [
            {
              role: "assistant",
              content: [],
              stopReason: "error",
              errorMessage: "401 The API Key appears to be invalid or may have expired.",
            },
          ],
        },
      },
    } as any;

    const mgr = new ChannelSessionManager({
      channelName: "Wake",
      sessionsRootDir: dir,
      createSession: async () => session,
    });

    await expect(
      mgr.processMessage("agent:main:wake:default", "m1", "【盯盘触发】...")
    ).rejects.toThrow("401 The API Key appears to be invalid");

    const events = readEvents(join(dir, "agent:main:wake:default"));
    expect(events.map((e) => e.type)).toContain("error");
  });

  it("shutdown 释放所有 session", async () => {
    let disposed = 0;
    const session = { ...fakeSession(), dispose() { disposed++; } };
    const mgr = new ChannelSessionManager({
      channelName: "Wake",
      sessionsRootDir: dir,
      createSession: async () => session as any,
    });
    await mgr.processMessage("agent:main:wake:default", "m1", "hi");
    mgr.shutdown();
    expect(disposed).toBe(1);
  });
});
