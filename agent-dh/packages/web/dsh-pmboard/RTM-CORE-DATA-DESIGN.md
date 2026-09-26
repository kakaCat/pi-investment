# RTM YAML 重新定位：核心追溯数据，不是所有细节

> 重新设计：2026-09-26  
> 核心理念：RTM 只记录追溯关系，不复制台账数据

---

## 🎯 之前的误解

### 误解 1：RTM 记录所有数据 ❌

之前设计的 RTM 包含了太多细节：
- 任务的 status、phase、side
- 任务的 executions 执行记录
- 任务的 completed_at 时间戳
- 测试用例的 status

**问题**：这些数据已经在台账里了，RTM 不应该重复存储

### 误解 2：RTM 是完整的数据副本 ❌

RTM 变成了需求的"完整镜像"，包含了所有细节

**问题**：数据冗余、不一致风险、维护成本高

---

## ✅ 正确的理解

### RTM YAML = 核心追溯关系

**只记录追溯链的映射关系，不记录实体的详细属性**

```yaml
# docs/requirements/REQ-xxx/rtm.yml

# 核心追溯关系（精简版）
traceability:
  # 需求 → 设计
  requirements_to_design:
    FR-1: [design/architecture#1.1, design/architecture#1.2]
    FR-2: [design/architecture#2]
    FR-3: [design/interfaces#1]
  
  # 设计 → 任务
  design_to_tasks:
    design/architecture#1.1: [t-354ea0, t-abc123]
    design/architecture#1.2: [t-0c18e3]
    design/architecture#2: [t-f0e25a]
  
  # 任务 → 测试
  tasks_to_tests:
    t-354ea0: [TC-1]
    t-0c18e3: [TC-2]
    t-f0e25a: []  # 无测试

# 元数据（最少）
metadata:
  requirement_id: REQ-xxx
  generated_at: 2026-09-26T10:00:00Z
  last_updated: 2026-09-26T18:00:00Z
```

---

## 📊 数据分工

### 台账（requirements.json + tasks.json）

**存储实体的详细属性**：
- 需求的 title、description、status、category
- 任务的 title、status、phase、side、executions
- 评论、时间线、产物列表

### RTM YAML

**只存储追溯关系映射**：
- FR-1 对应哪些设计章节
- 设计章节对应哪些任务
- 任务对应哪些测试

### 文档（requirement.md / design/*.md / tasks/*.md）

**存储文本内容和标注**：
- 需求描述
- 设计方案
- 任务实施细节
- `serves:` / `implements:` / `covers:` 标注

---

## 🔍 RTM 的作用

### 不是数据副本

❌ **不做**：存储任务的 status、title、phase
❌ **不做**：存储设计章节的内容
❌ **不做**：存储 FR 的描述

### 是追溯索引

