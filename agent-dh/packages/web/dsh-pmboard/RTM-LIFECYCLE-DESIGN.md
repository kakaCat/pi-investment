# RTM YAML 重新设计：从立项开始的全生命周期追溯

> 设计日期：2026-09-26  
> 核心理念：RTM YAML 是立项内部流程的完整数据记录

---

## 🎯 重新理解需求

### 之前的误解

❌ **误解**：RTM YAML 在批准计划时才生成
❌ **误解**：RTM 只记录设计→任务→测试的追溯

### 正确的理解

✅ **正确**：RTM YAML 从立项开始就创建，记录整个需求生命周期
✅ **正确**：RTM 是需求内部流程的数据记录本，不是外部管理工具

---

## 📊 RTM YAML 的定位

### 对比：看板 vs RTM

| 维度 | 看板（dsh-pmboard） | RTM YAML |
|------|-------------------|----------|
| **作用** | 多需求管理（项目级） | 单需求内部流程记录 |
| **粒度** | 需求列表、状态流转 | 需求内部的追溯链 |
| **生命周期** | 跨需求、持续运行 | 跟随单个需求 |
| **数据源** | 台账（requirements.json） | 文档 + 台账合成 |
| **用户** | PM + 多个 Agent | 单个需求的执行者 |

### RTM 的角色

**RTM YAML = 需求内部的"行车记录仪"**

- 📝 立项时创建（骨架）
- 📈 需求分析阶段：记录 FR 提取
- 🎨 设计阶段：记录设计章节 + serves 关系
- 🔀 拆分阶段：记录任务 + implements 关系
- ⚙️ 实施阶段：更新任务状态
- ✅ 验收阶段：记录测试 + covers 关系
- 📦 归档阶段：最终快照

---

## 🗂️ RTM YAML 生命周期

### 阶段1：立项（draft → brainstorming）

**时机**：`reqboard_create` 创建需求时

**生成内容**：
```yaml
# docs/requirements/REQ-xxx/rtm.yml

requirement_id: REQ-260925234037-1503
title: 优化 Dive Armed 模式的工具提示词与文档
category: feature
created_at: 2026-09-26T10:00:00Z

# 需求文档尚未提交，FR 列表为空
requirements: []

# 设计尚未开始
design_sections: []

# 任务尚未拆分
tasks: []

# 测试尚未编写
test_cases: []

# 追溯链状态
lifecycle:
  current_stage: draft
  stages_completed: []
  last_updated: 2026-09-26T10:00:00Z
```

### 阶段2：需求分析（brainstorming）

**时机**：`reqboard_submit(kind=requirement)` 提交需求文档后

**更新内容**：
```yaml
# 从 requirement.md 提取 FR
requirements:
  - id: FR-1
    title: 删除过时工具
    description: 删除 DecomposeTool/MoveTool/TaskMoveTool 及其代码
    source: requirement.md
    line: 42
    
  - id: FR-2
    title: Dive Armed 默认化
    description: 新需求默认 armed 模式
    source: requirement.md
    line: 56

lifecycle:
  current_stage: brainstorming
  stages_completed: [draft]
  last_updated: 2026-09-26T11:30:00Z
```

### 阶段3：设计（design）

**时机**：`reqboard_submit(kind=design)` 提交设计文档后

**更新内容**：
```yaml
# 从 design/*.md 提取设计章节
design_sections:
  - ref: design/architecture#1
    title: 工具删除架构
    file: design/architecture.md
    section: "1"
    serves: [FR-1]  # 从 \`serves: FR-1\` 提取
    
  - ref: design/architecture#1.1
    title: 删除工具目录结构
    file: design/architecture.md
    section: "1.1"
    serves: [FR-1]
    
  - ref: design/architecture#2
    title: 配置变更
    file: design/architecture.md
    section: "2"
    serves: [FR-2, FR-6]

lifecycle:
  current_stage: design
  stages_completed: [draft, brainstorming]
  last_updated: 2026-09-26T14:00:00Z
```

### 阶段4：拆分（decomposing）

**时机**：批准拆分计划后（`reqboard_ask_confirm(target=plan)` 批准）

