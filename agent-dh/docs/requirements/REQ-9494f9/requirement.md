# REQ-9494f9 需求文档 · 修复 solve-kit 收单催办把字符串当消息投递导致控制流崩溃

- **类型**：bug
- **窗口**：w-f8006463（角色 investor）
- **日期**：2026-09-21
- **关联计划**：docs/requirements/REQ-9494f9/plan.md

## 1. 背景与用户原话

> 「[session-controller] control stream failed: RemoteError: Cannot read properties of undefined (reading 'kind')
>     at RemoteStreamMuxClient.open (client.js:370:1)
>     at async Proxy.invokeStream (client.js:1637:1)
>     at async RemoteStream.read (client.js:861:1)
>     at async RemoteSnapshotStream.consume (client.js:1375:1)
> 报错了，查看一下原因」

用户在 :13080 GUI 控制台持续看到 `[session-controller] control stream failed`。该错误与用户当前所在窗口无关——**任何窗口都会报**（原因见 §4）。

## 2. 复现步骤（可证伪）

**R-1 · 数据复现（已复现，命令 + 输出）**：

```bash
cd /Users/yunpeng/pi-investment/agent-dh
find .dsh-data/sessions -name 'session.v3.jsonl.zstd' | while read -r f; do
  zstd -d -c "$f" 2>/dev/null | grep -q 'inserted":\["' && echo "HIT $f"
done
# 实测输出（2026-09-21 02:3x CST）：
# HIT .../session-6faac762-d721-4942-ae9a-f6463ab7cf79/session.v3.jsonl.zstd
# scanned=315 hits=1
```

**R-2 · 形状复现（红→绿，落成单测）**：对**修复前**代码执行形状断言必须失败（证明催办投递物不是消息对象）：

```js
const msg = buildNudgeMessage({ eventId: 'x', title: 't', attempt: 1, total: 3,
  actorWindow: 'w-a', panel: '执行看板', plugin: 'dashboard-execution' })
typeof msg === 'object' && typeof msg.id === 'string'   // 期望 true，修复前实为 false
msg.source?.kind                                        // 期望 'plugin'，修复前实为 undefined
```

可执行入口：`npx vitest run packages/solve-kit/tests/nudge-message.test.ts`（计划 t2 新建；修复前必须红）。

**R-3 · 症状复现（现场证据）**：

1. 浏览器控制台 `[session-controller] control stream failed: RemoteError: Cannot read properties of undefined (reading 'kind')`（来源：`dsh-api-session-controller/lib/client.js:3527` 的 failed 回调）。
2. 运行日志 `.dsh-data/state/restart-1789909889688.log` 出现相邻两行：

```
[solve-kit] 收单催办已投递: 7f0819b1 第 1 次 → w-6faac762
[solve-kit] 收单盯梢检查异常（下一检查点重试）: message "undefined" is already pending
```

3. 持久化脏数据：`session-6faac762…/session.v3.jsonl.zstd` 的 `seq=1471`、`type=agent/inbox/spliced`、`target=next-turn`，`inserted[0]` **是字符串**（`⏰ 收单催办（执行看板 · 第 1/3 次，来自 w-6faac762 的派单）…`），且其后**无任何**移除该消息的 splice 事件。

**预期 vs 实际**：预期催办以消息信封入箱、控制流正常；实际入箱物是字符串、control stream 持续失败。

## 3. 根因（已定位到行）

**缺陷**：`packages/solve-kit/src/host.ts` 的 `buildNudgeMessage()`（host.ts:106-114）返回**纯字符串**（数组 .join(NL)），`watchResolution()` 在 **host.ts:134** 直接 `target.agent.followup(buildNudgeMessage({...}))`。

**契约**：`agent.followup` 要求 **UserMessage 信封**，不是文本。链路（框架侧，只读核实）：

