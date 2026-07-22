# Agent Gateway 与 Session 资产化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一 agent-ts 入站通道为 Gateway + Adapter 架构，session 结构化事件流本地持久化并异步同步到 quantsys-v2，提供诊断 API。

**Architecture:** OpenClaw 式 gateway-first：`InboundEvent` 统一信封 + `ChannelAdapter` 接口 + canonical session key（`agent:main:{channel}:{peerId}`）；session 事件写本地 `events.jsonl`（权威源），`SessionSyncer` 幂等批量同步到 v2 两张新表；v2 提供查询/诊断 API。设计文档：`docs/superpowers/specs/2026-07-22-agent-gateway-session-design.md`

**Tech Stack:** agent-ts: TypeScript / Express / lark SDK / Jest(ESM)。quantsys-v2: Flask / psycopg2(BaseRepository 原生 SQL) / pytest。

**前置状态（已完成，勿重复）：**
- v2 `agent_notification_service.py` 已有 `send_reminder()` 且 `import logging` 已修复
- agent-ts `decision_record` 工具已存在并已注册（`src/infrastructure/tools/decision/decision-record-tool.ts`）
- v2 测试 `tests/services/test_agent_notification_service.py` 已存在

---

### Task 1: session-key 模块

**Files:**
- Create: `agent-ts/src/api/gateway/session-key.ts`
- Test: `agent-ts/src/api/gateway/session-key.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// agent-ts/src/api/gateway/session-key.test.ts
import { buildSessionKey, parseSessionKey } from "./session-key.js";

describe("buildSessionKey", () => {
  it("构造 canonical key", () => {
    expect(buildSessionKey("feishu", "oc_abc123")).toBe("agent:main:feishu:oc_abc123");
    expect(buildSessionKey("wake", "default")).toBe("agent:main:wake:default");
  });

  it("peerId 中的非法字符替换为下划线", () => {
    expect(buildSessionKey("feishu", "oc_xx/yy zz")).toBe("agent:main:feishu:oc_xx_yy_zz");
  });

  it("parseSessionKey 还原各部分", () => {
    expect(parseSessionKey("agent:main:feishu:oc_abc")).toEqual({
      agentId: "main",
      channel: "feishu",
      peerId: "oc_abc",
    });
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd agent-ts && npx jest src/api/gateway/session-key.test.ts 2>&1 | tail -3`
Expected: FAIL — Cannot find module './session-key.js'

- [ ] **Step 3: 实现**

