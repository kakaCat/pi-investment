# t-7a84fe 核心迁移助手（internal/token-usage.ts）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
核心迁移助手（internal/token-usage.ts）

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准

命令：cd packages/pages/dsh-pmboard && pnpm test token-transition-helper；期望输出：✓ tests/token-transition-helper.test.ts (3 tests)，包含 有快照结算/无快照不结算/快照不可得 三个场景

## 实施方案（implementation）
在 packages/pages/dsh-pmboard/src/application/internal/token-usage.ts 新增：(1) TransitionOpts 接口 {at, actor, reason?, snap?}；(2) transitionRequirement 函数：snap存在时调accumulateStageDelta，写req.status/version/updatedAt/updatedBy，调recordStatus(含snap)。导出供全部用例使用。新增单测 tests/token-transition-helper.test.ts。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-18T16:39:52.531Z，窗口 session-2b82d910-6ab6-453d-9f0c-ffad83413851）

核心迁移助手实施完成：transitionRequirement 函数 + TransitionOpts 接口 + 单测 3 条全绿

### 完成项

- 在 token-usage.ts 新增 TransitionOpts 接口（at/actor/reason/snap 四字段）
- 新增 transitionRequirement 函数：snap 存在时调 accumulateStageDelta 结算离开节点，迁移状态（status/version/updatedAt/updatedBy），调 recordStatus 记录事件带快照
- 新增单测 tests/token-transition-helper.test.ts：有快照场景断言 byStage 累加+事件带快照；无快照场景断言不累加+事件无快照；unavailable 快照场景断言结算失败但事件仍记录
- pnpm test token-transition-helper 通过（3/3 tests passed）

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/token-usage.ts`
- `packages/pages/dsh-pmboard/tests/token-transition-helper.test.ts`

### 下一步

推进到 done，解锁 t2/t3/t4/t5 四个并行任务（改造 MoveRequirement/AskConfirm/rollup/AcceptSheet+verdicts）

---
## 汇报 2（2026-09-18T16:40:02.636Z，窗口 session-2b82d910-6ab6-453d-9f0c-ffad83413851）

核心迁移助手实施完成：transitionRequirement 函数 + TransitionOpts 接口 + 单测 3 条全绿

### 完成项

- 在 token-usage.ts 新增 TransitionOpts 接口（at/actor/reason/snap 四字段）
- 新增 transitionRequirement 函数：snap 存在时调 accumulateStageDelta 结算离开节点，迁移状态（status/version/updatedAt/updatedBy），调 recordStatus 记录事件带快照
- 新增单测 tests/token-transition-helper.test.ts：有快照场景断言 byStage 累加+事件带快照；无快照场景断言不累加+事件无快照；unavailable 快照场景断言结算失败但事件仍记录
- pnpm test token-transition-helper 通过（3/3 tests passed）

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/token-usage.ts`
- `packages/pages/dsh-pmboard/tests/token-transition-helper.test.ts`

### 下一步

推进到 testing → in_review → done，解锁 t2/t3/t4/t5

---
