import { mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import {
  emitSessionEvent,
  onSessionEvent,
  readEvents,
  setSessionContext,
  getSessionContext,
  resetSessionEventState,
  type StoredSessionEvent,
} from "./session-events.js";

describe("session-events", () => {
  let dir: string;
  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "sess-events-"));
    resetSessionEventState(dir);
  });
  afterEach(() => rmSync(dir, { recursive: true, force: true }));

  it("事件写入 events.jsonl 且 seq 单调递增", () => {
    emitSessionEvent("agent:main:wake:default", { type: "session_start", channel: "wake", peerId: "default", agentId: "main" });
    emitSessionEvent("agent:main:wake:default", { type: "user_message", messageId: "m1", text: "hello" });

    const events = readEvents(join(dir, "agent:main:wake:default"));
    expect(events).toHaveLength(2);
    expect(events[0].seq).toBe(1);
    expect(events[1].seq).toBe(2);
    expect(events[1].type).toBe("user_message");
    expect(events[1].timestamp).toBeTruthy();
  });

  it("不同 sessionKey 的 seq 各自独立", () => {
    emitSessionEvent("agent:main:wake:a", { type: "session_start", channel: "wake", peerId: "a", agentId: "main" });
    emitSessionEvent("agent:main:feishu:b", { type: "session_start", channel: "feishu", peerId: "b", agentId: "main" });
    expect(readEvents(join(dir, "agent:main:feishu:b"))[0].seq).toBe(1);
  });

  it("监听器收到事件（syncer 订阅点）", () => {
    const received: Array<{ sessionKey: string; event: StoredSessionEvent }> = [];
    onSessionEvent((sessionKey, event) => received.push({ sessionKey, event }));
    emitSessionEvent("agent:main:wake:default", { type: "error", stage: "dispatch", message: "boom" });
    expect(received).toHaveLength(1);
    expect(received[0].event.type).toBe("error");
  });

  it("setSessionContext / getSessionContext", () => {
    expect(getSessionContext()).toBeNull();
    setSessionContext("agent:main:wake:default", "/tmp/x");
    expect(getSessionContext()).toEqual({ sessionKey: "agent:main:wake:default", sessionDir: "/tmp/x" });
  });
});
