---
requirement: REQ-84bea5
title: 修复「批准计划→自动开跑」断链设计
status: draft
created: 2026-09-21
requirement_refs: [FR-1, FR-2, FR-3, FR-4]
---

# 修复「批准计划→自动开跑」断链设计

> serves: FR-1, FR-2, FR-3, FR-4

## 1. 目标（serves: FR-1, FR-2, FR-3, FR-4）

**可证伪目标**：让带 requirement.md（含 FR 编号）+ decomposition.md（含 RTM 表）的需求在批准拆分计划后能自动落卡并开跑；开跑失败时在看板留可见标记并发出告警；验收提交时不再因缺 plan.md 被拒。

**验证方式**：
- `npx vitest run tests/auto-chain-approval.test.ts` 新增用例先红后绿（断链复现→修复后通过）
- 开跑失败的需求在看板显示「自动链失败」标记，台账有系统评论与 alert 调用记录
- 带 decomposition.md 但无 plan.md 的需求能通过 `checkDocCompleteness` 验收门禁
- 全量测试 `npx vitest run` 保持绿灯

## 2. 设计（serves: FR-1, FR-2, FR-3, FR-4）

### 2.1 覆盖门禁双源合并（serves: FR-1）

**改动文件**：
- `src/application/internal/content-gate-wiring.ts`：`assertClauseCoverageGate` 函数

**接口变更**：
```typescript
// 现状（只读任务对象）
const taskRefs = tasks.flatMap(t => t.requirement_refs || []);

// 修复后（双源合并：任务对象 ∪ decomposition.md RTM）
const taskRefs = new Set([
  ...tasks.flatMap(t => t.requirement_refs || []),
  ...taskRefsFromDecomposition(requirementDir)  // 已有函数，在 content-trace.ts
]);
```

**数据契约**：
- 输入：`requirementDir: string`（需求目录路径，如 `docs/requirements/REQ-xxxxx`）
- 输出：`taskRefs: Set<string>`（去重后的全部接收声明，如 `["FR-1", "FR-2"]`）
- RTM 解析不到时（表缺失/表头不符）返回空数组，不把"没记录"当"已覆盖"

**关键逻辑**：
1. 从任务对象读 `requirement_refs`（旧路径，保持向后兼容）
2. 调用 `taskRefsFromDecomposition(requirementDir)` 读 RTM 表（新增）
3. 两者取并集（Set 去重）
4. 与需求条款比对，未被接收的条款仍触发 `requirement_uncovered` 拒绝

**回退路径**：修改只在覆盖门禁层（content-gate-wiring.ts），不改数据写入链；回滚即恢复原"仅读对象"逻辑。

---

### 2.2 开跑失败响亮化（serves: FR-2）

**改动文件**：
- `src/application/use-cases/AskConfirm.ts`：`catch` 路径增强（约 L295-299）
- `src/domain/requirement/RequirementRecord.ts`：台账增加 `advance.pausedReason` 字段（可选）

**接口变更**：
```typescript
// AskConfirm.ts catch 路径（现状：只写返回 note）
catch (err) {
  return { success: false, note: `自动拆分/开跑失败：${err.message}` };
}

// 修复后：评论 + 告警 + 台账标记
catch (err) {
  const reason = `自动开跑失败：${err.message}`;
  
  // 1. 写系统评论（已有机制）
  await deps.comments.addSystemComment(req.id, {
    content: `⚠️ **自动链启动失败**\n\n原因：${err.message}\n\n**恢复路径**：修复后手动执行：\`reqboard_decompose(requirement_id: "${req.id}")\`，然后 \`reqboard_task_run(task_id: "<父卡id>")\``,
    level: 'error'
  });
  
  // 2. 发送告警（复用 deps.alert）
  await deps.alert({
    level: 'high',
    title: '需求自动链启动失败',
    body: `需求 ${req.id}《${req.title}》批准计划后自动开跑失败：${err.message}`,
    requirement_id: req.id
  });
  
  // 3. 台账留标记（使需求在看板可区分"手动"与"失败"）
  await deps.repo.updateRequirement(req.id, {
    'advance.pausedReason': reason
  });
  
  return { 
    success: false, 
    advanced: false,
    note: `${reason}（已记录评论与告警）` 
  };
}
```

**数据契约**：
- `RequirementRecord.advance.pausedReason?: string`（可选，存在即表示自动链未跑起来）
- 系统评论格式：`{ content: string, level: 'error' | 'warning' | 'info' }`
- 告警参数：`{ level: 'high', title: string, body: string, requirement_id: string }`

**看板呈现**（实施阶段设计，本设计只定契约）：
- `advance.pausedReason` 存在时显示「⚠️ 自动链失败」徽标
- 控制面增加「重新开跑」按钮（调用 `reqboard_task_run`）

**回退路径**：台账字段可选，不影响旧数据；回滚后失败再次静默，但历史评论与告警记录保留。

---

### 2.3 验收文档清单移除 plan.md（serves: FR-3）

**改动文件**：
- `src/domain/workflow/DocCompleteness.ts`：`VERIFICATION_DOC_CLASSES` 常量
- `src/domain/requirement/RequirementStatus.ts`：阶段注释（L27）
- `docs/requirements/_template/`：模板文件（删除 plan.md 引用）

**数据契约**：
```typescript
// 现状（DocCompleteness.ts:37）
const VERIFICATION_DOC_CLASSES = [
  { kind: 'requirement', title: 'requirement.md（需求文档）' },
  { kind: 'plan', title: 'plan.md（拆分计划）' },  // ← 删除这一行
  // ... 其余 8 类保持
];

