# Dive Armed 模式使用指南

**需求**: REQ-260925234037-1503  
**更新**: 2026-09-25

## 什么是 Dive Armed 模式？

Dive Armed 是项目看板的**唯一工作方式**，实现需求从立项到归档的全自动流程控制。

## 核心理念

**Dive Armed = 自动驾驶**

- 需求创建后自动推进，无需人工输入"继续"
- 门禁点自动检查，通过后自动进入下一阶段
- 任务自动执行，完成后自动推进
- Agent 自主决策，人只在关键点确认

## 快速开始

### 1. 创建需求

```typescript
// Dive Armed 是默认模式
const req = await tools.reqboard_create({
  title: "实现新功能",
  category: "feature",
  summary: "功能描述..."
});
// dive.activation 自动为 'armed'
```

### 2. 自动推进流程

需求创建后，系统自动：
1. Agent 分析需求 → 写需求文档
2. 通过设计门禁 → 自动进入拆分
3. 批准拆分计划 → 自动落库任务
4. 任务逐个执行 → 自动推进状态
5. 全部完成 → 自动提交验收
6. 验收通过 → 自动归档

**全程无需人工催促！**

### 3. 人工介入点

虽然是自动模式，但关键决策仍需人确认：

#### 必须确认的门禁
- **计划批准**: 拆分计划需人审批（防止错误拆分）
- **设计确认**: 重大设计需人确认（可选）
- **验收通过**: 最终交付需人验收

#### Break Glass（紧急情况）
当自动流程卡住时，使用 `reqboard_clear_pause`：

```typescript
// 解除锁定，允许手动操作
await tools.reqboard_clear_pause({
  requirement_id: "REQ-xxxxxx"
});

// 现在可以手动干预
await tools.reqboard_move({ to: "design" });
```

**注意**: 这是紧急操作，正常流程不应使用。

## 完整工作流

```
draft (立项)
  ↓ 自动
brainstorming (需求分析)
  ↓ Agent 写需求文档
  ↓ 【确认门】需求文档确认
design (设计)
  ↓ Agent 写设计文档
  ↓ 【设计门禁】design_refs 覆盖检查
  ↓ 【确认门】设计确认（可选）
decomposing (拆分)
  ↓ Agent 写拆分计划
  ↓ 【确认门】计划批准（必须）
  ↓ 自动落库任务
implementing (实施)
  ↓ Agent 逐个执行任务
  ↓ 自动推进任务状态
accepting (验收)
  ↓ Agent 提交验收材料
  ↓ 【确认门】验收通过（必须）
  ↓ 自动归档（accepting.autoExecute = true）
archived (已归档)
```

## 阶段详解

### brainstorming (需求分析)
**Agent 自主**: 分析需求，提取功能点  
**产出**: `requirement.md` 包含 FR 列表  
**人工**: 确认需求文档

### design (设计)
**Agent 自主**: 设计架构、接口、数据模型  
**产出**: `design/` 目录下的设计文档  
**门禁**: 所有 FR 的 design_refs 已填写  
**人工**: 确认设计（可选）

### decomposing (拆分)
**Agent 自主**: 写拆分计划，定义任务依赖  
**产出**: `decomposition.md` + 任务表  
**门禁**: 所有 FR 的 task_refs 已覆盖  
**人工**: **必须批准计划**

### implementing (实施)
**Agent 自主**: 按依赖顺序执行任务  
**自动**: 任务完成后推进状态 (todo → in_progress → testing → done)  
**人工**: 无需介入（除非 break glass）

### accepting (验收)
**Agent 自主**: 提交验收材料  
**门禁**: 所有 FR 的 acceptance_status = passed  
**人工**: **必须验收通过**  
**自动**: 验收通过后自动归档

## 工具使用频率

### 高频工具（日常使用）
- `reqboard_status` - 查看需求状态
- `reqboard_task_run` - 执行任务（Dive Armed 核心）
- `reqboard_ask_confirm` - 确认门禁点

### 低频工具（特殊场景）
- `reqboard_clear_pause` - Break glass 紧急操作
- `reqboard_submit` - 提交产物（通常自动）
- `reqboard_task_report` - 任务汇报（通常自动）

### 已废弃工具（请勿使用）
- ~~`reqboard_decompose`~~ - 已删除，由 Dive Armed 自动处理
- ~~`reqboard_move`~~ - 已删除，由 Dive Armed 自动推进
- ~~`reqboard_task_move`~~ - 已删除，由 Dive Armed 自动推进

## 最佳实践

### ✅ 推荐做法

1. **信任自动流程**: 让 Agent 自主完成大部分工作
2. **关键点把关**: 计划批准和验收通过时仔细检查
3. **及时响应确认**: Agent 请求确认时尽快处理
4. **合理拆分任务**: 计划批准前确保任务粒度合适

### ❌ 避免做法

1. **频繁 clear_pause**: 这表明流程设计有问题
2. **跳过确认门**: 关键决策必须人工把关
3. **过度干预**: 不要在自动流程中频繁手动操作
4. **忽略门禁**: 门禁失败说明有问题，不要强行跳过

## 故障排查

### 流程卡住不动
**现象**: Agent 一直不推进  
**排查**: 
1. `reqboard_status` 查看当前状态
2. 检查是否在等待人工确认
3. 查看 Agent 日志是否有错误

### 门禁检查失败
**现象**: design_refs / task_refs 覆盖不全  
**解决**:
1. 检查需求文档中的 FR 列表
2. 确认所有 FR 都有对应的 refs
3. 更新文档后重新提交

### 任务执行失败
**现象**: 任务状态卡在 in_progress  
**排查**:
1. 查看任务日志
2. 检查任务验收标准是否明确
3. 必要时 clear_pause 后手动完成

## 配置说明

### accepting 自动归档

```typescript
// packages/web/dsh-pmboard/src/application/dive/stage-configs.ts
accepting: {
  requiresConfirmation: true,
  autoExecute: true,  // 验收通过后自动归档
  maxRounds: 5,
  description: '验收阶段，需人工验收'
}
```

### Dive Armed 默认开启

```typescript
// reqboard_create / reqboard_capture 自动设置
dive: {
  activation: 'armed',  // 默认模式
  phase: 'brainstorming',
  roundsCompleted: 0
}
```

## 总结

Dive Armed 是项目看板的**唯一工作方式**：

- ✅ 自动推进流程
- ✅ 关键点人工把关
- ✅ 减少重复劳动
- ✅ 提高交付效率

不再需要手动调用 decompose/move/task_move，让 Agent 自主完成整个流程！
