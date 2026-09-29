---
id: reqboard-dive-wake-defect
title: 需求流水线「唤醒」通道缺失 —— H4 空转 × Dive 永不介入（根因分析与修复方案）
summary: 人点头推进阶段后无人唤醒 agent 的根因与证据：闸门链 H4 无条件 skip（把唤醒委托给 Dive），而 Dive 起轮门槛 armed+active 全仓 0 命中（83/83 需求无 dive 字段），两静默叠加=静默停摆。含 session 消息级铁证、被拆通道清单（deliver 端口/适配器 + 3 个消费者）、与缺陷表 D2 的同源复发关系、判据错位（autoExecute 误用）、三层修复方案与验收口径。
type: architecture
status: living
updated: 2026-09-28
owners: [w-6cbda737]
tags: [reqboard, dive, gate-post-chain, h4-resume, defect, wake]
---

# 需求流水线「唤醒」通道缺失 —— H4 空转 × Dive 永不介入

**这页回答**：人点头确认之后，谁负责把 agent 叫起来干活？为什么没叫？怎么修？

> 调查窗口：`w-6cbda737`（session-6cbda737-2159-497d-9384-10ef3330279f）
> 现场需求：REQ-260928001915-f978《队列 DAG 真图卡片类型与可视化设计》
> 调查时间：2026-09-28｜状态：**根因已定，修复未实施**

## 0. 一句话结论

阶段推进之后，闸门后置链只完成了 H1（推进）/ H2（造包）/ H3（取词），**H4（唤醒）无条件返回 skip**；
本该接手的 Dive round driver 因起轮门槛 `armed + active` **全仓 0 命中**而永不运行。

两个静默叠加 = **阶段推进了、节点输入包也落进了对话历史，但没有任何东西叫醒 agent。**

## 1. 现象

- 人在弹框里点「确认推进到设计」→ 台账里阶段确实从 `brainstorming` 推进到 `design`；
- 设计文档一份都没写（`on_disk: false` / `registered: false`）；
- agent 自己先问了一句「需要我继续进入设计阶段，开始编写设计文档吗？」然后结束回合；
- **然后再无任何事发生** —— 直到人主动再打一句话，才又起了一轮。

用户的原话：**「dive 有 bug，没有完成整个链路。」**

## 2. 铁证（消息级，来自 session 原始日志）

数据源：`.dsh-data/sessions/--Users-yunpeng-.../session-6cbda737-2159-497d-9384-10ef3330279f/session.v3.jsonl.zstd`
（zstd 解压后 1971 条事件；事件字段 `type / seq / time / data / sourceEventSeqs / surfaceOp`）

### 2.1 那一刻的时间线（2026-09-28）

```text
01:45:02  人确认推进（reqboard_ask_confirm）
01:45:03  ask_confirm 工具返回「已确认并推进 brainstorming → design」
01:45:05  step/start (step 12)            ← agent 在同一回合里继续
01:45:19  assistant/message               ← agent 最后一句：
            「…需要我继续进入设计阶段，开始编写设计文档吗？」
01:45:19  turn/end {"kind":"completed"}   ← 回合自己结束了
01:45:19  user/message id=pmboard-node-input-1        ← 输入包落【历史】（+129ms）
            source={kind:"plugin", plugin:"dsh-pmboard", form:"notice"}
01:45:19  user/message id=pmboard-node-input-1        ← 又落一份（+25ms）⚠️ 见 §9.2
          ↓↓↓ 34.5 秒，零事件 ↓↓↓
01:45:54  agent/inbox/spliced source={kind:"user"}    ← 【用户自己打字】
            「dive模式没有干活，这是bug吗」
01:45:54  turn/start  turn=20                          ← 才起的轮
```

### 2.2 全会话投递来源统计（决定性的一行）

```text
=== 全会话 agent/inbox/spliced 插入来源分布 ===
   29  kind=user      ← 全部 29 条都是用户自己打的
    0  kind=dive
    0  kind=plugin
```