// 修复后（只删除第 2 类，decomposition.md 保持必交）
const VERIFICATION_DOC_CLASSES = [
  { kind: 'requirement', title: 'requirement.md（需求文档）' },
  // plan.md 已删除
  { kind: 'decomposition', title: 'decomposition.md（拆分计划）' },
  // ... 其余 7 类
];
```

**影响范围**：
- 新需求：验收时不再要求 plan.md
- 存量需求：已有 plan.md 的不受影响（多出的文件无害，门禁只检查"必交缺失"，不检查"多交"）
- `req.plan` 记录保持（批准弹框与落卡仍消费其 path/summary/tasks），本 FR 只移除"必交"约束

**迁移策略**：无需数据回填。存量 34 个 plan.md 文件保留作档案（不删不动）。

**回退路径**：重新加回第 2 类即可；已交 decomposition.md 的需求不受影响。

---

### 2.4 回归测试增强（serves: FR-4）

**新增测试文件**：
`tests/auto-chain-approval-fix.test.ts`（复制现有 `auto-chain-approval.test.ts` 并增强）

**测试用例**：
```typescript
describe('REQ-84bea5: 断链修复', () => {
  it('FR-1: 带 RTM 的需求批准后自动落卡', async () => {
    // 种子需求：requirement.md 含 FR-1~FR-3 + decomposition.md 含 RTM
    const req = await seedRequirement({
      hasRequirementDoc: true,  // ← 修复前测试缺这个，门禁短路
      requirementClauses: ['FR-1', 'FR-2', 'FR-3'],
      plan: { 
        tasks: [
          { key: 't1', title: '实现 XX', implementation: '...', acceptance: '...' }
          // ← plan.tasks 对象无 requirement_refs（这是根因）
        ]
      },
      decompositionDoc: {
        rtm: [
          { clause: 'FR-1', tasks: ['t1'] },
          { clause: 'FR-2', tasks: ['t1'] },
          { clause: 'FR-3', tasks: ['t1'] }
        ]
      }
    });
    
    // 批准计划（修复前：requirement_uncovered 拒绝；修复后：通过）
    const result = await askConfirm({ requirement_id: req.id, target: 'plan' });
    
    expect(result.success).toBe(true);
    expect(result.advanced).toBe(true);  // 自动推进到 implementing
    
    // 验证自动链真的跑起来了
    const updated = await getRequirement(req.id);
    expect(updated.status).toBe('implementing');
    expect(updated.advance?.autoRun).toBe(true);
    
    // 验证子卡已落库
    const tasks = await listTasks(req.id);
    expect(tasks.length).toBeGreaterThan(1);  // 父卡 + 子卡
  });
  
  it('FR-2: 开跑失败时留评论+告警+标记', async () => {
    // 种子需求：双源都无 refs（必然触发 requirement_uncovered）
    const req = await seedRequirement({
      hasRequirementDoc: true,
      requirementClauses: ['FR-1'],
      plan: { tasks: [{ key: 't1', title: 'XX' }] },  // 无 refs
      decompositionDoc: { rtm: [] }  // 无 RTM
    });
    
    const result = await askConfirm({ requirement_id: req.id, target: 'plan' });
    
    // 验证拒绝
    expect(result.success).toBe(false);
    expect(result.note).toContain('requirement_uncovered');
    
    // 验证评论已写入
    const comments = await listComments(req.id);
    const errorComment = comments.find(c => c.level === 'error' && c.content.includes('自动链启动失败'));
    expect(errorComment).toBeDefined();
    
    // 验证告警已调用（mock 断言）
    expect(mockAlert).toHaveBeenCalledWith(
      expect.objectContaining({
        level: 'high',
        requirement_id: req.id
      })
    );
    
    // 验证台账标记
    const updated = await getRequirement(req.id);
    expect(updated.advance?.pausedReason).toContain('自动开跑失败');
  });
  
  it('FR-3: 无 plan.md 有 decomposition.md 通过验收', async () => {
    const req = await seedRequirement({ status: 'implementing' });
    const docs = [
      { kind: 'requirement', path: 'requirement.md' },
      { kind: 'decomposition', path: 'decomposition.md' },  // 有这个
      // 无 plan.md
      { kind: 'verification', path: 'verification.md' }
      // ... 其余必交文档
    ];
    
    const result = await checkDocCompleteness(req, docs);
    
    expect(result.passed).toBe(true);
    expect(result.missing).not.toContain('plan.md');
  });
  
  it('FR-4: 全量测试不回退', async () => {
    // 本测试由 `npx vitest run` 覆盖，此处只验证 isLegacy 豁免不变
    const legacyReq = { id: 'REQ-legacy', created: '2026-08-01' };
    const result = await checkSomeRule(legacyReq);
    expect(result.bypassed).toBe(true);  // 旧需求仍豁免
  });
});
```

**执行策略**：
1. 先跑新测试（预期红）→ 证明断链可复现
2. 实施 FR-1~FR-3 修复
3. 再跑新测试（预期绿）→ 证明修复有效
4. 全量测试 `npx vitest run` 保持绿灯

---

## 3. 验收口径（serves: FR-1, FR-2, FR-3, FR-4）

### 3.1 自动化验收（must pass）（serves: FR-4）

```bash
# 1. 新增测试先红后绿（修复前后各跑一次，留两次输出作证据）
npx vitest run tests/auto-chain-approval-fix.test.ts

