# t-e64f6e 删除 domain/memory 领域实现

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
删除 domain/memory 领域实现

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
① grep -rn 'MemoryService|MemoryRepository|domain.memory' domain/ application/ adapters/ infrastructure/ → 返回 0 命中；② 重启 v2 后启动日志不含 ImportError。

## 实施方案（implementation）
删 domain/memory/ 目录（service.py、hybrid_search.py、embedding.py、distiller.py、models.py、__init__.py）；删前先跑反向断言确认无残留引用。

## 上游产出摘要（dependsSummary）
- 删除 v2 记忆端点与仓储

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