本会话共 **27 个 `turn/start`**，而 inbox 插入来源 **100% 是 `kind=user`**。

> 判据：机器起轮必须经 `agent.followup()`，在会话日志里表现为一次 `agent/inbox/spliced`
> （source 为 `dive` 或 `plugin`）。**0 条即意味着：这个会话没有任何一轮是机器发起的。**

### 2.3 agent 当时到底有没有指令？有

step 12 那次的 system prompt 共 **116591 字符**，design 阶段纪律**全文在里面**：

```text
## 项目看板（reqboard · 本窗口 session-6cbda737 已绑定需求）
- REQ-260928001915-f978《队列 DAG 真图卡片类型与可视化设计》当前状态：design

# 设计（design）· 轻档
- [ ] 落盘：写进 docs/requirements/REQ-xxxxxx/design/ 目录…
- [ ] 下一步：decomposing —— 用 reqboard_ask_confirm(target=artifact, kind=design) 交棒
```

关键词命中：`design` ×5、`设计文档` ×5、`reqboard_submit` ×5。
**交付物、目标目录、下一步命令，全都在它眼前** —— 它并不需要问许可（见 §9.1）。

## 3. 机制：写历史 ≠ 起轮

这是本次故障最容易被误读的一点。节点输入包**确实送达了**，只是它送的是"历史"，不是"唤醒"：

| 动作 | 作用 | 实现 | 现状 |
|---|---|---|---|
| **写历史** | 把节点输入包塞进对话历史（并被 agent 下次请求读到） | `append('user/message', 输入包)` + `surfaceOp replace(start..end)` | ✅ 还活着 |
| **起轮** | 真正启动一个 agent turn 去干活 | `agent.followup(msg)`（经投递端口） | ❌ 已被删除 |

- 写历史：agent-dh/packages/web/dsh-pmboard/src/application/use-cases/IsolateNodeContext.ts、agent-dh/packages/web/dsh-pmboard/src/adapters/NodeIsolationAdapter.ts
- 起轮：agent-dh/packages/web/dsh-pmboard/src/adapters/AgentDeliverer.ts（`deliver()` 已删）

**所以"包在你眼前、机器却没动"不是错觉，是这两个动作被拆散了。**

## 4. 根因链（四环，逐环可核）

| # | 环节 | 代码位置 | 事实 |
|---|---|---|---|
| 1 | **H4 无条件让位** | agent-dh/packages/web/dsh-pmboard/src/application/gate/handlers/h4-resume.ts（整个 `run()` 只剩一行 return skip） | 注释理由：「所有需求都在Dive模式下运行」——**前提为假** |
| 2 | **Dive 起轮门槛 = armed+active** | agent-dh/packages/web/dsh-pmboard/src/application/dive/round-state.ts:127（`isDrivableRequirement`）；round-driver.ts:267 | 两者必须同时成立才起轮 |
| 3 | **全仓没有任何代码写 armed** | 生产代码里 `activation` 只有 `disarmed` 的写入（round-driver.ts:116、ClearPause.ts:62/67） | 台账实测：83 个需求 **0 个有 `dive` 字段**，0 个 armed |
| 4 | **于是无人唤醒** | 台账闸门链原文：`G1：h1-advance=ok；h2-compact=ok；h3-inject=ok；h4-resume=skip（dive_handles_resume）` | 里程碑催办同样被拦：台账写明「未 armed+active → **本轮不投递会话**」 |

环节 3 的实测输出：

```text
需求总数: 83
有 dive 字段的: 0
armed 的: 0
activation 分布: {'<无dive>': 83}
```

同时，`drive()` 被拦下的那一行是**静默**的（无 log、无台账 comment）——
对比同文件 `terminalBlock()` 会写 comment。**门口既没人开，也没人喊**，这才是它长期未被发现的原因。

## 5. 引入点：e084ada1 的一次越界拆除

