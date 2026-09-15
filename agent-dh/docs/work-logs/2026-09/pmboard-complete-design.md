# pmboard 完整流程设计 - Goal + Workflow + 人机回路

> 参考：Superpowers (obra) 的 Goal/Workflow/人机回路机制

## 架构概览

```
Requirement (Goal 层)
  ├─ status: 粗粒度阶段
  ├─ phases: 阶段记录（完成了什么）
  └─ tasks: Workflow 单元
      ├─ 执行指令（description/acceptance/context）
      ├─ 状态流转（in_progress → integrating → testing → in_review → done）
      └─ 人机回路（完成后汇报，等待确认）
```

---

## 1. Goal 层（Requirement）

### 数据结构增强

```typescript
interface RequirementRecord {
  // ... 现有字段
  
  // 新增：Goal 跟踪
  goal?: {
    objective: string              // 目标
    phases: PhaseRecord[]          // 阶段完成记录
    humanCheckpoints: string[]     // 人工确认点
    completedContent: string[]     // 完成了哪些内容（累积）
  }
}

interface PhaseRecord {
  phase: 'requirement-analysis' | 'technical-design' | 'implementing' | 'verifying' | 'archiving'
  startedAt: number
  completedAt?: number
  deliverables: string[]           // 本阶段产出
  humanApproved?: boolean          // 是否通过人工确认
  approvedAt?: number
  note: string                     // 阶段总结
}
```

### Goal 工具

```typescript
// 创建 Goal（立项时自动创建）
reqboard_goal_create({
  requirement_id: 'REQ-xxx',
  objective: '实现用户登录功能',
  phases: ['requirement-analysis', 'technical-design', 'implementing', 'verifying', 'archiving']
})

// 完成阶段（自动记录）
reqboard_goal_complete_phase({
  requirement_id: 'REQ-xxx',
  phase: 'requirement-analysis',
  deliverables: ['需求文档', '技术方案草稿'],
  note: '与用户讨论确认了需求边界和功能范围'
})

// 查看 Goal 进度
reqboard_goal_status({
  requirement_id: 'REQ-xxx'
})
// 返回：
{
  objective: '实现用户登录功能',
  currentPhase: 'implementing',
  completedPhases: ['requirement-analysis', 'technical-design'],
  completedContent: [
    '✅ 需求文档（docs/requirements/REQ-xxx/requirement.md）',
    '✅ 技术设计文档（docs/requirements/REQ-xxx/design.md）',
    '🔄 实施中：3/5 任务完成'
  ],
  nextCheckpoint: 'implementing → verifying（等待所有任务完成）'
}
```

---

## 2. Workflow 层（Task）

### 当前已有（无需改动）

```typescript
interface TaskRecord {
  title: string            // 任务名
  description: string      // 执行指令
  context: string          // 背景
  acceptance: string       // 验收标准
  status: TaskStatus       // in_progress → integrating → testing → in_review → done
}
```

### Workflow 执行模式（已通过 SystemPrompt 实现）

1. **自动注入**：implementing 阶段，SystemPrompt 自动注入当前 in_progress 任务
2. **Agent 执行**：按 description 执行
3. **状态推进**：完成后调 `reqboard_task_move`
4. **人机回路**：⭐ 这里需要增强

---

## 3. 人机回路（参考 Superpowers）

### 3.1 完成汇报机制

**当前问题**：Agent 完成任务后只是推进状态，**没有向人汇报做了什么**

**解决方案**：任务完成时自动生成汇报

```typescript
// 新工具：reqboard_task_report
reqboard_task_report({
  task_id: 't-001',
  summary: '登录 API 已实现',
  completed: [
    '✅ 创建 POST /api/auth/login 接口',
    '✅ 实现 JWT token 生成',
    '✅ 添加登录日志记录',
    '✅ 单元测试覆盖率 85%'
  ],
  files_changed: [
    'src/routes/auth.ts (新增 120 行)',
    'tests/auth.test.ts (新增 80 行)'
  ],
  next_step: '准备进入联调阶段，需要前端配合测试接口'
})

// 自动触发：
// 1. 更新任务状态为 integrating
// 2. 发送飞书通知给用户
// 3. 记录到 Goal 的 completedContent
```

### 3.2 人工确认点

**关键阶段需要人确认**：

