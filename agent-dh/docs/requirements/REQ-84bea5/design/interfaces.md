---
requirement: REQ-84bea5
title: 接口设计
created: 2026-09-21
requirement_refs: [FR-1, FR-2, FR-3]
---

# 修复「批准计划→自动开跑」断链 - 接口设计

> serves: FR-1, FR-2, FR-3

## 1. 内部接口变更（serves: FR-1, FR-2, FR-3）

### 1.1 assertClauseCoverageGate（serves: FR-1）

**文件**：`src/application/internal/content-gate-wiring.ts`

**函数签名**（无变更）：
```typescript
function assertClauseCoverageGate(
  requirementDir: string,
  tasks: NormalizedTask[],
  clauses: string[]
): void;
```

**实现变更**：
```typescript
// 修复前（只读任务对象）
const taskRefs = tasks.flatMap(t => t.requirement_refs || []);

// 修复后（双源合并）
import { taskRefsFromDecomposition } from './content-trace';

const taskRefs = new Set([
  ...tasks.flatMap(t => t.requirement_refs || []),
  ...taskRefsFromDecomposition(requirementDir)
]);
```

**行为变更**：
- **输入**：无变更
- **输出**：无变更（仍为 void 或抛异常）
- **副作用**：新增读取 `requirementDir/decomposition.md` 的 RTM 表
- **异常**：
  - 双源皆无 refs → 抛 `requirement_uncovered`（行为保持）
  - RTM 解析失败 → 返回空数组，门禁仍按"未覆盖"拒绝（新增兜底）

**依赖变更**：
- 新增依赖：`taskRefsFromDecomposition` 函数（已存在于 `content-trace.ts`）
- 无新增外部依赖

### 1.2 AskConfirm catch 路径（serves: FR-2）

**文件**：`src/application/use-cases/AskConfirm.ts`

**位置**：自动拆分/开跑的 catch 块（约 L295-299）

**接口签名**（无变更）：
```typescript
async execute(params: {
  requirement_id: string;
  target: 'plan' | 'artifact';
  // ...
}): Promise<AskConfirmResult>;
```

**实现变更**：
```typescript
// 修复前（只返回 note）
catch (error) {
  return {
    success: true,
    note: `自动开跑失败：${error.message}`
  };
}

// 修复后（评论 + 告警 + 标记）
catch (error) {
  // 1. 写系统评论
  await this.commentRepo.create({
    requirement_id: req.id,
    author: 'system',
    content: `自动开跑失败：${error.message}\n\n恢复路径：修复后手动调用 reqboard_decompose + reqboard_task_run`
  });
  
  // 2. 发高优告警
  await deps.alert({
    level: 'high',
    title: '自动链开跑失败',
    requirement_id: req.id,
    detail: error.message
  });
  
  // 3. 标记 pausedReason
  await this.reqRepo.update(req.id, {
    advance: { ...req.advance, pausedReason: error.message }
  });
  
  // 4. 保留原返回（兼容）
  return {
    success: true,
    note: `自动开跑失败：${error.message}。已记录系统评论与告警。`
  };
}
```

**返回值变更**：
- `note` 字段：补充"已记录系统评论与告警"说明
- 其他字段：无变更

**副作用变更**：
- 新增：写系统评论（`commentRepo.create`）
- 新增：发送告警（`deps.alert`）
- 新增：更新需求台账（`reqRepo.update`）

**依赖注入**：
- 需注入：`commentRepo`（既有依赖）
- 需注入：`deps.alert`（需确认 FailureAlert 接口定义）

### 1.3 checkDocCompleteness（serves: FR-3）

**文件**：`src/domain/workflow/DocCompleteness.ts`

**常量变更**：
```typescript
// 修复前（9 类文档）
const VERIFICATION_DOC_CLASSES = [
  { kind: 'requirement', label: 'requirement.md（需求文档）', ... },
  { kind: 'plan', label: 'plan.md（拆分计划）', ... },  // 删除此行
  // ... 其他 7 类
  { kind: 'decomposition', label: 'decomposition.md（拆分计划）', ... },
];

// 修复后（8 类文档）
const VERIFICATION_DOC_CLASSES = [
  { kind: 'requirement', label: 'requirement.md（需求文档）', ... },
  // plan.md 已删除
  // ... 其他 7 类
  { kind: 'decomposition', label: 'decomposition.md（拆分计划）', ... },
];
```

