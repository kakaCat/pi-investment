# LLM 供给模块解耦设计（src/services/llm/）

- 日期：2026-08-11
- 状态：已获用户批准（方向与深度），待实现计划
- 参考：Claude Code 模型配置机制（分层优先级、/model 持久化、provider env 开关、无插件接口）

## 1. 背景与问题

当前 LLM 配置与 agent 项目耦合过紧，具体症状：

1. **依赖方向混乱**：`agent-loop.ts` / `background-agent-loop.ts` / `session-factory.ts` 三处直接 import `config.ts` 的 `createModel()`；agent loop 知道模型如何构造、来自哪个 provider、甚至知道 pi-ai SDK 的 `Model` 类型形状。
2. **配置散落**：provider 定义硬编码在 `config.ts` 的 `PROVIDER_PRESETS`；凭证/端点走多层环境变量优先级链（`LLM_PROVIDER` / `{PROVIDER}_MODEL_ID` / `MODEL_ID` / 别名表）。
3. **切换不持久**：`/provider` 命令与 `model_switch` 工具的热切换只写内存（`model-switcher.ts`），重启回退 `.env`。已发生实际脱节事故：`.env` 配置 kimi/k3，运行时人工切到 deepseek，重启即回退。
4. **入口行为不一致**：`/provider` 当前会话立即生效；`model_switch` 仅新会话生效。
5. **SDK 怪癖泄漏**：`createModel()` 副作用改写 `OPENAI_API_KEY` 环境变量（pi-ai SDK 只从该变量取 key）；kimi compat（`supportsDeveloperRole: false`）曾两次丢失导致 `tokenization failed` 事故。
6. **一次性调用绕过抽象**：`plan-agent.ts` / `clarify-agent.ts` / `reflect-agent.ts` 直接 `completeSimple(createModel(), ...)` import pi-ai。

## 2. 目标（用户已确认的决策）

| 决策点 | 结论 |
|--------|------|
| 核心目标 | **统一切换入口**：所有入口走同一个切换服务，行为一致（立即生效 + 持久化） |
| 活跃会话生效方式 | **下一轮惰性生效**：触发者会话立即生效；其他已存在会话下一轮对话时检测并切换（挂 `beforePrompt` 钩子，不建会话注册表） |
| 持久化方式 | `.env` 作为所有 provider 的"配置目录"启动时加载进内存；当前选择是独立状态，持久化到 `.pi-invest/llm-state.json`，优先级高于 `.env` |
| 解耦深度 | **完全自有类型体系**：定义自己的 LLM 类型（模型配置/消息/响应/用量/错误），pi-ai SDK 只是 adapter，未来可替换 |

明确**不做**（YAGNI）：
- provider 配置文件驱动的插件注册表（Claude Code 也无此机制，provider 内置 + env 注入是主流做法）
- 自动 failover（429/401 自动切备选 provider）
- apiKeyHelper 动态凭证脚本
- session-only 切换模式（后续需要再加）
- 替换 SDK 的会话内工具循环/流式事件/compaction（等于重写 agent 框架）

## 3. 模块结构

```
src/services/llm/
├── types.ts           # 自有类型体系（禁止 import 任何 SDK 类型）
│                      #   LLMModelConfig / ChatMessage / ChatRequest /
│                      #   ChatResponse / Usage / LLMError / LLMSelection
├── port.ts            # LLMPort 接口 —— agent 世界依赖的唯一抽象
├── catalog.ts         # provider 目录：presets(代码) + .env 合成；含别名表、compat 声明
├── selection.ts       # 当前选择 + 版本号 + 持久化 .pi-invest/llm-state.json
├── switch-service.ts  # 统一切换：resolve → validate → 持久化 → 审计
├── client.ts          # 自有 LLM 客户端：complete() 直走 OpenAI 兼容 HTTP
└── adapters/pi-ai.ts  # 模块内唯一允许 import pi-ai 的文件：
                       #   LLMModelConfig → SDK Model；
                       #   封装 OPENAI_API_KEY 同步、kimi compat 等全部 SDK 怪癖
```

