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
## 汇报 1（2026-09-27T13:32:12.486Z，窗口 session-3936d77f-2391-4042-8305-9b0fb5e9d2b8）

执行任务时会真的从队列取父卡信息，并打印出「此刻能做哪些」；把一张卡标记完成，队列会立刻解锁依赖它的下游任务。同时钉死了一条容易出事的顺序——先改任务、再改需求状态，现在有打点断言守着。还确认了「跑任务只看不改」：一次执行前后，队列文件的指纹完全一致。

### 完成项

- ExecuteTask.ts：子卡/父卡一律 store.get，同需求任务 listByRequirement；日志打印 Queue ready tasks:<ids>（就绪口径共用 readyTasksOf，不另写一份）
- MoveTask.ts：任务写与需求写拆两段（顺序契约），补齐 expandSubtasks 返回 TaskRecord → QueueTask 的 layer 映射（落盘前由 TaskStore.recompute 重算）
- AdvanceChain.ts：同款 layer 映射（含 10 行注释说明为何是占位）；progressOf 入参 ledger → view（消除 TC-8.12 静态门禁对台账取任务的误报）
- 顺序契约有打点断言：真实 QueueTaskStore 上 log === ['taskStore.mutate','repo.mutate']（TC-8.11）
- task_run 只读语义：投递式任务前后 queue.json md5 相同
- 队列缺失时 task_move 干净报 REQBOARD_TASK_NOT_FOUND，不崩且不隐式建档
- tests/t12-queue-readonly-ordering.test.ts 5 例逐条对应锚点（ready 依赖按队列算：日志含 t-s1 不含 t-s2；move done 后 readQueue().ready 含 t-s2）
- 写域残留归零：grep -rn 'ledger\.tasks|snapshot()\.tasks|changed\.tasks' src/application/use-cases/ src/application/internal/{plan-landing,confirm-settle,rollup}.ts = 0
- 验收：npx vitest run t9+t11+t12 三个测试文件 → 3 files / 14 passed

### 改动文件

- `packages/web/dsh-pmboard/src/application/use-cases/ExecuteTask.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/AdvanceChain.ts`
- `packages/web/dsh-pmboard/tests/t12-queue-readonly-ordering.test.ts`

### 下一步

修复派给本成员的 13 个用例层测试文件（等 queue-core 逐行改法清单）

---