- **提交**：`e084ada1`（2026-09-27 21:38:34，窗口 `w-3936d77f` / Lead 托管提交）
- **自称范围**：REQ-260927202051-f6df 的「读方改造（TaskStore 迁移）」
- **实际动作**：把整条**非 Dive 投递能力**连端口带适配器一起掏空

### 5.1 被拆清单（这才是完整破坏面）

| # | 白名单文档要求 | 现状 | 证据 |
|---|---|---|---|
| — | `AgentDeliveryPort.deliver()` | **接口被掏空**（注释「deliver() 已删除」） | agent-dh/packages/web/dsh-pmboard/src/application/ports.ts:292-294 |
| — | `AgentDeliverer.deliver()` | **方法被删除** | agent-dh/packages/web/dsh-pmboard/src/adapters/AgentDeliverer.ts:4-6 |
| 1 | 闸门链 H4 resume ｜ **保留 deliver()** | 无条件 `skip` | agent-dh/packages/web/dsh-pmboard/src/application/gate/handlers/h4-resume.ts |
| 2 | pending-confirm wake ｜ **保留 deliver()** | `wake()` 变**空函数**（算了 `text` 变量后丢弃） | agent-dh/packages/web/dsh-pmboard/src/application/internal/pending-confirm.ts:121-129 |
| 3 | 失败告警 FailureAlert ｜ **保留 deliver()** | **只写日志**，不再投递会话 | agent-dh/packages/web/dsh-pmboard/src/adapters/FailureAlert.ts:4-6 |
| 4 | FR-14 弹框降级投递 ｜ 保留 | 注释还在，能力已无 | agent-dh/packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts:150-162 |

而替代品（round 半的 `deliverMessage`）**全仓只有一个调用点**：
agent-dh/packages/web/dsh-pmboard/src/application/dive/round-driver.ts:230 —— 且它永远不触发。

### 5.2 与设计文档**直接矛盾**（同一天写下的）

`docs/architecture/reqboard-dive-mode.md` 的「投递白名单」节：

- :187 目标态表格：`闸门链 H4 resume | deliver() | 保留：人点头后的唤醒`
- :191 不变量：**「不得加 `if (!armed) return` —— 全仓至今 0 个需求开过 armed，一旦被门控，流水线立刻停摆」**

**文档知道没人 armed，实现却以「全都在 Dive 下跑」为由删掉了唤醒路。**
而 `h4-resume.ts` 自己就是 :187 那行说"保留"的东西 —— 且它的注释日期写成占位符 `2026-XX-XX`，说明该前提**从未被核实**。

## 6. 为什么 11 条测试没拦住

agent-dh/packages/web/dsh-pmboard/tests/e2e/dive-full-flow.test.ts 里 **11 条 `expect(true).toBe(true)` 占位断言**，
覆盖组正是「armed 锁机制」「解锁机制」「自动续跑」——**没有一条断言过 armed 路径是否真的有人开**。

> 于是"是否有人上膛"这个前提**永远不会被任何测试证伪**。
> 本次故障的可复现判据（见 §11）应直接写成断言，而不是留占位。

## 7. 同源复发：缺陷表 D2 已经记过同一句话

`docs/architecture/reqboard-pipeline-flow.md` 的缺陷落点索引（D1–D13）：

| 缺陷 | 节点 | 一句话 | 修复状态 |
|---|---|---|---|
| D1 | decomposing | 批准计划不落库（createdCount=0） | ✅ **批准动作内同步落库** |
| **D2** | decomposing | **委托 Dive 但无人监听 → 静默停滞零告警** | ✅ pausedReason + 告警 + 系统评论 |

**D2 就是同一个 bug 的第一次发作**，发生在 decomposing 节点；当时的修法是
「**这处别再委托 Dive，改成就地同步做**」（D1 同款），**根因（H4 skip + 无人上膛）原样留着**。

> **规律**：「把活委托给 Dive」是本仓的系统性缺陷模式。
> D1/D2 在 decomposing 处**就地绕过**了它，而 H4（design/decomposing/brainstorming 的唤醒）
> **没有被绕过** → 洞留着 → 在 design 节点复发。
> 两次记的是同一句话，因为每次都被当作单点缺陷修掉。

