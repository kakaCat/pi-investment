---
req_id: REQ-260926215013-1568
kind: design
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11
---

# 架构设计 · Dive 两半驱动器对齐 DSH Goal driver

**需求**: REQ-260926215013-1568（feature / 对齐重构）
**基线**: `@deepseek-ai/dsh-goal-round-driver@0.1.6-alpha.2`（`lib/index.js` + `README.zh.md`）

## 目标与范围 «serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11»

**代码层目标（一句话，可证伪）**：Dive 的自动续跑只在「整 agent 空闲且无竞争输入」时经 `withoutInitiator` 串行起一轮，
回合号走 **reservation → admission**（只有回合消息真正进入 history 才 `roundsInStage + 1`），
回合上限写 **终态** `dive.phase='paused' + pausedReason='round-limit'`；
所有竞态（revision 变、人类插话、陈旧内容、卸载）在 `agent/pre-step` 被 fail-closed 拒绝且**不计数**。

可证伪：`tests/dive-manager-alignment.test.ts` 的 11 组断言（每条对应一个 FR）全过；本轮只改机制，不改台账唯一事实源。

本设计**照其形自实现** Goal driver 的机制，**不引入** `dsh-goal-round-driver` 依赖（本机未挂该包，profile 只有 tool-goal/command-goal）。

## 现状与偏差 «serves: FR-2, FR-3, FR-6, FR-7, FR-8»

三处会真实出错 / 已实证失效的点：

1. **会打断正在跑的回合**：`ReqboardDiveManager` 挂在 `reqboard/requirement-moved` 上直接 `followup()`，
   窗口正忙也照发。Goal 的铁律是 *A round starts only at whole-agent idle*。
2. **回合数被乐观吃掉 + 静默停跑**：`incrementRound` 在 `followup()` 之后**无条件** +1（投递失败/被拒也算一回合），
   到上限只打一行 `warn` 就 `return false` —— 无终态、无告警、无 comment。
3. **续跑路实际是死代码（本次核对新增）**：`getActiveRequirement` 读 `(this.ctx as any).reqboard?.store`，
   但全仓**没有** `reqboard` 这个 Cordis 服务（`ReqboardStore` 是 index.ts 里的局部变量），
   且 manager 是 `new ReqboardDiveManager(ctx)` 手工构造（`static inject` 不生效）→ `store` 恒 undefined，
   `requirement-moved` 事件永远 `return`。这与「Dive 莫名其妙不跑了」的表象一致，必须一并修（FR-6 的接线前提）。

`session-driver.ts`（采集/簿记半）已于 2026-09-26 对齐驱动点（`agent/status === idle`），本次**只增量补纪律**，不重做采集。

## 组件与依赖方向 «serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11»

依赖方向不变（`application` 只依赖 `domain`/`shared` 的类型与端口，禁 `node:`/`@deepseek-ai/*` 运行时 import）。

