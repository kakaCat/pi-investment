# REQ-260925110957-552d 拆分与验收阶段问题汇总与修复清单

> **文档目标**：汇总拆分和验收阶段的所有问题，提供清晰的修复优先级和实施步骤。

---

## 📋 问题总览

### 拆分阶段问题（3个）

| 问题 | 严重性 | 影响 | 状态 |
|------|--------|------|------|
| P1: 反复退回 design | 🔴 高 | 无法完成拆分，需手动重试 | 已诊断 |
| P2: 链停滞在批次间 | 🔴 高 | 前10个任务完成后卡住 | 已诊断 |
| P3: 功能点未被接收 | 🔴 致命 | 阻塞验收和归档 | 已诊断 |

### 验收阶段问题（2个）

| 问题 | 严重性 | 影响 | 状态 |
|------|--------|------|------|
| P4: 验收材料未提交 | 🟡 中 | 卡在 accepting 阶段 | 已诊断 |
| P5: 缺少验收提示词 | 🟡 中 | Agent 不知道怎么验收 | 已诊断 |

---

## 🔍 问题详细分析

### P1: 拆分反复退回 design ↔ decomposing

**症状**：
```
03:52 - 进入 decomposing
04:39 - 退回 design（REQBOARD_DRIVER_REQUIRED）
04:40 - 再次进入 decomposing（手动推进）
05:12 - 成功进入 implementing
```

**根因**：
- `confirm-settle.ts` 在批准弹框回调中尝试"自动开跑"
- 批准回调不在 agent 的 live driver 回合内
- SessionProbeAdapter 检查失败 → `REQBOARD_DRIVER_REQUIRED`

**影响**：
- 拆分流程不稳定，需要手动重试
- 浪费时间，降低自动化程度

---

### P2: 链停滞在批次之间

**症状**：
```
批次1-4: 10个任务 done ✅
批次5: t-b1fe76, t-7f957a 永久卡在 todo ❌
```

**根因**：
1. **任务没有 `stages` 字段**
   - 所有23个任务的 `stages = undefined`
   - `expandSubtasks` 读不到 stages → 返回空数组
   - 父卡开工但没有子卡

2. **选择器只认父子结构**
   - `selectAdvanceEvent` 只会选择：
     - FINALIZE_PARENT（收尾有子卡的父卡）
     - RUN_SUBTASK（执行子卡）
     - OPEN_PARENT（开新父卡）
   - 普通任务（无子卡）永远不会被选中

**影响**：
- 实施链永久停滞
- 需要手动干预才能继续

---

### P3: 功能点未被接收（验收阻塞）

**症状**：
```
需求定义：9个功能点（FR-1 到 FR-9）
任务完成：23个任务 done (100%)
接收状态：所有功能点 🔴 未被接收

数据证据：
- 总任务数: 23
- 有 requirement_refs: 0
- 无 requirement_refs: 23
```

**根因**：
1. **Schema 缺失**
   - `DecomposeTool.ts` 的 tasks schema 没有 `requirement_refs` 字段

2. **用例不处理**
   - `Decompose.ts` 创建 TaskRecord 时没有读取 `requirement_refs`

3. **提示词不要求**
   - 拆分提示词没有明确要求填写 `requirement_refs`

**影响**：
- ❌ 无法生成功能点验收项
- ❌ 验收人说"拆分有问题"
- ❌ 即使任务都完成，功能点仍是"未实现"
- ❌ 阻塞验收和归档

---

### P4: 验收材料未提交

**症状**：
```
需求状态: accepting
验收文档: 已编写多个（COMPLETION-REPORT.md、deploy-verification-actual.md 等）
verification 产物: ❌ 无
acceptanceSheet: ❌ 无
```

**根因**：
- Agent 进入 accepting 后不知道应该调用 `reqboard_submit(kind='verification')`
- 写了很多文档但不知道哪个是"正式验收材料"

**影响**：
- 无法生成验收单
- 无法进行人工验收
- 卡在 accepting 阶段

---

### P5: 缺少 accepting 阶段提示词

