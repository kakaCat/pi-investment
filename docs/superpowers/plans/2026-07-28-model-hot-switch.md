# 模型热切换（DeepSeek ↔ Kimi）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 不重启进程切换 agent-ts 的 LLM provider：人用 `/provider` 斜杠命令（当前会话立即生效），agent 用 `model_switch` 工具（新会话生效）。

**Architecture:** 新增 `src/config/model-switcher.ts` 持有运行时 provider 状态；`config.ts` 的 `getActiveProvider()` 优先读运行时状态。斜杠命令通过 SDK extension（`DefaultResourceLoader` 的 `extensionFactories`）注入，handler 调 `pi.setModel(createModel())`。agent 工具只设运行时状态。仅内存生效，重启还原。

**Tech Stack:** TypeScript (ESM)、Jest（`--experimental-vm-modules`，必须 `npm test`，不能裸 `npx jest`）、`@mariozechner/pi-coding-agent` SDK。

**Spec:** `docs/superpowers/specs/2026-07-28-model-hot-switch-design.md`

**Worktree（仓库硬性规则）:** 先在主仓库创建 worktree 再开工：
```bash
cd /Users/mac/Documents/ai/pi-investment
git worktree add .claude/worktrees/model-hot-switch -b feat/model-hot-switch
cd .claude/worktrees/model-hot-switch/agent-ts
```
所有代码改动、测试、提交都在 worktree 内进行；合并回 main 由收尾会话处理。下述路径均相对 `agent-ts/`。

**已知约束（探索阶段验证过的事实）：**
- `createModel()` 每次调用现读 env 并同步 `OPENAI_API_KEY`（config.ts:113-150），无需改动。
- 注意：`isProviderConfigured` 检查 key 时**不能**把 `OPENAI_API_KEY` 算作任一 provider 的 key —— `createModel()` 会把当前 provider 的 key 写进 `OPENAI_API_KEY`，会造成另一 provider "假已配置"。
- SDK 内置 `/model` 命令已存在（打开模型选择器，不认识我们的自定义模型），所以自定义命令命名为 **`/provider`**，避免冲突。这是对 spec 的偏差，Task 5 同步更新 spec。
- 工具 execute 签名是 `(toolCallId, params)`，拿不到 session —— `model_switch` 工具无法切当前会话，只影响新会话（spec 已注明）。
- SDK 只在**自己创建** resourceLoader 时才调 `reload()`；我们提供自定义 loader 时必须自己 `await loader.reload()`（sdk.js:94-97）。
- `getAgentDir` 和 `DefaultResourceLoader` 均从包根导出（index.d.ts:1,14）。

---

### Task 1: model-switcher 运行时状态模块

**Files:**
- Create: `src/config/model-switcher.ts`
- Test: `src/config/model-switcher.test.ts`

- [ ] **Step 1: 写失败测试**

创建 `src/config/model-switcher.test.ts`：

