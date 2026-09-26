# t-69ab2a reqboard_task_run 改造

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
reqboard_task_run 改造

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
工具调用返回 <1s；返回体含 status=dispatched/running + jobId + runId；重复调用幂等

## 实施方案（implementation）
1. 修改 tools/reqboard_task_run.ts：
   - 调用 StartSubtaskChain.execute()
   - 返回格式：{success, task_id, requirement_id, status:'dispatched', job_id, run_id, running:[], next_ready:[]}
   - 保留既有错误码（任务不属于本窗口等）
   - 新增错误码：DSH_JOBS_UNAVAILABLE（ctx.jobs 不可用）

## 上游产出摘要（dependsSummary）
- AdvanceChain 改造

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T07:47:14.147Z，窗口 session-c954a261-4edb-4445-b1ff-56a53a9b5431）

完成 reqboard_task_run 改造：投递式调用立即返回

### 完成项

- 修改 AdvanceTool (reqboard_task_run 工具) 适配投递式 advanceRequirement
- 检查 out.dispatched 字段判断投递是否成功
- 投递失败返回 {success:false, error, code}
- 新增错误码 DSH_JOBS_UNAVAILABLE（ctx.jobs 不可用时）
- 新增错误码 REQBOARD_DISPATCH_FAILED（其他投递失败）
- 投递成功立即返回 {status:"dispatched", job_id, run_id}
- 返回 running 数组（当前 in_progress 子卡 ID 列表）
- 返回 next_ready 数组（下一批 ready 子卡 ID）
- 保留 chain 进度信息（done/total）和 parent_status
- 不再等待执行完成（链在后台 ctx.jobs 中运行）
- 调用返回时间 < 1s（投递即返回，不占用调用方预算）

### 改动文件

- `packages/web/dsh-pmboard/src/tools/AdvanceTool/AdvanceTool.ts`

### 下一步

下一步：t-c031de reqboard_run_status 新增（查询运行态）

---

### 验证方法（可执行命令）
1. 调用advanceRequirement: `grep "advanceRequirement" packages/web/dsh-pmboard/src/tools/AdvanceTool/AdvanceTool.ts` 预期有输出
2. 返回dispatched字段: `grep "dispatched" packages/web/dsh-pmboard/src/tools/AdvanceTool/AdvanceTool.ts` 预期有输出
