# 数据模型设计（REQ-260928001915-f978）

> 每章标题行必须带 `serves: FR-x` 标注（缺标注 = 孤儿章节被门禁拦）。

## 队列文件契约（QueueFile）`serves: FR-2, FR-3`

**唯一数据源**：`docs/requirements/<REQ>/queue.json`

**契约定义处**：`packages/web/dsh-pmboard/src/domain/queue/QueueTypes.ts`

```typescript
interface QueueFile {
  version: number              // 队列格式版本（当前 1）
  requirement_id: string       // 所属需求 ID
  schemaVersion: number        // 台账 schema 版本（迁移后为 9）
  generated_at: string         // 生成时间（ISO 8601）
  updated_at?: string          // 最后更新时间
  tasks: QueueTask[]           // 任务卡（完整 TaskRecord + layer）
  edges: QueueEdge[]           // 依赖边（由 dependsOn 展开）
  layers: QueueLayer[]         // 层级分组（拓扑排序结果）
  ready: string[]              // 当前可执行任务 id
}

interface QueueTask extends TaskRecord {
  layer: number                // DAG 层级（0 = 无依赖）
}

interface QueueEdge {
  from: string                 // 前置任务 id
  to: string                   // 后继任务 id
}

interface QueueLayer {
  layer: number                // 层级编号
  tasks: string[]              // 该层任务 id 列表
}
```

**与 requirement.md 数据契约的差异**（纠正漂移）：

requirement.md 声称 `layers: string[][]`，但实际 `QueueFile.layers` 是 `QueueLayer[]`（对象数组，含 `layer` 编号）。本设计以 QueueTypes.ts 为准。

## TaskRecord 字段子集（渲染所需）`serves: FR-1, FR-2`

卡片类型系统需要的字段（完整定义见 `src/shared/protocol.ts`）：

```typescript
interface TaskRecord {
  id: string                   // t-xxxxxx
  requirementId: string
  title: string
  
  // 四轴分类
  phase: TaskPhase             // 任务类型（七选一）
  side: TaskSide               // 端侧（四选一）
  status: TaskStatus           // 状态（六选一 + canceled）
  parentId?: string            // 父卡 id（子卡必填、父卡/普通卡无）
  
  // 依赖与层级
  dependsOn: string[]          // 前置任务 id 列表
  layer: number                // DAG 层级（派生字段，队列文件写入）
  
  // 子卡专属
  stageKind?: StageKind        // 子卡阶段（dev/integrate/review/test 等）
}

// 枚举定义
type TaskPhase = 'doc' | 'ui' | 'analysis' | 'implement' | 'test' | 'review' | 'merge'
type TaskSide = 'frontend' | 'backend' | 'fullstack' | 'doc'
type TaskStatus = 'todo' | 'in_progress' | 'integrating' | 'testing' | 'in_review' | 'done' | 'canceled'
type StageKind = 'dev' | 'integrate' | 'review' | 'test' | ... // 共 16 个（见 SubtaskTemplate.ts）
```

## 派生字段（内存计算，不写回）`serves: FR-1, FR-2, FR-3`

卡片渲染需要的派生信息：

```typescript
interface DerivedTaskFields {
  // 角色（由 parentId 和反查推断）
  role: 'parent' | 'child' | 'solo'
  
  // 父卡的子卡列表（由 parentId 反查得到）
  kids?: Array<{
    id: string
    stageKind: StageKind       // dev/integrate/review/test
    status: TaskStatus         // 用于子卡链进度条颜色
    title: string
  }>
}

// 计算逻辑（伪代码）
function deriveRole(task: QueueTask, allTasks: QueueTask[]): 'parent' | 'child' | 'solo' {
  if (task.parentId) return 'child'
  const hasKids = allTasks.some(t => t.parentId === task.id)
  return hasKids ? 'parent' : 'solo'
}

function deriveKids(parentId: string, allTasks: QueueTask[]) {
  return allTasks
    .filter(t => t.parentId === parentId)
    .sort(byStageKindOrder)  // dev → integrate → review → test
    .map(t => ({ id: t.id, stageKind: t.stageKind, status: t.status, title: t.title }))
}
```

## 渲染状态（前端内存）`serves: FR-4, FR-5, FR-6, FR-7`

交互状态，不持久化：

```typescript
interface DagRenderState {
  direction: 'tb' | 'lr'        // 布局方向（纵向/横向）
  pinned: string | null         // 钉住的节点 id（点击固定高亮）
  focusMainline: boolean        // 是否只显示主线（关键路径）
  positions: Map<string, {x: number, y: number}>  // 节点坐标缓存
  criticalSet: Set<string>      // 关键路径节点集合
}
```

## 数据约束（校验规则）`serves: FR-2, FR-3`

以下约束在 `validateQueueFile` 中校验（定义见 QueueTypes.ts）：

| 规则 ID | 约束 | 违反后果 |
|---|---|---|
| V-1 | `tasks` 数组不为空 | 拒绝加载队列 |
| V-2 | `edges[].from/to` 引用的 id 必须存在于 `tasks[]` | 边线渲染失败 |
| V-3 | 所有任务的 `requirementId` 与队列文件的 `requirement_id` 一致 | 防跨需求串档 |
| V-4 | `dependsOn` 不形成环 | 拓扑排序失败 |
| V-5 | `layer` 字段正确（前驱 layer < 后继 layer） | 布局错乱 |
| V-6 | `ready` 数组中的任务必须存在且状态为 `todo` | 绿点标记错误 |

## 数据来源与更新路径 `serves: FR-2`

```
写入路径（队列文件生成）：
  reqboard_decompose() 
    → QueueWriter.write()
    → 写入 docs/requirements/<REQ>/queue.json
    → 包含 tasks/edges/layers/ready 四个派生字段

读取路径（节点详情面板）：
  StageDetail.body.tasks (decomposing/implementing)
    → 从队列文件读取
    → 传给 renderDag()
    → 前端渲染 DAG 可视化

更新路径（任务状态变化）：
  reqboard_task_move()
    → QueueWriter.update()
    → 重算 ready[] + 局部更新 tasks[]
    → 写回队列文件
```

**关键设计决策**：
- `edges` / `layers` / `ready` 都是**派生的**，写回时整份重算，不允许手工编辑
- `dependsOn` 是源数据，`edges` 是 `dependsOn` 的展开结果（等价）
- 关键路径算法优先用 `dependsOn`（数据源头），`edges` 仅用于画线

## 迁移与兼容 `serves: FR-2`

无数据迁移。本设计只消费现有 `QueueFile` 字段，不新增持久化字段。

**降级路径**：
- `edges` 缺失或不一致 → 从 `dependsOn` 重建
- `layer` 缺失 → 调用 `topoLevels()` 重算（现有逻辑）
- `ready` 缺失 → 显示警告，不标记绿点

## 数据新鲜度 `serves: FR-2`

队列文件的 `updated_at` 字段记录最后更新时间。渲染时无需校验新鲜度（节点详情面板每次打开重新读取）。

关键路径 / 主线折叠状态在前端内存，页面刷新后重置为默认值（`focusMainline: false`，显示全图）。
