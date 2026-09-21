---
requirement: REQ-84bea5
title: 测试用例设计
created: 2026-09-21
requirement_refs: [FR-4]
---

# 修复「批准计划→自动开跑」断链 - 测试用例

> serves: FR-4

## 1. 测试策略（serves: FR-4）

### 1.1 测试目标（serves: FR-4）

1. **断链复现**：修复前测试必红（证明问题存在）
2. **修复验证**：修复后测试变绿（证明问题解决）
3. **回归保护**：全量测试保持绿灯（不引入新问题）

### 1.2 测试层级（serves: FR-4）

- **单元测试**：`assertClauseCoverageGate`、`checkDocCompleteness` 函数级测试
- **集成测试**：`AskConfirm` 端到端流程测试
- **回归测试**：`npx vitest run` 全量测试套件

## 2. 核心测试用例（serves: FR-4）

### 2.1 断链复现与修复验证（serves: FR-1, FR-4）

**文件**：`tests/auto-chain-approval.test.ts`

**用例 TC-1.1：批准计划后自动开跑（RTM 覆盖）**

```typescript
test('批准计划后自动开跑（RTM 覆盖）', async () => {
  // 准备：种子需求（带 FR + RTM，plan 无 refs）
  const reqDir = await createSeedRequirement({
    'requirement.md': 'FR-1: 功能点一\nFR-2: 功能点二',
    'decomposition.md': '| Task | Title | Requirements |\n|------|-------|--------------|\n| T1 | 任务一 | FR-1 |\n| T2 | 任务二 | FR-2 |',
    'plan': { 
      path: 'decomposition.md',
      tasks: [
        { key: 'T1', title: '任务一' },  // 无 requirement_refs
        { key: 'T2', title: '任务二' }
      ]
    }
  });
  
  // 执行：批准计划
  const result = await tools.reqboard_ask_confirm({
    requirement_id: reqDir.id,
    target: 'plan'
  });
  
  // 断言 1：批准成功
  expect(result.success).toBe(true);
  expect(result.confirmed).toBe(true);
  
  // 断言 2：自动开跑成功
  const req = await getRequirement(reqDir.id);
  expect(req.advance?.autoRun).toBe(true);
  expect(req.advance?.pausedReason).toBeUndefined();
  
  // 断言 3：状态推进到 implementing
  expect(req.status).toBe('implementing');
  
  // 断言 4：任务已落库
  const tasks = await getTasks(reqDir.id);
  expect(tasks.length).toBeGreaterThan(0);
  
  // 断言 5：子卡链已开跑
  const runningTasks = tasks.filter(t => t.status === 'in_progress');
  expect(runningTasks.length).toBeGreaterThan(0);
});
```

**预期结果**：
- 修复前：❌ 测试失败（`requirement_uncovered` 异常，autoRun 未置位）
- 修复后：✅ 测试通过（自动开跑成功）

---

### 2.2 失败响亮化验证（serves: FR-2, FR-4）

**用例 TC-2.1：双源皆无 refs 时批准被拒**

```typescript
test('双源无 refs 时批准被拒且响亮失败', async () => {
  // 准备：种子需求（双源皆无 refs）
  const reqDir = await createSeedRequirement({
    'requirement.md': 'FR-1: 功能点一',
    'decomposition.md': '| Task | Title | Requirements |\n|------|-------|--------------|\n| T1 | 任务一 | - |',  // 无覆盖
    'plan': { 
      tasks: [{ key: 'T1', title: '任务一' }]  // 无 requirement_refs
    }
  });
  
  // 执行：批准计划
  const result = await tools.reqboard_ask_confirm({
    requirement_id: reqDir.id,
    target: 'plan'
  });
  
  // 断言 1：批准失败（返回 success 但有 note 说明失败）
  expect(result.note).toContain('自动开跑失败');
  expect(result.note).toContain('requirement_uncovered');
  
  // 断言 2：系统评论已写入
  const comments = await getComments(reqDir.id);
  const systemComment = comments.find(c => 
    c.author === 'system' && c.content.includes('自动开跑失败')
  );
  expect(systemComment).toBeDefined();
  expect(systemComment.content).toContain('恢复路径');
  
  // 断言 3：告警已发送
  expect(mockAlert).toHaveBeenCalledWith({
    level: 'high',
    title: '自动链开跑失败',
    requirement_id: reqDir.id,
    detail: expect.stringContaining('requirement_uncovered')
  });
  
  // 断言 4：pausedReason 已标记
  const req = await getRequirement(reqDir.id);
  expect(req.advance?.pausedReason).toContain('requirement_uncovered');
  expect(req.advance?.autoRun).toBeUndefined();
  
  // 断言 5：状态未推进（仍在 decomposing）
  expect(req.status).toBe('decomposing');
});
```

