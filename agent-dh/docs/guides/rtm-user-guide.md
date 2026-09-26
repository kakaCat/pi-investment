# RTM 使用指南

## 1. RTM 是什么

**RTM (Requirements Traceability Matrix)** 是需求可追溯性矩阵，用于追踪需求从定义到验收的完整路径。

### 核心功能

- **FR 覆盖度追踪**：确保每个功能需求（FR）都被任务覆盖
- **验收追踪**：从 FR 的验收标准自动生成验收项
- **验收门禁**：自动检查验收通过率，决定是否归档
- **进度可视化**：在 reqboard_status 中显示覆盖度和验收进度

### 工作流程

```
FR 文件（functional-requirements/*.md）
    ↓
[reqboard_decompose] 拆分任务
    ↓ 填充 task_coverage（任务覆盖哪些 FR）
    ↓ 检查覆盖度（是否所有 FR 都被覆盖）
    ↓
[reqboard_submit] 提交验收
    ↓ 填充 acceptance_tracking（从 FR 生成验收项）
    ↓
[reqboard_accept_sheet] 验收裁决
    ↓ 更新 acceptance_tracking（passed/failed）
    ↓ 检查验收门禁（通过率 >= 100% → 自动归档）
    ↓
[reqboard_status] 状态查询
    ↓ 显示 fr_coverage（覆盖度统计）
    ↓ 显示 fr_acceptance_progress（验收进度）
```

---

## 2. FR 文件格式规范

### 文件位置

FR 文件必须放在需求目录下的 `functional-requirements/` 子目录中：

```
docs/requirements/REQ-xxxxxx/
└── functional-requirements/
    ├── FR-1-user-auth.md
    ├── FR-2-data-export.md
    └── FR-3-notification.md
```

### 文件命名

- 格式：`FR-{编号}-{简短描述}.md`
- 编号：从 1 开始连续编号
- 示例：`FR-1-user-login.md`、`FR-2-password-reset.md`

### 内容格式

每个 FR 文件必须包含：

```markdown
# FR-1: 用户登录功能

## 功能描述
用户可以使用用户名和密码登录系统。

## 验收标准
- A1: 用户输入正确的用户名和密码，点击"登录"后进入主界面
- A2: 用户输入错误的密码，系统提示"用户名或密码错误"
- A3: 用户连续输入错误密码 3 次，账户被锁定 30 分钟
- A4: 用户可以选择"记住我"，下次自动登录

## 依赖关系
- 依赖 FR-2（用户注册）
```

**关键要点**：

1. **标题必须是 `# FR-{编号}: {标题}`**（一级标题，冒号后有空格）
2. **验收标准章节**：
   - 必须有 `## 验收标准` 或 `**验收标准**:` 标记
   - 每条验收标准以 `- A{序号}:` 开头（如 `- A1:`、`- A2:`）
   - A 序号从 1 开始连续编号
3. **依赖关系章节**（可选）：
   - 使用 `## 依赖关系` 或 `**依赖关系**:` 标记
   - 引用其他 FR 使用 `FR-{编号}` 格式

---

## 3. 如何使用 RTM

### 3.1 拆分任务时追踪覆盖度

在调用 `reqboard_decompose` 拆分任务时，系统会自动：

1. 扫描 `functional-requirements/` 目录下的所有 FR 文件
2. 根据任务的 `requirement_refs` 字段生成 `task_coverage`
3. 检查是否所有 FR 都被任务覆盖

**示例**：

```typescript
// 拆分计划中的任务
const tasks = [
  {
    key: 't1',
    title: '实现用户登录和注册',
    requirement_refs: ['FR-1', 'FR-2'], // 覆盖 FR-1 和 FR-2
    // ...
  },
  {
    key: 't2',
    title: '实现通知系统',
    requirement_refs: ['FR-3'], // 覆盖 FR-3
    // ...
  }
];

// reqboard_decompose 会返回：
{
  task_coverage: [
    {
      task_key: 't1',
      covers_frs: ['FR-1', 'FR-2'],
      covers_acceptance: ['FR-1-A1', 'FR-1-A2', 'FR-2-A1', ...]
    },
    {
      task_key: 't2',
      covers_frs: ['FR-3'],
      covers_acceptance: ['FR-3-A1', 'FR-3-A2', ...]
    }
  ],
  coverage_check: {
    total_frs: 3,
    covered_frs: 3,
    unreceived_clauses: [], // 空 = 全部覆盖
    coverage_rate: 100
  }
}
```