**症状**：
```
packages/web/dsh-pmboard/src/domain/prompt/
  ├── brainstorming.txt ✅
  ├── design.txt ✅
  ├── decomposing.txt ✅
  ├── implementing.txt ✅
  └── accepting.txt ❌ 不存在
```

**根因**：
- 没有 accepting.txt 提示词
- Agent 不知道验收阶段的工作流程

**影响**：
- Agent 不知道应该做什么
- 验收流程断链

---

## 🔧 完整修复方案

### 修复优先级

| 优先级 | 问题 | 修复工作量 | 紧急度 |
|--------|------|-----------|--------|
| **P0** | P3: 功能点未被接收 | 中（4个文件） | 🔴 阻塞验收 |
| **P1** | P2: 链停滞 | 中（3个文件） | 🔴 阻塞实施 |
| **P2** | P1: 反复退回 | 低（1个文件） | 🟡 体验问题 |
| **P3** | P4: 验收未提交 | 低（手动调用） | 🟡 可绕过 |
| **P4** | P5: 缺少提示词 | 低（1个文件） | 🟢 增强体验 |

---

## 📦 修复清单

### 修复组A：功能点接收（P0）

**问题**：requirement_refs 全部为空 → 功能点未被接收

#### A1. 短期修复：手动补充 requirement_refs

**文件**：`.dsh-data/dsh-reqboard.json`

**步骤**：
1. 备份数据库
2. 根据 decomposition.md 的 RTM 表，为每个任务补充 requirement_refs
3. 验证覆盖率

**映射关系**（从 RTM 表提取）：
```javascript
// 批次1-2: 基础
t-cda91b (t1 领域类型定义)     → ["FR-3", "FR-4", "FR-9"]
t-54d646 (t2 台账迁移)          → ["FR-3"]
t-6a1ad6 (t3 DSH jobs 适配器)  → ["FR-1"]
t-69b7c1 (t4 workflow schema)  → ["FR-7"]

// 批次3: 核心算法
t-7cdbbd (t5 写集冲突检测)      → ["FR-4"]
t-29de13 (t6 批调度器)          → ["FR-4"]
t-f750de (t7 孤儿回收)          → ["FR-5"]
t-8fc069 (t8 checkpoint 管理器) → ["FR-3"]

// 批次4: 执行器
t-89953c (t9 后台执行器)        → ["FR-1", "FR-3", "FR-4", "FR-5"]
t-1cbdd7 (t10 投递用例)         → ["FR-1"]
t-b1fe76 (t11 查询用例)         → ["FR-2"]
t-7f957a (t12 仓储层扩展)       → ["FR-3", "FR-5", "FR-9"]

// 批次5: 实施链改造
t-dc5b58 (t13 AdvanceChain)    → ["FR-1", "FR-6"]
t-3c54fb (t14 ExecuteTask)     → ["FR-7"]
t-9e3b7b (t15 选择器改造)       → ["FR-5"]
t-182606 (t16 workflow script) → ["FR-7"]

// 批次6: 工具层
t-69ab2a (t17 task_run 改造)   → ["FR-1"]
t-c031de (t18 run_status 新增) → ["FR-2", "FR-9"]
t-301eee (t19 工具注册提示词)   → ["FR-1", "FR-2"]

// 批次7: 测试
t-dcc586 (t20 集成测试)        → ["FR-6"]
t-966b43 (t21 E2E 测试)        → ["FR-1", "FR-2", "FR-3", "FR-4", "FR-5", "FR-6", "FR-7", "FR-9"]

// 批次8: 交付
t-b37ffb (t22 构建验证)        → ["FR-8"]
t-97f31d (t23 部署验证)        → ["FR-8"]
```

