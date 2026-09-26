# REQ-260925110957-552d 验收阶段问题分析

## 问题诊断

### 当前状态
- ✅ 需求状态：accepting（2026-09-25 08:08:05）
- ✅ 任务完成：23/23 (100%)
- ✅ 验收文档：已编写多个（COMPLETION-REPORT.md、FINAL-DELIVERY.md 等）
- ❌ **验收提交：未调用 reqboard_submit(kind='verification')**
- ❌ **验收单：未生成（因为未提交）**
- ❌ **人工验收：无法进行（卡住）**

### 根本原因

**Agent 进入 accepting 后不知道下一步应该做什么**

1. **缺少 accepting 阶段提示词**
   - packages/web/dsh-pmboard/src/domain/prompt/ 下没有 accepting.txt
   - Agent 没有明确的验收流程指引

2. **验收材料散乱**
   - 写了很多文档，但不清楚哪个是"正式验收材料"
   - 不知道应该调用 reqboard_submit 提交

3. **工作流断链**
   - implementing → accepting（自动推进 ✅）
   - accepting → 提交验收材料（❌ 断链）
   - 提交 → 生成验收单（❌ 无法进行）
   - 验收单 → 人工审核 → archived（❌ 卡住）

---

## 立即修复（手动提交验收）

### 步骤1：准备验收材料

查看现有文档：
```bash
cd docs/requirements/REQ-260925110957-552d

# 主要验收材料
ls -lh COMPLETION-REPORT.md          # 工作完成报告
ls -lh deploy-verification-actual.md # 部署验证
ls -lh tests/test-evidence.md        # 测试证据
ls -lh reviews/code-review.md        # 代码评审
```

### 步骤2：调用 reqboard_submit 提交

```typescript
await tools.reqboard_submit({
  kind: 'verification',
  requirement_id: 'REQ-260925110957-552d',
  
  summary: `
## 交付结论

**REQ-260925110957-552d - ctx.jobs 异步化 + 写集并行 + 中断可续** 已完成全部23个任务，功能实现完整，测试通过，已部署验证。

### 核心交付
1. ✅ ctx.jobs 异步化：后台任务注册、立即返回、跑完通知
2. ✅ 写集并行：批调度器、冲突检测、批内并发
3. ✅ 中断可续：checkpoint 管理、孤儿回收、选择器恢复

### 质量保证
- 单测：全绿（vitest）
- 集成测试：task-chain.test.ts 通过
- E2E 测试：workflow-resume.test.ts 通过
- 部署验证：13080 端口工具表可见、实际调用正常

### 代码交付
- 13 个 git 提交
- 13 个文件（6 新增，7 修改）
- 889 行插入，174 行删除
  `,
  
  evidence: [
    '1. 构建验证：pnpm build 成功（packages/web/dsh-pmboard/dist/index.mjs 已生成）',
    '2. 重启验证：./scripts/restart-with-build.sh 成功，端口 13080 正常响应',
    '3. 工具表验证：reqboard_task_run / reqboard_run_status 可见且可调用',
    '4. 单测验证：npx vitest run 全绿',
    '5. 集成测试：packages/web/dsh-pmboard/tests/integration/task-chain.test.ts 通过',
    '6. E2E 测试：packages/web/dsh-pmboard/tests/e2e/workflow-resume.test.ts 通过',
    '7. 部署文档：docs/requirements/REQ-260925110957-552d/deploy-verification-actual.md',
    '8. 完成报告：docs/requirements/REQ-260925110957-552d/COMPLETION-REPORT.md',
    '9. 测试证据：docs/requirements/REQ-260925110957-552d/tests/test-evidence.md',
    '10. 代码评审：docs/requirements/REQ-260925110957-552d/reviews/code-review.md'
  ]
});
```

**预期结果**：
- ✅ 登记 verification 产物
- ✅ 生成验收单（acceptanceSheet）
- ✅ 验收单包含所有功能点的验收项
- ✅ 可以开始人工验收（reqboard_accept_sheet）

