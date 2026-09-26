# FR-1: reqboard_decompose 支持从 FR 文件读取验收标准

## 1. 功能描述

### What（做什么）
修改 `reqboard_decompose` 工具，支持从 `functional-requirements/FR-*.md` 文件读取验收标准，在拆分时填充 `task_coverage`，校验所有 FR 被任务覆盖。

### Why（为什么）
- **解决问题 1**：当前任务的 `requirement_refs` 为空，无法追踪任务覆盖了哪些功能需求
- **解决问题 2**：人工手写 RTM 表容易遗漏，工具自动校验更可靠
- **支持新结构**：功能点独立文件后，需要工具能读取这些文件

### Scope（范围）
- ✅ 读取 FR 文件：扫描 `functional-requirements/` 目录，解析 FR-*.md
- ✅ 填充 task_coverage：任务拆分时，记录每个任务接收了哪些 FR
- ✅ 校验覆盖度：检查所有 FR 是否被至少一个任务接收
- ✅ 错误提示：未覆盖的 FR 标记为 `unreceived_clauses`（红色）
- ❌ 不做：不验证 FR 文件内容的合理性（由人工审核）

## 2. 功能规格

### 2.1 输入
`reqboard_decompose` 增强参数：
```typescript
{
  requirement_id: string,
  tasks: [{
    key: string,
    title: string,
    requirement_refs: string[],  // 新增：接收的 FR 列表，如 ['FR-1', 'FR-2']
    // ...其他字段
  }]
}
```

### 2.2 输出
```typescript
{
  success: true,
  created: [{key: 't1', id: 't-xxx'}],
  task_coverage: [                      // 新增：任务覆盖追踪
    {
      task_id: 't-xxx',
      task_key: 't1',
      covers_frs: ['FR-1'],
      covers_acceptance: ['FR-1-A1', 'FR-1-A2', 'FR-1-A3', 'FR-1-A4']
    }
  ],
  unreceived_clauses: []                // 未被覆盖的 FR 列表
}
```

### 2.3 行为

1. **扫描 FR 文件**：
   - 读取 `docs/requirements/<REQ>/functional-requirements/` 目录
   - 找到所有 `FR-*.md` 文件
   - 解析文件名提取 FR 编号（如 FR-1）

2. **填充 task_coverage**：
   - 遍历 `tasks` 数组
   - 读取每个任务的 `requirement_refs`
   - 为每个任务创建 `task_coverage` 记录
   - 从对应 FR 文件的"验收标准"章节提取 A1-A4

3. **校验覆盖度**：
   - 收集所有 FR 编号（从文件名）
   - 收集所有任务接收的 FR（从 `requirement_refs`）
   - 计算差集：未被任何任务接收的 FR
   - 返回 `unreceived_clauses`

4. **错误处理**：
   - `requirement_refs` 引用不存在的 FR → 警告，但允许继续
   - 有 `unreceived_clauses` → 返回警告，不阻止拆分（由人工决定是否补充任务）

### 2.4 约束
- FR 文件必须存在于 `functional-requirements/` 目录
- FR 文件名格式：`FR-N-description.md`
- 任务的 `requirement_refs` 可以为空（表示该任务不直接覆盖 FR，如基础设施任务）

## 3. 验收标准

### 3.1 功能验收
- **A1**: 成功读取 FR 文件列表  
  验证：调用 `reqboard_decompose`，返回的 `task_coverage` 包含从 FR 文件提取的验收标准

- **A2**: 填充 task_coverage  
  验证：任务 `requirement_refs=['FR-1']`，返回 `task_coverage[0].covers_frs=['FR-1']` 且 `covers_acceptance` 包含 FR-1-A1 至 FR-1-A4

- **A3**: 校验覆盖度  
  验证：有 FR-3 文件但无任务接收，返回 `unreceived_clauses=['FR-3']`

- **A4**: 引用不存在的 FR 时给出警告  
  验证：任务 `requirement_refs=['FR-999']`，返回警告但不阻止拆分

### 3.2 质量验收
- **Q1**: 性能：扫描 10 个 FR 文件 < 1s
- **Q2**: 兼容性：旧需求（无 FR 文件）不报错，返回空 `task_coverage`

### 3.3 文档验收
- **D1**: FR 文件格式文档化（README 或注释）

## 4. 依赖关系

### 4.1 前置依赖
- FR 文件必须已创建（`functional-requirements/FR-*.md`）

### 4.2 后续依赖
- **FR-2**: `reqboard_submit` 使用 `task_coverage` 生成验收单
- **FR-5**: `reqboard_status` 显示覆盖度

## 5. 实施建议

### 5.1 技术方案
**修改位置**：`packages/web/dsh-pmboard/src/reqboard/decompose.ts`

**核心逻辑**：
```typescript
// 1. 扫描 FR 文件
const frFiles = scanFRFiles(requirementDir);
const allFRs = frFiles.map(f => extractFRNumber(f)); // ['FR-1', 'FR-2', ...]

// 2. 填充 task_coverage
const taskCoverage = [];
for (const task of tasks) {
  const coversFRs = task.requirement_refs || [];
  const coversAcceptance = [];
  
  for (const fr of coversFRs) {
    const frFile = frFiles.find(f => extractFRNumber(f) === fr);
    if (frFile) {
      const acceptance = extractAcceptanceFromFile(frFile); // ['FR-1-A1', ...]
      coversAcceptance.push(...acceptance);
    }
  }
  
  taskCoverage.push({
    task_id: task.id,
    task_key: task.key,
    covers_frs: coversFRs,
    covers_acceptance: coversAcceptance
  });
}

// 3. 校验覆盖度
const receivedFRs = new Set(taskCoverage.flatMap(t => t.covers_frs));
const unreceivedClauses = allFRs.filter(fr => !receivedFRs.has(fr));

return { success: true, taskCoverage, unreceivedClauses };
```

### 5.2 拆分建议
- **Task 1**: 实现 FR 文件扫描和解析
- **Task 2**: 实现 task_coverage 填充逻辑
- **Task 3**: 实现覆盖度校验
- **Task 4**: 集成到 reqboard_decompose 并测试

### 5.3 测试要点
- 正常流程（有 FR 文件、任务正确引用）
- 无 FR 文件（旧需求兼容）
- 部分 FR 未覆盖
- 引用不存在的 FR
- 性能测试（10+ FR 文件）

## 6. 变更历史

| 版本 | 日期 | 变更内容 | 作者 |
|-----|------|---------|------|
| v1.0 | 2026-09-25 | 初始版本 | Agent |

## 7. 接收状态

> 本节由系统自动维护

- 待分配任务

---

**文件路径**: `functional-requirements/FR-1-decompose-fr-support.md`  
**功能点编号**: FR-1  
**所属需求**: REQ-260925172227-2d61
