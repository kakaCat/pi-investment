# t-3fa90a unpositioned_engine 非持仓判定

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
unpositioned_engine 非持仓判定

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/v2/test_unpositioned_engine.py -q 退出码 0；买点触发断言 notified=true；未触断言无通知

## 实施方案（implementation）
新建 v2/unpositioned_engine.py：evaluate→entry 买点触发/观察。验证：买点触发/未触不触发单测。

## 上游产出摘要（dependsSummary）
- v2 引擎骨架：主循环 + 加载 + 统一取价前置

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
