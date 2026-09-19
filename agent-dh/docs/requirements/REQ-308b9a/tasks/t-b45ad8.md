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
