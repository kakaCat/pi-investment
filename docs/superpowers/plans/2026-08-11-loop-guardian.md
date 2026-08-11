# LoopGuardian Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 agent-ts 的 AgentSession 加装引擎侧防呆护栏（轮次纠偏注入 / 重复调用检测 / no_tool 拦截 / LLM 静默失败通知），对治光说不练、死循环、静默失败三类事故。

**Architecture:** 以 SDK Extension 钩子实现（先例：`src/api/extensions/model-command.ts`）。拆两个文件：`loop-guardian-core.ts`（纯函数：状态 + 规则判定，不碰 SDK，Jest 直接测）+ `loop-guardian.ts`（薄事件翻译层：`pi.on` 收事件 → 更新状态 → 执行干预）。注册 = `createAppResourceLoader` 的 `extensionFactories` 数组加一项。

**Tech Stack:** TypeScript / pi-coding-agent SDK Extension API / Jest（ESM，必须 `npm test`，裸 `npx jest` 误报 TS1378）。

**设计规格:** `docs/superpowers/specs/2026-08-11-loop-guardian-design.md`

**关键已验证事实**（实现者不必再查）：
- Extension 事件无 `auto_retry`；R7 用 `pi.on("after_provider_response", e => e.status >= 400)` 计数替代
- `TurnEndEvent = { turnIndex, message, toolResults }`；`AgentEndEvent = { messages }`；`ToolExecutionStartEvent = { toolCallId, toolName, args }`；`AfterProviderResponseEvent = { status, headers }`
- 注入用 `pi.sendUserMessage(text, { deliverAs: "steer" | "followUp" })`
- 通知用 `notificationService.sendCard({ title, content, type, metadata })`（`src/services/notification/notification-service.ts` 单例，broadcast 到所有渠道；无渠道时静默安全）
- 所有工作必须在 worktree 中进行（根 CLAUDE.md 规则）

---

### Task 1: core 模块骨架 + R1/R2 轮次纠偏

**Files:**
- Create: `agent-ts/src/api/extensions/loop-guardian-core.ts`
- Test: `agent-ts/src/api/extensions/loop-guardian-core.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// agent-ts/src/api/extensions/loop-guardian-core.test.ts
import {
  createGuardianState,
  evaluateTurnEnd,
  NUDGE_INTERVAL,
  FILE_CHECKPOINT_INTERVAL,
} from "./loop-guardian-core.js";

describe("R1/R2 轮次纠偏", () => {
  test("普通轮次不干预", () => {
    const s = createGuardianState();
    s.turnCount = 5;
    expect(evaluateTurnEnd(s)).toEqual([]);
  });

  test(`turn=${NUDGE_INTERVAL} 触发 R1 steer`, () => {
    const s = createGuardianState();
    s.turnCount = NUDGE_INTERVAL;
    const out = evaluateTurnEnd(s);
    expect(out).toHaveLength(1);
    expect(out[0].kind).toBe("steer");
    expect(out[0].text).toContain("停止无新信息的重试");
  });

  test("同一档位不重复触发", () => {
    const s = createGuardianState();
    s.turnCount = NUDGE_INTERVAL;
    evaluateTurnEnd(s); // 第一次，消费掉
    expect(evaluateTurnEnd(s)).toEqual([]); // 同档位不再发
  });

  test(`turn=${FILE_CHECKPOINT_INTERVAL} 触发 R2 写文件提示`, () => {
    const s = createGuardianState();
    s.turnCount = FILE_CHECKPOINT_INTERVAL;
    const out = evaluateTurnEnd(s);
    expect(out.some(i => i.kind === "steer" && i.text.includes("写入文件"))).toBe(true);
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd agent-ts && npm test -- loop-guardian-core`
Expected: FAIL（模块不存在 / 导出不存在）

- [ ] **Step 3: 写最小实现**

