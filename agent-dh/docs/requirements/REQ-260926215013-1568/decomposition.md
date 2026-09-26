# 拆分计划 · Dive 续跑与采集全量对齐 DSH Goal driver

**需求**: REQ-260926215013-1568（feature / 对齐重构）
**设计**: `docs/requirements/REQ-260926215013-1568/design/`（5 份，已确认落章）
**目标**: 让 Dive 的自动续跑与 DSH Goal round driver 同机制——只在整 agent 空闲时起一轮，
回合号走 reservation→admission，上限写终态；消除「打断正在跑的回合」与「回合数被乐观吃掉后静默停跑」。
**做法**: 新增一个框架无关的回合状态机（端口注入），`createDiveSessionDriver` 组合它，
`ReqboardDiveManager` 重写为订阅持有者；投递端口扩展出带 `source:{kind:'dive'}` 的回合消息。

## 范围与不做什么

**做**: 一个 agent 一个驱动状态（attempt / competingQueued / needsCheckpoint / requested / run / stopping）；
pre-step 竞态栅栏（进出各校验一次）；inbox 竞争让位；排队点台账检查点；`withoutInitiator` 串行化；
fail-closed teardown；回合消息带 source 与内容不变量；11 个 FR 全部落测。

**不做**: 不引入 `dsh-goal-round-driver` 依赖；不改 Goal 实体语义；不改 `stage-configs.ts` 的 maxRounds；
不重做采集/簿记半；不改「谁来把需求置 armed」（既成语义空白，本轮不碰）；无台账 schema 迁移与数据回填。

## 任务表（含依赖）

```text
T-1 契约与数据模型 ──┬─→ T-2 round 状态机 ──┬─→ T-4 会话驱动器组合 ──┐
                     │                        │                        ├─→ T-6 对齐验收单测 ─→ T-7 迁移兼容 + 回归发版
                     └─→ T-3 投递适配 ────────┴─→ T-5 Dive 服务接线 ────┘
```

| Key | 任务（业务标题） | phase | side | depends_on |
|-----|------------------|-------|------|------------|
| T-1 | 契约定死：回合来源、相位值域与驱动状态纯判定 | implement | backend | — |
| T-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | implement | backend | T-1 |
| T-3 | 投递适配：回合消息带机器可识别的来源标识 | implement | backend | T-1 |
| T-4 | 会话驱动器组合：一拍内的定序与原采集行为不变 | implement | backend | T-2 |
| T-5 | Dive 服务接线：订阅收归服务、requirement-moved 不再直接续跑 | implement | backend | T-3, T-4 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | test | backend | T-2, T-3, T-4, T-5 |
| T-7 | 迁移与兼容核查 + 回归发版 | test | backend | T-6 |

## RTM 覆盖表（任务 ↔ 需求条款）

> 机器解析口径：**每行只取「根编号」列的第一个编号**（`taskRefsFromDecomposition`），
> 故本表**一行只写一条条款**（一张卡覆盖多条 → 多行重复该卡）。

