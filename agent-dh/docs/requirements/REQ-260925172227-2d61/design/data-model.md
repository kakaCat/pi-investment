# 数据模型

## 1. rtm.yaml 数据结构（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）
### 1.1 完整结构（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
```yaml
# RTM（需求追踪矩阵）
version: "1.0"                        # RTM 格式版本
requirement_id: "REQ-xxx"             # 需求 ID
generated_at: "2026-09-25T00:00:00Z"  # 生成时间（ISO 8601）

# 功能需求清单（由 RTMManager.init() 填充）
functional_requirements:
  - id: "FR-1"                        # FR 编号
    file: "functional-requirements/FR-1-xxx.md"  # 文件相对路径
    title: "RTM 初始化"               # 标题
    priority: "P0"                    # 优先级
    depends_on: []                    # 依赖的其他 FR
    acceptance_criteria:              # 验收标准列表
      - id: "FR-1-A1"                 # 验收标准编号
        description: "需求创建时自动生成 rtm.yaml"  # 描述
        verification: "调用 reqboard_create，检查 rtm.yaml 文件存在"  # 验证方式

# 任务覆盖追踪（由 RTMManager.addTaskCoverage() 填充）
task_coverage:
  - task_id: "t-xxx"                  # 任务 ID
    task_key: "t1"                    # 批次内键
    task_title: "实现 RTM 初始化"      # 任务标题
    covers_frs:                       # 接收的 FR 列表
      - "FR-1"
    covers_acceptance:                # 接收的验收标准列表
      - "FR-1-A1"
      - "FR-1-A2"
      - "FR-1-A3"
      - "FR-1-A4"
    assigned_at: 1234567890           # 拆分时间戳（Unix timestamp）
    status: "todo"                    # 任务状态（由 trackTaskStatus 更新）
    started_at: null                  # 开始时间戳
    completed_at: null                # 完成时间戳

# 验收追踪（由 RTMManager.fillAcceptanceTracking() 填充）
acceptance_tracking:
  - acceptance_id: "FR-1-A1"          # 验收标准编号
    fr_id: "FR-1"                     # 所属 FR
    description: "需求创建时自动生成 rtm.yaml"  # 描述
    verification: "调用 reqboard_create，检查 rtm.yaml 文件存在"  # 验证方式
    status: "pending"                 # 状态：pending/passed/failed
    evidence: null                    # 证据（初始为 null）
    judged_at: null                   # 裁决时间戳（初始为 null）
    judged_by: null                   # 裁决人（初始为 null）
    user_feedback: null               # 用户反馈（失败时填充）

# 覆盖检查规则（由 RTMManager.init() 填充）
coverage_rules:
  - rule: "all_frs_covered"
    description: "所有功能需求必须被至少一个任务接收"
    check: "每个 FR 的 id 必须出现在至少一个 task_coverage.covers_frs 中"
  
  - rule: "all_acceptance_covered"
    description: "所有验收标准必须有对应的验收项"
    check: "每个 FR-*-A* 必须出现在 acceptance_tracking 中"
  
  - rule: "file_exists"
    description: "功能需求文件必须存在"
    check: "每个 FR 的 file 路径必须指向存在的文件"

# 验收门禁（由 RTMManager.init() 填充）
acceptance_gate:
  pass_condition: "所有 acceptance_tracking 的 status 必须为 passed"
  fail_action: "生成 rework_tasks，要求 Agent 处理返工"
  auto_archive: true
  archive_condition: "pass_condition 满足时自动调用 reqboard_move(to='archived')"
```

---

## 2. 字段说明（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）
### 2.1 functional_requirements（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
| 字段 | 类型 | 必填 | 说明 | 示例 |
|-----|------|-----|------|------|
| id | string | ✅ | FR 编号 | "FR-1" |
| file | string | ✅ | 文件相对路径 | "functional-requirements/FR-1-xxx.md" |
| title | string | ✅ | 标题 | "RTM 初始化" |
| priority | "P0"|"P1"|"P2" | ✅ | 优先级 | "P0" |
| depends_on | string[] | ⬜ | 依赖的其他 FR | ["FR-2"] |
| acceptance_criteria | array | ✅ | 验收标准列表 | 见下 |