时间上也对得上：`e084ada1` 于 2026-09-27 21:38 拆除唤醒通道，
**本需求 2026-09-28 00:19 才创建 —— 它从出生起就带着这个洞。**

## 8. 判据错位：为什么 `armed` 是错的轴

### 8.1 `autoExecute` 把两件正交的事绑成一件

agent-dh/packages/web/dsh-pmboard/src/application/dive/stage-configs.ts 的 design 配置：

```ts
design: { requiresConfirmation: true, autoExecute: false, maxRounds: 10 }
```

字段注释写的是 `autoExecute: 是否自动执行任务（implementing 阶段适用）`——
**作者把"出口有人工门"误当成了"本阶段没有可自动推进的工作"**。两件事是正交的：

| 问题 | design | decomposing | implementing | 该挂什么 |
|---|---|---|---|---|
| **本阶段有可自动推进的工作吗？** | **有**（写文档+提交+请确认） | **有**（写计划+提交待批） | 有 | ← **自动续跑该挂这个** |
| **推进到下一阶段要人点头吗？** | 要 | 要 | 不要（除验收） | 门的属性，**不决定唤醒** |

### 8.2 `requiresConfirmation` / `isAutoExecute` 是死代码

`stage-configs.ts:111/118` 定义了这两个函数，**全仓 0 处调用**（grep 只有定义处）——
驱动体只用到了 `maxRounds`。也就是说**"阶段感知"目前只存在于文档里**。

### 8.3 另外三处判据缺陷（发现于同一轮排查）

| 缺陷 | 位置 | 后果 |
|---|---|---|
| `bound()` 取**数组第一个**、不筛状态、不取最新 | agent-dh/packages/web/dsh-pmboard/src/application/dive/round-driver.ts:96 与 :210 | 73 个窗口里 **8 个**绑了多个需求（最多 3 个）。实测窗口 `session-8375f8a6` 同时有 archived #53 与 brainstorming #55 → 一旦上膛，驱动的是**已归档的那个** |
| `blocked` 从未被检查 | dive 目录内 grep `blocked` = 0 命中 | 被阻塞的需求照样会被驱动 |
| `roundsInStage` 不随阶段归零 | 上膛写点 | 各阶段上限差极大（draft=1 / decomposing=5 / implementing=100），跨阶段累计必撞上限 |

## 9. 次生与附带发现

### 9.1 【行为纪律｜非代码】agent 手握阶段纪律仍问许可

§2.3 已证明：design 阶段纪律（含"落盘到 design/ 目录"与"下一步"）就在 step 12 的 system prompt 里，
agent 却在 `turn/end` 前回了「需要我继续进入设计阶段，开始编写设计文档吗？」。

- 它是本次停顿的**直接触发者**（回合自己结束了，才需要唤醒）；
- 但它是**独立缺陷**：纪律已在 prompt，本仓既有约定是「状态由窗口自己维护，不必等人点按钮」。

### 9.2 【待查】节点输入包被"套压缩"了两次

本会话共 8 次输入包注入，前 7 次正常（`replace(a..b)` 覆盖上一段，区间连续），**第 8 次（正好是 design 这次）异常**：

| 事件 | surfaceOp | 长度 | sourceEventSeqs |
|---|---|---|---|
| 01:36:10（前一次，正常） | `replace(1047..1310)` | 6087 | 上游历史 |
| **01:45:19.942** | `replace(1314..1428)` | 11127 | 30 个源事件 |
| **01:45:19.967** | **`replace(1432..1432)`** | 10440 | **`[1432]`** ← 指向刚插入的那条包自己 |

第二次压缩把第一次刚插入的输入包当成了"待遗弃的历史"，又生成了一份（正文不同：11127 → 10440），
典型**压缩套压缩**。**根因未定**（疑为同一节点被结算两次，或 H2 与遗留隔离路径各跑一次），
本页不作为结论，登记为独立待查项。