---

## 长期修复（补充 accepting 阶段提示词）

### 修改1：创建 accepting 阶段提示词

**新建文件**：`packages/web/dsh-pmboard/src/domain/prompt/accepting.txt`

```
## Accepting 阶段（验收）

需求状态为 accepting 时，表示所有实施任务已完成，现在需要验收交付成果。

### 工作流程

1. **整理验收材料**
   - 回顾需求文档（requirement.md）中的功能点（FR-1 到 FR-N）
   - 收集验收证据：
     * 构建验证（pnpm build 输出）
     * 测试证据（单测/集成测试/E2E 测试通过记录）
     * 部署验证（重启后工具可见、实际调用正常）
     * 文档交付（设计文档、任务卡、测试报告）

2. **提交验收材料**
   调用 reqboard_submit(kind='verification')：
   ```typescript
   reqboard_submit({
     kind: 'verification',
     requirement_id: '<REQ-ID>',
     summary: '交付结论：完成了什么、质量如何、已验证项',
     evidence: [
       '1. 构建验证：命令 + 输出摘要',
       '2. 测试验证：测试文件路径 + 结果',
       '3. 部署验证：部署文档路径',
       // ... 可复核的证据清单（1-20条）
     ]
   })
   ```

3. **生成验收单**
   - 提交后系统自动生成 acceptanceSheet
   - 验收单包含需求文档中所有功能点的验收项
   - 每项对应一个 FR-N，需要逐项验收

4. **人工验收**
   - 调用 reqboard_accept_sheet 逐项验收
   - 每批最多 5-10 项，通过/改进/其他
   - 选"改进"需要写明改进意见
   - 全部通过后需求自动归档

### 注意事项

- **summary 必须包含**：完成了什么、质量保证、已验证项
- **evidence 必须可复核**：命令+输出/文件路径/截图路径
- **不要跳过提交**：没有 verification 产物无法生成验收单
- **验收单是必经之路**：必须逐项通过才能归档

### 常见问题

Q: 为什么进入 accepting 后卡住了？
A: 可能忘记调用 reqboard_submit(kind='verification')

Q: 验收单在哪里？
A: 提交验收材料后自动生成，调 reqboard_accept_sheet 查看

Q: 可以直接归档吗？
A: 不行，必须先提交验收 → 生成验收单 → 逐项通过 → 自动归档
```

### 修改2：注册提示词

**文件**：`packages/web/dsh-pmboard/src/domain/prompt/index.ts`

```typescript
import acceptingPrompt from './accepting.txt?raw'

export const STAGE_PROMPTS = {
  // ... 其他阶段
  accepting: acceptingPrompt,  // ← 新增
}
```

### 修改3：在 system prompt 中注入

确保 accepting 阶段的提示词被注入到 agent 的 system prompt 中。

---

## 预期效果

### Before（当前问题）
```
implementing → accepting（自动）
  → ❓ 不知道做什么
  → 写了很多文档但不提交
  → 永久卡在 accepting
```

### After（修复后）
```
implementing → accepting（自动）
  → 看到 accepting 提示词
  → 整理验收证据
  → 调用 reqboard_submit(kind='verification')
  → 生成验收单
  → reqboard_accept_sheet 逐项验收
  → 全部通过 → 自动归档
```

---

## 总结

### 问题本质

**accepting 阶段缺少明确的工作流指引**
- 没有提示词 → Agent 不知道该做什么
- 没有验收单 → 无法人工审核
- 卡在验收 → 无法归档

### 解决方案

1. **短期**：手动调用 reqboard_submit 提交验收材料
2. **长期**：补充 accepting.txt 提示词，让 Agent 知道验收流程

### 关键原则

- ✅ **每个阶段都应有提示词**：指导 Agent 该阶段做什么
- ✅ **验收是必经之路**：不能跳过，必须生成验收单
- ✅ **提交即生成**：reqboard_submit(verification) → acceptanceSheet
