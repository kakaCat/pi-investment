# t-3ed4b5 会话面板挂载钩子（DOM 就绪后挂载）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
会话面板挂载钩子（DOM 就绪后挂载）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果

打开 :13080 会话右上角流程节点 → 实施阶段 [DAG] 页签可见画布（2026-09-29 裁定 B：无标题行 / 无统计条）；切到泳道再切回 [DAG] 画布仍存在；cd packages/web/dsh-pmboard && npx vitest run tests/node-panel.test.ts tests/client-view.test.ts 全绿

## 实施方案（implementation）
改 packages/web/dsh-pmboard/src/client/conversation-progress.ts：新增 useEffect（依赖 detailOpen / selectedStage / stageOverview），从 stageOverview.stages 取所选阶段，stage 为 implementing 或 decomposing 时读 body.tasks 并调 tryMountDagCanvas(tasks, undefined, PANEL_DAG_CANVAS_ID)；不传 ready（对齐 FR-7 标注「推导」），阶段或任务缺失时不调用。

## 上游产出摘要（dependsSummary）
- 画布 id 参数化 + 挂载实例表
- 会话面板两处 DAG 块改调同一构建函数

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
