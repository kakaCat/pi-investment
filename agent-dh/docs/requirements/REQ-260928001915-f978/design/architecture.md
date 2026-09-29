# 架构设计（REQ-260928001915-f978）

> 每章标题行必须带 `serves: FR-x` 标注（缺标注 = 孤儿章节被门禁拦）。

## 目标与总体方案 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7`

**问题**：现有 DAG 渲染（node-panel.ts 的 renderDag）只输出简单层级列表（"第 N 层 · X 个可并行"），无真实图结构、无依赖线、无卡片类型视觉、无交互。用户无法直观理解任务依赖关系、关键路径、卡片类型差异。

**当前状况**：
- `renderDag()` 调用 `topoLevels()` 分层后，每层渲染为 `<button>` 列表
- 卡片只显示 id + title，用 `data-status` 着底色
- 无边线、无位置布局、无类型徽标、无悬停高亮、无关键路径、无主线折叠

**设计方案**：
1. **卡片类型系统（FR-1）**：四轴视觉编码 `phase × side × role × status`，七类任务类型彩色徽标 + 四类端侧徽标 + 六态底色 + 三角色结构差异（父卡蓝条 + 子卡链进度、子卡左缩进、普通卡）
2. **真实 DAG 渲染（FR-2/FR-3）**：消费 `QueueFile.edges[]` 画 SVG 连线（曲线 Bézier），节点按 `layer` 布局（纵向/横向可切换），`ready[]` 右上角绿点标记
3. **悬停高亮上下游（FR-4）**：鼠标悬停卡片时高亮该节点 + 上游依赖（橙色）+ 下游后继（蓝色），其他节点半透明
4. **点击钉住（FR-5）**：点击卡片固定高亮状态，再点取消；点空白清除
5. **关键路径（FR-6）**：`computeCrit()` 算法计算最长路径，关键路径节点加虚线轮廓、边线加粗蓝色
6. **主线折叠（FR-7）**："只看主线"开关默认折叠到关键路径，卡角显示 `+N 支线` 徽标，点击展开全图

**不这么做的后果**：
- 用户仍需依赖文字列表 + 脑内想象依赖关系
- 大图（如 83 边 12 层）无法快速定位关键路径与瓶颈
- 卡片类型（实施/测试/文档/评审等）混在一起无法区分

## 模块改动地图 `serves: FR-2, FR-3`

**改动清单**：

| 模块/文件 | 类型 | 改动内容 | 原因（serves） | 影响范围 |
|---|---|---|---|---|
| `src/client/node-panel.ts` | 修改 | `renderDag()` 从简单列表改为 SVG + 绝对定位节点 | FR-2/FR-3 真实图渲染 | decomposing/implementing 阶段的 DAG 展示 |
| `src/client/styles/node-panel.ts` | 新增 | 卡片类型 CSS（phase 7 色 + side 4 色 + status 6 态 + 角色） | FR-1 类型系统 | 所有 DAG 卡片视觉 |
| `src/client/node-panel.ts` | 新增函数 | `layoutDag()` 布局算法（纵向/横向） | FR-3 布局 | 节点坐标计算 |
| `src/client/node-panel.ts` | 新增函数 | `computeCriticalPath()` 关键路径 | FR-6 | 关键路径标记 |
| `src/client/node-panel.ts` | 新增函数 | `computeNeighbors()` 上下游遍历 | FR-4 悬停高亮 | 交互逻辑 |
| `src/client/node-panel.ts` | 新增事件 | mouseover/mouseout/click 事件监听 | FR-4/FR-5 交互 | DOM 事件绑定 |

## 数据结构变更 `serves: FR-1, FR-2`

### 新增的派生字段（内部状态，不写回 queue.json） `serves: FR-1, FR-2`

