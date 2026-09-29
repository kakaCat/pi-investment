# 拆分计划（REQ-260928001915-f978）

## 目标

完成队列 DAG 真图的卡片类型定义和可视化方案设计，使 DAG 图可读性提升、信息层次清晰。

## 做法

按照设计文档，将 7 个功能点拆分成 8 张任务卡：
1. **类型系统定义**（FR-1）- 定义四轴枚举与颜色映射
2. **卡片样式实现**（FR-2）- 实现 7 个视觉元素的渲染
3. **DAG 布局引擎**（FR-3）- 实现真实 DAG 的节点布局与连线
4. **边线着色逻辑**（FR-4）- 根据任务状态分层着色
5. **关键路径算法**（FR-6）- 计算最长路径并标记
6. **悬停交互**（FR-5）- 实现高亮与 dimming 效果
7. **父卡子卡链**（FR-7）- 实现 4 段进度条
8. **集成测试与文档**（验收）- 端到端验证与使用文档

## 代码改动盘点

### 新增文件

1. `demo/card-types.ts` - 类型定义（FR-1）
2. `demo/card-renderer.ts` - 卡片渲染器（FR-2）
3. `demo/dag-layout.ts` - DAG 布局引擎（FR-3）
4. `demo/edge-renderer.ts` - 边线渲染器（FR-4）
5. `demo/critical-path.ts` - 关键路径算法（FR-6）
6. `demo/interaction.ts` - 交互处理器（FR-5）
7. `demo/progress-bar.ts` - 子卡链进度条（FR-7）
8. `demo/integration.ts` - 主集成模块

### 修改文件

1. `demo/build-demo.py` - 更新构建脚本，集成新模块
2. `demo/template.html` - 更新 HTML 模板，加载新的 JS 模块

### 数据文件

- 消费现有的 `queue.json` 文件（不修改数据结构）
- 读取真实队列文件测试（小图 12 卡、中图 20 卡、压力图 65 卡）


## FR 覆盖对照表

| 需求条款 | 功能描述 | 接收任务 |
|---------|---------|---------|
| FR-1 | 卡片四轴类型系统 | t1 |
| FR-2 | 卡片视觉规范 | t2 |
| FR-3 | 真实 DAG 布局 | t3 |
| FR-4 | 边线分层着色 | t4 |
| FR-5 | 悬停交互 | t6 |
| FR-6 | 关键路径计算 | t5 |
| FR-7 | 父卡子卡链 | t7 |

**覆盖说明**：
- 所有 FR-1 至 FR-7 都被任务卡接收
- t8（集成测试）验证全部功能点的端到端集成
- 无孤儿条款

## 任务表