```typescript
/**
 * model-switcher 运行时 provider 状态测试
 */
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import {
  getRuntimeOverride,
  setRuntimeProvider,
  resetRuntimeProviderForTests,
  isProviderConfigured,
  listProviders,
} from './model-switcher.js';

const ENV_KEYS = [
  'LLM_PROVIDER', 'LLM_API_KEY',
  'DEEPSEEK_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY', 'OPENAI_API_KEY',
];
let savedEnv: Record<string, string | undefined>;

beforeEach(() => {
  savedEnv = {};
  for (const k of ENV_KEYS) { savedEnv[k] = process.env[k]; delete process.env[k]; }
  resetRuntimeProviderForTests();
});

afterEach(() => {
  for (const k of ENV_KEYS) {
    if (savedEnv[k] === undefined) delete process.env[k];
    else process.env[k] = savedEnv[k];
  }
  resetRuntimeProviderForTests();
});

describe('运行时 provider 状态', () => {
  it('默认无 override', () => {
    expect(getRuntimeOverride()).toBeNull();
  });

  it('setRuntimeProvider 后 getRuntimeOverride 返回新值', () => {
    setRuntimeProvider('kimi');
    expect(getRuntimeOverride()).toBe('kimi');
  });

  it('resetRuntimeProviderForTests 清除 override', () => {
    setRuntimeProvider('kimi');
    resetRuntimeProviderForTests();
    expect(getRuntimeOverride()).toBeNull();
  });
});

describe('isProviderConfigured', () => {
  it('DEEPSEEK_API_KEY 存在时 deepseek 已配置', () => {
    process.env.DEEPSEEK_API_KEY = 'sk-test';
    expect(isProviderConfigured('deepseek')).toBe(true);
  });

  it('KIMI_API_KEY / MOONSHOT_API_KEY 任一存在时 kimi 已配置', () => {
    process.env.MOONSHOT_API_KEY = 'sk-test';
    expect(isProviderConfigured('kimi')).toBe(true);
  });

  it('LLM_API_KEY 通用覆盖视为已配置', () => {
    process.env.LLM_API_KEY = 'sk-test';
    expect(isProviderConfigured('kimi')).toBe(true);
  });

  it('OPENAI_API_KEY 不算作任何 provider 的 key（createModel 会同步它，防假阳性）', () => {
    process.env.OPENAI_API_KEY = 'sk-deepseek-synced';
    expect(isProviderConfigured('kimi')).toBe(false);
    expect(isProviderConfigured('deepseek')).toBe(false);
  });

  it('无任何 key 时未配置', () => {
    expect(isProviderConfigured('deepseek')).toBe(false);
  });
});

describe('listProviders', () => {
  it('返回两个 provider 及配置状态', () => {
    process.env.DEEPSEEK_API_KEY = 'sk-test';
    const list = listProviders();
    expect(list).toEqual([
      { name: 'deepseek', configured: true },
      { name: 'kimi', configured: false },
    ]);
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd agent-ts && npm test -- model-switcher 2>&1 | tail -5
```
预期：FAIL，报 `Cannot find module './model-switcher.js'`。

- [ ] **Step 3: 实现 model-switcher.ts**

创建 `src/config/model-switcher.ts`：

```typescript
/**
 * 模型 Provider 运行时切换状态
 *
 * LLM_PROVIDER 环境变量决定启动时的 provider；本模块提供进程内
 * 热切换能力（仅内存，重启后回到环境变量）。
 *
 * config.ts 的 getActiveProvider() 优先读这里的 override。
 * 切换入口：/provider 斜杠命令（人）、model_switch 工具（agent）。
 */
import { appendFileSync, mkdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

export type RuntimeProviderName = "deepseek" | "kimi";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const AGENT_ROOT = join(__dirname, "../..");
const SWITCH_LOG_DIR = join(AGENT_ROOT, ".pi-invest");
const SWITCH_LOG_FILE = join(SWITCH_LOG_DIR, "model-switch.log");

/**
 * 各 provider 的专用 key 环境变量（用于"是否已配置"判断）。
 * 故意不包含 OPENAI_API_KEY：createModel() 会把当前 provider 的 key
 * 同步到 OPENAI_API_KEY，包含它会让另一 provider 出现"假已配置"。
 */
const PROVIDER_KEY_ENV: Record<RuntimeProviderName, string[]> = {
  deepseek: ["DEEPSEEK_API_KEY"],
  kimi: ["KIMI_API_KEY", "MOONSHOT_API_KEY"],
};

let runtimeProvider: RuntimeProviderName | null = null;

/** 当前运行时 override；null 表示未切换过（用 LLM_PROVIDER 环境变量） */
export function getRuntimeOverride(): RuntimeProviderName | null {
  return runtimeProvider;
}

export function setRuntimeProvider(p: RuntimeProviderName): void {
  runtimeProvider = p;
}

/** 仅测试使用：清除运行时 override */
export function resetRuntimeProviderForTests(): void {
  runtimeProvider = null;
}

/** 目标 provider 的 API key 是否已配置（LLM_API_KEY 通用覆盖也算） */
export function isProviderConfigured(p: RuntimeProviderName): boolean {
  if (process.env.LLM_API_KEY) return true;
  return PROVIDER_KEY_ENV[p].some((k) => !!process.env[k]);
}

export interface ProviderInfo {
  name: RuntimeProviderName;
  configured: boolean;
}

export function listProviders(): ProviderInfo[] {
  return (Object.keys(PROVIDER_KEY_ENV) as RuntimeProviderName[]).map((name) => ({
    name,
    configured: isProviderConfigured(name),
  }));
}

/** 切换审计日志：JSON 行追加到 .pi-invest/model-switch.log，同时打 console */
export function logSwitch(
  from: string,
  to: string,
  trigger: "human" | "agent"
): void {
  const entry = { ts: new Date().toISOString(), from, to, trigger };
  console.log(`[model-switch] ${entry.ts} ${from} → ${to} (${trigger})`);
  try {
    mkdirSync(SWITCH_LOG_DIR, { recursive: true });
    appendFileSync(SWITCH_LOG_FILE, JSON.stringify(entry) + "\n");
  } catch {
    // 日志写失败不影响切换
  }
}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd agent-ts && npm test -- model-switcher 2>&1 | tail -5
```
预期：PASS（9 个用例）。

