# t-e4e9db 实现边线渲染器

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现边线渲染器

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：frontend

## 得到什么结果
运行 `npx tsc demo/edge-renderer.ts --noEmit` 编译通过；`grep 'strokeStyle' demo/edge-renderer.ts | wc -l` 返回至少 3 行（验证有多种颜色逻辑）；文件包含 rgba(52,199,89 和 rgba(0,113,227 颜色代码。

## 实施方案（implementation）
编写 edge-renderer.ts，实现 renderEdges 函数，根据任务状态给连线着色：from/to 都 done=绿色（rgba(52,199,89,.5)，1.3px）；默认=灰色（rgba(0,0,0,.17)，1.2px）；关键路径=蓝色（rgba(0,113,227,.75)，1.8px）。支持传入关键路径节点集合。接收 FR-4。

## 上游产出摘要（dependsSummary）
- 实现 DAG 布局引擎

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
