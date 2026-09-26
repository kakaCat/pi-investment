# REQ-260925110957-552d 拆分问题分析与解决方案

## 问题诊断总结

### 问题1：拆分阶段反复退回（design ↔ decomposing）

**时间线**：
- 03:52 - 进入 decomposing
- 04:39 - 退回 design（REQBOARD_DRIVER_REQUIRED）
- 04:40 - 再次进入 decomposing
- 05:12 - 成功进入 implementing

**根因**：
`confirm-settle.ts` 在批准弹框回调中尝试"自动开跑"（触发推进事件），但：
- 批准弹框回调不在 agent 的 live driver 回合内
- SessionProbeAdapter 检查失败 → REQBOARD_DRIVER_REQUIRED
- 系统退回 design 重新调整

### 问题2：实施阶段链停滞（批次之间无法推进）

**现状**：
- 前10个任务 done
- 第11个任务（t-b1fe76, t-7f957a）永久卡在 todo
- 没有 in_progress 任务

**根因**：
1. **拆分时没有声明 `stages` 字段**
   - 23个任务都是普通任务（无 stages）
   - expandSubtasks 读不到 stages → 返回空数组
   - 父卡开工但没有子卡

2. **选择器只认父子结构**
   - selectAdvanceEvent 只会选择：
     - FINALIZE_PARENT（收尾有子卡的父卡）
     - RUN_SUBTASK（执行子卡）
     - OPEN_PARENT（开新父卡）
   - **没有"执行普通任务"的逻辑**
   - 普通 todo 任务永远不会被选中

3. **前10个任务"莫名其妙"完成**
   - 可能是手动推进
   - 或者有其他机制（待确认）

## 完整解决方案

### 方案架构：三层修复

```
┌─────────────────────────────────────────────────────┐
│ 第1层：拆分时声明 stages（混合模式）                  │
│ - Agent 规划时为每个任务声明 stages                  │
│ - reqboard_decompose 落库时写入 stages 字段         │
│ - 人批准时能看到任务的阶段划分                       │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ 第2层：移除 confirm-settle 的自动开跑                │
│ - 只设置 autoRun = true                             │
│ - 不在批准回调中触发推进                             │
│ - 让 agent 在下一回合自己调用                        │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│ 第3层：scanAndResume 保底机制                        │
│ - 定期扫描 autoRun=true 且未完成的需求              │
│ - 自动触发 advanceRequirement 继续推进              │
│ - 防止链永久停滞                                     │
└─────────────────────────────────────────────────────┘
```

---

## 修改清单

### 修改1：拆分计划 schema 增加 stages 字段

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
      
      // ✅ 新增：stages 字段（可选，但强烈建议）
      stages: {
        type: 'array',
        items: { 
          type: 'string',
          enum: ['analysis', 'doc', 'ui', 'implement', 'integrate', 'test', 'review', 'merge']
        },
        description: '任务阶段列表（父卡开工时懒展开子卡）。常见组合：["implement","test"] / ["implement","integrate","test"] / ["doc"]'
      },
      
      phase: { type: 'string' },
      side: { type: 'string' },
      depends_on: { type: 'array', items: { type: 'string' } },
      acceptance: { type: 'string' },
      implementation: { type: 'string' },
    }
  }
}
```

**提示词更新**：`packages/web/dsh-pmboard/src/tools/SubmitTool/prompt.ts`

```typescript
// kind=plan 的说明中增加：
"- stages（可选数组）：任务阶段列表，父卡开工时懒展开子卡。建议：
  - 纯代码任务：['implement', 'test']
  - 需要联调：['implement', 'integrate', 'test']
  - 复杂任务：['analysis', 'implement', 'test', 'review']
  - 纯文档：['doc']
  - 不填 stages = 普通任务（不展开子卡，需手动推进）"