```typescript
// agent-ts/src/api/extensions/loop-guardian-core.ts
/**
 * LoopGuardian 核心 —— 纯函数规则判定，不依赖 SDK。
 * 全部阈值与文案集中在常量区（将来可被文本参数进化系统调优）。
 */

// ---------- 阈值常量 ----------
export const NUDGE_INTERVAL = 13;          // R1：停止无效重试
export const FILE_CHECKPOINT_INTERVAL = 31; // R2：发现写入文件
export const HARD_TURN_LIMIT = 150;        // R4：软收尾上限
export const REPEAT_CALL_THRESHOLD = 3;    // R3：同 tool+args 连续次数
export const PROVIDER_ERROR_THRESHOLD = 3; // R7：provider 错误次数

// ---------- 状态 ----------
export interface GuardianState {
  turnCount: number;
  toolCallCount: number;
  consecutiveNoToolTurns: number;
  recentCallHashes: string[];
  providerErrors: number;
  firedNudgeTurns: Set<number>;
  hardLimitFired: boolean;
  followUpSent: boolean;
}

export function createGuardianState(): GuardianState {
  return {
    turnCount: 0,
    toolCallCount: 0,
    consecutiveNoToolTurns: 0,
    recentCallHashes: [],
    providerErrors: 0,
    firedNudgeTurns: new Set(),
    hardLimitFired: false,
    followUpSent: false,
  };
}

// ---------- 干预动作 ----------
export type Intervention =
  | { kind: "steer"; text: string; reason: string }
  | { kind: "followUp"; text: string; reason: string }
  | { kind: "notify"; title: string; content: string; reason: string };

// ---------- R1/R2：轮次纠偏 ----------
export function evaluateTurnEnd(s: GuardianState): Intervention[] {
  const out: Intervention[] = [];
  if (
    s.turnCount > 0 &&
    s.turnCount % NUDGE_INTERVAL === 0 &&
    !s.firedNudgeTurns.has(s.turnCount)
  ) {
    s.firedNudgeTurns.add(s.turnCount);
    out.push({
      kind: "steer",
      text: `[系统] 第${s.turnCount}轮：停止无新信息的重试。把关键上下文存入 memory_write；若无进展，换方案或重读相关 skill。`,
      reason: "R1:nudge",
    });
  }
  if (
    s.turnCount > 0 &&
    s.turnCount % FILE_CHECKPOINT_INTERVAL === 0 &&
    !s.firedNudgeTurns.has(-s.turnCount) // R2 用负数键与 R1 区分
  ) {
    s.firedNudgeTurns.add(-s.turnCount);
    out.push({
      kind: "steer",
      text: `[系统] 第${s.turnCount}轮：把关键发现/已试方案写入文件（不止工作记忆），防止上下文压缩后丢失。`,
      reason: "R2:file-checkpoint",
    });
  }
  return out;
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd agent-ts && npm test -- loop-guardian-core`
Expected: 4 个用例 PASS

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/api/extensions/loop-guardian-core.ts agent-ts/src/api/extensions/loop-guardian-core.test.ts
git commit -m "feat(guardian): LoopGuardian core 骨架 + R1/R2 轮次纠偏纯函数"
```

---

### Task 2: R3 重复调用检测

**Files:**
- Modify: `agent-ts/src/api/extensions/loop-guardian-core.ts`
- Test: `agent-ts/src/api/extensions/loop-guardian-core.test.ts`

- [ ] **Step 1: 写失败测试（追加 describe 块）**

```typescript
import { evaluateToolCall, REPEAT_CALL_THRESHOLD } from "./loop-guardian-core.js";

