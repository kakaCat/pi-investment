# REQ-260925110957-552d 拆分与验收问题完整诊断

## 🚨 核心问题

### 问题1：所有功能点未被接收（0/9）

**现状**：
- 需求定义了 9 个功能点（FR-1 到 FR-9）
- 拆分创建了 23 个任务
- **但所有任务的 `requirement_refs` 都是空数组 `[]`**
- 需求文档显示：所有功能点 🔴 **未被接收**

**数据证据**：
```
# requirement.md 第261-269行
| FR-1 | 🔴 **未被接收** | — |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
...全部9条都是未被接收

# 数据库检查
总任务数: 23
有 requirement_refs: 0
无 requirement_refs: 23
```

### 问题2：拆分时没有填写 requirement_refs

**decomposition.md 的 RTM 对照表**：
```markdown
| 根编号 | 任务编号 | 标题 |
|--------|---------|------|
| FR-4 | t1 | 领域类型定义 |
| FR-3 | t1 | 领域类型定义 |
| FR-9 | t1 | 领域类型定义 |
| FR-3 | t2 | 台账迁移 |
| FR-1 | t3 | DSH jobs 适配器 |
...
```

**问题**：
- ✅ RTM 表说明了映射关系
- ❌ 但任务定义中**没有 `requirement_refs` 字段**
- ❌ `reqboard_decompose` 落库时没有写入这个字段
- ❌ 导致所有功能点显示"未被接收"

### 问题3：验收无法进行

因为功能点未被接收，验收时：
- ❌ 无法生成功能点对应的验收项
- ❌ 无法确认哪些功能已实现
- ❌ 即使23个任务都完成，功能点仍是"未实现"
- ❌ 验收人只能说"拆分有问题"

### 问题4：Agent 可能修改验收标准

你提到"agent还修改验收标准"，可能是因为：
- Agent 发现功能点未被接收
- 尝试修改任务的 acceptance 字段来绕过
- 或者修改需求文档的验收标准
- **这是错误的**：应该修复拆分，而不是改标准

---

## 🔍 根本原因分析

### 原因1：拆分工具缺陷

**`reqboard_decompose` 工具的问题**：

1. **schema 没有 `requirement_refs` 字段**
   - `packages/web/dsh-pmboard/src/tools/DecomposeTool/DecomposeTool.ts`
   - tasks schema 定义中缺少 `requirement_refs`

2. **`Decompose.ts` 用例没有处理**
   - `packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`
   - 创建 TaskRecord 时没有从 plan 读取 `requirement_refs`

3. **提示词没有要求**
   - `packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts`
   - 拆分计划的提示词没有明确要求填写 `requirement_refs`

### 原因2：Agent 拆分时疏忽

即使工具支持，Agent 在编写拆分计划时也需要：
- 为每个任务明确声明 `requirement_refs: ["FR-1", "FR-4"]`
- 确保每个功能点至少被一个任务接收
- 但当前的拆分计划中没有这个字段

---

## 🔧 完整解决方案

### 修复1：补充 schema 定义

**文件**：`packages/web/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts`

```typescript
// plan 模式的 tasks schema
tasks: {
  type: 'array',
  items: {
    type: 'object',
    properties: {
      key: { type: 'string' },
      title: { type: 'string' },
      
      // ✅ 新增：requirement_refs 字段（必填）
      requirement_refs: {
        type: 'array',
        items: { type: 'string' },
        description: '本任务实现的功能点编号（如 ["FR-1", "FR-4"]）。' +
                     '每个功能点至少要被一个任务接收。' +
                     '覆盖门禁会检查：所有 FR-N 都至少出现在一个任务的 requirement_refs 里'
      },
      
      stages: { type: 'array', items: { type: 'string' } },  // ← 之前的修复
      phase: { type: 'string' },
      side: { type: 'string' },
      depends_on: { type: 'array', items: { type: 'string' } },
      acceptance: { type: 'string' },
      implementation: { type: 'string' },
    }
  }
}
```

### 修复2：Decompose 用例处理

**文件**：`packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`

```typescript
const child: TaskRecord = {
  id,
  requirementId: target.id,
  title: task.title.slice(0, 120),
  // ...
  
  // ✅ 新增：从 task.requirement_refs 读取
  requirement_refs: task.requirement_refs ?? [],  // 默认空数组
  
  stages: task.stages ?? undefined,
  // ...
}
```

### 修复3：提示词更新

**文件**：`packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts`

```typescript
+ '- requirement_refs（必填数组）：本任务实现的功能点编号。'
+ '  例如：["FR-1", "FR-4"]'
+ '  覆盖门禁：每个功能点至少要被一个任务接收，否则拆分被拒。'
+ '  RTM 对照表只是参考，真正生效的是每个任务定义里的 requirement_refs。'
```

### 修复4：覆盖门禁（Coverage Gate）

**文件**：`packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`

在落库前增加检查：

```typescript
// 检查覆盖率：每个 FR-N 至少被一个任务接收
const allFRs = new Set<string>()
// 从需求文档提取 FR-1 到 FR-9（或读取 requirement.functionalRequirements）
for (let i = 1; i <= 9; i++) {
  allFRs.add(`FR-${i}`)
}

const coveredFRs = new Set<string>()
for (const task of draft) {
  for (const fr of task.requirement_refs ?? []) {
    coveredFRs.add(fr)
  }
}

const uncovered = [...allFRs].filter(fr => !coveredFRs.has(fr))
if (uncovered.length > 0) {
  reject(
    `拆分计划覆盖不完整：功能点 ${uncovered.join(', ')} 未被任何任务接收。` +
    `每个任务的 requirement_refs 必须声明它实现了哪些功能点。`,
    'REQBOARD_INCOMPLETE_COVERAGE'
  )
}
```

