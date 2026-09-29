═══════════════════════════════════════════════════════════════════════════════
  三个核心 RTM 文件的完整内容（按阶段命名）
═══════════════════════════════════════════════════════════════════════════════

## 1. 需求的 RTM 文件：rtm-brainstorming.yml

**阶段**：brainstorming（需求分析）  
**生成器**：brainstorming-generator.ts  
**触发时机**：
  - submit:requirement（提交需求文档）
  - confirm:artifact kind=requirement（确认需求文档）

**文件结构**：
```yaml
metadata:
  stage: brainstorming
  requirement_id: REQ-xxxxxx
  generated_at: "2024-09-27T10:30:00Z"
  generated_by: dsh-pmboard
  version: 1

outputs:
  requirements:                    # FR（功能需求）列表
    - id: FR-1
      title: "用户登录功能"
      description: "..."
      acceptance_criteria:         # AC（验收标准）
        - AC-1.1
        - AC-1.2
    - id: FR-2
      title: "数据导出功能"
      ...

status:
  artifacts:                       # 需求文档产物状态
    - kind: requirement
      path: docs/requirements/REQ-xxx/requirement.md
      confirmed: true              # 是否已人工确认
      confirmed_at: "2024-09-27T11:00:00Z"
```

**内容说明**：
- **outputs.requirements**：从需求文档提取的 FR 列表（含 AC）
- **status.artifacts**：需求文档的确认状态
- **作用**：
  - 为后续阶段提供 FR 输入
  - 记录需求文档确认历史
  - 供设计阶段计算覆盖度使用

═══════════════════════════════════════════════════════════════════════════════

## 2. 拆分 RTM 文件：rtm-decomposing.yml

**阶段**：decomposing（拆分）  
**生成器**：decomposing-generator.ts  
**触发时机**：
  - confirm:plan（批准拆分计划）
  - task:status（任务状态变更）
  - task:report（任务汇报）

**文件结构**：
```yaml
metadata:
  stage: decomposing
  requirement_id: REQ-xxxxxx
  generated_at: "2024-09-27T12:00:00Z"
  generated_by: dsh-pmboard
  version: 3

inputs:
  requirements:                    # 来自 brainstorming 的 FR
    - id: FR-1
      title: "..."
    - id: FR-2
      title: "..."
  
  design_sections:                 # 来自 design 的设计章节
    - id: "design/architecture.md#section-1"
      title: "架构设计"
      serves: [FR-1, FR-2]         # 该章节服务的 FR
    - id: "design/interface.md#api-design"
      title: "API 设计"
      serves: [FR-1]

outputs:
  tasks:                           # 任务列表（从台账读取）
    - id: t-001
      title: "实现登录 API"
      implements: "design/interface.md#api-design"    # 实现的设计章节
      serves: [FR-1]               # 服务的 FR
      depends_on: []
      phase: implement             # 工作流阶段
      side: backend
    - id: t-002
      title: "登录页面组件"
      implements: "design/interface.md#ui-design"
      serves: [FR-1]
      depends_on: [t-001]
      phase: implement
      side: frontend

traceability:                      # 追溯映射
  design_to_tasks:                 # 设计章节 → 任务
    "design/interface.md#api-design": [t-001]
    "design/interface.md#ui-design": [t-002]
  
  fr_to_tasks:                     # FR → 任务（通过设计桥接）
    FR-1: [t-001, t-002]
    FR-2: []

coverage:
  implementation:                  # 实施覆盖度 ⭐ 关键！
    total: 10                      # 总设计章节数
    covered: 8                     # 被任务接收的章节数
    percentage: 80                 # 覆盖率
    unreceived:                    # 未被任务接收的设计章节
      - "design/data-model.md#section-3"
      - "design/test-strategy.md#section-1"
```

**内容说明**：
- **inputs**：
  - requirements：来自 rtm-brainstorming.yml 的 FR
  - design_sections：来自 rtm-design.yml 的设计章节
