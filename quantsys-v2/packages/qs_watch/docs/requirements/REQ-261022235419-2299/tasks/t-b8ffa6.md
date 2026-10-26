# t-b8ffa6 v2 引擎骨架：主循环 + 加载 + 统一取价前置

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
v2 引擎骨架：主循环 + 加载 + 统一取价前置

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/v2/test_loader.py tests/v2/test_quote_first.py -q 退出码 0；取价集合==激活 symbol 集合断言通过

## 实施方案（implementation）
新建 v2/engine.py（WatchEngineV2：run_forever/tick）+ 两个测试文件。tick 内 list_by_state('active')→按 symbol 去重取价（复用 quote_service）。单测断言取价输入集合==激活 symbol 集合。验证：pytest 两文件退出码 0。

## 上游产出摘要（dependsSummary）
- 数据迁移：trigger_channel/process_state/cycle_count + engine 标记

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
