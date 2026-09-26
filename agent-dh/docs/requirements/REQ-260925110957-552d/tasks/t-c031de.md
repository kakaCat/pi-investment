# t-c031de reqboard_run_status 新增

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
reqboard_run_status 新增

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
工具可调用；返回体含 runId/stepIndex/running/nextReady/jobStatus/pauseReason；无 run 时返回终止态不报错

## 实施方案（implementation）
1. 新增 tools/reqboard_run_status.ts：
   - 参数：requirement_id（可选，默认本窗口绑定需求）或 run_id
   - 调用 QueryRunStatus.execute()
   - 返回格式：{success, requirement_id, run_id?, snapshot:{runId, stepIndex, running, nextReady, jobStatus, pauseReason, autoRun}}
   - 无 active run 时返回 {success:true, snapshot:{status:'terminated', reason:...}}

## 上游产出摘要（dependsSummary）
- 查询用例

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T07:51:10.258Z，窗口 session-c954a261-4edb-4445-b1ff-56a53a9b5431）

完成 reqboard_run_status 新增：查询运行态工具

### 完成项

- 新增 RunStatusTool 工具壳（tools/RunStatusTool/ 目录）
- 创建 prompt.ts：工具提示词，说明用途和返回格式
- 创建 RunStatusTool.ts：工具主文件，调用 QueryRunStatus 用例
- 创建 index.ts：导出文件
- 参数支持：requirement_id（可选，默认本窗口绑定需求）或 run_id
- 通过 run_id 反查 requirement_id（从台账查找）
- 返回格式：{success, requirement_id, run_id, snapshot}
- snapshot 包含：runId/stepIndex/currentSubtaskId/nextReady/jobStatus/pauseReason/autoRun
- 无 active run 时返回终止态（status:"terminated"），不报错
- 适合投递后轮询查询，配合 reqboard_task_run 使用

### 改动文件

- `packages/web/dsh-pmboard/src/tools/RunStatusTool/RunStatusTool.ts`
- `packages/web/dsh-pmboard/src/tools/RunStatusTool/prompt.ts`
- `packages/web/dsh-pmboard/src/tools/RunStatusTool/index.ts`

### 下一步

下一步：t-301eee 工具注册与提示词（批次 6 最后一个任务）

---

### 验证方法（可执行命令）
1. RunStatusTool文件存在: `ls packages/web/dsh-pmboard/src/tools/RunStatusTool/RunStatusTool.ts` 预期文件存在
2. 调用queryRunStatus: `grep "queryRunStatus" packages/web/dsh-pmboard/src/tools/RunStatusTool/RunStatusTool.ts` 预期有输出
3. 工具已注册: `grep "RunStatusTool" packages/web/dsh-pmboard/src/tools/index.ts` 预期有输出