**执行脚本**：
```bash
cd .dsh-data
cp dsh-reqboard.json dsh-reqboard.json.backup

# 使用 jq 批量更新
jq '
  .tasks |= map(
    if .id == "t-cda91b" then . + {requirement_refs: ["FR-3", "FR-4", "FR-9"]}
    elif .id == "t-54d646" then . + {requirement_refs: ["FR-3"]}
    elif .id == "t-6a1ad6" then . + {requirement_refs: ["FR-1"]}
    elif .id == "t-69b7c1" then . + {requirement_refs: ["FR-7"]}
    elif .id == "t-7cdbbd" then . + {requirement_refs: ["FR-4"]}
    elif .id == "t-29de13" then . + {requirement_refs: ["FR-4"]}
    elif .id == "t-f750de" then . + {requirement_refs: ["FR-5"]}
    elif .id == "t-8fc069" then . + {requirement_refs: ["FR-3"]}
    elif .id == "t-89953c" then . + {requirement_refs: ["FR-1", "FR-3", "FR-4", "FR-5"]}
    elif .id == "t-1cbdd7" then . + {requirement_refs: ["FR-1"]}
    elif .id == "t-b1fe76" then . + {requirement_refs: ["FR-2"]}
    elif .id == "t-7f957a" then . + {requirement_refs: ["FR-3", "FR-5", "FR-9"]}
    elif .id == "t-dc5b58" then . + {requirement_refs: ["FR-1", "FR-6"]}
    elif .id == "t-3c54fb" then . + {requirement_refs: ["FR-7"]}
    elif .id == "t-9e3b7b" then . + {requirement_refs: ["FR-5"]}
    elif .id == "t-182606" then . + {requirement_refs: ["FR-7"]}
    elif .id == "t-69ab2a" then . + {requirement_refs: ["FR-1"]}
    elif .id == "t-c031de" then . + {requirement_refs: ["FR-2", "FR-9"]}
    elif .id == "t-301eee" then . + {requirement_refs: ["FR-1", "FR-2"]}
    elif .id == "t-dcc586" then . + {requirement_refs: ["FR-6"]}
    elif .id == "t-966b43" then . + {requirement_refs: ["FR-1", "FR-2", "FR-3", "FR-4", "FR-5", "FR-6", "FR-7", "FR-9"]}
    elif .id == "t-b37ffb" then . + {requirement_refs: ["FR-8"]}
    elif .id == "t-97f31d" then . + {requirement_refs: ["FR-8"]}
    else . end
  )
' dsh-reqboard.json > tmp.json && mv tmp.json dsh-reqboard.json

# 验证覆盖
echo "验证功能点覆盖："
for fr in FR-1 FR-2 FR-3 FR-4 FR-5 FR-6 FR-7 FR-8 FR-9; do
  count=$(jq "[.tasks[] | select(.requirementId == \"REQ-260925110957-552d\" and (.requirement_refs // []) | contains([\"$fr\"]))] | length" dsh-reqboard.json)
  echo "$fr: $count 个任务接收"
done
```

**预期结果**：
```
FR-1: 7 个任务接收
FR-2: 4 个任务接收
FR-3: 5 个任务接收
FR-4: 5 个任务接收
FR-5: 5 个任务接收
FR-6: 3 个任务接收
FR-7: 4 个任务接收
FR-8: 2 个任务接收
FR-9: 4 个任务接收
```

#### A2. 长期修复：工具支持 requirement_refs

**修改文件清单**：
1. `packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts`
2. `packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts`
3. `packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`
4. `packages/web/dsh-pmboard/tests/unit/decompose-coverage.test.ts`（新增）

**详细修改见附录A**

---

### 修复组B：链停滞问题（P1）

**问题**：任务无 stages → 无子卡 → 选择器找不到事件

#### B1. 短期修复：手动补充 stages

**执行脚本**：
```bash
cd .dsh-data

jq '
  .tasks |= map(
    if .requirementId == "REQ-260925110957-552d" and .stages == null then
      . + {stages: ["implement", "test"]}
    else . end
  )
' dsh-reqboard.json > tmp.json && mv tmp.json dsh-reqboard.json
```

#### B2. 长期修复：工具支持 stages

**修改文件清单**：
1. `packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts`
2. `packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts`
3. `packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`

**详细修改见附录B**

---

### 修复组C：自动开跑问题（P2）

**问题**：批准回调中触发推进 → REQBOARD_DRIVER_REQUIRED

#### C1. 修复：移除自动开跑

**文件**：`packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts`