### 2.2 acceptance_criteria（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
| 字段 | 类型 | 必填 | 说明 | 示例 |
|-----|------|-----|------|------|
| id | string | ✅ | 验收标准编号 | "FR-1-A1" |
| description | string | ✅ | 描述 | "需求创建时自动生成 rtm.yaml" |
| verification | string | ✅ | 可证伪的验证方式 | "调用 reqboard_create，检查 rtm.yaml 文件存在" |

### 2.3 task_coverage（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
| 字段 | 类型 | 必填 | 说明 | 示例 |
|-----|------|-----|------|------|
| task_id | string | ✅ | 任务 ID | "t-xxx" |
| task_key | string | ✅ | 批次内键 | "t1" |
| task_title | string | ✅ | 任务标题 | "实现 RTM 初始化" |
| covers_frs | string[] | ✅ | 接收的 FR 列表 | ["FR-1"] |
| covers_acceptance | string[] | ✅ | 接收的验收标准列表 | ["FR-1-A1", "FR-1-A2"] |
| assigned_at | number | ✅ | 拆分时间戳 | 1234567890 |
| status | TaskStatus | ⬜ | 任务状态 | "in_progress" |
| started_at | number|null | ⬜ | 开始时间戳 | 1234567890 |
| completed_at | number|null | ⬜ | 完成时间戳 | 1234567890 |

**TaskStatus 枚举**：
```typescript
type TaskStatus = 
  | 'todo'          // 待开始
  | 'in_progress'   // 进行中
  | 'testing'       // 测试中
  | 'in_review'     // 审核中
  | 'done'          // 已完成
  | 'canceled';     // 已取消
```

### 2.4 acceptance_tracking（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
| 字段 | 类型 | 必填 | 说明 | 示例 |
|-----|------|-----|------|------|
| acceptance_id | string | ✅ | 验收标准编号 | "FR-1-A1" |
| fr_id | string | ✅ | 所属 FR | "FR-1" |
| description | string | ✅ | 描述 | "需求创建时自动生成 rtm.yaml" |
| verification | string | ✅ | 验证方式 | "调用 reqboard_create，检查 rtm.yaml 文件存在" |
| status | AcceptanceStatus | ✅ | 状态 | "passed" |
| evidence | string|null | ⬜ | 证据 | "执行测试通过" |
| judged_at | number|null | ⬜ | 裁决时间戳 | 1234567890 |
| judged_by | string|null | ⬜ | 裁决人 | "user_123" |
| user_feedback | string|null | ⬜ | 用户反馈（失败时） | "测试覆盖不足" |

**AcceptanceStatus 枚举**：
```typescript
type AcceptanceStatus = 
  | 'pending'       // 待审核
  | 'passed'        // 已通过
  | 'failed';       // 未通过
```

---

## 3. FR 文件结构（serves: FR-1, FR-2, FR-4）
### 3.1 标准章节结构（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
每个 FR 文件（`functional-requirements/FR-*.md`）必须包含以下章节：

```markdown
# FR-N: 功能点标题

## 1. 功能描述

### What（做什么）

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**
### Why（为什么）

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**
### Scope（范围）

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**

## 2. 功能规格

### 2.1 输入

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**
### 2.2 输出

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**
### 2.3 行为

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**
### 2.4 约束

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**

## 3. 验收标准

### 3.1 功能验收

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**
- **A1**: 描述
  验证：可证伪的验证方式
- **A2**: 描述
  验证：可证伪的验证方式

### 3.2 质量验收

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**
### 3.3 文档验收

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**

## 4. 依赖关系

### 4.1 前置依赖

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**
### 4.2 后续依赖

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**

## 5. 实施建议

### 5.1 技术方案

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**
### 5.2 拆分建议

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**
### 5.3 测试要点

**serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7**

## 6. 变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|-----|------|---------|------|

## 7. 接收状态

> 本节由系统自动维护

- 待分配任务
```

### 3.2 第 7 章"接收状态"格式（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**由 RTMManager.updateFRFileReceiveStatus() 自动更新**：

```markdown
## 7. 接收状态

> 本节由系统自动维护，记录哪些任务接收了本功能点

- **任务 t-xxx**（实现 RTM 初始化）：✅ 已接收（2026-09-25）
- **任务 t-yyy**（集成测试）：✅ 已接收（2026-09-26）
```

---

