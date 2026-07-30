# LLM 流式中断（terminated）容错设计：可见性 + 更强重试

日期：2026-07-30
状态：已获用户批准（方案 A）
范围：agent-ts

## 背景与问题

Agent 在工具调用成功返回后，下一步 LLM 流式请求（SSE）被中途掐断时，TUI 直接显示
`Error: terminated`，整轮 run 失败。

根因调查结论：

- "terminated" 来自 Node 内置 fetch（undici）的 `TypeError: terminated` —— 响应头已收到、
  响应体流读取中途连接被终止（Kimi 服务端掐流 / 本地网络抖动 / 合盖休眠）。
- pi-coding-agent 的 `AgentSession` **已内置 auto-retry**：`_isRetryableError` 正则明确包含
  `terminated`，默认 enabled、maxRetries=3、baseDelayMs=2000（退避 2s→4s→8s）。
- 但 agent-ts **未订阅 `auto_retry_start` / `auto_retry_end` 事件**，重试过程在 UI 完全静默，
  用户只能看到最终失败，无法区分"没重试"与"重试耗尽"。
- 默认重试预算偏小（总计约 14s），覆盖不了持续 30s+ 的抖动或休眠唤醒场景。
- [config.ts](../../../agent-ts/src/config/config.ts) 中的 `maxRetries: 2` 传给 OpenAI client，
  只管建连阶段，与流中断无关，不在本次改动范围。

## 目标

1. 增强重试预算：覆盖分钟级以内的瞬时中断。
2. 重试过程可见：TUI / gateway 日志 / events.jsonl 三个渠道都能看到重试发生与结果，
   为后续诊断提供证据。

非目标（YAGNI）：不改 SDK、不做 provider 自动 failover、不动 OpenAI client 层 maxRetries。

## 设计

### 1. 重试策略配置

新建 `agent-ts/.pi/settings.json`：

```json
{ "retry": { "enabled": true, "maxRetries": 5, "baseDelayMs": 3000 } }
```

- SDK 从 `<cwd>/.pi/settings.json` 读取 project settings
  （pi-coding-agent `settings-manager.js`，`projectSettingsPath = join(cwd, ".pi", "settings.json")`，
  cwd = agent-ts 根目录）。
- 退避序列：3s → 6s → 12s → 24s → 48s，总等待约 93 秒，共 5 次重试。
- `.pi/` 未被 gitignore（仅 `.pi-invest/` 被忽略），该文件提交进仓库，随 Syncthing/git 双机一致。
- 注意：`SettingsManager` 只有 `setRetryEnabled` setter，maxRetries/baseDelayMs 只能通过
  settings 文件配置 —— 这是采用 settings.json 而非纯代码注入的原因。

### 2. 重试可见性

修改 `agent-ts/src/infrastructure/session/session-factory.ts` 的 `attachLogger`，
在事件 switch 中新增两个分支（主 agent 与 subagent/plan 的 session 都经过此函数，
天然覆盖所有通道）：

- `auto_retry_start`：
  - console 输出：`🔄 LLM 连接中断，{delayMs/1000}s 后重试 ({attempt}/{maxAttempts}): {errorMessage}`
  - 写 events.jsonl：新增 `llm.retry` 事件（observable-logger 新增 `logLLMRetry` 函数），
    字段：attempt、maxAttempts、delayMs、errorMessage
- `auto_retry_end`：
  - 成功：console `✅ 重试成功（第 {attempt} 次）`
  - 失败：console `❌ 重试耗尽（{attempt} 次）: {finalError}`
  - 同样落 `llm.retry` 事件（success 标志 + finalError）

### 3. 错误处理

- attachLogger 内事件处理沿用现有风格（静默 try/catch 不需要 —— 现有分支均不捕获，
  保持一致；事件字段缺失时用默认值兜底，不 throw）。
- settings.json 缺失/损坏时 SDK 回退默认（3 次/2s），不影响启动。

### 4. 测试

jest 单测（必须 `npm test`，禁止裸 `npx jest`）：

- `session-factory` 新增/扩展测试：mock session，分别 emit
  `auto_retry_start` / `auto_retry_end`（成功与失败两种），断言 console 输出内容
  与 observable-logger 的 `llm.retry` 写入。
- settings 生效验证：用 `SettingsManager.create(agent-ts 根目录, 临时 agentDir)` 读取
  项目 `.pi/settings.json`，断言 `getRetrySettings()` 返回 `{enabled: true, maxRetries: 5, baseDelayMs: 3000}`。

### 5. 改动文件清单

| 文件 | 改动 |
|---|---|
| `agent-ts/.pi/settings.json` | 新增，retry 配置 |
| `agent-ts/src/infrastructure/session/session-factory.ts` | attachLogger 增加两个事件分支 |
| `agent-ts/src/infrastructure/logging/observable-logger.ts` | 新增 `logLLMRetry` |
| `agent-ts/src/infrastructure/session/session-factory.test.ts`（或新测试文件） | 单测 |

## 验证方式

- `npm test` 通过（注意区分 [memory: baseline-failing-tests] 中已存在的预存失败）。
- 手动验证：启动 agent，断网/恢复模拟中断，观察 console 重试提示与 events.jsonl 记录
  （可选，实现后视情况做）。
