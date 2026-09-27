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
## 汇报 1（2026-09-27T13:25:17.117Z，窗口 session-3936d77f-2391-4042-8305-9b0fb5e9d2b8）

迁移的「零丢失」拿到了可复核的证明：612 张任务卡逐张按 id 与源台账比对——每个字段、18 个可选字段里的每一个、依赖关系、各需求条数、状态分布，全部一模一样；所有比对数字都由源台账现场计算，没有任何写死的计数，因此下次台账再长也不会让这道证明变红。另外，有一条任务的归属需求目录已被归档删除，迁移会为它重建最小目录并迁进去（而不是隔离丢弃），且回滚时会把新建目录一起删掉。

### 完成项

- TC-7.1~7.5 全部数据驱动，无任何硬编码计数（裁决 D7）
- 逐条按 id 配对 deepEqual（queueTask 去 layer 与源 task），不是按下标
- 键集相等断言 + 18 个可选字段逐一点名（含原文档漏列的 executorHint/cardDoc/requirementRefs/skipIntegration/blockedReason/claimedBy/claimedAt）
- 分组守恒：源按 requirementId 现算 → 各 queue.json 条数逐一相等
- dependsOn 条数守恒 + 全部可解析；状态分布由源现算逐一相等；每份 queue.json 的 requirement_id 与目录一致
- 合成穷举断言：37 字段源 → 38 键目标，差集仅 {layer}，且源没有的键不得凭空出现
- D10 建目录护栏落地：仅当 requirementId 在 ledger.requirements 中真实存在才建（写成 MIGRATION_INVARIANT 断言）；报告新增 createdDirs；manifest 记录；--rollback 删除本次新建目录
- 真实副本实测：51 份 queue.json（含新建 REQ-48d896，9 任务）/ 迁移 612 / orphan 0 / skipped 0 / unmigrated=0
- 验收命令：npx vitest run tests/migrate-ledger-v8v9.test.ts tests/migrate-contract.test.ts tests/migration.test.ts → 3 files / 39 passed

### 改动文件

- `packages/web/dsh-pmboard/scripts/migrate-ledger.ts`
- `packages/web/dsh-pmboard/tests/migrate-contract.test.ts`

### 下一步

等 Lead 投产指令（先备份 + 校验脚本 + 回滚预案）；同时等 tests/ledger-v6-token.test.ts 的归属裁定

---
