---
requirement_id: REQ-260926140539-457b
design_type: data-model
version: 1.0
---

# RTM YAML Schema 设计

## 概述 serves: FR-1

本文档定义了 RTM（Requirements Traceability Matrix）YAML 文件的完整 Schema。RTM 系统包含 6 个核心 YAML 文件，分别对应需求流水线的各个阶段。

## 设计原则 serves: FR-1

1. **可读性优先**：YAML 格式，人类可读可编辑
2. **增量更新**：只更新变化的部分，不全量重写
3. **文件分离**：implementing 阶段拆分文件，避免单文件过大
4. **版本追踪**：每个文件包含版本和更新时间
5. **完整追溯**：需求 → 设计 → 任务 → 测试的完整链路

## 1. rtm-lifecycle.yml（全局生命周期） serves: FR-1

**路径**：`docs/requirements/<REQ>/rtm-lifecycle.yml`

**用途**：记录需求的全局生命周期信息，所有阶段的总览。

**生成时机（2026-09-26 补）**：**窗口绑定（bound=true）之后**立即生成——两条立项路径
（reqboard_capture 弹框路径、reqboard_create 手工路径）都在绑窗口 + 阶段落定后触发 create
触发点。放在推进之后而非绑定之前：current_stage 直接取自台账，先写会立刻过期（FR-3 一致性优先）。

```yaml
# RTM 生命周期文件
serves: FR-1
requirement:
  id: REQ-260926140539-457b
  title: "RTM YAML 追溯基础设施"
  category: feature
  created_at: "2024-01-01T09:00:00Z"
  # 立项绑定窗口（台账 sourceSessionId 的投影）——"窗口↔需求"的需求侧锚点；
  # Dive 唤醒要按它投递。未绑定 → 该键缺省（不写空串）。
  source_session: session-c5ea210f-afc3-4735-a4d1-f9058b378363
  # 需求目录绝对路径（读快照的一方不必先知道工作区根）
  dir: /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260926140539-457b
  
metadata:
  # 本文件绝对路径（自定位）
  file_path: /Users/yunpeng/pi-investment/agent-dh/docs/requirements/REQ-260926140539-457b/rtm-lifecycle.yml
  
lifecycle:
  current_stage: implementing
  # 本需求有多少个节点：分类流程档案启用的节点数 + 清单（顺序 = 流水线顺序）
  stage_count: 7
  stage_list: [draft, brainstorming, design, decomposing, implementing, accepting, done]
  stages:
    - stage: draft
      # false = 本分类跳过该节点（看板标灰"本分类跳过"，不算缺失）
      enabled: true
      entered_at: "2024-01-01T09:00:00Z"
      completed_at: "2024-01-01T09:05:00Z"
      
    - stage: brainstorming
      enabled: true
      entered_at: "2024-01-01T09:05:00Z"
      completed_at: "2024-01-01T12:00:00Z"
      artifacts:
        - kind: requirement
          path: requirement.md
          confirmed_at: "2024-01-01T12:00:00Z"
      
    - stage: design
      entered_at: "2024-01-01T12:00:00Z"
      completed_at: "2024-01-02T16:00:00Z"
      artifacts:
        - kind: design
          path: design/architecture.md
          confirmed_at: "2024-01-02T14:00:00Z"
        - kind: design
          path: design/data-model.md
          confirmed_at: "2024-01-02T15:00:00Z"
      
    - stage: decomposing
      entered_at: "2024-01-02T16:00:00Z"
      completed_at: "2024-01-03T10:00:00Z"
      artifacts:
        - kind: plan
          path: decomposition.md
          approved_at: "2024-01-03T10:00:00Z"
      
    - stage: implementing
      entered_at: "2024-01-03T10:00:00Z"
      in_progress: true
      artifacts:
        - kind: task_detail
          count: 5
          path: rtm-implementing/*.yml
      
    - stage: accepting
      status: pending
      
    - stage: done
      status: pending

metadata:
  rtm_version: "1.0"
  last_updated: "2024-01-03T14:30:00Z"
  generated_by: "rtm-generator"
```

**字段说明**：
- `requirement`: 需求基本信息
- `lifecycle.current_stage`: 当前所在阶段
- `lifecycle.stages[]`: 各阶段的历史记录
  - `entered_at`: 进入该阶段的时间
  - `completed_at`: 完成该阶段的时间（可选）
  - `artifacts[]`: 该阶段产出的确认产物
