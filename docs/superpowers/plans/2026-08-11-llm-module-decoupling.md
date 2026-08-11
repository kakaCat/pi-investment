# LLM 供给模块解耦 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 LLM provider 配置/切换/调用从 config.ts 与 agent loop 中解耦为独立模块 `src/services/llm/`（自有类型体系 + LLMPort 端口），切换统一切换服务并持久化，活跃会话下一轮惰性生效。

**Architecture:** 新建 `src/services/llm/`（types / port / catalog / selection / switch-service / client / adapters/pi-ai），agent 世界只依赖 `port.ts`+`types.ts`；`config.ts` 的 `createModel()` 等改为薄代理保持向后兼容；`/provider` 与 `model_switch` 统一调 `switch()`；gateway `beforePrompt` 挂版本比对实现惰性生效。

**Tech Stack:** TypeScript (ESM)、Jest（必须 `npm test`，禁止裸 `npx jest`——会误报 TS1378）、pi-ai SDK（仅 adapters/pi-ai.ts 可 import）。

**Spec:** `docs/superpowers/specs/2026-08-11-llm-module-decoupling-design.md`

**关键既有事实（执行者必读）：**
- 现有回归测试 `src/config/config.test.ts` / `src/config/model-switcher.test.ts` 必须全程保持绿色（kimi compat 两次事故的教训，锁死 `supportsDeveloperRole: false`）。
- 测试运行：`npm test -- --runTestsByPath <file>`。
- 遗留运行时 override 链：`config/model-switcher.ts`（内存）保留不动；生产链路改为 state 文件 > env > 默认，model-switcher override 仅在单测中生效。
- selection 模块**显式初始化**（`initSelection(piDir)`），未初始化时回退 env/default——这保证既有单测不读到真实 state 文件。
- 工作区规则：本仓库要求 worktree 隔离开发，合并回 main 后再删 worktree。
- 审计日志格式（保留兼容）：`.pi-invest/model-switch.log` 每行 JSON `{ts, from, to, trigger}`。

---

### Task 1: types.ts —— 自有类型体系

**Files:**
- Create: `agent-ts/src/services/llm/types.ts`
- Test: `agent-ts/src/services/llm/types.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// agent-ts/src/services/llm/types.test.ts
import { describe, it, expect } from '@jest/globals';
import { LLMError } from './types.js';

describe('LLMError', () => {
  it('携带 kind 与 retryable，且是 Error 实例', () => {
    const e = new LLMError('boom', 'rate_limit', true);
    expect(e.message).toBe('boom');
    expect(e.kind).toBe('rate_limit');
    expect(e.retryable).toBe(true);
    expect(e).toBeInstanceOf(Error);
    expect(e.name).toBe('LLMError');
  });

  it('默认 kind=unknown 且不可重试', () => {
    const e = new LLMError('x');
    expect(e.kind).toBe('unknown');
    expect(e.retryable).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/types.test.ts`
Expected: FAIL — `Cannot find module './types.js'`

- [ ] **Step 3: Write implementation**

```ts
// agent-ts/src/services/llm/types.ts
/**
 * LLM 自有类型体系 —— 禁止 import 任何 SDK 类型。
 * agent 世界（agent loop / 工具 / 命令）只依赖本文件与 port.ts。
 */

export type LLMProviderName = 'deepseek' | 'kimi';

export interface LLMCompat {
  supportsDeveloperRole?: boolean;
  supportsStore?: boolean;
  maxTokensField?: 'max_tokens' | 'max_completion_tokens';
}

/** 已解析完成的模型配置（凭证/端点已合成终值） */
export interface LLMModelConfig {
  provider: LLMProviderName;
  modelId: string;
  displayName: string;
  baseUrl: string;
  apiKey: string;
  contextWindow: number;
  maxTokens: number;
  reasoning: boolean;
  compat?: LLMCompat;
  timeoutMs: number;
  maxRetries: number;
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  maxTokens?: number;
  temperature?: number;
}

export interface Usage {
  input: number;
  output: number;
  totalTokens: number;
}

export interface ChatResponse {
  text: string;
  usage: Usage;
  model: string;
}

export type LLMErrorKind =
  | 'auth'
  | 'rate_limit'
  | 'overloaded'
  | 'timeout'
  | 'invalid_request'
  | 'unknown';

export class LLMError extends Error {
  readonly kind: LLMErrorKind;
  readonly retryable: boolean;
  constructor(message: string, kind: LLMErrorKind = 'unknown', retryable = false) {
    super(message);
    this.name = 'LLMError';
    this.kind = kind;
    this.retryable = retryable;
  }
}

/** 当前选择来源：state 文件 > env > 默认 */
export type SelectionSource = 'state' | 'env' | 'default';

export interface LLMSelection {
  provider: LLMProviderName;
  modelId: string;
  updatedBy: 'human' | 'agent' | 'env' | 'default';
  updatedAt: string; // ISO
  version: number;   // 单调递增，惰性生效比对用
}

export interface SwitchResult {
  ok: boolean;
  changed: boolean;
  from: string; // 'provider:modelId'
  to: string;
  error?: string;
}

export interface LLMProviderStatus {
  name: LLMProviderName;
  configured: boolean;
  active: boolean;
  modelId: string;
}

export interface LLMStatus {
  current: LLMSelection;
  source: SelectionSource;
  providers: LLMProviderStatus[];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/types.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/services/llm/types.ts agent-ts/src/services/llm/types.test.ts
git commit -m "feat(llm): 自有类型体系 types.ts——LLMModelConfig/Chat*/LLMError/Selection"
```

---

### Task 2: catalog.ts —— provider 目录（presets + env 合成）

从 `config.ts` 迁入 `PROVIDER_PRESETS` / 别名表 / `MODEL_TARGETS` / key 检测，**逐字保留** preset 数值与 compat 声明（含注释中的事故教训）。

**Files:**
- Create: `agent-ts/src/services/llm/catalog.ts`
- Test: `agent-ts/src/services/llm/catalog.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// agent-ts/src/services/llm/catalog.test.ts
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import {
  buildModelConfig,
  envModelId,
  isProviderConfigured,
  resolveModelTarget,
  resolveProvider,
} from './catalog.js';

const ENV_KEYS = [
  'LLM_PROVIDER', 'LLM_API_KEY', 'LLM_BASE_URL', 'LLM_REASONING',
  'LLM_CONTEXT_WINDOW', 'LLM_MAX_TOKENS', 'MODEL_ID',
  'DEEPSEEK_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY', 'OPENAI_API_KEY',
  'KIMI_BASE_URL', 'KIMI_MODEL_ID', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_MODEL_ID',
];
let saved: Record<string, string | undefined>;
beforeEach(() => {
  saved = {};
  for (const k of ENV_KEYS) { saved[k] = process.env[k]; delete process.env[k]; }
});
afterEach(() => {
  for (const k of ENV_KEYS) {
    if (saved[k] === undefined) delete process.env[k]; else process.env[k] = saved[k];
  }
});

describe('resolveProvider 别名', () => {
  it('k3/moonshot 归一为 kimi；deepseek-chat 归一为 deepseek', () => {
    expect(resolveProvider('k3')).toBe('kimi');
    expect(resolveProvider('Moonshot')).toBe('kimi');
    expect(resolveProvider('deepseek-chat')).toBe('deepseek');
    expect(resolveProvider('gpt-5')).toBeNull();
  });
});

describe('resolveModelTarget', () => {
  it('flash/pro 短别名与完整模型 ID', () => {
    expect(resolveModelTarget('flash')).toEqual({ provider: 'deepseek', modelId: 'deepseek-v4-flash' });
    expect(resolveModelTarget('PRO')).toEqual({ provider: 'deepseek', modelId: 'deepseek-v4-pro' });
    expect(resolveModelTarget('kimi-k3')).toEqual({ provider: 'kimi', modelId: 'kimi-k3' });
    expect(resolveModelTarget('deepseek')).toBeNull();
  });
});

describe('buildModelConfig', () => {
  it('kimi compat 锁死：supportsDeveloperRole=false（两次事故回归）', () => {
    process.env.KIMI_API_KEY = 'k';
    const c = buildModelConfig('kimi', 'kimi-k3');
    expect(c.compat?.supportsDeveloperRole).toBe(false);
    expect(c.compat?.supportsStore).toBe(false);
    expect(c.compat?.maxTokensField).toBe('max_tokens');
  });

  it('deepseek 默认 flash，128K 工作窗口，DEEPSEEK_MODEL_ID 可覆盖', () => {
    process.env.DEEPSEEK_API_KEY = 'k';
    expect(buildModelConfig('deepseek', envModelId('deepseek')).modelId).toBe('deepseek-v4-flash');
    expect(buildModelConfig('deepseek', envModelId('deepseek')).contextWindow).toBe(128000);
    process.env.DEEPSEEK_MODEL_ID = 'deepseek-v4-pro';
    expect(envModelId('deepseek')).toBe('deepseek-v4-pro');
  });

  it('通用覆盖：LLM_BASE_URL / LLM_CONTEXT_WINDOW / LLM_REASONING=false', () => {
    process.env.DEEPSEEK_API_KEY = 'k';
    process.env.LLM_BASE_URL = 'http://proxy.local/v1';
    process.env.LLM_CONTEXT_WINDOW = '1000000';
    process.env.LLM_REASONING = 'false';
    const c = buildModelConfig('deepseek', 'deepseek-v4-flash');
    expect(c.baseUrl).toBe('http://proxy.local/v1');
    expect(c.contextWindow).toBe(1000000);
    expect(c.reasoning).toBe(false);
  });

  it('key 解析：LLM_API_KEY 通用覆盖优先', () => {
    process.env.DEEPSEEK_API_KEY = 'ds';
    process.env.LLM_API_KEY = 'override';
    expect(buildModelConfig('deepseek', 'deepseek-v4-flash').apiKey).toBe('override');
  });
});

describe('isProviderConfigured', () => {
  it('专用 key 或 LLM_API_KEY 存在即已配置；OPENAI_API_KEY 不算（防假已配置）', () => {
    expect(isProviderConfigured('kimi')).toBe(false);
    process.env.OPENAI_API_KEY = 'x';
    expect(isProviderConfigured('kimi')).toBe(false);
    process.env.KIMI_API_KEY = 'x';
    expect(isProviderConfigured('kimi')).toBe(true);
    delete process.env.KIMI_API_KEY;
    process.env.LLM_API_KEY = 'x';
    expect(isProviderConfigured('kimi')).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/catalog.test.ts`
