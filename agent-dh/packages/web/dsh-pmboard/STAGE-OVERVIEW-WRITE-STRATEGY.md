# StageOverview 数据写入策略分析

> 分析日期：2026-09-26  
> 核心问题：引入 RTM 后，StageOverview 之前写入的数据还继续写入吗？

---

## 🎯 核心理解

### StageOverview 是什么？

**StageOverview 不是存储，是查询投影**

```typescript
// StageOverview 是实时组装的视图，不是持久化数据
export async function queryStageOverview(deps, requirementId) {
  const snapshot = deps.repo.snapshot()  // ← 从台账读取
  const req = snapshot.requirements.find(r => r.id === requirementId)
  return assembleStageOverview(req, snapshot)  // ← 实时组装
}
```

**关键点**：
- ❌ StageOverview **不写入任何地方**
- ✅ StageOverview 是从台账**实时组装**的
- ✅ 每次请求都重新组装

---

## 📊 数据存储位置

### 当前数据存储（没有 RTM）

```
数据持久化位置：
  └─ dsh-reqboard.json（台账）
      ├─ requirements[] - 需求记录
      │   ├─ id, title, status, category
      │   ├─ artifacts[] - 产物列表
      │   └─ timeline[] - 状态事件
      └─ tasks[] - 任务记录
          ├─ id, title, status, phase
          └─ requirementId

查询视图（不持久化）：
  └─ StageOverview（实时组装）
      └─ assembleStageOverview(req, snapshot)
```

### 引入 RTM 后的数据存储

```
数据持久化位置：
  ├─ dsh-reqboard.json（台账）← 继续写入
  │   ├─ requirements[]
  │   └─ tasks[]
  │
  └─ rtm-*.yml（新增）← 新增写入
      ├─ rtm-lifecycle.yml
      ├─ rtm-implementing.yml
      └─ ...

查询视图（不持久化）：
  └─ StageOverview（实时组装）← 继续组装
      └─ assembleStageOverview(req, snapshot)
      └─ 未来可集成 RTM 数据
```

---

## ✅ 答案

### 台账继续写入 ✅

**所有基础数据继续写入台账**：

```typescript
// 1. 创建需求 → 写入台账
await deps.repo.mutate('requirement-created', {
  requirement: { id, title, status, category, ... }
})

// 2. 任务状态变更 → 写入台账
await deps.repo.mutate('task-status-updated', {
  taskId, status, ...
})

// 3. 推进节点 → 写入台账
await deps.repo.mutate('requirement-status-updated', {
  requirementId, status, ...
})
```

**为什么继续写入？**
- ✅ 台账是唯一事实来源（Single Source of Truth）
- ✅ StageOverview 从台账组装
- ✅ RTM 也从台账同步

### RTM 新增写入 ✨

**追溯关系和覆盖度写入 RTM**：

```typescript
// 提交设计文档后 → 写入 RTM
await updateRTM(req, {
  traceability: {
    fr_to_design: { FR-1: [...], FR-2: [...] }
  },
  coverage: {
    design: { total: 3, covered: 2, rate: 67 }
  }
})

// 任务状态变更后 → 同步写入 RTM
await updateRTM(req, {
  status: {
    tasks_done: 5,
    task_details: [...]
  }
})
```

**为什么新增写入？**
- ✅ RTM 提供缓存（性能优化）
- ✅ RTM 记录追溯关系（台账没有）
- ✅ RTM 记录覆盖度统计（台账没有）

### StageOverview 继续组装 ✅

**StageOverview 继续从台账实时组装**：

```typescript
// 现在
const overview = assembleStageOverview(req, snapshot)

// 未来（集成 RTM）
const overview = assembleStageOverview(req, snapshot)
const implRTM = readYAML('rtm-implementing.yml')
overview.stages.implementing.body.traceability = implRTM.traceability
```

**为什么继续组装？**
- ✅ StageOverview 是查询视图，不是存储
- ✅ 基础数据从台账组装（保持不变）
- ✅ 追溯数据从 RTM 读取（新增）

---

