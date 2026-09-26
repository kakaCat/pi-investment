# RTM 创建和更新时机修正

> 修正日期：2026-09-26  
> 核心问题：RTM 应该在提交时创建，还是在门禁通过后创建？

---

## 🎯 关键问题

### 您的问题

**"提交通过校验，才开始创建和更新 RTM 是吗？"**

### 两种理解

#### 理解A：立项时就创建骨架 ❓
- 立项 → 立即创建 RTM 骨架
- 每个阶段提交 → 更新 RTM
- 无论是否通过校验

#### 理解B：门禁通过后才创建/更新 ❓
- 立项 → 不创建 RTM
- 提交需求文档 → 校验通过 → **才创建** RTM
- 提交设计文档 → 校验通过 → **才更新** RTM
- 门禁拒绝 → RTM 不变

---

## 📊 门禁流程分析

### 当前的门禁设计

```
用户提交文档
  ↓
校验门禁
  ├─ 通过 → 登记产物 → 人工确认 → 推进阶段
  └─ 拒绝 → 提示错误 → 不登记
```

### RTM 应该在哪一步？

```
选项1：提交时立即更新（无论是否通过校验）
用户提交文档
  ├─ 立即更新 RTM ← 这里
  ↓
校验门禁
  ├─ 通过 → 登记产物
  └─ 拒绝 → 回滚 RTM？

选项2：校验通过后才更新（推荐）✅
用户提交文档
  ↓
校验门禁
  ├─ 通过 → 登记产物 → 更新 RTM ← 这里
  └─ 拒绝 → RTM 不变
```

---

## ✅ 推荐：校验通过后才创建/更新

### 理由

1. **数据一致性**
   - RTM 应该反映"已通过校验"的状态
   - 如果提交被拒绝，RTM 不应该包含无效数据

2. **避免回滚**
   - 提交时更新 → 校验失败 → 需要回滚 RTM（复杂）
   - 校验通过后更新 → 失败不更新（简单）

3. **与产物登记一致**
   - 产物在校验通过后才登记
   - RTM 应该与产物登记同步

4. **门禁是质量关卡**
   - 通过门禁 = 质量合格
   - RTM 只记录合格的数据

---

## 🔄 修正后的流程

### 阶段1：立项

```
reqboard_create（创建需求）
  ↓
需求记录写入台账
  ↓
✅ 创建 RTM 骨架（无需校验）
  ├─ rtm-lifecycle.yml（current_stage: draft）
  └─ rtm-traceability.yml（空映射）
```

**为什么立项时就创建？**
- 立项本身就是一个决策，没有"校验"
- RTM 骨架是占位符，不包含业务数据

---

### 阶段2：需求分析

```
reqboard_submit(kind=requirement)
  ↓
读取 requirement.md
  ↓
门禁校验：checkRequirementDocFormatGate
  ├─ 拒绝 → 返回错误 → RTM 不变 ❌
  └─ 通过 ↓
  
登记产物（kind=requirement）
  ↓
✅ 更新 RTM（提取 FR 列表）
  ├─ rtm-lifecycle: brainstorming.status = completed
  └─ rtm-traceability: 初始化 fr_to_design 空映射
  ↓
等待人工确认
  ↓
人工确认通过
  ↓
✅ 更新 RTM（标记已确认）
  └─ rtm-lifecycle: brainstorming.artifacts[0].confirmed = true
  ↓
推进到下一阶段（design）
  ↓
✅ 更新 RTM（推进节点）
  └─ rtm-lifecycle: current_stage = design
```

**关键点**：
- ❌ 门禁拒绝 → RTM 不变
- ✅ 门禁通过 + 产物登记 → 更新 RTM
- ✅ 人工确认 → 更新 RTM
- ✅ 推进阶段 → 更新 RTM

---

### 阶段3：设计

```
reqboard_submit(kind=design)
  ↓
扫描 design/*.md
  ↓
门禁校验：checkDesignServesGate（检查 serves 标注）
  ├─ 拒绝（缺少 serves）→ 返回错误 → RTM 不变 ❌
  └─ 通过 ↓
  
登记产物（kind=design）
  ↓
✅ 更新 RTM（提取设计章节 + serves 映射）
  └─ rtm-traceability: fr_to_design 映射填充
  ↓
人工确认
  ↓
✅ 更新 RTM（标记已确认）
  ↓
推进到 decomposing
  ↓
✅ 更新 RTM（推进节点）
  └─ rtm-lifecycle: current_stage = decomposing
```

---

### 阶段4：拆分

```
reqboard_submit(kind=plan)
  ↓
解析 decomposition.md
  ↓
门禁校验：assertClauseCoverageGate（检查 FR 覆盖）
  ├─ 拒绝（有 FR 未覆盖）→ 返回错误 → RTM 不变 ❌
  └─ 通过 ↓
  
登记产物（kind=decomposition）
  ↓
等待人工批准
  ↓
人工批准（reqboard_ask_confirm target=plan）
  ↓
创建任务到台账
  ↓
✅ 更新 RTM（提取任务追溯）
  ├─ rtm-traceability: design_to_tasks 映射填充
  └─ rtm-lifecycle: implementing.tasks_total = 8
  ↓
推进到 implementing
  ↓
✅ 更新 RTM（推进节点）
  └─ rtm-lifecycle: current_stage = implementing
```

---

### 阶段5：实施

```
reqboard_task_move（任务状态变更）
  ↓
校验状态转移（assertTaskTransition）
  ├─ 拒绝（非法状态转移）→ 返回错误 → RTM 不变 ❌
  └─ 通过 ↓
  
更新台账任务状态
  ↓
✅ 更新 RTM（重新统计）
  └─ rtm-lifecycle: implementing.tasks_done++
  ↓
（如果所有任务完成）
  ↓
✅ 更新 RTM（推进节点）
  └─ rtm-lifecycle: current_stage = accepting
```