### 3.1 自有类型（types.ts，要点）

```ts
interface LLMModelConfig {
  provider: string;          // 'deepseek' | 'kimi'（catalog 注册名为准）
  modelId: string;
  baseUrl: string;
  apiKey: string;            // 已从 env 解析好的最终值
  contextWindow: number;
  maxTokens: number;
  reasoning: boolean;
  compat?: {                 // SDK 适配声明（adapter 消费，业务方不感知）
    supportsDeveloperRole?: boolean;
    supportsStore?: boolean;
    maxTokensField?: 'max_tokens' | 'max_completion_tokens';
  };
  timeoutMs: number;
  maxRetries: number;
}

interface ChatMessage { role: 'system' | 'user' | 'assistant'; content: string }

interface ChatRequest {
  messages: ChatMessage[];
  maxTokens?: number;
  temperature?: number;
}

interface ChatResponse {
  text: string;
  usage: Usage;              // { input, output, totalTokens }
  model: string;             // 实际响应的模型 ID
}

type LLMErrorKind = 'auth' | 'rate_limit' | 'overloaded' | 'timeout' | 'invalid_request' | 'unknown';
class LLMError extends Error { kind: LLMErrorKind; retryable: boolean }

interface LLMSelection {
  provider: string;
  modelId: string;
  updatedBy: 'human' | 'agent' | 'env' | 'default';
  updatedAt: string;         // ISO 时间
  version: number;           // 单调递增，惰性生效比对用
}
```

### 3.2 端口定义（port.ts）

```ts
interface LLMPort {
  current(): LLMSelection;
  getModelConfig(): LLMModelConfig;                   // 自有类型，可不透明传递
  getSessionModel(): unknown;                         // 给 SDK 会话的句柄（内部经 adapter）
  complete(req: ChatRequest): Promise<ChatResponse>;  // 一次性调用（plan agents 改走这里）
  switch(target: string, by: 'human' | 'agent'): Promise<SwitchResult>;
  status(): LLMStatus;                                // 各 provider key 配置状态 + 当前选择
  onChange(cb: (s: LLMSelection) => void): void;      // 惰性生效钩子
}
```

### 3.3 依赖规则（须有测试或 lint 守护）

- agent loop、session-factory、background-agent-loop、plan 三杰、`/provider`、`model_switch` → **只允许** import `port.ts` + `types.ts`
- `adapters/pi-ai.ts` 是 llm 模块内唯一 import pi-ai 的文件
- llm 模块不 import agent loop 的任何模块（无环）

### 3.4 边界诚实声明

自有类型体系覆盖 **LLM 调用面**（模型描述 / 一次性问答 / 用量 / 错误归一化）。SDK 会话内部的工具循环、流式事件、compaction 仍是 pi-coding-agent 的领域（`sdk-facade` / `session-facade` / `compaction-facade` 不变）。

## 4. 配置优先级链（写在模块文档，单一事实来源）

```
.pi-invest/llm-state.json   ← /provider、model_switch 写入（≈ Claude Code 的 /model 持久化到 user settings）
        ↓ （文件不存在或损坏时，警告并回退）
LLM_PROVIDER / {PROVIDER}_MODEL_ID / MODEL_ID 环境变量（≈ ANTHROPIC_MODEL）
        ↓
catalog 默认值 deepseek-v4-flash（≈ 系统默认）
```

`.env` 角色：所有 provider 的凭证/端点/模型覆盖的**配置目录**（`DEEPSEEK_API_KEY`、`KIMI_BASE_URL`、`DEEPSEEK_MODEL_ID` 等），启动时由 catalog 合成内存目录；运行时不回写 `.env`。

## 5. 统一切换流程

`/provider` 命令与 `model_switch` 工具均调用 `switchService.switch(target, by)`：