```

---

### 修改2：reqboard_decompose 处理 stages 字段

**文件**：`packages/web/dsh-pmboard/src/application/use-cases/Decompose.ts`

**位置**：创建 TaskRecord 时（约第150-200行）

```typescript
const child: TaskRecord = {
  id,
  requirementId: target.id,
  title: task.title.slice(0, 120),
  description: task.description,
  phase: task.phase,
  side: task.side,
  dependsOn: mappedDeps,
  scope: asScope(task.scope ?? {}),
  
  // ✅ 新增：从 task.stages 读取并写入
  stages: task.stages ?? undefined,  // 保留 undefined（而非空数组），以区分"未声明"和"空阶段"
  
  acceptance: normalizeText(task.acceptance, true),
  implementation: normalizeText(task.implementation, true),
  context: normalizeText(task.context, false),
  parentId: undefined,
  attempt: 0,
  revisions: [],
  status: 'todo',
  blocked: false,
  executions: [],
  comments: [],
  version: 1,
  createdAt: nowTs,
  updatedAt: nowTs,
  createdBy: actor,
  updatedBy: actor,
  statusHistory: [],
}
```

---

### 修改3：移除 confirm-settle 的自动开跑

**文件**：`packages/web/dsh-pmboard/src/application/internal/confirm-settle.ts`

**修改前**（约第200-230行）：
```typescript
// 2026-09-21 用户裁定：拆分计划挪到**拆分阶段**提交与批准——
// 本块在 from=decomposing 时生效：先落章 decomposition 产物（拆分计划本体）→
// 自动落库任务卡 → 自动进实施 + autoRun=true → 触发首个推进事件，中途不再打断。
if (from === 'decomposing' && to === 'implementing') {
  // ... 落库任务的代码 ...
  
  // ❌ 删除这段：
  req.autoRun = true
  req.comments.push({
    body: '[自动开跑] 批准拆分计划 → 自动拆分 N 张卡 → 自动进入实施（autoRun=true），触发首个推进事件'
  })
  // 然后触发推进...
}
```

**修改后**：
```typescript
// 批准拆分计划后：落库任务 + 开启自动链开关，但不立即触发推进。
// 推进由 agent 在下一回合调用 reqboard_task_run 或通过 scanAndResume 自动触发。
if (from === 'decomposing' && to === 'implementing') {
  // ... 落库任务的代码保持不变 ...
  
  // ✅ 只设置开关，不触发推进
  req.autoRun = true
  req.comments.push({
    id: deps.ids.comment(),
    body: fmt(
      '[自动链] 批准拆分计划 → 落库 {n} 张任务卡 → 进入实施（autoRun=true）。' +
      '推进由 agent 调用 reqboard_task_run 触发，或由 scanAndResume 保底扫描自动触发',
      { n: createdCount }
    ),
    createdAt: nowTs,
    createdBy: actor,
  })
  
  // ❌ 不在这里触发推进（会遇到 REQBOARD_DRIVER_REQUIRED）
  // agent 在下一回合看到需求状态=implementing + autoRun=true，会自己调用 reqboard_task_run
}
```

---

### 修改4：Agent 提示词引导

**文件**：`packages/web/dsh-pmboard/src/infrastructure/prompts/implementing.txt`

**新增段落**：
```
## 拆分后的首次推进

需求刚进入 implementing 且 autoRun=true 时：
1. 调用 reqboard_task_run 触发首个推进事件（"推倒第一张骨牌"）
2. 后续推进由 advanceRequirement 自动链接执行
3. 无需每次手动调用——链会自己跑，直到 ROLLUP 或 PAUSE

示例：
```typescript
// 看到需求刚进 implementing
reqboard_task_run({ task_id: '<第一个ready任务>' })
// → 触发自动链 → 后续自动推进
```