**更新内容**：
```yaml
# 从拆分计划和台账任务提取
tasks:
  - id: t-354ea0
    key: t1
    title: 删除工具目录
    phase: implement
    side: backend
    status: todo
    serves_requirements: [FR-1]       # 从任务 requirement_refs 提取
    implements_design: [design/architecture#1.1]  # 从任务 design_serves 提取
    depends_on: []
    card_doc: docs/requirements/REQ-xxx/tasks/t-354ea0.md
    
  - id: t-0c18e3
    key: t2
    title: 删除 use-case 文件
    status: todo
    serves_requirements: [FR-1]
    implements_design: [design/architecture#1.2]
    depends_on: []

lifecycle:
  current_stage: decomposing
  stages_completed: [draft, brainstorming, design]
  last_updated: 2026-09-26T15:30:00Z
```

### 阶段5：实施（implementing）

**时机**：任务状态变更时（`reqboard_task_move`）

**更新内容**：
```yaml
tasks:
  - id: t-354ea0
    status: done  # ← 状态更新
    completed_at: 2026-09-26T18:00:00Z
    executions:
      - session: s-abc123
        started_at: 2026-09-26T16:00:00Z
        ended_at: 2026-09-26T18:00:00Z
        outcome: succeeded
    
  - id: t-0c18e3
    status: in_progress  # ← 状态更新
    claimed_by: s-def456

lifecycle:
  current_stage: implementing
  stages_completed: [draft, brainstorming, design, decomposing]
  last_updated: 2026-09-26T18:05:00Z
```

### 阶段6：验收（accepting）

**时机**：`reqboard_submit(kind=verification)` 提交验收材料后

**更新内容**：
```yaml
# 从测试文档提取
test_cases:
  - id: TC-1
    title: 工具目录删除验证
    file: design/test-cases.md
    covers_tasks: [t-354ea0]       # 从 \`covers: t-354ea0\` 提取
    validates_requirements: [FR-1] # 从 \`validates: FR-1\` 提取
    validates_design: [design/architecture#1.1]
    status: passed
    
  - id: TC-2
    title: use-case 文件删除验证
    covers_tasks: [t-0c18e3]
    validates_requirements: [FR-1]
    status: pending

lifecycle:
  current_stage: accepting
  stages_completed: [draft, brainstorming, design, decomposing, implementing]
  last_updated: 2026-09-26T20:00:00Z
```

### 阶段7：归档（archived）

**时机**：验收通过归档时

**最终快照**：
```yaml
# 完整的追溯链记录
requirements: [...]      # 6 个 FR
design_sections: [...]   # 8 个设计章节
tasks: [...]             # 8 个任务（全部 done）
test_cases: [...]        # 8 个测试用例

# 覆盖度最终统计
coverage:
  design:
    total: 6
    covered: 6
    rate: 100
  implementation:
    total: 8
    covered: 8
    rate: 100
  testing:
    total: 8
    covered: 8
    rate: 100

lifecycle:
  current_stage: archived
  stages_completed: [draft, brainstorming, design, decomposing, implementing, accepting]
  created_at: 2026-09-26T10:00:00Z
  archived_at: 2026-09-26T21:00:00Z
  last_updated: 2026-09-26T21:00:00Z
```

---

## 🔄 RTM 更新触发点

| 事件 | 触发函数 | 更新内容 |
|------|---------|---------|
| **立项** | `reqboard_create` | 创建 rtm.yml 骨架 |
| **提交需求文档** | `reqboard_submit(kind=requirement)` | 提取 FR 列表 |
| **提交设计文档** | `reqboard_submit(kind=design)` | 提取设计章节 + serves |
| **批准拆分计划** | `reqboard_ask_confirm(target=plan)` | 提取任务 + implements |
| **任务状态变更** | `reqboard_task_move` | 更新任务状态 |
| **提交验收材料** | `reqboard_submit(kind=verification)` | 提取测试用例 + covers |
| **归档** | `reqboard_submit(kind=archive)` | 最终快照 |

---

## 💡 RTM 的使用场景

### 1. Agent 自查进度

```bash
# Agent 读取 rtm.yml 了解当前进度
cat docs/requirements/REQ-xxx/rtm.yml

# 查看追溯覆盖度
coverage:
  design:
    rate: 100  # ✅ 所有 FR 都有设计
  implementation:
    rate: 75   # ⚠️ 还有 2 个设计章节没有任务
```

### 2. 会话节点展示

会话右侧流程图节点的「追溯」Tab 直接读取 rtm.yml：

