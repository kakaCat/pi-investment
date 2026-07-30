# LLM 流式 terminated 容错（可见性+更强重试）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LLM 流式响应中途被 terminated 时，SDK 自动重试预算从 3 次/2s 基线提升到 5 次/3s 基线，并把重试过程显示到 console 且落 events.jsonl。

**Architecture:** 纯配置 + 事件订阅，不改 SDK。重试策略走 pi-coding-agent 原生 project settings（`agent-ts/.pi/settings.json`）；可见性在 `session-factory.ts` 的 `attachLogger`（所有 session 的唯一事件订阅点）增加 `auto_retry_start`/`auto_retry_end` 分支，日志经 `observable-logger.ts` 新增 `logLLMRetry` 写 `llm.retry` 事件。

**Tech Stack:** TypeScript, jest（必须 `npm test`，禁裸 `npx jest`）, pi-coding-agent SDK 0.73。

**Spec:** `docs/superpowers/specs/2026-07-30-llm-stream-retry-visibility-design.md`

**Worktree:** `.claude/worktrees/llm-retry-visibility`（分支 `worktree-llm-retry-visibility`），所有命令在 worktree 内执行。

---

### Task 0: Worktree 环境准备

worktree 没有 node_modules（本仓库所有 worktree 均需自行安装依赖），先装。

**Files:**
- 无文件改动

- [ ] **Step 1: 安装依赖**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts && npm install
```

预期：完成无 ERR（peer warning 可忽略）。验证：

```bash
ls /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts/node_modules/jest/bin/jest.js
```

预期：文件存在。

- [ ] **Step 2: 确认测试基线可跑**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts && npm test -- --listTests 2>&1 | head -5
```

预期：列出测试文件（如 `src/infrastructure/logging/observable-logger.test.ts`）。注意：仓库存在预存失败套件（见 memory baseline-failing-tests），本计划只要求新增/修改的测试文件全绿 + 不引入新失败。

---

### Task 1: observable-logger 新增 logLLMRetry

**Files:**
- Modify: `agent-ts/src/infrastructure/logging/observable-logger.ts`（在 `logSubagentEnd` 之后插入新函数；在文件尾部 `observableLogger` 导出对象中注册）
- Test: `agent-ts/src/infrastructure/logging/observable-logger.test.ts`（追加 describe 块）

参考现有风格：`logSubagentEnd`（observable-logger.ts:427-436）通过 `logEvent('<name>', {...})` 写事件，`turnIndex` 是模块级变量。

- [ ] **Step 1: 写失败测试**

在 `agent-ts/src/infrastructure/logging/observable-logger.test.ts` 文件末尾追加：

```ts
describe("logLLMRetry", () => {
  test("writes llm.retry event with start phase fields", async () => {
    tempDir = mkdtempSync(join(tmpdir(), "pi-invest-logger-retry-"));
    process.chdir(tempDir);

    const logger = await import("./observable-logger.js");
    logger.initSession("20260730010101_retry0001");

    logger.logLLMRetry({
      phase: "start",
      attempt: 1,
      maxAttempts: 5,
      delayMs: 3000,
      errorMessage: "terminated",
    });

    const eventsFile = join(tempDir, ".pi-invest", "sessions", "20260730010101_retry0001", "events.jsonl");
    const events = readFileSync(eventsFile, "utf-8").trim().split("\n").map((line) => JSON.parse(line));
    const retryEvent = events.find((event) => event.event === "llm.retry");

    expect(retryEvent).toBeDefined();
    expect(retryEvent.phase).toBe("start");
    expect(retryEvent.attempt).toBe(1);
    expect(retryEvent.maxAttempts).toBe(5);
    expect(retryEvent.delayMs).toBe(3000);
    expect(retryEvent.errorMessage).toBe("terminated");
  });

  test("writes llm.retry event with end phase fields", async () => {
    tempDir = mkdtempSync(join(tmpdir(), "pi-invest-logger-retry-end-"));
    process.chdir(tempDir);

    const logger = await import("./observable-logger.js");
    logger.initSession("20260730010202_retry0002");

    logger.logLLMRetry({ phase: "end", attempt: 3, success: false, finalError: "terminated" });

    const eventsFile = join(tempDir, ".pi-invest", "sessions", "20260730010202_retry0002", "events.jsonl");
    const events = readFileSync(eventsFile, "utf-8").trim().split("\n").map((line) => JSON.parse(line));
    const retryEvent = events.find((event) => event.event === "llm.retry");

    expect(retryEvent.phase).toBe("end");
    expect(retryEvent.attempt).toBe(3);
    expect(retryEvent.success).toBe(false);
    expect(retryEvent.finalError).toBe("terminated");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts && npm test -- src/infrastructure/logging/observable-logger.test.ts 2>&1 | tail -15
```

