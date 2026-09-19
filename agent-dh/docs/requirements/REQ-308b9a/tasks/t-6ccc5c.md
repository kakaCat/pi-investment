# t-6ccc5c 看板「退回返工」收敛为等价入口

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
看板「退回返工」收敛为等价入口

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑 pnpm --filter dsh-pmboard test 的 T-E4，断言看板 rework 与自动回退行为一致（同一 use-case 调用）。

## 实施方案（implementation）
src/http/routers/verdicts.ts 的 rework 端点复用自动回退 use-case，删除独立分支，避免双实现漂移。

## 上游产出摘要（dependsSummary）
- FR-8 验收失败自动回退实施（application）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