- `metadata`: 元数据（版本、更新时间等）

---

## 2. rtm-brainstorming.yml（需求分析阶段） serves: FR-1, FR-2

**路径**：`docs/requirements/<REQ>/rtm-brainstorming.yml`

**用途**：记录需求分析阶段的输入输出和追溯关系。

```yaml
stage: brainstorming

inputs:
  user_request: "创建 RTM YAML 追溯基础设施"
  background: "Dive 模式需要快速读取追溯信息，当前通过解析文档太慢（500ms）"
  
outputs:
  requirement_doc: requirement.md
  functional_requirements:
    - id: FR-1
      title: "RTM 文件结构"
      description: "定义 6 个 RTM YAML 文件的结构"
      
    - id: FR-2
      title: "RTM 生成逻辑"
      description: "7 个触发点自动生成/更新 RTM"
      
    - id: FR-3
      title: "数据同步机制"
      description: "台账数据自动同步到 RTM 文件"
      
    # ... FR-4 到 FR-11
  
  non_functional_requirements:
    - id: NFR-1
      title: "性能要求"
      target: "RTM 读取 < 2ms（相比文档解析的 500ms）"
      
    - id: NFR-2
      title: "可扩展性"
      target: "支持 50+ 任务的需求"

traceability:
  user_needs:
    - "快速读取追溯信息"
    - "支持 Dive 模式自动化"
  
  covers:
    - user_need: "快速读取追溯信息"
      functional_requirements: [FR-1, FR-2, FR-10]
      
    - user_need: "支持 Dive 模式自动化"
      functional_requirements: [FR-8, FR-11]

metadata:
  generated_at: "2024-01-01T12:00:00Z"
  last_updated: "2024-01-01T12:00:00Z"
  version: 1
```

**字段说明**：
- `inputs`: 输入（用户需求、背景）
- `outputs.functional_requirements[]`: 功能需求列表（FR-1 到 FR-11）
- `outputs.non_functional_requirements[]`: 非功能需求
- `traceability`: 追溯关系（用户需求 → FR）

---

## 3. rtm-design.yml（设计阶段） serves: FR-1, FR-2, FR-4, FR-5

**路径**：`docs/requirements/<REQ>/rtm-design.yml`

**用途**：记录设计阶段的输入输出和追溯关系。

```yaml
stage: design

inputs:
  requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11]

outputs:
  design_docs:
    - path: design/rtm-schema.md
      type: data-model
      covers_frs: [FR-1]
      sections:
        - "1. rtm-lifecycle.yml"
        - "2. rtm-brainstorming.yml"
        - "3. rtm-design.yml"
        - "4. rtm-decomposing.yml"
        - "5. rtm-implementing.yml"
        - "6. rtm-accepting.yml"
      
    - path: design/agent-teams-integration.md
      type: architecture
      covers_frs: [FR-11]
      sections:
        - "Worker Agent 设计"
        - "共享任务板设计"
        - "事件驱动监控"
      
    - path: design/dive-integration.md
      type: architecture
      covers_frs: [FR-8]
      sections:
        - "节点输入包注入"
        - "RTM 数据压缩"
        - "阶段提示词生成"
      
    - path: design/data-sync.md
      type: architecture
      covers_frs: [FR-2, FR-3, FR-6]
      sections:
        - "RTM 更新触发点"
        - "跨节点反馈循环"
        - "版本追踪"

traceability:
  fr_to_design:
    FR-1: [design/rtm-schema.md]
    FR-2: [design/data-sync.md]
    FR-3: [design/data-sync.md]
    FR-8: [design/dive-integration.md]
    FR-11: [design/agent-teams-integration.md]
    # ... 其他 FR

coverage:
  total_frs: 11
  covered_frs: 11
  uncovered: []
  rate: 100%

metadata:
  generated_at: "2024-01-02T16:00:00Z"
  last_updated: "2024-01-02T16:00:00Z"
  version: 1
```

**字段说明**：
- `inputs.requirement_refs[]`: 覆盖的 FR 列表
- `outputs.design_docs[]`: 设计文档列表
  - `covers_frs[]`: 该文档覆盖的 FR
  - `sections[]`: 文档的主要章节
