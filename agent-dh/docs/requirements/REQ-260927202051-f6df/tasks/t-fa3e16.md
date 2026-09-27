# t-fa3e16 接线 ExecuteTask/MoveTask：读队列与顺序契约

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
接线 ExecuteTask/MoveTask：读队列与顺序契约

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
① `npx vitest run src/application/use-cases/MoveTask.test.ts` 全绿；② task_run 日志断言包含 `Queue ready tasks:` 且父卡字段取自队列（TC-9.2）；③ `reqboard_task_move(to=done)` 后 `jq -e '.ready|index("<下游id>")' <queue.json>` 命中（TC-9.3）；④ 打点断言 taskStore.mutate 先于 repo.mutate（TC-8.11）；⑤ task_run 前后 `md5 <queue.json>` 输出不变（只读）；⑥ 删除队列后 task_move 仍返回 success（TC-9.4）。

## 实施方案（implementation）
改 src/application/use-cases/ExecuteTask.ts：执行前经 taskStore 取该需求任务与 ready，日志打印 ready 列表；父卡字段（acceptance/implementation/context/dependsSummary/parentId）取自队列；本步骤不得写队列。改 MoveTask.ts：状态改 taskStore.mutate（先）→ 重算派生视图并原子写 → 再 repo.mutate 改需求状态（后）。顺序在代码里固定并加打点以便测试断言。

## 上游产出摘要（dependsSummary）
- 接线 Decompose：任务写入队列

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
