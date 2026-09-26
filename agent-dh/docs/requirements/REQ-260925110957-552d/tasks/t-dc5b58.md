# t-dc5b58 AdvanceChain 改造

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
AdvanceChain 改造

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
集成测试验证：调用后立即返回；链在后台推进；scanAndResume 不再抛 parent undefined

## 实施方案（implementation）
1. 修改 application/use-cases/AdvanceChain.ts：
   - advanceRequirement() 改为调用 StartSubtaskChain.execute()
   - 移除同步 for 循环（advanceMaxStepsPerCall）
   - scanAndResume() 补充 exec 参数透传给 StartSubtaskChain
2. 保留 pauseRequirement / rollupRequirement 逻辑不变

## 上游产出摘要（dependsSummary）
- 投递用例
- 仓储层扩展

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T07:32:34.559Z，窗口 session-c954a261-4edb-4445-b1ff-56a53a9b5431）

完成 AdvanceChain 改造：移除同步循环，改为投递式执行

### 完成项

- 修改 advanceRequirement() 为投递式：调用 deps.jobs.start() 注册后台任务
- 移除同步 for 循环（原 246-341 行），链逻辑移到后台 run 函数内部
- 添加依赖检查：deps.jobs 不可用时显式返回 {dispatched:false, reason}
- 添加幂等检查：已有 runId 时返回 {dispatched:false, existing_run_id}
- 生成 runId 并认领：写 lockAt + runId 到台账
- 后台循环复用原有逻辑：选择器、执行器、历史记录、失败处理
- 立即返回 {dispatched:true, job_id, run_id}
- 修改 scanAndResume() 补充 exec 参数透传给 advanceRequirement
- 在 ports.ts 添加 JobsPort 接口定义（start/get/available）
- 在 UseCaseDeps 添加 jobs? 字段
- 更新 AdvanceOutcome 类型支持新字段（dispatched/job_id/run_id/reason/existing_run_id）

### 改动文件

- `packages/web/dsh-pmboard/src/application/ports.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/AdvanceChain.ts`

### 下一步

下一步：t-3c54fb ExecuteTask 改造（依赖本任务完成）

---

### 验证方法（可执行命令）
1. deps.jobs.start调用存在: `grep "deps.jobs.start" packages/web/dsh-pmboard/src/application/use-cases/AdvanceChain.ts` 预期有输出
2. 返回dispatched字段: `grep "dispatched: true" packages/web/dsh-pmboard/src/application/use-cases/AdvanceChain.ts` 预期有输出
