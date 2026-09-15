# pmboard 优化实施方案 - 完整版

## 目标

让 agent 在执行任务时：
1. 知道要做什么（任务卡 = 执行指令）✅ 已完成
2. 自动汇报做了什么（任务完成 hook）⬅️ 要做这个
3. 人能看到整体进度（Goal 跟踪）⬅️ 然后做这个

---

## 已完成 ✅

### 1. SystemPrompt 注入任务执行指引
- **位置**：`packages/pages/dsh-pmboard/src/host/capture.ts`
- **修改**：`boundSectionText` 函数
- **效果**：implementing 阶段，agent 看到当前 in_progress 任务的：
  - 任务说明（description）
  - 需求背景（context）
  - 验收标准（acceptance）
  - 阶段/端侧（phase/side）

### 2. 项目全景工具
- **位置**：`packages/pages/dsh-pmboard/src/host/agent-tools.ts`
- **新增工具**：
  - `reqboard_overview`: 查看所有进行中需求、任务进度
  - `reqboard_task_detail`: 查看任务详情

---

## 待实施

### Phase 1: 任务完成汇报 Hook（核心，2-3小时）

#### 1.1 扩展数据结构

**文件**：`packages/pages/dsh-pmboard/src/shared/protocol.ts`

```typescript
// 扩展 TaskRecord
interface TaskRecord {
  // ... 现有字段
  
  // 新增：完成报告
  completionReport?: {
    summary: string              // 一句话总结
    completed: string[]          // 完成了什么
    filesChanged: string[]       // 改了哪些文件
    nextStep?: string            // 下一步（给下个任务的提示）
    reportedAt: number           // 汇报时间
    reportedBy: ActorRef         // 谁汇报的
  }
}

// 扩展 RequirementRecord
interface RequirementRecord {
  // ... 现有字段
  
  // 新增：Goal 跟踪
  goal?: {
    objective: string            // 目标（立项时的 title）
    completedContent: string[]   // 累积完成的内容
    phases: {
      phase: string
      completedAt?: number
      deliverables: string[]
    }[]
  }
}
```

#### 1.2 实现任务完成 Hook

**文件**：`packages/pages/dsh-pmboard/src/host/rollup.ts`

```typescript
// 在 rollup 的任务状态变更处理中增加

async function handleTaskCompletion(
  task: TaskRecord,
  requirement: RequirementRecord,
  ctx: Context
) {
  // 1. 检查：任务刚推进到 done 且没有完成报告
  if (task.status !== 'done' || task.completionReport) {
    return
  }
  
  // 2. 触发 hook：通知 agent 需要汇报
  // 方式 A：通过 SystemPrompt 注入（静默式）
  // 方式 B：通过 ask_user_question 弹框（主动式）
  
  // 推荐方式 B：主动弹框
  const questions = [{
    id: 'task_completion_summary',
    header: '任务完成汇报',
    question: `任务「${task.title}」已完成，请总结你做了什么：`,
    // 不给选项，让 agent 自己输入
  }]
  
  // 注意：这里的问题是"谁来调用 ask_user_question"？
  // rollup 是后台自动执行的，不在 agent 的执行上下文中
  
  // 解决方案：在 SystemPrompt 中注入"等待汇报"提示
}
```

**问题**：rollup 是后台自动执行，不能直接调用 `ask_user_question`

**解决方案**：通过 SystemPrompt 注入"待汇报"提示

#### 1.3 SystemPrompt 注入待汇报提示

**文件**：`packages/pages/dsh-pmboard/src/host/capture.ts`

```typescript
// 在 boundSectionText 中增加

export function boundSectionText(ledger: ReqboardLedger, context: unknown): string {
  // ... 现有逻辑
  
  // 检查是否有刚完成但未汇报的任务
  const completedNoReport = ledger.tasks.filter(t => 
    open.some(r => r.id === t.requirementId) &&
    t.status === 'done' &&
    !t.completionReport
  )
  
  if (completedNoReport.length > 0) {
    const task = completedNoReport[0]
    lines.push('## 【任务完成待汇报】')
    lines.push('')
    lines.push(`任务「${task.title}」已完成，请调用 reqboard_task_report 汇报：`)
    lines.push('')
    lines.push('reqboard_task_report({')
    lines.push(`  task_id: '${task.id}',`)
    lines.push('  summary: "一句话总结你做了什么",')
    lines.push('  completed: ["✅ 完成项1", "✅ 完成项2"],')
    lines.push('  files_changed: ["文件路径 (新增/修改 XX 行)"]')
    lines.push('})')
    lines.push('')
  }
  
  // ... 其余逻辑
}
```

#### 1.4 创建 reqboard_task_report 工具

**文件**：`packages/pages/dsh-pmboard/src/host/agent-tools.ts`