| 任务编号 | 任务标题 | 根编号 |
|----------|----------|--------|
| T-1 | 契约定死：回合来源、相位值域与驱动状态纯判定 | FR-1 |
| T-1 | 契约定死：回合来源、相位值域与驱动状态纯判定 | FR-5 |
| T-1 | 契约定死：回合来源、相位值域与驱动状态纯判定 | FR-7 |
| T-1 | 契约定死：回合来源、相位值域与驱动状态纯判定 | FR-8 |
| T-1 | 契约定死：回合来源、相位值域与驱动状态纯判定 | FR-10 |
| T-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | FR-1 |
| T-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | FR-2 |
| T-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | FR-3 |
| T-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | FR-4 |
| T-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | FR-6 |
| T-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | FR-7 |
| T-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | FR-8 |
| T-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | FR-9 |
| T-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | FR-10 |
| T-2 | 回合状态机：空闲才起轮、准入才计数、上限写终态 | FR-11 |
| T-3 | 投递适配：回合消息带机器可识别的来源标识 | FR-10 |
| T-4 | 会话驱动器组合：一拍内的定序与原采集行为不变 | FR-2 |
| T-4 | 会话驱动器组合：一拍内的定序与原采集行为不变 | FR-3 |
| T-4 | 会话驱动器组合：一拍内的定序与原采集行为不变 | FR-5 |
| T-4 | 会话驱动器组合：一拍内的定序与原采集行为不变 | FR-6 |
| T-5 | Dive 服务接线：订阅收归服务、requirement-moved 不再直接续跑 | FR-5 |
| T-5 | Dive 服务接线：订阅收归服务、requirement-moved 不再直接续跑 | FR-6 |
| T-5 | Dive 服务接线：订阅收归服务、requirement-moved 不再直接续跑 | FR-9 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | FR-1 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | FR-2 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | FR-3 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | FR-4 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | FR-5 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | FR-6 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | FR-7 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | FR-8 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | FR-9 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | FR-10 |
| T-6 | 对齐验收：11 个 FR 的可证伪单测 | FR-11 |
| T-7 | 迁移与兼容核查 + 回归发版 | FR-7 |
| T-7 | 迁移与兼容核查 + 回归发版 | FR-8 |
| T-7 | 迁移与兼容核查 + 回归发版 | FR-11 |

覆盖自检：FR-1…FR-11 每条至少被一张卡接收（无未接收条款）。

## 卡片详情（改哪些文件 / 步骤 / 验收）

### T-1 契约定死：回合来源、相位值域与驱动状态纯判定

**实现**: 新增 `src/application/dive/round-state.ts`（`DriverState`/`RoundAttempt`/`DiveRoundSource` 结构类型 +
`isDiveRoundSource`/`sameQueued`/`roundReservationValid`/`deepEqualJson`/`roundLimitFor` 纯函数）；
`src/shared/protocol.ts` 修正 `RequirementDive.phase` 为 `'idle'|'active'|'paused'`、新增 `DiveRoundSource`；
`src/application/ports.ts` 给 `AgentDeliveryPort` 增 `createRoundMessage`/`deliverMessage` 签名；
新增 `tests/dive-round-state.test.ts`。

**验收**: `npx vitest run tests/dive-round-state.test.ts` 全绿（覆盖：非 dive 来源不认、round 号必须 = roundsInStage+1、
内容不一致返回 false）；`npx tsc --noEmit -p tsconfig.json` 错误数不高于改动前基线；`grep -n "paused" src/shared/protocol.ts` 可见 phase 值域含 paused。

### T-2 回合状态机：空闲才起轮、准入才计数、上限写终态

**实现**: 新增 `src/application/dive/round-driver.ts`：`createDiveRoundDriver(ports)` 实现
`onIdle/onPreStep/onInboxInserted|Claimed|Discarded/onAgentError/onAgentDisposed/onRequirementMoved/onSessionEvent/requestDrive/teardown/whenQuiet`；
`requestDrive` 用 `ports.agents.withoutInitiator` 串 `while(requested && !stopping)` 单链；
`drive()` 按设计 §驱动状态机 7 步（含排队点 `await checkpoint()` 屏障）；`onPreStep` 前后各一次 `roundReservationValid` + `restoreOtherClaimed`；
admission 落 `dive-round-admitted`，终态落 `dive-terminal-block`，异常/检查点失败落 `dive-disarm`。新增 `tests/dive-round-driver.test.ts`（fake 端口）。

**验收**: `npx vitest run tests/dive-round-driver.test.ts` 全绿（断言：连发 3 次触发只执行 1 次驱动体；
驱动体抛错不产生未捕获异常/未处理 rejection；需求 version 变化后 pre-step 返回 reject 且同批消息被放回；
checkpoint 失败 → `activation==='disarmed'`；`roundsInStage===maxRounds` → `phase==='paused'` 且 `pausedReason==='round-limit'`）。

### T-3 投递适配：回合消息带机器可识别的来源标识

**实现**: `src/adapters/AgentDeliverer.ts` 增 `createRoundMessage`（结构复刻 `{id,role:'user',content:[{type:'text',text}],source:{kind:'dive',requirementId,revision,round}}`，
不 import `@deepseek-ai/dsh-llm`）与 `deliverMessage`（复用三态守卫，永不抛）；扩展 `tests/agent-deliverer.test.ts`。

