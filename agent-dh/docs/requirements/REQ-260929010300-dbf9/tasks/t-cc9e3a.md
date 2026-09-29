# t-cc9e3a 定契约：入参结构类型收敛 + 面板画布常量·复核

> 需求：REQ-260929010300-dbf9 流程节点面板的 DAG 改用与需求详情一致的 Canvas 真图

## 在做什么
定契约：入参结构类型收敛 + 面板画布常量·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-09-28T18:19:38.156Z，窗口 session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e）

复核对象：t-d03789/t-cc9e3a（定契约：入参结构类型收敛 + 面板画布常量·复核）。逐条比对「设计（design/data-model.md §入参结构类型收敛不伪造、design/interfaces.md §三个入口签名/常量、本卡 implementation）」与「实现（packages/web/dsh-pmboard/src/client/views/dag-view.ts）」，结论如下：
① DagTaskLike 定义与导出：无偏离。dag-view.ts:60-71 为 export interface，必填 id/title/status/phase/side/dependsOn，可选 parentId/stageKind/cardDoc，与设计字段集逐字一致（cardDoc 当前绘制不消费，符合设计「保留字段以便两入参互换」）。
② 三入口入参收敛：无偏离。buildDagData:158 / buildDagCanvas:235 / mountDagCanvas:312 入参均为 DagTaskLike[]；全文件 grep「TaskRecord」仅命中 4 处注释（L10/57/58/152），无任何 TaskRecord 类型引用。
③ 面板画布常量：无偏离。dag-view.ts:51-52 export const PANEL_DAG_CONTAINER_ID = 'np-dag-canvas-container'、PANEL_DAG_CANVAS_ID = 'np-dag-canvas'，取值与导出要求逐字一致（单一常量源）。
④ 签名与新参可选：无偏离。buildDagCanvas(tasks, containerId='dag-canvas-container', canvasId=…) 与 mountDagCanvas(tasks, ready?, canvasId=…) 的新增参数均带缺省值（可选）；canvasId 缺省以模块常量 DAG_CANVAS_ID（L44='dag-canvas'）表达，值恒等于设计缺省 'dag-canvas'，行为等价。
⑤ ready 两态语义：无偏离。buildDagData(tasks, ready?: readonly string[]) 保留 readonly string[]|undefined；L201 fromQueue = ready !== undefined、L223 readySource 区分 queue/derived，与设计「undefined=推导、空数组=队列确实无卡」一致。
⑥ 缺省即旧行为 + 不改调用方：无偏离。缺省产出 id="dag-canvas-container" 与 id="dag-canvas"（tests/dag-view.test.ts:271-283 已断言）；需求详情调用方 views/stage-detail.ts:315 buildDagCanvas(tasks, 'dag-canvas-container') 与新签名兼容且该文件 mtime 2026-09-29T00:04:28 早于本卡编辑窗（01:28:25），确未被本卡触碰；结构上 TaskRecord（protocol.ts:1167-1233 / client/types.ts:209-245）与 StageTaskRef（protocol.ts:390-416）均含 6 个必填字段，可赋给 DagTaskLike，故收敛不迫使调用方改动。
⑦ 不改挂载生命周期：无偏离（依据为声明+契约一致性）。dev 报告（queue.json:738-747）声明 disposers Map 实例表与 openTaskDetail(canvasId) 保持原样、filesChanged 仅 dag-view.ts 与 tests/dag-view.test.ts；且该 Map 正是 data-model.md L14 规定的目标不变量，与设计无冲突。附注（非缺陷，2 条）：(a) dag-view.ts 未被 git 跟踪（git ls-files --error-unmatch 失败、git status 为 ??），无基线 diff，「未改挂载生命周期/未改调用方」无法做代码级独立验证，仅能依赖 dev 报告与 mtime 归属（node-panel.ts 01:28:44、conversation-progress.ts

### 完成项

- 复核对象：t-d03789/t-cc9e3a（定契约：入参结构类型收敛 + 面板画布常量·复核）。逐条比对「设计（design/data-model.md §入参结构类型收敛不伪造、design/interfaces.md §三个入口签名/常量、本卡 implementation）」与「实现（packages/web/dsh-pmboard/src/client/views/dag-view.ts）」，结论如下：
① DagTaskLike 定义与导出：无偏离。dag-view.ts:60-71 为 export interface，必填 id/title/status/phase/side/dependsOn，可选 parentId/stageKind/cardDoc，与设计字段集逐字一致（cardDoc 当前绘制不消费，符合设计「保留字段以便两入参互换」）。
② 三入口入参收敛：无偏离。buildDagData:158 / buildDagCanvas:235 / mountDagCanvas:312 入参均为 DagTaskLike[]；全

---