### 9.3 【已登记】D13 在本需求也有实例

台账里有两条「里程碑催办」指向 `kind=notes`（rtm-lifecycle.yml / rtm-brainstorming.yml），
与缺陷表 **D13**（提醒把过程产物当门禁产物，命令与门不匹配）一致 —— 同一片区域的第三处问题。

## 10. 修复方案（待立项实施）

### 第 1 层 · 恢复通用投递通道（救火，7 处）

| # | 文件 | 动作 |
|---|---|---|
| 1 | agent-dh/packages/web/dsh-pmboard/src/application/ports.ts:288-294 | `AgentDeliveryPort` 恢复 `deliver(windowKey, message): DeliveryResult` |
| 2 | agent-dh/packages/web/dsh-pmboard/src/adapters/AgentDeliverer.ts | 恢复 `deliver()`（构造 **`source.kind='plugin'`** 的消息后 `followup`；**不可用 `'dive'`**，否则会被 `onPreStep` 当回合预留校验并 reject） |
| 3 | agent-dh/packages/web/dsh-pmboard/src/application/gate/handlers/h4-resume.ts | 整份还原：`git show e084ada1^:agent-dh/packages/web/dsh-pmboard/src/application/gate/handlers/h4-resume.ts`（其 6 项依赖已核全部在位） |
| 4 | agent-dh/packages/web/dsh-pmboard/src/gate-wiring.ts:85 | `createH4ResumeHandler({ delivery: deps.deliverer, plugin: deps.plugin })`（`deps.deliverer` 已在 `GateChainDeps` 内，无需新接线） |
| 5 | agent-dh/packages/web/dsh-pmboard/src/application/internal/pending-confirm.ts:121-129 | `wake()` 恢复投递（人在弹框作答后必须通知 agent 去取回执） |
| 6 | agent-dh/packages/web/dsh-pmboard/src/adapters/FailureAlert.ts | 二选一并让文档与代码一致：**(a)** 恢复会话投递；或 **(b)** 明确降级为"日志+看板"并同步改白名单文档 |
| 7 | agent-dh/packages/web/dsh-pmboard/src/wiring/pm-capture-root.ts:150-162 | 修掉那段描述不存在能力的**假注释** |

> ⚠️ **审阅红线**：还原后**绝不允许**给 H4 加 `if (!armed) return` —— 那就是本页记录的故障本身。

### 第 2 层 · 把"静默"改成"响亮"

- H4 投递失败 → `degraded` + reason（原文已具备，还原即得）；
- `disarm()` 补写台账 comment（现仅 `log.warn`）；
- **新增护栏测试**：断言「闸门确认后 H4 必须产生**恰好一次**投递调用」——把"不许再改成 skip"变成 CI 红线。

### 第 3 层 · 治本：判据从"有没有上膛"换成"有没有欠账"（含 B 组前提）

**核心原则 —— 默认值方向反转**：
现在「默认不动，除非有人上膛」→ 失效形态 = **静默停摆**；
反转后「默认按阶段动，除非显式暂停」→ 失效形态 = **多跑一轮（喧闹可见）**。

判据候选：

| 判据 | 能修本页症状 | 刷屏风险 | 备注 |
|---|---|---|---|
| `armed + active`（现状） | ❌ 恒 false | — | 门开着没人上膛 |
| `isAutoExecute(status)` | ❌ **design 的 autoExecute=false** | 低 | 修不了本页症状 |
| **「本节点欠账」**（推荐） | ✅ 覆盖所有可注入阶段 | 低（销账即停） | 欠账信号**系统已算出**，见下 |
| `armed` 降级为**否决开关**（默认允许） | ✅ | 低 | 与上一行并用 |

**推荐判据**：`isDrivableRequirement := isOpenRequirement(status) && !blocked && 本节点有欠账`

「欠账」是现成的、系统已经在返回的事实（无需新状态）：