```typescript
interface DagRenderState {
  /** 布局方向 */
  direction: 'tb' | 'lr'  // tb=纵向 top-bottom, lr=横向 left-right
  
  /** 钉住的节点 id（点击固定高亮） */
  pinned: string | null
  
  /** 是否只显示主线（关键路径） */
  focusMainline: boolean
  
  /** 节点坐标缓存（layout 计算结果） */
  positions: Map<string, { x: number; y: number }>
  
  /** 关键路径节点集合（computeCriticalPath 计算） */
  criticalSet: Set<string>
}

interface DerivedTaskFields {
  /** 派生角色（由 parentId 和 kids 推断） */
  role?: 'parent' | 'child' | 'solo'
  
  /** 父卡的子卡列表（由 parentId 反查得到） */
  kids?: Array<{ id: string; stageKind: string; status: TaskStatus; title: string }>
}
```

### 兼容性分析 `serves: FR-1, FR-2, FR-3`

无数据持久化变更。`DagRenderState` 是前端内存状态，`DerivedTaskFields` 从 `QueueFile` 实时计算。

## 接口变更 `serves: FR-2, FR-3`

### 修改的接口 `serves: FR-2, FR-3`

```typescript
// Before（当前 node-panel.ts:142）
function renderDag(tasks: StageTaskRef[]): string

// After
function renderDag(data: DagData, state: DagRenderState): string

interface DagData {
  tasks: StageTaskRef[]  // 完整任务列表（含 layer/dependsOn/parentId/stageKind）
  edges: QueueEdge[]     // 依赖边（由 dependsOn 展开）
  ready: string[]        // 当前可执行节点 id
}
```

**改动原因**：
- 新签名需要 `edges` 画连线、`ready` 标记绿点
- `state` 参数支持方向切换 + 主线折叠 + 交互状态持久化

**影响范围**：
- `renderDecomposingInfo()`（L171）调用点改为传 `{ tasks, edges, ready }`
- `renderImplementingInfo()` 同理

## 关键算法/流程 `serves: FR-3, FR-4, FR-6`

### 布局算法（layoutDag） `serves: FR-3`

```
输入：tasks（含 layer）、direction（'tb'/'lr'）、availWidth
输出：{ positions: Map<id, {x, y}>, width, height }

算法：
1. 按 layer 分组：layers[n] = 同层任务列表
2. 纵向模式（tb）：
   - 每层按 availWidth 分列（cols = floor((availW - PAD*2 + GAP_X) / (CARD_W + GAP_X))）
   - y 坐标累加：y += rows * (CARD_H + GAP_Y) + 层间距
3. 横向模式（lr）：
   - 每层按 maxRows=8 分列
   - x 坐标累加：x += cols * (CARD_W + GAP_X) + 层间距
4. 常量（沿用 prototype.html）：
   - CARD_W=208, CARD_H=72, GAP_X=14, GAP_Y=22, PAD=14
```

### 关键路径算法（computeCriticalPath） `serves: FR-6`

```
输入：tasks（含 layer/dependsOn）
输出：Set<string> 关键路径节点 id 集合

算法（动态规划，longest path in DAG）：
1. 按 layer 升序排序任务（拓扑序）
2. 初始化 dist[id] = 1（该节点到起点最长路长度）
3. 遍历每个任务 t：
   - 对每个前驱 d in t.dependsOn：
     - if dist[d] + 1 > dist[t.id]: 更新 dist[t.id] 并记录 prev[t.id] = d
4. 找终点 end = argmax(dist)
5. 回溯路径：cur = end; while cur: add cur to set; cur = prev[cur]
6. 返回 set
```

**与需求数据契约的差异**：
- prototype/demo 用 `dependsOn` 数组计算路径
- `QueueFile.edges[]` 是 `dependsOn` 展开结果，两者等价
- 实现时优先用 `dependsOn`（数据源头），`edges` 仅用于画线

### 上下游遍历（computeNeighbors） `serves: FR-4, FR-5`