预期：FAIL，`logger.logLLMRetry is not a function`（两个新用例失败，原有 2 个用例仍通过）。

- [ ] **Step 3: 实现 logLLMRetry**

在 `observable-logger.ts` 的 `logSubagentEnd` 函数（427-436 行）之后插入：

```ts
// 记录 LLM 自动重试（SDK auto_retry_start / auto_retry_end 事件）
export function logLLMRetry(data: {
  phase: 'start' | 'end';
  attempt: number;
  maxAttempts?: number;
  delayMs?: number;
  errorMessage?: string;
  success?: boolean;
  finalError?: string;
}) {
  logEvent('llm.retry', {
    turn_index: turnIndex,
    ...data,
  });
}
```

在文件尾部 `observableLogger` 导出对象中，`logSubagentEnd,` 之后加一行：

```ts
  logLLMRetry,
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts && npm test -- src/infrastructure/logging/observable-logger.test.ts 2>&1 | tail -8
```

预期：PASS，4 个用例全绿。

- [ ] **Step 5: 提交**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility && git add agent-ts/src/infrastructure/logging/observable-logger.ts agent-ts/src/infrastructure/logging/observable-logger.test.ts && git commit -m "feat(agent-ts): observable-logger 新增 logLLMRetry 记录 llm.retry 事件"
```

---

### Task 2: .pi/settings.json 提升重试预算

SDK 的 project settings 路径为 `<cwd>/.pi/settings.json`（pi-coding-agent settings-manager.js，`CONFIG_DIR_NAME = ".pi"`，cwd = agent-ts 根目录）。`.pi/` 未被 gitignore（只有 `.pi-invest/` 被忽略），可提交。`SettingsManager` 只有 `setRetryEnabled` setter，maxRetries/baseDelayMs 只能经此文件配置。

**Files:**
- Create: `agent-ts/.pi/settings.json`
- Test: `agent-ts/src/config/retry-settings.test.ts`（新建）

- [ ] **Step 1: 写失败测试**

新建 `agent-ts/src/config/retry-settings.test.ts`：

```ts
import { describe, expect, test } from "@jest/globals";
import { mkdtempSync, rmSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import { SettingsManager } from "@mariozechner/pi-coding-agent";

// npm test 的工作目录即 agent-ts 根目录，process.cwd()/.pi/settings.json 即项目 settings
describe("LLM retry project settings", () => {
  test("SDK reads retry policy from agent-ts/.pi/settings.json", () => {
    const tmpAgentDir = mkdtempSync(join(tmpdir(), "pi-agent-dir-"));
    try {
      const sm = SettingsManager.create(process.cwd(), tmpAgentDir);
      expect(sm.getRetrySettings()).toEqual({
        enabled: true,
        maxRetries: 5,
        baseDelayMs: 3000,
      });
    } finally {
      rmSync(tmpAgentDir, { recursive: true, force: true });
    }
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts && npm test -- src/config/retry-settings.test.ts 2>&1 | tail -10
```

预期：FAIL，`getRetrySettings()` 返回默认值 `{enabled: true, maxRetries: 3, baseDelayMs: 2000}`。

- [ ] **Step 3: 创建 settings.json**

新建 `agent-ts/.pi/settings.json`：

```json
{
  "retry": {
    "enabled": true,
    "maxRetries": 5,
    "baseDelayMs": 3000
  }
}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts && npm test -- src/config/retry-settings.test.ts 2>&1 | tail -6
```

预期：PASS。

- [ ] **Step 5: 确认 .pi 未被 gitignore 并提交**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility && git check-ignore agent-ts/.pi/settings.json; echo "check-ignore exit=$?"
```

预期：无输出，`exit=1`（即未被忽略）。然后：

```bash
git add agent-ts/.pi/settings.json agent-ts/src/config/retry-settings.test.ts && git commit -m "feat(agent-ts): .pi/settings.json 提升 LLM 自动重试预算至 5 次/3s 指数退避"
```

---

### Task 3: attachLogger 订阅 auto_retry 事件

SDK 事件类型（pi-coding-agent `agent-session.d.ts`）：

```ts
{ type: "auto_retry_start"; attempt: number; maxAttempts: number; delayMs: number; errorMessage: string }
{ type: "auto_retry_end"; success: boolean; attempt: number; finalError?: string }
```

**Files:**
- Modify: `agent-ts/src/infrastructure/session/session-factory.ts`（`attachLogger` 的事件 switch，在 `agent_end` case 之后、`break;` 收尾前插入两个 case）
- Test: `agent-ts/src/infrastructure/session/session-factory.test.ts`（新建）

- [ ] **Step 1: 写失败测试**

新建 `agent-ts/src/infrastructure/session/session-factory.test.ts`：

```ts
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
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts && npm test -- src/infrastructure/session/session-factory.test.ts 2>&1 | tail -12
```

预期：FAIL，3 个用例的 console 断言全部不通过（attachLogger 目前不认识这两个事件类型）。

- [ ] **Step 3: 实现 auto_retry 分支**

在 `agent-ts/src/infrastructure/session/session-factory.ts` 的 `attachLogger` 函数中，`case 'agent_end':` 块结束之后（即现有代码 173 行 `break;` 之后、switch 收尾 `}` 之前）插入：

```ts
      case 'auto_retry_start': {
        const delaySec = Math.round((event.delayMs ?? 0) / 1000);
        console.log(`🔄 LLM 连接中断，${delaySec}s 后重试 (${event.attempt}/${event.maxAttempts}): ${event.errorMessage}`);
        logger.logLLMRetry({
          phase: 'start',
          attempt: event.attempt,
          maxAttempts: event.maxAttempts,
          delayMs: event.delayMs,
          errorMessage: event.errorMessage,
        });
        break;
      }

      case 'auto_retry_end': {
        if (event.success) {
          console.log(`✅ LLM 重试成功（第 ${event.attempt} 次）`);
        } else {
          console.error(`❌ LLM 重试耗尽（${event.attempt} 次）: ${event.finalError ?? 'unknown'}`);
        }
        logger.logLLMRetry({
          phase: 'end',
          attempt: event.attempt,
          success: event.success,
          finalError: event.finalError,
        });
        break;
      }
```

同时在文件头部注释（第 7-11 行的 SDK 事件类型列表）追加一行说明：

```ts
 * - auto_retry_start / auto_retry_end (SDK 内置 LLM 错误重试)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts && npm test -- src/infrastructure/session/session-factory.test.ts 2>&1 | tail -6
```

预期：PASS，3 个用例全绿。

- [ ] **Step 5: 提交**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility && git add agent-ts/src/infrastructure/session/session-factory.ts agent-ts/src/infrastructure/session/session-factory.test.ts && git commit -m "feat(agent-ts): attachLogger 订阅 auto_retry 事件，LLM 重试过程 console+日志可见"
```

---

### Task 4: 全量验证

**Files:**
- 无文件改动

- [ ] **Step 1: 跑本计划涉及的三个测试文件**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts && npm test -- src/infrastructure/logging/observable-logger.test.ts src/config/retry-settings.test.ts src/infrastructure/session/session-factory.test.ts 2>&1 | tail -12
```

预期：3 个套件全部 PASS（共 8 个用例：observable-logger 4 + retry-settings 1 + session-factory 3）。

- [ ] **Step 2: 全量 jest，对比预存失败基线**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts && npm test 2>&1 | tail -25
```

预期：本仓库存在预存失败套件（memory baseline-failing-tests，jest 37 个套件级失败为已知基线）。判定标准：
- 本计划新增/修改的 3 个测试文件必须全 PASS；
- 失败清单与 main 基线一致（无可归因于本次改动的新失败，重点排除 logging/session/config 相关套件）。

- [ ] **Step 3: TypeScript 编译检查**

```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/llm-retry-visibility/agent-ts && npm run build 2>&1 | tail -5
```

预期：无 TS 错误（改动文件通过编译；若 main 基线本身有预存编译错误，确认本次改动文件无新增错误即可）。
