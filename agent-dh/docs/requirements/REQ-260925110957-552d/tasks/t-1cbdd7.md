# t-1cbdd7 投递用例

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
投递用例

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
单测验证：重复调用幂等；返回 jobId 和 dispatched 状态；认领与注册原子完成

## 实施方案（implementation）
1. 新增 application/use-cases/StartSubtaskChain.ts
2. 流程：
   - 检查是否已有 active run（幂等）
   - 认领：写 lockAt + runId
   - 注册后台任务：dshJobsAdapter.startJob({kind:'reqboard', run: backgroundRunner.runChain})
   - 立即返回 {status:'dispatched', jobId, runId}
3. 新增 tests/unit/start-subtask-chain.test.ts

## 上游产出摘要（dependsSummary）
- DSH jobs 适配器
- 后台执行器

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T07:04:00.851Z，窗口 session-c954a261-4edb-4445-b1ff-56a53a9b5431）

完成投递用例：认领+注册后台任务+立即返回

### 完成项

- 新增 application/use-cases/StartSubtaskChain.ts：投递用例实现
- 实现幂等检查：已有 runId 时返回 already_running
- 实现认领：写 lockAt + runId 到 RequirementRecord.advance
- 实现注册后台任务：通过 DshJobsAdapter.startJob 注册
- 立即返回：{status, runId, jobId}
- 认领与注册原子完成：确保一致性
- 新增 tests/unit/start-subtask-chain.test.ts：6个测试全部通过
- 测试覆盖：首次投递、幂等、原子性、重复调用、jobId返回、runId唯一性

### 改动文件

- `packages/web/dsh-pmboard/src/application/use-cases/StartSubtaskChain.ts`
- `packages/web/dsh-pmboard/tests/unit/start-subtask-chain.test.ts`

### 下一步

投递用例完成，下一步：t11 查询用例

---

### 验证方法（可执行命令）
1. 单元测试通过: `cd packages/web/dsh-pmboard && npx vitest run tests/unit/start-subtask-chain.test.ts` 预期输出包含 "6 tests" 和 "passed"
2. StartSubtaskChain文件存在: `ls packages/web/dsh-pmboard/src/application/use-cases/StartSubtaskChain.ts` 预期文件存在