```json
[
  {
    "key": "t1",
    "title": "定义卡片四轴类型系统",
    "phase": "doc",
    "side": "doc",
    "depends_on": [],
    "requirement_refs": ["FR-1"],
    "implementation": "编写 card-types.ts 文件，定义四轴枚举（Phase/Side/Role/Status）、颜色映射表（7+4+6 种颜色）、状态底色表。导出 TypeScript 类型定义和常量。",
    "acceptance": "运行 `npx tsc demo/card-types.ts --noEmit` 编译通过；枚举值总数 = 7+4+3+6=20 个；每个 phase 有对应的颜色代码（如 implement=#5856D6）。"
  },
  {
    "key": "t2",
    "title": "实现卡片样式渲染器",
    "phase": "implement",
    "side": "frontend",
    "depends_on": ["t1"],
    "requirement_refs": ["FR-2"],
    "implementation": "编写 card-renderer.ts，实现 renderCard 函数，根据任务数据渲染 7 个视觉元素：ID、类型徽标、端侧徽标、标题、状态底色、父卡标识（左侧蓝条）、ready 绿点。卡片尺寸 208×72px，支持传入位置坐标。",
    "acceptance": "调用 `renderCard({ id: 't1', title: 'Test', phase: 'implement', side: 'backend', status: 'done', role: 'parent' }, 100, 100)` 在画布上正确绘制卡片，左侧有蓝条，底色为浅绿色（done 状态）。"
  },
  {
    "key": "t3",
    "title": "实现 DAG 布局引擎",
    "phase": "implement",
    "side": "frontend",
    "depends_on": ["t2"],
    "requirement_refs": ["FR-3"],
    "implementation": "编写 dag-layout.ts，实现 calculateLayout 函数，消费 queue.json 的 layers 和 tasks 数据，支持纵向/横向两种布局方向。纵向：按层级从上到下，同层折行；横向：按层级从左到右，同层纵向堆叠。返回每个节点的 (x, y) 坐标和画布尺寸。",
    "acceptance": "用测试数据（12 卡，3 层）调用 `calculateLayout(tasks, layers, 'vertical')`，返回 12 个节点坐标，同层节点 y 值相同；切换到 'horizontal' 模式，同层节点 x 值相同。"
  },
  {
    "key": "t4",
    "title": "实现边线渲染器",
    "phase": "implement",
    "side": "frontend",
    "depends_on": ["t3"],
    "requirement_refs": ["FR-4"],
    "implementation": "编写 edge-renderer.ts，实现 renderEdges 函数，根据任务状态给连线着色：from/to 都 done=绿色（rgba(52,199,89,.5)，1.3px）；默认=灰色（rgba(0,0,0,.17)，1.2px）；关键路径=蓝色（rgba(0,113,227,.75)，1.8px）。支持传入关键路径节点集合。",
    "acceptance": "调用 `renderEdges(edges, nodePositions, taskStatusMap, criticalPathSet)`，在画布上绘制边线，已完成链路为绿色，关键路径为蓝色加粗，其余为灰色。"
  },
  {
    "key": "t5",
    "title": "实现关键路径算法",
    "phase": "implement",
    "side": "backend",
    "depends_on": ["t3"],
    "requirement_refs": ["FR-6"],
    "implementation": "编写 critical-path.ts，实现 findCriticalPath 函数，使用拓扑排序 + 动态规划计算 DAG 的最长路径。从入度为 0 的节点开始，计算到每个节点的最长路径长度，回溯得到关键路径节点集合。返回 Set<taskId>。",
    "acceptance": "用测试 DAG（6 节点，2 条路径：1→2→3→6 长度 3，1→4→5→6 长度 3）调用 `findCriticalPath(tasks, edges)`，返回其中一条长度为 3 的路径节点集合。"
  },
  {
    "key": "t6",
    "title": "实现悬停交互处理器",
    "phase": "implement",
    "side": "frontend",
    "depends_on": ["t4"],
    "requirement_refs": ["FR-5"],
    "implementation": "编写 interaction.ts，实现 setupInteraction 函数，监听 canvas 的 mousemove 和 click 事件。悬停时高亮上游（橙色）和下游（蓝色）边线，未高亮元素 dimming（透明度 0.18/0.05），当前卡片加黑边框和阴影。点击钉住状态，再次点击或点击画布取消。",
    "acceptance": "在浏览器中打开生成的 HTML，鼠标移到任意卡片上，上下游边线高亮正确，背景变暗；点击卡片保持高亮，点击空白处取消。"
  },
  {
    "key": "t7",
    "title": "实现父卡子卡链进度条",
    "phase": "implement",
    "side": "frontend",
    "depends_on": ["t2"],
    "requirement_refs": ["FR-7"],
    "implementation": "编写 progress-bar.ts，实现 renderProgressBar 函数，在父卡底部绘制 4 段进度条（dev/integrate/review/test），每段根据子卡状态着色：已完成=绿色、进行中=蓝色、待开始=灰色。显示进度文本 '已完成数/总数'。",
    "acceptance": "调用 `renderProgressBar(parentTask, 10, 60, 188)`（父卡有 4 个子卡，2 个 done、1 个 in_progress、1 个 todo），在指定位置绘制进度条，前 2 段绿色、第 3 段蓝色、第 4 段灰色，文本显示 '2/4'。"
  },
  {
    "key": "t8",
    "title": "集成测试与文档",
    "phase": "test",
    "side": "fullstack",
    "depends_on": ["t6", "t7"],
    "requirement_refs": ["FR-1", "FR-2", "FR-3", "FR-4", "FR-5", "FR-6", "FR-7"],
    "implementation": "编写 integration.ts，集成所有模块，实现主渲染流程。更新 build-demo.py 和 template.html，加载所有 JS 模块。用真实队列文件（小图 12 卡、中图 20 卡、压力图 65 卡）测试。编写 README.md 说明使用方法。",
    "acceptance": "运行 `python3 docs/requirements/REQ-260928001915-f978/demo/build-demo.py`，生成 dag-card-types-demo.html；在浏览器打开，三档数据集都能正确渲染；悬停交互、关键路径、子卡链进度都正常工作；纵向/横向布局切换正常。"
  }
]
```

## 依赖关系

```
t1 (类型系统)
 ├─→ t2 (卡片样式)
 │    ├─→ t3 (DAG 布局)
 │    │    ├─→ t4 (边线着色) ─→ t6 (悬停交互) ─┐
 │    │    └─→ t5 (关键路径) ───────────────────┤
 │    └─→ t7 (子卡链进度) ──────────────────────┤
 │                                              ↓
 └──────────────────────────────────────────→ t8 (集成测试)
```

## 验收门禁

1. **FR 覆盖完整性**：所有 FR-1 到 FR-7 都至少被一个任务接收
2. **类型安全**：所有 TypeScript 文件编译通过（`npx tsc --noEmit`）
3. **功能验证**：三档数据集（12/20/65 卡）都能正确渲染
4. **交互验证**：悬停高亮、点击钉住、关键路径、布局切换都正常工作
5. **视觉验证**：四轴类型的 20 个枚举值都有对应的视觉表现

## 风险与缓解

- **风险 1**：Canvas 性能问题（65 卡 + 边线可能卡顿）
  - 缓解：先实现基础功能，性能优化作为后续改进
- **风险 2**：真实队列数据结构变化
  - 缓解：按照现有 queue.json 契约实现，兼容层在 integration.ts 处理
- **风险 3**：浏览器兼容性
  - 缓解：使用标准 Canvas API，避免实验性特性

## 交付清单

1. 8 个 TypeScript 源文件（demo/*.ts）
2. 更新的构建脚本（build-demo.py）
3. 更新的 HTML 模板（template.html）
4. 生成的演示页面（dag-card-types-demo.html）
5. 使用文档（README.md）