Expected: FAIL — `Cannot find module './catalog.js'`

- [ ] **Step 3: Write implementation**

```ts
// agent-ts/src/services/llm/catalog.ts
/**
 * Provider 目录：代码内置 presets + env 合成（自 config.ts 迁入，数值逐字保留）。
 *
 * 所有 provider 均走 OpenAI 兼容接口；.env 是所有 provider 的"配置目录"
 * （凭证/端点/模型覆盖），启动时由本模块合成为内存配置。
 */
import type { LLMCompat, LLMModelConfig, LLMProviderName } from './types.js';

export interface ProviderPreset {
  name: string;
  baseUrl: string;
  modelId: string;
  apiKeyEnv: string[];
  contextWindow: number;
  maxTokens: number;
  reasoning: boolean;
  compat?: LLMCompat;
}

export const PROVIDER_PRESETS: Record<LLMProviderName, ProviderPreset> = {
  deepseek: {
    name: 'DeepSeek Chat',
    baseUrl: 'https://api.deepseek.com/v1',
    // 官方模型列表现仅 deepseek-v4-flash / deepseek-v4-pro（deepseek-chat 为遗留别名）。
    modelId: 'deepseek-v4-flash',
    apiKeyEnv: ['DEEPSEEK_API_KEY', 'OPENAI_API_KEY'],
    // v4 全系实际上下文 1M / 最大输出 384K。这里按 128K 工作窗口配置：
    // agent 每轮全量重发上下文，窗口越大单轮成本越高；需要长上下文时
    // 用 LLM_CONTEXT_WINDOW 覆盖（上限 1048576）。
    contextWindow: 128000,
    maxTokens: 8000,
    reasoning: true,
  },
  kimi: {
    name: 'Kimi (Moonshot)',
    baseUrl: 'https://api.moonshot.cn/v1',
    modelId: 'kimi-k3',
    apiKeyEnv: ['KIMI_API_KEY', 'MOONSHOT_API_KEY', 'OPENAI_API_KEY'],
    contextWindow: 256000,
    maxTokens: 8000,
    reasoning: true,
    // api.kimi.com / 本地代理 不匹配 SDK 的 isMoonshot 检测（只认 api.moonshot.*），
    // 会被当作标准 OpenAI：reasoning=true 时 system prompt 以 role:"developer" 发送，
    // Kimi 端点不认识该 role，报 400 Invalid request: tokenization failed。
    // ⚠️ 勿删——已两次因丢失此配置出事故。
    compat: {
      supportsDeveloperRole: false,
      supportsStore: false,
      maxTokensField: 'max_tokens',
    },
  },
};

export const PROVIDER_NAMES = Object.keys(PROVIDER_PRESETS) as LLMProviderName[];

/** LLM_PROVIDER 常见误写兜底（模型 ID 误填进 provider 时映射回正确 provider） */
const PROVIDER_ALIASES: Record<string, LLMProviderName> = {
  kimi: 'kimi',
  moonshot: 'kimi',
  k3: 'kimi',
  'kimi-k3': 'kimi',
  deepseek: 'deepseek',
  'deepseek-chat': 'deepseek',
  'deepseek-v4-flash': 'deepseek',
  'deepseek-v4-pro': 'deepseek',
  'deepseek-reasoner': 'deepseek',
};

export function resolveProvider(input: string): LLMProviderName | null {
  return PROVIDER_ALIASES[input.trim().toLowerCase()] ?? null;
}

/** 可热切换的模型目标（短别名 + 完整模型 ID）；provider 名/未知串返回 null */
const MODEL_TARGETS: Record<string, { provider: LLMProviderName; modelId: string }> = {
  flash: { provider: 'deepseek', modelId: 'deepseek-v4-flash' },
  pro: { provider: 'deepseek', modelId: 'deepseek-v4-pro' },
  'deepseek-v4-flash': { provider: 'deepseek', modelId: 'deepseek-v4-flash' },
  'deepseek-v4-pro': { provider: 'deepseek', modelId: 'deepseek-v4-pro' },
  'kimi-k3': { provider: 'kimi', modelId: 'kimi-k3' },
  k3: { provider: 'kimi', modelId: 'kimi-k3' },
};

export function resolveModelTarget(
  input: string,
): { provider: LLMProviderName; modelId: string } | null {
  return MODEL_TARGETS[input.trim().toLowerCase()] ?? null;
}

/**
 * 各 provider 的专用 key 环境变量（用于"是否已配置"判断）。
 * 故意不包含 OPENAI_API_KEY：adapter 会把当前 provider 的 key 同步到
 * OPENAI_API_KEY，包含它会让另一 provider 出现"假已配置"。
 */
const PROVIDER_KEY_ENV: Record<LLMProviderName, string[]> = {
  deepseek: ['DEEPSEEK_API_KEY'],
  kimi: ['KIMI_API_KEY', 'MOONSHOT_API_KEY'],
};

export function isProviderConfigured(p: LLMProviderName, env = process.env): boolean {
  if (env.LLM_API_KEY) return true;
  return PROVIDER_KEY_ENV[p].some((k) => !!env[k]);
}

export function resolveApiKey(provider: LLMProviderName, env = process.env): string {
  const preset = PROVIDER_PRESETS[provider];
  return env.LLM_API_KEY || preset.apiKeyEnv.map((k) => env[k]).find(Boolean) || '';
}

/** env 链模型解析：{PROVIDER}_MODEL_ID > MODEL_ID > preset 默认 */
export function envModelId(provider: LLMProviderName, env = process.env): string {
  return (
    env[`${provider.toUpperCase()}_MODEL_ID`] ||
    env.MODEL_ID ||
    PROVIDER_PRESETS[provider].modelId
  );
}

/** 合成最终模型配置：preset 为底，LLM_* / {PROVIDER}_* env 覆盖 */
export function buildModelConfig(
  provider: LLMProviderName,
  modelId: string,
  env = process.env,
): LLMModelConfig {
  const preset = PROVIDER_PRESETS[provider];
  return {
    provider,
    modelId,
    displayName: preset.name,
    baseUrl:
      env.LLM_BASE_URL || env[`${provider.toUpperCase()}_BASE_URL`] || preset.baseUrl,
    apiKey: resolveApiKey(provider, env),
    contextWindow: Number(env.LLM_CONTEXT_WINDOW) || preset.contextWindow,
    maxTokens: Number(env.LLM_MAX_TOKENS) || preset.maxTokens,
    reasoning: env.LLM_REASONING ? env.LLM_REASONING !== 'false' : preset.reasoning,
    ...(preset.compat ? { compat: preset.compat } : {}),
    timeoutMs: 120000,
    maxRetries: 2,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/catalog.test.ts`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/services/llm/catalog.ts agent-ts/src/services/llm/catalog.test.ts
git commit -m "feat(llm): catalog.ts——provider presets/别名/模型目标/env合成（自config.ts迁入）"
```

---

### Task 3: selection.ts —— 当前选择 + 持久化 + 优先级链

显式初始化设计：`initSelection(piDir)` 由启动引导调用；未初始化时 `effectiveSelection()` 回退 env/default（既有单测不会读到真实 state 文件）。

**Files:**
- Create: `agent-ts/src/services/llm/selection.ts`
- Test: `agent-ts/src/services/llm/selection.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// agent-ts/src/services/llm/selection.test.ts
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdtempSync, writeFileSync, readFileSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import {
  effectiveSelection,
  getSelection,
  initSelection,
  onSelectionChange,
  resetSelectionForTests,
  selectionSource,
  setSelection,
} from './selection.js';

let dir: string;
let savedProvider: string | undefined;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'llm-sel-'));
  savedProvider = process.env.LLM_PROVIDER;
  delete process.env.LLM_PROVIDER;
  resetSelectionForTests();
});
afterEach(() => {
  if (savedProvider === undefined) delete process.env.LLM_PROVIDER;
  else process.env.LLM_PROVIDER = savedProvider;
  resetSelectionForTests();
  rmSync(dir, { recursive: true, force: true });
});

describe('initSelection 优先级链', () => {
  it('无 state 文件无 env → 默认 deepseek-v4-flash，source=default', () => {
    const sel = initSelection(dir);
    expect(sel.provider).toBe('deepseek');
    expect(sel.modelId).toBe('deepseek-v4-flash');
    expect(selectionSource()).toBe('default');
  });

  it('无 state 文件有 LLM_PROVIDER=kimi → env 生效，source=env', () => {
    process.env.LLM_PROVIDER = 'kimi';
    const sel = initSelection(dir);
    expect(sel.provider).toBe('kimi');
    expect(sel.modelId).toBe('kimi-k3');
    expect(selectionSource()).toBe('env');
  });

  it('state 文件存在 → 压过 env，source=state', () => {
    process.env.LLM_PROVIDER = 'kimi';
    writeFileSync(join(dir, 'llm-state.json'), JSON.stringify({
      provider: 'deepseek', modelId: 'deepseek-v4-pro',
      updatedBy: 'human', updatedAt: '2026-08-11T00:00:00.000Z', version: 7,
    }));
    const sel = initSelection(dir);
    expect(sel.provider).toBe('deepseek');
    expect(sel.modelId).toBe('deepseek-v4-pro');
    expect(sel.version).toBe(7);
    expect(selectionSource()).toBe('state');
  });

  it('state 文件损坏 → 警告并回退 env/default，不抛错', () => {
    writeFileSync(join(dir, 'llm-state.json'), '{broken json');
    const sel = initSelection(dir);
    expect(sel.provider).toBe('deepseek');
    expect(selectionSource()).toBe('default');
  });

  it('state 文件 provider 非法 → 回退 env/default', () => {
    writeFileSync(join(dir, 'llm-state.json'), JSON.stringify({ provider: 'gpt5', modelId: 'x' }));
    const sel = initSelection(dir);
    expect(sel.provider).toBe('deepseek');
  });
});