```
[DAG] [泳道] [追溯]

追溯 Tab 显示：
  📋 需求层：6 个 FR（从 rtm.yml 读取）
  🎨 设计层：8 个章节（从 rtm.yml 读取）
  ⚙️ 任务层：8 个任务（从 rtm.yml 读取）
  📊 覆盖度：100% / 100% / 75%
```

### 3. 验收门禁

```typescript
// 验收前检查追溯完整性
const rtm = readRTM(requirementId)

if (rtm.coverage.design.rate < 100) {
  reject('设计覆盖度不足，还有 FR 没有设计章节')
}

if (rtm.coverage.implementation.rate < 100) {
  reject('实施覆盖度不足，还有设计章节没有任务实现')
}
```

### 4. 复盘分析

```bash
# 查看需求的完整追溯历史
git log docs/requirements/REQ-xxx/rtm.yml

# 对比不同版本
git diff HEAD~5 HEAD -- docs/requirements/REQ-xxx/rtm.yml
```

---

## 📈 完整数据流（修正版）

```
立项（reqboard_create）
  ↓
创建 rtm.yml 骨架
  ↓
需求分析（submit requirement）
  ↓
更新 rtm.yml：提取 FR
  ↓
设计（submit design）
  ↓
更新 rtm.yml：提取设计章节 + serves
  ↓
拆分（approve plan）
  ↓
更新 rtm.yml：提取任务 + implements
  ↓
实施（task move）
  ↓
更新 rtm.yml：任务状态
  ↓
验收（submit verification）
  ↓
更新 rtm.yml：测试用例 + covers
  ↓
归档（submit archive）
  ↓
rtm.yml 最终快照
  ↓
版本控制（git）保留完整历史
```

---

## ✅ 核心变更

### 之前的设计（错误）

❌ RTM 在批准计划时才生成
❌ RTM 只记录设计→任务→测试

### 正确的设计

✅ RTM 在立项时创建（骨架）
✅ RTM 跟随需求全生命周期更新
✅ RTM 记录完整追溯链（FR → 设计 → 任务 → 测试）
✅ RTM 是需求内部的数据记录本

---

## 🔧 实施调整

### 新增：RTM 初始化

```typescript
// packages/web/dsh-pmboard/src/application/use-cases/CreateRequirement.ts

async function executeCreateRequirement(...) {
  // 创建需求记录
  const requirement = { ... }
  await deps.repo.mutate('requirement-created', ...)
  
  // 初始化 RTM YAML ← 新增
  await initializeRTM(deps.docs, requirement)
  
  return { requirement_id: requirement.id, ... }
}

async function initializeRTM(docs: DocsWriter, req: RequirementRecord) {
  const rtmPath = `docs/requirements/${req.id}/rtm.yml`
  const skeleton = {
    requirement_id: req.id,
    title: req.title,
    category: req.category,
    created_at: new Date().toISOString(),
    requirements: [],
    design_sections: [],
    tasks: [],
    test_cases: [],
    lifecycle: {
      current_stage: 'draft',
      stages_completed: [],
      last_updated: new Date().toISOString()
    }
  }
  await docs.write(rtmPath, stringifyYAML(skeleton))
}
```

### 修改：各阶段更新 RTM

每个 `reqboard_submit` 和关键状态变更后，调用 `updateRTM()`：

```typescript
// 提交需求文档后
await updateRTM(docs, req, 'requirements')

// 提交设计文档后
await updateRTM(docs, req, 'design_sections')

// 批准计划后
await updateRTM(docs, req, 'tasks')

// 任务状态变更后
await updateRTM(docs, req, 'task_status')

// 提交验收材料后
await updateRTM(docs, req, 'test_cases')
```

---

## ⏱️ 工作量调整

| 阶段 | 任务 | 工作量 |
|------|------|--------|
| **阶段1** | RTM 初始化（立项时） | 1小时 |
| **阶段2** | RTM 更新（各阶段触发点） | 4-5小时 |
| **阶段3** | RTM 读取与展示（会话节点） | 4-5小时 |
| **阶段4** | 测试与验证 | 3小时 |
| **总计** | | **12-14小时** |

**预估工期**：2 个工作日

---

## 💡 核心理念

**RTM YAML = 需求内部流程的完整数据记录**

- 📝 从立项开始创建
- 📈 跟随需求全生命周期更新
- 🔗 记录完整四级追溯链
- 📊 实时反映覆盖度统计
- 📦 归档时形成最终快照
- 🔄 Git 保留完整历史

**RTM 不是外部管理工具，而是需求内部的"行车记录仪"**