**修改**：
```typescript
// 批准拆分计划后：只设置 autoRun = true，不触发推进
if (from === 'decomposing' && to === 'implementing') {
  // ... 落库任务的代码保持不变 ...
  
  // ✅ 只设置开关
  req.autoRun = true
  req.comments.push({
    body: '[自动链] 批准拆分 → autoRun=true，推进由 agent 触发或 scanAndResume 保底'
  })
  
  // ❌ 删除：触发推进的代码
}
```

**详细修改见附录C**

---

### 修复组D：验收流程（P3 + P4）

**问题**：验收材料未提交 + 缺少提示词

#### D1. 短期修复：手动提交验收

**调用工具**：
```typescript
reqboard_submit({
  kind: 'verification',
  requirement_id: 'REQ-260925110957-552d',
  summary: `
## 交付结论
REQ-260925110957-552d 已完成全部23个任务，功能实现完整。

### 核心交付
1. ✅ ctx.jobs 异步化
2. ✅ 写集并行
3. ✅ 中断可续

### 质量保证
- 单测全绿
- 集成测试通过
- E2E 测试通过
- 部署验证完成
  `,
  evidence: [
    '1. 构建验证：pnpm build 成功',
    '2. 重启验证：13080 端口正常',
    '3. 工具表验证：reqboard_task_run / reqboard_run_status 可见',
    '4. 单测：vitest 全绿',
    '5. 集成测试：task-chain.test.ts 通过',
    '6. E2E 测试：workflow-resume.test.ts 通过',
    '7. 完成报告：COMPLETION-REPORT.md',
    '8. 部署文档：deploy-verification-actual.md',
    '9. 测试证据：tests/test-evidence.md',
    '10. 代码评审：reviews/code-review.md'
  ]
})
```

#### D2. 长期修复：补充 accepting 提示词

**新建文件**：`packages/web/dsh-pmboard/src/domain/prompt/accepting.txt`

**详细修改见附录D**

---

## 📊 修复效果对比

### Before（当前问题）

```
【拆分阶段】
03:52 → decomposing
04:39 → design（退回，REQBOARD_DRIVER_REQUIRED）
04:40 → decomposing（手动重试）
05:12 → implementing
08:08 → accepting（自动 rollup）

【实施阶段】
批次1-4: 10个任务 done ✅
批次5: 永久卡在 todo ❌（无 stages）

【验收阶段】
accepting 状态 ✅
所有任务 done ✅
功能点未被接收 ❌（无 requirement_refs）
验收材料未提交 ❌
验收单未生成 ❌
卡住无法归档 ❌
```

### After（修复后）

```
【拆分阶段】
03:52 → decomposing
批准计划（含 stages + requirement_refs）
落库任务（autoRun=true）
agent 主动触发推进 ✅
直接进入 implementing ✅

【实施阶段】
父卡开工 → 读取 stages → 创建子卡
子卡执行 → 父卡收尾 → 自动推进
批次1-8 全部完成 ✅
自动 rollup → accepting ✅

【验收阶段】
功能点全部接收 ✅
reqboard_submit 提交 ✅
生成验收单 ✅
reqboard_accept_sheet 逐项验收 ✅
全部通过 → 自动归档 ✅
```

---

## 🎯 实施计划

### 阶段1：紧急修复（立即执行）

**目标**：让当前需求能够通过验收

| 步骤 | 操作 | 预计时间 | 负责人 |
|------|------|---------|--------|
| 1 | 手动补充 requirement_refs | 5分钟 | Agent/人工 |
| 2 | 手动补充 stages | 2分钟 | Agent/人工 |
| 3 | 调用 reqboard_submit 提交验收 | 2分钟 | Agent |
| 4 | 生成验收单并逐项验收 | 10分钟 | 人工 |
| 5 | 归档 | 自动 | 系统 |

**总计**：约20分钟

---

### 阶段2：代码修复（后续版本）

**目标**：让未来的需求不再遇到同样问题

