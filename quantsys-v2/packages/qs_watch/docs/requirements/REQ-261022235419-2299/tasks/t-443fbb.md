# t-443fbb 失效判定模块（全票覆盖）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
失效判定模块（全票覆盖）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/v2/test_invalidation.py -q 退出码 0；六边界断言全过（超阈标 invalid/止损豁免/未超阈/NULL fail-open/持仓/未持仓同覆盖）

## 实施方案（implementation）
新建 v2/invalidation.py：偏离计算（|现价−阈值|/阈值 > invalidation_threshold_pct）→标 invalid+留痕+投递（先 stub notify_agent）；止损豁免。验证：六边界单测（沿用今日验证口径）。

## 上游产出摘要（dependsSummary）
- v2 引擎骨架：主循环 + 加载 + 统一取价前置

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