- **outputs.tasks**：从台账读取的任务列表（含 implements/serves）
- **traceability**：
  - design_to_tasks：设计章节 → 任务的映射
  - fr_to_tasks：FR → 任务的映射（通过设计桥接）
- **coverage.implementation**：实施覆盖度（设计 → 任务）
- **作用**：
  - **Level 2 追溯链**：设计 ← 任务
  - **编号链完整性门禁**数据源（confirm:plan 时检查）
  - 识别未被任务接收的设计章节（unreceived）

═══════════════════════════════════════════════════════════════════════════════

## 3. 验收 RTM 文件：rtm-accepting.yml

**阶段**：accepting（验收）  
**生成器**：accepting-generator.ts  
**触发时机**：
  - submit:verification（提交验收材料）

**文件结构**：
```yaml
metadata:
  stage: accepting
  requirement_id: REQ-xxxxxx
  generated_at: "2024-09-27T15:00:00Z"
  generated_by: dsh-pmboard
  version: 1

inputs:
  tasks:                           # 来自台账的任务列表
    - id: t-001
      title: "实现登录 API"
      status: done
    - id: t-002
      title: "登录页面组件"
      status: done

outputs:
  test_cases:                      # 测试用例（从测试文件提取）
    - id: "tests/login.spec.ts#should-login-successfully"
      title: "应该成功登录"
      file: "tests/login.spec.ts"
      covers: [t-001, t-002]       # 覆盖的任务（从 @covers 标注提取）
      type: e2e
    - id: "tests/api/auth.test.ts#test-login-api"
      title: "测试登录 API"
      file: "tests/api/auth.test.ts"
      covers: [t-001]
      type: unit

traceability:                      # 追溯映射
  task_to_tests:                   # 任务 → 测试用例
    t-001: 
      - "tests/login.spec.ts#should-login-successfully"
      - "tests/api/auth.test.ts#test-login-api"
    t-002:
      - "tests/login.spec.ts#should-login-successfully"
  
  fr_to_tests:                     # FR → 测试（通过任务桥接）
    FR-1: 
      - "tests/login.spec.ts#should-login-successfully"
      - "tests/api/auth.test.ts#test-login-api"
    FR-2: []

coverage:
  testing:                         # 测试覆盖度 ⭐ 关键！
    total: 15                      # 总任务数
    tested: 12                     # 有测试的任务数
    percentage: 80                 # 测试覆盖率
    untested:                      # 无测试的任务
      - t-003
      - t-007
      - t-012
```

**内容说明**：
- **inputs.tasks**：从台账读取的任务列表（含状态）
- **outputs.test_cases**：从测试文件提取的测试用例
  - 提取规则：通过 @covers 标注识别覆盖的任务
  - 支持 E2E 和单元测试
- **traceability**：
  - task_to_tests：任务 → 测试用例的映射
  - fr_to_tests：FR → 测试的映射（通过任务 + 设计桥接）
- **coverage.testing**：测试覆盖度（任务 → 测试）
- **作用**：
  - **Level 3 追溯链**：任务 ← 测试
  - **文档完整性门禁**数据源（submit:verification 时检查）
  - 识别无测试的任务（untested）

═══════════════════════════════════════════════════════════════════════════════

## 还有设计 RTM 文件：rtm-design.yml

**阶段**：design（设计）  
**生成器**：design-generator.ts  
**触发时机**：
  - confirm:artifact kind=design（确认设计文档）
  - submit:design（提交设计文档，⭐ 门禁预检点）

