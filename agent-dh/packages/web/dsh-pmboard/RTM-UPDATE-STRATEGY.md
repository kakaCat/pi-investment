# 修改需求时 RTM 的更新策略

> 分析日期：2026-09-26  
> 核心问题：需求修改后，RTM 数据如何处理？

---

## 🎯 场景分析

### 场景1：修改需求文档（brainstorming 阶段）

#### 初次提交

```
用户提交 requirement.md
  - FR-1: 删除过时工具
  - FR-2: Dive Armed 默认化
  ↓
门禁通过 → 产物登记
  ↓
✅ 生成/更新 RTM
  rtm-traceability.yml:
    fr_to_design:
      FR-1: []
      FR-2: []
```

#### 人工确认：需要修改

```
人工反馈："FR-2 描述不清楚，需要补充细节"
  ↓
❌ RTM 标记"待同步"（但不删除）
  rtm-lifecycle.yml:
    brainstorming:
      artifacts:
        - kind: requirement
          confirmed: false  # 取消确认
          pending_sync: true  # 标记待同步
          change_note: "FR-2 描述不清楚"
```

#### 用户修改后重新提交

```
用户修改 requirement.md
  - FR-1: 删除过时工具
  - FR-2: Dive Armed 默认化（补充了详细描述）
  - FR-3: 新增功能（新增）← 新增的 FR
  ↓
门禁通过 → 产物登记（change_note 必填）
  ↓
✅ 重新生成/更新 RTM
  rtm-traceability.yml:
    fr_to_design:
      FR-1: []        # 保持不变
      FR-2: []        # 保持不变
      FR-3: []        # 新增
    version: 2        # 版本号 +1
```

**策略**：
- ✅ **增量更新**（新增 FR-3）
- ✅ **保留旧数据**（FR-1, FR-2 不变）
- ✅ **版本号递增**（追踪变更）

---

### 场景2：修改设计文档（design 阶段）

#### 初次提交

```
用户提交 design/architecture.md
  ## 1.1 删除工具目录
  `serves: FR-1`
  
  ## 1.2 删除 use-case
  `serves: FR-1`
  ↓
门禁通过 → 产物登记
  ↓
✅ 生成/更新 RTM
  rtm-traceability.yml:
    fr_to_design:
      FR-1: [design/architecture#1.1, design/architecture#1.2]
      FR-2: []  # 未覆盖
```

#### 人工确认：需要修改

```
人工反馈："缺少 FR-2 的设计"
  ↓
❌ RTM 标记"待同步"
  rtm-lifecycle.yml:
    design:
      artifacts:
        - file: design/architecture.md
          confirmed: false
          pending_sync: true
          change_note: "缺少 FR-2 的设计"
```

#### 用户补充设计后重新提交

```
用户修改 design/architecture.md
  ## 1.1 删除工具目录
  `serves: FR-1`
  
  ## 1.2 删除 use-case
  `serves: FR-1`
  
  ## 2 配置变更（新增）← 新增章节
  `serves: FR-2`
  ↓
门禁通过 → 产物登记（change_note 必填）
  ↓
✅ 重新生成/更新 RTM
  rtm-traceability.yml:
    fr_to_design:
      FR-1: [design/architecture#1.1, design/architecture#1.2]  # 保持不变
      FR-2: [design/architecture#2]  # 新增
    version: 3
```

**策略**：
- ✅ **增量更新**（新增 design/architecture#2）
- ✅ **保留旧映射**（FR-1 的映射不变）
- ✅ **重新扫描**（全文件扫描，确保完整）

---

### 场景3：删除设计章节

#### 用户删除了某个章节

```
用户修改 design/architecture.md
  ## 1.1 删除工具目录
  `serves: FR-1`
  
  ## 1.2 删除 use-case（删除）← 章节被删除
  `serves: FR-1`  ← 这个没了
  
  ## 2 配置变更
  `serves: FR-2`
  ↓
门禁通过 → 产物登记（change_note: "删除了 1.2 章节"）
  ↓
✅ 重新生成 RTM
  rtm-traceability.yml:
    fr_to_design:
      FR-1: [design/architecture#1.1]  # ← 1.2 被移除
      FR-2: [design/architecture#2]
    version: 4
```

**策略**：
- ✅ **完全重建映射**（扫描当前文档，重新生成）
- ✅ **不保留已删除的引用**
- ⚠️ **可能影响下游**（如果任务已经引用了 design/architecture#1.2）

---

### 场景4：任务已创建后，修改设计

#### 当前状态

```
rtm-traceability.yml:
  fr_to_design:
    FR-1: [design/architecture#1.1, design/architecture#1.2]
  
  design_to_tasks:
    design/architecture#1.1: [t-354ea0]
    design/architecture#1.2: [t-0c18e3]  # 任务已创建
```

#### 用户删除设计章节 1.2

```
用户修改 design/architecture.md（删除 1.2 章节）
  ↓
门禁通过 → 产物登记
  ↓
✅ 重新生成 RTM
  rtm-traceability.yml:
    fr_to_design:
      FR-1: [design/architecture#1.1]  # 1.2 被移除
    
    design_to_tasks:
      design/architecture#1.1: [t-354ea0]
      design/architecture#1.2: [t-0c18e3]  # ⚠️ 孤儿任务！
    
    orphan_tasks:  # 新增字段：孤儿任务
      - task_id: t-0c18e3
        reason: "implements 的设计章节 design/architecture#1.2 已被删除"
```

**策略**：
- ✅ **标记孤儿任务**（design_serves 指向的设计不存在）
- ⚠️ **不自动删除任务**（任务已创建，可能已开始实施）
- ✅ **提示需要人工处理**（重新分配或删除孤儿任务）

---

## 📊 RTM 更新策略总结

