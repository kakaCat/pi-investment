# t-b45ad8 扩展验收项状态与通过判据（domain）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
扩展验收项状态与通过判据（domain）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑 pnpm --filter dsh-pmboard test，tests/domain/acceptance-sheet.test.ts 的新增用例 T-U1~T-U4 全绿。

## 实施方案（implementation）
改 packages/pages/dsh-pmboard/src/shared/protocol.ts:540（status 扩四值 not_verifiable）；src/domain/workflow/AcceptanceSheetSpec.ts：isAllPassed→isFullyDecided（无 pending 即放行）、applyVerdicts 对 failed/not_verifiable 强制 opinion。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-19T17:48:15.493Z，窗口 session-7cfa4169-c6dd-4608-b5c4-fb5af4f69a54）

域层契约落地：验收项状态扩为四值（新增 not_verifiable），通过判据新增 isFullyDecided（无 pending 即可放行），not_verifiable 与 failed 一样强制填写原因。

### 完成项

- protocol.ts: VerificationItem.status 扩为 pending|passed|failed|not_verifiable
- AcceptanceSheetSpec.ts: SheetItemLike/SheetVerdictInput 扩四值；applyVerdicts 对 not_verifiable 强制原因（AC-9.2）；新增 isFullyDecided（AC-9.3）；结果含 notVerifiable 计数
- Predicates.ts: isDecidableItemStatus 纳入 not_verifiable；新增 isNotVerifiableItem / countNotVerifiableItems / isFullyDecidedItems
- tests/domain/acceptance-sheet.test.ts: 新增 T-U1~T-U4（字段级）

### 改动文件

- `packages/pages/dsh-pmboard/src/shared/protocol.ts`
- `packages/pages/dsh-pmboard/src/domain/workflow/AcceptanceSheetSpec.ts`
- `packages/pages/dsh-pmboard/src/domain/status/Predicates.ts`
- `packages/pages/dsh-pmboard/tests/domain/acceptance-sheet.test.ts`

### 下一步

t2：applyVerdicts 出现 failed 时同笔 mutate 内自动回退 implementing + 物化返工卡

---