```typescript
ctx.tools.register(defineTool({
  name: 'reqboard_task_report',
  description: '任务完成汇报：记录你做了什么、改了哪些文件',
  parameters: {
    task_id: { type: 'string', required: true },
    summary: { type: 'string', description: '一句话总结', required: true },
    completed: { type: 'array', items: { type: 'string' }, required: true },
    files_changed: { type: 'array', items: { type: 'string' }, required: false },
    next_step: { type: 'string', required: false }
  },
  execute: async (args, exec) => {
    const windowKey = agentIdFromExec(exec)
    const nowTs = deps.now()
    
    // 1. 写入任务的 completionReport
    const result = await deps.store.mutate('task_report', (ledger) => {
      const task = ledger.tasks.find(t => t.id === args.task_id)
      if (!task) reject('任务不存在', 'TASK_NOT_FOUND')
      if (task.status !== 'done') reject('只能为已完成的任务汇报', 'TASK_NOT_DONE')
      
      task.completionReport = {
        summary: args.summary,
        completed: args.completed,
        filesChanged: args.files_changed || [],
        nextStep: args.next_step,
        reportedAt: nowTs,
        reportedBy: { kind: 'agent', sessionId: windowKey }
      }
      
      // 2. 累积到需求的 goal.completedContent
      const req = ledger.requirements.find(r => r.id === task.requirementId)
      if (req) {
        if (!req.goal) {
          req.goal = {
            objective: req.title,
            completedContent: [],
            phases: []
          }
        }
        req.goal.completedContent.push(`✅ ${task.title}: ${args.summary}`)
      }
      
      return { tasks: [task], requirements: req ? [req] : [] }
    })
    
    return {
      success: true,
      task_id: args.task_id,
      message: '任务完成报告已记录'
    }
  }
}))
```

---

### Phase 2: Goal 进度跟踪（1-2小时）

#### 2.1 Goal 状态工具

**文件**：`packages/pages/dsh-pmboard/src/host/agent-tools.ts`

```typescript
ctx.tools.register(defineTool({
  name: 'reqboard_goal_status',
  description: '查看需求的 Goal 进度：完成了哪些内容',
  parameters: {
    requirement_id: { type: 'string', required: false }
  },
  execute: async (args, exec) => {
    const windowKey = agentIdFromExec(exec)
    const snapshot = deps.store.snapshot()
    
    // 找到目标需求
    let req: RequirementRecord | undefined
    if (args.requirement_id) {
      req = snapshot.requirements.find(r => r.id === args.requirement_id)
    } else {
      // 当前窗口的需求
      req = snapshot.requirements.find(r => 
        r.sourceSessionId === windowKey &&
        isOpenReq(r)
      )
    }
    
    if (!req) {
      return { hasRequirement: false }
    }
    
    return {
      requirement: req.id,
      objective: req.goal?.objective || req.title,
      status: req.status,
      completedContent: req.goal?.completedContent || [],
      phases: req.goal?.phases || [],
      summary: `已完成 ${req.goal?.completedContent?.length || 0} 项内容`
    }
  }
}))
```

#### 2.2 在验收时自动生成总结

**文件**：`packages/pages/dsh-pmboard/src/host/agent-tools.ts`

修改 `reqboard_verify_submit` 工具：

```typescript
// 在验收提交时，自动从 goal.completedContent 生成摘要
const completedSummary = req.goal?.completedContent?.join('\n') || '（无完成记录）'

// 添加到验收材料的 summary 中
```

---

### Phase 3: 集成与测试（1小时）

#### 3.1 验证流程

1. 创建需求 → 自动初始化 goal
2. 拆分任务
3. 完成任务 → SystemPrompt 提示汇报 → agent 调用 reqboard_task_report
4. 查看 reqboard_goal_status → 看到累积的完成内容
5. 验收时自动包含完成内容

#### 3.2 测试用例

```typescript
// 测试任务汇报
reqboard_task_report({
  task_id: 't-001',
  summary: '登录 API 已实现',
  completed: [
    '✅ 创建 POST /api/auth/login',
    '✅ 实现 JWT token 生成',
    '✅ 单元测试覆盖率 85%'
  ],
  files_changed: ['src/routes/auth.ts (新增 120 行)']
})

// 测试 Goal 查询
reqboard_goal_status()
// 应该看到累积的完成内容
```

---

## 实施顺序

### 立即做（今天，3小时）

1. ✅ 扩展数据结构（protocol.ts）- 30分钟
2. ✅ 创建 reqboard_task_report 工具 - 1小时
3. ✅ SystemPrompt 注入"待汇报"提示 - 30分钟
4. ✅ 测试完整流程 - 1小时

### 明天做（1小时）

5. ✅ 创建 reqboard_goal_status 工具 - 30分钟
6. ✅ 集成到验收流程 - 30分钟

---

## 关键设计决策

### 1. 为什么不用 Hook 自动弹框？

**问题**：rollup 是后台执行，不在 agent 的交互上下文中

**解决**：通过 SystemPrompt 注入提示 + 提供工具

### 2. 为什么需要 reqboard_task_report 工具？

**作用**：
- 记录任务完成内容（供验收查看）
- 累积到 Goal（整体进度）
- 明确的汇报动作（人机回路）

### 3. completionReport 放在哪？

**数据结构**：`TaskRecord.completionReport`
- 每个任务独立记录
- 可以单独查看某个任务做了什么
- 自动累积到需求的 goal.completedContent

---

## 预期效果

### Before（当前）
```
Agent: 任务完成
      reqboard_task_move(to='done')
      
User:  ？？？做了什么？
```

### After（优化后）
```
Agent: 任务完成
      reqboard_task_move(to='done')
      
SystemPrompt: 【任务完成待汇报】请调用 reqboard_task_report

Agent: reqboard_task_report({
        summary: '登录 API 已实现',
        completed: ['✅ 创建接口', '✅ 测试通过'],
        files_changed: ['src/routes/auth.ts']
      })
      
User: 在 reqboard_goal_status 中看到：
      ✅ 任务A: 登录 API 已实现
      ✅ 任务B: 登录页面已完成
      ...
```

---

**开始实施？**
