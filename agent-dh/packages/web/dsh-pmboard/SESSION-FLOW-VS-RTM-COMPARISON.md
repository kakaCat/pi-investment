# 会话流程图数据 vs RTM 数据对比

> 分析日期：2026-09-26  
> 核心问题：会话右上角的流程图数据和 RTM 的数据是否一致？

---

## 🎯 答案

**基础数据一致，RTM 有额外数据**：

### 1. ✅ 一致的数据（都从台账读取）

| 数据 | 会话流程图（StageOverview）| RTM |
|------|-------------------------|-----|
| 当前节点 | currentStage | lifecycle.current_stage |
| 节点状态 | stages[].enabled | lifecycle.stages[].status |
| 任务列表 | body.tasks | task_details |
| 任务状态 | task.status | task_details[].status |

**保证一致**：都从台账（dsh-reqboard.json）读取

### 2. ✨ RTM 独有数据（从文档解析）

| 数据 | 会话流程图 | RTM |
|------|-----------|-----|
| **追溯关系** | ❌ 无 | ✅ FR→设计→任务→测试 |
| **覆盖度统计** | ❌ 无 | ✅ 67% / 100% / 25% |
| **节点输入输出** | ❌ 无 | ✅ inputs/outputs |
| **版本追踪** | ❌ 无 | ✅ version +1 |

---

## 📊 数据来源对比

### 会话流程图（现在）

```
台账（dsh-reqboard.json）
  ↓ 实时读取
assembleStageOverview()
  ↓
StageOverview
  ↓
会话右上角流程图
```

**特点**：
- ✅ 实时查询，永远最新
- ❌ 每次都要组装（~10ms）
- ❌ 没有追溯关系

### RTM（设计中）

```
台账 + 文档（*.md）
  ↓ 状态变更时更新
rtm-*.yml（缓存）
  ↓ 直接读取
会话节点追溯 Tab
```

**特点**：
- ✅ 缓存读取，极快（~1ms）
- ✅ 包含追溯关系
- ⚠️ 需要保证与台账同步

---

## 🔄 一致性保证机制

### 更新时机

**RTM 更新时从台账同步**：

```typescript
// 任务状态变更时
reqboard_task_move(task_id, new_status)
  ↓
1. 更新台账（tasks.json）
   task.status = new_status
  ↓
2. 更新 RTM（rtm-implementing.yml）
   从台账重新统计：
   - tasks_done = tasks.filter(t => t.status === 'done').length
   - task_details[i].status = new_status
```

**保证**：
- ✅ RTM 的任务状态 = 台账的任务状态
- ✅ StageOverview 的任务状态 = 台账的任务状态
- ✅ **RTM = StageOverview**（基础数据）

---

## 💡 未来集成方案

### StageOverview 可以读取 RTM

```typescript
// 未来：assembleStageOverview 集成 RTM
async function assembleStageOverview(req, snapshot, deps) {
  // 现有逻辑：从台账组装基础数据
  const overview = assembleFromLedger(req, snapshot)
  
  // 新增：读取 RTM 追溯数据
  const implRTM = readYAML('rtm-implementing.yml')
  
  // 合并到 StageOverview
  overview.stages.implementing.body.traceability = implRTM.traceability
  overview.stages.implementing.body.coverage = implRTM.coverage
  
  return overview
}
```

**好处**：
- ✅ 会话流程图可以显示追溯关系
- ✅ 会话流程图可以显示覆盖度
- ✅ 一次 API 调用获取完整数据
