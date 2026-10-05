# t-cc1a66 删除记忆测试（10 文件）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
删除记忆测试（10 文件）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
① pytest tests/ -q --collect-only 后 grep -c domain/memory → 返回 0；② 用例总数与基线之差等于被删用例数（一致）。

## 实施方案（implementation）
删 tests/domain/memory/ 目录（含 __init__.py）；删前记录 pytest --collect-only 的总数作为基线。

## 上游产出摘要（dependsSummary）
- 删除 domain/memory 领域实现

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