- [ ] **Step 5: 提交**

```bash
git add src/config/model-switcher.ts src/config/model-switcher.test.ts
git commit -m "feat(config): model-switcher 运行时 provider 状态模块"
```

---

### Task 2: config.ts 接入运行时状态

**Files:**
- Modify: `src/config/config.ts:73-80`（`getActiveProvider`）
- Test: `src/config/model-switcher.test.ts`（追加集成用例）

- [ ] **Step 1: 追加失败测试**

在 `src/config/model-switcher.test.ts` 末尾追加：

```typescript
describe('config 集成：getActiveProvider / createModel', () => {
  it('未切换时 getActiveProvider 读 LLM_PROVIDER 环境变量', async () => {
    const { getActiveProvider } = await import('./config.js');
    expect(getActiveProvider()).toBe('deepseek'); // env 缺省
    process.env.LLM_PROVIDER = 'kimi';
    expect(getActiveProvider()).toBe('kimi');
  });

  it('切换后 getActiveProvider 优先返回运行时 override', async () => {
    process.env.LLM_PROVIDER = 'deepseek';
    setRuntimeProvider('kimi');
    const { getActiveProvider } = await import('./config.js');
    expect(getActiveProvider()).toBe('kimi');
  });

  it('切换后 createModel 返回新 provider 的模型并同步 OPENAI_API_KEY', async () => {
    process.env.KIMI_API_KEY = 'sk-kimi-test';
    process.env.KIMI_BASE_URL = 'https://api.kimi.com/coding/v1';
    process.env.KIMI_MODEL_ID = 'k3';
    setRuntimeProvider('kimi');
    const { createModel } = await import('./config.js');
    const model = createModel();
    expect(model.id).toBe('k3');
    expect(model.baseUrl).toBe('https://api.kimi.com/coding/v1');
    expect(process.env.OPENAI_API_KEY).toBe('sk-kimi-test');
  });
});
```

同时在文件顶部 import 区追加 `setRuntimeProvider`（已在 Task 1 的 import 列表中，无需改）。另外把 `'KIMI_BASE_URL'`、`'KIMI_MODEL_ID'` 加入 `ENV_KEYS` 数组。

注意：`config.js` 是动态 import 且模块级有缓存——本测试文件在 Task 1 用例之后跑，config.js 只会加载一次，`getActiveProvider` 每次调用现读状态，所以无顺序问题。

- [ ] **Step 2: 跑测试确认失败**

```bash
cd agent-ts && npm test -- model-switcher 2>&1 | tail -8
```
预期：后两个集成用例 FAIL（override 未生效，createModel 仍返回 deepseek 配置）。

- [ ] **Step 3: 修改 config.ts**

`src/config/config.ts` 顶部 import 区追加：