---

## 🚑 立即修复（当前需求）

### 步骤1：手动补充 requirement_refs

根据 decomposition.md 的 RTM 对照表，手动更新数据库：

```bash
cd .dsh-data

# 备份
cp dsh-reqboard.json dsh-reqboard.json.backup

# 使用 jq 更新（示例）
jq '
  .tasks |= map(
    if .id == "t-cda91b" then
      . + {requirement_refs: ["FR-3", "FR-4", "FR-9"]}
    elif .id == "t-54d646" then
      . + {requirement_refs: ["FR-3"]}
    elif .id == "t-6a1ad6" then
      . + {requirement_refs: ["FR-1"]}
    # ... 其他任务类似
    else
      .
    end
  )
' dsh-reqboard.json > tmp.json && mv tmp.json dsh-reqboard.json
```

**完整映射**（从 RTM 表提取）：
```
t1 (t-cda91b 领域类型定义) → ["FR-3", "FR-4", "FR-9"]
t2 (t-54d646 台账迁移) → ["FR-3"]
t3 (t-6a1ad6 DSH jobs 适配器) → ["FR-1"]
t4 (t-69b7c1 workflow schema 适配器) → ["FR-7"]
t5 (t-7cdbbd 写集冲突检测) → ["FR-4"]
t6 (t-29de13 批调度器) → ["FR-4"]
t7 (t-f750de 孤儿回收) → ["FR-5"]
t8 (t-8fc069 checkpoint 管理器) → ["FR-3"]
t9 (t-89953c 后台执行器) → ["FR-1", "FR-3", "FR-4", "FR-5"]
t10 (t-1cbdd7 投递用例) → ["FR-1"]
t11 (t-b1fe76 查询用例) → ["FR-2"]
t12 (t-7f957a 仓储层扩展) → ["FR-3", "FR-5", "FR-9"]
t13 (t-dc5b58 AdvanceChain 改造) → ["FR-1", "FR-6"]
t14 (t-3c54fb ExecuteTask 改造) → ["FR-7"]
t15 (t-9e3b7b 选择器改造) → ["FR-5"]
t16 (t-182606 workflow script 改造) → ["FR-7"]
t17 (t-69ab2a reqboard_task_run 改造) → ["FR-1"]
t18 (t-c031de reqboard_run_status 新增) → ["FR-2", "FR-9"]
t19 (t-301eee 工具注册与提示词) → ["FR-1", "FR-2"]
t20 (t-dcc586 集成测试) → ["FR-6"]
t21 (t-966b43 E2E 测试) → ["FR-1", "FR-2", "FR-3", "FR-4", "FR-5", "FR-6", "FR-7", "FR-9"]
t22 (t-b37ffb 构建验证) → ["FR-8"]
t23 (t-97f31d 部署验证) → ["FR-8"]
```

### 步骤2：更新需求文档的接收状态

```bash
cd docs/requirements/REQ-260925110957-552d

# 需求文档会自动更新（通过 syncRequirementMarks）
# 或手动触发更新
```

### 步骤3：验证覆盖

```bash
# 检查每个 FR 是否都有任务接收
cd .dsh-data
for fr in FR-1 FR-2 FR-3 FR-4 FR-5 FR-6 FR-7 FR-8 FR-9; do
  count=$(jq "[.tasks[] | select(.requirementId == \"REQ-260925110957-552d\" and (.requirement_refs // []) | contains([\"$fr\"]))] | length" dsh-reqboard.json)
  echo "$fr: $count 个任务接收"
done
```

预期结果：每个 FR 至少1个任务接收。

---

## 📊 修复前后对比

### Before（当前问题）
```
拆分计划：
- 23 个任务定义
- ❌ 所有任务 requirement_refs = []
- ❌ 所有功能点显示"未被接收"

验收：
- ❌ 无法生成功能点验收项
- ❌ 验收人说"拆分有问题"
- ❌ Agent 试图修改验收标准
```

### After（修复后）
```
拆分计划：
- 23 个任务定义
- ✅ 每个任务声明 requirement_refs
- ✅ 所有功能点都被接收
- ✅ 覆盖门禁通过

验收：
- ✅ 自动生成功能点验收项
- ✅ 验收人逐项检查 FR-1 到 FR-9
- ✅ 全部通过后自动归档
```

---

## 🎯 总结

### 拆分的三个致命缺陷

1. **❌ 没有声明 `stages`** → 任务无子卡 → 链停滞
2. **❌ 没有声明 `requirement_refs`** → 功能点未接收 → 验收失败
3. **❌ 自动开跑时机错误** → 批准回调触发 → REQBOARD_DRIVER_REQUIRED

### 完整修复清单

| 问题 | 短期修复 | 长期修复 |
|------|---------|---------|
| 链停滞 | 手动补 stages | schema 增加 stages + 提示词 |
| 功能点未接收 | 手动补 requirement_refs | schema 增加 + 覆盖门禁 |
| 自动开跑失败 | — | 移除 confirm-settle 自动开跑 |
| 验收卡住 | 手动调用 reqboard_submit | 补充 accepting.txt |

### 关键原则

1. **拆分计划必须完整**：stages + requirement_refs + acceptance + implementation
2. **覆盖门禁必须有**：确保每个功能点都被接收
3. **验收基于功能点**：不是基于任务完成数，而是基于 FR 覆盖
4. **不能修改标准**：发现拆分有问题应该修复拆分，而不是降低标准
