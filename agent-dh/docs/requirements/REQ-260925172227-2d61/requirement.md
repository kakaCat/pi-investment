# REQ-260925172227-2d61: REQ流水线拆分与验收问题修复

## 边界

**做什么**：
1. **拆分问题修复**：确保 `reqboard_decompose` 生成的任务卡包含 `implementation` 和可证伪 `acceptance`
2. **验收单生成修复**：`reqboard_submit(kind=verification)` 能正确生成验收单
3. **验收流程修复**：`reqboard_accept_sheet` 弹框逐项验收、记录裁决、处理返工卡、验收通过后自动归档

**不做什么**：
- 不改 REQ 流水线的其他阶段（brainstorming/design 保持现状）
- 不新增验收维度（只修复现有 FR 条款验收）
- 不改数据模型结构（在现有 dsh-reqboard.json schema 内修复）

**轻路径依据**：
- 改动面小：只涉及 decompose/submit/accept_sheet 三个工具的逻辑修复
- 无新决策点：验收标准、返工机制、自动推进逻辑都已在 RFC 015 中定义
- 不动数据模型：在现有 verification_sheet / rework_tasks 结构内修复

## 产品定义

### 目标
修复 REQ 流水线的拆分与验收问题，让任务拆分后能正确执行、验收单能正常提交并通过人工审核。

### 可证伪判定标准
1. 执行 `reqboard_decompose` 能成功落库任务，任务卡包含实施方案与可证伪验收标准
2. 任务执行完成后，`reqboard_submit(kind=verification)` 能生成验收单
3. 验收单能弹框让人逐项审核，审核结果正确记录到数据库
4. 全部通过后需求自动推进到 `done` 或 `archived`

### 问题背景
当前 REQ 流水线存在三个关键问题：
1. **任务卡缺实施方案**：`reqboard_decompose` 生成的任务卡可能缺少 `implementation` 字段
2. **验收单生成失败**：`reqboard_submit(kind=verification)` 无法正确提取任务验收标准或匹配证据
3. **验收流程断链**：`reqboard_accept_sheet` 弹框后用户裁决无法正确记录，或返工卡处理逻辑缺失

## 用户与角色

### 主要用户
- **Agent 执行窗口**：调用 `reqboard_decompose` 拆分任务、调用 `reqboard_submit(kind=verification)` 提交验收
- **人工审核者**：通过 `reqboard_accept_sheet` 弹框逐项审核验收单，或在看板上操作

### 使用场景
1. Agent 完成需求设计后，调用 `reqboard_decompose` 拆分成任务 DAG
2. Agent 执行完所有任务后，调用 `reqboard_submit(kind=verification)` 提交验收材料
3. 人工审核者收到弹框，逐项审核验收单（通过/改进/其他）
4. 审核未通过的任务进入返工队列，Agent 处理返工卡
5. 全部通过后系统自动归档需求

## 功能点

> **说明**：本需求让 REQ 流水线每个阶段都支持 RTM（需求追踪矩阵），实现从需求分析到验收的完整追踪。

### 需求分析阶段（brainstorming）

- **FR-1: RTM 初始化 - 需求创建时生成 rtm.yaml**  
  `reqboard_create` 时扫描 FR 文件，生成 rtm.yaml（包含 functional_requirements、coverage_rules、acceptance_gate）。详见：[functional-requirements/FR-1-rtm-init-brainstorming.md](functional-requirements/FR-1-rtm-init-brainstorming.md)

### 设计阶段（design）

- **FR-2: RTM 校验 - 设计文档提交时校验 FR 文件完整性**  
  `reqboard_submit(kind=design)` 时校验所有 FR 文件存在、包含完整章节、验收标准可证伪。详见：[functional-requirements/FR-2-rtm-validate-design.md](functional-requirements/FR-2-rtm-validate-design.md)

### 拆分阶段（decomposing）

- **FR-3: RTM 填充 task_coverage - 任务拆分时记录覆盖关系**  
  `reqboard_decompose` 时填充 task_coverage（任务接收了哪些 FR），校验覆盖度 100%。详见：[functional-requirements/FR-3-rtm-coverage-decompose.md](functional-requirements/FR-3-rtm-coverage-decompose.md)

