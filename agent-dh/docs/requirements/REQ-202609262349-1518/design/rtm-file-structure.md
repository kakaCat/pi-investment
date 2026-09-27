# RTM 文件结构设计


定义 7 个 RTM YAML 文件的完整 schema（字段、类型、约束），使所有节点的 RTM 文件结构统一且可解析，验收标准：生成的 RTM 文件能通过 YAML schema 验证，且包含所有必需字段（metadata / inputs / outputs / traceability / coverage）。


## 通用结构（serves: FR-1）

所有 RTM 文件共享的基础结构：

```yaml
metadata:
  version: 1                          # RTM schema 版本号
  requirement_id: REQ-xxx             # 需求 ID
  stage: brainstorming                # 节点名称
  generated_at: 2026-09-26T23:49:00Z  # 生成时间（ISO 8601）
  generator: reqboard-rtm-v1          # 生成器标识

inputs: {}      # 上游节点输出（各节点不同）
outputs: {}     # 本节点产出（各节点不同）
traceability: {}  # 追溯映射（各节点不同）
coverage: {}    # 覆盖度统计（各节点不同）
```

## rtm-lifecycle.yml（serves: FR-1）

全局节点状态文件：

```yaml
metadata:
  version: 1
  requirement_id: REQ-202609262349-1518
  stage: lifecycle
  generated_at: 2026-09-26T23:49:00Z
  generator: reqboard-rtm-v1

lifecycle:
  current_stage: design               # 当前节点
  stages:
    draft:
      status: completed               # pending / in_progress / completed
      started_at: 2026-09-26T20:00:00Z
      completed_at: 2026-09-26T20:10:00Z
    brainstorming:
      status: completed
      started_at: 2026-09-26T20:10:00Z
      completed_at: 2026-09-26T22:00:00Z
    design:
      status: in_progress
      started_at: 2026-09-26T22:00:00Z
    decomposing:
      status: pending
    implementing:
      status: pending
    accepting:
      status: pending
    done:
      status: pending
```

## rtm-brainstorming.yml（serves: FR-1）

需求分析节点 RTM：

```yaml
metadata:
  version: 1
  requirement_id: REQ-202609262349-1518
  stage: brainstorming
  generated_at: 2026-09-26T22:00:00Z
  generator: reqboard-rtm-v1

inputs: {}  # 无上游输入

outputs:
  requirements:                       # FR 列表
    - id: FR-1
      title: RTM 文件结构设计
      source: requirement.md          # 来源文件
      line: 120                       # 行号
    - id: FR-2
      title: 台账数据模型扩展
      source: requirement.md
      line: 145

traceability:
  fr_to_design: {}                    # 初始化空映射（在 design 阶段填充）

coverage: {}                          # 无覆盖度统计
```

## rtm-design.yml（serves: FR-1）

设计节点 RTM：

```yaml
metadata:
  version: 1
  requirement_id: REQ-202609262349-1518
  stage: design
  generated_at: 2026-09-27T10:00:00Z
  generator: reqboard-rtm-v1

inputs:
  requirements:                       # 来自 brainstorming
    - FR-1
    - FR-2
    - FR-3

outputs:
  design_sections:                    # 设计章节列表
    - ref: design/architecture.md#整体架构
      title: 整体架构
      serves: [FR-1, FR-3]            # 服务的 FR
      line: 15
    - ref: design/rtm-file-structure.md#通用结构
      title: 通用结构
      serves: [FR-1]
      line: 10

traceability:
  fr_to_design:                       # FR → 设计章节映射
    FR-1:
      - design/architecture.md#整体架构
      - design/rtm-file-structure.md#通用结构
    FR-2:
      - design/ledger-schema.md#新增字段
    FR-3:
      - design/architecture.md#整体架构
      - design/rtm-generation.md#触发点集成

coverage:
  design:
    total_frs: 9                      # FR 总数
    covered_frs: 9                    # 有设计的 FR 数
    uncovered: []                     # 缺少设计的 FR
    rate: 1.0                         # 覆盖率（100%）
```

## rtm-decomposing.yml（serves: FR-1）

拆分节点 RTM：

```yaml
metadata:
  version: 1
  requirement_id: REQ-202609262349-1518
  stage: decomposing
  generated_at: 2026-09-27T15:00:00Z
  generator: reqboard-rtm-v1

inputs:
  requirements: [FR-1, FR-2, ..., FR-9]
  design_sections:
    - design/architecture.md#整体架构
    - design/rtm-file-structure.md#通用结构

outputs:
  tasks:                              # 任务列表
    - id: t-354ea0
      title: 实现 RTM 文件结构
      implements: design/rtm-file-structure.md#通用结构
      serves: [FR-1]
      depends_on: []
      phase: implement
      side: backend
    - id: t-abc123
      title: 实现 RTM 生成逻辑
      implements: design/rtm-generation.md#触发点集成
      serves: [FR-2, FR-3]
      depends_on: [t-354ea0]
      phase: implement
      side: backend

traceability:
  design_to_tasks:                    # 设计章节 → 任务映射
    "design/rtm-file-structure.md#通用结构":
      - t-354ea0
    "design/rtm-generation.md#触发点集成":
      - t-abc123
  fr_to_tasks:                        # FR → 任务映射（衍生）
    FR-1: [t-354ea0]
    FR-2: [t-abc123]
    FR-3: [t-abc123]

coverage:
  implementation:
    total_designs: 7                  # 设计章节总数
    covered_designs: 7                # 有任务实现的章节数
    uncovered: []                     # 缺少任务的章节
    rate: 1.0                         # 覆盖率（100%）
```

