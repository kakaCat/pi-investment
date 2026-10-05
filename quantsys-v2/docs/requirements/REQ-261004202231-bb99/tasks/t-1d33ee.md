# t-1d33ee 摘除 v2 记忆路由注册点

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
摘除 v2 记忆路由注册点

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
① 对 v2 启动日志 logs/launchd-api.log 执行 grep -c 'Registered: memory' → 返回 0；② 同一日志 grep 'optional_failed' 的条目与删除前一致（不变）；③ 复核 adapters/inbound/fastapi_app/main.py 不含 memory 字面量。

## 实施方案（implementation）
改 adapters/inbound/fastapi_app/route_registrar.py:278-279；改 adapters/inbound/fastapi_app/main.py:1067-1083；重启 v2 后核对日志。

## 上游产出摘要（dependsSummary）
- 摘除外部三处记忆消费方

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