**函数签名**（无变更）：
```typescript
function checkDocCompleteness(
  docs: DocArtifact[]
): { passed: boolean; missing: string[] };
```

**行为变更**：
- **输入**：无变更
- **输出**：`missing` 数组不再包含 "plan.md（拆分计划）"
- **语义**：带 decomposition.md 但无 plan.md 的需求可通过验收

## 2. 工具接口（无变更）（serves: FR-1, FR-2, FR-3）

本次修复不涉及对外工具接口变更：
- `reqboard_ask_confirm`：签名与行为保持，返回 note 新增说明文字（向后兼容）
- `reqboard_decompose`：无变更
- `reqboard_task_run`：无变更
- `reqboard_submit`：无变更（plan.tasks schema 不扩展）

## 3. API 依赖（serves: FR-1, FR-2）

### 3.1 新增依赖（serves: FR-1）

```typescript
// content-gate-wiring.ts
import { taskRefsFromDecomposition } from './content-trace';
```

### 3.2 现有依赖（serves: FR-2）

```typescript
// AskConfirm.ts
constructor(
  private commentRepo: CommentRepository,   // 既有
  private reqRepo: RequirementRepository,   // 既有
  deps: { alert: FailureAlert }             // 需确认接口定义
) {}
```

## 4. 错误处理（serves: FR-1, FR-2）

### 4.1 assertClauseCoverageGate 异常（serves: FR-1）

| 场景 | 异常类型 | 错误信息 |
|-----|---------|---------|
| 双源皆无 refs | `requirement_uncovered` | "FR-1, FR-2 既没有被任何任务卡接收、也没有标「本轮不做」" |
| RTM 解析失败 | 无异常 | 返回空数组，门禁按"未覆盖"拒绝 |

### 4.2 AskConfirm catch 处理（serves: FR-2）

| 异常来源 | 处理方式 |
|---------|---------|
| `assertClauseCoverageGate` | 捕获 → 评论 + 告警 + 标记 → 返回 note |
| `reqboard_decompose` | 捕获 → 评论 + 告警 + 标记 → 返回 note |
| `reqboard_task_run` | 捕获 → 评论 + 告警 + 标记 → 返回 note |

## 5. 向后兼容性（serves: FR-1, FR-2, FR-3）

### 5.1 接口兼容（serves: FR-1, FR-2, FR-3）

- ✅ `assertClauseCoverageGate`：签名不变，行为扩展（双源合并）
- ✅ `AskConfirm`：返回值扩展 note 文字，不影响调用方
- ✅ `checkDocCompleteness`：签名不变，行为放宽（少一项必交文档）

### 5.2 数据兼容（serves: FR-2, FR-3）

- ✅ 既有需求：`advance.pausedReason` 可选字段，不影响既有数据
- ✅ 存量 plan.md：保留作档案，不强制删除

### 5.3 工具兼容（serves: FR-1, FR-2, FR-3）

- ✅ 工具调用方：无变更
- ✅ 看板前端：需适配 `pausedReason` 渲染（新功能，不影响既有展示）

## 6. 接口测试清单（serves: FR-4）

### 6.1 assertClauseCoverageGate（serves: FR-4）

```typescript
// 测试用例 1：RTM 覆盖（双源合一）
const req = { requirement_md: 'FR-1', decomposition_md: 'T1 → FR-1' };
assertClauseCoverageGate(reqDir, [{ key: 'T1' }], ['FR-1']); // 不抛异常

// 测试用例 2：双源皆空
const req = { requirement_md: 'FR-1', decomposition_md: 'T1 → -' };
assertClauseCoverageGate(reqDir, [{ key: 'T1' }], ['FR-1']); // 抛 requirement_uncovered
```

### 6.2 AskConfirm（serves: FR-4）

```typescript
// 测试用例 1：自动开跑成功
await askConfirm({ target: 'plan', requirement_id: 'REQ-xxx' });
// 断言：advance.autoRun === true，无 pausedReason

// 测试用例 2：自动开跑失败
await askConfirm({ target: 'plan', requirement_id: 'REQ-yyy' });
// 断言：advance.pausedReason 存在，有系统评论，alert 被调用
```

### 6.3 checkDocCompleteness（serves: FR-4）

```typescript
// 测试用例：无 plan.md 但有 decomposition.md
const docs = [
  { kind: 'requirement' },
  { kind: 'decomposition' },
  // ... 其他 6 类
];
const result = checkDocCompleteness(docs);
expect(result.passed).toBe(true); // 通过
```