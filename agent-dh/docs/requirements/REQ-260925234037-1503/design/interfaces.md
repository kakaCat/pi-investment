# 接口设计

**需求**: REQ-260925234037-1503  
**版本**: 1.0  
**更新**: 2026-09-25



### 删除的工具接口 `serves: FR-1`


#### reqboard_decompose（删除） `serves: FR-1, FR-2`

**原接口**：
```typescript
reqboard_decompose({
  requirement_id?: string,
  tasks?: Array<{
    key?: string,
    title?: string,
    description?: string,
    phase?: string,
    side?: string,
    depends_on?: string[],
    acceptance?: string,
    implementation?: string,
    context?: string,
    requirement_refs?: string[],
    skip_integration?: boolean
  }>
})
```

**删除后**：工具不存在，调用返回 `unknown tool` 错误


#### reqboard_move（删除） `serves: FR-1, FR-2`

**原接口**：
```typescript
reqboard_move({
  to: 'draft' | 'brainstorming' | 'design' | 'decomposing' | 'implementing' | 'accepting' | 'done' | 'archived' | 'canceled',
  requirement_id?: string,
  reason?: string
})
```

**删除后**：工具不存在，调用返回 `unknown tool` 错误


#### reqboard_task_move（删除） `serves: FR-1, FR-2`

**原接口**：
```typescript
reqboard_task_move({
  task_id: string,
  to: 'todo' | 'in_progress' | 'integrating' | 'testing' | 'in_review' | 'done' | 'canceled',
  reason?: string,
  acceptance?: string
})
```

**删除后**：工具不存在，调用返回 `unknown tool` 错误



### 修改的工具接口 `serves: FR-1, FR-2`


#### reqboard_create（参数变更） `serves: FR-1, FR-2`

**修改前**：
```typescript
reqboard_create({
  title: string,
  category: 'feature' | 'bug' | 'doc' | 'refactor' | 'spike' | 'chore',
  summary?: string,
  reason?: string,
  prompt_difficulty?: 'simple' | 'standard' | 'advanced' | 'expert',
  doc_location?: string,
  dive_mode?: 'armed' | 'disarmed'  // 可选参数
})
```

**修改后**：
```typescript
reqboard_create({
  title: string,
  category: 'feature' | 'bug' | 'doc' | 'refactor' | 'spike' | 'chore',
  summary?: string,
  reason?: string,
  prompt_difficulty?: 'simple' | 'standard' | 'advanced' | 'expert',
  doc_location?: string
  // 删除 dive_mode 参数
})
```

**行为变更**：
- 固定创建 `dive.activation = 'armed'`
- 不再支持创建 disarmed 需求

**返回值**（不变）：
```typescript
{
  success: boolean,
  requirement_id: string,
  title: string,
  category: string,
  status: string,
  doc_location: string,
  defaults_used: string[],
  note: string,
  board_link: string
}
```


#### reqboard_capture（参数变更） `serves: FR-1, FR-2`

**修改前**：
```typescript
reqboard_capture({
  title_options?: string[],
  summary?: string,
  reason?: string,
  dive_mode?: 'armed' | 'disarmed'  // 可选参数
})
```

**修改后**：
```typescript
reqboard_capture({
  title_options?: string[],
  summary?: string,
  reason?: string
  // 删除 dive_mode 参数
})
```

**行为变更**：
- 立项弹框移除 dive_mode 问项
- 固定创建 `dive.activation = 'armed'`

**返回值**（不变）：
```typescript
{
  success: boolean,
  requirement_id: string,
  status: string,
  answers: {
    title: string,
    category: string,
    difficulty: string,
    docLocation: string
  },
  defaults_used: string[],
  doc_location: string,
  fallback?: string,
  note: string,
  board_link: string
}
```



### 优化的工具接口 `serves: FR-3`


#### reqboard_task_run（提示词优化） `serves: FR-3`

**接口**（不变）：
```typescript
reqboard_task_run({
  task_id: string
})
```

**返回值**（不变）：
```typescript
{
  success: boolean,
  task_id: string,
  status: string,
  subtask_executed?: object,
  next_ready?: object,
  chain?: object,
  blocked?: object,
  parent_status: string,
  stopped?: string,
  error?: string
}
```

**提示词变更**（在 prompt.ts 中）：
- 添加："这是 Dive Armed 模式的核心执行入口"
- 添加："自动执行父卡下的子卡链"
- 添加："implementing 阶段主要使用本工具"


