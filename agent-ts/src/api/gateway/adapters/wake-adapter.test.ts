import { mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { WakeAdapter, buildPromptFromEvent, formatEventLabel } from "./wake-adapter.js";
import { resetSessionEventState } from "../session-events.js";
import type { GatewayHandlers } from "../types.js";

const PORT = 39217;
const BASE = `http://127.0.0.1:${PORT}`;

describe("WakeAdapter", () => {
  let adapter: WakeAdapter;
  let dir: string;
  const dispatched: any[] = [];
  const handlers: GatewayHandlers = {
    dispatch: async (event) => { dispatched.push(event); return "agent回复"; },
    isProcessing: () => false,
    abort: async () => true,
  };

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), "wake-"));
    resetSessionEventState(dir);
    dispatched.length = 0;
  });
  afterEach(() => {
    adapter?.shutdown();
    rmSync(dir, { recursive: true, force: true });
  });

  it("token 配置后无凭证返回 401", async () => {
    adapter = new WakeAdapter({ port: PORT, token: "secret-token" });
    adapter.start(handlers);
    const resp = await fetch(`${BASE}/wake`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event: "market_alert", data: {} }),
    });
    expect(resp.status).toBe(401);
  });

  it("正确 token + 事件 → dispatch 并返回回复", async () => {
    adapter = new WakeAdapter({ port: PORT, token: "secret-token" });
    adapter.start(handlers);
    const resp = await fetch(`${BASE}/wake`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Wake-Token": "secret-token" },
      body: JSON.stringify({ event: "daily_report", task_name: "日报", data: { date: "2026-07-22" } }),
    });
    expect(resp.status).toBe(200);
    const body = await resp.json() as any;
    expect(body.success).toBe(true);
    expect(body.reply).toBe("agent回复");
    expect(dispatched).toHaveLength(1);
    expect(dispatched[0]).toMatchObject({ channel: "wake", peerId: "default", event: "daily_report" });
    expect(dispatched[0].text).toContain("日报");
  });

  it("缺少必填字段返回 400", async () => {
    adapter = new WakeAdapter({ port: PORT }); // 无 token → dev 放行
    adapter.start(handlers);
    const resp = await fetch(`${BASE}/wake`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(resp.status).toBe(400);
  });

  it("/wake/health 无需鉴权", async () => {
    adapter = new WakeAdapter({ port: PORT, token: "secret-token" });
    adapter.start(handlers);
    const resp = await fetch(`${BASE}/wake/health`);
    expect(resp.status).toBe(200);
  });

  it("buildPromptFromEvent 覆盖核心事件类型", () => {
    expect(buildPromptFromEvent("market_alert", undefined, undefined, { sh_change: -0.04 })).toContain("市场异动");
    expect(buildPromptFromEvent("daily_report", 1, "日报任务", {})).toContain("日报任务");
    expect(buildPromptFromEvent("unknown_event", undefined, undefined, {})).toContain("unknown_event");
  });

  it("formatEventLabel 不产出 undefined（watch 事件无 task 字段时回退 rule_id）", () => {
    expect(formatEventLabel(undefined, undefined)).not.toContain("undefined");
    expect(formatEventLabel(undefined, undefined, { rule_id: 22 })).toBe("rule:22");
    expect(formatEventLabel("日报", undefined)).toBe("日报");
    expect(formatEventLabel(undefined, 7)).toBe("7");
  });
});