describe('setSelection 持久化', () => {
  it('写 state 文件、版本+1、触发监听、updatedBy 记录', () => {
    initSelection(dir);
    const seen: string[] = [];
    onSelectionChange((s) => seen.push(`${s.provider}:${s.modelId}@${s.version}`));
    const next = setSelection('kimi', 'kimi-k3', 'human');
    expect(next.version).toBe(1);
    expect(selectionSource()).toBe('state');
    const onDisk = JSON.parse(readFileSync(join(dir, 'llm-state.json'), 'utf8'));
    expect(onDisk.provider).toBe('kimi');
    expect(onDisk.updatedBy).toBe('human');
    expect(seen).toEqual(['kimi:kimi-k3@1']);
    const again = setSelection('deepseek', 'deepseek-v4-pro', 'agent');
    expect(again.version).toBe(2);
  });

  it('未初始化时 setSelection 抛错（防止隐式写错位置）', () => {
    expect(() => setSelection('kimi', 'kimi-k3', 'human')).toThrow(/initSelection/);
  });
});

describe('未初始化回退', () => {
  it('effectiveSelection 未初始化时走 env/default（既有单测安全网）', () => {
    expect(getSelection()).toBeNull();
    expect(effectiveSelection().provider).toBe('deepseek');
    process.env.LLM_PROVIDER = 'kimi';
    expect(effectiveSelection().provider).toBe('kimi');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/selection.test.ts`
Expected: FAIL — `Cannot find module './selection.js'`

- [ ] **Step 3: Write implementation**

```ts
// agent-ts/src/services/llm/selection.ts
/**
 * 当前 LLM 选择（provider + modelId）——持久化与优先级链。
 *
 * 优先级：state 文件（.pi-invest/llm-state.json） > LLM_PROVIDER env > catalog 默认。
 *
 * 显式初始化：启动引导必须调用 initSelection(piDir)；未初始化时
 * effectiveSelection() 回退 env/default —— 保证既有单测不读真实 state 文件。
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import type { LLMProviderName, LLMSelection, SelectionSource } from './types.js';
import { envModelId, resolveProvider } from './catalog.js';

export const STATE_FILE_NAME = 'llm-state.json';

interface SelectionState {
  piDir: string;
  selection: LLMSelection;
  source: SelectionSource;
  listeners: Array<(s: LLMSelection) => void>;
}

let state: SelectionState | null = null;

function envSelection(env = process.env): { selection: LLMSelection; source: SelectionSource } {
  const raw = (env.LLM_PROVIDER || '').toLowerCase();
  let provider: LLMProviderName = 'deepseek';
  let source: SelectionSource = 'default';
  if (raw) {
    const alias = resolveProvider(raw);
    if (alias) {
      provider = alias;
      source = 'env';
      if (alias !== raw) console.warn(`[llm] LLM_PROVIDER="${raw}" 按别名解析为 ${alias}`);
    } else {
      console.warn(`[llm] 未知 LLM_PROVIDER="${raw}"，回退 deepseek`);
    }
  }
  return {
    selection: {
      provider,
      modelId: envModelId(provider, env),
      updatedBy: source === 'env' ? 'env' : 'default',
      updatedAt: new Date(0).toISOString(),
      version: 0,
    },
    source,
  };
}

function readStateFile(piDir: string): LLMSelection | null {
  const file = join(piDir, STATE_FILE_NAME);
  try {
    if (!existsSync(file)) return null;
    const parsed = JSON.parse(readFileSync(file, 'utf8'));
    const provider = typeof parsed?.provider === 'string' ? resolveProvider(parsed.provider) : null;
    if (!provider || typeof parsed?.modelId !== 'string') {
      console.warn(`[llm] ${STATE_FILE_NAME} 内容非法，回退 env/default`);
      return null;
    }
    return {
      provider,
      modelId: parsed.modelId,
      updatedBy: parsed.updatedBy === 'agent' ? 'agent' : 'human',
      updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : new Date().toISOString(),
      version: Number(parsed.version) || 1,
    };
  } catch (e) {
    console.warn(`[llm] ${STATE_FILE_NAME} 读取失败（回退 env/default）:`, (e as Error).message);
    return null;
  }
}

export function initSelection(piDir: string, env = process.env): LLMSelection {
  const fromFile = readStateFile(piDir);
  const base = envSelection(env);
  state = {
    piDir,
    selection: fromFile ?? base.selection,
    source: fromFile ? 'state' : base.source,
    listeners: [],
  };
  return state.selection;
}

export function isSelectionInitialized(): boolean {
  return state !== null;
}

/** 已初始化时返回当前选择；未初始化返回 null */
export function getSelection(): LLMSelection | null {
  return state?.selection ?? null;
}

/** 当前生效选择（未初始化时回退 env/default） */
export function effectiveSelection(env = process.env): LLMSelection {
  return state?.selection ?? envSelection(env).selection;
}

export function selectionSource(env = process.env): SelectionSource {
  return state?.source ?? envSelection(env).source;
}

export function setSelection(
  provider: LLMProviderName,
  modelId: string,
  updatedBy: 'human' | 'agent',
): LLMSelection {
  if (!state) throw new Error('selection 未初始化：先调用 initSelection(piDir)');
  const next: LLMSelection = {
    provider,
    modelId,
    updatedBy,
    updatedAt: new Date().toISOString(),
    version: state.selection.version + 1,
  };
  state.selection = next;
  state.source = 'state';
  mkdirSync(state.piDir, { recursive: true });
  writeFileSync(join(state.piDir, STATE_FILE_NAME), JSON.stringify(next, null, 2) + '\n');
  for (const cb of state.listeners) cb(next);
  return next;
}

export function onSelectionChange(cb: (s: LLMSelection) => void): void {
  if (!state) throw new Error('selection 未初始化：先调用 initSelection(piDir)');
  state.listeners.push(cb);
}

/** 仅测试使用 */
export function resetSelectionForTests(): void {
  state = null;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/selection.test.ts`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/services/llm/selection.ts agent-ts/src/services/llm/selection.test.ts
git commit -m "feat(llm): selection.ts——state文件持久化+优先级链(state>env>默认)+版本号"
```

---

### Task 4: switch-service.ts —— 统一切换入口

**Files:**
- Create: `agent-ts/src/services/llm/switch-service.ts`
- Test: `agent-ts/src/services/llm/switch-service.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// agent-ts/src/services/llm/switch-service.test.ts
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdtempSync, readFileSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { initSelection, resetSelectionForTests } from './selection.js';
import { resolveSwitchTarget, switchLLM } from './switch-service.js';

const ENV_KEYS = ['LLM_PROVIDER', 'LLM_API_KEY', 'DEEPSEEK_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY', 'DEEPSEEK_MODEL_ID', 'KIMI_MODEL_ID', 'MODEL_ID'];
let dir: string;
let saved: Record<string, string | undefined>;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'llm-sw-'));
  saved = {};
  for (const k of ENV_KEYS) { saved[k] = process.env[k]; delete process.env[k]; }
  resetSelectionForTests();
  initSelection(dir);
});
afterEach(() => {
  for (const k of ENV_KEYS) {
    if (saved[k] === undefined) delete process.env[k]; else process.env[k] = saved[k];
  }
  resetSelectionForTests();
  rmSync(dir, { recursive: true, force: true });
});

describe('resolveSwitchTarget', () => {
  it('模型别名 / provider 名（provider 用 env 链解析模型）', () => {
    expect(resolveSwitchTarget('pro')).toEqual({ provider: 'deepseek', modelId: 'deepseek-v4-pro' });
    expect(resolveSwitchTarget('kimi')).toEqual({ provider: 'kimi', modelId: 'kimi-k3' });
    process.env.KIMI_MODEL_ID = 'kimi-k3-0905';
    expect(resolveSwitchTarget('kimi')).toEqual({ provider: 'kimi', modelId: 'kimi-k3-0905' });
    expect(resolveSwitchTarget('gpt-5')).toBeNull();
  });
});

describe('switchLLM', () => {
  it('未知目标 → ok:false，报可选值', () => {
    const r = switchLLM('gpt-5', 'human', { piDir: dir });
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/未知目标/);
  });

  it('相同目标 → ok:true changed:false', () => {
    const r = switchLLM('deepseek', 'human', { piDir: dir });
    expect(r).toMatchObject({ ok: true, changed: false });
  });

  it('目标 key 未配置 → 拒绝并指出缺哪个变量', () => {
    const r = switchLLM('kimi', 'human', { piDir: dir });
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/KIMI_API_KEY/);
  });

  it('成功切换：持久化 state 文件 + 审计日志追加', () => {
    process.env.KIMI_API_KEY = 'k';
    const r = switchLLM('kimi', 'human', { piDir: dir });
    expect(r).toMatchObject({ ok: true, changed: true, from: 'deepseek:deepseek-v4-flash', to: 'kimi:kimi-k3' });
    const state = JSON.parse(readFileSync(join(dir, 'llm-state.json'), 'utf8'));
    expect(state.provider).toBe('kimi');
    const log = readFileSync(join(dir, 'model-switch.log'), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
    expect(log).toHaveLength(1);
    expect(log[0]).toMatchObject({ from: 'deepseek:deepseek-v4-flash', to: 'kimi:kimi-k3', trigger: 'human' });
    expect(typeof log[0].ts).toBe('string');
  });

  it('模型档位切换（pro）也走同一入口', () => {
    process.env.DEEPSEEK_API_KEY = 'k';
    const r = switchLLM('pro', 'agent', { piDir: dir });
    expect(r).toMatchObject({ ok: true, changed: true, to: 'deepseek:deepseek-v4-pro' });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/switch-service.test.ts`
Expected: FAIL — `Cannot find module './switch-service.js'`

- [ ] **Step 3: Write implementation**

```ts
// agent-ts/src/services/llm/switch-service.ts
/**
 * 统一切换服务 —— /provider 命令与 model_switch 工具的唯一入口。
 * resolve → validate(key 已配置) → 持久化 → 审计日志。
 * （agent 侧 1 小时 3 次限流保留在 model_switch 工具层，不属于本服务。）
 */
import { appendFileSync, mkdirSync } from 'fs';
import { join } from 'path';
import type { LLMProviderName, SwitchResult } from './types.js';
import {
  envModelId,
  isProviderConfigured,
  PROVIDER_NAMES,
  resolveModelTarget,
  resolveProvider,
} from './catalog.js';
import { effectiveSelection, setSelection } from './selection.js';

export interface SwitchDeps {
  piDir: string;
  env?: NodeJS.ProcessEnv;
}

const MODEL_HINTS = ['flash', 'pro', 'deepseek-v4-flash', 'deepseek-v4-pro', 'kimi-k3'];

/** 解析切换目标：模型别名/完整模型 ID 优先，其次 provider 名（模型走 env 链） */
export function resolveSwitchTarget(
  input: string,
  env = process.env,
): { provider: LLMProviderName; modelId: string } | null {
  const modelTarget = resolveModelTarget(input);
  if (modelTarget) return modelTarget;
  const provider = resolveProvider(input);
  if (provider) return { provider, modelId: envModelId(provider, env) };
  return null;
}

export function switchLLM(
  input: string,
  by: 'human' | 'agent',
  deps: SwitchDeps,
): SwitchResult {
  const current = effectiveSelection(deps.env);
  const from = `${current.provider}:${current.modelId}`;

  const target = resolveSwitchTarget(input, deps.env);
  if (!target) {
    return {
      ok: false, changed: false, from, to: from,
      error: `未知目标 "${input}"，可选：${[...PROVIDER_NAMES, ...MODEL_HINTS].join(', ')}`,
    };
  }
  const to = `${target.provider}:${target.modelId}`;

  if (target.provider === current.provider && target.modelId === current.modelId) {
    return { ok: true, changed: false, from, to };
  }
  if (!isProviderConfigured(target.provider, deps.env)) {
    return {
      ok: false, changed: false, from, to,
      error: `${target.provider} 的 API key 未配置（检查 .env 的 ${target.provider.toUpperCase()}_API_KEY）`,
    };
  }

  const sel = setSelection(target.provider, target.modelId, by);
  appendSwitchLog(deps.piDir, { ts: sel.updatedAt, from, to, trigger: by });
  console.log(`[model-switch] ${sel.updatedAt} ${from} → ${to} (${by})`);
  return { ok: true, changed: true, from, to };
}

/** 审计日志：JSON 行追加到 .pi-invest/model-switch.log（格式与历史一致） */
function appendSwitchLog(
  piDir: string,
  entry: { ts: string; from: string; to: string; trigger: 'human' | 'agent' },
): void {
  try {
    mkdirSync(piDir, { recursive: true });
    appendFileSync(join(piDir, 'model-switch.log'), JSON.stringify(entry) + '\n');
  } catch {
    // 日志写失败不影响切换
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/switch-service.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/services/llm/switch-service.ts agent-ts/src/services/llm/switch-service.test.ts
git commit -m "feat(llm): switch-service.ts——统一切换入口(resolve/validate/持久化/审计)"
```

---

### Task 5: client.ts —— 自有 LLM 客户端 complete()

依赖注入 `fetchImpl`/`sleep`，测试不打全局 fetch、不被 3s 重试拖慢。

**Files:**
- Create: `agent-ts/src/services/llm/client.ts`
- Test: `agent-ts/src/services/llm/client.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// agent-ts/src/services/llm/client.test.ts
import { describe, it, expect } from '@jest/globals';
import { complete } from './client.js';
import { LLMError, type LLMModelConfig } from './types.js';

const baseConfig: LLMModelConfig = {
  provider: 'deepseek',
  modelId: 'deepseek-v4-flash',
  displayName: 'DeepSeek Chat',
  baseUrl: 'https://api.deepseek.com/v1',
  apiKey: 'test-key',
  contextWindow: 128000,
  maxTokens: 8000,
  reasoning: true,
  timeoutMs: 120000,
  maxRetries: 2,
};

const noSleep = () => Promise.resolve();
const req = { messages: [{ role: 'user' as const, content: 'hi' }] };

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

describe('complete', () => {
  it('成功：映射 text/usage/model，请求体符合 OpenAI 格式', async () => {
    let captured: { url: string; init: RequestInit } | null = null;
    const fetchImpl = async (url: any, init: any) => {
      captured = { url: String(url), init };
      return jsonResponse(200, {
        model: 'deepseek-v4-flash',
        choices: [{ message: { role: 'assistant', content: '你好' } }],
        usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
      });
    };
    const r = await complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep });
    expect(r.text).toBe('你好');
    expect(r.usage).toEqual({ input: 10, output: 5, totalTokens: 15 });
    expect(r.model).toBe('deepseek-v4-flash');
    expect(captured!.url).toBe('https://api.deepseek.com/v1/chat/completions');
    const body = JSON.parse(String(captured!.init.body));
    expect(body.model).toBe('deepseek-v4-flash');
    expect(body.messages).toEqual([{ role: 'user', content: 'hi' }]);
    expect((captured!.init.headers as any).Authorization).toBe('Bearer test-key');
  });

  it('401 → LLMError auth 不可重试（fetch 只调一次）', async () => {
    let calls = 0;
    const fetchImpl = async () => { calls++; return jsonResponse(401, { error: 'bad key' }); };
    await expect(complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep }))
      .rejects.toMatchObject({ kind: 'auth', retryable: false });
    expect(calls).toBe(1);
  });

  it('429 overloaded → kind=overloaded，重试后成功', async () => {
    let calls = 0;
    const fetchImpl = async () => {
      calls++;
      if (calls === 1) return new Response('429 The engine is currently overloaded', { status: 429 });
      return jsonResponse(200, { choices: [{ message: { content: 'ok' } }], usage: {} });
    };
    const r = await complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep });
    expect(r.text).toBe('ok');
    expect(calls).toBe(2);
  });

  it('500 持续失败 → 重试 5 次后抛 overloaded', async () => {
    let calls = 0;
    const fetchImpl = async () => { calls++; return jsonResponse(500, 'server error'); };
    await expect(complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep }))
      .rejects.toMatchObject({ kind: 'overloaded', retryable: true });
    expect(calls).toBe(6); // 1 + 5 retries
  });

  it('fetch 抛 AbortError → kind=timeout 可重试', async () => {
    const fetchImpl = async () => { throw new DOMException('aborted', 'AbortError'); };
    await expect(complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep }))
      .rejects.toMatchObject({ kind: 'timeout', retryable: true });
  });

  it('400 → invalid_request 不重试', async () => {
    let calls = 0;
    const fetchImpl = async () => { calls++; return jsonResponse(400, 'bad request'); };
    await expect(complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep }))
      .rejects.toBeInstanceOf(LLMError);
    expect(calls).toBe(1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/client.test.ts`
Expected: FAIL — `Cannot find module './client.js'`

- [ ] **Step 3: Write implementation**

```ts
// agent-ts/src/services/llm/client.ts
/**
 * 自有 LLM 客户端：complete() 直走 OpenAI 兼容 HTTP。
 * 错误归一化为 LLMError，调用方不感知 provider/SDK 特有错误。
 * 重试策略沿用 .pi/settings.json：最多 5 次重试，间隔 3s（仅 retryable 错误）。
 */
import { LLMError, type ChatRequest, type ChatResponse, type LLMModelConfig } from './types.js';

const MAX_RETRIES = 5;
const RETRY_DELAY_MS = 3000;

export interface ClientDeps {
  fetchImpl?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
}

export async function complete(
  config: LLMModelConfig,
  req: ChatRequest,
  deps: ClientDeps = {},
): Promise<ChatResponse> {
  const sleep = deps.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
  let lastErr: LLMError | null = null;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await completeOnce(config, req, deps.fetchImpl ?? fetch);
    } catch (e) {
      const err = e instanceof LLMError ? e : new LLMError(String(e), 'unknown', false);
      if (!err.retryable || attempt === MAX_RETRIES) throw err;
      lastErr = err;
      await sleep(RETRY_DELAY_MS);
    }
  }
  throw lastErr ?? new LLMError('unreachable', 'unknown', false);
}

async function completeOnce(
  config: LLMModelConfig,
  req: ChatRequest,
  fetchImpl: typeof fetch,
): Promise<ChatResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), config.timeoutMs);
  try {
    const res = await fetchImpl(`${config.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${config.apiKey}`,
      },
      body: JSON.stringify({
        model: config.modelId,
        messages: req.messages,
        max_tokens: req.maxTokens ?? config.maxTokens,
        ...(req.temperature !== undefined ? { temperature: req.temperature } : {}),
        stream: false,
      }),
      signal: controller.signal,
    });
    if (!res.ok) throw await toLLMError(res);
    const data = (await res.json()) as any;
    const message = data.choices?.[0]?.message ?? {};
    const usage = data.usage ?? {};
    return {
      text: typeof message.content === 'string' ? message.content : '',
      model: data.model ?? config.modelId,
      usage: {
        input: usage.prompt_tokens ?? 0,
        output: usage.completion_tokens ?? 0,
        totalTokens: usage.total_tokens ?? 0,
      },
    };
  } catch (e) {
    if (e instanceof LLMError) throw e;
    if ((e as Error).name === 'AbortError') {
      throw new LLMError(`请求超时（${config.timeoutMs}ms）`, 'timeout', true);
    }
    throw new LLMError(`网络错误: ${(e as Error).message}`, 'unknown', true);
  } finally {
    clearTimeout(timer);
  }
}

async function toLLMError(res: Response): Promise<LLMError> {
  const body = await res.text().catch(() => '');
  if (res.status === 401 || res.status === 403) {
    return new LLMError(`认证失败 (${res.status}): ${body}`, 'auth', false);
  }
  if (res.status === 429) {
    const overloaded = /overloaded/i.test(body);
    return new LLMError(
      `限流/过载 (429): ${body}`,
      overloaded ? 'overloaded' : 'rate_limit',
      true,
    );
  }
  if (res.status === 400) return new LLMError(`请求无效 (400): ${body}`, 'invalid_request', false);
  if (res.status >= 500) return new LLMError(`服务端错误 (${res.status}): ${body}`, 'overloaded', true);
  return new LLMError(`HTTP ${res.status}: ${body}`, 'unknown', false);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/client.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/services/llm/client.ts agent-ts/src/services/llm/client.test.ts
git commit -m "feat(llm): client.ts——complete()自有客户端+LLMError归一化+5次/3s重试"
```

---

### Task 6: adapters/pi-ai.ts —— SDK 适配（唯一允许 import pi-ai 的文件）

**Files:**
- Create: `agent-ts/src/services/llm/adapters/pi-ai.ts`
- Test: `agent-ts/src/services/llm/adapters/pi-ai.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// agent-ts/src/services/llm/adapters/pi-ai.test.ts
import { describe, it, expect, afterEach } from '@jest/globals';
import type { LLMModelConfig } from '../types.js';
import { toSDKModel } from './pi-ai.js';

const kimiConfig: LLMModelConfig = {
  provider: 'kimi',
  modelId: 'kimi-k3',
  displayName: 'Kimi (Moonshot)',
  baseUrl: 'https://api.kimi.com/coding/v1',
  apiKey: 'kimi-key',
  contextWindow: 256000,
  maxTokens: 8000,
  reasoning: true,
  compat: { supportsDeveloperRole: false, supportsStore: false, maxTokensField: 'max_tokens' },
  timeoutMs: 120000,
  maxRetries: 2,
};

const dsConfig: LLMModelConfig = {
  provider: 'deepseek',
  modelId: 'deepseek-v4-flash',
  displayName: 'DeepSeek Chat',
  baseUrl: 'https://api.deepseek.com/v1',
  apiKey: 'ds-key',
  contextWindow: 128000,
  maxTokens: 8000,
  reasoning: true,
  timeoutMs: 120000,
  maxRetries: 2,
};

const savedOpenAIKey = process.env.OPENAI_API_KEY;
afterEach(() => {
  if (savedOpenAIKey === undefined) delete process.env.OPENAI_API_KEY;
  else process.env.OPENAI_API_KEY = savedOpenAIKey;
});

describe('toSDKModel', () => {
  it('kimi compat 透传锁死（两次 tokenization failed 事故回归）', () => {
    const m = toSDKModel(kimiConfig) as any;
    expect(m.id).toBe('kimi-k3');
    expect(m.baseUrl).toBe('https://api.kimi.com/coding/v1');
    expect(m.compat).toEqual({ supportsDeveloperRole: false, supportsStore: false, maxTokensField: 'max_tokens' });
  });

  it('deepseek 无 compat 覆盖（依赖 SDK 自动检测）', () => {
    const m = toSDKModel(dsConfig) as any;
    expect(m.compat).toBeUndefined();
    expect(m.provider).toBe('openai');
    expect(m.api).toBe('openai-completions');
  });

  it('副作用：同步 OPENAI_API_KEY 为当前 provider 的 key（SDK 只认该变量）', () => {
    toSDKModel(kimiConfig);
    expect(process.env.OPENAI_API_KEY).toBe('kimi-key');
    toSDKModel(dsConfig);
    expect(process.env.OPENAI_API_KEY).toBe('ds-key');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/adapters/pi-ai.test.ts`
Expected: FAIL — `Cannot find module './pi-ai.js'`

- [ ] **Step 3: Write implementation**

```ts
// agent-ts/src/services/llm/adapters/pi-ai.ts
/**
 * pi-ai SDK 适配器 —— llm 模块内唯一允许 import pi-ai 的文件。
 * 全部 SDK 怪癖封装在此：
 * 1) SDK 不读 model.apiKey，openai provider 的 key 只从 OPENAI_API_KEY
 *    环境变量解析 → 这里把当前 provider 的 key 同步过去（否则切 provider
 *    后带着旧 key 请求新端点，401 Invalid Authentication）。
 * 2) kimi compat（supportsDeveloperRole=false 等）透传——两次事故教训。
 */
import type { Model } from '@mariozechner/pi-ai';
import type { LLMModelConfig } from '../types.js';

export function toSDKModel(config: LLMModelConfig): Model<'openai-completions'> {
  if (config.apiKey) {
    process.env.OPENAI_API_KEY = config.apiKey;
  }
  return {
    id: config.modelId,
    name: config.displayName,
    api: 'openai-completions',
    provider: 'openai',
    apiKey: config.apiKey,
    baseUrl: config.baseUrl,
    reasoning: config.reasoning,
    input: ['text'],
    cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
    ...(config.compat ? { compat: config.compat } : {}),
    contextWindow: config.contextWindow,
    maxTokens: config.maxTokens,
    timeout: config.timeoutMs,
    maxRetries: config.maxRetries,
  } as any;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/adapters/pi-ai.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/services/llm/adapters/pi-ai.ts agent-ts/src/services/llm/adapters/pi-ai.test.ts
git commit -m "feat(llm): adapters/pi-ai.ts——SDK适配封装(OPENAI_API_KEY同步+compat透传)"
```

---

### Task 7: port.ts + index.ts —— LLMPort 组合根 + 启动初始化

**Files:**
- Create: `agent-ts/src/services/llm/port.ts`
- Create: `agent-ts/src/services/llm/index.ts`
- Test: `agent-ts/src/services/llm/index.test.ts`
- Modify: `agent-ts/src/index.ts`（启动引导处加 `initLLM`，具体位置见 Step 4 说明）
- Modify: `agent-ts/src/api/index.ts`（同上）

- [ ] **Step 1: Write the failing test**

```ts
// agent-ts/src/services/llm/index.test.ts
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdtempSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { getLLM, initLLM, resetLLMForTests } from './index.js';

const ENV_KEYS = ['LLM_PROVIDER', 'LLM_API_KEY', 'DEEPSEEK_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY', 'MODEL_ID', 'DEEPSEEK_MODEL_ID', 'KIMI_MODEL_ID'];
let dir: string;
let saved: Record<string, string | undefined>;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'llm-port-'));
  saved = {};
  for (const k of ENV_KEYS) { saved[k] = process.env[k]; delete process.env[k]; }
  resetLLMForTests();
});
afterEach(() => {
  for (const k of ENV_KEYS) {
    if (saved[k] === undefined) delete process.env[k]; else process.env[k] = saved[k];
  }
  resetLLMForTests();
  rmSync(dir, { recursive: true, force: true });
});

describe('LLMPort', () => {
  it('initLLM 后 current() 返回默认选择，source=default', () => {
    initLLM(dir);
    const llm = getLLM();
    expect(llm.current()).toMatchObject({ provider: 'deepseek', modelId: 'deepseek-v4-flash' });
    expect(llm.source()).toBe('default');
  });

  it('switch 成功 → current/getSessionModel/status 全部反映新选择，onChange 触发', () => {
    process.env.KIMI_API_KEY = 'k';
    const llm = initLLM(dir);
    const seen: string[] = [];
    llm.onChange((s) => seen.push(s.modelId));
    const r = llm.switch('kimi', 'human');
    expect(r.ok).toBe(true);
    expect(llm.current().provider).toBe('kimi');
    expect((llm.getSessionModel() as any).id).toBe('kimi-k3');
    const st = llm.status();
    expect(st.source).toBe('state');
    expect(st.providers.find((p) => p.name === 'kimi')).toMatchObject({ configured: true, active: true });
    expect(st.providers.find((p) => p.name === 'deepseek')).toMatchObject({ active: false });
    expect(seen).toEqual(['kimi-k3']);
  });

  it('switch 失败（key 未配置）→ 选择不变', () => {
    const llm = initLLM(dir);
    const r = llm.switch('kimi', 'agent');
    expect(r.ok).toBe(false);
    expect(llm.current().provider).toBe('deepseek');
  });

  it('getModelConfig 返回自有类型（含 kimi compat）', () => {
    process.env.LLM_PROVIDER = 'kimi';
    process.env.KIMI_API_KEY = 'k';
    const llm = initLLM(dir);
    const c = llm.getModelConfig();
    expect(c.provider).toBe('kimi');
    expect(c.compat?.supportsDeveloperRole).toBe(false);
  });

  it('未 initLLM 时 getLLM() 惰性可用（env/default 回退，兼容旧调用方）', () => {
    process.env.LLM_PROVIDER = 'kimi';
    process.env.KIMI_API_KEY = 'k';
    const llm = getLLM();
    expect(llm.current().provider).toBe('kimi');
    expect(() => llm.switch('deepseek', 'human')).toThrow(/initSelection/);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/index.test.ts`
Expected: FAIL — `Cannot find module './index.js'`

- [ ] **Step 3: Write implementation**

```ts
// agent-ts/src/services/llm/port.ts
/**
 * LLMPort —— agent 世界依赖的唯一抽象。
 * 依赖规则：agent loop / session-factory / 工具 / 命令 只允许 import
 * 本文件与 types.ts；禁止 import adapters/pi-ai.ts。
 */
import type {
  ChatRequest,
  ChatResponse,
  LLMModelConfig,
  LLMSelection,
  LLMStatus,
  SelectionSource,
  SwitchResult,
} from './types.js';

export interface LLMPort {
  /** 当前选择（含版本号） */
  current(): LLMSelection;
  /** 当前选择来源：state / env / default */
  source(): SelectionSource;
  /** 自有模型配置（可不透明传递） */
  getModelConfig(): LLMModelConfig;
  /** 给 SDK 会话的模型句柄（内部经 adapter，调用方不理解其结构） */
  getSessionModel(): unknown;
  /** 一次性 LLM 调用（plan agents 等直接调用方使用） */
  complete(req: ChatRequest): Promise<ChatResponse>;
  /** 统一切换入口（/provider 与 model_switch 共用） */
  switch(target: string, by: 'human' | 'agent'): SwitchResult;
  /** 各 provider 配置状态 + 当前选择 */
  status(): LLMStatus;
  /** 选择变化监听（惰性生效钩子） */
  onChange(cb: (s: LLMSelection) => void): void;
}
```

```ts
// agent-ts/src/services/llm/index.ts
/**
 * llm 模块组合根。
 * 启动引导调用 initLLM(piDir)；旧调用方可直接用 getLLM()（惰性单例，
 * 未初始化时 selection 回退 env/default，保证向后兼容）。
 */
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { buildModelConfig, envModelId, isProviderConfigured, PROVIDER_NAMES } from './catalog.js';
import { complete as clientComplete } from './client.js';
import { toSDKModel } from './adapters/pi-ai.js';
import type { LLMPort } from './port.js';
import {
  effectiveSelection,
  initSelection,
  isSelectionInitialized,
  onSelectionChange,
  resetSelectionForTests,
  selectionSource,
} from './selection.js';
import { switchLLM } from './switch-service.js';
import type { ChatRequest, ChatResponse, LLMModelConfig, LLMStatus, SwitchResult } from './types.js';

const __filename = fileURLToPath(import.meta.url);
const AGENT_ROOT = join(dirname(__filename), '../../..');
const DEFAULT_PI_DIR = join(AGENT_ROOT, '.pi-invest');

let port: (LLMPort & { _piDir: string }) | null = null;

export function initLLM(piDir: string = DEFAULT_PI_DIR): LLMPort {
  initSelection(piDir);
  port = createPort(piDir);
  return port;
}

export function getLLM(): LLMPort {
  if (!port) port = createPort(DEFAULT_PI_DIR);
  return port;
}

/** 仅测试使用 */
export function resetLLMForTests(): void {
  port = null;
  resetSelectionForTests();
}

function createPort(piDir: string): LLMPort & { _piDir: string } {
  const config = (): LLMModelConfig => {
    const sel = effectiveSelection();
    return buildModelConfig(sel.provider, sel.modelId);
  };
  return {
    _piDir: piDir,
    current: () => effectiveSelection(),
    source: () => selectionSource(),
    getModelConfig: config,
    getSessionModel: () => toSDKModel(config()),
    complete: (req: ChatRequest): Promise<ChatResponse> => clientComplete(config(), req),
    switch: (target, by): SwitchResult => switchLLM(target, by, { piDir }),
    status: (): LLMStatus => {
      const sel = effectiveSelection();
      return {
        current: sel,
        source: selectionSource(),
        providers: PROVIDER_NAMES.map((name) => ({
          name,
          configured: isProviderConfigured(name),
          active: name === sel.provider,
          modelId: name === sel.provider ? sel.modelId : envModelId(name),
        })),
      };
    },
    onChange: (cb) => onSelectionChange(cb),
  };
}

/** switch 需要已初始化的 selection；未初始化时给出明确错误 */
export function requireInitialized(): void {
  if (!isSelectionInitialized()) {
    throw new Error('llm 模块未初始化：启动引导请先调用 initLLM(piDir)');
  }
}
```

注意：`switch()` 在 selection 未初始化时会由 `setSelection` 抛出 `initSelection` 错误——这是预期行为（测试已锁定）。

- [ ] **Step 4: 启动引导接线**

在 `agent-ts/src/index.ts` 与 `agent-ts/src/api/index.ts` 的启动序列中（env 加载完成之后、任何 session 创建之前）各加：

```ts
import { initLLM } from './services/llm/index.js'; // api/index.ts 用 '../services/llm/index.js'
import { paths } from './config/config.js';        // 若已 import 则复用

initLLM(paths.piDir);
```

先读这两个文件找到既有初始化调用点（如 `initBaseOnce` / dotenv 加载处），把 `initLLM(paths.piDir)` 放在其后。

- [ ] **Step 5: Run tests**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/index.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add agent-ts/src/services/llm/port.ts agent-ts/src/services/llm/index.ts agent-ts/src/services/llm/index.test.ts agent-ts/src/index.ts agent-ts/src/api/index.ts
git commit -m "feat(llm): LLMPort端口+组合根index.ts+启动初始化接线"
```

---

### Task 8: config.ts 薄代理化（回归关键任务）

把 `config.ts` 的 LLM 部分改为转发 llm 模块的薄代理；`PROVIDER_PRESETS`/别名表/`MODEL_TARGETS` 删除（已迁入 catalog），保留 re-export 兼容。**既有 `config.test.ts` / `model-switcher.test.ts` 不许改、必须全绿。**

**Files:**
- Modify: `agent-ts/src/config/config.ts`

- [ ] **Step 1: 先跑基线**

Run: `cd agent-ts && npm test -- --runTestsByPath src/config/config.test.ts src/config/model-switcher.test.ts`
Expected: 全 PASS（记录基线）

- [ ] **Step 2: 改写 config.ts 的 LLM 段**

删除 `ProviderPreset`/`PROVIDER_PRESETS`/`PROVIDER_ALIASES`/`MODEL_TARGETS` 定义与 `createModel` 旧实现，替换为：

```ts
/**
 * LLM Provider 配置 —— 薄代理，转发到 services/llm 模块。
 * @deprecated 新代码直接用 services/llm 的 getLLM()；此处仅为向后兼容保留。
 *
 * 生效链（生产）：model-switcher 运行时 override（遗留/单测）
 *   > llm-state.json（state） > LLM_PROVIDER env > catalog 默认。
 */
import type { Model } from '@mariozechner/pi-ai';
import { getLLM } from '../services/llm/index.js';
import { envModelId, resolveModelTarget as catalogResolveModelTarget } from '../services/llm/catalog.js';
import type { LLMProviderName } from '../services/llm/types.js';
import { getRuntimeOverride, getRuntimeModelOverride } from './model-switcher.js';

export type { LLMProviderName };

export function getActiveProvider(): LLMProviderName {
  return getRuntimeOverride() ?? getLLM().current().provider;
}

export function getActiveApiKey(): string {
  return getLLM().getModelConfig().apiKey;
}

export function getActiveModelId(): string {
  const provider = getActiveProvider();
  const runtimeModel = getRuntimeModelOverride();
  if (runtimeModel && runtimeModel.provider === provider) return runtimeModel.modelId;
  const sel = getLLM().current();
  if (sel.provider === provider) return sel.modelId;
  return envModelId(provider);
}

export function resolveModelTarget(input: string) {
  return catalogResolveModelTarget(input);
}

export function createModel(): Model<'openai-completions'> {
  // 遗留运行时 override（单测/旧路径）优先；生产走 llm 模块当前选择
  const override = getRuntimeOverride();
  const runtimeModel = getRuntimeModelOverride();
  if (override) {
    const modelId = runtimeModel && runtimeModel.provider === override
      ? runtimeModel.modelId
      : envModelId(override);
    // 经 adapter 构造，保持 SDK 副作用（OPENAI_API_KEY 同步）一致
    const { buildModelConfig } = require('../services/llm/catalog.js');
    const { toSDKModel } = require('../services/llm/adapters/pi-ai.js');
    return toSDKModel(buildModelConfig(override, modelId));
  }
  return getLLM().getSessionModel() as Model<'openai-completions'>;
}
```

注意：本项目为 ESM，不能用 `require`——把上面 `createModel` 改为顶部静态 import `buildModelConfig` 与 `toSDKModel`：

```ts
import { buildModelConfig, envModelId, resolveModelTarget as catalogResolveModelTarget } from '../services/llm/catalog.js';
import { toSDKModel } from '../services/llm/adapters/pi-ai.js';

export function createModel(): Model<'openai-completions'> {
  const override = getRuntimeOverride();
  if (override) {
    const runtimeModel = getRuntimeModelOverride();
    const modelId = runtimeModel && runtimeModel.provider === override
      ? runtimeModel.modelId
      : envModelId(override);
    return toSDKModel(buildModelConfig(override, modelId));
  }
  return getLLM().getSessionModel() as Model<'openai-completions'>;
}
```

`config.ts` 其余部分（paths/compactionConfig/bootstrap 等）不动。

- [ ] **Step 3: 跑回归**

Run: `cd agent-ts && npm test -- --runTestsByPath src/config/config.test.ts src/config/model-switcher.test.ts`
Expected: 全 PASS（与基线一致）。若有失败：对照失败用例检查代理链（runtime override 优先于 selection；未初始化 selection 回退 env），修代理不改测试。

- [ ] **Step 4: 全量测试确认无其他破坏**

Run: `cd agent-ts && npm test`
Expected: 与既有基线一致（仓库存在预存在失败清单，见 memory；只允许预存在的失败，不许新增）。

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/config/config.ts
git commit -m "refactor(llm): config.ts LLM段薄代理化——转发services/llm，回归测试全绿"
```

---

### Task 9: 三处 session 创建点改走 LLMPort

**Files:**
- Modify: `agent-ts/src/core/agent/agent-loop.ts:198`（`model: createModel()`）
- Modify: `agent-ts/src/core/agent/background-agent-loop.ts:53`
- Modify: `agent-ts/src/api/gateway/session-factory.ts:82`

- [ ] **Step 1: 逐文件替换**

三处都做相同改动。以 agent-loop.ts 为例：

```ts
// 旧
import { createModel, paths } from "../../config/config.js";
//   ...
model: createModel(),

// 新
import { paths } from "../../config/config.js";
import { getLLM } from "../../services/llm/index.js";
//   ...
model: getLLM().getSessionModel() as any,
```

session-factory.ts 与 background-agent-loop.ts 同理（相对路径分别为 `../../services/llm/index.js` 与 `../../services/llm/index.js`，以实际目录深度为准）。

- [ ] **Step 2: 编译检查**

Run: `cd agent-ts && npx tsc -p tsconfig.build.json --noEmit`
Expected: 无 error（config.ts 仍 export createModel，其他未迁移调用方不受影响）

- [ ] **Step 3: 全量测试**

Run: `cd agent-ts && npm test`
Expected: 无新增失败

- [ ] **Step 4: Commit**

```bash
git add agent-ts/src/core/agent/agent-loop.ts agent-ts/src/core/agent/background-agent-loop.ts agent-ts/src/api/gateway/session-factory.ts
git commit -m "refactor(llm): 三处session创建点改走LLMPort.getSessionModel()"
```

---

### Task 10: plan 三杰改走 llm.complete()

`plan-agent.ts` / `clarify-agent.ts` / `reflect-agent.ts` 目前是 `completeSimple(createModel(), {systemPrompt, messages})`，直接 import pi-ai——改为 LLMPort 的 `complete()`（自有类型）。

**Files:**
- Modify: `agent-ts/src/services/plan/plan-agent.ts:139-145`
- Modify: `agent-ts/src/services/plan/clarify-agent.ts`（同构调用点）
- Modify: `agent-ts/src/services/plan/reflect-agent.ts`（同构调用点）
- Test: `agent-ts/src/services/plan/plan-agent.test.ts`（新建；clarify/reflect 同构，各加一个用例可合并在各自新测试文件）

- [ ] **Step 1: Write the failing test（plan-agent）**

```ts
// agent-ts/src/services/plan/plan-agent.test.ts
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdtempSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { initLLM, resetLLMForTests } from '../llm/index.js';
import * as client from '../llm/client.js';
import { createPlanAgent } from './plan-agent.js';

let dir: string;
let savedKey: string | undefined;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'llm-plan-'));
  savedKey = process.env.DEEPSEEK_API_KEY;
  process.env.DEEPSEEK_API_KEY = 'test';
  resetLLMForTests();
  initLLM(dir);
});
afterEach(() => {
  if (savedKey === undefined) delete process.env.DEEPSEEK_API_KEY;
  else process.env.DEEPSEEK_API_KEY = savedKey;
  resetLLMForTests();
  rmSync(dir, { recursive: true, force: true });
  jest.restoreAllMocks();
});

describe('createPlanAgent', () => {
  it('经 llm.complete 调用（system+user 两条消息），返回文本', async () => {
    const spy = jest.spyOn(client, 'complete').mockResolvedValue({
      text: '1. 第一步\n2. 第二步',
      usage: { input: 1, output: 1, totalTokens: 2 },
      model: 'deepseek-v4-flash',
    });
    const plan = await createPlanAgent('测试任务');
    expect(plan).toContain('第一步');
    expect(spy).toHaveBeenCalledTimes(1);
    const req = spy.mock.calls[0][1];
    expect(req.messages[0].role).toBe('system');
    expect(req.messages[1].role).toBe('user');
    expect(req.messages[1].content).toContain('测试任务');
  });
});
```

注意：plan-agent 必须通过 port 的 `complete` 转发到 `client.complete` 才能被 spy 到——即 port 实现里 `complete: (req) => clientComplete(config(), req)` 保留对该模块函数的**具名调用**（Task 7 的实现已满足）。

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/plan/plan-agent.test.ts`
Expected: FAIL — spy 未被调用（当前实现走 completeSimple）

- [ ] **Step 3: 改写 plan-agent.ts 调用段**

```ts
// 旧
import { completeSimple } from "@mariozechner/pi-ai";
import { createModel } from "../../config/config.js";
//   ...
const result = await completeSimple(createModel(), {
  systemPrompt,
  messages: [{ role: "user", content: userPrompt, timestamp: Date.now() }],
});
const textContent = result.content.find(c => c.type === "text");
return textContent && "text" in textContent ? (textContent as any).text : "Plan Agent 未能生成有效计划";

// 新
import { getLLM } from "../llm/index.js";
//   ...
const result = await getLLM().complete({
  messages: [
    { role: "system", content: systemPrompt },
    { role: "user", content: userPrompt },
  ],
});
return result.text || "Plan Agent 未能生成有效计划";
```

`clarify-agent.ts` / `reflect-agent.ts` 做同构替换（先读文件确认调用形状，systemPrompt 进 messages[0]）。删除这两个文件顶部的 `import { completeSimple } from "@mariozechner/pi-ai"` 与 `createModel` import。

- [ ] **Step 4: Run tests**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/plan/plan-agent.test.ts && npm test -- --runTestsByPath src/services/llm/index.test.ts`
Expected: PASS

- [ ] **Step 5: 编译 + 全量测试**

Run: `cd agent-ts && npx tsc -p tsconfig.build.json --noEmit && npm test`
Expected: 编译无 error；无新增测试失败

- [ ] **Step 6: Commit**

```bash
git add agent-ts/src/services/plan/
git commit -m "refactor(llm): plan三杰改走LLMPort.complete()，移除pi-ai直接依赖"
```

---

### Task 11: /provider 与 model_switch 统一调 switch()

**Files:**
- Modify: `agent-ts/src/api/extensions/model-command.ts`
- Modify: `agent-ts/src/infrastructure/tools/agent/model-switch-tool.ts`

- [ ] **Step 1: 改写 model-command.ts handler 主体**

保留命令注册/参数解析外壳，handler 改为：

```ts
import { getLLM } from "../../../services/llm/index.js";

// handler 内：
const target = args.trim().toLowerCase();
const llm = getLLM();

if (!target) {
  const st = llm.status();
  const lines = st.providers
    .map((p) => ` ${p.active ? "→" : " "} ${p.name}: ${p.configured ? "key 已配置" : "❌ key 未配置"}${p.active ? ` (${p.modelId})` : ""}`)
    .join("\n");
  ctx.ui.notify(
    `当前: ${st.current.provider} (${st.current.modelId}) [来源: ${st.source}]\n${lines}\n切换: /provider deepseek | kimi | flash | pro`,
    "info",
  );
  return;
}

const result = llm.switch(target, "human");
if (!result.ok) {
  ctx.ui.notify(`❌ ${result.error}`, "error");
  return;
}
if (!result.changed) {
  ctx.ui.notify(`ℹ️ 已是 ${result.to}，无需切换`, "info");
  return;
}
const ok = await pi.setModel(llm.getSessionModel() as any);
if (ok) {
  ctx.ui.notify(`✅ 已切换 ${result.from} → ${result.to}，下一轮对话生效（已持久化，重启保持）`, "info");
} else {
  ctx.ui.notify(`⚠️ 已持久化切换（新会话将用 ${result.to}），但当前会话 setModel 未生效`, "warning");
}
```

删除旧的 `setRuntimeProvider`/`setRuntimeModelOverride`/`logSwitch`/`createModel`/`getActiveProvider` 等 import。

- [ ] **Step 2: 改写 model-switch-tool.ts execute 主体**

保留防抖动窗口（`WINDOW_MS`/`MAX_SWITCHES_PER_WINDOW`/`switchTimestamps`/`resetSwitchHistoryForTests`）与参数 schema，核心逻辑改为：

```ts
import { getLLM } from "../../../services/llm/index.js";

// execute 内（在 checkFlap 定义之后）：
const llm = getLLM();
const current = llm.current();

// 先判定是否为"相同目标"（不计入防抖动）：
//   llm.switch 对相同目标返回 changed:false，直接透传
// 防抖动在确认会发生真实切换前调用：
const preview = llm.switch(provider, "agent");
if (!preview.ok) {
  return fail(`❌ ${preview.error}`);
}
if (!preview.changed) {
  return {
    content: [{ type: "text" as const, text: `ℹ️ 已是 ${preview.to}，无需切换。` }],
    details: { changed: false },
  };
}
// 注意：switch 已持久化。防抖动必须在 switch 之前——因此重构为两步：
```

**修正**：`switch()` 是即时生效的，不能先调再限流。改为先解析+校验（只读），再过限流，最后执行：

```ts
import { getLLM } from "../../../services/llm/index.js";
import { resolveSwitchTarget } from "../../../services/llm/switch-service.js";
import { isProviderConfigured } from "../../../services/llm/catalog.js";

// execute 内：
const llm = getLLM();
const current = llm.current();

const target = resolveSwitchTarget(provider);
if (!target) {
  return fail(`❌ 未知目标 "${provider}"，可选：deepseek, kimi, flash, pro, deepseek-v4-flash, deepseek-v4-pro, kimi-k3`);
}
const from = `${current.provider}:${current.modelId}`;
const to = `${target.provider}:${target.modelId}`;
if (from === to) {
  return {
    content: [{ type: "text" as const, text: `ℹ️ 已是 ${to}，无需切换。` }],
    details: { from, to, changed: false },
  };
}
if (!isProviderConfigured(target.provider)) {
  return fail(`❌ ${target.provider} 的 API key 未配置，无法切换。请在 .env 配置后重试。`);
}
const flapErr = checkFlap();
if (flapErr) return fail(flapErr);

const result = llm.switch(provider, "agent");
if (!result.ok) return fail(`❌ ${result.error}`);

const text = [
  `✅ 已切换：${result.from} → ${result.to}（已持久化，重启保持）。`,
  `生效范围：新会话立即使用；运行中的其他会话（wake/飞书/定时任务）下一轮对话自动切换。`,
  `如需本会话立即切换，请提示用户使用 /provider ${provider}。`,
].join("\n");
return {
  content: [{ type: "text" as const, text }],
  details: { from: result.from, to: result.to, changed: true },
};
```

同时更新工具的 `description`：把"仅对之后新建的会话生效"改为"已持久化（重启保持）；其他运行中会话下一轮对话自动切换"。

- [ ] **Step 3: 编译 + 相关测试**

Run: `cd agent-ts && npx tsc -p tsconfig.build.json --noEmit && npm test -- --runTestsByPath src/infrastructure/tools/agent/model-switch-tool.test.ts 2>/dev/null || true; npm test`
Expected: 编译无 error；全量测试无新增失败（若无 model-switch-tool.test.ts 则跳过该条）

- [ ] **Step 4: Commit**

```bash
git add agent-ts/src/api/extensions/model-command.ts agent-ts/src/infrastructure/tools/agent/model-switch-tool.ts
git commit -m "refactor(llm): /provider与model_switch统一走switch()——持久化+行为一致"
```

---

### Task 12: beforePrompt 惰性生效

**Files:**
- Create: `agent-ts/src/api/gateway/llm-lazy-sync.ts`
- Test: `agent-ts/src/api/gateway/llm-lazy-sync.test.ts`
- Modify: `agent-ts/src/api/gateway/session-factory.ts`（beforePrompt 内挂入）

- [ ] **Step 1: Write the failing test**

```ts
// agent-ts/src/api/gateway/llm-lazy-sync.test.ts
import { describe, it, expect, beforeEach } from '@jest/globals';
import { createLazyModelSync } from './llm-lazy-sync.js';

describe('createLazyModelSync', () => {
  let versions: Map<string, number>;
  let sync: ReturnType<typeof createLazyModelSync>;

  beforeEach(() => {
    versions = new Map();
    sync = createLazyModelSync({
      getVersion: () => currentVersion,
      getSessionModel: () => ({ id: `model-v${currentVersion}` }),
    });
  });

  let currentVersion = 1;

  it('首次调用只记录版本，不 setModel', () => {
    currentVersion = 1;
    const session = { setModel: jest.fn() };
    sync(session, 'wake:default');
    expect(session.setModel).not.toHaveBeenCalled();
  });

  it('版本变化 → setModel 新模型；再次同版本不重复', () => {
    currentVersion = 1;
    const session = { setModel: jest.fn() };
    sync(session, 'wake:default');
    currentVersion = 2;
    sync(session, 'wake:default');
    expect(session.setModel).toHaveBeenCalledTimes(1);
    expect(session.setModel).toHaveBeenCalledWith({ id: 'model-v2' });
    sync(session, 'wake:default');
    expect(session.setModel).toHaveBeenCalledTimes(1);
  });

  it('不同 sessionKey 独立跟踪', () => {
    currentVersion = 1;
    const a = { setModel: jest.fn() };
    const b = { setModel: jest.fn() };
    sync(a, 'wake:a');
    currentVersion = 2;
    sync(a, 'wake:a');
    sync(b, 'wake:b'); // b 首次：只记录
    expect(a.setModel).toHaveBeenCalledTimes(1);
    expect(b.setModel).not.toHaveBeenCalled();
  });

  it('session 无 setModel 方法 → 静默跳过不抛错', () => {
    currentVersion = 1;
    expect(() => sync({}, 'wake:x')).not.toThrow();
    currentVersion = 2;
    expect(() => sync({}, 'wake:x')).not.toThrow();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd agent-ts && npm test -- --runTestsByPath src/api/gateway/llm-lazy-sync.test.ts`
Expected: FAIL — `Cannot find module './llm-lazy-sync.js'`

- [ ] **Step 3: Write implementation + 挂入 beforePrompt**

```ts
// agent-ts/src/api/gateway/llm-lazy-sync.ts
/**
 * 会话模型惰性同步：每个 gateway 会话记录上次所见的选择版本，
 * beforePrompt 时比对——版本变了就 setModel（"下一轮生效"）。
 */
export interface LazySyncDeps {
  getVersion: () => number;
  getSessionModel: () => unknown;
}

export function createLazyModelSync(deps: LazySyncDeps) {
  const seen = new Map<string, number>();
  return function sync(session: unknown, sessionKey: string): void {
    try {
      const version = deps.getVersion();
      const last = seen.get(sessionKey);
      if (last !== undefined && last !== version) {
        const s = session as { setModel?: (m: unknown) => void };
        if (typeof s.setModel === 'function') {
          s.setModel(deps.getSessionModel());
          console.log(`[llm] 会话 ${sessionKey} 惰性切换模型（v${last} → v${version}）`);
        }
      }
      seen.set(sessionKey, version);
    } catch (e) {
      console.warn('[llm] 惰性切换检查失败（不影响本次对话）:', (e as Error).message);
    }
  };
}
```

在 `session-factory.ts` 的 `createGatewaySessionFactory` 内（`beforePrompt` 定义之前）：

```ts
import { getLLM } from "../../../services/llm/index.js";
import { createLazyModelSync } from "./llm-lazy-sync.js";

// createGatewaySessionFactory 函数体内：
const lazyModelSync = createLazyModelSync({
  getVersion: () => getLLM().current().version,
  getSessionModel: () => getLLM().getSessionModel(),
});
```

并在 `beforePrompt` 开头（`setSessionContext` 之后）加一行：

```ts
lazyModelSync(session, sessionKey);
```

- [ ] **Step 4: Run tests**

Run: `cd agent-ts && npm test -- --runTestsByPath src/api/gateway/llm-lazy-sync.test.ts && npx tsc -p tsconfig.build.json --noEmit && npm test`
Expected: 新测试 PASS；编译无 error；全量无新增失败

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/api/gateway/llm-lazy-sync.ts agent-ts/src/api/gateway/llm-lazy-sync.test.ts agent-ts/src/api/gateway/session-factory.ts
git commit -m "feat(llm): beforePrompt版本比对惰性切换——活跃会话下一轮生效"
```

---

### Task 13: 依赖边界守护测试 + deprecated 标记

**Files:**
- Create: `agent-ts/src/services/llm/boundary.test.ts`
- Modify: `agent-ts/src/config/model-switcher.ts`（仅加 @deprecated 注释，不改行为）

- [ ] **Step 1: Write the test**

```ts
// agent-ts/src/services/llm/boundary.test.ts
/**
 * llm 模块依赖边界守护：
 * 1) 除 adapters/pi-ai.ts 外，模块内任何文件不得 import pi-ai / pi-coding-agent
 * 2) llm 模块不得 import agent loop（core/agent）
 */
import { describe, it, expect } from '@jest/globals';
import { readdirSync, readFileSync, statSync } from 'fs';
import { join, relative } from 'path';

const LLM_DIR = __dirname;

function listSourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...listSourceFiles(p));
    else if (name.endsWith('.ts') && !name.endsWith('.test.ts')) out.push(p);
  }
  return out;
}

describe('llm 模块依赖边界', () => {
  it('除 adapters/pi-ai.ts 外不得 import SDK', () => {
    const offenders: string[] = [];
    for (const f of listSourceFiles(LLM_DIR)) {
      if (f.endsWith(join('adapters', 'pi-ai.ts'))) continue;
      const src = readFileSync(f, 'utf8');
      if (src.includes('@mariozechner/pi-ai') || src.includes('@mariozechner/pi-coding-agent')) {
        offenders.push(relative(LLM_DIR, f));
      }
    }
    expect(offenders).toEqual([]);
  });

  it('llm 模块不得 import core/agent（无环）', () => {
    const offenders: string[] = [];
    for (const f of listSourceFiles(LLM_DIR)) {
      const src = readFileSync(f, 'utf8');
      if (/from\s+['"][^'"]*core\/agent/.test(src)) offenders.push(relative(LLM_DIR, f));
    }
    expect(offenders).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it passes（此时模块已合规，直接应绿；若红说明前面任务引入了越界 import，先修）**

Run: `cd agent-ts && npm test -- --runTestsByPath src/services/llm/boundary.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 3: model-switcher.ts 加 deprecated 标记**

在文件头注释追加一行（不改任何代码）：

```ts
 * @deprecated 生产切换已迁移到 services/llm/switch-service.ts（持久化）。
 * 本模块仅保留为 config.ts 薄代理的遗留运行时 override 层与单测兼容。
```

- [ ] **Step 4: 全量测试 + Commit**

Run: `cd agent-ts && npm test`
Expected: 无新增失败

```bash
git add agent-ts/src/services/llm/boundary.test.ts agent-ts/src/config/model-switcher.ts
git commit -m "test(llm): 依赖边界守护测试+model-switcher标记deprecated"
```

---

### Task 14: 文档更新

**Files:**
- Modify: `agent-ts/CLAUDE.md`（Environment Setup 的"运行时热切换"段）

- [ ] **Step 1: 更新文档**

把 `agent-ts/CLAUDE.md` 中「运行时热切换 provider/模型（不重启进程）」一节更新为：

```markdown
**LLM 供给模块**（`src/services/llm/`）：
- agent 世界只依赖 `port.ts`（LLMPort）+ `types.ts`；SDK 适配封装在 `adapters/pi-ai.ts`
- 切换：`/provider`（人工）与 `model_switch`（agent）统一走 `switch()`——立即持久化到
  `.pi-invest/llm-state.json`（重启保持）；触发者会话立即生效，其他活跃会话下一轮对话惰性生效
- 优先级链：`llm-state.json` > `LLM_PROVIDER`/`{PROVIDER}_MODEL_ID` env > catalog 默认（deepseek-v4-flash）
- 切换审计：`.pi-invest/model-switch.log`
```

- [ ] **Step 2: Commit**

```bash
git add agent-ts/CLAUDE.md
git commit -m "docs(llm): CLAUDE.md 更新 LLM 供给模块说明"
```

---

## Self-Review 记录

- **Spec 覆盖**：模块结构(T1-T7) ✓ 优先级链(T3) ✓ 统一切换(T4,T11) ✓ 惰性生效(T12) ✓ 错误处理(T3损坏回退/T4拒绝/T5归一化) ✓ 迁移路径 1-6(T1-T13,含 deprecated 标记) ✓ 测试策略含 compat 锁死/边界守护(T6/T13) ✓
- **已知留白（执行时处理）**：`src/index.ts`/`api/index.ts` 的 initLLM 确切插入行需读文件后定（T7 Step 4 已说明方法）；clarify/reflect-agent 的调用形状需先读文件（T10 Step 3 已说明）。
- **类型一致性**：`LLMPort.switch` 返回同步 `SwitchResult`（非 Promise——switch 无 IO 等待需求，持久化是同步 writeFileSync）；spec 中写的 `Promise<SwitchResult>` 以本计划为准。
