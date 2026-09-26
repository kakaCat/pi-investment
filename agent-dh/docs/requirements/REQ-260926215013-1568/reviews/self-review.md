# 自评审报告 · Dive 对齐 DSH Goal driver

**需求**: REQ-260926215013-1568
**评审人**: 实施窗口（session-c5ea210f）
**日期**: 2026-09-26

## 1. 设计 ↔ 实现逐条对照（FR-1…FR-11）

| FR | 设计要求 | 实现落点 | 验证 |
|----|----------|----------|------|
| FR-1 | pre-step 前后各校验一次；不成立 reject 并把同批已认领消息放回 | `round-driver.ts:onPreStep`（前/后 `roundReservationValid` + `restoreOtherClaimed`） | TC-01 / T-2 单测 |
| FR-2 | inbox 竞争让位；idle 复位 | `onInboxInserted`（competingQueued + stale）、`onIdle` 复位 | TC-02 / TC-11 |
| FR-3 | 排队前落盘；await 后重查；失败解除武装 | `drive()` 排队点 `await checkpoint()` 屏障（两处） | TC-03 |
| FR-4 | withoutInitiator 串行；合并触发；异常不冒泡 | `requestDrive` + `run.then(retire, …)` | TC-04 |
| FR-5 | teardown 关准入 → 解除武装 → 取消在飞 → 等静默 | `teardown()` + 全局 `stopped` | TC-05 |
| FR-6 | 只在 idle 起轮；requirement-moved 只置标志 + 请求 | `readyToDrive`、`onRequirementMoved` | TC-06 |
| FR-7 | 只有进入 history 才计数；reject/discard/stale 不计数 | `onSessionEvent` user/message → `persistAdmission`（幂等） | TC-07 |
| FR-8 | 上限写终态 paused + round-limit（含上限与阶段）+ 一次 warn | `terminalBlock` | TC-08 |
| FR-9 | max-tokens → 解武装；aborted 已认领 → 标 cancelled + 空闲暂停；error/disposed 收尾 | `onSessionEvent` turn/end 分支、`onAgentError/onAgentDisposed`、`pauseAborted` | TC-09 |
| FR-10 | 回合消息带 source；只有逐字一致才认领 | `protocol.ts:DiveRoundSource` + `AgentDeliverer.createRoundMessage` | TC-10 |
| FR-11 | 每条路径都有结构化留痕，禁止静默 | 起轮 info / 拒绝 warn / 让位 debug / 检查点 warn / 终态 warn+comment / teardown info | TC-11 |

**覆盖结论**：11/11 有实现落点与可证伪断言；`tests/dive-manager-alignment.test.ts` 一 FR 一断言。

## 2. 与设计的偏差（3 条，均为落地细化，未改契约语义）

1. **投递端口用子类型而非扩父接口**：设计写"扩 `AgentDeliveryPort`"，实现改为新增 `DiveRoundDeliveryPort extends AgentDeliveryPort`。理由：直接扩父接口会同时打红既有实现与 6 处测试替身（T-1 验收要求"tsc 错误数不高于基线"）。
2. **5 条纪律落在 `round-driver.ts` 而非 `session-driver.ts` 正文**：设计已标注该权衡（session-driver 397 行贴尺寸门禁）；`createDiveSessionDriver` 通过可选 `deps.round` 组合，形状仍是"一个状态机 + 两路订阅"。
3. **预约簿记以 `attempt` 保留在 admission 之后**（对齐 Goal），下一次空闲的 `drive()` 才清理并重新排队。

## 3. 自测发现并修复的缺陷（2 条真实缺陷）

1. **teardown 后仍可起轮**：teardown 清空状态表，之后新触发会 `stateFor` 重建一个 `stopping=false` 的新状态 → 违反 fail-closed。修复：加驱动级全局 `stopped`，`requestDrive` 一律拒绝。
2. **disarm 自身可能二次抛**：`disarm` 查需求失败时会从 catch 块内再抛，冒泡进事件循环 → 违反"绝不冒泡"。修复：需求查询加保护，失败只 warn 返回。

两条都由 T-2 单测抓出（`tests/dive-round-driver.test.ts`）。

## 4. 未决与风险（如实报出，不静默）

- **后台实施链仍不可用**：`useCaseDeps.jobs`（JobsPort）在组合根**未装配**，故 `advanceRequirement` 对"自动执行链"仍返回 `dispatched:false`。这是本需求范围外的既有缺口（同一根因也是本次"自动开跑失败"的一环）；本次为解阻塞另开了看板 `POST req/decompose` 恢复入口。建议单独立项补 JobsPort 适配。
- **尺寸门禁基线本就是红的**：`content-gate-wiring.ts 552`、`content-trace.ts 481`、`AdvanceChain.ts 462`、`Decompose.ts 427`、`IsolateNodeContext.ts 411`、`http/routers/requirements.ts 440`、`index.ts 410` 超 400 行。其中后三者含本次为排障新增的代码（Decompose 恢复 427、requirements 路由 440、index 410）；新增的 4 个源文件均 ≤400（round-driver 399 / round-state 157 / idle-capture-actions 66 / round-subscriptions 78）。
- **运行实例加载 dist 而非 src**：本仓 `dsh-pmboard` 的 `main` 指向 `dist/index.mjs`，任何源码改动必须 `pnpm build` + 重启才生效（本次已执行）。