### 实施阶段（implementing）

- **FR-4: RTM 追踪任务状态 - 任务执行时更新进度**  
  `reqboard_task_move` 时更新任务状态到 task_coverage，`reqboard_task_report` 时更新 FR 文件第 7 章。详见：[functional-requirements/FR-4-rtm-track-implementing.md](functional-requirements/FR-4-rtm-track-implementing.md)

### 验收阶段（accepting）

- **FR-5: RTM 填充 acceptance_tracking - 提交验收时生成验收追踪**  
  `reqboard_submit(kind=verification)` 时从 FR 文件提取验收标准，填充 acceptance_tracking（status=pending）。详见：[functional-requirements/FR-5-rtm-acceptance-submit.md](functional-requirements/FR-5-rtm-acceptance-submit.md)

- **FR-6: RTM 更新 acceptance_tracking - 人工审核时记录裁决**  
  `reqboard_accept_sheet` 时更新 acceptance_tracking（status=passed/failed），检查验收门禁，触发自动归档。详见：[functional-requirements/FR-6-rtm-acceptance-review.md](functional-requirements/FR-6-rtm-acceptance-review.md)

### 全流程支持

- **FR-7: RTM 查询与可视化 - 随时查看追踪状态**  
  `reqboard_status` 显示 FR 覆盖度、任务进度、验收进度，支持按 FR/按阶段查询。详见：[functional-requirements/FR-7-rtm-query-visualization.md](functional-requirements/FR-7-rtm-query-visualization.md)

### 功能点索引表

| 编号 | 功能点 | 文件路径 | 优先级 | 依赖 |
|-----|-------|---------|--------|------|
| FR-1 | 任务卡包含实施方案与可证伪验收标准 | [functional-requirements/FR-1-task-card-validation.md](functional-requirements/FR-1-task-card-validation.md) | P0 | 无 |
| FR-2 | 验收单正确生成 | [functional-requirements/FR-2-verification-sheet-generation.md](functional-requirements/FR-2-verification-sheet-generation.md) | P0 | FR-1 |
| FR-3 | 验收弹框逐项审核并记录裁决 | [functional-requirements/FR-3-acceptance-review.md](functional-requirements/FR-3-acceptance-review.md) | P0 | FR-2 |
| FR-4 | 返工卡正确生成与处理 | [functional-requirements/FR-4-rework-handling.md](functional-requirements/FR-4-rework-handling.md) | P0 | FR-3 |
| FR-5 | status 支持显示 FR 覆盖度和验收进度 | [functional-requirements/FR-5-status-fr-tracking.md](functional-requirements/FR-5-status-fr-tracking.md) | P0 | FR-1 |
| FR-6 | RTM 自动生成与维护 | [functional-requirements/FR-6-rtm-automation.md](functional-requirements/FR-6-rtm-automation.md) | P0 | FR-1, FR-2, FR-3 |

**功能点文件结构**（每个文件包含）：
1. 功能描述（What/Why/Scope）
2. 功能规格（输入/输出/行为/约束）
3. 验收标准（功能/质量/文档验收）
4. 依赖关系（前置/后续）
5. 实施建议（技术方案/拆分建议/测试要点）
6. 变更历史
7. 接收状态（由系统自动维护）

## 需求追踪矩阵（RTM）

**机器可读的执行标准**：[rtm.yaml](rtm.yaml)

### 5.1 功能需求清单