```typescript
// agent-ts/src/api/gateway/session-key.ts
/**
 * Canonical Session Key — 全局唯一会话寻址
 * 格式: agent:{agentId}:{channel}:{peerId}
 * 参考 OpenClaw canonical session key 设计
 */
export type ChannelName = 'feishu' | 'wake' | 'cli';

export function buildSessionKey(channel: ChannelName, peerId: string, agentId = 'main'): string {
  const safePeer = peerId.replace(/[^A-Za-z0-9_-]/g, '_');
  return `agent:${agentId}:${channel}:${safePeer}`;
}

export function parseSessionKey(key: string): { agentId: string; channel: string; peerId: string } {
  const parts = key.split(':');
  if (parts.length !== 4 || parts[0] !== 'agent') {
    throw new Error(`Invalid session key: ${key}`);
  }
  return { agentId: parts[1], channel: parts[2], peerId: parts[3] };
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd agent-ts && npx jest src/api/gateway/session-key.test.ts 2>&1 | tail -3`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd agent-ts && git add src/api/gateway/session-key.ts src/api/gateway/session-key.test.ts
git commit -m "feat(gateway): canonical session key 模块"
```

---

### Task 2: session-events 事件总线与本地持久化

**Files:**
- Create: `agent-ts/src/api/gateway/session-events.ts`
- Test: `agent-ts/src/api/gateway/session-events.test.ts`

说明：事件类型即 spec §4.1。`seq` 由本模块按 sessionKey 单调递增分配；事件写 `{sessionsRootDir}/{sessionKey}/events.jsonl` 并同步通知监听器（syncer 订阅）。`setSessionContext` 让工具层（decision_record 等）感知所属会话。

- [ ] **Step 1: 写失败测试**

```typescript
// agent-ts/src/api/gateway/session-events.test.ts
import { mkdtempSync, readFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import {
  emitSessionEvent,
  onSessionEvent,
  readEvents,
  setSessionContext,
  getSessionContext,
  resetSessionEventState,
  type SessionEvent,
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
    const received: Array<{ sessionKey: string; event: SessionEvent }> = [];
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd agent-ts && npx jest src/api/gateway/session-events.test.ts 2>&1 | tail -3`
Expected: FAIL — Cannot find module './session-events.js'

- [ ] **Step 3: 实现**

```typescript
// agent-ts/src/api/gateway/session-events.ts
/**
 * Session 结构化事件流 — agent 工作质量审计的核心数据
 *
 * 本地 events.jsonl 是权威源；监听器（SessionSyncer）异步同步到 v2。
 */
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { join } from "path";
import { paths } from "../../config/config.js";

export type SessionEvent =
  | { type: 'session_start'; channel: string; peerId: string; agentId: string; legacy?: boolean }
  | { type: 'user_message'; messageId: string; text: string; event?: string; data?: Record<string, any> }
  | { type: 'tool_call'; toolName: string; params?: Record<string, any>; durationMs: number; success: boolean; error?: string; resultSummary?: string }
  | { type: 'assistant_reply'; text: string; replyLength: number }
  | { type: 'error'; stage: string; message: string }
  | { type: 'session_idle'; reason: string }
  | { type: 'legacy_note'; note: string };

export interface StoredSessionEvent {
  seq: number;
  timestamp: string;
  type: string;
  [key: string]: any;
}

type EventListener = (sessionKey: string, event: StoredSessionEvent) => void;

let _sessionsRootDir = join(paths.piDir, "agent-sessions");
const _seqCounters = new Map<string, number>();
const _listeners: EventListener[] = [];

/** 测试用：重置内存状态并覆盖根目录 */
export function resetSessionEventState(rootDir?: string): void {
  _seqCounters.clear();
  _listeners.length = 0;
  if (rootDir) _sessionsRootDir = rootDir;
  setSessionContext(null);
}

export function getAgentSessionsRootDir(): string {
  return _sessionsRootDir;
}

export function sessionDirOf(sessionKey: string): string {
  return join(_sessionsRootDir, sessionKey);
}

/** 追加事件到 events.jsonl，并通知监听器。写盘失败只告警不抛错（不阻塞主链路） */
export function emitSessionEvent(sessionKey: string, event: SessionEvent): void {
  const seq = (_seqCounters.get(sessionKey) ?? 0) + 1;
  _seqCounters.set(sessionKey, seq);

  const stored: StoredSessionEvent = {
    ...event,
    seq,
    timestamp: new Date().toISOString(),
  };

  try {
    const dir = sessionDirOf(sessionKey);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    appendFileSync(join(dir, "events.jsonl"), JSON.stringify(stored) + "\n", "utf-8");
  } catch (err) {
    console.warn(`⚠️ [session-events] 写入 events.jsonl 失败:`, err instanceof Error ? err.message : err);
  }

  for (const listener of _listeners) {
    try {
      listener(sessionKey, stored);
    } catch (err) {
      console.warn(`⚠️ [session-events] 监听器异常:`, err instanceof Error ? err.message : err);
    }
  }
}

export function onSessionEvent(listener: EventListener): void {
  _listeners.push(listener);
}

/** 读取会话目录下的事件流 */
export function readEvents(sessionDir: string): StoredSessionEvent[] {
  const file = join(sessionDir, "events.jsonl");
  if (!existsSync(file)) return [];
  return readFileSync(file, "utf-8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as StoredSessionEvent);
}

// ─── 当前会话上下文（工具层感知所属会话）───
let _context: { sessionKey: string; sessionDir: string } | null = null;

export function setSessionContext(sessionKey: string | null, sessionDir?: string): void {
  _context = sessionKey ? { sessionKey, sessionDir: sessionDir ?? sessionDirOf(sessionKey) } : null;
}

export function getSessionContext(): { sessionKey: string; sessionDir: string } | null {
  return _context;
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd agent-ts && npx jest src/api/gateway/session-events.test.ts 2>&1 | tail -3`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd agent-ts && git add src/api/gateway/session-events.ts src/api/gateway/session-events.test.ts
git commit -m "feat(gateway): session 结构化事件总线与本地持久化"
```

---

### Task 3: gateway/types.ts 类型定义

**Files:**
- Create: `agent-ts/src/api/gateway/types.ts`

无测试（纯类型）。在后续 Task 中编译验证。

- [ ] **Step 1: 创建类型文件**

```typescript
// agent-ts/src/api/gateway/types.ts
/**
 * Gateway 核心类型：统一入站信封与通道适配器接口
 * 参考 OpenClaw: channel adapter 只做"翻译+传输"，agent 逻辑对传输层无感
 */
import type { ChannelName } from "./session-key.js";

export interface InboundEvent {
  channel: ChannelName;
  peerId: string;               // feishu: chatId; wake: session_id || 'default'
  messageId: string;            // 去重键
  text: string;                 // 已规范化的 prompt 文本
  event?: string;               // wake 事件类型（market_alert 等）
  data?: Record<string, any>;   // 原始载荷（审计用）
}

export interface GatewayHandlers {
  dispatch(event: InboundEvent): Promise<string>;
  isProcessing(sessionKey: string): boolean;
  abort(sessionKey: string): Promise<boolean>;
}

export interface ChannelAdapter {
  readonly name: string;
  start(handlers: GatewayHandlers): void;
  shutdown(): void;
}
```

- [ ] **Step 2: 编译验证**

Run: `cd agent-ts && npx tsc --noEmit -p tsconfig.build.json 2>&1 | head -3`
Expected: 无输出（exit 0）

- [ ] **Step 3: Commit**

```bash
cd agent-ts && git add src/api/gateway/types.ts
git commit -m "feat(gateway): InboundEvent / ChannelAdapter 核心类型"
```

---

### Task 4: 迁移并增强 ChannelSessionManager

**Files:**
- Create: `agent-ts/src/api/gateway/channel-session-manager.ts`
- Test: `agent-ts/src/api/gateway/channel-session-manager.test.ts`

说明：以现有 `src/api/channel-session-manager.ts` 为基底移入 gateway/，增强三点（合并 FeishuSessionManager 的优点）：
1. 新增 `shutdown()`（释放全部 session）
2. `abort()` 时 reject 排队中的 promise（修复 wake `/wake/abort` 悬挂 bug）
3. 集成 session-events：session 创建/用户消息/回复/错误时发事件。manager 的 `sessionId` 参数即 sessionKey（由 gateway 传入）

- [ ] **Step 1: 写失败测试**

```typescript
// agent-ts/src/api/gateway/channel-session-manager.test.ts
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

    const aborted = await mgr.abort("agent:main:wake:default");
    expect(aborted).toBe(true);
    await expect(second).rejects.toThrow("Task cancelled");
    await first;
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd agent-ts && npx jest src/api/gateway/channel-session-manager.test.ts 2>&1 | tail -3`
Expected: FAIL — Cannot find module

- [ ] **Step 3: 实现**（在现有 `src/api/channel-session-manager.ts` 基础上改造）

```bash
cd agent-ts && cp src/api/channel-session-manager.ts src/api/gateway/channel-session-manager.ts
```

然后对新文件做 4 处修改：

**3a. 顶部 import 增加：**

```typescript
import { emitSessionEvent } from "./session-events.js";
import { parseSessionKey } from "./session-key.js";
```

**3b. `getOrCreateSession` 中，session 创建成功后发射 session_start：**

在 `this.sessions.set(sessionId, state);` 之后、`this.logConversation(...)` 之前插入：

```typescript
    const { channel, peerId, agentId } = parseSessionKey(sessionId);
    emitSessionEvent(sessionId, { type: "session_start", channel, peerId, agentId });
```

**3c. `drainQueue` 的 while 循环内，发射 user_message / assistant_reply / error 事件：**

`this.logConversation(state, `\n[User ...]`);` 之后插入：

```typescript
        emitSessionEvent(state.sessionId, { type: "user_message", messageId: item.messageId, text: item.text });
```

`item.resolve(reply);` 之前插入：

```typescript
        if (reply) {
          emitSessionEvent(state.sessionId, { type: "assistant_reply", text: reply, replyLength: reply.length });
        }
```

catch 块内 `item.reject(...)` 之前插入：

```typescript
        emitSessionEvent(state.sessionId, { type: "error", stage: "prompt", message: errorMessage });
```

**3d. `abort()` 修复：reject 排队 promise；新增 `shutdown()`：**

替换整个 abort 方法：

```typescript
  async abort(sessionId: string): Promise<boolean> {
    const state = this.sessions.get(sessionId);
    if (!state?.processing) {
      return false;
    }

    // 先 reject 排队中的消息，避免调用方悬挂
    const queued = state.queue.splice(0);
    const cancellationError = new Error("Task cancelled");
    for (const item of queued) {
      item.reject(cancellationError);
    }

    try {
      await state.session.abort();
      return true;
    } catch (error) {
      console.error(`❌ [${this.options.channelName}] 中断会话失败:`, error);
      return false;
    }
  }

  /** 释放所有 session（进程退出时调用） */
  shutdown(): void {
    for (const state of this.sessions.values()) {
      state.session.dispose();
    }
    this.sessions.clear();
    this.messageIds.clear();
  }
```

- [ ] **Step 4: 运行确认通过**

Run: `cd agent-ts && npx jest src/api/gateway/channel-session-manager.test.ts 2>&1 | tail -3`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd agent-ts && git add src/api/gateway/channel-session-manager.ts src/api/gateway/channel-session-manager.test.ts
git commit -m "feat(gateway): manager 移入并增强（shutdown/abort reject/session 事件）"
```

---

### Task 5: session-factory 共享会话工厂

**Files:**
- Create: `agent-ts/src/api/gateway/session-factory.ts`

说明：抽取 feishu.ts 与 wake-channel.ts 中几乎相同的 createSession + beforePrompt。采用 feishu 版的完整 beforePrompt（含 microCompact、自动压缩、重试死循环检测）——wake 版是其子集，统一后 wake 通道也获得这些保护。无独立测试：行为经 Task 9 的入口集成与现有 feishu 流程验证；此处保证编译通过。

- [ ] **Step 1: 创建文件**

```typescript
// agent-ts/src/api/gateway/session-factory.ts
/**
 * 共享 Gateway 会话工厂
 * 从 feishu.ts / wake-channel.ts 抽取的公共会话创建与提示词准备逻辑
 */
import { estimateTokens, SessionManager, type Skill } from "../../sdk-facade.js";
import { createTrackedSession } from "../../infrastructure/session/session-factory.js";
import type { ToolDefinition } from "../../infrastructure/tools/index.js";
import { createModel, paths } from "../../config/config.js";
import {
  autoRecall,
  buildAgentSystemPrompt,
  readDailyMemory,
} from "../../core/agent/system-prompt.js";
import { setSessionDataDir } from "../../infrastructure/tools/shared/session-utils.js";
import {
  setSystemPrompt,
  getMessages,
  getMessageCount,
  hasState,
  addMessage,
  createUserMessage,
} from "../../core/agent/session-adapter.js";
import { microCompact, compactConversationHistory } from "../../services/compaction/compaction-service.js";
import * as logger from "../../infrastructure/logging/observable-logger.js";
import { setSessionContext } from "./session-events.js";
import type { ChannelAgentSession } from "./channel-session-manager.js";

export interface GatewaySessionFactory {
  createSession(sessionKey: string, sessionDir: string): Promise<ChannelAgentSession>;
  beforePrompt(session: ChannelAgentSession, sessionKey: string, text: string, sessionDir: string): Promise<void>;
}

export function createGatewaySessionFactory(
  tools: ToolDefinition[],
  skills: Skill[],
): GatewaySessionFactory {
  return {
    createSession: async (_sessionKey, sessionDir) => {
      const trackedSession = await createTrackedSession({
        agentType: "subagent",
        createOptions: {
          cwd: paths.root,
          sessionManager: SessionManager.continueRecent(paths.root, sessionDir),
          model: createModel(),
          systemPrompt: () => buildAgentSystemPrompt({
            memoryContext: "",
            dailyMemory: "",
            tools,
            workspaceDir: paths.root,
          }),
          customTools: tools,
          skills,
        },
      });
      return trackedSession as unknown as ChannelAgentSession;
    },

    beforePrompt: async (session, sessionKey, text, sessionDir) => {
      if (sessionDir) setSessionDataDir(sessionDir);
      setSessionContext(sessionKey, sessionDir);

      const memoryContext = autoRecall(text);
      const dailyMemory = readDailyMemory(paths.piDir);
      const systemPrompt = buildAgentSystemPrompt({
        memoryContext,
        dailyMemory,
        tools,
        workspaceDir: paths.root,
      });

      if (!hasState(session)) return;

      setSystemPrompt(session, systemPrompt);
      logger.logSystemPrompt(systemPrompt, getMessageCount(session));

      const messages = getMessages(session);
      microCompact(messages as any);

      const totalTokens = messages.reduce(
        (sum: number, message: unknown) => sum + estimateTokens(message as any),
        0,
      );
      if (totalTokens > 40000) {
        compactConversationHistory(messages as any, (m: unknown) => estimateTokens(m as any), {
          keepTurns: 3,
          tokenThreshold: 40000,
        });

        console.log("🧠 触发自动记忆保存");
        await session.prompt(
          "Pre-compaction memory flush: Use memory_write to save important facts, " +
          "decisions, and context worth remembering across sessions. Be selective.",
        );
      }

      // 工具重试死循环检测：最近 5+ 个连续 toolResult 全是错误时注入终止指令
      const recentToolErrors: Array<{ toolName: string }> = [];
      for (let i = messages.length - 1; i >= 0; i--) {
        const m = messages[i] as any;
        if (m.role === "toolResult") {
          if (m.isError) recentToolErrors.unshift(m);
          else break;
        } else if (m.role === "assistant") {
          continue;
        } else {
          break;
        }
      }
      if (recentToolErrors.length >= 5) {
        const failedTools = [...new Set(recentToolErrors.map((m: any) => m.toolName))].join(", ");
        console.warn(`⚠️ 检测到工具重试死循环: ${recentToolErrors.length} 次连续失败 (${failedTools})，注入终止指令`);
        addMessage(session, createUserMessage(
          `[系统提示] 以下工具连续失败 ${recentToolErrors.length} 次: ${failedTools}。请停止重试这些工具，基于已有数据直接给出分析结论，不要再调用这些失败的工具。`,
        ));
      }
    },
  };
}
```

- [ ] **Step 2: 编译验证**

Run: `cd agent-ts && npx tsc --noEmit -p tsconfig.build.json 2>&1 | head -5`
Expected: exit 0

- [ ] **Step 3: Commit**

```bash
cd agent-ts && git add src/api/gateway/session-factory.ts
git commit -m "feat(gateway): 共享会话工厂（合并 feishu/wake 重复逻辑）"
```

---

### Task 6: AgentGateway 核心

**Files:**
- Create: `agent-ts/src/api/gateway/gateway.ts`
- Test: `agent-ts/src/api/gateway/gateway.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// agent-ts/src/api/gateway/gateway.test.ts
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd agent-ts && npx jest src/api/gateway/gateway.test.ts 2>&1 | tail -3`
Expected: FAIL — Cannot find module './gateway.js'

- [ ] **Step 3: 实现**

```typescript
// agent-ts/src/api/gateway/gateway.ts
/**
 * AgentGateway — 入站通道的统一汇聚点
 * 所有 adapter 把消息规范化为 InboundEvent 后交给 dispatch
 */
import { ChannelSessionManager, type ChannelAgentSession } from "./channel-session-manager.js";
import { buildSessionKey } from "./session-key.js";
import type { GatewayHandlers, InboundEvent } from "./types.js";

export interface AgentGatewayOptions {
  sessionsRootDir: string;
  createSession: (sessionKey: string, sessionDir: string) => Promise<ChannelAgentSession>;
  beforePrompt?: (session: ChannelAgentSession, sessionKey: string, text: string, sessionDir: string) => Promise<void>;
}

export class AgentGateway {
  private manager: ChannelSessionManager;

  constructor(options: AgentGatewayOptions) {
    this.manager = new ChannelSessionManager({
      channelName: "Gateway",
      sessionsRootDir: options.sessionsRootDir,
      createSession: options.createSession,
      beforePrompt: options.beforePrompt,
    });
  }

  isDuplicate(messageId: string): boolean {
    return this.manager.isDuplicate(messageId);
  }

  isProcessing(sessionKey: string): boolean {
    return this.manager.isProcessing(sessionKey);
  }

  async dispatch(event: InboundEvent): Promise<string> {
    const sessionKey = buildSessionKey(event.channel, event.peerId);
    return this.manager.processMessage(sessionKey, event.messageId, event.text);
  }

  async abort(sessionKey: string): Promise<boolean> {
    return this.manager.abort(sessionKey);
  }

  /** 提供给 adapter 的处理器集合 */
  handlers(): GatewayHandlers {
    return {
      dispatch: (event) => this.dispatch(event),
      isProcessing: (sessionKey) => this.isProcessing(sessionKey),
      abort: (sessionKey) => this.abort(sessionKey),
    };
  }

  shutdown(): void {
    this.manager.shutdown();
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd agent-ts && npx jest src/api/gateway/gateway.test.ts 2>&1 | tail -3`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd agent-ts && git add src/api/gateway/gateway.ts src/api/gateway/gateway.test.ts
git commit -m "feat(gateway): AgentGateway 核心"
```

---

### Task 7: SessionSyncer 异步同步

**Files:**
- Create: `agent-ts/src/api/gateway/session-syncer.ts`
- Test: `agent-ts/src/api/gateway/session-syncer.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// agent-ts/src/api/gateway/session-syncer.test.ts
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

  const okFetch = async (url: string, opts: any) => {
    posted.push({ url, body: JSON.parse(opts.body) });
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
    syncer = makeSyncer(async () => {
      calls++;
      if (calls === 1) throw new Error("v2 down");
      return okFetch("", { body: "{}" });
    });
    // 第二次调用的 okFetch 需要真实 body，换实现：
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
```

- [ ] **Step 2: 运行确认失败**

Run: `cd agent-ts && npx jest src/api/gateway/session-syncer.test.ts 2>&1 | tail -3`
Expected: FAIL — Cannot find module './session-syncer.js'

- [ ] **Step 3: 实现**

```typescript
// agent-ts/src/api/gateway/session-syncer.ts
/**
 * SessionSyncer — session 事件异步同步到 quantsys-v2
 *
 * 原则：本地 events.jsonl 是权威源；同步失败只记日志，永不阻塞消息处理。
 * 幂等：v2 端 UNIQUE(session_key, seq) 去重，重复推送安全。
 * 断点续传：.sync-state.json 记录每个 sessionKey 的 lastSyncedSeq。
 */
import { existsSync, readFileSync, readdirSync, writeFileSync } from "fs";
import { join } from "path";
import { onSessionEvent, readEvents, type StoredSessionEvent } from "./session-events.js";

export interface SessionSyncerOptions {
  apiBase: string;               // 如 http://127.0.0.1:5001
  sessionsRootDir: string;
  stateFile?: string;
  flushIntervalMs?: number;      // 默认 5000
  batchSize?: number;            // 默认 20
  fetchImpl?: typeof fetch;
}

interface QueuedEvent {
  session_key: string;
  seq: number;
  event_type: string;
  payload: Record<string, any>;
  created_at: string;
}

export class SessionSyncer {
  private queue: QueuedEvent[] = [];
  private state: Record<string, number> = {};
  private timer: NodeJS.Timeout | null = null;
  private flushing = false;
  private readonly stateFile: string;
  private readonly flushIntervalMs: number;
  private readonly batchSize: number;
  private readonly fetchImpl: typeof fetch;

  constructor(private options: SessionSyncerOptions) {
    this.stateFile = options.stateFile ?? join(options.sessionsRootDir, ".sync-state.json");
    this.flushIntervalMs = options.flushIntervalMs ?? 5000;
    this.batchSize = options.batchSize ?? 20;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.loadState();
  }

  start(): void {
    onSessionEvent((sessionKey, event) => this.enqueue(sessionKey, event));
    this.resumeUnsynced();
    this.timer = setInterval(() => { void this.flush(); }, this.flushIntervalMs);
    this.timer.unref?.();
  }

  async stop(): Promise<void> {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    await this.flush();
  }

  enqueue(sessionKey: string, event: StoredSessionEvent): void {
    const { seq, timestamp, type, ...payload } = event;
    this.queue.push({
      session_key: sessionKey,
      seq,
      event_type: type,
      payload,
      created_at: timestamp,
    });
  }

  async flush(): Promise<void> {
    if (this.flushing || this.queue.length === 0) return;
    this.flushing = true;
    try {
      const batch = this.queue.slice(0, this.batchSize);
      const resp = await this.fetchImpl(`${this.options.apiBase}/api/sessions/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: batch }),
      });
      const result = (await resp.json()) as any;
      if (!resp.ok || result?.success === false) {
        throw new Error(result?.error || `HTTP ${resp.status}`);
      }
      // 成功：移出队列并推进断点
      this.queue.splice(0, batch.length);
      for (const e of batch) {
        this.state[e.session_key] = Math.max(this.state[e.session_key] ?? 0, e.seq);
      }
      this.saveState();
    } catch (err) {
      // 失败保留队列，下轮重试（指数退避由 flush 间隔兜底，本地数据不丢）
      console.warn(`⚠️ [syncer] 同步失败，${this.queue.length} 条事件待重试:`,
        err instanceof Error ? err.message : err);
    } finally {
      this.flushing = false;
    }
  }

  /** 启动时扫描磁盘，把 lastSyncedSeq 之后的事件重新入队 */
  private resumeUnsynced(): void {
    if (!existsSync(this.options.sessionsRootDir)) return;
    for (const entry of readdirSync(this.options.sessionsRootDir, { withFileTypes: true })) {
      if (!entry.isDirectory() || !entry.name.startsWith("agent:")) continue;
      const lastSynced = this.state[entry.name] ?? 0;
      const events = readEvents(join(this.options.sessionsRootDir, entry.name));
      for (const event of events) {
        if (event.seq > lastSynced) {
          this.enqueue(entry.name, event);
        }
      }
    }
  }

  private loadState(): void {
    try {
      if (existsSync(this.stateFile)) {
        this.state = JSON.parse(readFileSync(this.stateFile, "utf-8"));
      }
    } catch {
      this.state = {};
    }
  }

  private saveState(): void {
    try {
      writeFileSync(this.stateFile, JSON.stringify(this.state, null, 2), "utf-8");
    } catch (err) {
      console.warn(`⚠️ [syncer] 保存 sync state 失败:`, err instanceof Error ? err.message : err);
    }
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd agent-ts && npx jest src/api/gateway/session-syncer.test.ts 2>&1 | tail -3`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd agent-ts && git add src/api/gateway/session-syncer.ts src/api/gateway/session-syncer.test.ts
git commit -m "feat(gateway): SessionSyncer 幂等批量同步与断点续传"
```

---

### Task 8: WakeAdapter（端口 3002 + token 鉴权）

**Files:**
- Create: `agent-ts/src/api/gateway/adapters/wake-adapter.ts`
- Test: `agent-ts/src/api/gateway/adapters/wake-adapter.test.ts`

说明：承载现有 `wake-channel.ts` 的 HTTP 面（`/wake`、`/wake/abort`、`/wake/health`）与 `buildPromptFromEvent` 逻辑，新增 token 中间件，默认端口改为 3002。

- [ ] **Step 1: 写失败测试**（真实 HTTP，用高端口避免冲突）

```typescript
// agent-ts/src/api/gateway/adapters/wake-adapter.test.ts
import { mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { WakeAdapter, buildPromptFromEvent } from "./wake-adapter.js";
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
    const body = await resp.json();
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
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd agent-ts && npx jest src/api/gateway/adapters/wake-adapter.test.ts 2>&1 | tail -3`
Expected: FAIL — Cannot find module

- [ ] **Step 3: 实现**

```typescript
// agent-ts/src/api/gateway/adapters/wake-adapter.ts
/**
 * WakeAdapter — quantsys-v2 HTTP 推送通道
 * POST /wake (X-Wake-Token 鉴权) → InboundEvent → Gateway.dispatch
 */
import express, { type Express } from "express";
import cors from "cors";
import type { Server } from "http";
import type { ChannelAdapter, GatewayHandlers, InboundEvent } from "../types.js";

export interface WakeAdapterOptions {
  port?: number;    // 默认 3002
  token?: string;   // WAKE_TOKEN；未配置时放行 + 警告（dev 模式）
}

export class WakeAdapter implements ChannelAdapter {
  readonly name = "wake";
  private server: Server | null = null;
  private readonly port: number;
  private readonly token?: string;

  constructor(options: WakeAdapterOptions = {}) {
    this.port = options.port ?? (process.env.WAKE_CHANNEL_PORT ? parseInt(process.env.WAKE_CHANNEL_PORT) : 3002);
    this.token = options.token ?? process.env.WAKE_TOKEN;
  }

  start(handlers: GatewayHandlers): void {
    const app: Express = express();
    app.use(cors({ origin: process.env.CORS_ORIGIN || "*" }));
    app.use(express.json());

    // token 鉴权中间件（/wake/health 公开）
    app.use((req, res, next) => {
      if (req.path === "/wake/health") return next();
      if (!this.token) return next();
      if (req.headers["x-wake-token"] === this.token) return next();
      res.status(401).json({ success: false, error: "Unauthorized: invalid or missing X-Wake-Token" });
    });

    app.post("/wake", async (req, res) => {
      const { event, task_id, task_name, data, session_id } = req.body;
      if (!event || !data) {
        return res.status(400).json({ success: false, error: "Missing required fields: event, data" });
      }

      const inbound: InboundEvent = {
        channel: "wake",
        peerId: session_id || "default",
        messageId: `wake-${event}-${Date.now()}`,
        text: buildPromptFromEvent(event, task_id, task_name, data),
        event,
        data,
      };

      console.log(`📬 [Wake] 收到事件: ${event} (task: ${task_name || task_id})`);
      try {
        const reply = await handlers.dispatch(inbound);
        res.json({ success: true, event, session_id: inbound.peerId, reply: reply.substring(0, 500) });
      } catch (error) {
        console.error(`❌ [Wake] 事件处理失败:`, error);
        res.status(500).json({ success: false, error: error instanceof Error ? error.message : "Unknown error" });
      }
    });

    app.post("/wake/abort", async (req, res) => {
      const sessionId = req.body?.session_id || "default";
      const aborted = await handlers.abort(`agent:main:wake:${sessionId}`);
      res.json({ success: true, aborted, message: aborted ? "已中断当前任务" : "当前没有运行中的任务" });
    });

    app.get("/wake/health", (_req, res) => {
      res.json({ status: "ok", channel: "wake", timestamp: new Date().toISOString() });
    });

    this.server = app.listen(this.port, () => {
      console.log(`🔔 Wake Channel 启动: http://127.0.0.1:${this.port}`);
      if (!this.token) {
        console.warn(`⚠️ [Wake] WAKE_TOKEN 未配置，/wake 无鉴权（仅建议开发环境）`);
      }
    });
  }

  shutdown(): void {
    this.server?.close();
    this.server = null;
  }
}

