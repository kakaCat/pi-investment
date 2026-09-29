# 接口视角 · REQ-260929010300-dbf9 设计 `serves: FR-1, FR-2, FR-3, FR-4, FR-5`

## 三个入口签名 `serves: FR-1, FR-2, FR-3`

| 入口 | 签名 | 返回 | 错误语义 |
|---|---|---|---|
| 构建面板 HTML | `buildDagCanvas(tasks, containerId?, canvasId?)` | 面板 HTML 字符串 | 空任务 → 空态占位串；无副作用 |
| 挂载 | `mountDagCanvas(tasks, ready?, canvasId?)` | `DagViewer \| undefined` | 找不到画布或顶层卡为空 → `undefined`（不抛） |
| DOM 就绪后挂载 | `tryMountDagCanvas(tasks, ready?, canvasId?)` | `void` | 内部 catch 并 `console.error`，不打断宿主渲染 |

缺省值：`containerId = 'dag-canvas-container'`、`canvasId = 'dag-canvas'`——**缺省即旧行为**，
需求详情调用方（`views/stage-detail.ts` 的 `buildDag`）一行不改。

## 常量与调用方契约 `serves: FR-1, FR-2, FR-3`

- 从 `views/dag-view.ts` 导出 `PANEL_DAG_CONTAINER_ID` 与 `PANEL_DAG_CANVAS_ID`（会话面板专用）——**单一常量源**，
  `node-panel.ts` 与 `conversation-progress.ts` 共用，禁止两处各写一份字面量。
- `node-panel.ts`（纯字符串渲染器）：两处 DAG 块改为 `buildDagCanvas(tasks, PANEL_DAG_CONTAINER_ID, PANEL_DAG_CANVAS_ID)`。
- `conversation-progress.ts`（React 宿主）：面板渲染后 `tryMountDagCanvas(tasks, undefined, PANEL_DAG_CANVAS_ID)`；
  `tasks` 取所选阶段的 `body.tasks`（拆分/实施），阶段或任务拿不到时不调用。
- 双击打开任务仍走既有 `data-action="open-task"` 委托，只是多带本实例 `canvasId`，不新开导航链路。

## DOM 与样式契约 `serves: FR-1, FR-6`

- DOM：面板根 `dsh-pm-dag-panel`（`id = containerId`）、画布 `<canvas id=canvasId class="dsh-pm-dag-canvas">`，
  钩子 `data-dag-dir / data-dag-toggle / data-dag-stat / data-dag-wrap` 全部照旧（挂载与交互靠它们定位）。
- 样式：类名零变更，取值来源换成 `--dsh-pm-np-*`；改完后 `styles/dag.ts` 内**不再出现 `--dsw-`**。
- 两处 DAG 面板的 DOM 类名集合逐项相同（同一构建函数产出，天然满足）。