| 环节 | 位置 | 行为 |
|---|---|---|
| followup | `dsh-agent-loop/lib/index.js:789` | `followup(input){ this.send(input,'next-turn',true) }` |
| 入箱 | 同文件 `inbox.splice → mutate`（:194） | 去重校验读 `message.id` → 字符串得 undefined |
| 建基线 | `dsh-api-session-controller/lib/index.js:1162`（queueItemsFromInbox） | 读 `message.source.kind` → **TypeError** |
| 抛到前端 | `dsh-api-gateway/lib/client.js:370` | 包成 RemoteError 抛出 → 即用户看到的报错 |

**同文件已有正确范式**：`buildSolveMessage()`（host.ts:57-94）返回 `{id: randomUUID(), role:'user', content:[{type:'text',text}], source:{kind:'plugin',plugin}}`；`board-solve.ts:112`、`lifecycle`（均用 `createUserMessage`）、`dsh-pmboard/AgentDeliverer.ts:68` 也都是信封。**只有催办这一条路径漏了**——同一包内两种形状并存，是本次缺陷的直接成因。

**为什么第二次催办报 "already pending"**：字符串的 `id` 恒为 undefined，第一次插入时无冲突；第二次插入时去重集合里已有 undefined → 抛错。两条日志因此成对出现（同一根因的两个症状）。

## 4. 影响面

- **Host-wide**：control stream 的 baseline 会遍历**全部** session 的 queue（session-controller `baseline()`，index.js:1055-1069），因此**一个 session 的脏消息让所有浏览器窗口的控制流建基线失败**——这是"报错出现在无关窗口"的原因。
- **持久**：脏消息写在 session event log 里，投影重放后依旧存在 → **重启 DSH 不修复**。
- **不限于 control stream**：任何读 `message.source.kind` 的消费者都会被这条脏消息打挂，例如会话队列移除通道（session-controller index.js:855）与 `agent/inbox/claimed` 处理器（`dsh-tool-jobs/lib/index.js:176`）——即"让它被 claim 掉"这条捷径本身也会崩。
- **业务影响**：w-6faac762 的收单催办链路事实上失效（第 2、3 次催办全部抛错），错误事件闭环靠人自觉。

## 5. 期望行为

- 催办消息以合法 UserMessage 信封投递；连续多次催办不触发 `already pending`。
- 修掉存量脏数据后，**任何窗口**的控制台不再出现 `[session-controller] control stream failed`。

## 6. 需求条款

- **FR-1**：`buildNudgeMessage()` 必须返回 UserMessage 信封（`id`=randomUUID、`role:'user'`、`content:[{type:'text',text}]`、`source:{kind:'plugin',plugin}`）；调用点（host.ts:134）须传入 plugin 署名。**禁止**再向 `followup` / `deliverMessage` 传字符串。
- **FR-2**：回归测试锁死形状：断言催办消息为对象且 `typeof id === 'string'`、`source.kind === 'plugin'`、`content[0].type === 'text'`；并覆盖"连续两次催办"不抛 `already pending`（用严格双重身模拟 inbox 去重）。
- **FR-3**：审计 solve-kit 全部投递点（`followup` / `deliverMessage` 调用方）形状一致；同包内不得再出现"一份信封、一份字符串"。
- **FR-4**：**存量数据修复**：session-6faac762 的 next-turn 脏字符串被移除，且移除过程不触发 `message.source.kind` 读取（不得走 claim 路径）；修复前先备份 session 文件。
- **FR-5**：线上可核验：浏览器控制台连续刷新不再出现 `[session-controller] control stream failed`；日志中催办第二次不再报 `already pending`。
- **FR-6**：留痕：记录根因、修复动作与验证证据（decision_audit / memory_write），并标注数据来源与时点。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已完成（有证据） | t-90d985 |
| FR-2 | ✅ 已完成（有证据） | t-673e77 |
| FR-3 | ✅ 已接收 | t-0f54a6 |
| FR-4 | ✅ 已接收 | t-f0dcf2 |
| FR-5 | ✅ 已接收 | t-f0dcf2 |
| FR-6 | ✅ 已接收 | t-0f54a6 |

> 无未接收条款（6 条全部有落点）。