- `traceability.fr_to_design`: FR → 设计文档的映射
- `coverage`: 覆盖度统计（必须 100%）

---

## 4. rtm-decomposing.yml（拆分阶段） serves: FR-1, FR-2, FR-4, FR-5

**路径**：`docs/requirements/<REQ>/rtm-decomposing.yml`

**用途**：记录拆分阶段的输入输出和追溯关系。

```yaml
stage: decomposing

inputs:
  design_refs:
    - design/rtm-schema.md
    - design/agent-teams-integration.md
    - design/dive-integration.md
    - design/data-sync.md

outputs:
  tasks:
    - id: t-354ea0
      title: "实现 RTM 文件结构"
      implements: "design/rtm-schema.md#1-6"
      serves: [FR-1, FR-2]
      depends_on: []
      phase: fullstack
      side: backend
      
    - id: t-abc123
      title: "实现 RTM 生成逻辑"
      implements: "design/data-sync.md#rtm-generator"
      serves: [FR-2, FR-3]
      depends_on: [t-354ea0]
      phase: implement
      side: backend
      
    - id: t-def456
      title: "实现 Dive 模式注入"
      implements: "design/dive-integration.md#injection"
      serves: [FR-8]
      depends_on: [t-354ea0]
      phase: fullstack
      side: backend
      
    # ... 更多任务

traceability:
  design_to_tasks:
    "design/rtm-schema.md": [t-354ea0]
    "design/agent-teams-integration.md": [t-789012]
    "design/dive-integration.md": [t-def456]
    "design/data-sync.md": [t-abc123, t-345678]
  
  fr_to_tasks:
    FR-1: [t-354ea0]
    FR-2: [t-354ea0, t-abc123]
    FR-3: [t-abc123]
    FR-8: [t-def456]
    FR-11: [t-789012]
    # ... 其他 FR

coverage:
  implementation:
    total_designs: 4
    covered_designs: 4
    uncovered: []
    rate: 100%

metadata:
  generated_at: "2024-01-03T10:00:00Z"
  last_updated: "2024-01-03T10:00:00Z"
  version: 1
```

**字段说明**：
- `outputs.tasks[]`: 任务列表
  - `implements`: 实现哪个设计章节
  - `serves[]`: 覆盖哪些 FR
  - `depends_on[]`: 依赖哪些任务（DAG）
  - `phase`: 任务类型（决定子阶段）
  - `side`: frontend / backend / fullstack / doc
- `traceability`: 设计 → 任务、FR → 任务的映射
- `coverage`: 必须 100% 覆盖所有设计

---

## 5. rtm-implementing.yml（实施阶段 - 汇总文件） serves: FR-1, FR-2, FR-11

**路径**：`docs/requirements/<REQ>/rtm-implementing.yml`

**用途**：实施阶段的汇总文件（轻量，只有统计和任务列表）。

```yaml
stage: implementing

summary:
  total_tasks: 5
  tasks_done: 2
  tasks_in_progress: 2
  tasks_todo: 1

tasks:
  - id: t-354ea0
    title: "实现 RTM 文件结构"
    status: done
    completed_at: "2024-01-03T14:00:00Z"
    
  - id: t-abc123
    title: "实现 RTM 生成逻辑"
    status: in_progress
    started_at: "2024-01-03T14:00:00Z"
    
  - id: t-def456
    title: "实现 Dive 模式注入"
    status: in_progress
    started_at: "2024-01-03T14:30:00Z"
    
  - id: t-789012
    title: "实现 Agent Teams 集成"
    status: todo
    
  - id: t-345678
    title: "实现数据同步机制"
    status: todo

metadata:
  detail_dir: rtm-implementing/
  detail_count: 5
  generated_at: "2024-01-03T10:00:00Z"
  last_updated: "2024-01-03T14:30:00Z"
  version: 3
```

**字段说明**：
- `summary`: 统计信息（总数、完成数、进行中、待办）
- `tasks[]`: 任务列表（只有 id / title / status，详情在独立文件中）
- `metadata.detail_dir`: 详情文件目录

---

## 6. rtm-implementing/t-xxx.yml（实施阶段 - 任务详情） serves: FR-1, FR-2, FR-11

