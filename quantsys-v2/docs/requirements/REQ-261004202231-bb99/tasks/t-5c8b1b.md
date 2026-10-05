# t-5c8b1b 删除 v2 记忆端点与仓储

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
删除 v2 记忆端点与仓储

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
① curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:5001/api/memory/search → 返回 404；② 同法请求 /api/memory/health → 返回 404。

## 实施方案（implementation）
删 adapters/inbound/fastapi_app/routes/memory_async.py 与 memory_distill_async.py；删 adapters/outbound/repositories/memory_repository.py 与 memory_recall_audit_repository.py。

## 上游产出摘要（dependsSummary）
- 摘除 v2 记忆路由注册点

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