**验收**: `npx vitest run tests/agent-deliverer.test.ts` 全绿；断言 `createRoundMessage(...).message.source` 与
`{kind:'dive',requirementId,revision,round}` 结构相等、`deliverMessage` 在 agents 不可得时返回 `delivered:false` 且不抛。

### T-4 会话驱动器组合：一拍内的定序与原采集行为不变

**实现**: 抽出 `src/application/dive/idle-capture-actions.ts`（`withAddressSection`/`milestoneReminderFor` 逐字搬移）；
`src/application/dive/session-driver.ts` 增**可选** `deps.round`（`DiveRoundDriver`），`onAgentStatus(idle)` 内按
「复位 competingQueued → 采集跑批 → requestDrive」定序，session/event 尾部调 `round.onSessionEvent`；不注入时退化为原行为。

**验收**: `npx vitest run tests/capture-hook.test.ts tests/dive-session-driver-wiring.test.ts tests/isolate-node-context.test.ts` 全绿（旧调用方无 round 端口仍与改动前一致）；`wc -l src/application/dive/session-driver.ts` ≤ 400。

### T-5 Dive 服务接线：订阅收归服务、requirement-moved 不再直接续跑

**实现**: 重写 `src/application/dive/ReqboardDiveManager.ts`：`constructor(ctx, store)`；构造内订阅
`agent/pre-step`、`agent/inbox/inserted|claimed|discarded`、`agent/error`、`agent/disposed`、`reqboard/requirement-moved`（全部委托 round 半，
成立/失败均留痕）；`reqboard/requirement-moved` 只置 `needsCheckpoint` + `requestDrive`；
暴露 `roundDriver()`/`teardown()`；删除 `shouldContinue/triggerContinuation/incrementRound/checkAndContinue`。
改 `src/index.ts`（`new ReqboardDiveManager(ctx, store)`、构造 ctx 端口、登记 teardown disposer）与
`src/wiring/pm-capture-root.ts`（注入 `round` 端口 + 订阅缺失响亮 warn）。新增 `tests/dive-manager-wiring.test.ts`。

**验收**: `npx vitest run tests/dive-manager-wiring.test.ts` 全绿（断言：7 条订阅全部成立；`requirement-moved` 后
`deliverMessage` 未被调用、agent 空闲后才投递一次；`teardown()` 后触发不再投递）；`grep -c "followup" src/application/dive/ReqboardDiveManager.ts` 为 0。

### T-6 对齐验收：11 个 FR 的可证伪单测

**实现**: 新增 `tests/dive-manager-alignment.test.ts`（文件头 `// serves: FR-1 … FR-11`），按设计 test-cases.md 的
TC-01…TC-11 逐条断言（含 FR-11 六条路径留痕断言）。

**验收**: `npx vitest run tests/dive-manager-alignment.test.ts` 输出 ≥ 11 passed、0 failed；每条 FR 至少一条断言。

### T-7 迁移与兼容核查 + 回归发版

**实现**: 核查旧台账读容错（缺 phase/activation 不驱动）、旧调用方兼容（`createDiveSessionDriver` 不传 round 仍可用）、
回滚路径（revert + relink + kickstart）；记录 tsc 基线错误数并对比；`relink-profile.py` + 重启 `:13080` 后复跑回归。

**验收**: `python3 scripts/relink-profile.py --check` 退出码 0；`npx vitest run tests/capture-hook.test.ts tests/dive-session-driver-wiring.test.ts tests/isolate-node-context.test.ts` 全绿且 `npx tsc --noEmit -p tsconfig.json` 错误数不高于基线；`curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:13080/` 输出 200。

## 批准后会发生什么

批准本计划 = 批准任务粒度、依赖与验收口径；随后自动把 T-1…T-7 落库为任务卡（DAG 按 depends_on 解析），
需求进入 implementing，由 Dive 自动执行链逐卡推进。计划要改须在拆分阶段重交（旧批准作废，需重新批准）。