**预期结果**：
- ✅ 批准被拒（覆盖门禁生效）
- ✅ 系统评论已写入
- ✅ 告警已发送
- ✅ pausedReason 已标记

---

### 2.3 验收文档门禁验证（serves: FR-3, FR-4）

**用例 TC-3.1：无 plan.md 但有 decomposition.md 时验收通过**

```typescript
test('无 plan.md 但有 decomposition.md 时验收通过', () => {
  // 准备：8 类文档（无 plan.md，有 decomposition.md）
  const docs = [
    { kind: 'requirement', path: 'requirement.md' },
    // 无 plan.md
    { kind: 'verification', path: 'verification.md' },
    { kind: 'retro', path: 'retro.md' },
    { kind: 'notes', path: 'notes.md' },
    { kind: 'design', path: 'design/architecture.md' },
    { kind: 'design', path: 'design/data-model.md' },
    { kind: 'decomposition', path: 'decomposition.md' },
    { kind: 'task_detail', path: 'tasks/T1.md' }
  ];
  
  // 执行：检查文档完整性
  const result = checkDocCompleteness(docs);
  
  // 断言：通过验收
  expect(result.passed).toBe(true);
  expect(result.missing).not.toContain('plan.md');
});
```

**预期结果**：
- ✅ 验收通过（plan.md 不再是必交文档）

**用例 TC-3.2：缺 decomposition.md 时验收不通过**

```typescript
test('缺 decomposition.md 时验收不通过', () => {
  const docs = [
    { kind: 'requirement', path: 'requirement.md' },
    // 无 decomposition.md
    // ... 其他 6 类
  ];
  
  const result = checkDocCompleteness(docs);
  
  expect(result.passed).toBe(false);
  expect(result.missing).toContain('decomposition.md');
});
```

---

## 3. 边界测试用例（serves: FR-4）

### 3.1 RTM 解析失败（serves: FR-1, FR-4）

**用例 TC-B.1：decomposition.md 不存在**

```typescript
test('decomposition.md 不存在时返回空数组', () => {
  const reqDir = '/tmp/req-no-decomposition';
  // 只有 requirement.md，无 decomposition.md
  
  const refs = taskRefsFromDecomposition(reqDir);
  
  expect(refs).toEqual([]);  // 不把"没记录"误判为"已覆盖"
});
```

**用例 TC-B.2：RTM 表头不符**

```typescript
test('RTM 表头不符时返回空数组', () => {
  const reqDir = await createSeedRequirement({
    'decomposition.md': '| Task | Title |\n|------|-------|\n| T1 | 任务一 |'  // 无 Requirements 列
  });
  
  const refs = taskRefsFromDecomposition(reqDir.path);
  
  expect(refs).toEqual([]);
});
```

### 3.2 存量需求兼容（serves: FR-3, FR-4）

**用例 TC-B.3：既有 plan.md 的需求不受影响**

```typescript
test('既有 plan.md 的需求仍可通过验收', () => {
  const docs = [
    { kind: 'requirement', path: 'requirement.md' },
    { kind: 'plan', path: 'plan.md' },  // 存量文件保留
    { kind: 'decomposition', path: 'decomposition.md' },
    // ... 其他 6 类
  ];
  
  const result = checkDocCompleteness(docs);
  
  expect(result.passed).toBe(true);  // 多出的文档无害
});
```

