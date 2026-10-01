# t-4f6f4b 消 application 层 12 处顶层越层导入

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
消 application 层 12 处顶层越层导入

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑 `venv/bin/python tools/analyze_layer_violations.py | grep 违规导入总数` 顶层部分降为 0；`grep -rn "^from infrastructure.notification.channels" application/` 为 0；`pytest tests/notification -q` 通过。

## 实施方案（implementation）
12 处顶层越层导入改为经 port/工厂注入或按裁定口径下沉；application/notification/notification_factory.py:20,28,29,30 的 infrastructure.config.settings 与 notification.channels.* 顶层导入移至 infrastructure 侧装配；删除 application/services/scheduler.py 的 `from infrastructure.scheduler.scheduler import *` 通配壳。

## 上游产出摘要（dependsSummary）
- 挂上分层护栏（hook + 基线 + 纯净性断言）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
