# t-f8ed18 先定契约：挂起确认能标出「被中止」，判定口径只留一处

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
先定契约：挂起确认能标出「被中止」，判定口径只留一处

## 解决什么问题
确认门在等待期间被中止后，这次等待既查不到、也没法续；而且「台账是否已落章」由守卫和回执各判一次，容易口径漂移。先把中止留痕与判定口径收敛成一处，后续守卫/回执才有共同的事实依据。

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts 全绿：targetConfirmedInLedger 对 plan（approvedAt 已写）与 artifact（该 kind 成组 confirmedAt 已写）分别返回 true、未落章返回 false；markInterrupted 二次调用后 interruptedAt 不变；createdAt 早于中止时间时记录不提前过期。

## 实施方案（implementation）
① src/shared/protocol.ts：PendingConfirmation 增可选 interruptedAt?: number。② src/application/ports.ts：PendingConfirmPort 增 markInterrupted(ticket): PendingConfirmation | undefined（不抛）。③ src/adapters/PendingConfirmRegistry.ts：实现 markInterrupted（幂等，只写首次）；get/pendingForWindow 过期基准改 (interruptedAt ?? createdAt) + ttlMs。④ 新增 src/application/internal/pending-guard.ts：从 ConfirmReceipt.ts:76-80 逐字提取 targetConfirmedInLedger，并实现 livePendingConfirm(deps, windowKey)（过滤已 settle/已过期/台账已落章）+ PENDING_CONFIRM_BLOCKED_TOOLS + 恢复文案常量。⑤ src/application/use-cases/ConfirmReceipt.ts：删私有谓词、改用共享谓词，interruptedAt 且未作答时改文案。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T05:26:02.992Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

这一步做完，确认门在等待期间被中止会留下可查的痕（interruptedAt），不会因为登记得早而提前过期；「台账是否已落章」的判定也从两处收敛成一处（pending-guard.targetConfirmedInLedger），回执与后续停手守卫从此共用同一份事实口径。验收命令 pending-guard.test.ts 9 项全绿。

### 完成项

- PendingConfirmation 增可选 interruptedAt（共享协议契约）
- PendingConfirmPort 增 markInterrupted(ticket)（不抛、未知 ticket 返回 undefined）
- PendingConfirmRegistry 实现 markInterrupted（幂等，只写首次）；get / pendingForWindow 过期基准改为 (interruptedAt ?? createdAt) + ttlMs
- 新增 internal/pending-guard.ts：targetConfirmedInLedger 单点 + livePendingConfirm（滤已 settle/过期/台账已落章）+ PENDING_CONFIRM_BLOCKED_TOOLS + 恢复文案与拒绝文案
- ConfirmReceipt.ts 删私有 confirmedInLedger，改用共享谓词；interruptedAt 且未作答时回执文案改为「等待已被中止」并给出看板/重新发起两条路
- 自测：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts → 9 passed（0 failed）
- 顺带回归：ask-confirm-pending.test.ts / contract-shapes.test.ts 运行期全绿；未改动本卡范围外文件

### 改动文件

- `agent-dh/packages/web/dsh-pmboard/src/shared/protocol.ts`
- `agent-dh/packages/web/dsh-pmboard/src/application/ports.ts`
- `agent-dh/packages/web/dsh-pmboard/src/adapters/PendingConfirmRegistry.ts`
- `agent-dh/packages/web/dsh-pmboard/src/application/internal/pending-guard.ts`
- `agent-dh/packages/web/dsh-pmboard/src/application/use-cases/ConfirmReceipt.ts`
- `agent-dh/packages/web/dsh-pmboard/tests/pending-guard.test.ts`

### 下一步

下游 t2（缺省阻塞）用 markInterrupted；t3（停手守卫/状态投影）用 livePendingConfirm 与 PENDING_CONFIRM_BLOCKED_TOOLS。注意：contract-shapes.test.ts 的 PendingConfirmPort 形状断言（3 处 TS 报错）按拆分计划归属 t5 更新，本卡刻意未动——本仓 typecheck 基线本就有 118 处既有报错，非本次引入。

---
## 汇报 2（2026-09-27T05:43:53.316Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

父卡收尾：挂起确认的判定口径与中止留痕已由 4 张子卡（研发/联调/复核/测试）全部完成——interruptedAt 契约、markInterrupted 幂等、过期基准 (interruptedAt ?? createdAt)+ttl、pending-guard 单点台账落章谓词均已落盘并验证；验收命令 pending-guard.test.ts 9/9 全绿。

### 完成项

- 研发 t-a0c273：契约+实现落盘（interruptedAt / markInterrupted / 过期基准 / pending-guard 单点谓词 / ConfirmReceipt 改用共享谓词）
- 联调 t-3b5f9c：registry 方法对未知/跨窗口/过期一律不抛；回执链路接共享谓词
- 复核 t-738238：实现与设计 I-4/I-6 无偏离
- 测试 t-db1d48：验收命令 pending-guard.test.ts 9/9 全绿，回归 20/20
- 父卡验收命令：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/pending-guard.test.ts → 9 passed

### 改动文件

- `docs/requirements/REQ-260927123256-196b/evidence/t-a0c273-dev.md`
- `docs/requirements/REQ-260927123256-196b/evidence/t-db1d48-test.md`
- `packages/web/dsh-pmboard/src/shared/protocol.ts`
- `packages/web/dsh-pmboard/src/application/ports.ts`
- `packages/web/dsh-pmboard/src/adapters/PendingConfirmRegistry.ts`
- `packages/web/dsh-pmboard/src/application/internal/pending-guard.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/ConfirmReceipt.ts`
- `packages/web/dsh-pmboard/tests/pending-guard.test.ts`

### 下一步

父卡进 done 后，需求剩余任务 t-4d87e5/t-fd257f/t-16cefa/t-93e425/t-2231a8 依次推进。

---
