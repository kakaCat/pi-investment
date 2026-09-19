# DSH Workflow 任务执行迁移指南

本指南说明如何从旧的任务执行方式迁移到基于 DSH Workflow 的新系统。

## 概述

**REQ-327bdf** 引入了基于 DSH Workflow 的任务执行流程，用 DSH 原生能力替换自己实现的状态机。

### 核心变化

| 方面 | 旧系统 | 新系统 |
|------|--------|--------|
| 任务状态 | 自己维护 6 个状态 | 使用 DSH todo 系统 |
| 执行进度 | 黑盒（看不到中间过程） | 可视化（6 阶段进度） |
| 失败重试 | 手动重新开始 | 支持从失败阶段恢复 |
| 执行记录 | 手动汇报 | 自动记录到任务卡 |

---

## 迁移步骤

### 1. 停止使用旧工具

**不再使用**：
- ❌ 手动执行任务（逐步实施）
- ❌ 手动更新任务状态
- ❌ 手动写执行记录

### 2. 使用新工具

**开始使用**：
- ✅ `reqboard_task_execute` - 自动执行任务
- ✅ `reqboard_task_status` - 查询状态和进度
- ✅ `reqboard_decompose` - 拆分任务（增强版）

---

## 迁移前后对比

### 场景 1：执行任务

**旧方式**（手动）：
```typescript
// 1. 手动开工
await tools.reqboard_task_move({
  task_id: 't-xxx',
  to: 'in_progress'
})

// 2. 手动执行各个步骤
// - 读需求
// - 写代码
// - 测试
// - 汇报

// 3. 手动汇报
await tools.reqboard_task_report({
  task_id: 't-xxx',
  summary: '...',
  completed: [...]
})

// 4. 手动完成
await tools.reqboard_task_move({
  task_id: 't-xxx',
  to: 'done'
})
```

**新方式**（自动）：
```typescript
// 一键执行全流程
await tools.reqboard_task_execute({
  task_id: 't-xxx'
})

// DSH Workflow 自动：
// - 6 阶段执行
// - 每阶段进度可见
// - 自动更新任务卡
// - 失败自动记录
```

---

### 场景 2：查询进度

**旧方式**：
```typescript
// 只能看到粗粒度状态
// 不知道 agent 在做什么
```

**新方式**：
```typescript
// 实时查询进度
const status = await tools.reqboard_task_status({
  task_id: 't-xxx'
})

console.log(`进度: ${status.progress}%`)
console.log(`当前阶段: ${status.workflow?.stages[2].name}`)
```

---

### 场景 3：失败重试

**旧方式**：
```typescript
// 从头开始
// 浪费已完成的工作
```

**新方式**：
```typescript
// 从失败阶段恢复
await tools.reqboard_task_execute({
  task_id: 't-xxx',
  resume_from: 3  // 从第 3 阶段继续
})
```

---

### 场景 4：任务拆分

**旧方式**：
```typescript
// 拆分后任务只在 reqboard 中可见
await tools.reqboard_decompose({
  requirement_id: 'REQ-xxx',
  tasks: [...]
})
```

**新方式**（增强）：
```typescript
// 拆分后自动注册到 DSH todo 系统
await tools.reqboard_decompose({
  requirement_id: 'REQ-xxx',
  tasks: [...]
})

// 任务在 DSH todo 列表中可见
// 用户可以看到进度
```

---

## 兼容性

### 向后兼容

✅ **旧工具仍然可用**：
- `reqboard_task_move` - 仍可手动推进状态
- `reqboard_task_report` - 仍可手动汇报

### 渐进式迁移

**推荐策略**：
1. 新任务使用 `reqboard_task_execute`
2. 旧任务继续手动执行（不强制迁移）
3. 逐步熟悉新工具
4. 完全迁移后停用旧方式

---

## 任务卡格式变化

### 旧格式

任务卡只有基本信息：
```markdown
# t-xxx 任务标题

## 在做什么
...

## 验收标准
...
```

### 新格式（增强）

任务卡自动添加执行记录：
```markdown
# t-xxx 任务标题

## 在做什么
...

## Workflow 执行记录

**Workflow Run ID**: `workflow-abc123`
**状态**: ✅ 已完成
**执行时间**: 2026-09-19 23:45:00

### 阶段执行详情

#### ✅ 阶段 1：需求分析
<details>
<summary>查看输出</summary>
...
</details>

#### ✅ 阶段 2：方案设计
...
```

---

## 故障排查

### 问题：任务执行失败

**症状**：`reqboard_task_execute` 返回错误

**排查**：
1. 查看错误消息
2. 检查任务卡的实施方案是否完整
3. 使用 `resume_from` 重试

**示例**：
```typescript
// 从第 3 阶段重试
await tools.reqboard_task_execute({
  task_id: 't-xxx',
  resume_from: 3
})
```

### 问题：进度不更新

**症状**：`reqboard_task_status` 显示进度为 0

**原因**：
- Workflow 还未启动
- 任务卡未更新

**解决**：
- 等待 Workflow 执行
- 检查任务卡文件是否存在

### 问题：旧任务如何处理

**答案**：
- 旧任务可以继续手动执行
- 不需要强制迁移
- 新任务建议使用新工具

---

## 最佳实践

### 1. 优先使用新工具

对于新任务，优先使用 `reqboard_task_execute`：
- 自动化程度高
- 进度可见
- 失败可恢复

### 2. 查询进度

执行长任务时，定期查询进度：
```typescript
const status = await tools.reqboard_task_status({
  task_id: 't-xxx'
})

if (status.progress < 100) {
  console.log(`还在执行中... ${status.progress}%`)
}
```

### 3. 保留执行记录

不要删除任务卡中的 Workflow 执行记录：
- 可供复盘
- 可追溯决策过程

### 4. 合理使用恢复功能

失败后不要盲目重试：
1. 先分析失败原因
2. 修复问题
3. 再使用 `resume_from` 恢复

---

## 时间线

| 时间 | 事项 |
|------|------|
| 2026-09-19 | 新系统上线 |
| 2026-09-19 ~ 2026-09-30 | 渐进式迁移期（旧工具仍可用） |
| 2026-10-01 起 | 推荐全部使用新工具 |

---

## 相关文档

- [Workflow 工具使用指南](./workflow-tools-guide.md) - 详细使用说明
- [REQ-327bdf 需求文档](../requirements/REQ-327bdf/requirement.md) - 完整需求
- [DSH Workflow 文档](https://docs.deepseek.com/dsh/workflow) - DSH 官方文档

---

## 支持

如有问题，请：
1. 查看本指南和工具使用指南
2. 查看任务卡的执行记录
3. 联系开发团队

---

**最后更新**: 2026-09-19
