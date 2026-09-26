---
requirement_id: REQ-260926140539-457b
design_type: data-model
version: 1.0
serves: FR-1, FR-3, FR-4
---

# RTM 数据模型设计

## 目标 serves: FR-1, FR-3, FR-4

定义 RTM YAML 文件的完整数据结构，包括 6 个核心文件的 Schema、字段定义、类型约束和关系映射。

---

## 数据模型概览 serves: FR-1

RTM 系统包含 7 个 YAML 文件（1 个全局 + 6 个节点）：

```
rtm-lifecycle.yml          # 全局生命周期
rtm-brainstorming.yml      # 需求分析节点
rtm-design.yml             # 设计节点
rtm-decomposing.yml        # 拆分节点
rtm-implementing.yml       # 实施节点（汇总）
rtm-implementing/*.yml     # 实施节点（任务详情）
rtm-accepting.yml          # 验收节点
```

---

## 核心数据结构 serves: FR-1
### 1. rtm-lifecycle.yml（全局生命周期） serves: FR-1, FR-3, FR-4
serves: FR-1

```yaml
requirement:
  id: string              # REQ-xxx
  title: string
  category: string        # feature/bug/doc/refactor/spike/chore
  created_at: string      # ISO 8601

lifecycle:
  current_stage: string   # draft/brainstorming/design/...
  stages:
    - stage: string
      entered_at: string
      completed_at: string
      artifacts: Artifact[]

metadata:
  rtm_version: string
  last_updated: string
  generated_by: string
```

### 2. rtm-brainstorming.yml（需求分析） serves: FR-1

```yaml
metadata:
  stage: brainstorming
  requirement_id: string
  generated_at: string
  version: number

outputs:
  requirements:
    - id: string          # FR-1
      title: string
      source: string      # requirement.md
      line: number

status:
  artifacts:
    - kind: requirement
      path: string
      confirmed: boolean
      confirmed_at: string
```

### 3. rtm-design.yml（设计） serves: FR-1

```yaml
metadata:
  stage: design
  requirement_id: string
  generated_at: string
  version: number

inputs:
  requirements: FR[]      # 来自 brainstorming

outputs:
  design_sections:
    - ref: string         # design/arch.md#1.1
      title: string
      serves: string[]    # [FR-1, FR-2]
      file: string
      section: string

traceability:
  fr_to_design:
    FR-1: [design/arch#1.1, ...]

coverage:
  design:
    total_frs: number
    covered_frs: number
    uncovered: string[]
    rate: number          # 0-100
```

### 4. rtm-decomposing.yml（拆分） serves: FR-1

```yaml
metadata:
  stage: decomposing
  requirement_id: string
  generated_at: string
  version: number

inputs:
  requirements: FR[]
  design_sections: DesignSection[]

outputs:
  tasks:
    - id: string          # t-354ea0
      title: string
      implements: string  # design/arch#1.1
      serves: string[]    # [FR-1]
      depends_on: string[]
      phase: string
      side: string

traceability:
  design_to_tasks:
    design/arch#1.1: [t-354ea0, ...]
  fr_to_tasks:
    FR-1: [t-354ea0, ...]

coverage:
  implementation:
    total_designs: number
    covered_designs: number
    uncovered: string[]
    rate: number
```

### 5. rtm-implementing.yml（实施汇总） serves: FR-1, FR-11

```yaml
metadata:
  stage: implementing
  requirement_id: string
  generated_at: string
  version: number

inputs:
  tasks: TaskSummary[]

status:
  tasks_total: number
  tasks_done: number
  tasks_in_progress: number
  tasks_todo: number

tasks:
  - id: string
    status: string        # todo/in_progress/testing/in_review/done
```

### 6. rtm-implementing/t-xxx.yml（任务详情） serves: FR-1, FR-11

```yaml
task:
  id: string
  title: string
  status: string
  implements: string
  serves: string[]
  depends_on: string[]
  phase: string
  side: string
  
  workflow_params:        # Subagent 参数
    REQ_ID: string
    TASK_ID: string
    DESIGN_FILES: string
    TEST_PATTERN: string
  
  workflow_total: number
  workflow_done: number
  workflow:
    - phase: string       # doc/ui/analysis/implement/test/review/commit
      status: string      # pending/in_progress/done/skipped
      started_at: string
      completed_at: string
      skip_reason: string

metadata:
  last_updated: string
  version: number
```

### 7. rtm-accepting.yml（验收） serves: FR-1

