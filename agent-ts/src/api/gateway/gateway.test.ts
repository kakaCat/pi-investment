import { mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { AgentGateway } from "./gateway.js";
import { resetSessionEventState } from "./session-events.js";
import type { ChannelAgentSession } from "./channel-session-manager.js";

function fakeSession(reply: string): ChannelAgentSession {
  return {
    async prompt() {},
    async abort() {},
    dispose() {},
    agent: { state: { messages: [{ role: "assistant", content: reply }] } },
  } as any;
}

function makeGateway(dir: string) {
  return new AgentGateway({
    sessionsRootDir: dir,
    createSession: async () => fakeSession("回复内容"),
  });
}

describe("AgentGateway", () => {
  let dir: string;
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "gw-"));
    resetSessionEventState(dir);
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it("dispatch 按 sessionKey 创建会话并返回回复", async () => {
    const gw = makeGateway(dir);
    const reply = await gw.dispatch({
      channel: "wake", peerId: "default", messageId: "m1", text: "分析市场",
    });
    expect(reply).toBe("回复内容");
  });

  it("同一 channel+peer 复用会话，不同 channel 隔离", async () => {
    let created = 0;
    const gw = new AgentGateway({
      sessionsRootDir: dir,
      createSession: async () => { created++; return fakeSession("r"); },
    });
    await gw.dispatch({ channel: "feishu", peerId: "oc_1", messageId: "m1", text: "a" });
    await gw.dispatch({ channel: "feishu", peerId: "oc_1", messageId: "m2", text: "b" });
    await gw.dispatch({ channel: "wake", peerId: "oc_1", messageId: "m3", text: "c" });
    expect(created).toBe(2); // feishu:oc_1 与 wake:oc_1 各一个
  });

  it("isDuplicate 去重", async () => {
    const gw = makeGateway(dir);
    expect(gw.isDuplicate("m1")).toBe(false);
    expect(gw.isDuplicate("m1")).toBe(true);
  });

  it("handlers 暴露给 adapter", async () => {
    const gw = makeGateway(dir);
    const handlers = gw.handlers();
    expect(typeof handlers.dispatch).toBe("function");
    expect(typeof handlers.isProcessing).toBe("function");
    expect(typeof handlers.abort).toBe("function");
  });
});