| FR编号 | 功能点 | 验收标准 | 优先级 | 依赖 |
|-------|-------|---------|--------|------|
| **FR-1** | 任务卡包含实施方案与可证伪验收标准 | FR-1-A1: 提交完整字段任务成功落库<br>FR-1-A2: 缺implementation返回错误<br>FR-1-A3: 缺acceptance返回错误<br>FR-1-A4: 错误信息包含任务key | P0 | 无 |
| **FR-2** | 验收单正确生成 | FR-2-A1: 成功生成验收单<br>FR-2-A2: 需求状态变更为accepting<br>FR-2-A3: 验收项包含任务信息和证据<br>FR-2-A4: 续验时只包含上版未通过项 | P0 | FR-1 |
| **FR-3** | 验收弹框逐项审核并记录裁决 | FR-3-A1: 弹框成功展示待验项<br>FR-3-A2: 裁决结果正确写入数据库<br>FR-3-A3: 返回信息包含统计数据<br>FR-3-A4: 全部通过时自动归档 | P0 | FR-2 |
| **FR-4** | 返工卡正确生成与处理 | FR-4-A1: 验收未通过时自动生成返工卡<br>FR-4-A2: reqboard_status能查询到返工卡<br>FR-4-A3: 续验时只包含返工项<br>FR-4-A4: 返工解决后标记resolved | P0 | FR-3 |
| **FR-5** | status 支持显示 FR 覆盖度和验收进度 | FR-5-A1: 返回 fr_coverage 列表<br>FR-5-A2: 返回 fr_acceptance_progress<br>FR-5-A3: 显示未接收的 FR<br>FR-5-A4: 显示验收未通过的 FR | P0 | FR-1 |
| **FR-6** | RTM 自动生成与维护 | FR-6-A1: 需求创建时自动生成 rtm.yaml<br>FR-6-A2: decompose 时填充 task_coverage<br>FR-6-A3: submit 时填充 acceptance_tracking<br>FR-6-A4: accept_sheet 时更新 acceptance_tracking | P0 | FR-1, FR-2, FR-3 |

**共 24 个可证伪验收标准**（每个 FR 包含 4 个验收项 A1-A4）

### 5.2 任务-需求追踪（task_coverage）

**作用**：记录哪些任务接收了哪些功能需求

**由 reqboard_decompose 填充**：
```yaml
task_coverage:
  - task_id: t-xxx            # 任务 id
    task_key: t1              # 批次内键
    task_title: 实现任务卡校验逻辑
    covers_frs: [FR-1]        # 接收的 FR 列表
    covers_acceptance:        # 接收的验收标准列表
      - FR-1-A1
      - FR-1-A2
      - FR-1-A3
      - FR-1-A4
```

**校验规则**：
- ✅ 所有 FR 必须被至少一个任务接收（`covers_frs` 不能为空）
- ✅ 所有验收标准必须有对应的验收项（`covers_acceptance` 不能为空）

### 5.3 验收追踪（acceptance_tracking）

**作用**：记录每个验收标准的验收状态

**由 reqboard_submit(verification) 填充**：
```yaml
acceptance_tracking:
  - acceptance_id: FR-1-A1
    status: pending           # pending/passed/failed
    evidence: "执行 npm test -- decompose.test.ts，输出：PASS 4/4"
    judged_at: null           # 裁决时间戳
    judged_by: null           # 裁决人
    user_feedback: null       # 失败时的反馈意见
```

**由 reqboard_accept_sheet 更新**：
- 人工裁决后，更新 `status`, `judged_at`, `judged_by`, `user_feedback`

### 5.4 覆盖检查规则（coverage_rules）

| 规则 | 描述 | 检查方式 |
|-----|------|---------|
| **all_frs_covered** | 所有功能需求必须被至少一个任务接收 | 每个 FR 的 id 必须出现在至少一个 `task_coverage.covers_frs` 中 |
| **all_acceptance_covered** | 所有验收标准必须有对应的验收项 | 每个 FR-*-A* 必须出现在 `acceptance_tracking` 中 |
| **file_exists** | 功能需求文件必须存在 | 每个 FR 的 file 路径必须指向存在的文件 |

**由 reqboard_decompose 执行校验**：
- 拆分时检查 `all_frs_covered` 规则
- 未覆盖的 FR 会被标记为 `unreceived_clauses`（红色）
- 阻止提交验收，直到所有 FR 被覆盖

### 5.5 验收门禁（acceptance_gate）

**通过条件**：
```yaml
pass_condition: "所有 acceptance_tracking 的 status 必须为 passed"
```

**失败处理**：
```yaml
fail_action: "生成 rework_tasks，要求 Agent 处理返工"
```

