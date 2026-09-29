# t-1fadb6 定契约：入参结构类型收敛 + 面板画布常量·联调

> 需求：REQ-260929010300-dbf9 流程节点面板的 DAG 改用与需求详情一致的 Canvas 真图

## 在做什么
定契约：入参结构类型收敛 + 面板画布常量·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

cd packages/web/dsh-pmboard && npx vitest run tests/dag-view.test.ts → 全绿；grep -n "PANEL_DAG_CANVAS_ID" packages/web/dsh-pmboard/src/client/views/dag-view.ts → 有命中（本卡接线确实在源码里）

## 汇报 1（2026-09-28T18:19:38.030Z，窗口 session-9e82f8c1-635e-458c-9df0-ff9aba1ae00e）

联调通过：dag-view.ts 的 DagTaskLike 入参收敛与两个面板画布常量已在真实调用中生效，12/12 断言与期望逐字一致。① buildDagData 接受仅含 6 个必填字段的最小对象（面板侧 StageTaskRef 子集），子卡折叠、依赖重路由（传递归约）、队列 ready 上提父卡均按预期；② buildDagCanvas 缺省仍为 dag-canvas-container/dag-canvas，显式传 PANEL_DAG_CONTAINER_ID/PANEL_DAG_CANVAS_ID 时输出 np-dag-canvas-container/np-dag-canvas 且不残留缺省 id，空任务空态不变；③ mountDagCanvas 第 3 参 canvasId 与新可选 ready 真实透传到 document.getElementById；④ 跨模块真实调用方 renderNodePanel(implementing/decomposing) 与 tryMountDagCanvas 均按面板常量挂载、零异常。类型侧 tsc 探针退出 0：最小入参可编过，3 个反向用例（缺 phase/side/dependsOn、dependsOn 非 string[]、多余字段）全部按契约报错。附注（非缺陷）：DagTaskLike 的 phase/side 声明为 string，进入 CardData 时是无校验类型断言，运行时依赖调用方传受控枚举。

### 完成项

- 联调通过：dag-view.ts 的 DagTaskLike 入参收敛与两个面板画布常量已在真实调用中生效，12/12 断言与期望逐字一致。① buildDagData 接受仅含 6 个必填字段的最小对象（面板侧 StageTaskRef 子集），子卡折叠、依赖重路由（传递归约）、队列 ready 上提父卡均按预期；② buildDagCanvas 缺省仍为 dag-canvas-container/dag-canvas，显式传 PANEL_DAG_CONTAINER_ID/PANEL_DAG_CANVAS_ID 时输出 np-dag-canvas-container/np-dag-canvas 且不残留缺省 id，空任务空态不变；③ mountDagCanvas 第 3 参 canvasId 与新可选 ready 真实透传到 document.getElementById；④ 跨模块真实调用方 renderNodePanel(implementing/decomposing) 与 tryMountDagCanvas 均按面板常量挂载、零异常。类

---
