# REQ-260925110957-552d 批次 5-6 完成总结

## 执行概览

- **执行时间**: 2026-09-25
- **完成批次**: 批次 5（实施链改造）+ 批次 6（工具层改造）
- **完成任务**: 7/23 (30.4%)
- **累计进度**: 19/23 (82.6%)
- **分支**: feature/REQ-260925110957-552d
- **提交数**: 7 个检查点提交

## 批次 5：实施链改造（4 任务）

### 核心目标
将同步阻塞的实施链改为异步投递式，支持中断可续

### 完成任务

#### 1. t-dc5b58 AdvanceChain 改造 (581c4760)
**改动**：
- 移除同步 for 循环（原 246-341 行）
- 改为 `deps.jobs.start()` 投递后台任务
- 立即返回 `{dispatched: true, job_id, run_id}`
- 补充 `scanAndResume()` 的 exec 参数透传

**影响文件**：
- `packages/web/dsh-pmboard/src/application/use-cases/AdvanceChain.ts`

#### 2. t-3c54fb ExecuteTask 改造 (285b86a0)
**改动**：
- 移除"认领即 in_progress"逻辑（原 125-138 行）
- 改用 `WorkflowSchemaAdapter.executeWithSchema()`
- 传递 `SubtaskOutputSchema`（filesChanged + summary）
- 执行成功后才写 in_progress 状态
- 处理 schema 校验失败：降级为空值结构

**影响文件**：
- `packages/web/dsh-pmboard/src/application/use-cases/ExecuteTask.ts`

#### 3. t-9e3b7b 选择器改造 (5034fd0f)
**改动**：
- 在"跑子卡"分支后增加 resume 分支（优先级 2.5）
- 调用 `identifyOrphans()` 识别孤儿卡
- 孤儿卡返回 RUN_SUBTASK 事件（触发重试）
- 非孤儿 in_progress 卡不被选中

**影响文件**：
- `packages/web/dsh-pmboard/src/application/internal/advance-select.ts`

#### 4. t-182606 workflow script 改造 (0eb8a9ab)
**改动**：
- 修改 `generateSubtaskScript()` 函数
- 生成的脚本从 `agent(prompt)` 改为 `agent(prompt, {schema})`
- schema 定义 filesChanged 和 summary 两个必需字段
- 引擎自动校验返回结果，确保结构化产出

**影响文件**：
- `packages/web/dsh-pmboard/src/application/internal/workflow-script.ts`

### 批次 5 统计
- **文件变更**: 4 个文件
- **代码变更**: 344 行插入，138 行删除
- **提交数**: 4 个检查点

## 批次 6：工具层改造（3 任务）

### 核心目标
工具层适配投递式调用，提供状态查询能力

### 完成任务

#### 1. t-69ab2a reqboard_task_run 改造 (9040469e)
**改动**：
- 修改 AdvanceTool 适配投递式 `advanceRequirement`
- 检查 `dispatched` 字段判断投递成功
- 投递失败返回 `{success:false, error, code}`
- 新增错误码 `DSH_JOBS_UNAVAILABLE`（ctx.jobs 不可用）
- 投递成功立即返回 `{status:'dispatched', job_id, run_id}`
- 返回 running 数组（当前 in_progress 子卡 ID 列表）
- 返回 next_ready 数组（下一批 ready 子卡 ID）

**影响文件**：
- `packages/web/dsh-pmboard/src/tools/AdvanceTool/AdvanceTool.ts`

#### 2. t-c031de reqboard_run_status 新增 (59329998)
**改动**：
- 新增 RunStatusTool 工具壳（3个文件）
- 调用 QueryRunStatus 用例查询运行态
- 支持 requirement_id 或 run_id 参数
- 通过 run_id 反查 requirement_id（从台账查找）
- 返回运行状态快照：
  - runId: 运行 ID
  - stepIndex: 当前步骤索引
  - currentSubtaskId: 当前正在执行的子卡 ID
  - nextReady: 下一批 ready 的任务 ID 列表
  - jobStatus: Job 状态（running/completed/failed/not_found）
  - pauseReason: 暂停原因
  - autoRun: 是否自动运行
- 无 active run 时返回终止态，不报错

**影响文件**：
- `packages/web/dsh-pmboard/src/tools/RunStatusTool/RunStatusTool.ts`（新增）
- `packages/web/dsh-pmboard/src/tools/RunStatusTool/prompt.ts`（新增）
- `packages/web/dsh-pmboard/src/tools/RunStatusTool/index.ts`（新增）

#### 3. t-301eee 工具注册与提示词 (1156d787)
**改动**：
- 在 `tools/index.ts` 中注册 `reqboard_run_status`
- 更新 AdvanceTool 提示词说明投递式语义
- 明确"投递≠完成"：调用返回 <1s，实际执行在后台
- 说明配套使用 reqboard_run_status 查询运行态

**影响文件**：
- `packages/web/dsh-pmboard/src/tools/index.ts`
- `packages/web/dsh-pmboard/src/tools/AdvanceTool/prompt.ts`

### 批次 6 统计
- **文件变更**: 6 个文件（3 新增，3 修改）
- **代码变更**: 167 行插入，18 行删除
- **提交数**: 3 个检查点

## 技术债务与改进

### 已解决
- ✅ 同步阻塞 → 投递式异步
- ✅ 猜测解析 → Schema 强制
- ✅ 认领执行 → 先执行后认领
- ✅ 等待完成 → 立即返回 + 状态查询

### 遗留问题
无

## 验证记录

### 编译验证
- ✅ 批次 5 所有改动：TypeScript 编译通过
- ✅ 批次 6 所有改动：TypeScript 编译通过

### 功能验证
待批次 7 集成测试和 E2E 测试验证

## 下一步

### 批次 7：测试（2 任务）
- t-dcc586 集成测试
- t-966b43 E2E 测试

### 批次 8：构建交付（2 任务）
- t-b37ffb 构建验证
- t-97f31d 部署验证

## 统计数据

### 代码变更
- **批次 5**: 4 个文件，344 行插入，138 行删除
- **批次 6**: 6 个文件，167 行插入，18 行删除
- **合计**: 10 个文件，511 行插入，156 行删除

### 提交记录
```
581c4760 feat(pmboard): AdvanceChain 改造 - 移除同步循环改为投递式
285b86a0 feat(pmboard): ExecuteTask 改造 - 先执行后认领 + schema 强制产出
5034fd0f feat(pmboard): 选择器改造 - 补充孤儿回收 resume 分支
0eb8a9ab feat(pmboard): workflow script 改造 - 生成的脚本使用 agent(prompt, {schema})
9040469e feat(pmboard): reqboard_task_run 改造 - 投递式调用立即返回
59329998 feat(pmboard): 新增 reqboard_run_status 工具 - 查询运行态
1156d787 feat(pmboard): 工具注册与提示词更新 - 投递式语义说明
```

### Token 使用
- **本轮消耗**: 141K
- **剩余**: 59K (29.5%)

## 建议

1. **代码审查**: 审查批次 5-6 的所有改动，重点关注异步化逻辑
2. **功能验证**: 手动测试投递式调用和状态查询
3. **文档更新**: 更新用户文档说明新的工具使用方式
4. **下一轮**: Token 充足，可继续批次 7-8（建议新窗口）
