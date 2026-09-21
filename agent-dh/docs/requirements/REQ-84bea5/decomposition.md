---
requirement: REQ-84bea5
title: 修复「批准计划→自动开跑」断链拆分计划
created: 2026-09-21
status: pending_approval
---

# REQ-84bea5 拆分计划

## 1. 改动盘点

### 1.1 核心修复（FR-1: 覆盖门禁双源合并）

**文件**：`src/application/internal/content-gate-wiring.ts`  
**改动类型**：修改  
**改动内容**：
- `assertClauseCoverageGate` 函数：从"仅任务对象"改为"任务对象 ∪ decomposition.md RTM"
- 新增：调用 `taskRefsFromDecomposition(requirementDir)` 读取 RTM 表
- 逻辑：两个来源取并集（Set 去重），任一来源声明接收即算有落点

**依赖**：无（`taskRefsFromDecomposition` 函数已存在于 `content-trace.ts`）

---

### 1.2 失败响亮化（FR-2: 自动开跑失败可观测）

**文件**：`src/application/use-cases/AskConfirm.ts`  
**改动类型**：修改  
**改动内容**：
- 自动拆分/开跑的 catch 路径（约 L295-299）：
  - 新增：写系统评论（含失败原因与恢复指引）
  - 新增：调用 `deps.alert`（FailureAlert）发高优告警
  - 新增：在需求台账标记 `advance.pausedReason`（失败原因）
  - 保留：返回 note（兼容既有行为）

**文件**：`src/domain/requirement/RequirementRecord.ts`  
**改动类型**：修改  
**改动内容**：
- `RequirementRecord` 接口：`advance` 字段新增 `pausedReason?: string`
- 语义：自动链失败时记录失败原因，与手动模式区分

**依赖**：T1（数据契约）

---

### 1.3 验收清单更新（FR-3: plan.md 残留清理）

**文件**：`src/domain/workflow/DocCompleteness.ts`  
**改动类型**：修改  
**改动内容**：
- `VERIFICATION_DOC_CLASSES` 数组：删除第 2 类 `plan.md（拆分计划）`
- 保留第 7 类 `decomposition.md（拆分计划）`

**文件**：`src/domain/requirement/RequirementStatus.ts`  
**改动类型**：修改  
**改动内容**：
- L27 阶段注释：删除 "plan.md" 表述

**文件**：`docs/requirements/_template/plan.md`  
**改动类型**：删除  
**说明**：模板文件删除（新流程不再生成 plan.md）

**依赖**：无

---

### 1.4 回归测试（FR-4: 断链复现与修复验证）

**文件**：`tests/auto-chain-approval.test.ts`  
**改动类型**：修改  
**改动内容**：
- 现有测试：为种子需求补充 `requirement.md`（含 FR 编号），验证门禁不再短路
- 新增用例 1：**断链复现测试**（带 FR + RTM，修复前必红）
  - 种子：requirement.md（含 FR-1/FR-2）+ decomposition.md（RTM 表覆盖）+ plan payload 无 refs
  - 批准后断言：`autoRun === true`、任务落库、链推进到 in_progress
- 新增用例 2：**双源皆空测试**
  - 种子：requirement.md（含 FR-1）+ plan/decomposition 皆无 refs
  - 批准仍被拒 `requirement_uncovered`，且台账新增评论 + alert 调用一次
- 新增用例 3：**验收文档门禁测试**
  - 输入：8 类文档（无 plan.md、有 decomposition.md）
  - `checkDocCompleteness` 返回 `passed === true`

**依赖**：T1（数据契约）、T2（覆盖门禁）、T3（失败响亮）、T4（验收清单）

---

## 2. 任务表（RTM 覆盖表）

| Key | Title | Phase | Side | Depends On | Requirement Refs |
|-----|-------|-------|------|------------|------------------|
| T1  | 数据契约：RequirementRecord 扩展 pausedReason | doc | backend | - | FR-2 |
| T2  | 覆盖门禁双源合并实现 | implement | backend | - | FR-1 |
| T3  | 失败响亮化：评论+告警+标记 | implement | backend | T1 | FR-2 |
| T4  | 验收清单：删除 plan.md 残留 | implement | backend | - | FR-3 |
| T5  | 回归测试：断链复现+修复验证 | test | backend | T1, T2, T3, T4 | FR-4 |

---

## 3. 任务详细定义

