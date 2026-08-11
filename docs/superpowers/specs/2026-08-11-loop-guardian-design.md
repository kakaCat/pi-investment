# LoopGuardian 设计文档 —— agent-ts 引擎侧防呆护栏

> 日期：2026-08-11
> 来源：GenericAgent 学习报告（docs/generic-agent-lessons-report.md）P0-1 + P0-2
> 状态：设计已确认（方案 A / 全场景 / 通知+软收尾 / Extension 钩子实现）

## 1. 目标与背景

对治 agent-ts 无人值守长跑时真实发生过的三类事故：

1. **光说不练**：模型回复写了一大段代码/方案，但一个工具都没调，任务实际未执行
2. **死循环**：同一工具同一参数反复调用，几百轮烧 token 无结果
3. **静默失败**：LLM 调用出错（如 401）被吞掉，任务"看似跑完"实际什么都没做（2026-07 wake 事故）

LoopGuardian 是**纯工程护栏**：一堆写死的 if/else 规则，不调用 LLM、不学习、不参与投资决策。阈值与文案集中为常量，将来可被文本参数进化系统调优（它是被调优对象，不是决策者）。

## 2. 实现方式：SDK Extension 钩子

`pi-coding-agent` SDK 自带 Extension API，代码库已有先例：`src/api/extensions/model-command.ts`（ExtensionFactory），经 `createAppResourceLoader()` 的 `extensionFactories` 数组注册。

**新增一个文件**：`agent-ts/src/api/extensions/loop-guardian.ts`，导出 `loopGuardianExtension: ExtensionFactory`。

**改动一行**：`model-command.ts` 的 `createAppResourceLoader()` 中 `extensionFactories: [modelCommandExtension, loopGuardianExtension]`。

挂载后 TUI / 飞书 / wake channel / cron 调度全覆盖（共享同一 session 创建路径）。SDK 自动管理扩展生命周期（/resume 重建无需处理）。

### 使用的 SDK API

```typescript
pi.on("turn_end", handler)              // 轮次计数
pi.on("tool_execution_start", handler)  // tool+args 重复检测
pi.on("auto_retry_start", ...)          // LLM 静默重试计数（若扩展事件不含此项则退回 session 事件）
pi.on("agent_end", handler)             // 最终回复检查
pi.sendUserMessage(text, { deliverAs: "steer" })    // 运行中插话
pi.sendUserMessage(text, { deliverAs: "followUp" }) // 结束后自动追问
```

> 实现期需确认 `auto_retry_start/end` 是否经扩展事件透出；若否，R7 改从 `pi.on` 可用事件推导或经 session.subscribe 补充。

## 3. 内部结构

```
loop-guardian.ts
├── 常量区：阈值（13/31/150/3/3）+ 全部文案（中文、集中、可被进化调优）
├── GuardianState      —— 每 prompt 周期重置：turnCount / consecutiveNoTool /
│                        recentCalls(tool+args 哈希队列) / retryErrors / 已触发档位集合
├── evaluate(snapshot) → Intervention[]   —— 纯函数，规则判定，不碰 SDK（单测核心）
└── loopGuardianExtension(pi)             —— 薄事件翻译层：事件 → 更新 state →
                                            evaluate → 执行动作（sendUserMessage / notify / 日志）
```

## 4. 规则表

| # | 条件 | 动作 | 渠道 |
|---|---|---|---|
| R1 | turn % 13 == 0（每档一次） | 注入"停止无新信息重试；存关键上下文；无进展换方案或重读 skill" | steer |
| R2 | turn % 31 == 0（每档一次） | 注入"关键发现/已试方案写入文件，防止上下文压缩丢失" | steer |
| R3 | 同一 tool+args 哈希连续 ≥3 次 | 注入"连续 N 次相同调用 {tool}，先分析上次结果为何不符预期" | steer |
| R4 | turn ≥ 150（每任务一次） | 通知 + 注入"停止尝试，总结已验证进展与残余风险后收尾" | notify + steer |
| R5 | agent_end：本周期 0 次工具调用，最终消息以单个大代码块结尾且块外残余文字 <30 字符 | 追问"要执行/写入/分析请显式调工具；仅供展示请说明后结束" | followUp |
| R6 | agent_end：最终消息为空或含截断标记 | 追问"分小步重新生成并完成操作" | followUp |
| R7 | agent_end：本周期 LLM 重试 ≥3 且 0 次工具调用 | 写事故日志 + 飞书通知（不注入对话，agent 大概率已坏） | 日志 + notify |

**防打扰约束**：
- R1/R2 同一档位每周期只触发一次
- R5/R6 每个任务最多追问 1 次，追问后仍不调工具则放行——Guardian 自身绝不形成追问循环
- 交互式场景 R4 只提示不硬收尾（判断依据：SessionContext.type）

**通知**：复用 `src/services/notification/` 飞书通道，含场景类型、sessionId、任务摘要（前 80 字）、建议排查项。

**与现有机制防重复**：agent-loop.ts 已有 >50k token 异步记忆保存，R1 文案不提"记忆保存"，只说"存关键上下文"，避免双写冲突。

## 5. 测试策略

**单元测试**（`loop-guardian.test.ts`，`npm test` 运行，ESM 走 --experimental-vm-modules）：

- 普通轮次（turn 5）→ 无干预
- R1：turn 13 → steer 一次；同档不重复
- R3：同 tool 同 args ×3 → 触发；同 tool 不同 args ×3 → 不触发
- R5：0 工具 + 大代码块结尾 + 残余 <30 字 → followUp；有大段解释文字 → 不触发；已追问过 → 不再追问
- R7：retryErrors≥3 且 0 工具 → notify 动作

**集成测试（轻量）**：mock `pi` 上下文（`on` 收集 handler、`sendUserMessage` 记录调用），事件序列驱动（turn_end×13 → 断言 steer 调 1 次）。不起真 session、不调真 LLM。

**手动验收**（worktree 内 TUI）：
1. 15+ 轮任务 → 观察第 13 轮 steer 注入
2. 构造"只贴代码不调工具" → 观察 followUp 追问

## 6. 验收标准

- `npm test` 新增用例全绿，不加重既有失败清单（对照 baseline failing tests 记忆）
- 交互式普通问答（1-2 轮）零干扰
- Guardian 无定时器、无未 await promise 悬挂（不引入异步泄漏）
- 环境变量 `LOOP_GUARDIAN=off` 整体禁用（默认开），免回滚回退

## 7. 明确不做

- 不调用 LLM、不学习、不参与投资决策
- 不改 60+ 领域工具、不动 scheduler/进化系统
- 不做轮次上限硬杀（软收尾 + 通知）
- 阈值自调（留给文本参数进化系统）
