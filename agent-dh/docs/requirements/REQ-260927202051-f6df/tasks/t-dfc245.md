# t-dfc245 迁移契约比对：587 条零字段丢失

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
迁移契约比对：587 条零字段丢失

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
① `npx vitest run scripts/__tests__/migrate-contract.test.ts` 全绿；② 逐字段深比对断言 queue.tasks[i] 去 layer 后 deepEqual 源 ledger.tasks[i]（TC-7.1）；③ 点名断言 lastRun/lastReport/revisions/statusHistory/executions/parentId/stageKind/implementation/context 均已迁移（TC-7.2）；④ 465 条 dependsOn 断言全部可解析（TC-7.3）；⑤ 状态分布断言为 done 556 / in_progress 7 / todo 24（TC-7.4）；⑥ 每份 queue.json 的 requirement_id 断言与其目录一致（TC-7.5）。

## 实施方案（implementation）
写迁移契约测试（scripts/__tests__/migrate-contract.test.ts）：对真实台账副本跑迁移，逐字段深比对源 ledger.tasks 与目标 queue.tasks（去掉 layer）；点名断言关键字段未丢（少迁 lastRun 会让子卡完工凭证门静默失效）；全量断言 465 条 dependsOn 在目标队列内可解析；断言状态分布与需求归属一致。

## 上游产出摘要（dependsSummary）
- 迁移安全：白名单、幂等与 orphan

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