```typescript
// 需求分析完成 → 等待人确认
{
  phase: 'requirement-analysis',
  deliverable: 'requirement.md',
  humanCheckpoint: true,
  notification: {
    title: '【需求分析完成】用户登录功能',
    content: '已完成需求讨论并生成需求文档，请确认：\n- 需求文档：docs/requirements/REQ-xxx/requirement.md\n- 涉及模块：登录 API + 登录页面\n- 预计工作量：5 个任务，约 2-3 天',
    actions: ['✅ 确认继续', '📝 需要修改', '❌ 取消']
  }
}

// 技术设计完成 → 等待人确认
{
  phase: 'technical-design',
  deliverable: 'design.md',
  humanCheckpoint: true,
  notification: {
    title: '【技术设计完成】用户登录功能',
    content: '技术设计方案：\n- 新增接口：POST /api/auth/login\n- 新增表：users, login_logs\n- 前端页面：LoginPage.vue\n\n请在项目看板点「批准计划」',
    actions: ['✅ 批准计划', '📝 需要调整']
  }
}

// 所有任务完成 → 等待验收
{
  phase: 'implementing',
  allTasksDone: true,
  humanCheckpoint: true,
  notification: {
    title: '【开发完成】用户登录功能',
    content: '所有任务已完成：\n✅ 登录 API (t-001)\n✅ 登录页面 (t-002)\n✅ 单元测试 (t-003)\n✅ 集成测试 (t-004)\n✅ 文档更新 (t-005)\n\n请验收功能',
    actions: ['🧪 开始验收']
  }
}
```

### 3.3 通知机制

**多渠道通知**：

```typescript
interface HumanLoopNotification {
  type: 'checkpoint' | 'report' | 'blocked' | 'completed'
  requirementId: string
  title: string
  content: string
  actions?: string[]          // 可选动作按钮
  urgency: 'low' | 'normal' | 'high'
  channels: ('feishu' | 'email' | 'dashboard')[]
}

// 发送通知
reqboard_notify_human({
  type: 'checkpoint',
  requirement: req,
  message: '需求分析完成，请确认',
  deliverables: ['requirement.md'],
  nextAction: '确认后将进入技术设计阶段'
})
```

---

## 4. 完整流程示例

### 4.1 立项 → 需求分析

```
1. 用户：「实现用户登录功能」
2. Agent：弹两问确认 → reqboard_create
3. 系统：自动创建 Goal
   {
     objective: '实现用户登录功能',
     phases: [...],
     completedContent: []
   }
4. Agent：进入 brainstorming，读取 wiki
5. Agent：与用户讨论需求细节
6. Agent：生成 requirement.md
7. Agent：reqboard_goal_complete_phase('requirement-analysis')
8. 系统：发送通知「需求分析完成，请确认」
9. 用户：在飞书点「✅ 确认继续」
10. 系统：自动推进到 planning
```

### 4.2 技术设计

```
11. Agent：生成 design.md（API/表/页面）
12. Agent：reqboard_plan_submit
13. 系统：发送通知「技术设计完成，请批准计划」
14. 用户：在项目看板点「批准计划」
15. Agent：reqboard_decompose（落库 5 个任务）
16. 系统：自动推进到 implementing
```

### 4.3 实施（Workflow 并行执行）

```
17. Agent：开始执行 Task A（登录 API）
    - SystemPrompt 注入任务详情
    - Agent 按 description 实现
    - 运行测试
    - reqboard_task_report（汇报完成内容）
    - reqboard_task_move(to='integrating')
    - 系统：通知「任务 A 完成，已进入联调」

18. Agent：继续 Task B（登录页面）
    ...

19. 所有任务完成
    - 系统：自动推进到 accepting
    - 发送通知「开发完成，请验收」
```

### 4.4 验收

```
20. Agent：reqboard_verify_submit
    - 自动生成验收文档
    - 汇总所有任务的完成内容
21. 用户：在项目看板验收功能
22. 用户：点「✅ 验收通过」
23. 系统：需求 → done
```

### 4.5 归档

```
24. Agent：reqboard_archive_submit
    - 整合文档到 wiki
    - 更新 API 文档
25. 用户：在项目看板点「归档」
26. 系统：需求 → archived
27. Goal 完成记录：
    completedContent: [
      '✅ 需求文档',
      '✅ 技术设计文档',
      '✅ 登录 API (POST /api/auth/login)',
      '✅ 登录页面 (LoginPage.vue)',
      '✅ 单元测试 (覆盖率 85%)',
      '✅ 集成测试',
      '✅ API 文档更新',
      '✅ 验收文档'
    ]
```

---

## 5. 实施计划

### P0: 人机回路基础（本周，4-6小时）

- [ ] `reqboard_task_report` 工具（任务完成汇报）
- [ ] `reqboard_notify_human` 工具（多渠道通知）
- [ ] 关键阶段自动发通知（需求分析完成/设计完成/所有任务完成）

### P1: Goal 跟踪（下周，3-4小时）

- [ ] 扩展 RequirementRecord 数据结构（增加 goal 字段）
- [ ] `reqboard_goal_status` 工具（查看进度）
- [ ] `reqboard_goal_complete_phase` 工具（记录阶段产出）

### P2: 完整集成（后续，2-3小时）

- [ ] Dashboard 展示 Goal 进度
- [ ] 飞书卡片支持动作按钮
- [ ] Workflow 可视化（甘特图增强）

---

## 6. 与现有系统的集成

### 已完成 ✅
- SystemPrompt 注入任务执行指引
- `reqboard_overview` 项目全景
- `reqboard_task_detail` 任务详情

### 需要新增
- 任务完成汇报机制
- 人机回路通知
- Goal 进度跟踪

---

**开始实施 P0？**
