# t-7b5e7a 实现断点常驻与续跑输入包

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现断点常驻与续跑输入包

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/interruption-checkpoint.test.ts 全绿：只交棒 → 台账 interruption.reason==='checkpoint' 且 pendingAction 非空；喂 turn/end 且 reason.kind='error' → reason 变 error:UPSTREAM_STREAM_IDLE:…；重建输入包含 ## 断点 与 pendingAction；老需求无字段 → 输入包逐字节不变

## 实施方案（implementation）
新增 packages/web/dsh-pmboard/src/application/internal/interruption.ts、packages/web/dsh-pmboard/src/application/use-cases/NoteInterruption.ts、packages/web/dsh-pmboard/src/tools/NoteInterruptionTool/NoteInterruptionTool.ts；改 packages/web/dsh-pmboard/src/adapters/CaptureHook.ts（onTurnFinished 信号）、packages/web/dsh-pmboard/src/application/internal/node-input-package.ts（## 断点节）、packages/web/dsh-pmboard/src/application/use-cases/SubmitArtifact.ts、packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts、packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts、packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts、packages/web/dsh-pmboard/src/application/use-cases/AcceptSheet.ts、packages/web/dsh-pmboard/src/application/use-cases/AskConfirm.ts（stampCheckpoint）、packages/web/dsh-pmboard/src/index.ts（异步边界接线+注册）；新增 packages/web/dsh-pmboard/tests/interruption-checkpoint.test.ts。

## 上游产出摘要（dependsSummary）
- 弹框改非阻塞投递并加回执工具

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
