# 接口设计（REQ-260928001915-f978）

> 每章标题行必须带 `serves: FR-x` 标注（缺标注 = 孤儿章节被门禁拦）。

## 核心渲染接口 `serves: FR-2, FR-3`

### renderDag() `serves: FR-2, FR-3`

**签名变更**：

```typescript
// Before（现有 node-panel.ts:142）
function renderDag(tasks: StageTaskRef[]): string

// After
function renderDag(data: DagData, state: DagRenderState): string
```

**参数**：

```typescript
interface DagData {
  tasks: StageTaskRef[]        // 完整任务列表（含 layer/dependsOn/parentId/stageKind）
  edges: QueueEdge[]           // 依赖边（由 dependsOn 展开，来自 QueueFile.edges）
  ready: string[]              // 当前可执行任务 id（来自 QueueFile.ready）
}

interface DagRenderState {
  direction: 'tb' | 'lr'       // 布局方向（'tb' 纵向，'lr' 横向）
  pinned: string | null        // 钉住的节点 id（null = 未钉住）
  focusMainline: boolean       // 是否只显示主线（true = 折叠到关键路径）
  positions?: Map<string, {x: number, y: number}>    // 节点坐标缓存（可选，重算时传 undefined）
  criticalSet?: Set<string>    // 关键路径节点集合（可选，重算时传 undefined）
}
```

**返回值**：

```typescript
返回 HTML 字符串，结构：
<div class="dsh-pm-np-dag" data-direction="tb" data-focus="false">
  <svg class="dsh-pm-np-dag-edges">...</svg>
  <div class="dsh-pm-np-dag-node" data-id="t-xxx" style="left:Xpx;top:Ypx">
    <div class="card" data-phase="implement" data-side="backend" data-status="in_progress" data-role="parent">
      ...
    </div>
  </div>
  ...
</div>
```

**错误处理**：

| 错误场景 | 行为 | 返回值 |
|---|---|---|
| `tasks` 为空数组 | 返回占位 HTML | `<div class="dsh-pm-np-empty">暂无任务</div>` |
| `edges` 引用不存在的任务 id | 控制台警告，跳过该边 | 正常 HTML（缺失边线） |
| `layer` 缺失 | 调用 `topoLevels()` 重算 | 正常 HTML |
| 循环依赖 | 控制台错误 | `<div class="dsh-pm-np-error">DAG 存在循环依赖</div>` |

## 布局算法接口 `serves: FR-3`

### layoutDag() `serves: FR-3`

```typescript
function layoutDag(
  tasks: StageTaskRef[], 
  direction: 'tb' | 'lr', 
  availWidth: number
): LayoutResult

interface LayoutResult {
  positions: Map<string, { x: number; y: number }>  // 节点坐标
  width: number                                       // 画布总宽度
  height: number                                      // 画布总高度
}
```

**算法说明**：

纵向模式（`direction='tb'`）：
- 每层按 `availWidth` 分列（`cols = floor((availW - PAD*2 + GAP_X) / (CARD_W + GAP_X))`）
- 同层任务从左到右、从上到下排列
- `y` 坐标逐层累加

横向模式（`direction='lr'`）：
- 每层按 `maxRows=8` 限高分列
- `x` 坐标逐层累加

**常量**：

```typescript
const CARD_W = 208     // 卡片宽度
const CARD_H = 72      // 卡片高度
const GAP_X = 14       // 水平间距
const GAP_Y = 22       // 垂直间距
const PAD = 14         // 画布内边距
```

## 关键路径接口 `serves: FR-6`

### computeCriticalPath() `serves: FR-6`

```typescript
function computeCriticalPath(tasks: StageTaskRef[]): Set<string>
```

**参数**：`tasks` - 任务列表（必须含 `layer` 和 `dependsOn`）

**返回值**：关键路径节点 id 的 Set（最长路径上的所有节点）

**算法**：动态规划求 DAG 最长路径（见 architecture.md §关键算法）

**前置条件**：`tasks` 必须按 `layer` 拓扑有序（`dependsOn` 不形成环）