```yaml
metadata:
  stage: accepting
  requirement_id: string
  generated_at: string
  version: number

inputs:
  tasks: Task[]

outputs:
  test_cases:
    - id: string          # TC-1
      title: string
      covers: string[]    # [t-354ea0]
      validates: string[] # [FR-1]

traceability:
  task_to_tests:
    t-354ea0: [TC-1, TC-2, ...]

coverage:
  testing:
    total_tasks: number
    tested_tasks: number
    untested: string[]
    rate: number
```

---

## 追溯关系映射 serves: FR-4
### FR → 设计 (fr_to_design) serves: FR-4

```typescript
Map<string, string[]>
// 示例：
{
  "FR-1": ["design/arch.md#1.1", "design/arch.md#1.2"],
  "FR-2": ["design/data.md#2.1"]
}
```

### 设计 → 任务 (design_to_tasks) serves: FR-4

```typescript
Map<string, string[]>
// 示例：
{
  "design/arch.md#1.1": ["t-354ea0", "t-abc123"],
  "design/data.md#2.1": ["t-def456"]
}
```

### 任务 → 测试 (task_to_tests) serves: FR-4

```typescript
Map<string, string[]>
// 示例：
{
  "t-354ea0": ["TC-1", "TC-2"],
  "t-abc123": ["TC-3"]
}
```

---

## 数据一致性规则 serves: FR-3, FR-9
### 台账数据同步 serves: FR-3

1. **任务状态**：从 dsh-reqboard.json 的 tasks[].status 同步
2. **子任务状态**：从 tasks[].workflow 同步
3. **节点状态**：从 requirements[].status 同步
4. **产物列表**：从 requirements[].artifacts 同步

### 文档数据解析 serves: FR-3

1. **FR 列表**：解析 requirement.md 的 `**FR-N:` 标记
2. **设计章节**：解析 design/*.md 的 `## N.M` 和 `serves:` 标注
3. **任务追溯**：从 tasks[].design_serves 字段提取
4. **测试用例**：解析测试文档的 `covers:` 标注

### 版本控制 serves: FR-1, FR-6, FR-9

- 每次更新 RTM 时 version +1
- last_updated 记录最后更新时间
- 使用 version 检测数据陈旧

---

## 文件大小控制 serves: FR-1

| 文件 | 目标行数 | 实际作用 |
|-----|---------|---------|
| rtm-lifecycle.yml | ~50 | 全局状态快照 |
| rtm-brainstorming.yml | ~40 | FR 列表 |
| rtm-design.yml | ~60 | 设计章节 + FR 覆盖度 |
| rtm-decomposing.yml | ~80 | 任务列表 + 实施覆盖度 |
| rtm-implementing.yml | ~50 | 任务统计（轻量汇总）|
| rtm-implementing/t-xxx.yml | ~30 | 单任务详情 + workflow |
| rtm-accepting.yml | ~60 | 测试用例 + 测试覆盖度 |

**关键优化**：implementing 节点拆分为汇总 + 详情，Dive 模式只读汇总（~50 行），需要详情时才读单个任务文件（~30 行）。

---

## 验收口径 serves: FR-1, FR-3, FR-9, FR-10
### 数据完整性测试 serves: FR-1, FR-3, FR-4
serves: FR-3

```bash
npm test -- rtm-schema-validation.test.ts

# 预期：
serves: FR-1
# ✓ 所有 RTM 文件符合 Schema 定义
serves: FR-1
# ✓ 必填字段不能为空
serves: FR-1
# ✓ 类型约束正确
serves: FR-1
# ✓ 追溯关系引用有效
serves: FR-1
```

### 数据一致性测试 serves: FR-3

```bash
npm test -- rtm-consistency.test.ts

# 预期：
serves: FR-1
# ✓ RTM 任务状态 === 台账任务状态
serves: FR-1
# ✓ RTM FR 列表 === requirement.md FR 列表
serves: FR-1
# ✓ RTM 追溯关系 === 文档标注
serves: FR-1
```

### 性能测试 serves: FR-10

```bash
npm test -- rtm-file-size.test.ts

# 预期：
serves: FR-1
# ✓ rtm-lifecycle.yml < 100 行
serves: FR-1
# ✓ rtm-implementing.yml < 100 行（汇总）
serves: FR-1
# ✓ rtm-implementing/t-xxx.yml < 50 行
serves: FR-1
# ✓ 读取单个 RTM < 2ms
serves: FR-1
```

---

## 完整 Schema 定义 serves: FR-1

详细的 TypeScript 类型定义和 YAML 示例见 rtm-schema.md 文档（645 行完整定义）。