1. **resolve**：`target` 经别名表（`flash`/`pro`/`k3`/完整模型 ID/provider 名）解析为 `{provider, modelId}`
2. **validate**：目标 provider 的 API key 已配置（缺则拒绝，报出缺哪个环境变量）
3. **persist**：写入 `.pi-invest/llm-state.json`，版本号 +1
4. **审计**：追加 `.pi-invest/model-switch.log`（现有格式保留：`{ts, from, to, trigger}`）
5. **生效**：触发者会话由入口立即 `setModel`（保留现有行为）；`onChange` 通知惰性消费者
6. 返回统一 `SwitchResult { ok, from, to, error? }`

agent 侧 1 小时 3 次限流保留在 `model_switch` 工具层（不属于切换服务）。

## 6. 惰性生效机制

- `selection` 模块维护内存版本号 + state 文件 mtime 缓存（避免每轮读盘）
- gateway 会话在已有的 `beforePrompt` 钩子（`session-factory.ts`）比对版本，变了就 `session.setModel(getSessionModel())`
- 新会话创建时 `getSessionModel()` 自然读到最新选择（现状已如此）
- 主 TUI 会话即触发者，立即生效（现有 `pi.setModel` 路径）

## 7. 错误处理

| 场景 | 行为 |
|------|------|
| state 文件损坏/缺失 | 警告并回退 env 链，不 crash |
| 切换目标 key 未配置 | 拒绝切换，报出缺哪个环境变量 |
| `complete()` HTTP 错误 | 归一化为 `LLMError`（auth/rate_limit/overloaded/timeout/...），调用方不见 SDK 特有错误；沿用 `.pi/settings.json` 的 5 次/3s 重试策略 |
| 切换后首次调用 401/429 | 仅记审计日志，**不做自动 failover** |

## 8. 迁移路径（每步独立可验证）

1. 建 `types.ts` + `port.ts` + `catalog.ts` / `selection.ts` / `switch-service.ts` / `client.ts` / `adapters/pi-ai.ts`（纯新增，不动旧代码）
2. `config.ts` 的 `createModel()` / `getActiveProvider()` / `getActiveModelId()` 改为薄代理转发 llm 模块（现有 `config.test.ts` 必须全绿）
3. 三处 session 创建点（agent-loop / background-agent-loop / session-factory）+ plan 三杰 改走 LLMPort
4. `/provider` 与 `model_switch` 统一调 `switch()`
5. `beforePrompt` 挂版本比对 → 惰性生效
6. `config.ts` 旧代理标记 deprecated，观察一个迭代后删除

## 9. 测试策略（TDD）

- **selection**：state 文件读写、损坏回退、优先级链（state > env > 默认）、版本号单调
- **switch-service**：成功切换 / 未配置拒绝 / 持久化验证 / 审计日志追加 / 别名解析
- **compat 回归锁死**：kimi `supportsDeveloperRole: false` 必须在 adapter 输出中（历史两次事故）
- **client**：`complete()` 的错误归一化（mock HTTP 401/429/500/timeout）
- **惰性生效**：beforePrompt 版本比对触发切换
- **依赖规则**：扫描测试——`src/services/llm/` 外不得 import `adapters/pi-ai.ts`；llm 模块不得 import `core/agent/`
- **回归**：现有 `config.test.ts`、`model-switcher.test.ts` 全绿

## 10. 风险与对策

| 风险 | 对策 |
|------|------|
| `config.ts` 是敏感区（kimi compat 两次事故） | 先加回归测试锁死 compat，再动代码；薄代理期新旧并存 |
| 自有类型做成漏风抽象 | 类型只覆盖两个真实消费面（session model 句柄 + complete 一次性调用），不超前抽象流式/工具循环 |
| state 文件与 .env 双来源混淆 | 模块文档写死优先级链；`/provider` 无参状态输出显示当前选择来源（state/env/default） |
| 多进程不一致（当前单进程，未来若拆分） | state 文件 mtime 缓存已为此预留；届时改为文件监听 |