**文件结构**：
```yaml
metadata:
  stage: design
  requirement_id: REQ-xxxxxx
  generated_at: "2024-09-27T11:30:00Z"
  generated_by: dsh-pmboard
  version: 2

inputs:
  requirements:                    # 来自 brainstorming 的 FR
    - id: FR-1
      title: "用户登录功能"
    - id: FR-2
      title: "数据导出功能"

outputs:
  design_sections:                 # 设计章节（从设计文件提取）
    - id: "design/architecture.md#section-1"
      title: "架构设计"
      file: "docs/requirements/REQ-xxx/design/architecture.md"
      serves: [FR-1, FR-2]         # serves 标注（必须）
      content_preview: "采用前后端分离架构..."
    - id: "design/interface.md#api-design"
      title: "API 设计"
      file: "docs/requirements/REQ-xxx/design/interface.md"
      serves: [FR-1]
      content_preview: "RESTful API 设计..."

traceability:
  fr_to_design:                    # FR → 设计章节映射 ⭐ 核心！
    FR-1: 
      - "design/architecture.md#section-1"
      - "design/interface.md#api-design"
    FR-2:
      - "design/architecture.md#section-1"

coverage:
  design:                          # 设计覆盖度 ⭐⭐⭐ 最严格门禁！
    total: 2                       # 总 FR 数
    covered: 2                     # 有 serves 标注的 FR 数
    percentage: 100                # 覆盖率（必须 100%）
    uncovered: []                  # 未覆盖的 FR（必须为空）
```

**内容说明**：
- **inputs.requirements**：来自 rtm-brainstorming.yml 的 FR
- **outputs.design_sections**：从设计文档提取的章节（含 serves 标注）
- **traceability.fr_to_design**：FR → 设计章节的映射
- **coverage.design**：设计覆盖度（FR → 设计）
- **作用**：
  - **Level 1 追溯链**：需求 ← 设计
  - **设计覆盖度 100% 门禁**数据源（submit:design 时检查，最严格）
  - 识别未被设计覆盖的 FR（uncovered，必须为空）

═══════════════════════════════════════════════════════════════════════════════

## 四个 RTM 文件的依赖关系

```
rtm-brainstorming.yml (需求阶段)
    │
    │ outputs.requirements (FR 列表)
    ↓
rtm-design.yml (设计阶段)
    │
    │ outputs.design_sections (设计章节 + serves 标注)
    ↓
rtm-decomposing.yml (拆分阶段)
    │
    │ outputs.tasks (任务列表 + implements 标注)
    ↓
rtm-accepting.yml (验收阶段)
    │
    │ outputs.test_cases (测试用例 + @covers 标注)
    ↓
三级追溯链完成！
```

═══════════════════════════════════════════════════════════════════════════════

## 三级追溯链映射

| 级别 | 映射关系 | 数据源文件 | 桥接字段 | 门禁 |
|------|---------|-----------|---------|------|
| **Level 1** | 需求 ← 设计 | rtm-design.yml | serves: [FR-x] | ✅ 100% 覆盖度 |
| **Level 2** | 设计 ← 任务 | rtm-decomposing.yml | implements: "design/..." | ✅ 编号链完整性 |
| **Level 3** | 任务 ← 测试 | rtm-accepting.yml | @covers t-xxx | ✅ 文档完整性 |

### 追溯链示例

```
FR-1 (用户登录功能)
  ↓ serves                        [Level 1: 需求 ← 设计]
design/interface.md#api-design
  ↓ implements                    [Level 2: 设计 ← 任务]
t-001 (实现登录 API)
  ↓ @covers                       [Level 3: 任务 ← 测试]
tests/login.spec.ts#should-login-successfully
```

完整追溯：从测试用例可以一路追溯到需求 FR！

═══════════════════════════════════════════════════════════════════════════════

## 总结

✅ **四个核心 RTM 文件按阶段命名**

1. **rtm-brainstorming.yml**（需求）- FR 列表
2. **rtm-design.yml**（设计）- FR → 设计映射 + 100% 覆盖度门禁
3. **rtm-decomposing.yml**（拆分）- 设计 → 任务映射 + 编号链门禁
4. **rtm-accepting.yml**（验收）- 任务 → 测试映射 + 文档完整性门禁

每个文件都有明确的：
- **inputs**：上游阶段的输出
- **outputs**：本阶段的产出
- **traceability**：追溯映射关系
- **coverage**：覆盖度统计（供门禁使用）

这四个文件共同构成了完整的需求追溯体系（RTM）。

═══════════════════════════════════════════════════════════════════════════════