/** 根据事件类型构造 Agent 提示词（规范化逻辑，adapter 内部职责） */
export function buildPromptFromEvent(
  event: string,
  task_id?: number,
  task_name?: string,
  data?: Record<string, any>,
): string {
  const taskInfo = task_name || task_id || "unknown";

  switch (event) {
    case "market_alert":
      return `【任务】请按以下步骤处理市场异动：

1. 分析当前市场数据：上证 ${data?.sh_change || "N/A"}，深证 ${data?.sz_change || "N/A"}，${data?.reason || ""}。
2. 用 market_sentiment 工具查看市场情绪。
3. 如果是大跌，用 opportunity_scan 扫描超跌机会。
4. 综合以上信息，用 feishu_notify 工具给用户发送一份完整的分析报告，内容包括：
   - 市场发生了什么
   - 原因分析
   - 情绪面判断
   - 发现的投资机会
   - 操作建议

不要只报告数据，要做真正的投资分析，所有分析结果必须通过飞书发送给用户。`;

    case "daily_report":
      return `生成每日投资报告（任务：${taskInfo}）。请使用 daily_report 工具生成报告，然后通过 feishu_notify 推送。`;

    case "weekly_report":
      return `生成每周投资报告（任务：${taskInfo}）。请汇总本周数据并通过 feishu_notify 推送报告。`;

    case "position_alert":
      return `持仓告警：${data?.symbol || "股票"}触发${data?.alert_type === "stop_loss" ? "止损" : "止盈"}。当前价格：${data?.current_price}，成本价：${data?.cost_price}。请使用 feishu_notify 推送告警。`;

    case "signal_generated":
      return `新交易信号生成（任务：${taskInfo}）。生成了 ${data?.signal_count || 0} 个新信号。请使用 feishu_notify 推送信号通知。`;

    case "premarket_report":
      return `生成盘前准备报告（任务：${taskInfo}）。请分析今日市场预期并通过 feishu_notify 推送。`;

    case "agent_reminder":
      return `【提醒】${data?.message || "你有一个提醒"}。请按提醒内容执行相应操作，必要时通过 feishu_notify 告知用户。`;

    default:
      return `收到 quantsys-v2 推送事件：${event}（任务：${taskInfo}）。数据：${JSON.stringify(data || {}, null, 2)}。请根据事件类型执行相应操作。`;
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd agent-ts && npx jest src/api/gateway/adapters/wake-adapter.test.ts 2>&1 | tail -3`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
cd agent-ts && git add src/api/gateway/adapters/wake-adapter.ts src/api/gateway/adapters/wake-adapter.test.ts
git commit -m "feat(gateway): WakeAdapter（端口 3002 + X-Wake-Token 鉴权）"
```

---

### Task 9: FeishuAdapter

**Files:**
- Create: `agent-ts/src/api/gateway/adapters/feishu-adapter.ts`
- Test: `agent-ts/src/api/gateway/adapters/feishu-adapter.test.ts`

说明：从 `src/api/feishu.ts` 抽取 lark 收发逻辑。可测部分是消息规范化（纯函数）；lark WSClient 部分只做薄封装。CronService 保留在 adapter 内（它回复飞书，属于飞书通道职责）。

- [ ] **Step 1: 写失败测试**

```typescript
// agent-ts/src/api/gateway/adapters/feishu-adapter.test.ts
import { normalizeFeishuMessage } from "./feishu-adapter.js";

describe("normalizeFeishuMessage", () => {
  it("文本消息 → InboundEvent", () => {
    const event = normalizeFeishuMessage({
      message_id: "om_123",
      chat_id: "oc_abc",
      message_type: "text",
      content: JSON.stringify({ text: "分析一下茅台" }),
    });
    expect(event).toEqual({
      channel: "feishu",
      peerId: "oc_abc",
      messageId: "om_123",
      text: "分析一下茅台",
    });
  });

  it("非文本消息返回 null", () => {
    expect(normalizeFeishuMessage({
      message_id: "om_1", chat_id: "oc_1", message_type: "image", content: "{}",
    })).toBeNull();
  });

  it("空文本或缺 chat_id 返回 null", () => {
    expect(normalizeFeishuMessage({
      message_id: "om_1", chat_id: "oc_1", message_type: "text", content: JSON.stringify({ text: "  " }),
    })).toBeNull();
    expect(normalizeFeishuMessage({
      message_id: "om_1", chat_id: "", message_type: "text", content: JSON.stringify({ text: "hi" }),
    })).toBeNull();
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `cd agent-ts && npx jest src/api/gateway/adapters/feishu-adapter.test.ts 2>&1 | tail -3`
Expected: FAIL — Cannot find module

- [ ] **Step 3: 实现**

```typescript
// agent-ts/src/api/gateway/adapters/feishu-adapter.ts
/**
 * FeishuAdapter — 飞书通道（lark WSClient 长连接）
 * 只负责"翻译+传输"：飞书消息 ↔ InboundEvent
 */
import * as lark from "@larksuiteoapi/node-sdk";
import { join } from "path";
import { paths } from "../../../config/config.js";
// @ts-ignore - Module stub needed
import { CronService, type CronJobPayload } from "../../../services/operations/cron-service.js";
import { buildSessionKey } from "../session-key.js";
import type { ChannelAdapter, GatewayHandlers, InboundEvent } from "../types.js";

const FEISHU_CRON_FILE = join(paths.piDir, "FEISHU_CRON.json");

export interface FeishuAdapterOptions {
  appId: string;
  appSecret: string;
}

/** 纯函数：飞书消息 → InboundEvent（不可规范化的返回 null） */
export function normalizeFeishuMessage(message: any): InboundEvent | null {
  if (!message || message.message_type !== "text") return null;
  const text = parseTextMessage(message.content);
  if (!text || !message.chat_id) return null;
  return {
    channel: "feishu",
    peerId: message.chat_id,
    messageId: message.message_id,
    text,
  };
}

function parseTextMessage(content: string): string {
  try {
    const parsed = JSON.parse(content);
    return (parsed.text ?? "").trim();
  } catch {
    return "";
  }
}

export class FeishuAdapter implements ChannelAdapter {
  readonly name = "feishu";
  private client: lark.Client;
  private wsClient: lark.WSClient | null = null;
  private cronService: CronService | null = null;

  constructor(private options: FeishuAdapterOptions) {
    this.client = new lark.Client({ appId: options.appId, appSecret: options.appSecret });
  }

  start(handlers: GatewayHandlers): void {
    this.cronService = new CronService(
      FEISHU_CRON_FILE,
      paths.piDir,
      async (payload: CronJobPayload) => {
        if (payload.kind !== "agent_turn" || !payload.chatId || !payload.message) return;
        const reply = await handlers.dispatch({
          channel: "feishu",
          peerId: payload.chatId,
          messageId: `cron-${Date.now()}`,
          text: payload.message,
        });
        if (reply) await this.sendReply(payload.chatId, reply);
      },
    );

    const dispatcher = new lark.EventDispatcher({}).register({
      "im.message.receive_v1": async (data: any) => {
        const inbound = normalizeFeishuMessage(data?.message);
        if (!inbound) return;

        if (inbound.text.toLowerCase() === "stop") {
          const aborted = await handlers.abort(buildSessionKey("feishu", inbound.peerId));
          await this.sendTextReply(inbound.peerId, aborted ? "已取消当前任务" : "当前没有运行中的任务");
          return;
        }

        const sessionKey = buildSessionKey("feishu", inbound.peerId);
        await this.sendTextReply(
          inbound.peerId,
          handlers.isProcessing(sessionKey) ? "任务处理中，消息已排队" : "收到，正在处理",
        );

        try {
          const reply = await handlers.dispatch(inbound);
          if (reply) await this.sendReply(inbound.peerId, reply);
        } catch (error) {
          console.error("❌ 飞书消息处理失败:", error instanceof Error ? error.message : String(error));
          await this.sendTextReply(inbound.peerId, "抱歉，处理消息时出现错误，请稍后重试。");
        }
      },
      "im.message.message_read_v1": async () => {},
      "im.message.reaction.created_v1": async () => {},
      "im.chat.access_event.bot_p2p_chat_entered_v1": async () => {},
    });

    this.wsClient = new lark.WSClient({
      appId: this.options.appId,
      appSecret: this.options.appSecret,
      loggerLevel: lark.LoggerLevel.error,
    });

    this.cronService.start();
    this.wsClient.start({ eventDispatcher: dispatcher });
    console.log("🤖 飞书 Bot 已启动（WebSocket 监听中）");
  }

  shutdown(): void {
    this.cronService?.stop();
  }

  private async sendTextReply(chatId: string, text: string): Promise<void> {
    await this.client.im.message.create({
      params: { receive_id_type: "chat_id" },
      data: {
        receive_id: chatId,
        msg_type: "text",
        content: JSON.stringify({ text }),
      },
    });
  }

  private async sendReply(chatId: string, text: string): Promise<void> {
    // 飞书单条消息长度限制，分段发送
    const MAX_LEN = 3000;
    for (let i = 0; i < text.length; i += MAX_LEN) {
      await this.sendTextReply(chatId, text.slice(i, i + MAX_LEN));
    }
  }
}
```

注意：若现有 `feishu.ts` 的 `sendReply`/`parseTextMessage` 实现与上面不同（如富文本 post 格式），以现有实现为准搬运——先读 `feishu.ts` 第 60-190 行确认。

- [ ] **Step 4: 运行确认通过**

Run: `cd agent-ts && npx jest src/api/gateway/adapters/feishu-adapter.test.ts 2>&1 | tail -3`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd agent-ts && git add src/api/gateway/adapters/feishu-adapter.ts src/api/gateway/adapters/feishu-adapter.test.ts
git commit -m "feat(gateway): FeishuAdapter（消息规范化 + WSClient 薄封装）"
```

---

### Task 10: 薄入口重写 + 删除旧文件

**Files:**
- Create: `agent-ts/src/api/gateway/start-gateway.ts`（共享 bootstrap）
- Modify: `agent-ts/src/api/start-wake-channel.ts`（重写为薄入口）
- Modify: `agent-ts/src/api/feishu.ts`（重写为薄入口）
- Delete: `agent-ts/src/api/wake-channel.ts`
- Delete: `agent-ts/src/api/channel-session-manager.ts`
- Delete: `agent-ts/src/api/feishu-session-manager.ts`
- Delete: `agent-ts/src/api/feishu-session-manager.test.ts`

- [ ] **Step 1: 创建共享 bootstrap**

```typescript
// agent-ts/src/api/gateway/start-gateway.ts
/**
 * Gateway 共享启动引导：tools + skills + factory + gateway + syncer
 * Phase 1: 每个进程挂自己的 adapter；Phase 2: 单进程挂多个 adapter
 */
import { join } from "path";
import { existsSync, mkdirSync } from "fs";
import { SessionManager as _sm, loadSkills, type Skill } from "../../sdk-facade.js";
import { allCustomTools, initMemoryTools } from "../../infrastructure/tools/index.js";
import type { ToolDefinition } from "../../infrastructure/tools/index.js";
import { setPlanToolContext } from "../../infrastructure/tools/agent/plan-tool.js";
import { paths } from "../../config/config.js";
import { AgentGateway } from "./gateway.js";
import { createGatewaySessionFactory } from "./session-factory.js";
import { SessionSyncer } from "./session-syncer.js";
import { getAgentSessionsRootDir } from "./session-events.js";
import type { ChannelAdapter } from "./types.js";

function loadProjectSkills(): Skill[] {
  try {
    // @ts-ignore - Type mismatch from SDK update
    const result = loadSkills({
      cwd: paths.root,
      skillPaths: [paths.skillsDir],
      agentDir: paths.root,
      includeDefaults: true,
    });
    return result.skills;
  } catch (error) {
    console.warn("⚠️ Skills 加载失败:", error instanceof Error ? error.message : String(error));
    return [];
  }
}

export interface GatewayHandle {
  gateway: AgentGateway;
  shutdown: () => Promise<void>;
}

export function startGateway(adapters: ChannelAdapter[]): GatewayHandle {
  const sessionsRootDir = getAgentSessionsRootDir();
  if (!existsSync(sessionsRootDir)) mkdirSync(sessionsRootDir, { recursive: true });

  const skills = loadProjectSkills();
  const tools = [...allCustomTools] as ToolDefinition[];
  console.log(`[Gateway] 已加载 ${tools.length} 个工具`);
  initMemoryTools(paths.piDir);
  setPlanToolContext(tools);

  const factory = createGatewaySessionFactory(tools, skills);
  const gateway = new AgentGateway({
    sessionsRootDir,
    createSession: factory.createSession,
    beforePrompt: factory.beforePrompt,
  });

  const syncer = new SessionSyncer({
    apiBase: process.env.QUANTSYS_V2_API_URL ?? "http://127.0.0.1:5001",
    sessionsRootDir,
  });
  syncer.start();

  const handlers = gateway.handlers();
  for (const adapter of adapters) {
    adapter.start(handlers);
  }
  console.log(`[Gateway] 已启动 ${adapters.length} 个通道: ${adapters.map((a) => a.name).join(", ")}`);
  console.log(`📁 会话目录: ${sessionsRootDir}`);

  return {
    gateway,
    shutdown: async () => {
      for (const adapter of adapters) adapter.shutdown();
      gateway.shutdown();
      await syncer.stop();
    },
  };
}
```

- [ ] **Step 2: 重写 wake 入口**

```typescript
// agent-ts/src/api/start-wake-channel.ts（全量替换）
#!/usr/bin/env node
/**
 * Wake Channel 启动脚本（薄入口）
 * quantsys-v2 推送通知接收服务：WakeAdapter + Gateway
 */
import "dotenv/config";
import { startGateway } from "./gateway/start-gateway.js";
import { WakeAdapter } from "./gateway/adapters/wake-adapter.js";

console.log("🚀 启动 Wake Channel...");
const { shutdown } = startGateway([new WakeAdapter()]);

process.on("SIGINT", async () => { await shutdown(); process.exit(0); });
process.on("SIGTERM", async () => { await shutdown(); process.exit(0); });
```

- [ ] **Step 3: 重写飞书入口**

```typescript
// agent-ts/src/api/feishu.ts（全量替换为薄入口）
/**
 * 飞书 Bot 启动脚本（薄入口）
 * FeishuAdapter + Gateway
 */
import "dotenv/config";
import { startGateway } from "./gateway/start-gateway.js";
import { FeishuAdapter } from "./gateway/adapters/feishu-adapter.js";

const appId = process.env.FEISHU_APP_ID;
const appSecret = process.env.FEISHU_APP_SECRET;
if (!appId || !appSecret) {
  console.error("❌ 缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET");
  process.exit(1);
}

console.log("🚀 启动飞书 Bot...");
const { shutdown } = startGateway([new FeishuAdapter({ appId, appSecret })]);

process.on("SIGINT", async () => { await shutdown(); process.exit(0); });
process.on("SIGTERM", async () => { await shutdown(); process.exit(0); });
```

- [ ] **Step 4: 删除旧文件并确认编译**

```bash
cd agent-ts
git rm src/api/wake-channel.ts src/api/channel-session-manager.ts src/api/feishu-session-manager.ts src/api/feishu-session-manager.test.ts
npx tsc --noEmit -p tsconfig.build.json 2>&1 | head -10
```
Expected: exit 0（若有隐藏引用，编译器会报出来——按报错处理）

- [ ] **Step 5: 全量测试**

Run: `cd agent-ts && npx jest src/api/gateway/ 2>&1 | tail -5`
Expected: 全部 passed

- [ ] **Step 6: Commit**

```bash
cd agent-ts && git add src/api/gateway/ src/api/feishu.ts src/api/start-wake-channel.ts
git commit -m "feat(gateway): 薄入口重写，删除旧平行实现（cutover）"
```

---

### Task 11: decision_record 携带 sessionKey

**Files:**
- Modify: `agent-ts/src/infrastructure/tools/decision/decision-record-tool.ts`
- Modify: `agent-ts/src/infrastructure/tools/decision/decision-record-tool.test.ts`

- [ ] **Step 1: 追加失败测试**

在现有 test 文件 describe 内追加：

```typescript
  it("有会话上下文时自动携带 session_key", async () => {
    const { setSessionContext } = await import("../../../api/gateway/session-events.js");
    setSessionContext("agent:main:wake:default", "/tmp/x");

    mockFetch.mockResolvedValue({
      json: async () => ({ success: true, data: { decision_id: "dec_9" } }),
    });

    await decisionRecordTool.execute("call-4", {
      decision_type: "refresh_pool",
      reasoning: "定时刷新",
    });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.session_key).toBe("agent:main:wake:default");
    setSessionContext(null);
  });
```

- [ ] **Step 2: 运行确认失败**

Run: `cd agent-ts && npx jest src/infrastructure/tools/decision/decision-record-tool.test.ts 2>&1 | tail -3`
Expected: FAIL — expect undefined toBe "agent:main:wake:default"

- [ ] **Step 3: 实现**（decision-record-tool.ts 的 execute 内）

import 增加：

```typescript
import { getSessionContext } from "../../../api/gateway/session-events.js";
```

body 构建处追加：

```typescript
      const sessionCtx = getSessionContext();
      if (sessionCtx) body.session_key = sessionCtx.sessionKey;
```

- [ ] **Step 4: 运行确认通过（4 passed）并 commit**

```bash
cd agent-ts && npx jest src/infrastructure/tools/decision/ 2>&1 | tail -3
git add src/infrastructure/tools/decision/
git commit -m "feat(gateway): decision_record 自动携带 session_key"
```

---

### Task 12: v2 数据库迁移

**Files:**
- Create: `quantsys-v2/infrastructure/persistence/migrations/create_agent_session_tables.sql`

- [ ] **Step 1: 创建迁移文件**

```sql
-- ============================================
-- Agent Session 审计表
-- 创建日期: 2026-07-22
-- 用途: session 事件流持久化（agent 工作质量诊断与 web 可视化）
-- ============================================

CREATE TABLE IF NOT EXISTS quant.agent_sessions (
  session_key      TEXT PRIMARY KEY,
  channel          VARCHAR(20) NOT NULL,
  peer_id          VARCHAR(200) NOT NULL,
  agent_id         VARCHAR(50) NOT NULL DEFAULT 'main',
  started_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_active_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status           VARCHAR(20) NOT NULL DEFAULT 'active',
  message_count    INT DEFAULT 0,
  tool_call_count  INT DEFAULT 0,
  error_count      INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quant.agent_session_events (
  id           BIGSERIAL PRIMARY KEY,
  session_key  TEXT NOT NULL REFERENCES quant.agent_sessions(session_key),
  seq          INT NOT NULL,
  event_type   VARCHAR(30) NOT NULL,
  payload      JSONB NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL,
  UNIQUE(session_key, seq)
);

CREATE INDEX IF NOT EXISTS idx_agent_session_events_type ON quant.agent_session_events(event_type);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_channel ON quant.agent_sessions(channel);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_active ON quant.agent_sessions(last_active_at DESC);

ALTER TABLE quant.agent_decisions ADD COLUMN IF NOT EXISTS session_key TEXT;
CREATE INDEX IF NOT EXISTS idx_agent_decisions_session ON quant.agent_decisions(session_key);

COMMENT ON TABLE quant.agent_sessions IS 'Agent 会话元数据：通道、计数器、活跃状态';
COMMENT ON TABLE quant.agent_session_events IS 'Agent 会话事件流：seq 幂等，支撑诊断与会话回放';
```

- [ ] **Step 2: 应用到生产和测试库**

```bash
cd quantsys-v2
psql -d quant_investment -f infrastructure/persistence/migrations/create_agent_session_tables.sql
psql -d quant_test -f infrastructure/persistence/migrations/create_agent_session_tables.sql
```
Expected: 两个库均输出 CREATE TABLE / CREATE INDEX / ALTER TABLE 无报错

- [ ] **Step 3: Commit**

```bash
cd quantsys-v2 && git add infrastructure/persistence/migrations/create_agent_session_tables.sql
git commit -m "feat(gateway): agent_sessions / agent_session_events 表迁移"
```

---

### Task 13: v2 SessionService（ingest + 查询 + 诊断）

**Files:**
- Create: `quantsys-v2/application/services/session_service.py`
- Test: `quantsys-v2/tests/services/test_session_service.py`

说明：DB 访问用 `BaseRepository._get_cursor()` 原生 SQL 模式（与 routes/signals.py 一致）。测试在 quant_test 库上自建表（IF NOT EXISTS，幂等）。

- [ ] **Step 1: 写失败测试**

```python
# quantsys-v2/tests/services/test_session_service.py
"""SessionService 测试：事件摄入幂等、计数器、诊断聚合"""
import pytest
from datetime import datetime, timezone
from infrastructure.persistence.database.base_repository import BaseRepository
from application.services.session_service import SessionService

DDL = """
CREATE TABLE IF NOT EXISTS quant.agent_sessions (
  session_key TEXT PRIMARY KEY, channel VARCHAR(20) NOT NULL, peer_id VARCHAR(200) NOT NULL,
  agent_id VARCHAR(50) NOT NULL DEFAULT 'main',
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), last_active_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  message_count INT DEFAULT 0, tool_call_count INT DEFAULT 0, error_count INT DEFAULT 0
);
CREATE TABLE IF NOT EXISTS quant.agent_session_events (
  id BIGSERIAL PRIMARY KEY,
  session_key TEXT NOT NULL, seq INT NOT NULL,
  event_type VARCHAR(30) NOT NULL, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(session_key, seq)
);
"""


@pytest.fixture
def service():
    repo = BaseRepository()
    cursor = repo._get_cursor()
    cursor.execute(DDL)
    cursor.execute("DELETE FROM quant.agent_session_events")
    cursor.execute("DELETE FROM quant.agent_sessions")
    repo._get_connection().commit() if hasattr(repo, '_get_connection') else None
    yield SessionService()


def _ev(seq, etype, payload, key="agent:main:wake:default"):
    return {
        "session_key": key, "seq": seq, "event_type": etype,
        "payload": payload, "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_ingest_events_creates_session_and_counts(service):
    result = service.ingest_events([
        _ev(1, "session_start", {"channel": "wake", "peerId": "default", "agentId": "main"}),
        _ev(2, "user_message", {"messageId": "m1", "text": "hi"}),
        _ev(3, "tool_call", {"toolName": "pool_manage", "durationMs": 1200, "success": True}),
        _ev(4, "assistant_reply", {"text": "done", "replyLength": 4}),
    ])
    assert result["accepted"] == 4

    session = service.get_session("agent:main:wake:default")
    assert session["channel"] == "wake"
    assert session["message_count"] == 1
    assert session["tool_call_count"] == 1
    assert session["error_count"] == 0


def test_ingest_events_idempotent(service):
    events = [_ev(1, "session_start", {"channel": "wake", "peerId": "default", "agentId": "main"})]
    service.ingest_events(events)
    result = service.ingest_events(events)  # 重复推送
    assert result["accepted"] == 0
    assert result["duplicates"] == 1

    session = service.get_session("agent:main:wake:default")
    assert session["message_count"] == 0


def test_diagnosis_aggregates(service):
    service.ingest_events([
        _ev(1, "session_start", {"channel": "wake", "peerId": "default", "agentId": "main"}),
        _ev(2, "tool_call", {"toolName": "a", "durationMs": 100, "success": True}),
        _ev(3, "tool_call", {"toolName": "b", "durationMs": 300, "success": False, "error": "timeout"}),
        _ev(4, "error", {"stage": "prompt", "message": "boom"}),
    ])
    diag = service.get_diagnosis("agent:main:wake:default")
    assert diag["tool_success_rate"] == 0.5
    assert diag["avg_tool_duration_ms"] == 200
    assert diag["error_count"] == 1
    assert diag["insight"]
```

注意 fixture 中 BaseRepository 的 commit 方式需按实际实现调整（先读 `infrastructure/persistence/database/base_repository.py` 确认连接/提交 API）。

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && ./venv/bin/python -m pytest tests/services/test_session_service.py -x -q 2>&1 | tail -3`
Expected: FAIL — ModuleNotFoundError: session_service

- [ ] **Step 3: 实现**

```python
# quantsys-v2/application/services/session_service.py
"""
Session 服务 — agent session 事件摄入、查询与诊断

设计原则：返回洞察而非原始数据（diagnosis 附解读）
"""
import structlog
from typing import Dict, Any, List, Optional
from infrastructure.persistence.database.base_repository import BaseRepository

logger = structlog.get_logger(__name__)

# 事件类型 → 会话计数器字段
_COUNTER_MAP = {
    "user_message": "message_count",
    "tool_call": "tool_call_count",
    "error": "error_count",
}


class SessionService:
    """Agent session 事件摄入与诊断服务"""

    def ingest_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量摄入事件（幂等：UNIQUE(session_key, seq)）

        Args:
            events: [{session_key, seq, event_type, payload, created_at}]

        Returns:
            {accepted, duplicates, skipped}
        """
        repo = BaseRepository()
        cursor = repo._get_cursor()
        accepted = duplicates = skipped = 0

        for ev in events:
            try:
                key = ev["session_key"]
                seq = ev["seq"]
                etype = ev["event_type"]
            except (KeyError, TypeError):
                skipped += 1
                continue

            payload = ev.get("payload") or {}
            import json
            cursor.execute(
                """
                INSERT INTO quant.agent_session_events (session_key, seq, event_type, payload, created_at)
                VALUES (%s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (session_key, seq) DO NOTHING
                RETURNING id
                """,
                (key, seq, etype, json.dumps(payload), ev.get("created_at")),
            )
            row = cursor.fetchone()
            if row is None:
                duplicates += 1
                continue

            accepted += 1
            counter = _COUNTER_MAP.get(etype)
            counter_sql = f", {counter} = {counter} + 1" if counter else ""
            cursor.execute(
                f"""
                INSERT INTO quant.agent_sessions (session_key, channel, peer_id, agent_id, last_active_at{counter and f', {counter}' or ''})
                VALUES (%s, %s, %s, %s, %s{counter and ', 1' or ''})
                ON CONFLICT (session_key) DO UPDATE SET
                  last_active_at = EXCLUDED.last_active_at{counter_sql}
                """,
                (
                    key,
                    payload.get("channel", "unknown"),
                    str(payload.get("peerId", "")),
                    payload.get("agentId", "main"),
                    ev.get("created_at"),
                ),
            )

        return {"accepted": accepted, "duplicates": duplicates, "skipped": skipped}

    def list_sessions(self, channel: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        repo = BaseRepository()
        cursor = repo._get_cursor()
        if channel:
            cursor.execute(
                "SELECT * FROM quant.agent_sessions WHERE channel = %s ORDER BY last_active_at DESC LIMIT %s",
                (channel, limit),
            )
        else:
            cursor.execute("SELECT * FROM quant.agent_sessions ORDER BY last_active_at DESC LIMIT %s", (limit,))
        return [self._row_to_dict(cursor, r) for r in cursor.fetchall()]

    def get_session(self, session_key: str) -> Optional[Dict[str, Any]]:
        repo = BaseRepository()
        cursor = repo._get_cursor()
        cursor.execute("SELECT * FROM quant.agent_sessions WHERE session_key = %s", (session_key,))
        row = cursor.fetchone()
        return self._row_to_dict(cursor, row) if row else None

    def get_events(self, session_key: str, event_type: Optional[str] = None,
                   limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        repo = BaseRepository()
        cursor = repo._get_cursor()
        if event_type:
            cursor.execute(
                """SELECT seq, event_type, payload, created_at FROM quant.agent_session_events
                   WHERE session_key = %s AND event_type = %s ORDER BY seq LIMIT %s OFFSET %s""",
                (session_key, event_type, limit, offset),
            )
        else:
            cursor.execute(
                """SELECT seq, event_type, payload, created_at FROM quant.agent_session_events
                   WHERE session_key = %s ORDER BY seq LIMIT %s OFFSET %s""",
                (session_key, limit, offset),
            )
        return [self._row_to_dict(cursor, r) for r in cursor.fetchall()]

    def get_diagnosis(self, session_key: str) -> Dict[str, Any]:
        """诊断：工具成功率、耗时、错误聚类、关联决策 + 洞察解读"""
        repo = BaseRepository()
        cursor = repo._get_cursor()

        cursor.execute(
            """SELECT
                 COUNT(*) FILTER (WHERE (payload->>'success')::boolean) AS ok,
                 COUNT(*) AS total,
                 COALESCE(AVG((payload->>'durationMs')::numeric), 0) AS avg_ms,
                 COALESCE(MAX((payload->>'durationMs')::numeric), 0) AS max_ms
               FROM quant.agent_session_events
               WHERE session_key = %s AND event_type = 'tool_call'""",
            (session_key,),
        )
        tool = self._row_to_dict(cursor, cursor.fetchone())
        total = int(tool.get("total") or 0)
        ok = int(tool.get("ok") or 0)
        success_rate = (ok / total) if total else None

        cursor.execute(
            """SELECT payload->>'message' AS message, COUNT(*) AS cnt
               FROM quant.agent_session_events
               WHERE session_key = %s AND event_type = 'error'
               GROUP BY message ORDER BY cnt DESC LIMIT 5""",
            (session_key,),
        )
        errors = [self._row_to_dict(cursor, r) for r in cursor.fetchall()]

        cursor.execute(
            """SELECT decision_id, decision_type, reasoning, evaluation_status, success
               FROM quant.agent_decisions WHERE session_key = %s ORDER BY created_at DESC LIMIT 20""",
            (session_key,),
        )
        decisions = [self._row_to_dict(cursor, r) for r in cursor.fetchall()]

        insight = self._build_insight(success_rate, total, tool, errors)

        return {
            "session_key": session_key,
            "tool_success_rate": success_rate,
            "tool_call_count": total,
            "avg_tool_duration_ms": round(float(tool.get("avg_ms") or 0)),
            "max_tool_duration_ms": int(tool.get("max_ms") or 0),
            "error_count": sum(int(e["cnt"]) for e in errors),
            "top_errors": errors,
            "decisions": decisions,
            "insight": insight,
        }

    def _build_insight(self, success_rate, total, tool, errors) -> str:
        if total == 0:
            return "本会话无工具调用记录。"
        parts = []
        if success_rate is not None and success_rate < 0.8:
            parts.append(f"工具成功率偏低（{success_rate:.0%}），建议检查失败工具的参数或数据源。")
        if float(tool.get("max_ms") or 0) > 10000:
            parts.append(f"存在慢工具调用（最大 {int(tool['max_ms'])}ms），建议排查超时原因。")
        if errors:
            parts.append(f"最高频错误：{errors[0]['message']}（{errors[0]['cnt']} 次）。")
        return " ".join(parts) if parts else f"会话健康：{total} 次工具调用，成功率 {success_rate:.0%}。"

    @staticmethod
    def _row_to_dict(cursor, row) -> Dict[str, Any]:
        if row is None:
            return {}
        if isinstance(row, dict):
            return dict(row)
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row))
```

- [ ] **Step 4: 运行确认通过**

Run: `cd quantsys-v2 && ./venv/bin/python -m pytest tests/services/test_session_service.py -q 2>&1 | tail -3`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2 && git add application/services/session_service.py tests/services/test_session_service.py
git commit -m "feat(gateway): SessionService 事件摄入/查询/诊断"
```

---

### Task 14: v2 sessions API 路由

**Files:**
- Create: `quantsys-v2/adapters/inbound/api/routes/agent_sessions.py`
- Modify: `quantsys-v2/adapters/inbound/api/server.py`（注册蓝图，在 decision_tracking 注册处附近，第 177-179 行区域）
- Test: `quantsys-v2/tests/api/test_agent_session_routes.py`

- [ ] **Step 1: 写失败测试**

```python
# quantsys-v2/tests/api/test_agent_session_routes.py
"""agent sessions API 路由测试"""
import pytest
from adapters.inbound.api.server import create_app  # 按 server.py 实际工厂函数调整
from infrastructure.persistence.database.base_repository import BaseRepository
from tests.services.test_session_service import DDL


@pytest.fixture
def client():
    repo = BaseRepository()
    cursor = repo._get_cursor()
    cursor.execute(DDL)
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_post_events_and_get_sessions(client):
    resp = client.post("/api/sessions/events", json={
        "events": [{
            "session_key": "agent:main:wake:default", "seq": 1,
            "event_type": "session_start",
            "payload": {"channel": "wake", "peerId": "default", "agentId": "main"},
            "created_at": "2026-07-22T02:00:00+00:00",
        }]
    })
    assert resp.status_code == 200
    assert resp.get_json()["data"]["accepted"] == 1

    resp = client.get("/api/sessions")
    data = resp.get_json()["data"]
    assert any(s["session_key"] == "agent:main:wake:default" for s in data["sessions"])

    resp = client.get("/api/sessions/agent:main:wake:default/events")
    events = resp.get_json()["data"]["events"]
    assert events[0]["event_type"] == "session_start"

    resp = client.get("/api/sessions/agent:main:wake:default/diagnosis")
    assert resp.get_json()["data"]["session_key"] == "agent:main:wake:default"
```

注意：先读 `server.py` 确认 app 工厂函数名（可能是 `create_app` 或模块级 `app`），测试按其调整；URL 中的 session_key 含 `:`，Flask 路由用 `<path:session_key>`。

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && ./venv/bin/python -m pytest tests/api/test_agent_session_routes.py -x -q 2>&1 | tail -3`
Expected: FAIL — 404 / ModuleNotFoundError

- [ ] **Step 3: 实现路由**

```python
# quantsys-v2/adapters/inbound/api/routes/agent_sessions.py
"""
Agent Session API 路由
事件摄入（agent syncer）+ 查询/诊断（web 展示）
"""
from flask import Blueprint, jsonify, request
from adapters.inbound.api.decorators import handle_errors
from application.services.session_service import SessionService

agent_sessions_bp = Blueprint('agent_sessions', __name__, url_prefix='/api/sessions')


@agent_sessions_bp.route('/events', methods=['POST'])
@handle_errors
def ingest_events():
    """批量摄入 session 事件（幂等）"""
    body = request.get_json() or {}
    events = body.get('events', [])
    if not isinstance(events, list) or not events:
        return jsonify({'success': False, 'error': 'events 必须是非空数组'}), 400

    result = SessionService().ingest_events(events)
    return jsonify({'success': True, 'data': result})


@agent_sessions_bp.route('', methods=['GET'])
@handle_errors
def list_sessions():
    channel = request.args.get('channel')
    limit = min(int(request.args.get('limit', 50)), 200)
    sessions = SessionService().list_sessions(channel=channel, limit=limit)
    return jsonify({'success': True, 'data': {'sessions': sessions, 'total': len(sessions)}})


@agent_sessions_bp.route('/<path:session_key>', methods=['GET'])
@handle_errors
def get_session(session_key):
    session = SessionService().get_session(session_key)
    if not session:
        return jsonify({'success': False, 'error': '会话不存在'}), 404
    return jsonify({'success': True, 'data': session})


@agent_sessions_bp.route('/<path:session_key>/events', methods=['GET'])
@handle_errors
def get_events(session_key):
    event_type = request.args.get('event_type')
    limit = min(int(request.args.get('limit', 200)), 1000)
    offset = int(request.args.get('offset', 0))
    events = SessionService().get_events(session_key, event_type=event_type, limit=limit, offset=offset)
    return jsonify({'success': True, 'data': {'events': events, 'total': len(events)}})


@agent_sessions_bp.route('/<path:session_key>/diagnosis', methods=['GET'])
@handle_errors
def get_diagnosis(session_key):
    diagnosis = SessionService().get_diagnosis(session_key)
    return jsonify({'success': True, 'data': diagnosis})
```

**注册蓝图**（server.py 第 177-179 行附近追加）：

```python
    from adapters.inbound.api.routes.agent_sessions import agent_sessions_bp
    app.register_blueprint(agent_sessions_bp)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd quantsys-v2 && ./venv/bin/python -m pytest tests/api/test_agent_session_routes.py -q 2>&1 | tail -3`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2 && git add adapters/inbound/api/routes/agent_sessions.py adapters/inbound/api/server.py tests/api/test_agent_session_routes.py
git commit -m "feat(gateway): /api/sessions 摄入与诊断路由"
```

---

### Task 15: v2 agent_notification_service 端口与 token

**Files:**
- Modify: `quantsys-v2/application/services/agent_notification_service.py:28`（默认 URL）与 `notify_agent` 请求头
- Modify: `quantsys-v2/tests/services/test_agent_notification_service.py`（追加断言）

- [ ] **Step 1: 追加失败测试**

```python
def test_notify_sends_token_header_and_default_port_3002(monkeypatch):
    """token 配置时请求带 X-Wake-Token；默认 URL 为 3002"""
    from unittest.mock import patch, MagicMock
    monkeypatch.delenv('AGENT_API_URL', raising=False)
    monkeypatch.setenv('AGENT_API_TOKEN', 'tok-123')
    from application.services.agent_notification_service import AgentNotificationService

    service = AgentNotificationService()
    assert service.agent_url == 'http://127.0.0.1:3002'

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {'success': True}
    with patch('application.services.agent_notification_service.requests.post', return_value=mock_resp) as mock_post:
        assert service.notify_agent('agent_reminder', {'message': 'hi'}) is True
    assert mock_post.call_args.kwargs['headers']['X-Wake-Token'] == 'tok-123'
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && ./venv/bin/python -m pytest tests/services/test_agent_notification_service.py::test_notify_sends_token_header_and_default_port_3002 -q 2>&1 | tail -3`
Expected: FAIL

- [ ] **Step 3: 实现**

`agent_notification_service.py` 修改两处：

```python
# __init__ 中（line 28 附近）：
        self.agent_url = agent_url or os.getenv('AGENT_API_URL', 'http://127.0.0.1:3002')
        self.token = os.getenv('AGENT_API_TOKEN')
```

`notify_agent` 的 headers 改为：

```python
            headers = {'Content-Type': 'application/json'}
            if self.token:
                headers['X-Wake-Token'] = self.token
            response = requests.post(
                f'{self.agent_url}/wake',
                json=payload,
                timeout=self.timeout,
                headers=headers
            )
```

- [ ] **Step 4: 运行确认通过（7 passed）并 commit**

```bash
cd quantsys-v2 && ./venv/bin/python -m pytest tests/services/test_agent_notification_service.py -q 2>&1 | tail -3
git add application/services/agent_notification_service.py tests/services/test_agent_notification_service.py
git commit -m "feat(gateway): 通知服务默认端口 3002 + X-Wake-Token"
```

---

### Task 16: v2 decision 记录 session_key 透传

**Files:**
- Modify: `quantsys-v2/adapters/outbound/repositories/agent_intelligence_repository.py`（ORM 模型加列 + create_decision 透传）
- Modify: `quantsys-v2/application/services/decision_service.py`（_validate_decision_data 放行 session_key）
- Test: `quantsys-v2/tests/services/test_decision_service_session_key.py`

- [ ] **Step 1: 写失败测试**

```python
# quantsys-v2/tests/services/test_decision_service_session_key.py
"""decision 记录透传 session_key"""
from unittest.mock import patch
from application.services.decision_service import DecisionService


def test_record_decision_passes_session_key():
    service = DecisionService()
    with patch.object(service.decision_repo, 'create_decision', return_value={'decision_id': 'dec_1'}) as mock_create:
        service.record_decision({
            'decision_type': 'create_pool',
            'context': {}, 'parameters': {},
            'reasoning': 'test',
            'session_key': 'agent:main:wake:default',
        })
    assert mock_create.call_args[0][0]['session_key'] == 'agent:main:wake:default'
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && ./venv/bin/python -m pytest tests/services/test_decision_service_session_key.py -q 2>&1 | tail -3`
Expected: FAIL（session_key 被丢弃或校验拒绝）

- [ ] **Step 3: 实现**

先读 `agent_intelligence_repository.py` 的 `AgentDecision` ORM 模型与 `create_decision`，然后：
1. ORM 模型加 `session_key = Column(String(200), nullable=True)`
2. `create_decision` 构造 ORM 对象时透传 `session_key=decision_data.get('session_key')`
3. `decision_service._validate_decision_data` 若校验未知字段，放行 `session_key`

- [ ] **Step 4: 运行确认通过并 commit**

```bash
cd quantsys-v2 && ./venv/bin/python -m pytest tests/services/test_decision_service_session_key.py -q 2>&1 | tail -3
git add adapters/outbound/repositories/agent_intelligence_repository.py application/services/decision_service.py tests/services/test_decision_service_session_key.py
git commit -m "feat(gateway): agent_decisions 透传 session_key"
```

---

### Task 17: legacy session 导入脚本

**Files:**
- Create: `agent-ts/scripts/import-legacy-sessions.ts`

说明：一次性脚本，不做 jest（手动验证）。只导入飞书结构化 log.jsonl；wake 的 conversation.log 是自由文本，写一条 legacy_note 摘要。

- [ ] **Step 1: 创建脚本**

```typescript
// agent-ts/scripts/import-legacy-sessions.ts
#!/usr/bin/env node
/**
 * Legacy session 导入：旧 sessions/ 与 wake-sessions/ → agent-sessions/ 新事件模型
 * 用法: npx tsx scripts/import-legacy-sessions.ts
 */
import { existsSync, readFileSync, readdirSync } from "fs";
import { join } from "path";
import { paths } from "../src/config/config.js";
import { emitSessionEvent, resetSessionEventState, sessionDirOf } from "../src/api/gateway/session-events.js";

function importFeishuSessions(): number {
  const root = join(paths.piDir, "sessions");
  if (!existsSync(root)) return 0;
  let count = 0;

  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const logFile = join(root, entry.name, "log.jsonl");
    if (!existsSync(logFile)) continue;

    const sessionKey = `agent:main:feishu:${entry.name.replace(/[^A-Za-z0-9_-]/g, "_")}`;
    emitSessionEvent(sessionKey, { type: "session_start", channel: "feishu", peerId: entry.name, agentId: "main", legacy: true });

    for (const line of readFileSync(logFile, "utf-8").split("\n")) {
      if (!line.trim()) continue;
      try {
        const rec = JSON.parse(line);
        if (rec.role === "user") {
          emitSessionEvent(sessionKey, { type: "user_message", messageId: rec.message_id ?? `legacy-${Date.now()}`, text: rec.content ?? "" });
        } else if (rec.role === "assistant") {
          emitSessionEvent(sessionKey, { type: "assistant_reply", text: rec.content ?? "", replyLength: (rec.content ?? "").length });
        }
      } catch { /* 跳过坏行 */ }
    }
    count++;
  }
  return count;
}

function importWakeSessions(): number {
  const root = join(paths.piDir, "wake-sessions");
  if (!existsSync(root)) return 0;
  let count = 0;

  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const logFile = join(root, entry.name, "conversation.log");
    if (!existsSync(logFile)) continue;

    const sessionKey = `agent:main:wake:${entry.name.replace(/[^A-Za-z0-9_-]/g, "_")}`;
    emitSessionEvent(sessionKey, { type: "session_start", channel: "wake", peerId: entry.name, agentId: "main", legacy: true });
    const raw = readFileSync(logFile, "utf-8");
    emitSessionEvent(sessionKey, { type: "legacy_note", note: raw.slice(0, 4000) });
    count++;
  }
  return count;
}

resetSessionEventState();
const feishu = importFeishuSessions();
const wake = importWakeSessions();
console.log(`✅ 导入完成: feishu ${feishu} 个会话, wake ${wake} 个会话`);
console.log(`📁 输出目录: ${sessionDirOf("")}`);
```

- [ ] **Step 2: 手动运行验证**

```bash
cd agent-ts && npx tsx scripts/import-legacy-sessions.ts
ls ~/.pi-invest/agent-sessions/ | head
```
Expected: 列出 `agent:main:feishu:*` / `agent:main:wake:*` 目录

- [ ] **Step 3: Commit**

```bash
cd agent-ts && git add scripts/import-legacy-sessions.ts
git commit -m "feat(gateway): legacy session 导入脚本"
```

---

### Task 18: 配置与文档更新

**Files:**
- Modify: `agent-ts/.env.example`
- Modify: `quantsys-v2/.env.automation.example`
- Modify: `agent-ts/CLAUDE.md`（固定端口表）

- [ ] **Step 1: agent-ts .env.example 追加**

```bash
# Agent Gateway / Wake Channel
WAKE_CHANNEL_PORT=3002
WAKE_TOKEN=          # 配置后 /wake 强制鉴权；留空则放行（仅开发）
```

- [ ] **Step 2: v2 .env.automation.example 更新**

`AGENT_API_URL` 改为 `http://127.0.0.1:3002`，追加：

```bash
AGENT_API_TOKEN=     # 与 agent 侧 WAKE_TOKEN 一致
```

- [ ] **Step 3: agent-ts CLAUDE.md 固定端口表加一行**

在端口表 `| web-frontend Vite | 127.0.0.1:3001 | ... |` 后追加：

```markdown
| agent-ts Wake Channel | `127.0.0.1:3002` | `WAKE_CHANNEL_PORT` / `WAKE_TOKEN` 环境变量 |
```

- [ ] **Step 4: Commit**

```bash
git add agent-ts/.env.example agent-ts/CLAUDE.md quantsys-v2/.env.automation.example
git commit -m "docs(gateway): 端口 3002 与 token 配置约定"
```

---

### Task 19: 端到端验证

- [ ] **Step 1: 启动 v2 并确认表就绪**

```bash
cd quantsys-v2 && ./venv/bin/python adapters/inbound/api/server.py &
curl -s http://127.0.0.1:5001/api/health | head -1
```

- [ ] **Step 2: 启动 wake channel**

```bash
cd agent-ts && WAKE_TOKEN=test-tok npm run wake &
curl -s http://127.0.0.1:3002/wake/health
```
Expected: `{"status":"ok","channel":"wake",...}`

- [ ] **Step 3: 推送事件并验证全链路**

```bash
curl -s -X POST http://127.0.0.1:3002/wake \
  -H "Content-Type: application/json" -H "X-Wake-Token: test-tok" \
  -d '{"event":"agent_reminder","data":{"message":"测试链路"},"session_id":"e2e"}'
# 无 token 应 401：
curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:3002/wake \
  -H "Content-Type: application/json" -d '{"event":"agent_reminder","data":{"message":"x"}}'
# 本地事件：
cat ~/.pi-invest/agent-sessions/agent:main:wake:e2e/events.jsonl | head -3
# 同步回 v2（等 5s+ 后）：
curl -s "http://127.0.0.1:5001/api/sessions?channel=wake" | head -20
curl -s "http://127.0.0.1:5001/api/sessions/agent:main:wake:e2e/diagnosis"
```
Expected: 401；events.jsonl 有 session_start/user_message/assistant_reply；v2 可查到会话与诊断

- [ ] **Step 4: 飞书冒烟（如配置了 FEISHU_APP_ID）**

```bash
cd agent-ts && npm run feishu
# 飞书中发消息 → 收到"收到，正在处理" → 收到回复
# ls ~/.pi-invest/agent-sessions/ 出现 agent:main:feishu:oc_* 目录
```

- [ ] **Step 5: 全量回归**

```bash
cd agent-ts && npx jest 2>&1 | tail -5
cd quantsys-v2 && ./venv/bin/python -m pytest tests/services/test_session_service.py tests/services/test_agent_notification_service.py tests/api/test_agent_session_routes.py tests/services/test_decision_service_session_key.py -q 2>&1 | tail -3
```

---

## Self-Review 记录

- **Spec 覆盖**：§3 架构（Task 3-10）✓；§4 事件模型（Task 2, 4, 11, 16）✓；§5 syncer（Task 7）✓；§6 表/API（Task 12-14）✓；§7 端口/鉴权（Task 8, 15, 18）✓；§8 错误处理（融入各 Task）✓；§9 测试（每 Task TDD）✓；§10 改动清单含 legacy 导入（Task 17）✓。CLI/TUI 不动（spec 边界）✓。
- **类型一致性**：`GatewayHandlers{dispatch,isProcessing,abort}` 在 Task 3/6/8/9/10 一致；`buildSessionKey` 签名一致；syncer 入队格式 `{session_key,seq,event_type,payload,created_at}` 与 v2 ingest 一致；`resetSessionEventState` 在 Task 2 定义、Task 4/6/7 测试复用。
- **已明确的坑**：fixture 中 BaseRepository 提交方式、server.py 工厂函数名、feishu.ts sendReply 实现——均在对应 Task 注明"先读实际代码调整"。