**错误处理**：
- 循环依赖 → 返回空 Set + 控制台错误
- `layer` 缺失 → 调用 `topoLevels()` 重算

## 上下游遍历接口 `serves: FR-4`

### computeNeighbors() `serves: FR-4`

```typescript
function computeNeighbors(
  tasks: StageTaskRef[], 
  targetId: string
): { up: Set<string>; down: Set<string> }
```

**参数**：
- `tasks` - 任务列表（必须含 `dependsOn`）
- `targetId` - 目标节点 id

**返回值**：
- `up` - 上游依赖节点集合（所有可达前驱）
- `down` - 下游后继节点集合（所有可达后继）

**算法**：
- 上游：从 `targetId` 递归访问 `dependsOn` 数组
- 下游：构造反向邻接表后递归访问

## 派生字段计算接口 `serves: FR-1`

### deriveTaskFields() `serves: FR-1`

```typescript
function deriveTaskFields(task: QueueTask, allTasks: QueueTask[]): DerivedTaskFields

interface DerivedTaskFields {
  role: 'parent' | 'child' | 'solo'
  kids?: Array<{ id: string; stageKind: StageKind; status: TaskStatus; title: string }>
}
```

**逻辑**：

```typescript
function deriveTaskFields(task: QueueTask, allTasks: QueueTask[]): DerivedTaskFields {
  // 1. 推断角色
  if (task.parentId) {
    return { role: 'child' }
  }
  
  // 2. 查找子卡
  const kids = allTasks
    .filter(t => t.parentId === task.id)
    .sort(byStageKindOrder)  // dev → integrate → review → test
    .map(t => ({ id: t.id, stageKind: t.stageKind!, status: t.status, title: t.title }))
  
  return {
    role: kids.length > 0 ? 'parent' : 'solo',
    kids: kids.length > 0 ? kids : undefined
  }
}
```

## 卡片渲染接口 `serves: FR-1`

### cardHtml() `serves: FR-1, FR-2`

```typescript
function cardHtml(
  task: StageTaskRef, 
  derived: DerivedTaskFields, 
  options: { ready?: boolean }
): string
```

**返回值**：卡片 HTML 字符串

```html
<div class="card" 
     data-phase="implement" 
     data-side="backend" 
     data-status="in_progress" 
     data-role="parent">
  <div class="card-crown"></div>  <!-- 父卡左侧蓝条 -->
  <div class="card-top">
    <span class="card-id">t-abc123</span>
    <span class="chip chip-type" data-phase="implement">实施</span>
    <span class="chip chip-side" data-side="backend">backend</span>
  </div>
  <div class="card-title">实现核心业务逻辑</div>
  <div class="card-chain">  <!-- 父卡子卡链进度 -->
    <i class="on"></i>  <!-- 已完成子卡：绿色 -->
    <i class="now"></i> <!-- 进行中子卡：蓝色 -->
    <i></i>             <!-- 未开始子卡：灰色 -->
    <i></i>
    <span>2/4</span>
  </div>
  <span class="ready-dot"></span>  <!-- ready 绿点 -->
</div>
```

## 交互事件接口 `serves: FR-4, FR-5`

### 事件绑定 `serves: FR-4, FR-5`

```typescript
// 在 renderDag() 返回 HTML 后，调用方需绑定事件：
const canvas = document.querySelector('.dsh-pm-np-dag')

canvas.addEventListener('mouseover', (ev) => {
  const node = ev.target.closest('.dsh-pm-np-dag-node')
  if (node && state.pinned === null) {
    highlightNode(node.dataset.id)
  }
})

canvas.addEventListener('mouseout', (ev) => {
  const node = ev.target.closest('.dsh-pm-np-dag-node')
  if (node && state.pinned === null) {
    clearHighlight()
  }
})

canvas.addEventListener('click', (ev) => {
  const node = ev.target.closest('.dsh-pm-np-dag-node')
  if (node) {
    // 切换钉住状态
    state.pinned = (state.pinned === node.dataset.id) ? null : node.dataset.id
    if (state.pinned) highlightNode(state.pinned)
    else clearHighlight()
  } else {
    // 点击空白清除
    state.pinned = null
    clearHighlight()
  }
})
```