### T1: 数据契约：RequirementRecord 扩展 pausedReason

**Phase**: doc  
**Side**: backend  
**Depends On**: -

**Implementation**:
1. 打开 `src/domain/requirement/RequirementRecord.ts`
2. 找到 `RequirementRecord` 接口的 `advance` 字段定义
3. 在 `advance` 对象类型中新增：`pausedReason?: string;`
4. 添加 JSDoc 注释：`/** 自动链失败原因（与手动模式区分） */`

**Acceptance**:
- `grep -n "pausedReason" src/domain/requirement/RequirementRecord.ts` 命中一行
- TypeScript 编译通过：`npx tsc --noEmit`

---

### T2: 覆盖门禁双源合并实现

**Phase**: implement  
**Side**: backend  
**Depends On**: -

**Implementation**:
1. 打开 `src/application/internal/content-gate-wiring.ts`
2. 定位 `assertClauseCoverageGate` 函数（约 L56-99）
3. 找到 `taskRefs` 计算逻辑（当前只从任务对象读）
4. 导入 `taskRefsFromDecomposition`（从 `content-trace.ts`）
5. 改为：
   ```typescript
   const taskRefs = new Set([
     ...tasks.flatMap(t => t.requirement_refs || []),
     ...taskRefsFromDecomposition(requirementDir)
   ]);
   ```
6. 确保 RTM 解析失败时返回空数组（不把"没记录"当"已覆盖"）

**Acceptance**:
- 代码中 `taskRefsFromDecomposition` 被调用
- `npx tsc --noEmit` 编译通过
- 手工测试：创建临时需求目录，requirement.md 含 FR-1，decomposition.md RTM 表标注 T1→FR-1，plan payload 无 refs，调用 `assertClauseCoverageGate` 不抛 requirement_uncovered

---

### T3: 失败响亮化：评论+告警+标记

**Phase**: implement  
**Side**: backend  
**Depends On**: T1

**Implementation**:
1. 打开 `src/application/use-cases/AskConfirm.ts`
2. 定位自动拆分/开跑的 catch 路径（约 L295-299）
3. 在 catch 块内新增三步：
   a. 写系统评论：
      ```typescript
      await this.commentRepo.create({
        requirement_id: req.id,
        author: 'system',
        content: `自动开跑失败：${error.message}\n\n恢复路径：修复后手动调用 reqboard_decompose + reqboard_task_run`
      });
      ```
   b. 发高优告警：
      ```typescript
      await deps.alert({
        level: 'high',
        title: '自动链开跑失败',
        requirement_id: req.id,
        detail: error.message
      });
      ```
   c. 标记 pausedReason：
      ```typescript
      await this.reqRepo.update(req.id, {
        advance: { ...req.advance, pausedReason: error.message }
      });
      ```
4. 保留原 note 返回（兼容）

**Acceptance**:
- `grep -n "pausedReason" src/application/use-cases/AskConfirm.ts` 命中
- `grep -n "commentRepo.create" src/application/use-cases/AskConfirm.ts` 命中
- `grep -n "deps.alert" src/application/use-cases/AskConfirm.ts` 命中
- `npx tsc --noEmit` 编译通过

---

### T4: 验收清单：删除 plan.md 残留

**Phase**: implement  
**Side**: backend  
**Depends On**: -

**Implementation**:
1. 打开 `src/domain/workflow/DocCompleteness.ts`
2. 找到 `VERIFICATION_DOC_CLASSES` 数组定义（约 L37）
3. 删除第 2 类：`{ kind: 'plan', label: 'plan.md（拆分计划）', ...}`
4. 确认第 7 类 `decomposition.md` 保留
5. 打开 `src/domain/requirement/RequirementStatus.ts`
6. 定位 L27 阶段注释，删除 "plan.md" 表述
7. 删除模板文件：`rm docs/requirements/_template/plan.md`（如存在）

**Acceptance**:
- `grep -i "plan\.md" src/domain/workflow/DocCompleteness.ts` 无输出
- `grep -i "plan\.md" src/domain/requirement/RequirementStatus.ts` 无输出
- `ls docs/requirements/_template/plan.md` 返回 "No such file"
- `npx tsc --noEmit` 编译通过

---

### T5: 回归测试：断链复现+修复验证

**Phase**: test  
**Side**: backend  
**Depends On**: T1, T2, T3, T4