**未覆盖警告**：

如果有 FR 未被任何任务覆盖，`unreceived_clauses` 会列出：

```json
{
  "coverage_check": {
    "total_frs": 5,
    "covered_frs": 4,
    "unreceived_clauses": ["FR-5"],
    "coverage_rate": 80
  }
}
```

此时需要补充任务或更新任务的 `requirement_refs`。

### 3.2 提交验收时生成验收项

在调用 `reqboard_submit(kind='verification')` 提交验收时，系统会自动：

1. 从所有 FR 文件中提取验收标准
2. 生成 `acceptance_tracking`（每个验收标准一条）
3. 返回验收项总数

**示例**：

```typescript
// 3 个 FR，每个 4 条验收标准 = 12 条验收项
{
  acceptance_tracking_count: 12,
  is_rework: false // 首次验收
}
```

**返工续验**：

如果上一版验收有 failed 项，本次只生成这些项：

```typescript
{
  acceptance_tracking_count: 2, // 只重新验收 2 项
  is_rework: true // 续验标记
}
```

### 3.3 验收裁决时检查门禁

在调用 `reqboard_accept_sheet` 进行验收裁决时，系统会自动：

1. 更新 `acceptance_tracking` 的状态（passed/failed）
2. 检查验收门禁（通过率是否达标）
3. 判定是否应该自动归档

**门禁规则**：

- `gate_status = 'passed'`：通过率 = 100%，所有项都 passed
- `gate_status = 'blocked'`：有 failed 项，不能归档
- `gate_status = 'pending'`：有 pending 项，验收未完成

**示例**：

```typescript
// 第一次验收：10/12 通过
{
  gate_status: 'blocked',
  archived: false,
  passed: 10,
  failed: 2,
  pass_rate: 83
}

// 返工后第二次验收：12/12 通过
{
  gate_status: 'passed',
  archived: true, // 应该自动归档
  passed: 12,
  failed: 0,
  pass_rate: 100
}
```

### 3.4 查询状态时显示进度

在调用 `reqboard_status` 查询状态时，系统会自动显示：

1. `fr_coverage`：FR 覆盖度统计
2. `fr_acceptance_progress`：验收进度（仅验收阶段）

**示例**：

```typescript
{
  // FR 覆盖度
  fr_coverage: {
    total_frs: 3,
    covered_frs: 3,
    unreceived_clauses: [],
    coverage_rate: 100
  },
  
  // 验收进度（仅 accepting 阶段有）
  fr_acceptance_progress: {
    total: 12,
    passed: 12,
    failed: 0,
    pending: 0,
    pass_rate: 100,
    gate_status: 'passed'
  }
}
```

---

## 4. 如何读取 RTM 数据

### 4.1 读取 task_coverage

任务的 `task_coverage` 记录在需求的 decomposition 产物中：

```typescript
// 从需求对象读取
requirement.artifacts
  .filter(a => a.kind === 'decomposition')
  .map(a => a.metadata?.task_coverage)
```

### 4.2 读取 acceptance_tracking

验收追踪记录在需求的 `verification.sheet.rtmTracking` 中：

```typescript
// 从需求对象读取
requirement.verification?.sheet?.rtmTracking
// 返回 AcceptanceTracking[]
```

每条记录包含：

```typescript
{
  acceptance_id: 'FR-1-A1',
  fr_id: 'FR-1',
  description: '验收标准描述',
  verification: '如何验证',
  status: 'passed' | 'failed' | 'pending',
  evidence: '通过证据或失败原因',
  judged_at: 时间戳,
  judged_by: '裁决人',
  user_feedback: '用户反馈'
}
```

### 4.3 读取覆盖度和验收进度

直接调用 `reqboard_status` 即可获取：

```bash
# 查询当前需求的覆盖度和验收进度
reqboard_status
```

返回的 `fr_coverage` 和 `fr_acceptance_progress` 字段包含完整统计。

---

## 5. 故障排查

### 5.1 FR 文件解析失败

