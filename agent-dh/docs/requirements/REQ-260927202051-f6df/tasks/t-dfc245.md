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

① 逐字段深比对：`queue.tasks[i]` 去 `layer` 后与源 `ledger.tasks` 按 **id 配对** `deepEqual`（不是按下标）；② **键集相等**断言 —— 覆盖全部 18 个可选字段，含 `executorHint`/`cardDoc`/`requirementRefs`/`skipIntegration`/`blockedReason`/`claimedBy`/`claimedAt` 共 7 个原设计文档漏列字段（TC-7.2）；③ 全部 `dependsOn` 可解析（TC-7.3，条数**由源台账现算**，不写死）；④ 状态分布**迁移前后逐一相等**（分布由源台账现算）（TC-7.4）；⑤ 每份 queue.json 的 `requirement_id` 与所在目录一致（TC-7.5）；⑥ 覆盖计数、条数一律由源台账现算并注明数据时点与来源，**禁止任何硬编码计数**（裁决 D7）。

※ 测试文件路径修订：原定 `scripts/__tests__/migrate-contract.test.ts` 不被 vitest 收集（`vitest.config.ts` include = `tests/**/*.test.ts`，实测 "No test files found"），实施落在 `tests/migrate-contract.test.ts`，验收命令相应为 `npx vitest run tests/migrate-contract.test.ts`；未改 vitest 配置。

## 实施方案（implementation）
写迁移契约测试（scripts/__tests__/migrate-contract.test.ts）：对真实台账副本跑迁移，逐字段深比对源 ledger.tasks 与目标 queue.tasks（去掉 layer）；点名断言关键字段未丢（少迁 lastRun 会让子卡完工凭证门静默失效）；全量断言 465 条 dependsOn 在目标队列内可解析；断言状态分布与需求归属一致。

## 上游产出摘要（dependsSummary）
- 迁移安全：白名单、幂等与 orphan

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