<!-- reqboard:marks:end -->

## 7. 边界（明确不做）

- **不改 DSH 框架代码**（`node_modules` 内 control baseline / inbox 的去重与防御性校验）——上游对坏形状零容忍属其设计，本需求只保证我们不产出坏形状；"基线对单条坏数据应降级而非整体失败"另立需求。
- **不改其他投递点形状**（execution / holdings / bulletin / pmboard / lifecycle 均已正确，只做只读审计）。
- **不重构 watchResolution 的计时机制**（内存 setTimeout、宿主重启即丢——已知限制，不在本需求）。
- **不动 session 数据的其他部分**（不改历史事件、不裁剪日志、不做迁移）。
- **不加通用运行时守卫**（如给 followup 套类型检查 wrapper）——本需求以修形状 + 回归测试为准，守卫另行评估。
- **不做顺手重构**：不把催办改走 `deliverMessage`（信封仍须由调用方构造，改道纯属搬迁）。

## 8. 回归（回归测试与复核口径）

- **落点**：`packages/solve-kit/tests/nudge-message.test.ts`（计划 t2 新建；根 vitest.config.ts 已 include `packages/**/tests/**/*.test.ts`）。
- **断言**：A1 形状（对象 + id 为字符串 UUID + role='user' + content[0].type='text' + source.kind='plugin' + plugin 透传）；A2 连续两次调用 id 不相等；A3 严格双重身（模拟 `inbox.mutate` 去重读 `message.id`、模拟 `queueItemsFromInbox` 读 `message.source.kind`）不抛错。
- **先红后绿**：修复前该文件必须失败（R-2）；修复后必须全绿——验收只认可复核的"失败 → 通过"对比，不接受"改完看起来好了"。
- **故障注入**：把 `buildNudgeMessage` 临时改回返回字符串，同命令必须重新变红（证明测试真锁得住这条复现路径）。
- **命令**：`cd agent-dh && npx vitest run packages/solve-kit/tests/nudge-message.test.ts`。

## 9. 验收标准

| 编号 | 验收动作 | 通过标准 |
|---|---|---|
| AC-1 | 读 buildNudgeMessage 返回值 | 为对象信封，含 id/role/content/source |
| AC-2 | 跑 solve-kit 回归测试 | 形状断言 + "连续两次催办"用例全绿（且修复前为红） |
| AC-3 | 全仓扫 followup( 调用方 | 无字符串实参（只有信封或 createUserMessage） |
| AC-4 | 扫 session-6faac762 event log | 脏字符串已有对应移除 splice；折叠投影后 next-turn 为空 |
| AC-5 | 浏览器刷新 :13080 | 控制台无 [session-controller] control stream failed |
| AC-6 | 全量扫 session 日志 | `inserted":["` 的 splice 数为 0（修复前 scanned=315 hits=1） |

## 10. 证据附录（诊断阶段，2026-09-21 02:35 CST）

- 运行日志：`.dsh-data/state/restart-1789909889688.log`（进程 pid=33627，启动于 2026-09-20 21:11）
- 脏数据：`session-6faac762-d721-4942-ae9a-f6463ab7cf79` `seq=1471`，`time=1789910900746`
- 全量扫描（对每个 session 解压后匹配 `inserted":["`）：scanned=315 hits=1
- 框架事实：日志格式为可拼接的独立 zstd 帧容器（`dsh-session-persistence-jsonl` "concatenated-frame container"，每帧 checksumFlag=1）；事件信封 `{"type","seq","time","data"}`，当前最后 `seq=1481`
- 事故时序：21:28:20 第 1 次催办字符串入箱（turn 9 进行中）→ 21:34:22 turn 9 因 403 额度错误 turn/end，字符串无人 claim → 至今滞留
- 诊断窗口：w-f8006463（investor）

> 注：§4 §5 §9 与 §10 中「期望/验收/证据」为追加编号节，不改变 bug 类型必填节（复现步骤 / 根因 / 边界 / 回归）的存在性。