| 欠账信号 | 出处 |
|---|---|
| `design_docs[].on_disk / registered / confirmed` | `reqboard_status` |
| `traceability_chain.*_coverage{status, gaps}` | `reqboard_status` |
| `milestoneReminderFor`（产物登记 N 分钟未确认） | agent-dh/packages/web/dsh-pmboard/src/application/dive/session-driver.ts:298 |

**请求点必须挪到"输入包落地之后"**：当前 idle 拍的那次 `requestDrive` 发生在 append 之前
（结算走 `setImmediate` 异步边界 —— agent-dh/packages/web/dsh-pmboard/src/application/internal/node-settlement.ts:202 的 D-17 约束），
应改为在 `execute()` 内 chain 跑完之后请求一次驱动。

**B 组前提（必须先做，否则上膛会引入新事故）**：

| 序 | 动作 | 不做会怎样 |
|---|---|---|
| B2 先做 | `bound()` / `requirementFor()` 改 `filter(isOpenRequirement).sort(updatedAt desc)[0]` | 上膛 = 驱动归档需求（8/73 窗口已具备条件） |
| B3 | 上膛同一次 mutate 写 `roundsInStage: 0` | 跨阶段累计撞上限 |
| B4 | `disarm()` 写台账 comment | 又一处静默 |
| B5 | 判据纳入 `!blocked` | blocked 需求照样被驱动 |
| B1 | 上膛判据真的调用 `isAutoExecute()` | 字段继续是死代码 |

### 与 H4 的分工（不是二选一）

| | 触发 | 时效 | 可靠性 |
|---|---|---|---|
| **H4 投递**（第 1 层） | 人点头（事件驱动） | 立即 | 会丢（投递失败/重启/订阅未成立） |
| **idle 欠账兜底**（第 3 层） | agent 空闲 + 有欠账（状态驱动） | 慢一拍 | **能自愈** |

## 11. 验收口径（可执行）

```bash
# ① 静态：依赖符号在位
cd agent-dh && npx tsc -p packages/web/dsh-pmboard --noEmit

# ② 反回归：占位断言换成真断言（至少 3 条）
npx vitest run packages/web/dsh-pmboard/tests/e2e/dive-full-flow.test.ts
#   必含：「闸门确认 → 恰好 1 次投递调用」

# ③ 构建 + dist 产物校验（本包从 dist 加载，光重启无效）
pnpm build
grep -c "dive_handles_resume" packages/web/dsh-pmboard/dist/index.mjs   # 期望 0
grep -c "AgentDeliveryPort"  packages/web/dsh-pmboard/dist/index.mjs    # 期望 >0

# ④ 真机（唯一能证明修好的证据）
#    在看板点一次「确认推进」→ 观察会话：
#    a) 出现一条唤醒消息（含「进入本阶段的第一步」）
#    b) agent 自主开工，而不是等人开口
#    c) 会话日志中 agent/inbox/spliced 首次出现 source.kind != 'user'
```

**④ 不可省**。源码级绿灯不能证明线上行为 —— 本仓已踩过两次（dist 陈旧、dump-config 假阴性）。

## 12. 未核实边界（诚实清单）

- §9.2 输入包「套压缩」的**根因未定**，只有现象证据（两次 replace 的区间与 sourceEventSeqs 差异）。
- §4 环节 3「全仓无 armed 写入」是**当前 HEAD 的静态结论**（grep 生产代码 + 台账 83/83）；未追查是否有已删除的历史上膛路径之外的外部写入（如脚本/看板 API）。已查：client 侧 0 处 `dive` 引用。
- §8.3 的三处判据缺陷是**代码级发现**，未构造线上复现。
- 本页未修改任何代码；第 10 节是方案，不是已完成的修复。

## 13. 变更记录

| 日期 | 变更 | 窗口 |
|---|---|---|
| 2026-09-28 | 首版：根因定位 + session 铁证 + 被拆通道清单 + 三层修复方案 | w-6cbda737 |