✅ **做**：记录 FR-1 → [design/arch#1.1, design/arch#1.2]
✅ **做**：记录 design/arch#1.1 → [t-354ea0, t-abc123]
✅ **做**：记录 t-354ea0 → [TC-1]
✅ **做**：计算覆盖度统计

**类比**：RTM 像数据库的"索引"，不是"表"

---

## 📝 精简的 RTM YAML 结构

```yaml
# docs/requirements/REQ-260925234037-1503/rtm.yml

# 元数据
metadata:
  requirement_id: REQ-260925234037-1503
  generated_at: 2026-09-26T10:00:00Z
  last_updated: 2026-09-26T18:00:00Z
  version: 3  # 每次更新 +1

# 核心追溯关系
traceability:
  # Level 1: 需求 → 设计
  fr_to_design:
    FR-1:
      - design/architecture.md#1
      - design/architecture.md#1.1
      - design/architecture.md#1.2
    FR-2:
      - design/architecture.md#2
    FR-3:
      - design/interfaces.md#1
    FR-4: []  # 未覆盖
  
  # Level 2: 设计 → 任务
  design_to_tasks:
    "design/architecture.md#1.1":
      - t-354ea0
      - t-abc123
    "design/architecture.md#1.2":
      - t-0c18e3
    "design/architecture.md#2":
      - t-f0e25a
    "design/interfaces.md#1": []  # 未实现
  
  # Level 3: 任务 → 测试
  task_to_tests:
    t-354ea0:
      - TC-1
    t-0c18e3:
      - TC-2
    t-abc123: []  # 无测试
    t-f0e25a: []

# 覆盖度统计（派生数据，可选）
coverage:
  design:
    total_frs: 4
    covered_frs: 3
    uncovered: [FR-4]
  implementation:
    total_designs: 4
    covered_designs: 3
    uncovered: ["design/interfaces.md#1"]
  testing:
    total_tasks: 4
    covered_tasks: 2
    uncovered: [t-abc123, t-f0e25a]
```

**大小对比**：
- 之前设计：~500 行（包含所有细节）
- 精简版：~50-100 行（只有追溯关系）

---

## 🔄 数据流（精简版）

### 生成 RTM

```typescript
function generateRTM(docs: DocsReader, req: RequirementRecord, tasks: TaskRecord[]) {
  // 1. 扫描设计文档，提取 serves 标注
  const designSections = extractAllDesignSections(docs, req.id)
  const frToDesign = buildFRToDesignMap(designSections)
  
  // 2. 从任务的 design_serves 字段提取
  const designToTasks = buildDesignToTasksMap(tasks)
  
  // 3. 扫描测试文档，提取 covers 标注
  const testCases = extractTestCases(docs, req.id)
  const taskToTests = buildTaskToTestsMap(testCases)
  
  return {
    metadata: { requirement_id: req.id, ... },
    traceability: { frToDesign, designToTasks, taskToTests },
    coverage: calculateCoverage(frToDesign, designToTasks, taskToTests)
  }
}
```

### 使用 RTM

```typescript
// 会话节点读取 RTM
const rtm = readRTM(requirementId)

// 查询：FR-1 有哪些设计章节？
const designs = rtm.traceability.fr_to_design['FR-1']
// => ["design/architecture.md#1.1", "design/architecture.md#1.2"]

// 查询：design/architecture.md#1.1 有哪些任务实现？
const tasks = rtm.traceability.design_to_tasks['design/architecture.md#1.1']
// => ["t-354ea0", "t-abc123"]

// 查询任务详情 → 从台账读取
const taskDetails = ledger.tasks.filter(t => tasks.includes(t.id))
```

---

## ✅ 核心原则

### 1. 单一职责

**RTM YAML 只负责追溯关系，不负责数据存储**

### 2. 最小化

**只记录 ID 映射，不记录实体属性**

### 3. 派生数据

**RTM 是从文档和台账派生出来的，不是原始数据源**

### 4. 不可变快照

**每次生成是快照，不实时同步（版本号标记）**

---

## 📈 对比：之前 vs 现在

| 维度 | 之前设计 | 现在设计（精简） |
|------|---------|----------------|
| **数据量** | ~500 行 | ~50-100 行 |
| **内容** | 实体详细属性 | 只有 ID 映射 |
| **更新频率** | 实时同步 | 快照（版本号）|
| **数据源** | 复制台账 | 派生索引 |
| **维护成本** | 高 | 低 |
| **一致性风险** | 高 | 低 |

---

## 🔧 实施调整

### 之前的 RTM（太重）

```yaml
tasks:
  - id: t-354ea0
    title: 删除工具目录       # ← 冗余（台账已有）
    status: done             # ← 冗余
    phase: implement         # ← 冗余
    side: backend            # ← 冗余
    completed_at: 2026-...   # ← 冗余
    executions: [...]        # ← 冗余
    serves_requirements: [FR-1]     # ✓ 需要
    implements_design: [design/...] # ✓ 需要
```

### 现在的 RTM（精简）

```yaml
design_to_tasks:
  "design/architecture.md#1.1": [t-354ea0, t-abc123]  # ✓ 只记录映射

task_to_tests:
  t-354ea0: [TC-1]  # ✓ 只记录映射
```

**详细数据从哪来？**
- 任务详情 → 从台账读取
- 设计内容 → 从文档读取
- 测试详情 → 从文档读取

---

## 💡 核心结论

**RTM YAML = 追溯关系的索引，不是数据的副本**

- ✅ 只记录 ID 映射（FR → 设计 → 任务 → 测试）
- ✅ 不记录实体的详细属性
- ✅ 文件大小从 ~500 行降到 ~50-100 行
- ✅ 维护成本低、一致性风险低
- ✅ 快照模式（版本号标记），不实时同步

**类比**：
- 台账 = 数据库表（存储实体）
- 文档 = 文本内容（描述和标注）
- **RTM = 数据库索引**（加速查询追溯关系）