## 🔄 完整数据流（引入 RTM 后）

### 写入流程

```
用户操作
  ↓
reqboard_* 工具
  ↓
┌──────────────────┐
│ 1. 写入台账       │← 继续写入
│   requirements[] │
│   tasks[]        │
└──────────────────┘
  ↓
┌──────────────────┐
│ 2. 写入 RTM      │← 新增写入
│   rtm-*.yml      │
│   （追溯+覆盖度）│
└──────────────────┘
```

### 查询流程

```
GET /api/stage-overview/:id
  ↓
┌──────────────────────┐
│ 1. 从台账组装         │← 继续组装
│   assembleStageOverview│
│   (req, snapshot)     │
└──────────────────────┘
  ↓
┌──────────────────────┐
│ 2. 读取 RTM（可选）   │← 新增读取
│   readYAML(rtm-*.yml)│
│   合并追溯数据        │
└──────────────────────┘
  ↓
返回 StageOverview（增强版）
```

---

## 📊 数据对比

### 台账（dsh-reqboard.json）

**写入内容**：
- ✅ 需求基础信息（id/title/status/category）
- ✅ 产物列表（artifacts[]）
- ✅ 状态事件（timeline[]）
- ✅ 任务基础信息（id/title/status/phase）
- ❌ **不写入追溯关系**
- ❌ **不写入覆盖度统计**

**继续写入** ✅

### RTM YAML

**写入内容**：
- ✅ 追溯关系（FR → 设计 → 任务 → 测试）
- ✅ 覆盖度统计（design/implementation/testing）
- ✅ 节点输入输出
- ✅ 任务状态（从台账同步）
- ❌ **不写入需求基础信息**（从台账读取）

**新增写入** ✨

### StageOverview

**是查询视图，不持久化** ❌

**组装逻辑**：
- ✅ 从台账读取基础数据
- ✅ 从 RTM 读取追溯数据（未来）

**继续组装** ✅

---

## 💡 为什么这样设计？

### 1. 单一事实来源（台账）

**台账是唯一权威数据源**：
- ✅ 需求状态（status）
- ✅ 任务状态（status）
- ✅ 产物列表（artifacts）
- ✅ 状态事件（timeline）

**保证**：
- 所有系统都从台账读取基础数据
- 数据一致性有保证

### 2. RTM 是增强缓存

**RTM 提供额外数据和性能优化**：
- ✅ 追溯关系（台账没有）
- ✅ 覆盖度统计（台账没有）
- ✅ 缓存读取（性能优化）

**保证**：
- RTM 的基础数据从台账同步
- RTM 不替代台账，只增强

### 3. StageOverview 是视图

**StageOverview 是实时组装的查询视图**：
- ✅ 不持久化
- ✅ 从台账组装基础数据
- ✅ 从 RTM 读取追溯数据（未来）

**保证**：
- 永远最新（实时组装）
- 可以集成任何数据源

---

## ✅ 总结

### 回答您的问题

**"StageOverview 之前写入的数据还继续写入吗？"**

**答案**：

1. ❌ **StageOverview 从来不写入**
   - StageOverview 是查询视图，不是存储
   - 它是从台账实时组装的

2. ✅ **台账继续写入**
   - 需求基础信息
   - 任务基础信息
   - 产物列表、状态事件

3. ✨ **RTM 新增写入**
   - 追溯关系（新增）
   - 覆盖度统计（新增）
   - 任务状态（从台账同步）

4. ✅ **StageOverview 继续组装**
   - 从台账读取基础数据（保持不变）
   - 从 RTM 读取追溯数据（未来新增）

---

## 🔑 核心理念

**数据分层架构**：

```
存储层：
  ├─ 台账（dsh-reqboard.json）← 唯一事实来源
  └─ RTM (rtm-*.yml)          ← 增强缓存

查询层：
  └─ StageOverview            ← 实时组装视图
```

**原则**：
- ✅ 台账 = 唯一事实来源
- ✅ RTM = 追溯关系 + 性能缓存
- ✅ StageOverview = 查询视图（不持久化）
