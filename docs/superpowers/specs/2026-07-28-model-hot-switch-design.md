# 模型热切换设计（DeepSeek ↔ Kimi）

日期：2026-07-28
状态：已确认，待实现

## 背景

agent-ts 的 LLM provider **不是写死的**：[config.ts](../../../agent-ts/src/config/config.ts) 已有 `PROVIDER_PRESETS`（deepseek / kimi 双预设），启动时由 `LLM_PROVIDER` 环境变量静态选择，`createModel()` 每次调用时现读配置。

痛点：切换 provider 必须改 `.env` 并重启进程。盘中 DeepSeek 限流/宕机时无法快速切到 Kimi。

## 目标

- 不重启进程切换 provider，当前会话与未来会话（定时任务唤醒、subagent、memory-saver）都生效
- 两个入口：人用 CLI 斜杠命令；agent 用工具自主切换（如检测到持续报错时）
- 仅内存生效，重启后回到 `.env` 的 `LLM_PROVIDER`（不改写配置文件）

## 非目标

- 代码级自动 failover（SDK 调用失败自动换 provider 重试）——本次以"agent 自主决策切换"的形式覆盖，不做透明重试
- 按任务类型分流（长上下文走 Kimi 等）
- 切换持久化到 `.env`

## 架构

```
┌─ 入口1: /model 斜杠命令 (extension) ─┐
│                                      ├─→ model-switcher (运行时状态) ─→ getActiveProvider()
├─ 入口2: model_switch agent 工具 ─────┘                                      │
                                                                              ↓
session.setModel(createModel()) ←── createModel() 现读 provider + 同步 OPENAI_API_KEY
```

### 组件 1：`src/config/model-switcher.ts`（新增，约 60 行）

```typescript
let runtimeProvider: LLMProviderName | null = null;  // null = 未切换过

export function getRuntimeProvider(): LLMProviderName;       // runtime ?? env
export function setRuntimeProvider(p: LLMProviderName): void; // 仅内存
export function listProviders(): ProviderInfo[];              // 各 provider + key 是否已配置
export function isProviderConfigured(p: LLMProviderName): boolean;
```

### 组件 2：config.ts 改造（一行逻辑）

`getActiveProvider()` 先读 `model-switcher` 运行时状态，未设置再回退 `LLM_PROVIDER` 环境变量。`createModel()` 无需改动 —— 它每次调用现读 provider/key，且已有 `OPENAI_API_KEY` 同步逻辑（SDK 只从该环境变量读 key）。

### 组件 3：CLI 斜杠命令 `/model`

新增 `src/api/extensions/model-command.ts`，用 SDK extension 的 `registerCommand` 注册，session 创建时挂载：

| 用法 | 行为 |
|------|------|
| `/model` | 显示当前 provider、模型 ID、各 provider key 配置状态 |
| `/model kimi` / `/model deepseek` | `setRuntimeProvider()` + `session.setModel(createModel())`，TUI 打印确认 |

### 组件 4：Agent 工具 `model_switch`

新增 `src/infrastructure/tools/agent/model-switch-tool.ts`，注册进工具表：

- 参数：`provider: "deepseek" | "kimi"`
- 执行：`setRuntimeProvider()`（当前会话下一轮即生效）
- 返回：切换前后 provider、新模型 ID、决策上下文（"切换已生效，后续任务将使用 Kimi"）

## 切换语义

- 切换影响"下一次模型调用"起的行为；正在流式输出的回复不中断
- 全进程生效：gateway 模式多并行会话共享同一进程时，切换影响所有会话（设计意图）
- `setModel()` 是 SDK 公开 API（agent-session.d.ts:402），auth 校验风险见「风险」

## 护栏（两个入口共用）

1. 目标 provider = 当前 provider → 幂等返回"已是当前模型"
2. 目标 provider key 未配置 → 拒绝，提示缺哪个环境变量
3. Agent 工具额外限制：每会话最多切换 3 次，超出拒绝并提示人工 `/model` 处理（防 DeepSeek↔Kimi 报错来回抖动）
4. 每次切换写日志：时间、从→到、触发方（human/agent）

## 测试

### 单元测试（Jest，npm test）

`model-switcher.test.ts`：
- 默认读环境变量；`setRuntimeProvider()` 后优先运行时状态
- 未知 provider 回退 deepseek（保持现有行为）
- 切换后 `createModel()` 返回新 baseUrl/modelId，`OPENAI_API_KEY` 已同步
- `listProviders()` 正确标注 key 配置状态

`model-switch-tool.test.ts`：
- 正常切换返回决策上下文
- 幂等切换
- 缺 key 拒绝
- 每会话 3 次上限后拒绝

### 手动验证（npm run dev）

1. `/model` 显示当前 deepseek
2. `/model kimi` → 确认 → 发问，日志确认请求打到 `api.kimi.com/coding/v1`
3. `/model deepseek` 切回
4. 让 agent 调 `model_switch`，观察下一轮行为与日志

## 风险

- **`session.setModel()` auth 校验**：自定义模型走 `provider: 'openai'` + 显式 baseUrl，SDK 可能校验 auth 配置。若报错，降级方案：命令只设运行时状态（新会话生效，当前会话不变）。手动验证时确认。
- **多会话并行**：gateway 模式下切换是全进程的，文档已注明为设计意图。

## 环境变量（不变）

```bash
LLM_PROVIDER=deepseek          # 启动默认（运行时切换的 fallback）
DEEPSEEK_API_KEY / KIMI_API_KEY
DEEPSEEK_MODEL_ID=deepseek-v4-pro / KIMI_MODEL_ID=k3
KIMI_BASE_URL=https://api.kimi.com/coding/v1   # 必须带 /v1
```
