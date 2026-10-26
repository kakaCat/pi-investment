# t-bb04d8 evolution_run 降级 null 键剔除与契约用例

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
evolution_run 降级 null 键剔除与契约用例

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
cd agent-dh && npx vitest run apps/web/tests/evolution-qv2-contract.test.ts 全绿（C4 断言 data_source==='degraded'、degraded_reason 原文保留、四键 in 判定均为 false；既有 REAL_RUN/DEGRADED_RUN 用例继续全绿）；npx vitest run apps/web/tests/plugin-schema.smoke.test.ts 全绿

## 实施方案（implementation）
在 EvolutionRunTool.ts 的 normalizeRunResult（:26-47）现有 degraded_reason null 剔除之后，对白名单 ['best_params','best_metrics','fitness','fitness_improvement'] 做同款 null/undefined 整体剔除（不全局剔 null）。prompt.ts output schema 零改动。在 evolution-qv2-contract.test.ts 新增 C4 用例：mock 用线上 _degraded_run 真实形状（显式 bestParams/bestMetrics/fitness/fitnessImprovement: null，strategy_evolution_service.py:487-505），断言输出中四键不存在、data_source==='degraded'、degraded_reason 保留。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
