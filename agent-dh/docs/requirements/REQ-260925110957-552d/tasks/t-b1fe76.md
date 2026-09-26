# t-b1fe76 查询用例

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
查询用例

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
单测验证：返回 runId/stepIndex/currentSubtask/nextReady/jobStatus/pauseReason

## 实施方案（implementation）
1. 新增 application/use-cases/QueryRunStatus.ts
2. 流程：
   - 读 checkpoint（runId/stepIndex/currentSubtaskId）
   - 调用 dshJobsAdapter.getJob(jobId) 获取 job 快照
   - 读台账获取 nextReady 子卡、pauseReason
   - 合成返回 {runId, stepIndex, running, nextReady, jobStatus, pauseReason, autoRun}
3. 新增 tests/unit/query-run-status.test.ts

## 上游产出摘要（dependsSummary）
- DSH jobs 适配器
- checkpoint 管理器

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T07:07:15.607Z，窗口 session-c954a261-4edb-4445-b1ff-56a53a9b5431）

完成查询用例：快照投影，返回运行状态

### 完成项

- 新增 application/use-cases/QueryRunStatus.ts：查询用例实现
- 实现快照投影：读 checkpoint + job 状态
- 返回运行状态：runId/stepIndex/currentSubtaskId/nextReady/jobStatus/pauseReason/autoRun
- 实现 findReadyTasks()：查找可执行任务
- 支持多种 job 状态：running/completed/failed/not_found
- 实现暂停原因判断：有任务但都不 ready
- 新增 tests/unit/query-run-status.test.ts：10个测试全部通过
- 测试覆盖：无运行、有checkpoint、各种job状态、nextReady、pauseReason、异常处理

### 改动文件

- `packages/web/dsh-pmboard/src/application/use-cases/QueryRunStatus.ts`
- `packages/web/dsh-pmboard/tests/unit/query-run-status.test.ts`

### 下一步

查询用例完成，下一步：t12 仓储层扩展（批次4最后一个）

---

### 验证方法（可执行命令）
1. QueryRunStatus文件存在: `ls packages/web/dsh-pmboard/src/application/use-cases/QueryRunStatus.ts` 预期文件存在
2. queryRunStatus函数存在: `grep "export.*queryRunStatus" packages/web/dsh-pmboard/src/application/use-cases/QueryRunStatus.ts` 预期有输出