```
输入：tasks、targetId
输出：{ up: Set<string>, down: Set<string> }

算法：
1. 上游遍历（walkUp）：
   - 从 targetId 出发，递归访问 dependsOn 数组
   - 记录所有可达前驱节点
2. 下游遍历（walkDown）：
   - 构造反向邻接表 rev[d] = [后继节点列表]
   - 从 targetId 出发，递归访问后继
3. 返回 up/down 两个集合
```

## 测试策略 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7`

**必测场景**：

| 场景 | 输入 | 预期输出 | 测试用例编号 |
|---|---|---|---|
| 七类任务类型彩色徽标 | 各 phase 的任务 | 七种颜色正确显示 | TC-1 |
| 四类端侧徽标 | 各 side 的任务 | 四种端侧颜色正确显示 | TC-2 |
| 父卡结构 | 含 kids 的 parent 任务 | 左侧蓝条 + 子卡链进度条 | TC-3 |
| 子卡缩进 | role=child 任务 | 左缩进 18px + 左侧竖线 | TC-4 |
| ready 绿点 | ready 数组含该任务 id | 右上角绿点 + 光晕 | TC-5 |
| 依赖边渲染 | edges 数组 | SVG 路径连接对应节点 | TC-6 |
| 纵向/横向布局切换 | direction='tb'/'lr' | 节点坐标变化 | TC-7 |
| 悬停高亮上游 | 鼠标悬停任务 B（依赖 A） | B 黑框高亮、A 橙框、其他半透明 | TC-8 |
| 悬停高亮下游 | 鼠标悬停任务 A（被 C 依赖） | A 黑框、C 蓝框、其他半透明 | TC-9 |
| 点击钉住 | 点击任务 | 高亮保持，再点取消 | TC-10 |
| 点击空白清除 | 钉住状态下点画布空白 | 清除高亮 | TC-11 |
| 关键路径标记 | 包含关键路径的 DAG | 路径节点虚线轮廓 + 边线加粗蓝色 | TC-12 |
| 主线折叠 | focusMainline=true | 只显示关键路径节点，卡角显示 +N 支线 | TC-13 |
| 主线展开 | focusMainline=false | 显示全部节点 | TC-14 |

## 错误处理 `serves: FR-2, FR-3`

**新增错误场景**：

| 错误场景 | 触发条件 | 用户看到什么 | 如何恢复 |
|---|---|---|---|
| edges 与 dependsOn 不一致 | `edges` 缺少 `dependsOn` 对应边 | 控制台警告 + 边线缺失 | 降级：用 dependsOn 重建 edges |
| layer 缺失 | 任务无 `layer` 字段 | 控制台警告 + 节点堆叠在 layer 0 | 降级：调用 `topoLevels()` 重算 |
| 循环依赖 | `dependsOn` 形成环 | 控制台错误 + 渲染失败提示 | 用户修复 queue.json |
| 空 DAG | tasks=[] | 显示占位文本"暂无任务" | 正常业务状态 |

## 文档更新清单 `serves: FR-1, FR-2`

| 文档 | 更新内容 | 负责人 |
|---|---|---|
| `docs/architecture/reqboard-queue-storage.md` | 补充 DAG 可视化消费 edges/ready 的说明 | 本需求 |
| `packages/web/dsh-pmboard/README.md` | 新增"节点详情面板 DAG 可视化"章节 | 本需求 |

## 部署变更 `serves: FR-2`

无环境变量或启动参数变更。前端静态资源（CSS/JS）随 `pnpm build` 构建，重启 DSH 生效。

## 遗留问题 `serves: FR-2, FR-6`

| 问题 | 影响 | 计划何时解决 |
|---|---|---|
| 大图性能（>100 节点） | 渲染可能卡顿 | 本轮不做；未来考虑虚拟滚动或 Canvas 渲染 |
| 关键路径算法只取单条最长路径 | 多条等长路径只显示一条 | 本轮足够；未来可考虑显示所有等长路径 |
| 父子卡在 DAG 中的视觉关联弱 | 父卡与 4 张子卡在图中可能相距很远 | 本轮不做；未来考虑"子卡吸附到父卡附近"的布局优化 |