| 修复组 | 文件数 | 预计工作量 | 测试工作量 |
|--------|--------|-----------|-----------|
| A: requirement_refs | 4 | 2小时 | 1小时 |
| B: stages | 3 | 1.5小时 | 0.5小时 |
| C: 自动开跑 | 1 | 0.5小时 | 0.5小时 |
| D: accepting 提示词 | 2 | 1小时 | 0.5小时 |

**总计**：约5小时开发 + 2.5小时测试 = 7.5小时

---

## 📝 验证清单

### 紧急修复验证

- [ ] requirement_refs 已补充（每个 FR 至少1个任务接收）
- [ ] stages 已补充（所有任务都有 stages）
- [ ] 需求文档显示所有功能点 ✅ 已被接收
- [ ] verification 产物已登记
- [ ] acceptanceSheet 已生成
- [ ] 所有验收项通过
- [ ] 需求已归档

### 代码修复验证

- [ ] SubmitTool schema 包含 requirement_refs 和 stages
- [ ] Decompose.ts 正确处理这两个字段
- [ ] 提示词明确要求填写
- [ ] 覆盖门禁生效（缺失功能点时拒绝拆分）
- [ ] 新需求拆分测试通过
- [ ] 自动开跑不再失败
- [ ] accepting 提示词生效

---

## 附录

### 附录A：requirement_refs 详细修改

#### A.1 SubmitTool schema

```typescript
// packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts
requirement_refs: {
  type: 'array',
  items: { type: 'string', pattern: '^FR-[0-9]+$' },
  description: '本任务实现的功能点编号（如 ["FR-1", "FR-4"]）'
}
```

#### A.2 Decompose 用例

```typescript
// packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts
const child: TaskRecord = {
  // ...
  requirement_refs: task.requirement_refs ?? [],
  // ...
}
```

#### A.3 覆盖门禁

```typescript
// 在 Decompose.ts 落库前检查
const uncovered = findUncoveredFRs(requirement, draft)
if (uncovered.length > 0) {
  reject(`功能点 ${uncovered.join(', ')} 未被接收`, 'REQBOARD_INCOMPLETE_COVERAGE')
}
```

### 附录B：stages 详细修改

#### B.1 SubmitTool schema

```typescript
stages: {
  type: 'array',
  items: { 
    type: 'string',
    enum: ['analysis', 'doc', 'ui', 'implement', 'integrate', 'test', 'review', 'merge']
  },
  description: '任务阶段列表。常见：["implement","test"]'
}
```

#### B.2 Decompose 用例

```typescript
const child: TaskRecord = {
  // ...
  stages: task.stages ?? undefined,
  // ...
}
```

### 附录C：confirm-settle 修改

```typescript
// packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts

// 修改前（第200-230行）
if (from === 'decomposing' && to === 'implementing') {
  // ... 落库任务 ...
  req.autoRun = true
  // ❌ 删除：触发推进的代码
}

// 修改后
if (from === 'decomposing' && to === 'implementing') {
  // ... 落库任务 ...
  req.autoRun = true
  req.comments.push({
    body: '[自动链] autoRun=true，推进由 agent 触发'
  })
  // ✅ 不在这里触发推进
}
```

### 附录D：accepting 提示词

```
## Accepting 阶段（验收）

### 工作流程
1. 整理验收材料（构建/测试/部署证据）
2. 调用 reqboard_submit(kind='verification')
3. 生成验收单
4. reqboard_accept_sheet 逐项验收
5. 全部通过后自动归档

### 注意事项
- summary 必须包含：完成了什么、质量保证
- evidence 必须可复核（1-20条）
- 不要跳过提交步骤
```

---

## 总结

### 5个问题，2套修复

**紧急修复**（20分钟）：
- 手动补数据（requirement_refs + stages）
- 手动提交验收
- 完成当前需求

**长期修复**（7.5小时）：
- 4个修复组，11个文件
- 单测 + 集成测试
- 未来需求不再遇到

### 关键教训

1. **拆分计划必须完整**：stages + requirement_refs 缺一不可
2. **工具 schema 是合约**：缺字段 = 无法填 = 无法验证
3. **验收基于功能点**：不是任务数，而是 FR 覆盖
4. **每个阶段要有提示词**：让 Agent 知道该做什么
