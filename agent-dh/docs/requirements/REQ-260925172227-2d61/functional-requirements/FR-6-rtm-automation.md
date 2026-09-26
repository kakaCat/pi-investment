# FR-6: RTM（需求追踪矩阵）自动生成与维护

## 1. 功能描述

### What（做什么）
工具自动生成和维护 `rtm.yaml` 文件，记录 `task_coverage`（任务覆盖）、`acceptance_tracking`（验收追踪）、覆盖检查规则、验收门禁。

### Why（为什么）
- **机器可读**：RTM 是执行标准，不是文档装饰
- **自动维护**：工具自动填充，不需要人工手写
- **可追溯**：随时查看任务-需求-验收的完整追踪链

### Scope（范围）
- ✅ 自动生成 rtm.yaml：需求创建时初始化
- ✅ 填充 task_coverage：decompose 时写入
- ✅ 填充 acceptance_tracking：submit 时写入
- ✅ 更新 acceptance_tracking：accept_sheet 时写入
- ✅ 校验规则：decompose 时执行
- ❌ 不做：不验证 RTM 的语义正确性（由工具逻辑保证）

## 2. 功能规格

### 2.1 RTM 文件结构

```yaml
version: "1.0"
requirement_id: "REQ-xxx"
generated_at: "2026-09-25T00:00:00Z"

functional_requirements:
  - id: FR-1
    file: functional-requirements/FR-1-xxx.md
    title: 功能点标题
    priority: P0
    acceptance_criteria:
      - id: FR-1-A1
        description: 验收标准描述
        verification: 可证伪的验证方式

task_coverage:                    # 由 decompose 填充
  - task_id: t-xxx
    covers_frs: [FR-1]
    covers_acceptance: [FR-1-A1, FR-1-A2]

acceptance_tracking:              # 由 submit 填充，accept_sheet 更新
  - acceptance_id: FR-1-A1
    status: pending               # pending/passed/failed
    evidence: "..."
    judged_at: null

coverage_rules:                   # 校验规则
  - rule: all_frs_covered
    check: "每个 FR 必须被至少一个任务接收"

acceptance_gate:                  # 验收门禁
  pass_condition: "所有 status 必须为 passed"
  auto_archive: true
```

### 2.2 工具职责

| 工具 | 操作 | 写入内容 |
|-----|------|---------|
| **reqboard_create** | 初始化 rtm.yaml | functional_requirements, coverage_rules, acceptance_gate |
| **reqboard_decompose** | 填充 task_coverage | task_id, covers_frs, covers_acceptance |
| **reqboard_submit** | 填充 acceptance_tracking | acceptance_id, status=pending, evidence |
| **reqboard_accept_sheet** | 更新 acceptance_tracking | status, judged_at, user_feedback |

### 2.3 行为

1. **初始化（reqboard_create）**：
   - 扫描 `functional-requirements/` 目录
   - 从 FR 文件提取 id/title/acceptance_criteria
   - 生成初始 rtm.yaml

2. **填充 task_coverage（reqboard_decompose）**：
   - 读取任务的 `requirement_refs`
   - 从 FR 文件提取对应的验收标准
   - 写入 `task_coverage`

3. **填充 acceptance_tracking（reqboard_submit）**：
   - 读取 `functional_requirements.acceptance_criteria`
   - 为每个验收标准创建追踪记录
   - 初始 `status=pending`

4. **更新 acceptance_tracking（reqboard_accept_sheet）**：
   - 读取用户裁决
   - 更新对应验收项的 `status`/`judged_at`/`user_feedback`

## 3. 验收标准

### 3.1 功能验收
- **A1**: 需求创建时自动生成 rtm.yaml  
  验证：调用 `reqboard_create`，检查 `rtm.yaml` 文件存在

- **A2**: decompose 时填充 task_coverage  
  验证：拆分任务后，`rtm.yaml` 的 `task_coverage` 包含任务记录

- **A3**: submit 时填充 acceptance_tracking  
  验证：提交验收后，`rtm.yaml` 的 `acceptance_tracking` 包含所有验收项

- **A4**: accept_sheet 时更新 acceptance_tracking  
  验证：审核后，`rtm.yaml` 的对应验收项 `status` 变为 `passed` 或 `failed`

### 3.2 质量验收
- **Q1**: RTM 文件格式正确（YAML 合法）
- **Q2**: 并发安全（多个工具同时写入不冲突）

### 3.3 文档验收
- **D1**: RTM 结构文档化（requirement.md 第五章）

## 4. 依赖关系

### 4.1 前置依赖
- FR 文件必须存在

### 4.2 后续依赖
- **FR-1, FR-2, FR-3**: 都依赖 RTM 文件

## 5. 实施建议

### 5.1 技术方案
**修改位置**：各工具文件 + 新建 `rtm-manager.ts`

**核心逻辑**：
```typescript
// rtm-manager.ts
export class RTMManager {
  async init(requirementId: string) {
    const frFiles = scanFRFiles(requirementId);
    const rtm = {
      version: '1.0',
      requirement_id: requirementId,
      functional_requirements: frFiles.map(parseFRFile),
      task_coverage: [],
      acceptance_tracking: [],
      coverage_rules: [...],
      acceptance_gate: {...}
    };
    await writeYAML('rtm.yaml', rtm);
  }
  
  async addTaskCoverage(taskId, coversFRs, coversAcceptance) {
    const rtm = await readYAML('rtm.yaml');
    rtm.task_coverage.push({taskId, coversFRs, coversAcceptance});
    await writeYAML('rtm.yaml', rtm);
  }
  
  // ...其他方法
}
```

### 5.2 拆分建议
- **Task 1**: 实现 RTMManager 类
- **Task 2**: 集成到 reqboard_create（初始化）
- **Task 3**: 集成到 reqboard_decompose（填充 task_coverage）
- **Task 4**: 集成到 reqboard_submit/accept_sheet（填充/更新 acceptance_tracking）

## 6. 变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|-----|------|---------|------|
| v1.0 | 2026-09-25 | 初始版本 | Agent |

## 7. 接收状态

> 本节由系统自动维护

- 待分配任务

---

**文件路径**: `functional-requirements/FR-6-rtm-automation.md`  
**功能点编号**: FR-6  
**所属需求**: REQ-260925172227-2d61
