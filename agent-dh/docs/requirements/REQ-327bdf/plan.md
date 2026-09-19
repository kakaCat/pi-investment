---
requirement: REQ-327bdf
title: 用 DSH Subagent 重构任务执行流程 - 拆分计划
stage: decomposing
created: 2026-09-19
---

# 拆分计划：基于 DSH Subagent 的任务执行

> **本文档定义「做什么、怎么验收、谁依赖谁」**：任务列表、验收标准、依赖关系。

---

## 1. 总体目标

用 DSH Subagent 重构任务执行流程，对齐 Claude Code Task 模式：
- ✅ 用 DSH todo_write 持久化（不用 YAML）
- ✅ Agent 二次拆解生成详细计划
- ✅ 用 subagent 工具执行 Sub-task
- ✅ Markdown 卡片实时更新

---

## 2. 任务列表

| Key | 标题 | Phase | Side | 依赖 | 接收条款 |
|-----|------|-------|------|------|---------|
| t-001 | 实现 reqboard_task_execute | implement | backend | — | FR-1、FR-2 |
| t-002 | 实现 updateTaskCard | implement | backend | — | FR-2 |
| t-003 | 修改 reqboard_decompose | implement | backend | — | FR-1 |
| t-005 | 实现 agentGenerateDetailedPlan | implement | backend | — | FR-1、FR-2 |
| t-004 | 实现 reqboard_task_status | implement | backend | t-002 | FR-2 |
| t-006 | E2E 测试 | test | backend | t-001, t-002, t-003, t-005 | FR-1、FR-2、FR-3 |
| t-007 | 单元测试：失败重试 | test | backend | t-001 | FR-4 |
| t-008 | 更新用户文档 | doc | doc | t-001, t-003 | FR-1、FR-2 |
| t-009 | 迁移指南 | doc | doc | t-008 | — |

**覆盖说明**：
- 拆分时每条根编号 FR-1 ~ FR-4 都被至少一张卡的接收条款接收（覆盖门禁不报缺口）
- t-009 为文档类任务，不接收功能条款

---

## 3. 详细说明

### t-001: 实现 reqboard_task_execute

**验收标准**：
- npx vitest run tests/reqboard-task-execute.test.ts 通过

**实施方案**：
1. 新增工具
2. generateDetailedPlan
3. 调用 subagent
4. 失败处理

### t-002: 实现 updateTaskCard

**验收标准**：
- grep "✅ 已完成" tasks/t-test-001.md 返回匹配

**实施方案**：
1. 解析 Markdown
2. 生成详细计划节
3. 更新进度
4. 写 sub-agent ID

### t-003: 修改 reqboard_decompose

**验收标准**：
- test -f tasks.yml 返回非零
- todo_write 返回 success

**实施方案**：
1. 读现有代码
2. 移除 YAML
3. 调用 todo_write
4. 保持 Markdown

### t-005: 实现 agentGenerateDetailedPlan

**验收标准**：
- 返回 data.length === 6 通过

**实施方案**：
1. 定义 6 阶段
2. 根据 side 调整
3. 生成 prompt

### t-004: 实现 reqboard_task_status

**验收标准**：
- 返回 data.progress 在 0-100 范围内通过

**实施方案**：
1. 读任务卡
2. 解析进度
3. 计算百分比
4. 返回状态

### t-006: E2E 测试

**验收标准**：
- npx vitest run tests/e2e-task-execution.test.ts 通过

**实施方案**：
1. 创建测试需求
2. 调用 decompose
3. 调用 execute
4. 验证结果

### t-007: 单元测试：失败重试

**验收标准**：
- npx vitest run tests/task-retry.test.ts 通过

**实施方案**：
1. 模拟失败
2. 验证记录
3. 重新执行
4. 验证跳过

### t-008: 更新用户文档

**验收标准**：
- grep "reqboard_task_execute" docs/architecture/project-manual.md 返回匹配

**实施方案**：
1. 更新文档
2. 添加示例
3. 添加说明
4. 更新链接

### t-009: 迁移指南

**验收标准**：
- test -f docs/guides/task-execution-migration.md 返回零

**实施方案**：
1. 创建指南
2. 说明区别
3. 迁移步骤
4. 示例

---