**特殊性**：
- 任务状态变更频繁
- 每次合法状态转移都更新 RTM
- 不需要人工确认

---

### 阶段6：验收

```
reqboard_submit(kind=verification)
  ↓
扫描测试文档
  ↓
门禁校验：assertFullTraceabilityGate（检查追溯完整性）
  ├─ 拒绝（测试覆盖度不足）→ 返回错误 → RTM 不变 ❌
  └─ 通过 ↓
  
登记产物（kind=verification）
  ↓
✅ 更新 RTM（提取测试用例 + covers 映射）
  └─ rtm-traceability: task_to_tests 映射填充
  ↓
生成验收单
  ↓
人工验收（逐项通过/失败）
  ↓
验收通过
  ↓
推进到 archived
  ↓
✅ 更新 RTM（最终快照）
  └─ rtm-lifecycle: current_stage = archived
```

---

## 📊 总结：RTM 更新的触发条件

| 事件 | 校验门禁 | 更新 RTM | 时机 |
|------|---------|---------|------|
| **立项** | 无 | ✅ 立即创建骨架 | 创建需求后 |
| **提交需求文档** | checkRequirementDocFormatGate | ✅ 通过后更新 | 产物登记后 |
| **确认需求** | 无 | ✅ 立即更新 | 人工确认后 |
| **提交设计文档** | checkDesignServesGate | ✅ 通过后更新 | 产物登记后 |
| **提交拆分计划** | assertClauseCoverageGate | ❌ 不更新 | 等待批准 |
| **批准计划** | 无 | ✅ 立即更新 | 批准后 + 创建任务后 |
| **任务状态变更** | assertTaskTransition | ✅ 通过后更新 | 状态更新后 |
| **提交验收材料** | assertFullTraceabilityGate | ✅ 通过后更新 | 产物登记后 |
| **验收通过** | 无 | ✅ 立即更新 | 人工验收后 |
| **归档** | 无 | ✅ 最终快照 | 归档后 |

---

## 🔍 特殊情况处理

### 情况1：门禁拒绝

```
用户提交设计文档（缺少 serves 标注）
  ↓
checkDesignServesGate: 拒绝
  ↓
返回错误：DESIGN_SERVES_MISSING
  ↓
❌ RTM 不变（保持上一个有效状态）
```

### 情况2：人工确认拒绝

```
用户提交需求文档
  ↓
门禁通过 → 产物登记 → RTM 更新（提取 FR）
  ↓
人工确认：需要修改
  ↓
❌ RTM 标记"待同步"（不回滚，等待重新提交）
  ↓
用户修改后重新提交
  ↓
门禁通过 → RTM 更新（change_note 记录变更）
```

### 情况3：重新提交

```
第一次提交设计文档
  ↓
门禁通过 → RTM 更新（fr_to_design v1）
  ↓
人工确认：需要修改
  ↓
用户修改设计
  ↓
第二次提交设计文档（change_note 必填）
  ↓
门禁通过 → RTM 更新（fr_to_design v2）
  ↓
✅ RTM 版本号 +1
```

---

## ✅ 核心原则

### 1. 校验通过才更新

**RTM 只记录通过校验的数据**
- ✅ 门禁通过 → 更新 RTM
- ❌ 门禁拒绝 → RTM 不变

### 2. 与产物登记同步

**RTM 更新与产物登记同步发生**
- 产物登记成功 → 同时更新 RTM
- 产物登记失败 → RTM 不变

### 3. 人工确认后更新

**人工确认/批准也触发 RTM 更新**
- 确认通过 → 更新 RTM（标记已确认）
- 确认拒绝 → RTM 标记"待同步"

### 4. 版本号追踪

**每次更新 RTM 版本号 +1**
- 便于追踪变更历史
- Git 配合版本管理

---

## 🔧 代码实现示意

```typescript
// 提交需求文档
async function submitRequirement(docs, req) {
  // 1. 校验门禁
  const gateResult = checkRequirementDocFormatGate(docs, req)
  if (gateResult.failed) {
    return reject(gateResult.message)  // ❌ RTM 不变
  }
  
  // 2. 登记产物
  const artifact = registerArtifact(req, 'requirement')
  
  // 3. ✅ 更新 RTM（校验通过后）
  await updateRTM(req, {
    lifecycle: {
      stages: {
        brainstorming: { status: 'completed' }
      }
    },
    traceability: {
      fr_to_design: extractFRs(docs, req)  // 初始化空映射
    }
  })
  
  return { success: true }
}

// 批准拆分计划
async function approvePlan(req) {
  // 1. 创建任务到台账
  const tasks = createTasksFromPlan(req)
  
  // 2. ✅ 更新 RTM（批准后）
  await updateRTM(req, {
    lifecycle: {
      current_stage: 'implementing',
      stages: {
        decomposing: { status: 'completed' },
        implementing: {
          status: 'in_progress',
          tasks_total: tasks.length
        }
      }
    },
    traceability: {
      design_to_tasks: extractDesignToTasks(tasks)
    }
  })
  
  return { success: true }
}
```

---

## 📝 最终确认

**RTM 创建和更新的正确时机**：

1. ✅ **立项时立即创建骨架**（无需校验）
2. ✅ **门禁通过后更新**（提交需求/设计/验收）
3. ✅ **人工确认/批准后更新**（确认需求/批准计划）
4. ✅ **状态变更通过后更新**（任务状态变更）
5. ❌ **门禁拒绝时不更新**（保持上一个有效状态）

**核心原则**：RTM 只记录通过校验的、有效的数据