```typescript
import { getRuntimeOverride } from "./model-switcher.js";
```

`getActiveProvider()` 改为：

```typescript
/**
 * 当前激活的 LLM provider
 * 优先级：运行时 override（/provider 命令或 model_switch 工具设置）
 *        > LLM_PROVIDER 环境变量 > 默认 deepseek
 */
export function getActiveProvider(): LLMProviderName {
  const override = getRuntimeOverride();
  if (override) return override;
  const p = (process.env.LLM_PROVIDER || 'deepseek').toLowerCase();
  if (p in PROVIDER_PRESETS) return p as LLMProviderName;
  console.warn(`[config] 未知 LLM_PROVIDER="${p}"，回退到 deepseek`);
  return 'deepseek';
}
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd agent-ts && npm test -- model-switcher 2>&1 | tail -5
```
预期：PASS（12 个用例）。

- [ ] **Step 5: 回归——跑全部 config 相关测试**

```bash
cd agent-ts && npm test -- src/config 2>&1 | tail -5
```
预期：全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add src/config/config.ts src/config/model-switcher.test.ts
git commit -m "feat(config): getActiveProvider 优先读运行时 override，支持热切换"
```

---

### Task 3: model_switch agent 工具

**Files:**
- Create: `src/infrastructure/tools/agent/model-switch-tool.ts`
- Test: `src/infrastructure/tools/agent/model-switch-tool.test.ts`
- Modify: `src/infrastructure/tools/index.ts`（import + allCustomTools 注册）
- Modify: `src/infrastructure/tools/tool-groups.ts`（CORE_TOOLS 加 `"model_switch"`）

- [ ] **Step 1: 写失败测试**

创建 `src/infrastructure/tools/agent/model-switch-tool.test.ts`：

```typescript
/**
 * model_switch 工具测试
 */
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { modelSwitchTool, resetSwitchHistoryForTests } from './model-switch-tool.js';
import {
  setRuntimeProvider,
  resetRuntimeProviderForTests,
  getRuntimeOverride,
} from '../../../config/model-switcher.js';

const ENV_KEYS = ['LLM_API_KEY', 'DEEPSEEK_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY'];
let savedEnv: Record<string, string | undefined>;

beforeEach(() => {
  savedEnv = {};
  for (const k of ENV_KEYS) { savedEnv[k] = process.env[k]; delete process.env[k]; }
  resetRuntimeProviderForTests();
  resetSwitchHistoryForTests();
});

afterEach(() => {
  for (const k of ENV_KEYS) {
    if (savedEnv[k] === undefined) delete process.env[k];
    else process.env[k] = savedEnv[k];
  }
  resetRuntimeProviderForTests();
});

async function run(provider: string): Promise<string> {
  const result = await modelSwitchTool.execute('test-call', { provider });
  return result.content[0].type === 'text' ? result.content[0].text : '';
}

