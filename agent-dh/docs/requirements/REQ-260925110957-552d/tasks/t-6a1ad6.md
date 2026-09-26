# t-6a1ad6 DSH jobs 适配器

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
DSH jobs 适配器

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

1. 单元测试通过: `cd packages/web/dsh-pmboard && npx vitest run tests/unit/dsh-jobs-adapter.test.ts` 预期输出包含 "11 tests" 和 "passed"
2. 关键方法存在: `grep -E "async start|async get|available" packages/web/dsh-pmboard/src/adapters/DshJobsAdapter.ts | wc -l` 预期输出 ≥3

## 实施方案（implementation）
1. 新增 infrastructure/dsh-jobs-adapter.ts
2. 导出 DshJobsAdapter 类：startJob(spec) → jobId，getJob(jobId) → snapshot
3. 启动时检测 ctx.jobs 存在性，不存在时抛 DshJobsUnavailable 错误
4. 新增 tests/unit/dsh-jobs-adapter.test.ts 用 mock ctx.jobs 验证

## 上游产出摘要（dependsSummary）
- 领域类型定义

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T05:25:33.964Z，窗口 session-c954a261-4edb-4445-b1ff-56a53a9b5431）

完成 DSH jobs 适配器：封装 ctx.jobs.start/get 为领域友好接口

### 完成项

- 新增 adapters/DshJobsAdapter.ts：封装 ctx.jobs.start/get
- 实现 DshJobsAdapter 类：startJob() 返回 jobId，getJob() 返回快照
- 启动时检测 ctx.jobs 存在性：不可用时抛 DshJobsUnavailable 错误
- 实现状态映射：DSH job 状态 → 领域 JobStatus
- 提供静态方法 isAvailable() 检测可用性
- 新增 tests/unit/dsh-jobs-adapter.test.ts：11个测试全部通过

### 改动文件

- `packages/web/dsh-pmboard/src/adapters/DshJobsAdapter.ts`
- `packages/web/dsh-pmboard/tests/unit/dsh-jobs-adapter.test.ts`

### 下一步

DSH jobs 适配器完成，下一步：t4 workflow schema 适配器

---

### 验证方法（可执行命令）
1. 单元测试通过: `cd packages/web/dsh-pmboard && npx vitest run tests/unit/dsh-jobs-adapter.test.ts` 预期输出包含 "11 tests" 和 "passed"
2. 关键方法存在: `grep -E "async start|async get|available" packages/web/dsh-pmboard/src/adapters/DshJobsAdapter.ts | wc -l` 预期输出 ≥3
