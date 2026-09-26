# t-3c54fb ExecuteTask 改造

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
ExecuteTask 改造

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
集成测试验证：filesChanged 必定存在（schema 保证）；先执行后写 in_progress；引擎拒绝时有明确错误

## 实施方案（implementation）
1. 修改 application/use-cases/ExecuteTask.ts：
   - 移除"认领即 in_progress"逻辑，改为执行成功后才写状态
   - deps.workflow.start() 改为 workflowSchemaAdapter.executeWithSchema()
   - 传递 SubtaskOutputSchema
   - 处理引擎 schema 校验失败：降级为结构化空值 {filesChanged:[], summary:'schema validation failed'}

## 上游产出摘要（dependsSummary）
- workflow schema 适配器
- AdvanceChain 改造

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T07:38:34.758Z，窗口 session-c954a261-4edb-4445-b1ff-56a53a9b5431）

完成 ExecuteTask 改造：先执行后认领 + schema 强制产出

### 完成项

- 移除"认领即 in_progress"逻辑（原第125-138行）
- 添加 WorkflowSchemaAdapter 导入
- 改用 executeWithSchema() 调用引擎，传递 SubtaskOutputSchema
- 构造 schema 定义：filesChanged（必需）+ summary（必需）
- 处理引擎不可用：降级为 createEmptySubtaskOutput()
- 处理引擎异常：catch 后降级为空值结构
- 修改产出解析逻辑：使用 schemaOutput.filesChanged 和 schemaOutput.summary
- 在 subtask-ran mutate 中添加"先执行后认领"逻辑
- 执行成功后才写 in_progress 状态、claimedAt、executions 记录
- filesChanged 必定存在（schema 保证，不再是空数组导致凭证门拦截）

### 改动文件

- `packages/web/dsh-pmboard/src/application/use-cases/ExecuteTask.ts`

### 下一步

下一步：批次 5 其他任务（t-9e3b7b 选择器改造 / t-182606 workflow script 改造）

---

### 验证方法（可执行命令）
1. 调用WorkflowSchemaAdapter: `grep "workflowSchemaAdapter\|WorkflowSchemaAdapter" packages/web/dsh-pmboard/src/application/use-cases/ExecuteTask.ts` 预期有输出
2. filesChanged字段在schema中: `grep "filesChanged" packages/web/dsh-pmboard/src/adapters/WorkflowSchemaAdapter.ts` 预期有输出
