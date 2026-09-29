# 架构视角 · REQ-260929010300-dbf9 设计 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7`

> 轻档设计：每节够用即止；接口签名与数据契约分别见 interfaces.md / data-model.md。
> 参照系 = **会话流程节点面板的 np 苹果风皮肤**（2026-09-29 用户订正，见 requirement.md 头部）。

## 现状与目标 `serves: FR-1, FR-2, FR-6`

两条 DAG 展示路径并存：需求详情走 `views/dag-view.ts` 的 `buildDagCanvas` + `mountDagCanvas`（Canvas 真图，
皮肤 `styles/dag.ts` 的 `DAG_CSS`，取值引用 `--dsw-*` 主题变量）；会话流程节点面板走 `node-panel.ts` 的 `renderDag`
（按层分组卡片列表，皮肤 `styles/node-panel.ts` 的 `NODE_PANEL_CSS`，`--dsh-pm-np-*` 苹果风令牌）——观感不同源。

目标：两处共用**同一个面板构建函数**与**同一套 np 苹果风皮肤**，会话面板的 DAG 换成 Canvas 真图；
画布内卡片绘制（`dag/card-renderer.ts`）与 `dag/*` 渲染语义（折叠 / 传递归约 / 箭头分级）零改动。
（2026-09-29 裁定 D 例外一处：`card-renderer.ts` 删除**父卡左侧蓝条**，使 DAG 卡片与泳道卡片外观一致。）

## 模块职责与数据流 `serves: FR-1, FR-2, FR-3, FR-5`

- `client/views/dag-view.ts`：数据桥（`buildDagData`）+ 面板骨架（`buildDagCanvas`）+ 挂载（`mountDagCanvas`：工具条 / 统计 / ResizeObserver / 双击开卡）——本次唯一的功能改动点。
- `client/dag-mount.ts`：`tryMountDagCanvas`（rAF + 存在性检查 + catch），透传 `canvasId`。
- `client/node-panel.ts`：只**调用**构建器产出 HTML 字符串，不再自己画 DAG（`renderDag` 保留函数但不再被调用）。
- `client/conversation-progress.ts`：面板渲染后的挂载钩子（useEffect）。

数据流：`StageOverview` / `BoardState` → 任务数组（`StageTaskRef[]` 或 `TaskRecord[]`）→ `buildDagData`
（`collapseToCardLevel` 折叠卡片层 + `reduceEdges` 传递归约）→ `createDagViewer` → `<canvas>`。两处同一条数据流，
差异只在「传不传队列 `ready[]`」。

竖向布局自 2026-09-29 裁定 C 起**不折行**：每层一行、画布按最宽层展开、容器窄则横向滚动（`availW` 仅作最小宽度）。

## 皮肤真源与迁移 `serves: FR-6`

统一皮肤 = `NODE_PANEL_CSS` 已定义在 `:root` 的 `--dsh-pm-np-*` 令牌（`-text / -text2 / -text3 / -line / -line-soft /
-bg / -bg-hover / -blue`）。`DAG_CSS` 改写为引用该令牌集：泳道底色圆角面板、`#f5f5f7` 头块、980px 胶囊按钮、
轻阴影、8px 圆角滚动条——**类名保持不变**（`dsh-pm-dag-panel/-head/-sub/-seg/-btn/-canvas-wrap/-canvas/-legend`）。
2026-09-29 追加裁定 B（用户）：`-title` 与 `-flowstat` 连同其规则一并删除，两处同源同删。

因此：`styles.ts` 的拼接顺序不动；`scripts/verify-client-build.mjs` 的符号守卫（`dsh-pm-dag-panel`）无需改；
`tests/dag-view.test.ts`、`tests/client-view.test.ts` 的既有断言继续成立。
已知取舍：np 皮肤固定浅色，DAG 面板不再随明暗主题变化（用户 2026-09-29 追认）。

## 单例到多实例（挂载生命周期） `serves: FR-3, FR-4`

现状 `dag-view.ts` 用模块级单槽 `activeDispose`——第二次挂载会释放第一块画布，同页两实例必然互踩。
设计：改为 `Map<canvasId, () => void>` 的**实例表**，`disposeDagCanvas(canvasId)` 只释放同名条目；
`openTaskDetail(taskId, canvasId)` 用本实例的 canvasId 定位锚点。

挂载时机与自适应沿用既有机制：`requestAnimationFrame` 后查 `getElementById(canvasId)`（不存在即静默返回）；
`ResizeObserver` 监听画布容器宽度，宽度真变才重画（面板从 `display:none` 转可见、侧栏开合、窗口缩放都覆盖）。