### highlightNode() / clearHighlight() `serves: FR-4, FR-5`

```typescript
function highlightNode(id: string): void {
  const nb = computeNeighbors(data.tasks, id)
  canvas.classList.add('dimming')  // 其他节点半透明
  
  // 节点高亮：self 黑框、up 橙框、down 蓝框
  canvas.querySelectorAll('.dsh-pm-np-dag-node').forEach(n => {
    n.classList.toggle('hi-self', n.dataset.id === id)
    n.classList.toggle('hi-up', n.dataset.id !== id && nb.up.has(n.dataset.id))
    n.classList.toggle('hi-down', n.dataset.id !== id && nb.down.has(n.dataset.id))
  })
  
  // 边线高亮：up 橙色、down 蓝色
  canvas.querySelectorAll('path').forEach(p => {
    const from = p.dataset.from, to = p.dataset.to
    const isUp = nb.up.has(to) || nb.up.has(from)
    const isDown = nb.down.has(from)
    p.classList.toggle('hi-up', isUp)
    p.classList.toggle('hi-down', !isUp && isDown)
  })
}

function clearHighlight(): void {
  canvas.classList.remove('dimming')
  canvas.querySelectorAll('.dsh-pm-np-dag-node, path').forEach(el => {
    el.classList.remove('hi-self', 'hi-up', 'hi-down')
  })
}
```

## 数据校验接口 `serves: FR-2`

### validateQueueFile() `serves: FR-2, FR-3`

```typescript
function validateQueueFile(queue: QueueFile): ValidationResult

interface ValidationResult {
  passed: boolean
  issues: ValidationIssue[]
}

interface ValidationIssue {
  rule: 'V-1' | 'V-2' | 'V-3' | 'V-4' | 'V-5' | 'V-6'  // 规则编号（见 data-model.md）
  message: string                                        // 错误描述
  path?: string                                          // 出错位置（JSON 路径，如 'tasks[2].dependsOn[0]'）
}
```

**校验规则**（定义见 data-model.md §数据约束）：

| 规则 | 检查内容 | 失败示例 |
|---|---|---|
| V-1 | `tasks` 非空 | `{ tasks: [] }` |
| V-2 | `edges` 引用存在 | `{ from: 't-999' }` 但 `tasks` 里无 t-999 |
| V-3 | `requirementId` 一致 | `tasks[0].requirementId = 'REQ-A'` 但 `requirement_id = 'REQ-B'` |
| V-4 | 无循环依赖 | `t-1 → t-2 → t-3 → t-1` |
| V-5 | `layer` 正确 | 前驱 `layer=2`，后继 `layer=1`（违反拓扑序） |
| V-6 | `ready` 合法 | `ready` 含 `status='done'` 的任务 |

**使用方式**：

```typescript
const result = validateQueueFile(queueData)
if (!result.passed) {
  console.error('队列文件校验失败：', result.issues)
  // 降级渲染或拒绝加载
}
```

## 调用方集成示例 `serves: FR-2, FR-3`

```typescript
// 在 renderDecomposingInfo() / renderImplementingInfo() 中：
function renderDecomposingInfo(p: StageDetail): string {
  const queueFile = loadQueueFile(p.requirement_id)  // 读取队列文件
  
  // 校验
  const validation = validateQueueFile(queueFile)
  if (!validation.passed) {
    return '<div class="error">队列数据校验失败</div>'
  }
  
  // 准备数据
  const dagData: DagData = {
    tasks: queueFile.tasks,
    edges: queueFile.edges,
    ready: queueFile.ready
  }
  
  // 初始状态
  const state: DagRenderState = {
    direction: 'tb',
    pinned: null,
    focusMainline: false
  }
  
  // 渲染
  const html = renderDag(dagData, state)
  
  // 绑定事件（HTML 插入 DOM 后）
  setTimeout(() => bindDagEvents(dagData, state), 0)
  
  return html
}
```