**路径**：`docs/requirements/<REQ>/rtm-implementing/<task_id>.yml`

**用途**：单个任务的详细信息（包含 workflow 执行记录）。

```yaml
task:
  id: t-354ea0
  title: "实现 RTM 文件结构"
  status: done
  implements: "design/rtm-schema.md#1-6"
  serves: [FR-1, FR-2]
  depends_on: []
  phase: fullstack
  side: backend
  
  # Agent Teams 信息
  team_task_id: "task-001"  # 共享任务板上的任务 ID
  assigned_worker: "worker-1"
  
  # Workflow 参数
  workflow_params:
    REQ_ID: "REQ-260926140539-457b"
    TASK_ID: "t-354ea0"
    TASK_TITLE: "实现 RTM 文件结构"
    DESIGN_FILES: "design/rtm-schema.md"
    IMPL_FILES: "src/rtm/generator.ts"
    TEST_PATTERN: "rtm.test.ts"
    SIDE: "backend"
    PHASE: "fullstack"
  
  # 子阶段执行记录（根据 phase 决定数量）
  workflow_total: 7
  workflow_done: 7
  workflow:
    - phase: doc
      status: done
      started_at: "2024-01-03T10:00:00Z"
      completed_at: "2024-01-03T10:30:00Z"
      steps_completed:
        - action: "编写任务文档"
          description: "创建 docs/requirements/REQ-xxx/tasks/t-354ea0.md"
          files_changed: ["docs/requirements/REQ-xxx/tasks/t-354ea0.md"]
          output: "任务文档已完成，包含实施方案和验收标准"
      
    - phase: ui
      status: skipped
      skip_reason: "backend task, no UI needed"
      
    - phase: analysis
      status: done
      started_at: "2024-01-03T10:30:00Z"
      completed_at: "2024-01-03T11:00:00Z"
      steps_completed:
        - action: "分析实现方案"
          description: "确定文件结构和生成逻辑"
          output: "决定使用 YAML 格式，拆分汇总和详情文件"
      
    - phase: implement
      status: done
      started_at: "2024-01-03T11:00:00Z"
      completed_at: "2024-01-03T13:00:00Z"
      steps_completed:
        - action: "创建 RTM 生成器"
          description: "实现 src/rtm/generator.ts"
          files_changed: ["src/rtm/generator.ts", "src/rtm/types.ts"]
          commit: "feat: add rtm generator"
        - action: "实现文件写入逻辑"
          files_changed: ["src/rtm/writer.ts"]
          commit: "feat: add rtm writer"
      
    - phase: test
      status: done
      started_at: "2024-01-03T13:00:00Z"
      completed_at: "2024-01-03T13:30:00Z"
      steps_completed:
        - action: "编写单元测试"
          files_changed: ["tests/rtm/generator.test.ts"]
        - action: "运行测试"
          output: "所有测试通过，覆盖度 85%"
      test_coverage: 85
      
    - phase: review
      status: done
      started_at: "2024-01-03T13:30:00Z"
      completed_at: "2024-01-03T13:45:00Z"
      steps_completed:
        - action: "代码审查"
          output: "无问题，符合规范"
      
    - phase: commit
      status: done
      started_at: "2024-01-03T13:45:00Z"
      completed_at: "2024-01-03T14:00:00Z"
      steps_completed:
        - action: "提交代码"
          commit: "b5f3a2c"
          message: "feat(rtm): implement RTM file structure"

metadata:
  generated_at: "2024-01-03T10:00:00Z"
  last_updated: "2024-01-03T14:00:00Z"
  version: 8
```

**字段说明**：
- `task`: 任务基本信息
- `team_task_id`: DSH Agent Teams 的共享任务 ID
- `workflow_params`: 用于生成 Worker Agent prompt 的参数
- `workflow[]`: 子阶段执行记录
  - `phase`: doc / ui / analysis / implement / test / review / commit
  - `status`: pending / in_progress / done / skipped / failed
  - `steps_completed[]`: 详细步骤记录

---

## 7. rtm-accepting.yml（验收阶段） serves: FR-1, FR-2, FR-4, FR-5

**路径**：`docs/requirements/<REQ>/rtm-accepting.yml`

**用途**：记录验收阶段的测试追溯和验收结果。