---

## 4. 测试数据准备（serves: FR-4）

### 4.1 种子需求工厂（serves: FR-4）

```typescript
async function createSeedRequirement(files: {
  'requirement.md'?: string;
  'decomposition.md'?: string;
  'plan'?: { path: string; tasks: any[] };
}): Promise<{ id: string; path: string }> {
  const tempDir = await fs.mkdtemp('/tmp/req-test-');
  
  // 创建 requirement.md
  if (files['requirement.md']) {
    await fs.writeFile(
      path.join(tempDir, 'requirement.md'),
      files['requirement.md']
    );
  }
  
  // 创建 decomposition.md
  if (files['decomposition.md']) {
    await fs.writeFile(
      path.join(tempDir, 'decomposition.md'),
      files['decomposition.md']
    );
  }
  
  // 创建需求记录
  const req = await reqRepo.create({
    title: 'Test Requirement',
    category: 'feature',
    status: 'decomposing',
    plan: files.plan
  });
  
  return { id: req.id, path: tempDir };
}
```

### 4.2 Mock 依赖（serves: FR-4）

```typescript
// Mock alert
const mockAlert = jest.fn();
const deps = { alert: mockAlert };

// Mock commentRepo
const mockCommentRepo = {
  create: jest.fn(),
  find: jest.fn()
};
```

---

## 5. 测试执行计划（serves: FR-4）

### 5.1 单元测试（serves: FR-4）

```bash
# 1. 覆盖门禁测试
npx vitest run tests/content-gate-wiring.test.ts

# 2. 文档完整性测试
npx vitest run tests/doc-completeness.test.ts
```

### 5.2 集成测试（serves: FR-4）

```bash
# 自动链批准测试（核心）
npx vitest run tests/auto-chain-approval.test.ts
```

### 5.3 回归测试（serves: FR-4）

```bash
# 全量测试（dsh-pmboard 包）
npx vitest run
```

---

## 6. 验收标准（serves: FR-4）

### 6.1 先红后绿证明（serves: FR-4）

1. **修复前运行 TC-1.1**：
   - 预期：❌ 测试失败
   - 错误信息：`requirement_uncovered: FR-1, FR-2`
   - 截图保存：`tests/evidence/before-fix.png`

2. **应用 T2（覆盖门禁双源合并）后运行 TC-1.1**：
   - 预期：✅ 测试通过
   - 截图保存：`tests/evidence/after-fix.png`

### 6.2 测试覆盖率（serves: FR-4）

- ✅ FR-1：TC-1.1（断链复现与修复）
- ✅ FR-2：TC-2.1（失败响亮化）
- ✅ FR-3：TC-3.1、TC-3.2（验收文档门禁）
- ✅ FR-4：全量回归测试

### 6.3 通过条件（serves: FR-4）

- [ ] TC-1.1 先红后绿（断链复现证明）
- [ ] TC-2.1 通过（失败响亮化验证）
- [ ] TC-3.1、TC-3.2 通过（验收门禁验证）
- [ ] 边界用例 TC-B.1、TC-B.2、TC-B.3 通过
- [ ] `npx vitest run` 全绿（无回归问题）

---

## 7. 测试环境要求（serves: FR-4）

### 7.1 依赖（serves: FR-4）

- Node.js >= 18
- Vitest >= 1.0
- @pi-investment/dsh-pmboard 包完整依赖

### 7.2 Mock 配置（serves: FR-4）

- `deps.alert`：需 mock 或实现 FailureAlert 占位
- 文件系统：使用 `fs.mkdtemp` 创建临时目录
- 数据库：使用内存 SQLite 或 mock repository

### 7.3 清理（serves: FR-4）

```typescript
afterEach(async () => {
  // 清理临时文件
  await fs.rm(tempDir, { recursive: true, force: true });
  
  // 清理测试需求
  await reqRepo.delete(testReqId);
  
  // 重置 mock
  mockAlert.mockClear();
  mockCommentRepo.create.mockClear();
});
```