注意：投递后立即返回（dispatched/running + job_id），跑完由通知唤醒。
不要在一个回合内反复调用——每个父卡的子卡链是后台任务，会自动执行完。
```

---

### 修改5：scanAndResume 保底机制

**文件**：`packages/web/dsh-pmboard/src/application/use-cases/AdvanceChain.ts`

**位置**：在 scanAndResume 函数中（约第344-360行）

**修改前**：
```typescript
export async function scanAndResume(deps: UseCaseDeps): Promise<AdvanceOutcome[]> {
  const snapshot = deps.repo.snapshot()
  const candidates = snapshot.requirements.filter(
    (r: RequirementRecord) => r.autoRun === true && !TERMINAL_REQ.has(r.status),
  )
  const out: AdvanceOutcome[] = []
  for (const req of candidates) {
    const result = await advanceRequirement(deps, req.id, undefined)
    out.push(result)
  }
  return out
}
```

**修改后**（增加日志和错误处理）：
```typescript
/** 启动恢复扫描（崩溃不丢链）：autoRun=true 且未到验收态的需求 → 续跑下一个事件。 */
export async function scanAndResume(deps: UseCaseDeps): Promise<AdvanceOutcome[]> {
  const snapshot = deps.repo.snapshot()
  const candidates = snapshot.requirements.filter(
    (r: RequirementRecord) => r.autoRun === true && !TERMINAL_REQ.has(r.status),
  )
  
  // ✅ 增加：日志记录扫描到的需求
  if (candidates.length > 0) {
    console.log(`[scanAndResume] 发现 ${candidates.length} 个需要推进的需求：`, 
      candidates.map(r => `${r.id}(${r.status})`))
  }
  
  const out: AdvanceOutcome[] = []
  for (const req of candidates) {
    try {
      const result = await advanceRequirement(deps, req.id, undefined)
      out.push(result)
      
      // ✅ 增加：记录推进结果
      console.log(`[scanAndResume] ${req.id} 推进完成：${result.steps.length} 步，停止原因=${result.stopped}`)
    } catch (err) {
      // ✅ 增加：错误处理，不因单个需求失败而中断整个扫描
      console.error(`[scanAndResume] ${req.id} 推进失败：`, err)
      out.push({
        requirementId: req.id,
        steps: [],
        stopped: 'error',
      })
    }
  }
  return out
}
```

**定时调用**（可选，如果需要的话）：
```typescript
// 在插件启动时注册定时扫描（每5分钟）
ctx.setInterval(async () => {
  try {
    const results = await scanAndResume(deps)
    if (results.length > 0) {
      console.log('[定时扫描] 推进了', results.length, '个需求')
    }
  } catch (err) {
    console.error('[定时扫描] 失败：', err)
  }
}, 5 * 60 * 1000)  // 5分钟
```

---

### 修改6：decomposition.md 模板更新

**文件**：拆分文档模板（Agent 生成时参考）

```markdown
## 任务清单

每个任务必须包含以下字段：

| 字段 | 说明 | 示例 |
|------|------|------|
| key | 任务引用键 | t1, t2 |
| title | 任务标题 | 领域类型定义 |
| **stages** | **阶段列表（必填）** | ["implement", "test"] |
| dependsOn | 依赖的任务 key | [t1] |
| acceptance | 验收标准（可证伪） | 单测全绿，覆盖率>80% |
| implementation | 实施方案 | 新增 domain/write-set.ts... |

### stages 字段说明

**必须填写**，决定父卡开工时创建哪些子卡：

- **纯代码任务**：`["implement", "test"]`
  - 适用：新增模块、工具函数、领域逻辑
  
- **需要联调**：`["implement", "integrate", "test"]`
  - 适用：跨模块改造、API 集成
  
- **复杂任务**：`["analysis", "implement", "test", "review"]`
  - 适用：重构、架构变更
  
- **纯文档**：`["doc"]`
  - 适用：文档编写、注释补充

**不填 stages = 错误配置**，会导致链停滞！

### 任务示例

```json
{
  "key": "t1",
  "title": "领域类型定义",
  "stages": ["implement", "test"],
  "dependsOn": [],
  "acceptance": "类型定义完整，domain/ 下单测全绿",
  "implementation": "新增 domain/write-set.ts、domain/job-spec.ts、domain/checkpoint.ts"
}
```
```

---

## 实施步骤

### 阶段1：修复当前需求（REQ-260925110957-552d）

**步骤1：手动补 stages**
```bash
# 进入数据库手动修改
cd .dsh-data
cp dsh-reqboard.json dsh-reqboard.json.backup

