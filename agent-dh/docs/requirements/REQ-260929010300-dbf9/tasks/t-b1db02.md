# t-b1db02 会话面板挂载钩子（DOM 就绪后挂载）·研发

> 需求：REQ-260929010300-dbf9 流程节点面板的 DAG 改用与需求详情一致的 Canvas 真图

## 在做什么
会话面板挂载钩子（DOM 就绪后挂载）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

cd packages/web/dsh-pmboard && npx tsc --noEmit -p tsconfig.json → 本次涉及文件 0 error；cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts tests/client-view.test.ts → 全绿；git diff --stat 可见本卡改动文件（mtime ≥ 链出身）

## 汇报 1（2026-09-28T18:19:39.442Z，窗口 session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e）

完成 t-b1db02（会话面板挂载钩子·研发）：在 packages/web/dsh-pmboard/src/client/conversation-progress.ts 中落盘 Canvas DAG 挂载 useEffect——依赖 [detailOpen, selectedStage, stageOverview]，stageKey = selectedStage ?? stageOverview.currentStage，仅当阶段为 implementing / decomposing 时从 stageOverview.stages.find(...).body.tasks 取任务，阶段缺失 / 任务缺失或为空一律不调用，命中时调 tryMountDagCanvas(tasks, undefined, PANEL_DAG_CANVAS_ID)（不传 ready，对齐 FR-7 统计条标「推导」；canvasId 用面板专用常量与需求详情 #dag-canvas 隔离）；顶部已引入 tryMountDagCanvas（./dag-mount.ts）与 PANEL_DAG_CANVAS_ID（./views/dag-view.js）。本轮把原先嵌套三元（两分支同值）规范为显式二阶段判断并补注释，语义不变、类型收窄不变。effect 位于组件早退之前（Hooks 顺序安全），面板 HTML 由同一 commit 注入后 effect 执行，rAF + getElementById 保证 DOM 未就绪时静默。

### 完成项

- 完成 t-b1db02（会话面板挂载钩子·研发）：在 packages/web/dsh-pmboard/src/client/conversation-progress.ts 中落盘 Canvas DAG 挂载 useEffect——依赖 [detailOpen, selectedStage, stageOverview]，stageKey = selectedStage ?? stageOverview.currentStage，仅当阶段为 implementing / decomposing 时从 stageOverview.stages.find(...).body.tasks 取任务，阶段缺失 / 任务缺失或为空一律不调用，命中时调 tryMountDagCanvas(tasks, undefined, PANEL_DAG_CANVAS_ID)（不传 ready，对齐 FR-7 统计条标「推导」；canvasId 用面板专用常量与需求详情 #dag-canvas 隔离）；顶部已引入 tryMountDagCanvas（./dag-moun

### 改动文件

- `packages/web/dsh-pmboard/src/client/conversation-progress.ts`

---