**Implementation**:
1. 打开 `tests/auto-chain-approval.test.ts`
2. 为现有测试补充种子 `requirement.md`（含 FR-1/FR-2）
3. 新增测试用例 1：**断链复现与修复**
   ```typescript
   test('批准计划后自动开跑（RTM 覆盖）', async () => {
     // 种子：requirement.md + decomposition.md RTM + plan 无 refs
     const req = await createSeedRequirement({
       requirement_md: 'FR-1: 功能点一\nFR-2: 功能点二',
       decomposition_md: '| T1 | 任务一 | FR-1 |\n| T2 | 任务二 | FR-2 |',
       plan: { tasks: [{ key: 'T1', title: '任务一' }] } // 无 requirement_refs
     });
     
     // 批准计划
     const result = await askConfirm({ target: 'plan', requirement_id: req.id });
     
     // 断言：自动开跑成功
     expect(result.success).toBe(true);
     const updated = await getRequirement(req.id);
     expect(updated.advance?.autoRun).toBe(true);
     expect(updated.status).toBe('implementing');
     const tasks = await getTasks(req.id);
     expect(tasks.length).toBeGreaterThan(0);
     expect(tasks.some(t => t.status === 'in_progress')).toBe(true);
   });
   ```
4. 新增测试用例 2：**双源皆空仍拒绝**
   ```typescript
   test('双源无 refs 时批准被拒', async () => {
     const req = await createSeedRequirement({
       requirement_md: 'FR-1: 功能点',
       decomposition_md: '| T1 | 任务 | - |', // 无覆盖
       plan: { tasks: [{ key: 'T1' }] }
     });
     
     await expect(askConfirm({ target: 'plan', requirement_id: req.id }))
       .rejects.toThrow('requirement_uncovered');
     
     // 断言：评论与告警
     const comments = await getComments(req.id);
     expect(comments.some(c => c.author === 'system' && c.content.includes('失败'))).toBe(true);
     // 注：alert 调用需 mock deps.alert 验证
   });
   ```
5. 新增测试用例 3：**验收文档门禁**
   ```typescript
   test('无 plan.md 但有 decomposition.md 时验收通过', () => {
     const docs = [
       { kind: 'requirement', path: 'requirement.md' },
       // 无 plan.md
       { kind: 'decomposition', path: 'decomposition.md' },
       { kind: 'verification', path: 'verification.md' },
       // ... 其他 6 类
     ];
     
     const result = checkDocCompleteness(docs);
     expect(result.passed).toBe(true);
   });
   ```
6. 运行测试：`npx vitest run tests/auto-chain-approval.test.ts`

**Acceptance**:
- 修复前运行新增用例 1，测试**必红**（断链复现）
- 应用 T2 后运行，测试**变绿**（修复生效）
- 用例 2、3 通过（双源空仍拒、验收门禁正确）
- 全量测试 `npx vitest run` 保持绿灯

---

## 4. 验收总览

1. **代码覆盖**：
   - `content-gate-wiring.ts` 已双源合并
   - `AskConfirm.ts` catch 已响亮化（评论+告警+标记）
   - `DocCompleteness.ts` / `RequirementStatus.ts` plan.md 残留已清理
   - `RequirementRecord.ts` 已扩展 pausedReason

2. **测试证据**：
   - `npx vitest run tests/auto-chain-approval.test.ts` **先红后绿**（断链复现用例）
   - 双源皆空测试通过（仍被拒 + 评论 + 告警）
   - 验收文档门禁测试通过（无 plan.md 可通过）
   - `npx vitest run` 全绿（dsh-pmboard 包）

3. **回归安全**：
   - 既有需求（含已交 plan.md 的 34 个存量）不受影响
   - RTM 解析失败时不误判为"已覆盖"
   - 手动模式（无 autoRun）与自动链失败（有 pausedReason）可区分

---

## 5. 风险与兜底

- **TypeScript 类型错误**：每卡完成后立即 `npx tsc --noEmit` 验证
- **测试环境依赖**：种子需求需 mock 文件系统（requirement.md / decomposition.md）
- **alert 接口未定义**：T3 需确认 `deps.alert` 可用，否则先实现 FailureAlert 占位
- **存量迁移**：34 个历史 plan.md 保留作档案，不强制清理

---

**提交后下一步**：调用 `reqboard_ask_confirm(target=plan)` 请人批准，批准后自动落库任务卡并进入实施。
