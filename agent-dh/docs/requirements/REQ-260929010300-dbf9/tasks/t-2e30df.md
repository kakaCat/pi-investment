# t-2e30df 画布 id 参数化 + 挂载实例表·联调

> 需求：REQ-260929010300-dbf9 流程节点面板的 DAG 改用与需求详情一致的 Canvas 真图

## 在做什么
画布 id 参数化 + 挂载实例表·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿；grep -n "disposers" packages/web/dsh-pmboard/src/client/views/dag-view.ts → 有命中（本卡接线确实在源码里）

## 汇报 1（2026-09-28T18:19:38.542Z，窗口 session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e）

接口联调通过：按本卡验收「请求样例 + 期望响应 vs 实际返回」实测 11/11 一致（exit 0，allPass=true），源码级（tsx 直载 TS）与产物级（browser 实际加载的 lib/client.js 静态核对）双向确认。①buildDagCanvas(tasks, containerId, canvasId) 产出的 <canvas id> 与 tryMountDagCanvas(tasks, ready?, canvasId) 查找/挂载的 id 两侧同源：需求详情 wire（stage-detail.ts:315 buildDagCanvas(tasks,'dag-canvas-container') ↔ board-mount.ts:263 tryMountDagCanvas(reqTasks, reqReady)，canvasId 走缺省 dag-canvas）与会话面板 wire（node-panel.ts:176/236 传 PANEL_DAG_CANVAS_ID ↔ conversation-progress.ts:289 传同一常量 np-dag-canvas）均实测挂载成功；②实例表 Map 后两画布互不释放、同 id 重挂只释放同名条目、画布被换掉/只剩子卡时先回收同名旧条目（ResizeObserver disconnect，不泄漏）、目标画布不存在时静默 no-op；③双击卡片经 openTaskDetail(taskId, canvasId) 用本画布的 parentElement 作锚点派发 open-task 事件，实测 payload={action:open-task,task:t-p1}。仅发现 1 处产物与源码不同步（释放顺序，详见 issues），属构建同步问题、不改本卡接口契约，故判 pass。

### 完成项

- 接口联调通过：按本卡验收「请求样例 + 期望响应 vs 实际返回」实测 11/11 一致（exit 0，allPass=true），源码级（tsx 直载 TS）与产物级（browser 实际加载的 lib/client.js 静态核对）双向确认。①buildDagCanvas(tasks, containerId, canvasId) 产出的 <canvas id> 与 tryMountDagCanvas(tasks, ready?, canvasId) 查找/挂载的 id 两侧同源：需求详情 wire（stage-detail.ts:315 buildDagCanvas(tasks,'dag-canvas-container') ↔ board-mount.ts:263 tryMountDagCanvas(reqTasks, reqReady)，canvasId 走缺省 dag-canvas）与会话面板 wire（node-panel.ts:176/236 传 PANEL_DAG_CANVAS_ID ↔ conversation-progres

---