**自动归档**：
```yaml
auto_archive: true
archive_condition: "pass_condition 满足时自动调用 reqboard_move(to='archived')"
```

### 5.6 工具如何使用 RTM

| 工具 | 读取 | 写入 | 校验 |
|-----|------|------|------|
| **reqboard_decompose** | - 读取 `functional_requirements` 清单<br>- 读取 `coverage_rules` | - 填充 `task_coverage` | - 校验 `all_frs_covered`<br>- 校验 `file_exists` |
| **reqboard_submit(verification)** | - 读取 FR 文件的验收标准<br>- 读取 `task_coverage` | - 填充 `acceptance_tracking` | - 校验 `all_acceptance_covered` |
| **reqboard_accept_sheet** | - 读取 `acceptance_tracking`<br>- 读取 `acceptance_gate` | - 更新 `acceptance_tracking.status`<br>- 生成 `rework_tasks` | - 检查 `pass_condition`<br>- 触发 `auto_archive` |

### 5.7 RTM 在各阶段的设计

#### 5.7.1 需求分析阶段（brainstorming）

**RTM 初始化**：
- **触发时机**：需求创建时（`reqboard_create`）
- **生成内容**：
  ```yaml
  # 扫描 functional-requirements/ 目录
  functional_requirements:
    - id: FR-1
      file: functional-requirements/FR-1-xxx.md
      title: 从文件第一行提取
      priority: P0  # 从文件 front-matter 提取
      acceptance_criteria:
        - id: FR-1-A1
          description: 从"验收标准"章节提取
          verification: 可证伪的验证方式
  
  # 定义覆盖规则
  coverage_rules:
    - rule: all_frs_covered
      check: "每个 FR 必须被至少一个任务接收"
  
  # 定义验收门禁
  acceptance_gate:
    pass_condition: "所有 status 必须为 passed"
    auto_archive: true
  ```

- **验证点**：
  - ✅ rtm.yaml 文件已创建
  - ✅ 包含所有 FR 文件的元数据
  - ✅ 每个 FR 的验收标准（A1-A4）已提取

#### 5.7.2 设计阶段（design）

**RTM 校验**：
- **触发时机**：设计文档提交时（`reqboard_submit(kind=design)`）
- **校验内容**：
  - 检查所有 FR 文件是否存在
  - 检查每个 FR 文件是否包含完整的 7 个章节
  - 检查验收标准是否可证伪
  
- **输出结果**：
  ```yaml
  design_validation:
    fr_files_exist: true
    missing_files: []
    incomplete_files:  # 缺少必要章节的文件
      - file: FR-1-xxx.md
        missing_sections: ["5. 实施建议"]
    unfalsifiable_acceptance:  # 验收标准不可证伪
      - FR-2-A3: "系统性能良好"  # ❌ 不可证伪
  ```

- **验证点**：
  - ✅ 所有 FR 文件完整
  - ✅ 验收标准可证伪
  - ✅ 依赖关系清晰

#### 5.7.3 拆分阶段（decomposing）

**RTM 填充 task_coverage**：
- **触发时机**：任务拆分时（`reqboard_decompose`）
- **填充内容**：
  ```yaml
  task_coverage:
    - task_id: t-xxx
      task_key: t1
      task_title: 实现 decompose FR 支持
      covers_frs: [FR-1]              # 从任务的 requirement_refs 读取
      covers_acceptance:              # 从 FR 文件提取
        - FR-1-A1
        - FR-1-A2
        - FR-1-A3
        - FR-1-A4
      assigned_at: 1234567890         # 拆分时间戳
  ```

- **校验内容**：
  - 检查所有 FR 是否被至少一个任务覆盖
  - 计算 `unreceived_clauses`（未被覆盖的 FR）
  
- **输出结果**：
  ```yaml
  coverage_check:
    total_frs: 6
    covered_frs: 5
    unreceived_clauses: [FR-6]  # FR-6 未被任何任务接收
    coverage_rate: 83%
  ```

- **验证点**：
  - ✅ task_coverage 已填充
  - ✅ 覆盖度 = 100%（所有 FR 被覆盖）
  - ⚠️ 覆盖度 < 100% 时给出警告