## rtm-implementing.yml（汇总文件）（serves: FR-1）

实施节点汇总 RTM（轻量级）：

```yaml
metadata:
  version: 1
  requirement_id: REQ-202609262349-1518
  stage: implementing
  generated_at: 2026-09-27T16:00:00Z
  generator: reqboard-rtm-v1

inputs:
  tasks: [t-354ea0, t-abc123, ...]    # 任务 ID 列表

status:
  tasks_total: 5
  tasks_done: 2
  tasks_in_progress: 2
  tasks_todo: 1

tasks:                                # 只含 id 和 status（不含详情）
  - id: t-354ea0
    status: done
  - id: t-abc123
    status: in_progress
  - id: t-def456
    status: in_progress
  - id: t-789012
    status: todo
  - id: t-345678
    status: todo
```

## rtm-implementing/t-354ea0.yml（任务详情）（serves: FR-1）

单个任务的详细 RTM：

```yaml
metadata:
  version: 1
  requirement_id: REQ-202609262349-1518
  stage: implementing
  task_id: t-354ea0
  generated_at: 2026-09-27T16:30:00Z
  generator: reqboard-rtm-v1

task:
  id: t-354ea0
  title: 实现 RTM 文件结构
  status: done
  implements: design/rtm-file-structure.md#通用结构
  serves: [FR-1]
  workflow_total: 7                   # 子阶段总数
  workflow_done: 7                    # 已完成子阶段数

workflow:                             # 子阶段执行状态
  - phase: doc
    status: done
    started_at: 2026-09-27T16:00:00Z
    completed_at: 2026-09-27T16:10:00Z
  - phase: ui
    status: done
    started_at: 2026-09-27T16:10:00Z
    completed_at: 2026-09-27T16:15:00Z
  - phase: analysis
    status: done
    started_at: 2026-09-27T16:15:00Z
    completed_at: 2026-09-27T16:20:00Z
  - phase: implement
    status: done
    started_at: 2026-09-27T16:20:00Z
    completed_at: 2026-09-27T16:50:00Z
  - phase: test
    status: done
    started_at: 2026-09-27T16:50:00Z
    completed_at: 2026-09-27T17:00:00Z
  - phase: review
    status: done
    started_at: 2026-09-27T17:00:00Z
    completed_at: 2026-09-27T17:05:00Z
  - phase: commit
    status: done
    started_at: 2026-09-27T17:05:00Z
    completed_at: 2026-09-27T17:10:00Z
```

## rtm-accepting.yml（serves: FR-1）

验收节点 RTM：

```yaml
metadata:
  version: 1
  requirement_id: REQ-202609262349-1518
  stage: accepting
  generated_at: 2026-09-28T10:00:00Z
  generator: reqboard-rtm-v1

inputs:
  tasks: [t-354ea0, t-abc123, ...]    # 任务列表

outputs:
  test_cases:                         # 测试用例列表
    - id: TC-1
      title: RTM 文件生成测试
      covers: [t-354ea0]              # 覆盖的任务
      validates: [FR-1]               # 验证的 FR
      source: test-cases.md
      line: 50
    - id: TC-2
      title: 覆盖度门禁测试
      covers: [t-abc123]
      validates: [FR-7]
      source: test-cases.md
      line: 80

traceability:
  task_to_tests:                      # 任务 → 测试用例映射
    t-354ea0: [TC-1]
    t-abc123: [TC-2]

coverage:
  testing:
    total_tasks: 5                    # 任务总数
    tested_tasks: 4                   # 有测试的任务数
    untested: [t-789012]              # 缺少测试的任务
    rate: 0.8                         # 覆盖率（80%）
```

## 文件组织（serves: FR-1）

```
docs/requirements/REQ-202609262349-1518/
├── requirement.md
├── design/
│   ├── architecture.md
│   ├── rtm-file-structure.md
│   └── ...
├── decomposition.md
├── tasks/
│   ├── t-354ea0.md
│   └── t-abc123.md
├── test-cases.md
├── rtm-lifecycle.yml              # 全局节点状态
├── rtm-brainstorming.yml          # 需求分析节点
├── rtm-design.yml                 # 设计节点
├── rtm-decomposing.yml            # 拆分节点
├── rtm-implementing.yml           # 实施节点汇总
├── rtm-implementing/              # 实施节点任务详情目录
│   ├── t-354ea0.yml
│   ├── t-abc123.yml
│   └── ...
└── rtm-accepting.yml              # 验收节点
```