# 2. 验收门禁不再硬要 plan.md
npx vitest run -t "FR-3: 无 plan.md"

# 3. 全量回归测试
npx vitest run  # 期望全绿
```

### 3.2 手工验收（代码审查）（serves: FR-1, FR-2, FR-3）

```bash
# 1. 确认覆盖门禁已双源合并
grep -n "taskRefsFromDecomposition" src/application/internal/content-gate-wiring.ts
# 期望命中，且在 assertClauseCoverageGate 函数内

# 2. 确认开跑失败有评论+告警+标记
grep -n "addSystemComment\|deps.alert\|pausedReason" src/application/use-cases/AskConfirm.ts
# 期望 3 处命中，均在 catch 路径内

# 3. 确认 plan.md 已从必交清单移除
grep -n "kind: 'plan'" src/domain/workflow/DocCompleteness.ts
# 期望无命中（已删除）

grep -n "decomposition.md" src/domain/workflow/DocCompleteness.ts
# 期望命中（保留，kind: 'decomposition'）

# 4. 确认残留引用已清理
grep -rn "plan.md" src/domain/requirement/RequirementStatus.ts docs/requirements/_template/
# 期望阶段注释已改、模板无 plan.md 指引
```

### 3.3 边界验证（实测场景）（serves: FR-1, FR-2, FR-3）

**场景 1**：REQ-2d1c74 类需求（有 FR 编号、有 RTM、plan 对象无 refs）
- 批准后不再被 requirement_uncovered 拒绝 ✓
- autoRun===true、子卡已落库 ✓

**场景 2**：开跑失败的需求
- 看板显示「⚠️ 自动链失败」徽标 ✓
- 台账有系统评论（含恢复指引）✓
- 收到高优告警（飞书/邮件）✓

**场景 3**：新需求提交验收
- 有 decomposition.md、无 plan.md → 通过 ✓
- 有 plan.md、无 decomposition.md → 被拒（后者仍必交）✓

---

## 4. 迁移与兼容（serves: FR-1, FR-2, FR-3）

**向后兼容**：
- 旧需求（已有 plan.md）不受影响，多出的文件无害
- `req.plan` 记录保持，批准弹框与落卡仍消费
- `requirement_refs` 字段保留（任务对象上的绑定仍有效）

**数据迁移**：
- 无需回填。台账新增字段 `advance.pausedReason` 可选，旧数据缺失即表示"无失败记录"

**开关与灰度**：
- 无需开关。修复是纯逻辑层改动（门禁双源 + 失败响亮 + 文档清单），不影响数据写入链

**回滚路径**：
- FR-1：恢复 content-gate-wiring.ts 的旧逻辑（仅读任务对象）
- FR-2：删除 catch 路径的评论/告警/标记代码
- FR-3：重新加回 VERIFICATION_DOC_CLASSES 第 2 类
- 回滚后存量评论与告警记录保留（无害）
