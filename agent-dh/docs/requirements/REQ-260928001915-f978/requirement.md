# 需求说明（REQ-260928001915-f978）

## 一句话目标

完成队列 DAG 真图的卡片类型定义和可视化方案设计，使 DAG 图可读性提升、信息层次清晰。

## 可证伪判定标准

- 运行 `python3 docs/requirements/REQ-260928001915-f978/demo/build-demo.py`，生成的 HTML 能正确展示真实队列的 DAG 结构
- 卡片类型系统（phase/side/role/status 四轴）定义清晰，每张卡上的信息层次明确
- 交互功能（悬停高亮上下游、关键路径、主线折叠）正常工作

## 边界（做什么 / 不做什么）

**本次做**：
1. 定义卡片类型系统（四轴：任务类型 phase、端侧 side、角色 role、状态 status）
2. 设计卡片视觉规范（ID、类型徽标、端侧徽标、标题、状态底色、子卡链进度、ready 标记的位置和样式）
3. 实现真实 DAG 可视化（用队列 `edges[]` 画连线，支持纵向/横向布局）
4. 交互功能（悬停高亮上下游、点击钉住、关键路径、主线折叠）

**本次不做**：
1. 不改动队列数据模型本身（只消费现有 queue.json 的字段）
2. 不实现拖拽编辑（只读展示）
3. 不集成到 pmboard 页面（本次只产出设计规范和原型）

## 产品定义

队列 DAG 真图卡片是**项目看板任务卡的 DAG 视图**，用于：
- 可视化任务之间的依赖关系（edges）
- 快速识别任务类型（实施/测试/文档等）和状态（待开始/进行中/已完成等）
- 展示父卡的子卡链进度（dev → integrate → review → test）
- 支持大图场景（65+ 卡）的主线折叠

## 用户与角色

**主要用户**：开发者、项目管理者  
**使用场景**：
- 查看需求的任务依赖关系
- 识别关键路径（longest path）
- 追踪子卡链进度
- 发现可开工任务（ready 标记）

## 功能点

- **FR-1: 卡片四轴类型系统** — 定义四根正交的轴，决定卡片上的信息层次：
  - **phase（任务类型，7 类）**：`implement`（实施）、`test`（测试）、`doc`（文档）、`review`（评审）、`ui`（UI）、`analysis`（分析）、`merge`（合并）
  - **side（端侧，4 类）**：`backend`（后端）、`frontend`（前端）、`fullstack`（全栈）、`doc`（文档）
  - **role（角色，3 类）**：`parent`（父卡）、`child`（子卡）、`solo`（独立卡）
  - **status（状态，6 类）**：`todo`（待开始）、`in_progress`（开发中）、`integrating`（联调中）、`testing`（测试中）、`in_review`（待复核）、`done`（已完成）

- **FR-2: 卡片视觉规范** — 卡片布局分为两行，7 个视觉元素各司其职：
  - **第一行（card-top）**：① ID（左对齐，灰色等宽字体）② 类型徽标（phase，彩色圆角，7 种颜色）③ 端侧徽标（side，次要颜色）
  - **第二行**：④ 标题（黑色，粗体，最多 2 行）
  - **状态底色**：整个卡片的背景色由 status 决定（6 种浅色背景）
  - **附加元素**：⑥ 子卡链进度（父卡专属，4 段进度条）⑦ ready 绿点（右上角，表示可开工）
  - **父卡标识**：左侧蓝色竖条（3px 宽）

- **FR-3: 真实 DAG 布局** — 消费队列 `layers[]` 和 `edges[]`，支持纵向/横向两种布局方向：
  - **纵向布局**（默认）：按层级从上到下排列，同层内自动折行（根据可用宽度计算列数）
  - **横向布局**：按层级从左到右排列，同层内纵向堆叠（最多 8 行）
  - **卡片尺寸**：208×72px，间距 14px（横）× 22px（纵）
  - **画布自适应**：根据节点数量和布局方向计算画布宽高