# 用 jq 为所有该需求的任务添加 stages
jq '
  .tasks |= map(
    if .requirementId == "REQ-260925110957-552d" and .stages == null then
      . + {stages: ["implement", "test"]}
    else
      .
    end
  )
' dsh-reqboard.json > dsh-reqboard.json.tmp
mv dsh-reqboard.json.tmp dsh-reqboard.json
```

**步骤2：重启自动链**
```typescript
// 在 agent 会话中调用
reqboard_task_run({ task_id: 't-b1fe76' })  // 第11个任务
```

---

### 阶段2：代码修改（按清单）

1. **修改1**：SubmitTool schema 增加 stages
2. **修改2**：Decompose.ts 处理 stages
3. **修改3**：confirm-settle.ts 移除自动开跑
4. **修改4**：implementing.txt 提示词引导
5. **修改5**：scanAndResume 增强
6. **修改6**：文档模板更新

**验证**：
```bash
# 单测
cd packages/web/dsh-pmboard
npx vitest run

# 类型检查
npx tsc --noEmit

# 构建
pnpm build
```

---

### 阶段3：回归测试

**测试场景1：新需求拆分**
1. 创建测试需求
2. 编写拆分计划（包含 stages）
3. 批准计划
4. 验证：
   - ✅ 不退回 design
   - ✅ 成功进入 implementing
   - ✅ autoRun = true

**测试场景2：任务执行**
1. 调用 reqboard_task_run
2. 验证：
   - ✅ 父卡开工
   - ✅ 创建子卡
   - ✅ 子卡执行
   - ✅ 父卡收尾
   - ✅ 自动推进下一个

**测试场景3：链恢复**
1. 中途停止 agent
2. 重启
3. 验证：
   - ✅ scanAndResume 触发
   - ✅ 链继续推进

---

## 预期效果

### Before（当前问题）
```
拆分 → 批准 → confirm-settle 自动开跑 → REQBOARD_DRIVER_REQUIRED
      → 退回 design → 手动推进 → 再次拆分 → 成功进入 implementing
      → 任务无 stages → expandSubtasks 返回空 → 选择器找不到事件
      → 链停滞 → 人工干预
```

### After（修复后）
```
拆分 → 声明 stages → 批准 → confirm-settle 设置 autoRun=true
      → agent 下一回合调用 reqboard_task_run 
      → 父卡开工 → expandSubtasks 读取 stages → 创建子卡
      → 子卡执行 → 父卡收尾 → 选择器找到下一个事件
      → 自动推进 → 直到 ROLLUP → 进入验收
```

---

## 风险评估

### 低风险
- ✅ schema 增加可选字段（向后兼容）
- ✅ 移除有问题的自动开跑（减少复杂度）
- ✅ scanAndResume 增强（只是加日志）

### 中风险
- ⚠️ 提示词变更：需要 agent 学习新的拆分规范
- ⚠️ 模板变更：历史文档可能不含 stages

**缓解措施**：
- 提示词中保留"不填 stages 的后果"警告
- expandSubtasks 对无 stages 的容错（按需求类型推导）

### 无风险
- 不影响已完成的需求
- 不改变核心推进逻辑
- 保持向后兼容

---

## 总结

### 三层修复的协同

1. **第1层（stages）**：解决"任务无子卡"问题
2. **第2层（移除自动开跑）**：解决"拆分反复退回"问题  
3. **第3层（scanAndResume）**：解决"链意外停滞"的保底

三层共同作用，形成：
- ✅ 拆分时规划完整（有 stages）
- ✅ 批准后平滑进入（不报错退回）
- ✅ 执行中自动推进（有子卡可执行）
- ✅ 意外中断可恢复（保底扫描）

### 关键原则

1. **声明式优于推导式**：stages 显式声明，不靠隐式规则
2. **Agent 驱动优于回调驱动**：推进由 agent 主动触发，不在弹框回调中
3. **保底机制优于完美逻辑**：scanAndResume 兜底，防止链永久停滞