describe('model_switch 工具', () => {
  it('正常切换：设置 override 并返回决策上下文', async () => {
    process.env.DEEPSEEK_API_KEY = 'sk-a';
    process.env.KIMI_API_KEY = 'sk-b';
    const text = await run('kimi');
    expect(getRuntimeOverride()).toBe('kimi');
    expect(text).toContain('kimi');
    expect(text).toContain('新会话');
  });

  it('幂等：目标 = 当前 provider 时不重复切换', async () => {
    process.env.DEEPSEEK_API_KEY = 'sk-a';
    const text = await run('deepseek'); // 当前默认就是 deepseek
    expect(text).toContain('已是');
    expect(getRuntimeOverride()).toBeNull(); // 未设置 override
  });

  it('缺 key 拒绝切换', async () => {
    process.env.DEEPSEEK_API_KEY = 'sk-a';
    const text = await run('kimi'); // kimi 无 key
    expect(text).toContain('未配置');
    expect(getRuntimeOverride()).toBeNull();
  });

  it('防抖动：滚动窗口内最多 3 次，第 4 次拒绝', async () => {
    process.env.DEEPSEEK_API_KEY = 'sk-a';
    process.env.KIMI_API_KEY = 'sk-b';
    expect(await run('kimi')).toContain('kimi');
    expect(await run('deepseek')).toContain('deepseek');
    expect(await run('kimi')).toContain('kimi');
    const fourth = await run('deepseek');
    expect(fourth).toContain('过于频繁');
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd agent-ts && npm test -- model-switch-tool 2>&1 | tail -5
```
预期：FAIL，`Cannot find module './model-switch-tool.js'`。

- [ ] **Step 3: 实现工具**

创建 `src/infrastructure/tools/agent/model-switch-tool.ts`：

```typescript
/**
 * model_switch — LLM provider 热切换工具（agent 自主入口）
 *
 * 当当前模型持续报错（429 限流 / 超时 / 5xx）时，agent 可调用本工具
 * 切换到备用 provider。
 *
 * 生效范围（重要）：只设置进程级运行时状态，对之后新建的会话
 * （定时任务唤醒、subagent、下一个人工会话）立即生效；
 * 当前正在运行的会话保持原模型直到结束——工具拿不到 session 句柄，
 * 无法调 setModel。人工要立即切当前会话请用 /provider 命令。
 *
 * 防抖动：滚动 1 小时窗口内最多切换 3 次。
 */

import type { ToolDefinition } from "../index.js";
import { getActiveProvider, getActiveModelId, createModel } from "../../../config/config.js";
import {
  setRuntimeProvider,
  isProviderConfigured,
  logSwitch,
  type RuntimeProviderName,
} from "../../../config/model-switcher.js";

const WINDOW_MS = 60 * 60 * 1000;
const MAX_SWITCHES_PER_WINDOW = 3;
const switchTimestamps: number[] = [];

/** 仅测试使用：清空切换历史 */
export function resetSwitchHistoryForTests(): void {
  switchTimestamps.length = 0;
}

const PROVIDERS: RuntimeProviderName[] = ["deepseek", "kimi"];

export const modelSwitchTool: ToolDefinition = {
  name: "model_switch",
  description:
    "切换 LLM provider（deepseek ↔ kimi）。当当前模型持续报错（429 限流、超时、5xx）时使用。" +
    "注意：仅对之后新建的会话生效（定时任务、subagent），当前会话继续用原模型直到结束；" +
    "如需本会话立即切换，请提示用户使用 /provider 命令。1 小时内最多切换 3 次。",
  parameters: {
    type: "object",
    properties: {
      provider: {
        type: "string",
        enum: PROVIDERS,
        description: "目标 provider：deepseek 或 kimi",
      },
    },
    required: ["provider"],
  },
  execute: async (_toolCallId, params) => {
    const { provider } = params as { provider: string };
    const fail = (msg: string) => ({
      content: [{ type: "text" as const, text: msg }],
      details: { error: msg },
    });

    if (!PROVIDERS.includes(provider as RuntimeProviderName)) {
      return fail(`❌ 未知 provider "${provider}"，可选：${PROVIDERS.join(", ")}`);
    }
    const target = provider as RuntimeProviderName;
    const current = getActiveProvider();

    if (target === current) {
      return {
        content: [{ type: "text" as const, text: `ℹ️ 已是 ${target}（${getActiveModelId()}），无需切换。` }],
        details: { provider: current, changed: false },
      };
    }

    if (!isProviderConfigured(target)) {
      return fail(`❌ ${target} 的 API key 未配置，无法切换。请在 .env 配置后重试。`);
    }

    const now = Date.now();
    const recent = switchTimestamps.filter((t) => now - t < WINDOW_MS);
    if (recent.length >= MAX_SWITCHES_PER_WINDOW) {
      return fail(
        `❌ 切换过于频繁：1 小时内已切换 ${recent.length} 次（上限 ${MAX_SWITCHES_PER_WINDOW}）。` +
        `两个 provider 可能都不可用，请提示用户人工排查（/provider 命令不受此限制）。`
      );
    }

    setRuntimeProvider(target);
    switchTimestamps.push(now);
    const model = createModel(); // 同步 OPENAI_API_KEY 到新 provider 的 key
    logSwitch(current, target, "agent");

    const text = [
      `✅ 已从 ${current} 切换到 ${target}（${model.id}）。`,
      `生效范围：之后新建的会话（定时任务唤醒、subagent）将使用 ${target}；`,
      `当前会话继续使用 ${current} 直到结束。如需本会话立即切换，请提示用户使用 /provider 命令。`,
    ].join("\n");
    return {
      content: [{ type: "text" as const, text }],
      details: { from: current, to: target, modelId: model.id, changed: true },
    };
  },
};
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd agent-ts && npm test -- model-switch-tool 2>&1 | tail -5
```
预期：PASS（4 个用例）。

- [ ] **Step 5: 注册工具**

`src/infrastructure/tools/index.ts`：在 `import { loadToolsTool } ...`（约 186 行）下方追加：

```typescript
import { modelSwitchTool } from "./agent/model-switch-tool.js";
```

在 `allCustomTools` 数组中 `loadToolsTool,`（约 216 行）下方追加：

```typescript
  modelSwitchTool,
```

`src/infrastructure/tools/tool-groups.ts`：在 `CORE_TOOLS` 数组中 `"load_tools"` 所在位置附近追加 `"model_switch",`（保持注释分组，加一行 `// === 系统 ===` 注释非必需）。先 grep 确认 `load_tools` 在 CORE_TOOLS 的行号：

```bash
grep -n '"load_tools"' src/infrastructure/tools/tool-groups.ts
```

- [ ] **Step 6: 回归测试**

```bash
cd agent-ts && npm test -- tool-groups 2>&1 | tail -5
cd agent-ts && npm test -- model-switch 2>&1 | tail -5
```
预期：全部 PASS。

- [ ] **Step 7: 提交**

```bash
git add src/infrastructure/tools/agent/model-switch-tool.ts \
        src/infrastructure/tools/agent/model-switch-tool.test.ts \
        src/infrastructure/tools/index.ts \
        src/infrastructure/tools/tool-groups.ts
git commit -m "feat(tools): model_switch 工具——agent 可自主切换 LLM provider（新会话生效，3次/小时防抖）"
```

---

### Task 4: /provider 斜杠命令（SDK extension）

**Files:**
- Create: `src/api/extensions/model-command.ts`
- Modify: `src/core/agent/agent-loop.ts`（createAgentSession options 加 resourceLoader，约 203-210 行）
- Modify: `src/api/gateway/session-factory.ts`（同上，约 83 行附近）
- Modify: `src/core/agent/background-agent-loop.ts`（同上，约 52 行附近）

- [ ] **Step 1: 实现 extension**

创建 `src/api/extensions/model-command.ts`：

```typescript
/**
 * /provider 斜杠命令 — LLM provider 热切换（人工入口）
 *
 * 通过 SDK extensionFactories 注入。命名 /provider 而非 /model，
 * 因为 SDK 内置 /model 已存在（模型选择器，不认识我们的自定义模型）。
 *
 * 用法：
 *   /provider            显示当前 provider 与各 provider key 配置状态
 *   /provider kimi       切换到 Kimi（当前会话立即生效 + 未来新会话）
 *   /provider deepseek   切换到 DeepSeek
 */

import {
  DefaultResourceLoader,
  getAgentDir,
  type ExtensionFactory,
} from "@mariozechner/pi-coding-agent";
import {
  createModel,
  getActiveProvider,
  getActiveModelId,
} from "../../config/config.js";
import {
  setRuntimeProvider,
  isProviderConfigured,
  listProviders,
  logSwitch,
  type RuntimeProviderName,
} from "../../config/model-switcher.js";

const PROVIDERS: RuntimeProviderName[] = ["deepseek", "kimi"];

export const modelCommandExtension: ExtensionFactory = (pi) => {
  pi.registerCommand("provider", {
    description: "查看或切换 LLM provider（deepseek/kimi）",
    handler: async (args, ctx) => {
      const target = args.trim();

      // 无参数：显示状态
      if (!target) {
        const current = getActiveProvider();
        const lines = listProviders()
          .map((p) => ` ${p.name === current ? "→" : " "} ${p.name}: ${p.configured ? "key 已配置" : "❌ key 未配置"}`)
          .join("\n");
        ctx.ui.notify(`当前 provider: ${current} (${getActiveModelId()})\n${lines}`, "info");
        return;
      }

      if (!PROVIDERS.includes(target as RuntimeProviderName)) {
        ctx.ui.notify(`❌ 未知 provider "${target}"，可选：${PROVIDERS.join(", ")}`, "error");
        return;
      }

      const current = getActiveProvider();
      if (target === current) {
        ctx.ui.notify(`ℹ️ 已是 ${target}，无需切换`, "info");
        return;
      }

      if (!isProviderConfigured(target as RuntimeProviderName)) {
        ctx.ui.notify(`❌ ${target} 的 API key 未配置（检查 .env 的 ${target.toUpperCase()}_API_KEY）`, "error");
        return;
      }

      setRuntimeProvider(target as RuntimeProviderName);
      const model = createModel();
      const ok = await pi.setModel(model);
      if (ok) {
        logSwitch(current, target, "human");
        ctx.ui.notify(`✅ 已切换 ${current} → ${target} (${model.id})，下一轮对话生效`, "info");
      } else {
        ctx.ui.notify(
          `⚠️ 运行时状态已切换（新会话将用 ${target}），但当前会话 setModel 未生效`,
          "warning"
        );
      }
    },
  });
};

/**
 * 构建带 /provider 命令的 ResourceLoader。
 * 与 SDK 内部默认构造参数一致（sdk.js: new DefaultResourceLoader({ cwd, agentDir, settingsManager })），
 * 仅追加 extensionFactories。SDK 只在自己创建 loader 时才调 reload()，
 * 所以这里必须自行 await reload()。
 */
export async function createAppResourceLoader(cwd: string): Promise<DefaultResourceLoader> {
  const loader = new DefaultResourceLoader({
    cwd,
    agentDir: getAgentDir(),
    extensionFactories: [modelCommandExtension],
  });
  await loader.reload();
  return loader;
}
```

- [ ] **Step 2: 编译检查**

```bash
cd agent-ts && npx tsc --noEmit -p tsconfig.build.json 2>&1 | grep -v "^$" | head -20
```
预期：无 `model-command.ts` 相关错误（仓库若存在基线错误，只关注新文件的）。若 `pi.setModel` 或 `registerCommand` 类型不匹配，对照 `node_modules/@mariozechner/pi-coding-agent/dist/core/extensions/types.d.ts:816,863` 调整。

- [ ] **Step 3: 接线 agent-loop.ts**

`src/core/agent/agent-loop.ts` 顶部 import 追加：

```typescript
import { createAppResourceLoader } from "../../api/extensions/model-command.js";
```

`createSessionInternal` 中 `createAgentSession` 调用（约 203 行）改为：

```typescript
  const resourceLoader = await createAppResourceLoader(paths.root);
  // @ts-ignore - Type mismatch from SDK update
  const result = await createAgentSession({
    cwd: paths.root,
    model: createModel(),
    sessionManager,
    resourceLoader,
    systemPrompt: () => buildSystemPromptForContext(sessionContext),
    customTools: cachedTools,
    skills: cachedSkills,
  } as any);
```

- [ ] **Step 4: 接线 gateway/session-factory.ts 与 background-agent-loop.ts**

两处同样：import `createAppResourceLoader`，在各自 `createAgentSession`/`createSession` 调用点（gateway/session-factory.ts:83、background-agent-loop.ts:52 附近的 `model: createModel()` 处）的 options 里加 `resourceLoader: await createAppResourceLoader(paths.root)`。先读这两个文件确认 options 对象形状再改。

注意：gateway 每个会话一个 loader 实例是安全的（工厂幂等注册）；若发现启动变慢再考虑共享单例。

- [ ] **Step 5: 编译 + 全部测试回归**

```bash
cd agent-ts && npx tsc --noEmit -p tsconfig.build.json 2>&1 | head -20
cd agent-ts && npm test 2>&1 | tail -8
```
预期：无新编译错误；全部测试 PASS（关注 session-factory.test.ts 等涉及 session 创建的测试）。

- [ ] **Step 6: 提交**

```bash
git add src/api/extensions/model-command.ts \
        src/core/agent/agent-loop.ts \
        src/api/gateway/session-factory.ts \
        src/core/agent/background-agent-loop.ts
git commit -m "feat(cli): /provider 斜杠命令——人工热切换 LLM provider（当前会话立即生效）"
```

- [ ] **Step 7: 手动验证（人在终端执行）**

```bash
cd agent-ts && npm run dev
```

1. 输入 `/provider` → 显示当前 deepseek 及各 key 状态
2. 输入 `/provider kimi` → `✅ 已切换 deepseek → kimi (k3)`
3. 随便问一句 → 确认能正常回复（请求打到 KIMI_BASE_URL）
4. `cat .pi-invest/model-switch.log` → 有切换记录
5. `/provider deepseek` 切回

若 `pi.setModel` 返回 false 或抛错（auth 校验），记录现象——降级路径已在代码中（warning 提示，新会话仍生效）。

---

### Task 5: 文档同步与收尾

**Files:**
- Modify: `docs/superpowers/specs/2026-07-28-model-hot-switch-design.md`（命令名 /model → /provider）
- Modify: `agent-ts/CLAUDE.md`（Environment Setup 节加热切换说明）

- [ ] **Step 1: 更新 spec**

把 spec 中「组件 3：CLI 斜杠命令 `/model`」一节及「手动验证」里的 `/model` 全部改为 `/provider`，并在组件 3 开头加一句：

> 命名说明：SDK 内置 `/model` 命令（模型选择器）已存在，为避免冲突自定义命令命名为 `/provider`。

- [ ] **Step 2: 更新 agent-ts/CLAUDE.md**

在 `## Environment Setup` 的 env 列表示例（`LLM_PROVIDER=deepseek` 处）下方加一段：

```markdown
**运行时热切换（2026-07-28）：** 不重启进程切换 provider：
- 人工：TUI 中 `/provider` 查看状态，`/provider kimi` / `/provider deepseek` 切换（当前会话立即生效）
- Agent：`model_switch` 工具（仅新会话生效，1 小时内限 3 次）
- 仅内存生效，重启后回到 `LLM_PROVIDER`；切换审计日志在 `.pi-invest/model-switch.log`
```

- [ ] **Step 3: 提交**

```bash
git add docs/superpowers/specs/2026-07-28-model-hot-switch-design.md agent-ts/CLAUDE.md
git commit -m "docs: 模型热切换文档同步（/provider 命令命名与使用说明）"
```

- [ ] **Step 4: 最终验证**

worktree 内全量测试通过后，按仓库规则合并回 main（临时 worktree 合并或 PR），再推送。

---

## Self-Review 记录

- **Spec 覆盖**：运行时状态(T1) / config 接入(T2) / agent 工具+护栏+日志(T3) / 斜杠命令(T4) / 文档(T5)。spec 的「持久化不做」「自动 failover 不做」为非目标，无任务。
- **已知 spec 偏差**：命令名 `/model` → `/provider`（SDK 内置冲突），T5 Step 1 同步 spec。
- **类型一致性**：`RuntimeProviderName`、`setRuntimeProvider`、`isProviderConfigured`、`listProviders`、`logSwitch`、`resetRuntimeProviderForTests`、`resetSwitchHistoryForTests`、`createAppResourceLoader`、`modelCommandExtension` 在定义与引用处一致。
- **防抖动口径**：spec 写"每会话最多 3 次"，工具拿不到 session 标识，实现为"滚动 1 小时窗口 3 次"（进程级），比 spec 更保守；已在工具描述和报错文案中说明。