#### 5.7.4 实施阶段（implementing）

**RTM 追踪任务状态**：
- **触发时机**：任务状态变更时（`reqboard_task_move`）
- **更新内容**：
  ```yaml
  task_coverage:
    - task_id: t-xxx
      covers_frs: [FR-1]
      status: in_progress           # 新增：任务状态
      started_at: 1234567890        # 新增：开始时间
      completed_at: null            # 任务完成时填充
  ```

- **实时统计**：
  ```yaml
  implementation_progress:
    total_tasks: 10
    completed_tasks: 3
    in_progress_tasks: 2
    pending_tasks: 5
    
    # 按 FR 分组的进度
    fr_progress:
      - fr_id: FR-1
        total_tasks: 2
        completed_tasks: 1
        progress: 50%
      - fr_id: FR-2
        total_tasks: 3
        completed_tasks: 0
        progress: 0%
  ```

- **验证点**：
  - ✅ 任务状态实时更新到 RTM
  - ✅ 可按 FR 查询实施进度
  - ✅ 任务完成时更新 FR 文件第 7 章

#### 5.7.5 验收阶段（accepting）

**RTM 填充 acceptance_tracking**：
- **触发时机（submit）**：提交验收时（`reqboard_submit(kind=verification)`）
  ```yaml
  acceptance_tracking:
    - acceptance_id: FR-1-A1
      fr_id: FR-1
      description: 提交完整字段任务成功落库
      verification: "调用 reqboard_decompose(...)"
      status: pending               # 初始状态
      evidence: null                # 待填充
      judged_at: null
      judged_by: null
      user_feedback: null
  ```

- **触发时机（accept_sheet）**：人工审核时（`reqboard_accept_sheet`）
  ```yaml
  acceptance_tracking:
    - acceptance_id: FR-1-A1
      status: passed                # 更新：裁决结果
      evidence: "执行测试通过，输出：PASS 4/4"
      judged_at: 1234567890         # 更新：裁决时间
      judged_by: "user_123"         # 更新：裁决人
      user_feedback: null           # passed 时为空
  ```

- **验收门禁检查**：
  ```yaml
  acceptance_gate_check:
    total_acceptance: 24            # 6 FR × 4 验收项
    passed: 20
    failed: 2
    pending: 2
    pass_rate: 83%
    
    gate_status: blocked            # passed / blocked
    block_reason: "FR-3-A2 和 FR-4-A1 未通过"
    
    failed_items:
      - acceptance_id: FR-3-A2
        user_feedback: "裁决结果未正确写入数据库"
      - acceptance_id: FR-4-A1
        user_feedback: "返工卡生成逻辑有bug"
  ```

- **验证点**：
  - ✅ acceptance_tracking 已填充（submit 时）
  - ✅ 裁决结果已记录（accept_sheet 时）
  - ✅ 门禁检查通过 → 自动归档
  - ⚠️ 门禁检查失败 → 生成返工卡

### 5.8 RTM 的完整生命周期

```
需求分析 (brainstorming)
    ↓
  生成 rtm.yaml (初始化)
  - functional_requirements
  - coverage_rules
  - acceptance_gate
    ↓
设计 (design)
    ↓
  校验 FR 文件完整性
  - fr_files_exist
  - incomplete_files
  - unfalsifiable_acceptance
    ↓
拆分 (decomposing)
    ↓
  填充 task_coverage (decompose)
  - covers_frs
  - covers_acceptance
  - 校验覆盖度 (100%)
    ↓
实施 (implementing)
    ↓
  追踪任务状态 (task_move)
  - status: in_progress / done
  - 更新 FR 文件第 7 章 (task_report)
    ↓
验收 (accepting)
    ↓
  填充 acceptance_tracking (submit)
  - status: pending
    ↓
  更新 acceptance_tracking (accept_sheet)
  - status: passed / failed
  - judged_at, user_feedback
    ↓
  检查验收门禁
  - pass_rate = 100%?
    ├─ Yes → 自动归档
    └─ No  → 生成返工卡 → 回到实施
```

