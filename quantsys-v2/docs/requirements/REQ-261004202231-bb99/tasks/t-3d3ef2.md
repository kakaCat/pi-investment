# t-3d3ef2 文档落档：v2 不再承载记忆

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
文档落档：v2 不再承载记忆

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：doc
- 端侧：doc

## 得到什么结果
① 执行 python3 agent-dh/scripts/wiki_probe.py → 无新增死链/孤儿；② 落档文档中包含「记忆由 agent 侧承载」与 REQ-261004202231-bb99。

## 实施方案（implementation）
在 quantsys-v2/docs/architecture/ 下新增或追加一节：写明 v2 侧记忆子系统已下线、消费方摘除清单、以及「记忆归 agent 侧」的口径。

## 上游产出摘要（dependsSummary）
- 删除记忆测试（10 文件）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