```yaml
stage: accepting

inputs:
  completed_tasks: [t-354ea0, t-abc123, t-def456, t-789012, t-345678]

verification:
  test_coverage:
    total_tasks: 5
    tested_tasks: 5
    coverage_rate: 100%
  
  acceptance_tests:
    - id: AT-1
      title: "RTM 文件生成测试"
      covers_frs: [FR-1, FR-2]
      covers_tasks: [t-354ea0, t-abc123]
      status: passed
      executed_at: "2024-01-05T10:00:00Z"
      
    - id: AT-2
      title: "Dive 模式集成测试"
      covers_frs: [FR-8]
      covers_tasks: [t-def456]
      status: passed
      executed_at: "2024-01-05T10:30:00Z"
      
    - id: AT-3
      title: "Agent Teams 集成测试"
      covers_frs: [FR-11]
      covers_tasks: [t-789012]
      status: passed
      executed_at: "2024-01-05T11:00:00Z"
      
    # ... 更多验收测试

traceability:
  fr_to_tests:
    FR-1: [AT-1]
    FR-2: [AT-1]
    FR-8: [AT-2]
    FR-11: [AT-3]
    # ... 其他 FR
  
  task_to_tests:
    t-354ea0: [AT-1]
    t-abc123: [AT-1]
    t-def456: [AT-2]
    t-789012: [AT-3]
    t-345678: [AT-1, AT-4]

coverage:
  total_frs: 11
  tested_frs: 11
  untested: []
  rate: 100%

acceptance_status:
  all_tests_passed: true
  ready_for_done: true

metadata:
  generated_at: "2024-01-05T09:00:00Z"
  last_updated: "2024-01-05T11:30:00Z"
  version: 1
```

**字段说明**：
- `inputs.completed_tasks[]`: 已完成的任务列表
- `verification.acceptance_tests[]`: 验收测试列表
  - `covers_frs[]`: 覆盖的 FR
  - `covers_tasks[]`: 覆盖的任务
  - `status`: passed / failed / skipped
- `traceability`: FR → 测试、任务 → 测试的映射
- `coverage`: 验收覆盖度（建议 ≥80%）
- `acceptance_status.ready_for_done`: 是否可以推进到 done

---

## 完整追溯链示例 serves: FR-4

```
用户需求："快速读取追溯信息"
  ↓ (rtm-brainstorming.yml)
FR-1: RTM 文件结构
FR-2: RTM 生成逻辑
FR-10: 性能优化
  ↓ (rtm-design.yml)
design/rtm-schema.md
design/data-sync.md
  ↓ (rtm-decomposing.yml)
t-354ea0: 实现 RTM 文件结构
t-abc123: 实现 RTM 生成逻辑
  ↓ (rtm-implementing/*.yml)
t-354ea0: 7个子阶段执行记录
t-abc123: 7个子阶段执行记录
  ↓ (rtm-accepting.yml)
AT-1: RTM 文件生成测试（覆盖 FR-1, FR-2）
  ↓
验收通过 → done
```

---

## 性能指标 serves: FR-10

| 文件 | 预估大小 | 读取时间目标 |
|-----|---------|-------------|
| rtm-lifecycle.yml | ~2KB | <1ms |
| rtm-brainstorming.yml | ~3KB | <1ms |
| rtm-design.yml | ~5KB | <1ms |
| rtm-decomposing.yml | ~8KB | <2ms |
| rtm-implementing.yml | ~5KB | <1ms |
| rtm-implementing/t-xxx.yml | ~1KB/任务 | <1ms |
| rtm-accepting.yml | ~6KB | <2ms |

**总计**：完整读取所有 RTM < 10ms（相比文档解析的 500ms，提升 50 倍）

---

## 版本控制 serves: FR-1, FR-6

每个 RTM 文件包含：
- `metadata.version`: 版本号（每次更新 +1）
- `metadata.last_updated`: 最后更新时间
- `metadata.generated_by`: 生成器标识

版本号用于：
- 检测文件是否过期
- 触发跨节点反馈循环
- 审计追踪

---

## 下一步 serves: FR-1

本 Schema 定义后，下一个设计文档将设计：
1. RTM 生成器架构（如何生成这些文件）
2. Agent Teams 集成（如何使用 DSH 原生能力）
3. Dive 模式集成（如何注入 RTM 数据）