**症状**：`coverage_check.total_frs = 0`

**可能原因**：

1. FR 文件不在 `functional-requirements/` 目录下
2. FR 文件标题格式错误（不是 `# FR-{编号}: {标题}`）
3. 验收标准章节标记错误（不是 `## 验收标准` 或 `**验收标准**:`）

**解决方案**：

1. 检查文件位置：`docs/requirements/REQ-xxx/functional-requirements/`
2. 检查标题格式：必须是一级标题 `# FR-1: 标题`
3. 检查验收标准章节：必须有明确的章节标记

### 5.2 验收项数量不对

**症状**：`acceptance_tracking_count` 不等于预期

**可能原因**：

1. FR 文件中的验收标准格式错误（不是 `- A{序号}:` 开头）
2. 续验模式下只生成 failed 项

**解决方案**：

1. 检查每条验收标准是否以 `- A1:`、`- A2:` 开头
2. 确认是否为续验（`is_rework = true`）

### 5.3 覆盖度统计不准确

**症状**：`unreceived_clauses` 包含已覆盖的 FR

**可能原因**：

1. 任务的 `requirement_refs` 未正确填写
2. `requirement_refs` 中的 FR 编号与文件不匹配

**解决方案**：

1. 检查任务的 `requirement_refs` 字段
2. 确保 FR 编号一致（文件名、标题、`requirement_refs` 都要一致）

### 5.4 验收门禁未通过

**症状**：`gate_status = 'blocked'` 但认为应该通过

**可能原因**：

1. 有 failed 项未返工
2. 有 pending 项未裁决

**解决方案**：

1. 查看 `failed` 和 `pending` 数量
2. 对 failed 项进行返工后重新验收
3. 对 pending 项完成裁决

### 5.5 测试运行失败

**症状**：单元测试或 E2E 测试失败

**解决方案**：

```bash
# 运行 RTM 核心测试
npx vitest run packages/tools/reqboard/tests/rtm/

# 运行集成测试
npx vitest run packages/web/dsh-pmboard/tests/*-rtm-integration.test.ts

# 运行 E2E 测试
npx vitest run packages/tools/reqboard/tests/e2e/rtm-full-flow.test.ts
```

如果测试持续失败，检查：

1. FR 文件是否符合格式规范
2. 测试数据是否正确（任务的 `requirement_refs`、验收单状态等）
3. 临时目录是否正确清理（`afterEach` 中的 `rmSync`）

---

## 附录：完整示例

### 示例需求结构

```
docs/requirements/REQ-123456/
├── requirement.md
├── design/
│   └── architecture.md
├── functional-requirements/
│   ├── FR-1-user-login.md
│   ├── FR-2-user-register.md
│   └── FR-3-notification.md
└── tasks/
    ├── t-001.md
    ├── t-002.md
    └── t-003.md
```

### 示例 FR 文件

**FR-1-user-login.md**：

```markdown
# FR-1: 用户登录

**验收标准**:
- A1: 输入正确凭据后成功登录
- A2: 输入错误密码后提示错误
- A3: 连续失败 3 次后锁定账户
```

### 示例任务

```typescript
{
  id: 't-001',
  title: '实现用户认证模块',
  requirement_refs: ['FR-1', 'FR-2'], // 覆盖 FR-1 和 FR-2
  // ...
}
```

### 完整流程示例

```typescript
// 1. 拆分任务
const decomposeResult = await reqboard_decompose({
  requirement_id: 'REQ-123456',
  tasks: [...]
});
// 返回 task_coverage 和 coverage_check

// 2. 提交验收
const submitResult = await reqboard_submit({
  kind: 'verification',
  requirement_id: 'REQ-123456',
  summary: '开发完成，提交验收',
  evidence: ['所有单元测试通过', '集成测试通过']
});
// 返回 acceptance_tracking_count

// 3. 验收裁决
const acceptResult = await reqboard_accept_sheet({
  requirement_id: 'REQ-123456'
});
// 返回 gate_status 和 archived

// 4. 查询状态
const statusResult = await reqboard_status();
// 返回 fr_coverage 和 fr_acceptance_progress
```

---

**文档版本**：1.0  
**最后更新**：2026-09-25  
**相关需求**：REQ-260925172227-2d61