#### reqboard_clear_pause（提示词优化） `serves: FR-3`

**接口**（不变）：
```typescript
reqboard_clear_pause({
  requirement_id?: string,
  reason: string
})
```

**返回值**（不变）：
```typescript
{
  success: boolean,
  requirement_id: string,
  from_phase: string,
  to_phase: string,
  note: string
}
```

**提示词变更**：
- 添加："break glass 紧急干预工具"
- 添加："仅在 Dive 流程异常时使用"
- 添加："正常情况下不需要调用"


#### reqboard_status（返回值扩展） `serves: FR-3`

**接口**（不变）：
```typescript
reqboard_status({})
```

**返回值扩展**：
```typescript
{
  window_key: string,
  bound: boolean,
  open_count: number,
  open_requirements: Array<{
    id: string,
    title: string,
    status: string,
    category: string,
    dive?: {  // 新增 dive 状态显示
      activation: 'armed' | 'disarmed',
      phase: 'idle' | 'active' | 'paused',
      roundsInStage: number,
      pausedReason?: string
    }
  }>,
  next_actions: string[],
  clause_receive_status: Array<object>,
  unreceived_clauses: string[],
  design_docs: Array<object>,
  note: string,
  board_link: string
}
```

**行为变更**：
- 在 `open_requirements` 中添加 `dive` 字段
- 显示 Dive 状态：activation, phase, roundsInStage



### 配置接口变更 `serves: FR-1, FR-2`


#### StageConfig（accepting 阶段） `serves: FR-6`

**文件**: `packages/web/dsh-pmboard/src/application/dive/stage-configs.ts`

**修改前**：
```typescript
accepting: {
  requiresConfirmation: true,
  autoExecute: false,  // ← 错误配置
  maxRounds: 5,
  description: '验收阶段，需人工验收'
}
```

**修改后**：
```typescript
accepting: {
  requiresConfirmation: true,
  autoExecute: true,   // ← 修复：验收通过自动归档
  maxRounds: 5,
  description: '验收阶段，需人工验收，通过后自动归档'
}
```

**影响**：
- 验收通过后不再需要手动调用 move
- Dive 流程完整闭环（brainstorming → archived）

## 错误码设计 <!-- serves: FR-4 -->


### 工具调用错误 `serves: FR-4`


#### 工具不存在错误 `serves: FR-4`

```json
{
  "error": "unknown tool: reqboard_decompose"
}
```

**触发条件**：调用已删除的工具

**用户指引**：
- "工具 reqboard_decompose 已删除"
- "使用 reqboard_task_run 替代"
- "Dive Armed 模式下自动拆分"


#### 参数错误 `serves: FR-4`

```json
{
  "error": "unknown parameter: dive_mode"
}
```

**触发条件**：向 create/capture 传递 dive_mode

**用户指引**：
- "dive_mode 参数已移除"
- "所有新需求固定为 armed"

## 向后兼容性 <!-- serves: FR-1, FR-2 -->


### 数据兼容 `serves: FR-1, FR-2`

- ✅ 现有需求的 dive.activation 保持不变
- ✅ disarmed 需求仍可正常读取
- ✅ 不改变 Requirement 数据模型


### 行为不兼容 `serves: FR-1, FR-2`

- ❌ 无法创建新的 disarmed 需求
- ❌ 无法手动调用 decompose/move/task_move
- ❌ 必须使用 Dive Armed 工作流程

## 迁移指南 <!-- serves: FR-5 -->


### Agent 适配 `serves: FR-1, FR-2`

**删除工具调用**：
```typescript
// 删除
await tools.reqboard_decompose({ ... })
await tools.reqboard_move({ ... })
await tools.reqboard_task_move({ ... })

// 替换为
await tools.reqboard_task_run({ task_id: '...' })
```

**移除 dive_mode 参数**：
```typescript
// 删除
await tools.reqboard_create({ 
  title: '...',
  dive_mode: 'armed'  // 移除此参数
})

// 改为
await tools.reqboard_create({ 
  title: '...'
  // dive_mode 已固定为 armed
})
```


### 系统提示词更新 `serves: FR-1, FR-2`

需要更新的地方：
1. 删除 reqboard_decompose 的使用说明
2. 删除 reqboard_move 的使用说明
3. 删除 reqboard_task_move 的使用说明
4. 强调 reqboard_task_run 是唯一执行入口
5. 说明 Dive Armed 是唯一工作方式