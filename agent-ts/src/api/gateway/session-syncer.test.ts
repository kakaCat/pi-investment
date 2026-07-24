import { mkdtempSync, readFileSync, rmSync, writeFileSync, mkdirSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { SessionSyncer } from "./session-syncer.js";
import { emitSessionEvent, resetSessionEventState } from "./session-events.js";

describe("SessionSyncer", () => {
  let dir: string;
  let posted: any[];
  let syncer: SessionSyncer;

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "sync-"));
    resetSessionEventState(dir);
    posted = [];
  });
  afterEach(async () => {
    await syncer?.stop();
    rmSync(dir, { recursive: true, force: true });
  });

  function makeSyncer(fetchImpl: any) {
    return new SessionSyncer({
      apiBase: "http://v2.test:5001",
      sessionsRootDir: dir,
      stateFile: join(dir, ".sync-state.json"),
      flushIntervalMs: 60 * 60 * 1000, // 测试中只手动 flush
      fetchImpl,
    });
  }

  const okFetch = async (_url: string, opts: any) => {
    posted.push({ url: _url, body: JSON.parse(opts.body) });
    return { ok: true, json: async () => ({ success: true }) } as any;
  };

  it("事件入队并批量 POST 到 v2，成功后推进 lastSyncedSeq", async () => {
    syncer = makeSyncer(okFetch);
    syncer.start();
    emitSessionEvent("agent:main:wake:default", { type: "session_start", channel: "wake", peerId: "default", agentId: "main" });
    emitSessionEvent("agent:main:wake:default", { type: "user_message", messageId: "m1", text: "hi" });

    await syncer.flush();

    expect(posted).toHaveLength(1);
    expect(posted[0].url).toBe("http://v2.test:5001/api/sessions/events");
    expect(posted[0].body.events).toHaveLength(2);
    expect(posted[0].body.events[0]).toMatchObject({
      session_key: "agent:main:wake:default", seq: 1, event_type: "session_start",
    });

    const state = JSON.parse(readFileSync(join(dir, ".sync-state.json"), "utf-8"));
    expect(state["agent:main:wake:default"]).toBe(2);
  });

  it("POST 失败保留事件，下次 flush 重试", async () => {
    let calls = 0;
    syncer = makeSyncer(async (url: string, opts: any) => {
      calls++;
      if (calls === 1) throw new Error("v2 down");
      return okFetch(url, opts);
    });
    syncer.start();
    emitSessionEvent("agent:main:wake:default", { type: "error", stage: "x", message: "y" });

    await syncer.flush();
    expect(posted).toHaveLength(0);

    await syncer.flush();
    expect(posted).toHaveLength(1);
    expect(posted[0].body.events[0].seq).toBe(1);
  });

  it("重启后从 lastSyncedSeq 断点续传", async () => {
    // 模拟：磁盘上已有 3 条事件，state 记录已同步 2 条
    const sessionDir = join(dir, "agent:main:wake:default");
    mkdirSync(sessionDir, { recursive: true });
    const lines = [1, 2, 3].map((seq) =>
      JSON.stringify({ seq, timestamp: "2026-07-22T00:00:00Z", type: "user_message", messageId: `m${seq}`, text: `t${seq}` })
    );
    writeFileSync(join(sessionDir, "events.jsonl"), lines.join("\n") + "\n");
    writeFileSync(join(dir, ".sync-state.json"), JSON.stringify({ "agent:main:wake:default": 2 }));

    syncer = makeSyncer(okFetch);
    syncer.start();
    await syncer.flush();

    expect(posted).toHaveLength(1);
    expect(posted[0].body.events).toHaveLength(1);
    expect(posted[0].body.events[0].seq).toBe(3);
  });
});