- **FR-4: 边线分层着色** — 根据任务状态和路径类型给连线着色：
  - **已完成链路**（绿色，rgba(52,199,89,.5)，线宽 1.3px）：from 和 to 都是 done 状态
  - **进行中/待办**（灰色，rgba(0,0,0,.17)，线宽 1.2px）：默认连线
  - **关键路径**（蓝色，rgba(0,113,227,.75)，线宽 1.8px 加粗）：最长路径（FR-6 计算）

- **FR-5: 悬停交互** — 鼠标移到卡片上高亮其依赖链路：
  - **上游高亮**（橙色，#ff9500，线宽 2px）：该任务依赖的所有上游任务
  - **下游高亮**（蓝色，#0071e3，线宽 2px）：依赖该任务的所有下游任务
  - **当前卡片**：黑色边框（2px）+ 阴影
  - **背景变暗**（dimming）：未高亮的节点和边线透明度降至 0.18 / 0.05
  - **点击钉住**：点击卡片保持高亮状态，再次点击或点击画布取消

- **FR-6: 关键路径计算** — 计算 DAG 的最长路径（longest path）：
  - 算法：从入度为 0 的节点开始，计算到每个节点的最长路径
  - 标记：关键路径上的边线用蓝色加粗显示
  - "只看主线"模式：折叠支线任务，显示 `+N 支线` 徽标

- **FR-7: 父卡子卡链** — 父卡专属的子卡链进度展示：
  - **4 段进度条**：dev（开发）→ integrate（集成）→ review（评审）→ test（测试）
  - **进度状态**：已完成（绿色）、进行中（蓝色）、待开始（灰色）
  - **进度文本**：显示 "已完成数/总数"（如 "2/4"）
  - **子卡折叠**：子卡默认不在 DAG 中显示（或缩进显示）

## 功能点依赖关系

功能点之间的依赖关系（用于拆分时确定任务顺序）：

```
FR-1 (类型系统) → FR-2 (视觉规范) → FR-3 (DAG布局)
                                          ↓
FR-6 (关键路径) → FR-4 (边线着色) ←─────┘
                       ↓
                  FR-5 (悬停交互)
                  
FR-7 (父卡子卡链) - 独立特性，可与 FR-3 并行
```

**依赖说明**：
- FR-1 是基础，必须先定义类型系统（四轴枚举值）
- FR-2 依赖 FR-1 的类型定义来设计视觉规范（颜色、布局）
- FR-3 需要 FR-2 的卡片样式才能渲染 DAG
- FR-6 和 FR-4 依赖 FR-3 的图结构（节点位置、边线路径）
- FR-5 依赖 FR-4 的着色逻辑
- FR-7 可以与主流程并行开发（只依赖 FR-2 的卡片样式）

## 拆分指导

### 任务范围建议

**文档类任务**（FR-1, FR-2）：
- FR-1: 编写类型系统规范文档（定义四轴枚举值、颜色映射表、状态底色表）
- FR-2: 编写卡片视觉规范文档（7 个元素的位置、尺寸、样式、交互态）
- 产出：设计文档，不涉及代码实现

**实现类任务**（FR-3 到 FR-7）：
- FR-3: 核心渲染引擎（读 queue.json、计算布局、画卡片和边线、支持纵横切换）
- FR-4: 边线着色逻辑（根据任务状态分类、应用不同颜色和线宽）
- FR-5: 交互事件处理（悬停、点击、高亮、dimming）
- FR-6: 关键路径算法（longest path 计算、主线折叠）
- FR-7: 父卡子卡链展示（4 段进度条渲染、进度文本）

### FR 覆盖要求

拆分时每个任务必须声明 `requirement_refs` 字段，指明接收哪些 FR。例如：

```json
{
  "key": "t1",
  "title": "定义卡片四轴类型系统",
  "requirement_refs": ["FR-1"],
  "implementation": "编写类型系统规范文档，定义 phase/side/role/status 四轴的枚举值...",
  "acceptance": "文档中明确列出 7+4+3+6=20 个枚举值及其含义"
}
```