describe("R3 重复调用检测", () => {
  test(`同 tool+args 连续 ${REPEAT_CALL_THRESHOLD} 次触发 steer`, () => {
    const s = createGuardianState();
    let out: unknown[] = [];
    for (let i = 0; i < REPEAT_CALL_THRESHOLD; i++) {
      out = evaluateToolCall(s, "data_fetch_quote", { symbol: "600519" });
    }
    expect(out).toHaveLength(1);
    expect((out[0] as any).kind).toBe("steer");
    expect((out[0] as any).text).toContain("data_fetch_quote");
  });

  test("同 tool 不同 args 不触发", () => {
    const s = createGuardianState();
    let out: unknown[] = [];
    for (let i = 0; i < REPEAT_CALL_THRESHOLD; i++) {
      out = evaluateToolCall(s, "data_fetch_quote", { symbol: `60051${i}` });
    }
    expect(out).toEqual([]);
  });

  test("R3 触发后不重复刷屏", () => {
    const s = createGuardianState();
    for (let i = 0; i < REPEAT_CALL_THRESHOLD + 1; i++) {
      evaluateToolCall(s, "data_fetch_quote", { symbol: "600519" });
    }
    const out = evaluateToolCall(s, "data_fetch_quote", { symbol: "600519" });
    expect(out).toEqual([]);
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd agent-ts && npm test -- loop-guardian-core`
Expected: FAIL（`evaluateToolCall` 未导出）

- [ ] **Step 3: 追加实现**

```typescript
// 追加到 loop-guardian-core.ts

/** key 排序的稳定序列化（同语义不同 key 顺序视为同一调用） */
export function stableStringify(v: unknown): string {
  if (v === null || typeof v !== "object") return JSON.stringify(v);
  if (Array.isArray(v)) return `[${v.map(stableStringify).join(",")}]`;
  const o = v as Record<string, unknown>;
  return `{${Object.keys(o).sort().map(k => `${JSON.stringify(k)}:${stableStringify(o[k])}`).join(",")}}`;
}

// ---------- R3：重复调用检测 ----------
export function evaluateToolCall(
  s: GuardianState,
  toolName: string,
  args: unknown
): Intervention[] {
  s.toolCallCount++;
  const hash = `${toolName}(${stableStringify(args)})`;
  s.recentCallHashes.push(hash);
  if (s.recentCallHashes.length > REPEAT_CALL_THRESHOLD) {
    s.recentCallHashes.shift();
  }
  const repeated =
    s.recentCallHashes.length === REPEAT_CALL_THRESHOLD &&
    s.recentCallHashes.every(h => h === hash);
  if (repeated && !s.firedNudgeTurns.has(hashCode(hash))) {
    s.firedNudgeTurns.add(hashCode(hash));
    return [{
      kind: "steer",
      text: `[系统] 检测到连续 ${REPEAT_CALL_THRESHOLD} 次相同调用 ${toolName}（参数相同）。先分析上次结果为什么不符合预期，再决定下一步。`,
      reason: "R3:repeat-call",
    }];
  }
  return [];
}

/** 简单字符串哈希（仅用于 firedNudgeTurns 去重键，非加密用途） */
function hashCode(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (h * 31 + str.charCodeAt(i)) | 0;
  }
  return h;
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd agent-ts && npm test -- loop-guardian-core`
Expected: 全部 PASS（累计 7 个用例）

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/api/extensions/loop-guardian-core.ts agent-ts/src/api/extensions/loop-guardian-core.test.ts
git commit -m "feat(guardian): R3 重复调用检测（stableStringify + 连续阈值）"
```

---

### Task 3: R4 硬上限通知 + 软收尾

**Files:**
- Modify: `agent-ts/src/api/extensions/loop-guardian-core.ts`
- Test: `agent-ts/src/api/extensions/loop-guardian-core.test.ts`

- [ ] **Step 1: 写失败测试（追加 describe 块）**

```typescript
import { HARD_TURN_LIMIT } from "./loop-guardian-core.js";

describe("R4 硬上限", () => {
  test(`turn=${HARD_TURN_LIMIT} 触发 notify + steer 两个动作`, () => {
    const s = createGuardianState();
    s.turnCount = HARD_TURN_LIMIT;
    const out = evaluateTurnEnd(s);
    expect(out.some(i => i.kind === "notify")).toBe(true);
    expect(out.some(i => i.kind === "steer" && i.text.includes("收尾"))).toBe(true);
  });

  test("硬上限每任务只触发一次", () => {
    const s = createGuardianState();
    s.turnCount = HARD_TURN_LIMIT;
    evaluateTurnEnd(s);
    s.turnCount = HARD_TURN_LIMIT + 13; // 更高档位仍不再发 R4
    const out = evaluateTurnEnd(s);
    expect(out.some(i => i.kind === "notify")).toBe(false);
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd agent-ts && npm test -- loop-guardian-core`
Expected: FAIL（R4 逻辑未实现）

- [ ] **Step 3: 修改 `evaluateTurnEnd`，在函数末尾 `return out` 前追加 R4 块**

```typescript
  // ---------- R4：硬上限（每任务一次） ----------
  if (s.turnCount >= HARD_TURN_LIMIT && !s.hardLimitFired) {
    s.hardLimitFired = true;
    out.push(
      {
        kind: "notify",
        title: "⚠️ LoopGuardian 硬上限",
        content: `任务已达 ${s.turnCount} 轮上限，已要求 agent 总结进展并收尾。`,
        reason: "R4:hard-limit",
      },
      {
        kind: "steer",
        text: `[系统] 已达 ${s.turnCount} 轮上限。停止继续尝试，总结已验证的进展和残余风险后收尾。`,
        reason: "R4:hard-limit",
      }
    );
  }
```

注意：R4 块放在 R1/R2 之后、`return out` 之前。`turnCount=150` 同时是 13 的倍数时会与 R1 同轮各发一条，属预期（评测标准不禁止）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd agent-ts && npm test -- loop-guardian-core`
Expected: 全部 PASS（累计 9 个用例）

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/api/extensions/loop-guardian-core.ts agent-ts/src/api/extensions/loop-guardian-core.test.ts
git commit -m "feat(guardian): R4 硬上限 notify+软收尾（每任务一次）"
```

---

### Task 4: R5/R6 agent_end 最终回复检查

**Files:**
- Modify: `agent-ts/src/api/extensions/loop-guardian-core.ts`
- Test: `agent-ts/src/api/extensions/loop-guardian-core.test.ts`

- [ ] **Step 1: 写失败测试（追加 describe 块）**

```typescript
import { evaluateAgentEnd } from "./loop-guardian-core.js";

describe("R5/R6 agent_end 检查", () => {
  test("R5: 0 工具 + 单个大代码块结尾 → followUp", () => {
    const s = createGuardianState(); // toolCallCount = 0
    const text = "分析如下：\n```python\n" + "x = 1\n".repeat(20) + "```";
    const out = evaluateAgentEnd(s, text);
    expect(out).toHaveLength(1);
    expect(out[0].kind).toBe("followUp");
    expect(out[0].text).toContain("未调用任何工具");
  });

  test("R5: 代码块后有大段解释 → 不触发", () => {
    const s = createGuardianState();
    const text = "```python\n" + "x = 1\n".repeat(20) + "```\n以上代码仅供你参考，"
      + "这是详细的说明文字，超过三十个字符的解释内容，不需要执行。";
    expect(evaluateAgentEnd(s, text)).toEqual([]);
  });

  test("R5: 本周期调过工具 → 不触发", () => {
    const s = createGuardianState();
    s.toolCallCount = 2;
    const text = "```python\n" + "x = 1\n".repeat(20) + "```";
    expect(evaluateAgentEnd(s, text)).toEqual([]);
  });

  test("R5 防追问循环：每任务最多追问一次", () => {
    const s = createGuardianState();
    const text = "```python\n" + "x = 1\n".repeat(20) + "```";
    evaluateAgentEnd(s, text); // 第一次追问
    expect(evaluateAgentEnd(s, text)).toEqual([]); // 第二次放行
  });

  test("R6: 空回复 → followUp", () => {
    const s = createGuardianState();
    const out = evaluateAgentEnd(s, "   ");
    expect(out).toHaveLength(1);
    expect(out[0].kind).toBe("followUp");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd agent-ts && npm test -- loop-guardian-core`
Expected: FAIL（`evaluateAgentEnd` 未导出）

- [ ] **Step 3: 追加实现**

```typescript
// 追加到 loop-guardian-core.ts

// ---------- R5/R6：agent_end 最终回复检查 ----------
const CODE_BLOCK_AT_END = /```[a-zA-Z0-9_]*\n[\s\S]{50,}?```\s*$/;
const MIN_RESIDUAL_LEN = 30;

export function evaluateAgentEnd(
  s: GuardianState,
  finalText: string
): Intervention[] {
  if (s.followUpSent) return []; // 防追问循环：每任务最多一次

  // R6：空回复或截断
  if (!finalText.trim()) {
    s.followUpSent = true;
    return [{
      kind: "followUp",
      text: "[系统] 上轮回复为空或被截断。请分小步重新生成并完成操作。",
      reason: "R6:empty-response",
    }];
  }

  // R5：0 工具 + 单个大代码块结尾 + 块外残余 < 30 字符
  if (s.toolCallCount === 0) {
    const m = finalText.match(CODE_BLOCK_AT_END);
    if (m) {
      const residual = finalText
        .slice(0, finalText.length - m[0].length)
        .replace(/<thinking>[\s\S]*?<\/thinking>/gi, "")
        .replace(/<summary>[\s\S]*?<\/summary>/gi, "")
        .replace(/\s+/g, "");
      if (residual.length < MIN_RESIDUAL_LEN) {
        s.followUpSent = true;
        return [{
          kind: "followUp",
          text: "[系统] 你的回复以大段代码结尾但未调用任何工具。若要执行/写入/分析，请显式调用工具；若仅供展示，请用一句话说明后结束。",
          reason: "R5:code-block-no-tool",
        }];
      }
    }
  }
  return [];
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd agent-ts && npm test -- loop-guardian-core`
Expected: 全部 PASS（累计 14 个用例）

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/api/extensions/loop-guardian-core.ts agent-ts/src/api/extensions/loop-guardian-core.test.ts
git commit -m "feat(guardian): R5/R6 agent_end 检查（大代码块无工具/空回复，防追问循环）"
```

---

### Task 5: R7 provider 静默失败通知

**Files:**
- Modify: `agent-ts/src/api/extensions/loop-guardian-core.ts`
- Test: `agent-ts/src/api/extensions/loop-guardian-core.test.ts`

- [ ] **Step 1: 写失败测试（追加 describe 块）**

```typescript
import { evaluateProviderResponse, PROVIDER_ERROR_THRESHOLD } from "./loop-guardian-core.js";

describe("R7 provider 静默失败", () => {
  test(`provider 错误 ≥${PROVIDER_ERROR_THRESHOLD} 且 0 工具 → notify`, () => {
    const s = createGuardianState();
    for (let i = 0; i < PROVIDER_ERROR_THRESHOLD; i++) {
      evaluateProviderResponse(s, 401);
    }
    const out = evaluateAgentEnd(s, "看起来一切正常的回复");
    expect(out.some(i => i.kind === "notify" && i.title.includes("静默失败"))).toBe(true);
  });

  test("provider 错误但调过工具 → 不告警", () => {
    const s = createGuardianState();
    s.toolCallCount = 1;
    for (let i = 0; i < PROVIDER_ERROR_THRESHOLD; i++) {
      evaluateProviderResponse(s, 500);
    }
    expect(evaluateAgentEnd(s, "正常回复")).toEqual([]);
  });

  test("status 200 不计错误", () => {
    const s = createGuardianState();
    for (let i = 0; i < PROVIDER_ERROR_THRESHOLD + 2; i++) {
      evaluateProviderResponse(s, 200);
    }
    expect(s.providerErrors).toBe(0);
  });
});
```

注意：R7 的判定挂在 `evaluateAgentEnd` 内，因此 Task 4 的 R5/R6 用例（providerErrors=0）不受影响。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd agent-ts && npm test -- loop-guardian-core`
Expected: FAIL（`evaluateProviderResponse` 未导出）

- [ ] **Step 3: 追加实现 + 修改 `evaluateAgentEnd`**

在文件末尾追加：

```typescript
// ---------- R7：provider 错误计数 ----------
export function evaluateProviderResponse(
  s: GuardianState,
  status: number
): void {
  if (status >= 400) s.providerErrors++;
}
```

修改 `evaluateAgentEnd`：在 `if (s.followUpSent) return [];` **之后**、R6 判断**之前**插入 R7 块：

```typescript
  // R7：provider 多次错误且全程 0 工具 → 静默失败告警（不注入对话，agent 大概率已坏）
  if (s.providerErrors >= PROVIDER_ERROR_THRESHOLD && s.toolCallCount === 0) {
    s.followUpSent = true; // 同时抑制 R5/R6，避免对一个坏掉的会话追问
    return [{
      kind: "notify",
      title: "🚨 LoopGuardian 疑似静默失败",
      content: `本周期 LLM provider 返回错误 ${s.providerErrors} 次且 0 次工具调用，任务可能未实际执行。建议检查 API key / model-switch.log。`,
      reason: "R7:silent-failure",
    }];
  }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd agent-ts && npm test -- loop-guardian-core`
Expected: 全部 PASS（累计 17 个用例）

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/api/extensions/loop-guardian-core.ts agent-ts/src/api/extensions/loop-guardian-core.test.ts
git commit -m "feat(guardian): R7 provider 静默失败检测（after_provider_response status 计数）"
```

---

### Task 6: Extension 薄接线层 + mock pi 集成测试

**Files:**
- Create: `agent-ts/src/api/extensions/loop-guardian.ts`
- Test: `agent-ts/src/api/extensions/loop-guardian.test.ts`

**事件 → 状态映射**（翻译层职责，全部逻辑在 core）：

| SDK 事件 | 状态更新 | 随后调用 |
|---|---|---|
| `agent_start` | `state = createGuardianState()` | — |
| `turn_end` | `turnCount++`；`toolResults.length ? consecutiveNoToolTurns=0 : ++` | `evaluateTurnEnd` |
| `tool_execution_start` | — | `evaluateToolCall(state, toolName, args)` |
| `after_provider_response` | — | `evaluateProviderResponse(state, status)` |
| `agent_end` | — | 提取最终 assistant 文本 → `evaluateAgentEnd` |

- [ ] **Step 1: 写失败测试（mock pi 上下文）**

```typescript
// agent-ts/src/api/extensions/loop-guardian.test.ts
import { loopGuardianExtension } from "./loop-guardian.js";
import { NUDGE_INTERVAL } from "./loop-guardian-core.js";

type Handler = (event: any) => void;

function createMockPi() {
  const handlers = new Map<string, Handler[]>();
  const sent: Array<{ content: string; deliverAs?: string }> = [];
  const pi = {
    on(event: string, handler: Handler) {
      handlers.set(event, [...(handlers.get(event) ?? []), handler]);
    },
    sendUserMessage(content: string, options?: { deliverAs?: string }) {
      sent.push({ content, deliverAs: options?.deliverAs });
    },
    emit(event: string, payload: any = {}) {
      for (const h of handlers.get(event) ?? []) h({ type: event, ...payload });
    },
    sent,
  };
  return pi;
}

describe("loopGuardianExtension 接线", () => {
  test(`turn_end ×${NUDGE_INTERVAL} → steer 注入一次`, () => {
    const pi = createMockPi();
    loopGuardianExtension(pi as any);
    pi.emit("agent_start");
    for (let i = 0; i < NUDGE_INTERVAL; i++) {
      pi.emit("turn_end", { turnIndex: i, message: {}, toolResults: [{}] });
    }
    expect(pi.sent).toHaveLength(1);
    expect(pi.sent[0].deliverAs).toBe("steer");
    expect(pi.sent[0].content).toContain("停止无新信息的重试");
  });

  test("agent_end 大代码块无工具 → followUp 追问", () => {
    const pi = createMockPi();
    loopGuardianExtension(pi as any);
    pi.emit("agent_start");
    pi.emit("agent_end", {
      messages: [{
        role: "assistant",
        content: [{ type: "text", text: "```python\n" + "x = 1\n".repeat(20) + "```" }],
      }],
    });
    expect(pi.sent).toHaveLength(1);
    expect(pi.sent[0].deliverAs).toBe("followUp");
  });

  test("agent_start 重置状态（新任务重新计数）", () => {
    const pi = createMockPi();
    loopGuardianExtension(pi as any);
    pi.emit("agent_start");
    for (let i = 0; i < NUDGE_INTERVAL; i++) {
      pi.emit("turn_end", { turnIndex: i, message: {}, toolResults: [{}] });
    }
    pi.emit("agent_start"); // 新任务
    for (let i = 0; i < NUDGE_INTERVAL; i++) {
      pi.emit("turn_end", { turnIndex: i, message: {}, toolResults: [{}] });
    }
    expect(pi.sent).toHaveLength(2); // 两个任务各触发一次 R1
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd agent-ts && npm test -- loop-guardian.test`
Expected: FAIL（`loop-guardian.ts` 不存在）

- [ ] **Step 3: 写实现**

```typescript
// agent-ts/src/api/extensions/loop-guardian.ts
/**
 * LoopGuardian —— 引擎侧防呆护栏（纯工程机制，不调用 LLM）
 *
 * 设计：docs/superpowers/specs/2026-08-11-loop-guardian-design.md
 * 对治：光说不练（R5/R6）、死循环（R1-R4）、静默失败（R7）
 *
 * 本文件是薄事件翻译层：SDK 事件 → 更新状态 → core 纯函数判定 → 执行干预。
 * 全部规则逻辑在 loop-guardian-core.ts（可单测）。
 *
 * 开关：LOOP_GUARDIAN=off 整体禁用（默认开）。
 */
import type { ExtensionFactory } from "@mariozechner/pi-coding-agent";
import {
  createGuardianState,
  evaluateTurnEnd,
  evaluateToolCall,
  evaluateProviderResponse,
  evaluateAgentEnd,
  type GuardianState,
  type Intervention,
} from "./loop-guardian-core.js";
import { notificationService } from "../../services/notification/notification-service.js";

/** 从 SDK AgentMessage 提取纯文本（content 为 string 或 {type:"text"} 数组） */
function extractText(message: any): string {
  if (!message) return "";
  const c = message.content;
  if (typeof c === "string") return c;
  if (Array.isArray(c)) {
    return c.filter((b: any) => b?.type === "text").map((b: any) => b.text ?? "").join("\n");
  }
  return "";
}

async function execute(pi: any, interventions: Intervention[]): Promise<void> {
  for (const iv of interventions) {
    console.log(`[LoopGuardian] ${iv.reason} → ${iv.kind}`);
    if (iv.kind === "notify") {
      try {
        await notificationService.sendCard({
          title: iv.title,
          content: iv.content,
          type: "warning",
          metadata: { reason: iv.reason },
        });
      } catch (e) {
        console.warn("[LoopGuardian] 通知发送失败:", e);
      }
    } else {
      pi.sendUserMessage(iv.text, { deliverAs: iv.kind });
    }
  }
}

export const loopGuardianExtension: ExtensionFactory = (pi) => {
  if (process.env.LOOP_GUARDIAN === "off") return;

  let state: GuardianState = createGuardianState();

  pi.on("agent_start", () => {
    state = createGuardianState();
  });

  pi.on("turn_end", (event) => {
    state.turnCount++;
    if (event.toolResults?.length) {
      state.consecutiveNoToolTurns = 0;
    } else {
      state.consecutiveNoToolTurns++;
    }
    void execute(pi, evaluateTurnEnd(state));
  });

  pi.on("tool_execution_start", (event) => {
    void execute(pi, evaluateToolCall(state, event.toolName, event.args));
  });

  pi.on("after_provider_response", (event) => {
    evaluateProviderResponse(state, event.status);
  });

  pi.on("agent_end", (event) => {
    const lastAssistant = [...(event.messages ?? [])]
      .reverse()
      .find((m: any) => m?.role === "assistant");
    void execute(pi, evaluateAgentEnd(state, extractText(lastAssistant)));
  });
};
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd agent-ts && npm test -- loop-guardian`
Expected: 全部 PASS（本文件 3 个 + core 17 个）

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/api/extensions/loop-guardian.ts agent-ts/src/api/extensions/loop-guardian.test.ts
git commit -m "feat(guardian): Extension 接线层——pi.on 事件翻译 + steer/followUp/notify 执行"
```

---

### Task 7: 注册 + 全量验证 + 手动验收

**Files:**
- Modify: `agent-ts/src/api/extensions/model-command.ts:127-135`

- [ ] **Step 1: 注册到 extensionFactories**

修改 `createAppResourceLoader`：

```typescript
import { loopGuardianExtension } from "./loop-guardian.js";

export async function createAppResourceLoader(cwd: string): Promise<DefaultResourceLoader> {
  const loader = new DefaultResourceLoader({
    cwd,
    agentDir: getAgentDir(),
    extensionFactories: [modelCommandExtension, loopGuardianExtension],
  });
  await loader.reload();
  return loader;
}
```

- [ ] **Step 2: TypeScript 编译检查**

Run: `cd agent-ts && npm run build`
Expected: 无 loop-guardian 相关报错（既有 baseline 报错若有，对照 main 分支输出确认非新增）

- [ ] **Step 3: 全量测试，对照 baseline**

Run: `cd agent-ts && npm test 2>&1 | tail -20`
Expected: loop-guardian 相关 20 个用例全绿；既有失败套件数不超过 baseline（见项目记忆 baseline-failing-tests，37 套件预存在失败）。若失败数增加且涉及 loop-guardian → 修复；与 guardian 无关的新增失败 → 停下来报告。

- [ ] **Step 4: 手动验收（worktree 内）**

```bash
cd agent-ts && npm run dev
```

场景 A（轮次纠偏）：给 agent 一个需多轮的任务（如"逐只分析这 20 只股票：600519、000001…"），观察到第 13 轮附近出现 `[LoopGuardian] R1:nudge → steer` 日志且 agent 收到系统提示。

场景 B（no_tool 拦截）：诱导"只贴代码不调工具"（如"给我看一段计算 RSI 的代码，不要执行"后追问"那帮我算一下 600519 的 RSI"若它仍只贴代码），观察 followUp 追问。

场景 C（开关）：`LOOP_GUARDIAN=off npm run dev`，重复场景 A，应无任何 `[LoopGuardian]` 日志。

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/api/extensions/model-command.ts
git commit -m "feat(guardian): 注册 loopGuardianExtension 到 extensionFactories"
```

---

## Self-Review 记录

- **Spec 覆盖**：R1-R7 → Task 1-5；Extension 钩子实现 → Task 6；注册+开关+验收 → Task 7；通知渠道（notificationService）→ Task 6 execute()；防追问循环 → Task 4 用例覆盖。✅
- **类型一致性**：`Intervention` 三个 kind（steer/followUp/notify）在 core、extension、测试中一致；`evaluateTurnEnd/evaluateToolCall/evaluateProviderResponse/evaluateAgentEnd` 签名跨任务一致。✅
- **已知取舍**：R7 用 `after_provider_response.status` 替代 spec 中的 auto_retry（扩展事件无此 API，spec §2 已预留此 fallback）；`consecutiveNoToolTurns` 状态已接线但当前规则未消费（保留给未来规则，YAGNI 边界：仅 3 行）。turn=150 与 R1 同档叠加发两条为预期行为（Task 3 Step 3 已注明）。