## 4. 数据约束（serves: FR-1, FR-2, FR-3, FR-5, FR-6）
### 4.1 唯一性约束（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
- `functional_requirements[].id` 必须唯一
- `task_coverage[].task_id` 必须唯一
- `acceptance_tracking[].acceptance_id` 必须唯一

### 4.2 外键约束（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
- `task_coverage[].covers_frs[]` 必须引用存在的 `functional_requirements[].id`
- `task_coverage[].covers_acceptance[]` 必须引用存在的 `acceptance_criteria[].id`
- `acceptance_tracking[].fr_id` 必须引用存在的 `functional_requirements[].id`
- `acceptance_tracking[].acceptance_id` 必须引用存在的 `acceptance_criteria[].id`

### 4.3 格式约束（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
- FR 编号格式：`/^FR-\d+$/`（如 FR-1, FR-10）
- 验收标准编号格式：`/^FR-\d+-A\d+$/`（如 FR-1-A1）
- 时间戳：Unix timestamp（秒）
- 任务 ID 格式：`/^t-[a-z0-9]+$/`（如 t-xxx）

### 4.4 必填约束（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**初始化时必填**（RTMManager.init）：
- `version`
- `requirement_id`
- `generated_at`
- `functional_requirements`（至少 1 个）
- `coverage_rules`
- `acceptance_gate`

**拆分时必填**（addTaskCoverage）：
- `task_coverage[].task_id`
- `task_coverage[].covers_frs`（至少 1 个）

**验收提交时必填**（fillAcceptanceTracking）：
- `acceptance_tracking[].acceptance_id`
- `acceptance_tracking[].status = 'pending'`

**验收审核时必填**（updateAcceptanceTracking）：
- `acceptance_tracking[].status`（passed 或 failed）
- `acceptance_tracking[].judged_at`
- `acceptance_tracking[].judged_by`
- 若 `status = 'failed'`，则 `user_feedback` 必填

---

## 5. 数据迁移（serves: FR-1）
### 5.1 从无到有（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景**：旧需求没有 rtm.yaml

**处理**：
1. 调用 `RTMManager.init()` 生成 rtm.yaml
2. 若已有任务，调用 `addTaskCoverage()` 补充覆盖关系
3. 若已在验收，调用 `fillAcceptanceTracking()` 补充验收追踪

### 5.2 从旧格式到新格式（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景**：rtm.yaml 格式升级

**处理**：
1. 读取旧格式文件
2. 转换为新格式（保留已有数据）
3. 写回文件，备份旧版本

### 5.3 回滚路径（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**场景**：需要回退到旧版本

**处理**：
1. 删除 rtm.yaml（或重命名为 rtm.yaml.bak）
2. 系统降级为"无 RTM"模式（不影响核心流程）
3. FR 文件的第 7 章保持不变（人工可读）

---

## 6. 数据存储位置（serves: FR-1）
### 6.1 rtm.yaml（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**位置**：`docs/requirements/<REQ>/rtm.yaml`

**权限**：
- 读：所有工具
- 写：仅 RTMManager

### 6.2 FR 文件（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**位置**：`docs/requirements/<REQ>/functional-requirements/FR-*.md`

**权限**：
- 读：所有工具、人工
- 写：人工（1-6 章）、RTMManager（第 7 章）

---

## 7. 性能考虑（serves: FR-3, FR-7）
### 7.1 文件大小估算（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
**单个需求**：
- rtm.yaml：~10KB（10 个 FR × 4 个验收标准）
- FR 文件：~5KB × 10 = 50KB

**总计**：~60KB（可接受）

### 7.2 读写频率（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7）
| 操作 | 频率 | 文件 |
|-----|------|------|
| init | 1 次/需求 | rtm.yaml（创建） |
| validate | 1 次/需求 | FR 文件（读） |
| addTaskCoverage | 1 次/需求 | rtm.yaml（追加） |
| trackTaskStatus | N 次（任务状态变更） | rtm.yaml（更新） |
| fillAcceptanceTracking | 1 次/需求 | rtm.yaml（追加） |
| updateAcceptanceTracking | M 次（分批审核） | rtm.yaml（更新） |
| query | 随时 | rtm.yaml（读） |

**优化**：
- 缓存 rtm.yaml 在内存（写后失效）
- 批量更新（减少写次数）

---

**文档版本**: v1.0  
**最后更新**: 2026-09-25  
**作者**: Agent