**覆盖门禁**：所有 FR-1 到 FR-7 必须至少被一个任务接收，否则拆分会被拒绝。

### 文件冲突避免

如果多个任务需要修改同一文件，必须：
- 要么建立依赖关系（`dependsOn`）
- 要么重新划分任务范围

常见冲突场景：
- FR-3 和 FR-7 都要修改卡片渲染逻辑 → FR-7 依赖 FR-3
- FR-4 和 FR-5 都要修改边线样式 → FR-5 依赖 FR-4
- FR-3 和 FR-6 都要修改布局算法 → FR-6 依赖 FR-3

## 验收标准

1. 运行 `python3 docs/requirements/REQ-260928001915-f978/demo/build-demo.py`，输出的 `dag-card-types-demo.html` 正常打开
2. 小图（12卡）、中图（20卡）、压力图（65卡）三档数据集都能正确渲染
3. 悬停任意卡片，上下游高亮正确（橙色=上游，蓝色=下游）
4. 点击"只看主线"，关键路径正确提取，支线折叠到 `+N 支线` 徽标
5. 卡片类型徽标、端侧、子卡链进度、ready 标记都能正确显示
6. 纵向/横向布局切换正常，画布尺寸自适应
7. 四轴类型系统的所有枚举值（7+4+3+6=20 个）都有对应的视觉表现

## 相关资料

- 数据来源：`docs/requirements/*/queue.json`（全仓 51 份队列文件）
- 参考实现：`packages/web/dsh-pmboard/client/src/pages/board/node-panel.ts`
- 样式文件：`packages/web/dsh-pmboard/client/src/pages/board/styles/node-panel.ts`
- 原型图：`docs/requirements/REQ-260928001915-f978/prototype.html`（已实现的可视化原型）

## 数据契约

### queue.json 关键字段

任务卡片消费以下字段：

```typescript
interface Task {
  id: string;              // 任务 ID
  title: string;           // 任务标题
  phase: Phase;            // 任务类型（7 类枚举）
  side: Side;              // 端侧（4 类枚举）
  status: Status;          // 状态（6 类枚举）
  dependsOn?: string[];    // 依赖的任务 ID 列表
  layer?: number;          // 所在层级（用于布局）
  
  // 父卡/子卡专属
  role?: 'parent' | 'child' | 'solo';  // 角色
  stageKind?: 'dev' | 'integrate' | 'review' | 'test';  // 子卡所属阶段
  kids?: Array<{           // 父卡的子卡链
    stageKind: string;
    status: Status;
  }>;
}

interface Queue {
  tasks: Task[];
  layers: string[][];      // 分层结果（用于布局）
  edges: Array<{           // 边线
    from: string;
    to: string;
  }>;
}
```

### 类型枚举定义

```typescript
type Phase = 'implement' | 'test' | 'doc' | 'review' | 'ui' | 'analysis' | 'merge';
type Side = 'backend' | 'frontend' | 'fullstack' | 'doc';
type Role = 'parent' | 'child' | 'solo';
type Status = 'todo' | 'in_progress' | 'integrating' | 'testing' | 'in_review' | 'done';
```

## RTM 追溯快照（FR-8 · brainstorming · full）

- 下一步建议：等待需求产物确认（已提取 7 个功能点）

```json
{"status":{"artifacts":[{"kind":"requirement","path":"docs/requirements/REQ-260928001915-f978/requirement.md","confirmed":false}]},"outputs":{"requirements":["FR-1","FR-2","FR-3","FR-4","FR-5","FR-6","FR-7"]}}
```

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t1 |
| FR-2 | ✅ 已接收 | t2 |
| FR-3 | ✅ 已接收 | t3 |
| FR-4 | ✅ 已接收 | t4 |
| FR-5 | ✅ 已接收 | t6 |
| FR-6 | ✅ 已接收 | t5 |
| FR-7 | ✅ 已接收 | t7 |

> 无未接收条款（7 条全部有落点）。

<!-- reqboard:marks:end -->