| 文件 | 动作 | 职责 |
|------|------|------|
| `application/dive/round-state.ts` | 新增 | 纯数据契约与判定：`DriverState`/`RoundAttempt`/`DiveRoundSource`、`isDiveRoundSource`、`sameQueued`、`roundReservationValid`、`deepEqualJson`、`roundLimitFor` |
| `application/dive/round-driver.ts` | 新增 | **Goal 对齐状态机**：`attempt/competingQueued/needsCheckpoint/requested/run/stopping`、`drive()`、串行化、teardown、全部 FR 的可观测留痕 |
| `application/dive/session-driver.ts` | 修改 | 采集/簿记半保持不变；`createDiveSessionDriver` 组合 round 半，暴露 `onPreStep/onInbox*/onAgentError/onAgentDisposed/onRequirementMoved/teardown/whenQuiet`；`onAgentStatus(idle)` 内定「复位 → 采集跑批 → 请求驱动」次序 |
| `application/dive/idle-capture-actions.ts` | 新增 | 从 session-driver 抽出 `withAddressSection`/`milestoneReminderFor`（腾出 ≤400 行尺寸门禁余量，纯函数逐字搬移） |
| `application/dive/ReqboardDiveManager.ts` | 重写 | **Dive 服务**：持有全部订阅（session/event、agent/status、agent/pre-step、agent/inbox/*、agent/error、agent/disposed、reqboard/requirement-moved）；持 `store`；`requirement-moved` 只置检查标志并请求一次驱动；不再直接 followup |
| `application/ports.ts` | 修改 | `AgentDeliveryPort` 增 `createRoundMessage` / `deliverMessage` |
| `adapters/AgentDeliverer.ts` | 修改 | 唯一投递实现新增 round 消息构造（`source:{kind:'dive',…}`），沿用结构复刻（不 import `@deepseek-ai/dsh-llm`） |
| `wiring/pm-capture-root.ts` | 修改 | 组装时注入 `round` 端口；新增订阅失败「响亮」警告 |
| `index.ts` | 修改 | `new ReqboardDiveManager(ctx, store)`；构造 ctx 端口（agents/store/now/logger）注入 round；登记 teardown disposer |
| `shared/protocol.ts` | 修改 | `RequirementDive.phase` 值域修正为 `'idle'\|'active'\|'paused'`；新增 `DiveRoundSource` 结构类型 |

## 驱动状态机与事件流 «serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-9, FR-10»

**一个 agent 一个 `DriverState`**（内存态，不落盘）。订阅 → 处理函数（全部由 manager 持有、委托 round 半）：

| 宿主事件 | 处理 | 效果 |
|----------|------|------|
| `agent/status === 'idle'` | `onIdle` | `competingQueued=false` → 采集跑批 → 若 `attempt.cancelled` 则终态暂停该需求 → `requestDrive` |
| `agent/pre-step`（waterfall） | `onPreStep` | 前后各校验一次 `roundReservationValid`；不成立 → 放回同批消息 + `reject` |
| `agent/inbox/inserted` | `onInboxInserted` | 非本回合消息（且落在 `nextTurn`）→ `competingQueued=true`；`queued` 的 attempt 标 `stale` |
| `agent/inbox/claimed` / `discarded` | `onInboxClaimed/Discarded` | 本回合消息 → `phase='claimed'` / `cancelled=true` |
| `session/event: user/message` | `onSessionEvent` | `data.id === attempt.messageId` → `phase='admitted'` 且 `roundsInStage+1`（恰好一次） |
| `session/event: turn/end` | `onSessionEvent` | `max-tokens` → 解除武装；`aborted` → 在飞则 `cancelled`，否则解除武装 |
| `agent/error` / `agent/disposed` | `onAgentError` / `onAgentDisposed` | 解除武装 / 删除该 agent 状态 |
| `reqboard/requirement-moved` | `onRequirementMoved` | 只置 `needsCheckpoint=true` + `requestDrive`（**绝不直接 followup**） |

**idle 一拍内的定序（关键）**：先复位 `competingQueued`，再跑采集（可能注入阶段纪律 → 同步触发 `inbox/inserted` 又置位），
最后 `requestDrive`。`drive()` 首行同步复查 `readyToDrive`，因此采集刚排入的竞争输入会让本拍**让位**，留到下一个 idle。

**`drive(state)` 流程（逐条对齐 `lib/index.js:103-164`）**：

1. `!readyToDrive` → 返回（fiber active ∧ `!stopping` ∧ `agents.get(id)===state.agent` ∧ `status==='idle'` ∧ `!competingQueued`）；
2. `needsCheckpoint` → 置 false、`await checkpoint()`；失败 → `warn` + 解除武装 + 返回；await 后 `readyAfterCheckpoint` 不成立 → 返回；
3. 已有 `attempt` → 清预留、置 `needsCheckpoint`/`requested`、返回（下一拍重来，不叠加执行）；
4. 取绑定需求：无 / 非 `armed` / `phase!=='active'` → 返回；
5. **FR-3 排队点屏障**：`await checkpoint()`（兑现「排队前必须先落盘」）→ 复查 `readyAfterCheckpoint` 与需求 revision/phase；
6. `roundsInStage >= roundLimitFor(req.status)` → 写终态 `phase='paused'+pausedReason='round-limit'` + comment + 单次 `warn`，返回（此后不再判定/起轮）；
7. `round = roundsInStage + 1`；`createRoundMessage({requirementId, revision, round, text})` → 登记 `attempt{phase:'queued',...}` → `followup(message)`；
   抛错 → 清 attempt、`warn` + 解除武装（FR-4 口径：不冒泡）。

**串行化（FR-4）**：`requestDrive` 只置 `requested`；`state.run ??= withoutInitiator(async () => { while (requested && !stopping) { requested=false; await drive() } })`；
`run` 结算后 `retire`（清 `run`，若又 `requested` 且未 stopping 再起）。驱动体异常一律 `warn` + 解除武装。

## 五条纪律落点 «serves: FR-1, FR-2, FR-3, FR-4, FR-5»

| 纪律 | 机制 | 落点 |
|------|------|------|
| 竞态栅栏 | pre-step 前后 `roundReservationValid` + `restoreOtherClaimed` + `reject` | `round-driver.ts:onPreStep` |
| 竞争让位 | `agent/inbox/inserted` → `competingQueued`；idle 复位 | `round-driver.ts:onInboxInserted/onIdle` |
| 耐久检查点 | 排队点 `await` 台账写队列排空（`store.read(()=>undefined)`）；失败解除武装 | `round-driver.ts:checkpointStep` + `ports.checkpoint` |
| 驱动串行化 | `requested` 标志 + 单 `run` 链 + `withoutInitiator` | `round-driver.ts:requestDrive` |
| teardown fail-closed | 先 `stopping=true` 关准入，再解除武装 + 取消在飞（cause=`parent`）+ 等 `run`/agent 静默 | `round-driver.ts:teardown` + `index.ts` disposer |

> **落地说明（对需求边界的诚实标注）**：需求「做什么 §1」把 5 条纪律记在 `session-driver.ts` 名下。由于它们是**回合预留的机制**，
> 而 `session-driver.ts` 已 397/400 行（尺寸门禁），故实现落在同一 driver 对象的兄弟模块 `round-driver.ts`，
> 由 `createDiveSessionDriver` 组合后对外暴露——「一个状态机 + 两路订阅」的形状不变，且避免两个文件写同一个状态。

## 不改什么 / 边界 «serves: FR-6, FR-7, FR-8»

- **不加依赖**：不改 `config/cordis.yml` / bundle，不把 `dsh-goal-round-driver` 挂进 profile。
- **台账唯一事实源**：需求/任务状态仍只存 `dsh-reqboard.json`，不搬进 Goal 实体；goal/session 服务非必需（`inject` 保持 `['agents','reqboard']`，本轮不需要 goals/sessions）。
- **阶段配置语义不变**：`stage-configs.ts` 的每阶段 `maxRounds` 保留，作为 FR-8 上限来源（Goal 无配置，此处是合理适配）。
- **采集半不动**：`session/event` 的 user/message、tool/call、turn/end 簿记行为逐字保持（回归锁定）。
- **arming 仍非本需求范围**：全仓至今无人把 `dive.activation` 置 `armed`，驱动器在该状态下自然静默；本需求不改这个既成语义。

## 迁移与兼容 «serves: FR-5, FR-8, FR-11»

- **无台账 schema 迁移**：唯一类型变更是 `RequirementDive.phase` 值域由「阶段名联合」修正为 `'idle'|'active'|'paused'`（与 `docs/architecture/reqboard-dive-mode.md` 及 FR-6/FR-8 一致）；无写者曾写入阶段名态，故**无需回填脚本**。
- **存量记录**：缺 `phase`/`activation` 的需求读出即 `!== 'active'` → 不驱动（与今天的静默一致，不放大行为）。
- **向后兼容（对测试与脚本）**：`DiveSessionDriverDeps.round` **可选**——不注入时 driver 退化为纯采集/簿记（现有 `capture-hook`/`isolate-node-context`/`interruption-checkpoint` 全绿），并留一行 info 说明续跑未启用。
- **灰度开关**：无新增配置项；round 半的存在与否即开关（组合根是否注入 `round` 端口）。
- **回滚路径**：`git revert` 本次提交 → `python3 scripts/relink-profile.py` → `launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`（`:13080`）。

## 风险与缓解 «serves: FR-1, FR-4, FR-5»

1. **行为变更**：续跑由「状态推进即触发」改为「空闲才起轮」。某窗口长期不空闲时续跑推迟——**这是期望行为**（人类工作优先），
   但须写清「什么时候仍会跑」（见 use-cases.md §什么时候仍会跑）。
2. **并发写**：`ReqboardDiveManager.ts`/`session-driver.ts` 近期被多窗口改动。实施前必须取最新内容、按文件认领，禁止整文件覆盖。
3. **尺寸门禁**：`session-driver.ts` 397 行，须先抽出 `idle-capture-actions.ts` 再做增量；新文件均须 ≤400 行。
4. **线上生效**：改动落在 `:13080` 运行实例，须 relink + 重启 + 复跑回归才生效。