### 5.9 完整 RTM 文件

**详细内容**：[rtm.yaml](rtm.yaml)（包含完整的 YAML 结构和注释）

## 整体流程

```
需求进入 implementing
        ↓
   Agent 执行任务
        ↓
  所有任务完成？ ───No──→ 继续执行
        ↓ Yes
调用 reqboard_submit(kind=verification)
        ↓
  系统生成验收单 (FR-2)
        ↓
  需求推进到 accepting
        ↓
调用 reqboard_accept_sheet
        ↓
  弹框展示验收项 (FR-3)
        ↓
    人工裁决
        ├─→ 全部通过 ──→ 自动归档 (FR-5) ──→ 需求完成
        └─→ 部分失败 ──→ 生成返工卡 (FR-4)
                              ↓
                        Agent 处理返工
                              ↓
                    重新提交验收（续验模式）
                              ↓
                    调用 reqboard_accept_sheet
                              ↓
                          （重新审核）
```

## 接口定义

详见各功能点文件的"功能规格"章节：
- FR-1：`reqboard_decompose` 的 `tasks` 参数校验
- FR-2：`reqboard_submit(kind=verification)` 的输入输出
- FR-3：`reqboard_accept_sheet` 的输入输出
- FR-4：`rework_tasks` 数据结构
- FR-5：自动归档触发条件

## 数据契约

详见各功能点文件的"功能规格"章节：
- **Task**：必须包含 `implementation` 和 `acceptance` 字段（FR-1）
- **VerificationSheet**：包含 `version`, `items`, `created_at`（FR-2）
- **VerificationItem**：包含 `task_id`, `acceptance`, `evidence`, `status`, `user_feedback`, `judged_at`（FR-3）
- **ReworkTask**：包含 `task_id`, `reason`, `created_at`, `resolved`（FR-4）

## 迁移与兼容

### 旧数据兼容
- **旧任务卡缺字段**：首次验收时标记为 `thin_cards` 警告，允许人工补全
- **旧验收单无 version**：读取时默认 `version=1`
- **旧 rework_tasks 无 resolved**：读取时默认 `resolved=false`

### 不可回滚点
- 提交第一张验收单后，需求进入 `accepting` 状态，回滚需人工操作
- 验收通过自动归档后，回滚需人工操作

## 验收标准

完整的验收标准在 [rtm.yaml](rtm.yaml) 中定义，包含 20 个可证伪的验收项（FR-1-A1 至 FR-5-A4）。

**整体验收流程**：
1. 拆分任务（包含 implementation + acceptance）→ FR-1 通过
2. 完成任务并提交验收 → FR-2 通过
3. 人工审核（弹框） → FR-3 通过
4. 审核未通过生成返工卡 → FR-4 通过
5. 全部通过自动归档 → FR-5 通过

## 非功能需求

### 性能
- 单次验收弹框响应时间 < 2s（batch_size=10）
- 验收单生成时间 < 5s（任务数 ≤ 50）

### 可靠性
- 验收裁决写入失败时自动重试 3 次
- 弹框超时（30s 无响应）时返回 fallback=board

### 可观测性
- 每次验收操作记录到需求 comments（时间戳/操作者/结果）
- 返工卡生成时发送通知（可选）

---

**文档版本**: v2.0  
**创建时间**: 2026-09-25  
**更新时间**: 2026-09-25  
**作者**: Agent (session-18ecbbd5)  
**变更记录**: 
- v1.0-v1.5: 单文件格式，包含所有功能点细节
- v2.0: **结构化重构**：功能点拆分到独立文件，requirement.md 改为索引表，新增机器可读的 rtm.yaml

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | 🔴 **未被接收** | — |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | 🔴 **未被接收** | — |
| FR-5 | 🔴 **未被接收** | — |
| FR-6 | 🔴 **未被接收** | — |
| FR-7 | 🔴 **未被接收** | — |

> 🔴 **未被接收（7 条）**：FR-1、FR-2、FR-3、FR-4、FR-5、FR-6、FR-7

<!-- reqboard:marks:end -->
