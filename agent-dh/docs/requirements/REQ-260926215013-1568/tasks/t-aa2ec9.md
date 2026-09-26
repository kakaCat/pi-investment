# t-aa2ec9 契约定死：回合来源、相位值域与驱动状态纯判定

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
契约定死：回合来源、相位值域与驱动状态纯判定

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/dive-round-state.test.ts 全绿（非 dive 来源不认、round 必须等于 roundsInStage+1、内容不一致返回 false）；npx tsc --noEmit -p tsconfig.json 错误数不高于改动前基线；grep -n paused src/shared/protocol.ts 可见 phase 值域含 paused。

## 实施方案（implementation）
新增 src/application/dive/round-state.ts（DriverState/RoundAttempt/DiveRoundSource 结构类型 + isDiveRoundSource/sameQueued/roundReservationValid/deepEqualJson/roundLimitFor 纯函数）；src/shared/protocol.ts 修正 RequirementDive.phase 为 'idle'|'active'|'paused'、新增 DiveRoundSource + isDiveRoundSource；src/application/ports.ts 给 AgentDeliveryPort 增 createRoundMessage/deliverMessage 签名；新增 tests/dive-round-state.test.ts。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-26T14:36:15.468Z，窗口 session-c5ea210f-afc3-4735-a4d1-f9058b378363）

回合驱动器的契约定死了：来源标识、相位值域与「什么算合法预留」的判定现在各有唯一出处。做完后，任何一条续跑回合消息只要不是本驱动器登记的那条（来源不符或内容被篡改），都会被机械判为不认，且实现与测试都读同一份契约。

### 完成项

- protocol.ts：RequirementDive.phase 值域修正为 idle|active|paused（原为阶段名联合，与文档/FR-6/FR-8 矛盾）；maxRoundsPerStage 降为可选
- protocol.ts：新增 DiveRoundSource 来源契约 + isDiveRoundSource 判定（非 dive / round≤0 → false）
- ports.ts：新增 DiveRoundDeliveryPort 子端口（createRoundMessage/deliverMessage），不扩父接口以保 tsc 基线
- 新增 application/dive/round-state.ts：DriverState/RoundAttempt 契约 + deepEqualJson/sameQueued/roundReservationValid/roundLimitFor/renderDiveRoundText/isDrivableRequirement
- 新增 tests/dive-round-state.test.ts：12 条断言（非 dive 不认 / 内容逐字相等 / round 必须=roundsInStage+1 / stale·cancelled·revision 变·非 armed+active 一律拒 / 上限来源与回落）

### 改动文件

- `packages/web/dsh-pmboard/src/shared/protocol.ts`
- `packages/web/dsh-pmboard/src/application/ports.ts`
- `packages/web/dsh-pmboard/src/application/dive/round-state.ts`
- `packages/web/dsh-pmboard/tests/dive-round-state.test.ts`

### 下一步

T-2（round 状态机）与 T-3（投递适配）可并行开工

---
