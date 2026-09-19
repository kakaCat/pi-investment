---
requirement: REQ-327bdf
title: 用 DSH Subagent 重构任务执行流程 - 设计
stage: design
created: 2026-09-19
serves: FR-1, FR-2, FR-3, FR-4, NFR-1
---

# 设计：用 DSH Subagent 重构任务执行

---

## 核心方案：对齐 Claude Code Task（serves: FR-1）

**旧设计**：YAML 存储 + Workflow Script + 预定义执行计划  
**新设计**：DSH todo_write + Agent 动态生成计划 + Subagent 执行

| 维度 | 旧 | 新 |
|------|-----|-----|
| Task 存储 | YAML文件 | DSH todo_write |
| 执行计划 | Workflow Script | Agent 二次拆解 |
| 执行单元 | Workflow agent() | DSH subagent |
| 任务卡 | 数据源 | 文档 |

## 两层 Task 概念（serves: FR-1, FR-2）

**拆分阶段**：粗粒度 Task（业务层面） → todo_write 持久化  
**实施阶段**：Agent 开工时二次拆解 → 生成 6 阶段详细计划 → 逐个调用 subagent

## 新增工具（serves: FR-1, FR-2）

- **reqboard_task_execute**: 核心执行工具（读任务 → 二次拆解 → 调 subagent → 更新卡片）
- **reqboard_task_status**: 查询执行状态
- **agentGenerateDetailedPlan**: Agent 动态生成 6 阶段计划
- **updateTaskCard**: 更新 Markdown 任务卡进度

## 修改的工具（serves: FR-1）

- **reqboard_decompose**: 改用 todo_write，不再生成 YAML
- **reqboard_task_move**: 标记为 deprecated

## 并发支持（serves: FR-3）

用 Promise.all 并发执行多个粗粒度 Task：

```typescript
const backendTask = executeTask('t-001');
const frontendTask = executeTask('t-002');
await Promise.all([backendTask, frontendTask]);
```

## 失败处理（serves: FR-4）

Sub-task 失败时记录失败阶段，重置 todo 为 pending，可从指定阶段重新执行：

```typescript
await reqboard_task_execute({
  task_id: 't-001',
  from_phase: '单元测试'  // 从失败的阶段开始
});
```

---