### 策略1：增量更新（推荐）✅

**适用场景**：新增内容
- 新增 FR
- 新增设计章节
- 新增任务

**操作**：
```typescript
function updateRTMIncremental(oldRTM, newData) {
  return {
    ...oldRTM,
    traceability: {
      fr_to_design: {
        ...oldRTM.traceability.fr_to_design,  // 保留旧数据
        ...newData.fr_to_design                // 合并新数据
      }
    },
    version: oldRTM.version + 1
  }
}
```

**优点**：
- ✅ 保留历史数据
- ✅ 不破坏已有映射
- ✅ 性能好

---

### 策略2：完全重建（某些场景必需）

**适用场景**：删除内容
- 删除 FR
- 删除设计章节
- 重命名章节

**操作**：
```typescript
function rebuildRTM(docs, req, tasks) {
  // 1. 重新扫描文档
  const frs = extractFRs(docs, req)
  const designs = extractAllDesignSections(docs, req)
  
  // 2. 重新构建映射
  const frToDesign = buildFRToDesignMap(designs)
  const designToTasks = buildDesignToTasksMap(tasks)
  
  // 3. 检测孤儿任务
  const orphanTasks = detectOrphanTasks(designToTasks, designs)
  
  return {
    traceability: { frToDesign, designToTasks },
    orphan_tasks: orphanTasks,
    version: oldRTM.version + 1
  }
}
```

**优点**：
- ✅ 数据一致性
- ✅ 能检测删除
- ✅ 能发现孤儿

**缺点**：
- ⚠️ 性能稍差（需要扫描）

---

### 策略3：混合策略（最佳实践）✅

**判断逻辑**：
```typescript
function updateRTM(docs, req, tasks, changeNote) {
  // 如果 change_note 包含"删除"关键词 → 完全重建
  if (changeNote && (changeNote.includes('删除') || changeNote.includes('移除'))) {
    return rebuildRTM(docs, req, tasks)
  }
  
  // 否则 → 增量更新
  return updateRTMIncremental(oldRTM, extractNewData(docs))
}
```

---

## 🔍 特殊情况处理

### 情况1：修改 FR 编号

```
原来：FR-1, FR-2, FR-3
修改后：FR-1, FR-2a, FR-2b, FR-3  （FR-2 拆分成 2a/2b）
```

**处理**：
- ✅ 完全重建 RTM
- ✅ 标记受影响的设计章节
- ⚠️ 提示：设计章节的 `serves: FR-2` 需要更新

---

### 情况2：重命名设计章节

```
原来：design/architecture.md#1.1
修改后：design/architecture.md#1-工具删除  （标题改了）
```

**处理**：
- ✅ 完全重建 RTM
- ✅ 标记孤儿任务（引用旧 ref 的任务）
- ⚠️ 提示：任务的 design_serves 需要更新

---

### 情况3：合并设计章节

```
原来：1.1 删除工具目录 + 1.2 删除 use-case
修改后：1 删除工具（合并）
```

**处理**：
- ✅ 完全重建 RTM
- ✅ 检测多个任务现在指向同一章节
- ✅ 合并 design_to_tasks 映射

---

## ✅ 最终策略

### 默认：增量更新

**大部分情况**（新增内容）：
- ✅ 增量更新 RTM
- ✅ 保留旧数据
- ✅ 版本号 +1

### 检测到删除：完全重建

**change_note 包含删除关键词**：
- ✅ 完全重建 RTM
- ✅ 检测孤儿任务/设计
- ✅ 提示需要人工处理

### 下游已创建：标记孤儿

**任务已创建后，设计被删除**：
- ✅ 标记孤儿任务
- ⚠️ 不自动删除（可能已开始实施）
- ✅ 提示需要人工决策

---

## 🔧 代码实现示意

```typescript
async function updateRTMOnDocumentChange(
  docs: DocsReader,
  req: RequirementRecord,
  tasks: TaskRecord[],
  changeNote?: string
) {
  const rtmPath = `docs/requirements/${req.id}/rtm-traceability.yml`
  const oldRTM = await readYAML(rtmPath)
  
  let newRTM: RTM
  
  // 判断更新策略
  if (changeNote && isDestructiveChange(changeNote)) {
    // 策略：完全重建
    console.log('检测到删除操作，完全重建 RTM')
    newRTM = await rebuildRTM(docs, req, tasks)
    
    // 检测孤儿
    if (newRTM.orphan_tasks?.length > 0) {
      console.warn(`发现 ${newRTM.orphan_tasks.length} 个孤儿任务`)
    }
  } else {
    // 策略：增量更新
    console.log('增量更新 RTM')
    const newData = await extractNewData(docs, req)
    newRTM = mergeRTM(oldRTM, newData)
  }
  
  // 版本号 +1
  newRTM.metadata.version = oldRTM.metadata.version + 1
  newRTM.metadata.last_updated = new Date().toISOString()
  
  // 写回文件
  await writeYAML(rtmPath, newRTM)
  
  return newRTM
}

function isDestructiveChange(changeNote: string): boolean {
  const keywords = ['删除', '移除', '重命名', '合并', '拆分']
  return keywords.some(kw => changeNote.includes(kw))
}
```

---

## 📝 总结

### 修改需求时，RTM 会重新修改吗？

**答案**：**会**，但采用智能策略

1. **新增内容** → 增量更新（保留旧数据）
2. **删除内容** → 完全重建（检测孤儿）
3. **下游已创建** → 标记冲突（人工决策）

### 核心原则

- ✅ **保留历史**（增量更新为主）
- ✅ **检测冲突**（完全重建检测孤儿）
- ✅ **版本追踪**（每次更新 version +1）
- ✅ **人工决策**（重大冲突提示人工处理）
