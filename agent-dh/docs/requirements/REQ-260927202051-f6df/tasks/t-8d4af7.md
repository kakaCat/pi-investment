# t-8d4af7 读方改造 D：门禁、查询与 Dive

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
读方改造 D：门禁、查询与 Dive

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
① `npx vitest run src/application/internal/` 全绿；② RTM/覆盖门禁读到的任务键集断言一致（TC-8.9）；③ 全仓残留静态检查：`grep -rn 'ledger\.tasks\|snapshot()\.tasks\|changed\.tasks' src/` 命中数为 0（TC-8.12）；④ `npx tsc --noEmit` 退出码 0。

## 实施方案（implementation）
改 src/application/internal/*（plan-landing、lazy-expand、rollup、rtm-yaml、rework-update、verdicts、failure-handling、support、confirm-settle、agent-handle、capture-section、verification-doc-writer）、src/application/query/*（QueryState、QueryStageDetail、QueryRequirementToken）、src/application/dive/idle-capture-actions.ts、src/application/gate/handlers/h3-inject.ts。完成后跑全仓 grep 断言零残留。

## 上游产出摘要（dependsSummary）
- 台账 schema v9：移除 tasks

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
